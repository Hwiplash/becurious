from __future__ import annotations

import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.period_change import format_change, jan_jun_change
from src.total_market import personal_rows, POPULATION_LABELS

PALETTE = ["#22D3A7", "#4DA3FF", "#F3B75B", "#E76F8A", "#A78BFA", "#75D5E8"]


def _nice_step(raw_step: float) -> float:
    if raw_step <= 0:
        return 1
    magnitude = 10 ** math.floor(math.log10(raw_step))
    normalized = raw_step / magnitude
    nice = next(value for value in (1, 2, 5, 10) if normalized <= value)
    return nice * magnitude


def _axis_ticks(max_value: float, kind: str = "money", count: int = 5) -> tuple[list[float], list[str], str]:
    if kind == "money":
        scales = [(1_0000_0000_0000, "조원"), (1_0000_0000, "억원"), (1_0000, "만원"), (1, "원")]
    else:
        scales = [(1_0000_0000, "억건"), (1_0000, "만건"), (1_000, "천건"), (1, "건")]
    divisor, unit = next(((scale, label) for scale, label in scales if max_value >= scale), scales[-1])
    scaled_max = max_value / divisor if divisor else max_value
    step = _nice_step(scaled_max / count)
    axis_max = math.ceil(scaled_max / step) * step
    scaled_values = [step * index for index in range(int(round(axis_max / step)) + 1)] if max_value > 0 else [0]
    values = [value * divisor for value in scaled_values]
    decimals = max(0, -math.floor(math.log10(step))) if step < 1 else 0
    labels = [f"{value:,.{decimals}f}" for value in scaled_values]
    return values, labels, unit


def style(fig: go.Figure, height: int = 340) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=12, r=12, t=48, b=46),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#475467"), legend_title_text="",
        hoverlabel=dict(bgcolor="#FFFFFF", font_color="#172033"),
    )
    fig.update_xaxes(gridcolor="rgba(23,32,51,.07)")
    fig.update_yaxes(gridcolor="rgba(23,32,51,.08)")
    return fig


def monthly_sales_trend(df: pd.DataFrame, forecast: pd.DataFrame | None = None) -> go.Figure:
    monthly = df.groupby("month", as_index=False).agg(매출액=("amt", "sum"), 이용건수=("cnt", "sum"))
    fig = go.Figure()
    if forecast is not None and not forecast.empty:
        fig.add_trace(go.Scatter(
            x=forecast["month"], y=forecast["lower90_amt"], name="90% 범위 하한",
            mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=forecast["month"], y=forecast["upper90_amt"], name="회귀 기대범위(90%)",
            mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(243,183,91,.20)",
            hovertemplate="90% 참고 상한 %{y:,.0f}원<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=forecast["month"], y=forecast["expected_amt"], name="회귀 기대매출",
            mode="lines", line=dict(color="#D89A32", width=2, dash="dash"),
            hovertemplate="회귀 기대매출 %{y:,.0f}원<extra></extra>",
        ))
    fig.add_trace(go.Scatter(x=monthly["month"], y=monthly["매출액"], name="매출액", mode="lines+markers", line=dict(color=PALETTE[0], width=3), fill="tozeroy", fillcolor="rgba(34,211,167,.10)"))
    money_max = float(monthly["매출액"].max())
    if forecast is not None and not forecast.empty:
        money_max = max(money_max, float(forecast["upper90_amt"].max()))
    tickvals, ticktext, money_unit = _axis_ticks(money_max, "money")
    fig.update_layout(
        yaxis=dict(title=f"매출액 ({money_unit})", tickvals=tickvals, ticktext=ticktext),
        hovermode="x unified",
        showlegend=False,
    )
    fig = style(fig, 340)
    fig.update_layout(margin=dict(l=12, r=12, t=30, b=24))
    return fig


