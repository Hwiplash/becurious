from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from src.data import compact_won


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


def growth(series: pd.Series) -> float:
    series = series.sort_index()
    return float(series.iloc[-1] / series.iloc[0] - 1) if len(series) > 1 and series.iloc[0] else 0.0


def summary_metrics(frame: pd.DataFrame) -> tuple[float, float, float, float]:
    amount, count = float(frame["amt"].sum()), float(frame["cnt"].sum())
    return amount, count, amount / count if count else 0, growth(frame.groupby("month")["amt"].sum())


def signal_items(frame: pd.DataFrame, index_context: dict | None = None) -> tuple[list[str], list[str]]:
    _, _, _, sales_growth = summary_metrics(frame)
    count_growth = growth(frame.groupby("month")["cnt"].sum())
    monthly = frame.groupby("month").agg(amt=("amt", "sum"), cnt=("cnt", "sum"))
    ticket_growth = growth(monthly["amt"].div(monthly["cnt"].replace(0, pd.NA)).fillna(0))
    changes = sorted((str(name), growth(group.groupby("month")["amt"].sum())) for name, group in frame.groupby("TP_BUZ_NM"))
    changes.sort(key=lambda item: item[1])
    strengths, weaknesses = [], []
    index_strengths: list[str] = []
    index_weaknesses: list[str] = []
    (strengths if sales_growth >= 0 else weaknesses).append(
        f"기간 매출이 {sales_growth:+.1%} 늘어 업종 소비 규모가 확대되는 흐름입니다."
        if sales_growth >= 0 else f"기간 매출이 {abs(sales_growth):.1%} 줄어 업종 소비 규모의 회복이 필요합니다."
    )
    (strengths if count_growth >= 0 else weaknesses).append(
        f"이용 건수가 {count_growth:+.1%} 늘어 고객의 결제 활동이 활발해지는 흐름입니다."
        if count_growth >= 0 else f"이용 건수가 {abs(count_growth):.1%} 줄어 고객 유입과 재이용을 높일 필요가 있습니다."
    )
    (strengths if ticket_growth >= 0 else weaknesses).append(
        f"건당 결제액이 {ticket_growth:+.1%} 올라 한 번의 결제에서 지출하는 규모가 커졌습니다."
        if ticket_growth >= 0 else f"건당 결제액이 {abs(ticket_growth):.1%} 낮아져 세트 구성과 추가 구매 유도 전략을 점검할 필요가 있습니다."
    )
    if len(changes) > 1:
        strengths.append(f"비교 업종 중 {changes[-1][0]}에서 {changes[-1][1]:+.1%}로 가장 뚜렷한 성장 흐름이 나타납니다.")
        weaknesses.append(f"비교 업종 중 {changes[0][0]}은 {changes[0][1]:+.1%}로 상대적으로 회복 필요성이 가장 큽니다.")
    if index_context:
        scale, activity = index_context.get("scale"), index_context.get("activity")
        if scale is not None and activity is not None and not pd.isna(scale) and not pd.isna(activity):
            if scale >= 100 and activity >= 100:
                index_strengths.append(f"결제규모 {scale:.1f}, 거래활력 {activity:.1f}로 기준 100을 함께 웃돌아 안정적인 고객 수요 기반을 갖추고 있습니다.")
            elif scale < 100 and activity < 100:
                index_weaknesses.append(f"결제규모 {scale:.1f}, 거래활력 {activity:.1f}로 기준 100보다 낮아 신규 고객 유입과 재이용 회복이 함께 필요합니다.")
            elif scale >= 100:
                index_strengths.append(f"결제규모는 {scale:.1f}로 기준보다 크고 거래활력은 {activity:.1f}로 낮아 기존 고객의 재이용을 늘릴 여지가 있습니다.")
            else:
                index_weaknesses.append(f"거래활력은 {activity:.1f}로 기준보다 높지만 결제규모는 {scale:.1f}로 낮아 세트·추가 구매로 소비 규모를 키울 여지가 있습니다.")
        comparisons = [
            ("소비 프리미엄", index_context.get("premium"), "상대적으로 고액 소비 성향이 강합니다.", "기대 수준보다 결제 규모가 낮아 상품 구성과 부가 구매를 점검할 필요가 있습니다."),
            ("업종다양성", index_context.get("diversity"), "업종 구성이 비교적 고르게 분산돼 있습니다.", "특정 업종 의존도가 높아 수요 변화에 취약할 수 있습니다."),
            ("주민 소비강도", index_context.get("population_intensity"), "인구 규모를 고려해도 지역 내 소비가 활발합니다.", "인구 규모에 비해 소비금액이 낮아 지역 수요를 붙잡을 전략이 필요합니다."),
            ("주민 거래강도", index_context.get("transaction_intensity"), "주민 수에 비해 거래가 활발해 생활권 수요가 탄탄합니다.", "주민 수에 비해 거래가 적어 생활권 고객의 이용 빈도를 높일 필요가 있습니다."),
        ]
        if scale is None or activity is None or pd.isna(scale) or pd.isna(activity):
            comparisons.insert(0, ("거래활력", activity, "거래가 비교적 활발해 고객 접점이 충분합니다.", "거래 빈도가 낮아 고객 유입과 재이용 회복이 필요합니다."))
        for label, value, high_text, low_text in comparisons:
            if value is None or pd.isna(value):
                continue
            target = index_strengths if value >= 100 else index_weaknesses
            target.append(f"{label}은 {value:.1f}로 기준 100과 비교하면 {high_text if value >= 100 else low_text}")
    return [*index_strengths, *strengths][:5], [*index_weaknesses, *weaknesses][:5]


