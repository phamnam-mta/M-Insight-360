"use client";

import { useEffect, useState } from "react";
import { RbCaseSection, getCase, updateCaseSection } from "@/lib/rb-portal-api";

export type SectionField = {
  key: string;
  label: string;
  type: "text" | "number" | "select" | "date";
  options?: { value: string; label: string }[];
};

export function SectionForm({
  caseId, section, title, fields,
}: { caseId: string; section: RbCaseSection; title: string; fields: SectionField[] }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getCase(caseId)
      .then((c) => {
        const section_data = (c[section] as Record<string, unknown> | null) ?? {};
        const asStrings: Record<string, string> = {};
        for (const f of fields) {
          const v = section_data[f.key];
          asStrings[f.key] = v === null || v === undefined ? "" : String(v);
        }
        setValues(asStrings);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Không tải được dữ liệu"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, section]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const payload: Record<string, unknown> = {};
      for (const f of fields) {
        const raw = values[f.key] ?? "";
        payload[f.key] = f.type === "number" ? (raw === "" ? null : Number(raw)) : raw || null;
      }
      await updateCaseSection(caseId, section, payload);
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
      <h3 className="text-sm font-semibold text-msb-navy">{title}</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {fields.map((f) => (
          <div key={f.key}>
            <label className="block text-xs font-medium text-msb-navy mb-1">{f.label}</label>
            {f.type === "select" ? (
              <select
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                value={values[f.key] ?? ""}
                onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
              >
                <option value="">— Chọn —</option>
                {f.options?.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            ) : (
              <input
                type={f.type === "date" ? "date" : f.type === "number" ? "number" : "text"}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                value={values[f.key] ?? ""}
                onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
              />
            )}
          </div>
        ))}
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="bg-msb-orange text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50"
        >
          {saving ? "Đang lưu..." : "Lưu"}
        </button>
        {saved && <span className="text-xs text-green-600">Đã lưu.</span>}
      </div>
    </div>
  );
}
