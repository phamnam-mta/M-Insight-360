import { ACTIVATED_STATUS, INSUFFICIENT_DATA_STATUS, RiskFlag } from "./api";

// RF04 (Digisale/DSP-vs-BCTC reconciliation) is a data-quality signal, not
// a credit signal, even when its status is ACTIVATED_STATUS — it never
// belongs in Nhóm A (M6) despite firing like one.
const DATA_WARNING_RULE_IDS_EVEN_WHEN_ACTIVATED = new Set(["RF04"]);

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
const REQUIRED_FIELD_NAMES = [
  "net_revenue_vnd", "pbt_vnd", "pat_vnd", "interest_expense_vnd",
  "depreciation_vnd", "current_assets_vnd", "current_liabilities_vnd",
  "equity_vnd", "receivables_vnd",
];

export function computeCoverage(financialInputs?: Record<string, number>): number {
  if (!financialInputs) return 0;
  const present = REQUIRED_FIELD_NAMES.filter((f) => typeof financialInputs[f] === "number").length;
  return Math.round((present / REQUIRED_FIELD_NAMES.length) * 100);
}
