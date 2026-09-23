"use client";

import { useState } from "react";
import { Brain } from "lucide-react";
import { SectionHeader } from "./SectionHeader";

export function AiInsightSection({
  why,
  creditMemo,
  title = "AI Insight",
  onRetry,
}: {
  why: string[];
  creditMemo?: string;
  title?: string;
  onRetry?: () => void;
}) {
  const [showDeepAnalysis, setShowDeepAnalysis] = useState(false);
  return (
    <div data-testid="ai-insight-panel" className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-3">
      <SectionHeader
        icon={Brain}
        title={title}
        right={
          <button
            className="text-xs font-semibold text-msb-navy underline shrink-0"
            onClick={() => setShowDeepAnalysis((v) => !v)}
          >
            {showDeepAnalysis ? "Ẩn phân tích sâu" : "Phân tích sâu"}
          </button>
        }
      />
      {why.length > 0 ? (
        <ul className="text-sm space-y-2 list-disc list-inside">
          {why.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      ) : (
        <div className="text-sm text-gray-500 space-y-2">
          <p>Đang tổng hợp nhận định — bấm Tạo lại nhận định nếu chưa hiện sau vài giây.</p>
          {onRetry && (
            <button onClick={onRetry} className="text-xs font-semibold text-msb-navy underline">
              Tạo lại nhận định
            </button>
          )}
        </div>
      )}
      {showDeepAnalysis && (
        <p className="text-sm text-gray-600 border-t pt-2">
          {creditMemo || "Chỉ có 1 kỳ dữ liệu hoặc chưa đủ dữ liệu — chưa đủ để phân tích xu hướng."}
        </p>
      )}
    </div>
  );
}
