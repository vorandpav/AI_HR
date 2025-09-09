# backend/routers/vacancies.py
import io
import mimetypes
from urllib.parse import quote, unquote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import database, models, schemas

router = APIRouter()


@router.post("/", response_model=schemas.VacancyResponse)
async def create_vacancy(
    title: str = Form(...),
    file: UploadFile = File(None),
    telegram_username: str = Form(...),
    telegram_user_id: str = Form(...),
    db: Session = Depends(database.get_db),
):
    file_bytes = await file.read() if file else None
    filename = unquote(file.filename) if file else None
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
async def get_vacancy(vacancy_id: int, db: Session = Depends(database.get_db)):
    vacancy = db.query(models.Vacancy).filter(models.Vacancy.id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Вакансия не найдена")
    return vacancy


@router.get("/{vacancy_id}/download")
def download_vacancy(vacancy_id: int, db: Session = Depends(database.get_db)):
    vacancy = db.query(models.Vacancy).filter(models.Vacancy.id == vacancy_id).first()
    if not vacancy or not vacancy.file_data:
        raise HTTPException(status_code=404, detail="Файл вакансии не найден")

    mime_type = mimetypes.guess_type(vacancy.file_name)[0] or "application/octet-stream"
    quoted = quote(vacancy.file_name or f"vacancy_{vacancy_id}")
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"}

    return StreamingResponse(
        io.BytesIO(vacancy.file_data), media_type=mime_type, headers=headers
    )
