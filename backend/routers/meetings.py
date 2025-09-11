import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from backend import database, models, schemas
from backend.dependencies import get_current_user, get_meeting_for_authorized_user

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


@router.post("/", response_model=schemas.MeetingResponse)
def create_meeting(
        resume_id: int,
        user: str = Depends(get_current_user),
        db: Session = Depends(database.get_db),
):
    """
    Создает новую встречу (интервью) для кандидата.
    Доступно только владельцу вакансии.
    """
    resume = (
        db.query(models.Resume)
        .options(joinedload(models.Resume.vacancy))
        .filter(models.Resume.id == resume_id)
        .first()
    )

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    if resume.vacancy.telegram_username != user:
        raise HTTPException(
            status_code=403, detail="You do not have access to create a meeting for this resume"
        )

    new_meeting = models.Meeting(
        token=uuid.uuid4().hex,
        resume_id=resume.id,
        organizer_username=resume.vacancy.telegram_username,
        candidate_username=resume.telegram_username,
    )
    db.add(new_meeting)
    db.commit()
    db.refresh(new_meeting)

    return new_meeting


@router.get("/{token}", response_model=schemas.MeetingResponse)
def get_meeting(
        meeting: models.Meeting = Depends(get_meeting_for_authorized_user),
):
    """
    Возвращает информацию о встрече по ее токену.
    Доступно только организатору или кандидату.
    """
    return meeting


@router.post("/{token}/finish", response_model=schemas.MeetingResponse)
def finish_meeting(
        meeting: models.Meeting = Depends(get_meeting_for_authorized_user),
        db: Session = Depends(database.get_db),
):
    """
    Завершает встречу.
    Доступно только организатору или кандидату/
    """
    if meeting.is_finished:
        raise HTTPException(status_code=400, detail="Meeting is already finished")

    meeting.is_finished = True
    db.commit()
    db.refresh(meeting)

    logger.info(f"Meeting {meeting.token} is finished.")
    return meeting
