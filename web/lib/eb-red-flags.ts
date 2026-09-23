import { ACTIVATED_STATUS, INSUFFICIENT_DATA_STATUS, RiskFlag } from "./api";

// RF04 (Digisale/DSP-vs-BCTC reconciliation) and LOW_OCR_CONFIDENCE
// (extraction-quality warning, not a credit signal) are data-quality
// signals, not credit signals, even when their status is
// ACTIVATED_STATUS — neither belongs in Nhóm A (M6) despite firing like
// one. Must stay in sync with the backend's NHOM_A_CANONICAL_RULE_IDS
// (app/agents/eb/export_gate.py), which already excludes both.
const DATA_WARNING_RULE_IDS_EVEN_WHEN_ACTIVATED = new Set(["RF04", "LOW_OCR_CONFIDENCE"]);

export function splitRiskFlags(flags: RiskFlag[]): { nhomA: RiskFlag[]; nhomB: RiskFlag[] } {
  const nhomA: RiskFlag[] = [];
  const nhomB: RiskFlag[] = [];
  for (const f of flags) {
    const isDataWarningOverride = f.rule_id !== undefined && DATA_WARNING_RULE_IDS_EVEN_WHEN_ACTIVATED.has(f.rule_id);
    if (f.status === INSUFFICIENT_DATA_STATUS || (isDataWarningOverride && f.status === ACTIVATED_STATUS)) {
      nhomB.push(f);
    } else if (f.status === ACTIVATED_STATUS) {
      nhomA.push(f);
    }
  }
  return { nhomA, nhomB };
}

// Mirrors the instruction's ★ (required) fields from BẢNG MAP TRƯỜNG CHUẨN.
export const REQUIRED_FIELD_LABELS: Record<string, string> = {
  net_revenue_vnd: "Doanh thu thuần",
  pbt_vnd: "Lợi nhuận trước thuế",
  pat_vnd: "Lợi nhuận sau thuế",
  interest_expense_vnd: "Chi phí lãi vay",
  depreciation_vnd: "Khấu hao",
  current_assets_vnd: "Tài sản ngắn hạn",
  current_liabilities_vnd: "Nợ ngắn hạn",
  equity_vnd: "Vốn chủ sở hữu",
  receivables_vnd: "Phải thu khách hàng",
};
const REQUIRED_FIELD_NAMES = Object.keys(REQUIRED_FIELD_LABELS);

export function computeCoverage(financialInputs?: Record<string, number>): number {
  if (!financialInputs) return 0;
  const present = REQUIRED_FIELD_NAMES.filter((f) => typeof financialInputs[f] === "number").length;
  return Math.round((present / REQUIRED_FIELD_NAMES.length) * 100);
}

// The BCTC-required fields a hồ sơ still hasn't produced a value for —
// drives R2's "Trường BCTC chưa đọc được" checklist.
export function missingRequiredFieldLabels(financialInputs?: Record<string, number>): string[] {
  return REQUIRED_FIELD_NAMES.filter((f) => typeof financialInputs?.[f] !== "number").map((f) => REQUIRED_FIELD_LABELS[f]);
}
