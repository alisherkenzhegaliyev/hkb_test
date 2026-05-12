from __future__ import annotations

import asyncio
import json
import logging
from src.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Ты — опытный рекрутер. Оцени соответствие кандидата вакансии. "
    "Отвечай ТОЛЬКО на русском языке. "
    'Верни ТОЛЬКО валидный JSON: '
    '{"score": <float 0.0-1.0>, "explanation": "<1-2 предложения>", '
    '"strengths": ["<до 3 пунктов>"], "gaps": ["<до 3 пунктов>"]}'
)


def _make_client():
    if settings.openai_api_key:
        from openai import AsyncOpenAI
        return AsyncOpenAI(api_key=settings.openai_api_key), settings.openai_model
    from groq import AsyncGroq
    return AsyncGroq(api_key=settings.groq_api_key), settings.groq_model


async def _score_one(client, model: str, vacancy: dict, c: dict) -> None:
    user_msg = (
        f"Vacancy: {vacancy.get('title', '')}\n"
        f"{(vacancy.get('description') or '')}\n\n"
        f"Candidate: {c.get('name') or 'Unknown'}, "
        f"{c.get('experience_years') or '?'} yrs exp\n"
        f"Skills: {', '.join((c.get('skills') or [])[:15])}\n\n"
        f"Resume:\n{(c.get('raw_text') or '')}"
    )

    for attempt in range(3):
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=256,
            )
            data = json.loads(resp.choices[0].message.content)
            c["llm_score"] = float(data.get("score", 0.0))
            c["llm_explanation"] = data.get("explanation", "")
            c["strengths"] = data.get("strengths", [])
            c["gaps"] = data.get("gaps", [])
            return
        except Exception as exc:
            err_str = str(exc)
            is_rate_limit = "429" in err_str or "rate_limit" in err_str.lower() or "RateLimitError" in type(exc).__name__
            if is_rate_limit and attempt < 2:
                wait = 15 * (attempt + 1)
                logger.warning("LLM 429 for candidate %s, retrying in %ds", c.get("id"), wait)
                await asyncio.sleep(wait)
            else:
                logger.warning("LLM scoring failed for candidate %s: %s", c.get("id"), exc)
                c.setdefault("llm_score", 0.0)
                c.setdefault("llm_explanation", "Rate limit — try again later" if is_rate_limit else "Scoring unavailable")
                c.setdefault("strengths", [])
                c.setdefault("gaps", [])
                return


async def rank_candidates(
    vacancy: dict,
    candidates: list[dict],
    top_k: int,
) -> list[dict]:
    if not candidates:
        return []

    client, model = _make_client()
    provider = "OpenAI" if settings.openai_api_key else "Groq"
    logger.info("LLM stage: scoring %d candidates via %s (%s)", len(candidates), provider, model)

    for c in candidates:
        await _score_one(client, model, vacancy, c)
        await asyncio.sleep(0.3)

    candidates.sort(key=lambda x: x.get("llm_score", 0.0), reverse=True)
    logger.info("LLM stage: done, returning top %d", top_k)
    return candidates[:top_k]
