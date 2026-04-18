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


class GpuStatus(str, Enum):
    OFFLINE = "offline"       # No instance exists
    RENTING = "renting"       # Creating instance, waiting for it to be ready
    RUNNING = "running"       # Instance is running and ready
    STOPPED = "stopped"       # Instance stopped (storage only billing)
    SETUP = "setup"           # Installing Wan 2.2 / downloading model
    ERROR = "error"


class GpuInstance(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)  # Singleton row
    instance_id: int | None = None                 # Vast.ai instance ID
    status: GpuStatus = Field(default=GpuStatus.OFFLINE)
    gpu_name: str | None = None
    ssh_host: str | None = None
    ssh_port: int | None = None
    cost_per_hour: float | None = None
    error_message: str | None = None
    is_setup_done: bool = Field(default=False)     # Model installed?
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GpuInstanceResponse(SQLModel):
    instance_id: int | None
    status: GpuStatus
    gpu_name: str | None
    ssh_host: str | None
    ssh_port: int | None
    cost_per_hour: float | None
    error_message: str | None
    is_setup_done: bool
    updated_at: datetime


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
