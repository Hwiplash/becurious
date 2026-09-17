from __future__ import annotations

import pandas as pd
import streamlit as st

from src.charts import industry_bar, intensity_compare, monthly_trend, premium_quadrant, regional_ranking, segment_chart
from src.data import compact_won, default_data_path, default_indices_path, load_csv, load_indices
from src.maps import index_map, sido_map, sigungu_map

st.set_page_config(page_title="ABP 상권 인사이트", page_icon="◈", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 80% 0%,#E8FBF5 0,#F7F9FC 38%,#F3F6FA 100%)}
[data-testid="stSidebar"]{display:none}.hero{padding:.4rem 0 1rem}.eyebrow{color:#0E9F7D;font-size:.78rem;font-weight:700;letter-spacing:.16em}
.hero h1{font-size:2.25rem;margin:.3rem 0;color:#172033}.hero p{color:#667085;margin:0}
[data-testid="stMetric"]{background:rgba(255,255,255,.94);border:1px solid #E4EAF1;box-shadow:0 6px 20px rgba(23,32,51,.05);padding:1rem 1.1rem;border-radius:14px}
[data-testid="stMetricValue"]{font-size:1.55rem}.section-label{font-size:.78rem;color:#0E9F7D;font-weight:700;letter-spacing:.12em;margin-top:.5rem}
div[data-testid="stVerticalBlockBorderWrapper"]{background:rgba(255,255,255,.92);border-color:#E4EAF1!important;box-shadow:0 6px 20px rgba(23,32,51,.04)}
div[data-testid="stPlotlyChart"]{background:rgba(255,255,255,.94);border:1px solid #E4EAF1;border-radius:16px;padding:4px}.stDataFrame{border:1px solid #E4EAF1;border-radius:12px;overflow:hidden}
</style>
""", unsafe_allow_html=True)


def metric_value(row: pd.Series, name: str) -> str:
    return f"{row[name]:,.1f}" if pd.notna(row[name]) else "-"


def selected_sido(event) -> str | None:
    try:
        points = event.selection.points
        if not points:
            return None
        custom = points[0].get("customdata")
        return custom[0] if custom else points[0].get("location")
    except (AttributeError, IndexError, TypeError):
        return None


try:
    raw_path, index_path = default_data_path(), default_indices_path()
    if raw_path is None:
        st.error("ABP_CONTEST_DATA.csv를 data/raw 또는 프로젝트 상위 폴더에 배치해주세요."); st.stop()
    if index_path is None:
        st.error("regional_indices_rank_final_v2_20260913.xlsx를 data/raw 또는 프로젝트 상위 폴더에 배치해주세요."); st.stop()
    data = load_csv(str(raw_path.resolve()))
    indices = load_indices(str(index_path.resolve()))
except Exception as exc:
    st.error(f"데이터를 읽지 못했습니다: {exc}"); st.stop()

st.markdown("<div class='hero'><div class='eyebrow'>AI FINANCIAL BIG DATA PLATFORM</div><h1>대한민국 소비 상권 인사이트</h1><p>소비 규모에서 인구보정·업종 경쟁력까지 지역 상권을 입체적으로 탐색하세요.</p></div>", unsafe_allow_html=True)
mode = st.radio("분석 모드", ["소비 현황", "상권 종합지수", "인구보정", "업종 순위"], horizontal=True, label_visibility="collapsed")

if mode == "소비 현황":
    min_month, max_month = data["month"].min(), data["month"].max()
    available_months = sorted(data["month"].unique())
    st.markdown("<div class='section-label'>ANALYSIS FILTERS</div>", unsafe_allow_html=True)
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.35, 1.2, 1, 1])
        with c1: month_range = st.select_slider("기간", options=available_months, value=(available_months[0], available_months[-1]), format_func=lambda x: pd.Timestamp(x).strftime("%Y.%m"))
        with c2: industry = st.multiselect("업종", sorted(data["TP_BUZ_NM"].unique()), placeholder="전체 업종")
        with c3: genders = st.multiselect("성별", [x for x in ["남성", "여성", "외국인", "미상", "기타"] if x in set(data["gender"])], placeholder="전체 성별")
        with c4: ages = st.multiselect("연령", [x for x in ["20대 이하", "20대", "30대", "40대", "50대", "60대 이상", "미상", "기타"] if x in set(data["age"])], placeholder="전체 연령")
        st.caption(f"원천 데이터 · {raw_path.name} · {len(data):,}행 · {min_month:%Y.%m}–{max_month:%Y.%m}")
    filtered = data[data["month"].between(pd.Timestamp(month_range[0]), pd.Timestamp(month_range[1]))]
    if industry: filtered = filtered[filtered["TP_BUZ_NM"].isin(industry)]
    if genders: filtered = filtered[filtered["gender"].isin(genders)]
    if ages: filtered = filtered[filtered["age"].isin(ages)]
    if filtered.empty: st.warning("선택한 조건에 해당하는 데이터가 없습니다."); st.stop()
    total_amt, total_cnt = filtered["amt"].sum(), filtered["cnt"].sum()
    monthly = filtered.groupby("month")["amt"].sum().sort_index()
    growth = (monthly.iloc[-1] / monthly.iloc[0] - 1) if len(monthly) > 1 and monthly.iloc[0] else 0
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("총 매출액", compact_won(total_amt)); k2.metric("이용 건수", f"{total_cnt:,.0f}건")
    k3.metric("건당 결제액", compact_won(total_amt / total_cnt if total_cnt else 0)); k4.metric("기간 성장률", f"{growth:+.1%}")
    if "sales_page" not in st.session_state:
        st.session_state.sales_page = "national"

    if st.session_state.sales_page == "national":
        st.markdown("<div class='section-label'>NATIONAL OVERVIEW</div>", unsafe_allow_html=True)
        national_map_col, national_rank_col = st.columns([1.18, .82], gap="large")
        with national_map_col:
            st.subheader("전국 매출 지도")
            st.caption("시도를 클릭하면 해당 지역의 시군구 분석으로 이동합니다.")
            map_event = st.plotly_chart(sido_map(filtered), width="stretch", on_select="rerun", key="sales_national_map")
        with national_rank_col:
            st.subheader("시도 비교")
            sido_ranking = regional_ranking(filtered, "SIDO_NM")
            st.dataframe(sido_ranking, hide_index=True, width="stretch", height=590, column_config={"SIDO_NM": "시도", "매출액": st.column_config.NumberColumn(format="%,.0f원"), "이용건수": st.column_config.NumberColumn(format="%,.0f건"), "건당결제액": st.column_config.NumberColumn(format="%,.0f원"), "매출비중": st.column_config.ProgressColumn(format="%.1%%", min_value=0, max_value=1)})
        clicked = selected_sido(map_event)
        if clicked in set(filtered["SIDO_NM"]):
            st.session_state.sales_selected_sido = clicked
            st.session_state.sales_page = "regional"
            st.rerun()
    elif st.session_state.sales_page == "regional":
        sido_options = sorted(filtered["SIDO_NM"].unique())
        saved_sido = st.session_state.get("sales_selected_sido", sido_options[0])
        if saved_sido not in sido_options:
            saved_sido = sido_options[0]
        nav_col, select_col = st.columns([.7, 2.3])
        with nav_col:
            if st.button("← 전국 지도로", width="stretch"):
                st.session_state.sales_page = "national"
                st.rerun()
        with select_col:
            sido = st.selectbox("분석 지역", sido_options, index=sido_options.index(saved_sido), key="sales_region_select")
        if sido != st.session_state.get("sales_selected_sido"):
            st.session_state.pop("sales_selected_ccg", None)
        st.session_state.sales_selected_sido = sido
        sido_df = filtered[filtered["SIDO_NM"] == sido]
        ranking = regional_ranking(sido_df, "CCG_NM")
        st.markdown(f"<div class='section-label'>REGIONAL DETAIL</div>", unsafe_allow_html=True)
        st.header(f"{sido} 소비 상권")
        local_map_col, ranking_col = st.columns([1.12, .88], gap="large")
        with local_map_col:
            st.subheader("시군구 매출 지도")
            st.caption("시군구를 클릭하면 해당 지역의 상세 분석으로 이동합니다.")
            local_event = st.plotly_chart(sigungu_map(sido_df, sido), width="stretch", on_select="rerun", key=f"sales_local_{sido}")
        with ranking_col:
            st.subheader("시군구 비교")
            st.dataframe(ranking, hide_index=True, width="stretch", height=590, column_config={"CCG_NM": "시군구", "매출액": st.column_config.NumberColumn(format="%,.0f원"), "이용건수": st.column_config.NumberColumn(format="%,.0f건"), "건당결제액": st.column_config.NumberColumn(format="%,.0f원"), "매출비중": st.column_config.ProgressColumn(format="%.1%%", min_value=0, max_value=1)})
        clicked_ccg = selected_sido(local_event)
        if clicked_ccg in set(sido_df["CCG_NM"]):
            st.session_state.sales_selected_ccg = clicked_ccg
            st.session_state.sales_page = "local"
            st.rerun()
        st.markdown("<div class='section-label'>REGIONAL TRENDS</div>", unsafe_allow_html=True)
        st.subheader(f"{sido} 월별 추이")
        st.plotly_chart(monthly_trend(sido_df), width="stretch", key=f"regional_trend_{sido}")
        regional_industry, regional_segment = st.columns(2, gap="large")
        with regional_industry:
            st.subheader("업종별 매출 TOP 10")
            st.plotly_chart(industry_bar(sido_df), width="stretch", key=f"regional_industry_{sido}")
        with regional_segment:
            st.subheader("연령·성별 소비 구성")
            st.plotly_chart(segment_chart(sido_df), width="stretch", key=f"regional_segment_{sido}")
    else:
        sido_options = sorted(filtered["SIDO_NM"].unique())
        sido = st.session_state.get("sales_selected_sido", sido_options[0])
        if sido not in sido_options:
            sido = sido_options[0]
        sido_df = filtered[filtered["SIDO_NM"] == sido]
        ccg_options = sorted(sido_df["CCG_NM"].unique())
        ccg = st.session_state.get("sales_selected_ccg", ccg_options[0])
        if ccg not in ccg_options:
            ccg = ccg_options[0]
        back_national, back_region, select_col = st.columns([.62, .72, 1.66])
        with back_national:
            if st.button("← 전국", width="stretch"):
                st.session_state.sales_page = "national"
                st.rerun()
        with back_region:
            if st.button(f"← {sido}", width="stretch"):
                st.session_state.sales_page = "regional"
                st.rerun()
        with select_col:
            ccg = st.selectbox("시군구", ccg_options, index=ccg_options.index(ccg), key=f"sales_local_select_{sido}")
        st.session_state.sales_selected_ccg = ccg
        local_df = sido_df[sido_df["CCG_NM"] == ccg]
        local_amt, local_cnt = local_df["amt"].sum(), local_df["cnt"].sum()
        local_monthly = local_df.groupby("month")["amt"].sum().sort_index()
        local_growth = (local_monthly.iloc[-1] / local_monthly.iloc[0] - 1) if len(local_monthly) > 1 and local_monthly.iloc[0] else 0
        st.markdown("<div class='section-label'>LOCAL DETAIL</div>", unsafe_allow_html=True)
        st.header(f"{sido} {ccg}")
        l1, l2, l3, l4 = st.columns(4)
        l1.metric("매출액", compact_won(local_amt)); l2.metric("이용 건수", f"{local_cnt:,.0f}건")
        l3.metric("건당 결제액", compact_won(local_amt / local_cnt if local_cnt else 0)); l4.metric("기간 성장률", f"{local_growth:+.1%}")
        st.subheader("월별 추이")
        st.plotly_chart(monthly_trend(local_df), width="stretch")
        a, b = st.columns(2, gap="large")
        with a: st.subheader("업종별 매출 TOP 10"); st.plotly_chart(industry_bar(local_df), width="stretch")
        with b: st.subheader("연령·성별 소비 구성"); st.plotly_chart(segment_chart(local_df), width="stretch")

elif mode == "상권 종합지수":
    base, premium = indices["지역지수"], indices["프리미엄"]
    merged = base.merge(premium, on=["시도", "시군구"], suffixes=("", "_프리미엄"))
    metrics = {"결제금액 규모": "결제금액 규모지수", "거래활력": "거래활력지수", "소비 프리미엄": "6개월 통합 프리미엄지수", "업종다양성": "업종다양성지수"}
    st.markdown("<div class='section-label'>COMMERCIAL DISTRICT INDEX</div>", unsafe_allow_html=True)
    with st.container(border=True):
        f1, f2, f3 = st.columns([1, 1, 1.2]); metric_label = f1.selectbox("지도 지표", list(metrics)); sido = f2.selectbox("시도", sorted(merged["시도"].unique()), key="index_sido")
        ccg = f3.selectbox("시군구", sorted(merged.loc[merged["시도"] == sido, "시군구"].unique()), key="index_ccg")
        st.caption("모든 지수는 100을 기준으로 해석하되, 지표별 비교 기준은 서로 다릅니다.")
    metric = metrics[metric_label]; map_col, card_col = st.columns([1.2, .8], gap="large")
    with map_col: st.subheader(f"전국 {metric_label} 지수"); st.plotly_chart(index_map(merged, metric, metric_label), width="stretch", key=f"index_map_{metric}")
    row = merged[(merged["시도"] == sido) & (merged["시군구"] == ccg)].iloc[0]
    with card_col:
        st.subheader(f"{sido} {ccg}"); c1, c2 = st.columns(2); c1.metric("규모지수", metric_value(row, "결제금액 규모지수")); c2.metric("거래활력", metric_value(row, "거래활력지수"))
        c3, c4 = st.columns(2); c3.metric("소비 프리미엄", metric_value(row, "6개월 통합 프리미엄지수")); c4.metric("업종다양성", metric_value(row, "업종다양성지수"))
        st.info(f"**{row['규모·프리미엄 유형']}**\n\n최대 매출 업종: **{row['최대 업종']}** ({row['최대 업종 금액비중']:.1%})\n\n최대 프리미엄 업종: **{row['최대 프리미엄 업종']}** ({row['최대 업종 프리미엄지수']:.1f})")
    st.subheader("규모–프리미엄 포지셔닝"); st.plotly_chart(premium_quadrant(merged[merged["시도"] == sido], ccg), width="stretch")
    with st.expander("지수 해석 방법"):
        st.markdown("**규모·거래활력·업종다양성**은 지역 평균 또는 분포 기준입니다. **소비 프리미엄**은 거래건수를 고려한 예상 건당결제액 대비 수준입니다. 지수는 인과관계나 잠재매출을 의미하지 않습니다.")

elif mode == "인구보정":
    pop, groups = indices["인구보정"], indices["소비유형"]
    st.markdown("<div class='section-label'>POPULATION ADJUSTED · 2026.06</div>", unsafe_allow_html=True)
    with st.container(border=True):
        f1, f2, f3 = st.columns([1.1, 1, 1]); metric_choices = {"개인 소비금액 강도": "개인 금액 지수(평균=100)", "개인 거래건수 강도": "개인 건수 지수(평균=100)", "남성 소비강도": "남성 강도 지수", "여성 소비강도": "여성 강도 지수"}
        label = f1.selectbox("지도 지표", list(metric_choices)); sido = f2.selectbox("시도", sorted(pop["시도"].unique()), key="pop_sido"); ccg = f3.selectbox("시군구", sorted(pop.loc[pop["시도"] == sido, "시군구"].unique()), key="pop_ccg")
        st.caption("2026년 6월 주민등록인구 기준 단면 비교입니다. 외국인·법인은 인구 분모에 포함하지 않습니다.")
    metric = metric_choices[label]; map_col, detail_col = st.columns([1.15, .85], gap="large")
    with map_col: st.subheader(f"전국 {label}"); st.plotly_chart(index_map(pop, metric, label), width="stretch", key=f"pop_map_{metric}")
    row = pop[(pop["시도"] == sido) & (pop["시군구"] == ccg)].iloc[0]
    with detail_col:
        st.subheader(f"{sido} {ccg}"); c1, c2 = st.columns(2); c1.metric("주민 1인당 개인금액", compact_won(row["개인 금액/주민"])); c2.metric("주민 1인당 거래", f"{row['개인 건수/주민']:.2f}건")
        c3, c4 = st.columns(2); c3.metric("외국인 금액비중", f"{row['외국인 금액비중']:.1%}"); c4.metric("법인 금액비중", f"{row['법인 금액비중']:.1%}")
        st.plotly_chart(intensity_compare(row), width="stretch")
    local_groups = groups[(groups["시도"] == sido) & (groups["시군구"] == ccg)]
    st.subheader("먹거리·쇼핑 소비강도")
    st.dataframe(local_groups[["소비유형", "BC 금액", "BC 건수", "금액/주민등록인구", "금액/주민 지수(유형 평균=100)", "지역 내 금액비중"]], hide_index=True, width="stretch", column_config={"BC 금액": st.column_config.NumberColumn(format="%,.0f원"), "BC 건수": st.column_config.NumberColumn(format="%,.0f건"), "금액/주민등록인구": st.column_config.NumberColumn(format="%,.0f원"), "지역 내 금액비중": st.column_config.ProgressColumn(format="%.1%%", min_value=0, max_value=1)})

else:
    ranks = indices["업종순위"]
    st.markdown("<div class='section-label'>INDUSTRY COMPETITIVENESS · 2026.06</div>", unsafe_allow_html=True)
    with st.container(border=True):
        f1, f2, f3 = st.columns(3); sido = f1.selectbox("시도", sorted(ranks["시도"].unique()), key="rank_sido"); ccg = f2.selectbox("시군구", sorted(ranks.loc[ranks["시도"] == sido, "시군구"].unique()), key="rank_ccg")
        industry = f3.selectbox("업종", sorted(ranks[(ranks["시도"] == sido) & (ranks["시군구"] == ccg)]["업종"].unique()), key="rank_industry"); st.caption("2026년 6월 기준이며, 순위 1이 가장 높은 매출액을 의미합니다.")
    row = ranks[(ranks["시도"] == sido) & (ranks["시군구"] == ccg) & (ranks["업종"] == industry)].iloc[0]
    k1, k2, k3, k4 = st.columns(4); k1.metric("업종 매출액", compact_won(row["매출액"])); k2.metric("건당 결제", compact_won(row["건당결제"])); k3.metric("전국 동일업종 순위", f"{int(row['전국 동일업종 지역순위'])}위"); k4.metric("광역 동일업종 순위", f"{int(row['광역 동일업종 지역순위'])}위")
    st.success(f"{sido} {ccg}의 **{industry}**은 지역 내 {int(row['지역 내 업종순위'])}위, 전국 동일 업종 {int(row['전국 동일업종 지역순위'])}위, {sido} 내 {int(row['광역 동일업종 지역순위'])}위입니다.")
    local = ranks[(ranks["시도"] == sido) & (ranks["시군구"] == ccg)].sort_values("지역 내 업종순위"); national = ranks[ranks["업종"] == industry].nsmallest(15, "전국 동일업종 지역순위")
    left, right = st.columns(2, gap="large")
    with left: st.subheader(f"{ccg} 업종 구성"); st.dataframe(local[["업종", "매출액", "거래건수", "건당결제", "지역 내 업종순위"]], hide_index=True, width="stretch", column_config={"매출액": st.column_config.NumberColumn(format="%,.0f원"), "거래건수": st.column_config.NumberColumn(format="%,.0f건"), "건당결제": st.column_config.NumberColumn(format="%,.0f원")})
    with right: st.subheader(f"{industry} 전국 TOP 15"); st.dataframe(national[["시도", "시군구", "매출액", "전국 동일업종 지역순위"]], hide_index=True, width="stretch", column_config={"매출액": st.column_config.NumberColumn(format="%,.0f원")})

st.caption("※ BC카드 관측 소비와 주민등록인구를 바탕으로 한 상대 비교입니다. 전체 시장 규모, 인과관계 또는 개별 점포 수익성을 의미하지 않습니다.")
