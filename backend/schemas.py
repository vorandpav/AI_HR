from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class VacancyBase(BaseModel):
    title: str


class VacancyResponse(VacancyBase):
    id: int
    title: str
    telegram_username: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ResumeResponse(BaseModel):
    id: int
    vacancy_id: int
    original_filename: str
    telegram_username: str
    telegram_user_id: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class SimilarityResponse(BaseModel):
    resume_id: int
    vacancy_id: Optional[int] = None
    score: float
    result_text: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingCreate(BaseModel):
    resume_id: int


class MeetingResponse(BaseModel):
    id: int
    token: str
    resume_id: int
    organizer_username: str
    candidate_username: str
    created_at: datetime

    class Config:
        from_attributes = True
