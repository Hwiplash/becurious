from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.total_market import diagnostic_series, load_total_market_regions, personal_rows, population_context, HANDOFF_DIR
from src.problem_regions import load_problem_regions
from src.charts import consumption_diagnostic_chart, segment_chart

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO.parent


class TotalMarketTests(unittest.TestCase):
    def test_11_12_all_total_actual_expected_chart_traces_match_json(self):
        """Check all adapter values, plus representative complete and incomplete charts."""
        records = load_total_market_regions()
        self.assertEqual(len(records), 251)
        count = 0
        plotted = 0
        first_region = next(iter(records.values()))["region_key"]
        for record in records.values():
            for scope in ["core9", "4004", "4010", "4020", "8001", "8004", "8005", "8006", "8021", "8301"]:
                rows = [r for r in record["monthly"] if r["scope"] == scope]
                industry = "업종 전체" if scope == "core9" else rows[0]["industry"]
                frame = diagnostic_series(record["sido"], record["sigungu"], industry)
                self.assertIsNotNone(frame)
                self.assertEqual(len(frame), 6)
                for target in ["amt", "cnt"]:
                    for column in ["lower90_" + target, "upper90_" + target, "expected_" + target, "actual_" + target]:
                        expected = np.array([np.nan if r.get(column) is None else r[column] for r in rows], float)
                        np.testing.assert_allclose(frame[column].to_numpy(float), expected, rtol=1e-12, equal_nan=True)
                    if record["region_key"] not in (first_region, "인천광역시|옹진군"):
                        count += 1
                        continue
                    figure = consumption_diagnostic_chart(frame, target)
                    for trace, column in [(0, "lower90_" + target), (1, "upper90_" + target), (2, "expected_" + target), (3, "actual_" + target)]:
                        expected = np.array([np.nan if r.get(column) is None else r[column] for r in rows], float)
                        if scope == "core9":
                            expected[~frame["aggregate_scope_complete"].to_numpy()] = np.nan
                        np.testing.assert_allclose(np.asarray(figure.data[trace].y, float), expected, rtol=1e-12, equal_nan=True)
                    if scope == "core9" and not frame["aggregate_scope_complete"].all():
                        incomplete = frame.loc[~frame["aggregate_scope_complete"]]
                        np.testing.assert_allclose(np.asarray(figure.data[4].y, float), incomplete["actual_" + target], rtol=1e-12)
                        self.assertIn("비교 제외", figure.data[4].name)
                    plotted += 1
                    count += 1
        self.assertEqual(count, 5020)
        self.assertEqual(plotted, 40)

    def test_personal_series_preserves_personal_actual_expected_and_center(self):
        for record in load_problem_regions().values():
            frame = diagnostic_series(record["sido"], record["sigungu"], "업종 전체", "domestic_personal")
            rows = [r for r in record["monthly"] if r["scope"] == "core9"]
            self.assertIsNotNone(frame)
            for field in ["actual_amt", "expected_amt", "pi_center_amt", "actual_cnt", "expected_cnt"]:
                np.testing.assert_allclose(frame[field], [r[field] for r in rows], rtol=1e-12)
            self.assertTrue(frame.population_scope.eq("domestic_personal").all())

    def test_customer_composition_excludes_foreign_and_corporate(self):
        frame = pd.DataFrame({"GENDER_CD": ["1", "2", "3", "x"], "AGE_CD": ["2", "3", "2", "x"], "age": ["20대", "30대", "20대", "연령 미적용"], "gender": ["내국인 남성", "내국인 여성", "외국인", "법인"], "amt": [10, 20, 300, 400], "cnt": [1, 2, 30, 40]})
        self.assertEqual(personal_rows(frame).amt.sum(), 30)
        fig = segment_chart(frame)
        self.assertEqual(sum(sum(trace.y) for trace in fig.data), 30)
        self.assertEqual({trace.name for trace in fig.data}, {"내국인 남성", "내국인 여성"})

    def test_rag_has_separate_populations_and_limits(self):
        for record in load_total_market_regions().values():
            c = population_context(record["sido"], record["sigungu"], "업종 전체")
            for key in ["total_market_status", "domestic_personal_status", "population_comparison", "nonpersonal_share_amount", "foreign_actual_amount", "corporate_actual_amount", "domestic_personal_customer_structure", "interpretation_limits"]:
                self.assertIn(key, c)
            self.assertEqual(c["domestic_personal_customer_structure"]["population_scope"], "domestic_personal")
        self.assertNotIn("Tier ", (HANDOFF_DIR / "total_market_problem_regions.jsonl").read_text(encoding="utf-8"))
        self.assertNotIn("F1_food_wide_low", (HANDOFF_DIR / "total_market_problem_regions.jsonl").read_text(encoding="utf-8"))

    def test_mixed_population_chart_is_rejected(self):
        r = next(iter(load_total_market_regions().values()))
        f = diagnostic_series(r["sido"], r["sigungu"], "업종 전체")
        f.loc[0, "population_scope"] = "domestic_personal"
        with self.assertRaises(ValueError):
            consumption_diagnostic_chart(f)

    def test_bad_workbook_sheet_is_not_loaded(self):
        from src.data import load_indices
        load_indices.clear()
        with patch("src.data.pd.read_excel", return_value=pd.DataFrame({"시도": []})) as reader:
            result = load_indices("test-sheet-contract.xlsx")
        sheets = [c.kwargs["sheet_name"] for c in reader.call_args_list]
        self.assertNotIn("202606업종별인구보정", sheets)
        self.assertIn("202606인구보정지수", sheets)
        self.assertNotIn("소비유형", result)
        load_indices.clear()

    def test_streamlit_total_default_and_personal_switch(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(REPO / "app.py"), default_timeout=90)
        app.session_state["region_view"] = "local"
        app.session_state["selected_sido"] = "서울특별시"
        app.session_state["selected_ccg"] = "중구"
        app.run()
        self.assertEqual(len(app.exception), 0, str(app.exception))
        self.assertEqual(len(app.error), 0, str(app.error))
        self.assertEqual(app.radio(key="local_population_scope").value, "전체 상권")
        self.assertTrue(any("전체 상권:" in msg.value for msg in app.info))
        app.radio(key="local_population_scope").set_value("내국인 개인").run()
        self.assertEqual(len(app.exception), 0, str(app.exception))
        self.assertEqual(len(app.error), 0, str(app.error))
        self.assertTrue(any("내국인 개인 BC" in msg.value for msg in app.markdown))


if __name__ == "__main__":
    unittest.main()
