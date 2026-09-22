"use client";

import { Scale } from "lucide-react";
import { CapitalBalanceCheck } from "@/lib/api";
import { SectionHeader } from "../shared/SectionHeader";

function formatVnd(v: number | null): string {
  if (v === null) return "Chưa xác định từ hồ sơ tải lên";
  return `${(v / 1_000_000_000).toFixed(2)} tỷ`;
}

export function CapitalBalanceDiagram({ check }: { check?: CapitalBalanceCheck }) {
  if (!check) return null;
  const balanced = check.trang_thai === "Can bang";
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
      <SectionHeader icon={Scale} title="Cân đối tài chính" />
      <div className="flex items-center justify-center gap-3 text-sm">
        <div className="text-center">
          <p className="text-xs text-gray-400">Vốn lưu động ròng</p>
          <p className="font-semibold text-msb-navy">{formatVnd(check.trai)}</p>
        </div>
        <span className="text-gray-300">=</span>
        <div className="text-center">
          <p className="text-xs text-gray-400">Nguồn vốn dài hạn ròng</p>
          <p className="font-semibold text-msb-navy">{formatVnd(check.phai)}</p>
        </div>
      </div>
      <span
        className={`inline-block text-xs font-semibold px-2.5 py-1 rounded-full ${
          balanced ? "bg-green-100 text-green-800" : "bg-amber-100 text-amber-800"
        }`}
      >
        {balanced ? "Cân bằng" : check.trang_thai}
      </span>
      <p className="text-xs text-gray-500">{check.nhan_xet}</p>
    </div>
  );
}
