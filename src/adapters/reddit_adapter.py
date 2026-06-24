import logging
from datetime import datetime, timezone
from src.adapters.base import MacroSignalProvider
from src.models.macro_signal import MacroSignal, SourceType
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class RedditAdapter(MacroSignalProvider):
    def __init__(self) -> None:
        import praw
        s = get_settings()
        self._reddit = praw.Reddit(
            client_id=s.reddit_client_id,
            client_secret=s.reddit_client_secret,
            user_agent=s.reddit_user_agent,
        )
        self._subreddits = s.reddit_subreddits
        self._limit = s.reddit_hot_post_limit

    async def fetch_signals(self) -> list[MacroSignal]:
        signals: list[MacroSignal] = []
        now = datetime.now(timezone.utc)
        for sub_name in self._subreddits:
            try:
                subreddit = self._reddit.subreddit(sub_name)
                for post in subreddit.hot(limit=self._limit):
                    summary = (post.selftext or "")[:500] if hasattr(post, "selftext") else None
                    signals.append(MacroSignal(
                        id=f"reddit:{sub_name}:{post.id}",
                        source_type=SourceType.REDDIT,
                        source_id=sub_name,
                        title=post.title,
                        summary=summary or None,
                        url=f"https://reddit.com{post.permalink}",
                        published_at=datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
                        ingested_at=now,
                    ))
            except Exception as e:
                logger.warning("Reddit fetch failed for r/%s: %s", sub_name, e)
        return signals
