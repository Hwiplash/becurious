from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import subprocess
import threading
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
import urllib3
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
LIST_URL = "https://www.nongsaro.go.kr/portal/ps/psz/psza/contentMain.ps"
DEFAULT_PARAMS = {
    "menuId": "PS03343",
    "pageSize": "7",
    "pageUnit": "9",
    "cntntsNo": "",
    "sUpperClCode": "376004",
    "sAreaNm": "",
    "sAreaCode": "",
    "sText": "",
}
BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
    "figcaption", "figure", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "li",
    "main", "p", "section", "table", "td", "th", "tr", "ul",
}
SKIP_TAGS = {"script", "style", "svg", "noscript", "template", "form", "nav", "footer"}
FOOD_WORDS = (
    "요리", "음식", "레시피", "조리", "활용법", "먹는 법", "먹는법", "만드는 법",
    "만드는법", "무침", "국", "탕", "찌개", "전", "죽", "밥", "떡", "차", "청",
    "잼", "김치", "장아찌", "샐러드", "디저트",
)
FOOD_TRIGGERS = ("요리", "음식", "레시피", "조리", "활용", "만들어 먹", "만들 수", "재료로")
FOOD_NAME_RE = re.compile(
    r"[가-힣]{1,15}(?:국|탕|찌개|전|죽|밥|떡|차|청|잼|김치|장아찌|샐러드|국수|무침|볶음|튀김|구이)"
)
FEATURE_WORDS = (
    "특징", "특성", "효능", "품질", "맛", "향", "식감", "재배", "생산", "유래",
    "소개", "설명", "유명", "대표", "풍부", "우수", "영양",
)
THREAD_LOCAL = threading.local()
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
}


@dataclass
class Specialty:
    name: str
    region: str
    detail_url: str
    image_url: str = ""


class NongsaroListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.list_depth: int | None = None
        self.li_depth: int | None = None
        self.field: str | None = None
        self.current: dict[str, str] = {}
        self.items: list[Specialty] = []

    @staticmethod
    def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key: value or "" for key, value in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.depth += 1
        values = self._attrs(attrs)
        classes = set(values.get("class", "").split())
        if tag == "div" and "data_list" in classes:
            self.list_depth = self.depth
        elif self.list_depth is not None and tag == "li" and self.li_depth is None:
            self.li_depth = self.depth
            self.current = {"name": "", "region": "", "detail_url": "", "image_url": ""}
        elif self.li_depth is not None and tag == "a" and "inBox" in classes:
            self.current["detail_url"] = values.get("href", "")
        elif self.li_depth is not None and tag == "img":
            self.current["image_url"] = values.get("src", "")
            self.current["name"] = self.current["name"] or values.get("alt", "")
        elif self.li_depth is not None and tag in {"dt", "dd"}:
            self.field = "name" if tag == "dt" else "region"
            self.current[self.field] = ""

    def handle_data(self, data: str) -> None:
        if self.li_depth is not None and self.field:
            self.current[self.field] += data

    def handle_endtag(self, tag: str) -> None:
        if self.li_depth is not None and tag in {"dt", "dd"}:
            self.field = None
        if self.li_depth == self.depth and tag == "li":
            row = {key: " ".join(value.split()) for key, value in self.current.items()}
            if row["name"] and row["detail_url"]:
                self.items.append(Specialty(**row))
            self.li_depth = None
            self.current = {}
        if self.list_depth == self.depth and tag == "div":
            self.list_depth = None
        self.depth -= 1


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS:
            self.skip_depth += 1
        elif not self.skip_depth and tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
        elif not self.skip_depth and tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self.parts).splitlines()]
        return "\n".join(line for line in lines if line)


def normalize_url(url: str, base: str = LIST_URL) -> str:
    absolute = urljoin(base, html.unescape(url.strip()))
    parts = urlsplit(absolute)
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)), doseq=True)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, query, ""))


