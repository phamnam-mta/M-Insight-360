"use client";

import { AlertTriangle } from "lucide-react";
import { ExportGateInfo } from "@/lib/api";

export function ExportGateScreen({
  gate, onClose, onForceExport, exporting,
}: {
  gate: ExportGateInfo;
  onClose: () => void;
  onForceExport: () => void;
  exporting: boolean;
}) {
  const canOverride = gate.block_type === "SOFT";
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-lg w-full p-6 space-y-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0" />
          <h2 className="text-base font-semibold text-msb-navy">
            Chưa xuất tờ trình tự động — số liệu BCTC cho thấy {gate.signal_count} tín hiệu cần thẩm định thêm.
          </h2>
        </div>
        <ul className="text-sm space-y-1.5">
          {gate.signals.map((s, i) => (
            <li key={i} className="text-red-700">
              {s.rule_name ?? s.rule_id}
              {s.observed_value !== undefined && s.observed_value !== null ? `: ${s.observed_value}` : ""}
            </li>
          ))}
          {gate.reasons.map((r, i) => (
            <li key={`r-${i}`} className="text-red-700">{r}</li>
          ))}
        </ul>
        <div>
          <p className="text-sm font-medium text-msb-navy">Việc cần làm trước khi trình:</p>
          <ul className="text-sm text-gray-600 list-disc list-inside">
            <li>Lấy lịch trả nợ chi tiết</li>
            <li>Bảng tuổi nợ phải thu</li>
            <li>Xác minh cơ cấu kỳ hạn nợ</li>
            <li>Bổ sung nguồn trả nợ / tài sản đảm bảo</li>
          </ul>
        </div>
        <p className="text-[11px] text-gray-400 border-t pt-3">
          Khuyến nghị sơ bộ từ dữ liệu BCTC — cần phê duyệt theo quy trình tín dụng MSB.
        </p>
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="text-xs font-semibold px-3 py-2 rounded-lg border border-gray-200 text-gray-600">
            Xem chi tiết tín hiệu rủi ro
          </button>
          {canOverride && (
            <button
              onClick={onForceExport}
              disabled={exporting}
              className="text-xs font-semibold px-3 py-2 rounded-lg bg-msb-orange text-white disabled:opacity-50"
            >
              {exporting ? "Đang xuất..." : "Vẫn xuất bản nháp để trao đổi nội bộ"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
