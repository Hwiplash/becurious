from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.agent import EVIDENCE_GROUP_LABELS, generate_proposal, retrieve_evidence_groups
from src.analytics import diagnose_region
from src.rag import INDEX_DIR, index_ready, local_corpus_ready


load_dotenv()


def _score_label(item: dict) -> str:
    parts = []
    if item.get("dense_score") is not None:
        parts.append(f"의미 유사도 {item['dense_score']:.3f}")
    matched = item.get("matched_by", [])
    if matched:
        names = {"dense": "임베딩", "keyword": "키워드"}
        parts.append("검색 " + "+".join(names.get(value, value) for value in matched))
    if item.get("rrf_score") is not None:
        parts.append(f"종합순위점수 {item['rrf_score']:.4f}")
    return " · ".join(parts) or "키워드 검색 결과"


def render_ai_agent(data: pd.DataFrame) -> None:
    st.markdown("<div class='section-label'>LOCAL COMMERCE AI AGENT</div>", unsafe_allow_html=True)
    st.header("상권 부흥 정책 제안 에이전트")
    st.caption("정량 매출 진단과 PDF 정책·사례 근거를 결합해 지자체 및 점주 실행안을 제안합니다.")

    c1, c2, c3 = st.columns(3)
    sido = c1.selectbox("시도", sorted(data["SIDO_NM"].unique()), key="ai_sido")
    local = data[data["SIDO_NM"] == sido]
    ccg = c2.selectbox("시군구", sorted(local["CCG_NM"].unique()), key="ai_ccg")
    local = local[local["CCG_NM"] == ccg]
    industry = c3.selectbox("업종", sorted(local["TP_BUZ_NM"].unique()), key="ai_industry")

    c4, c5 = st.columns(2)
    role = c4.radio("제안 대상", ["지자체 정책담당자", "가게 사장님", "둘 다"], horizontal=True)
    budget = c5.select_slider("실행 예산", ["최소", "낮음", "중간", "높음"], value="중간")
    question = st.text_input("추가 요청", placeholder="예: 40대 가족 고객을 다시 유입할 수 있는 전략을 제안해줘")

    try:
        diagnosis = diagnose_region(data, sido, ccg, industry)
    except ValueError as exc:
        st.warning(str(exc))
        return

    left, right = st.columns(2)
    with left:
        st.subheader("Pain Points")
        for item in diagnosis.pain_points:
            st.error(item, icon="⚠️")
    with right:
        st.subheader("Advantages")
        for item in diagnosis.advantages:
            st.success(item, icon="↗️")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("업종 매출 변화", f"{diagnosis.sales_change:+.1%}")
    k2.metric("거래 건수 변화", f"{diagnosis.transaction_change:+.1%}")
    k3.metric("건당 결제 변화", f"{diagnosis.ticket_change:+.1%}")
    k4.metric("지역 전체 변화", f"{diagnosis.regional_sales_change:+.1%}")

    if not index_ready() and local_corpus_ready():
        st.info("현재 로컬 키워드 검색으로 작동합니다. API 임베딩을 만들면 의미 기반 검색이 추가됩니다.")
    elif not local_corpus_ready():
        st.info(f"PDF 말뭉치가 없습니다. `python scripts/build_local_corpus.py`를 실행하세요.\n\n인덱스 위치: {INDEX_DIR}")
    if not os.getenv("OPENAI_API_KEY"):
        st.warning("OPENAI_API_KEY가 설정되지 않아 AI 제안 생성은 비활성화됩니다.")

    per_group = int(os.getenv("RAG_RESULTS_PER_GROUP", "3"))
    if st.button("지역·업종·Pain·Advantage 근거 검색", width="stretch"):
        evidence_groups = retrieve_evidence_groups(
            diagnosis.to_dict(), question,
            os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            per_group,
        )
        st.subheader("유형별 PDF 근거")
        for group, items in evidence_groups.items():
            st.markdown(f"#### {EVIDENCE_GROUP_LABELS[group]}")
            if not items:
                st.caption("일치하는 근거가 없습니다.")
            for item in items:
                page = item.get("page") or (item.get("source_pages") or [""])[0]
                st.markdown(f"**{item.get('source', '출처 미상')} · p.{page}**")
                st.caption(_score_label(item))
                st.caption(item.get("text", "")[:700])

    if st.button("AI 정책 제안 생성", type="primary", disabled=not os.getenv("OPENAI_API_KEY"), width="stretch"):
        with st.spinner("지역 진단과 유사 사례를 결합하는 중입니다…"):
            evidence_groups = retrieve_evidence_groups(
                diagnosis.to_dict(), question,
                os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
                per_group,
            )
            proposal = generate_proposal(diagnosis.to_dict(), evidence_groups, role, budget, question)
        st.subheader("제안 결과")
        st.markdown(proposal)
        with st.expander("검색된 PDF 근거", expanded=True):
            if not any(evidence_groups.values()):
                st.caption("검색된 근거가 없습니다. 제안은 정량 진단만 바탕으로 생성되었습니다.")
            for group, items in evidence_groups.items():
                st.markdown(f"#### {EVIDENCE_GROUP_LABELS[group]}")
                for item in items:
                    page = item.get("page") or (item.get("source_pages") or [""])[0]
                    st.markdown(f"**{item['source']} · p.{page}**")
                    st.caption(_score_label(item))
                    st.caption(item["text"][:700])
