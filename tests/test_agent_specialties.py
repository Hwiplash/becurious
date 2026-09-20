from __future__ import annotations

import unittest

from src.agent import _rank_specialty_candidates


class SpecialtyPolicyEvidenceTest(unittest.TestCase):
    def test_prefers_same_region_specialty_with_food_evidence(self) -> None:
        candidates = [
            {"id": "1", "chunk_type": "regional-specialty", "specialty": "망개떡", "regions": ["경상남도", "의령군"], "foods": [], "text": "의령군 망개떡"},
            {"id": "2", "chunk_type": "regional-specialty", "specialty": "구아바", "regions": ["경상남도", "의령군"], "foods": ["구아바차"], "text": "의령군 구아바 구아바차"},
            {"id": "3", "chunk_type": "regional-specialty", "specialty": "사과", "regions": ["경상북도", "영양군"], "foods": [], "text": "영양군 사과"},
        ]
        results = _rank_specialty_candidates(candidates, "경상남도 의령군", "제과점", 3)
        self.assertEqual([item["specialty"] for item in results], ["구아바", "망개떡"])
        self.assertNotIn("사과", [item["specialty"] for item in results])

    def test_excludes_non_specialty_chunks(self) -> None:
        candidates = [{"id": "x", "chunk_type": "industry-taxonomy", "regions": ["전국"], "text": "제과점"}]
        self.assertEqual(_rank_specialty_candidates(candidates, "경상남도 의령군", "제과점", 3), [])


if __name__ == "__main__":
    unittest.main()
