"""개인 모집단 회귀검증. 저장된 JSON/원본은 읽기만 한다.

저장소 루트에서 .venv/Scripts/python.exe -B -m unittest discover -s tests -p test_population.py -v
BC 원본은 BC_RAW_PATH, 서비스 JSONL은 BC_SERVICE_PATH로 지정 가능하다.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.charts import prediction_trend
from src.data import (CORE9, REPO_ROOT, comparison_details, comparison_monthly,
                      default_data_path, load_problem_regions, normalize_code,
                      personal_consumption, prepare)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PopulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_path = Path(os.environ.get("BC_RAW_PATH", default_data_path() or "missing.csv"))
        cls.service_path = Path(os.environ.get("BC_SERVICE_PATH", REPO_ROOT.parent / "analysis/service_sigungu_payload/json/sigungu_service_payload.jsonl"))
        cls.handoff_path = REPO_ROOT / "handoff/problem_regions/problem_regions.jsonl"
        cls.protected = [cls.raw_path, cls.service_path, *cls.handoff_path.parent.glob("*.json*"),
                         *cls.service_path.parent.parent.glob("tables/*.csv")]
        cls.hashes = {str(p): digest(p) for p in cls.protected}
        cls.regions = load_problem_regions()
        cls.serialized = json.dumps(cls.regions, ensure_ascii=False, sort_keys=True)
        # 원본 재집계는 UI 필터를 호출하지 않아 독립적으로 검증한다.
        cls.raw = pd.read_csv(cls.raw_path, dtype={"GENDER_CD": str, "AGE_CD": str, "TP_BUZ_NO": str, "STRD_YYMM": str})
        raw = cls.raw
        cls.personal = raw.loc[raw.GENDER_CD.isin(["1", "2"]) & raw.AGE_CD.isin(list("123456")) & raw.TP_BUZ_NO.isin(CORE9)].copy()
        cls.personal["region_key"] = cls.personal.SIDO_NM + "|" + cls.personal.CCG_NM
        cls.raw_industry = cls.personal.groupby(["region_key", "TP_BUZ_NO", "STRD_YYMM"])[["amt", "cnt"]].sum(min_count=1).rename_axis(["region_key", "scope", "month"])
        cls.raw_core9 = cls.personal.groupby(["region_key", "STRD_YYMM"])[["amt", "cnt"]].sum(min_count=1).rename_axis(["region_key", "month"])
        cls.monthly = pd.DataFrame([dict(row, region_key=key) for key, region in cls.regions.items() for row in region["monthly"]])
        cls.service = [json.loads(line) for line in cls.service_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    @classmethod
    def tearDownClass(cls):
        if {str(p): digest(p) for p in cls.protected} != cls.hashes:
            raise AssertionError("원본 또는 분석/전달 산출물이 변경됐습니다.")
        if json.dumps(cls.regions, ensure_ascii=False, sort_keys=True) != cls.serialized:
            raise AssertionError("UI가 읽은 JSON의 기대값·구간·후보 판정이 변형됐습니다.")

    def assertNumeric(self, a, b, count=False):
        # 직렬화된 OOF 실제값의 부동소수점 오차만 허용(금액 0.01원, 건수 0.00001건).
        np.testing.assert_allclose(np.asarray(a, dtype=float), np.asarray(b, dtype=float), rtol=0, atol=1e-5 if count else .01, equal_nan=True)

    def check_raw_values(self, frame):
        frame = frame.copy()
        frame["month"] = frame["month"].astype(str)
        parts = []
        for scope, rows in frame.groupby("scope"):
            if scope == "core9":
                raw = self.raw_core9.reset_index()
            elif scope in CORE9:
                raw = self.raw_industry.xs(scope, level="scope").reset_index()
            else:
                # 외식 합계는 해당 객체의 food_scope(food5/food6) 구성으로 검증한다.
                self.assertIn(scope, ("food6", "food5_no_japanese"))
                codes = [code for code in CORE9 if code.startswith("8") and (scope != "food5_no_japanese" or code != "8004")]
                raw = self.personal[self.personal.TP_BUZ_NO.isin(codes)].groupby(["region_key", "STRD_YYMM"])[["amt", "cnt"]].sum(min_count=1).rename_axis(["region_key", "month"]).reset_index()
            z = rows.merge(raw, on=["region_key", "month"], how="left", validate="one_to_one", indicator=True)
            for target in ("amt", "cnt"):
                available = z[f"actual_{target}"].notna()
                self.assertTrue(z.loc[available, "_merge"].eq("both").all())
                self.assertNumeric(z.loc[available, f"actual_{target}"], z.loc[available, target], target == "cnt")
            parts.append(z)
        return pd.concat(parts, ignore_index=True)

    def test_all_handoff_monthly_cells_against_raw(self):
        self.assertEqual(len(self.monthly), 16566)
        self.assertFalse(self.monthly.duplicated(["region_key", "scope", "month"]).any())
        z = self.check_raw_values(self.monthly)
        individual = z.scope.isin(CORE9)
        self.assertTrue(z.loc[individual & ~z.data_available, ["actual_amt", "actual_cnt", "amt", "cnt"]].isna().all().all())
        # 반대 방향도 검사하여 사용 가능한 원본 셀이 JSON에서 누락되지 않았는지 확인.
        raw = self.raw_industry.reset_index()
        raw = raw[raw.region_key.isin(self.regions)]
        joined = raw.merge(self.monthly.loc[self.monthly.scope.isin(CORE9), ["region_key", "scope", "month", "data_available"]], on=["region_key", "scope", "month"], how="left", validate="one_to_one")
        self.assertTrue(joined.data_available.eq(True).all())

    def test_service_monthly_cells_against_raw(self):
        frame = pd.DataFrame([dict(row, region_key=row["sido"] + "|" + row["sigungu"]) for region in self.service for row in region["monthly"]])
        self.assertEqual(len(frame), 15060)
        self.check_raw_values(frame)
        self.assertTrue(frame.loc[~frame.data_available, ["actual_amt", "actual_cnt"]].isna().all().all())
        handoff = self.monthly.copy()
        handoff["month"] = handoff["month"].astype(str)
        frame["month"] = frame["month"].astype(str)
        z = frame.loc[frame.data_available].merge(handoff, on=["region_key", "scope", "month"], suffixes=("_service", "_handoff"), validate="one_to_one")
        for field in ["actual_amt", "actual_cnt", "expected_amt", "expected_cnt"]:
            self.assertNumeric(z[field + "_service"], z[field + "_handoff"], field.endswith("cnt"))

    def test_core9_equals_observed_personal_industry_sum(self):
        industries = self.monthly[self.monthly.scope.isin(CORE9)]
        sums = industries.groupby(["region_key", "month"])[["actual_amt", "actual_cnt"]].sum(min_count=1)
        core = self.monthly[self.monthly.scope.eq("core9")].set_index(["region_key", "month"]).sort_index()
        for target in ["amt", "cnt"]:
            self.assertNumeric(core[f"actual_{target}"], sums.reindex(core.index)[f"actual_{target}"], target == "cnt")

    def test_every_region_industry_selector_and_json_fields(self):
        for key, region in self.regions.items():
            for scope in ["core9", *CORE9]:
                with self.subTest(region=key, scope=scope):
                    monthly = comparison_monthly(self.regions, region["sido"], region["sigungu"], scope)
                    self.assertEqual(len(monthly), 6)
                    self.assertEqual(set(monthly.region_key), {key})
                    self.assertEqual(set(monthly.scope), {scope})
                    details = comparison_details(monthly)
                    source = pd.DataFrame([row for row in region["monthly"] if row["scope"] == scope]).sort_values("month")
                    for target in ("amt", "cnt"):
                        for field in (f"actual_{target}", f"expected_{target}", f"pi_center_{target}", f"lower90_{target}", f"upper90_{target}", f"below90_{target}"):
                            self.assertNumeric(details[field], monthly[field], target == "cnt")
                        self.assertNumeric(details[f"ratio_{target}"], source[f"I_{target}"], True)
                        self.assertNumeric(details[f"gap_{target}"], source[f"actual_{target}"] - source[f"expected_{target}"], target == "cnt")
                    self.assertEqual(details.amount_count_ticket_path.tolist(), source.amount_count_ticket_path.tolist())
                    self.assertNumeric(details.ticket_ratio, source.ticket_ratio, True)

    def test_code_normalization_and_excluded_customers(self):
        rows = []
        for gender, age, industry, expected in [(1, 1, 8001, True), (2.0, 6.0, 8301.0, True), (" 1.0 ", " 3 ", "4010", True), ("3", "1", "8001", False), (" x ", " X ", "8001", False), ("1", "x", "8001", False), ("2", "6", "8002", False)]:
            rows.append(dict(STRD_YYMM=202601.0, SIDO_NM="시도", CCG_NM="지역", GENDER_CD=gender, AGE_CD=age, TP_BUZ_NO=industry, TP_BUZ_NM="업종", amt=10 if expected else 1000000, cnt=1 if expected else 100000, expected=expected))
        prepared = prepare(pd.DataFrame(rows))
        actual = personal_consumption(prepared)
        self.assertEqual(len(actual), 3)
        self.assertEqual(actual.amt.sum(), 30)
        self.assertEqual(actual.cnt.sum(), 3)
        self.assertEqual(normalize_code(pd.Series(["x", " X ", 1., " 2.0 "])).tolist(), ["X", "X", "1", "2"])
        selected = personal_consumption(prepare(self.raw.copy()))
        self.assertEqual(selected.amt.sum(), self.personal.amt.sum())
        self.assertEqual(selected.cnt.sum(), self.personal.cnt.sum())

    def test_chart_gaps_bands_and_missing_month_changes(self):
        examples = [("강원특별자치도", "고성군", "8301"), ("경상남도", "고성군", "8001")]
        partial = self.monthly[self.monthly.band_status.eq("partial_observation_inference") & self.monthly.scope.isin(CORE9)].iloc[0]
        examples.append((*partial.region_key.split("|"), partial.scope))
        for sido, ccg, scope in examples:
            monthly = comparison_monthly(self.regions, sido, ccg, scope)
            for target in ("amt", "cnt"):
                fig = prediction_trend(monthly, target)
                self.assertNumeric(fig.data[-1].y, monthly[f"actual_{target}"], target == "cnt")
                for trace, field in [(0, "lower90"), (1, "upper90"), (2, "pi_center")]:
                    self.assertNumeric(fig.data[trace].y, monthly[f"{field}_{target}"].where(monthly.prediction_interval_available), target == "cnt")
                self.assertTrue(all(trace.connectgaps is False for trace in fig.data))
        synthetic = copy.deepcopy(self.regions)
        region = synthetic["강원특별자치도|고성군"]
        for row in region["monthly"]:
            if row["scope"] == "8301" and row["month"] == "202602":
                row.update(actual_amt=None, actual_cnt=None, data_available=False)
        frame = comparison_monthly(synthetic, "강원특별자치도", "고성군", "8301")
        detail = comparison_details(frame)
        self.assertTrue(detail.loc[[1, 2], ["mom_amt", "mom_cnt"]].isna().all().all())
        self.assertTrue(pd.isna(prediction_trend(frame).data[-1].y[1]))
        self.assertTrue(comparison_monthly(self.regions, "없는시도", "고성군").empty)
        with self.assertRaises(ValueError):
            comparison_monthly(self.regions, "경상남도", "고성군", "8002")
        with self.assertRaises(ValueError):
            prediction_trend(pd.concat([frame, comparison_monthly(self.regions, "경상남도", "고성군", "8301")]))

    def test_national_and_goseong_report(self):
        report = {}
        for label, data in [("전국 원본 전체 11업종", self.raw), ("전국 분석 9업종", self.raw[self.raw.TP_BUZ_NO.isin(CORE9)]), ("M9 251지역 9업종", self.raw[(self.raw.SIDO_NM + "|" + self.raw.CCG_NM).isin(self.regions) & self.raw.TP_BUZ_NO.isin(CORE9)])]:
            personal = data[data.GENDER_CD.isin(["1", "2"]) & data.AGE_CD.isin(list("123456"))]
            report[label] = {target: {"all": int(data[target].sum()), "personal": int(personal[target].sum()), "difference": int(data[target].sum() - personal[target].sum()), "personal_share": float(personal[target].sum() / data[target].sum())} for target in ("amt", "cnt")}
        samples = []
        for sido in ["강원특별자치도", "경상남도"]:
            for scope in ["8301", "8001"]:
                before = self.raw[self.raw.SIDO_NM.eq(sido) & self.raw.CCG_NM.eq("고성군") & self.raw.TP_BUZ_NO.eq(scope)]
                after = comparison_monthly(self.regions, sido, "고성군", scope)
                samples.append(dict(region=sido + "|고성군", industry=CORE9[scope], before_amt=int(before.amt.sum()), after_amt=round(after.actual_amt.sum()), before_cnt=int(before.cnt.sum()), after_cnt=round(after.actual_cnt.sum()), monthly=[dict(month=row.month.strftime("%Y%m"), amt=row.actual_amt, cnt=row.actual_cnt) for row in after.itertuples()]))
        print("POPULATION_REPORT=" + json.dumps(dict(national=report, goseong=samples, handoff_rows=len(self.monthly), available_industry_rows=int((self.monthly.data_available & self.monthly.scope.isin(CORE9)).sum()), protected_files=len(self.protected)), ensure_ascii=False))

    def test_streamlit_region_industry_and_metric_selection(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
        self.assertFalse(app.exception)
        for sido in ("강원특별자치도", "경상남도"):
            app.session_state["region_view"] = "regional"
            app.session_state["selected_sido"] = sido
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[0].label, "전체 BC카드 이용금액")
            app.session_state["region_view"] = "local"
            app.session_state["selected_ccg"] = "고성군"
            app.run()
            self.assertFalse(app.exception)
            for name in ["업종 전체", *CORE9.values()]:
                app.button(key=f"industry_pick_{name}").click().run()
                self.assertFalse(app.exception, (sido, name))
                self.assertEqual(app.metric[0].label, "내국인 개인 BC 이용금액")
                scope = "core9" if name == "업종 전체" else next(code for code, value in CORE9.items() if value == name)
                source = comparison_monthly(self.regions, sido, "고성군", scope)
                total = source.actual_amt.sum(min_count=1)
                from src.data import compact_won
                self.assertEqual(app.metric[0].value, compact_won(total) if pd.notna(total) else "자료 없음")
            app.radio(key="comparison_target").set_value("cnt").run()
            self.assertFalse(app.exception)
        app.session_state["selected_sido"] = "경기도"
        app.session_state["selected_ccg"] = "화성시"
        app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any("지역 범위에 포함되지" in item.value for item in app.info))

    def test_national_industry_mode(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
        app.get("button_group")[0].set_value("업종별").run()
        self.assertFalse(app.exception)
        app.button(key="industry_pick_제과점").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].label, "전체 BC카드 이용금액")
        app.get("button_group")[0].set_value("지역별").run()
        self.assertFalse(app.exception)

    def test_policy_context_uses_personal_json_without_external_calls(self):
        from streamlit.testing.v1 import AppTest

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-no-network"}), patch("src.policy_ui.retrieve_evidence_groups", return_value={}), patch("src.policy_ui.generate_proposal", return_value="테스트 제안") as generate:
            # AppTest는 대화상자의 fragment 전용 rerun 대신 전체 스크립트를 실행한다.
            # 대화상자를 매번 열어 실제 생성 버튼/컨텍스트 경로를 검증한다.
            app = AppTest.from_string(
                "from src.data import load_csv, default_data_path\n"
                "from src.policy_ui import policy_dialog\n"
                "policy_dialog(load_csv(str(default_data_path())), {}, '강원특별자치도', '고성군', '제과점')\n",
                default_timeout=30,
            ).run()
            self.assertFalse(app.exception)
            next(button for button in app.button if button.label == "SWOT 기반 정책 분석 시작").click().run()
            self.assertFalse(app.exception)
            generate.assert_called_once()
            payload = generate.call_args.args[0]
            self.assertIn("내국인 개인", payload["population"])
            expected = [row for row in self.regions["강원특별자치도|고성군"]["monthly"] if row["scope"] == "8301"]
            self.assertEqual(payload["m9_comparison"]["monthly"], expected)
            self.assertAlmostEqual(payload["sales_change"], expected[-1]["actual_amt"] / expected[0]["actual_amt"] - 1)


if __name__ == "__main__":
    unittest.main()
