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
}: {
  label: string;
  unit: string;
  metric: MetricValue;
  note?: string;
}) {
  const [open, setOpen] = useState(false);
  const hasValue = metric.status === "OK" && metric.value !== null;
  return (
    <div className="bg-white rounded-lg border border-gray-100 shadow-sm p-4">
      <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</h3>
      <p className={`text-2xl font-bold mt-1 ${hasValue ? "text-msb-navy" : "text-gray-400"}`}>
        {hasValue ? `${metric.value} ${unit}` : "Chưa có dữ liệu"}
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
