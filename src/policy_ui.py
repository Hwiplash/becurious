from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from src.agent import EVIDENCE_GROUP_LABELS, generate_proposal, retrieve_evidence_groups
from src.api_access import api_calls_enabled
from src.analytics import diagnose_scope, find_similar_districts
from src.industry_taxonomy import resolve_industry_name


@st.dialog("✨ 상권 활성화 솔루션 제안", width="large")
def policy_dialog(
    data: pd.DataFrame,
    indices: dict[str, pd.DataFrame] | None = None,
    default_sido: str | None = None,
    default_ccg: str | None = None,
    default_industry: str | None = None,
    initial_question: str = "",
) -> None:
    all_regions = "전체 지역"
    sido_options = [all_regions, *sorted(data["SIDO_NM"].unique())]
    sido = st.selectbox(
        "시도", sido_options,
        index=sido_options.index(default_sido) if default_sido in sido_options else 0,
        key=f"policy_sido_{default_sido or 'all'}_{default_ccg or 'all'}",
    )
    local = data if sido == all_regions else data[data["SIDO_NM"] == sido]
    ccg_options = [all_regions] if sido == all_regions else [all_regions, *sorted(local["CCG_NM"].unique())]
    ccg = st.selectbox(
        "시군구", ccg_options,
        index=ccg_options.index(default_ccg) if default_ccg in ccg_options else 0,
        key=f"policy_ccg_{default_sido or 'all'}_{default_ccg or 'all'}",
        disabled=sido == all_regions,
    )
    if ccg != all_regions:
        local = local[local["CCG_NM"] == ccg]
    industry_options = sorted(local["TP_BUZ_NM"].unique())
    industry = st.selectbox(
        "업종", industry_options,
        index=industry_options.index(default_industry) if default_industry in industry_options else 0,
        key=f"policy_industry_{default_sido or 'all'}_{default_ccg or 'all'}_{default_industry or 'all'}",
    )
    role = st.segmented_control(
        "답변 형식",
        ["지자체", "점주"],
        default="지자체",
        key="policy_role_v2",
        help="지자체는 정책·집행 중심, 점주는 매장 운영·메뉴 실행 중심으로 답변합니다.",
    )
    question = st.text_area(
        "추가 요청",
        value=initial_question,
        placeholder="예: 약해진 30대 고객층을 회복하면서 강점 고객층을 활용할 정책을 제안해줘",
        height=90,
    )
    api_enabled = api_calls_enabled()
    if not api_enabled:
        st.info("현재 공개 데모에서는 AI 분석 기능이 비활성화되어 있습니다. 지역·업종과 요청 내용을 선택해 화면 구성을 체험할 수 있습니다.")
    if st.button(
        "분석 시작" if api_enabled else "분석 시작 · 데모에서는 비활성화",
        type="primary",
        width="stretch",
        disabled=not api_enabled,
    ):
        selected_sido = None if sido == all_regions else sido
        selected_ccg = None if ccg == all_regions else ccg
        diagnosis = diagnose_scope(data, industry, selected_sido, selected_ccg)
        diagnosis_payload = diagnosis.to_dict()
        if indices and selected_sido is not None and selected_ccg is not None:
            diagnosis_payload["similar_districts"] = find_similar_districts(
                data, indices, selected_sido, selected_ccg, industry, top_k=5
            )
            base = indices["지역지수"]
            premium = indices["프리미엄"]
            population = indices["인구보정"]
            industry_rank = indices["업종순위"]
            base_row = base[(base["시도"] == selected_sido) & (base["시군구"] == selected_ccg)]
            premium_row = premium[(premium["시도"] == selected_sido) & (premium["시군구"] == selected_ccg)]
            population_row = population[(population["시도"] == selected_sido) & (population["시군구"] == selected_ccg)]
            industry_row = industry_rank[(industry_rank["시도"] == selected_sido) & (industry_rank["시군구"] == selected_ccg) & (industry_rank["업종"] == industry)]
            if not base_row.empty and not premium_row.empty and not population_row.empty:
                b, p, pop = base_row.iloc[0], premium_row.iloc[0], population_row.iloc[0]
                diagnosis_payload["commercial_indices"] = {
                    "scale_index": float(b["결제금액 규모지수"]),
                    "activity_index": float(b["거래활력지수"]),
                    "premium_index": float(p["6개월 통합 프리미엄지수"]),
                    "diversity_index": float(b["업종다양성지수"]),
                    "population_spend_index": float(pop["개인 금액 지수(평균=100)"]),
                    "population_transaction_index": float(pop["개인 건수 지수(평균=100)"]),
                    "market_type": str(p["규모·프리미엄 유형"]),
                    "top_industry": str(b["최대 업종"]),
                }
            if not industry_row.empty:
                row = industry_row.iloc[0]
                diagnosis_payload["industry_ranks"] = {
                    "local_rank": int(row["지역 내 업종순위"]),
                    "national_same_industry_rank": int(row["전국 동일업종 지역순위"]),
                    "metro_same_industry_rank": int(row["광역 동일업종 지역순위"]),
                }
        with st.spinner("지역·업종·유사 Pain·유사 Advantage 사례를 각각 분석하고 있습니다…"):
            evidence = retrieve_evidence_groups(
                diagnosis_payload, question,
                os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
                int(os.getenv("RAG_RESULTS_PER_GROUP", "3")),
                role=role or "지자체",
            )
            proposal = generate_proposal(
                diagnosis_payload, evidence,
                {"지자체": "지자체 정책담당자", "점주": "가게 사장님"}[role or "지자체"],
                question=question,
            )
        st.markdown(proposal)
        similar = diagnosis_payload.get("similar_districts", [])
        if similar:
            st.markdown("#### 정량 유사 상권")
            st.caption("상권 체력 55% · 업종 성과 30% · 고객 연령구조 15%를 표준화해 비교했습니다.")
            st.markdown(" · ".join(
                f"**{item['region']}** {item['match_score']:.1f}점" for item in similar
            ))
        with st.expander("제안에 사용된 근거 확인"):
            for group, items in evidence.items():
                st.markdown(f"**{EVIDENCE_GROUP_LABELS[group]}**")
                for item in items:
                    page = item.get("page") or (item.get("source_pages") or ["?"])[0]
                    similarity = item.get("dense_score")
                    suffix = f" · 의미 유사도 {similarity:.3f}" if similarity is not None else ""
                    st.caption(f"{item.get('source')} · p.{page}{suffix}")


