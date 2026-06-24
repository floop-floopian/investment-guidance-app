from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import pytest
from src.models.macro_signal import MacroSignal, SourceType, SentimentLabel


def _make_signal(i: int) -> MacroSignal:
    return MacroSignal(
        id=f"sig-{i}",
        source_type=SourceType.REDDIT,
        source_id="investing",
        title=f"Test headline {i}",
        ingested_at=datetime.now(timezone.utc),
        run_id="run-test",
    )


MOCK_ANTHROPIC_RESPONSE = {
    "items": [
        {"id": "sig-0", "score": 0.6, "label": "BULLISH"},
        {"id": "sig-1", "score": -0.3, "label": "BEARISH"},
        {"id": "sig-2", "score": 0.1, "label": "NEUTRAL"},
    ],
    "aggregate": 0.133,
    "summary": "Mixed signals with slight bullish tilt.",
}


@pytest.mark.asyncio
async def test_score_signals_returns_updated_macro_signals():
    from src.services.sentiment_service import SentimentService
    signals = [_make_signal(i) for i in range(3)]
    service = SentimentService()
    with patch.object(service, "_call_claude", new_callable=AsyncMock, return_value=MOCK_ANTHROPIC_RESPONSE):
        scored, aggregate = await service.score_signals(signals)
    assert len(scored) == 3
    assert all(isinstance(s, MacroSignal) for s in scored)


@pytest.mark.asyncio
async def test_sentiment_scores_in_valid_range():
    from src.services.sentiment_service import SentimentService
    signals = [_make_signal(i) for i in range(3)]
    service = SentimentService()
    with patch.object(service, "_call_claude", new_callable=AsyncMock, return_value=MOCK_ANTHROPIC_RESPONSE):
        scored, _ = await service.score_signals(signals)
    for s in scored:
        assert s.sentiment_score is not None
        assert -1.0 <= s.sentiment_score <= 1.0


@pytest.mark.asyncio
async def test_sentiment_labels_assigned():
    from src.services.sentiment_service import SentimentService
    signals = [_make_signal(i) for i in range(3)]
    service = SentimentService()
    with patch.object(service, "_call_claude", new_callable=AsyncMock, return_value=MOCK_ANTHROPIC_RESPONSE):
        scored, _ = await service.score_signals(signals)
    labels = {s.sentiment_label for s in scored}
    assert labels.issubset({SentimentLabel.BULLISH, SentimentLabel.BEARISH, SentimentLabel.NEUTRAL})


@pytest.mark.asyncio
async def test_aggregate_signal_computed():
    from src.services.sentiment_service import SentimentService
    signals = [_make_signal(i) for i in range(3)]
    service = SentimentService()
    with patch.object(service, "_call_claude", new_callable=AsyncMock, return_value=MOCK_ANTHROPIC_RESPONSE):
        _, aggregate = await service.score_signals(signals)
    assert isinstance(aggregate, float)
    assert -1.0 <= aggregate <= 1.0


@pytest.mark.asyncio
async def test_structured_json_parsed_correctly():
    from src.services.sentiment_service import SentimentService
    signals = [_make_signal(0)]
    single_response = {
        "items": [{"id": "sig-0", "score": 0.9, "label": "BULLISH"}],
        "aggregate": 0.9,
        "summary": "Very bullish.",
    }
    service = SentimentService()
    with patch.object(service, "_call_claude", new_callable=AsyncMock, return_value=single_response):
        scored, aggregate = await service.score_signals(signals)
    assert scored[0].sentiment_score == pytest.approx(0.9, abs=0.01)
    assert scored[0].sentiment_label == SentimentLabel.BULLISH
    assert aggregate == pytest.approx(0.9, abs=0.01)
