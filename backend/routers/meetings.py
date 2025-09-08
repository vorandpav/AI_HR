# backend/routers/meetings.py
import datetime
import logging
import uuid
import os
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas, database
from fastapi.responses import StreamingResponse
import io
from ..services.minio_client import get_minio_client

router = APIRouter()
logger = logging.getLogger("Meetings")


def get_user(x_telegram_user: str | None = Header(None)):
    if not x_telegram_user:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-User header")
    return x_telegram_user


def get_meeting_by_token(token: str):
    db = database.SessionLocal()
    try:
        return db.query(models.Meeting).filter(models.Meeting.token == token).first()
    finally:
        db.close()


@router.post("/arrange_meeting", response_model=schemas.MeetingResponse)
def arrange_meeting(
        payload: schemas.MeetingCreate,
        db: Session = Depends(database.get_db),
        x_telegram_user: str = Depends(get_user)
):
    resume = db.query(models.Resume).filter(models.Resume.id == payload.resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    vacancy = db.query(models.Vacancy).filter(models.Vacancy.id == resume.vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    if vacancy.telegram_username != x_telegram_user:
        raise HTTPException(status_code=403, detail="Forbidden: not the owner of vacancy")

    existing = db.query(models.Meeting).filter(
        models.Meeting.resume_id == payload.resume_id,
        models.Meeting.is_finished == False
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="An active meeting for this resume already exists")

    token = uuid.uuid4().hex

    meeting = models.Meeting(
        token=token,
        resume_id=payload.resume_id,
        organizer_username=x_telegram_user,
        candidate_username=resume.telegram_username,
        is_finished=False
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    return meeting


def finish_meeting_sync(token: str, session_id: str = None):
    db = database.SessionLocal()
    try:
        meeting = db.query(models.Meeting).filter(models.Meeting.token == token).first()
        if meeting:
            meeting.is_finished = True
            meeting.ended_at = datetime.datetime.now(datetime.timezone.utc)
            if session_id:
                meeting.last_session_id = session_id
            db.add(meeting)
            db.commit()
    finally:
        db.close()


@router.get("/meetings/{token}", response_model=schemas.MeetingResponse)
def get_meeting(token: str, db: Session = Depends(database.get_db)):
    meeting = db.query(models.Meeting).filter(models.Meeting.token == token).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.get("/user/meetings", response_model=List[schemas.MeetingResponse])
def list_user_meetings(db: Session = Depends(database.get_db), x_telegram_user: str = Depends(get_user)):
    meetings = db.query(models.Meeting).filter(
        (models.Meeting.organizer_username == x_telegram_user) |
        (models.Meeting.candidate_username == x_telegram_user)
    ).order_by(models.Meeting.created_at.desc()).all()
    return meetings


@router.get("/meetings/{token}/recording")
def download_meeting_recording(
        token: str,
        db: Session = Depends(database.get_db),
        x_telegram_user: str = Depends(get_user)
):
    meeting = db.query(models.Meeting).filter(models.Meeting.token == token).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    allowed = (meeting.organizer_username == x_telegram_user) or (
            meeting.candidate_username == x_telegram_user
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Forbidden: You cannot access this recording")

    # Вызываем нашу новую вспомогательную функцию
    return get_recording_response(meeting)

def get_recording_response(meeting: models.Meeting):
    """
    Находит финальную запись для встречи и возвращает StreamingResponse.
    """
    if not meeting.last_session_id:
        raise HTTPException(status_code=404, detail="Запись недоступна для этой встречи (нет session_id)")

    db = database.SessionLocal()
    try:
        final_recording = db.query(models.AudioObject).filter(
            models.AudioObject.session_id == meeting.last_session_id,
            models.AudioObject.is_final == True
        ).first()
    finally:
        db.close()

    if not final_recording:
        raise HTTPException(status_code=404, detail="Финальная запись не найдена для этой встречи")

    try:
        minio_client = get_minio_client()
        response = minio_client.client.get_object(
            bucket_name=os.getenv("MINIO_BUCKET", "audio"),
            object_name=final_recording.object_key
        )
        data = response.read()

        filename = f"recording_meeting_{meeting.id}.ogg"
        return StreamingResponse(
            io.BytesIO(data),
            media_type="audio/ogg",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error downloading recording {final_recording.object_key}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving recording")
