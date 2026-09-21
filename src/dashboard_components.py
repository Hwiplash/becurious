from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from src.data import compact_won
from src.period_change import format_change, jan_jun_change


def selected_map_value(event) -> str | None:
    try:
        points = event.selection.points
        custom = points[0].get("customdata") if points else None
        return custom[0] if custom else (points[0].get("location") if points else None)
    except (AttributeError, IndexError, TypeError):
        return None


def selected_table_value(event, frame: pd.DataFrame, column: str) -> str | None:
    try:
        rows = event.selection.rows
        return str(frame.iloc[rows[0]][column]) if rows else None
    except (AttributeError, IndexError, TypeError):
        return None


def growth(series: pd.Series) -> float | None:
    return jan_jun_change(series)


def summary_metrics(frame: pd.DataFrame, change_allowed: bool = True) -> tuple[float, float, float, float | None]:
    amount, count = float(frame["amt"].sum()), float(frame["cnt"].sum())
    change = growth(frame.groupby("month")["amt"].sum()) if change_allowed else None
    return amount, count, amount / count if count else 0, change


def signal_items(frame: pd.DataFrame, index_context: dict | None = None, change_allowed: bool = True) -> tuple[list[str], list[str]]:
    _, _, _, sales_growth = summary_metrics(frame, change_allowed)
    count_growth = growth(frame.groupby("month")["cnt"].sum()) if change_allowed else None
    monthly = frame.groupby("month").agg(amt=("amt", "sum"), cnt=("cnt", "sum"))
    ticket_growth = growth(monthly["amt"].div(monthly["cnt"].replace(0, pd.NA))) if change_allowed else None
    changes = [(str(name), rate) for name, group in frame.groupby("TP_BUZ_NM")
               if (rate := growth(group.groupby("month")["amt"].sum())) is not None]
    changes.sort(key=lambda item: item[1])
    strengths, weaknesses = [], []
    if sales_growth is not None:
        (strengths if sales_growth >= 0 else weaknesses).append(f"1월→6월 이용금액이 {sales_growth:+.1%} {'증가했습니다.' if sales_growth >= 0 else '감소했습니다.'}")
    if count_growth is not None:
        (strengths if count_growth >= 0 else weaknesses).append(f"1월→6월 이용 건수가 {count_growth:+.1%} {'늘었습니다.' if count_growth >= 0 else '줄었습니다.'}")
    if ticket_growth is not None:
        (strengths if ticket_growth >= 0 else weaknesses).append(f"1월→6월 건당 결제액이 {ticket_growth:+.1%} {'상승했습니다.' if ticket_growth >= 0 else '낮아졌습니다.'}")
    if len(changes) > 1 and change_allowed:
        strengths.append(f"성장 신호가 가장 큰 업종은 {changes[-1][0]}({changes[-1][1]:+.1%})입니다.")
        weaknesses.append(f"회복이 가장 필요한 업종은 {changes[0][0]}({changes[0][1]:+.1%})입니다.")
    if index_context:
        comparisons = [
            ("소비 프리미엄", index_context.get("premium")),
            ("거래활력", index_context.get("activity")),
            ("업종다양성", index_context.get("diversity")),
            ("주민 소비강도", index_context.get("population_intensity")),
        ]
        for label, value in comparisons:
            if value is None or pd.isna(value):
                continue
            target = strengths if value >= 100 else weaknesses
            target.append(f"{label}지수는 {value:.1f}로 전국 기준 100보다 {'높습니다.' if value >= 100 else '낮습니다.'}")
    return strengths[:4], weaknesses[:4]


def render_signals(frame: pd.DataFrame, index_context: dict | None = None, change_allowed: bool = True) -> None:
    strengths, weaknesses = signal_items(frame, index_context, change_allowed)
    if not change_allowed:
        st.caption("1월·6월의 관측 업종 구성이 달라 합계 변화율과 업종 간 변화 순위를 계산하지 않았습니다.")
    listing = lambda items: "".join(f"<li>{html.escape(item)}</li>" for item in items) or "<li>뚜렷한 신호가 없습니다.</li>"
    st.markdown(f"<div class='signal-grid'><div class='signal-card strength'><div class='signal-title'>↗ Strength</div><ul>{listing(strengths)}</ul></div><div class='signal-card weakness'><div class='signal-title'>↘ Weakness</div><ul>{listing(weaknesses)}</ul></div></div>", unsafe_allow_html=True)


