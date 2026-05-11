# AI Recruiting Agent — Project Guide

## What This Project Is

An AI-powered recruiting agent for **АО Home Credit Bank (ДБ АО «ForteBank»)** that:
- Ingests candidate resumes from email (IMAP, primary path) or file upload
- Scrapes real vacancies from hh.kz (employer ID 49971) using Playwright
- Matches candidates to vacancies via a 3-stage funnel
- Returns top-5 candidates with LLM explanations via FastAPI + Streamlit

## Tech Stack

- **Parsing**: `docling` (PDF/DOCX → markdown) + regex for name/email/phone extraction
- **Vacancy scraping**: `playwright` Chromium headless → hh.kz
- **Embeddings**: `BAAI/bge-m3` (local, 1024-dim, best <1B retrieval model on RTEB)
- **TF-IDF**: `scikit-learn` TfidfVectorizer
- **LLM**: `groq` SDK — `llama3-70b-8192` for Stage 3 matching + explanations
- **DB**: PostgreSQL + SQLAlchemy async (asyncpg)
- **API**: FastAPI + uvicorn
- **Frontend**: Streamlit
- **Scheduling**: APScheduler (email polling + re-indexing)
- **Container**: Docker Compose (services: postgres, api, streamlit)

## Matching Funnel (3-Stage Cascade)

```
All candidates
    │
    ▼  Stage 1: TF-IDF (sklearn) — lexical filter, threshold 0.05
    ▼  Stage 2: BGE-M3 dense embeddings — semantic filter, threshold 0.35
    ▼  Stage 3: Groq LLaMA3-70B — deep reasoning, returns top-5 with {score, explanation, strengths, gaps}
```

API also supports standalone `method=semantic`, `method=tfidf`, `method=llm`.

## Project Structure

```
hkb_test/
├── src/
│   ├── config.py              # pydantic-settings, all env vars
│   ├── database.py            # async SQLAlchemy engine
│   ├── models.py              # ORM: Candidate, Vacancy, MatchResult
│   ├── schemas.py             # Pydantic schemas
│   ├── pipeline.py            # parse → embed → store orchestrator
│   ├── email_service/fetcher.py   # IMAP polling
│   ├── parsers/resume_parser.py   # docling + regex
│   ├── vacancy_scraper/hh_scraper.py  # Playwright hh.kz
│   ├── nlp/embeddings.py      # BGE-M3 singleton
│   ├── nlp/tfidf.py           # TF-IDF fit/transform/persist
│   ├── matching/funnel.py     # 3-stage cascade
│   ├── matching/tfidf_matcher.py
│   ├── matching/semantic.py
│   ├── matching/llm_matcher.py
│   └── api/
│       ├── main.py            # FastAPI app + APScheduler
│       └── routers/           # candidates, vacancies, recommendations
├── frontend/app.py            # Streamlit 4-tab UI
├── data/resumes/              # saved email attachments
├── notebooks/exploration.ipynb
├── Dockerfile.api
├── Dockerfile.streamlit
├── docker-compose.yml
└── .env.example
```

## Environment Variables

All secrets in `.env` (never committed). See `.env.example` for full list.
Key vars: `IMAP_HOST`, `IMAP_USER`, `IMAP_PASSWORD`, `GROQ_API_KEY`, `DATABASE_URL`, `EMPLOYER_ID`.

## Running Locally

```bash
cp .env.example .env  # fill in your credentials
docker-compose up --build
# API:       http://localhost:8000/docs
# Streamlit: http://localhost:8501
```

## Key Decisions

- **docling over pdfplumber**: handles multi-column, scanned, Cyrillic OCR — critical for varied resume formats
- **No LLM at parse time**: docling + regex is sufficient for extraction; Groq LLM only used in Stage 3 matching. If parsing proves insufficient, add Groq extraction step in `resume_parser.py`.
- **BGE-M3 over paraphrase-multilingual-mpnet**: BGE-M3 is purpose-built for retrieval (not paraphrase detection), top local model on RTEB benchmark
- **Playwright over hh.kz API**: hh.kz API returns 403 (DDoS Guard) for server-side requests — confirmed
- **Semantic pre-filter before LLM**: avoids O(N) Groq calls; semantic narrows to ~30, LLM scores those 30
