from __future__ import annotations

import pandas as pd
import streamlit as st

from src.charts import industry_bar, monthly_trend, regional_ranking, segment_chart
from src.data import compact_won, default_data_path, load_csv, load_uploaded
from src.maps import sido_map, sigungu_map


st.set_page_config(page_title="ABP 상권 인사이트", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {background: radial-gradient(circle at 80% 0%, #102E3C 0, #07111F 38%, #050C16 100%);}
    [data-testid="stSidebar"] {background:#0A1626; border-right:1px solid rgba(255,255,255,.08)}
    .hero {padding:.4rem 0 1.1rem}.eyebrow{color:#22D3A7;font-size:.78rem;font-weight:700;letter-spacing:.16em}
    .hero h1{font-size:2.25rem;margin:.3rem 0}.hero p{color:#91A4B8;margin:0}
    [data-testid="stMetric"] {background:rgba(16,29,46,.78);border:1px solid rgba(255,255,255,.08);padding:1rem 1.1rem;border-radius:14px}
    [data-testid="stMetricValue"] {font-size:1.55rem}
    .section-label{font-size:.78rem;color:#22D3A7;font-weight:700;letter-spacing:.12em;margin-top:.4rem}
    div[data-testid="stPlotlyChart"] {background:rgba(10,22,38,.62);border:1px solid rgba(255,255,255,.07);border-radius:16px;padding:4px}
    .stDataFrame {border:1px solid rgba(255,255,255,.07);border-radius:12px;overflow:hidden}
</style>
""", unsafe_allow_html=True)


def selected_point(event, field: str) -> str | None:
    try:
        points = event.selection.points
        if not points:
            return None
        custom = points[0].get("customdata")
        return custom[0] if custom else points[0].get(field)
    except (AttributeError, IndexError, TypeError):
        return None


with st.sidebar:
    st.markdown("### ◈ ABP INSIGHT")
    st.caption("BC카드 소비데이터 탐색기")
    upload = st.file_uploader("새 CSV 불러오기", type="csv", help="같은 레이아웃의 후속 데이터를 바로 분석할 수 있습니다.")

try:
    if upload:
        data = load_uploaded(upload.getvalue())
        source_label = upload.name
    else:
        path = default_data_path()
        if path is None:
            st.error("데이터를 찾을 수 없습니다. 사이드바에서 CSV를 업로드하거나 data/raw/ABP_CONTEST_DATA.csv에 배치해주세요.")
            st.stop()
        data = load_csv(str(path.resolve()))
        source_label = path.name
except Exception as exc:
    st.error(f"데이터를 읽지 못했습니다: {exc}")
    st.stop()

with st.sidebar:
    st.divider()
    st.markdown("#### 분석 조건")
    min_month, max_month = data["month"].min(), data["month"].max()
    available_months = sorted(data["month"].unique())
    month_range = st.select_slider("기간", options=available_months, value=(available_months[0], available_months[-1]), format_func=lambda x: pd.Timestamp(x).strftime("%Y.%m"))
    industries = sorted(data["TP_BUZ_NM"].unique())
    industry = st.multiselect("업종", industries, placeholder="전체 업종")
    genders = st.multiselect("성별", [x for x in ["남성", "여성", "외국인", "미상", "기타"] if x in set(data["gender"])], placeholder="전체 성별")
    ages = st.multiselect("연령", [x for x in ["20대 이하", "20대", "30대", "40대", "50대", "60대 이상", "미상", "기타"] if x in set(data["age"])], placeholder="전체 연령")
    st.divider()
    st.caption(f"데이터 · {source_label}\n\n{len(data):,}행 · {min_month:%Y.%m}–{max_month:%Y.%m}")

filtered = data[data["month"].between(pd.Timestamp(month_range[0]), pd.Timestamp(month_range[1]))]
if industry:
    filtered = filtered[filtered["TP_BUZ_NM"].isin(industry)]
if genders:
    filtered = filtered[filtered["gender"].isin(genders)]
if ages:
    filtered = filtered[filtered["age"].isin(ages)]

st.markdown("<div class='hero'><div class='eyebrow'>AI FINANCIAL BIG DATA PLATFORM</div><h1>대한민국 소비 상권 인사이트</h1><p>지역을 선택해 전국에서 시군구까지 소비 흐름을 탐색하세요.</p></div>", unsafe_allow_html=True)

if filtered.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

total_amt, total_cnt = filtered["amt"].sum(), filtered["cnt"].sum()
monthly = filtered.groupby("month")["amt"].sum().sort_index()
growth = (monthly.iloc[-1] / monthly.iloc[0] - 1) if len(monthly) > 1 and monthly.iloc[0] else 0
top_region = filtered.groupby("SIDO_NM")["amt"].sum().idxmax()
k1, k2, k3, k4 = st.columns(4)
k1.metric("총 매출액", compact_won(total_amt))
k2.metric("이용 건수", f"{total_cnt:,.0f}건")
k3.metric("건당 결제액", compact_won(total_amt / total_cnt if total_cnt else 0))
k4.metric("기간 성장률", f"{growth:+.1%}", help="선택 기간 첫 달 대비 마지막 달 매출액 증감률")

st.markdown("<div class='section-label'>REGIONAL EXPLORER</div>", unsafe_allow_html=True)
map_col, detail_col = st.columns([1.16, .84], gap="large")
with map_col:
    st.subheader("전국 매출 지도")
    map_event = st.plotly_chart(sido_map(filtered), width="stretch", on_select="rerun", key="sido_map")
    clicked_sido = selected_point(map_event, "location")
with detail_col:
    st.subheader("지역 선택")
    sido_options = sorted(filtered["SIDO_NM"].unique())
    default_sido = clicked_sido if clicked_sido in sido_options else top_region
    sido = st.selectbox("시도", sido_options, index=sido_options.index(default_sido), help="지도 영역을 클릭해도 선택됩니다.")
    sido_df = filtered[filtered["SIDO_NM"] == sido]
    ranking = regional_ranking(sido_df, "CCG_NM")
    st.markdown(f"#### {sido} 상위 상권")
    st.dataframe(
        ranking.head(8), hide_index=True, width="stretch",
        column_config={"매출액": st.column_config.NumberColumn(format="%,.0f원"), "이용건수": st.column_config.NumberColumn(format="%,.0f건"), "건당결제액": st.column_config.NumberColumn(format="%,.0f원"), "매출비중": st.column_config.ProgressColumn(format="%.1%%", min_value=0, max_value=1)},
    )

st.markdown("<div class='section-label'>LOCAL ZOOM</div>", unsafe_allow_html=True)
local_map_col, trend_col = st.columns([.95, 1.25], gap="large")
with local_map_col:
    st.subheader(f"{sido} 시군구 지도")
    local_event = st.plotly_chart(sigungu_map(sido_df, sido), width="stretch", on_select="rerun", key=f"sigungu_{sido}")
    clicked_ccg = selected_point(local_event, "location")
    ccg_options = ["전체"] + sorted(sido_df["CCG_NM"].unique())
    ccg_index = ccg_options.index(clicked_ccg) if clicked_ccg in ccg_options else 0
    ccg = st.selectbox("시군구 상세", ccg_options, index=ccg_index, help="지도 영역을 클릭해도 선택됩니다.")

local_df = sido_df if ccg == "전체" else sido_df[sido_df["CCG_NM"] == ccg]
with trend_col:
    st.subheader(f"{sido} {'' if ccg == '전체' else ccg} 월별 추이")
    st.plotly_chart(monthly_trend(local_df), width="stretch", key="trend")

st.markdown("<div class='section-label'>MARKET COMPOSITION</div>", unsafe_allow_html=True)
industry_col, segment_col = st.columns(2, gap="large")
with industry_col:
    st.subheader("업종별 매출 TOP 10")
    st.plotly_chart(industry_bar(local_df), width="stretch")
with segment_col:
    st.subheader("연령·성별 소비 구성")
    st.plotly_chart(segment_chart(local_df), width="stretch")

with st.expander("선택 데이터 보기 · 다운로드"):
    export_columns = ["STRD_YYMM", "SIDO_NM", "CCG_NM", "GENDER_CD", "AGE_CD", "TP_BUZ_NO", "TP_BUZ_NM", "amt", "cnt"]
    st.dataframe(local_df[export_columns].head(1000), width="stretch", hide_index=True)
    st.download_button("필터 결과 CSV 다운로드", local_df[export_columns].to_csv(index=False).encode("utf-8-sig"), "abp_filtered.csv", "text/csv")

st.caption("※ 매출은 BC카드 제공 소비 집계 기준이며 전체 시장 규모 또는 개별 점포 수익성을 의미하지 않습니다. 지도 경계는 2013년 공개 행정구역 자료로, 최근 개편 지역은 선택 메뉴와 표를 함께 확인하세요.")
