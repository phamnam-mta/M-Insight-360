"use client";

import { useEffect, useState } from "react";
import { AssessmentResult, HistoryItem, fetchHistory } from "@/lib/api";

type Props = {
  agentType: "rb" | "eb" | "crosssell";
  onSelect: (result: AssessmentResult) => void;
  refreshKey?: number;
};

const STATUS_LABEL: Record<string, string> = {
  READY: "Sẵn sàng",
  READY_WITH_CONDITIONS: "Sẵn sàng có điều kiện",
  MANUAL_REVIEW_REQUIRED: "Cần thẩm định thủ công",
  NOT_READY: "Thiếu hồ sơ",
  OK: "OK",
  WARN: "Cảnh báo",
  BLOCK: "Chặn",
};

function statusOf(item: HistoryItem): string {
  const readiness = item.result?.credit_readiness;
  const verdict = item.result?.precheck?.verdict;
  const raw = readiness ?? verdict;
  if (!raw) return "—";
  return STATUS_LABEL[raw] ?? raw;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("vi-VN");
  } catch {
    return iso;
  }
}

export default function HistoryPanel({ agentType, onSelect, refreshKey }: Props) {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchHistory(agentType, 5)
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Lỗi không xác định");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [agentType, refreshKey]);

  return (
    <div className="bg-white rounded-lg shadow p-6 mt-6">
      <h2 className="text-lg font-semibold text-msb-navy mb-3">Lịch sử thẩm định gần nhất</h2>
      {loading && <p className="text-sm text-gray-500">Đang tải...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!loading && !error && items.length === 0 && (
        <p className="text-sm text-gray-500">Chưa có hồ sơ nào được thẩm định.</p>
      )}
      {items.length > 0 && (
        <ul className="divide-y">
          {items.map((item) => (
            <li key={item.id} className="py-2 flex items-center justify-between gap-3">
              <button
                onClick={() => onSelect(item.result)}
                className="text-left flex-1 hover:bg-msb-bg rounded px-2 py-1 -mx-2 transition-colors"
              >
                <p className="text-sm font-medium text-msb-navy">{item.customer_name}</p>
                <p className="text-xs text-gray-500">
                  MST {item.tax_id} · {formatDate(item.created_at)}
                </p>
              </button>
              <span className="text-xs font-semibold px-2 py-1 rounded bg-msb-bg text-msb-navy shrink-0">
                {statusOf(item)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
