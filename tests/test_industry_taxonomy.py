from __future__ import annotations

import unittest

from src.industry_taxonomy import industry_by_code, resolve_industry_candidates, resolve_industry_name

class IndustryTaxonomyTest(unittest.TestCase):
    def test_code_lookup(self) -> None:
        self.assertEqual(industry_by_code("8301")["name"], "제과점")

    def test_specific_alias_resolution(self) -> None:
        self.assertEqual(resolve_industry_name("우리 지역 짜장면 매출 분석"), "중국음식")
        self.assertEqual(resolve_industry_name("카페와 파스타 소비"), "서양음식")

    def test_ambiguous_alias_returns_candidates(self) -> None:
        candidates = resolve_industry_candidates("푸드트럭 활성화")
        self.assertGreaterEqual(len(candidates), 4)
        self.assertIsNone(resolve_industry_name("푸드트럭 활성화"))

if __name__ == "__main__":
    unittest.main()
