from __future__ import annotations

import html
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from src.charts import industry_bar, monthly_count_trend, monthly_sales_trend, performance_change_compare, regional_ranking, segment_chart
from src.data import default_data_path, default_indices_path, load_csv, load_indices
from src.dashboard_components import (
    chart_label,
    filter_industry,
    go_to,
    industry_index_snapshot,
    index_snapshot,
    industry_picker,
    region_industry_filter,
    render_disclaimer,
    render_index_cards,
    render_metrics,
    render_signals,
    selected_map_value,
    selected_table_value,
)
from src.maps import sido_map, sigungu_map
from src.policy_ui import render_chat_launcher
from src.problem_regions import prediction_band

load_dotenv()
st.set_page_config(page_title="상권 활성화 대책 제안 AI", page_icon="✦", layout="wide", initial_sidebar_state="collapsed")

if st.query_params.get("home") == "1":
    st.session_state.region_view = "national"
    st.session_state.region_industry_filter = "업종 전체"
    st.session_state.pop("selected_sido", None)
    st.session_state.pop("selected_ccg", None)
    st.session_state["_scroll_top"] = True
    st.query_params.clear()
    st.rerun()

if st.session_state.pop("_scroll_top", False):
    components.html("<script>window.parent.scrollTo({top:0,left:0,behavior:'instant'});</script>", height=0)
