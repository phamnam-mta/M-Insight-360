"use client";

import { useEffect, useState } from "react";
import { RbHistoryVersion, getHistory } from "@/lib/rb-portal-api";

const KIND_LABEL: Record<string, string> = { PRELIMINARY: "Thẩm định sơ bộ", FULL: "Thẩm định đầy đủ" };

export function HistoryTab({ caseId }: { caseId: string }) {
  const [versions, setVersions] = useState<RbHistoryVersion[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHistory(caseId).then(setVersions).catch((err) => setError(err instanceof Error ? err.message : "Không tải được"));
  }, [caseId]);

  if (error) return <p className="text-sm text-red-600">{error}</p>;

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
      <h3 className="text-sm font-semibold text-msb-navy">Lịch sử thẩm định</h3>
      {versions.length === 0 ? (
        <p className="text-sm text-gray-500">Chưa có lần thẩm định nào.</p>
      ) : (
        <ul className="divide-y">
          {versions.map((v) => (
            <li key={v.version} className="py-2.5">
              <p className="text-sm font-medium text-msb-navy">
                Phiên bản {v.version} — {KIND_LABEL[v.kind] ?? v.kind}
              </p>
              <p className="text-xs text-gray-500">
                {new Date(v.created_at).toLocaleString("vi-VN")} · {v.computed.credit_readiness}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
