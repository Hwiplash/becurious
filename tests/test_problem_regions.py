from __future__ import annotations

import unittest

import pandas as pd

from src.charts import monthly_count_trend, monthly_sales_trend
from src.problem_regions import load_problem_regions, prediction_band


class ProblemRegionHandoffTest(unittest.TestCase):
    def test_handoff_has_unique_region_records(self) -> None:
        records = load_problem_regions()
        self.assertEqual(len(records), 251)
        self.assertTrue(all("|" in key for key in records))

    def test_prediction_band_preserves_aggregate_bounds(self) -> None:
        record = next(
            row for row in load_problem_regions().values()
            if row.get("industry_signals")
        )
        evidence = next(
            row for row in record["industry_signals"]
            if row.get("lower90_amt") is not None and row.get("upper90_amt") is not None
        )
        band = prediction_band(record["sido"], record["sigungu"], evidence["industry"])
        self.assertIsNotNone(band)
        assert band is not None
        self.assertEqual(len(band), 6)
        self.assertAlmostEqual(float(band["lower90_amt"].sum()), float(evidence["lower90_amt"]), places=2)
        self.assertAlmostEqual(float(band["upper90_amt"].sum()), float(evidence["upper90_amt"]), places=2)
        self.assertTrue((band["lower90_amt"] <= band["expected_amt"]).all())
        self.assertTrue((band["expected_amt"] <= band["upper90_amt"]).all())

    def test_all_industries_does_not_mix_in_food_aggregate(self) -> None:
        record = next(iter(load_problem_regions().values()))
        self.assertIsNone(prediction_band(record["sido"], record["sigungu"], "업종 전체"))

    def test_sales_and_count_charts_are_separate_without_legends(self) -> None:
        frame = pd.DataFrame({
            "month": pd.to_datetime(["2026-01-01", "2026-02-01"]),
            "amt": [100.0, 120.0],
            "cnt": [10.0, 12.0],
        })
        sales = monthly_sales_trend(frame)
        counts = monthly_count_trend(frame)
        self.assertEqual([trace.name for trace in sales.data], ["매출액"])
        self.assertEqual([trace.name for trace in counts.data], ["이용건수"])
        self.assertFalse(sales.layout.showlegend)
        self.assertFalse(counts.layout.showlegend)


if __name__ == "__main__":
    unittest.main()
