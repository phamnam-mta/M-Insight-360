"use client";

import { useState } from "react";

export type MetricValue = {
  value: number | string | null;
  formula?: string;
  input_values?: Record<string, unknown>;
  input_sources?: Record<string, string>;
  status?: string;
  policy_version?: string | null;
};

export function MetricCard({
  label,
  unit,
  metric,
  note,
  compact = false,
}: {
  label: string;
  unit: string;
  metric: MetricValue;
  note?: string;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const hasValue = metric.status === "OK" && metric.value !== null;

  if (compact) {
    return (
      <div
        data-testid="eb-kpi-card"
        className="bg-gray-50 border border-gray-100 rounded-lg px-2.5 py-2 flex flex-col justify-center min-w-0"
        style={{ maxHeight: 72 }}
      >
        <h3 className="text-[10px] font-medium text-gray-500 uppercase tracking-wide truncate">{label}</h3>
        <p className="text-sm font-semibold text-gray-400">—</p>
      </div>
    );
  }

  if (!hasValue) {
    return (
      <div data-testid="eb-kpi-card" className="bg-gray-50 rounded-lg border border-gray-100 p-2.5 self-start">
        <h3 className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">{label}</h3>
        <p className="text-base font-semibold text-gray-400 mt-0.5">—</p>
        <button className="text-[11px] text-msb-navy underline mt-1" onClick={() => setOpen((v) => !v)}>
          {open ? "Ẩn giải thích" : "Giải thích"}
        </button>
        {open && (
          <div className="mt-1.5 text-[11px] text-gray-500 space-y-1 border-t pt-1.5">
            <p>Chưa xác định từ hồ sơ tải lên.</p>
            {metric.formula && <p>Công thức: {metric.formula}</p>}
            <button className="text-msb-navy underline">Nhập tay giá trị này</button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div data-testid="eb-kpi-card" className="bg-white rounded-lg border border-gray-100 shadow-sm p-4">
      <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</h3>
      <p className="text-2xl font-bold mt-1 text-msb-navy">
        {metric.value} {unit}
      </p>
      {note && <p className="text-xs text-gray-500 mt-1">{note}</p>}
      <button className="text-xs text-msb-navy underline mt-2" onClick={() => setOpen((v) => !v)}>
        {open ? "Ẩn giải thích" : "Giải thích"}
      </button>
      {open && (
        <div className="mt-2 text-xs text-gray-600 space-y-1 border-t pt-2">
          <p>Công thức: {metric.formula ?? "—"}</p>
          {metric.input_values &&
            Object.entries(metric.input_values).map(([k, v]) => (
              <p key={k}>
                {k}: {String(v)} ({metric.input_sources?.[k] ?? "—"})
              </p>
            ))}
          <p>{metric.policy_version ?? "Ngưỡng demo – chờ nghiệp vụ xác nhận"}</p>
        </div>
      )}
    </div>
  );
}