def render_chat_launcher(
    data: pd.DataFrame,
    indices: dict[str, pd.DataFrame] | None = None,
    sido: str | None = None,
    ccg: str | None = None,
    industry: str | None = None,
) -> None:
    st.markdown("<div class='chat-label'>AI에게 바로 물어보세요</div>", unsafe_allow_html=True)
    scope = " ".join(value for value in (sido, ccg, industry if industry != "업종 전체" else None) if value)
    scope = scope or "우리 지역 외식 상권"
    suggested_questions = [
        f"{scope}의 가장 큰 약점과 우선 개선 정책은 무엇인가요?",
        f"{scope}의 강점을 활용해 방문과 재방문을 늘릴 방법은 무엇인가요?",
        f"{scope} 기준으로 유사한 지역·업종 사례를 찾아 실행 대책을 제안해 주세요.",
    ]
    selected_question = None
    key_scope = f"{sido or 'all'}_{ccg or 'all'}_{industry or 'all'}"
    with st.container(key="quick_questions"):
        question_columns = st.columns(3)
        for index, (column, question) in enumerate(zip(question_columns, suggested_questions)):
            if column.button(f'“{question}”', key=f"quick_question_{key_scope}_{index}", width="stretch"):
                selected_question = question

    prompt = st.chat_input("지역과 업종의 문제를 입력하면 근거 기반 정책을 제안해드려요")
    prompt = selected_question or prompt
    if prompt:
        allowed_industries = set(data["TP_BUZ_NM"].unique())
        matched_industry = resolve_industry_name(prompt, allowed_industries)
        matched_industry = matched_industry or next((name for name in sorted(allowed_industries, key=len, reverse=True) if name in prompt), industry)
        matched_sido = next((name for name in sorted(data["SIDO_NM"].unique(), key=len, reverse=True) if name in prompt), sido)
        search_scope = data[data["SIDO_NM"] == matched_sido] if matched_sido else data
        matched_ccg = next((name for name in sorted(search_scope["CCG_NM"].unique(), key=len, reverse=True) if name in prompt), ccg)
        policy_dialog(data, indices, matched_sido, matched_ccg, matched_industry, prompt)
