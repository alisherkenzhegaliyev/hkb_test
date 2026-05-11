from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CandidateOut(BaseModel):
    id: int
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    skills: list
    experience_years: Optional[float]
    education: Optional[str]
    source_file: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class VacancyOut(BaseModel):
    id: int
    hh_id: Optional[str]
    title: str
    description: str
    requirements: list
    url: Optional[str]
    scraped_at: datetime

    model_config = {"from_attributes": True}


class MatchResultOut(BaseModel):
    candidate_id: int
    vacancy_id: int
    method: str
    tfidf_score: Optional[float]
    semantic_score: Optional[float]
    llm_score: Optional[float]
    llm_explanation: Optional[str]
    strengths: list
    gaps: list
    candidate: Optional[dict] = None


class RecommendationResponse(BaseModel):
    vacancy_id: int
    method: str
    results: list[MatchResultOut]


class ScrapeResponse(BaseModel):
    imported: int
    total: int


class HealthResponse(BaseModel):
    status: str
    candidate_count: int
    vacancy_count: int
    last_email_poll: Optional[str]
