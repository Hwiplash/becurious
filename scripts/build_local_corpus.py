from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingestion.case_extractor import build_case_card, candidate_score, is_candidate
from src.ingestion.chunker import build_chunks
from src.ingestion.extractor import extract_pages


PDF_DIR = ROOT / "data" / "pdfs"
QA_DIR = ROOT / "data" / "qa"
PROCESSED_DIR = ROOT / "data" / "processed"

REGIONS = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "제주", "경기", "강원",
    "충북", "충남", "전북", "전남", "경북", "경남", "포항", "안양", "부천", "청주", "군산",
    "서산", "부평", "영주", "태안", "담양", "영암", "인제", "함양", "구례", "부여", "태백",
    "춘천", "관악", "강동", "강북", "금정", "나주", "정읍", "익산", "철원", "화성", "옥천",
    "해운대", "기장", "종로", "이태원", "여수", "목포", "평택", "영광", "진주", "포천",
    "함평", "월곡", "대부도", "울산중구", "울산남구",
]

FILENAME_TOPIC_KEYWORDS = {
    "외식산업": ("외식", "식당", "음식점", "먹거리", "푸드", "K-FOOD", "한식"),
    "대표음식·메뉴": ("대표음식", "메뉴", "레시피", "음식개발"),
    "관광·특화거리": ("관광", "특화거리", "음식문화거리"),
    "상권활성화": ("상권", "골목경제"),
    "전통시장": ("전통시장", "상점가"),
    "로컬푸드·공급망": ("로컬푸드", "직거래", "식자재", "공급망"),
    "지역경제·소상공인": ("소상공인", "지역경제", "지역상생"),
}


def infer_year(filename: str) -> int | None:
    years = [int(value) for value in re.findall(r"(?:19|20)\d{2}", filename)]
    years = [year for year in years if 1990 <= year <= 2026]
    return max(years) if years else None


def infer_regions(filename: str) -> list[str]:
    matches = [region for region in sorted(REGIONS, key=len, reverse=True) if region in filename]
    if "해운대" in matches and "대구" in matches:
        matches.remove("대구")
    return matches or ["전국"]


def infer_topics_from_filename(filename: str) -> list[str]:
    return [topic for topic, keywords in FILENAME_TOPIC_KEYWORDS.items() if any(keyword in filename for keyword in keywords)]


def document_id(sha256: str, filename: str) -> str:
    value = sha256 or hashlib.sha256(filename.encode("utf-8")).hexdigest()
    return f"doc-{value[:12]}"


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    inventory = json.loads((QA_DIR / "pdf_inventory.json").read_text(encoding="utf-8"))
    file_map = {path.name: path for path in PDF_DIR.rglob("*.pdf")}
    override_file = ROOT / "data" / "ocr_output" / "overrides.json"
    overrides = json.loads(override_file.read_text(encoding="utf-8")) if override_file.exists() else {}
    seen_hashes: set[str] = set()
    catalog, chunks, cards, qa_rows = [], [], [], []

    for index, row in enumerate(inventory, start=1):
        override_path = ROOT / overrides[row["filename"]] if row["filename"] in overrides else None
        path = override_path if override_path and override_path.exists() else file_map.get(row["filename"], PDF_DIR / row["filename"])
        status = "processed"
        reason = ""
        if row["status"] != "ok" or not path.exists() or path.stat().st_size == 0:
            status, reason = "excluded", row.get("error") or "invalid file"
        elif row["sha256"] in seen_hashes:
            status, reason = "excluded", "exact duplicate"

        topics = [topic for topic in row.get("topics", "").split("|") if topic]
        if not topics:
            topics = infer_topics_from_filename(row["filename"])
        priority = "A" if any(topic in topics for topic in ("외식산업", "상권활성화", "대표음식·메뉴", "관광·특화거리")) else "C"
        if float(row.get("text_page_ratio") or 0) < 0.5 and priority == "A":
            priority = "B"
        doc = {
            "document_id": document_id(row.get("sha256", ""), row["filename"]),
            "filename": row["filename"],
            "sha256": row.get("sha256", ""),
            "year": infer_year(row["filename"]),
            "regions": infer_regions(row["filename"]),
            "topics": topics,
            "parser_type": row.get("parser_type", "report"),
            "priority": priority,
            "pages": int(row.get("pages") or 0),
            "status": status,
            "exclude_reason": reason,
            "ocr_override": bool(override_path and override_path.exists()),
        }
        catalog.append(doc)
        if status != "processed":
            qa_rows.append({"filename": row["filename"], "status": status, "chunks": 0, "case_cards": 0, "ocr_candidates": 0, "reason": reason})
            continue

        seen_hashes.add(row["sha256"])
        try:
            pages, ocr_candidates = extract_pages(path)
            doc_chunks = build_chunks(doc, pages)
            candidates = [chunk for chunk in doc_chunks if is_candidate(chunk)]
            candidates.sort(key=candidate_score, reverse=True)
            doc_cards = [build_case_card(chunk) for chunk in candidates[:25]]
            chunks.extend(doc_chunks)
            cards.extend(doc_cards)
            total_pages = max(int(row.get("pages") or 0), 1)
            ocr_ratio = min(len(ocr_candidates) / total_pages, 1.0)
            needs_review = ocr_ratio >= 0.25 or not doc_chunks
            qa_rows.append({
                "filename": row["filename"],
                "status": "review" if needs_review else "ok",
                "chunks": len(doc_chunks),
                "case_cards": len(doc_cards),
                "ocr_candidates": len(ocr_candidates),
                "ocr_ratio": round(ocr_ratio, 4),
                "reason": "OCR candidate ratio >= 25%" if needs_review else "",
            })
        except Exception as exc:
            doc["status"] = "failed"
            qa_rows.append({"filename": row["filename"], "status": "failed", "chunks": 0, "case_cards": 0, "ocr_candidates": 0, "reason": str(exc)[:300]})
        print(f"[{index}/{len(inventory)}] {row['filename']}", flush=True)

    (PROCESSED_DIR / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    (PROCESSED_DIR / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    (PROCESSED_DIR / "case_cards.json").write_text(json.dumps(cards, ensure_ascii=False), encoding="utf-8")
    with (QA_DIR / "ingestion_report.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["filename", "status", "chunks", "case_cards", "ocr_candidates", "ocr_ratio", "reason"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(qa_rows)
    summary = {
        "documents": len(catalog),
        "processed_documents": sum(doc["status"] == "processed" for doc in catalog),
        "chunks": len(chunks),
        "case_cards": len(cards),
        "qa_status": dict(Counter(row["status"] for row in qa_rows)),
    }
    (PROCESSED_DIR / "corpus_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