st.markdown("""
<style>
:root{--ink:#12211d;--muted:#66756f;--line:#dfe8e3;--green:#087f5b}
[data-testid="stAppViewContainer"]{background:linear-gradient(145deg,#f7fbf8 0%,#f4f7f5 55%,#edf5f1 100%)}
[data-testid="stHeader"]{background:transparent}[data-testid="stSidebar"]{display:none}
.block-container{max-width:1440px;padding-top:1.4rem;padding-bottom:5rem}
.brand{display:flex;align-items:center;justify-content:center;gap:.7rem;color:var(--green);font-weight:800;letter-spacing:.08em;font-size:.82rem;margin-bottom:.8rem}
.brand-mark{display:inline-grid;place-items:center;width:29px;height:29px;border-radius:9px;background:#0b8f68;color:white;font-size:16px}
.hero{position:relative;text-align:center;padding:3.1rem 2rem 4.2rem;margin-bottom:.15rem;border:0;border-radius:0;background:radial-gradient(circle at 18% 10%,rgba(92,219,190,.38),transparent 35%),radial-gradient(circle at 78% 5%,rgba(100,173,255,.32),transparent 37%),radial-gradient(circle at 70% 62%,rgba(191,132,255,.22),transparent 38%),linear-gradient(to bottom,rgba(241,253,249,.94) 0%,rgba(242,248,255,.78) 58%,rgba(247,251,248,0) 100%);box-shadow:none}
.hero-title{font-size:clamp(2.25rem,4.5vw,4.35rem);line-height:1.08;letter-spacing:-.055em;margin:.65rem auto;color:var(--ink);text-align:center;font-weight:800}.hero-title a{color:inherit!important;text-decoration:none!important}.hero-title a:hover{color:#087f5b!important}
.hero p{font-size:1.08rem;line-height:1.7;color:var(--muted);margin:.85rem auto 0;max-width:760px;text-align:center}.eyebrow{font-size:.78rem;letter-spacing:.17em;color:var(--green);font-weight:800;text-align:center}
[data-testid="stMetric"]{background:rgba(255,255,255,.88);border:1px solid var(--line);border-radius:17px;padding:1rem 1.1rem;box-shadow:0 8px 30px rgba(18,33,29,.045)}
[data-testid="stMetricLabel"]{color:var(--muted)}[data-testid="stMetricValue"]{color:var(--ink);font-size:1.55rem}
div[data-testid="stPlotlyChart"]{background:rgba(255,255,255,.9);border:1px solid var(--line);border-radius:20px;padding:0;overflow:hidden;box-sizing:border-box;box-shadow:0 10px 35px rgba(18,33,29,.04)}
.stDataFrame{background:rgba(255,255,255,.9);border:1px solid var(--line);border-radius:20px;padding:6px 6px 14px;overflow:hidden;box-sizing:border-box;box-shadow:0 10px 35px rgba(18,33,29,.04)}
.section-kicker{font-size:.76rem;letter-spacing:.14em;font-weight:800;color:var(--green);margin-top:1.65rem;text-align:center}.section-title{font-size:clamp(1.85rem,2.6vw,2.45rem);line-height:1.25;font-weight:780;color:var(--ink);margin:.22rem 0 1.15rem;text-align:center;letter-spacing:-.035em}
.signal-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:.6rem 0 1.4rem}.signal-card{padding:20px 22px;border-radius:18px;border:1px solid var(--line);background:rgba(255,255,255,.88)}
.signal-card.strength{border-top:4px solid #0b9b70}.signal-card.weakness{border-top:4px solid #d06a6a}.signal-title{font-weight:800;font-size:1rem;color:var(--ink);margin-bottom:.55rem}.signal-card ul{padding-left:1.1rem;margin:.2rem 0;color:#45534e}.signal-card li{margin:.38rem 0}
.chat-label{text-align:center;color:var(--ink);font-weight:820;font-size:1.58rem;letter-spacing:-.03em;margin:4.7rem 0 1rem}.st-key-quick_questions{max-width:1100px;margin:0 auto 1.15rem;text-align:center}.st-key-quick_questions [data-testid="stHorizontalBlock"]{justify-content:center}.st-key-quick_questions button{min-height:76px;border:1px solid #dfe8e3;border-radius:15px;background:rgba(255,255,255,.82);color:#40504a;font-family:"Nanum Pen Script","나눔손글씨 펜","Segoe Print","Malgun Gothic",cursive!important;font-size:1.02rem;font-style:italic;font-weight:500;line-height:1.45;text-align:center!important;justify-content:center!important;padding:.75rem 1rem}.st-key-quick_questions button [data-testid="stMarkdownContainer"]{width:100%;display:flex;align-items:center;justify-content:center;text-align:center!important}.st-key-quick_questions button p{width:100%;margin:0!important;text-align:center!important;white-space:normal!important;overflow:visible!important;text-overflow:clip!important;font-family:inherit!important;font-style:italic!important}.st-key-quick_questions button:hover{border-color:#65ad94;color:#087f5b;background:#f4fbf8}div[data-testid="stChatInput"]{max-width:900px;margin:0 auto;border-radius:22px;box-shadow:0 14px 45px rgba(18,33,29,.11)}
div[data-testid="stSegmentedControl"]{max-width:680px;margin:2.25rem auto 2.45rem;background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important}div[data-testid="stSegmentedControl"]>div{background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important}div[data-testid="stSegmentedControl"] label{min-height:62px;font-size:1.2rem;font-weight:780;padding:.9rem 3.2rem}
div[data-testid="stPills"]{background:rgba(255,255,255,.78);padding:6px;border:1px solid var(--line);border-radius:16px;box-shadow:0 8px 24px rgba(18,33,29,.05)}.crumb{color:var(--muted);font-size:.9rem;margin:.2rem 0 .65rem;text-align:center}.crumb b{color:var(--ink)}
.chart-label{font-size:.93rem;font-weight:780;color:#34463f;margin:1.15rem 0 .45rem;letter-spacing:-.01em}.industry-grid{margin:.35rem 0 1.5rem}
.region-filter-label{text-align:center;color:#66756f;font-size:.84rem;font-weight:700;margin:-.55rem 0 .2rem}
.mode-spacer{height:2.4rem}
.index-note{text-align:center;color:#89958f;font-size:.86rem;margin:-.8rem 0 1.1rem}.index-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:.45rem 0 1rem}.index-card{position:relative;min-height:112px;padding:18px 20px;border:1px solid var(--line);border-radius:17px;background:rgba(255,255,255,.9);box-shadow:0 8px 30px rgba(18,33,29,.04)}.index-card-label{color:#66756f;font-size:.9rem;font-weight:650;padding-right:25px}.index-card-value{color:var(--ink);font-size:1.72rem;font-weight:760;margin-top:.45rem}.info-wrap{position:absolute;right:15px;top:14px;width:18px;height:18px;display:grid;place-items:center;border-radius:50%;background:#edf1ef;color:#8a9590;font-size:.72rem;font-weight:800;cursor:help;z-index:5}.index-tooltip{position:absolute;right:0;bottom:calc(100% + 9px);width:285px;padding:12px 14px;border-radius:11px;background:#28332f;color:#fff;font-size:.78rem;font-weight:450;line-height:1.55;box-shadow:0 12px 32px rgba(18,33,29,.22);opacity:0;visibility:hidden;transform:translateY(5px);transition:.16s ease;pointer-events:none;text-align:left}.info-wrap:hover .index-tooltip,.info-wrap:focus .index-tooltip{opacity:1;visibility:visible;transform:translateY(0)}
@media(max-width:800px){.signal-grid,.index-grid{grid-template-columns:1fr}.hero-title{font-size:2.35rem}.block-container{padding-left:1rem;padding-right:1rem}.index-tooltip{width:240px}}
</style>
""", unsafe_allow_html=True)


