from __future__ import annotations

import logging
from src.matching import tfidf_matcher, semantic, llm_matcher

logger = logging.getLogger(__name__)


async def run_funnel(
    vacancy: dict,
    all_candidates: list[dict],
    top_k: int,
    tfidf_threshold: float,
    semantic_threshold: float,
) -> list[dict]:
    if not all_candidates:
        return []

    vacancy_text = f"{vacancy.get('title', '')}\n\n{vacancy.get('description', '')}"

    logger.info("Funnel start: %d candidates", len(all_candidates))

    stage1 = tfidf_matcher.filter_candidates(vacancy_text, all_candidates, tfidf_threshold)
    logger.info("Stage 1 (TF-IDF): %d remain", len(stage1))
    if not stage1:
        return []

    stage2 = semantic.filter_candidates(vacancy_text, stage1, semantic_threshold)
    logger.info("Stage 2 (Semantic): %d remain", len(stage2))
    if not stage2:
        return []

    stage3 = await llm_matcher.rank_candidates(vacancy, stage2, top_k)
    logger.info("Stage 3 (LLM): %d final results", len(stage3))
    return stage3


async def run_single_method(
    method: str,
    vacancy: dict,
    all_candidates: list[dict],
    top_k: int,
) -> list[dict]:
    if not all_candidates:
        return []

    vacancy_text = f"{vacancy.get('title', '')}\n\n{vacancy.get('description', '')}"

    if method == "tfidf":
        results = tfidf_matcher.filter_candidates(vacancy_text, all_candidates, threshold=0.0)
        return results[:top_k]

    elif method == "semantic":
        results = semantic.filter_candidates(vacancy_text, all_candidates, threshold=0.0)
        return results[:top_k]

    elif method == "llm":
        return await llm_matcher.rank_candidates(vacancy, all_candidates, top_k)

    else:
        raise ValueError(f"Unknown method: {method}. Use funnel, tfidf, semantic, or llm.")
