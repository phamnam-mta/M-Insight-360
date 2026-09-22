"use client";

import { useState } from "react";
import {
  ACTIVATED_STATUS,
  AssessmentResult,
  ConditionRow,
  DocumentStatus,
  INSUFFICIENT_DATA_STATUS,
  RiskFlag,
  evidenceFileUrl,
} from "@/lib/api";

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
  INSUFFICIENT_DATA: "bg-gray-100 text-gray-700",
  PENDING_INTERNAL_CHECK: "bg-amber-100 text-amber-800",
  NOT_APPLICABLE: "bg-gray-100 text-gray-500",
};

function ResultBadge({ result }: { result: string }) {
  return (
    <span className={`text-xs font-semibold px-2 py-1 rounded ${RESULT_STYLE[result] ?? "bg-gray-100"}`}>
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
          <tr className="text-left border-b bg-msb-bg">
            <th className="py-2 px-2">Tên điều kiện</th>
            <th className="py-2 px-2">Giá trị/hiện trạng thực tế</th>
            <th className="py-2 px-2">Điều kiện đối chiếu</th>
            <th className="py-2 px-2">Kết quả</th>
            <th className="py-2 px-2">Nguồn chứng cứ và ngày dữ liệu</th>
            <th className="py-2 px-2">Lý do/chứng từ còn thiếu</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.condition_id} className="border-b align-top">
              <td className="py-2 px-2 font-medium">{row.condition_name}</td>
              <td className="py-2 px-2">{formatObservedValue(row)}</td>
              <td className="py-2 px-2 text-gray-600">{row.compare_rule}</td>
              <td className="py-2 px-2"><ResultBadge result={row.result} /></td>
              <td className="py-2 px-2"><EvidenceCell row={row} caseId={caseId} /></td>
              <td className="py-2 px-2 text-gray-600">{row.reason_if_incomplete ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const METRIC_LABELS: Record<string, { label: string; unit: string }> = {
  nwc: { label: "Vốn lưu động ròng (NWC)", unit: "VND" },
  dscr: { label: "Hệ số trả nợ (DSCR)", unit: "lần" },
  icr: { label: "Hệ số bù đắp lãi vay (ICR)", unit: "lần" },
  output_contract_financing_ratio: { label: "Tỷ lệ tài trợ hợp đồng đầu ra", unit: "%" },
};

type MetricValue = {
  value: number | string | null;
  formula?: string;
  input_values?: Record<string, unknown>;
  input_sources?: Record<string, string>;
  status?: string;
  policy_version?: string | null;
};

function MetricCard({ metricKey, metric }: { metricKey: string; metric: MetricValue }) {
  const [open, setOpen] = useState(false);
  const meta = METRIC_LABELS[metricKey] ?? { label: metricKey, unit: "" };
  const hasValue = metric.status === "OK" && metric.value !== null;
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-medium text-gray-500">{meta.label}</h3>
      <p className="text-2xl font-bold text-msb-navy">
        {hasValue ? `${metric.value} ${meta.unit}` : "Chưa có dữ liệu"}
      </p>
      {metricKey === "output_contract_financing_ratio" && (
        <p className="text-xs text-gray-500 mt-1">Tỷ lệ đề xuất, chưa phải mức đã phê duyệt.</p>
      )}
      <button className="text-xs text-msb-navy underline mt-2" onClick={() => setOpen((v) => !v)}>
        {open ? "Ẩn giải thích" : "Giải thích"}
      </button>
      {open && (
        <div className="mt-2 text-xs text-gray-600 space-y-1 border-t pt-2">
          <p>Công thức: {metric.formula ?? "—"}</p>
          {metric.input_values &&
            Object.entries(metric.input_values).map(([k, v]) => (
              <p key={k}>
                {k}: {String(v)} ({metric.input_sources?.[k] ?? "—"})
              </p>
            ))}
          <p>{metric.policy_version ?? "Ngưỡng demo – chờ nghiệp vụ xác nhận"}</p>
        </div>
      )}
    </div>
  );
}

function RiskFlagsSection({ flags }: { flags: RiskFlag[] }) {
  const activated = flags.filter((f) => f.status === ACTIVATED_STATUS);
  const undetermined = flags.filter((f) => f.status === INSUFFICIENT_DATA_STATUS);
  const cleared = flags.filter((f) => f.status !== ACTIVATED_STATUS && f.status !== INSUFFICIENT_DATA_STATUS);
  const [showCleared, setShowCleared] = useState(false);

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-3">
      <h2 className="text-lg font-semibold text-msb-navy">C. Cảnh báo rủi ro ({activated.length})</h2>
      {activated.length > 0 ? (
        <ul className="text-sm space-y-2">
          {activated.map((f, i) => (
            <li key={i} className="border-l-4 border-red-400 pl-3">
              <span className="font-semibold">{f.rule_name ?? f.rule_id}</span> ({f.severity}): {f.impact}
              {f.evidence_refs && Object.keys(f.evidence_refs).length > 0 && (
                <ul className="text-xs text-gray-500 mt-1">
                  {Object.values(f.evidence_refs).flat().map((ev, j) => (
                    <li key={j}>{ev.filename} — {ev.location}: &quot;{ev.original_text}&quot;</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-gray-500">Không có cảnh báo được kích hoạt trong số các quy tắc đã kiểm tra.</p>
      )}
      {undetermined.length > 0 && (
        <div className="pt-2 border-t">
          <h3 className="text-sm font-medium text-gray-500 mb-1">Chưa thể đánh giá</h3>
          <ul className="text-sm text-gray-500 space-y-1">
            {undetermined.map((f, i) => (
              <li key={i}>{f.rule_name ?? f.rule_id}: {f.impact}</li>
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
              {cleared.map((f, i) => <li key={i}>{f.rule_name ?? f.rule_id}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

const DOC_STATUS_LABEL: Record<string, string> = {
  "KHÔNG_ĐỌC_ĐƯỢC": "Không đọc được",
  "ĐÃ_TRÍCH_XUẤT": "Đã trích xuất",
  "CHỜ_XÁC_MINH": "Chờ xác minh",
  "ĐÃ_TẢI_LÊN": "Đã tải lên",
};

function DocumentPanel({ documents }: { documents: DocumentStatus[] }) {
  if (documents.length === 0) return null;
  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-2">
      <h2 className="text-lg font-semibold text-msb-navy">D. Hồ sơ khách hàng</h2>
      <ul className="text-sm divide-y">
        {documents.map((d, i) => (
          <li key={i} className="py-2 flex justify-between items-center">
            <div>
              <p className="font-medium">{d.filename}</p>
              <p className="text-xs text-gray-500">{d.doc_type ?? "—"} · {d.cited_field_count} trường đã trích xuất</p>
              {d.warnings.length > 0 && <p className="text-xs text-red-600">{d.warnings.join("; ")}</p>}
            </div>
            <span className="text-xs font-semibold px-2 py-1 rounded bg-gray-100">
              {DOC_STATUS_LABEL[d.status] ?? d.status}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function EbResultPanel({ result }: { result: AssessmentResult }) {
  const overview = result.overview ?? [];
  const summary = result.overview_summary;

  return (
    <div className="space-y-6 mt-6">
      <div className="bg-white rounded-lg shadow p-6 space-y-2">
        <div className="flex flex-wrap gap-6 text-sm">
          <div><span className="text-gray-500">Mã hồ sơ</span><p className="font-semibold">{result.case_id ?? "—"}</p></div>
          <div><span className="text-gray-500">Khách hàng</span><p className="font-semibold">{(result.customer_profile?.customer_name as string) ?? "—"}</p></div>
          <div><span className="text-gray-500">MST</span><p className="font-semibold">{(result.customer_profile?.tax_id as string) ?? "—"}</p></div>
          <div><span className="text-gray-500">Thời điểm chạy</span><p className="font-semibold">{result.assessed_at ?? "—"}</p></div>
        </div>
        {result.overall_conclusion && (
          <div className="bg-amber-50 border border-amber-300 rounded p-3 text-sm font-semibold text-amber-900">
            {result.overall_conclusion}
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow p-6 space-y-3">
        <h2 className="text-lg font-semibold text-msb-navy">A. Thông tin tổng quan</h2>
        {summary && (
          <p className="text-sm text-gray-600">
            {summary.checked}/{summary.total} điều kiện đã kiểm tra đủ dữ liệu; {summary.passed} đạt,{" "}
            {summary.failed} không đạt, {summary.pending} chờ xác minh.
          </p>
        )}
        <OverviewTable rows={overview} caseId={result.case_id} />
      </div>

      {result.credit_engine && (
        <div className="bg-white rounded-lg shadow p-6 space-y-3">
          <h2 className="text-lg font-semibold text-msb-navy">B.1 Bốn thẻ chỉ tiêu</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {Object.entries(result.credit_engine).map(([key, metric]) => (
              <MetricCard key={key} metricKey={key} metric={metric as MetricValue} />
            ))}
          </div>
        </div>
      )}

      <RiskFlagsSection flags={result.risk_flags ?? []} />
      <DocumentPanel documents={result.documents ?? []} />
    </div>
  );
}
