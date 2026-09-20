from __future__ import annotations

import unittest

import pandas as pd

from src.analytics import diagnose_scope


class DiagnoseScopeTest(unittest.TestCase):
    def test_national_scope_aggregates_selected_industry_without_region(self) -> None:
        data = pd.DataFrame(
            {
                "SIDO_NM": ["서울", "부산", "서울", "부산"],
                "CCG_NM": ["중구", "중구", "중구", "중구"],
                "TP_BUZ_NM": ["한식", "한식", "한식", "한식"],
                "month": pd.to_datetime(["2026-01-01", "2026-01-01", "2026-02-01", "2026-02-01"]),
                "amt": [100.0, 200.0, 150.0, 300.0],
                "cnt": [10.0, 20.0, 12.0, 24.0],
                "age": ["30대", "40대", "30대", "40대"],
            }
        )
        diagnosis = diagnose_scope(data, "한식")
        self.assertEqual(diagnosis.region, "전국")
        self.assertEqual(diagnosis.industry, "한식")
        self.assertAlmostEqual(diagnosis.sales_change, 0.5)


if __name__ == "__main__":
    unittest.main()
