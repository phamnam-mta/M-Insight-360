"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, ShieldCheck } from "lucide-react";
import { AssessmentResult } from "@/lib/api";
import { SectionHeader } from "../shared/SectionHeader";
import { computeCoverage } from "@/lib/eb-red-flags";

type CheckRow = { label: string; pass: boolean; note: string };

// Real uploads can carry many sheets (a bundled workbook, or several PDF
// pages each treated as their own "sheet") with long Vietnamese reason
// text — inlining all of them as table rows let the "Ghi chú" column grow
// past the card's own width and overlap the sibling column entirely.
// Past this count, collapse the detail behind a toggle instead.
const SHEET_ROWS_INLINE_LIMIT = 4;

function Pill({ pass }: { pass: boolean }) {
  return (
    <span
      className={`text-[11px] font-bold px-2 py-0.5 rounded-xl whitespace-nowrap ${
        pass ? "bg-[#e4f6ef] text-[#17976b]" : "bg-[#fdeae9] text-[#e0362c]"
      }`}
    >
      {pass ? "PASS" : "FAIL"}
    </span>
  );
}

// S7.2(a) Bước 0 — same hard-block signals the backend's export gate uses
// (pre_check_blocked, sanity_check.balance_mismatch), surfaced here as a
// checklist so an RM sees why a hồ sơ was flagged before reaching S7.
export function PreCheckCard({ result }: { result: AssessmentResult }) {
  const [sheetDetailOpen, setSheetDetailOpen] = useState(false);
  const hasAnyExtractedData = Object.keys(result.financial_inputs ?? {}).length > 0;
  const unreadable = !hasAnyExtractedData && (result.extraction_warnings ?? []).length > 0;
  const coverage = computeCoverage(result.financial_inputs as Record<string, number> | undefined);
  const balanceMismatch = result.sanity_check?.balance_mismatch ?? false;

  const sheetScan = result.sheet_scan ?? [];
  const includedCount = sheetScan.filter((s) => s.included).length;
  const fileReadableNote = unreadable
    ? "Không đọc được nội dung từ file tải lên"
    : sheetScan.length > 0
      ? `Đã quét ${sheetScan.length} sheet, ${includedCount} sheet dùng làm BCTC`
      : "Đọc được nội dung BCTC";

  // A long sheet list is collapsed by default — inlined only past the
  // toggle, and always inside its own scroll-bounded block so the card's
  // height (and everything below it on the page) never balloons with a
  // large real upload.
  const showSheetRowsInline = sheetScan.length > 0 && sheetScan.length <= SHEET_ROWS_INLINE_LIMIT;
  const sheetScanRows: CheckRow[] = showSheetRowsInline
    ? sheetScan.map((s) => ({ label: `↳ Sheet "${s.sheet}"`, pass: s.included, note: s.reason }))
    : [];

  const namCanXacNhan = result.cot_nam?.nam_can_nguoi_dung_xac_nhan ?? false;

  // Sheet-scan rows are rendered separately below (inline when few, behind
  // a collapsible toggle when many) — never folded into this list, or
  // they'd end up rendered twice.
  const rows: CheckRow[] = [
    {
      label: "File đọc được",
      pass: !unreadable,
      note: fileReadableNote,
    },
    {
      label: "Kỳ báo cáo xác định được",
      pass: !!result.ho_so_period?.selected,
      note: result.ho_so_period?.selected ? `Kỳ: ${result.ho_so_period.selected}` : "Chưa xác định được kỳ báo cáo",
    },
    {
      label: "Kỳ báo cáo không cần xác nhận thủ công",
      pass: !namCanXacNhan,
      note: namCanXacNhan
        ? "Nhiều kỳ có trong hồ sơ và chưa được chọn tường minh — cần cán bộ xác nhận kỳ báo cáo"
        : "Kỳ báo cáo xác định rõ ràng",
    },
    {
      label: "Cân đối kế toán: Tổng TS = Tổng NV",
      pass: !balanceMismatch,
      note: balanceMismatch ? result.sanity_check?.balance_mismatch_detail ?? "Không cân đối" : "Cân đối khớp",
    },
    {
      label: "Độ phủ dữ liệu bắt buộc",
      pass: coverage >= 70,
      note: `${coverage}% trường bắt buộc đọc được`,
    },
  ];

  const collapsedSheetCount = sheetScan.length;
  const fileRow = rows[0];
  const restRows = rows.slice(1);

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-2 min-w-0">
      <SectionHeader icon={ShieldCheck} title="Tiền kiểm hồ sơ — Bước 0" />
      {/* table-layout: fixed + explicit column widths keep every cell's
          content confined to its own column no matter how long a real
          sheet name or reason string is — without this, the browser's
          default auto layout lets a long "Ghi chú" grow past the card's
          own width and overlap the sibling column next to it. */}
      <table className="w-full text-[13px] table-fixed">
        <colgroup>
          <col className="w-[34%]" />
          <col className="w-[54px]" />
          <col />
        </colgroup>
        <thead>
          <tr className="text-left border-b border-gray-100">
            <th className="py-1.5 pr-2 font-medium text-[11px] uppercase text-gray-400">Kiểm tra</th>
            <th className="py-1.5 pr-2 font-medium text-[11px] uppercase text-gray-400">KQ</th>
            <th className="py-1.5 font-medium text-[11px] uppercase text-gray-400">Ghi chú</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-b border-gray-50 align-top">
            <td className="py-2 pr-2 text-[#42506a] break-words">{fileRow.label}</td>
            <td className="py-2 pr-2">
              <Pill pass={fileRow.pass} />
            </td>
            <td className="py-2 text-gray-500 break-words">{fileRow.note}</td>
          </tr>
          {!showSheetRowsInline && collapsedSheetCount > 0 && (
            <tr className="border-b border-gray-50 align-top">
              <td colSpan={3} className="py-1.5">
                <button
                  type="button"
                  onClick={() => setSheetDetailOpen((v) => !v)}
                  className="flex items-center gap-1 text-[12px] font-semibold text-msb-navy"
                >
                  {sheetDetailOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                  Xem chi tiết {collapsedSheetCount} sheet
                </button>
                {sheetDetailOpen && (
                  <div className="mt-2 max-h-[240px] overflow-y-auto space-y-1.5 pr-1 border-l-2 border-gray-100 pl-3">
                    {sheetScan.map((s, i) => (
                      <div key={`${s.sheet}-${i}`} className="flex items-start gap-2 min-w-0">
                        <Pill pass={s.included} />
                        <div className="min-w-0">
                          <div className="text-[#42506a] break-words">Sheet &quot;{s.sheet}&quot;</div>
                          <div className="text-gray-500 break-words">{s.reason}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </td>
            </tr>
          )}
          {showSheetRowsInline &&
            sheetScanRows.map((r) => (
              <tr key={r.label} className="border-b border-gray-50 align-top">
                <td className="py-2 pr-2 text-[#42506a] break-words">{r.label}</td>
                <td className="py-2 pr-2">
                  <Pill pass={r.pass} />
                </td>
                <td className="py-2 text-gray-500 break-words">{r.note}</td>
              </tr>
            ))}
          {restRows.map((r) => (
            <tr key={r.label} className="border-b border-gray-50 last:border-0 align-top">
              <td className="py-2 pr-2 text-[#42506a] break-words">{r.label}</td>
              <td className="py-2 pr-2">
                <Pill pass={r.pass} />
              </td>
              <td className="py-2 text-gray-500 break-words">{r.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
