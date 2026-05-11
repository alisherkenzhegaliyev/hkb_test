from __future__ import annotations

import logging
from src.nlp.tfidf import transform, cosine_sim_sparse

logger = logging.getLogger(__name__)


def filter_candidates(
    vacancy_text: str,
    candidates: list[dict],
    threshold: float,
) -> list[dict]:
    if not candidates:
        return []

    vacancy_vec = transform(vacancy_text)

    scored = []
    for c in candidates:
        try:
            c_vec = transform(c.get("raw_text", ""))
            score = cosine_sim_sparse(vacancy_vec, c_vec)
        except Exception as exc:
            logger.warning("TF-IDF scoring failed for candidate %s: %s", c.get("id"), exc)
            score = 0.0
        c["tfidf_score"] = score
        if score >= threshold:
            scored.append(c)

    scored.sort(key=lambda x: x["tfidf_score"], reverse=True)
    logger.info("TF-IDF stage: %d/%d candidates passed threshold %.3f", len(scored), len(candidates), threshold)
    return scored
