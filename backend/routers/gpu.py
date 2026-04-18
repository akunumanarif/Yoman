import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from config import settings
from database import get_session
from models import GpuInstance, GpuInstanceResponse, GpuStatus
from services.vast import VastService
from services.ssh import SSHService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["gpu"])

SETUP_SCRIPT = (Path(__file__).parent.parent / "vast_scripts" / "setup.sh").read_text()


def get_gpu(session: Session) -> GpuInstance:
    """Get or create the singleton GPU instance record."""
    gpu = session.get(GpuInstance, 1)
    if not gpu:
        gpu = GpuInstance(id=1)
        session.add(gpu)
        session.commit()
        session.refresh(gpu)
    return gpu


@router.get("/gpu/status", response_model=GpuInstanceResponse)
async def gpu_status(session: Session = Depends(get_session)):
    """Get current GPU instance status."""
    gpu = get_gpu(session)

    # Sync status from vast.ai if we have an instance
    if gpu.instance_id and gpu.status not in (GpuStatus.OFFLINE, GpuStatus.RENTING):
        vast = VastService()
        info = vast.get_instance(gpu.instance_id)
        if info:
            if info.status == "running" and gpu.status != GpuStatus.SETUP:
                gpu.status = GpuStatus.RUNNING
                gpu.ssh_host = info.ssh_host
                gpu.ssh_port = info.ssh_port
            elif info.status in ("exited", "stopped"):
                gpu.status = GpuStatus.STOPPED
            elif info.status in ("error", "offline"):
                gpu.status = GpuStatus.ERROR
                gpu.error_message = f"Instance status: {info.status}"
        else:
            # Instance no longer exists on vast.ai
            gpu.status = GpuStatus.OFFLINE
            gpu.instance_id = None
            gpu.is_setup_done = False

        gpu.updated_at = datetime.now(timezone.utc)
        session.add(gpu)
        session.commit()
        session.refresh(gpu)

    return gpu


@router.get("/gpu/offers")
async def list_offers():
    """List available GPU offers for renting."""
    vast = VastService()
    offers = vast.search_offers()
    if not offers:
        return []

    preferred = [m.strip().lower() for m in settings.gpu_preferred_models.split(",")]

    # Filter by preferred models
    filtered = [
        o for o in offers
        if any(p in o.get("gpu_name", "").lower() for p in preferred)
    ]
    if not filtered:
        filtered = offers

    # Sort by price
    filtered.sort(key=lambda o: o.get("dph_total", float("inf")))

    # Return top 20 with relevant fields
    return [
        {
            "id": o.get("id"),
            "gpu_name": o.get("gpu_name", "Unknown"),
            "gpu_ram": round(o.get("gpu_ram", 0)),
            "cpu_cores": o.get("cpu_cores_effective", o.get("cpu_cores", 0)),
            "disk_space": round(o.get("disk_space", 0)),
            "dph_total": o.get("dph_total", 0),
            "reliability": o.get("reliability2", o.get("reliability")),
        }
        for o in filtered[:20]
    ]


@router.get("/gpu/instances")
async def list_my_instances(session: Session = Depends(get_session)):
    """List all instances on the vast.ai account for connecting."""
    gpu = get_gpu(session)
    vast = VastService()
    instances = vast.list_instances()

    # Filter out the one we're already tracking
    return [
        {
            "id": inst.get("id"),
            "gpu_name": inst.get("gpu_name", "Unknown"),
            "gpu_ram": round(inst.get("gpu_ram", 0)),
            "status": inst.get("actual_status", inst.get("status_msg", "unknown")),
            "cost_per_hour": inst.get("dph_total", 0),
            "cur_state": inst.get("cur_state", "unknown"),
        }
        for inst in instances
        if inst.get("id") != gpu.instance_id
    ]


class RentRequest(BaseModel):
    offer_id: int


class ConnectRequest(BaseModel):
    instance_id: int


@router.post("/gpu/rent", response_model=GpuInstanceResponse)
async def rent_gpu(req: RentRequest, session: Session = Depends(get_session)):
    """Rent a GPU instance from a specific offer."""
    gpu = get_gpu(session)

    if gpu.status in (GpuStatus.RUNNING, GpuStatus.RENTING, GpuStatus.SETUP):
        raise HTTPException(400, f"GPU already {gpu.status.value}")

    vast = VastService()

    # Get offer details for display
    offers = vast.search_offers()
    offer = next((o for o in offers if o.get("id") == req.offer_id), None)

    gpu.status = GpuStatus.RENTING
    gpu.gpu_name = offer.get("gpu_name", "Unknown") if offer else "Unknown"
    gpu.cost_per_hour = offer.get("dph_total") if offer else None
    gpu.error_message = None
    gpu.updated_at = datetime.now(timezone.utc)
    session.add(gpu)
    session.commit()

    # Create instance
    instance_id = vast.create_instance(req.offer_id)
    if not instance_id:
        gpu.status = GpuStatus.ERROR
        gpu.error_message = "Failed to create instance"
        gpu.updated_at = datetime.now(timezone.utc)
        session.add(gpu)
        session.commit()
        raise HTTPException(503, "Failed to create instance on vast.ai")

    gpu.instance_id = instance_id
    gpu.updated_at = datetime.now(timezone.utc)
    session.add(gpu)
    session.commit()

    # Wait for running in background
    asyncio.create_task(_wait_and_setup(instance_id))

    session.refresh(gpu)
    return gpu


