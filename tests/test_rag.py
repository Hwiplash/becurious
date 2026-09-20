from __future__ import annotations

import unittest

from src.rag import _rrf_merge, local_corpus_ready, search_local_knowledge


class LocalRagTest(unittest.TestCase):
    def test_local_corpus_is_ready(self) -> None:
        self.assertTrue(local_corpus_ready())

    def test_local_search_returns_cited_results(self) -> None:
        results = search_local_knowledge("대전 외식업 상권 활성화 가족 고객 마케팅", top_k=3)
        self.assertTrue(results)
        self.assertTrue(all(item.get("source") for item in results))
        self.assertTrue(all(item.get("source_pages") for item in results))

    def test_rrf_merge_rewards_results_found_by_both_searches(self) -> None:
        keyword = [{"case_id": "case-shared", "chunk_id": "shared"}, {"case_id": "keyword-only"}]
        dense = [{"id": "dense-only"}, {"id": "shared"}]
        results = _rrf_merge(keyword, dense, top_k=3)
        self.assertEqual(results[0]["chunk_id"], "shared")
        self.assertEqual(results[0]["matched_by"], ["dense", "keyword"])

    def test_specialty_search_returns_regional_product(self) -> None:
        results = search_local_knowledge("의령군 망개떡 특징", top_k=5)
        self.assertTrue(any(item.get("specialty") == "망개떡" for item in results))

    def test_industry_alias_search_returns_standard_category(self) -> None:
        results = search_local_knowledge("짜장면 업종 코드는 무엇인가", top_k=5)
        self.assertEqual(results[0].get("industry_code"), "8005")


if __name__ == "__main__":
    unittest.main()
