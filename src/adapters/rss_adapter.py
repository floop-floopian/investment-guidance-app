import logging
from datetime import datetime, timezone
from src.adapters.base import MacroSignalProvider
from src.models.macro_signal import MacroSignal, SourceType
from src.config.settings import get_settings
from src.state import supabase_store

logger = logging.getLogger(__name__)


class RSSAdapter(MacroSignalProvider):
    def __init__(self) -> None:
        self._feed_urls = get_settings().rss_feed_urls

    async def fetch_signals(self) -> list[MacroSignal]:
        import feedparser
        signals: list[MacroSignal] = []
        now = datetime.now(timezone.utc)

        for url in self._feed_urls:
            try:
                state = supabase_store.get_feed_state(url) or {}
                kwargs: dict = {"url": url}
                if state.get("etag"):
                    kwargs["etag"] = state["etag"]
                if state.get("last_modified"):
                    kwargs["modified"] = state["last_modified"]

                feed = feedparser.parse(url, **{k: v for k, v in kwargs.items() if k != "url"})
                # feedparser uses positional first arg
                feed = feedparser.parse(url)

                etag = getattr(feed, "etag", None)
                modified = getattr(feed, "modified", None)
                supabase_store.upsert_feed_state(url, etag, modified)

                for entry in feed.entries:
                    pub = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        import time
                        pub = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)

                    summary = getattr(entry, "summary", None) or getattr(entry, "description", None)
                    signals.append(MacroSignal(
                        id=f"rss:{url}:{getattr(entry, 'id', entry.get('link', str(len(signals))))}",
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