@router.post("/gpu/connect", response_model=GpuInstanceResponse)
async def connect_gpu(req: ConnectRequest, session: Session = Depends(get_session)):
    """Connect an existing vast.ai instance (rented manually from UI)."""
    gpu = get_gpu(session)

    if gpu.status in (GpuStatus.RUNNING, GpuStatus.RENTING, GpuStatus.SETUP):
        raise HTTPException(400, f"GPU already {gpu.status.value}. Destroy it first.")

    vast = VastService()
    info = vast.get_instance(req.instance_id)
    if not info:
        raise HTTPException(404, f"Instance {req.instance_id} not found on vast.ai")

    gpu.instance_id = req.instance_id
    gpu.ssh_host = info.ssh_host
    gpu.ssh_port = info.ssh_port
    gpu.error_message = None
    gpu.updated_at = datetime.now(timezone.utc)

    # Try to get GPU name from vast.ai
    try:
        result = vast.client.show_instance(id=req.instance_id)
        import json
        if isinstance(result, str):
            result = json.loads(result)
        if isinstance(result, dict):
            gpu.gpu_name = result.get("gpu_name", "Unknown")
            gpu.cost_per_hour = result.get("dph_total")
    except Exception:
        gpu.gpu_name = "Unknown"

    if info.status == "running":
        # Instance is running, start setup
        gpu.status = GpuStatus.SETUP
        session.add(gpu)
        session.commit()
        asyncio.create_task(_run_setup(req.instance_id, info.ssh_host, info.ssh_port))
    else:
        # Instance exists but not running yet
        gpu.status = GpuStatus.RENTING
        session.add(gpu)
        session.commit()
        asyncio.create_task(_wait_and_setup(req.instance_id))

    session.refresh(gpu)
    return gpu


@router.post("/gpu/start", response_model=GpuInstanceResponse)
async def start_gpu(session: Session = Depends(get_session)):
    """Start a stopped GPU instance."""
    gpu = get_gpu(session)

    if not gpu.instance_id:
        raise HTTPException(400, "No GPU instance exists. Rent one first.")
    if gpu.status == GpuStatus.RUNNING:
        raise HTTPException(400, "GPU is already running")

    vast = VastService()
    try:
        vast.client.start_instance(ID=gpu.instance_id)
    except Exception as e:
        raise HTTPException(503, f"Failed to start instance: {e}")

    gpu.status = GpuStatus.RENTING  # Will become RUNNING after polling
    gpu.error_message = None
    gpu.updated_at = datetime.now(timezone.utc)
    session.add(gpu)
    session.commit()

    asyncio.create_task(_wait_for_running(gpu.instance_id))

    session.refresh(gpu)
    return gpu


@router.post("/gpu/stop", response_model=GpuInstanceResponse)
async def stop_gpu(session: Session = Depends(get_session)):
    """Stop the GPU instance (keeps storage, stops compute billing)."""
    gpu = get_gpu(session)

    if not gpu.instance_id:
        raise HTTPException(400, "No GPU instance exists")
    if gpu.status == GpuStatus.STOPPED:
        raise HTTPException(400, "GPU is already stopped")

    vast = VastService()
    try:
        vast.client.stop_instance(ID=gpu.instance_id)
    except Exception as e:
        raise HTTPException(503, f"Failed to stop instance: {e}")

    gpu.status = GpuStatus.STOPPED
    gpu.updated_at = datetime.now(timezone.utc)
    session.add(gpu)
    session.commit()

    session.refresh(gpu)
    return gpu


@router.post("/gpu/destroy", response_model=GpuInstanceResponse)
async def destroy_gpu(session: Session = Depends(get_session)):
    """Destroy the GPU instance completely."""
    gpu = get_gpu(session)

    if not gpu.instance_id:
        raise HTTPException(400, "No GPU instance exists")

    vast = VastService()
    try:
        vast.destroy_instance(gpu.instance_id)
    except Exception as e:
        logger.warning(f"Destroy instance error: {e}")

    gpu.instance_id = None
    gpu.status = GpuStatus.OFFLINE
    gpu.gpu_name = None
    gpu.ssh_host = None
    gpu.ssh_port = None
    gpu.cost_per_hour = None
    gpu.is_setup_done = False
    gpu.error_message = None
    gpu.updated_at = datetime.now(timezone.utc)
    session.add(gpu)
    session.commit()

    session.refresh(gpu)
    return gpu


