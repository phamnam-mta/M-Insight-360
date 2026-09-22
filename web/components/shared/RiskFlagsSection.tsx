"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { ACTIVATED_STATUS, INSUFFICIENT_DATA_STATUS, RiskFlag } from "@/lib/api";
import { SectionHeader } from "./SectionHeader";

export function RiskFlagsSection({ flags, title = "Cảnh báo rủi ro" }: { flags: RiskFlag[]; title?: string }) {
  const activated = flags.filter((f) => f.status === ACTIVATED_STATUS);
  const undetermined = flags.filter((f) => f.status === INSUFFICIENT_DATA_STATUS);
  const cleared = flags.filter((f) => f.status !== ACTIVATED_STATUS && f.status !== INSUFFICIENT_DATA_STATUS);
  const [showCleared, setShowCleared] = useState(false);

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-3">
      <SectionHeader icon={AlertTriangle} title={`${title} (${activated.length})`} />
      {activated.length > 0 ? (
        <ul className="text-sm space-y-2">
          {activated.map((f, i) => (
            <li key={i} className="border-l-4 border-red-400 pl-3">
              <span className="font-semibold">{f.rule_name ?? f.rule_id}</span>
              {f.severity && ` (${f.severity})`}
              {f.impact && `: ${f.impact}`}
              {f.evidence_refs && Object.keys(f.evidence_refs).length > 0 && (
                <ul className="text-xs text-gray-500 mt-1">
                  {Object.values(f.evidence_refs).flat().map((ev, j) => (
                    <li key={j}>
                      {ev.filename} — {ev.location}: &quot;{ev.original_text}&quot;
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <div>
          <p className="text-sm text-gray-500 mb-2">
            Không có cảnh báo được kích hoạt trong số các quy tắc đã kiểm tra.
          </p>
          <div className="flex items-center gap-2 border border-gray-100 rounded-lg px-3 py-2.5 text-sm text-gray-500 bg-gray-50/60">
            <CheckCircle2 className="h-4 w-4 text-gray-400 shrink-0" />
            Chưa có cảnh báo
          </div>
        </div>
      )}
      {undetermined.length > 0 && (
        <div className="pt-2 border-t">
          <h3 className="text-sm font-medium text-gray-500 mb-1">Chưa thể đánh giá</h3>
          <ul className="text-sm text-gray-500 space-y-1">
            {undetermined.map((f, i) => (
              <li key={i}>
                {f.rule_name ?? f.rule_id}
                {f.impact && `: ${f.impact}`}
              </li>
            ))}
          </ul>
        </div>
      )}
      {cleared.length > 0 && (
        <div className="pt-2 border-t">
          <button className="text-xs text-msb-navy underline" onClick={() => setShowCleared((v) => !v)}>
            {showCleared ? "Ẩn" : "Xem"} {cleared.length} quy tắc không kích hoạt
          </button>
          {showCleared && (
            <ul className="text-xs text-gray-400 mt-1 space-y-1">
              {cleared.map((f, i) => (
                <li key={i}>{f.rule_name ?? f.rule_id}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
