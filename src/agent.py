from __future__ import annotations

import json
import os
import re

from openai import OpenAI

from src.rag import search_knowledge


SYSTEM_PROMPT = """당신은 지역 음식상권 활성화 전략 컨설턴트다.
제공된 매출 진단과 분류된 PDF 검색 근거만 사용하고 수치를 임의로 만들지 않는다.
매출 변화율은 start_month에서 end_month까지의 변화다. 12개월 전 비교 자료가 없으면 절대로 '전년 동기 대비'라고 쓰지 않는다.

분석 구조:
1) 핵심 진단: 선택 지역·업종의 정량 신호를 짧게 설명한다.
2) 근거 기반 SWOT:
   - Strength: 대상 지역·업종 내부의 Advantage
   - Weakness: 대상 지역·업종 내부의 Pain Point
   - Opportunity: 유사 지역·업종이 강점을 활용했거나 성과를 낸 외부 사례
   - Threat: 유사 지역·업종에서 같은 문제를 악화시킨 조건과 주의점
   - 유사 지역은 정량 지표로 계산된 similar_districts를 우선 사용한다.
3) 교차 전략:
   - SO: 강점을 활용해 기회를 확대
   - WO: 유사 성공사례를 적용해 약점을 보완
   - ST: 현재 강점으로 유사 위험을 방어
   - WT: 약점과 위험이 겹치는 부분을 축소
4) 실행 제안: 사용자 역할에 맞춰 지자체 정책과 점주 솔루션을 구분한다. 각 제안에는 적용 근거와 구체적인 실행 방법을 붙인다.
5) 우선순위: 지금 먼저 할 일 3개만 제시한다.

KPI, 별도의 한계 장, 고정된 90일 계획은 사용자가 명시적으로 요청한 경우에만 작성한다.
검색 근거가 직접 근거가 아니면 '유사 사례에서의 시사점'이라고 명확히 표현한다.
인용은 [문서명 p.페이지] 형식으로 쓰며, 서로 다른 근거 유형을 한 사실처럼 섞지 않는다."""

EVIDENCE_GROUP_LABELS = {
    "local": "선택 지역 근거",
    "industry": "동일·유사 업종 근거",
    "pain": "유사 Pain Point 사례",
    "advantage": "유사 Advantage 활용 사례",
}


def _page_of(item: dict) -> str:
    return str(item.get("page") or (item.get("source_pages") or ["?"])[0])


def rerank_evidence(query: str, evidence: list[dict], final_count: int = 6) -> list[dict]:
    if not evidence or os.getenv("ENABLE_LLM_RERANK", "true").lower() != "true":
        return evidence[:final_count]
    candidates = "\n\n".join(
        f"ID={index}\n출처={item.get('source')} p.{_page_of(item)}\n{item.get('text', '')[:1200]}"
        for index, item in enumerate(evidence)
    )
    prompt = f"""질의와 직접 관련되고 실행 가능한 정책 근거를 고르시오.
지역·업종·고객층·문제 원인·실행수단·측정 성과를 우선한다.
일반론, 목차, 참고문헌, 질의와 다른 지역·업종은 낮게 평가한다.
가장 관련 있는 ID를 최대 {final_count}개, 쉼표로만 구분해 출력한다.

질의: {query}

후보:
{candidates}"""
    try:
        response = OpenAI().responses.create(
            model=os.getenv("OPENAI_RERANK_MODEL", "gpt-5.6-luna"),
            instructions="당신은 한국어 정책 근거 검색 재정렬기다. 요청한 ID 목록 외에는 출력하지 않는다.",
            input=prompt,
        )
        ids = [int(value) for value in re.findall(r"\d+", response.output_text)]
        selected, seen = [], set()
        for index in ids:
            if 0 <= index < len(evidence) and index not in seen:
                selected.append({**evidence[index], "reranked": True})
                seen.add(index)
        return (selected or evidence)[:final_count]
    except Exception:
        return evidence[:final_count]


def retrieve_evidence_groups(
    diagnosis: dict,
    question: str = "",
    embedding_model: str = "text-embedding-3-small",
    per_group: int = 4,
) -> dict[str, list[dict]]:
    """지역·업종·약점·강점 근거를 독립적으로 검색해 한 유형의 문서 쏠림을 줄인다."""
    region = diagnosis["region"]
    industry = diagnosis["industry"]
    pains = " ".join(diagnosis.get("pain_points", []))
    advantages = " ".join(diagnosis.get("advantages", []))
    similar_regions = " ".join(item.get("region", "") for item in diagnosis.get("similar_districts", []))
    queries = {
        "local": f"{region} 외식 상권 현황 활성화 정책 음식점 {question}",
        "industry": f"{industry} 음식점 경쟁력 메뉴 고객 유입 매출 개선 사례 유사상권 {similar_regions} {question}",
        "pain": f"외식 상권 유사 문제 해결 사례 {pains} {industry} 정량 유사지역 {similar_regions} {question}",
        "advantage": f"외식 상권 강점 활용 성공 사례 {advantages} {industry} 정량 유사지역 {similar_regions} {question}",
    }
    groups: dict[str, list[dict]] = {}
    used: set[str] = set()
    candidate_count = max(per_group * 3, 10)
    for group, query in queries.items():
        candidates = search_knowledge(
            query,
            top_k=candidate_count,
            embedding_model=embedding_model,
        )
        fresh = [item for item in candidates if _record_key(item) not in used]
        selected = rerank_evidence(query, fresh or candidates, per_group)
        tagged = [{**item, "evidence_group": group} for item in selected]
        groups[group] = tagged
        used.update(_record_key(item) for item in tagged)
    return groups


def _record_key(item: dict) -> str:
    return str(item.get("chunk_id") or item.get("id") or item.get("case_id"))


def generate_proposal(
    diagnosis: dict,
    evidence: dict[str, list[dict]] | list[dict],
    role: str,
    budget: str,
    question: str,
) -> str:
    if isinstance(evidence, list):
        evidence = {"general": evidence}
    sections = []
    for group, items in evidence.items():
        label = EVIDENCE_GROUP_LABELS.get(group, group)
        body = "\n\n".join(
            f"[{item['source']} p.{_page_of(item)}]\n{item['text']}" for item in items
        ) or "검색된 근거 없음"
        sections.append(f"### {label}\n{body}")
    evidence_text = "\n\n".join(sections)
    prompt = f"""사용자 역할: {role}
예산 수준: {budget}
추가 요청: {question or '없음'}

정량 진단:
{json.dumps(diagnosis, ensure_ascii=False, indent=2)}

유형별 PDF 검색 근거:
{evidence_text}
"""
    response = OpenAI().responses.create(
        model=os.getenv("OPENAI_GENERATION_MODEL", "gpt-5.6-luna"),
        instructions=SYSTEM_PROMPT,
        input=prompt,
    )
    return response.output_text
