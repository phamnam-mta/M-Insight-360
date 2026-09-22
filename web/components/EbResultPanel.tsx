"use client";

import { AssessmentResult, ConditionRow, evidenceFileUrl } from "@/lib/api";

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
    </div>
  );
}
