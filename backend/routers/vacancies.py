import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend import database, models, schemas
from backend.dependencies import get_current_user, get_vacancy_for_owner
from backend.services import file_service

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


@router.post("/", response_model=schemas.VacancyResponse)
def create_vacancy(
        title: str = Form(...),
        file: UploadFile = File(...),
        user: str = Depends(get_current_user),
        user_id: str = Form(...),
        db: Session = Depends(database.get_db),
):
    """
    Создает новую вакансию.
    """
    new_vacancy = models.Vacancy(
        title=title,
        telegram_username=user,
        telegram_user_id=user_id,
        original_filename=file.filename
    )
    db.add(new_vacancy)
    db.flush()

    try:
        file_service.save_document(
            db=db, file=file, file_type="vacancy", record=new_vacancy
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save vacancy document: {e}")
        raise HTTPException(status_code=500, detail="Failed to save vacancy document")

    db.refresh(new_vacancy)
    return new_vacancy


@router.get("/", response_model=List[schemas.VacancyResponse])
def list_my_vacancies(
        user: str = Depends(get_current_user),
        db: Session = Depends(database.get_db),
        skip: int = 0,
        limit: int = 100,
):
    """
    Возвращает список вакансий, созданных текущим пользователем.
    """
    vacancies = (
        db.query(models.Vacancy)
        .filter(models.Vacancy.telegram_username == user)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return vacancies


@router.get("/{vacancy_id}", response_model=schemas.VacancyResponse)
def get_vacancy(
        vacancy: models.Vacancy = Depends(get_vacancy_for_owner)
):
    """
    Возвращает вакансию по ID. Доступно только владельцу.
    """
    return vacancy


@router.get("/{vacancy_id}/download", response_class=StreamingResponse)
def download_vacancy_document(
        vacancy: models.Vacancy = Depends(get_vacancy_for_owner)  # Точно так же используем зависимость
):
    """
    Скачивает документ, прикрепленный к вакансии. Доступно только владельцу.
    """
    if not vacancy.object_key:
        raise HTTPException(status_code=404, detail="Vacancy document not found")

    try:
        file_bytes, content_type = file_service.get_file(vacancy.object_key)
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{vacancy.original_filename}"
        }
        return StreamingResponse(iter([file_bytes]), media_type=content_type, headers=headers)
    except Exception as e:
        logger.error(f"Failed to download vacancy document {vacancy.object_key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to download vacancy document")
