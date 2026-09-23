"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { getCase, updateCaseSection } from "@/lib/rb-portal-api";

type Relationship = { institution: string; credit_type: string; outstanding_vnd: string; monthly_payment_vnd: string };

const EMPTY_REL: Relationship = { institution: "", credit_type: "", outstanding_vnd: "", monthly_payment_vnd: "" };

export function OtherDocsTab({ caseId }: { caseId: string }) {
  const [notes, setNotes] = useState("");
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getCase(caseId)
      .then((c) => {
        const other = (c.other as Record<string, unknown> | null) ?? {};
        setNotes(String(other.notes ?? ""));
        const raw = (other.existing_credit_relationships ?? []) as Record<string, unknown>[];
        setRelationships(
          raw.map((r) => ({
            institution: String(r.institution ?? ""), credit_type: String(r.credit_type ?? ""),
            outstanding_vnd: r.outstanding_vnd == null ? "" : String(r.outstanding_vnd),
            monthly_payment_vnd: r.monthly_payment_vnd == null ? "" : String(r.monthly_payment_vnd),
          }))
        );
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Không tải được dữ liệu"))
      .finally(() => setLoading(false));
  }, [caseId]);

  function updateRel(i: number, patch: Partial<Relationship>) {
    setRelationships((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const payload = {
        notes: notes || null,
        existing_credit_relationships: relationships
          .filter((r) => r.institution.trim() !== "")
          .map((r) => ({
            institution: r.institution, credit_type: r.credit_type,
            outstanding_vnd: r.outstanding_vnd === "" ? null : Number(r.outstanding_vnd),
            monthly_payment_vnd: r.monthly_payment_vnd === "" ? null : Number(r.monthly_payment_vnd),
          })),
      };
      await updateCaseSection(caseId, "other", payload);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lưu thất bại");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="text-sm text-gray-500">Đang tải...</p>;

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-4">
      <h3 className="text-sm font-semibold text-msb-navy">Hồ sơ khác</h3>

      <div>
        <label className="block text-xs font-medium text-msb-navy mb-1">Ghi chú</label>
        <textarea
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>

      <div className="border-t pt-4 space-y-3">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
          Quan hệ tín dụng hiện có tại MSB/tổ chức khác
        </p>
        {relationships.map((r, i) => (
          <div key={i} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_1fr_1fr_auto] gap-2 items-end border-b border-gray-50 pb-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Tổ chức tín dụng</label>
              <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={r.institution} onChange={(e) => updateRel(i, { institution: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Hình thức cấp tín dụng</label>
              <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={r.credit_type} onChange={(e) => updateRel(i, { credit_type: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Dư nợ còn lại (VND)</label>
              <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={r.outstanding_vnd} onChange={(e) => updateRel(i, { outstanding_vnd: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Trả hàng tháng (VND)</label>
              <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={r.monthly_payment_vnd} onChange={(e) => updateRel(i, { monthly_payment_vnd: e.target.value })} />
            </div>
            <button onClick={() => setRelationships((prev) => prev.filter((_, idx) => idx !== i))} className="text-red-500 p-2">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        <button
          onClick={() => setRelationships((prev) => [...prev, { ...EMPTY_REL }])}
          className="inline-flex items-center gap-1.5 text-sm text-msb-navy underline"
        >
          <Plus className="h-4 w-4" /> Thêm quan hệ tín dụng
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex items-center gap-3 border-t pt-3">
        <button onClick={handleSave} disabled={saving} className="bg-msb-orange text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50">
          {saving ? "Đang lưu..." : "Lưu"}
        </button>
        {saved && <span className="text-xs text-green-600">Đã lưu.</span>}
      </div>
    </div>
  );
}
