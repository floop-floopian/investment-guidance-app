from enum import Enum
from pydantic import BaseModel, field_validator
import uuid


class AllocationBand(str, Enum):
    SAFE_CORE = "SAFE_CORE"
    SATELLITE = "SATELLITE"


class Allocation(BaseModel):
    id: str = ""
    ticker: str
    band: AllocationBand
    amount_usd: float
    percentage: float
    rationale: str | None = None
    run_id: str | None = None

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())

    @field_validator("percentage")
    @classmethod
    def pct_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 100.0):
            raise ValueError(f"percentage must be in [0, 100], got {v}")
        return v

    @field_validator("amount_usd")
    @classmethod
    def amount_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"amount_usd must be >= 0, got {v}")
        return v
