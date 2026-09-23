"use client";

import { useState } from "react";
import { MetricValue } from "../shared/MetricCard";
import { FinancialInputs, SanityCheck } from "@/lib/api";

const FIELD_CODES: Record<string, { label: string; code: string; formula: string; group: string }> = {
  net_revenue_vnd: { label: "Doanh thu thuần", code: "IS_REVENUE", formula: "Doanh thu bán hàng − các khoản giảm trừ", group: "Kết quả kinh doanh" },
  cogs_vnd: { label: "Giá vốn hàng bán", code: "IS_COGS", formula: "Theo BCTC", group: "Kết quả kinh doanh" },
  pbt_vnd: { label: "Lợi nhuận trước thuế", code: "IS_PBT", formula: "Theo BCTC", group: "Kết quả kinh doanh" },
  pat_vnd: { label: "Lợi nhuận sau thuế", code: "IS_PAT", formula: "Theo BCTC", group: "Kết quả kinh doanh" },
  interest_expense_vnd: { label: "Chi phí lãi vay", code: "IS_INTEREST", formula: "Theo BCTC", group: "Kết quả kinh doanh" },
  depreciation_vnd: { label: "Khấu hao", code: "IS_DEPRECIATION", formula: "Theo BCTC", group: "Kết quả kinh doanh" },
  ebitda: { label: "EBITDA", code: "CALC_EBITDA", formula: "EBIT + Khấu hao", group: "Kết quả kinh doanh" },
  current_assets_vnd: { label: "Tài sản ngắn hạn", code: "BS_CURRENT_ASSETS", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  current_liabilities_vnd: { label: "Nợ ngắn hạn", code: "BS_CURRENT_LIABILITIES", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  non_current_assets_vnd: { label: "Tài sản dài hạn", code: "BS_NON_CURRENT_ASSETS", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  charter_capital_vnd: { label: "Vốn điều lệ", code: "BS_CHARTER_CAPITAL", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  long_term_capital: { label: "Nguồn vốn dài hạn", code: "BS_LONG_TERM_CAPITAL", formula: "VCSH + Nợ dài hạn", group: "Vốn và cơ cấu" },
  total_borrowings: { label: "Tổng nợ vay", code: "BS_TOTAL_BORROWINGS", formula: "Vay ngắn hạn + dài hạn + thuê tài chính", group: "Vốn và cơ cấu" },
  receivables_vnd: { label: "Phải thu khách hàng", code: "BS_AR_CUSTOMER", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  inventory_vnd: { label: "Hàng tồn kho", code: "BS_INVENTORY", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  payables_vnd: { label: "Phải trả người bán", code: "BS_AP_SUPPLIER", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  equity_vnd: { label: "Vốn chủ sở hữu", code: "BS_EQUITY", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  cash_vnd: { label: "Tiền và tương đương tiền", code: "BS_CASH", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  nwc: { label: "Vốn lưu động ròng", code: "CALC_NWC", formula: "TSNH − Nợ NH", group: "Chỉ số tín dụng" },
  current_ratio: { label: "Khả năng thanh toán hiện hành", code: "CALC_CURRENT_RATIO", formula: "TSNH / Nợ NH", group: "Chỉ số tín dụng" },
  dscr: { label: "DSCR", code: "CALC_DSCR", formula: "(LNST + Khấu hao + Lãi vay) / (Nợ gốc + Lãi vay đến hạn)", group: "Chỉ số tín dụng" },
  icr: { label: "ICR", code: "CALC_ICR", formula: "EBIT / Chi phí lãi vay", group: "Chỉ số tín dụng" },
};

function formatVndSmart(value: unknown): string {
  if (typeof value !== "number") return "—";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)} tỷ`;
  if (abs >= 1_000_000) return `${Math.round(value / 1_000_000)} triệu`;
  return value.toLocaleString("vi-VN");
}

export function FinancialDataTable({
  creditEngine, financialInputs, sanityCheck,
}: { creditEngine?: Record<string, MetricValue>; financialInputs?: FinancialInputs; sanityCheck?: SanityCheck }) {
  const [openRow, setOpenRow] = useState<string | null>(null);
  const groups = ["Kết quả kinh doanh", "Vốn và cơ cấu", "Chỉ số tín dụng"];

  function rowValue(key: string): { value: unknown; source?: string; suspectReason?: string } {
    const suspectReason = sanityCheck?.suspect_fields[key];
    if (suspectReason) {
      return { value: undefined, suspectReason };
    }
    // Raw extracted BCTC fields read straight from financial_inputs — the
    // only reliable source, since not every field is cited in some metric's
    // input_values (e.g. inventory_vnd, payables_vnd, cash_vnd,
    // non_current_assets_vnd never are).
    if (financialInputs && typeof financialInputs[key] === "number") {
      return { value: financialInputs[key], source: "bctc" };
    }
    if (["ebitda", "long_term_capital", "total_borrowings", "nwc", "current_ratio", "dscr", "icr"].includes(key)) {
      const m = creditEngine?.[key];
      return { value: m?.status === "OK" ? m.value : undefined, source: "computed" };
    }
    return { value: undefined };
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
      <SectionHeaderInline title="Dữ liệu đã trích xuất · truy vết" />
      {groups.map((group) => (
        <div key={group} className="space-y-0.5">
          <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wide pt-1">{group}</p>
          {Object.entries(FIELD_CODES)
            .filter(([, meta]) => meta.group === group)
            .map(([key, meta]) => {
              const { value, source, suspectReason } = rowValue(key);
              const hasValue = typeof value === "number";
              return (
                <button
                  key={key}
                  className="block w-full text-left"
                  onClick={() => setOpenRow(openRow === key ? null : key)}
                >
                  <div className="flex justify-between gap-3 text-[13.5px] py-1.5">
                    <span className="text-gray-500">{meta.label}</span>
                    <span className={hasValue ? "font-semibold text-msb-navy text-right" : "font-semibold text-[#8b97a8] text-right text-[12px]"}>
                      {hasValue ? formatVndSmart(value) : suspectReason ? "Nghi ngờ sai dòng" : "Chưa xác định từ hồ sơ tải lên"}
                    </span>
                  </div>
                  <div className="text-[10.5px] text-gray-400 border-b border-dashed border-gray-100 pb-1.5 -mt-0.5 text-right">
                    {suspectReason ??
                      (source === "manual_rm_input" ? "Người dùng điều chỉnh" : hasValue ? meta.code : "chưa đọc được từ hồ sơ")}
                  </div>
                  {openRow === key && <p className="text-[11px] text-gray-500 pt-1 text-right">{meta.formula}</p>}
                </button>
              );
            })}
        </div>
      ))}
    </div>
  );
}

function SectionHeaderInline({ title }: { title: string }) {
  return <h3 className="text-sm font-semibold text-msb-navy">{title}</h3>;
}