def monthly_count_trend(df: pd.DataFrame) -> go.Figure:
    monthly = df.groupby("month", as_index=False).agg(이용건수=("cnt", "sum"))
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly["month"], y=monthly["이용건수"], name="이용건수",
        mode="lines+markers", line=dict(color=PALETTE[1], width=3),
        fill="tozeroy", fillcolor="rgba(77,163,255,.10)",
        hovertemplate="이용건수 %{y:,.0f}건<extra></extra>",
    ))
    countvals, counttext, count_unit = _axis_ticks(float(monthly["이용건수"].max()), "count")
    fig.update_layout(
        yaxis=dict(title=f"이용건수 ({count_unit})", tickvals=countvals, ticktext=counttext),
        hovermode="x unified",
        showlegend=False,
    )
    fig = style(fig, 300)
    fig.update_layout(margin=dict(l=12, r=12, t=30, b=24))
    return fig


def industry_bar(df: pd.DataFrame, n: int = 10) -> go.Figure:
    grouped = df.groupby("TP_BUZ_NM", as_index=False).agg(매출액=("amt", "sum")).nlargest(n, "매출액").sort_values("매출액")
    fig = px.bar(grouped, x="매출액", y="TP_BUZ_NM", orientation="h", color="매출액", color_continuous_scale=[[0, "#176260"], [1, "#34E0B1"]])
    tickvals, ticktext, unit = _axis_ticks(float(grouped["매출액"].max()), "money")
    fig.update_layout(coloraxis_showscale=False, xaxis_title=f"매출액 ({unit})", yaxis_title=None)
    fig.update_xaxes(tickvals=tickvals, ticktext=ticktext)
    fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:,.0f}원<extra></extra>")
    return style(fig, 380)


def performance_change_compare(df: pd.DataFrame, industry: str, scope_label: str,
                               required_industries: tuple[str, ...] | None = None) -> go.Figure:
    """선택 업종과 같은 지역 전체의 기간 변화를 매출·건수·객단가로 비교한다."""
    def changes(frame: pd.DataFrame, require_scope: bool = False) -> list[float | None]:
        monthly = frame.groupby("month").agg(amt=("amt", "sum"), cnt=("cnt", "sum"))
        if require_scope and required_industries:
            complete = frame.groupby("month")["TP_BUZ_NO"].nunique().eq(len(required_industries))
            monthly.loc[~complete, ["amt", "cnt"]] = float("nan")
        monthly["ticket"] = monthly["amt"].div(monthly["cnt"].replace(0, pd.NA))
        return [jan_jun_change(monthly[column]) for column in ("amt", "cnt", "ticket")]

    selected = df[df["TP_BUZ_NM"] == industry]
    metrics = ["매출액", "이용건수", "건당결제"]
    figure = go.Figure()
    for name, values, color in (
        (industry, changes(selected), PALETTE[0]),
        (scope_label, changes(df, require_scope=True), "#A7B4AE"),
    ):
        figure.add_trace(go.Bar(
            x=metrics,
            y=values,
            name=name,
            marker_color=color,
            text=[format_change(value) for value in values],
            textposition="outside",
            cliponaxis=False,
            hovertemplate=f"<b>{name}</b><br>%{{x}} %{{y:+.1%}}<extra></extra>",
        ))
    for trace_index, trace in enumerate(figure.data):
        for metric, value in zip(metrics, trace.y):
            if value is None:
                figure.add_annotation(x=metric, y=0, text="산출 불가", showarrow=False,
                                      xshift=-42 if trace_index == 0 else 42, yshift=14,
                                      font=dict(size=9, color="#66756f"))
    all_values = [float(value) for trace in figure.data for value in trace.y if value is not None]
    extent = max([abs(value) for value in all_values] or [0.1])
    figure.add_hline(y=0, line_color="#98A2B3", line_width=1)
    figure.update_layout(
        barmode="group",
        yaxis_title="1월 → 6월 변화율",
        yaxis_tickformat="+.0%",
        yaxis_range=[-extent * 1.35, extent * 1.35],
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="left", x=0),
    )
    return style(figure, 380)


