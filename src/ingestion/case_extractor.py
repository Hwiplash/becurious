from __future__ import annotations

import hashlib


CASE_KEYWORDS = ("사례", "정책", "전략", "활성화", "개선", "대책", "방안", "성과", "효과", "제안", "로드맵", "시사점")
PROBLEM_TERMS = ("감소", "침체", "부족", "문제", "쇠퇴", "노후", "부진", "약화", "폐업", "공실", "갈등", "부담")
ACTION_TERMS = ("조성", "지원", "개선", "개발", "육성", "연계", "교육", "홍보", "마케팅", "브랜드", "정비", "도입")


def is_candidate(chunk: dict) -> bool:
    text = chunk["text"]
    return candidate_score(chunk) >= 5


def candidate_score(chunk: dict) -> int:
    text = chunk["text"]
    case_hits = sum(keyword in text for keyword in CASE_KEYWORDS)
    problem_hits = sum(keyword in text for keyword in PROBLEM_TERMS)
    action_hits = sum(keyword in text for keyword in ACTION_TERMS)
    outcome_hits = sum(term in text for term in ("증가", "향상", "성과", "효과", "감소"))
    if len(text) < 250 or case_hits < 2 or not (problem_hits or action_hits):
        return 0
    return case_hits * 2 + min(problem_hits, 3) + min(action_hits, 3) + min(outcome_hits, 2)


def _sentences(text: str, terms: tuple[str, ...], limit: int = 4) -> list[str]:
    parts = [part.strip() for part in text.replace("\n", " ").split(".") if part.strip()]
    return [part[:300] for part in parts if any(term in part for term in terms)][:limit]


def build_case_card(chunk: dict) -> dict:
    digest = hashlib.sha1(chunk["id"].encode("utf-8")).hexdigest()[:12]
    outcomes = _sentences(chunk["text"], ("증가", "향상", "개선되", "감소하", "성과"), 3)
    evidence_level = "measured" if any(char.isdigit() for sentence in outcomes for char in sentence) else "proposal"
    return {
        "case_id": f"case-{digest}",
        "document_id": chunk["document_id"],
        "source": chunk["source"],
        "source_pages": [chunk["page"]],
        "section": chunk.get("section", ""),
        "topics": chunk.get("topics", []),
        "regions": chunk.get("regions", []),
        "problems": _sentences(chunk["text"], PROBLEM_TERMS),
        "interventions": _sentences(chunk["text"], ACTION_TERMS),
        "outcomes": outcomes,
        "evidence_level": evidence_level,
        "text": chunk["text"][:1800],
        "chunk_id": chunk["id"],
        "quality_score": candidate_score(chunk),
    }
