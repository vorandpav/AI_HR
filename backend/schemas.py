from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class VacancyBase(BaseModel):
    title: str
    description: Optional[str] = None

class VacancyResponse(VacancyBase):
    id: int
    telegram_username: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True

class ResumeResponse(BaseModel):
    id: int
    vacancy_id: int
    original_filename: str
    telegram_username: Optional[str]
    uploaded_at: datetime

    class Config:
        orm_mode = True

class SimilarityResponse(BaseModel):
    resume_id: int
    vacancy_id: Optional[int] = None
    score: float
    result_text: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True
