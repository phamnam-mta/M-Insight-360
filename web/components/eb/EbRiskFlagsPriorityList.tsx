"use client";

import { AlertTriangle, HelpCircle } from "lucide-react";
import { ACTIVATED_STATUS, INSUFFICIENT_DATA_STATUS, RiskFlag } from "@/lib/api";
import { SectionHeader } from "../shared/SectionHeader";

const SEVERITY_STYLE: Record<string, string> = {
  CRITICAL: "border-red-400 bg-red-50/40",
  HIGH: "border-red-300 bg-red-50/30",
  MEDIUM: "border-amber-300 bg-amber-50/30",
  LOW: "border-gray-300 bg-gray-50/30",
};

export function EbRiskFlagsPriorityList({ flags }: { flags: RiskFlag[] }) {
  const activated = flags.filter((f) => f.status === ACTIVATED_STATUS);
  const undetermined = flags.filter((f) => f.status === INSUFFICIENT_DATA_STATUS);
  const priorityRows = [...activated, ...undetermined];

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
      <SectionHeader icon={AlertTriangle} title="Tín hiệu cần thẩm định thêm từ dữ liệu BCTC" />
      {priorityRows.length === 0 ? (
        <p className="text-sm text-gray-500">Không có tín hiệu cần thẩm định thêm trong số các quy tắc đã kiểm tra.</p>
      ) : (
        <ul className="space-y-2.5">
          {priorityRows.map((f, i) => {
            const isUndetermined = f.status === INSUFFICIENT_DATA_STATUS;
            return (
              <li
                key={i}
                className={`border-l-4 rounded-r-lg px-3 py-2.5 text-sm ${
                  isUndetermined ? "border-gray-300 bg-gray-50/40" : SEVERITY_STYLE[f.severity ?? "LOW"]
                }`}
              >
                <div className="flex items-center gap-2 font-semibold text-msb-navy">
                  {isUndetermined && <HelpCircle className="h-3.5 w-3.5 text-gray-400 shrink-0" />}
                  {f.rule_name ?? f.rule_id}
                  {f.severity && !isUndetermined && (
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
            );
          })}
        </ul>
      )}
    </div>
  );
}
