import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class JobStatus(str, Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    PROCESSING = "processing"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    status: JobStatus = Field(default=JobStatus.PENDING)
    image_path: str
    video_path: str
    result_path: str | None = None
    instance_id: str | None = None
    retry_count: int = Field(default=0)
    error_message: str | None = None
    resolution: str = Field(default="720")  # "480" or "720"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JobCreate(SQLModel):
    resolution: str = "720"


class JobResponse(SQLModel):
    id: str
    status: JobStatus
    result_path: str | None
    instance_id: str | None
    retry_count: int
    error_message: str | None
    resolution: str
    created_at: datetime
    updated_at: datetime
