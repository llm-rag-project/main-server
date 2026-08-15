import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [comparisonPath, naturalAuditPath, diagnosticsPath, archivePath, outputPath, previewDir] = process.argv.slice(2);
if (!comparisonPath || !naturalAuditPath || !diagnosticsPath || !outputPath || !previewDir) {
  throw new Error("Usage: node build_hongbo_comparison_workbook.mjs comparison natural diagnostics archive output previewDir");
}

const comparison = JSON.parse(await fs.readFile(comparisonPath, "utf8"));
const natural = JSON.parse(await fs.readFile(naturalAuditPath, "utf8"));
const diagnostics = JSON.parse(await fs.readFile(diagnosticsPath, "utf8"));
const archive = archivePath && archivePath !== "-" ? JSON.parse(await fs.readFile(archivePath, "utf8")) : null;

const workbook = Workbook.create();
const palette = {
  navy: "#1F4E78",
  blue: "#2E75B6",
  pale: "#EAF2F8",
  pale2: "#F5F8FB",
  green: "#E2F0D9",
  amber: "#FFF2CC",
  red: "#FCE4E4",
  gray: "#667085",
  border: "#D6DEE8",
  white: "#FFFFFF",
};

function colName(index) {
  let value = index + 1;
  let result = "";
  while (value > 0) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

function rangeFor(startRow, startCol, rowCount, colCount) {
  const start = `${colName(startCol)}${startRow}`;
  const end = `${colName(startCol + colCount - 1)}${startRow + rowCount - 1}`;
  return `${start}:${end}`;
}

function setTitle(sheet, title, subtitle, endCol) {
  sheet.showGridLines = false;
  sheet.getRange(`A1:${endCol}2`).merge();
  sheet.getRange("A1").values = [[title]];
  sheet.getRange(`A1:${endCol}2`).format = {
    fill: palette.navy,
    font: { bold: true, color: palette.white, size: 18 },
    verticalAlignment: "center",
    horizontalAlignment: "left",
  };
  sheet.getRange(`A3:${endCol}3`).merge();
  sheet.getRange("A3").values = [[subtitle]];
  sheet.getRange(`A3:${endCol}3`).format = {
    fill: palette.pale,
    font: { color: palette.gray, size: 10 },
    verticalAlignment: "center",
  };
  sheet.getRange("A1:A3").format.rowHeight = 24;
}

function writeTable(sheet, startRow, headers, rows, widths, tableName) {
  const values = [headers, ...rows];
  const address = rangeFor(startRow, 0, values.length, headers.length);
  sheet.getRange(address).values = values;
  const header = sheet.getRange(rangeFor(startRow, 0, 1, headers.length));
  header.format = {
    fill: palette.navy,
    font: { bold: true, color: palette.white, size: 9 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: palette.border },
  };
  const body = sheet.getRange(rangeFor(startRow + 1, 0, Math.max(rows.length, 1), headers.length));
  body.format = {
    font: { size: 9, color: "#1F2937" },
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "inside", style: "thin", color: palette.border },
  };
  for (let index = 0; index < widths.length; index += 1) {
    sheet.getRange(`${colName(index)}:${colName(index)}`).format.columnWidth = widths[index];
  }
  if (rows.length) {
    const table = sheet.tables.add(address, true, tableName);
    table.style = "TableStyleMedium2";
    table.showBandedRows = true;
    table.showFilterButton = true;
  }
  sheet.freezePanes.freezeRows(startRow);
}

