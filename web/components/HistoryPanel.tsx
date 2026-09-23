"use client";

import { useEffect, useState } from "react";
import { History, Loader2 } from "lucide-react";
import { AssessmentResult, HistoryItem, HistoryRunStatus, fetchHistory, loadHistoryItemsLocally } from "@/lib/api";

type Props = {
  agentType: "rb" | "eb" | "crosssell";
  onSelect: (result: AssessmentResult) => void;
  refreshKey?: number;
  onLoaded?: (items: HistoryItem[]) => void;
};

// The badge shows whether the assessment RUN itself succeeded — not the
// credit decision it produced (that lives inside the result panel's own
// banner). A row with no run_status is a legacy entry written before this
// tracking existed; it only ever got written on success, so it reads as one.
const RUN_STATUS_LABEL: Record<HistoryRunStatus, string> = {
  processing: "Đang xử lý",
  success: "Thành công",
  failed: "Thất bại",
};

const RUN_STATUS_STYLE: Record<HistoryRunStatus, string> = {
  processing: "bg-amber-100 text-amber-700",
  success: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

function statusOf(item: HistoryItem): { status: HistoryRunStatus; label: string; style: string } {
  const status = item.run_status ?? "success";
  return { status, label: RUN_STATUS_LABEL[status], style: RUN_STATUS_STYLE[status] };
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("vi-VN");
  } catch {
    return iso;
  }
}

function mergeHistoryItems(local: HistoryItem[], remote: HistoryItem[]): HistoryItem[] {
  const seen = new Set<string>();
  const combined: HistoryItem[] = [];
  for (const item of [...local, ...remote]) {
    const key = item.result?.case_id ?? item.result?.ma_lo ?? `${item.agent_type}-${item.id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    combined.push(item);
  }
  combined.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  return combined.slice(0, 5);
}

export default function HistoryPanel({ agentType, onSelect, refreshKey, onLoaded }: Props) {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    onLoaded?.(items);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items]);

  useEffect(() => {
    let cancelled = false;
    // localStorage survives a page refresh even if the backend's SQLite
    // file was wiped by a container restart — show it immediately, before
    // the (possibly empty) backend response arrives.
    const local = loadHistoryItemsLocally(agentType);
    setItems(mergeHistoryItems(local, []));
    setLoading(true);
    setError(null);
    fetchHistory(agentType, 5)
      .then((remote) => {
        if (!cancelled) setItems(mergeHistoryItems(local, remote));
      })
      .catch((err) => {
        // Backend history unavailable — local items (if any) are still shown.
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
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mt-6">
      <div className="flex items-center gap-2.5 mb-3">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-msb-navy/5 text-msb-navy shrink-0">
          <History className="h-4 w-4" />
        </span>
        <h2 className="text-lg font-semibold text-msb-navy">Lịch sử thẩm định gần nhất</h2>
      </div>
      {loading && items.length === 0 && <p className="text-sm text-gray-500">Đang tải...</p>}
      {error && items.length === 0 && <p className="text-sm text-red-600">{error}</p>}
      {!loading && !error && items.length === 0 && (
        <p className="text-sm text-gray-500">Chưa có hồ sơ nào được thẩm định.</p>
      )}
      {items.length > 0 && (
        <ul className="divide-y">
          {items.map((item) => {
            const { status, label, style } = statusOf(item);
            const clickable = status === "success";
            const body = (
              <>
                <p className="text-sm font-medium text-msb-navy">{item.customer_name}</p>
                <p className="text-xs text-gray-500">
                  MST {item.tax_id} · {formatDate(item.created_at)}
                </p>
                {status === "failed" && item.error_message && (
                  <p className="text-xs text-red-600 mt-0.5 break-words">{item.error_message}</p>
                )}
              </>
            );
            return (
              <li key={item.id} className="py-2 flex items-center justify-between gap-3">
                {clickable ? (
                  <button
                    onClick={() => onSelect(item.result)}
                    className="text-left flex-1 min-w-0 hover:bg-msb-bg rounded-lg px-2 py-1 -mx-2 transition-colors"
                  >
                    {body}
                  </button>
                ) : (
                  <div className="text-left flex-1 min-w-0 px-2 py-1 -mx-2">{body}</div>
                )}
                <span
                  className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full shrink-0 ${style}`}
                >
                  {status === "processing" && <Loader2 className="h-3 w-3 animate-spin" />}
                  {label}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
