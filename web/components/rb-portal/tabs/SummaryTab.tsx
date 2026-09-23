"use client";

import { useEffect, useRef, useState } from "react";
import { Banknote, CheckCircle2, ClipboardList, FileDown, FileText, FolderOpen, IdCard } from "lucide-react";
import { RbSummary, getSummary } from "@/lib/rb-portal-api";
import { AiInsightSection } from "../../shared/AiInsightSection";
import { RiskFlagsSection } from "../../shared/RiskFlagsSection";
import { MetricCard, MetricValue } from "../../shared/MetricCard";
import { SectionHeader } from "../../shared/SectionHeader";

const METRIC_LABELS: Record<string, { label: string; unit: string }> = {
  eligible_monthly_income: { label: "Thu nhập đủ điều kiện", unit: "VND" },
  new_loan_first_month_payment: { label: "Trả nợ tháng đầu (khoản vay mới)", unit: "VND" },
  total_monthly_obligation: { label: "Tổng nghĩa vụ trả nợ hàng tháng", unit: "VND" },
  dti: { label: "Tỷ lệ nợ trên thu nhập (DTI)", unit: "" },
  dsr: { label: "Tỷ lệ trả nợ (DSR)", unit: "" },
  remaining_disposable_income: { label: "Thu nhập khả dụng còn lại", unit: "VND" },
};

// eligible_monthly_income and dti both require avg_monthly_revenue_vnd (true
// business revenue, before an eligibility margin), which RB Portal never
// collects for any case — it only collects the RM-entered income figure,
// which feeds dsr directly instead (see assessment.py's build_loan_inputs).
// These two metrics are therefore structurally unreachable here, not just
// "missing for this case" — an unexplained "Chưa có dữ liệu" would wrongly
// suggest a temporary gap the RM could fill in.
const _STRUCTURALLY_UNREACHABLE_NOTE: Record<string, string> = {
  eligible_monthly_income: "RB Portal không thu thập doanh thu kinh doanh nên không tính được chỉ tiêu này — xem DSR thay thế.",
  dti: "RB Portal không thu thập doanh thu kinh doanh nên không tính được DTI — xem DSR thay thế.",
};

const MISSING_LABEL: Record<string, string> = {
  legal_identity: "Họ tên khách hàng (tab Hồ sơ khách hàng)",
  id_document: "Loại giấy tờ định danh (tab Pháp lý)",
  income_section: "Thông tin nguồn thu (tab Nguồn thu)",
  income_source_type: "Nguồn thu nhập chính (tab Nguồn thu)",
  tax_declaration: "Xác nhận đã có tờ khai thuế (tab Nguồn thu)",
  loan_request: "Sản phẩm vay (tab Khoản vay)",
  loan_purpose: "Mục đích vay (tab Khoản vay)",
};

const READINESS_LABEL: Record<string, string> = {
  PRELIMINARY_READY: "Sẵn sàng thẩm định sơ bộ",
  PRELIMINARY_READY_WITH_CONDITIONS: "Sẵn sàng có điều kiện",
  INSUFFICIENT_DATA: "Chưa đủ dữ liệu",
  MANUAL_REVIEW_REQUIRED: "Cần thẩm định thủ công",
};

// Submitted as a hidden-iframe form POST rather than fetch()+blob()+<a download>:
// a blob: URL carries no HTTP headers, so the backend's Content-Disposition
// (which correctly RFC-5987-encodes the required Vietnamese filename) is
// invisible to a blob download — and Chromium was confirmed during Task 21's
// manual verification to silently discard non-ASCII `<a download>` values for
// blob: URLs, falling back to a bare "download" name. A real form POST is a
// normal browser-driven network download, so Content-Disposition governs the
// filename exactly as it does for any other file download.
const EXPORT_IFRAME_NAME = "rb-portal-export-frame";

