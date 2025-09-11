from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Float,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class Vacancy(Base):
    """Модель вакансии."""
    __tablename__ = "vacancies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    telegram_username = Column(String, index=True)
    telegram_user_id = Column(String, index=True)
    original_filename = Column(String)
    object_key = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resumes = relationship(
        "Resume",
        back_populates="vacancy",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Resume(Base):
    """Модель резюме (отклика на вакансию)."""
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    telegram_username = Column(String, index=True)
    telegram_user_id = Column(String, index=True)
    original_filename = Column(String)
    object_key = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    vacancy_id = Column(Integer, ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False)
    vacancy = relationship("Vacancy", back_populates="resumes")
    meetings = relationship(
        "Meeting",
        back_populates="resume",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="desc(Meeting.created_at)",
    )
    similarity = relationship(
        "Similarity",
        back_populates="resume",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Meeting(Base):
    """Модель встречи (интервью)."""
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    organizer_username = Column(String, index=True)
    candidate_username = Column(String, index=True)
    is_finished = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    resume = relationship("Resume", back_populates="meetings")
    audio_objects = relationship(
        "AudioObject",
        back_populates="meeting",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Similarity(Base):
    """Модель результата анализа схожести резюме и вакансии."""
    __tablename__ = "similarities"

    id = Column(Integer, primary_key=True)
    score = Column(Float)
    comment = Column(String)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), unique=True, nullable=False)
    resume = relationship("Resume", back_populates="similarity")


class AudioObject(Base):
    """Модель аудио-объекта в MinIO (чанк или финальная запись)."""
    __tablename__ = "audio_objects"

    id = Column(Integer, primary_key=True)
    session_id = Column(String, index=True, nullable=False)
    object_key = Column(String, unique=True, nullable=False)
    role = Column(String)
    size_bytes = Column(Integer)
    is_final = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), index=True)
    meeting = relationship("Meeting", back_populates="audio_objects")
