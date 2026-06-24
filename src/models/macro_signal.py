from datetime import datetime
from enum import Enum
from pydantic import BaseModel, field_validator


class SourceType(str, Enum):
    REDDIT = "REDDIT"
    RSS = "RSS"


class SentimentLabel(str, Enum):
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    BULLISH = "BULLISH"


class MacroSignal(BaseModel):
    id: str
    source_type: SourceType
    source_id: str
    title: str
    summary: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    ingested_at: datetime
    sentiment_score: float | None = None
    sentiment_label: SentimentLabel | None = None
    run_id: str | None = None

    @field_validator("sentiment_score")
    @classmethod
    def score_in_range(cls, v: float | None) -> float | None:
        if v is not None and not (-1.0 <= v <= 1.0):
            raise ValueError(f"sentiment_score must be in [-1.0, 1.0], got {v}")
        return v
