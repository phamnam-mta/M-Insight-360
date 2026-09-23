"use client";

import { Building2 } from "lucide-react";
import { AssessmentResult } from "@/lib/api";
import { SectionHeader } from "../shared/SectionHeader";
import { computeCoverage } from "@/lib/eb-red-flags";

function KvRow({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 text-[13.5px] py-1.5 border-b border-gray-50 last:border-0">
      <span className="text-gray-500 shrink-0">{k}</span>
      <span className="font-semibold text-right text-msb-navy break-words">{v}</span>
    </div>
  );
}

export function CompanyInfoBlock({
  result,
  onPeriodChange,
}: {
  result: AssessmentResult;
  onPeriodChange: (year: string) => void;
}) {
  const period = result.ho_so_period;
  const doc = (result.documents ?? [])[0];
  const coverage = computeCoverage(result.financial_inputs as Record<string, number> | undefined);
  const extractedOk = (result.documents ?? []).some((d) => d.status === "ĐÃ_TRÍCH_XUẤT");

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-1">
      <div className="pb-2">
        <SectionHeader icon={Building2} title="Hồ sơ" />
      </div>
      <KvRow k="Tên hồ sơ" v={(result.customer_profile?.customer_name as string) ?? "—"} />
      <KvRow k="Mã số thuế" v={(result.customer_profile?.tax_id as string) ?? "—"} />
      <KvRow
        k="Kỳ báo cáo"
        v={
          period && period.available.length > 1 ? (
            <select
              className="border border-gray-200 rounded-lg px-1.5 py-0.5 text-[13.5px] font-semibold text-msb-navy"
              value={period.selected ?? ""}
              onChange={(e) => onPeriodChange(e.target.value)}
            >
              {period.available.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          ) : (
            period?.selected ?? "—"
          )
        }
      />
      <KvRow k="Loại BCTC" v={doc?.doc_type ?? "Chưa xác định từ hồ sơ tải lên"} />
      <KvRow k="Tệp nguồn" v={doc?.filename ?? "Chưa có tệp"} />
      <KvRow k="Trạng thái" v={extractedOk ? "AI đã trích xuất" : "Chờ xác minh"} />
      <KvRow k="Độ phủ dữ liệu" v={`${coverage}%`} />
      {period?.fallback_notice && (
        <p className="text-xs text-amber-700 bg-amber-50 rounded-lg px-2.5 py-1.5 mt-2">{period.fallback_notice}</p>
      )}
      <p className="text-[11px] text-gray-400 mt-2 pt-2 border-t border-gray-100">
        Dữ liệu read-only sau khi AI trích xuất. Sửa có kiểm soát, lưu vết người sửa và thời gian.
      </p>
    </div>
  );
}
