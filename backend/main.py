import io
import mimetypes
import random
from typing import List
from urllib.parse import quote
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from . import database, schemas
import models
from sqlalchemy.exc import OperationalError
import asyncio
import logging
from fastapi import Header
from urllib.parse import unquote

logger = logging.getLogger("uvicorn.error")
app = FastAPI()


async def wait_postgres_and_create_tables(retries: int = 10, delay: float = 1.0):
    for attempt in range(1, retries + 1):
        try:
            models.Base.metadata.create_all(bind=database.engine)
            logger.info("DB connected and tables ensured.")
            return
        except OperationalError as e:
            logger.warning("DB not ready (attempt %s/%s). Waiting %s s... (%s)", attempt, retries, delay, e)
            await asyncio.sleep(delay)
            delay *= 1.5
    logger.error("Could not connect to DB after %s attempts.", retries)
    raise RuntimeError("Database is not available")


@app.on_event("startup")
async def startup_event():
    await wait_postgres_and_create_tables()


# dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_requesting_user(x_telegram_user: str | None = Header(None)):
    if not x_telegram_user:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-User header")
    return x_telegram_user


# --- create_vacancy: принимаем telegram_username ---
@app.post("/vacancies/", response_model=schemas.VacancyResponse)
async def create_vacancy(
        title: str = Form(...),
        description: str = Form(None),
        file: UploadFile = File(None),
        telegram_username: str = Form(None),  # <- опционально принимаем ник
        db: Session = Depends(get_db)
):
    file_bytes = await file.read() if file else None
    filename = file.filename if file else None
    vacancy = models.Vacancy(
        title=title,
        description=description,
        file_name=unquote(filename),
        file_data=file_bytes,
        telegram_username=telegram_username
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy


# --- upload_resume: сохраняем telegram_username тоже ---
@app.post("/resumes/", response_model=schemas.ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
        vacancy_id: int = Form(...),
        file: UploadFile = File(...),
        telegram_username: str = Form(None),  # <- ник того, кто загружает
        db: Session = Depends(get_db)
):
    try:
        file_bytes = await file.read()
        MAX_SIZE = 30 * 1024 * 1024
        if len(file_bytes) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="Файл слишком большой (макс 30 MB)")

        resume = models.Resume(
            vacancy_id=vacancy_id,
            original_filename=unquote(file.filename),
            file_data=file_bytes,
            telegram_username=telegram_username
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)

        score = float(random.randint(0, 100))
        result_text = f"Эмуляция результата: имя файла {resume.original_filename}. Случайный скор: {int(score)}."
        sim = models.Similarity(resume_id=resume.id, score=score, result_text=result_text)
        db.add(sim)
        db.commit()
        db.refresh(sim)

        return resume

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка при сохранении резюме")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка при сохранении резюме")


# --- GET resumes for vacancy: теперь требует заголовок и проверяет право ---
@app.get("/resumes/vacancy/{vacancy_id}", response_model=List[schemas.ResumeResponse])
def get_resumes_for_vacancy(vacancy_id: int, db: Session = Depends(get_db), x_telegram_user: str | None = Header(None)):
    if not x_telegram_user:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-User header")
    vacancy = db.query(models.Vacancy).filter(models.Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    # only owner of vacancy can list resumes
    if vacancy.telegram_username != x_telegram_user:
        raise HTTPException(status_code=403, detail="Forbidden: you are not owner of this vacancy")
    resumes = db.query(models.Resume).filter(models.Resume.vacancy_id == vacancy_id).all()
    return resumes


# --- download_resume: allow owner of resume or owner of vacancy ---
@app.get("/resumes/{resume_id}/download")
def download_resume(resume_id: int, db: Session = Depends(get_db), x_telegram_user: str | None = Header(None)):
    if not x_telegram_user:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-User header")
    resume = db.query(models.Resume).filter(models.Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(404, "Резюме не найдено")

    vacancy = db.query(models.Vacancy).filter(models.Vacancy.id == resume.vacancy_id).first()

    allowed = (resume.telegram_username == x_telegram_user) or (
            vacancy and vacancy.telegram_username == x_telegram_user)
    if not allowed:
        raise HTTPException(status_code=403, detail="Forbidden: you cannot download this resume")

    mime_type = mimetypes.guess_type(resume.original_filename)[0] or "application/octet-stream"
    filename = resume.original_filename or f"resume_{resume.id}"
    quoted = quote(filename)
    headers = {"Content-Disposition": f'attachment; filename="{quoted}"; filename*=UTF-8\'\'{quoted}'}
    return StreamingResponse(io.BytesIO(resume.file_data), media_type=mime_type, headers=headers)


# --- get_similarity: allow owner of resume or owner of vacancy; return vacancy_id too ---
@app.get("/similarity/resume/{resume_id}", response_model=schemas.SimilarityResponse)
def get_similarity(resume_id: int, db: Session = Depends(get_db), x_telegram_user: str | None = Header(None)):
    if not x_telegram_user:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-User header")
    sim = db.query(models.Similarity).filter(models.Similarity.resume_id == resume_id).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Результат не найден")
    resume = db.query(models.Resume).filter(models.Resume.id == resume_id).first()
    vacancy = db.query(models.Vacancy).filter(models.Vacancy.id == resume.vacancy_id).first()
    allowed = (resume.telegram_username == x_telegram_user) or (
            vacancy and vacancy.telegram_username == x_telegram_user)
    if not allowed:
        raise HTTPException(status_code=403, detail="Forbidden: you cannot view this result")
    # build response dict including vacancy_id
    return {
        "resume_id": sim.resume_id,
        "vacancy_id": resume.vacancy_id,
        "score": sim.score,
        "result_text": sim.result_text,
        "created_at": sim.created_at
    }


# --- User endpoints: list your vacancies and resumes ---
@app.get("/user/vacancies", response_model=List[schemas.VacancyResponse])
def list_user_vacancies(db: Session = Depends(get_db), x_telegram_user: str | None = Header(None)):
    if not x_telegram_user:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-User header")
    vacs = db.query(models.Vacancy).filter(models.Vacancy.telegram_username == x_telegram_user).all()
    return vacs


@app.get("/user/resumes", response_model=List[schemas.ResumeResponse])
def list_user_resumes(db: Session = Depends(get_db), x_telegram_user: str | None = Header(None)):
    if not x_telegram_user:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-User header")
    resumes = db.query(models.Resume).filter(models.Resume.telegram_username == x_telegram_user).all()
    return resumes
