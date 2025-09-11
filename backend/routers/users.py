from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.dependencies import get_current_user
from .. import database, models, schemas

router = APIRouter()


@router.get("/vacancies", response_model=List[schemas.VacancyResponse])
def list_user_vacancies(
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user),
):
    vacancies = (
        db.query(models.Vacancy)
        .filter(models.Vacancy.telegram_username == user)
        .order_by(models.Vacancy.created_at.desc())
        .all()
    )
    return vacancies


@router.get("/resumes", response_model=List[schemas.ResumeResponse])
def list_user_resumes(
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user),
):
    resumes = (
        db.query(models.Resume)
        .filter(models.Resume.telegram_username == user)
        .order_by(models.Resume.created_at.desc())
        .all()
    )
    return resumes


@router.get("/meetings", response_model=List[schemas.MeetingResponse])
def list_user_meetings(
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user),
):
    meetings = (
        db.query(models.Meeting)
        .filter(
            (models.Meeting.organizer_username == user)
            | (models.Meeting.candidate_username == user)
        )
        .order_by(models.Meeting.created_at.desc())
        .all()
    )
    return meetings
