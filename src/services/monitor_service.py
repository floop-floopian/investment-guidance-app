import asyncio
import logging
import uuid
from datetime import datetime, timezone
from src.adapters.reddit_adapter import RedditAdapter
from src.adapters.rss_adapter import RSSAdapter
from src.adapters.telegram_adapter import TelegramAdapter
from src.services.sentiment_service import SentimentService
from src.models.state_log import StateLogEntry, ActionType, LogLevel
from src.models.stock import VolatilityTier
from src.state import log_writer, supabase_store
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class MonitorService:
    def __init__(self) -> None:
        self._settings = get_settings()

    def get_interval_for_tier(self, tier: VolatilityTier) -> int:
        s = self._settings
        if tier == VolatilityTier.HIGH:
            return s.monitor_interval_high_vol_minutes
        if tier == VolatilityTier.LOW:
            return s.monitor_interval_low_vol_minutes
        return s.monitor_interval_med_vol_minutes

    def _log(self, run_id: str, action: ActionType, payload: dict = {}, level: LogLevel = LogLevel.INFO) -> None:
        entry = StateLogEntry(
            run_id=run_id,
            action=action,
            timestamp=datetime.now(timezone.utc),
            level=level,
            payload=payload,
        )
        log_writer.append_entry(entry)
        try:
            supabase_store.append_state_log(entry)
        except Exception:
            pass

    async def run_cycle(self, run_id: str | None = None) -> float:
        """Run one monitor cycle. Returns the sentiment delta."""
        run_id = run_id or str(uuid.uuid4())

        reddit = RedditAdapter()
        rss = RSSAdapter()
        reddit_signals = await reddit.fetch_signals()
        rss_signals = await rss.fetch_signals()
        all_signals = reddit_signals + rss_signals

        sentiment = SentimentService()
        scored_signals, aggregate = await sentiment.score_signals(all_signals)

        prior = supabase_store.get_last_aggregate()
        if prior is None:
            prior = 0.0
        delta = abs(aggregate - prior)

        supabase_store.set_last_aggregate(aggregate)

        if delta >= self._settings.sentiment_critical_delta:
            self._log(run_id, ActionType.CRITICAL_SIGNAL_DETECTED, {
                "aggregate": aggregate,
                "prior": prior,
                "delta": delta,
            })
            telegram = TelegramAdapter()
            message = (
                f"*⚠️ Critical Macro Signal Detected*\n"
                f"Sentiment shift: `{prior:+.2f}` → `{aggregate:+.2f}` (Δ`{delta:.2f}`)\n"
                f"Sources: {len(all_signals)} signals ingested."
            )
            sent = await telegram.send_message(message)
            if sent:
                self._log(run_id, ActionType.TELEGRAM_SENT, {"type": "critical_alert"})
            else:
                self._log(run_id, ActionType.TELEGRAM_FAILED, {}, LogLevel.ERROR)
        else:
            self._log(run_id, ActionType.MONITOR_CYCLE_COMPLETE, {
                "aggregate": aggregate,
                "prior": prior,
                "delta": delta,
                "signal_count": len(all_signals),
            })

        return delta

    async def run_forever(self) -> None:
        """Run monitor cycles indefinitely using the default MED interval."""
        interval_minutes = self._settings.monitor_interval_med_vol_minutes
        self._log("monitor", ActionType.PIPELINE_STARTED, {"interval_minutes": interval_minutes})
        logger.info("Monitor started. Cycle interval: %d min", interval_minutes)

        while True:
            try:
                delta = await self.run_cycle()
                logger.info("Monitor cycle complete. Delta: %.3f", delta)
            except Exception as e:
                logger.error("Monitor cycle failed: %s", e)

            await asyncio.sleep(interval_minutes * 60)
