from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Vast.ai
    vast_api_key: str = ""

    # Paths
    upload_dir: Path = Path("./uploads")
    output_dir: Path = Path("./outputs")
    db_path: Path = Path("./data/yoman.db")

    # GPU Preferences
    gpu_min_vram: int = 24
    gpu_max_bid_price: float = 0.30
    gpu_preferred_models: str = "RTX 4090,A100,H100"

    # Vast.ai Docker image for GPU instances
    vast_docker_image: str = "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-devel"

    # Worker
    worker_poll_interval: int = 10  # seconds
    max_retries: int = 3

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# Ensure directories exist
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.output_dir.mkdir(parents=True, exist_ok=True)
settings.db_path.parent.mkdir(parents=True, exist_ok=True)
