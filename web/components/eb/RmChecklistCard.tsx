"use client";

import { ClipboardCheck } from "lucide-react";
import { SectionHeader } from "../shared/SectionHeader";
import { missingRequiredFieldLabels } from "@/lib/eb-red-flags";

// S8 (ngoài BCTC) and S1.3 (checkbox pháp lý) are instruction-fixed lists —
// this codebase has no extraction source for either (S8's own fields are
// entered by the RM directly; S1.3's checkboxes are a manual legal
// attestation), so they're rendered as a static reminder, same pattern as
// the R2 LockedPlaceholders panel already uses for not-yet-connected checks.
const S8_FIELDS = [
  "Nợ gốc đến hạn 12 tháng (lịch trả nợ chi tiết)",
  "Mục đích cấp tín dụng, phương án sử dụng vốn",
  "Tài sản bảo đảm",
  "Xếp hạng tín dụng, kết quả CIC",
];

const S1_3_CHECKS = [
  "Đối tượng không/hạn chế được cấp tín dụng theo pháp luật",
  "Đối tượng không/hạn chế theo quy định MSB",
  "Đánh giá rủi ro MTXH",
];

export function RmChecklistCard({ financialInputs }: { financialInputs?: Record<string, number> }) {
  const missingBctc = missingRequiredFieldLabels(financialInputs);

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
      <SectionHeader icon={ClipboardCheck} title="Việc RM cần xác nhận" />
      {missingBctc.length > 0 && (
        <div>
          <p className="text-[13px] font-bold text-msb-navy">Trường BCTC chưa đọc được</p>
          <ul className="text-[12.5px] text-gray-600 list-disc list-inside mt-1 space-y-0.5">
            {missingBctc.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </div>
      )}
      <div>
        <p className="text-[13px] font-bold text-msb-navy">Trường ngoài BCTC — RM tự điền (S8)</p>
        <ul className="text-[12.5px] text-gray-600 list-disc list-inside mt-1 space-y-0.5">
          {S8_FIELDS.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      </div>
      <div>
        <p className="text-[13px] font-bold text-msb-navy">Checkbox pháp lý chờ RM tích (S1.3)</p>
        <ul className="text-[12.5px] text-gray-600 list-disc list-inside mt-1 space-y-0.5">
          {S1_3_CHECKS.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
