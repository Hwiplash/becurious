from __future__ import annotations

import unittest

import pandas as pd

from src.charts import performance_change_compare


class PerformanceCompareChartTest(unittest.TestCase):
    def test_compares_selected_industry_with_region(self) -> None:
        frame = pd.DataFrame({
            "month": pd.to_datetime(["2026-01-01", "2026-06-01"] * 2),
            "TP_BUZ_NM": ["제과점", "제과점", "일반한식", "일반한식"],
            "amt": [100.0, 150.0, 300.0, 330.0],
            "cnt": [10.0, 12.0, 30.0, 33.0],
        })
        figure = performance_change_compare(frame, "제과점", "의령군 전체")
        self.assertEqual([trace.name for trace in figure.data], ["제과점", "의령군 전체"])
        self.assertEqual(list(figure.data[0].x), ["매출액", "이용건수", "건당결제"])
        self.assertAlmostEqual(float(figure.data[0].y[0]), 0.5)
        self.assertAlmostEqual(float(figure.data[0].y[1]), 0.2)


if __name__ == "__main__":
    unittest.main()
