import asyncio
import hashlib
import logging
import time
from datetime import datetime, timezone
import feedparser
from src.adapters.base import MacroSignalProvider
from src.models.macro_signal import MacroSignal, SourceType
from src.config.settings import get_settings
from src.state import supabase_store

logger = logging.getLogger(__name__)


class RSSAdapter(MacroSignalProvider):
    def __init__(self) -> None:
        self._feed_urls = get_settings().rss_feed_urls

    async def fetch_signals(self) -> list[MacroSignal]:
        signals: list[MacroSignal] = []
        now = datetime.now(timezone.utc)

        for url in self._feed_urls:
            try:
                state = supabase_store.get_feed_state(url) or {}
                kwargs: dict = {}
                if state.get("etag"):
                    kwargs["etag"] = state["etag"]
                if state.get("last_modified"):
                    kwargs["modified"] = state["last_modified"]

                feed = await asyncio.to_thread(feedparser.parse, url, **kwargs)

                supabase_store.upsert_feed_state(
                    url,
                    getattr(feed, "etag", None),
                    getattr(feed, "modified", None),
                )

                for entry in feed.entries:
                    pub = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub = datetime.fromtimestamp(
                            time.mktime(entry.published_parsed), tz=timezone.utc
                        )

                    summary = getattr(entry, "summary", None) or getattr(entry, "description", None)
                    entry_key = getattr(entry, "id", None) or getattr(entry, "link", None) or getattr(entry, "title", str(len(signals)))
                    entry_hash = hashlib.md5(f"{url}:{entry_key}".encode()).hexdigest()[:16]
                    signals.append(MacroSignal(
                        id=f"rss:{entry_hash}",
                        source_type=SourceType.RSS,
                        source_id=url,
                        title=getattr(entry, "title", ""),
                        summary=(summary or "")[:500] or None,
                        url=getattr(entry, "link", None),
                        published_at=pub,
                        ingested_at=now,
                    ))
            except Exception as e:
                logger.warning("RSS fetch failed for %s: %s", url, e)

        return signals
