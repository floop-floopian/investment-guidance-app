from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel
import uuid


class ActionType(str, Enum):
    PIPELINE_STARTED = "PIPELINE_STARTED"
    MACRO_INGESTION_COMPLETE = "MACRO_INGESTION_COMPLETE"
    SENTIMENT_SCORED = "SENTIMENT_SCORED"
    ANALYSIS_COMPLETE = "ANALYSIS_COMPLETE"
    BARBELL_CLASSIFIED = "BARBELL_CLASSIFIED"
    ALLOCATION_GENERATED = "ALLOCATION_GENERATED"
    TELEGRAM_SENT = "TELEGRAM_SENT"
    TELEGRAM_FAILED = "TELEGRAM_FAILED"
    API_ERROR = "API_ERROR"
    MONITOR_CYCLE_COMPLETE = "MONITOR_CYCLE_COMPLETE"
    CRITICAL_SIGNAL_DETECTED = "CRITICAL_SIGNAL_DETECTED"
    PIPELINE_COMPLETED = "PIPELINE_COMPLETED"
    PIPELINE_FAILED = "PIPELINE_FAILED"


class LogLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class StateLogEntry(BaseModel):
    id: str = ""
    run_id: str
    action: ActionType
    timestamp: datetime
    level: LogLevel = LogLevel.INFO
    payload: dict[str, Any] = {}

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())
