"use client";

import { useState } from "react";
import { RbSummary, runFullAssessment, runPreliminaryAssessment } from "@/lib/rb-portal-api";

export function AssessmentTab({ caseId }: { caseId: string }) {
  const [loading, setLoading] = useState<"preliminary" | "full" | null>(null);
  const [result, setResult] = useState<RbSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(kind: "preliminary" | "full") {
    setLoading(kind);
    setError(null);
    setResult(null);
    try {
      const body = kind === "preliminary" ? await runPreliminaryAssessment(caseId) : await runFullAssessment(caseId);
      setResult(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Thẩm định thất bại");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-4">
      <h3 className="text-sm font-semibold text-msb-navy">Thẩm định</h3>
      <p className="text-xs text-gray-500">
        Thẩm định sơ bộ chạy được ngay khi có dữ liệu tối thiểu. Thẩm định đầy đủ yêu cầu đủ
        checklist bắt buộc (xem tab Tổng hợp) — nếu thiếu sẽ báo lỗi thay vì chạy ngầm.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => run("preliminary")}
          disabled={loading !== null}
          className="bg-msb-orange text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50"
        >
          {loading === "preliminary" ? "Đang chạy..." : "Chạy thẩm định sơ bộ"}
        </button>
        <button
          onClick={() => run("full")}
          disabled={loading !== null}
          className="border border-msb-navy text-msb-navy text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50"
        >
          {loading === "full" ? "Đang chạy..." : "Chạy thẩm định đầy đủ"}
        </button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {result && (
        <div className="border-t pt-3 space-y-1 text-sm">
          <p><span className="font-medium">Kết quả:</span> {result.credit_readiness}</p>
          <p><span className="font-medium">Khuyến nghị:</span> {result.recommendation}</p>
          <p className="text-xs text-gray-500">Xem chi tiết đầy đủ ở tab Tổng hợp.</p>
        </div>
      )}
    </div>
  );
}
