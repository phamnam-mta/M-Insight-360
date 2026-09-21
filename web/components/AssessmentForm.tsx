"use client";

import { useState } from "react";
import { AssessmentResult, runAssessment } from "@/lib/api";

type Props = {
  agentType: "rb" | "eb";
  onResult: (result: AssessmentResult) => void;
};

export default function AssessmentForm({ agentType, onResult }: Props) {
  const [customerName, setCustomerName] = useState("");
  const [taxId, setTaxId] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = customerName.trim() !== "" && taxId.trim() !== "" && files.length > 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    try {
      const result = await runAssessment(agentType, customerName, taxId, files);
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
