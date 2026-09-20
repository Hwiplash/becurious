from __future__ import annotations

from pathlib import Path
import json
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

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE9 = {
    "4004": "대형할인점", "4010": "편의점", "4020": "슈퍼마켓",
    "8001": "일반한식", "8004": "일식회집", "8005": "중국음식",
    "8006": "서양음식", "8021": "스넥", "8301": "제과점",
}
PERSONAL_POPULATION = "내국인 개인 BC"
POPULATION_NOTE = (
    "실제값과 기대구간은 성별·연령이 확인되는 내국인 개인 결제를 동일하게 집계해 비교합니다. "
    "외국인 및 법인·미상 결제는 이 비교에서 제외됩니다."
)


def normalize_code(values: pd.Series) -> pd.Series:
    """CSV 문자열과 숫자형 코드(1, 1.0, ' 1 ')를 같은 코드로 읽는다."""
    return values.astype("string").str.strip().str.upper().str.replace(r"^(\d+)\.0+$", r"\1", regex=True)


def personal_consumption(df: pd.DataFrame) -> pd.DataFrame:
    """M9의 고객·업종·기간 범위. 관측 행만 남기며 결측 셀을 만들지 않는다."""
    return df.loc[
        normalize_code(df["GENDER_CD"]).isin(["1", "2"])
        & normalize_code(df["AGE_CD"]).isin(list("123456"))
        & normalize_code(df["TP_BUZ_NO"]).isin(CORE9)
        & normalize_code(df["STRD_YYMM"]).isin([f"20260{i}" for i in range(1, 7)])
    ].copy()


@st.cache_data(show_spinner=False)
def load_problem_regions(path: str | None = None) -> dict[str, dict]:
    source = Path(path) if path else REPO_ROOT / "handoff/problem_regions/problem_regions.jsonl"
    regions = {}
    with source.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            region = json.loads(line)
            key = region["region_key"]
            if key != f"{region['sido']}|{region['sigungu']}" or key in regions:
                raise ValueError(f"문제지역 키 중복 또는 불일치: {key}")
            regions[key] = region
    return regions


def comparison_monthly(regions: dict[str, dict], sido: str, ccg: str, scope: str = "core9") -> pd.DataFrame:
    """하나의 JSON 지역×업종 시계열을 그대로 사용한다. 원본 전 코드로 대체하지 않는다."""
    if scope not in CORE9 and scope != "core9":
        raise ValueError(f"M9 분석 범위 밖 업종: {scope}")
    key = f"{sido.strip()}|{ccg.strip()}"
    region = regions.get(key)
    if region is None:
        return pd.DataFrame()
    frame = pd.DataFrame([row for row in region["monthly"] if row["scope"] == scope])
    if frame.empty:
        return frame
    frame["month"] = pd.to_datetime(frame["month"].astype(str), format="%Y%m", errors="raise")
    if frame["month"].duplicated().any():
        raise ValueError(f"월별 키 중복: {key} / {scope}")
    if (frame.loc[~frame["data_available"], ["actual_amt", "actual_cnt"]].notna().any().any()):
        raise ValueError(f"미관측 실제값이 null이 아닙니다: {key} / {scope}")
    frame["region_key"] = key
    frame["population"] = PERSONAL_POPULATION
    return frame.sort_values("month").reset_index(drop=True)


def comparison_details(monthly: pd.DataFrame) -> pd.DataFrame:
    """비율·경로는 JSON 권위값을 유지하고, 없는 차이·객단가·증감률만 같은 행에서 파생한다."""
    frame = monthly.copy()
    for target in ("amt", "cnt"):
        actual = pd.to_numeric(frame[f"actual_{target}"], errors="coerce")
        expected = pd.to_numeric(frame[f"expected_{target}"], errors="coerce")
        ratio = frame.get(f"I_{target}", frame.get(f"ratio_{target}"))
        frame[f"ratio_{target}"] = ratio if ratio is not None else actual.div(expected.where(expected.ne(0)))
        if f"gap_{target}" not in frame:
            frame[f"gap_{target}"] = actual - expected
        # 미관측 월을 건너뛴 전월비와 앞선 값으로 채우기를 금지한다.
        previous = actual.shift()
        adjacent = frame["month"].dt.to_period("M").astype("int64").diff().eq(1)
        frame[f"mom_{target}"] = actual.div(previous.where(previous.ne(0))).sub(1).where(adjacent)
        band_available = frame["prediction_interval_available"] & frame["data_available"]
        for side, operator in (("below", "lt"), ("above", "gt")):
            field = f"{side}90_{target}"
            if field not in frame:
                bound = pd.to_numeric(frame[f"{'lower' if side == 'below' else 'upper'}90_{target}"], errors="coerce")
                frame[field] = getattr(actual, operator)(bound).astype("boolean").where(band_available & bound.notna())
    count = pd.to_numeric(frame["actual_cnt"], errors="coerce")
    frame["actual_ticket"] = pd.to_numeric(frame["actual_amt"], errors="coerce").div(count.where(count.ne(0)))
    expected_count = pd.to_numeric(frame["expected_cnt"], errors="coerce")
    frame["expected_ticket"] = pd.to_numeric(frame["expected_amt"], errors="coerce").div(expected_count.where(expected_count.ne(0)))
    return frame


def default_data_path() -> Path | None:
    candidates = [
        REPO_ROOT / "data/raw/ABP_CONTEST_DATA.csv",
        REPO_ROOT.parent / "data/ABP_CONTEST_DATA.csv",
        Path("data/raw/ABP_CONTEST_DATA.csv"),
        Path("../ABP_CONTEST_DATA.csv"),
        Path("ABP_CONTEST_DATA.csv"),
    ]
    return next((path for path in candidates if path.exists()), None)


def default_indices_path() -> Path | None:
    candidates = [
        Path("data/raw/regional_indices_rank_final_v2_20260913.xlsx"),
        Path("../regional_indices_rank_final_v2_20260913.xlsx"),
        Path("regional_indices_rank_final_v2_20260913.xlsx"),
    ]
    return next((path for path in candidates if path.exists()), None)


@st.cache_data(show_spinner="상권 지수를 불러오는 중입니다…")
def load_indices(path: str) -> dict[str, pd.DataFrame]:
    sheets = {
        "지역지수": ("지역별지수", 3),
        "프리미엄": ("지역별프리미엄", 3),
        "인구보정": ("202606인구보정지수", 0),
        "소비유형": ("202606업종별인구보정", 0),
        "지역순위": ("지역총량핵심지수순위", 0),
        "업종순위": ("업종별지역순위", 0),
    }
    result = {}
    for key, (sheet, header) in sheets.items():
        frame = pd.read_excel(path, sheet_name=sheet, header=header)
        frame.columns = [str(column).strip() for column in frame.columns]
        for column in ["시도", "시군구", "업종", "소비유형"]:
            if column in frame:
                frame[column] = frame[column].astype(str).str.strip()
        if "업종" in frame:
            frame["업종"] = frame["업종"].str.replace(r"\s+", "", regex=True)
        result[key] = frame
    return result


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
    for column in ["STRD_YYMM", "GENDER_CD", "AGE_CD", "TP_BUZ_NO"]:
        df[column] = normalize_code(df[column])
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
