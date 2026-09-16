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

function uniqueInOrder(values) {
  return [...new Set(values)];
}

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

const fgPeriods = uniqueInOrder(payload.fg_plan.map((row) => row.period));
const fgItems = uniqueInOrder(payload.fg_plan.map((row) => row.item));
const fgMetricDefinitions = [
  ["Inventory", "closing_balance_before_new_production", "inventory"],
  ["Forecast / Demand", "latest_demand", "number"],
  ["Safety Stock", "safety_stock_target", "number"],
  ["Inbound ETA", "inbound_eta", "number"],
  [
    "Total Planned Production",
    "newly_calculated_production_recommendation",
    "production",
  ],
];

const fgBlocks = fgItems.map((item) => {
  const itemRows = payload.fg_plan.filter((row) => row.item === item);
  const rowByPeriod = new Map(itemRows.map((row) => [row.period, row]));
  const description = itemRows.find((row) => row.sku_description)?.sku_description ?? null;
  return {
    firstIdentity: item,
    secondIdentity: description,
    rows: fgMetricDefinitions.map(([label, key, kind]) => ({
      label,
      kind,
      values: fgPeriods.map((period) => rowByPeriod.get(period)?.[key] ?? null),
      changedFrozenPeriods: fgPeriods.map(
        (period) =>
          kind === "production" &&
          rowByPeriod.get(period)?.planning_status ===
            "FROZEN_PERIOD_PRODUCTION_CHANGE",
      ),
    })),
  };
});

const componentNeedPeriods = uniqueInOrder(
  payload.component_plan.map((row) => row.component_need_period),
);
const componentNeedPeriodSet = new Set(componentNeedPeriods);
const componentLookbackPeriods = uniqueInOrder(
  payload.component_plan
    .map((row) => row.required_po_release_period)
    .filter((period) => period != null && !componentNeedPeriodSet.has(period)),
);
const componentPeriods = [...componentLookbackPeriods, ...componentNeedPeriods];
const componentItems = uniqueInOrder(
  payload.component_plan.map((row) => row.component),
);
const componentMetricDefinitions = [
  ["Gross Requirement", "gross_requirement", "number"],
  ["Opening / Projected Inventory", "opening_inventory", "number"],
  ["Scheduled PO Receipt", "scheduled_po_receipt", "number"],
  ["Closing Balance", "closing_balance", "number"],
  ["Physical Shortage", "physical_shortage", "shortage"],
  ["Component Need Period", "component_need_period", "releaseTiming"],
  ["Required PO Release Period", "required_po_release_period", "releaseTiming"],
  ["Status", "status", "status"],
];

const componentBlocks = componentItems.map((component) => {
  const componentRows = payload.component_plan.filter(
    (row) => row.component === component,
  );
  const rowByNeedPeriod = new Map(
    componentRows.map((row) => [row.component_need_period, row]),
  );
  const releaseRowByPeriod = new Map(
    componentRows
      .filter((row) => row.required_po_release_period != null)
      .map((row) => [row.required_po_release_period, row]),
  );
  const parentFg = uniqueInOrder(
    componentRows.map((row) => row.parent_fg).filter(Boolean),
  ).join(", ");

  return {
    firstIdentity: component,
    secondIdentity: parentFg,
    rows: componentMetricDefinitions.map(([label, key, kind]) => ({
      label,
      kind,
      values: componentPeriods.map((period) => {
        if (kind === "releaseTiming") {
          return releaseRowByPeriod.get(period)?.[key] ?? null;
        }
        return rowByNeedPeriod.get(period)?.[key] ?? null;
      }),
    })),
  };
});

