"use client";

import {
  Badge as BadgeIcon,
  Building2,
  Clock,
  ClipboardList,
  File,
  FileDown,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  TrendingUp,
} from "lucide-react";
import {
  AssessmentResult,
  ConditionRow,
  DocumentStatus,
  evidenceFileUrl,
  exportMb02,
} from "@/lib/api";
import { AiInsightSection } from "./shared/AiInsightSection";
import { CrossSellOpportunities } from "./shared/CrossSellOpportunities";
import { InfoBar, InfoBarItem } from "./shared/InfoBar";
import { MetricCard, MetricValue } from "./shared/MetricCard";
import { SectionHeader } from "./shared/SectionHeader";
import { useState } from "react";
import { CompanyInfoBlock } from "./eb/CompanyInfoBlock";
import { FinancialDataTable } from "./eb/FinancialDataTable";
import { CapitalBalanceDiagram } from "./eb/CapitalBalanceDiagram";
import { Qd039Card } from "./eb/Qd039Card";
import { EbRiskFlagsPriorityList } from "./eb/EbRiskFlagsPriorityList";
import { StressTestDrawer } from "./eb/StressTestDrawer";

function fileIconFor(filename: string) {
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "csv" || ext === "xlsx") return FileSpreadsheet;
  if (ext === "pdf" || ext === "docx") return FileText;
  return File;
}

const RESULT_LABEL: Record<string, string> = {
  PASS: "Đạt",
  FAIL: "Không đạt",
  INSUFFICIENT_DATA: "Chưa đủ dữ liệu",
  PENDING_INTERNAL_CHECK: "Chờ kiểm tra trên hệ thống nội bộ",
  NOT_APPLICABLE: "Không áp dụng",
};

const RESULT_STYLE: Record<string, string> = {
  PASS: "bg-green-100 text-green-800",
  FAIL: "bg-red-100 text-red-800",
  INSUFFICIENT_DATA: "bg-gray-100 text-gray-600",
  PENDING_INTERNAL_CHECK: "bg-amber-100 text-amber-800",
  NOT_APPLICABLE: "bg-gray-100 text-gray-500",
};

function ResultBadge({ result }: { result: string }) {
  return (
    <span
      className={`inline-block text-xs font-semibold px-2.5 py-1 rounded-full whitespace-nowrap ${
        RESULT_STYLE[result] ?? "bg-gray-100 text-gray-600"
      }`}
    >
      {RESULT_LABEL[result] ?? result}
    </span>
  );
}

function formatObservedValue(row: ConditionRow): string {
  const v = row.observed.value;
  if (v === null || v === undefined) return "Chưa có dữ liệu";
  if (typeof v === "number") {
    return row.observed.unit === "VND" ? `${v.toLocaleString("vi-VN")} VND` : v.toLocaleString("vi-VN");
  }
  return String(v);
}

function EvidenceCell({ row, caseId }: { row: ConditionRow; caseId?: string }) {
  if (row.observed.evidence.length === 0) {
    return <span className="text-xs text-gray-400">—</span>;
  }
  return (
    <ul className="text-xs space-y-1">
      {row.observed.evidence.map((ev, i) => (
        <li key={i}>
          {caseId ? (
            <a
              href={evidenceFileUrl(caseId, ev.file_id)}
              target="_blank"
              rel="noopener noreferrer"
              className="text-msb-navy underline"
            >
              {ev.filename} — {ev.location}
            </a>
          ) : (
            <span>{ev.filename} — {ev.location}</span>
          )}
          <div className="text-gray-500 italic">&quot;{ev.original_text}&quot;</div>
        </li>
      ))}
    </ul>
  );
}

