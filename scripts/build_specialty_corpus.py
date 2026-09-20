from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output" / "pdf" / "nongsaro_specialties" / "specialties.csv"
OUTPUT = ROOT / "data" / "processed" / "specialty_chunks.json"


def clean_region(region: str) -> list[str]:
    return [part.strip() for part in region.split(">") if part.strip()]


def build_text(row: dict[str, str]) -> str:
    foods = json.loads(row.get("foods") or "[]")
    parts = [
        f"지역 특산물: {row['specialty']}",
        f"지역: {row['region']}",
        f"특징: {row.get('features') or '원문에서 특징 정보를 확인하지 못했습니다.'}",
    ]
    if foods:
        parts.append("만들 수 있는 음식 및 활용 정보: " + " / ".join(foods))
    else:
        parts.append("만들 수 있는 음식 및 활용 정보: 원문에 별도 정보가 제공되지 않았습니다.")
    parts.append(f"출처: {row.get('final_url') or row.get('source_url')}")
    return "\n".join(parts)


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"특산물 수집 결과가 없습니다: {SOURCE}")
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    chunks: list[dict] = []
    for row in rows:
        digest = hashlib.sha1(row["item_key"].encode("utf-8")).hexdigest()[:16]
        regions = clean_region(row["region"])
        source_url = row.get("final_url") or row.get("source_url") or ""
        chunks.append({
            "id": f"specialty-{digest}",
            "document_id": f"nongsaro-{digest}",
            "source": source_url,
            "source_url": source_url,
            "pdf_path": row.get("pdf_path", ""),
            "page": 1,
            "page_start": 1,
            "page_end": 1,
            "section": row["specialty"],
            "chunk_type": "regional-specialty",
            "topics": ["지역특산물", "농산물", "지역먹거리"],
            "regions": regions,
            "priority": "A" if row.get("status") == "ok" else "C",
            "specialty": row["specialty"],
            "foods": json.loads(row.get("foods") or "[]"),
            "extraction_confidence": row.get("extraction_confidence", "low"),
            "source_status": row.get("status", "failed"),
            "text": build_text(row),
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"source_rows": len(rows), "specialty_chunks": len(chunks), "output": str(OUTPUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
