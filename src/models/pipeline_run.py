from datetime import datetime
from enum import Enum
from pydantic import BaseModel
import uuid


class TriggerType(str, Enum):
    ON_DEMAND = "ON_DEMAND"
    SCHEDULED = "SCHEDULED"


class RunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class PipelineRun(BaseModel):
    id: str = ""
    trigger_type: TriggerType
    started_at: datetime
    completed_at: datetime | None = None
    status: RunStatus = RunStatus.RUNNING
    capital_input: float | None = None
    macro_signal_count: int = 0
    shortlist_count: int = 0
    allocation_count: int = 0
    telegram_sent: bool = False
    error_message: str | None = None

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())
