import pytest
from src.models.stock import Stock, BarbellClass


def _stock(**kwargs) -> Stock:
    defaults = {"ticker": "TEST", "price": 100.0}
    defaults.update(kwargs)
    return Stock(**defaults)


@pytest.fixture
def service():
    from src.services.barbell_service import BarbellService
    return BarbellService()


def test_safe_core_by_low_beta(service):
    stock = _stock(beta=0.5)
    result = service.classify(stock, macro_aggregate=0.0)
    assert result.barbell_class == BarbellClass.SAFE_CORE


def test_safe_core_by_low_pe(service):
    stock = _stock(pe_ratio=15.0, beta=1.5)
    result = service.classify(stock, macro_aggregate=0.0)
    assert result.barbell_class == BarbellClass.SAFE_CORE


def test_safe_core_by_dividend_yield(service):
    stock = _stock(dividend_yield=2.0, beta=1.5)
    result = service.classify(stock, macro_aggregate=0.0)
    assert result.barbell_class == BarbellClass.SAFE_CORE


def test_safe_core_by_large_market_cap(service):
    stock = _stock(market_cap=20_000_000_000.0, beta=1.5)
    result = service.classify(stock, macro_aggregate=0.0)
    assert result.barbell_class == BarbellClass.SAFE_CORE


def test_satellite_by_momentum_and_rsi(service):
    stock = _stock(momentum_90d=20.0, rsi_14=55.0, beta=1.5)
    result = service.classify(stock, macro_aggregate=0.0)
    assert result.barbell_class == BarbellClass.SATELLITE


def test_satellite_by_momentum_and_sentiment(service):
    stock = _stock(momentum_90d=20.0, beta=1.5)
    result = service.classify(stock, macro_aggregate=0.4)
    assert result.barbell_class == BarbellClass.SATELLITE


def test_excluded_when_no_thresholds_met(service):
    stock = _stock(beta=1.5, pe_ratio=50.0, dividend_yield=0.2, market_cap=1_000_000.0)
    result = service.classify(stock, macro_aggregate=0.0)
    assert result.barbell_class == BarbellClass.EXCLUDED


def test_excluded_when_no_data(service):
    stock = _stock()
    result = service.classify(stock, macro_aggregate=0.0)
    assert result.barbell_class == BarbellClass.EXCLUDED


def test_classify_all_returns_list(service):
    stocks = [_stock(ticker="A", beta=0.5), _stock(ticker="B", beta=2.0, momentum_90d=20.0, rsi_14=55.0)]
    results = service.classify_all(stocks, macro_aggregate=0.0)
    assert len(results) == 2


def test_custom_threshold_override(service):
    from src.config.settings import Settings
    from unittest.mock import patch

    custom = {"barbell_safe_beta_max": 0.3}
    stock = _stock(beta=0.5)  # beta=0.5 > 0.3 → should NOT be safe-core with custom threshold

    with patch.object(service, "_settings") as mock_s:
        mock_s.barbell_safe_beta_max = 0.3
        mock_s.barbell_safe_pe_max = 20.0
        mock_s.barbell_safe_dividend_yield_min = 1.5
        mock_s.barbell_safe_market_cap_min = 10_000_000_000.0
        mock_s.barbell_satellite_momentum_min = 15.0
        mock_s.barbell_satellite_rsi_min = 40.0
        mock_s.barbell_satellite_rsi_max = 70.0
        mock_s.barbell_satellite_analyst_min = 4.0
        mock_s.sentiment_critical_delta = 0.3
        result = service.classify(stock, macro_aggregate=0.0)
    assert result.barbell_class == BarbellClass.EXCLUDED
