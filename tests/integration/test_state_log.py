"""
Integration test: verifies state log completeness and ordering.
All external adapters are mocked.
"""
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.models.macro_signal import MacroSignal, SourceType, SentimentLabel
from src.models.state_log import ActionType


MOCK_SIGNAL = MacroSignal(
    id="sig-1",
    source_type=SourceType.REDDIT,
    source_id="investing",
    title="Markets steady",
    ingested_at=datetime.now(timezone.utc),
    sentiment_score=0.2,
    sentiment_label=SentimentLabel.NEUTRAL,
)


@pytest.mark.asyncio
async def test_all_action_types_present_in_ndjson(tmp_path, mock_settings):
    mock_settings.state_log_path = tmp_path / "state.ndjson"
    mock_settings.capital_min_position_usd = 0.0  # allow small allocations

    required = {
        ActionType.PIPELINE_STARTED.value,
        ActionType.MACRO_INGESTION_COMPLETE.value,
        ActionType.SENTIMENT_SCORED.value,
        ActionType.ANALYSIS_COMPLETE.value,
        ActionType.BARBELL_CLASSIFIED.value,
        ActionType.ALLOCATION_GENERATED.value,
        ActionType.TELEGRAM_SENT.value,
        ActionType.PIPELINE_COMPLETED.value,
    }

    with (
        patch("src.config.settings.get_settings", return_value=mock_settings),
        patch("src.state.log_writer.get_settings", return_value=mock_settings),
        patch("src.state.supabase_store._client", side_effect=Exception("no supabase")),
        patch("src.pipeline.orchestrator.RedditAdapter") as MockReddit,
        patch("src.pipeline.orchestrator.RSSAdapter") as MockRSS,
        patch("src.pipeline.orchestrator.FinnhubAdapter") as MockFinnhub,
        patch("src.pipeline.orchestrator.AlphaVantageAdapter") as MockAV,
        patch("src.pipeline.orchestrator.TelegramAdapter") as MockTelegram,
        patch("src.services.sentiment_service.SentimentService._call_claude") as mock_claude,
        patch("src.services.shortlist_service.ShortlistService._call_claude_reasoning") as mock_reason,
        patch("src.services.allocation_service.AllocationService._call_claude_rationale") as mock_rat,
    ):
        MockReddit.return_value.fetch_signals = AsyncMock(return_value=[MOCK_SIGNAL])
        MockRSS.return_value.fetch_signals = AsyncMock(return_value=[])
        MockFinnhub.return_value.get_quote = AsyncMock(return_value={"price": 150.0})
        MockFinnhub.return_value.get_fundamentals = AsyncMock(
            return_value={"pe_ratio": 15.0, "market_cap": 15_000_000_000.0, "beta": 0.7}
        )
        MockFinnhub.return_value.get_technicals = AsyncMock(return_value={})
        MockAV.return_value.get_technicals = AsyncMock(return_value={"rsi_14": 50.0, "momentum_90d": 5.0})
        MockTelegram.return_value.send_message = AsyncMock(return_value=True)
        mock_claude.return_value = {
            "items": [{"id": "sig-1", "score": 0.2, "label": "NEUTRAL"}],
            "aggregate": 0.2,
            "summary": "Steady.",
        }
        mock_reason.return_value = "Solid defensive stock."
        mock_rat.return_value = ({"AAPL": "Core holding."}, "Balanced portfolio.")

        from src.pipeline.orchestrator import PipelineOrchestrator
        orch = PipelineOrchestrator()
        await orch.run_on_demand(capital=10_000.0)

    found = set()
    with open(tmp_path / "state.ndjson") as f:
        for line in f:
            if line.strip():
                found.add(json.loads(line)["action"])

    missing = required - found
    assert not missing, f"Missing log action types: {missing}"


@pytest.mark.asyncio
async def test_state_log_written_before_telegram(tmp_path, mock_settings):
    mock_settings.state_log_path = tmp_path / "state.ndjson"
    mock_settings.capital_min_position_usd = 0.0

    telegram_seen_allocation = {"result": False}

    with (
        patch("src.config.settings.get_settings", return_value=mock_settings),
        patch("src.state.log_writer.get_settings", return_value=mock_settings),
        patch("src.state.supabase_store._client", side_effect=Exception("no supabase")),
        patch("src.pipeline.orchestrator.RedditAdapter") as MockReddit,
        patch("src.pipeline.orchestrator.RSSAdapter") as MockRSS,
        patch("src.pipeline.orchestrator.FinnhubAdapter") as MockFinnhub,
        patch("src.pipeline.orchestrator.AlphaVantageAdapter") as MockAV,
        patch("src.pipeline.orchestrator.TelegramAdapter") as MockTelegram,
        patch("src.services.sentiment_service.SentimentService._call_claude") as mock_claude,
        patch("src.services.shortlist_service.ShortlistService._call_claude_reasoning") as mock_reason,
        patch("src.services.allocation_service.AllocationService._call_claude_rationale") as mock_rat,
    ):
        async def check_log_then_send(msg):
            log_path = tmp_path / "state.ndjson"
            if log_path.exists():
                with open(log_path) as f:
                    actions = [json.loads(l)["action"] for l in f if l.strip()]
                if ActionType.ALLOCATION_GENERATED.value in actions:
                    telegram_seen_allocation["result"] = True
            return True

        MockReddit.return_value.fetch_signals = AsyncMock(return_value=[MOCK_SIGNAL])
        MockRSS.return_value.fetch_signals = AsyncMock(return_value=[])
        MockFinnhub.return_value.get_quote = AsyncMock(return_value={"price": 150.0})
        MockFinnhub.return_value.get_fundamentals = AsyncMock(
            return_value={"pe_ratio": 15.0, "market_cap": 15_000_000_000.0, "beta": 0.7}
        )
        MockFinnhub.return_value.get_technicals = AsyncMock(return_value={})
        MockAV.return_value.get_technicals = AsyncMock(return_value={"rsi_14": 50.0})
        MockTelegram.return_value.send_message = check_log_then_send
        mock_claude.return_value = {
            "items": [{"id": "sig-1", "score": 0.2, "label": "NEUTRAL"}],
            "aggregate": 0.2,
            "summary": "Steady.",
        }
        mock_reason.return_value = "Good stock."
        mock_rat.return_value = ({"AAPL": "Core."}, "Balanced.")

        from src.pipeline.orchestrator import PipelineOrchestrator
        orch = PipelineOrchestrator()
        await orch.run_on_demand(capital=10_000.0)

    assert telegram_seen_allocation["result"], \
        "ALLOCATION_GENERATED must be logged before Telegram send (Principle VI)"
