import pytest
from src.models.stock import Stock, BarbellClass
from src.models.allocation import Allocation, AllocationBand


def _stock(ticker: str, cls: BarbellClass, score: float = 0.5) -> Stock:
    return Stock(ticker=ticker, barbell_class=cls, risk_reward_score=score, price=100.0)


@pytest.fixture
def service():
    from src.services.allocation_service import AllocationService
    return AllocationService()


@pytest.mark.asyncio
async def test_60_40_band_split(service):
    stocks = [
        _stock("A", BarbellClass.SAFE_CORE, 0.8),
        _stock("B", BarbellClass.SAFE_CORE, 0.6),
        _stock("C", BarbellClass.SATELLITE, 0.9),
    ]
    allocations = await service.allocate(stocks, capital=10_000.0, run_id="r1")
    safe_total = sum(a.amount_usd for a in allocations if a.band == AllocationBand.SAFE_CORE)
    sat_total = sum(a.amount_usd for a in allocations if a.band == AllocationBand.SATELLITE)
    assert safe_total == pytest.approx(6_000.0, rel=0.01)
    assert sat_total == pytest.approx(4_000.0, rel=0.01)


@pytest.mark.asyncio
async def test_allocation_sum_does_not_exceed_capital(service):
    stocks = [_stock(f"T{i}", BarbellClass.SAFE_CORE, 0.5) for i in range(5)]
    allocations = await service.allocate(stocks, capital=5_000.0, run_id="r1")
    total = sum(a.amount_usd for a in allocations)
    assert total <= 5_000.0 + 0.01  # float tolerance


@pytest.mark.asyncio
async def test_proportional_weighting_by_risk_reward_score(service):
    stocks = [
        _stock("HIGH", BarbellClass.SAFE_CORE, 0.9),
        _stock("LOW", BarbellClass.SAFE_CORE, 0.1),
    ]
    allocations = await service.allocate(stocks, capital=10_000.0, run_id="r1")
    high_alloc = next(a for a in allocations if a.ticker == "HIGH")
    low_alloc = next(a for a in allocations if a.ticker == "LOW")
    assert high_alloc.amount_usd > low_alloc.amount_usd


@pytest.mark.asyncio
async def test_minimum_position_enforcement(service):
    # Capital too low for minimum position size ($500 default)
    stocks = [_stock("A", BarbellClass.SAFE_CORE, 0.5) for _ in range(20)]
    allocations = await service.allocate(stocks, capital=100.0, run_id="r1")
    # All positions should be filtered out or result in empty allocation
    assert all(a.amount_usd >= 0 for a in allocations)
    total = sum(a.amount_usd for a in allocations)
    assert total <= 100.0


@pytest.mark.asyncio
async def test_ratio_overridable(service):
    from unittest.mock import patch
    stocks = [
        _stock("A", BarbellClass.SAFE_CORE, 0.8),
        _stock("B", BarbellClass.SATELLITE, 0.9),
    ]
    with patch.object(service, "_settings") as mock_s:
        mock_s.barbell_safe_core_ratio = 0.7
        mock_s.capital_min_position_usd = 0.0
        allocations = await service.allocate(stocks, capital=10_000.0, run_id="r1")
    safe_total = sum(a.amount_usd for a in allocations if a.band == AllocationBand.SAFE_CORE)
    assert safe_total == pytest.approx(7_000.0, rel=0.02)


@pytest.mark.asyncio
async def test_returns_list_of_allocations(service):
    stocks = [_stock("A", BarbellClass.SAFE_CORE, 0.5)]
    result = await service.allocate(stocks, capital=5_000.0, run_id="r1")
    assert isinstance(result, list)
    assert all(isinstance(a, Allocation) for a in result)
