import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from .. import database, models, schemas
from ..dependencies import get_current_user
from ..services import analysis_service

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


@router.get("/{resume_id}", response_model=schemas.SimilarityResponse)
def get_similarity_for_resume(
        resume_id: int,
        user: str = Depends(get_current_user),
        db: Session = Depends(database.get_db),
):
    """
    Получает результат анализа схожести для указанного резюме.
    Возвращает 404, если анализ еще не завершен или резюме не найдено.
    """
    resume = db.query(models.Resume).filter(models.Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    if resume.telegram_username != user and resume.vacancy.telegram_username != user:
        raise HTTPException(status_code=403, detail="Not authorized to access this resource")

    similarity_record = db.query(models.Similarity).filter(models.Similarity.resume_id == resume_id).first()
    if not similarity_record:
        raise HTTPException(status_code=404, detail="Similarity analysis is not complete yet or has not been started.")

    return similarity_record


@router.post("/trigger/{resume_id}", status_code=202)
def trigger_analysis_for_resume(
        resume_id: int,
        background_tasks: BackgroundTasks,
        user: str = Depends(get_current_user),  # Защищаем эндпоинт
        db: Session = Depends(database.get_db),
):
    """
    Принудительно запускает фоновую задачу анализа схожести для резюме.
    Полезно, если первоначальный запуск не удался.
    """
    resume = db.query(models.Resume).filter(models.Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Только владелец вакансии может запускать повторный анализ
    if resume.vacancy.telegram_username != user:
        raise HTTPException(status_code=403, detail="Only the vacancy owner can trigger a re-analysis.")

    logger.info(f"Manually triggering similarity analysis for resume ID={resume_id} by user {user}")
    background_tasks.add_task(analysis_service.trigger_similarity_analysis, resume_id)

    return {"message": "Similarity analysis has been scheduled to run in the background."}
