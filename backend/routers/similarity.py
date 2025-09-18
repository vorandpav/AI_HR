import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from .. import database, models, schemas
from ..dependencies import get_similarity_for_authorized_user
from ..services import analysis_service

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


@router.get("/{resume_id}/trigger", response_model=schemas.SimilarityResponse)
def get_trigger_similarity(
        similarity: models.Resume = Depends(get_similarity_for_authorized_user),
):
    """
    Получает результат анализа схожести для резюме.
    Доступен владельцу вакансии и кандидату.
    """
    return similarity
