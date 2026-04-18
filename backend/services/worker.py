import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, select

from config import settings
from database import engine
from models import Job, JobStatus, GpuInstance, GpuStatus
from services.ssh import SSHService

logger = logging.getLogger(__name__)

INFERENCE_SCRIPT = (Path(__file__).parent.parent / "vast_scripts" / "inference.sh").read_text()


class JobWorker:
    def __init__(self):
        self._running = False

    async def start(self):
        """Start the background worker loop."""
        self._running = True
        logger.info("Worker started")
        while self._running:
            try:
                await self._process_pending_jobs()
            except Exception as e:
                logger.exception(f"Worker loop error: {e}")
            await asyncio.sleep(settings.worker_poll_interval)

    def stop(self):
        self._running = False
        logger.info("Worker stopped")

    def _get_gpu(self, session: Session) -> GpuInstance | None:
        """Get the current GPU instance if running and setup is done."""
        gpu = session.get(GpuInstance, 1)
        if gpu and gpu.status == GpuStatus.RUNNING and gpu.is_setup_done:
            return gpu
        return None

    async def _process_pending_jobs(self):
        """Pick up pending jobs and run on the existing GPU instance."""
        with Session(engine) as session:
            jobs = session.exec(
                select(Job).where(Job.status == JobStatus.PENDING)
            ).all()

            if not jobs:
                return

            gpu = self._get_gpu(session)
            if not gpu:
                return  # No GPU running, jobs wait

            for job in jobs:
                logger.info(f"Processing job {job.id}")
                try:
                    job.status = JobStatus.PROCESSING
                    job.instance_id = str(gpu.instance_id)
                    job.updated_at = datetime.now(timezone.utc)
                    session.add(job)
                    session.commit()

                    await self._run_on_instance(job, gpu.ssh_host, gpu.ssh_port)

                    job.status = JobStatus.COMPLETED
                    job.updated_at = datetime.now(timezone.utc)
                    session.add(job)
                    session.commit()
                    logger.info(f"Job {job.id} completed successfully")

                except Exception as e:
                    logger.exception(f"Failed to process job {job.id}: {e}")
                    job.status = JobStatus.FAILED
                    job.error_message = str(e)[:500]
                    job.updated_at = datetime.now(timezone.utc)
                    session.add(job)
                    session.commit()

    async def _run_on_instance(self, job: Job, ssh_host: str, ssh_port: int):
        """Upload files, run inference, download result on existing instance."""
        with SSHService(ssh_host, ssh_port) as ssh:
            job_dir = f"/workspace/jobs/{job.id}"
            ssh.execute(f"mkdir -p {job_dir}/inputs {job_dir}/output")

            # Upload input files
            logger.info(f"Job {job.id}: Uploading input files...")
            image_ext = Path(job.image_path).suffix
            video_ext = Path(job.video_path).suffix
            ssh.upload(job.image_path, f"{job_dir}/inputs/image{image_ext}")
            ssh.upload(job.video_path, f"{job_dir}/inputs/video{video_ext}")

            # Upload inference script
            ssh.execute(f"cat << 'INF_EOF' > {job_dir}/inference.sh\n{INFERENCE_SCRIPT}\nINF_EOF")
            ssh.execute(f"chmod +x {job_dir}/inference.sh")

            # Run inference
            logger.info(f"Job {job.id}: Running inference...")
            stdout, stderr, exit_code = ssh.execute(
                f"bash {job_dir}/inference.sh "
                f"{job_dir}/inputs/image{image_ext} "
                f"{job_dir}/inputs/video{video_ext} "
                f"{job_dir}/output "
                f"{job.resolution}",
                timeout=7200,
            )
            if exit_code != 0:
                raise RuntimeError(f"Inference failed: {stderr[:500]}")

            if not ssh.file_exists(f"{job_dir}/output/DONE"):
                raise RuntimeError("Inference did not produce completion marker")

            # Download result
            output_dir = settings.output_dir / job.id
            output_dir.mkdir(parents=True, exist_ok=True)
            result_path = str(output_dir / "result.mp4")

            logger.info(f"Job {job.id}: Downloading result...")
            ssh.download(f"{job_dir}/output/result.mp4", result_path)

            # Cleanup remote job files
            ssh.execute(f"rm -rf {job_dir}")

            job.result_path = result_path


# Singleton worker instance
worker = JobWorker()
