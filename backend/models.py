# backend/models.py
from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Integer,
                        LargeBinary, String, Text, func)
from sqlalchemy.orm import relationship

from .database import Base


class Vacancy(Base):
    __tablename__ = "vacancies"
    id = Column(Integer, primary_key=True, index=True)
    telegram_username = Column(String, nullable=True)
    telegram_user_id = Column(String, nullable=True)
    title = Column(String, nullable=False)
    file_name = Column(String, nullable=True)
    file_data = Column(LargeBinary, nullable=True)
    resumes = relationship("Resume", back_populates="vacancy")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Resume(Base):
    __tablename__ = "resumes"
    id = Column(Integer, primary_key=True, index=True)
    vacancy_id = Column(Integer, ForeignKey("vacancies.id"), nullable=False)
    telegram_username = Column(String, nullable=True)
    telegram_user_id = Column(String, nullable=True)
    original_filename = Column(String, nullable=False)
    file_data = Column(LargeBinary, nullable=False)
    vacancy = relationship("Vacancy", back_populates="resumes")
    similarity = relationship("Similarity", back_populates="resume", uselist=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())


class Similarity(Base):
    __tablename__ = "similarities"
    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False, unique=True)
    score = Column(Float, nullable=False)
    result_text = Column(Text, nullable=True)
    resume = relationship("Resume", back_populates="similarity")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AudioChunk(Base):
    __tablename__ = "audio_chunks"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    role = Column(String, default="participant")
    wav_bytes = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AudioObject(Base):
    __tablename__ = "audio_objects"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True, index=True)
    meeting = relationship("Meeting", back_populates="audio_objects")
    object_key = Column(String, nullable=False)
    role = Column(String, default="participant", nullable=False)
    duration_sec = Column(Float, nullable=True)
    size_bytes = Column(Integer, nullable=False)
    is_final = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    resume_id = Column(Integer, nullable=False)
    organizer_username = Column(String, nullable=False)
    candidate_username = Column(String, nullable=True)
    is_finished = Column(Boolean, default=False, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_session_id = Column(String, nullable=True, index=True)
    audio_objects = relationship(
        "AudioObject", back_populates="meeting", cascade="all, delete-orphan"
    )
