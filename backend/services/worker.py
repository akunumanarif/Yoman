import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, select

from config import settings
from database import engine
from models import Job, JobStatus
from services.vast import VastService
from services.ssh import SSHService

logger = logging.getLogger(__name__)

SETUP_SCRIPT = (Path(__file__).parent.parent / "vast_scripts" / "setup.sh").read_text()
INFERENCE_SCRIPT = (Path(__file__).parent.parent / "vast_scripts" / "inference.sh").read_text()


class JobWorker:
    def __init__(self):
        self.vast = VastService()
        self._running = False

    async def start(self):
        """Start the background worker loop."""
        self._running = True
        logger.info("Worker started")
        while self._running:
            try:
                await self._process_pending_jobs()
                await self._check_active_jobs()
            except Exception as e:
                logger.exception(f"Worker loop error: {e}")
            await asyncio.sleep(settings.worker_poll_interval)

    def stop(self):
        self._running = False
        logger.info("Worker stopped")

    async def _process_pending_jobs(self):
        """Pick up pending jobs and start GPU provisioning."""
        with Session(engine) as session:
            jobs = session.exec(
                select(Job).where(Job.status == JobStatus.PENDING)
            ).all()

            for job in jobs:
                logger.info(f"Processing job {job.id}")
                try:
                    await self._provision_and_run(job, session)
                except Exception as e:
                    logger.exception(f"Failed to process job {job.id}: {e}")
                    job.status = JobStatus.FAILED
                    job.error_message = str(e)
                    job.updated_at = datetime.now(timezone.utc)
                    session.add(job)
                    session.commit()

    async def _provision_and_run(self, job: Job, session: Session):
        """Full lifecycle: provision GPU → upload → run → download → cleanup."""
        # Step 1: Find GPU
        job.status = JobStatus.PROVISIONING
        job.updated_at = datetime.now(timezone.utc)
        session.add(job)
        session.commit()

        offer = self.vast.find_cheapest_gpu()
        if not offer:
            raise RuntimeError("No suitable GPU offer found on vast.ai")

        # Step 2: Create instance
        offer_id = offer.get("id")
        instance_id = self.vast.create_instance(offer_id)
        if not instance_id:
            raise RuntimeError(f"Failed to create instance from offer {offer_id}")

        job.instance_id = str(instance_id)
        job.updated_at = datetime.now(timezone.utc)
        session.add(job)
        session.commit()

        try:
            # Step 3: Wait for instance to be running
            info = self.vast.wait_for_running(instance_id)
            if not info:
                raise RuntimeError(f"Instance {instance_id} failed to start")

            # Step 4: Run the job on the instance
            job.status = JobStatus.PROCESSING
            job.updated_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()

            await self._run_on_instance(job, info.ssh_host, info.ssh_port)

            # Step 5: Mark as completed
            job.status = JobStatus.COMPLETED
            job.updated_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()
            logger.info(f"Job {job.id} completed successfully")

        except Exception as e:
            logger.error(f"Job {job.id} failed on instance {instance_id}: {e}")
            await self._handle_failure(job, session, e)
        finally:
            # Always clean up the instance
            try:
                self.vast.destroy_instance(instance_id)
            except Exception:
                logger.warning(f"Failed to destroy instance {instance_id}")

    async def _run_on_instance(self, job: Job, ssh_host: str, ssh_port: int):
        """Upload files, run setup + inference, download result."""
        with SSHService(ssh_host, ssh_port) as ssh:
            # Upload setup script and run it
            ssh.execute("mkdir -p /workspace/inputs /workspace/output")

            # Run setup (install Wan2.2 + download model)
            logger.info(f"Job {job.id}: Running setup script...")
            ssh.execute(f"cat << 'SETUP_EOF' > /workspace/setup.sh\n{SETUP_SCRIPT}\nSETUP_EOF")
            ssh.execute("chmod +x /workspace/setup.sh")
            stdout, stderr, exit_code = ssh.execute("bash /workspace/setup.sh", timeout=7200)
            if exit_code != 0:
                raise RuntimeError(f"Setup failed: {stderr[:500]}")

            # Upload input files
            logger.info(f"Job {job.id}: Uploading input files...")
            ssh.upload(job.image_path, "/workspace/inputs/image" + Path(job.image_path).suffix)
            ssh.upload(job.video_path, "/workspace/inputs/video" + Path(job.video_path).suffix)

            # Upload and run inference script
            ssh.execute(f"cat << 'INF_EOF' > /workspace/inference.sh\n{INFERENCE_SCRIPT}\nINF_EOF")
            ssh.execute("chmod +x /workspace/inference.sh")

            image_ext = Path(job.image_path).suffix
            video_ext = Path(job.video_path).suffix

            logger.info(f"Job {job.id}: Running inference...")
            stdout, stderr, exit_code = ssh.execute(
                f"bash /workspace/inference.sh "
                f"/workspace/inputs/image{image_ext} "
                f"/workspace/inputs/video{video_ext} "
                f"/workspace/output "
                f"{job.resolution}",
                timeout=7200,
            )
            if exit_code != 0:
                raise RuntimeError(f"Inference failed: {stderr[:500]}")

            # Check for completion marker
            if not ssh.file_exists("/workspace/output/DONE"):
                raise RuntimeError("Inference did not produce completion marker")

            # Download result
            output_dir = settings.output_dir / job.id
            output_dir.mkdir(parents=True, exist_ok=True)
            result_path = str(output_dir / "result.mp4")

            logger.info(f"Job {job.id}: Downloading result...")
            ssh.download("/workspace/output/result.mp4", result_path)

            job.result_path = result_path

    async def _handle_failure(self, job: Job, session: Session, error: Exception):
        """Handle job failure with retry logic."""
        job.retry_count += 1
        job.error_message = str(error)
        job.updated_at = datetime.now(timezone.utc)

        if job.retry_count < settings.max_retries:
            job.status = JobStatus.RETRYING
            logger.info(f"Job {job.id}: Retrying ({job.retry_count}/{settings.max_retries})")
            # Reset to pending so worker picks it up again
            job.status = JobStatus.PENDING
        else:
            job.status = JobStatus.FAILED
            logger.error(f"Job {job.id}: Max retries exceeded")

        session.add(job)
        session.commit()

    async def _check_active_jobs(self):
        """Check for preempted instances on active jobs."""
        with Session(engine) as session:
            active_jobs = session.exec(
                select(Job).where(
                    Job.status.in_([JobStatus.PROVISIONING, JobStatus.PROCESSING])
                )
            ).all()

            for job in active_jobs:
                if not job.instance_id:
                    continue
                info = self.vast.get_instance(int(job.instance_id))
                if info and info.status in ("exited", "error", "offline"):
                    logger.warning(
                        f"Job {job.id}: Instance {job.instance_id} was preempted "
                        f"(status: {info.status})"
                    )
                    await self._handle_failure(
                        job, session,
                        RuntimeError(f"Instance preempted: {info.status}"),
                    )


# Singleton worker instance
worker = JobWorker()
