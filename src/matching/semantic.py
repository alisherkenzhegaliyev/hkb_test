from __future__ import annotations

import logging
import numpy as np
from src.nlp.embeddings import encode_vacancy, encode_resumes_batch

logger = logging.getLogger(__name__)


def filter_candidates(
    vacancy_text: str,
    candidates: list[dict],
    threshold: float,
) -> list[dict]:
    if not candidates:
        return []

    vacancy_vec = np.array(encode_vacancy(vacancy_text))
    texts = [c.get("raw_text", "") for c in candidates]
    resume_vecs = np.array(encode_resumes_batch(texts))  # shape (N, 1024)

    # Dot product = cosine similarity (BGE-M3 outputs normalized vectors)
    scores = resume_vecs @ vacancy_vec  # shape (N,)

    scored = []
    for c, score in zip(candidates, scores):
        c["semantic_score"] = float(score)
        if float(score) >= threshold:
            scored.append(c)

    scored.sort(key=lambda x: x["semantic_score"], reverse=True)
    logger.info("Semantic stage: %d/%d candidates passed threshold %.3f", len(scored), len(candidates), threshold)
    return scored
