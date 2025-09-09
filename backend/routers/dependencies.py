from fastapi import Header, HTTPException
from sqlalchemy.orm import Session
from .. import models


def get_current_user(x_telegram_user: str | None = Header(None)):
    if not x_telegram_user:
        raise HTTPException(status_code=401, detail="Отсутствует заголовок безопасности")
    return x_telegram_user


def can_access_resume(resume_id: int, user: str, db: Session):
    resume = db.query(models.Resume).filter(models.Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Резюме не найдено")
    vacancy = db.query(models.Vacancy).filter(models.Vacancy.id == resume.vacancy_id).first()
    allowed = (resume.telegram_username == user) or (vacancy and vacancy.telegram_username == user)
    if not allowed:
        raise HTTPException(status_code=403, detail="Запрещено: вы не можете просматривать это резюме")
    return resume


def can_access_meeting(token: str, user: str, db: Session):
    meeting = db.query(models.Meeting).filter(models.Meeting.token == token).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Встреча не найдена")
    allowed = (meeting.organizer_username == user) or (meeting.candidate_username == user)
    if not allowed:
        raise HTTPException(status_code=403, detail="Запрещено: вы не можете просматривать эту встречу")
    return meeting


def can_access_vacancy(vacancy_id: int, user: str, db: Session):
    vacancy = db.query(models.Vacancy).filter(models.Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Вакансия не найдена")
    allowed = (vacancy.telegram_username == user)
    if not allowed:
        raise HTTPException(status_code=403, detail="Запрещено: вы не можете просматривать эту вакансию")
    return vacancy
