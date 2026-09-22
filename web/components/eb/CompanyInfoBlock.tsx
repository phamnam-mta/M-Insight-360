"use client";

import { Building2, Calendar, FileText, IdCard } from "lucide-react";
import { AssessmentResult } from "@/lib/api";
import { SectionHeader } from "../shared/SectionHeader";

export function CompanyInfoBlock({
  result,
  onPeriodChange,
}: {
  result: AssessmentResult;
  onPeriodChange: (year: string) => void;
}) {
  const period = result.ho_so_period;
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
      <SectionHeader icon={Building2} title="Thông tin doanh nghiệp" />
      <div className="text-sm space-y-2">
        <div className="flex items-center gap-2">
          <Building2 className="h-3.5 w-3.5 text-gray-400 shrink-0" />
          <span className="font-medium text-msb-navy">{(result.customer_profile?.customer_name as string) ?? "—"}</span>
        </div>
        <div className="flex items-center gap-2">
          <IdCard className="h-3.5 w-3.5 text-gray-400 shrink-0" />
          <span>MST {(result.customer_profile?.tax_id as string) ?? "—"}</span>
        </div>
        {period && period.available.length > 0 && (
          <div className="flex items-center gap-2">
            <Calendar className="h-3.5 w-3.5 text-gray-400 shrink-0" />
            <label className="text-xs text-gray-500">Kỳ báo cáo</label>
            <select
              className="border border-gray-200 rounded-lg px-2 py-1 text-sm"
              value={period.selected ?? ""}
              onChange={(e) => onPeriodChange(e.target.value)}
            >
              {period.available.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
        )}
        <div className="flex items-center gap-2 text-gray-500 text-xs">
          <FileText className="h-3.5 w-3.5 shrink-0" />
          {(result.documents ?? []).map((d) => d.filename).join(", ") || "Chưa có tệp"}
        </div>
      </div>
    </div>
  );
}
