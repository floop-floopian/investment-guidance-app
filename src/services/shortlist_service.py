import asyncio
import json
import logging
from typing import Any
from groq import Groq
from src.models.stock import Stock, BarbellClass
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


def _compute_risk_reward(stock: Stock, macro_aggregate: float) -> float:
    """Weighted composite score: 40% fundamentals, 40% technicals, 20% macro."""
    fund_score = 0.0
    fund_count = 0
    if stock.pe_ratio is not None:
        # Lower P/E → higher score (cap at P/E=50)
        fund_score += max(0.0, 1.0 - stock.pe_ratio / 50.0)
        fund_count += 1
    if stock.revenue_growth_yoy is not None:
        fund_score += min(1.0, max(0.0, stock.revenue_growth_yoy / 50.0))
        fund_count += 1
    if stock.dividend_yield is not None:
        fund_score += min(1.0, stock.dividend_yield / 5.0)
        fund_count += 1
    f = fund_score / fund_count if fund_count else 0.5

    tech_score = 0.0
    tech_count = 0
    if stock.momentum_90d is not None:
        tech_score += min(1.0, max(0.0, (stock.momentum_90d + 30) / 60))
        tech_count += 1
    if stock.rsi_14 is not None:
        # RSI 45–65 is ideal
        rsi_norm = 1.0 - abs(stock.rsi_14 - 55) / 55
        tech_score += max(0.0, rsi_norm)
        tech_count += 1
    t = tech_score / tech_count if tech_count else 0.5

    m = (macro_aggregate + 1.0) / 2.0  # normalise -1..1 → 0..1

    return round(0.40 * f + 0.40 * t + 0.20 * m, 4)


class ShortlistService:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = Groq(api_key=settings.groq_api_key)
        self._model = settings.groq_model

    async def _call_llm_reasoning(self, stock: Stock, macro_aggregate: float) -> str:
        prompt = (
            f"Provide a 2-3 sentence investment reasoning for {stock.ticker} ({stock.company_name}).\n"
            f"Barbell class: {stock.barbell_class.value}. Risk-reward score: {stock.risk_reward_score:.2f}.\n"
            f"Key metrics: P/E={stock.pe_ratio}, beta={stock.beta}, RSI={stock.rsi_14}, "
            f"momentum_90d={stock.momentum_90d}%, macro_sentiment={macro_aggregate:.2f}.\n"
            "Be concise and specific. No disclaimers."
        )
        response = await asyncio.to_thread(
            self._client.chat.completions.create,
            model=self._model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    async def build_shortlist(
        self, stocks: list[Stock], macro_aggregate: float
    ) -> list[Stock]:
        candidates = [s for s in stocks if s.barbell_class != BarbellClass.EXCLUDED]
        if not candidates:
            return []

        scored = [
            s.model_copy(update={"risk_reward_score": _compute_risk_reward(s, macro_aggregate)})
            for s in candidates
        ]
        scored.sort(key=lambda s: s.risk_reward_score, reverse=True)

        # Generate reasoning concurrently
        async def enrich(stock: Stock) -> Stock:
            try:
                reasoning = await self._call_llm_reasoning(stock, macro_aggregate)
                return stock.model_copy(update={"reasoning": reasoning})
            except Exception as e:
                logger.warning("Reasoning generation failed for %s: %s", stock.ticker, e)
                return stock

        enriched = await asyncio.gather(*[enrich(s) for s in scored])
        return list(enriched)