try:
    raw_path, index_path = default_data_path(), default_indices_path()
    if raw_path is None or index_path is None:
        st.error("필수 데이터 파일을 찾지 못했습니다."); st.stop()
    data = load_csv(str(raw_path.resolve())); indices = load_indices(str(index_path.resolve()))
except Exception as exc:
    st.error(f"데이터를 읽지 못했습니다: {exc}"); st.stop()

st.markdown("<div class='brand'><span class='brand-mark'>✦</span> LOCAL REVIVE AI</div>", unsafe_allow_html=True)
st.markdown("<div class='hero'><div class='eyebrow'>DATA-DRIVEN POLICY INTELLIGENCE</div><div class='hero-title' role='heading' aria-level='1'><a href='?home=1' target='_self'>상권 활성화 대책 제안 AI</a></div><p>지역 소비 데이터와 170여 개 정책·연구 보고서를 연결해 지역과 업종에 맞는 실행 전략을 제안합니다.</p></div>", unsafe_allow_html=True)
st.markdown("<div class='mode-spacer'></div>", unsafe_allow_html=True)
mode_left, mode_center, mode_right = st.columns([1, 2, 1])
with mode_center:
    mode = st.segmented_control("분석 기준", ["지역별", "업종별"], default="지역별", label_visibility="collapsed", width="stretch")
if st.session_state.get("_last_mode") not in (None, mode):
    components.html("<script>window.parent.scrollTo({top:0,left:0,behavior:'instant'});</script>", height=0)
st.session_state["_last_mode"] = mode
if "region_view" not in st.session_state: st.session_state.region_view = "national"

