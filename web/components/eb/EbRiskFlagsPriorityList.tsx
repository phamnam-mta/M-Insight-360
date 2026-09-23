"use client";

import { AlertTriangle, FileWarning } from "lucide-react";
import { RiskFlag } from "@/lib/api";
import { SectionHeader } from "../shared/SectionHeader";

const SEVERITY_PILL: Record<string, string> = {
  CRITICAL: "bg-[#fdeae9] text-[#e0362c]",
  HIGH: "bg-[#fdeae9] text-[#e0362c]",
  MEDIUM: "bg-[#fdf1de] text-[#c8892a]",
  LOW: "bg-[#eef1f5] text-[#8b97a8]",
};

const VARIANT_META = {
  nhom_a: {
    title: "Tín hiệu tín dụng cần thẩm định thêm",
    icon: AlertTriangle,
    emptyText: "Chưa phát hiện tín hiệu cần thẩm định thêm từ các chỉ tiêu đã trích xuất được.",
  },
  nhom_b: {
    title: "Cảnh báo dữ liệu",
    icon: FileWarning,
    emptyText: "Không có cảnh báo dữ liệu.",
  },
};

export function EbRiskFlagsPriorityList({ flags, variant }: { flags: RiskFlag[]; variant: "nhom_a" | "nhom_b" }) {
  const meta = VARIANT_META[variant];
  const isNhomA = variant === "nhom_a";
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
      <SectionHeader icon={meta.icon} title={meta.title} />
      {flags.length === 0 ? (
        <p className="text-sm text-gray-500">{meta.emptyText}</p>
      ) : (
        <ul className="space-y-2.5">
          {flags.map((f, i) => (
            <li
              key={i}
              className={
                isNhomA
                  ? "border-l-[3px] border-[#e0362c] pl-2.5 text-sm"
                  : "border-l-[3px] border-dashed border-[#8b97a8] pl-2.5 text-sm"
              }
            >
              <div className="flex items-center gap-2 font-semibold text-sm">
                <span>{isNhomA ? "⛔" : "◻︎"}</span>
                {f.rule_name ?? f.rule_id}
                {f.severity && isNhomA && (
                  <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded-xl ${SEVERITY_PILL[f.severity] ?? SEVERITY_PILL.LOW}`}>
                    {f.severity}
                  </span>
                )}
              </div>
              {f.impact && <p className="text-[#42506a] mt-0.5">{f.impact}</p>}
              {f.recommended_action && (
                <p className="text-[#6b7a90] mt-0.5">
                  <span className="font-medium">Hành động RM:</span> {f.recommended_action}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
