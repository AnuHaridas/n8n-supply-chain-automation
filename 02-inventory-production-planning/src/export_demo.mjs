import { execFileSync } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const projectDirectory = path.resolve(process.env.PROJECT_DIRECTORY ?? process.cwd());
const pythonExecutable = process.env.PYTHON_EXECUTABLE ?? "python";
const outputPath = path.join(
  projectDirectory,
  "outputs",
  "Demand_Supply_Response.xlsx",
);
const previewDirectory = process.env.PREVIEW_DIRECTORY;

const payloadText = execFileSync(
  pythonExecutable,
  ["-m", "src.demo_export_data"],
  { cwd: projectDirectory, encoding: "utf8" },
);
const payload = JSON.parse(payloadText);

const workbook = Workbook.create();
const fgSheet = workbook.worksheets.add("FG Plan");
const componentSheet = workbook.worksheets.add("Component Plan");
const fontFamily = "Arial";

const fgColumns = [
  ["Item", "item"],
  ["Period", "period"],
  ["Demand", "demand"],
  ["Opening inventory", "opening_inventory"],
  ["In-transit", "in_transit"],
  ["Existing production receipt", "existing_production_receipt"],
  ["Closing balance before new production", "closing_balance_before_new_production"],
  ["Physical shortage", "physical_shortage"],
  ["Safety stock target", "safety_stock_target"],
  ["Net production requirement", "net_production_requirement"],
  ["Recommended production", "recommended_production"],
  ["Production start period", "production_start_period"],
  ["Status", "status"],
];

const componentColumns = [
  ["Component", "component"],
  ["Parent FG", "parent_fg"],
  ["Production order / proposal reference", "production_order_reference"],
  ["Component need period", "component_need_period"],
  ["Gross requirement", "gross_requirement"],
  ["Opening inventory", "opening_inventory"],
  ["Scheduled PO receipt", "scheduled_po_receipt"],
  ["Closing balance", "closing_balance"],
  ["Physical shortage", "physical_shortage"],
  ["Purchase lead time", "purchase_lead_time"],
  ["Required PO release period", "required_po_release_period"],
  ["Status", "status"],
];

function columnLetter(index) {
  let value = index + 1;
  let result = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    result = String.fromCharCode(65 + remainder) + result;
    value = Math.floor((value - 1) / 26);
  }
  return result;
}

