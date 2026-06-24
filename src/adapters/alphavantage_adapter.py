import asyncio
import logging
from typing import Any
from src.adapters.base import FinancialDataProvider
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_DAILY_LIMIT = 75
_daily_counter: dict[str, int] = {"count": 0, "date": ""}


def _check_limit() -> bool:
    import datetime
    today = datetime.date.today().isoformat()
    if _daily_counter["date"] != today:
        _daily_counter["count"] = 0
        _daily_counter["date"] = today
    if _daily_counter["count"] >= _DAILY_LIMIT:
        logger.warning("Alpha Vantage daily limit reached (%d/%d). Skipping call.", _daily_counter["count"], _DAILY_LIMIT)
        return False
    if _daily_counter["count"] >= 60:
        logger.warning("Alpha Vantage approaching daily limit (%d/%d).", _daily_counter["count"], _DAILY_LIMIT)
    _daily_counter["count"] += 1
    return True


class AlphaVantageAdapter(FinancialDataProvider):
    def __init__(self) -> None:
        from alpha_vantage.techindicators import TechIndicators
        from alpha_vantage.timeseries import TimeSeries
        key = get_settings().alpha_vantage_api_key
        self._ti = TechIndicators(key=key, output_format="pandas")
        self._ts = TimeSeries(key=key, output_format="pandas")

    async def get_quote(self, ticker: str) -> dict[str, Any]:
        # Alpha Vantage used primarily for technicals; return empty for quote
        return {}

    async def get_fundamentals(self, ticker: str) -> dict[str, Any]:
        return {}

    async def get_technicals(self, ticker: str) -> dict[str, Any]:
        if not _check_limit():
            return {}
        try:
            rsi_data, _ = await asyncio.to_thread(self._ti.get_rsi, ticker, interval="daily", time_period=14)
            rsi = float(rsi_data["RSI"].iloc[-1]) if not rsi_data.empty else None
        except Exception as e:
            logger.warning("AV RSI failed for %s: %s", ticker, e)
            rsi = None

        if not _check_limit():
            return {"rsi_14": rsi}
        try:
            sma50_data, _ = await asyncio.to_thread(self._ti.get_sma, ticker, interval="daily", time_period=50)
            sma50 = float(sma50_data["SMA"].iloc[-1]) if not sma50_data.empty else None
        except Exception as e:
            logger.warning("AV SMA50 failed for %s: %s", ticker, e)
            sma50 = None

        if not _check_limit():
            return {"rsi_14": rsi, "sma_50": sma50}
        try:
            sma200_data, _ = await asyncio.to_thread(self._ti.get_sma, ticker, interval="daily", time_period=200)
            sma200 = float(sma200_data["SMA"].iloc[-1]) if not sma200_data.empty else None
        except Exception as e:
            logger.warning("AV SMA200 failed for %s: %s", ticker, e)
            sma200 = None

        # 90d momentum: compare latest close to close 90 trading days ago
        momentum_90d = None
        if not _check_limit():
            pass
        else:
            try:
                ts_data, _ = await asyncio.to_thread(self._ts.get_daily_adjusted, ticker, outputsize="compact")
                if len(ts_data) >= 90:
                    latest = float(ts_data["5. adjusted close"].iloc[0])
                    past = float(ts_data["5. adjusted close"].iloc[89])
                    momentum_90d = (latest - past) / past * 100
            except Exception as e:
                logger.warning("AV momentum failed for %s: %s", ticker, e)

        return {"rsi_14": rsi, "sma_50": sma50, "sma_200": sma200, "momentum_90d": momentum_90d}
