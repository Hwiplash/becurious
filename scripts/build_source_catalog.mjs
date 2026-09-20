import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const readJson = async (...parts) => JSON.parse(await fs.readFile(path.join(root, ...parts), "utf8"));
const catalog = await readJson("data", "processed", "catalog.json");
const chunks = await readJson("data", "rag_index", "chunks.json");
const audit = await readJson("data", "qa", "pdf_inventory_summary.json");
const outputDir = path.join(root, "outputs", "source_catalog");
await fs.mkdir(outputDir, { recursive: true });

const countBy = (items, keyFn) => {
  const result = new Map();
  for (const item of items) {
    const key = keyFn(item);
    result.set(key, (result.get(key) ?? 0) + 1);
  }
  return result;
};
const join = (value) => Array.isArray(value) ? value.join(", ") : (value ?? "");
const policyChunks = chunks.filter((x) => x.chunk_type === "body" || x.chunk_type === "slide");
const specialtyChunks = chunks.filter((x) => x.chunk_type === "regional-specialty");
const taxonomyChunks = chunks.filter((x) => x.chunk_type === "industry-taxonomy");
const policyChunkCounts = countBy(policyChunks, (x) => x.document_id);

const policyRows = catalog.map((doc, index) => {
  const indexed = policyChunkCounts.get(doc.document_id) ?? 0;
  return [index + 1, indexed > 0 ? "사용" : "제외/미색인", doc.priority ?? "", doc.filename,
    doc.document_id, doc.year ?? "", join(doc.regions), join(doc.topics), doc.parser_type ?? "",
    Number(doc.pages ?? 0), indexed, doc.status ?? "", doc.ocr_override ? "예" : "아니오",
    `data/pdfs/${doc.filename}`, doc.sha256 ?? "", doc.exclude_reason ?? ""];
});
const specialtyRows = specialtyChunks.map((item, index) => [index + 1, "사용", item.specialty ?? item.section ?? "",
  item.document_id ?? "", join(item.regions), join(item.foods), item.extraction_confidence ?? "",
  item.source_status ?? "", item.source_url ?? item.source ?? "", item.pdf_path ?? "", item.id ?? "", item.text?.length ?? 0]);
const taxonomyRows = taxonomyChunks.map((item, index) => [index + 1, "사용", item.industry_code ?? "",
  item.industry_name ?? "", join(item.aliases), item.document_id ?? "", item.source ?? "업종 분류 상세", item.id ?? ""]);

const workbook = Workbook.create();
const summarySheet = workbook.worksheets.add("요약");
const policySheet = workbook.worksheets.add("정책PDF");
const specialtySheet = workbook.worksheets.add("지역특산품");
const taxonomySheet = workbook.worksheets.add("업종분류");
const rulesSheet = workbook.worksheets.add("관리기준");
for (const sheet of [summarySheet, policySheet, specialtySheet, taxonomySheet, rulesSheet]) sheet.showGridLines = false;

const title = (sheet, end, text, subtitle) => {
  sheet.getRange(`A1:${end}1`).merge();
  sheet.getRange("A1").values = [[text]];
  sheet.getRange(`A2:${end}2`).merge();
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange("A1").format.font = { name: "Arial", size: 15, bold: true, color: "#172033" };
  sheet.getRange("A2").format.font = { name: "Arial", size: 10, italic: true, color: "#667085" };
};
const addTable = (sheet, headers, rows, name) => {
  sheet.getRange("A4").write([headers, ...rows]);
  const lastColumn = String.fromCharCode(64 + headers.length);
  const lastRow = rows.length + 4;
  const table = sheet.tables.add(`A4:${lastColumn}${lastRow}`, true, name);
  table.style = "TableStyleMedium2";
  sheet.freezePanes.freezeRows(4);
  sheet.getRange(`A4:${lastColumn}${lastRow}`).format.verticalAlignment = "center";
  sheet.getRange(`A5:${lastColumn}${lastRow}`).format.font = { name: "Arial", size: 9 };
  return { lastColumn, lastRow };
};

title(summarySheet, "F", "RAG 전체 출처 관리 대장", "현재 data/rag_index/chunks.json에 실제 포함된 근거와 원본 문서 상태를 기준으로 생성했습니다.");
summarySheet.getRange("A4:B12").values = [
  ["항목", "값"], ["전체 RAG 청크", chunks.length], ["정책·연구 PDF 청크", policyChunks.length],
  ["지역 특산품 청크", specialtyChunks.length], ["업종분류 청크", taxonomyChunks.length],
  ["PDF 원본", catalog.length], ["RAG 색인 PDF", policyChunkCounts.size], ["PDF 총 페이지", audit.total_pages],
  ["마지막 갱신일", new Date().toISOString().slice(0, 10)]
];
summarySheet.getRange("D4:F8").values = [
  ["출처군", "관리 단위", "기준 파일"], ["정책·연구 PDF", "문서", "data/processed/catalog.json"],
  ["지역 특산품", "특산품 항목", "data/processed/specialty_chunks.json"],
  ["업종분류", "업종 코드", "data/processed/industry_taxonomy_chunks.json"],
  ["실제 검색 인덱스", "청크", "data/rag_index/chunks.json"]
];
for (const range of ["A4:B4", "D4:F4"]) summarySheet.getRange(range).format = { fill: "#25364D", font: { name: "Arial", bold: true, color: "#FFFFFF" } };
summarySheet.getRange("A4:F12").format.font = { name: "Arial", size: 10 };
summarySheet.getRange("B5:B11").format.numberFormat = "#,##0";
[24, 18, 3, 24, 18, 42].forEach((w, i) => summarySheet.getRangeByIndexes(0, i, 12, 1).format.columnWidth = w);

