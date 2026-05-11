import re
import logging
from pathlib import Path
from docling.document_converter import DocumentConverter

logger = logging.getLogger(__name__)

_converter = DocumentConverter()

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(r"[\+\(]?[0-9][0-9\s\-\(\)]{7,}[0-9]")

_SKILLS_HEADERS = re.compile(
    r"(навыки|skills|компетенции|технологии|стек|stack|ключевые\s+навыки|hard\s+skills|soft\s+skills)",
    re.IGNORECASE,
)
_EDU_HEADERS = re.compile(
    r"(образование|education|university|университет|обучение)",
    re.IGNORECASE,
)
_EXP_YEARS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\+?\s*(?:years?|лет|года?|год)|опыт[:\s]+(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def parse(file_path: str | Path) -> dict:
    path = Path(file_path)

    try:
        result = _converter.convert(str(path))
        markdown = result.document.export_to_markdown()
    except Exception as exc:
        logger.warning("docling failed for %s: %s — falling back to raw read", path, exc)
        markdown = _fallback_read(path)

    return {
        "raw_text": markdown,
        "name": _extract_name(markdown),
        "email": _extract_email(markdown),
        "phone": _extract_phone(markdown),
        "skills": _extract_skills_section(markdown),
        "experience_years": _extract_experience_years(markdown),
        "education": _extract_section(markdown, _EDU_HEADERS),
    }


def _fallback_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_email(text: str) -> str | None:
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else None


def _extract_phone(text: str) -> str | None:
    m = _PHONE_RE.search(text)
    return m.group(0).strip() if m else None


def _extract_name(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if not line:
            continue
        if _EMAIL_RE.search(line) or _PHONE_RE.search(line):
            continue
        words = line.split()
        if 2 <= len(words) <= 6 and len(line) < 60:
            return line
    return None


def _extract_experience_years(text: str) -> float | None:
    m = _EXP_YEARS_RE.search(text)
    if m:
        val = m.group(1) or m.group(2)
        try:
            return float(val)
        except (TypeError, ValueError):
            pass
    return None


def _extract_skills_section(text: str) -> list[str]:
    section = _extract_section(text, _SKILLS_HEADERS)
    if not section:
        return []
    skills = []
    for line in section.splitlines():
        line = line.strip().lstrip("-•*·").strip()
        if line and len(line) < 100:
            skills.append(line)
    return skills[:30]  # cap to avoid noise


def _extract_section(text: str, header_re: re.Pattern, max_lines: int = 10) -> str | None:
    lines = text.splitlines()
    capturing = False
    collected: list[str] = []

    for line in lines:
        if header_re.search(line):
            capturing = True
            collected = []
            continue
        if capturing:
            stripped = line.strip()
            # Stop at the next heading
            if stripped.startswith("#") or (stripped and stripped == stripped.upper() and len(stripped) > 3):
                break
            collected.append(stripped)
            if len(collected) >= max_lines:
                break

    result = "\n".join(l for l in collected if l).strip()
    return result if result else None
