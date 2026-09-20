from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import pymupdf


ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "data" / "pdfs"
QA_DIR = ROOT / "data" / "qa"

TOPICS = {
    "상권활성화": ["상권", "골목", "원도심", "도심상권"],
    "전통시장": ["전통시장", "시장활성화", "야시장"],
    "외식산업": ["외식산업", "외식업", "음식점"],
    "대표음식·메뉴": ["대표음식", "향토음식", "메뉴개발", "먹거리", "음식문화"],
    "관광·특화거리": ["관광", "특화거리", "음식거리", "문화거리"],
    "푸드테크·플랫폼": ["푸드테크", "플랫폼", "디지털", "빅데이터"],
    "로컬푸드·공급망": ["로컬푸드", "산지직거래", "식재료", "먹거리 전략", "농산물"],
    "지역경제·소상공인": ["지역경제", "소상공인", "상생", "지역화폐"],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def detect_topics(filename: str, sample_text: str) -> list[str]:
    haystack = f"{filename} {sample_text}".lower()
    return [topic for topic, words in TOPICS.items() if any(word.lower() in haystack for word in words)]


def inspect(path: Path) -> dict:
    base = {
        "filename": path.name,
        "size_mb": round(path.stat().st_size / 1024 / 1024, 2),
        "sha256": "",
        "pages": 0,
        "text_pages": 0,
        "ocr_pages": 0,
        "text_page_ratio": 0.0,
        "avg_chars_per_page": 0,
        "landscape_ratio": 0.0,
        "parser_type": "invalid",
        "topics": "",
        "status": "ok",
        "error": "",
    }
    if path.stat().st_size == 0:
        base.update(status="invalid", error="zero-byte file")
        return base
    try:
        base["sha256"] = sha256(path)
        doc = pymupdf.open(path)
        lengths: list[int] = []
        landscape = 0
        sample_parts: list[str] = []
        for page_no, page in enumerate(doc):
            text = page.get_text("text").strip()
            lengths.append(len(text))
            landscape += int(page.rect.width > page.rect.height)
            if page_no < 15 or page_no >= max(0, len(doc) - 10) or page_no % 25 == 0:
                sample_parts.append(text[:5000])
        pages = len(doc)
        text_pages = sum(length >= 150 for length in lengths)
        ocr_pages = sum(length < 150 for length in lengths)
        text_ratio = text_pages / pages if pages else 0
        landscape_ratio = landscape / pages if pages else 0
        if text_ratio < 0.2:
            parser_type = "scanned"
        elif landscape_ratio >= 0.6:
            parser_type = "slide"
        elif text_ratio >= 0.75 and landscape_ratio < 0.3:
            parser_type = "report"
        else:
            parser_type = "mixed"
        topics = detect_topics(path.name, " ".join(sample_parts))
        base.update(
            pages=pages,
            text_pages=text_pages,
            ocr_pages=ocr_pages,
            text_page_ratio=round(text_ratio, 3),
            avg_chars_per_page=round(sum(lengths) / pages) if pages else 0,
            landscape_ratio=round(landscape_ratio, 3),
            parser_type=parser_type,
            topics="|".join(topics),
        )
    except Exception as exc:
        base.update(status="invalid", error=str(exc)[:300])
    return base


def main() -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(PDF_DIR.rglob("*.pdf"))
    rows = []
    for index, path in enumerate(pdfs, start=1):
        rows.append(inspect(path))
        print(f"[{index}/{len(pdfs)}] {path.name}", flush=True)

    hash_counts = Counter(row["sha256"] for row in rows if row["sha256"])
    for row in rows:
        row["duplicate_count"] = hash_counts.get(row["sha256"], 0)

    csv_path = QA_DIR / "pdf_inventory.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (QA_DIR / "pdf_inventory.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    valid = [row for row in rows if row["status"] == "ok"]
    topic_counts = Counter()
    for row in valid:
        topic_counts.update(filter(None, row["topics"].split("|")))
    type_counts = Counter(row["parser_type"] for row in valid)
    summary = {
        "files": len(rows),
        "valid_files": len(valid),
        "invalid_files": len(rows) - len(valid),
        "total_size_mb": round(sum(row["size_mb"] for row in rows), 2),
        "total_pages": sum(row["pages"] for row in valid),
        "text_pages": sum(row["text_pages"] for row in valid),
        "ocr_candidate_pages": sum(row["ocr_pages"] for row in valid),
        "exact_duplicate_files": sum(count - 1 for count in hash_counts.values() if count > 1),
        "parser_types": dict(type_counts),
        "topics": dict(topic_counts.most_common()),
    }
    (QA_DIR / "pdf_inventory_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
