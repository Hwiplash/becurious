"""Regression checks for missing contest-period endpoints and aggregate scope."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.analytics import diagnose_region
from src.charts import consumption_diagnostic_chart, performance_change_compare
from src.dashboard_components import summary_metrics
from src.total_market import diagnostic_series, population_context


REPO = Path(__file__).resolve().parents[1]


class PeriodChangeTests(unittest.TestCase):
    def test_missing_june_and_one_month_are_unavailable_everywhere(self):
        frame = pd.DataFrame({
            "SIDO_NM": ["전북특별자치도"] * 3,
            "CCG_NM": ["임실군"] * 3,
            "TP_BUZ_NM": ["일식회집"] * 3,
            "TP_BUZ_NO": ["8001"] * 3,
            "month": pd.to_datetime(["2026-01-01", "2026-04-01", "2026-05-01"]),
            "amt": [100.0, 130.0, 150.0],
            "cnt": [10.0, 13.0, 15.0],
            "GENDER_CD": ["1"] * 3,
            "AGE_CD": ["2"] * 3,
            "age": ["20대"] * 3,
        })
        self.assertIsNone(summary_metrics(frame)[3])
        figure = performance_change_compare(frame, "일식회집", "임실군 전체")
        self.assertTrue(all(value is None for trace in figure.data for value in trace.y))
        self.assertEqual(sum(annotation.text == "산출 불가" for annotation in figure.layout.annotations), 6)
        with patch("src.analytics.population_context", return_value={}):
            diagnosis = diagnose_region(frame, "전북특별자치도", "임실군", "일식회집")
        self.assertIsNone(diagnosis.sales_change)
        self.assertIsNone(diagnosis.transaction_change)
        self.assertIsNone(diagnosis.ticket_change)
        self.assertFalse(any("0.0%" in item for item in diagnosis.pain_points + diagnosis.advantages))

        one_month = frame.iloc[[2]].copy()
        self.assertIsNone(summary_metrics(one_month)[3])

    def test_core9_missing_industry_is_not_compared_with_full_scope(self):
        frame = diagnostic_series("인천광역시", "옹진군", "업종 전체")
        self.assertIsNotNone(frame)
        self.assertEqual(frame["observed_industries"].tolist(), [9, 9, 9, 9, 8, 8])
        self.assertTrue(frame.loc[4:, "missing_industries"].str.contains("대형할인점").all())
        chart = consumption_diagnostic_chart(frame, "amt")
        for trace in chart.data[:4]:
            self.assertTrue(np.isnan(np.asarray(trace.y, float)[4:]).all())
        np.testing.assert_allclose(np.asarray(chart.data[4].y, float), frame.loc[4:, "actual_amt"])
        context = population_context("인천광역시", "옹진군", "업종 전체")
        self.assertFalse(context["core9_scope"]["all_months_complete"])
        self.assertEqual([row["month"] for row in context["core9_scope"]["incomplete_months"]], ["2026-05", "2026-06"])

    def test_streamlit_shows_unavailable_rate_and_scope_warning(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(REPO / "app.py"), default_timeout=90)
        app.session_state["region_view"] = "local"
        app.session_state["selected_sido"] = "인천광역시"
        app.session_state["selected_ccg"] = "옹진군"
        app.run()
        self.assertEqual(len(app.exception), 0, str(app.exception))
        self.assertTrue(any("대형할인점" in warning.value and "8/9" in warning.value for warning in app.warning))
        self.assertTrue(any(metric.label == "1월 → 6월 변화" and metric.value == "산출 불가" for metric in app.metric))
        app.selectbox(key="region_industry_filter").set_value("대형할인점").run()
        self.assertEqual(len(app.exception), 0, str(app.exception))
        self.assertTrue(any(metric.label == "1월 → 6월 변화" and metric.value == "산출 불가" for metric in app.metric))


if __name__ == "__main__":
    unittest.main()
