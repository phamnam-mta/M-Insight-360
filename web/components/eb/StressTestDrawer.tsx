"use client";

import { useState } from "react";
import { X } from "lucide-react";
import {
  AssessmentResult,
  StressScenario,
  StressTestV2Result,
  fetchStressScenarios,
  runStressTestV2,
  saveStressScenario,
} from "@/lib/api";

type Preset = "co_so" | "than_trong" | "bat_loi" | "tuy_chinh";

const PRESETS: Record<Exclude<Preset, "tuy_chinh">, { revenue_pct: number; ebit_pct: number; interest_pct: number; receivable_days_add: number; inventory_pct: number }> = {
  co_so: { revenue_pct: 0, ebit_pct: 0, interest_pct: 0, receivable_days_add: 0, inventory_pct: 0 },
  than_trong: { revenue_pct: -10, ebit_pct: -15, interest_pct: 15, receivable_days_add: 15, inventory_pct: 10 },
  bat_loi: { revenue_pct: -20, ebit_pct: -30, interest_pct: 30, receivable_days_add: 30, inventory_pct: 20 },
};

function fmt(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${(v / 1_000_000_000).toFixed(2)} tỷ`;
}

function dscrColor(v: number | null): string {
  if (v === null) return "text-gray-400";
  if (v < 1.0) return "text-red-600";
  if (v < 1.2) return "text-amber-600";
  return "text-green-600";
}

function icrColor(v: number | null): string {
  if (v === null) return "text-gray-400";
  return v < 1.5 ? "text-red-600" : "text-green-600";
}

export function StressTestDrawer({ open, onClose, result }: { open: boolean; onClose: () => void; result: AssessmentResult }) {
  const [preset, setPreset] = useState<Preset>("co_so");
  const [deltas, setDeltas] = useState(PRESETS.co_so);
  const [comprehensive, setComprehensive] = useState(false);
  const [stressResult, setStressResult] = useState<StressTestV2Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scenarioName, setScenarioName] = useState("");
  const [createdBy, setCreatedBy] = useState("RM");
  const [scenarios, setScenarios] = useState<StressScenario[]>([]);

  if (!open) return null;

  function applyPreset(p: Preset) {
    setPreset(p);
    if (p !== "tuy_chinh") setDeltas(PRESETS[p]);
  }

  async function run() {
    setError(null);
    try {
      // Raw extracted BCTC fields, straight from the /assess response's own
      // financial_inputs channel — not scavenged from Metric.input_values,
      // which exposes resolved/derived values under keys that don't always
      // match a real EbFinancialInputs field name.
      const inputs: Record<string, number | null> = { ...(result.financial_inputs ?? {}) };
      const r = await runStressTestV2(inputs, deltas, comprehensive);
      setStressResult(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stress test thất bại");
    }
  }

  async function loadScenarios() {
    if (!result.case_id) return;
    try {
      setScenarios(await fetchStressScenarios(result.case_id));
    } catch {
      // best-effort — scenario history is a convenience, not required for the run itself
    }
  }

  async function save() {
    if (!result.case_id || !stressResult || !scenarioName.trim()) return;
    await saveStressScenario(
      result.case_id, scenarioName.trim(), createdBy, result.ho_so_period?.selected ?? null,
      { preset, deltas, comprehensive_mode: comprehensive }, stressResult
    );
    setScenarioName("");
    loadScenarios();
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div className="w-full sm:w-[560px] max-w-full h-full bg-white overflow-y-auto p-6 space-y-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-msb-navy">Stress Test Dòng tiền</h2>
            <p className="text-xs text-gray-400">
              {(result.customer_profile?.customer_name as string) ?? "—"} · MST {(result.customer_profile?.tax_id as string) ?? "—"} · Kỳ {result.ho_so_period?.selected ?? "—"}
            </p>
          </div>
          <button onClick={onClose}><X className="h-5 w-5 text-gray-400" /></button>
        </div>
        <span className="inline-block text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-100 text-amber-800">Mô phỏng sơ bộ</span>

        <div className="space-y-2">
          <p className="text-sm font-semibold text-msb-navy">Kịch bản giả định</p>
          <div className="flex flex-wrap gap-2">
            {(["co_so", "than_trong", "bat_loi", "tuy_chinh"] as Preset[]).map((p) => (
              <button
                key={p}
                onClick={() => applyPreset(p)}
                className={`text-xs font-semibold px-3 py-1.5 rounded-full ${preset === p ? "bg-msb-orange text-white" : "bg-gray-100 text-gray-600"}`}
              >
                {p === "co_so" ? "Cơ sở" : p === "than_trong" ? "Thận trọng" : p === "bat_loi" ? "Bất lợi" : "Tùy chỉnh"}
              </button>
            ))}
          </div>
          {preset === "tuy_chinh" && (
            <div className="grid grid-cols-2 gap-2 pt-1">
              {(Object.keys(deltas) as Array<keyof typeof deltas>).map((k) => (
                <div key={k}>
                  <label className="block text-[11px] text-gray-500 mb-0.5">{k}</label>
                  <input
                    type="number"
                    className="w-full border border-gray-200 rounded-lg px-2 py-1 text-sm"
                    value={deltas[k]}
                    onChange={(e) => setDeltas((prev) => ({ ...prev, [k]: Number(e.target.value) }))}
                  />
                </div>
              ))}
            </div>
          )}
          <label className="flex items-center gap-2 text-xs text-gray-500 pt-1">
            <input type="checkbox" checked={comprehensive} onChange={(e) => setComprehensive(e.target.checked)} />
            Bao quát toàn bộ nghĩa vụ nợ
          </label>
          <div className="bg-gray-50 rounded-lg px-3 py-2 text-xs text-gray-600">
            Doanh thu thay đổi {deltas.revenue_pct}%, EBIT thay đổi {deltas.ebit_pct}%, chi phí lãi vay thay đổi {deltas.interest_pct}%.
          </div>
          <button onClick={run} className="bg-msb-orange text-white text-sm font-semibold px-4 py-2 rounded-lg">Chạy mô phỏng</button>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>

        {stressResult && (
          <>
            <div className="space-y-2">
              <p className="text-sm font-semibold text-msb-navy">Tác động lên dòng tiền và nghĩa vụ nợ</p>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div><p className="text-xs text-gray-400">Doanh thu</p><p>{fmt(stressResult.before.revenue as number)} → {fmt(stressResult.after.revenue as number)}</p></div>
                <div><p className="text-xs text-gray-400">EBIT</p><p>{fmt(stressResult.before.ebit as number)} → {fmt(stressResult.after.ebit as number)}</p></div>
                <div><p className="text-xs text-gray-400">Chi phí lãi vay</p><p>{fmt(stressResult.before.interest_expense as number)} → {fmt(stressResult.after.interest_expense as number)}</p></div>
                <div>
                  <p className="text-xs text-gray-400">Vốn lưu động ròng</p>
                  <p>{stressResult.nwc_impact_quantifiable ? "Xem chỉ tiêu B.1" : "Chưa đủ dữ liệu để định lượng tác động vốn lưu động"}</p>
                </div>
              </div>
              <div className="bg-gray-50 rounded-lg px-3 py-2 text-xs text-gray-600">
                {stressResult.before.debt_service_label}: {fmt(stressResult.before.debt_service_total as number)} → {fmt(stressResult.after.debt_service_total as number)}
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-sm font-semibold text-msb-navy">Khả năng trả nợ sau stress</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-gray-400">DSCR sau stress</p>
                  <p className={`text-2xl font-bold ${dscrColor(stressResult.after.dscr.value as number | null)}`}>
                    {stressResult.after.dscr.value !== null ? `${(stressResult.after.dscr.value as number).toFixed(2)}x` : "Chưa xác định từ hồ sơ tải lên"}
                  </p>
                  {stressResult.buffers.dscr_buffer !== undefined && (
                    <p className="text-xs text-gray-500">Đệm: {stressResult.buffers.dscr_buffer.toFixed(2)}x</p>
                  )}
                </div>
                <div>
                  <p className="text-xs text-gray-400">ICR sau stress</p>
                  <p className={`text-2xl font-bold ${icrColor(stressResult.after.icr.value as number | null)}`}>
                    {stressResult.after.icr.value !== null ? `${(stressResult.after.icr.value as number).toFixed(2)}x` : "Chưa xác định từ hồ sơ tải lên"}
                  </p>
                  {stressResult.buffers.icr_buffer !== undefined && (
                    <p className="text-xs text-gray-500">Đệm: {stressResult.buffers.icr_buffer.toFixed(2)}x</p>
                  )}
                </div>
              </div>
            </div>

            {stressResult.conclusions.length > 0 && (
              <div className="space-y-1">
                <p className="text-sm font-semibold text-msb-navy">Kết luận AI</p>
                <ul className="text-xs text-gray-600 list-disc list-inside space-y-1">
                  {stressResult.conclusions.map((c, i) => <li key={i}>{c}</li>)}
                </ul>
              </div>
            )}
            {stressResult.recommended_actions.length > 0 && (
              <div className="space-y-1">
                <p className="text-sm font-semibold text-msb-navy">Hành động RM đề xuất</p>
                <ol className="text-xs text-gray-600 list-decimal list-inside space-y-1">
                  {stressResult.recommended_actions.map((a, i) => <li key={i}>{a}</li>)}
                </ol>
              </div>
            )}

            <p className="text-[11px] text-gray-400 border-t pt-2">{stressResult.disclaimer}</p>

            <div className="space-y-2 border-t pt-3">
              <div className="flex gap-2">
                <input
                  className="flex-1 border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
                  placeholder="Tên kịch bản"
                  value={scenarioName}
                  onChange={(e) => setScenarioName(e.target.value)}
                />
                <input
                  className="w-24 border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
                  placeholder="Người tạo"
                  value={createdBy}
                  onChange={(e) => setCreatedBy(e.target.value)}
                />
                <button onClick={save} className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-msb-navy text-white shrink-0">Lưu kịch bản</button>
              </div>
              <button onClick={() => applyPreset("co_so")} className="text-xs text-gray-500 underline">Khôi phục kịch bản cơ sở</button>
              <button onClick={loadScenarios} className="text-xs text-msb-navy underline ml-3">Xem kịch bản đã lưu</button>
              {scenarios.length > 0 && (
                <ul className="text-xs text-gray-500 space-y-1 pt-1">
                  {scenarios.map((s) => (
                    <li key={s.id}>{s.name} · {s.created_by} · {new Date(s.created_at).toLocaleString("vi-VN")}</li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
