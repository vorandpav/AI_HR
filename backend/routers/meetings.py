# backend/routers/meetings.py
import datetime
import io
import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .dependencies import get_current_user, can_access_meeting
from .. import database, models, schemas

router = APIRouter()
logger = logging.getLogger("Meetings")


@router.get("/", response_model=List[schemas.MeetingResponse])
def list_meetings(
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user),
        resume_id: int = None
):
    query = db.query(models.Meeting)
    if resume_id is not None:
        query = query.filter(models.Meeting.resume_id == resume_id)
    else:
        query = query.filter(
            (models.Meeting.organizer_username == user) |
            (models.Meeting.candidate_username == user)
        )
    meetings = query.order_by(models.Meeting.created_at.desc()).all()
    return meetings


@router.post("/", response_model=schemas.MeetingResponse)
def arrange_meeting(
        payload: schemas.MeetingCreate,
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user),
):
    resume = db.query(models.Resume).filter(models.Resume.id == payload.resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    vacancy = db.query(models.Vacancy).filter(models.Vacancy.id == resume.vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    if vacancy.telegram_username != user:
        raise HTTPException(status_code=403, detail="Forbidden: not the owner of vacancy")
    existing = db.query(models.Meeting) \
        .filter(models.Meeting.resume_id == payload.resume_id, models.Meeting.is_finished == False) \
        .first()
    if existing:
        raise HTTPException(status_code=400, detail="An active meeting for this resume already exists")
    token = uuid.uuid4().hex
    meeting = models.Meeting(
        token=token,
        resume_id=payload.resume_id,
        organizer_username=user,
        candidate_username=resume.telegram_username,
        is_finished=False,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


@router.get("/{token}", response_model=schemas.MeetingResponse)
def get_meeting(token: str, db: Session = Depends(database.get_db), user: str = Depends(get_current_user)):
    meeting = can_access_meeting(token, user, db)
    return meeting


@router.get("/{token}/recording")
def download_meeting_recording(token: str, db: Session = Depends(database.get_db),
                               user: str = Depends(get_current_user)):
    meeting = can_access_meeting(token, user, db)
    if not getattr(meeting, "final_recording_data", None):
        raise HTTPException(status_code=404, detail="Meeting recording not found")
    mime_type = "audio/webm"
    filename = getattr(meeting, "final_recording_filename", f"meeting_{token}_recording.webm")
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    return StreamingResponse(
        io.BytesIO(meeting.final_recording_data), media_type=mime_type, headers=headers
    )