title(policySheet, "P", "정책·연구 PDF 출처", "PDF 원본 248건과 실제 색인 청크 수를 연결했습니다. '사용'은 현재 RAG 인덱스에 포함된 문서입니다.");
const policy = addTable(policySheet,
  ["번호", "RAG상태", "우선순위", "파일명", "문서ID", "발행연도", "지역", "주제", "문서유형", "페이지", "RAG청크", "처리상태", "OCR대체", "로컬경로", "SHA-256", "제외사유"], policyRows, "PolicySources");
policySheet.getRange(`D5:H${policy.lastRow}`).format.wrapText = true;
policySheet.getRange(`N5:P${policy.lastRow}`).format.wrapText = true;
[7, 12, 10, 44, 20, 10, 20, 30, 12, 10, 11, 12, 10, 48, 20, 28].forEach((w, i) => policySheet.getRangeByIndexes(0, i, policy.lastRow, 1).format.columnWidth = w);
policySheet.getRange(`B5:B${policy.lastRow}`).conditionalFormats.add("containsText", { text: "미색인", format: { fill: "#FDE2E2", font: { color: "#A61B1B" } } });

title(specialtySheet, "L", "지역 특산품 출처", "특산품·지역·활용 음식과 원문 URL을 항목별로 관리합니다.");
const specialty = addTable(specialtySheet,
  ["번호", "RAG상태", "특산품", "문서ID", "지역", "활용음식", "추출신뢰도", "원문상태", "원문URL", "PDF경로", "청크ID", "본문글자수"], specialtyRows, "SpecialtySources");
specialtySheet.getRange(`C5:J${specialty.lastRow}`).format.wrapText = true;
[7, 10, 20, 24, 22, 30, 12, 12, 48, 42, 28, 12].forEach((w, i) => specialtySheet.getRangeByIndexes(0, i, specialty.lastRow, 1).format.columnWidth = w);

title(taxonomySheet, "H", "업종분류 출처", "정책 메뉴 추천에 사용하는 표준 업종 코드와 검색 별칭입니다.");
const taxonomy = addTable(taxonomySheet,
  ["번호", "RAG상태", "업종코드", "표준업종명", "검색별칭", "문서ID", "출처", "청크ID"], taxonomyRows, "IndustrySources");
taxonomySheet.getRange(`D5:H${taxonomy.lastRow}`).format.wrapText = true;
[7, 10, 12, 18, 70, 26, 22, 30].forEach((w, i) => taxonomySheet.getRangeByIndexes(0, i, taxonomy.lastRow, 1).format.columnWidth = w);

title(rulesSheet, "D", "출처 관리 및 갱신 기준", "앱 검색 결과와 이 대장의 수치가 다르면 실제 검색 인덱스(data/rag_index/chunks.json)를 우선합니다.");
rulesSheet.getRange("A4:D13").values = [
  ["구분", "판정 기준", "관리 파일", "갱신 방법"],
  ["정책 PDF", "body 또는 slide 청크가 존재", "catalog.json / chunks.json", "audit_pdfs.py → build_local_corpus.py → 인덱스 추가"],
  ["지역 특산품", "regional-specialty 청크가 존재", "specialty_chunks.json / chunks.json", "특산품 전처리 후 인덱스 추가"],
  ["업종분류", "industry-taxonomy 청크가 존재", "industry_taxonomy_chunks.json / chunks.json", "분류표 전처리 후 인덱스 추가"],
  ["사용", "현재 RAG 인덱스에 하나 이상의 청크 포함", "chunks.json", "검색 회귀 테스트 수행"],
  ["제외/미색인", "원본은 있으나 현재 인덱스에 없음", "catalog.json", "오류·중복·품질 사유 확인"],
  ["원문 URL", "공식 기관 또는 원 게시 페이지", "지역특산품 탭", "접속 불가 시 URL 상태 갱신"],
  ["로컬 경로", "저장소 루트 기준 상대 경로", "정책PDF/지역특산품 탭", "파일 이동 시 대장 재생성"],
  ["재생성", "인덱스 갱신 후 실행", "scripts/build_source_catalog.mjs", "node scripts/build_source_catalog.mjs"],
  ["검증", "수식 오류 없음·시트 렌더 정상", "data/qa/*source-preview.png", "미리보기와 자동 검사를 함께 확인"]
];
rulesSheet.getRange("A4:D4").format = { fill: "#25364D", font: { name: "Arial", bold: true, color: "#FFFFFF" } };
rulesSheet.getRange("A4:D13").format.wrapText = true;
rulesSheet.getRange("A4:D13").format.verticalAlignment = "top";
[18, 38, 42, 52].forEach((w, i) => rulesSheet.getRangeByIndexes(0, i, 13, 1).format.columnWidth = w);
rulesSheet.freezePanes.freezeRows(4);

const inspect = await workbook.inspect({ kind: "table", sheetId: "요약", range: "A1:F12", include: "values,formulas", tableMaxRows: 12, tableMaxCols: 6 });
console.log(inspect.ndjson);
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: "final formula error scan" });
console.log(errors.ndjson);
for (const [sheetName, range, file] of [
  ["요약", "A1:F12", "source-summary-preview.png"], ["정책PDF", "A1:P14", "source-policy-preview.png"],
  ["지역특산품", "A1:L14", "source-specialty-preview.png"], ["업종분류", "A1:H15", "source-taxonomy-preview.png"],
  ["관리기준", "A1:D13", "source-rules-preview.png"]
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1.2, format: "png" });
  await fs.writeFile(path.join(root, "data", "qa", file), new Uint8Array(await preview.arrayBuffer()));
}
const output = await SpreadsheetFile.exportXlsx(workbook);
const outputPath = path.join(outputDir, "지역외식산업_AI_출처관리대장.xlsx");
await output.save(outputPath);
console.log(outputPath);