export function SummaryTab({ caseId, onEditSection }: { caseId: string; onEditSection: (tab: string) => void }) {
  const [summary, setSummary] = useState<RbSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  function reload() {
    getSummary(caseId).then(setSummary).catch((err) => setError(err instanceof Error ? err.message : "Không tải được"));
  }

  useEffect(reload, [caseId]);

  function handleExport() {
    setExporting(true);
    setExportError(null);
    const form = document.createElement("form");
    form.method = "POST";
    form.action = `/api/rb-portal/cases/${encodeURIComponent(caseId)}/export/mb01a`;
    form.target = EXPORT_IFRAME_NAME;
    document.body.appendChild(form);
    form.submit();
    document.body.removeChild(form);
    setTimeout(() => setExporting(false), 1200);
  }

  // A successful attachment download never navigates the iframe (the browser
  // intercepts it as a download before rendering), so this `load` firing
  // means the server actually rendered a page into the iframe — an error
  // response (like the Dockerfile-missing-template 500 found during Task 21),
  // not the .docx. Previously this failed completely silently, against the
  // "không silent fail" business rule.
  function handleExportFrameLoad() {
    try {
      const doc = iframeRef.current?.contentDocument;
      const text = doc?.body?.textContent?.trim();
      if (text) {
        setExportError(`Xuất tờ trình thất bại: ${text.slice(0, 200)}`);
      }
    } catch {
      // cross-origin or otherwise unreadable — nothing more we can safely detect
    }
  }

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!summary) return <p className="text-sm text-gray-500">Đang tải...</p>;

  const customer = (summary.customer ?? {}) as Record<string, unknown>;
  const loan = (summary.loan ?? {}) as Record<string, unknown>;

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-xl border border-gray-100 p-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs text-gray-400">Hồ sơ &gt; {summary.case_id} &gt; Tổng hợp</p>
          <h2 className="text-lg font-bold text-msb-navy">Kết quả thẩm định sơ bộ</h2>
        </div>
        <div className="flex flex-col items-end gap-1">
          <button
            onClick={handleExport}
            disabled={exporting}
            className="inline-flex items-center gap-1.5 bg-msb-navy text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50"
          >
            <FileDown className="h-4 w-4" />
            {exporting ? "Đang xuất..." : "Xuất MB01A QT.RR.038 (lần 3)"}
          </button>
          {exportError && <p className="text-xs text-red-600 max-w-xs text-right">{exportError}</p>}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-2">
          <div className="flex items-center justify-between">
            <SectionHeader icon={IdCard} title="Thông tin khách hàng" />
            <button onClick={() => onEditSection("customer")} className="text-xs text-msb-navy underline shrink-0">Chỉnh sửa</button>
          </div>
          <p className="text-sm"><span className="text-gray-500">Họ tên:</span> {String(customer.full_name ?? "—")}</p>
          <p className="text-sm"><span className="text-gray-500">MST:</span> {summary.tax_id}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-2">
          <div className="flex items-center justify-between">
            <SectionHeader icon={Banknote} title="Thông tin khoản vay đề nghị" />
            <button onClick={() => onEditSection("loan")} className="text-xs text-msb-navy underline shrink-0">Chỉnh sửa</button>
          </div>
          <p className="text-sm"><span className="text-gray-500">Sản phẩm:</span> {String(loan.product ?? "—")}</p>
          <p className="text-sm"><span className="text-gray-500">Số tiền:</span> {loan.amount_vnd ? `${loan.amount_vnd} VND` : "—"}</p>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
        <SectionHeader icon={ClipboardList} title="Chỉ tiêu tài chính sơ bộ" />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {Object.entries(summary.credit_engine)
            .filter(([key]) => key in METRIC_LABELS)
            .map(([key, metric]) => (
              <MetricCard
                key={key}
                label={METRIC_LABELS[key].label}
                unit={METRIC_LABELS[key].unit}
                metric={metric as MetricValue}
                note={_STRUCTURALLY_UNREACHABLE_NOTE[key]}
              />
            ))}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-1">
        <SectionHeader icon={CheckCircle2} title="Đánh giá & Khuyến nghị" />
        <p className="text-sm font-semibold text-msb-navy">{READINESS_LABEL[summary.credit_readiness] ?? summary.credit_readiness}</p>
        <p className="text-xs text-gray-500">{summary.recommendation}</p>
      </div>

      <RiskFlagsSection flags={summary.risk_flags} title="Điểm cần lưu ý" />

      <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-2">
        <SectionHeader icon={ClipboardList} title="Trạng thái hồ sơ" />
        <ol className="flex flex-wrap gap-3 text-xs">
          {summary.timeline.map((step) => (
            <li key={step.status} className={`px-3 py-1.5 rounded-full ${step.reached ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-400"}`}>
              {step.label}
            </li>
          ))}
        </ol>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-2">
        <SectionHeader icon={FileText} title={`Hồ sơ còn thiếu (${summary.missing_data.length})`} />
        {summary.missing_data.length === 0 ? (
          <p className="text-sm text-gray-500">Không có.</p>
        ) : (
          <ul className="text-sm list-disc list-inside space-y-1">
            {summary.missing_data.map((m, i) => (
              <li key={i}>
                {MISSING_LABEL[m] ?? m} <span className="text-xs text-gray-400">({m})</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-2">
        <SectionHeader icon={FolderOpen} title={`Hồ sơ đã tải lên (${summary.documents.length})`} />
        {summary.documents.length === 0 ? (
          <p className="text-sm text-gray-500">Chưa có tệp nào.</p>
        ) : (
          <ul className="text-sm divide-y">
            {summary.documents.map((d) => (
              <li key={d.id} className="py-2 flex justify-between gap-3">
                <span className="truncate">{d.filename}</span>
                <span className="text-xs text-gray-400 shrink-0">{d.category} · {d.status}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <AiInsightSection why={summary.why} creditMemo={summary.credit_memo} title="AI Insight" />

      <iframe ref={iframeRef} name={EXPORT_IFRAME_NAME} className="hidden" title="Xuất MB01A" onLoad={handleExportFrameLoad} />
    </div>
  );
}