if mode == "지역별":
    view = st.session_state.region_view
    region_industries = sorted(data["TP_BUZ_NM"].unique())
    if view == "national":
        st.markdown("<div class='section-kicker'>NATIONAL OVERVIEW</div><div class='section-title'>어느 지역의 가능성을 살펴볼까요?</div>", unsafe_allow_html=True)
        industry = region_industry_filter(region_industries)
        national = filter_industry(data, industry)
        map_col, table_col = st.columns([1.16, .84], gap="large"); ranking = regional_ranking(national, "SIDO_NM")
        with map_col:
            chart_label("전국 시도별 매출 분포" if industry == "업종 전체" else f"전국 시도별 {industry} 매출 분포")
            map_event = st.plotly_chart(sido_map(national), width="stretch", on_select="rerun", key=f"home_sido_map_{industry}")
        with table_col:
            chart_label("시도별 소비 규모 순위" if industry == "업종 전체" else f"시도별 {industry} 소비 규모 순위")
            table_event = st.dataframe(ranking, hide_index=True, width="stretch", height=574, on_select="rerun", selection_mode="single-row", key=f"home_sido_table_{industry}", column_config={"SIDO_NM":"지역","매출액":st.column_config.NumberColumn(format="%,.0f원"),"이용건수":st.column_config.NumberColumn(format="%,.0f건"),"건당결제액":st.column_config.NumberColumn(format="%,.0f원"),"매출비중":st.column_config.ProgressColumn(format="%.1%%",min_value=0,max_value=1)})
        chosen = selected_map_value(map_event) or selected_table_value(table_event, ranking, "SIDO_NM")
        if chosen in set(national["SIDO_NM"]): go_to("regional", sido=chosen)
        render_disclaimer()
        render_chat_launcher(data, indices, industry=industry)
    elif view == "regional":
        sido = st.session_state.get("selected_sido", sorted(data["SIDO_NM"].unique())[0]); region_all = data[data["SIDO_NM"] == sido]
        nav,spacer=st.columns([.7,3.3])
        with nav:
            if st.button("← 전국",width="stretch"): go_to("national")
        st.markdown(f"<div class='crumb'>전국 &nbsp;/&nbsp; <b>{html.escape(sido)}</b></div><div class='section-title'>{html.escape(sido)} 상권 현황</div>",unsafe_allow_html=True)
        industry = region_industry_filter(sorted(region_all["TP_BUZ_NM"].unique()))
        region = filter_industry(region_all, industry)
        render_metrics(region); map_col,table_col=st.columns([1.12,.88],gap="large"); ranking=regional_ranking(region,"CCG_NM")
        with map_col:
            chart_label("시군구별 매출 지도" if industry == "업종 전체" else f"시군구별 {industry} 매출 지도")
            map_event=st.plotly_chart(sigungu_map(region,sido),width="stretch",on_select="rerun",key=f"region_map_{sido}_{industry}")
        with table_col:
            chart_label("시군구별 소비 규모 순위" if industry == "업종 전체" else f"시군구별 {industry} 소비 규모 순위")
            table_event=st.dataframe(ranking,hide_index=True,width="stretch",height=574,on_select="rerun",selection_mode="single-row",key=f"region_table_{sido}_{industry}",column_config={"CCG_NM":"시군구","매출액":st.column_config.NumberColumn(format="%,.0f원"),"이용건수":st.column_config.NumberColumn(format="%,.0f건"),"건당결제액":st.column_config.NumberColumn(format="%,.0f원"),"매출비중":st.column_config.ProgressColumn(format="%.1%%",min_value=0,max_value=1)})
        chosen=selected_map_value(map_event) or selected_table_value(table_event,ranking,"CCG_NM")
        if chosen in set(region["CCG_NM"]): go_to("local", sido=sido, ccg=chosen)
        region_indices = index_snapshot(indices, sido, industry=industry)
        render_index_cards(region_indices, regional=True)
        st.markdown("<div class='section-kicker'>REGIONAL SIGNALS</div><div class='section-title'>강점과 회복 과제</div>",unsafe_allow_html=True); render_signals(region, region_indices)
        chart_label("월별 매출액 추이")
        st.plotly_chart(monthly_sales_trend(region),width="stretch",key=f"region_sales_trend_{sido}_{industry}")
        chart_label("월별 이용건수 추이")
        st.plotly_chart(monthly_count_trend(region),width="stretch",key=f"region_count_trend_{sido}_{industry}")
        left,right=st.columns(2,gap="large")
        with left:
            if industry == "업종 전체":
                chart_label("업종별 매출 TOP 10")
                st.plotly_chart(industry_bar(region),width="stretch",key=f"region_industry_{sido}_{industry}")
            else:
                chart_label(f"{industry} vs {sido} 전체 변화")
                st.plotly_chart(performance_change_compare(region_all, industry, f"{sido} 전체"),width="stretch",key=f"region_performance_{sido}_{industry}")
        with right:
            chart_label("연령·성별 소비 구성")
            st.plotly_chart(segment_chart(region),width="stretch",key=f"region_segment_{sido}_{industry}")
        render_disclaimer(); render_chat_launcher(data,indices,sido=sido,industry=industry)
    else:
        sido=st.session_state.selected_sido; ccg=st.session_state.get("selected_ccg",sorted(data[data["SIDO_NM"]==sido]["CCG_NM"].unique())[0]); local_all=data[(data["SIDO_NM"]==sido)&(data["CCG_NM"]==ccg)]
        nav1,nav2,spacer=st.columns([.55,.7,2.75])
        with nav1:
            if st.button("← 전국",width="stretch"): go_to("national")
        with nav2:
            if st.button(f"← {sido}",width="stretch"): go_to("regional", sido=sido)
        st.markdown(f"<div class='crumb'>{html.escape(sido)} &nbsp;/&nbsp; <b>{html.escape(ccg)}</b></div><div class='section-title'>{html.escape(ccg)} 상권 진단</div>",unsafe_allow_html=True)
        industry = region_industry_filter(sorted(local_all["TP_BUZ_NM"].unique()))
        local = filter_industry(local_all, industry)
        render_metrics(local)
        local_indices = index_snapshot(indices, sido, ccg, industry)
        render_index_cards(local_indices)
        st.markdown("<div class='section-kicker'>LOCAL SIGNALS</div><div class='section-title'>강점과 회복 과제</div>",unsafe_allow_html=True); render_signals(local, local_indices)
        forecast = prediction_band(sido, ccg, industry)
        chart_label("월별 매출액 및 회귀 기대범위")
        st.plotly_chart(monthly_sales_trend(local, forecast),width="stretch",key=f"local_sales_trend_{sido}_{ccg}_{industry}")
        if forecast is not None:
            st.caption("초록 실선은 실제 매출, 주황 점선은 예측구간 중심입니다. 주황 음영은 해당 지역·월의 90% 진단용 예측구간이며 미래 매출 예측이 아닙니다.")
        chart_label("월별 이용건수 추이")
        st.plotly_chart(monthly_count_trend(local),width="stretch",key=f"local_count_trend_{sido}_{ccg}_{industry}")
        left,right=st.columns(2,gap="large")
        with left:
            if industry == "업종 전체":
                chart_label("업종별 매출 TOP 10")
                st.plotly_chart(industry_bar(local),width="stretch",key=f"local_industry_{sido}_{ccg}_{industry}")
            else:
                chart_label(f"{industry} vs {ccg} 전체 변화")
                st.plotly_chart(performance_change_compare(local_all, industry, f"{ccg} 전체"),width="stretch",key=f"local_performance_{sido}_{ccg}_{industry}")
        with right:
            chart_label("연령·성별 소비 구성")
            st.plotly_chart(segment_chart(local),width="stretch",key=f"local_segment_{sido}_{ccg}_{industry}")
        render_disclaimer(); render_chat_launcher(data,indices,sido,ccg,industry)
