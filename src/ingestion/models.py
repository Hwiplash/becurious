from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PageProfile:
    page: int
    page_type: str
    text_length: int
    landscape: bool
    image_count: int
    requires_ocr: bool


@dataclass
class DocumentProfile:
    document_id: str
    filename: str
    file_hash: str
    page_count: int
    parser_type: str
    title: str = ""
    year: int | None = None
    publisher: str = ""
    regions: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    confidence: float = 0.0
    review_required: bool = False


@dataclass
class KnowledgeChunk:
    chunk_id: str
    document_id: str
    source: str
    page_start: int
    page_end: int
    section: str
    chunk_type: str
    text: str
    regions: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    evidence_level: str = "unknown"


@dataclass
class CaseCard:
    case_id: str
    document_id: str
    source_pages: list[int]
    problems: list[str]
    advantages: list[str]
    targets: list[str]
    interventions: list[str]
    outcomes: list[str]
    limitations: list[str]
    evidence_level: str

