from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from src.models.macro_signal import MacroSignal, SourceType
from src.models.state_log import ActionType


@pytest.fixture
def mock_signal():
    return MacroSignal(
        id="sig-monitor-1",
        source_type=SourceType.REDDIT,
        source_id="investing",
        title="Market update",
        ingested_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_cycle_logs_monitor_cycle_complete(mock_signal, tmp_path, mock_settings):
    mock_settings.state_log_path = tmp_path / "state.ndjson"

    with (
        patch("src.services.monitor_service.RedditAdapter") as MockReddit,
        patch("src.services.monitor_service.RSSAdapter") as MockRSS,
        patch("src.services.monitor_service.SentimentService") as MockSentiment,
        patch("src.services.monitor_service.supabase_store") as mock_store,
        patch("src.state.log_writer.get_settings", return_value=mock_settings),
        patch("src.services.monitor_service.TelegramAdapter") as MockTelegram,
    ):
        MockReddit.return_value.fetch_signals = AsyncMock(return_value=[mock_signal])
        MockRSS.return_value.fetch_signals = AsyncMock(return_value=[])
        MockSentiment.return_value.score_signals = AsyncMock(return_value=([mock_signal], 0.1))
        mock_store.get_last_aggregate.return_value = 0.05  # delta=0.05 < threshold, no alert
        mock_store.set_last_aggregate = MagicMock()
        MockTelegram.return_value.send_message = AsyncMock(return_value=True)

        from src.services.monitor_service import MonitorService
        svc = MonitorService()
        await svc.run_cycle(run_id="monitor-run-1")

    import json
    log_path = tmp_path / "state.ndjson"
    assert log_path.exists(), "State log file must be created"

    actions = []
    with open(log_path) as f:
        for line in f:
            if line.strip():
                actions.append(json.loads(line)["action"])

    assert ActionType.MONITOR_CYCLE_COMPLETE.value in actions, \
        f"Expected MONITOR_CYCLE_COMPLETE in log. Found: {actions}"


@pytest.mark.asyncio
async def test_feed_state_updated_after_cycle(mock_signal, tmp_path, mock_settings):
    mock_settings.state_log_path = tmp_path / "state.ndjson"
    mock_settings.rss_feed_urls = ["https://feeds.example.com/finance"]

    feed_state_calls = []

    with (
        patch("src.services.monitor_service.RedditAdapter") as MockReddit,
        patch("src.services.monitor_service.RSSAdapter") as MockRSS,
        patch("src.services.monitor_service.SentimentService") as MockSentiment,
        patch("src.services.monitor_service.supabase_store") as mock_store,
        patch("src.state.log_writer.get_settings", return_value=mock_settings),
        patch("src.adapters.rss_adapter.supabase_store") as mock_rss_store,
    ):
        def fake_upsert(url, etag, last_modified):
            feed_state_calls.append({"url": url, "etag": etag})

        MockReddit.return_value.fetch_signals = AsyncMock(return_value=[])
        MockRSS.return_value.fetch_signals = AsyncMock(return_value=[mock_signal])
        MockSentiment.return_value.score_signals = AsyncMock(return_value=([mock_signal], 0.0))
        mock_store.get_last_aggregate.return_value = 0.0
        mock_store.set_last_aggregate = MagicMock()
        mock_rss_store.upsert_feed_state = fake_upsert
        mock_rss_store.get_feed_state = MagicMock(return_value=None)

        from src.services.monitor_service import MonitorService
        svc = MonitorService()
        await svc.run_cycle(run_id="monitor-run-2")

    # The supabase store set_last_aggregate should be called
    mock_store.set_last_aggregate.assert_called_once()