@router.post("/gpu/retry-setup", response_model=GpuInstanceResponse)
async def retry_setup(session: Session = Depends(get_session)):
    """Re-run setup on the current instance (e.g. after a failed setup)."""
    gpu = get_gpu(session)

    if not gpu.instance_id or not gpu.ssh_host or not gpu.ssh_port:
        raise HTTPException(400, "No running GPU instance to retry setup on.")
    if gpu.status not in (GpuStatus.ERROR, GpuStatus.RUNNING):
        raise HTTPException(400, f"Cannot retry setup when status is {gpu.status.value}")

    gpu.status = GpuStatus.SETUP
    gpu.error_message = None
    gpu.updated_at = datetime.now(timezone.utc)
    session.add(gpu)
    session.commit()

    asyncio.create_task(_run_setup(gpu.instance_id, gpu.ssh_host, gpu.ssh_port))

    session.refresh(gpu)
    return gpu


async def _run_setup(instance_id: int, ssh_host: str, ssh_port: int):
    """Background: run Wan 2.2 setup on an already-running instance."""
    from database import engine

    try:
        with SSHService(ssh_host, ssh_port) as ssh:
            ssh.execute("mkdir -p /workspace/inputs /workspace/output")
            ssh.execute(f"cat << 'SETUP_EOF' > /workspace/setup.sh\n{SETUP_SCRIPT}\nSETUP_EOF")
            ssh.execute("chmod +x /workspace/setup.sh")
            stdout, stderr, exit_code = ssh.execute("bash /workspace/setup.sh", timeout=7200)

            with Session(engine) as session:
                gpu = get_gpu(session)
                if exit_code != 0:
                    gpu.status = GpuStatus.ERROR
                    gpu.error_message = f"Setup failed: {stderr[:300]}"
                else:
                    gpu.status = GpuStatus.RUNNING
                    gpu.is_setup_done = True
                gpu.updated_at = datetime.now(timezone.utc)
                session.add(gpu)
                session.commit()
    except Exception as e:
        logger.exception(f"Setup error: {e}")
        with Session(engine) as session:
            gpu = get_gpu(session)
            gpu.status = GpuStatus.ERROR
            gpu.error_message = str(e)
            gpu.updated_at = datetime.now(timezone.utc)
            session.add(gpu)
            session.commit()


async def _wait_and_setup(instance_id: int):
    """Background: wait for instance to run, then setup Wan 2.2."""
    from database import engine
    vast = VastService()

    info = vast.wait_for_running(instance_id)

    with Session(engine) as session:
        gpu = get_gpu(session)
        if not info:
            gpu.status = GpuStatus.ERROR
            gpu.error_message = "Instance failed to start"
            session.add(gpu)
            session.commit()
            return

        gpu.ssh_host = info.ssh_host
        gpu.ssh_port = info.ssh_port
        gpu.status = GpuStatus.SETUP
        gpu.updated_at = datetime.now(timezone.utc)
        session.add(gpu)
        session.commit()

    # Run setup script (install Wan 2.2 + download model)
    try:
        with SSHService(info.ssh_host, info.ssh_port) as ssh:
            ssh.execute("mkdir -p /workspace/inputs /workspace/output")
            ssh.execute(f"cat << 'SETUP_EOF' > /workspace/setup.sh\n{SETUP_SCRIPT}\nSETUP_EOF")
            ssh.execute("chmod +x /workspace/setup.sh")
            stdout, stderr, exit_code = ssh.execute("bash /workspace/setup.sh", timeout=7200)

            with Session(engine) as session:
                gpu = get_gpu(session)
                if exit_code != 0:
                    gpu.status = GpuStatus.ERROR
                    gpu.error_message = f"Setup failed: {stderr[:300]}"
                else:
                    gpu.status = GpuStatus.RUNNING
                    gpu.is_setup_done = True
                gpu.updated_at = datetime.now(timezone.utc)
                session.add(gpu)
                session.commit()
    except Exception as e:
        logger.exception(f"Setup error: {e}")
        with Session(engine) as session:
            gpu = get_gpu(session)
            gpu.status = GpuStatus.ERROR
            gpu.error_message = str(e)
            gpu.updated_at = datetime.now(timezone.utc)
            session.add(gpu)
            session.commit()


async def _wait_for_running(instance_id: int):
    """Background: wait for a started instance to become running."""
    from database import engine
    vast = VastService()

    info = vast.wait_for_running(instance_id)

    with Session(engine) as session:
        gpu = get_gpu(session)
        if info:
            gpu.status = GpuStatus.RUNNING
            gpu.ssh_host = info.ssh_host
            gpu.ssh_port = info.ssh_port
        else:
            gpu.status = GpuStatus.ERROR
            gpu.error_message = "Instance failed to start"
        gpu.updated_at = datetime.now(timezone.utc)
        session.add(gpu)
        session.commit()
