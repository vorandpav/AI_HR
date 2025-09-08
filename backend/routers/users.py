# backend/routers/users.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from .. import models, schemas, database

router = APIRouter()


@router.get("/vacancies", response_model=List[schemas.VacancyResponse])
def list_user_vacancies(
        db: Session = Depends(database.get_db),
        x_telegram_user: str | None = Header(None),
):
    if not x_telegram_user:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-User header")
    vacs = db.query(models.Vacancy).filter(models.Vacancy.telegram_username == x_telegram_user).all()
    return vacs


@router.get("/resumes", response_model=List[schemas.ResumeResponse])
def list_user_resumes(
        db: Session = Depends(database.get_db),
        x_telegram_user: str | None = Header(None),
):
    if not x_telegram_user:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-User header")
    resumes = db.query(models.Resume).filter(models.Resume.telegram_username == x_telegram_user).all()
    return resumes
