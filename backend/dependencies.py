from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session, joinedload

from backend import database, models


def get_current_user(x_telegram_user: str | None = Header(None)) -> str:
    """
    Получает имя пользователя из заголовка X-Telegram-User.
    """
    if not x_telegram_user:
        raise HTTPException(
            status_code=401,
            detail="Необходим заголовок безопасности",
        )
    return x_telegram_user


def get_vacancy_for_owner(
        vacancy_id: int,
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user),
) -> models.Vacancy:
    """
    Проверяет, что пользователь имеет право на доступ к вакансии.
    Права есть у владельца вакансии.
    Возвращает объект вакансии.
    """
    vacancy = db.query(models.Vacancy).filter(models.Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    if vacancy.telegram_username != user:
        raise HTTPException(status_code=403, detail="You do not have access to this vacancy")
    return vacancy


def get_resume_for_authorized_user(
        resume_id: int,
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user),
) -> models.Resume:
    """
    Проверяет, что пользователь имеет право на доступ к резюме.
    Права есть у:
    1. Владельца вакансии.
    2. Кандидата.
    Возвращает объект резюме.
    """
    resume = (
        db.query(models.Resume)
        .options(joinedload(models.Resume.vacancy))
        .filter(models.Resume.id == resume_id)
        .first()
    )
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if user not in [resume.telegram_username, resume.vacancy.telegram_username]:
        raise HTTPException(status_code=403, detail="You do not have access to this resume")

    return resume


def get_meeting_for_authorized_user(
        token: str,
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user),
) -> models.Meeting:
    """
    Проверяет что пользователь имеет право на доступ к встрече.
    Права есть у:
    1. Владельца вакансии.
    2. Кандидата.
    Возвращает объект встречи.
    """
    meeting = db.query(models.Meeting).filter(models.Meeting.token == token).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if user not in [meeting.organizer_username, meeting.candidate_username]:
        raise HTTPException(status_code=403, detail="You do not have access to this meeting")

    return meeting
