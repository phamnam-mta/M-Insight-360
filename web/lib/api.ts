export type AssessmentResult = {
  case_id?: string;
  customer_profile?: Record<string, unknown>;
  credit_engine?: Record<string, unknown>;
  risk_flags?: Array<{
    rule_id?: string;
    severity?: string;
    evidence?: string[];
    impact?: string;
    recommended_action?: string;
  }>;
  missing_data?: string[];
  credit_readiness?: string;
  recommendation?: string;
  why?: string[];
  credit_memo?: string;
  export_available?: boolean;
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
  agentType: "rb" | "eb",
  customerName: string,
  taxId: string,
  files: File[]
): Promise<AssessmentResult> {
  const form = new FormData();
  form.append("customer_name", customerName);
  form.append("tax_id", taxId);
  for (const f of files) form.append("files", f);

  const resp = await fetch(`/api/${agentType}/assess`, {
    method: "POST",
    body: form,
  });
  if (!resp.ok) {
    throw new Error(`Thẩm định thất bại: HTTP ${resp.status}`);
  }
  return resp.json();
}
