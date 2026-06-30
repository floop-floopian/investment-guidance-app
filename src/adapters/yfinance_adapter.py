import asyncio
import logging
from typing import Any
import pandas as pd
from src.adapters.base import FinancialDataProvider

logger = logging.getLogger(__name__)


def _compute_rsi(close: pd.Series, period: int = 14) -> float | None:
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("inf"))
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return float(val) if pd.notna(val) else None


class YFinanceAdapter(FinancialDataProvider):
    async def get_quote(self, ticker: str) -> dict[str, Any]:
        return {}

    async def get_fundamentals(self, ticker: str) -> dict[str, Any]:
        return {}

    async def get_technicals(self, ticker: str) -> dict[str, Any]:
        try:
            import yfinance as yf
            hist = await asyncio.to_thread(
                lambda: yf.Ticker(ticker).history(period="1y", auto_adjust=True)
            )
            if hist.empty:
                logger.warning("yfinance returned no data for %s", ticker)
                return {}

            close = hist["Close"]

            rsi_14 = _compute_rsi(close)

            sma_50_val = close.rolling(50).mean().iloc[-1]
            sma_50 = float(sma_50_val) if pd.notna(sma_50_val) else None

            sma_200_val = close.rolling(200).mean().iloc[-1]
            sma_200 = float(sma_200_val) if pd.notna(sma_200_val) else None

            momentum_90d = None
            if len(close) >= 90:
                latest = float(close.iloc[-1])
                past = float(close.iloc[-90])
                if past != 0:
                    momentum_90d = (latest - past) / past * 100

            return {
                "rsi_14": rsi_14,
                "sma_50": sma_50,
                "sma_200": sma_200,
                "momentum_90d": momentum_90d,
            }
        except Exception as e:
            logger.warning("yfinance technicals failed for %s: %s", ticker, e)
            return {}