def render_metrics(frame: pd.DataFrame, population_label: str = "전체 BC", change_allowed: bool = True) -> None:
    amount, count, ticket, rate = summary_metrics(frame, change_allowed)
    cols = st.columns(4)
    cols[0].metric(f"{population_label} 이용금액", compact_won(amount))
    cols[1].metric(f"{population_label} 이용건수", f"{count:,.0f}건")
    cols[2].metric("건당 결제", f"{ticket:,.0f}원")
    cols[3].metric("1월 → 6월 변화", format_change(rate))


def region_industry_filter(industries: list[str]) -> str:
    options = ["업종 전체", *industries]
    if st.session_state.get("region_industry_filter") not in options:
        st.session_state.region_industry_filter = "업종 전체"
    st.markdown("<div class='region-filter-label'>조회할 업종</div>", unsafe_allow_html=True)
    _, center, _ = st.columns([1.35, 1, 1.35])
    with center:
        return st.selectbox("지역별 업종 선택", options, key="region_industry_filter", label_visibility="collapsed")


def filter_industry(frame: pd.DataFrame, industry: str) -> pd.DataFrame:
    return frame if industry == "업종 전체" else frame[frame["TP_BUZ_NM"] == industry]


def go_to(view: str, sido: str | None = None, ccg: str | None = None) -> None:
    st.session_state.region_view = view
    if sido is not None:
        st.session_state.selected_sido = sido
    if ccg is not None:
        st.session_state.selected_ccg = ccg
    st.session_state["_scroll_top"] = True
    st.rerun()


def render_disclaimer() -> None:
    st.caption("2026년 1~6월 BC 이용금액·이용건수의 상대 비교입니다. 전체 카드시장이나 지역 실제 총매출을 뜻하지 않습니다. 연령·성별 구성은 내국인 개인 기준입니다.")


def index_snapshot(indices: dict[str, pd.DataFrame], sido: str, ccg: str | None = None, industry: str | None = None) -> dict:
    base = indices["지역지수"]
    premium = indices["프리미엄"]
    population = indices["인구보정"]
    rank = indices["지역순위"]
    selector = base["시도"].eq(sido)
    if ccg is not None:
        selector &= base["시군구"].eq(ccg)
    base_rows = base[selector]
    premium_rows = premium[premium["시도"].eq(sido) & (premium["시군구"].eq(ccg) if ccg else True)]
    population_rows = population[population["시도"].eq(sido) & (population["시군구"].eq(ccg) if ccg else True)]
    rank_rows = rank[rank["시도"].eq(sido) & (rank["시군구"].eq(ccg) if ccg else True)]
    result = {
        "selected_industry": industry,
        "scale": base_rows["결제금액 규모지수"].median() if not base_rows.empty else None,
        "activity": base_rows["거래활력지수"].median() if not base_rows.empty else None,
        "diversity": base_rows["업종다양성지수"].median() if not base_rows.empty else None,
        "premium": premium_rows["6개월 통합 프리미엄지수"].median() if not premium_rows.empty else None,
        "population_intensity": population_rows["개인 금액 지수(평균=100)"].median() if not population_rows.empty else None,
        "transaction_intensity": population_rows["개인 건수 지수(평균=100)"].median() if not population_rows.empty else None,
        "market_type": premium_rows.iloc[0]["규모·프리미엄 유형"] if ccg and not premium_rows.empty else None,
        "top_industry": base_rows.iloc[0]["최대 업종"] if ccg and not base_rows.empty else None,
        "top_industry_share": base_rows.iloc[0]["최대 업종 금액비중"] if ccg and not base_rows.empty else None,
        "national_rank": rank_rows.iloc[0]["전체매출 전국순위"] if ccg and not rank_rows.empty else None,
        "metro_rank": rank_rows.iloc[0]["전체매출 광역순위"] if ccg and not rank_rows.empty else None,
    }
    if ccg and industry and industry != "업종 전체":
        industry_rows = indices["업종순위"]
        industry_rows = industry_rows[(industry_rows["시도"] == sido) & (industry_rows["업종"] == industry) & (industry_rows["시군구"] == ccg)]
        if not industry_rows.empty:
            row = industry_rows.iloc[0]
            result.update({"industry_national_rank": row["전국 동일업종 지역순위"], "industry_metro_rank": row["광역 동일업종 지역순위"]})
    return result


