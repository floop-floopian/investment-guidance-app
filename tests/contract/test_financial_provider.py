import inspect
import pytest
from src.adapters.base import FinancialDataProvider


def test_financial_provider_is_abstract():
    with pytest.raises(TypeError):
        FinancialDataProvider()  # type: ignore[abstract]


def test_financial_provider_requires_get_quote():
    assert "get_quote" in FinancialDataProvider.__abstractmethods__


def test_financial_provider_requires_get_fundamentals():
    assert "get_fundamentals" in FinancialDataProvider.__abstractmethods__


def test_financial_provider_requires_get_technicals():
    assert "get_technicals" in FinancialDataProvider.__abstractmethods__


def test_concrete_adapter_must_implement_all_methods():
    class IncompleteAdapter(FinancialDataProvider):
        async def get_quote(self, ticker: str) -> dict:
            return {}
        # Missing get_fundamentals and get_technicals

    with pytest.raises(TypeError):
        IncompleteAdapter()  # type: ignore[abstract]


def test_concrete_adapter_is_valid_when_complete():
    class FullAdapter(FinancialDataProvider):
        async def get_quote(self, ticker: str) -> dict:
            return {"price": 100.0}

        async def get_fundamentals(self, ticker: str) -> dict:
            return {"pe_ratio": 15.0}

        async def get_technicals(self, ticker: str) -> dict:
            return {"rsi_14": 55.0}

    adapter = FullAdapter()
    assert isinstance(adapter, FinancialDataProvider)


@pytest.mark.asyncio
async def test_get_quote_returns_dict():
    class ConcreteAdapter(FinancialDataProvider):
        async def get_quote(self, ticker: str) -> dict:
            return {"price": 42.0, "ticker": ticker}

        async def get_fundamentals(self, ticker: str) -> dict:
            return {}

        async def get_technicals(self, ticker: str) -> dict:
            return {}

    adapter = ConcreteAdapter()
    result = await adapter.get_quote("AAPL")
    assert isinstance(result, dict)
    assert "price" in result
