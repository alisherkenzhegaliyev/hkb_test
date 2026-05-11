from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from src.config import settings
from src.database import AsyncSessionLocal, create_tables
from src.email_service.fetcher import fetch_and_process_emails, last_poll_time
from src.api.routers import candidates, vacancies, recommendations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _email_poll_job() -> None:
    async with AsyncSessionLocal() as db:
        count = await fetch_and_process_emails(AsyncSessionLocal)
        logger.info("Email poll job: processed %d new resumes", count)


def _prewarm_bge() -> None:
    from src.nlp.embeddings import get_model
    get_model()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    await create_tables()
    logger.info("Database tables ready")

    # Load BGE-M3 in background thread — avoids blocking the event loop on first CV
    asyncio.get_event_loop().run_in_executor(None, _prewarm_bge)

    if settings.imap_user and settings.imap_password:
        scheduler.add_job(
            _email_poll_job,
            "interval",
            minutes=settings.email_poll_interval,
            id="email_poll",
            replace_existing=True,
            max_instances=3,
        )
        scheduler.start()
        logger.info("Email poller started — every %d minutes", settings.email_poll_interval)

    yield

    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="AI Recruiting Agent — Home Credit Bank",
    description="3-stage candidate matching: TF-IDF → BGE-M3 semantic → Groq LLM",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(candidates.router)
app.include_router(vacancies.router)
app.include_router(recommendations.router)


@app.get("/health", tags=["health"])
async def health():
    from src.models import Candidate, Vacancy

    async with AsyncSessionLocal() as db:
        cand_count = (await db.execute(select(func.count()).select_from(Candidate))).scalar_one()
        vac_count = (await db.execute(select(func.count()).select_from(Vacancy))).scalar_one()

    from src.email_service import fetcher as f
    last_poll = f.last_poll_time.isoformat() if f.last_poll_time else None

    return {
        "status": "ok",
        "candidate_count": cand_count,
        "vacancy_count": vac_count,
        "last_email_poll": last_poll,
        "email_poller_running": scheduler.running,
    }