function applyResultCellStyle(cell, kind, value, changedFrozenPeriod = false) {
  if (value == null) {
    return;
  }
  if (kind === "production" && changedFrozenPeriod) {
    cell.format = {
      fill: "#FDE9E7",
      font: { name: fontFamily, size: 10, bold: true, color: "#B42318" },
      numberFormat: "#,##0",
      horizontalAlignment: "right",
    };
  } else if (kind === "production" && Number(value) > 0) {
    cell.format = {
      fill: "#DDEBF7",
      font: { name: fontFamily, size: 10, bold: true, color: "#1F4E78" },
      numberFormat: "#,##0",
      horizontalAlignment: "right",
    };
  } else if (kind === "inventory" && Number(value) < 0) {
    cell.format = {
      fill: "#FDE9E7",
      font: { name: fontFamily, size: 10, bold: true, color: "#B42318" },
      numberFormat: "#,##0;[Red]-#,##0",
      horizontalAlignment: "right",
    };
  } else if (kind === "shortage" && Number(value) > 0) {
    cell.format = {
      fill: "#FDE9E7",
      font: { name: fontFamily, size: 10, bold: true, color: "#B42318" },
      numberFormat: "#,##0",
      horizontalAlignment: "right",
    };
  } else if (kind === "status") {
    if (value === "PAST_DUE_RELEASE") {
      cell.format = {
        fill: "#FDE9E7",
        font: { name: fontFamily, size: 10, bold: true, color: "#B42318" },
        horizontalAlignment: "center",
        wrapText: true,
      };
    } else if (value === "SHORTAGE" || value === "PRODUCTION REQUIRED") {
      cell.format = {
        fill: "#FFF2CC",
        font: { name: fontFamily, size: 10, bold: true, color: "#7F6000" },
        horizontalAlignment: "center",
        wrapText: true,
      };
    }
  } else if (kind === "timing" || kind === "releaseTiming") {
    cell.format = {
      fill: "#EAF2F8",
      font: { name: fontFamily, size: 10, bold: true, color: "#1F4E78" },
      horizontalAlignment: "center",
    };
  }
}

function writeWidePlanSheet({
  sheet,
  title,
  subtitle,
  identityHeaders,
  periods,
  lookbackPeriods,
  blocks,
  periodColumnWidth,
}) {
  const headers = [...identityHeaders, "Metric", ...periods];
  const values = [headers];
  const blockLayouts = [];

  blocks.forEach((block, blockIndex) => {
    const startRow = 5 + values.length;
    block.rows.forEach((metricRow, metricIndex) => {
      values.push([
        metricIndex === 0 ? block.firstIdentity : null,
        metricIndex === 0 ? block.secondIdentity : null,
        metricRow.label,
        ...metricRow.values,
      ]);
    });
    blockLayouts.push({
      startRow,
      endRow: startRow + block.rows.length - 1,
      rows: block.rows,
    });
    if (blockIndex < blocks.length - 1) {
      values.push(headers.map(() => null));
    }
  });

  const lastColumn = columnLetter(headers.length - 1);
  const lastRow = 4 + values.length;
  sheet.showGridLines = false;
  sheet.tabColor = "#1F4E78";
  sheet.getRange("A2").values = [[title]];
  sheet.getRange("A3").values = [[subtitle]];
  sheet.getRange(`A5:${lastColumn}${lastRow}`).values = values;

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
    borders: {
      insideVertical: { style: "thin", color: "#FFFFFF" },
      bottom: { style: "medium", color: "#17365D" },
    },
  };

  const lookbackSet = new Set(lookbackPeriods);
  periods.forEach((period, periodIndex) => {
    const columnIndex = periodIndex + 3;
    const letter = columnLetter(columnIndex);
    sheet.getRange(`${letter}:${letter}`).format.columnWidth = periodColumnWidth;
    if (lookbackSet.has(period)) {
      sheet.getRange(`${letter}5`).format = {
        fill: "#5B6F82",
        font: { name: fontFamily, size: 10, bold: true, color: "#FFFFFF" },
        horizontalAlignment: "center",
        borders: {
          left: { style: "thin", color: "#FFFFFF" },
          right: { style: "thin", color: "#FFFFFF" },
          bottom: { style: "medium", color: "#3E4C59" },
        },
      };
      sheet.getRange(`${letter}6:${letter}${lastRow}`).format.fill = "#F5F7F9";
    }
  });

  sheet.getRange("A:A").format.columnWidth = 18;
  sheet.getRange("B:B").format.columnWidth = 24;
  sheet.getRange("C:C").format.columnWidth = 38;
  sheet.getRange(`A5:${lastColumn}5`).format.rowHeight = 28;
  sheet.freezePanes.freezeRows(5);
  sheet.freezePanes.freezeColumns(3);

  blockLayouts.forEach((layout) => {
    sheet.getRange(`A${layout.startRow}:B${layout.endRow}`).format.fill = "#F3F6F9";
    sheet.getRange(`C${layout.startRow}:C${layout.endRow}`).format = {
      fill: "#EAF2F8",
      font: { name: fontFamily, size: 10, bold: true, color: "#1F2937" },
    };
    sheet.getRange(`A${layout.startRow}:${lastColumn}${layout.endRow}`).format.borders = {
      top: { style: "medium", color: "#9FBAD0" },
      bottom: { style: "medium", color: "#9FBAD0" },
      insideHorizontal: { style: "thin", color: "#D9E2F3" },
    };
    sheet.getRange(`A${layout.startRow}:B${layout.startRow}`).format.font = {
      name: fontFamily,
      size: 10,
      bold: true,
      color: "#1F2937",
    };

    layout.rows.forEach((metricRow, rowIndex) => {
      const excelRow = layout.startRow + rowIndex;
      const periodRange = sheet.getRange(`D${excelRow}:${lastColumn}${excelRow}`);
      if (
        ["number", "inventory", "production", "shortage"].includes(
          metricRow.kind,
        )
      ) {
        periodRange.format.numberFormat = "#,##0";
        periodRange.format.horizontalAlignment = "right";
      } else {
        periodRange.format.horizontalAlignment = "center";
      }
      if (metricRow.kind === "status") {
        periodRange.format.wrapText = true;
        sheet.getRange(`A${excelRow}:${lastColumn}${excelRow}`).format.rowHeight = 32;
      }
      metricRow.values.forEach((value, periodIndex) => {
        const cell = sheet.getRange(
          `${columnLetter(periodIndex + 3)}${excelRow}`,
        );
        applyResultCellStyle(
          cell,
          metricRow.kind,
          value,
          metricRow.changedFrozenPeriods?.[periodIndex] ?? false,
        );
      });
    });
  });

  return { lastColumn, lastRow };
}

