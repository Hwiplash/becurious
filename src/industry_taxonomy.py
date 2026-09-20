from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

TAXONOMY_PATH = Path(__file__).resolve().parents[1] / "config" / "industry_taxonomy.json"

def _normalize(value: str) -> str:
    return re.sub(r"[\s·/()_-]+", "", str(value)).lower()

@lru_cache(maxsize=1)
def load_industry_taxonomy() -> list[dict]:
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))

def industry_by_code(code: str | int) -> dict | None:
    value = str(code).strip()
    return next((item for item in load_industry_taxonomy() if item["code"] == value), None)

def resolve_industry_candidates(text: str, allowed_names: set[str] | None = None) -> list[dict]:
    normalized = _normalize(text)
    matches: list[tuple[int, dict, str]] = []
    for item in load_industry_taxonomy():
        if allowed_names is not None and item["name"] not in allowed_names:
            continue
        terms = list(dict.fromkeys([item["name"], *item["aliases"]]))
        best = max((term for term in terms if _normalize(term) in normalized), key=len, default="")
        if best:
            matches.append((len(_normalize(best)), item, best))
    matches.sort(key=lambda value: (-value[0], value[1]["code"]))
    return [{**item, "matched_term": term} for _, item, term in matches]

def resolve_industry_name(text: str, allowed_names: set[str] | None = None) -> str | None:
    candidates = resolve_industry_candidates(text, allowed_names)
    if not candidates:
        return None
    normalized = _normalize(text)
    standard_matches = [item for item in candidates if _normalize(item["name"]) in normalized]
    if standard_matches:
        return max(standard_matches, key=lambda item: len(_normalize(item["name"])))["name"]
    best_length = len(_normalize(candidates[0]["matched_term"]))
    best = [item for item in candidates if len(_normalize(item["matched_term"])) == best_length]
    return best[0]["name"] if len(best) == 1 else None
