import asyncio
import logging
from datetime import datetime, timezone
from supabase import create_client, Client
from src.config.settings import get_settings
from src.models.macro_signal import MacroSignal
from src.models.stock import Stock
from src.models.allocation import Allocation
from src.models.pipeline_run import PipelineRun
from src.models.state_log import StateLogEntry

logger = logging.getLogger(__name__)


def _client() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_key)


def _run_async(coro):  # type: ignore[no-untyped-def]
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except Exception as e:
        logger.warning("Supabase write failed (best-effort): %s", e)
        return None


def upsert_pipeline_run(run: PipelineRun) -> None:
    try:
        data = run.model_dump()
        data["started_at"] = run.started_at.isoformat()
        if run.completed_at:
            data["completed_at"] = run.completed_at.isoformat()
        _client().table("pipeline_runs").upsert(data).execute()
    except Exception as e:
        logger.warning("Failed to upsert pipeline_run %s: %s", run.id, e)


def upsert_macro_signals(signals: list[MacroSignal]) -> None:
    if not signals:
        return
    try:
        seen: set[str] = set()
        rows = []
        for s in signals:
            if s.id in seen:
                continue
            seen.add(s.id)
            row = s.model_dump()
            row["ingested_at"] = s.ingested_at.isoformat()
            if s.published_at:
                row["published_at"] = s.published_at.isoformat()
            rows.append(row)
        _client().table("macro_signals").upsert(rows, on_conflict="id").execute()
    except Exception as e:
        logger.warning("Failed to upsert macro_signals: %s", e)


def upsert_stocks(stocks: list[Stock]) -> None:
    if not stocks:
        return
    try:
        rows = []
        for s in stocks:
            row = s.model_dump()
            if s.analyzed_at:
                row["analyzed_at"] = s.analyzed_at.isoformat()
            rows.append(row)
        _client().table("stocks").upsert(rows, on_conflict="run_id,ticker").execute()
    except Exception as e:
        logger.warning("Failed to upsert stocks: %s", e)


def upsert_allocations(allocations: list[Allocation]) -> None:
    if not allocations:
        return
    try:
        rows = [a.model_dump() for a in allocations]
        _client().table("allocations").upsert(rows).execute()
    except Exception as e:
        logger.warning("Failed to upsert allocations: %s", e)


def append_state_log(entry: StateLogEntry) -> None:
    try:
        row = entry.model_dump()
        row["timestamp"] = entry.timestamp.isoformat()
        _client().table("state_log").insert(row).execute()
    except Exception as e:
        logger.warning("Failed to insert state_log entry: %s", e)


def upsert_feed_state(feed_url: str, etag: str | None, last_modified: str | None) -> None:
    try:
        _client().table("feed_state").upsert({
            "feed_url": feed_url,
            "etag": etag,
            "last_modified": last_modified,
            "last_checked_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.warning("Failed to upsert feed_state for %s: %s", feed_url, e)


def get_feed_state(feed_url: str) -> dict | None:
    try:
        result = _client().table("feed_state").select("*").eq("feed_url", feed_url).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.warning("Failed to get feed_state for %s: %s", feed_url, e)
        return None


def get_last_aggregate() -> float | None:
    """Return the most recent sentiment aggregate stored in feed_state."""
    try:
        result = (
            _client()
            .table("feed_state")
            .select("last_aggregate")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data and result.data[0]["last_aggregate"] is not None:
            return float(result.data[0]["last_aggregate"])
        return None
    except Exception as e:
        logger.warning("Failed to get last aggregate: %s", e)
        return None


def set_last_aggregate(aggregate: float) -> None:
    """Store the current aggregate in the most recently updated feed_state row."""
    try:
        result = (
            _client()
            .table("feed_state")
            .select("feed_url")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            feed_url = result.data[0]["feed_url"]
            _client().table("feed_state").update({
                "last_aggregate": aggregate,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("feed_url", feed_url).execute()
    except Exception as e:
        logger.warning("Failed to set last aggregate: %s", e)


def get_active_discord_user_ids() -> list[str]:
    try:
        result = (
            _client()
            .table("users")
            .select("discord_user_id")
            .eq("is_active", True)
            .execute()
        )
        return [row["discord_user_id"] for row in result.data]
    except Exception as e:
        logger.warning("Failed to get active discord user IDs: %s", e)
        return []


def get_last_pipeline_run() -> dict | None:
    try:
        result = (
            _client()
            .table("pipeline_runs")
            .select("*")
            .order("started_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        logger.warning("Failed to get last pipeline run: %s", e)
        return None
