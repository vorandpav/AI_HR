import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend import database, models, schemas
from backend.dependencies import (
    get_current_user,
    get_resume_for_authorized_user,
    get_vacancy_for_owner,
)
from backend.services import file_service, analysis_service

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


@router.post("/", response_model=schemas.ResumeResponse)
def create_resume(
        background_tasks: BackgroundTasks,
        vacancy_id: int = Form(...),
        file: UploadFile = File(...),
        user: str = Depends(get_current_user),
        user_id: str = Form(...),
        db: Session = Depends(database.get_db),
):
    """
    Создает новое резюме для указанной вакансии.
    Запускает фоновую задачу для анализа.
    """
    vacancy = db.query(models.Vacancy).filter(models.Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    new_resume = models.Resume(
        vacancy_id=vacancy_id,
        telegram_username=user,
        telegram_user_id=user_id,
        original_filename=file.filename,
    )
    db.add(new_resume)
    db.flush()

    try:
        file_service.save_document(
            db=db, file=file, file_type="resume", record=new_resume
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save resume document: {e}")
        raise HTTPException(status_code=500, detail="Failed to save resume document")

    db.refresh(new_resume)
    background_tasks.add_task(analysis_service.trigger_similarity_analysis, new_resume.id)
    return new_resume


@router.get("/", response_model=List[schemas.ResumeShortResponse])
def list_resumes_for_vacancy(
        vacancy_id: int,
        vacancy: models.Vacancy = Depends(get_vacancy_for_owner),
        db: Session = Depends(database.get_db),
        skip: int = 0,
        limit: int = 100,
):
    """
    Возвращает список резюме для конкретной вакансии.
    Доступно только владельцу вакансии.
    """
    resumes = (
        db.query(models.Resume)
        .filter(models.Resume.vacancy_id == vacancy_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return resumes


@router.get("/full/{resume_id}", response_model=schemas.ResumeResponse)
def get_full_resume_info(
        resume: models.Resume = Depends(get_resume_for_authorized_user),
):
    """
    Возвращает резюме и вакансию по ID резюме.
    Доступно владельцу резюме или владельцу связанной вакансии.
    """
    print(resume.__dict__)
    return resume


@router.get("/{resume_id}/download", response_class=StreamingResponse)
def download_resume_document(
        resume: models.Resume = Depends(get_resume_for_authorized_user),
):
    """
    Скачивает документ, прикрепленный к резюме.
    Доступно владельцу резюме или владельцу связанной вакансии.
    """
    if not resume.object_key:
        raise HTTPException(status_code=404, detail="Resume document not found")

    try:
        file_bytes, content_type = file_service.get_file(resume.object_key)
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{resume.original_filename}"
        }
        return StreamingResponse(iter([file_bytes]), media_type=content_type, headers=headers)
    except Exception as e:
        logger.error(f"Failed to download resume document {resume.object_key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to download resume document")
