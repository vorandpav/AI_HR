# backend/routers/resumes.py
import io
import mimetypes
from typing import List
from urllib.parse import quote, unquote

from fastapi import (APIRouter, Depends, Header, HTTPException,
                     UploadFile)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .dependencies import get_current_user, can_access_resume
from .. import database, models, schemas

router = APIRouter()


@router.get("/", response_model=list[schemas.ResumeResponse])
def list_resumes(
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user)
):
    resumes = (
        db.query(models.Resume)
        .filter(models.Resume.telegram_username == user)
        .order_by(models.Resume.created_at.desc())
        .all()
    )
    return resumes


@router.post("/", response_model=schemas.ResumeResponse)
async def create_resume(
        vacancy_id: int,
        file: UploadFile,
        telegram_username: str,
        telegram_user_id: str,
        db: Session = Depends(database.get_db)
):
    file_bytes = await file.read() if file else None
    filename = unquote(file.filename) if file else None
    MAX_SIZE = 100 * 1024 * 1024
    if file_bytes and len(file_bytes) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Файл слишком большой (макс 100 MB)")
    resume = models.Resume(
        vacancy_id=vacancy_id,
        original_filename=filename,
        file_data=file_bytes,
        telegram_username=telegram_username,
        telegram_user_id=telegram_user_id,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.get("/{resume_id}", response_model=schemas.ResumeResponse)
def get_resume(
        resume_id: int,
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user)
):
    resume = can_access_resume(resume_id, user, db)
    return resume


@router.get("/{resume_id}/download")
def download_resume(
        resume_id: int,
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user)
):
    resume = can_access_resume(resume_id, user, db)
    if not resume.file_data:
        raise HTTPException(status_code=404, detail="Resume file not found")
    mime_type = mimetypes.guess_type(resume.original_filename or "")[0] or "application/octet-stream"
    quoted = quote(resume.original_filename or f"resume_{resume_id}")
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"}
    return StreamingResponse(io.BytesIO(resume.file_data), media_type=mime_type, headers=headers)


@router.get("/{resume_id}/meetings", response_model=list[schemas.MeetingResponse])
def get_resume_meetings(
        resume_id: int,
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user)
):
    resume = can_access_resume(resume_id, user, db)
    meetings = (
        db.query(models.Meeting)
        .filter(models.Meeting.resume_id == resume_id)
        .order_by(models.Meeting.created_at.desc())
        .all()
    )
    return meetings
