from __future__ import annotations

import unittest

import pandas as pd

from src.dashboard_components import industry_index_snapshot, signal_items


class SignalItemsTest(unittest.TestCase):
    def test_signals_explain_meaning_without_raw_percentages_or_index_values(self) -> None:
        frame = pd.DataFrame(
            {
                "month": ["202601", "202602"],
                "amt": [100.0, 120.0],
                "cnt": [10.0, 11.0],
                "TP_BUZ_NM": ["한식", "한식"],
            }
        )
        strengths, weaknesses = signal_items(
            frame,
            {"premium": 110.0, "activity": 90.0, "diversity": 105.0, "population_intensity": 95.0},
        )
        text = " ".join([*strengths, *weaknesses])
        self.assertIn("%", text)
        self.assertIn("110.0", text)
        self.assertIn("90.0", text)
        self.assertIn("소비 규모", text)
        self.assertIn("고객 유입", text)

    def test_industry_index_uses_average_industry_as_100(self) -> None:
        data = pd.DataFrame(
            {
                "TP_BUZ_NM": ["한식", "한식", "제과점", "제과점"],
                "amt": [150.0, 150.0, 50.0, 50.0],
                "cnt": [15.0, 15.0, 10.0, 10.0],
            }
        )
        snapshot = industry_index_snapshot(data, "한식")
        self.assertEqual(snapshot["scope"], "industry")
        self.assertEqual(snapshot["scale"], 150.0)
        self.assertEqual(snapshot["activity"], 120.0)


if __name__ == "__main__":
    unittest.main()
