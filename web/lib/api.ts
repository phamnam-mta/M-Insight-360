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
};

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
  // Cross-sell-only fields (POST /api/crosssell/assess returns a different
  // shape than RB/EB — no credit_readiness/recommendation/risk_flags).
  precheck?: {
    verdict?: string;
    reason?: string;
    total_credit?: number;
    total_debit?: number;
  };
  name_quality?: Record<string, unknown>;
  flow_classification?: {
    operating_in?: number;
    operating_in_pct?: number;
    cash?: number;
    interbank?: number;
  };
  dashboard?: Array<{
    month: string;
    transaction_count: number;
    total_in: number;
    total_out: number;
    net: number;
  }>;
  top_partners?: Array<{
    partner: string;
    transaction_count: number;
    total_value: number;
    qualifies: boolean;
  }>;
  opportunities?: RiskFlag[];
  confidence_ceiling?: string;
  extraction_warnings?: string[];
};

export async function exportMb02(result: AssessmentResult): Promise<Blob> {
  const resp = await fetch("/api/eb/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(result),
  });
  if (!resp.ok) throw new Error(`Xuất tờ trình thất bại: HTTP ${resp.status}`);
  return resp.blob();
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

export type StressTestResult = {
  assumptions: Record<string, unknown>;
  before: Record<string, { value: number | null; status: string }>;
  after: Record<string, { value: number | null; status: string }>;
};

export async function runStressTest(
  inputs: Record<string, number | null>,
  deltas: { revenue_pct?: number; margin_pct?: number; interest_rate_pct?: number; collection_speed_pct?: number }
): Promise<StressTestResult> {
  const resp = await fetch("/api/eb/stress-test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inputs, deltas }),
  });
  if (!resp.ok) throw new Error(`Stress test thất bại: HTTP ${resp.status}`);
  return resp.json();
}

export type HistoryItem = {
  id: number;
  agent_type: string;
  customer_name: string;
  tax_id: string;
  result: AssessmentResult;
  created_at: string;
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

export function saveHistoryItemLocally(
  agentType: "rb" | "eb" | "crosssell",
  customerName: string,
  taxId: string,
  result: AssessmentResult
): void {
  try {
    const item: HistoryItem = {
      id: Date.now(),
      agent_type: agentType,
      customer_name: customerName,
      tax_id: taxId,
      result,
      created_at: new Date().toISOString(),
    };
    const existing = loadHistoryItemsLocally(agentType);
    const updated = [item, ...existing].slice(0, LOCAL_HISTORY_MAX_ITEMS);
    localStorage.setItem(localHistoryKey(agentType), JSON.stringify(updated));
  } catch {
    // Private browsing, blocked storage, or quota exceeded — history simply
    // won't survive a refresh in that case; never break the assessment flow.
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
