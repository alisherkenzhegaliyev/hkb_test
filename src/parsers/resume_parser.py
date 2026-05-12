import json
import logging
import re
from datetime import date
from pathlib import Path

from docling.document_converter import DocumentConverter

from src.config import settings

logger = logging.getLogger(__name__)

_converter = DocumentConverter()
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(r"[\+\(]?[0-9][0-9\s\-\(\)]{7,}[0-9]")


def _fix_unicode_escapes(text: str) -> str:
    """Convert docling's /uniXXXX escape sequences back to actual characters."""
    def _replace(m: re.Match) -> str:
        try:
            return chr(int(m.group(1), 16))
        except (ValueError, OverflowError):
            return m.group(0)
    return re.sub(r"/uni([0-9A-Fa-f]{4})", _replace, text)

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

    markdown = _fix_unicode_escapes(markdown)
    extracted = _extract_structured(markdown)
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


def _extract_structured(text: str) -> dict:
    if settings.openai_api_key:
        return _extract_with_llm(text, provider="openai")
    if settings.groq_api_key:
        return _extract_with_llm(text, provider="groq")
    logger.warning("No LLM API key configured — falling back to regex extraction")
    return _extract_with_regex(text)


def _extract_with_llm(text: str, provider: str) -> dict:
    try:
        if provider == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            model = settings.openai_model
        else:
            from groq import Groq
            client = Groq(api_key=settings.groq_api_key)
            model = settings.groq_model

        today = date.today().isoformat()
        prompt = _EXTRACTION_PROMPT.format(text=text, today=today)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=1024,
        )
        raw = response.choices[0].message.content.strip()
        logger.info("%s extraction raw response:\n%s", provider, raw)
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw).strip()
        data = json.loads(raw)
        logger.info("work_positions: %s", data.get("work_positions"))
        return {
            "name": data.get("name"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "skills": data.get("skills") or [],
            "experience_years": data.get("experience_years"),
            "education": data.get("education"),
        }
    except Exception as exc:
        logger.warning("%s extraction failed: %s — falling back to regex", provider, exc)
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
