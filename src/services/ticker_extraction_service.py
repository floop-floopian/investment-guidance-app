import asyncio
import json
import logging
from groq import Groq
from src.models.macro_signal import MacroSignal
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_MAX_EXTRACTED = 10
_MAX_TOTAL = 15

_SYSTEM_PROMPT = (
    "You are a financial analyst. Given financial news headlines, extract all US-listed stock ticker symbols "
    "that are explicitly mentioned or strongly implied by company name. "
    'Return ONLY valid JSON: {"tickers": ["AAPL", "NVDA", ...]}. '
    "Only include real NYSE/NASDAQ tickers. Deduplicate. Return at most 10."
)


class TickerExtractionService:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = Groq(api_key=settings.groq_api_key)
        self._model = settings.groq_model
        self._fallback = settings.stock_tickers

    async def extract(self, signals: list[MacroSignal]) -> list[str]:
        if not signals:
            logger.info("No signals — using fallback ticker universe")
            return self._fallback

        headlines = "\n".join(f"- {s.title}" for s in signals)
        try:
            response = await asyncio.to_thread(
                self._client.chat.completions.create,
                model=self._model,
                max_tokens=256,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": f"Extract tickers from these headlines:\n\n{headlines}"},
                ],
                response_format={"type": "json_object"},
            )
            raw = json.loads(response.choices[0].message.content)
            extracted = [t.upper().strip() for t in raw.get("tickers", []) if t][:_MAX_EXTRACTED]
        except Exception as e:
            logger.warning("Ticker extraction failed: %s — using fallback", e)
            return self._fallback

        if not extracted:
            logger.info("No tickers extracted — using fallback universe")
            return self._fallback

        # Extracted tickers lead; fallback fills any remaining slots
        merged = list(dict.fromkeys(extracted + self._fallback))[:_MAX_TOTAL]
        logger.info("Extracted: %s | Final universe: %s", extracted, merged)
        return merged
