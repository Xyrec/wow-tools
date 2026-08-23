import type { Chain } from "@/lib/prio";
import { CLASS_COLORS, SPEC_SHORT, specClass } from "@/lib/wow";
import type { ItemFacts } from "@/types";

/** Styled .xlsx export matching the officers' "Fel Good Inc. Loot Prio"
 *  workbook: one sheet per raid, merged gray boss headers, Item Name/Bias
 *  header rows, zebra-striped item rows, class-color fills on spec cells,
 *  dark-gray separator and tail cells with white text, Arial throughout. */

const HEADER_FILL = "FF999999";
const COLHEAD_FILL = "FFBDBDBD";
const DARK_FILL = "FF666666";
const STRIPES = ["FFD9D9D9", "FFF3F3F3"];
const FULL_WIDTH = 22; // stripes and merged headers span A:V like the original

const RAID_ABBR: Record<string, string> = {
  Karazhan: "Kara",
  "Gruul's Lair": "Gruul",
  "Magtheridon's Lair": "Mag",
  "Serpentshrine Cavern": "SSC",
  "Tempest Keep": "TK",
  "Hyjal Summit": "MH",
  "Black Temple": "BT",
  "Zul'Aman": "ZA",
  "Sunwell Plateau": "Sunwell",
};

export interface XlsxRaid {
  raid: string;
  /** [encounterId, encounterName] in display order. */
  encounters: [string, string][];
  rows: Map<string, { item: ItemFacts; chain: Chain }[]>;
}

function argbClass(spec: string): string {
  const hex = CLASS_COLORS[specClass(spec)] ?? "#FFFFFF";
  return `FF${hex.slice(1).toUpperCase()}`;
}

export async function exportPhaseXlsx(phase: number, raids: XlsxRaid[]) {
  const ExcelJS = (await import("exceljs")).default;
  const wb = new ExcelJS.Workbook();
  for (const { raid, encounters, rows } of raids) {
    const ws = wb.addWorksheet(`Phase ${phase} ${RAID_ABBR[raid] ?? raid}`);
    ws.getColumn(1).width = 50.5;
    for (let c = 2; c < FULL_WIDTH; c++)
      ws.getColumn(c).width = c % 2 === 0 ? 14.5 : 4.6;
    ws.getColumn(FULL_WIDTH).width = 32.5;

    let r = 1;
    for (const [eid, encName] of encounters) {
      const encRows = rows.get(eid) ?? [];
      if (encRows.length === 0) continue;
      if (r > 1) r++; // blank row between boss sections

      ws.mergeCells(r, 1, r, FULL_WIDTH);
      const header = ws.getCell(r, 1);
      header.value = encName;
      header.font = { name: "Arial", bold: true };
      header.fill = {
        type: "pattern",
        pattern: "solid",
        fgColor: { argb: HEADER_FILL },
      };
      r++;

      for (const [col, label] of [
        [1, "Item Name"],
        [2, "Bias"],
      ] as const) {
        const cell = ws.getCell(r, col);
        cell.value = label;
        cell.font = { name: "Arial", bold: true };
        cell.fill = {
          type: "pattern",
          pattern: "solid",
          fgColor: { argb: COLHEAD_FILL },
        };
      }
      r++;

      encRows.forEach(({ item, chain }, idx) => {
        const stripe = STRIPES[idx % 2];
        for (let c = 1; c <= FULL_WIDTH; c++)
          ws.getCell(r, c).fill = {
            type: "pattern",
            pattern: "solid",
            fgColor: { argb: stripe },
          };
        const name = ws.getCell(r, 1);
        name.value = item.name;
        name.font = { name: "Arial", bold: true };

        let col = 2;
        const dark = (cell: import("exceljs").Cell, value: string) => {
          cell.value = value;
          cell.font = { name: "Arial", bold: true, color: { argb: "FFFFFFFF" } };
          cell.fill = {
            type: "pattern",
            pattern: "solid",
            fgColor: { argb: DARK_FILL },
          };
        };
        chain.named.forEach((s, i) => {
          if (i > 0) {
            dark(ws.getCell(r, col), chain.seps[i - 1]);
            col++;
          }
          const cell = ws.getCell(r, col);
          cell.value = SPEC_SHORT[s.spec] ?? s.spec;
          cell.font = { name: "Arial", bold: true };
          cell.fill = {
            type: "pattern",
            pattern: "solid",
            fgColor: { argb: argbClass(s.spec) },
          };
          col++;
        });
        if (chain.named.length > 0) {
          dark(ws.getCell(r, col), ">");
          col++;
        }
        dark(ws.getCell(r, col), chain.tail);
        r++;
      });
    }
  }

  const buffer = await wb.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `Fel Good Inc. Loot Prio - Phase ${phase}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}
