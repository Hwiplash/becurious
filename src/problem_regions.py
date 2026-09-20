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
    """선택 업종의 월별 회귀 기대값과 6개월 90% 범위를 월별 비중으로 배분해 반환한다."""
    if not industry or industry == "업종 전체":
        return None
    record = load_problem_regions().get(f"{sido.strip()}|{ccg.strip()}")
    if not record:
        return None
    evidence = next(
        (item for item in record.get("industry_signals", []) if item.get("industry", "").replace(" ", "") == industry.replace(" ", "")),
        None,
    )
    if not evidence or evidence.get("lower90_amt") is None or evidence.get("upper90_amt") is None:
        return None
    rows = [
        item for item in record.get("monthly", [])
        if item.get("level") == "industry"
        and item.get("industry", "").replace(" ", "") == industry.replace(" ", "")
        and item.get("expected_amt") is not None
    ]
    if not rows:
        return None
    frame = pd.DataFrame(rows)
    frame["month"] = pd.to_datetime(frame["month"], format="%Y%m", errors="coerce")
    frame["expected_amt"] = pd.to_numeric(frame["expected_amt"], errors="coerce")
    frame = frame.dropna(subset=["month", "expected_amt"]).sort_values("month")
    expected_total = float(frame["expected_amt"].sum())
    if frame.empty or expected_total <= 0:
        return None
    frame["lower90_amt"] = frame["expected_amt"] * float(evidence["lower90_amt"]) / expected_total
    frame["upper90_amt"] = frame["expected_amt"] * float(evidence["upper90_amt"]) / expected_total
    return frame[["month", "expected_amt", "lower90_amt", "upper90_amt"]].reset_index(drop=True)