const fgLayout = writeWidePlanSheet({
  sheet: fgSheet,
  title: "Finished-goods time-phased plan",
  subtitle:
    "Projected inventory, demand, inbound supply and production by month.",
  identityHeaders: ["SKU", "SKU Description"],
  periods: fgPeriods,
  lookbackPeriods: [],
  blocks: fgBlocks,
  periodColumnWidth: 18,
});

const componentLayout = writeWidePlanSheet({
  sheet: componentSheet,
  title: "Component time-phased plan",
  subtitle:
    "Lookback periods show required release timing from deterministic Python results. Values only; no Excel formulas.",
  identityHeaders: ["Component", "Parent FG"],
  periods: componentPeriods,
  lookbackPeriods: componentLookbackPeriods,
  blocks: componentBlocks,
  periodColumnWidth: 14,
});

workbook.recalculate();

const fgInspect = await workbook.inspect({
  kind: "table",
  range: `FG Plan!A2:${fgLayout.lastColumn}${fgLayout.lastRow}`,
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 12,
  maxChars: 4000,
});
console.log(fgInspect.ndjson);
const componentInspect = await workbook.inspect({
  kind: "table",
  range: `Component Plan!A2:${componentLayout.lastColumn}${componentLayout.lastRow}`,
  include: "values,formulas",
  tableMaxRows: 25,
  tableMaxCols: 12,
  maxChars: 5000,
});
console.log(componentInspect.ndjson);
const plannerErrorInspect = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
  maxChars: 2000,
});
console.log(plannerErrorInspect.ndjson);

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

