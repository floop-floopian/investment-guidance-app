from src.models.stock import Stock, BarbellClass
from src.config.settings import get_settings


class BarbellService:
    def __init__(self) -> None:
        self._settings = get_settings()

    def classify(self, stock: Stock, macro_aggregate: float) -> Stock:
        s = self._settings

        safe_qualifiers = 0
        if stock.beta is not None and stock.beta <= s.barbell_safe_beta_max:
            safe_qualifiers += 1
        if stock.pe_ratio is not None and stock.pe_ratio <= s.barbell_safe_pe_max:
            safe_qualifiers += 1
        if stock.dividend_yield is not None and stock.dividend_yield >= s.barbell_safe_dividend_yield_min:
            safe_qualifiers += 1
        if stock.market_cap is not None and stock.market_cap >= s.barbell_safe_market_cap_min:
            safe_qualifiers += 1

        if safe_qualifiers >= 1:
            return stock.model_copy(update={"barbell_class": BarbellClass.SAFE_CORE})

        sat_qualifiers = 0
        if stock.momentum_90d is not None and stock.momentum_90d >= s.barbell_satellite_momentum_min:
            sat_qualifiers += 1
        if (stock.rsi_14 is not None
                and s.barbell_satellite_rsi_min <= stock.rsi_14 <= s.barbell_satellite_rsi_max):
            sat_qualifiers += 1
        if macro_aggregate >= s.sentiment_critical_delta:
            sat_qualifiers += 1
        if stock.analyst_consensus is not None and stock.analyst_consensus >= s.barbell_satellite_analyst_min:
            sat_qualifiers += 1

        if sat_qualifiers >= 2:
            return stock.model_copy(update={"barbell_class": BarbellClass.SATELLITE})

        return stock.model_copy(update={"barbell_class": BarbellClass.EXCLUDED})

    def classify_all(self, stocks: list[Stock], macro_aggregate: float) -> list[Stock]:
        return [self.classify(s, macro_aggregate) for s in stocks]
