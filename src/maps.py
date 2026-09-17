from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.data import korean_money_ticks


GEO_DIR = Path(__file__).resolve().parents[1] / "data" / "geo"


def _load_geo(name: str) -> dict:
    return json.loads((GEO_DIR / name).read_text(encoding="utf-8"))


def _layout(fig: go.Figure, max_value: float, height: int = 560) -> go.Figure:
    tickvals, ticktext = korean_money_ticks(max_value, 4)
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=8, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#344054"),
        coloraxis_colorbar=dict(title="매출액", tickvals=tickvals, ticktext=ticktext, thickness=12),
        clickmode="event+select",
    )
    return fig


def sido_map(df: pd.DataFrame) -> go.Figure:
    geo = _load_geo("sido.geojson")
    grouped = df.groupby("SIDO_NM", as_index=False).agg(amt=("amt", "sum"), cnt=("cnt", "sum"))
    grouped["avg_ticket"] = grouped["amt"].div(grouped["cnt"].replace(0, pd.NA)).fillna(0)
    fig = px.choropleth(
        grouped, geojson=geo, locations="SIDO_NM", featureidkey="properties.name", color="amt",
        custom_data=["SIDO_NM", "cnt", "avg_ticket"],
        color_continuous_scale=[[0, "#173653"], [.45, "#167F78"], [1, "#34E0B1"]],
    )
    fig.update_traces(
        marker_line_color="#07111F", marker_line_width=1.2,
        hovertemplate="<b>%{customdata[0]}</b><br>매출 %{z:,.0f}원<br>건수 %{customdata[1]:,.0f}건<br>건당 %{customdata[2]:,.0f}원<extra></extra>",
        selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=.62)),
    )
    return _layout(fig, float(grouped["amt"].max()))


def sigungu_map(df: pd.DataFrame, sido: str) -> go.Figure:
    geo = _load_geo("sigungu.geojson")
    geo["features"] = [feature for feature in geo["features"] if feature["properties"].get("sido") == sido]
    grouped = df.groupby("CCG_NM", as_index=False).agg(amt=("amt", "sum"), cnt=("cnt", "sum"))
    grouped["avg_ticket"] = grouped["amt"].div(grouped["cnt"].replace(0, pd.NA)).fillna(0)
    fig = px.choropleth(
        grouped, geojson=geo, locations="CCG_NM", featureidkey="properties.name", color="amt",
        custom_data=["CCG_NM", "cnt", "avg_ticket"],
        color_continuous_scale=[[0, "#173653"], [.45, "#167F78"], [1, "#34E0B1"]],
    )
    fig.update_traces(
        marker_line_color="#07111F", marker_line_width=1,
        hovertemplate="<b>%{customdata[0]}</b><br>매출 %{z:,.0f}원<br>건수 %{customdata[1]:,.0f}건<br>건당 %{customdata[2]:,.0f}원<extra></extra>",
    )
    return _layout(fig, float(grouped["amt"].max()))


def index_map(df: pd.DataFrame, value: str, title: str, sido: str | None = None) -> go.Figure:
    geo = _load_geo("sigungu.geojson")
    for feature in geo["features"]:
        properties = feature["properties"]
        properties["region_key"] = f"{properties.get('sido')}|{properties.get('name')}"
    if sido:
        geo["features"] = [feature for feature in geo["features"] if feature["properties"].get("sido") == sido]
        frame = df[df["시도"] == sido].copy()
    else:
        frame = df.copy()
    frame["region_key"] = frame["시도"].astype(str) + "|" + frame["시군구"].astype(str)
    midpoint = 100 if frame[value].min() <= 100 <= frame[value].max() else None
    fig = px.choropleth(
        frame, geojson=geo, locations="region_key", featureidkey="properties.region_key", color=value,
        custom_data=["시도", "시군구", value], color_continuous_scale="RdYlGn",
        color_continuous_midpoint=midpoint,
    )
    fig.update_traces(
        marker_line_color="#FFFFFF", marker_line_width=.8,
        hovertemplate=f"<b>%{{customdata[0]}} %{{customdata[1]}}</b><br>{title} %{{customdata[2]:,.1f}}<extra></extra>",
    )
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(
        height=570, margin=dict(l=0, r=0, t=8, b=0), font=dict(color="#344054"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_colorbar=dict(title=title, thickness=12), clickmode="event+select",
    )
    return fig
