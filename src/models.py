from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from src.database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True)
    raw_text = Column(Text, nullable=False)
    skills = Column(JSON, default=list)
    experience_years = Column(Float, nullable=True)
    education = Column(Text, nullable=True)
    embedding = Column(JSON, nullable=True)       # BGE-M3 dense vector
    source_file = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    match_results = relationship("MatchResult", back_populates="candidate")


class Vacancy(Base):
    __tablename__ = "vacancies"

    id = Column(Integer, primary_key=True, index=True)
    hh_id = Column(String, unique=True, index=True, nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    requirements = Column(JSON, default=list)     # extracted requirement bullets
    embedding = Column(JSON, nullable=True)       # BGE-M3 dense vector
    url = Column(String, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)

    match_results = relationship("MatchResult", back_populates="vacancy")


class MatchResult(Base):
    __tablename__ = "match_results"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    vacancy_id = Column(Integer, ForeignKey("vacancies.id"), nullable=False)
    tfidf_score = Column(Float, nullable=True)
    semantic_score = Column(Float, nullable=True)
    llm_score = Column(Float, nullable=True)
    llm_explanation = Column(Text, nullable=True)
    strengths = Column(JSON, default=list)
    gaps = Column(JSON, default=list)
    method = Column(String, nullable=False)       # "funnel", "semantic", "tfidf", "llm"
    created_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="match_results")
    vacancy = relationship("Vacancy", back_populates="match_results")
