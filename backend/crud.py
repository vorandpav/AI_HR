import os
from sqlalchemy.orm import Session
from . import schemas, models

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def create_vacancy(db: Session, vacancy: schemas.VacancyCreate):
    db_vacancy = models.Vacancy(**vacancy.dict())
    db.add(db_vacancy)
    db.commit()
    db.refresh(db_vacancy)
    return db_vacancy

def get_vacancies(db: Session, skip: int = 0, limit: int = 10):
    return db.query(models.Vacancy).offset(skip).limit(limit).all()

def create_resume(db: Session, file_bytes: bytes, filename: str, meta: schemas.ResumeCreate):
    safe_name = f"{meta.vacancy_id}_{filename}"
    path = os.path.join(UPLOAD_DIR, safe_name)
    with open(path, "wb") as f:
        f.write(file_bytes)
    db_resume = models.Resume(file_path=path, vacancy_id=meta.vacancy_id)
    db.add(db_resume)
    db.commit()
    db.refresh(db_resume)
    return db_resume

def get_resumes_by_vacancy(db: Session, vacancy_id: int):
    return db.query(models.Resume).filter(models.Resume.vacancy_id == vacancy_id).all()

def get_resume(db: Session, resume_id: int):
    return db.query(models.Resume).filter(models.Resume.id == resume_id).first()

def create_similarity(db: Session, similarity: schemas.SimilarityCreate):
    existing = db.query(models.Similarity).filter(models.Similarity.resume_id == similarity.resume_id).first()
    if existing:
        existing.score = similarity.score
        existing.result_text = similarity.result_text
        db.commit()
        db.refresh(existing)
        return existing
    new = models.Similarity(resume_id=similarity.resume_id, score=similarity.score, result_text=similarity.result_text)
    db.add(new)
    db.commit()
    db.refresh(new)
    return new

def get_similarity_by_resume(db: Session, resume_id: int):
    return db.query(models.Similarity).filter(models.Similarity.resume_id == resume_id).first()
