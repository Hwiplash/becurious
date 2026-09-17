from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.data import korean_money_ticks


PALETTE = ["#22D3A7", "#4DA3FF", "#F3B75B", "#E76F8A", "#A78BFA", "#75D5E8"]


def style(fig: go.Figure, height: int = 340) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=38, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#475467"), legend_title_text="",
        hoverlabel=dict(bgcolor="#FFFFFF", font_color="#172033"),
    )
    fig.update_xaxes(gridcolor="rgba(23,32,51,.07)")
    fig.update_yaxes(gridcolor="rgba(23,32,51,.08)")
    return fig


def monthly_trend(df: pd.DataFrame) -> go.Figure:
    monthly = df.groupby("month", as_index=False).agg(매출액=("amt", "sum"), 이용건수=("cnt", "sum"))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=monthly["month"], y=monthly["매출액"], name="매출액", mode="lines+markers", line=dict(color=PALETTE[0], width=3), fill="tozeroy", fillcolor="rgba(34,211,167,.10)"))
    fig.add_trace(go.Scatter(x=monthly["month"], y=monthly["이용건수"], name="이용건수", mode="lines+markers", line=dict(color=PALETTE[1], width=2), yaxis="y2"))
    tickvals, ticktext = korean_money_ticks(float(monthly["매출액"].max()))
    fig.update_layout(yaxis=dict(title="매출액", tickvals=tickvals, ticktext=ticktext), yaxis2=dict(title="건수", overlaying="y", side="right", tickformat=","), hovermode="x unified")
    return style(fig, 360)


def industry_bar(df: pd.DataFrame, n: int = 10) -> go.Figure:
    grouped = df.groupby("TP_BUZ_NM", as_index=False).agg(매출액=("amt", "sum")).nlargest(n, "매출액").sort_values("매출액")
    fig = px.bar(grouped, x="매출액", y="TP_BUZ_NM", orientation="h", color="매출액", color_continuous_scale=[[0, "#176260"], [1, "#34E0B1"]])
    tickvals, ticktext = korean_money_ticks(float(grouped["매출액"].max()))
    fig.update_layout(coloraxis_showscale=False, xaxis_title="매출액", yaxis_title=None)
    fig.update_xaxes(tickvals=tickvals, ticktext=ticktext)
    fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:,.0f}원<extra></extra>")
    return style(fig, 380)


def segment_chart(df: pd.DataFrame) -> go.Figure:
    grouped = df.groupby(["age", "gender"], as_index=False).agg(매출액=("amt", "sum"))
    age_order = ["20대 이하", "20대", "30대", "40대", "50대", "60대 이상", "미상", "기타"]
    fig = px.bar(grouped, x="age", y="매출액", color="gender", barmode="group", color_discrete_sequence=PALETTE, category_orders={"age": age_order})
    tickvals, ticktext = korean_money_ticks(float(grouped["매출액"].max()))
    fig.update_layout(xaxis_title=None, yaxis_title="매출액")
    fig.update_yaxes(tickvals=tickvals, ticktext=ticktext)
    fig.update_traces(hovertemplate="%{x} · %{fullData.name}<br>%{y:,.0f}원<extra></extra>")
    return style(fig, 380)


def regional_ranking(df: pd.DataFrame, column: str) -> pd.DataFrame:
    ranking = df.groupby(column, as_index=False).agg(매출액=("amt", "sum"), 이용건수=("cnt", "sum"))
    ranking["건당결제액"] = ranking["매출액"].div(ranking["이용건수"].replace(0, pd.NA)).fillna(0)
    ranking["매출비중"] = ranking["매출액"] / ranking["매출액"].sum()
    return ranking.sort_values("매출액", ascending=False).reset_index(drop=True)


def premium_quadrant(df: pd.DataFrame, selected: str | None = None) -> go.Figure:
    frame = df.copy()
    frame["선택"] = frame["시군구"].eq(selected).map({True: "선택 지역", False: "다른 지역"})
    fig = px.scatter(
        frame, x="결제금액 규모지수", y="6개월 통합 프리미엄지수", size="거래활력지수",
        color="선택", hover_name="시군구", hover_data={"시도": True, "규모·프리미엄 유형": True},
        color_discrete_map={"다른 지역": "#9CB0C3", "선택 지역": "#0E9F7D"},
        size_max=28,
    )
    fig.add_hline(y=100, line_dash="dot", line_color="#98A2B3")
    fig.add_vline(x=100, line_dash="dot", line_color="#98A2B3")
    fig.update_layout(xaxis_title="결제금액 규모지수", yaxis_title="거래량 보정 소비 프리미엄", showlegend=False)
    return style(fig, 430)


def intensity_compare(row: pd.Series) -> go.Figure:
    frame = pd.DataFrame({
        "지표": ["개인 금액", "개인 건수", "남성 금액", "여성 금액"],
        "지수": [row["개인 금액 지수(평균=100)"], row["개인 건수 지수(평균=100)"], row["남성 강도 지수"], row["여성 강도 지수"]],
    })
    fig = px.bar(frame, x="지표", y="지수", color="지수", color_continuous_scale="Tealgrn")
    fig.add_hline(y=100, line_dash="dot", line_color="#667085", annotation_text="지역 평균 100")
    fig.update_layout(coloraxis_showscale=False, xaxis_title=None, yaxis_title="강도지수")
    return style(fig, 350)
