"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import { MetricValue } from "../shared/MetricCard";

export function Qd039Card({ creditEngine }: { creditEngine?: Record<string, MetricValue> }) {
  const [ltv, setLtv] = useState<"80" | "85">("80");
  const metric = creditEngine?.[`receivables_financing_limit_${ltv}`];
  const hasValue = metric?.status === "OK" && metric.value !== null;

  return (
    <div className="bg-white rounded-xl border-2 border-msb-orange/30 p-5 space-y-3">
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-msb-orange" />
        <h3 className="text-sm font-semibold text-msb-navy">Tài trợ Chuỗi QĐ 039</h3>
      </div>
      <div className="flex gap-2">
        {(["80", "85"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setLtv(v)}
            className={`text-xs font-semibold px-3 py-1.5 rounded-full ${
              ltv === v ? "bg-msb-orange text-white" : "bg-gray-100 text-gray-600"
            }`}
          >
            LTV {v}%
          </button>
        ))}
      </div>
      <p className={`text-2xl font-bold ${hasValue ? "text-msb-navy" : "text-gray-400"}`}>
        {hasValue ? `${(Number(metric!.value) / 1_000_000_000).toFixed(2)} tỷ` : "Chưa xác định từ hồ sơ tải lên"}
      </p>
      {hasValue && (
        <p className="text-xs text-gray-500">
          Khoản phải thu khách hàng có thể mở ra hạn mức tài trợ tham chiếu {(Number(metric!.value) / 1_000_000_000).toFixed(2)} tỷ.
        </p>
      )}
      {ltv === "85" && metric?.policy_version && (
        <p className="text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2">{metric.policy_version}</p>
      )}
      <p className="text-xs text-gray-400">
        Cần thẩm định điều kiện tài sản bảo đảm, bên mua và hồ sơ theo QĐ 039.
      </p>
      <p className="text-[11px] text-gray-400 border-t border-gray-100 pt-2">
        Khuyến nghị sơ bộ từ dữ liệu BCTC — cần phê duyệt theo quy trình tín dụng MSB.
      </p>
    </div>
  );
}
