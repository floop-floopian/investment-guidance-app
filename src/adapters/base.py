from abc import ABC, abstractmethod
from typing import Any


class MacroSignalProvider(ABC):
    @abstractmethod
    async def fetch_signals(self) -> list[Any]:
        """Fetch macro signals. Returns List[MacroSignal]."""
        ...


class FinancialDataProvider(ABC):
    @abstractmethod
    async def get_quote(self, ticker: str) -> dict[str, Any]:
        """Return current price data for ticker."""
        ...

    @abstractmethod
    async def get_fundamentals(self, ticker: str) -> dict[str, Any]:
        """Return fundamental metrics for ticker (P/E, market cap, etc.)."""
        ...

    @abstractmethod
    async def get_technicals(self, ticker: str) -> dict[str, Any]:
        """Return technical indicators for ticker (RSI, SMA, momentum)."""
        ...


class NotificationProvider(ABC):
    @abstractmethod
    async def send_message(self, text: str) -> bool:
        """Send a notification message. Returns True on success."""
        ...
