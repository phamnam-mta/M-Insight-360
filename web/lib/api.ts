// A rule/flag as the three agents' routers serialize it. `status` is the
// Vietnamese activation state: only ACTIVATED_STATUS means the rule actually
// fired — EB emits all five of its red flags on every assessment, activated
// or not.
export const ACTIVATED_STATUS = "KÍCH HOẠT";
export const INSUFFICIENT_DATA_STATUS = "CHƯA ĐÁNH GIÁ";

export type EvidenceRef = {
  file_id: string;
  filename: string;
  location: string;
  original_text: string;
  period?: string | null;
};

export type EvidencedField = {
  field_id: string;
  label: string;
  value: number | string | null;
  unit?: string | null;
  period?: string | null;
  status: "VERIFIED" | "COMPUTED" | "PENDING_REVIEW" | "MISSING_DATA" | "NOT_APPLICABLE";
  evidence: EvidenceRef[];
  formula?: string | null;
  input_fields?: string[];
  policy_version?: string | null;
  last_verified_at?: string | null;
};

export type ConditionRow = {
  condition_id: string;
  condition_name: string;
  observed: EvidencedField;
  compare_rule: string;
  result: "PASS" | "FAIL" | "INSUFFICIENT_DATA" | "PENDING_INTERNAL_CHECK" | "NOT_APPLICABLE";
  reason_if_incomplete?: string | null;
};

export type OverviewSummary = {
  checked: number;
  total: number;
  passed: number;
  failed: number;
  pending: number;
};

export type DocumentStatus = {
  filename: string;
  doc_type?: string;
  status: "KHÔNG_ĐỌC_ĐƯỢC" | "ĐÃ_TRÍCH_XUẤT" | "CHỜ_XÁC_MINH" | "ĐÃ_TẢI_LÊN";
  cited_field_count: number;
  warnings: string[];
};

export type OpportunityCard = {
  product_suggestion: string;
  basis_documents: string[];
  estimated_value: number | null;
  formula_note?: string;
  unverified_conditions?: string | null;
  priority: string;
  reviewer: string;
  recommended_action?: string;
  status: string;
};

export type RiskFlag = {
  rule_id?: string;
  rule_name?: string;
  status?: string;
  severity?: string;
  evidence?: string[];
  evidence_refs?: Record<string, EvidenceRef[]>;
  impact?: string;
  recommended_action?: string;
  observed_value?: number | string | null;
};

// Cross-sell v3.1 — POST /api/crosssell/assess returns a JSON shape driven
// entirely by AGENT_CrossSell_INSTRUCTION_FINAL.md §C, structurally unlike
// RB/EB's response (no credit_readiness/recommendation/risk_flags).
export type CrossSellBadge = { loai: "ok" | "warn" | "err" | "info" | "na"; nhan: string; tro_toi?: string };
export type CrossSellKpi = { nhan: string; gia_tri: string; phu?: string; nhan_manh?: boolean };
export type CrossSellDetailBlock = { tieu_de: string; noi_dung: string };
export type CrossSellScenario = { loai: "A" | "B"; doi_tuong: string; noi_dung: string };
export type CrossSellOpportunity = {
  rule_id: string;
  san_pham: string;
  segment: string;
  deal_size: number | null;
  deal_size_headline: string;
  deal_size_exact: string | null;
  priority: "P1" | "P2" | "P3" | "P-NA";
  confidence: string | null;
  ly_do_confidence: string | null;
  signal_1dong: string;
  chi_tiet: CrossSellDetailBlock[];
  canh_bao: string[];
  kich_ban: CrossSellScenario[];
};
export type CrossSellPartnerRow = {
  ten: string;
  chieu: string;
  so_gd: number;
  tong_gt: number;
  diem: number;
  trang_thai: string;
  co_canh_bao: boolean;
  nhan_canh_bao: string | null;
  sp_de_xuat: string;
};
export type CrossSellEvidenceBlock = { tieu_de: string; tom_tat: string; noi_dung: Record<string, unknown> };

export type HoSoPeriod = {
  selected: string | null;
  available: string[];
  requested?: string;
  fallback_notice?: string;
};

// Raw extracted BCTC field values (EbFinancialInputs, non-null only), keyed
// by real field name — independent of which credit_engine metric happens to
// cite a given field in its own input_values.
export type FinancialInputs = Record<string, number>;

export type CapitalBalanceCheck = {
  trai: number | null;
  phai: number | null;
  trang_thai: string;
  nhan_xet: string;
};

export type StressTestMetric = { value: number | null; status: string };

export type StressTestV2Result = {
  assumptions: { human_readable: string; deltas: Record<string, number>; comprehensive_mode: boolean };
  before: Record<string, unknown> & {
    revenue: number | null;
    ebit: number | null;
    interest_expense: number | null;
    nwc: StressTestMetric;
    dscr: StressTestMetric;
    icr: StressTestMetric;
    debt_service_label: string;
    principal_due: number | null;
    debt_service_total: number | null;
  };
  after: StressTestV2Result["before"];
  nwc_impact_quantifiable: boolean;
  buffers: { dscr_buffer?: number; icr_buffer?: number };
  conclusions: string[];
  recommended_actions: string[];
  disclaimer: string;
};

