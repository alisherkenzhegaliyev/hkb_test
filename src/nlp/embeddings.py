from __future__ import annotations

import logging
import numpy as np

logger = logging.getLogger(__name__)

_model = None


def get_model():
    global _model
    if _model is None:
        from FlagEmbedding import BGEM3FlagModel
        logger.info("Loading BAAI/bge-m3 (first call)...")
        _model = BGEM3FlagModel("BAAI/bge-m3", devices="cpu", use_fp16=False)
        logger.info("BGE-M3 ready.")
    return _model


def encode_vacancy(text: str) -> list[float]:
    out = get_model().encode_queries(
        [text], return_dense=True, return_sparse=False, return_colbert_vecs=False
    )
    return out["dense_vecs"][0].tolist()


def encode_resume(text: str) -> list[float]:
    out = get_model().encode_corpus(
        [text], return_dense=True, return_sparse=False, return_colbert_vecs=False
    )
    return out["dense_vecs"][0].tolist()


def encode_resumes_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    out = get_model().encode_corpus(
        texts, return_dense=True, return_sparse=False, return_colbert_vecs=False
    )
    return out["dense_vecs"].tolist()


def cosine_sim(vec_a: list[float], vec_b: list[float]) -> float:
    a, b = np.array(vec_a), np.array(vec_b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0
