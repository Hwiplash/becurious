from __future__ import annotations

import json
import os
import re
from pathlib import Path

from openai import OpenAI

from src.industry_taxonomy import load_industry_taxonomy
from src.rag import search_knowledge

SPECIALTY_CHUNKS_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "specialty_chunks.json"


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
4) 실행 제안: 지정된 사용자 역할의 권한과 실행 범위 안에서만 제안한다. 각 제안에는 적용 근거와 구체적인 실행 방법을 붙인다.
5) 우선순위: 지금 먼저 할 일 3개만 제시한다.

지역 특산품 메뉴 추천 규칙:
- 정책에 메뉴 개발, 상품 개발, 로컬푸드, 관광 먹거리, 대표 음식, 식재료 연계가 포함될 때만 특산품 메뉴를 제안한다.
- 이 경우 반드시 '지역 특산품·메뉴 근거'에 제시된 선택 지역 또는 해당 광역지역의 특산품 중에서만 1~3개를 고른다.
- 선택 업종의 조리·판매 형태와 연결 이유를 설명한다. 원문에 음식·조리 정보가 있으면 이를 우선 사용한다.
- 원문에 조리 정보가 없으면 특정 레시피를 사실처럼 단정하지 말고 '메뉴 적용 가능성 검토' 또는 '시제품 검증 필요'라고 표시한다.
- 근거에 없는 특산품, 효능, 음식, 레시피를 새로 만들어내지 않는다.
- 메뉴 제안이 정책 목적과 관련 없으면 특산품을 억지로 넣지 않는다.

KPI, 별도의 한계 장, 고정된 90일 계획은 사용자가 명시적으로 요청한 경우에만 작성한다.
검색 근거가 직접 근거가 아니면 '유사 사례에서의 시사점'이라고 명확히 표현한다.
인용은 [문서명 p.페이지] 형식으로 쓰며, 서로 다른 근거 유형을 한 사실처럼 섞지 않는다."""

ROLE_INSTRUCTIONS = {
    "지자체 정책담당자": """답변 대상은 지자체 정책담당자다. 개별 점포 운영 팁이 아니라 공공정책 설계와 집행 의사결정을 지원한다.
반드시 다음 순서와 제목으로 작성한다.
## 정책 판단 요약
- 정량 진단에 근거해 개입 필요성과 정책 목표를 3문장 이내로 제시한다.
## 근거 기반 SWOT
- Strength, Weakness, Opportunity, Threat를 각각 구분한다.
## 정책 패키지
- 3개 안팎의 사업을 제안하고 각 사업마다 대상, 지원 방식, 담당 주체, 선정 기준, 집행 절차를 적는다.
- 메뉴·특산품 사업이면 해당 지역·업종에 맞는 특산품 후보와 공공 지원 방식을 함께 제시한다.
## 예산 수준별 집행안
- 주어진 예산 수준에서 가능한 범위와 민간 자부담·연계기관 필요 여부를 설명한다. 근거 없는 금액은 만들지 않는다.
## 성과관리와 위험 통제
- 측정 가능한 성과지표, 데이터 수집 방법, 형평성·중복지원·지속가능성 위험을 적는다.
## 우선 추진 3단계
- 담당 부서 관점에서 순서, 협업 주체, 착수 조건을 제시한다.
점주에게 직접 명령하는 체크리스트나 점포 한 곳의 레시피·가격·홍보 문구 중심으로 답하지 않는다.""",
    "가게 사장님": """답변 대상은 음식점·식품 점포의 점주다. 행정사업 설계가 아니라 점주가 매장에서 직접 실행할 수 있는 의사결정을 지원한다.