export type StressScenario = {
  id: number;
  case_id: string;
  name: string;
  created_by: string;
  created_at: string;
  report_period: string | null;
  request: Record<string, unknown>;
  response: StressTestV2Result;
};

export async function runStressTestV2(
  inputs: Record<string, number | null>,
  deltas: Record<string, number>,
  comprehensiveMode: boolean
): Promise<StressTestV2Result> {
  const resp = await fetch("/api/eb/stress-test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inputs, deltas, comprehensive_mode: comprehensiveMode }),
  });
  if (!resp.ok) throw new Error(`Stress test thất bại: HTTP ${resp.status}`);
  return resp.json();
}

export async function saveStressScenario(
  caseId: string,
  name: string,
  createdBy: string,
  reportPeriod: string | null,
  request: Record<string, unknown>,
  response: StressTestV2Result
): Promise<{ id: number }> {
  const resp = await fetch("/api/eb/stress-test/scenarios", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case_id: caseId, name, created_by: createdBy, report_period: reportPeriod, request, response }),
  });
  if (!resp.ok) throw new Error(`Lưu kịch bản thất bại: HTTP ${resp.status}`);
  return resp.json();
}

export async function fetchStressScenarios(caseId: string): Promise<StressScenario[]> {
  const resp = await fetch(`/api/eb/stress-test/scenarios?case_id=${encodeURIComponent(caseId)}`);
  if (!resp.ok) throw new Error(`Không tải được danh sách kịch bản: HTTP ${resp.status}`);
  const body = await resp.json();
  return body.scenarios ?? [];
}

export type ExportGateInfo = {
  verdict: "XUAT" | "XUAT_KEM_CANH_BAO" | "KHONG_XUAT_TU_DONG";
  block_type: "HARD" | "SOFT" | null;
  signal_count: number;
  signals: RiskFlag[];
  data_warnings: RiskFlag[];
  reasons: string[];
};

export type SanityCheck = {
  suspect_fields: Record<string, string>;
  balance_mismatch: boolean;
  balance_mismatch_detail: string | null;
};

export type ExportResult =
  | { blocked: true; gate: ExportGateInfo }
  | { blocked: false; blob: Blob; filename: string };

export type AssessmentResult = {
  case_id?: string;
  assessed_at?: string;
  customer_profile?: Record<string, unknown>;
  credit_engine?: Record<string, unknown>;
  risk_flags?: RiskFlag[];
  missing_data?: string[];
  credit_readiness?: string;
  recommendation?: string;
  overview?: ConditionRow[];
  overview_summary?: OverviewSummary;
  overall_conclusion?: string | null;
  documents?: DocumentStatus[];
  crosssell_opportunities?: OpportunityCard[];
  why?: string[];
  credit_memo?: string;
  export_available?: boolean;
  extraction_warnings?: string[];
  // EB v2 screen redesign fields.
  ho_so_period?: HoSoPeriod;
  capital_balance_check?: CapitalBalanceCheck;
  financial_inputs?: FinancialInputs;
  export_gate?: ExportGateInfo;
  sanity_check?: SanityCheck;
  // Cross-sell v3.1 fields — see comment above.
  status?: "ok" | "partial" | "blocked" | "error";
  request_id?: string;
  ma_lo?: string;
  ho_so?: {
    ten_kh: string;
    mst: string;
    ky_sao_ke: string;
    so_gd: number;
    so_ngan_hang: number;
    nganh_suy_doan: string;
  };
  badges?: CrossSellBadge[];
  kpi?: CrossSellKpi[];
  co_hoi?: CrossSellOpportunity[];
  doi_tac?: {
    canh_bao_cif: string;
    danh_sach: CrossSellPartnerRow[];
    ghi_chu_mo_rong: { tieu_de: string; noi_dung: string } | null;
  };
  evidence?: Record<string, CrossSellEvidenceBlock>;
  ban_giao?: { noi_dung_mail: string; bang_tracking: unknown[]; ghi_chu_plumbing: string };
  warnings?: string[];
  error_code?: string | null;
};

export async function exportMb02(result: AssessmentResult, force = false): Promise<ExportResult> {
  const resp = await fetch("/api/eb/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ computed: result, force }),
  });
  const contentType = resp.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    const body = await resp.json();
    if (body.export_blocked) {
      return {
        blocked: true,
        gate: {
          verdict: body.verdict, block_type: body.block_type, signal_count: body.signal_count,
          signals: body.signals ?? [], data_warnings: [], reasons: body.reasons ?? [],
        },
      };
    }
    throw new Error("Xuất tờ trình thất bại: phản hồi không hợp lệ.");
  }
  if (!resp.ok) throw new Error(`Xuất tờ trình thất bại: HTTP ${resp.status}`);
  const blob = await resp.blob();
  const disposition = resp.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/);
  const filename = match ? match[1] : "to-trinh-mb02-du-thao_BANNHAP.docx";
  return { blocked: false, blob, filename };
}