def render_signals(frame: pd.DataFrame, index_context: dict | None = None) -> None:
    strengths, weaknesses = signal_items(frame, index_context)
    listing = lambda items: "".join(f"<li>{html.escape(item)}</li>" for item in items) or "<li>뚜렷한 신호가 없습니다.</li>"
    st.markdown(f"<div class='signal-grid'><div class='signal-card strength'><div class='signal-title'>↗ Strength</div><ul>{listing(strengths)}</ul></div><div class='signal-card weakness'><div class='signal-title'>↘ Weakness</div><ul>{listing(weaknesses)}</ul></div></div>", unsafe_allow_html=True)


def render_metrics(frame: pd.DataFrame) -> None:
    amount, count, ticket, rate = summary_metrics(frame)
    cols = st.columns(4)
    cols[0].metric("총 매출", compact_won(amount))
    cols[1].metric("이용 건수", f"{count:,.0f}건")
    cols[2].metric("건당 결제", f"{ticket:,.0f}원")
    cols[3].metric("1월 → 6월 변화", f"{rate:+.1%}")


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
    st.caption("BC카드 관측 소비를 기반으로 한 상대 비교이며, 2026년 1월에서 6월까지의 변화를 표시합니다.")


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


def industry_index_snapshot(data: pd.DataFrame, industry: str) -> dict:
    """선택 업종의 전국 실적을 외식 업종 평균(100)과 비교한다."""
    grouped = data.groupby("TP_BUZ_NM").agg(amt=("amt", "sum"), cnt=("cnt", "sum"))
    grouped["ticket"] = grouped["amt"].div(grouped["cnt"].replace(0, pd.NA))
    if industry not in grouped.index or grouped.empty:
        return {"selected_industry": industry, "scope": "industry"}
    row = grouped.loc[industry]

    def relative(value: float, benchmark: float) -> float | None:
        return float(value / benchmark * 100) if benchmark and not pd.isna(benchmark) else None

    return {
        "selected_industry": industry,
        "scope": "industry",
        "scale": relative(row["amt"], grouped["amt"].mean()),
        "activity": relative(row["cnt"], grouped["cnt"].mean()),
        "premium": relative(row["ticket"], grouped["ticket"].mean()),
        "diversity": None,
        "population_intensity": None,
        "transaction_intensity": None,
    }


def render_index_cards(context: dict, regional: bool = False) -> None:
    st.markdown("<div class='section-kicker'>COMMERCIAL VITALITY INDEX</div><div class='section-title'>상권 체력 지수</div>", unsafe_allow_html=True)
    if context.get("scope") == "industry":
        note = "선택 업종의 전국 실적 · 외식 업종 평균 100"
    else:
        note = "해당 시도 내 시군구 중앙값 · 전국 기준 100" if regional else "선택한 시군구 지수 · 전국 기준 100"
    st.markdown(f"<div class='index-note'>{note}</div>", unsafe_allow_html=True)
    if context.get("selected_industry") not in (None, "업종 전체") and context.get("scope") != "industry":
        st.caption(f"상권 체력 지수는 지역 전체 기준이며, 아래 상세 정보에 {context['selected_industry']} 동일 업종 순위를 함께 표시합니다.")
    descriptions = {
        "scale": "결제금액 규모를 전국 시군구와 비교한 지수입니다. 100은 전국 기준 수준이며, 높을수록 관측된 소비시장 규모가 큽니다.",
        "activity": "결제 건수를 바탕으로 소비 활동의 빈도와 활발함을 비교한 지수입니다. 100보다 높으면 전국 기준보다 거래가 활발합니다.",
        "premium": "거래량과 업종 구조를 고려한 기대 건당결제액 대비 실제 결제 수준입니다. 100보다 높으면 상대적으로 고액 소비 성향이 강합니다.",
        "diversity": "매출이 여러 업종에 얼마나 고르게 분포하는지 나타냅니다. 100보다 높으면 업종 구성이 비교적 다양하고, 낮으면 특정 업종 의존도가 높습니다.",
        "population_intensity": "주민등록인구 1인당 개인 BC 결제금액을 전국 시군구와 비교한 지수입니다. 100보다 높으면 주민 수를 고려해도 소비금액이 전국 기준보다 큽니다.",
        "transaction_intensity": "주민등록인구 1인당 개인 BC 결제건수를 전국 시군구와 비교한 지수입니다. 100보다 높으면 주민 수 대비 거래 빈도가 전국 기준보다 높습니다.",
    }
    if context.get("scope") == "industry":
        descriptions.update({
            "scale": "선택 업종의 전국 결제금액을 외식 업종별 평균과 비교합니다. 100보다 높으면 평균 업종보다 소비시장 규모가 큽니다.",
            "activity": "선택 업종의 전국 결제건수를 외식 업종별 평균과 비교합니다. 100보다 높으면 평균 업종보다 거래가 활발합니다.",
            "premium": "선택 업종의 건당결제액을 외식 업종별 평균과 비교합니다. 100보다 높으면 한 번의 결제에서 지출하는 규모가 상대적으로 큽니다.",
        })
    cards = [("결제규모", "scale"), ("거래활력", "activity"), ("소비 프리미엄", "premium"), ("업종다양성", "diversity"), ("주민 소비강도", "population_intensity"), ("주민 거래강도", "transaction_intensity")]
    cards = [(label, key) for label, key in cards if context.get(key) is not None and not pd.isna(context.get(key))]
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
