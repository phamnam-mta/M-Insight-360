"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { getCase, updateCaseSection } from "@/lib/rb-portal-api";

type CollateralItem = { asset_type: string; ownership_status: string; estimated_value_vnd: string };

const EMPTY_ITEM: CollateralItem = { asset_type: "", ownership_status: "", estimated_value_vnd: "" };

export function CollateralTab({ caseId }: { caseId: string }) {
  const [items, setItems] = useState<CollateralItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getCase(caseId)
      .then((c) => {
        const raw = (c.collateral?.items ?? []) as Record<string, unknown>[];
        setItems(
          raw.map((it) => ({
            asset_type: String(it.asset_type ?? ""), ownership_status: String(it.ownership_status ?? ""),
            estimated_value_vnd: it.estimated_value_vnd == null ? "" : String(it.estimated_value_vnd),
          }))
        );
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Không tải được dữ liệu"))
      .finally(() => setLoading(false));
  }, [caseId]);

  function updateItem(i: number, patch: Partial<CollateralItem>) {
    setItems((prev) => prev.map((it, idx) => (idx === i ? { ...it, ...patch } : it)));
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const payload = {
        items: items
          .filter((it) => it.asset_type.trim() !== "")
          .map((it) => ({
            asset_type: it.asset_type,
            ownership_status: it.ownership_status,
            estimated_value_vnd: it.estimated_value_vnd === "" ? null : Number(it.estimated_value_vnd),
          })),
      };
      await updateCaseSection(caseId, "collateral", payload);
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
      <h3 className="text-sm font-semibold text-msb-navy">Tài sản bảo đảm</h3>
      <div className="space-y-3">
        {items.map((it, i) => (
          <div key={i} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_1fr_auto] gap-2 items-end border-b border-gray-50 pb-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Loại tài sản</label>
              <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={it.asset_type} onChange={(e) => updateItem(i, { asset_type: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Tình trạng sở hữu</label>
              <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={it.ownership_status} onChange={(e) => updateItem(i, { ownership_status: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Giá trị ước tính (VND)</label>
              <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={it.estimated_value_vnd} onChange={(e) => updateItem(i, { estimated_value_vnd: e.target.value })} />
            </div>
            <button onClick={() => setItems((prev) => prev.filter((_, idx) => idx !== i))} className="text-red-500 p-2">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
      <button
        onClick={() => setItems((prev) => [...prev, { ...EMPTY_ITEM }])}
        className="inline-flex items-center gap-1.5 text-sm text-msb-navy underline"
      >
        <Plus className="h-4 w-4" /> Thêm tài sản
      </button>
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
