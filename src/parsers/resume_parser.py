import json
import logging
import re
from datetime import date
from pathlib import Path

from groq import Groq
from docling.document_converter import DocumentConverter

from src.config import settings

logger = logging.getLogger(__name__)

_converter = DocumentConverter()
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(r"[\+\(]?[0-9][0-9\s\-\(\)]{7,}[0-9]")

_EXTRACTION_PROMPT = """\
You are a resume parser. Today's date is {today}. Extract structured information from the resume text below.

Return ONLY a valid JSON object with these exact fields:
- name: full name of the candidate (string or null)
- email: email address (string or null)
- phone: phone number (string or null)
- skills: list of technical skills, tools, languages, frameworks (list of strings, exclude soft skills)
- work_positions: list of objects, one per WORK position (jobs, internships, research roles). Each object: {{"title": "...", "company": "...", "start": "YYYY-MM", "end": "YYYY-MM or present", "months": <integer>}}. Treat "Present" as {today}. EXCLUDE any education/university/academic entries entirely.
- experience_years: sum of all months in work_positions divided by 12, rounded to one decimal. Return null if work_positions is empty.
- education: highest education degree and institution (string or null)

Output ONLY the JSON object, no markdown, no explanation.

Resume:
{text}
"""


def parse(file_path: str | Path) -> dict:
    path = Path(file_path)

    try:
        result = _converter.convert(str(path))
        markdown = result.document.export_to_markdown()
    except Exception as exc:
        logger.warning("docling failed for %s: %s — falling back to raw read", path, exc)
        markdown = _fallback_read(path)

    extracted = _extract_with_groq(markdown)
    extracted["raw_text"] = markdown
    logger.info(
        "=== PARSED CANDIDATE ===\n"
        "Name: %s\nEmail: %s\nPhone: %s\nExperience: %s yrs\nEducation: %s\n"
        "Skills (%d): %s\n"
        "raw_text (%d chars) — this is what TF-IDF, BGE-M3, and LLM matching use:\n%s",
        extracted.get("name"),
        extracted.get("email"),
        extracted.get("phone"),
        extracted.get("experience_years"),
        extracted.get("education"),
        len(extracted.get("skills") or []),
        extracted.get("skills"),
        len(markdown),
        markdown,
    )
    return extracted


def _fallback_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_with_groq(text: str) -> dict:
    empty = {"name": None, "email": None, "phone": None, "skills": [], "experience_years": None, "education": None}

    if not settings.groq_api_key:
        logger.warning("GROQ_API_KEY not set — falling back to regex extraction")
        return _extract_with_regex(text)

    try:
        client = Groq(api_key=settings.groq_api_key)
        today = date.today().isoformat()
        prompt = _EXTRACTION_PROMPT.format(text=text, today=today)
        logger.info("Groq extraction prompt (%d chars):\n%s", len(prompt), prompt)
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=512,
        )
        raw = response.choices[0].message.content.strip()
        logger.info("Groq raw response:\n%s", raw)
        # Strip markdown code fences if the model wrapped the output
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw).strip()
        data = json.loads(raw)
        logger.info("Groq work_positions: %s", data.get("work_positions"))
        return {
            "name": data.get("name"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "skills": data.get("skills") or [],
            "experience_years": data.get("experience_years"),
            "education": data.get("education"),
        }
    except Exception as exc:
        logger.warning("Groq extraction failed for resume: %s — falling back to regex", exc)
        return _extract_with_regex(text)


def _extract_with_regex(text: str) -> dict:
    email_m = _EMAIL_RE.search(text)
    phone_m = _PHONE_RE.search(text)
    exp_m = re.search(
        r"(\d+(?:\.\d+)?)\+?\s*(?:years?|лет|года?|год)|опыт[:\s]+(\d+(?:\.\d+)?)",
        text, re.IGNORECASE,
    )
    experience_years = None
    if exp_m:
        val = exp_m.group(1) or exp_m.group(2)
        try:
            experience_years = float(val)
        except (TypeError, ValueError):
            pass

    return {
        "name": None,
        "email": email_m.group(0) if email_m else None,
        "phone": phone_m.group(0).strip() if phone_m else None,
        "skills": [],
        "experience_years": experience_years,
        "education": None,
    }
