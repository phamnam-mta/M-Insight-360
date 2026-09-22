"use client";

import { Badge as BadgeIcon, BarChart3, Building2, Clock, FileText, Users } from "lucide-react";
import { AssessmentResult } from "@/lib/api";
import { AiInsightSection } from "./shared/AiInsightSection";
import { BannerTone, InfoBar, InfoBarItem } from "./shared/InfoBar";
import { RiskFlagsSection } from "./shared/RiskFlagsSection";
import { SectionHeader } from "./shared/SectionHeader";

const VERDICT_TONE: Record<string, BannerTone> = {
  OK: "green",
  WARN: "amber",
  BLOCK: "red",
};

function formatVnd(n: number | undefined): string {
  if (n === undefined || n === null) return "—";
  return n.toLocaleString("vi-VN") + " VND";
}

export default function CrossSellPanel({ result }: { result: AssessmentResult }) {
  const precheck = result.precheck;

  const infoItems: InfoBarItem[] = [
    { icon: BadgeIcon, label: "Mã hồ sơ", value: result.case_id ?? "—" },
    { icon: Building2, label: "Khách hàng", value: (result.customer_profile?.customer_name as string) ?? "—" },
    { icon: FileText, label: "MST", value: (result.customer_profile?.tax_id as string) ?? "—" },
    { icon: Clock, label: "Thời điểm chạy", value: result.assessed_at ?? "—" },
  ];

  const banner = precheck
    ? `Kiểm tra tính toàn vẹn sao kê: ${precheck.verdict}${precheck.reason ? ` — ${precheck.reason}` : ""}`
    : null;

  return (
    <div className="space-y-6 mt-6">
      <InfoBar
        items={infoItems}
        banner={banner}
        bannerTone={precheck ? VERDICT_TONE[precheck.verdict ?? ""] ?? "amber" : "amber"}
      />

      {result.extraction_warnings && result.extraction_warnings.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-2">
          <SectionHeader icon={FileText} title="Cảnh báo trích xuất dữ liệu" />
          <ul className="text-sm list-disc list-inside">
            {result.extraction_warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {result.dashboard && result.dashboard.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-3">
          <SectionHeader icon={BarChart3} title="Dòng tiền theo tháng" />
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left border-b border-gray-200 text-gray-500">
                  <th className="py-2 px-2 font-semibold">Tháng</th>
                  <th className="py-2 px-2 font-semibold">Số GD</th>
                  <th className="py-2 px-2 font-semibold">Tiền vào</th>
                  <th className="py-2 px-2 font-semibold">Tiền ra</th>
                  <th className="py-2 px-2 font-semibold">Ròng</th>
                </tr>
              </thead>
              <tbody>
                {result.dashboard.map((row) => (
                  <tr key={row.month} className="border-b border-gray-100 last:border-0">
                    <td className="py-2 px-2">{row.month}</td>
                    <td className="py-2 px-2">{row.transaction_count}</td>
                    <td className="py-2 px-2">{formatVnd(row.total_in)}</td>
                    <td className="py-2 px-2">{formatVnd(row.total_out)}</td>
                    <td className={`py-2 px-2 ${row.net < 0 ? "text-red-600" : ""}`}>{formatVnd(row.net)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {result.top_partners && result.top_partners.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-2">
          <SectionHeader icon={Users} title="Đối tác giao dịch nhiều nhất" />
          <ul className="text-sm divide-y">
            {result.top_partners.map((p, i) => (
              <li key={i} className="py-2 flex justify-between items-center gap-3">
                <span>
                  {p.partner} ({p.transaction_count} GD)
                  {p.qualifies && <span className="ml-2 text-msb-orange font-semibold">Đủ điều kiện SCF</span>}
                </span>
                <span className="shrink-0">{formatVnd(p.total_value)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <RiskFlagsSection
        flags={result.opportunities ?? []}
        title={`Cơ hội bán chéo${result.confidence_ceiling ? ` — độ tin cậy ${result.confidence_ceiling}` : ""}`}
      />

      <AiInsightSection why={result.why ?? []} creditMemo={result.credit_memo} />
    </div>
  );
}