def segment_chart(df: pd.DataFrame) -> go.Figure:
    df = personal_rows(df)
    grouped = df.groupby(["age", "gender"], as_index=False).agg(매출액=("amt", "sum"))
    age_order = ["20대 이하", "20대", "30대", "40대", "50대", "60대 이상", "미상", "기타"]
    fig = px.bar(grouped, x="age", y="매출액", color="gender", barmode="group", color_discrete_sequence=PALETTE, category_orders={"age": age_order})
    tickvals, ticktext, unit = _axis_ticks(float(grouped["매출액"].max()) if not grouped.empty else 0, "money")
    fig.update_layout(xaxis_title=None, yaxis_title=f"내국인 개인 BC 이용금액 ({unit})")
    fig.update_yaxes(tickvals=tickvals, ticktext=ticktext)
    fig.update_traces(hovertemplate="%{x} · %{fullData.name}<br>%{y:,.0f}원<extra></extra>")
    return style(fig, 380)


def consumption_diagnostic_chart(frame: pd.DataFrame, target: str = "amt") -> go.Figure:
    """Actual, expected and band all come from one population-tagged handoff."""
    if target not in ("amt", "cnt") or frame["population_scope"].nunique() != 1 or frame["scope"].nunique() != 1:
        raise ValueError("진단 차트는 한 모집단·한 업종 범위만 표시합니다.")
    population = frame["population_scope"].iloc[0]
    label = POPULATION_LABELS[population]
    metric = "이용금액" if target == "amt" else "이용건수"
    unit = "원" if target == "amt" else "건"
    comparable = frame.get("aggregate_scope_complete", pd.Series(True, index=frame.index)).fillna(False).astype(bool)
    valid = frame["prediction_interval_available"].eq(True) & comparable
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=frame["month"], y=frame["lower90_" + target].where(valid), name="90% 하한", mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False, connectgaps=False))
    fig.add_trace(go.Scatter(x=frame["month"], y=frame["upper90_" + target].where(valid), name=f"{label} 90% 예측구간", mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(243,183,91,.20)", connectgaps=False, customdata=frame[["pi_center_" + target]], hovertemplate=f"90% 상한 %{{y:,.0f}}{unit}<br>구간 보정중심 %{{customdata[0]:,.0f}}{unit}<extra></extra>"))
    fig.add_trace(go.Scatter(x=frame["month"], y=frame["expected_" + target].where(comparable), name=f"{label} 구조적 기대{metric}", mode="lines", line=dict(color="#D89A32", width=2, dash="dash"), connectgaps=False))
    fig.add_trace(go.Scatter(x=frame["month"], y=frame["actual_" + target].where(comparable), name=f"{label} {metric}", mode="lines+markers", line=dict(color=PALETTE[0 if target == "amt" else 1], width=3), connectgaps=False))
    if (~comparable).any():
        incomplete = frame.loc[~comparable]
        fig.add_trace(go.Scatter(x=incomplete["month"], y=incomplete["actual_" + target],
                                 name="관측 업종 합계 · 비교 제외", mode="markers",
                                 marker=dict(color="#89958f", size=9, symbol="x"),
                                 customdata=incomplete[["observed_industries", "missing_industries"]],
                                 hovertemplate=f"관측 합계 %{{y:,.0f}}{unit}<br>관측 업종 %{{customdata[0]}}/9<br>미관측: %{{customdata[1]}}<extra></extra>"))
    values = pd.concat((frame["actual_" + target], frame["expected_" + target].where(comparable),
                        frame["upper90_" + target].where(valid))).dropna()
    maximum = float(values.max()) if not values.empty else 0
    ticks, labels, scaled_unit = _axis_ticks(maximum, "money" if target == "amt" else "count")
    fig = style(fig, 360)
    fig.update_layout(yaxis=dict(title=f"{metric} ({scaled_unit})", tickvals=ticks, ticktext=labels), hovermode="x unified", showlegend=True, legend=dict(orientation="h", y=1.2, font=dict(size=10)))
    return fig


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
