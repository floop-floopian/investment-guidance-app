import json
import logging
from typing import Any
import anthropic
from src.models.macro_signal import MacroSignal, SentimentLabel
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a financial macro sentiment analyzer. "
    "Given a list of news headlines and summaries, return a JSON object with:\n"
    '- "items": array of {id, score (-1.0 bearish to +1.0 bullish), label (BEARISH|NEUTRAL|BULLISH)}\n'
    '- "aggregate": overall sentiment score (-1.0 to +1.0)\n'
    '- "summary": one-sentence market summary\n'
    "Return ONLY valid JSON, no markdown."
)


class SentimentService:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)

    async def _call_claude(self, user_content: str) -> dict[str, Any]:
        import asyncio
        response = await asyncio.to_thread(
            self._client.messages.create,
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
        )
        raw = response.content[0].text
        return json.loads(raw)

    async def score_signals(self, signals: list[MacroSignal]) -> tuple[list[MacroSignal], float]:
        if not signals:
            return [], 0.0

        items_text = "\n".join(
            f'[{s.id}] {s.title}' + (f' — {s.summary[:200]}' if s.summary else '')
            for s in signals
        )
        user_content = f"Score these {len(signals)} macro signals:\n\n{items_text}"

        try:
            result = await self._call_claude(user_content)
        except Exception as e:
            logger.error("Sentiment scoring failed: %s", e)
            return signals, 0.0

        score_map: dict[str, dict[str, Any]] = {
            item["id"]: item for item in result.get("items", [])
        }
        label_map = {
            "BULLISH": SentimentLabel.BULLISH,
            "BEARISH": SentimentLabel.BEARISH,
            "NEUTRAL": SentimentLabel.NEUTRAL,
        }

        updated: list[MacroSignal] = []
        for signal in signals:
            item_data = score_map.get(signal.id, {})
            score = float(item_data.get("score", 0.0))
            score = max(-1.0, min(1.0, score))
            label_str = item_data.get("label", "NEUTRAL").upper()
            updated.append(signal.model_copy(update={
                "sentiment_score": score,
                "sentiment_label": label_map.get(label_str, SentimentLabel.NEUTRAL),
            }))

        aggregate = float(result.get("aggregate", 0.0))
        aggregate = max(-1.0, min(1.0, aggregate))
        return updated, aggregate