else:
    industries=sorted(data["TP_BUZ_NM"].unique()); industry=industry_picker(industries); frame=data if industry=="업종 전체" else data[data["TP_BUZ_NM"]==industry]
    heading="업종별 전국 비교" if industry=="업종 전체" else f"{industry} 전국 분석"
    st.markdown(f"<div class='section-kicker'>INDUSTRY VIEW</div><div class='section-title'>{html.escape(heading)}</div>",unsafe_allow_html=True)
    render_metrics(frame)
    industry_indices = industry_index_snapshot(data, industry) if industry != "업종 전체" else None
    if industry_indices:
        render_index_cards(industry_indices)
    st.markdown("<div class='section-kicker'>INDUSTRY SIGNALS</div><div class='section-title'>업종의 강점과 회복 과제</div>",unsafe_allow_html=True); render_signals(frame, industry_indices)
    chart_label("월별 매출액 추이")
    st.plotly_chart(monthly_sales_trend(frame),width="stretch",key=f"industry_sales_trend_{industry}")
    chart_label("월별 이용건수 추이")
    st.plotly_chart(monthly_count_trend(frame),width="stretch",key=f"industry_count_trend_{industry}")
    if industry == "업종 전체":
        ranking=regional_ranking(frame,"SIDO_NM")
    else:
        rank_source = indices["업종순위"]
        ranking = rank_source[rank_source["업종"] == industry].sort_values("전국 동일업종 지역순위").rename(columns={"시도":"SIDO_NM"})
    left,right=st.columns([.95,1.05],gap="large")
    with left:
        chart_label("지역별 매출 순위" if industry == "업종 전체" else "동일 업종 전국 상위 지역")
        if industry == "업종 전체":
            st.dataframe(ranking,hide_index=True,width="stretch",height=390,column_config={"SIDO_NM":"지역","매출액":st.column_config.NumberColumn(format="%,.0f원"),"이용건수":st.column_config.NumberColumn(format="%,.0f건"),"건당결제액":st.column_config.NumberColumn(format="%,.0f원"),"매출비중":st.column_config.ProgressColumn(format="%.1%%",min_value=0,max_value=1)})
        else:
            st.dataframe(ranking[["SIDO_NM","시군구","매출액","건당결제","전국 동일업종 지역순위","광역 동일업종 지역순위"]].head(20),hide_index=True,width="stretch",height=390,column_config={"SIDO_NM":"시도","매출액":st.column_config.NumberColumn(format="%,.0f원"),"건당결제":st.column_config.NumberColumn(format="%,.0f원"),"전국 동일업종 지역순위":"전국 순위","광역 동일업종 지역순위":"광역 순위"})
    with right:
        chart_label("연령·성별 소비 구성")
        st.plotly_chart(segment_chart(frame),width="stretch",key=f"industry_segment_{industry}")
    if industry=="업종 전체":
        chart_label("전체 업종 매출 비교")
        st.plotly_chart(industry_bar(data,n=len(industries)),width="stretch",key="all_industry_comparison")
    render_disclaimer(); render_chat_launcher(data,indices,industry=industry)
