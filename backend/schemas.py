from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime


# 1. Similarity (Результат анализа)


class SimilarityResponse(BaseModel):
    """Схема для отображения результата анализа схожести."""
    model_config = ConfigDict(from_attributes=True)

    score: float = Field(..., description="Оценка схожести от 0.0 до 1.0")
    comment: str = Field(..., description="Текстовый комментарий от ML-модели")
    created_at: datetime


# 2. AudioObject (Аудио-чанrи встреч)


class AudioObjectResponse(BaseModel):
    """Схема для отображения информации об аудио-файле."""
    model_config = ConfigDict(from_attributes=True)

    object_key: str
    role: str
    is_final: bool
    created_at: datetime


# 3. Meeting (Встречи/Интервью)


class MeetingResponse(BaseModel):
    """Полная информация о встрече, включая аудио."""
    model_config = ConfigDict(from_attributes=True)

    token: str
    organizer_username: str
    candidate_username: str
    is_finished: bool
    created_at: datetime
    audio_objects: List[AudioObjectResponse] = []


# 4. Resume (Резюме/Отклики)


class ResumeShortResponse(BaseModel):
    """Краткая информация о резюме (для списков)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_username: str
    original_filename: str
    created_at: datetime


class ResumeResponse(ResumeShortResponse):
    """Полная информация о резюме, включая встречи и результат анализа."""
    model_config = ConfigDict(from_attributes=True)

    vacancy_id: int
    object_key: Optional[str] = None
    meetings: List[MeetingResponse] = []
    similarity: Optional[SimilarityResponse] = None


# 5. Vacancy (Вакансии)


class VacancyResponse(BaseModel):
    """Полная информация о вакансии, включая список откликов."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    telegram_username: str
    original_filename: Optional[str] = None
    object_key: Optional[str] = None
    created_at: datetime
    resumes: List[ResumeShortResponse] = []


VacancyResponse.model_rebuild()
ResumeResponse.model_rebuild()
