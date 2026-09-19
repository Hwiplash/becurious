from __future__ import annotations

import html
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from src.charts import industry_bar, monthly_trend, regional_ranking, segment_chart
from src.data import compact_won, default_data_path, default_indices_path, load_csv, load_indices
from src.maps import sido_map, sigungu_map
from src.policy_ui import render_chat_launcher

load_dotenv()
st.set_page_config(page_title="상권 활성화 대책 제안 AI", page_icon="✦", layout="wide", initial_sidebar_state="collapsed")

if st.query_params.get("home") == "1":
    st.session_state.region_view = "national"
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
.mode-spacer{height:2.4rem}
.index-note{text-align:center;color:#89958f;font-size:.86rem;margin:-.8rem 0 1.1rem}.index-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:.45rem 0 1rem}.index-card{position:relative;min-height:112px;padding:18px 20px;border:1px solid var(--line);border-radius:17px;background:rgba(255,255,255,.9);box-shadow:0 8px 30px rgba(18,33,29,.04)}.index-card-label{color:#66756f;font-size:.9rem;font-weight:650;padding-right:25px}.index-card-value{color:var(--ink);font-size:1.72rem;font-weight:760;margin-top:.45rem}.info-wrap{position:absolute;right:15px;top:14px;width:18px;height:18px;display:grid;place-items:center;border-radius:50%;background:#edf1ef;color:#8a9590;font-size:.72rem;font-weight:800;cursor:help;z-index:5}.index-tooltip{position:absolute;right:0;bottom:calc(100% + 9px);width:285px;padding:12px 14px;border-radius:11px;background:#28332f;color:#fff;font-size:.78rem;font-weight:450;line-height:1.55;box-shadow:0 12px 32px rgba(18,33,29,.22);opacity:0;visibility:hidden;transform:translateY(5px);transition:.16s ease;pointer-events:none;text-align:left}.info-wrap:hover .index-tooltip,.info-wrap:focus .index-tooltip{opacity:1;visibility:visible;transform:translateY(0)}
@media(max-width:800px){.signal-grid,.index-grid{grid-template-columns:1fr}.hero-title{font-size:2.35rem}.block-container{padding-left:1rem;padding-right:1rem}.index-tooltip{width:240px}}
</style>
""", unsafe_allow_html=True)

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
    (strengths if sales_growth >= 0 else weaknesses).append(f"기간 매출이 {sales_growth:+.1%} {'성장했습니다.' if sales_growth >= 0 else '감소했습니다.'}")
    (strengths if count_growth >= 0 else weaknesses).append(f"이용 건수가 {count_growth:+.1%} {'늘었습니다.' if count_growth >= 0 else '줄었습니다.'}")
    (strengths if ticket_growth >= 0 else weaknesses).append(f"건당 결제액이 {ticket_growth:+.1%} {'상승했습니다.' if ticket_growth >= 0 else '낮아졌습니다.'}")
    if changes:
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

def render_signals(frame: pd.DataFrame, index_context: dict | None = None) -> None:
    strengths, weaknesses = signal_items(frame, index_context)
    listing = lambda items: "".join(f"<li>{html.escape(item)}</li>" for item in items) or "<li>뚜렷한 신호가 없습니다.</li>"
    st.markdown(f"<div class='signal-grid'><div class='signal-card strength'><div class='signal-title'>↗ Strength</div><ul>{listing(strengths)}</ul></div><div class='signal-card weakness'><div class='signal-title'>↘ Weakness</div><ul>{listing(weaknesses)}</ul></div></div>", unsafe_allow_html=True)

def render_metrics(frame: pd.DataFrame) -> None:
    amount, count, ticket, rate = summary_metrics(frame)
    cols = st.columns(4)
    cols[0].metric("총 매출", compact_won(amount)); cols[1].metric("이용 건수", f"{count:,.0f}건")
    cols[2].metric("건당 결제", f"{ticket:,.0f}원"); cols[3].metric("1월 → 6월 변화", f"{rate:+.1%}")

def go_to(view: str, sido: str | None = None, ccg: str | None = None) -> None:
    st.session_state.region_view = view
    if sido is not None: st.session_state.selected_sido = sido
    if ccg is not None: st.session_state.selected_ccg = ccg
    st.session_state["_scroll_top"] = True
    st.rerun()

def render_disclaimer() -> None:
    st.caption("BC카드 관측 소비를 기반으로 한 상대 비교이며, 2026년 1월에서 6월까지의 변화를 표시합니다.")

def index_snapshot(sido: str, ccg: str | None = None, industry: str | None = None) -> dict:
    base = indices["지역지수"]
    premium = indices["프리미엄"]
    population = indices["인구보정"]
    rank = indices["지역순위"]
    selector = base["시도"].eq(sido)
    if ccg is not None: selector &= base["시군구"].eq(ccg)
    base_rows = base[selector]
    premium_rows = premium[premium["시도"].eq(sido) & (premium["시군구"].eq(ccg) if ccg else True)]
    population_rows = population[population["시도"].eq(sido) & (population["시군구"].eq(ccg) if ccg else True)]
    rank_rows = rank[rank["시도"].eq(sido) & (rank["시군구"].eq(ccg) if ccg else True)]
    result = {
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
    if industry and industry != "업종 전체":
        industry_rows = indices["업종순위"]
        industry_rows = industry_rows[(industry_rows["시도"] == sido) & (industry_rows["업종"] == industry)]
        if ccg: industry_rows = industry_rows[industry_rows["시군구"] == ccg]
        if not industry_rows.empty:
            row = industry_rows.iloc[0]
            result.update({"industry_national_rank": row["전국 동일업종 지역순위"], "industry_metro_rank": row["광역 동일업종 지역순위"]})
    return result

def render_index_cards(context: dict, regional: bool = False) -> None:
    st.markdown("<div class='section-kicker'>COMMERCIAL VITALITY INDEX</div><div class='section-title'>상권 체력 지수</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='index-note'>해당 시도 내 시군구 중앙값 · 전국 기준 100</div>" if regional
        else "<div class='index-note'>선택한 시군구 지수 · 전국 기준 100</div>",
        unsafe_allow_html=True,
    )
    descriptions = {
        "scale": "결제금액 규모를 전국 시군구와 비교한 지수입니다. 100은 전국 기준 수준이며, 높을수록 관측된 소비시장 규모가 큽니다.",
        "activity": "결제 건수를 바탕으로 소비 활동의 빈도와 활발함을 비교한 지수입니다. 100보다 높으면 전국 기준보다 거래가 활발합니다.",
        "premium": "거래량과 업종 구조를 고려한 기대 건당결제액 대비 실제 결제 수준입니다. 100보다 높으면 상대적으로 고액 소비 성향이 강합니다.",
        "diversity": "매출이 여러 업종에 얼마나 고르게 분포하는지 나타냅니다. 100보다 높으면 업종 구성이 비교적 다양하고, 낮으면 특정 업종 의존도가 높습니다.",
    }
    descriptions["population_intensity"] = "주민등록인구 1인당 개인 BC 결제금액을 전국 시군구와 비교한 지수입니다. 100보다 높으면 주민 수를 고려해도 소비금액이 전국 기준보다 큽니다."
    descriptions["transaction_intensity"] = "주민등록인구 1인당 개인 BC 결제건수를 전국 시군구와 비교한 지수입니다. 100보다 높으면 주민 수 대비 거래 빈도가 전국 기준보다 높습니다."
    cards = [
        ("결제규모", "scale"), ("거래활력", "activity"), ("소비 프리미엄", "premium"),
        ("업종다양성", "diversity"), ("주민 소비강도", "population_intensity"), ("주민 거래강도", "transaction_intensity"),
    ]
    card_html = []
    for label, key in cards:
        value = context.get(key)
        display = f"{value:.1f}" if value is not None and not pd.isna(value) else "-"
        card_html.append(
            f"<div class='index-card'><div class='index-card-label'>{html.escape(label)}</div>"
            f"<div class='index-card-value'>{display}</div><div class='info-wrap' tabindex='0'>i"
            f"<div class='index-tooltip'>{html.escape(descriptions[key])}</div></div></div>"
        )
    st.markdown(f"<div class='index-grid'>{''.join(card_html)}</div>", unsafe_allow_html=True)
    details = []
    if context.get("market_type"): details.append(f"상권 유형 **{context['market_type']}**")
    if context.get("top_industry"): details.append(f"최대 매출 업종 **{context['top_industry']}** ({context['top_industry_share']:.1%})")
    if context.get("national_rank") is not None: details.append(f"전체 매출 전국 **{int(context['national_rank'])}위**, 광역 **{int(context['metro_rank'])}위**")
    if details: st.info(" · ".join(details))

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
    if view == "national":
        st.markdown("<div class='section-kicker'>NATIONAL OVERVIEW</div><div class='section-title'>어느 지역의 가능성을 살펴볼까요?</div>", unsafe_allow_html=True)
        map_col, table_col = st.columns([1.16, .84], gap="large"); ranking = regional_ranking(data, "SIDO_NM")
        with map_col:
            chart_label("전국 시도별 매출 분포")
            map_event = st.plotly_chart(sido_map(data), width="stretch", on_select="rerun", key="home_sido_map")
        with table_col:
            chart_label("시도별 소비 규모 순위")
            table_event = st.dataframe(ranking, hide_index=True, width="stretch", height=574, on_select="rerun", selection_mode="single-row", key="home_sido_table", column_config={"SIDO_NM":"지역","매출액":st.column_config.NumberColumn(format="%,.0f원"),"이용건수":st.column_config.NumberColumn(format="%,.0f건"),"건당결제액":st.column_config.NumberColumn(format="%,.0f원"),"매출비중":st.column_config.ProgressColumn(format="%.1%%",min_value=0,max_value=1)})
        chosen = selected_map_value(map_event) or selected_table_value(table_event, ranking, "SIDO_NM")
        if chosen in set(data["SIDO_NM"]): go_to("regional", sido=chosen)
        render_disclaimer()
        render_chat_launcher(data, indices)
    elif view == "regional":
        sido = st.session_state.get("selected_sido", sorted(data["SIDO_NM"].unique())[0]); region = data[data["SIDO_NM"] == sido]
        nav,spacer=st.columns([.7,3.3])
        with nav:
            if st.button("← 전국",width="stretch"): go_to("national")
        st.markdown(f"<div class='crumb'>전국 &nbsp;/&nbsp; <b>{html.escape(sido)}</b></div><div class='section-title'>{html.escape(sido)} 상권 현황</div>",unsafe_allow_html=True)
        render_metrics(region); map_col,table_col=st.columns([1.12,.88],gap="large"); ranking=regional_ranking(region,"CCG_NM")
        with map_col:
            chart_label("시군구별 매출 지도")
            map_event=st.plotly_chart(sigungu_map(region,sido),width="stretch",on_select="rerun",key=f"region_map_{sido}")
        with table_col:
            chart_label("시군구별 소비 규모 순위")
            table_event=st.dataframe(ranking,hide_index=True,width="stretch",height=574,on_select="rerun",selection_mode="single-row",key=f"region_table_{sido}",column_config={"CCG_NM":"시군구","매출액":st.column_config.NumberColumn(format="%,.0f원"),"이용건수":st.column_config.NumberColumn(format="%,.0f건"),"건당결제액":st.column_config.NumberColumn(format="%,.0f원"),"매출비중":st.column_config.ProgressColumn(format="%.1%%",min_value=0,max_value=1)})
        chosen=selected_map_value(map_event) or selected_table_value(table_event,ranking,"CCG_NM")
        if chosen in set(region["CCG_NM"]): go_to("local", sido=sido, ccg=chosen)
        region_indices = index_snapshot(sido)
        render_index_cards(region_indices, regional=True)
        st.markdown("<div class='section-kicker'>REGIONAL SIGNALS</div><div class='section-title'>강점과 회복 과제</div>",unsafe_allow_html=True); render_signals(region, region_indices)
        chart_label("월별 매출·이용 건수 추이")
        st.plotly_chart(monthly_trend(region),width="stretch",key=f"region_trend_{sido}"); left,right=st.columns(2,gap="large")
        with left:
            chart_label("업종별 매출 TOP 10")
            st.plotly_chart(industry_bar(region),width="stretch",key=f"region_industry_{sido}")
        with right:
            chart_label("연령·성별 소비 구성")
            st.plotly_chart(segment_chart(region),width="stretch",key=f"region_segment_{sido}")
        render_disclaimer(); render_chat_launcher(data,indices,sido=sido)
    else:
        sido=st.session_state.selected_sido; ccg=st.session_state.get("selected_ccg",sorted(data[data["SIDO_NM"]==sido]["CCG_NM"].unique())[0]); local=data[(data["SIDO_NM"]==sido)&(data["CCG_NM"]==ccg)]
        nav1,nav2,spacer=st.columns([.55,.7,2.75])
        with nav1:
            if st.button("← 전국",width="stretch"): go_to("national")
        with nav2:
            if st.button(f"← {sido}",width="stretch"): go_to("regional", sido=sido)
        st.markdown(f"<div class='crumb'>{html.escape(sido)} &nbsp;/&nbsp; <b>{html.escape(ccg)}</b></div><div class='section-title'>{html.escape(ccg)} 상권 진단</div>",unsafe_allow_html=True)
        render_metrics(local)
        local_indices = index_snapshot(sido, ccg)
        render_index_cards(local_indices)
        st.markdown("<div class='section-kicker'>LOCAL SIGNALS</div><div class='section-title'>강점과 회복 과제</div>",unsafe_allow_html=True); render_signals(local, local_indices)
        chart_label("월별 매출·이용 건수 추이")
        st.plotly_chart(monthly_trend(local),width="stretch",key=f"local_trend_{sido}_{ccg}"); left,right=st.columns(2,gap="large")
        with left:
            chart_label("업종별 매출 TOP 10")
            st.plotly_chart(industry_bar(local),width="stretch",key=f"local_industry_{sido}_{ccg}")
        with right:
            chart_label("연령·성별 소비 구성")
            st.plotly_chart(segment_chart(local),width="stretch",key=f"local_segment_{sido}_{ccg}")
        render_disclaimer(); render_chat_launcher(data,indices,sido,ccg)
else:
    industries=sorted(data["TP_BUZ_NM"].unique()); industry=industry_picker(industries); frame=data if industry=="업종 전체" else data[data["TP_BUZ_NM"]==industry]
    heading="업종별 전국 비교" if industry=="업종 전체" else f"{industry} 전국 분석"
    st.markdown(f"<div class='section-kicker'>INDUSTRY VIEW</div><div class='section-title'>{html.escape(heading)}</div>",unsafe_allow_html=True)
    render_metrics(frame); st.markdown("<div class='section-kicker'>INDUSTRY SIGNALS</div><div class='section-title'>업종의 강점과 회복 과제</div>",unsafe_allow_html=True); render_signals(frame)
    chart_label("월별 매출·이용 건수 추이")
    st.plotly_chart(monthly_trend(frame),width="stretch",key=f"industry_trend_{industry}")
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
            st.dataframe(ranking[["SIDO_NM","시군구","매출액","건당결제","전국 동일업종 지역순위","광역 동일업종 지역순위"]].head(20),hide_index=True,width="stretch",height=390,column_config={"SIDO_NM":"시도","매출액":st.column_config.NumberColumn(format="%,.0f원"),"건당결제":st.column_config.NumberColumn(format="%,.0f원")})
    with right:
        chart_label("연령·성별 소비 구성")
        st.plotly_chart(segment_chart(frame),width="stretch",key=f"industry_segment_{industry}")
    if industry=="업종 전체":
        chart_label("전체 업종 매출 비교")
        st.plotly_chart(industry_bar(data,n=len(industries)),width="stretch",key="all_industry_comparison")
    render_disclaimer(); render_chat_launcher(data,indices,industry=industry)
