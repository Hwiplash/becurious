from __future__ import annotations

import unittest

from src.charts import _trend_axis_ticks


class TrendAxisTest(unittest.TestCase):
    def test_narrow_variation_uses_nonzero_axis(self) -> None:
        ticks, _, _, axis_range = _trend_axis_ticks([10_000, 10_200, 10_400], "count")
        self.assertIsNotNone(axis_range)
        self.assertGreater(axis_range[0], 0)
        self.assertTrue(all((right - left) in (100, 200, 500, 1000) for left, right in zip(ticks, ticks[1:])))

    def test_wide_variation_keeps_zero_baseline(self) -> None:
        ticks, _, _, axis_range = _trend_axis_ticks([1_000, 10_000], "count")
        self.assertIsNone(axis_range)
        self.assertEqual(ticks[0], 0)

if __name__ == "__main__":
    unittest.main()
