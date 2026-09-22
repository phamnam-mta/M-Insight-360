"use client";

import { useState } from "react";
import { AssessmentResult, runAssessment } from "@/lib/api";

type Props = {
  agentType: "rb" | "eb" | "crosssell";
  onResult: (result: AssessmentResult) => void;
};

const CROSSSELL_FIELDS: Array<{ key: string; label: string }> = [
  { key: "opening_balance", label: "Số dư đầu kỳ (VND)" },
  { key: "closing_balance", label: "Số dư cuối kỳ (VND)" },
  { key: "receivables_131_current_vnd", label: "Phải thu 131 hiện tại (VND)" },
  { key: "payables_331_vnd", label: "Phải trả 331 (VND)" },
  { key: "total_receivable_credit_131_vnd", label: "Tổng phát sinh Có 131 (VND)" },
];

const EB_FIELDS: Array<{ key: string; label: string }> = [
  { key: "proposed_limit_vnd", label: "Hạn mức đề xuất cho hợp đồng (VND)" },
  { key: "eligible_contract_value_vnd", label: "Giá trị hợp đồng đủ điều kiện (VND)" },
];

export default function AssessmentForm({ agentType, onResult }: Props) {
  const [customerName, setCustomerName] = useState("");
  const [taxId, setTaxId] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [crosssellFields, setCrosssellFields] = useState<Record<string, string>>({});
  const [ebFields, setEbFields] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = customerName.trim() !== "" && taxId.trim() !== "" && files.length > 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    try {
      const result = await runAssessment(
        agentType,
        customerName,
        taxId,
        files,
        agentType === "crosssell" ? crosssellFields : agentType === "eb" ? ebFields : undefined
      );
      onResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đã xảy ra lỗi không xác định");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-4">
      <h2 className="text-lg font-semibold text-msb-navy">Thẩm định Khách hàng mới</h2>

      <div>
        <label className="block text-sm font-medium text-msb-navy mb-1">
          Tên Khách hàng <span className="text-red-600">*</span>
        </label>
        <input
          className="w-full border rounded px-3 py-2"
          value={customerName}
          onChange={(e) => setCustomerName(e.target.value)}
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-msb-navy mb-1">
          Mã số thuế <span className="text-red-600">*</span>
        </label>
        <input
          className="w-full border rounded px-3 py-2"
          value={taxId}
          onChange={(e) => setTaxId(e.target.value)}
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-msb-navy mb-1">
          Upload hồ sơ (docx, pdf, xlsx, csv) <span className="text-red-600">*</span>
        </label>
        <input
          type="file"
          multiple
          accept=".docx,.pdf,.xlsx,.csv"
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          required
        />
      </div>

      {agentType === "crosssell" && (
        <div className="border-t pt-4 space-y-3">
          <p className="text-sm text-gray-500">
            Số liệu bổ sung (tùy chọn) — giúp đối chiếu tính toàn vẹn sao kê và tính
            chính xác các cơ hội tài trợ phải thu/phải trả. Để trống nếu chưa có.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {CROSSSELL_FIELDS.map((f) => (
              <div key={f.key}>
                <label className="block text-xs font-medium text-msb-navy mb-1">{f.label}</label>
                <input
                  type="number"
                  className="w-full border rounded px-3 py-2 text-sm"
                  value={crosssellFields[f.key] ?? ""}
                  onChange={(e) =>
                    setCrosssellFields((prev) => ({ ...prev, [f.key]: e.target.value }))
                  }
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {agentType === "eb" && (
        <div className="border-t pt-4 space-y-3">
          <p className="text-sm text-gray-500">
            Số liệu bổ sung (tùy chọn) — dùng để tính tỷ lệ tài trợ hợp đồng đầu ra. Để trống nếu chưa có.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {EB_FIELDS.map((f) => (
              <div key={f.key}>
                <label className="block text-xs font-medium text-msb-navy mb-1">{f.label}</label>
                <input
                  type="number"
                  className="w-full border rounded px-3 py-2 text-sm"
                  value={ebFields[f.key] ?? ""}
                  onChange={(e) =>
                    setEbFields((prev) => ({ ...prev, [f.key]: e.target.value }))
                  }
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <button
        type="submit"
        disabled={!canSubmit || loading}
        className="bg-msb-orange text-white font-semibold px-4 py-2 rounded disabled:opacity-50"
      >
        {loading ? "Đang xử lý..." : "Chạy thẩm định AI"}
      </button>
    </form>
  );
}