def safe_stem(item: Specialty, url: str) -> str:
    label = re.sub(r"[<>:\"/\\|?*\x00-\x1f]+", "_", f"{item.region}_{item.name}")
    label = re.sub(r"\s+", "_", label).strip("._")[:90] or "specialty"
    return f"{label}_{hashlib.sha256(url.encode('utf-8')).hexdigest()[:10]}"


def fetch(session: requests.Session, url: str, *, timeout: int) -> tuple[str, str]:
    try:
        response = session.get(url, timeout=timeout, allow_redirects=True)
    except requests.exceptions.SSLError:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        try:
            response = session.get(url, timeout=timeout, allow_redirects=True, verify=False)
        except requests.exceptions.SSLError:
            parts = urlsplit(url)
            if parts.scheme != "https":
                raise
            http_url = urlunsplit(("http", parts.netloc, parts.path, parts.query, parts.fragment))
            response = session.get(http_url, timeout=timeout, allow_redirects=True, verify=False)
    response.raise_for_status()
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding
    return response.text, normalize_url(response.url)


def worker_session() -> requests.Session:
    session = getattr(THREAD_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(REQUEST_HEADERS)
        THREAD_LOCAL.session = session
    return session


def browser_fetch(url: str, timeout: int) -> tuple[str, str]:
    browsers = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    browser = next((path for path in browsers if path.exists()), None)
    if browser is None:
        raise FileNotFoundError("Chrome 또는 Edge를 찾지 못했습니다.")
    with tempfile.TemporaryDirectory(prefix="nongsaro_dump_") as profile:
        command = [
            str(browser), "--headless=new", "--disable-gpu", "--no-sandbox",
            "--ignore-certificate-errors", "--allow-running-insecure-content",
            f"--user-data-dir={profile}", "--virtual-time-budget=8000", "--dump-dom", url,
        ]
        completed = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
        )
    source = completed.stdout.strip()
    if completed.returncode != 0 or "<html" not in source.lower():
        message = (completed.stderr or source or "브라우저 HTML 수집 실패").strip()[-500:]
        raise RuntimeError(message)
    return source, url


def parse_list_page(source: str) -> list[Specialty]:
    parser = NongsaroListParser()
    parser.feed(source)
    return parser.items


def total_pages(source: str) -> int:
    matches = re.findall(r"총\s*([\d,]+)페이지|/\s*([\d,]+)\s*</span>", source)
    values = [int((a or b).replace(",", "")) for a, b in matches]
    return max(values) if values else 1


def visible_text(source: str) -> str:
    parser = VisibleTextParser()
    parser.feed(source)
    return parser.text()


def relevant_lines(text: str, item_name: str, keywords: tuple[str, ...], limit: int = 8) -> list[str]:
    lines = [line for line in text.splitlines() if 12 <= len(line) <= 700]
    chosen: list[str] = []
    for index, line in enumerate(lines):
        if item_name in line or any(word in line for word in keywords):
            for candidate in lines[max(0, index - 1): min(len(lines), index + 2)]:
                if candidate not in chosen:
                    chosen.append(candidate)
                if len(chosen) >= limit:
                    return chosen
    return chosen


def item_context(text: str, item_name: str, limit: int = 6) -> list[str]:
    lines = [line for line in text.splitlines() if line]
    exact = [index for index, line in enumerate(lines) if line.strip() == item_name]
    for index in exact:
        context: list[str] = []
        for line in lines[index + 1: index + 1 + limit]:
            if line in {"내용 더보기", "주요판매원"} or line.startswith("☎"):
                break
            if len(line) >= 12:
                context.append(line)
        if context:
            return context
    containing = [line for line in lines if item_name in line and 12 <= len(line) <= 700]
    return containing[:limit]


def extract_fields(text: str, item: Specialty) -> tuple[str, list[str], str]:
    feature_lines = item_context(text, item.name)
    if not feature_lines:
        feature_lines = relevant_lines(text, item.name, FEATURE_WORDS, limit=4)
    foods = []
    for line in feature_lines:
        if not any(trigger in line for trigger in FOOD_TRIGGERS):
            continue
        named_foods = [name for name in FOOD_NAME_RE.findall(line) if name != item.name]
        if named_foods:
            foods.append(line)
    foods = list(dict.fromkeys(foods))
    confidence = "high" if feature_lines and any(item.name in line for line in feature_lines) else "medium" if item.name in text else "low"
    return "\n".join(feature_lines), foods, confidence