def render_index_cards(context: dict, regional: bool = False) -> None:
    st.markdown("<div class='section-kicker'>COMMERCIAL VITALITY INDEX</div><div class='section-title'>상권 체력 지수</div>", unsafe_allow_html=True)
    note = "해당 시도 내 시군구 중앙값 · 전국 기준 100" if regional else "선택한 시군구 지수 · 전국 기준 100"
    st.markdown(f"<div class='index-note'>{note}</div>", unsafe_allow_html=True)
    st.caption("워크북 규모·거래·프리미엄·다양성 지수는 전체 고객코드, 인구보정 지표는 내국인 개인 기준입니다.")
    if context.get("selected_industry") not in (None, "업종 전체"):
        st.caption(f"상권 체력 지수는 지역 전체 기준이며, 아래 상세 정보에 {context['selected_industry']} 동일 업종 순위를 함께 표시합니다.")
    descriptions = {
        "scale": "결제금액 규모를 전국 시군구와 비교한 지수입니다. 100은 전국 기준 수준이며, 높을수록 관측된 소비시장 규모가 큽니다.",
        "activity": "결제 건수를 바탕으로 소비 활동의 빈도와 활발함을 비교한 지수입니다. 100보다 높으면 전국 기준보다 거래가 활발합니다.",
        "premium": "거래량과 업종 구조를 고려한 기대 건당결제액 대비 실제 결제 수준입니다. 100보다 높으면 상대적으로 고액 소비 성향이 강합니다.",
        "diversity": "매출이 여러 업종에 얼마나 고르게 분포하는지 나타냅니다. 100보다 높으면 업종 구성이 비교적 다양하고, 낮으면 특정 업종 의존도가 높습니다.",
        "population_intensity": "내국인 개인 BC 이용금액을 주민등록인구로 나눈 상대 지수입니다. 소비자의 거주지가 해당 지역이라는 뜻은 아닙니다.",
        "transaction_intensity": "내국인 개인 BC 이용건수를 주민등록인구로 나눈 상대 지수입니다. 소비자의 거주지나 고유 고객 수를 뜻하지 않습니다.",
    }
    cards = [("결제규모", "scale"), ("거래활력", "activity"), ("소비 프리미엄", "premium"), ("업종다양성", "diversity"), ("개인 인구보정 금액", "population_intensity"), ("개인 인구보정 건수", "transaction_intensity")]
    card_html = []
    for label, key in cards:
        value = context.get(key)
        display = f"{value:.1f}" if value is not None and not pd.isna(value) else "-"
        card_html.append(f"<div class='index-card'><div class='index-card-label'>{html.escape(label)}</div><div class='index-card-value'>{display}</div><div class='info-wrap' tabindex='0'>i<div class='index-tooltip'>{html.escape(descriptions[key])}</div></div></div>")
    st.markdown(f"<div class='index-grid'>{''.join(card_html)}</div>", unsafe_allow_html=True)
    details = []
    if context.get("market_type"):
        details.append(f"상권 유형 **{context['market_type']}**")
    if context.get("top_industry"):
        details.append(f"최대 매출 업종 **{context['top_industry']}** ({context['top_industry_share']:.1%})")
    if context.get("national_rank") is not None:
        details.append(f"전체 매출 전국 **{int(context['national_rank'])}위**, 광역 **{int(context['metro_rank'])}위**")
    if context.get("industry_national_rank") is not None:
        details.append(f"선택 업종 매출 전국 **{int(context['industry_national_rank'])}위**, 광역 **{int(context['industry_metro_rank'])}위**")
    if details:
        st.info(" · ".join(details))


def chart_label(text: str) -> None:
    st.markdown(f"<div class='chart-label'>{html.escape(text)}</div>", unsafe_allow_html=True)


def industry_picker(industries: list[str]) -> str:
    options = ["업종 전체", *industries]
    if st.session_state.get("selected_industry") not in options:
        st.session_state.selected_industry = "업종 전체"
    st.markdown("<div class='industry-grid'>", unsafe_allow_html=True)
    for start in range(0, len(options), 4):
        columns = st.columns(4, gap="small")
        for column, option in zip(columns, options[start:start + 4]):
            with column:
                selected = st.session_state.selected_industry == option
                if st.button(option, key=f"industry_pick_{option}", type="primary" if selected else "secondary", width="stretch"):
                    st.session_state.selected_industry = option
                    st.session_state["_scroll_top"] = True
                    st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    return st.session_state.selected_industry
