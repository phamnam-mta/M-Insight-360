"use client";

import { useState } from "react";
import { MetricValue } from "../shared/MetricCard";
import { FinancialInputs } from "@/lib/api";

const FIELD_CODES: Record<string, { label: string; code: string; formula: string; group: string }> = {
  net_revenue_vnd: { label: "Doanh thu thuần", code: "IS_REVENUE", formula: "Doanh thu bán hàng − các khoản giảm trừ", group: "Kết quả kinh doanh" },
  pbt_vnd: { label: "Lợi nhuận trước thuế", code: "IS_PBT", formula: "Theo BCTC", group: "Kết quả kinh doanh" },
  pat_vnd: { label: "Lợi nhuận sau thuế", code: "IS_PAT", formula: "Theo BCTC", group: "Kết quả kinh doanh" },
  interest_expense_vnd: { label: "Chi phí lãi vay", code: "IS_INTEREST", formula: "Theo BCTC", group: "Kết quả kinh doanh" },
  depreciation_vnd: { label: "Khấu hao", code: "IS_DEPRECIATION", formula: "Theo BCTC", group: "Kết quả kinh doanh" },
  ebitda: { label: "EBITDA", code: "CALC_EBITDA", formula: "EBIT + Khấu hao", group: "Kết quả kinh doanh" },
  current_assets_vnd: { label: "Tài sản ngắn hạn", code: "BS_CURRENT_ASSETS", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  current_liabilities_vnd: { label: "Nợ ngắn hạn", code: "BS_CURRENT_LIABILITIES", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  non_current_assets_vnd: { label: "Tài sản dài hạn", code: "BS_NON_CURRENT_ASSETS", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  long_term_capital: { label: "Nguồn vốn dài hạn", code: "BS_LONG_TERM_CAPITAL", formula: "VCSH + Nợ dài hạn", group: "Vốn và cơ cấu" },
  total_borrowings: { label: "Tổng nợ vay", code: "BS_TOTAL_BORROWINGS", formula: "Vay ngắn hạn + dài hạn + thuê tài chính", group: "Vốn và cơ cấu" },
  receivables_vnd: { label: "Phải thu khách hàng", code: "BS003", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  inventory_vnd: { label: "Hàng tồn kho", code: "BS004", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  payables_vnd: { label: "Phải trả người bán", code: "BS005", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  equity_vnd: { label: "Vốn chủ sở hữu", code: "BS008", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  cash_vnd: { label: "Tiền và tương đương tiền", code: "BS_CASH", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
};

function formatVndSmart(value: unknown): string {
  if (typeof value !== "number") return "—";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)} tỷ`;
  if (abs >= 1_000_000) return `${Math.round(value / 1_000_000)} triệu`;
  return value.toLocaleString("vi-VN");
}

export function FinancialDataTable({
  creditEngine, financialInputs,
}: { creditEngine?: Record<string, MetricValue>; financialInputs?: FinancialInputs }) {
  const [openRow, setOpenRow] = useState<string | null>(null);
  const groups = ["Kết quả kinh doanh", "Vốn và cơ cấu"];

  function rowValue(key: string): { value: unknown; source?: string } {
    // Raw extracted BCTC fields read straight from financial_inputs — the
    // only reliable source, since not every field is cited in some metric's
    // input_values (e.g. inventory_vnd, payables_vnd, cash_vnd,
    // non_current_assets_vnd never are).
    if (financialInputs && typeof financialInputs[key] === "number") {
      return { value: financialInputs[key], source: "bctc" };
    }
    if (key === "ebitda" || key === "long_term_capital" || key === "total_borrowings") {
      const m = creditEngine?.[key];
      return { value: m?.value, source: "computed" };
    }
    return { value: undefined };
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-4">
      <h3 className="text-sm font-semibold text-msb-navy">Dữ liệu BCTC cốt lõi (VND)</h3>
      {groups.map((group) => (
        <div key={group}>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">{group}</p>
          <table className="w-full text-sm">
            <tbody>
              {Object.entries(FIELD_CODES)
                .filter(([, meta]) => meta.group === group)
                .map(([key, meta]) => {
                  const { value, source } = rowValue(key);
                  const hasValue = typeof value === "number";
                  return (
                    <tr key={key} className="border-b border-gray-50 last:border-0">
                      <td className="py-2 pr-2 align-top">
                        <button
                          className="text-left"
                          title={meta.formula}
                          onClick={() => setOpenRow(openRow === key ? null : key)}
                        >
                          <span className="text-msb-navy">{meta.label}</span>
                          <span className="block text-[10px] text-gray-400">{meta.code}</span>
                        </button>
                        {openRow === key && <p className="text-[11px] text-gray-500 mt-1">{meta.formula}</p>}
                      </td>
                      <td className="py-2 text-right align-top">
                        <span className={hasValue ? "text-msb-navy font-medium" : "text-gray-400"}>
                          {hasValue ? formatVndSmart(value) : "Chưa xác định từ hồ sơ tải lên"}
                        </span>
                        <span className="block text-[10px] text-gray-400">
                          {source === "manual_rm_input" ? "Người dùng điều chỉnh" : hasValue ? "AI trích xuất" : ""}
                        </span>
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