def _pdf_font() -> str:
    font_name = "NongsaroKorean"
    if font_name in pdfmetrics.getRegisteredFontNames():
        return font_name
    candidates = [
        Path(r"C:\Windows\Fonts\malgun.ttf"),
        Path(r"C:\Windows\Fonts\gulim.ttc"),
    ]
    for path in candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont(font_name, str(path)))
            return font_name
    return "Helvetica"


def build_item_pdf(item: Specialty, features: str, foods: list[str], source_url: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    font = _pdf_font()
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "KoreanTitle", parent=styles["Title"], fontName=font, fontSize=22,
        leading=30, textColor=colors.HexColor("#174A31"), alignment=TA_CENTER,
        spaceAfter=12,
    )
    heading = ParagraphStyle(
        "KoreanHeading", parent=styles["Heading2"], fontName=font, fontSize=13,
        leading=19, textColor=colors.HexColor("#245B3C"), spaceBefore=12, spaceAfter=7,
    )
    body = ParagraphStyle(
        "KoreanBody", parent=styles["BodyText"], fontName=font, fontSize=10.5,
        leading=18, textColor=colors.HexColor("#202722"), wordWrap="CJK",
    )
    meta = ParagraphStyle(
        "KoreanMeta", parent=body, fontSize=9, leading=14, textColor=colors.HexColor("#566159"),
    )
    doc = SimpleDocTemplate(
        str(output), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title=f"{item.region} {item.name}", author="농사로 지역특산물 수집기",
    )
    story = [
        Paragraph(html.escape(item.name), title),
        Table(
            [
                [Paragraph("지역", meta), Paragraph(html.escape(item.region), body)],
                [Paragraph("수집일", meta), Paragraph(datetime.now().strftime("%Y-%m-%d"), body)],
            ],
            colWidths=[28 * mm, 118 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF3EC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B8C9BC")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CFDAD1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]),
        ),
        Paragraph("특징", heading),
        Paragraph(html.escape(features) if features else "연결 페이지에서 해당 특산물의 설명을 분리하지 못했습니다.", body),
        Paragraph("이 특산물로 만들 수 있는 음식", heading),
    ]
    if foods:
        for food in foods:
            story.append(Paragraph(f"- {html.escape(food)}", body))
    else:
        story.append(Paragraph("연결 페이지에 별도의 음식 또는 조리 정보가 제공되지 않았습니다.", body))
    story.extend([
        Spacer(1, 14),
        Paragraph("출처", heading),
        Paragraph(html.escape(source_url), meta),
        Spacer(1, 4),
        Paragraph("주의: 원문에서 해당 특산물과 직접 연결된 문장만 수록했으며, 다른 특산물 설명은 포함하지 않았습니다.", meta),
    ])
    doc.build(story)


def load_completed(path: Path) -> set[str]:
    if not path.exists():
        return set()
    completed: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("status") == "ok":
                completed.add(row.get("item_key", ""))
    return completed


def append_csv(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def compact_manifest(path: Path) -> None:
    if not path.exists():
        return
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        return
    selected: dict[str, dict[str, str]] = {}
    order: list[str] = []
    for row in rows:
        key = row["item_key"]
        if key not in selected:
            order.append(key)
        if key not in selected or row.get("status") == "ok" or selected[key].get("status") != "ok":
            selected[key] = row
    temp = path.with_suffix(".tmp.csv")
    with temp.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(selected[key] for key in order)
    temp.replace(path)


def crawl(args: argparse.Namespace) -> None:
    output = args.output.resolve()
    pdf_dir = output / "pdfs"
    manifest = output / "specialties.csv"
    raw_dir = output / "text"
    output.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    completed = load_completed(manifest) if args.resume else set()
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    first_params = dict(DEFAULT_PARAMS, pageIndex=str(args.start_page))
    first_response = session.get(LIST_URL, params=first_params, timeout=args.timeout)
    first_response.raise_for_status()
    first_response.encoding = "utf-8"
    last_page = min(total_pages(first_response.text), args.end_page or 10**9)
    processed = 0
    _pdf_font()

    def process_one(task: tuple[int, int, Specialty, int]) -> tuple[int, dict[str, object]] | None:
            page, position, item, item_count = task
            detail_url = normalize_url(item.detail_url)
            item_key = hashlib.sha256(f"{item.region}|{item.name}|{detail_url}".encode("utf-8")).hexdigest()[:16]
            if item_key in completed:
                return None
            stem = safe_stem(item, detail_url)
            pdf_path = pdf_dir / f"{stem}.pdf"
            text_path = raw_dir / f"{stem}.txt"
            status, error, final_url, text = "ok", "", detail_url, ""
            features, foods, confidence = "", [], "low"
            try:
                if args.delay:
                    time.sleep(args.delay)
                try:
                    source, final_url = fetch(worker_session(), detail_url, timeout=args.timeout)
                except requests.RequestException:
                    source, final_url = browser_fetch(detail_url, timeout=args.browser_timeout)
                text = visible_text(source)
                text_path.write_text(text, encoding="utf-8")
                features, foods, confidence = extract_fields(text, item)
                if not args.no_pdf:
                    build_item_pdf(item, features, foods, final_url, pdf_path)
            except Exception as exc:
                status, error = "failed", f"{type(exc).__name__}: {exc}"[:500]
                features = "원문 제공 사이트에 접속하지 못해 특징 정보를 수집하지 못했습니다. 아래 출처 URL과 오류 기록을 확인해 수동 검수해 주세요."
                confidence = "low"
                if not args.no_pdf:
                    build_item_pdf(item, features, [], detail_url, pdf_path)
            row = {
                "item_key": item_key,
                "status": status,
                "list_page": page,
                "list_position": position,
                "region": item.region,
                "specialty": item.name,
                "source_url": detail_url,
                "final_url": final_url,
                "pdf_path": str(pdf_path.relative_to(output)) if pdf_path.exists() else "",
                "text_path": str(text_path.relative_to(output)) if text_path.exists() else "",
                "features": features,
                "foods": json.dumps(foods, ensure_ascii=False),
                "extraction_confidence": confidence,
                "error": error,
            }
            return item_count, row

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for page in range(args.start_page, last_page + 1):
            if page == args.start_page:
                source = first_response.text
            else:
                response = session.get(LIST_URL, params=dict(DEFAULT_PARAMS, pageIndex=str(page)), timeout=args.timeout)
                response.raise_for_status()
                response.encoding = "utf-8"
                source = response.text
            items = parse_list_page(source)
            print(f"[목록 {page}/{last_page}] {len(items)}개", flush=True)
            tasks = [(page, position, item, len(items)) for position, item in enumerate(items, start=1)]
            if args.max_items:
                tasks = tasks[:max(0, args.max_items - processed)]
            for result in executor.map(process_one, tasks):
                if result is None:
                    continue
                item_count, row = result
                append_csv(manifest, row)
                processed += 1
                print(f"  [{row['list_position']}/{item_count}] {row['region']} / {row['specialty']}: {row['status']}", flush=True)
            if args.max_items and processed >= args.max_items:
                compact_manifest(manifest)
                return
    compact_manifest(manifest)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="농사로 지역특산물 링크를 PDF와 구조화 CSV로 수집합니다.")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "pdf" / "nongsaro_specialties")
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--end-page", type=int)
    parser.add_argument("--max-items", type=int, default=0, help="0이면 제한 없음")
    parser.add_argument("--delay", type=float, default=1.0, help="항목 간 대기 시간(초)")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--browser-timeout", type=int, default=45)
    parser.add_argument("--workers", type=int, default=4, help="동시에 처리할 상세페이지 수")
    parser.add_argument("--no-pdf", action="store_true", help="HTML 텍스트와 CSV만 수집")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    return parser


if __name__ == "__main__":
    crawl(build_parser().parse_args())
