from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime


# 1. Similarity (Результат анализа)

class SimilarityResponse(BaseModel):
    """Схема для отображения результата анализа схожести."""
    model_config = ConfigDict(from_attributes=True)

    score: float = None
    comment: str = None
    created_at: datetime


# 2. AudioObject (Аудио-чанrи встреч)

class AudioObjectResponse(BaseModel):
    """Схема для отображения информации об аудио-файле."""
    model_config = ConfigDict(from_attributes=True)

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


# 4. Short Responses

class ResumeShortResponse(BaseModel):
    """Краткая информация о резюме."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_username: str
    telegram_user_id: str
    original_filename: str
    created_at: datetime


class VacancyShortResponse(BaseModel):
    """Краткая информация о вакансии."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    telegram_username: str
    telegram_user_id: str
    original_filename: str
    created_at: datetime


# 5. Resume (Резюме/Отклики)

class ResumeResponse(ResumeShortResponse):
    """Полная информация о резюме, включая встречи и результат анализа."""
    model_config = ConfigDict(from_attributes=True)

    vacancy: VacancyShortResponse
    meetings: Optional[List[MeetingResponse]] = []
    similarity: Optional[SimilarityResponse] = None


# 6. Vacancy (Вакансии)

class VacancyResponse(VacancyShortResponse):
    """Полная информация о вакансии, включая список откликов."""
    model_config = ConfigDict(from_attributes=True)

    resumes: Optional[List[ResumeShortResponse]] = []


VacancyResponse.model_rebuild()
ResumeResponse.model_rebuild()
