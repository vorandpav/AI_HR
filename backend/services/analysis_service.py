import logging
import httpx
import os

from sqlalchemy.orm import Session
from backend import models, database

logger = logging.getLogger("uvicorn.error")

SIMILARITY_SERVICE_URL = os.getenv("SIMILARITY_SERVICE_URL", "http://localhost:8001/analyze")


async def trigger_similarity_analysis(resume_id: int):
    """
    Фоновая задача для запуска анализа схожести.
    1. Получает данные из БД.
    2. Делает запрос к внешнему ML-сервису.
    3. Сохраняет результат обратно в БД.
    """
    db: Session = next(database.get_db())

    try:
        resume = db.query(models.Resume).filter(models.Resume.id == resume_id).first()
        if not resume:
            logger.error(f"Resume ID={resume_id} not found.")
            return

        vacancy = resume.vacancy
        if not vacancy or not resume.object_key or not vacancy.object_key:
            logger.warning(f"Vacancy for resume ID={resume_id} not found.")
            return

        from backend.services import file_service
        vacancy_text_bytes, _ = file_service.get_file(vacancy.object_key)
        resume_text_bytes, _ = file_service.get_file(resume.object_key)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                SIMILARITY_SERVICE_URL,
                json={
                    "vacancy_text": vacancy_text_bytes.decode('utf-8', errors='ignore'),
                    "resume_text": resume_text_bytes.decode('utf-8', errors='ignore'),
                }
            )
            response.raise_for_status()
            result = response.json()
            score = result["score"]
            comment = result["comment"]

        similarity_record = db.query(models.Similarity).filter(models.Similarity.resume_id == resume.id).first()
        if not similarity_record:
            similarity_record = models.Similarity(resume_id=resume.id, score=score, comment=comment)
            db.add(similarity_record)
        db.commit()
    except Exception as e:
        logger.error(f"Error while getting similarity for resume ID={resume_id}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
