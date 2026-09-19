from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.rag import search_knowledge


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG 검색 결과와 출처를 간단히 점검합니다.")
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=6)
    args = parser.parse_args()

    load_dotenv()
    results = search_knowledge(args.query, top_k=args.top_k)
    print(f"results={len(results)}")
    for index, item in enumerate(results, start=1):
        page = item.get("page_start") or item.get("page")
        print(
            f"[{index}] {item.get('source')} / p.{page} / "
            f"{item.get('section', '')} / {item.get('matched_by', [])} / "
            f"dense={item.get('dense_score', 0):.4f}"
        )
        print((item.get("text") or "")[:220].replace("\n", " "))


if __name__ == "__main__":
    main()
