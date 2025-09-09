# backend/routers/similarity.py
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .. import database, models, schemas

router = APIRouter()


@router.get("/resume/{resume_id}", response_model=schemas.SimilarityResponse)
def get_similarity(
    resume_id: int,
    db: Session = Depends(database.get_db),
    x_telegram_user: str | None = Header(None),
):
    if not x_telegram_user:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-User header")

    sim = (
        db.query(models.Similarity)
        .filter(models.Similarity.resume_id == resume_id)
        .first()
    )
    if not sim:
        raise HTTPException(status_code=404, detail="Результат не найден")

    resume = db.query(models.Resume).filter(models.Resume.id == resume_id).first()
    vacancy = (
        db.query(models.Vacancy).filter(models.Vacancy.id == resume.vacancy_id).first()
    )

    allowed = (resume.telegram_username == x_telegram_user) or (
        vacancy and vacancy.telegram_username == x_telegram_user
    )
    if not allowed:
        raise HTTPException(
            status_code=403, detail="Вы не можете просматривать этот результат"
        )

    return {
        "resume_id": sim.resume_id,
        "vacancy_id": resume.vacancy_id,
        "score": sim.score,
        "result_text": sim.result_text,
        "created_at": sim.created_at,
    }
