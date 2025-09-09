# backend/routers/vacancies.py
import io
import mimetypes
from urllib.parse import quote, unquote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .dependencies import get_current_user, can_access_vacancy
from .. import database, models, schemas

router = APIRouter()


@router.get("/", response_model=list[schemas.VacancyResponse])
def list_vacancies(
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user)
):
    vacancies = (
        db.query(models.Vacancy)
        .filter(models.Vacancy.telegram_username == user)
        .order_by(models.Vacancy.created_at.desc())
        .all()
    )
    return vacancies


@router.post("/", response_model=schemas.VacancyResponse)
async def create_vacancy(
        title: str,
        file: UploadFile,
        telegram_username: str,
        telegram_user_id: str,
        db: Session = Depends(database.get_db),
):
    file_bytes = await file.read() if file else None
    filename = unquote(file.filename) if file else None
    MAX_SIZE = 100 * 1024 * 1024
    if file_bytes and len(file_bytes) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Файл слишком большой (макс 100 MB)")
    vacancy = models.Vacancy(
        title=title,
        file_name=filename,
        file_data=file_bytes,
        telegram_username=telegram_username,
        telegram_user_id=telegram_user_id,
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy


@router.get("/{vacancy_id}", response_model=schemas.VacancyResponse)
def get_vacancy(
        vacancy_id: int,
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user)
):
    vacancy = can_access_vacancy(vacancy_id, user, db)
    return vacancy


@router.get("/{vacancy_id}/download")
def download_vacancy(
        vacancy_id: int,
        db: Session = Depends(database.get_db),
        user: str = Depends(get_current_user)
):
    vacancy = can_access_vacancy(vacancy_id, user, db)
    if not vacancy.file_data:
        raise HTTPException(status_code=404, detail="Файл вакансии не найден")
    mime_type = mimetypes.guess_type(vacancy.file_name)[0] or "application/octet-stream"
    quoted = quote(vacancy.file_name or f"vacancy_{vacancy_id}")
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"}
    return StreamingResponse(io.BytesIO(vacancy.file_data), media_type=mime_type, headers=headers)
