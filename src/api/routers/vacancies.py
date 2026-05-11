from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models import Vacancy
from src.schemas import ScrapeResponse, VacancyOut
from src.vacancy_scraper.hh_scraper import scrape_vacancies

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vacancies", tags=["vacancies"])


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape(db: AsyncSession = Depends(get_db)):
    try:
        raw_vacancies = await scrape_vacancies()
    except Exception as exc:
        logger.exception("Scraping failed")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {exc}") from exc

    imported = 0
    for vac in raw_vacancies:
        existing = await db.execute(
            select(Vacancy).where(Vacancy.hh_id == vac["hh_id"])
        )
        db_vac = existing.scalar_one_or_none()
        if db_vac is None:
            db_vac = Vacancy(
                hh_id=vac["hh_id"],
                title=vac["title"],
                description=vac["description"],
                requirements=vac.get("requirements", []),
                url=vac["url"],
                scraped_at=datetime.now(timezone.utc),
            )
            db.add(db_vac)
            imported += 1
        else:
            db_vac.title = vac["title"]
            db_vac.description = vac["description"]
            db_vac.requirements = vac.get("requirements", [])
            db_vac.url = vac["url"]
            db_vac.scraped_at = datetime.now(timezone.utc)

    await db.commit()
    logger.info("Scrape complete: %d new vacancies imported", imported)
    return ScrapeResponse(imported=imported, total=len(raw_vacancies))


@router.get("/", response_model=list[VacancyOut])
async def list_vacancies(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Vacancy).order_by(Vacancy.scraped_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{vacancy_id}", response_model=VacancyOut)
async def get_vacancy(vacancy_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Vacancy).where(Vacancy.id == vacancy_id))
    vac = result.scalar_one_or_none()
    if vac is None:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return vac
