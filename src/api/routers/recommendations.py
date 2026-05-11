from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_db
from src.matching.funnel import run_funnel, run_single_method
from src.models import Candidate, MatchResult, Vacancy
from src.schemas import MatchResultOut, RecommendationResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

VALID_METHODS = {"funnel", "tfidf", "semantic", "llm"}


@router.get("/", response_model=RecommendationResponse)
async def get_recommendations(
    job_id: int = Query(..., description="Vacancy ID"),
    method: str = Query("funnel", description="funnel | tfidf | semantic | llm"),
    top_k: int = Query(5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    if method not in VALID_METHODS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid method '{method}'. Choose from: {sorted(VALID_METHODS)}",
        )

    vac_result = await db.execute(select(Vacancy).where(Vacancy.id == job_id))
    vacancy = vac_result.scalar_one_or_none()
    if vacancy is None:
        raise HTTPException(status_code=404, detail=f"Vacancy {job_id} not found")

    cand_result = await db.execute(select(Candidate))
    all_candidates = [
        {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "raw_text": c.raw_text or "",
            "skills": c.skills or [],
            "experience_years": c.experience_years,
            "education": c.education,
            "embedding": c.embedding,
        }
        for c in cand_result.scalars().all()
    ]

    if not all_candidates:
        return RecommendationResponse(results=[], method=method, vacancy_id=job_id)

    vacancy_dict = {
        "id": vacancy.id,
        "title": vacancy.title,
        "description": vacancy.description,
        "requirements": vacancy.requirements or [],
    }

    if method == "funnel":
        ranked = await run_funnel(
            vacancy=vacancy_dict,
            all_candidates=all_candidates,
            top_k=top_k,
            tfidf_threshold=settings.tfidf_threshold,
            semantic_threshold=settings.semantic_threshold,
        )
    else:
        ranked = await run_single_method(
            method=method,
            vacancy=vacancy_dict,
            all_candidates=all_candidates,
            top_k=top_k,
        )

    results: list[MatchResultOut] = []
    for cand_dict in ranked:
        mr = MatchResult(
            candidate_id=cand_dict["id"],
            vacancy_id=job_id,
            tfidf_score=cand_dict.get("tfidf_score"),
            semantic_score=cand_dict.get("semantic_score"),
            llm_score=cand_dict.get("llm_score"),
            llm_explanation=cand_dict.get("llm_explanation"),
            strengths=cand_dict.get("strengths", []),
            gaps=cand_dict.get("gaps", []),
            method=method,
            created_at=datetime.now(timezone.utc),
        )
        db.add(mr)
        results.append(
            MatchResultOut(
                candidate_id=cand_dict["id"],
                vacancy_id=job_id,
                tfidf_score=cand_dict.get("tfidf_score"),
                semantic_score=cand_dict.get("semantic_score"),
                llm_score=cand_dict.get("llm_score"),
                llm_explanation=cand_dict.get("llm_explanation"),
                strengths=cand_dict.get("strengths", []),
                gaps=cand_dict.get("gaps", []),
                method=method,
                candidate=cand_dict,
            )
        )

    await db.commit()
    return RecommendationResponse(results=results, method=method, vacancy_id=job_id)
