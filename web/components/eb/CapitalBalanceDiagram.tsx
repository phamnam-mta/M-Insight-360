"use client";

import { Scale } from "lucide-react";
import { CapitalBalanceCheck } from "@/lib/api";
import { SectionHeader } from "../shared/SectionHeader";

function formatVnd(v: number | null): string {
  if (v === null) return "Chưa xác định từ hồ sơ tải lên";
  return Math.round(v).toLocaleString("vi-VN");
}

export function CapitalBalanceDiagram({ check }: { check?: CapitalBalanceCheck }) {
  if (!check) return null;
  const balanced = check.trang_thai === "Cân bằng";
  const diff = check.trai !== null && check.phai !== null ? Math.abs(check.trai - check.phai) : null;
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
      <SectionHeader icon={Scale} title="Cân bằng hai vế · kỳ hạn nguồn vốn" />
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex-1 min-w-[180px] bg-[#f6f8fb] rounded-lg px-3.5 py-2.5">
          <p className="text-[11.5px] uppercase text-gray-400 font-bold">Vế trái — Vốn lưu động ròng</p>
          <p className="text-[17px] font-extrabold text-msb-navy mt-0.5">{formatVnd(check.trai)}</p>
        </div>
        <span className="text-[22px] text-gray-400">=</span>
        <div className="flex-1 min-w-[180px] bg-[#f6f8fb] rounded-lg px-3.5 py-2.5">
          <p className="text-[11.5px] uppercase text-gray-400 font-bold">Vế phải — Nguồn vốn dài hạn ròng</p>
          <p className="text-[17px] font-extrabold text-msb-navy mt-0.5">{formatVnd(check.phai)}</p>
        </div>
      </div>
      <div className="text-sm">
        Chênh lệch: <b>{diff === null ? "—" : formatVnd(diff)}</b>{" "}
        <span
          className={`inline-block text-[11.5px] font-semibold px-2.5 py-1 rounded-full ml-1 ${
            balanced ? "bg-[#e4f6ef] text-[#17976b]" : "bg-[#fdf1de] text-[#c8892a]"
          }`}
        >
          {check.trang_thai}
        </span>
      </div>
      <p className="text-xs text-gray-500">{check.nhan_xet}</p>
    </div>
  );
}
