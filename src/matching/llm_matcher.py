from __future__ import annotations

import json
import logging
from groq import AsyncGroq
from src.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a senior recruiter. Analyze the fit between a vacancy and a candidate profile. "
    'Return ONLY valid JSON with these exact fields: '
    '{"score": <float 0.0-1.0>, "explanation": "<1-2 sentences>", '
    '"strengths": ["<up to 3 items>"], "gaps": ["<up to 3 items>"]}'
)


async def rank_candidates(
    vacancy: dict,
    candidates: list[dict],
    top_k: int,
) -> list[dict]:
    if not candidates:
        return []

    client = AsyncGroq(api_key=settings.groq_api_key)

    for c in candidates:
        user_msg = (
            f"Vacancy: {vacancy.get('title', '')}\n\n"
            f"{vacancy.get('description', '')[:1000]}\n\n"
            f"Candidate: {c.get('name') or 'Unknown'}\n"
            f"Skills: {c.get('skills', [])}\n"
            f"Experience: {c.get('experience_years') or '?'} years\n\n"
            f"Resume excerpt:\n{c.get('raw_text', '')[:1500]}"
        )
        try:
            resp = await client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=512,
            )
            data = json.loads(resp.choices[0].message.content)
            c["llm_score"] = float(data.get("score", 0.0))
            c["llm_explanation"] = data.get("explanation", "")
            c["strengths"] = data.get("strengths", [])
            c["gaps"] = data.get("gaps", [])
        except Exception as exc:
            logger.warning("Groq scoring failed for candidate %s: %s", c.get("id"), exc)
            c["llm_score"] = 0.0
            c["llm_explanation"] = "Scoring unavailable"
            c["strengths"] = []
            c["gaps"] = []

    candidates.sort(key=lambda x: x["llm_score"], reverse=True)
    logger.info("LLM stage: scored %d candidates, returning top %d", len(candidates), top_k)
    return candidates[:top_k]
