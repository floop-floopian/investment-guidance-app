import asyncio
import logging
import time
from typing import Any
from src.adapters.base import FinancialDataProvider
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_RATE_LIMIT = 60  # requests per minute


class _TokenBucket:
    def __init__(self, rate: int) -> None:
        self._rate = rate
        self._tokens = float(rate)
        self._last = time.monotonic()

    def acquire(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        self._tokens = min(self._rate, self._tokens + elapsed * self._rate / 60)
        self._last = now
        if self._tokens < 1:
            sleep_for = (1 - self._tokens) * 60 / self._rate
            time.sleep(sleep_for)
            self._tokens = 0
        else:
            self._tokens -= 1


_bucket = _TokenBucket(_RATE_LIMIT)


class FinnhubAdapter(FinancialDataProvider):
    def __init__(self) -> None:
        import finnhub
        self._client = finnhub.Client(api_key=get_settings().finnhub_api_key)

    def _call(self, fn: Any, *args: Any) -> Any:
        _bucket.acquire()
        try:
            return fn(*args)
        except Exception as e:
            if "429" in str(e):
                logger.warning("Finnhub rate limited, sleeping 10s")
                time.sleep(10)
                return fn(*args)
            raise

    async def get_quote(self, ticker: str) -> dict[str, Any]:
        try:
            data = await asyncio.to_thread(self._call, self._client.quote, ticker)
            return {"price": data.get("c"), "high": data.get("h"), "low": data.get("l")}
        except Exception as e:
            logger.warning("Finnhub get_quote failed for %s: %s", ticker, e)
            return {}

    async def get_fundamentals(self, ticker: str) -> dict[str, Any]:
        try:
            profile = await asyncio.to_thread(self._call, self._client.company_basic_financials, ticker, "all")
            metrics = profile.get("metric", {})
            company = await asyncio.to_thread(self._call, self._client.company_profile2, **{"symbol": ticker})
            return {
                "pe_ratio": metrics.get("peBasicExclExtraTTM"),
                "market_cap": company.get("marketCapitalization", 0) * 1_000_000 if company else None,
                "dividend_yield": metrics.get("dividendYieldIndicatedAnnual"),
                "beta": metrics.get("beta"),
                "revenue_growth_yoy": metrics.get("revenueGrowthTTMYoy"),
                "debt_to_equity": metrics.get("totalDebt/totalEquityAnnual"),
                "analyst_consensus": None,
                "company_name": company.get("name") if company else None,
            }
        except Exception as e:
            logger.warning("Finnhub get_fundamentals failed for %s: %s", ticker, e)
            return {}

    async def get_technicals(self, ticker: str) -> dict[str, Any]:
        # Finnhub doesn't provide RSI/SMA directly; defer to Alpha Vantage for technicals
        return {}
