"use client";

import { useEffect, useState } from "react";
import { UploadCloud } from "lucide-react";
import { RbDocument, listDocuments, uploadDocument } from "@/lib/rb-portal-api";

const CATEGORIES = [
  { value: "LEGAL", label: "Pháp lý" }, { value: "INCOME", label: "Nguồn thu" },
  { value: "LOAN", label: "Khoản vay" }, { value: "COLLATERAL", label: "Tài sản bảo đảm" },
  { value: "OTHER", label: "Khác" },
];

const STATUS_LABEL: Record<string, string> = {
  UPLOADED: "Đã tải lên", PROCESSING: "Đang xử lý", EXTRACTED: "Đã trích xuất",
  FAILED: "Không đọc được", NEED_OCR_VLM: "Cần OCR thủ công",
};
const STATUS_STYLE: Record<string, string> = {
  UPLOADED: "bg-gray-100 text-gray-600", PROCESSING: "bg-amber-100 text-amber-700",
  EXTRACTED: "bg-green-100 text-green-700", FAILED: "bg-red-100 text-red-700",
  NEED_OCR_VLM: "bg-amber-100 text-amber-700",
};

export function DocumentsTab({ caseId }: { caseId: string }) {
  const [docs, setDocs] = useState<RbDocument[]>([]);
  const [category, setCategory] = useState("LEGAL");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    listDocuments(caseId).then(setDocs).catch(() => setDocs([]));
  }

  useEffect(reload, [caseId]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadDocument(caseId, file, category);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tải lên thất bại");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-4">
      <h3 className="text-sm font-semibold text-msb-navy">Tải lên chứng từ</h3>

      <div className="flex flex-wrap items-center gap-3 border border-dashed border-gray-300 rounded-lg p-3 bg-gray-50/60">
        <select
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        <label className="inline-flex items-center gap-1.5 text-xs font-semibold text-msb-navy bg-white border border-msb-navy/10 rounded-full px-3.5 py-1.5 cursor-pointer hover:bg-msb-bg">
          <UploadCloud className="h-3.5 w-3.5" />
          {uploading ? "Đang tải..." : "Chọn tệp"}
          <input type="file" className="hidden" onChange={handleUpload} disabled={uploading} />
        </label>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}

      {docs.length === 0 ? (
        <p className="text-sm text-gray-500">Chưa có chứng từ nào.</p>
      ) : (
        <ul className="divide-y">
          {docs.map((d) => (
            <li key={d.id} className="py-2.5 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-msb-navy truncate">{d.filename}</p>
                <p className="text-xs text-gray-500">
                  {CATEGORIES.find((c) => c.value === d.category)?.label ?? d.category}
                  {d.document_type ? ` · ${d.document_type}` : ""}
                </p>
              </div>
              <span className={`text-xs font-semibold px-2.5 py-1 rounded-full shrink-0 ${STATUS_STYLE[d.status] ?? "bg-gray-100 text-gray-600"}`}>
                {STATUS_LABEL[d.status] ?? d.status}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