async function createCmWorkbook(cmPlan) {
  const cmWorkbook = Workbook.create();
  const sheet = cmWorkbook.worksheets.add("Production Plan");
  const headers = cmPlan.columns;
  const rows = cmPlan.rows.map((row) =>
    headers.map((header) => row.values[header] ?? null),
  );
  const lastColumn = columnLetter(headers.length - 1);
  const lastRow = 5 + rows.length;

  sheet.showGridLines = false;
  sheet.tabColor = "#1F4E78";
  sheet.getRange("A2").values = [[`${cmPlan.cm} production plan`]];
  sheet.getRange("A3").values = [[
    cmPlan.ready_for_communication
      ? "Ready for communication"
      : "Not ready for communication: planner comment required",
  ]];
  sheet.getRange(`A5:${lastColumn}${lastRow}`).values = [headers, ...rows];

  const usedRange = sheet.getRange(`A2:${lastColumn}${lastRow}`);
  usedRange.format.font = { name: fontFamily, size: 10, color: "#1F2937" };
  usedRange.format.verticalAlignment = "center";
  sheet.getRange("A2").format.font = {
    name: fontFamily,
    size: 14,
    bold: true,
    color: "#1F2937",
  };
  sheet.getRange(`A3:${lastColumn}3`).format = cmPlan.ready_for_communication
    ? {
        font: { name: fontFamily, size: 10, color: "#5B6573" },
        borders: { bottom: { style: "thin", color: "#A7B0BC" } },
      }
    : {
        fill: "#FDE9E7",
        font: { name: fontFamily, size: 10, bold: true, color: "#B42318" },
        borders: { bottom: { style: "thin", color: "#B42318" } },
      };
  sheet.getRange(`A5:${lastColumn}5`).format = {
    fill: "#1F4E78",
    font: { name: fontFamily, size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    borders: {
      insideVertical: { style: "thin", color: "#FFFFFF" },
      bottom: { style: "medium", color: "#17365D" },
    },
  };
  sheet.getRange(`A6:${lastColumn}${lastRow}`).format.borders = {
    insideHorizontal: { style: "thin", color: "#D9E2F3" },
    bottom: { style: "thin", color: "#D9E2F3" },
  };
  sheet.getRange(`B6:${columnLetter(headers.length - 2)}${lastRow}`).format = {
    numberFormat: "#,##0;[Red]-#,##0",
    horizontalAlignment: "right",
  };
  sheet.getRange("A:A").format.columnWidth = 18;
  headers.forEach((header, index) => {
    const letter = columnLetter(index);
    if (header === "Comment") {
      sheet.getRange(`${letter}:${letter}`).format.columnWidth = 52;
      sheet.getRange(`${letter}6:${letter}${lastRow}`).format.wrapText = true;
    } else if (header !== "SKU") {
      sheet.getRange(`${letter}:${letter}`).format.columnWidth = 14;
    }
  });
  sheet.getRange(`A5:${lastColumn}5`).format.rowHeight = 28;
  sheet.freezePanes.freezeRows(5);
  sheet.freezePanes.freezeColumns(1);

  cmPlan.rows.forEach((row, rowIndex) => {
    const excelRow = rowIndex + 6;
    row.changed_frozen_periods.forEach((period) => {
      const periodLabel = cmPlan.period_display_labels[period];
      const quantityColumn = headers.indexOf(periodLabel);
      const deltaColumn = headers.indexOf(`${periodLabel} Delta`);
      for (const columnIndex of [quantityColumn, deltaColumn]) {
        const cell = sheet.getRange(`${columnLetter(columnIndex)}${excelRow}`);
        cell.format = {
          fill: "#FDE9E7",
          font: { name: fontFamily, size: 10, bold: true, color: "#B42318" },
          numberFormat: "#,##0;[Red]-#,##0",
          horizontalAlignment: "right",
        };
      }
    });

    const commentColumn = headers.indexOf("Comment");
    const commentCell = sheet.getRange(
      `${columnLetter(commentColumn)}${excelRow}`,
    );
    if (row.changed_frozen_periods.length > 0) {
      const hasComment = Boolean(row.values.Comment);
      commentCell.format = {
        fill: hasComment ? "#FFF2CC" : "#FDE9E7",
        font: {
          name: fontFamily,
          size: 10,
          bold: !hasComment,
          color: hasComment ? "#7F6000" : "#B42318",
        },
        wrapText: true,
        horizontalAlignment: "left",
      };
      sheet.getRange(`A${excelRow}:${lastColumn}${excelRow}`).format.rowHeight = 38;
    }
  });

  cmWorkbook.recalculate();
  const cmInspect = await cmWorkbook.inspect({
    kind: "table",
    range: `Production Plan!A2:${lastColumn}${lastRow}`,
    include: "values,formulas",
    tableMaxRows: 10,
    tableMaxCols: 15,
    maxChars: 4000,
  });
  console.log(cmInspect.ndjson);
  const cmErrorInspect = await cmWorkbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
    options: { useRegex: true, maxResults: 100 },
    summary: `${cmPlan.cm} formula error scan`,
    maxChars: 2000,
  });
  console.log(cmErrorInspect.ndjson);

  if (previewDirectory) {
    const preview = await cmWorkbook.render({
      sheetName: "Production Plan",
      autoCrop: "all",
      scale: 1,
      format: "png",
    });
    await fs.writeFile(
      path.join(
        previewDirectory,
        `${cmPlan.filename.replace(/\.xlsx$/i, "")}.png`,
      ),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }

  const cmOutputPath = path.join(projectDirectory, "outputs", cmPlan.filename);
  const cmOutput = await SpreadsheetFile.exportXlsx(cmWorkbook);
  await cmOutput.save(cmOutputPath);
  return cmOutputPath;
}

const cmOutputPaths = [];
for (const cmPlan of payload.cm_plans) {
  cmOutputPaths.push(await createCmWorkbook(cmPlan));
}

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
for (const cmOutputPath of cmOutputPaths) {
  console.log(`CM production plan path: ${cmOutputPath}`);
}
