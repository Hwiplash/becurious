from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent import EVIDENCE_GROUP_LABELS, generate_proposal, retrieve_evidence_groups
from src.analytics import diagnose_region
from src.data import default_data_path, load_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="매출 진단부터 정책 제안까지 전체 흐름을 점검합니다.")
    parser.add_argument("--sido", default="대전광역시")
    parser.add_argument("--ccg", default="유성구")
    parser.add_argument("--industry", default="갈비전문점")
    parser.add_argument("--role", default="지자체 정책담당자")
    parser.add_argument("--budget", default="중간")
    args = parser.parse_args()

    load_dotenv()
    data_path = default_data_path()
    if data_path is None:
        raise FileNotFoundError("ABP_CONTEST_DATA.csv를 찾을 수 없습니다.")
    data = load_csv(str(data_path))
    diagnosis = diagnose_region(data, args.sido, args.ccg, args.industry).to_dict()
    evidence = retrieve_evidence_groups(diagnosis, per_group=3)
    proposal = generate_proposal(
        diagnosis, evidence, args.role, args.budget,
        "지역과 업종의 약점과 강점을 결합한 우선 전략을 제시해 주세요.",
    )
    print("DIAGNOSIS")
    print(json.dumps(diagnosis, ensure_ascii=False, indent=2))
    print("\nEVIDENCE")
    for group, items in evidence.items():
        print(f"[{EVIDENCE_GROUP_LABELS[group]}]")
        for item in items:
            print(f"- {item.get('source')} p.{item.get('page') or (item.get('source_pages') or ['?'])[0]}")
    print("\nPROPOSAL")
    print(proposal)


if __name__ == "__main__":
    main()
