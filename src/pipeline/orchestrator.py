import logging
from datetime import datetime, timezone
from src.adapters.reddit_adapter import RedditAdapter
from src.adapters.rss_adapter import RSSAdapter
from src.adapters.finnhub_adapter import FinnhubAdapter
from src.adapters.alphavantage_adapter import AlphaVantageAdapter
from src.adapters.telegram_adapter import TelegramAdapter
from src.services.sentiment_service import SentimentService
from src.services.analysis_service import AnalysisService
from src.services.barbell_service import BarbellService
from src.services.shortlist_service import ShortlistService
from src.services.allocation_service import AllocationService
from src.models.pipeline_run import PipelineRun, TriggerType, RunStatus
from src.models.state_log import StateLogEntry, ActionType, LogLevel
from src.state import log_writer, supabase_store
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(self) -> None:
        self._settings = get_settings()

    def _log(
        self,
        run_id: str,
        action: ActionType,
        payload: dict = {},
        level: LogLevel = LogLevel.INFO,
    ) -> None:
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

    def _format_telegram_message(self, run: PipelineRun, stocks, allocations, aggregate: float) -> str:
        lines = [
            f"*Investment Guidance — Run {run.id[:8]}*",
            f"Macro Sentiment: `{aggregate:+.2f}` ({run.macro_signal_count} signals)\n",
            "*Shortlist:*",
        ]
        for stock in stocks:
            lines.append(
                f"• *{stock.ticker}* [{stock.barbell_class.value}] "
                f"Score: `{stock.risk_reward_score:.2f}`\n"
                f"  {stock.reasoning or 'N/A'}"
            )
        lines.append("\n*Capital Allocation:*")
        total = 0.0
        for alloc in allocations:
            lines.append(
                f"• {alloc.ticker}: `${alloc.amount_usd:,.0f}` ({alloc.percentage:.1f}%)\n"
                f"  {alloc.rationale or ''}"
            )
            total += alloc.amount_usd
        lines.append(f"\nTotal deployed: `${total:,.0f}`")
        return "\n".join(lines)

    async def run_on_demand(self, capital: float) -> PipelineRun:
        run = PipelineRun(
            trigger_type=TriggerType.ON_DEMAND,
            started_at=datetime.now(timezone.utc),
            capital_input=capital,
        )
        supabase_store.upsert_pipeline_run(run)
        self._log(run.id, ActionType.PIPELINE_STARTED, {"capital": capital})

        try:
            # Stage 1: Macro ingestion
            reddit = RedditAdapter()
            rss = RSSAdapter()
            reddit_signals = await reddit.fetch_signals()
            rss_signals = await rss.fetch_signals()
            all_signals = reddit_signals + rss_signals

            run = run.model_copy(update={"macro_signal_count": len(all_signals)})
            self._log(run.id, ActionType.MACRO_INGESTION_COMPLETE, {
                "reddit_count": len(reddit_signals),
                "rss_count": len(rss_signals),
                "total": len(all_signals),
            })
            supabase_store.upsert_macro_signals(all_signals)

            # Stage 2: Sentiment scoring
            sentiment = SentimentService()
            scored_signals, aggregate = await sentiment.score_signals(all_signals)
            self._log(run.id, ActionType.SENTIMENT_SCORED, {
                "aggregate": aggregate,
                "signal_count": len(scored_signals),
            })
            supabase_store.upsert_macro_signals(scored_signals)

            # Stage 3: Stock analysis
            finnhub = FinnhubAdapter()
            av = AlphaVantageAdapter()
            analysis = AnalysisService(primary=finnhub, fallback=av)
            tickers = self._settings.stock_tickers

            def _log_error(action, level, payload):
                self._log(run.id, action, payload, level)

            stocks = await analysis.analyse_tickers(tickers, run.id, log_error_fn=_log_error)
            self._log(run.id, ActionType.ANALYSIS_COMPLETE, {
                "ticker_count": len(stocks),
                "tickers": [s.ticker for s in stocks],
            })
            supabase_store.upsert_stocks(stocks)

            # Stage 4: Barbell classification
            barbell = BarbellService()
            classified = barbell.classify_all(stocks, aggregate)
            shortlist_stocks = [s for s in classified if s.barbell_class.value != "EXCLUDED"]
            run = run.model_copy(update={"shortlist_count": len(shortlist_stocks)})
            self._log(run.id, ActionType.BARBELL_CLASSIFIED, {
                "total": len(classified),
                "shortlisted": len(shortlist_stocks),
                "excluded": len(classified) - len(shortlist_stocks),
            })
            supabase_store.upsert_stocks(classified)

            # Stage 5: Shortlist with reasoning
            shortlist_svc = ShortlistService()
            shortlist = await shortlist_svc.build_shortlist(classified, aggregate)

            # Stage 6: Capital allocation — log BEFORE Telegram (Principle VI)
            alloc_svc = AllocationService()
            allocations = await alloc_svc.allocate(shortlist, capital, run.id)
            run = run.model_copy(update={"allocation_count": len(allocations)})
            self._log(run.id, ActionType.ALLOCATION_GENERATED, {
                "allocation_count": len(allocations),
                "allocations": [
                    {"ticker": a.ticker, "amount_usd": a.amount_usd, "band": a.band.value}
                    for a in allocations
                ],
            })
            supabase_store.upsert_allocations(allocations)

            # Stage 7: Telegram notification (AFTER state log — Principle VI)
            telegram = TelegramAdapter()
            message = self._format_telegram_message(run, shortlist, allocations, aggregate)
            sent = await telegram.send_message(message)

            if sent:
                run = run.model_copy(update={"telegram_sent": True})
                self._log(run.id, ActionType.TELEGRAM_SENT, {"message_length": len(message)})
            else:
                self._log(run.id, ActionType.TELEGRAM_FAILED, {}, LogLevel.ERROR)

            run = run.model_copy(update={
                "status": RunStatus.COMPLETED,
                "completed_at": datetime.now(timezone.utc),
            })
            self._log(run.id, ActionType.PIPELINE_COMPLETED, {
                "duration_s": (run.completed_at - run.started_at).total_seconds()
            })

        except Exception as e:
            logger.error("Pipeline failed: %s", e)
            run = run.model_copy(update={
                "status": RunStatus.FAILED,
                "completed_at": datetime.now(timezone.utc),
                "error_message": str(e),
            })
            self._log(run.id, ActionType.PIPELINE_FAILED, {"error": str(e)}, LogLevel.ERROR)

        supabase_store.upsert_pipeline_run(run)
        return run
