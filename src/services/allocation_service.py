import asyncio
import json
import logging
from typing import Any
from groq import Groq
from src.models.stock import Stock, BarbellClass
from src.models.allocation import Allocation, AllocationBand
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class AllocationService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = Groq(api_key=self._settings.groq_api_key)
        self._model = self._settings.groq_model

    async def _call_llm_rationale(
        self, allocations: list[Allocation], stocks: list[Stock], capital: float
    ) -> tuple[str, str]:
        """Returns (per_position_rationale_dict, overall_rationale)."""
        alloc_summary = "\n".join(
            f"- {a.ticker}: ${a.amount_usd:.0f} ({a.percentage:.1f}%, {a.band.value})"
            for a in allocations
        )
        prompt = (
            f"Capital: ${capital:.0f}. Allocation:\n{alloc_summary}\n\n"
            "Write a 2-sentence rationale for EACH position and a 2-sentence overall portfolio rationale.\n"
            'Return JSON: {"positions": {"TICKER": "rationale"}, "overall": "rationale"}'
        )
        response = await asyncio.to_thread(
            self._client.chat.completions.create,
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        raw = json.loads(response.choices[0].message.content)
        positions = raw.get("positions", {})
        overall = raw.get("overall", "")
        return positions, overall

    async def allocate(
        self, stocks: list[Stock], capital: float, run_id: str
    ) -> list[Allocation]:
        s = self._settings
        safe_ratio = s.barbell_safe_core_ratio
        sat_ratio = 1.0 - safe_ratio
        min_pos = s.capital_min_position_usd

        safe_stocks = [st for st in stocks if st.barbell_class == BarbellClass.SAFE_CORE]
        sat_stocks = [st for st in stocks if st.barbell_class == BarbellClass.SATELLITE]

        def _weight_allocate(
            band_stocks: list[Stock], band_capital: float, band: AllocationBand
        ) -> list[Allocation]:
            if not band_stocks or band_capital <= 0:
                return []
            total_score = sum(st.risk_reward_score for st in band_stocks)
            if total_score == 0:
                weights = [1.0 / len(band_stocks)] * len(band_stocks)
            else:
                weights = [st.risk_reward_score / total_score for st in band_stocks]

            raw_amounts = [w * band_capital for w in weights]

            # Filter positions below minimum
            valid = [(st, amt) for st, amt in zip(band_stocks, raw_amounts) if amt >= min_pos]
            if not valid:
                return []

            # Re-normalise after filtering
            total_valid = sum(amt for _, amt in valid)
            allocations: list[Allocation] = []
            for st, raw_amt in valid:
                final_amt = (raw_amt / total_valid) * band_capital
                if final_amt < min_pos:
                    continue
                allocations.append(Allocation(
                    ticker=st.ticker,
                    band=band,
                    amount_usd=round(final_amt, 2),
                    percentage=round(final_amt / capital * 100, 2),
                    run_id=run_id,
                ))
            return allocations

        safe_allocations = _weight_allocate(safe_stocks, capital * safe_ratio, AllocationBand.SAFE_CORE)
        sat_allocations = _weight_allocate(sat_stocks, capital * sat_ratio, AllocationBand.SATELLITE)
        all_allocations = safe_allocations + sat_allocations

        if not all_allocations:
            return []

        # Enrich with LLM rationale
        try:
            positions_rationale, overall_rationale = await self._call_llm_rationale(
                all_allocations, stocks, capital
            )
            enriched: list[Allocation] = []
            for alloc in all_allocations:
                rationale = positions_rationale.get(alloc.ticker, "")
                enriched.append(alloc.model_copy(update={"rationale": rationale}))
            return enriched
        except Exception as e:
            logger.warning("Allocation rationale generation failed: %s", e)
            return all_allocations
