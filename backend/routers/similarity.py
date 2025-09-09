import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .dependencies import get_current_user, can_access_resume, can_access_vacancy
from .. import database, models, schemas

router = APIRouter()


@router.get("/temp/{resume_id}/{vacancy_id}", response_model=schemas.SimilarityResponse)
def get_similarity_temp(
        resume_id: int,
        vacancy_id: int,
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user)
):
    can_access_resume(resume_id, user, db)
    can_access_vacancy(vacancy_id, user, db)
    similarity_score = round(random.uniform(0, 1), 3)
    return schemas.SimilarityResponse(
        resume_id=resume_id,
        vacancy_id=vacancy_id,
        score=similarity_score,
        comment="Временный случайный результат"
    )


@router.post("/", response_model=schemas.SimilarityResponse)
def create_similarity(
        similarity: schemas.SimilarityCreate,
        db: Session = Depends(database.get_db),
):
    existing = db.query(models.Similarity).filter(
        models.Similarity.resume_id == similarity.resume_id,
        models.Similarity.vacancy_id == similarity.vacancy_id
    ).first()
    if existing:
        existing.score = similarity.score
        existing.comment = similarity.comment
        db.commit()
        db.refresh(existing)
        return existing
    new_similarity = models.Similarity(
        resume_id=similarity.resume_id,
        vacancy_id=similarity.vacancy_id,
        score=similarity.score,
        comment=similarity.comment
    )
    db.add(new_similarity)
    db.commit()
    db.refresh(new_similarity)
    return new_similarity


@router.get("/{resume_id}/{vacancy_id}", response_model=schemas.SimilarityResponse)
def get_similarity(
        resume_id: int,
        vacancy_id: int,
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user)
):
    can_access_resume(resume_id, user, db)
    can_access_vacancy(vacancy_id, user, db)
    similarity = db.query(models.Similarity).filter(
        models.Similarity.resume_id == resume_id,
        models.Similarity.vacancy_id == vacancy_id
    ).first()
    if not similarity:
        raise HTTPException(status_code=404, detail="Similarity not found")
    return similarity