function OverviewTable({ rows, caseId }: { rows: ConditionRow[]; caseId?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-left border-b border-gray-200 text-gray-500">
            <th className="py-2 px-2 font-semibold">Tên điều kiện</th>
            <th className="py-2 px-2 font-semibold">Giá trị/hiện trạng thực tế</th>
            <th className="py-2 px-2 font-semibold">Điều kiện đối chiếu</th>
            <th className="py-2 px-2 font-semibold">Kết quả</th>
            <th className="py-2 px-2 font-semibold">Nguồn chứng cứ và ngày dữ liệu</th>
            <th className="py-2 px-2 font-semibold">Lý do/chứng từ còn thiếu</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.condition_id} className="border-b border-gray-100 align-top hover:bg-gray-50/60">
              <td className="py-2.5 px-2 font-medium text-msb-navy">{row.condition_name}</td>
              <td className="py-2.5 px-2">{formatObservedValue(row)}</td>
              <td className="py-2.5 px-2 text-gray-600">{row.compare_rule}</td>
              <td className="py-2.5 px-2"><ResultBadge result={row.result} /></td>
              <td className="py-2.5 px-2"><EvidenceCell row={row} caseId={caseId} /></td>
              <td className="py-2.5 px-2 text-gray-600">{row.reason_if_incomplete ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const METRIC_LABELS: Record<string, { label: string; unit: string; note?: string }> = {
  nwc: { label: "Vốn lưu động ròng (NWC)", unit: "VND" },
  dscr: { label: "Hệ số trả nợ (DSCR)", unit: "lần" },
  icr: { label: "Hệ số bù đắp lãi vay (ICR)", unit: "lần" },
  output_contract_financing_ratio: {
    label: "Tỷ lệ tài trợ hợp đồng đầu ra",
    unit: "%",
    note: "Tỷ lệ đề xuất, chưa phải mức đã phê duyệt.",
  },
};

const DOC_STATUS_LABEL: Record<string, string> = {
  "KHÔNG_ĐỌC_ĐƯỢC": "Không đọc được",
  "ĐÃ_TRÍCH_XUẤT": "Đã trích xuất",
  "CHỜ_XÁC_MINH": "Chờ xác minh",
  "ĐÃ_TẢI_LÊN": "Đã tải lên",
};

const DOC_STATUS_STYLE: Record<string, string> = {
  "KHÔNG_ĐỌC_ĐƯỢC": "bg-red-100 text-red-700",
  "ĐÃ_TRÍCH_XUẤT": "bg-green-100 text-green-800",
  "CHỜ_XÁC_MINH": "bg-amber-100 text-amber-800",
  "ĐÃ_TẢI_LÊN": "bg-gray-100 text-gray-600",
};

function DocumentPanel({ documents }: { documents: DocumentStatus[] }) {
  if (documents.length === 0) return null;
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-2">
      <SectionHeader icon={FolderOpen} title="D. Hồ sơ khách hàng" />
      <ul className="text-sm divide-y">
        {documents.map((d, i) => {
          const FileIcon = fileIconFor(d.filename);
          return (
            <li key={i} className="py-2.5 flex justify-between items-center gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <FileIcon className="h-4 w-4 text-gray-400 shrink-0" />
                <div className="min-w-0">
                  <p className="font-medium truncate">{d.filename}</p>
                  <p className="text-xs text-gray-500">{d.doc_type ?? "—"} · {d.cited_field_count} trường đã trích xuất</p>
                  {d.warnings.length > 0 && <p className="text-xs text-red-600">{d.warnings.join("; ")}</p>}
                </div>
              </div>
              <span
                className={`text-xs font-semibold px-2.5 py-1 rounded-full whitespace-nowrap shrink-0 ${
                  DOC_STATUS_STYLE[d.status] ?? "bg-gray-100 text-gray-600"
                }`}
              >
                {DOC_STATUS_LABEL[d.status] ?? d.status}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function EbResultPanel({
  result, onRerunWithPeriod,
}: {
  result: AssessmentResult;
  onRerunWithPeriod?: (period: string) => void;
}) {
  const overview = result.overview ?? [];
  const summary = result.overview_summary;
  const [stressOpen, setStressOpen] = useState(false);

  const EXTENDED_METRIC_LABELS: Record<string, { label: string; unit: string; note?: string }> = {
    ...METRIC_LABELS,
    ebitda: { label: "EBITDA", unit: "VND" },
    liquidity_balance: { label: "Cân đối thanh khoản", unit: "" },
  };

  return (
    <div className="mt-6">
      <InfoBar
        items={[
          { icon: BadgeIcon, label: "Mã hồ sơ", value: result.case_id ?? "—" },
          { icon: Clock, label: "Thời điểm chạy", value: result.assessed_at ?? "—" },
        ]}
        banner={result.overall_conclusion}
      />

      <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr_340px] gap-5 mt-5">
        {/* Cột trái — Hồ sơ & dữ liệu gốc */}
        <div className="space-y-5 order-4 lg:order-1">
          <CompanyInfoBlock result={result} onPeriodChange={(y) => onRerunWithPeriod?.(y)} />
          <FinancialDataTable creditEngine={result.credit_engine as Record<string, MetricValue> | undefined} />
        </div>

        {/* Cột giữa — Sức khỏe tài chính & quyết định tín dụng */}
        <div className="space-y-5 order-2">
          <div className="bg-white rounded-xl border border-gray-100 p-6 space-y-3">
            <SectionHeader
              icon={ClipboardList}
              title="Kết luận thẩm định"
              subtitle={
                summary
                  ? `${summary.checked}/${summary.total} điều kiện đã kiểm tra đủ dữ liệu; kỳ ${result.ho_so_period?.selected ?? "—"}.`
                  : undefined
              }
            />
            <p className="text-sm font-semibold text-msb-navy">{result.overall_conclusion ?? result.credit_readiness ?? "—"}</p>
            <p className="text-[11px] text-gray-400">
              Khuyến nghị sơ bộ từ dữ liệu BCTC — cần phê duyệt theo quy trình tín dụng MSB.
            </p>
          </div>

          {result.credit_engine && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {Object.entries(result.credit_engine)
                .filter(([key]) => key in EXTENDED_METRIC_LABELS)
                .map(([key, metric]) => {
                  const meta = EXTENDED_METRIC_LABELS[key];
                  return (
                    <MetricCard
                      key={key}
                      label={meta.label}
                      unit={meta.unit}
                      note={meta.note}
                      metric={metric as MetricValue}
                    />
                  );
                })}
            </div>
          )}

          <CapitalBalanceDiagram check={result.capital_balance_check} />
          <Qd039Card creditEngine={result.credit_engine as Record<string, MetricValue> | undefined} />
          <EbRiskFlagsPriorityList flags={result.risk_flags ?? []} />

          <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-3">
            <SectionHeader
              icon={ClipboardList}
              title="Thông tin tổng quan"
              subtitle={
                summary
                  ? `${summary.checked}/${summary.total} điều kiện đã kiểm tra đủ dữ liệu; ${summary.passed} đạt, ${summary.failed} không đạt, ${summary.pending} chờ xác minh.`
                  : undefined
              }
            />
            <OverviewTable rows={overview} caseId={result.case_id} />
          </div>
          <DocumentPanel documents={result.documents ?? []} />
        </div>

        {/* Cột phải — M-Insight AI & bán chéo */}
        <div className="space-y-5 order-3">
          <AiInsightSection why={result.why ?? []} creditMemo={result.credit_memo} title="M-Insight AI" />

          <div className="bg-white rounded-xl border border-gray-100 p-5 flex flex-wrap gap-2">
            <button
              onClick={() => setStressOpen(true)}
              className="text-xs font-semibold px-3 py-2 rounded-lg bg-msb-navy text-white"
            >
              Stress Test
            </button>
            {result.export_available && (
              <button
                onClick={async () => {
                  try {
                    const blob = await exportMb02(result);
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = "to-trinh-mb02-du-thao.docx";
                    a.click();
                    URL.revokeObjectURL(url);
                  } catch (err) {
                    alert(err instanceof Error ? err.message : "Xuất tờ trình thất bại.");
                  }
                }}
                className="text-xs font-semibold px-3 py-2 rounded-lg border border-msb-navy text-msb-navy"
              >
                <span className="inline-flex items-center gap-1.5">
                  <FileDown className="h-3.5 w-3.5" />
                  Soạn tờ trình MB02a
                </span>
              </button>
            )}
          </div>

          <CrossSellOpportunities
            opportunities={result.crosssell_opportunities ?? []}
            title="Cơ hội bán chéo"
          />
        </div>
      </div>

      <StressTestDrawer open={stressOpen} onClose={() => setStressOpen(false)} result={result} />
    </div>
  );
}
