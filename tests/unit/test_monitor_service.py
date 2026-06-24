from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from src.models.stock import VolatilityTier


@pytest.fixture
def service():
    from src.services.monitor_service import MonitorService
    return MonitorService()


@pytest.mark.asyncio
async def test_cycle_runs_ingestion_and_scoring(service, mock_settings):
    signals = []
    with (
        patch("src.services.monitor_service.RedditAdapter") as MockReddit,
        patch("src.services.monitor_service.RSSAdapter") as MockRSS,
        patch("src.services.monitor_service.SentimentService") as MockSentiment,
        patch("src.services.monitor_service.supabase_store") as mock_store,
        patch("src.services.monitor_service.log_writer") as mock_log,
    ):
        from datetime import datetime, timezone
        from src.models.macro_signal import MacroSignal, SourceType
        sig = MacroSignal(
            id="s1", source_type=SourceType.REDDIT, source_id="investing",
            title="Test", ingested_at=datetime.now(timezone.utc)
        )
        MockReddit.return_value.fetch_signals = AsyncMock(return_value=[sig])
        MockRSS.return_value.fetch_signals = AsyncMock(return_value=[])
        MockSentiment.return_value.score_signals = AsyncMock(return_value=([sig], 0.2))
        mock_store.get_last_aggregate.return_value = 0.1
        mock_store.set_last_aggregate = MagicMock()
        mock_log.append_entry = MagicMock()

        delta = await service.run_cycle(run_id="test-run")

    assert delta is not None


@pytest.mark.asyncio
async def test_delta_computed_against_prior_aggregate(service):
    with (
        patch("src.services.monitor_service.RedditAdapter") as MockReddit,
        patch("src.services.monitor_service.RSSAdapter") as MockRSS,
        patch("src.services.monitor_service.SentimentService") as MockSentiment,
        patch("src.services.monitor_service.supabase_store") as mock_store,
        patch("src.services.monitor_service.log_writer") as mock_log,
    ):
        from datetime import datetime, timezone
        from src.models.macro_signal import MacroSignal, SourceType
        sig = MacroSignal(id="s1", source_type=SourceType.REDDIT, source_id="investing",
                          title="Test", ingested_at=datetime.now(timezone.utc))
        MockReddit.return_value.fetch_signals = AsyncMock(return_value=[sig])
        MockRSS.return_value.fetch_signals = AsyncMock(return_value=[])
        MockSentiment.return_value.score_signals = AsyncMock(return_value=([sig], 0.5))
        mock_store.get_last_aggregate.return_value = 0.1
        mock_store.set_last_aggregate = MagicMock()
        mock_log.append_entry = MagicMock()

        delta = await service.run_cycle(run_id="test-run")

    assert abs(delta - 0.4) < 0.01


@pytest.mark.asyncio
async def test_critical_signal_detected_fires_when_delta_exceeds_threshold(service, mock_settings):
    mock_settings.sentiment_critical_delta = 0.3
    triggered = {"alert": False}

    with (
        patch("src.services.monitor_service.RedditAdapter") as MockReddit,
        patch("src.services.monitor_service.RSSAdapter") as MockRSS,
        patch("src.services.monitor_service.SentimentService") as MockSentiment,
        patch("src.services.monitor_service.supabase_store") as mock_store,
        patch("src.services.monitor_service.log_writer") as mock_log,
        patch("src.services.monitor_service.TelegramAdapter") as MockTelegram,
    ):
        from datetime import datetime, timezone
        from src.models.macro_signal import MacroSignal, SourceType
        sig = MacroSignal(id="s1", source_type=SourceType.REDDIT, source_id="investing",
                          title="Big news", ingested_at=datetime.now(timezone.utc))

        async def fake_send(msg):
            triggered["alert"] = True
            return True

        MockReddit.return_value.fetch_signals = AsyncMock(return_value=[sig])
        MockRSS.return_value.fetch_signals = AsyncMock(return_value=[])
        MockSentiment.return_value.score_signals = AsyncMock(return_value=([sig], 0.8))
        mock_store.get_last_aggregate.return_value = 0.1  # delta = 0.7 > 0.3
        mock_store.set_last_aggregate = MagicMock()
        mock_log.append_entry = MagicMock()
        MockTelegram.return_value.send_message = fake_send

        await service.run_cycle(run_id="test-run")

    assert triggered["alert"], "Expected Telegram alert for critical signal"


@pytest.mark.asyncio
async def test_no_alert_when_delta_below_threshold(service, mock_settings):
    mock_settings.sentiment_critical_delta = 0.3
    triggered = {"alert": False}

    with (
        patch("src.services.monitor_service.RedditAdapter") as MockReddit,
        patch("src.services.monitor_service.RSSAdapter") as MockRSS,
        patch("src.services.monitor_service.SentimentService") as MockSentiment,
        patch("src.services.monitor_service.supabase_store") as mock_store,
        patch("src.services.monitor_service.log_writer") as mock_log,
        patch("src.services.monitor_service.TelegramAdapter") as MockTelegram,
    ):
        from datetime import datetime, timezone
        from src.models.macro_signal import MacroSignal, SourceType
        sig = MacroSignal(id="s1", source_type=SourceType.REDDIT, source_id="investing",
                          title="Minor update", ingested_at=datetime.now(timezone.utc))

        async def fake_send(msg):
            triggered["alert"] = True
            return True

        MockReddit.return_value.fetch_signals = AsyncMock(return_value=[sig])
        MockRSS.return_value.fetch_signals = AsyncMock(return_value=[])
        MockSentiment.return_value.score_signals = AsyncMock(return_value=([sig], 0.15))
        mock_store.get_last_aggregate.return_value = 0.1  # delta = 0.05 < 0.3
        mock_store.set_last_aggregate = MagicMock()
        mock_log.append_entry = MagicMock()
        MockTelegram.return_value.send_message = fake_send

        await service.run_cycle(run_id="test-run")

    assert not triggered["alert"], "Should not alert when delta below threshold"


def test_high_vol_stocks_use_high_interval(service, mock_settings):
    mock_settings.monitor_interval_high_vol_minutes = 15
    mock_settings.monitor_interval_med_vol_minutes = 30
    mock_settings.monitor_interval_low_vol_minutes = 60

    interval = service.get_interval_for_tier(VolatilityTier.HIGH)
    assert interval == 15


def test_low_vol_stocks_use_low_interval(service, mock_settings):
    mock_settings.monitor_interval_high_vol_minutes = 15
    mock_settings.monitor_interval_med_vol_minutes = 30
    mock_settings.monitor_interval_low_vol_minutes = 60

    interval = service.get_interval_for_tier(VolatilityTier.LOW)
    assert interval == 60
