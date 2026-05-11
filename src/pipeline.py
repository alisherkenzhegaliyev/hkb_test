from __future__ import annotations

import asyncio
import logging
from pathlib import Path

# Docling + easyocr are not safe to run concurrently — one pipeline at a time
_pipeline_sem = asyncio.Semaphore(1)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models import Candidate
from src.parsers.resume_parser import parse as parse_resume
from src.nlp.embeddings import encode_resume
from src.nlp import tfidf as tfidf_module

logger = logging.getLogger(__name__)


async def process_resume_file(file_path: str | Path, db: AsyncSession) -> Candidate:
    """Parse a resume file, generate embeddings, and upsert into the database."""
    file_path = Path(file_path)
    loop = asyncio.get_event_loop()

    # Semaphore ensures only one docling/easyocr instance runs at a time
    async with _pipeline_sem:
        parsed = await loop.run_in_executor(None, parse_resume, file_path)
        embedding = await loop.run_in_executor(None, encode_resume, parsed["raw_text"])

    # Deduplicate by email first, fall back to source_file
    candidate = None
    parsed_email = parsed.get("email")
    if parsed_email:
        result = await db.execute(select(Candidate).where(Candidate.email == parsed_email))
        candidate = result.scalar_one_or_none()
    if candidate is None:
        result = await db.execute(select(Candidate).where(Candidate.source_file == file_path.name))
        candidate = result.scalar_one_or_none()

    if candidate is None:
        candidate = Candidate(
            name=parsed.get("name"),
            email=parsed.get("email"),
            phone=parsed.get("phone"),
            raw_text=parsed.get("raw_text", ""),
            skills=parsed.get("skills", []),
            experience_years=parsed.get("experience_years"),
            education=parsed.get("education", ""),
            embedding=embedding,
            source_file=file_path.name,
        )
        db.add(candidate)
    else:
        candidate.name = parsed.get("name") or candidate.name
        candidate.email = parsed.get("email") or candidate.email
        candidate.phone = parsed.get("phone") or candidate.phone
        candidate.raw_text = parsed.get("raw_text", "") or candidate.raw_text
        candidate.skills = parsed.get("skills", []) or candidate.skills
        candidate.experience_years = parsed.get("experience_years") or candidate.experience_years
        candidate.education = parsed.get("education", "") or candidate.education
        candidate.embedding = embedding
        candidate.source_file = file_path.name

    await db.commit()
    await db.refresh(candidate)

    logger.info("Processed candidate: %s (id=%s)", candidate.name, candidate.id)

    await _refit_tfidf(db)

    return candidate


async def _refit_tfidf(db: AsyncSession) -> None:
    """Refit TF-IDF vectorizer on all candidate raw texts."""
    result = await db.execute(select(Candidate.raw_text))
    texts = [row[0] for row in result.fetchall() if row[0]]
    if texts:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, tfidf_module.fit_and_save, texts)
