from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
from openai import OpenAI

from src.api_access import api_calls_enabled


INDEX_DIR = Path(__file__).resolve().parents[1] / "data" / "rag_index"
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
SPECIALTY_CHUNKS = PROCESSED_DIR / "specialty_chunks.json"
INDUSTRY_CHUNKS = PROCESSED_DIR / "industry_taxonomy_chunks.json"


def index_ready(index_dir: Path = INDEX_DIR) -> bool:
    return (index_dir / "chunks.json").exists() and (index_dir / "embeddings.npy").exists()


def local_corpus_ready(processed_dir: Path = PROCESSED_DIR) -> bool:
    return (processed_dir / "chunks.json").exists() and (processed_dir / "case_cards.json").exists()


@lru_cache(maxsize=1)
def _local_corpus() -> tuple[list[dict], dict[str, dict], list[dict]]:
    cards = json.loads((PROCESSED_DIR / "case_cards.json").read_text(encoding="utf-8"))
    chunks = json.loads((PROCESSED_DIR / "chunks.json").read_text(encoding="utf-8"))
    specialties = json.loads(SPECIALTY_CHUNKS.read_text(encoding="utf-8")) if SPECIALTY_CHUNKS.exists() else []
    industries = json.loads(INDUSTRY_CHUNKS.read_text(encoding="utf-8")) if INDUSTRY_CHUNKS.exists() else []
    return cards, {chunk["id"]: chunk for chunk in chunks}, specialties + industries


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", text)}


def search_local_knowledge(
    query: str,
    top_k: int = 6,
    allowed_sources: set[str] | None = None,
) -> list[dict]:
    if not local_corpus_ready():
        return []
    cards, chunks, specialties = _local_corpus()
    query_tokens = _tokens(query)
    scored: list[tuple[float, dict]] = []
    for card in cards:
        if allowed_sources is not None and card.get("source") not in allowed_sources:
            continue
        haystack = " ".join([
            card.get("source", ""), card.get("section", ""),
            " ".join(card.get("topics", [])), " ".join(card.get("regions", [])),
            card.get("text", ""),
        ])
        overlap = query_tokens & _tokens(haystack)
        if not overlap:
            continue
        exact_bonus = sum(1 for token in query_tokens if token in haystack.lower())
        score = len(overlap) / max(len(query_tokens), 1) + exact_bonus * 0.02 + card.get("quality_score", 0) * 0.002
        chunk = chunks.get(card["chunk_id"], {})
        scored.append((score, {**chunk, **card, "score": score, "keyword_score": score, "search_type": "local-keyword"}))
    for chunk in specialties:
        if allowed_sources is not None and chunk.get("source") not in allowed_sources:
            continue
        haystack = " ".join([
            chunk.get("specialty", ""), chunk.get("industry_name", ""), chunk.get("source", ""), chunk.get("section", ""),
            " ".join(chunk.get("topics", [])), " ".join(chunk.get("regions", [])), chunk.get("text", ""),
        ])
        overlap = query_tokens & _tokens(haystack)
        alias_hits = []
        if chunk.get("chunk_type") == "industry-taxonomy":
            compact_query = re.sub(r"\s+", "", query.lower())
            alias_hits = [alias for alias in [chunk.get("industry_name", ""), *chunk.get("aliases", [])] if alias and re.sub(r"\s+", "", alias.lower()) in compact_query]
        if not overlap and not alias_hits:
            continue
        exact_bonus = sum(1 for token in query_tokens if token in haystack.lower())
        confidence_bonus = {"high": 0.08, "medium": 0.04, "low": 0.0}.get(chunk.get("extraction_confidence"), 0.0)
        alias_bonus = 1.5 + max((len(alias) for alias in alias_hits), default=0) * 0.01 if alias_hits else 0.0
        score = len(overlap) / max(len(query_tokens), 1) + exact_bonus * 0.03 + confidence_bonus + alias_bonus
        scored.append((score, {
            **chunk, "chunk_id": chunk["id"], "source_pages": [1],
            "score": score, "keyword_score": score, "search_type": "local-keyword",
        }))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:top_k]]


def _record_key(item: dict) -> str:
    return str(item.get("chunk_id") or item.get("id") or item.get("case_id"))


def _rrf_merge(keyword: list[dict], dense: list[dict], top_k: int) -> list[dict]:
    """서로 다른 점수 척도를 순위 기반으로 결합한다."""
    merged: dict[str, dict] = {}
    scores: dict[str, float] = {}
    for search_type, results, weight in (("keyword", keyword, 1.0), ("dense", dense, 1.2)):
        for rank, item in enumerate(results, start=1):
            key = _record_key(item)
            merged.setdefault(key, item)
            if "dense_score" in item:
                merged[key]["dense_score"] = item["dense_score"]
            if "keyword_score" in item:
                merged[key]["keyword_score"] = item["keyword_score"]
            scores[key] = scores.get(key, 0.0) + weight / (60 + rank)
            types = set(merged[key].get("matched_by", []))
            types.add(search_type)
            merged[key]["matched_by"] = sorted(types)
    ranked = sorted(merged, key=lambda key: scores[key], reverse=True)[:top_k]
    return [
        {**merged[key], "score": scores[key], "rrf_score": scores[key], "search_type": "hybrid"}
        for key in ranked
    ]


def search_knowledge(
    query: str,
    top_k: int = 6,
    index_dir: Path = INDEX_DIR,
    embedding_model: str = "text-embedding-3-small",
    allowed_sources: set[str] | None = None,
) -> list[dict]:
    keyword_count = int(os.getenv("RAG_KEYWORD_CANDIDATES", "20"))
    dense_count = int(os.getenv("RAG_DENSE_CANDIDATES", "20"))
    keyword = search_local_knowledge(query, keyword_count, allowed_sources=allowed_sources)
    if not index_ready(index_dir) or not api_calls_enabled():
        return keyword[:top_k]
    chunks = json.loads((index_dir / "chunks.json").read_text(encoding="utf-8"))
    matrix = np.load(index_dir / "embeddings.npy")
    query_vector = np.asarray(
        OpenAI().embeddings.create(model=embedding_model, input=query).data[0].embedding,
        dtype=np.float32,
    )
    query_vector /= np.linalg.norm(query_vector) or 1
    scores = matrix @ query_vector
    ranked_positions = np.argsort(scores)[::-1]
    if allowed_sources is not None:
        ranked_positions = np.asarray([
            pos for pos in ranked_positions if chunks[int(pos)].get("source") in allowed_sources
        ])
    positions = ranked_positions[: min(dense_count, len(ranked_positions))]
    dense = [{**chunks[int(pos)], "dense_score": float(scores[int(pos)])} for pos in positions]
    return _rrf_merge(keyword, dense, top_k)
