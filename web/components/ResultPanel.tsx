"use client";

import { Badge as BadgeIcon, Building2, Clock, FileText, ListChecks } from "lucide-react";
import { AssessmentResult, exportMb02 } from "@/lib/api";
import { AiInsightSection } from "./shared/AiInsightSection";
import { CrossSellOpportunities } from "./shared/CrossSellOpportunities";
import { BannerTone, InfoBar, InfoBarItem } from "./shared/InfoBar";
import { MetricCard, MetricValue } from "./shared/MetricCard";
import { RiskFlagsSection } from "./shared/RiskFlagsSection";
import { SectionHeader } from "./shared/SectionHeader";

const READINESS_LABEL: Record<string, string> = {
  READY: "Sẵn sàng",
  READY_WITH_CONDITIONS: "Sẵn sàng có điều kiện",
  MANUAL_REVIEW_REQUIRED: "Cần thẩm định thủ công",
  NOT_READY: "Thiếu hồ sơ",
};

const READINESS_TONE: Record<string, BannerTone> = {
  READY: "green",
  READY_WITH_CONDITIONS: "amber",
  MANUAL_REVIEW_REQUIRED: "amber",
  NOT_READY: "red",
};

const METRIC_LABELS: Record<string, { label: string; unit: string }> = {
  eligible_monthly_income: { label: "Thu nhập đủ điều kiện", unit: "VND" },
  new_loan_first_month_payment: { label: "Trả nợ tháng đầu (khoản vay mới)", unit: "VND" },
  total_monthly_obligation: { label: "Tổng nghĩa vụ trả nợ hàng tháng", unit: "VND" },
  dti: { label: "Tỷ lệ nợ trên thu nhập (DTI)", unit: "" },
  dsr: { label: "Tỷ lệ trả nợ (DSR)", unit: "" },
  remaining_disposable_income: { label: "Thu nhập khả dụng còn lại", unit: "VND" },
};

export default function ResultPanel({ result }: { result: AssessmentResult }) {
  const infoItems: InfoBarItem[] = [
    { icon: BadgeIcon, label: "Mã hồ sơ", value: result.case_id ?? "—" },
    { icon: Building2, label: "Khách hàng", value: (result.customer_profile?.customer_name as string) ?? "—" },
    { icon: FileText, label: "MST", value: (result.customer_profile?.tax_id as string) ?? "—" },
    { icon: Clock, label: "Thời điểm chạy", value: result.assessed_at ?? "—" },
  ];

  const readiness = result.credit_readiness;
  const banner = readiness
    ? `${READINESS_LABEL[readiness] ?? readiness}${result.recommendation ? ` — ${result.recommendation}` : ""}`
    : null;

  return (
    <div className="space-y-6 mt-6">
      <InfoBar items={infoItems} banner={banner} bannerTone={readiness ? READINESS_TONE[readiness] ?? "amber" : "amber"} />

      {result.missing_data && result.missing_data.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-2">
          <SectionHeader icon={ListChecks} title="Hồ sơ còn thiếu" />
          <ul className="text-sm list-disc list-inside">
            {result.missing_data.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      {result.credit_engine && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-3">
          <SectionHeader icon={ListChecks} title="Chỉ tiêu thu nhập & khả năng trả nợ" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(result.credit_engine)
              .filter(([key]) => key in METRIC_LABELS)
              .map(([key, metric]) => {
                const meta = METRIC_LABELS[key];
                return (
                  <MetricCard key={key} label={meta.label} unit={meta.unit} metric={metric as MetricValue} />
                );
              })}
          </div>
        </div>
      )}

      <RiskFlagsSection flags={result.risk_flags ?? []} />
      <CrossSellOpportunities opportunities={result.crosssell_opportunities ?? []} />
      <AiInsightSection why={result.why ?? []} creditMemo={result.credit_memo} />

      {result.export_available && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6">
          <button
            onClick={async () => {
              try {
                const outcome = await exportMb02(result);
                if (outcome.blocked) {
                  alert("Xuất tờ trình thất bại: hồ sơ bị chặn xuất tự động.");
                  return;
                }
                const url = URL.createObjectURL(outcome.blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = outcome.filename;
                a.click();
                URL.revokeObjectURL(url);
              } catch (err) {
                alert(err instanceof Error ? err.message : "Xuất tờ trình thất bại.");
              }
            }}
            className="border border-msb-navy text-msb-navy font-semibold px-4 py-2 rounded-lg hover:bg-msb-bg transition"
          >
            Xuất tờ trình MB02
          </button>
        </div>
      )}
    </div>
  );
}
