"use client";

import { ShieldAlert } from "lucide-react";
import { ExportGateInfo } from "@/lib/api";
import { SectionHeader } from "../shared/SectionHeader";

const VERDICT_LABEL: Record<ExportGateInfo["verdict"], string> = {
  XUAT: "XUẤT TỰ ĐỘNG",
  XUAT_KEM_CANH_BAO: "XUẤT KÈM CẢNH BÁO",
  KHONG_XUAT_TU_DONG: "KHÔNG XUẤT TỰ ĐỘNG",
};

const VERDICT_PILL: Record<ExportGateInfo["verdict"], string> = {
  XUAT: "bg-[#e4f6ef] text-[#17976b]",
  XUAT_KEM_CANH_BAO: "bg-[#fdf1de] text-[#c8892a]",
  KHONG_XUAT_TU_DONG: "bg-[#fdeae9] text-[#e0362c]",
};

function formatVnd(v: number | string | null | undefined): string {
  if (typeof v !== "number") return "Chưa xác định từ hồ sơ tải lên";
  return Math.round(v).toLocaleString("vi-VN");
}

export function ExportGateSummaryCard({
  gate, equityVnd, exportFilename,
}: { gate: ExportGateInfo; equityVnd?: number | null; exportFilename?: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
      <SectionHeader icon={ShieldAlert} title="Cổng chặn xuất tờ trình — S7" />
      <div className="bg-[#fff8ec] border border-[#f0d9ae] rounded-lg px-3.5 py-3 text-[13.5px] space-y-1.5">
        <div>
          Verdict:{" "}
          <span className={`text-[11.5px] font-bold px-2.5 py-0.5 rounded-xl ${VERDICT_PILL[gate.verdict]}`}>
            {VERDICT_LABEL[gate.verdict]}
          </span>
        </div>
        <div>
          Tín hiệu tín dụng: <b>{gate.signal_count}</b> (ngưỡng chặn ≥ 3)
          {typeof equityVnd === "number" || equityVnd === null ? (
            <>
              {" "}
              · Vốn chủ sở hữu: <b>{formatVnd(equityVnd)}</b>
            </>
          ) : null}
        </div>
        <div>
          Cảnh báo dữ liệu: {gate.data_warnings.length} mục — <b>không tính vào verdict</b>.
        </div>
        {exportFilename && (
          <div>
            File xuất: <code className="bg-[#eef1f5] px-1.5 py-0.5 rounded text-[12px]">{exportFilename}</code> — đơn vị triệu đồng
          </div>
        )}
        {gate.reasons.length > 0 && <div>Lý do: {gate.reasons.join("; ")}</div>}
      </div>
      <p className="text-xs text-gray-500">
        Bản nháp. Cán bộ có quyền ghi đè quyết định của cổng chặn kèm lý do; mọi lần ghi đè đều lưu vết.
      </p>
    </div>
  );
}