export async function runAssessment(
  agentType: "rb" | "eb" | "crosssell",
  customerName: string,
  taxId: string,
  files: File[],
  extraFields?: Record<string, string>
): Promise<AssessmentResult> {
  const form = new FormData();
  form.append("customer_name", customerName);
  form.append("tax_id", taxId);
  for (const f of files) form.append("files", f);
  if (extraFields) {
    for (const [key, value] of Object.entries(extraFields)) {
      if (value.trim() !== "") form.append(key, value);
    }
  }

  const resp = await fetch(`/api/${agentType}/assess`, {
    method: "POST",
    body: form,
  });
  if (!resp.ok) {
    throw new Error(`Thẩm định thất bại: HTTP ${resp.status}`);
  }
  return resp.json();
}

export function evidenceFileUrl(caseId: string, fileId: string): string {
  return `/api/eb/files/${encodeURIComponent(caseId)}/${encodeURIComponent(fileId)}`;
}


// The run's own execution status — did the API call succeed, fail, or is it
// still in flight — distinct from credit_readiness (a decision ABOUT a
// completed assessment). A "processing" row exists only for the lifetime of
// its own in-flight request; "failed" rows are never surfaced today except
// through this history list, since a failed call previously vanished with
// nothing recorded.
export type HistoryRunStatus = "processing" | "success" | "failed";

export type HistoryItem = {
  id: number;
  agent_type: string;
  customer_name: string;
  tax_id: string;
  result: AssessmentResult;
  created_at: string;
  run_status?: HistoryRunStatus;
  error_message?: string;
};

export async function fetchHistory(
  agentType: "rb" | "eb" | "crosssell",
  limit = 5
): Promise<HistoryItem[]> {
  const resp = await fetch(`/api/history?agent_type=${agentType}&limit=${limit}`);
  if (!resp.ok) throw new Error(`Không tải được lịch sử thẩm định: HTTP ${resp.status}`);
  const body = await resp.json();
  return body.items ?? [];
}

// The backend keeps assessment history in a local SQLite file inside the
// runtime container — GreenNode AgentBase Runtime has no persistent-volume
// flag for this (confirmed against runtime.sh), so a container restart or
// cold start after idle wipes it and the server-side history goes empty on
// the next page load. Mirroring every completed assessment into this
// browser's localStorage gives history that survives an F5 regardless of
// backend container lifecycle; HistoryPanel merges both sources.
const LOCAL_HISTORY_KEY_PREFIX = "msb_assessment_history_";
const LOCAL_HISTORY_MAX_ITEMS = 20;

function localHistoryKey(agentType: "rb" | "eb" | "crosssell"): string {
  return `${LOCAL_HISTORY_KEY_PREFIX}${agentType}`;
}

// Records a run the moment it starts, as "processing" — so a request that
// later fails still leaves a trace, instead of silently vanishing the way a
// failed assessment previously did. Returns the entry's id (-1 if storage is
// unavailable) for the caller to pass back into finishHistoryPlaceholder.
export function startHistoryPlaceholder(
  agentType: "rb" | "eb" | "crosssell",
  customerName: string,
  taxId: string
): number {
  try {
    const id = Date.now();
    const item: HistoryItem = {
      id,
      agent_type: agentType,
      customer_name: customerName,
      tax_id: taxId,
      result: {},
      created_at: new Date().toISOString(),
      run_status: "processing",
    };
    const existing = loadHistoryItemsLocally(agentType);
    const updated = [item, ...existing].slice(0, LOCAL_HISTORY_MAX_ITEMS);
    localStorage.setItem(localHistoryKey(agentType), JSON.stringify(updated));
    return id;
  } catch {
    // Private browsing, blocked storage, or quota exceeded — history simply
    // won't survive a refresh in that case; never break the assessment flow.
    return -1;
  }
}

export function finishHistoryPlaceholder(
  agentType: "rb" | "eb" | "crosssell",
  id: number,
  outcome: { status: "success"; result: AssessmentResult } | { status: "failed"; errorMessage: string }
): void {
  if (id < 0) return;
  try {
    const items = loadHistoryItemsLocally(agentType);
    const updated = items.map((item) => {
      if (item.id !== id) return item;
      return outcome.status === "success"
        ? { ...item, result: outcome.result, run_status: "success" as const }
        : { ...item, run_status: "failed" as const, error_message: outcome.errorMessage };
    });
    localStorage.setItem(localHistoryKey(agentType), JSON.stringify(updated));
  } catch {
    // best-effort — see startHistoryPlaceholder.
  }
}

export function loadHistoryItemsLocally(agentType: "rb" | "eb" | "crosssell"): HistoryItem[] {
  try {
    const raw = localStorage.getItem(localHistoryKey(agentType));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}
