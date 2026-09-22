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
  SlidersHorizontal,
  TrendingUp,
} from "lucide-react";
import {
  AssessmentResult,
  ConditionRow,
  DocumentStatus,
  evidenceFileUrl,
  exportMb02,
  runStressTest,
} from "@/lib/api";
import { AiInsightSection } from "./shared/AiInsightSection";
import { CrossSellOpportunities } from "./shared/CrossSellOpportunities";
import { InfoBar, InfoBarItem } from "./shared/InfoBar";
import { MetricCard, MetricValue } from "./shared/MetricCard";
import { RiskFlagsSection } from "./shared/RiskFlagsSection";
import { SectionHeader } from "./shared/SectionHeader";
import { useState } from "react";

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

type StressTestState = {
  revenue_pct: number; margin_pct: number; interest_rate_pct: number; collection_speed_pct: number;
};

function StressTestPanel({ creditEngine }: { creditEngine?: Record<string, MetricValue> }) {
  const [deltas, setDeltas] = useState<StressTestState>({
    revenue_pct: 0, margin_pct: 0, interest_rate_pct: 0, collection_speed_pct: 0,
  });
  const [result, setResult] = useState<Awaited<ReturnType<typeof runStressTest>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setError(null);
    try {
      const inputs: Record<string, number | null> = {};
      for (const key of ["nwc", "dscr", "icr"]) {
        const m = creditEngine?.[key];
        if (m?.input_values) {
          for (const [k, v] of Object.entries(m.input_values)) {
            if (typeof v === "number") inputs[k] = v;
          }
        }
      }
      const r = await runStressTest(inputs, deltas);
      setResult(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stress test thất bại");
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-3">
      <SectionHeader
        icon={SlidersHorizontal}
        title="Stress Test (kịch bản giả định)"
        subtitle="Đây là kịch bản giả định do cán bộ nhập, không phải dự báo tài chính chắc chắn."
      />
      <div className="flex flex-wrap items-end gap-3">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 flex-1">
          {(Object.keys(deltas) as Array<keyof StressTestState>).map((key) => (
            <div key={key}>
              <label className="block text-xs text-gray-500 mb-1">{key} (%)</label>
              <div className="relative">
                <input
                  type="number"
                  className="w-full border border-gray-200 rounded-lg px-2 py-1.5 pr-6 text-sm focus:outline-none focus:ring-2 focus:ring-msb-orange/40 focus:border-msb-orange"
                  value={deltas[key]}
                  onChange={(e) => setDeltas((prev) => ({ ...prev, [key]: Number(e.target.value) }))}
                />
                <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400">%</span>
              </div>
            </div>
          ))}
        </div>
        <button
          onClick={handleRun}
          className="bg-msb-navy text-white text-sm font-semibold px-4 py-2 rounded-lg shrink-0 hover:brightness-110 transition"
        >
          Chạy kịch bản
        </button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {result && (
        <div className="text-sm grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 border-t">
          {Object.entries(result.after).map(([key, after]) => (
            <div key={key}>
              <p className="text-gray-500">{key}</p>
              <p>Trước: {result.before[key]?.value ?? "—"} → Sau: {after.value ?? "—"}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function EbResultPanel({ result }: { result: AssessmentResult }) {
  const overview = result.overview ?? [];
  const summary = result.overview_summary;

  const infoItems: InfoBarItem[] = [
    { icon: BadgeIcon, label: "Mã hồ sơ", value: result.case_id ?? "—" },
    { icon: Building2, label: "Khách hàng", value: (result.customer_profile?.customer_name as string) ?? "—" },
    { icon: FileText, label: "MST", value: (result.customer_profile?.tax_id as string) ?? "—" },
    { icon: Clock, label: "Thời điểm chạy", value: result.assessed_at ?? "—" },
  ];

  return (
    <div className="space-y-6 mt-6">
      <InfoBar items={infoItems} banner={result.overall_conclusion} />

      <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-3">
        <SectionHeader
          icon={ClipboardList}
          title="A. Thông tin tổng quan"
          subtitle={
            summary
              ? `${summary.checked}/${summary.total} điều kiện đã kiểm tra đủ dữ liệu; ${summary.passed} đạt, ${summary.failed} không đạt, ${summary.pending} chờ xác minh.`
              : undefined
          }
        />
        <OverviewTable rows={overview} caseId={result.case_id} />
      </div>

      {result.credit_engine && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-3">
          <SectionHeader icon={TrendingUp} title="B.1 Bốn thẻ chỉ tiêu" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {Object.entries(result.credit_engine)
              .filter(([key]) => key in METRIC_LABELS)
              .map(([key, metric]) => {
                const meta = METRIC_LABELS[key];
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
        </div>
      )}

      <RiskFlagsSection flags={result.risk_flags ?? []} title="C. Cảnh báo rủi ro" />
      <DocumentPanel documents={result.documents ?? []} />
      <CrossSellOpportunities
        opportunities={result.crosssell_opportunities ?? []}
        title="E. Cơ hội bán chéo"
      />
      <AiInsightSection why={result.why ?? []} creditMemo={result.credit_memo} title="F. AI Insight" />
      <StressTestPanel creditEngine={result.credit_engine as Record<string, MetricValue> | undefined} />

      {result.export_available && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6">
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
            className="inline-flex items-center gap-2 border border-msb-navy text-msb-navy font-semibold px-4 py-2 rounded-lg hover:bg-msb-bg transition"
          >
            <FileDown className="h-4 w-4" />
            Soạn tờ trình MB02a
          </button>
        </div>
      )}
    </div>
  );
}
