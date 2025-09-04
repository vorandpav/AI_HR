from sqlalchemy import Column, Integer, String, LargeBinary, DateTime, Float, Text, ForeignKey, func
from sqlalchemy.orm import relationship
from backend.database import Base


class Vacancy(Base):
    __tablename__ = "vacancies"
    id = Column(Integer, primary_key=True, index=True)
    telegram_username = Column(String, nullable=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    file_data = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resumes = relationship("Resume", back_populates="vacancy")


class Resume(Base):
    __tablename__ = "resumes"
    id = Column(Integer, primary_key=True, index=True)
    vacancy_id = Column(Integer, ForeignKey("vacancies.id"), nullable=False)
    telegram_username = Column(String, nullable=True)
    original_filename = Column(String, nullable=False)
    file_data = Column(LargeBinary, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    vacancy = relationship("Vacancy", back_populates="resumes")
    similarity = relationship("Similarity", back_populates="resume", uselist=False)


class Similarity(Base):
    __tablename__ = "similarities"
    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False, unique=True)
    score = Column(Float, nullable=False)
    result_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    resume = relationship("Resume", back_populates="similarity")


class AudioChunk(Base):
    __tablename__ = "audio_chunks"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    role = Column(String, default="participant")
    wav_bytes = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
