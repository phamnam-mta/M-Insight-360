"use client";

import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { RbCase, createCase, listCases } from "@/lib/rb-portal-api";

export function OverviewTab({ onSelectCase }: { onSelectCase: (caseId: string) => void }) {
  const [cases, setCases] = useState<RbCase[]>([]);
  const [customerName, setCustomerName] = useState("");
  const [taxId, setTaxId] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCases().then(setCases).catch(() => setCases([]));
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!customerName.trim() || !taxId.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const { case_id } = await createCase(customerName.trim(), taxId.trim());
      onSelectCase(case_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tạo hồ sơ thất bại");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-5">
      <form onSubmit={handleCreate} className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
        <h3 className="text-sm font-semibold text-msb-navy">Tạo hồ sơ mới</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <input
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
            placeholder="Tên khách hàng"
            value={customerName}
            onChange={(e) => setCustomerName(e.target.value)}
          />
          <input
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
            placeholder="Mã số thuế / CCCD"
            value={taxId}
            onChange={(e) => setTaxId(e.target.value)}
          />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={creating}
          className="inline-flex items-center gap-1.5 bg-msb-orange text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          {creating ? "Đang tạo..." : "Tạo hồ sơ"}
        </button>
      </form>

      <div className="bg-white rounded-xl border border-gray-100 p-5">
        <h3 className="text-sm font-semibold text-msb-navy mb-3">Hồ sơ gần đây</h3>
        {cases.length === 0 ? (
          <p className="text-sm text-gray-500">Chưa có hồ sơ nào.</p>
        ) : (
          <ul className="divide-y">
            {cases.map((c) => (
              <li key={c.case_id} className="py-2.5">
                <button
                  onClick={() => onSelectCase(c.case_id)}
                  className="w-full text-left hover:bg-msb-bg rounded-lg px-2 py-1 -mx-2 transition-colors"
                >
                  <p className="text-sm font-medium text-msb-navy">{c.customer_name}</p>
                  <p className="text-xs text-gray-500">
                    {c.case_id} · MST {c.tax_id} · {c.status}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
