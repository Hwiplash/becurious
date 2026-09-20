from __future__ import annotations

import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

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


def monthly_trend(df: pd.DataFrame, population: str = "전체 BC카드") -> go.Figure:
    monthly = df.groupby("month", as_index=False).agg(매출액=("amt", "sum"), 이용건수=("cnt", "sum"))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=monthly["month"], y=monthly["매출액"], name=f"{population} 이용금액", mode="lines+markers", line=dict(color=PALETTE[0], width=3), fill="tozeroy", fillcolor="rgba(34,211,167,.10)"))
    fig.add_trace(go.Scatter(x=monthly["month"], y=monthly["이용건수"], name=f"{population} 이용건수", mode="lines+markers", line=dict(color=PALETTE[1], width=2), yaxis="y2"))
    tickvals, ticktext, money_unit = _axis_ticks(float(monthly["매출액"].max()), "money")
    countvals, counttext, count_unit = _axis_ticks(float(monthly["이용건수"].max()), "count")
    fig.update_layout(
        yaxis=dict(title=f"매출액 ({money_unit})", tickvals=tickvals, ticktext=ticktext),
        yaxis2=dict(title=f"이용건수 ({count_unit})", overlaying="y", side="right", tickvals=countvals, ticktext=counttext),
        hovermode="x unified",
    )
    fig = style(fig, 390)
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.2, xanchor="left", x=0),
        margin=dict(l=12, r=12, t=96, b=24),
    )
    return fig


def prediction_trend(monthly: pd.DataFrame, target: str = "amt") -> go.Figure:
    """comparison_monthly의 단일 지역·업종 JSON 행만 차트로 그린다."""
    if target not in ("amt", "cnt"):
        raise ValueError("target must be amt or cnt")
    if (monthly.empty or monthly["region_key"].nunique() != 1
            or monthly["scope"].nunique() != 1
            or not monthly["population"].eq("내국인 개인 BC").all()):
        raise ValueError("예측구간은 동일한 지역·업종·개인 모집단만 비교할 수 있습니다.")
    frame = monthly.sort_values("month").copy()
    # 생략된 월도 공백으로 표시하여 실제선을 연결하지 않는다.
    frame = frame.set_index("month").reindex(pd.date_range(frame["month"].min(), frame["month"].max(), freq="MS"))
    band = frame["prediction_interval_available"].eq(True)
    actual = frame[f"actual_{target}"].where(frame["data_available"].eq(True))
    lower = frame[f"lower90_{target}"].where(band)
    upper = frame[f"upper90_{target}"].where(band)
    center = frame[f"pi_center_{target}"].where(band)
    label, unit = ("금액", "원") if target == "amt" else ("건수", "건")
    warnings = []
    for _, row in frame.iterrows():
        notes = [str(row["band_message"])] if pd.notna(row.get("band_message")) else []
        if pd.notna(row.get(f"calibration_ok_{target}")) and not row[f"calibration_ok_{target}"]:
            notes.append("보정 주의: 이 비교집단에서 조건부 정확도 미확인")
        if pd.notna(row.get("extrapolation_warning")) and row["extrapolation_warning"]:
            notes.append("일부 지역 구조값이 학습자료 범위를 벗어납니다.")
        warnings.append("<br>".join(notes))
    hover = f"%{{x|%Y년 %m월}}<br>%{{y:,.0f}}{unit}<br>%{{customdata}}<extra>%{{fullData.name}}</extra>"
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=frame.index, y=lower, name="90% 예측구간 하단", mode="lines", line=dict(width=0), showlegend=False, connectgaps=False, customdata=warnings, hovertemplate=hover))
    fig.add_trace(go.Scatter(x=frame.index, y=upper, name="내국인 개인 소비의 90% 예측구간", mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(77,163,255,.18)", connectgaps=False, customdata=warnings, hovertemplate=hover))
    fig.add_trace(go.Scatter(x=frame.index, y=center, name=f"지역 구조를 고려한 기대{label} (구간 중심)", mode="lines", line=dict(color=PALETTE[1], dash="dash"), connectgaps=False, customdata=warnings, hovertemplate=hover))
    fig.add_trace(go.Scatter(x=frame.index, y=frame[f"expected_{target}"], name=f"진단 비율 기준 기대{label} (반복 평균)", mode="lines", line=dict(color="#667085", dash="dot"), visible="legendonly", connectgaps=False, customdata=warnings, hovertemplate=hover))
    fig.add_trace(go.Scatter(x=frame.index, y=actual, name=f"내국인 개인 BC 이용{label}", mode="lines+markers", line=dict(color=PALETTE[0], width=3), connectgaps=False, customdata=warnings, hovertemplate=hover))
    maximum = pd.concat([actual, upper, center]).max()
    ticks, ticktext, axis_unit = _axis_ticks(float(maximum) if pd.notna(maximum) else 0, "money" if target == "amt" else "count")
    fig = style(fig, 440)
    fig.update_layout(yaxis=dict(title=f"이용{label} ({axis_unit})", tickvals=ticks, ticktext=ticktext), hovermode="x unified", legend=dict(orientation="h", yanchor="top", y=-.18), margin=dict(l=12, r=12, t=20, b=125))
    fig.update_xaxes(dtick="M1", tickformat="%m월")
    return fig


def industry_bar(df: pd.DataFrame, n: int = 10) -> go.Figure:
    grouped = df.groupby("TP_BUZ_NM", as_index=False).agg(매출액=("amt", "sum")).nlargest(n, "매출액").sort_values("매출액")
    fig = px.bar(grouped, x="매출액", y="TP_BUZ_NM", orientation="h", color="매출액", color_continuous_scale=[[0, "#176260"], [1, "#34E0B1"]])
    tickvals, ticktext, unit = _axis_ticks(float(grouped["매출액"].max()), "money")
    fig.update_layout(coloraxis_showscale=False, xaxis_title=f"매출액 ({unit})", yaxis_title=None)
    fig.update_xaxes(tickvals=tickvals, ticktext=ticktext)
    fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:,.0f}원<extra></extra>")
    return style(fig, 380)


def segment_chart(df: pd.DataFrame) -> go.Figure:
    grouped = df.groupby(["age", "gender"], as_index=False).agg(매출액=("amt", "sum"))
    age_order = ["20대 이하", "20대", "30대", "40대", "50대", "60대 이상", "미상", "기타"]
    fig = px.bar(grouped, x="age", y="매출액", color="gender", barmode="group", color_discrete_sequence=PALETTE, category_orders={"age": age_order})
    tickvals, ticktext, unit = _axis_ticks(float(grouped["매출액"].max()), "money")
    fig.update_layout(xaxis_title=None, yaxis_title=f"매출액 ({unit})")
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
