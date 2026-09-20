from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.industry_taxonomy import load_industry_taxonomy

OUTPUT = ROOT / "data" / "processed" / "industry_taxonomy_chunks.json"

def main() -> None:
    chunks = []
    for item in load_industry_taxonomy():
        digest = hashlib.sha1(item["code"].encode("utf-8")).hexdigest()[:12]
        aliases = ", ".join(item["aliases"])
        chunks.append({
            "id": f"industry-taxonomy-{digest}", "document_id": f"industry-taxonomy-{item['code']}",
            "source": "업종 분류 상세", "page": 1, "page_start": 1, "page_end": 1,
            "section": f"{item['code']} {item['name']}", "chunk_type": "industry-taxonomy",
            "topics": ["업종분류", "업종코드", "외식업종"], "regions": ["전국"], "priority": "A",
            "industry_code": item["code"], "industry_name": item["name"], "aliases": item["aliases"],
            "text": f"업종 코드: {item['code']}\n표준 업종명: {item['name']}\n관련 명칭 및 검색 동의어: {aliases}",
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"industry_chunks": len(chunks), "output": str(OUTPUT)}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