const summary = comparison.summary;
const sectionStats = new Map();
for (const payload of Object.values(comparison.dates)) {
  for (const item of payload.details || []) {
    const section = item["원본 섹션"] || "미분류";
    const outcome = item["비교 결과"] || "";
    const current = sectionStats.get(section) || { original: 0, matched: 0 };
    current.original += 1;
    if (outcome === "일치" || outcome === "동일 주제 대표 매체 차이") {
      current.matched += 1;
    }
    sectionStats.set(section, current);
  }
}
const summarySheet = workbook.worksheets.add("요약");
setTitle(summarySheet, "홍보처 기존 메일 · 서버 AI 선정 비교", "일반 재수집과 검증용 후보 보강을 구분한 분석 결과", "J");
summarySheet.getRange("A5:J5").values = [["비교 날짜", "홍보처 원본", "AI 선정", "정확 일치", "동일 주제", "총 일치", "일치 실패", "서버만 선정", "전체 일치율", "일반 수집 확인"]];
summarySheet.getRange("A6:J6").values = [[
  summary.date_count,
  summary.original_count,
  summary.selected_count,
  summary.exact_match_count,
  summary.topic_match_count,
  summary.total_match_count,
  summary.original_unmatched_count,
  summary.server_only_count,
  summary.original_count ? summary.total_match_count / summary.original_count : 0,
  natural.summary?.original_found_in_candidates || 0,
]];
summarySheet.getRange("A5:J5").format = {
  fill: palette.blue,
  font: { bold: true, color: palette.white, size: 9 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
summarySheet.getRange("A6:J6").format = {
  fill: palette.pale,
  font: { bold: true, color: palette.navy, size: 14 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: palette.border },
};
summarySheet.getRange("I6").format.numberFormat = "0.0%";
summarySheet.getRange("A5:J6").format.rowHeight = 30;
summarySheet.getRange("A:J").format.columnWidth = 14;

summarySheet.getRange("A9:B13").values = [
  ["결과 구분", "건수"],
  ["정확 일치", summary.exact_match_count],
  ["동일 주제·대표 매체 차이", summary.topic_match_count],
  ["원본 기준 일치 실패", summary.original_unmatched_count],
  ["서버만 선정", summary.server_only_count],
];
summarySheet.getRange("A9:B9").format = { fill: palette.navy, font: { bold: true, color: palette.white } };
summarySheet.getRange("A10:B13").format = { fill: palette.pale2, borders: { preset: "inside", style: "thin", color: palette.border } };
const outcomeChart = summarySheet.charts.add("bar", summarySheet.getRange("A9:B13"));
outcomeChart.title = "비교 결과 구성";
outcomeChart.hasLegend = false;
outcomeChart.setPosition("D9", "J23");

summarySheet.getRange("A16:C16").values = [["일치 실패 구분", "건수", "설명"]];
const reasonDescriptions = {
  "AI/정책 제외": "후보에는 있었으나 AI 대표 선정·중복 주제·최대 기사 수 정책에서 제외",
  "일반 수집 누락": "일반 검색 재수집은 실패했으나 검증용 원본 후보에서는 확인",
  "후보 미확보": "일반 재수집과 검증 후보 보강 후에도 확인되지 않음",
  "선정되지 않음": "후보에는 있으나 최종 대표 기사로 선택되지 않음",
};
const reasonRows = Object.entries(summary.reason_counts || {}).sort((a, b) => b[1] - a[1]).map(([name, count]) => [name, count, reasonDescriptions[name] || "기사별 상세 대조 참조"]);
summarySheet.getRange(rangeFor(17, 0, Math.max(reasonRows.length, 1), 3)).values = reasonRows.length ? reasonRows : [["없음", 0, ""]];
summarySheet.getRange("A16:C16").format = { fill: palette.navy, font: { bold: true, color: palette.white } };
summarySheet.getRange(rangeFor(17, 0, Math.max(reasonRows.length, 1), 3)).format = { wrapText: true, borders: { preset: "inside", style: "thin", color: palette.border } };
summarySheet.getRange("A:A").format.columnWidth = 24;
summarySheet.getRange("B:B").format.columnWidth = 12;
summarySheet.getRange("C:C").format.columnWidth = 56;

summarySheet.getRange("A22:C22").values = [["원본 섹션", "일치/원본", "일치율"]];
const sectionRows = ["동국대 [법인/건학위]", "대학 [교육]", "불교 [종단]"].map((name) => {
  const stat = sectionStats.get(name) || { original: 0, matched: 0 };
  return [name, `${stat.matched}/${stat.original}`, stat.original ? stat.matched / stat.original : 0];
});
summarySheet.getRange("A23:C25").values = sectionRows;
summarySheet.getRange("A22:C22").format = { fill: palette.navy, font: { bold: true, color: palette.white } };
summarySheet.getRange("A23:C25").format = { borders: { preset: "inside", style: "thin", color: palette.border } };
summarySheet.getRange("C23:C25").format.numberFormat = "0.0%";

const datesSheet = workbook.worksheets.add("날짜별 비교");
const dateHeaders = ["날짜", "홍보처 원본 기사", "서버 후보 기사", "AI 선정 기사", "정확 일치", "동일 주제·대표 매체 차이", "총 일치", "원본 기준 일치 실패", "서버만 선정", "일치율"];
const dateRows = Object.entries(comparison.dates).map(([date, payload]) => {
  const row = payload.summary;
  return [date, row["홍보처 원본 기사"], row["서버 후보 기사"], row["AI 선정 기사"], row["정확 일치"], row["동일 주제·대표 매체 차이"], row["총 일치"], row["원본 기준 일치 실패"], row["서버만 선정"], (row["일치율(%)"] || 0) / 100];
});
writeTable(datesSheet, 1, dateHeaders, dateRows, [13, 14, 14, 13, 12, 20, 12, 18, 13, 12], "DateComparisonTable");
datesSheet.getRange(`J2:J${dateRows.length + 1}`).format.numberFormat = "0.0%";
datesSheet.getRange(`H2:H${dateRows.length + 1}`).conditionalFormats.add("cellIs", { operator: "greaterThan", formula: 0, format: { fill: palette.red, font: { color: "#9C0006" } } });
datesSheet.getRange(`G2:G${dateRows.length + 1}`).conditionalFormats.add("cellIs", { operator: "greaterThan", formula: 0, format: { fill: palette.green, font: { color: "#375623" } } });

const detailSheet = workbook.worksheets.add("원본 기사별 대조");
const detailHeaders = ["메일 날짜", "원본 섹션", "원본 순번", "원본 기사 제목", "원본 언론사", "원본 URL", "비교 결과", "일치 방식", "유사도", "서버 선정 제목", "서버 선정 언론사", "서버 선정 URL", "차이/제외 이유", "일반 재수집 후보 확인", "최종 후보 확인"];
const details = Object.values(comparison.dates).flatMap((payload) => payload.details).map((item) => detailHeaders.map((header) => item[header] ?? ""));
writeTable(detailSheet, 1, detailHeaders, details, [12, 20, 9, 42, 16, 40, 18, 20, 10, 42, 16, 40, 56, 16, 14], "ArticleDetailTable");
detailSheet.getRange(`G2:G${details.length + 1}`).conditionalFormats.add("containsText", { text: "일치", format: { fill: palette.green } });
detailSheet.getRange(`G2:G${details.length + 1}`).conditionalFormats.add("containsText", { text: "누락", format: { fill: palette.red } });

const serverSheet = workbook.worksheets.add("서버 추가 선정");
const serverHeaders = ["메일 날짜", "서버 선정 제목", "언론사", "상위 분류", "하위 분류", "우선순위", "선정 이유", "URL"];
const serverRows = Object.values(comparison.dates)
  .flatMap((payload) => payload.server_only || [])
  .map((item) => serverHeaders.map((header) => item[header] ?? ""));
if (!serverRows.length) serverRows.push(["", "서버만 선정된 기사 없음", "", "", "", "", "", ""]);
writeTable(serverSheet, 1, serverHeaders, serverRows, [12, 44, 16, 18, 22, 12, 52, 42], "ServerOnlyTable");

const diagnosticsSheet = workbook.worksheets.add("수집 진단");
const diagnosticHeaders = ["메일 날짜", "소스 발견 건수", "신규 저장 건수", "결과 반환 소스", "시간 초과 소스", "재수집 결과 설명"];
const diagnosticRows = (diagnostics.dates || []).map((item) => diagnosticHeaders.map((header) => item[header] ?? ""));
writeTable(diagnosticsSheet, 1, diagnosticHeaders, diagnosticRows, [13, 14, 14, 34, 34, 58], "CollectionDiagnosticsTable");

const methodSheet = workbook.worksheets.add("방법론");
setTitle(methodSheet, "분석 방법 및 해석 기준", "수집 성과와 AI 선정 성과를 분리하여 해석합니다.", "H");
const methodRows = [
  ["원본 범위", "HWP/HWPX 87개 파일, 중복 문서 4개 제외, 83개 날짜·675개 기사"],
  ["일반 재수집", "현재 서비스의 업무일 범위와 Google·Naver·공식·교육·불교 소스를 그대로 사용하고 각 소스를 최대 3회 재시도"],
  ["검증용 후보 보강", "과거 검색 제공처가 결과를 반환하지 않는 날짜는 원본 메일 URL·제목을 후보에 추가해 AI 선정 기준 차이를 별도 검증"],
  ["정확 일치", "정규화된 URL 또는 제목이 같은 기사"],
  ["동일 주제·대표 매체 차이", "같은 사건·보도자료이나 AI가 다른 언론사 기사를 대표로 선택한 경우"],
  ["일치 실패", "후보 미확보, AI/정책 제외, 최대 기사 수 정책 또는 홍보처 원본과 다른 주제를 선택한 경우"],
  ["주의", "검증용 후보 보강 건수는 일반 수집 성공률에 합산하지 않음"],
  ["검증 백필", archive ? JSON.stringify(archive.database_counts || {}) : "미실행"],
];
writeTable(methodSheet, 5, ["항목", "정의"], methodRows, [24, 88], "MethodologyTable");

await fs.mkdir(previewDir, { recursive: true });
for (const [sheetName, range] of [["요약", "A1:J26"], ["날짜별 비교", "A1:J22"], ["원본 기사별 대조", "A1:O12"], ["수집 진단", "A1:F14"]]) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  const safeName = sheetName.replaceAll(" ", "_");
  await fs.writeFile(`${previewDir}/${safeName}.png`, new Uint8Array(await preview.arrayBuffer()));
}

const check = await workbook.inspect({ kind: "table", range: "요약!A1:J26", include: "values,formulas", tableMaxRows: 26, tableMaxCols: 10 });
await fs.writeFile(`${previewDir}/inspect-summary.ndjson`, check.ndjson, "utf8");
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan" });
await fs.writeFile(`${previewDir}/formula-errors.ndjson`, errors.ndjson, "utf8");

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ output: outputPath, previewDir, sheets: workbook.worksheets.items.map((sheet) => sheet.name) }));
