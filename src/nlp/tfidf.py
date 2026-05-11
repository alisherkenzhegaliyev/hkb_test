from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.config import settings

logger = logging.getLogger(__name__)

_vectorizer: TfidfVectorizer | None = None


def _load_from_disk() -> TfidfVectorizer | None:
    path = Path(settings.tfidf_model_path)
    if path.exists():
        try:
            return joblib.load(path)
        except Exception as exc:
            logger.warning("Failed to load TF-IDF model from disk: %s", exc)
    return None


def get_vectorizer() -> TfidfVectorizer:
    global _vectorizer
    if _vectorizer is None:
        _vectorizer = _load_from_disk()
    if _vectorizer is None:
        _vectorizer = TfidfVectorizer(sublinear_tf=True, min_df=1, analyzer="word")
    return _vectorizer


def fit_and_save(texts: list[str]) -> None:
    global _vectorizer
    _vectorizer = TfidfVectorizer(sublinear_tf=True, min_df=1, analyzer="word")
    _vectorizer.fit(texts)
    path = Path(settings.tfidf_model_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(_vectorizer, path)
    logger.info("TF-IDF model fitted on %d texts and saved.", len(texts))


def transform(text: str):
    vec = get_vectorizer()
    try:
        return vec.transform([text])
    except Exception:
        # Not fitted yet — fit on the single text (degenerate but safe)
        vec.fit([text])
        return vec.transform([text])


def cosine_sim_sparse(vec_a, vec_b) -> float:
    score = cosine_similarity(vec_a, vec_b)
    return float(score[0][0])
