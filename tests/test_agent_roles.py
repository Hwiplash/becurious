from __future__ import annotations

import unittest

from src.agent import role_instructions


class RoleInstructionsTest(unittest.TestCase):
    def test_local_government_format_is_policy_specific(self) -> None:
        prompt = role_instructions("지자체")
        self.assertIn("## 정책 패키지", prompt)
        self.assertIn("## 성과관리와 실행 안정성", prompt)
        self.assertNotIn("## 이번 주 우선 행동 3가지", prompt)

    def test_owner_format_is_store_specific(self) -> None:
        prompt = role_instructions("점주")
        self.assertIn("## 실행 메뉴·상품 전략", prompt)
        self.assertIn("## 강점 활용과 보완점", prompt)
        self.assertIn("## 이번 주 우선 행동 3가지", prompt)
        self.assertNotIn("## 정책 패키지", prompt)

    def test_combined_role_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            role_instructions("둘 다")


if __name__ == "__main__":
    unittest.main()
