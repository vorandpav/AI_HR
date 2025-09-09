from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class VacancyBase(BaseModel):
    title: str


class VacancyResponse(VacancyBase):
    id: int
    telegram_username: Optional[str]
    telegram_user_id: Optional[str]
    file_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ResumeBase(BaseModel):
    vacancy_id: int
    original_filename: str


class ResumeResponse(ResumeBase):
    id: int
    telegram_username: Optional[str]
    telegram_user_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SimilarityCreate(BaseModel):
    resume_id: int
    vacancy_id: int
    score: float
    comment: Optional[str] = None


class SimilarityResponse(BaseModel):
    resume_id: int
    vacancy_id: int
    score: float
    comment: Optional[str]
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
    candidate_username: Optional[str]
    is_finished: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AudioChunkResponse(BaseModel):
    id: int
    session_id: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class AudioObjectResponse(BaseModel):
    id: int
    session_id: str
    meeting_id: Optional[int]
    object_key: str
    role: str
    duration_sec: Optional[float]
    size_bytes: int
    is_final: bool
    created_at: datetime

    class Config:
        from_attributes = True
