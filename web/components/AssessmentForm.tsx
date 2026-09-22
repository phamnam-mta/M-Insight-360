"use client";

import { useState } from "react";
import { Coins, FileText, IdCard, Paperclip, Sparkles, User } from "lucide-react";
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
    <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 space-y-4">
      <div className="flex items-center gap-2.5 mb-1">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-msb-orange/10 text-msb-orange shrink-0">
          <IdCard className="h-4 w-4" />
        </span>
        <h2 className="text-lg font-semibold text-msb-navy">Thẩm định Khách hàng mới</h2>
      </div>

      <div>
        <label className="block text-sm font-medium text-msb-navy mb-1">
          Tên Khách hàng <span className="text-red-600">*</span>
        </label>
        <div className="relative">
          <User className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            className="w-full border border-gray-200 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-msb-orange/40 focus:border-msb-orange"
            value={customerName}
            onChange={(e) => setCustomerName(e.target.value)}
            required
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-msb-navy mb-1">
          Mã số thuế <span className="text-red-600">*</span>
        </label>
        <div className="relative">
          <FileText className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            className="w-full border border-gray-200 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-msb-orange/40 focus:border-msb-orange"
            value={taxId}
            onChange={(e) => setTaxId(e.target.value)}
            required
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-msb-navy mb-1">
          Upload hồ sơ (docx, pdf, xlsx, csv) <span className="text-red-600">*</span>
        </label>
        <div className="flex items-center gap-3 border border-dashed border-gray-300 rounded-lg px-3 py-2.5 bg-gray-50/60">
          <Paperclip className="h-4 w-4 text-gray-400 shrink-0" />
          <label className="inline-flex items-center gap-1.5 text-xs font-semibold text-msb-navy bg-msb-bg/70 border border-msb-navy/10 rounded-full px-3.5 py-1.5 cursor-pointer hover:bg-msb-bg shrink-0">
            Chọn tệp
            <input
              type="file"
              multiple
              accept=".docx,.pdf,.xlsx,.csv"
              onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
              required
              className="hidden"
            />
          </label>
          <span className="text-xs text-gray-500 truncate">
            {files.length > 0 ? `${files.length} tệp đã chọn` : "Chưa chọn tệp nào"}
          </span>
        </div>
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
                <div className="relative">
                  <Coins className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <input
                    type="number"
                    placeholder="Nhập số tiền"
                    className="w-full border border-gray-200 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-msb-orange/40 focus:border-msb-orange"
                    value={crosssellFields[f.key] ?? ""}
                    onChange={(e) =>
                      setCrosssellFields((prev) => ({ ...prev, [f.key]: e.target.value }))
                    }
                  />
                </div>
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
                <div className="relative">
                  <Coins className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <input
                    type="number"
                    placeholder="Nhập số tiền"
                    className="w-full border border-gray-200 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-msb-orange/40 focus:border-msb-orange"
                    value={ebFields[f.key] ?? ""}
                    onChange={(e) =>
                      setEbFields((prev) => ({ ...prev, [f.key]: e.target.value }))
                    }
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <button
        type="submit"
        disabled={!canSubmit || loading}
        className="inline-flex items-center justify-center gap-2 bg-msb-orange text-white text-sm font-semibold px-5 py-2 rounded-full shadow-sm hover:brightness-105 transition disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <Sparkles className="h-4 w-4" />
        {loading ? "Đang xử lý..." : "Chạy thẩm định AI"}
      </button>
    </form>
  );
}