function writePlanSheet({
  sheet,
  title,
  rows,
  columns,
  tableName,
  widths,
  numericColumnIndexes,
}) {
  const lastColumn = columnLetter(columns.length - 1);
  const lastRow = 5 + rows.length;
  sheet.showGridLines = false;
  sheet.tabColor = "#1F4E78";
  sheet.getRange("A2").values = [[title]];
  sheet.getRange("A3").values = [[
    "Generated from deterministic Python planning results. Values only; no Excel planning formulas.",
  ]];
  sheet.getRange(`A5:${lastColumn}${lastRow}`).values = [
    columns.map(([label]) => label),
    ...rows.map((row) => columns.map(([, key]) => row[key] ?? null)),
  ];

  const usedRange = sheet.getRange(`A2:${lastColumn}${lastRow}`);
  usedRange.format.font = { name: fontFamily, size: 10, color: "#1F2937" };
  usedRange.format.verticalAlignment = "center";

  sheet.getRange("A2").format.font = {
    name: fontFamily,
    size: 14,
    bold: true,
    color: "#1F2937",
  };
  sheet.getRange(`A3:${lastColumn}3`).format = {
    font: { name: fontFamily, size: 10, italic: true, color: "#5B6573" },
    borders: { bottom: { style: "thin", color: "#A7B0BC" } },
  };
  sheet.getRange(`A5:${lastColumn}5`).format = {
    fill: "#1F4E78",
    font: { name: fontFamily, size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: {
      insideVertical: { style: "thin", color: "#FFFFFF" },
      bottom: { style: "medium", color: "#17365D" },
    },
  };
  sheet.getRange(`A6:${lastColumn}${lastRow}`).format.borders = {
    insideHorizontal: { style: "thin", color: "#D9E2F3" },
  };

  columns.forEach((_, index) => {
    const letter = columnLetter(index);
    sheet.getRange(`${letter}:${letter}`).format.columnWidth = widths[index];
  });
  numericColumnIndexes.forEach((index) => {
    const letter = columnLetter(index);
    sheet.getRange(`${letter}6:${letter}${lastRow}`).format.numberFormat = "#,##0";
    sheet.getRange(`${letter}6:${letter}${lastRow}`).format.horizontalAlignment = "right";
  });

  sheet.getRange(`A5:${lastColumn}${lastRow}`).format.rowHeight = 22;
  sheet.getRange(`A5:${lastColumn}5`).format.rowHeight = 40;
  sheet.freezePanes.freezeRows(5);
  const table = sheet.tables.add(`A5:${lastColumn}${lastRow}`, true, tableName);
  table.style = "TableStyleMedium2";
  table.showBandedColumns = false;

  const statusIndex = columns.findIndex(([, key]) => key === "status");
  const statusLetter = columnLetter(statusIndex);
  rows.forEach((row, index) => {
    const statusCell = sheet.getRange(`${statusLetter}${index + 6}`);
    if (row.status === "PAST_DUE_RELEASE") {
      statusCell.format = {
        fill: "#FDE9E7",
        font: { name: fontFamily, size: 10, bold: true, color: "#B42318" },
      };
    } else if (row.status === "SHORTAGE" || row.status === "PRODUCTION REQUIRED") {
      statusCell.format = {
        fill: "#FFF2CC",
        font: { name: fontFamily, size: 10, bold: true, color: "#7F6000" },
      };
    }
  });
}

writePlanSheet({
  sheet: fgSheet,
  title: "Finished-goods demand and supply response",
  rows: payload.fg_plan,
  columns: fgColumns,
  tableName: "FGPlanTable",
  widths: [14, 10, 12, 18, 12, 24, 29, 18, 19, 24, 23, 22, 22],
  numericColumnIndexes: [2, 3, 4, 5, 6, 7, 8, 9, 10],
});

writePlanSheet({
  sheet: componentSheet,
  title: "Component gross-to-net plan",
  rows: payload.component_plan,
  columns: componentColumns,
  tableName: "ComponentPlanTable",
  widths: [16, 14, 32, 20, 18, 18, 21, 18, 18, 18, 25, 20],
  numericColumnIndexes: [4, 5, 6, 7, 8, 9],
});

workbook.recalculate();

await workbook.inspect({
  kind: "table",
  range: "FG Plan!A2:M9",
  include: "values,formulas",
  tableMaxRows: 10,
  tableMaxCols: 13,
});
await workbook.inspect({
  kind: "table",
  range: "Component Plan!A2:L13",
  include: "values,formulas",
  tableMaxRows: 15,
  tableMaxCols: 12,
});
await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});

if (previewDirectory) {
  await fs.mkdir(previewDirectory, { recursive: true });
  for (const sheetName of ["FG Plan", "Component Plan"]) {
    const preview = await workbook.render({
      sheetName,
      autoCrop: "all",
      scale: 1,
      format: "png",
    });
    await fs.writeFile(
      path.join(previewDirectory, `${sheetName.replaceAll(" ", "_")}.png`),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

function formatEntries(entries, formatter) {
  return entries.length > 0 ? entries.map(formatter).join("; ") : "None";
}

console.log(
  `FG additional production required: ${formatEntries(
    payload.summary.fg_additional_production_required,
    (entry) => `${entry.item} ${entry.period} = ${entry.quantity}`,
  )}`,
);
console.log(
  `Component shortages: ${formatEntries(
    payload.summary.component_shortages,
    (entry) => `${entry.component} ${entry.period} = ${entry.quantity}`,
  )}`,
);
console.log(
  `Required production start period: ${formatEntries(
    payload.summary.production_start_periods,
    (entry) => `${entry.item} ${entry.available_period} -> ${entry.start_period ?? entry.status}`,
  )}`,
);
console.log(
  `Past-due component release condition: ${formatEntries(
    payload.summary.past_due_component_releases,
    (entry) => `${entry.component} ${entry.period}`,
  )}`,
);
console.log(`Output workbook path: ${outputPath}`);
