import asyncio
import logging
from src.adapters.base import NotificationProvider
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_RETRY_DELAY = 2.0


class TelegramAdapter(NotificationProvider):
    def __init__(self) -> None:
        s = get_settings()
        self._token = s.telegram_bot_token
        self._chat_id = s.telegram_chat_id

    async def send_message(self, text: str) -> bool:
        from telegram import Bot
        from telegram.error import TelegramError
        bot = Bot(token=self._token)
        for attempt in range(_MAX_RETRIES + 1):
            try:
                await bot.send_message(
                    chat_id=self._chat_id,
                    text=text,
                    parse_mode="Markdown",
                )
                return True
            except TelegramError as e:
                if attempt < _MAX_RETRIES:
                    wait = _RETRY_DELAY * (2 ** attempt)
                    logger.warning("Telegram send failed (attempt %d/%d): %s — retrying in %.1fs", attempt + 1, _MAX_RETRIES + 1, e, wait)
                    await asyncio.sleep(wait)
                else:
                    logger.error("Telegram send failed after %d attempts: %s", _MAX_RETRIES + 1, e)
                    return False
        return False
