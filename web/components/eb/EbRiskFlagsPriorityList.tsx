"use client";

import { AlertTriangle, FileWarning } from "lucide-react";
import { RiskFlag } from "@/lib/api";
import { SectionHeader } from "../shared/SectionHeader";

const SEVERITY_STYLE: Record<string, string> = {
  CRITICAL: "border-red-400 bg-red-50/40",
  HIGH: "border-red-300 bg-red-50/30",
  MEDIUM: "border-amber-300 bg-amber-50/30",
  LOW: "border-gray-300 bg-gray-50/30",
};

const VARIANT_META = {
  nhom_a: {
    title: "Tín hiệu tín dụng cần thẩm định thêm",
    icon: AlertTriangle,
    emptyText: "Chưa phát hiện tín hiệu cần thẩm định thêm từ các chỉ tiêu đã trích xuất được.",
    rowClass: (f: RiskFlag) => SEVERITY_STYLE[f.severity ?? "LOW"],
  },
  nhom_b: {
    title: "Cảnh báo dữ liệu",
    icon: FileWarning,
    emptyText: "Không có cảnh báo dữ liệu.",
    rowClass: () => "border-gray-300 bg-gray-50/40",
  },
};

export function EbRiskFlagsPriorityList({ flags, variant }: { flags: RiskFlag[]; variant: "nhom_a" | "nhom_b" }) {
  const meta = VARIANT_META[variant];
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
      <SectionHeader icon={meta.icon} title={meta.title} />
      {flags.length === 0 ? (
        <p className="text-sm text-gray-500">{meta.emptyText}</p>
      ) : (
        <ul className="space-y-2.5">
          {flags.map((f, i) => (
            <li key={i} className={`border-l-4 rounded-r-lg px-3 py-2.5 text-sm ${meta.rowClass(f)}`}>
              <div className="flex items-center gap-2 font-semibold text-msb-navy">
                {f.rule_name ?? f.rule_id}
                {f.severity && variant === "nhom_a" && (
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-white/70">{f.severity}</span>
                )}
              </div>
              {f.impact && <p className="text-gray-600 mt-0.5">{f.impact}</p>}
              {f.recommended_action && (
                <p className="text-xs text-gray-500 mt-1">
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
