"""Population-safe adapters for the parallel total BC M9 handoff."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

from src.problem_regions import load_problem_regions

HANDOFF_DIR = Path(__file__).resolve().parents[1] / "handoff" / "total_market_problem_regions"
CORE_CODES = ("4004", "4010", "4020", "8001", "8004", "8005", "8006", "8021", "8301")
POPULATION_LABELS = {"all_customer_codes": "전체 BC", "domestic_personal": "내국인 개인 BC"}


@lru_cache(maxsize=1)
def load_total_market_regions() -> dict[str, dict]:
    path = HANDOFF_DIR / "total_market_problem_regions.jsonl"
    if not path.exists():
        return {}
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(record.get("population_scope") != "all_customer_codes" for record in records):
        raise ValueError("전체 상권 handoff의 모집단이 일치하지 않습니다.")
    keys = [record["region_key"] for record in records]
    if len(keys) != len(set(keys)):
        raise ValueError("전체 상권 handoff 지역 키가 중복되었습니다.")
    return dict(zip(keys, records))


def personal_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Domestic personal only. Foreign age records never enter gender/age profiles."""
    if not {"GENDER_CD", "AGE_CD"}.issubset(frame.columns):
        return frame.iloc[0:0].copy()
    return frame[frame["GENDER_CD"].astype(str).isin(["1", "2"]) & frame["AGE_CD"].astype(str).isin(list("123456"))].copy()


def diagnostic_series(sido: str, ccg: str, industry: str, population_scope: str = "all_customer_codes") -> pd.DataFrame | None:
    if population_scope not in POPULATION_LABELS:
        raise ValueError("지원하지 않는 분석 모집단입니다.")
    records = load_total_market_regions() if population_scope == "all_customer_codes" else load_problem_regions()
    record = records.get(f"{sido.strip()}|{ccg.strip()}")
    if not record:
        return None
    rows = [row for row in record.get("monthly", []) if (
        row.get("scope") == "core9" if industry == "업종 전체"
        else row.get("level") == "industry" and row.get("industry", "").replace(" ", "") == industry.replace(" ", "")
    )]
    if not rows:
        return None
    if population_scope == "all_customer_codes" and any(row.get("population_scope") != population_scope for row in rows):
        raise ValueError("월별 실제·기대 모집단이 일치하지 않습니다.")
    frame = pd.DataFrame(rows).copy()
    if industry == "업종 전체":
        observed = {month: set() for month in frame["month"]}
        names = {}
        for row in record.get("monthly", []):
            if row.get("scope") in CORE_CODES:
                names[row["scope"]] = row["industry"]
                if row.get("observed", row.get("data_available", False)):
                    observed[row["month"]].add(row["scope"])
        frame["observed_industries"] = frame["month"].map(lambda month: len(observed[month]))
        frame["missing_industries"] = frame["month"].map(
            lambda month: ", ".join(names.get(code, code) for code in CORE_CODES if code not in observed[month]) or "없음"
        )
        frame["aggregate_scope_complete"] = frame["observed_industries"].eq(len(CORE_CODES))
    else:
        frame["aggregate_scope_complete"] = True
        frame["missing_industries"] = "없음"
    frame["population_scope"] = population_scope
    frame["month"] = pd.to_datetime(frame["month"].astype(str), format="%Y%m", errors="raise")
    for target in ("amt", "cnt"):
        for prefix in ("actual_", "expected_", "pi_center_", "lower90_", "upper90_"):
            column = prefix + target
            frame[column] = pd.to_numeric(frame.get(column), errors="coerce")
    if "prediction_interval_available" not in frame:
        frame["prediction_interval_available"] = frame[["lower90_amt", "upper90_amt", "lower90_cnt", "upper90_cnt"]].notna().all(axis=1)
    if frame["month"].duplicated().any():
        raise ValueError("동일 업종·월의 진단 행이 중복되었습니다.")
    # Keep OOF expected and proper-training interval center distinct.
    return frame.sort_values("month").reset_index(drop=True)


def population_context(sido: str, ccg: str, industry: str) -> dict:
    record = load_total_market_regions().get(f"{sido.strip()}|{ccg.strip()}")
    if not record:
        return {"available": False, "message": "해당 지역의 구조모형 진단 자료가 없습니다."}
    selected = next((item for item in record["industry_summary"] if (
        item["scope"] == "core9" if industry == "업종 전체"
        else item["industry"].replace(" ", "") == industry.replace(" ", "")
    )), None)
    cohorts = record["personal_customer_structure"]
    selected_scope = selected["scope"] if selected else None
    cohort_rows = [item for item in cohorts.get("cohort_summary", []) if item.get("scope") == selected_scope]
    aggregate = diagnostic_series(sido, ccg, "업종 전체")
    incomplete = aggregate.loc[~aggregate["aggregate_scope_complete"]] if aggregate is not None else pd.DataFrame()
    core9_scope = {
        "all_months_complete": aggregate is not None and incomplete.empty,
        "incomplete_months": [
            {"month": row.month.strftime("%Y-%m"), "observed_industries": int(row.observed_industries),
             "missing_industries": row.missing_industries}
            for row in incomplete.itertuples()
        ],
        "interpretation": "미관측 업종은 0원이 아니다. 관측 업종이 9개 미만인 달은 고정된 9업종 총액의 실제·기대 비교와 증감 판단에서 제외한다.",
    }
    return {
        "available": True,
        "population_scope": "all_customer_codes",
        "population_group": "total_market",
        "total_market_status": record["total_market_status"],
        "domestic_personal_status": record["personal_consumption_status"],
        "population_comparison": record["population_comparison"],
        "core9_scope": core9_scope,
        "selected_industry_comparison": selected,
        "nonpersonal_share_amount": (selected or record["population_comparison"])["nonpersonal_share_amount"],
        "foreign_actual_amount": (selected or record["population_comparison"])["foreign_actual_amount"],
        "corporate_actual_amount": (selected or record["population_comparison"])["corporate_actual_amount"],
        "domestic_personal_customer_structure": {"population_scope": "domestic_personal", "cohort_summary": cohort_rows},
        "interpretation_limits": record["interpretation_limits"],
    }
