import asyncio
import logging
import aiohttp
from src.adapters.base import NotificationProvider
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_RETRY_DELAY = 2.0
_DISCORD_API = "https://discord.com/api/v10"


class DiscordAdapter(NotificationProvider):
    def __init__(self) -> None:
        s = get_settings()
        self._token = s.discord_bot_token

    async def _get_dm_channel_id(self, session: aiohttp.ClientSession, discord_user_id: str) -> str | None:
        url = f"{_DISCORD_API}/users/@me/channels"
        headers = {"Authorization": f"Bot {self._token}", "Content-Type": "application/json"}
        async with session.post(url, json={"recipient_id": discord_user_id}, headers=headers) as resp:
            if resp.status in (200, 201):
                data = await resp.json()
                return data["id"]
            body = await resp.text()
            logger.error("Failed to open DM channel for user %s: %s %s", discord_user_id, resp.status, body)
            return None

    async def _send_to_channel(self, session: aiohttp.ClientSession, channel_id: str, text: str) -> bool:
        url = f"{_DISCORD_API}/channels/{channel_id}/messages"
        headers = {"Authorization": f"Bot {self._token}", "Content-Type": "application/json"}
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with session.post(url, json={"content": text}, headers=headers) as resp:
                    if resp.status in (200, 201):
                        return True
                    body = await resp.text()
                    raise RuntimeError(f"Discord API {resp.status}: {body}")
            except Exception as e:
                if attempt < _MAX_RETRIES:
                    wait = _RETRY_DELAY * (2 ** attempt)
                    logger.warning("Discord send failed (attempt %d/%d): %s — retrying in %.1fs", attempt + 1, _MAX_RETRIES + 1, e, wait)
                    await asyncio.sleep(wait)
                else:
                    logger.error("Discord send failed after %d attempts: %s", _MAX_RETRIES + 1, e)
                    return False
        return False

    @staticmethod
    def _chunk(text: str, limit: int = 1990) -> list[str]:
        if len(text) <= limit:
            return [text]
        chunks, current = [], ""
        for line in text.splitlines(keepends=True):
            if len(current) + len(line) > limit:
                chunks.append(current)
                current = ""
            current += line
        if current:
            chunks.append(current)
        return chunks

    async def send_message(self, text: str) -> bool:
        from src.state.supabase_store import get_active_discord_user_ids
        user_ids = get_active_discord_user_ids()
        if not user_ids:
            logger.warning("No active Discord users found in Supabase — message not sent")
            return False

        async with aiohttp.ClientSession() as session:
            results = []
            for user_id in user_ids:
                channel_id = await self._get_dm_channel_id(session, user_id)
                if not channel_id:
                    results.append(False)
                    continue
                ok = True
                for chunk in self._chunk(text):
                    ok = await self._send_to_channel(session, channel_id, chunk) and ok
                results.append(ok)

        return any(results)
