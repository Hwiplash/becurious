from __future__ import annotations

import re


HEADING_PATTERNS = (
    re.compile(r"^제\s*\d+\s*장"),
    re.compile(r"^\d+(?:\.\d+)*\.?\s+"),
    re.compile(r"^[가-힣]\.[ \t]+"),
    re.compile(r"^\([0-9]+\)[ \t]+"),
)


def find_heading(text: str) -> str:
    for line in text.splitlines()[:8]:
        candidate = " ".join(line.split()).strip()
        if 3 <= len(candidate) <= 100 and any(pattern.match(candidate) for pattern in HEADING_PATTERNS):
            return candidate
    return ""


def split_text(text: str, target: int = 2400, overlap: int = 250) -> list[str]:
    compact = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if len(compact) <= target:
        return [compact] if compact else []
    chunks, start = [], 0
    while start < len(compact):
        end = min(len(compact), start + target)
        if end < len(compact):
            candidates = [compact.rfind("\n", start, end), compact.rfind(". ", start, end)]
            split = max(candidates)
            if split > start + target // 2:
                end = split + 1
        chunks.append(compact[start:end].strip())
        if end >= len(compact):
            break
        start = max(start + 1, end - overlap)
    return [chunk for chunk in chunks if len(chunk) >= 80]


def build_chunks(document: dict, pages: list[dict], target: int = 2400, overlap: int = 250) -> list[dict]:
    chunks: list[dict] = []
    slide_mode = document.get("parser_type") == "slide"
    section = ""
    for page in pages:
        heading = find_heading(page["text"])
        if heading:
            section = heading
        page_type = "slide" if slide_mode or page["landscape"] else "body"
        for part_number, part in enumerate(split_text(page["text"], target, overlap), start=1):
            chunks.append({
                "id": f"{document['document_id']}-p{page['page']}-c{part_number}",
                "document_id": document["document_id"],
                "source": document["filename"],
                "page": page["page"],
                "page_start": page["page"],
                "page_end": page["page"],
                "section": section,
                "chunk_type": page_type,
                "topics": document.get("topics", []),
                "regions": document.get("regions", []),
                "priority": document.get("priority", "C"),
                "text": part,
            })
    return chunks

