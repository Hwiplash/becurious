from __future__ import annotations

import re
from pathlib import Path

import pymupdf


pymupdf.TOOLS.mupdf_display_errors(False)

EXCLUDE_PATTERNS = (
    "연구진",
    "표 목차",
    "그림 목차",
    "참고문헌",
)


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"(?m)^\s*-?\s*\d+\s*-?\s*$", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def should_exclude(text: str) -> bool:
    compact = " ".join(text.split())
    if len(compact) < 40:
        return True
    if len(compact) < 800 and any(pattern in compact for pattern in EXCLUDE_PATTERNS):
        return True
    if "목 차" in compact and len(compact) < 1200:
        return True
    return False


def extract_pages(path: Path, ocr_threshold: int = 150) -> tuple[list[dict], list[int]]:
    pages: list[dict] = []
    ocr_candidates: list[int] = []
    document = pymupdf.open(path)
    for page_number, page in enumerate(document, start=1):
        try:
            text = clean_text(page.get_text("text"))
        except Exception:
            text = ""
        if len(text) < ocr_threshold:
            ocr_candidates.append(page_number)
        if should_exclude(text):
            continue
        pages.append({
            "page": page_number,
            "text": text,
            "landscape": page.rect.width > page.rect.height,
        })
    return pages, ocr_candidates

