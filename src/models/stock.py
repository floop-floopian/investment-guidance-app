from datetime import datetime
from enum import Enum
from pydantic import BaseModel, field_validator


class BarbellClass(str, Enum):
    SAFE_CORE = "SAFE_CORE"
    SATELLITE = "SATELLITE"
    EXCLUDED = "EXCLUDED"


class VolatilityTier(str, Enum):
    HIGH = "HIGH"
    MED = "MED"
    LOW = "LOW"


class DataSource(str, Enum):
    FINNHUB = "FINNHUB"
    ALPHA_VANTAGE = "ALPHA_VANTAGE"
    PARTIAL = "PARTIAL"


class Stock(BaseModel):
    ticker: str
    company_name: str | None = None
    price: float | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    revenue_growth_yoy: float | None = None
    debt_to_equity: float | None = None
    rsi_14: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    momentum_90d: float | None = None
    analyst_consensus: float | None = None
    volatility_tier: VolatilityTier | None = None
    barbell_class: BarbellClass = BarbellClass.EXCLUDED
    risk_reward_score: float = 0.0
    reasoning: str | None = None
    data_source: DataSource | None = None
    analyzed_at: datetime | None = None
    run_id: str | None = None

    @field_validator("rsi_14")
    @classmethod
    def rsi_in_range(cls, v: float | None) -> float | None:
        if v is not None and not (0 <= v <= 100):
            raise ValueError(f"rsi_14 must be in [0, 100], got {v}")
        return v

    @field_validator("risk_reward_score")
    @classmethod
    def score_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"risk_reward_score must be in [0.0, 1.0], got {v}")
        return v
