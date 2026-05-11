# AI Recruiting Agent — Home Credit Bank

End-to-end AI recruiting pipeline for **АО Home Credit Bank (ДБ АО «ForteBank»)**:
- Auto-ingests resumes from email (IMAP) or manual upload
- Scrapes live vacancies from hh.kz (employer ID 49971) via Playwright
- Ranks candidates using a 3-stage funnel: TF-IDF → BGE-M3 semantic → Groq LLM
- REST API (FastAPI) + interactive UI (Streamlit)

## Architecture

```
Email Inbox (IMAP)          hh.kz
       │                      │
       ▼                      ▼
[Email Fetcher]        [Playwright Scraper]
       │                      │
       ▼                      ▼
[docling Parser]        [Vacancy DB]
       │
       ▼
[Candidate DB (PostgreSQL)]
       │
       ▼
[3-Stage Matching Funnel]
  1. TF-IDF cosine          (sklearn)
  2. BGE-M3 semantic        (FlagEmbedding)
  3. Groq LLM scoring       (llama-3.3-70b-versatile)
       │
       ▼
[FastAPI] ──► [Streamlit UI]
```

## Matching Funnel

| Stage | Method | Default threshold | Purpose |
|---|---|---|---|
| 1 | TF-IDF cosine (sklearn) | ≥ 0.05 | Lexical filter — remove obvious mismatches fast |
| 2 | BGE-M3 dense embeddings | ≥ 0.35 | Semantic relevance filter |
| 3 | Groq LLaMA-3.3-70B | top-K | Deep reasoning with `{score, explanation, strengths, gaps}` |

Individual methods (`tfidf`, `semantic`, `llm`) can be used standalone via the `method` query param.

## Quickstart

```bash
cp .env.example .env
# Fill in GROQ_API_KEY and optionally IMAP_* for email ingestion
docker-compose up --build
```

- **API docs:** http://localhost:8000/docs
- **Streamlit UI:** http://localhost:8501

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | **Yes** | Groq API key (get one at console.groq.com) |
| `IMAP_HOST` | No | IMAP server (e.g. imap.gmail.com) |
| `IMAP_USER` | No | Email address for resume inbox |
| `IMAP_PASSWORD` | No | Email password / app password |
| `TFIDF_THRESHOLD` | No | Stage 1 cutoff (default 0.05) |
| `SEMANTIC_THRESHOLD` | No | Stage 2 cutoff (default 0.35) |

## API Reference

| Method | Path | Description |
|---|---|---|
| GET | `/health` | System status, candidate/vacancy counts, last email poll |
| POST | `/candidates/upload` | Upload resume file (PDF/DOCX/TXT) |
| GET | `/candidates/` | List all parsed candidates |
| POST | `/vacancies/scrape` | Trigger hh.kz Playwright scrape |
| GET | `/vacancies/` | List all vacancies |
| GET | `/vacancies/{id}` | Get single vacancy |
| GET | `/recommendations/` | Match candidates: `?job_id=1&method=funnel&top_k=5` |

## curl Examples

```bash
# Health check
curl http://localhost:8000/health

# Upload a resume
curl -X POST http://localhost:8000/candidates/upload \
  -F "file=@candidate_resume.pdf"

# Scrape hh.kz vacancies
curl -X POST http://localhost:8000/vacancies/scrape

# Get top-5 candidates (3-stage funnel) for vacancy ID 1
curl "http://localhost:8000/recommendations/?job_id=1&method=funnel&top_k=5"

# Semantic-only matching
curl "http://localhost:8000/recommendations/?job_id=1&method=semantic&top_k=10"
```

## Tech Stack

| Component | Technology |
|---|---|
| Resume parsing | `docling` (IBM) — handles scanned PDFs, multi-column, Cyrillic OCR |
| Vacancy scraping | `playwright` — bypasses hh.kz DDoS Guard (API returns 403) |
| Embeddings | `BAAI/bge-m3` via FlagEmbedding — best <1B retrieval model on RTEB benchmark |
| TF-IDF | `scikit-learn` TfidfVectorizer |
| LLM | `groq` SDK — llama-3.3-70b-versatile |
| Database | PostgreSQL 16 + SQLAlchemy async (asyncpg) |
| API | FastAPI + uvicorn |
| Frontend | Streamlit |
| Email | `imap-tools` (IMAP IDLE polling) |
| Scheduling | APScheduler 3.x |
| Container | Docker Compose |
