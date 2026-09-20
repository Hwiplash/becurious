from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd


HANDOFF_DIR = Path(__file__).resolve().parents[1] / "handoff" / "problem_regions"
DETAIL_PATH = HANDOFF_DIR / "problem_regions.jsonl"


@lru_cache(maxsize=1)
def load_problem_regions() -> dict[str, dict]:
    if not DETAIL_PATH.exists():
        return {}
    records: dict[str, dict] = {}
    with DETAIL_PATH.open(encoding="utf-8") as source:
        for line in source:
            if line.strip():
                record = json.loads(line)
                records[record["region_key"]] = record
    return records


def prediction_band(sido: str, ccg: str, industry: str) -> pd.DataFrame | None:
    """선택 범위의 월별 예측구간 중심과 90% 밴드를 반환한다."""
    if not industry:
        return None
    record = load_problem_regions().get(f"{sido.strip()}|{ccg.strip()}")
    if not record:
        return None
    if industry == "업종 전체":
        rows = [item for item in record.get("monthly", []) if item.get("scope") == "core9"]
    else:
        normalized_industry = industry.replace(" ", "")
        rows = [
            item for item in record.get("monthly", [])
            if item.get("level") == "industry"
            and item.get("industry", "").replace(" ", "") == normalized_industry
        ]
    if not rows:
        return None
    frame = pd.DataFrame(rows)
    frame["month"] = pd.to_datetime(frame["month"], format="%Y%m", errors="coerce")
    center_column = "pi_center_amt" if "pi_center_amt" in frame else "expected_amt"
    for column in [center_column, "lower90_amt", "upper90_amt"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["month", center_column, "lower90_amt", "upper90_amt"]).sort_values("month")
    if frame.empty:
        return None
    frame["expected_amt"] = frame[center_column]
    return frame[["month", "expected_amt", "lower90_amt", "upper90_amt"]].reset_index(drop=True)
