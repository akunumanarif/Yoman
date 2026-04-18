import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from config import settings
from database import get_session
from models import Job, JobResponse, JobStatus

router = APIRouter(tags=["jobs"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo"}


def save_upload(file: UploadFile, job_id: str, subdir: str) -> str:
    """Save uploaded file and return the path."""
    ext = Path(file.filename).suffix if file.filename else ""
    dest_dir = settings.upload_dir / job_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{subdir}{ext}"
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return str(dest_path)


@router.post("/jobs", response_model=JobResponse)
async def create_job(
    image: UploadFile = File(...),
    video: UploadFile = File(...),
    resolution: str = Form(default="720"),
    session: Session = Depends(get_session),
):
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, f"Invalid image type: {image.content_type}")
    if video.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(400, f"Invalid video type: {video.content_type}")
    if resolution not in ("480", "720"):
        raise HTTPException(400, "Resolution must be '480' or '720'")

    job_id = str(uuid.uuid4())
    image_path = save_upload(image, job_id, "image")
    video_path = save_upload(video, job_id, "video")

    job = Job(
        id=job_id,
        image_path=image_path,
        video_path=video_path,
        resolution=resolution,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs(session: Session = Depends(get_session)):
    jobs = session.exec(select(Job).order_by(Job.created_at.desc())).all()
    return jobs


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    # Cancel if still running
    if job.status in (JobStatus.PENDING, JobStatus.PROVISIONING, JobStatus.PROCESSING):
        job.status = JobStatus.CANCELLED
        job.updated_at = datetime.now(timezone.utc)
        session.add(job)
        session.commit()
        # TODO: Destroy vast.ai instance if active

    # Clean up files
    upload_dir = settings.upload_dir / job_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir)

    output_dir = settings.output_dir / job_id
    if output_dir.exists():
        shutil.rmtree(output_dir)

    session.delete(job)
    session.commit()
    return {"status": "deleted"}


@router.get("/jobs/{job_id}/result")
async def get_result(job_id: str, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != JobStatus.COMPLETED or not job.result_path:
        raise HTTPException(400, "Result not available yet")

    result_path = Path(job.result_path)
    if not result_path.exists():
        raise HTTPException(404, "Result file not found")

    return FileResponse(result_path, media_type="video/mp4", filename=f"yoman_{job_id}.mp4")