반드시 다음 순서와 제목으로 작성한다.
## 매장 진단 요약
- 매출, 거래, 객단가, 고객 신호가 매장에 뜻하는 바를 쉬운 말로 3문장 이내로 설명한다.
## 기회와 주의점
- 활용할 강점과 먼저 막아야 할 약점을 나누어 적는다.
## 실행 메뉴·상품 전략
- 실행안 3개 안팎을 제시하고 각 실행안마다 대상 고객, 판매 방식, 필요한 준비, 기대 신호를 적는다.
- 특산품이 관련된 요청이면 해당 지역·업종에 맞는 후보를 제시하되 근거 없는 레시피나 효능을 만들지 않는다.
## 고객 유입·재방문 방법
- 매장 채널, 시간대, 세트·포장·홍보 등 점주가 통제할 수 있는 행동으로 구체화한다.
## 비용·운영 난이도
- 주어진 실행 여건에 맞춰 최소 실행안과 확장 조건을 설명한다. 근거 없는 금액은 만들지 않는다.
## 이번 주 우선 행동 3가지
- 바로 확인하거나 시험할 일, 관찰할 지표, 중단·확대 판단 기준을 적는다.
조례, 공모사업 운영, 지원대상 선정, 부서 간 협업처럼 지자체만 수행할 수 있는 일을 점주의 실행안으로 제시하지 않는다.""",
}

ROLE_ALIASES = {
    "지자체": "지자체 정책담당자",
    "점주": "가게 사장님",
}


def role_instructions(role: str) -> str:
    normalized = ROLE_ALIASES.get(role, role)
    if normalized not in ROLE_INSTRUCTIONS:
        raise ValueError(f"지원하지 않는 제안 대상입니다: {role}")
    return ROLE_INSTRUCTIONS[normalized]

EVIDENCE_GROUP_LABELS = {
    "local": "선택 지역 근거",
    "industry": "동일·유사 업종 근거",
    "pain": "유사 Pain Point 사례",
    "advantage": "유사 Advantage 활용 사례",
    "specialty_menu": "지역 특산품·메뉴 근거",
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


def _industry_terms(industry: str) -> list[str]:
    item = next((row for row in load_industry_taxonomy() if row["name"] == industry), None)
    if not item:
        return [industry]
    generic = {"일반음식", "간이음식", "휴게음식", "기타음식", "식당", "푸드트럭"}
    return [industry, *[alias for alias in item["aliases"] if alias not in generic]][:18]


def _rank_specialty_candidates(candidates: list[dict], region: str, industry: str, limit: int) -> list[dict]:
    region_parts = [part for part in region.split() if part]
    industry_terms = _industry_terms(industry)
    strict_menu_industries = {"일식회집", "중국음식", "서양음식", "스넥", "제과점"}
    non_food_terms = ("한지", "묘목", "도자기", "공예", "화장품", "비누", "의류", "목공", "석재", "분재")
    ranked: list[tuple[float, dict]] = []
    for item in candidates:
        if item.get("chunk_type") != "regional-specialty":
            continue
        if any(term in item.get("specialty", "") for term in non_food_terms):
            continue
        item_regions = item.get("regions", [])
        exact_region = all(part in item_regions or any(part in value for value in item_regions) for part in region_parts)
        metro_match = bool(region_parts and any(region_parts[0] in value or value in region_parts[0] for value in item_regions))
        if not exact_region and not metro_match:
            continue
        valid_foods = [food for food in item.get("foods", []) if len(food) <= 300]
        text = " ".join([item.get("specialty", ""), item.get("text", "")[:500], " ".join(valid_foods)])
        compatibility = sum(term in text for term in industry_terms)
        has_food = bool(valid_foods)
        if industry in strict_menu_industries and not compatibility and not has_food:
            continue
        score = (3.0 if exact_region else 1.5) + min(compatibility, 3) * 0.35 + (0.6 if has_food else 0.0)
        score += float(item.get("dense_score", 0)) * 0.2
        ranked.append((score, item))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in ranked[:limit]]


def retrieve_specialty_menu_evidence(
    diagnosis: dict,
    question: str,
    embedding_model: str,
    limit: int = 5,
) -> list[dict]:
    region = diagnosis["region"]
    industry = diagnosis["industry"]
    terms = " ".join(_industry_terms(industry))
    query = f"{region} 지역특산물 {industry} 메뉴 상품 개발 대표음식 로컬푸드 관광 먹거리 식재료 {terms} {question}"
    if SPECIALTY_CHUNKS_PATH.exists():
        candidates = json.loads(SPECIALTY_CHUNKS_PATH.read_text(encoding="utf-8"))
    else:
        candidates = search_knowledge(query, top_k=60, embedding_model=embedding_model)
    selected = _rank_specialty_candidates(candidates, region, industry, limit)
    return [{**item, "evidence_group": "specialty_menu"} for item in selected]


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
    groups["specialty_menu"] = retrieve_specialty_menu_evidence(
        diagnosis, question, embedding_model, limit=max(per_group, 5)
    )
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
    specialized_instructions = role_instructions(role)
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
    prompt = f"""사용자 역할: {ROLE_ALIASES.get(role, role)}
예산 수준: {budget}
추가 요청: {question or '없음'}

정량 진단:
{json.dumps(diagnosis, ensure_ascii=False, indent=2)}

유형별 검색 근거:
{evidence_text}
"""
    response = OpenAI().responses.create(
        model=os.getenv("OPENAI_GENERATION_MODEL", "gpt-5.6-luna"),
        instructions=f"{SYSTEM_PROMPT}\n\n{specialized_instructions}",
        input=prompt,
    )
    return response.output_text
