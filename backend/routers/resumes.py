# backend/routers/resumes.py
import io
import mimetypes
import os
import random
from urllib.parse import quote, unquote
from typing import List
from fastapi.responses import StreamingResponse

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from .. import models, schemas, database
from ..services.minio_client import get_minio_client
from .meetings import get_recording_response

router = APIRouter()


@router.post("/", response_model=schemas.ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
        vacancy_id: int = Form(...),
        file: UploadFile = File(...),
        telegram_username: str = Form(...),
        telegram_user_id: str = Form(...),
        db: Session = Depends(database.get_db)
):
    file_bytes = await file.read()
    MAX_SIZE = 30 * 1024 * 1024
    if len(file_bytes) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Файл слишком большой (макс 30 MB)")

    resume = models.Resume(
        vacancy_id=vacancy_id,
        original_filename=unquote(file.filename),
        file_data=file_bytes,
        telegram_username=telegram_username,
        telegram_user_id=telegram_user_id,
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


@router.get("/vacancy/{vacancy_id}", response_model=List[schemas.ResumeResponse])
def get_resumes_for_vacancy(
        vacancy_id: int,
        db: Session = Depends(database.get_db),
        x_telegram_user: str | None = Header(None),
):
    if not x_telegram_user:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-User header")

    vacancy = db.query(models.Vacancy).filter(models.Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    if vacancy.telegram_username != x_telegram_user:
        raise HTTPException(status_code=403, detail="Forbidden: you are not owner of this vacancy")

    resumes = db.query(models.Resume).filter(models.Resume.vacancy_id == vacancy_id).all()
    return resumes


@router.get("/{resume_id}", response_model=schemas.ResumeResponse)
def get_resume_info(resume_id: int, db: Session = Depends(database.get_db)):
    resume = db.query(models.Resume).filter(models.Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Резюме не найдено")
    return resume


@router.get("/{resume_id}/download")
def download_resume(
        resume_id: int,
        db: Session = Depends(database.get_db),
        x_telegram_user: str | None = Header(None),
):
    if not x_telegram_user:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-User header")

    resume = db.query(models.Resume).filter(models.Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(404, "Резюме не найдено")

    vacancy = db.query(models.Vacancy).filter(models.Vacancy.id == resume.vacancy_id).first()
    allowed = (resume.telegram_username == x_telegram_user) or (
            vacancy and vacancy.telegram_username == x_telegram_user
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Forbidden: you cannot download this resume")

    mime_type = mimetypes.guess_type(resume.original_filename)[0] or "application/octet-stream"
    quoted = quote(resume.original_filename or f"resume_{resume_id}")
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"}

    return StreamingResponse(io.BytesIO(resume.file_data), media_type=mime_type, headers=headers)


@router.get("/{resume_id}/recording")
def download_recording_by_resume(
        resume_id: int,
        db: Session = Depends(database.get_db),
        x_telegram_user: str = Header(None),
):
    if not x_telegram_user:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-User header")

    resume = db.query(models.Resume).filter(models.Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Резюме не найдено")

    vacancy = db.query(models.Vacancy).filter(models.Vacancy.id == resume.vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Вакансия для резюме не найдена")

    allowed = (resume.telegram_username == x_telegram_user) or (
            vacancy.telegram_username == x_telegram_user
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Forbidden: you cannot access this recording")

    meeting = db.query(models.Meeting).filter(
        models.Meeting.resume_id == resume_id,
        models.Meeting.is_finished == True
    ).order_by(models.Meeting.created_at.desc()).first()

    if not meeting:
        raise HTTPException(status_code=404, detail="Завершенная встреча для этого резюме не найдена")

    # Вызываем нашу новую вспомогательную функцию
    return get_recording_response(meeting)