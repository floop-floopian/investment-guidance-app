import logging
from datetime import datetime, timezone
from src.adapters.base import FinancialDataProvider
from src.models.stock import Stock, DataSource, VolatilityTier
from src.models.state_log import ActionType, LogLevel
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


def _tier_from_beta(beta: float | None, settings) -> VolatilityTier:
    if beta is None:
        return VolatilityTier.MED
    if beta >= settings.barbell_satellite_beta_min:
        return VolatilityTier.HIGH
    if beta <= settings.barbell_safe_beta_max:
        return VolatilityTier.LOW
    return VolatilityTier.MED


class AnalysisService:
    def __init__(
        self,
        primary: FinancialDataProvider,
        fallback: FinancialDataProvider | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._settings = get_settings()

    async def analyse_tickers(
        self,
        tickers: list[str],
        run_id: str,
        log_error_fn=None,
    ) -> list[Stock]:
        stocks: list[Stock] = []
        for ticker in tickers:
            try:
                quote = await self._primary.get_quote(ticker)
                fundamentals = await self._primary.get_fundamentals(ticker)
                technicals = await self._primary.get_technicals(ticker)

                # Fallback for technicals if primary returns empty
                if not technicals and self._fallback:
                    try:
                        technicals = await self._fallback.get_technicals(ticker)
                        source = DataSource.PARTIAL if (quote or fundamentals) else DataSource.ALPHA_VANTAGE
                    except Exception as e:
                        logger.warning("Fallback technicals failed for %s: %s", ticker, e)
                        source = DataSource.PARTIAL
                else:
                    source = DataSource.FINNHUB if quote else DataSource.PARTIAL

                beta = fundamentals.get("beta")
                stock = Stock(
                    ticker=ticker,
                    company_name=fundamentals.get("company_name"),
                    price=quote.get("price"),
                    market_cap=fundamentals.get("market_cap"),
                    pe_ratio=fundamentals.get("pe_ratio"),
                    dividend_yield=fundamentals.get("dividend_yield"),
                    beta=beta,
                    revenue_growth_yoy=fundamentals.get("revenue_growth_yoy"),
                    debt_to_equity=fundamentals.get("debt_to_equity"),
                    rsi_14=technicals.get("rsi_14"),
                    sma_50=technicals.get("sma_50"),
                    sma_200=technicals.get("sma_200"),
                    momentum_90d=technicals.get("momentum_90d"),
                    analyst_consensus=fundamentals.get("analyst_consensus"),
                    volatility_tier=_tier_from_beta(beta, self._settings),
                    data_source=source,
                    analyzed_at=datetime.now(timezone.utc),
                    run_id=run_id,
                )
                stocks.append(stock)
            except Exception as e:
                logger.warning("Analysis failed for %s: %s", ticker, e)
                if log_error_fn:
                    log_error_fn(ActionType.API_ERROR, LogLevel.WARNING, {
                        "ticker": ticker, "error": str(e)
                    })
        return stocks
