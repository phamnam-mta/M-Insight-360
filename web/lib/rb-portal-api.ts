import { RiskFlag } from "./api";
import { MetricValue } from "../components/shared/MetricCard";

export type RbCaseSection = "customer" | "legal" | "income" | "loan" | "collateral" | "other";

export type RbCase = {
  case_id: string;
  status: string;
  customer_name: string;
  tax_id: string;
  customer: Record<string, unknown> | null;
  legal: Record<string, unknown> | null;
  income: Record<string, unknown> | null;
  loan: Record<string, unknown> | null;
  collateral: { items: Record<string, unknown>[] } | null;
  other: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type RbDocument = {
  id: number;
  case_id: string;
  file_id: string;
  filename: string;
  category: string;
  document_type: string | null;
  status: "UPLOADED" | "PROCESSING" | "EXTRACTED" | "FAILED" | "NEED_OCR_VLM";
  content_type: string | null;
  size_bytes: number;
  storage_path: string;
  uploaded_at: string;
};

export type RbMandatoryCheck = {
  legal: string[];
  income: string[];
  loan: string[];
  other: string[];
  tax_declaration_required: boolean | null;
  tax_declaration_present: boolean;
  missing: string[];
};

export type RbTimelineStep = { status: string; label: string; reached: boolean };

// Exactly what run_case_assessment() (app/agents/rb_portal/assessment.py)
// returns, plus why/credit_memo — this is also exactly what gets persisted
// into rb_case_assessments.computed_json on each run, so it is the type of
// RbHistoryVersion.computed too. RbSummary below extends it with the extra
// fields the summary endpoint layers on top (document_overview, documents,
// timeline, ai_status) that are NOT part of the persisted blob — keep this
// split; giving RbHistoryVersion.computed the full RbSummary type would
// silently lie about fields (e.g. .document_overview) that are undefined
// at runtime on a history entry.
export type RbAssessmentComputed = {
  credit_engine: Record<string, MetricValue>;
  risk_flags: RiskFlag[];
  mandatory_check: RbMandatoryCheck;
  missing_data: string[];
  credit_readiness: string;
  recommendation: string;
  why: string[];
  credit_memo: string;
};

export type RbSummary = RbCase & RbAssessmentComputed & {
  document_overview: { total_documents: number; completion_percent: number; missing_count: number };
  documents: RbDocument[];
  timeline: RbTimelineStep[];
  ai_status: "AVAILABLE" | "UNAVAILABLE";
};

export type RbHistoryVersion = { version: number; kind: "PRELIMINARY" | "FULL"; computed: RbAssessmentComputed; created_at: string };

const BASE = "/api/rb-portal";

async function asJson<T>(resp: Response): Promise<T> {
  if (!resp.ok) throw new Error(`RB Portal request thất bại: HTTP ${resp.status}`);
  return resp.json();
}

export async function createCase(customerName: string, taxId: string): Promise<{ case_id: string }> {
  return asJson(
    await fetch(`${BASE}/cases`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ customer_name: customerName, tax_id: taxId }),
    })
  );
}

export async function listCases(limit = 20): Promise<RbCase[]> {
  const body = await asJson<{ cases: RbCase[] }>(await fetch(`${BASE}/cases?limit=${limit}`));
  return body.cases;
}

export async function getCase(caseId: string): Promise<RbCase> {
  return asJson(await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}`));
}

export async function updateCaseSection(
  caseId: string, section: RbCaseSection, data: Record<string, unknown>
): Promise<void> {
  const resp = await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/${section}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) throw new Error(`Lưu ${section} thất bại: HTTP ${resp.status}`);
}

export async function uploadDocument(caseId: string, file: File, category: string): Promise<RbDocument> {
  const form = new FormData();
  form.append("file", file);
  form.append("category", category);
  return asJson(
    await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/documents`, { method: "POST", body: form })
  );
}

export async function listDocuments(caseId: string): Promise<RbDocument[]> {
  const body = await asJson<{ documents: RbDocument[] }>(
    await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/documents`)
  );
  return body.documents;
}

export async function runPreliminaryAssessment(caseId: string): Promise<RbSummary> {
  return asJson(await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/preliminary-assessment`, { method: "POST" }));
}

export async function runFullAssessment(caseId: string): Promise<RbSummary> {
  const resp = await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/full-assessment`, { method: "POST" });
  if (resp.status === 409) {
    const body = await resp.json();
    throw new Error(`Chưa đủ hồ sơ bắt buộc: ${(body.detail?.missing ?? []).join(", ")}`);
  }
  return asJson(resp);
}

export async function getSummary(caseId: string): Promise<RbSummary> {
  return asJson(await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/summary`));
}

export async function getHistory(caseId: string): Promise<RbHistoryVersion[]> {
  const body = await asJson<{ versions: RbHistoryVersion[] }>(
    await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/history`)
  );
  return body.versions;
}

export async function exportMb01a(caseId: string): Promise<Blob> {
  const resp = await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/export/mb01a`, { method: "POST" });
  if (!resp.ok) throw new Error(`Xuất MB01A thất bại: HTTP ${resp.status}`);
  return resp.blob();
}

export async function getZaloQrStatus(): Promise<{ status: string; qr_url: string | null; message: string }> {
  return asJson(await fetch(`${BASE}/zalo-bot/qr`));
}
