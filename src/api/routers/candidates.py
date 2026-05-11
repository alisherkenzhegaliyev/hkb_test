from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_db
from src.models import Candidate
from src.pipeline import process_resume_file
from src.schemas import CandidateOut

router = APIRouter(prefix="/candidates", tags=["candidates"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}


@router.post("/upload", response_model=CandidateOut, status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    save_dir = Path(settings.resumes_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / file.filename

    with save_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        candidate = await process_resume_file(save_path, db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Parsing failed: {exc}") from exc

    return candidate


@router.get("/", response_model=list[CandidateOut])
async def list_candidates(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Candidate).order_by(Candidate.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()
