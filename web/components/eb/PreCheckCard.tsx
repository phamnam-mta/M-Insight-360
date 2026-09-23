"use client";

import { ShieldCheck } from "lucide-react";
import { AssessmentResult } from "@/lib/api";
import { SectionHeader } from "../shared/SectionHeader";
import { computeCoverage } from "@/lib/eb-red-flags";

type CheckRow = { label: string; pass: boolean; note: string };

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
  const hasAnyExtractedData = Object.keys(result.financial_inputs ?? {}).length > 0;
  const unreadable = !hasAnyExtractedData && (result.extraction_warnings ?? []).length > 0;
  const coverage = computeCoverage(result.financial_inputs as Record<string, number> | undefined);
  const balanceMismatch = result.sanity_check?.balance_mismatch ?? false;

  const sheetScan = result.sheet_scan ?? [];
  const fileReadableNote = unreadable
    ? "Không đọc được nội dung từ file tải lên"
    : sheetScan.length > 0
      ? `Đã quét ${sheetScan.length} sheet, ${sheetScan.filter((s) => s.included).length} sheet dùng làm BCTC`
      : "Đọc được nội dung BCTC";

  const sheetScanRows: CheckRow[] = sheetScan.map((s) => ({
    label: `↳ Sheet "${s.sheet}"`,
    pass: s.included,
    note: s.reason,
  }));

  const namCanXacNhan = result.cot_nam?.nam_can_nguoi_dung_xac_nhan ?? false;

  const rows: CheckRow[] = [
    {
      label: "File đọc được",
      pass: !unreadable,
      note: fileReadableNote,
    },
    ...sheetScanRows,
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

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-2">
      <SectionHeader icon={ShieldCheck} title="Tiền kiểm hồ sơ — Bước 0" />
      <table className="w-full text-[13px]">
        <thead>
          <tr className="text-left border-b border-gray-100">
            <th className="py-1.5 pr-2 font-medium text-[11px] uppercase text-gray-400">Kiểm tra</th>
            <th className="py-1.5 pr-2 font-medium text-[11px] uppercase text-gray-400">KQ</th>
            <th className="py-1.5 font-medium text-[11px] uppercase text-gray-400">Ghi chú</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label} className="border-b border-gray-50 last:border-0 align-top">
              <td className="py-2 pr-2 text-[#42506a]">{r.label}</td>
              <td className="py-2 pr-2">
                <Pill pass={r.pass} />
              </td>
              <td className="py-2 text-gray-500">{r.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
