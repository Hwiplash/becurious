from __future__ import annotations

from pathlib import Path
import re

import pandas as pd
import streamlit as st


REQUIRED_COLUMNS = {
    "STRD_YYMM", "SIDO_NM", "CCG_NM", "GENDER_CD", "AGE_CD",
    "TP_BUZ_NO", "TP_BUZ_NM", "amt", "cnt",
}

GENDER_LABELS = {"1": "남성", "2": "여성", "3": "외국인", "X": "미상"}
AGE_LABELS = {
    "1": "20대 이하", "2": "20대", "3": "30대", "4": "40대",
    "5": "50대", "6": "60대 이상", "X": "미상",
}


def default_data_path() -> Path | None:
    candidates = [
        Path("data/raw/ABP_CONTEST_DATA.csv"),
        Path("../ABP_CONTEST_DATA.csv"),
        Path("ABP_CONTEST_DATA.csv"),
    ]
    return next((path for path in candidates if path.exists()), None)


@st.cache_data(show_spinner="소비 데이터를 불러오는 중입니다…")
def load_csv(path: str) -> pd.DataFrame:
    return prepare(pd.read_csv(path, dtype={"STRD_YYMM": str, "GENDER_CD": str, "AGE_CD": str}))


@st.cache_data(show_spinner="업로드한 데이터를 불러오는 중입니다…")
def load_uploaded(raw: bytes) -> pd.DataFrame:
    from io import BytesIO
    return prepare(pd.read_csv(BytesIO(raw), dtype={"STRD_YYMM": str, "GENDER_CD": str, "AGE_CD": str}))


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(column).strip() for column in df.columns]
    # 대회 원본은 금액/건수 컬럼만 소문자이므로 두 표기를 모두 허용한다.
    df = df.rename(columns={"AMT": "amt", "CNT": "cnt", "TPBUZ_NO": "TP_BUZ_NO", "TPBUZ_NM": "TP_BUZ_NM"})
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(sorted(missing))}")

    text_columns = ["STRD_YYMM", "SIDO_NM", "CCG_NM", "GENDER_CD", "AGE_CD", "TP_BUZ_NO", "TP_BUZ_NM"]
    for column in text_columns:
        df[column] = df[column].fillna("X").astype(str).str.strip()
    for column in ["amt", "cnt"]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
    df["TP_BUZ_NM"] = df["TP_BUZ_NM"].str.replace(r"\s+", "", regex=True)
    df["month"] = pd.to_datetime(df["STRD_YYMM"], format="%Y%m", errors="coerce")
    df["gender"] = df["GENDER_CD"].map(GENDER_LABELS).fillna("기타")
    df["age"] = df["AGE_CD"].map(AGE_LABELS).fillna("기타")
    return df.dropna(subset=["month"])


def compact_won(value: float) -> str:
    if abs(value) >= 1_0000_0000_0000:
        return f"{value / 1_0000_0000_0000:,.1f}조원"
    if abs(value) >= 1_0000_0000:
        return f"{value / 1_0000_0000:,.1f}억원"
    if abs(value) >= 1_0000:
        return f"{value / 1_0000:,.0f}만원"
    return f"{value:,.0f}원"


def korean_money_ticks(max_value: float, count: int = 5) -> tuple[list[float], list[str]]:
    if max_value <= 0:
        return [0], ["0원"]
    values = [max_value * index / count for index in range(count + 1)]
    return values, [compact_won(value) for value in values]


def safe_key(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣_-]", "_", value)
