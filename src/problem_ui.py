"""M9 JSON을 사용하는 개인 소비 비교 화면. 모형·후보 재판정은 하지 않는다."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.charts import prediction_trend
from src.data import POPULATION_NOTE, compact_won, comparison_details


def render_comparison(region: dict, monthly: pd.DataFrame) -> None:
    if monthly.empty:
        st.info("선택한 지역·업종의 M9 비교 자료가 없습니다.")
        return
    detail = comparison_details(monthly)
    st.caption(POPULATION_NOTE)
    observed = detail["data_available"].sum()
    amount = detail["actual_amt"].sum(min_count=1)
    count = detail["actual_cnt"].sum(min_count=1)
    ticket = amount / count if pd.notna(count) and count != 0 else float("nan")
    first, last = detail.iloc[0], detail.iloc[-1]
    rate = last.actual_amt / first.actual_amt - 1 if pd.notna(first.actual_amt) and first.actual_amt != 0 else float("nan")
    cols = st.columns(4)
    cols[0].metric("내국인 개인 BC 이용금액", compact_won(amount) if pd.notna(amount) else "자료 없음")
    cols[1].metric("내국인 개인 BC 이용건수", f"{count:,.0f}건" if pd.notna(count) else "자료 없음")
    cols[2].metric("내국인 개인 건당 결제액", f"{ticket:,.0f}원" if pd.notna(ticket) else "자료 없음")
    cols[3].metric("1월 → 6월 금액 변화", f"{rate:+.1%}" if pd.notna(rate) else "자료 없음")
    st.caption(f"2026년 1~6월 · {int(observed)}/6개월 관측 · 합계는 관측된 월의 값입니다. 전체 업종은 분석 대상 9개 업종입니다.")
    target = st.radio("비교 지표", ["amt", "cnt"], format_func=lambda value: "이용금액" if value == "amt" else "이용건수", horizontal=True, key="comparison_target")
    st.plotly_chart(prediction_trend(monthly, target), width="stretch", key="personal_prediction_trend")
    st.caption("기대선은 지역 구조를 고려한 구간 중심입니다. 진단 비율·차이는 JSON의 반복 평균 기대값을 사용하므로 구간 중심과 다를 수 있습니다. 이 구간은 같은 월 지역 간 진단용이며 미래 매출 예측이 아닙니다.")
    messages = monthly["band_message"].dropna().unique()
    for message in messages:
        st.info(message)
    if monthly[["calibration_ok_amt", "calibration_ok_cnt"]].eq(False).any().any():
        st.caption("보정 주의: 일부 비교집단에서 조건부 정확도가 확인되지 않았습니다. 월별 툴팁을 함께 확인하세요.")
    scope = monthly.iloc[0]["scope"]
    status = region["region_status"]
    types = {"F1_food_wide_low": "외식 전반 저조형", "F2_industry_specific_low": "특정 업종 저조형"}
    if status["is_final_candidate"]:
        labels = [types.get(value, value) for value in status["candidate_types"]]
        st.warning("내국인 개인 소비 기준 지역 진단: " + " · ".join(labels) + " (외식업종에 대한 기존 최종 판정)")
    else:
        st.info("내국인 개인 소비 기준에서 최종 문제지역 신호가 확인되지 않았습니다. 문제가 없다는 판정은 아닙니다.")
    selected = [row for row in region["industry_signals"] if row["scope"] == scope]
    if selected:
        signal = selected[0]
        if signal.get("amount_count_ticket_path"):
            st.caption("선택 업종의 금액·건수·건당금액 경로: " + signal["amount_count_ticket_path"])
        if signal.get("model_warning"):
            st.caption(signal["model_warning"])
        if not signal.get("is_final_signal"):
            st.caption("선택 업종의 독립적인 최종 저조 신호는 확인되지 않았습니다.")
    with st.expander("월별 실제·기대·구간 및 거래 경로"):
        cols = ["month", "actual_amt", "expected_amt", "ratio_amt", "gap_amt", "actual_cnt", "expected_cnt", "ratio_cnt", "gap_cnt", "actual_ticket", "expected_ticket", "ticket_ratio", "mom_amt", "mom_cnt", "lower90_amt", "upper90_amt", "below90_amt", "above90_amt", "lower90_cnt", "upper90_cnt", "below90_cnt", "above90_cnt", "amount_count_ticket_path"]
        names = {"month": "월", "actual_amt": "개인 실제금액", "expected_amt": "진단 기대금액", "ratio_amt": "금액 실제/기대", "gap_amt": "금액 실제−기대", "actual_cnt": "개인 실제건수", "expected_cnt": "진단 기대건수", "ratio_cnt": "건수 실제/기대", "gap_cnt": "건수 실제−기대", "actual_ticket": "실제 건당금액", "expected_ticket": "기대 건당금액", "ticket_ratio": "건당금액 실제/기대", "mom_amt": "금액 전월비", "mom_cnt": "건수 전월비", "lower90_amt": "금액 90% 하한", "upper90_amt": "금액 90% 상한", "below90_amt": "금액 하단 이탈", "above90_amt": "금액 상단 이탈", "lower90_cnt": "건수 90% 하한", "upper90_cnt": "건수 90% 상한", "below90_cnt": "건수 하단 이탈", "above90_cnt": "건수 상단 이탈", "amount_count_ticket_path": "금액·건수·건당금액 경로"}
        table = detail[cols].rename(columns=names)
        table["월"] = table["월"].dt.strftime("%Y-%m")
        st.dataframe(table, hide_index=True, width="stretch", column_config={name: st.column_config.NumberColumn(format="%.1%%") for name in ["금액 실제/기대", "건수 실제/기대", "건당금액 실제/기대", "금액 전월비", "건수 전월비"]})
        st.caption("미관측 월은 빈 값입니다. 하단·상단 이탈은 구간과의 비교이며, 월별 이탈만으로 최종 과소·과대 소비나 정책 문제를 판정하지 않습니다.")
    st.caption(region["interpretation_boundary"] if isinstance(region["interpretation_boundary"], str) else " · ".join(region["interpretation_boundary"]))
