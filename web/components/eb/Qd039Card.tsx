"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import { MetricValue } from "../shared/MetricCard";

function formatVnd(v: number): string {
  return Math.round(v).toLocaleString("vi-VN");
}

export function Qd039Card({
  creditEngine, receivablesVnd,
}: { creditEngine?: Record<string, MetricValue>; receivablesVnd?: number | null }) {
  const [ltv, setLtv] = useState<"80" | "85">("80");
  const metric = creditEngine?.[`receivables_financing_limit_${ltv}`];
  const hasValue = metric?.status === "OK" && metric.value !== null;
  const hasReceivables = typeof receivablesVnd === "number";

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-msb-orange" />
          <h3 className="text-sm font-semibold text-msb-navy">Tài trợ chuỗi — QĐ.EB.039 (chỉ tiêu thẩm định)</h3>
        </div>
        <div className="flex gap-1.5">
          {(["80", "85"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setLtv(v)}
              className={`text-[11px] font-semibold px-2.5 py-1 rounded-full ${
                ltv === v ? "bg-msb-orange text-white" : "bg-gray-100 text-gray-600"
              }`}
            >
              LTV {v}%
            </button>
          ))}
        </div>
      </div>
      <table className="w-full text-[13.5px]">
        <thead>
          <tr className="text-left border-b border-gray-100">
            <th className="py-1.5 pr-2 font-medium text-[11.5px] uppercase text-gray-400">Chỉ tiêu</th>
            <th className="py-1.5 font-medium text-[11.5px] uppercase text-gray-400">Giá trị</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-b border-gray-50">
            <td className="py-2 pr-2 text-[#42506a]">Số dư phải thu khách hàng cuối kỳ</td>
            <td className="py-2 font-bold text-msb-navy">
              {hasReceivables ? formatVnd(receivablesVnd as number) : "Chưa xác định từ hồ sơ tải lên"}
            </td>
          </tr>
          <tr className="border-b border-gray-50">
            <td className="py-2 pr-2 text-[#42506a]">Tỷ lệ ứng trước áp dụng</td>
            <td className="py-2 text-msb-navy">{ltv}% — Giá trị tham chiếu từ BCTC</td>
          </tr>
          <tr>
            <td className="py-2 pr-2 text-[#42506a]">Hạn mức tham chiếu</td>
            <td className="py-2 font-bold text-msb-navy">
              {hasValue ? formatVnd(Number(metric!.value)) : "Chưa xác định từ hồ sơ tải lên"}
            </td>
          </tr>
        </tbody>
      </table>
      {ltv === "85" && metric?.policy_version && (
        <p className="text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2">{metric.policy_version}</p>
      )}
      <p className="text-xs text-gray-400">
        Hạn mức tính trên số dư phải thu cuối kỳ. Cần thẩm định bên mua, hồ sơ và điều kiện tài sản bảo đảm theo QĐ 039.
      </p>
    </div>
  );
}
