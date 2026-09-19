import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const inventory = JSON.parse(await fs.readFile(path.join(root, "data", "qa", "pdf_inventory.json"), "utf8"));
const summary = JSON.parse(await fs.readFile(path.join(root, "data", "qa", "pdf_inventory_summary.json"), "utf8"));
const outputDir = path.join(root, "outputs", "source_catalog");
await fs.mkdir(outputDir, { recursive: true });

const regions = [
  "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "제주",
  "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남",
  "포항", "안양", "부천", "청주", "군산", "서산", "부평", "영주", "태안",
  "담양", "영암", "인제", "함양", "구례", "부여", "태백", "춘천", "관악",
  "강동", "강북", "금정", "나주", "정읍", "익산", "철원", "화성", "옥천"
];

function inferRegion(filename) {
  const found = regions.filter((region) => filename.includes(region));
  return found.length ? [...new Set(found)].join(", ") : "전국/확인 필요";
}

function inferYear(filename) {
  const matches = filename.match(/(?:19|20)\d{2}/g) ?? [];
  const years = matches.map(Number).filter((year) => year >= 1990 && year <= 2026);
  return years.length ? Math.max(...years) : null;
}

function titleFromFilename(filename) {
  return filename
    .replace(/\.pdf$/i, "")
    .replace(/_compressed|_optimize|_opt|_final/gi, "")
    .replace(/\s*\(\d+\)\s*$/, "")
    .replace(/\[[^\]]*\]/g, "")
    .replace(/[_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function classify(row) {
  if (row.status !== "ok") return { priority: "제외", enabled: "아니오", reason: row.error || "열기 실패" };
  if (Number(row.duplicate_count) > 1) return { priority: "검토", enabled: "보류", reason: "완전 중복 후보" };
  const topics = row.topics ?? "";
  const core = ["외식산업", "대표음식·메뉴", "상권활성화", "관광·특화거리"];
  if (core.some((topic) => topics.includes(topic)) && Number(row.text_page_ratio) >= 0.5) {
    return { priority: "A", enabled: "예", reason: "핵심 주제·텍스트 추출 양호" };
  }
  if (core.some((topic) => topics.includes(topic))) {
    return { priority: "B", enabled: "예", reason: "핵심 주제·OCR 또는 추가 검수 필요" };
  }
  return { priority: "C", enabled: "보류", reason: "보조 주제 또는 관련성 검토 필요" };
}

const rows = inventory.map((row, index) => {
  const cls = classify(row);
  return [
    index + 1,
    cls.priority,
    cls.enabled,
    row.filename,
    titleFromFilename(row.filename),
    inferYear(row.filename),
    inferRegion(row.filename),
    "",
    row.parser_type,
    (row.topics ?? "").replaceAll("|", ", "),
    Number(row.pages),
    Number(row.size_mb),
    Number(row.text_page_ratio),
    Number(row.ocr_pages),
    Number(row.duplicate_count),
    row.status === "ok" ? "정상" : "오류",
    cls.reason,
    "",
    row.sha256,
    ""
  ];
});

const headers = [
  "번호", "우선순위", "사용여부", "파일명", "문서제목", "발행연도", "지역", "발행기관",
  "문서유형", "주제", "페이지", "용량MB", "텍스트비율", "OCR후보페이지", "동일파일수",
  "파일상태", "판정사유", "원문URL", "파일해시", "검수메모"
];

const workbook = Workbook.create();
const summarySheet = workbook.worksheets.add("요약");
const docsSheet = workbook.worksheets.add("문서목록");
const rulesSheet = workbook.worksheets.add("분류기준");

for (const sheet of [summarySheet, docsSheet, rulesSheet]) {
  sheet.showGridLines = false;
}

summarySheet.getRange("A1:F1").merge();
summarySheet.getRange("A1").values = [["지역 외식산업 컨설팅 AI 출처 관리"]];
summarySheet.getRange("A2:F2").merge();
summarySheet.getRange("A2").values = [["PDF 원본의 상태와 전처리 우선순위를 관리합니다. 발행기관·연도·원문 URL은 검수 과정에서 보완하세요."]];
summarySheet.getRange("A4:B10").values = [
  ["항목", "값"],
  ["전체 PDF", summary.files],
  ["정상 PDF", summary.valid_files],
  ["오류 PDF", summary.invalid_files],
  ["총 페이지", summary.total_pages],
  ["OCR 후보 페이지", summary.ocr_candidate_pages],
  ["완전 중복 파일", summary.exact_duplicate_files]
];
summarySheet.getRange("D4:E8").values = [
  ["문서유형", "파일 수"],
  ...Object.entries(summary.parser_types)
];
summarySheet.getRange("D11:E19").values = [
  ["주제", "관련 문서 수"],
  ...Object.entries(summary.topics)
];
summarySheet.getRange("A12:B17").values = [
  ["다음 작업", "설명"],
  ["1", "A등급 문서의 발행기관·발행연도·원문 URL 확인"],
  ["2", "중복 후보에서 사용할 대표 파일 한 개 지정"],
  ["3", "오류 파일은 재다운로드하거나 사용여부를 아니오로 유지"],
  ["4", "스캔 문서는 OCR 우선순위를 확인"],
  ["5", "검수 완료 후 자동 전처리·임베딩 실행"]
];

summarySheet.getRange("A1:F1").format.font = { name: "Arial", size: 16, bold: true, color: "#172033" };
summarySheet.getRange("A2:F2").format.font = { name: "Arial", size: 10, italic: true, color: "#667085" };
for (const range of ["A4:B4", "D4:E4", "D11:E11", "A12:B12"]) {
  summarySheet.getRange(range).format = { fill: "#25364D", font: { name: "Arial", bold: true, color: "#FFFFFF" } };
}
summarySheet.getRange("A4:E19").format.font = { name: "Arial", size: 10 };
summarySheet.getRange("B5:B10").format.numberFormat = "#,##0";
summarySheet.getRange("E5:E19").format.numberFormat = "#,##0";
summarySheet.getRange("A1:F19").format.autofitRows();
summarySheet.getRange("A:A").format.columnWidth = 22;
summarySheet.getRange("B:B").format.columnWidth = 50;
summarySheet.getRange("C:C").format.columnWidth = 3;
summarySheet.getRange("D:D").format.columnWidth = 24;
summarySheet.getRange("E:E").format.columnWidth = 14;

docsSheet.getRange("A1:T1").merge();
docsSheet.getRange("A1").values = [["문서 출처 목록"]];
docsSheet.getRange("A2:T2").merge();
docsSheet.getRange("A2").values = [["노란색 열은 검수·보완 대상입니다. 원문 URL과 발행기관은 확인된 정보만 입력하세요."]];
docsSheet.getRange("A4").write([headers, ...rows]);
const table = docsSheet.tables.add(`A4:T${rows.length + 4}`, true, "SourceDocuments");
table.style = "TableStyleMedium2";
docsSheet.freezePanes.freezeRows(4);
docsSheet.freezePanes.freezeColumns(4);
docsSheet.getRange("A1:T1").format.font = { name: "Arial", size: 15, bold: true, color: "#172033" };
docsSheet.getRange("A2:T2").format.font = { name: "Arial", size: 10, italic: true, color: "#667085" };
docsSheet.getRange(`A5:T${rows.length + 4}`).format.font = { name: "Arial", size: 9 };
docsSheet.getRange(`F5:F${rows.length + 4}`).format.numberFormat = "0";
docsSheet.getRange(`K5:L${rows.length + 4}`).format.numberFormat = "#,##0.00";
docsSheet.getRange(`M5:M${rows.length + 4}`).format.numberFormat = "0.0%";
docsSheet.getRange(`N5:O${rows.length + 4}`).format.numberFormat = "#,##0";
docsSheet.getRange(`B5:C${rows.length + 4}`).format.fill = "#FFF4CC";
docsSheet.getRange(`F5:H${rows.length + 4}`).format.fill = "#FFF9E8";
docsSheet.getRange(`R5:R${rows.length + 4}`).format.fill = "#FFF4CC";
docsSheet.getRange(`T5:T${rows.length + 4}`).format.fill = "#FFF9E8";
docsSheet.getRange(`B5:B${rows.length + 4}`).dataValidation = { rule: { type: "list", values: ["A", "B", "C", "검토", "제외"] } };
docsSheet.getRange(`C5:C${rows.length + 4}`).dataValidation = { rule: { type: "list", values: ["예", "보류", "아니오"] } };
docsSheet.getRange(`A4:T${rows.length + 4}`).format.verticalAlignment = "center";
docsSheet.getRange(`D5:J${rows.length + 4}`).format.wrapText = true;
docsSheet.getRange(`Q5:T${rows.length + 4}`).format.wrapText = true;

const widths = [7, 10, 10, 45, 42, 10, 18, 20, 12, 32, 10, 10, 12, 14, 12, 10, 28, 35, 18, 28];
widths.forEach((width, index) => docsSheet.getRangeByIndexes(0, index, rows.length + 4, 1).format.columnWidth = width);

docsSheet.getRange(`B5:B${rows.length + 4}`).conditionalFormats.add("containsText", { text: "A", format: { fill: "#DDF4E8", font: { bold: true, color: "#146C43" } } });
docsSheet.getRange(`B5:B${rows.length + 4}`).conditionalFormats.add("containsText", { text: "제외", format: { fill: "#FDE2E2", font: { color: "#A61B1B" } } });
docsSheet.getRange(`P5:P${rows.length + 4}`).conditionalFormats.add("containsText", { text: "오류", format: { fill: "#FDE2E2", font: { color: "#A61B1B" } } });

rulesSheet.getRange("A1:D1").merge();
rulesSheet.getRange("A1").values = [["분류 및 검수 기준"]];
rulesSheet.getRange("A3:D9").values = [
  ["구분", "사용 목적", "기준", "권장 처리"],
  ["A", "핵심 컨설팅 근거", "외식·상권 핵심 주제이며 텍스트 추출 양호", "우선 전처리·사례 카드 생성"],
  ["B", "핵심 보조 근거", "핵심 주제이나 OCR 또는 추가 검수 필요", "선택적 OCR 후 사용"],
  ["C", "일반 참고", "간접 관련 또는 보조 주제", "시간이 남으면 처리"],
  ["검토", "중복·품질 확인", "동일 파일 또는 판정 불확실", "대표본 지정"],
  ["제외", "사용하지 않음", "0바이트·손상·무관 자료", "재다운로드 또는 제외"],
  ["근거 수준", "답변 신뢰도", "실측 성과·평가·계획·의견을 구분", "성과가 없는 계획은 제안으로 표시"]
];
rulesSheet.getRange("A11:D16").values = [
  ["필드", "입력 책임", "입력 기준", "예시"],
  ["발행연도", "검수자", "표지 또는 발간정보 확인", "2024"],
  ["지역", "자동+검수", "연구대상 지역. 전국 자료는 전국", "대전 유성구"],
  ["발행기관", "검수자", "발주기관 또는 공식 발행기관", "농림축산식품부"],
  ["원문URL", "검수자", "공식 기관 원문 페이지 우선", "https://..."],
  ["검수메모", "검수자", "OCR·중복·최신성 관련 메모", "2022년 개정본 우선"]
];
for (const range of ["A3:D3", "A11:D11"]) {
  rulesSheet.getRange(range).format = { fill: "#25364D", font: { name: "Arial", bold: true, color: "#FFFFFF" } };
}
rulesSheet.getRange("A1:D1").format.font = { name: "Arial", size: 15, bold: true, color: "#172033" };
rulesSheet.getRange("A3:D16").format.font = { name: "Arial", size: 10 };
rulesSheet.getRange("A3:D16").format.wrapText = true;
rulesSheet.getRange("A3:D16").format.verticalAlignment = "top";
rulesSheet.getRange("A:A").format.columnWidth = 15;
rulesSheet.getRange("B:B").format.columnWidth = 22;
rulesSheet.getRange("C:C").format.columnWidth = 42;
rulesSheet.getRange("D:D").format.columnWidth = 42;
rulesSheet.freezePanes.freezeRows(3);

const inspect = await workbook.inspect({ kind: "table", sheetId: "문서목록", range: "A1:T12", include: "values,formulas", tableMaxRows: 12, tableMaxCols: 20 });
console.log(inspect.ndjson);

const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: "final formula error scan" });
console.log(errors.ndjson);

for (const [sheetName, range, file] of [
  ["요약", "A1:F19", "summary-preview.png"],
  ["문서목록", "A1:T18", "documents-preview.png"],
  ["분류기준", "A1:D16", "rules-preview.png"]
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1.3, format: "png" });
  await fs.writeFile(path.join(root, "data", "qa", file), new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(workbook);
const outputPath = path.join(outputDir, "지역외식산업_AI_출처관리대장.xlsx");
await output.save(outputPath);
console.log(outputPath);

