"use client";

import { SectionForm } from "./SectionForm";

export function LoanTab({ caseId }: { caseId: string }) {
  return (
    <SectionForm
      caseId={caseId}
      section="loan"
      title="Khoản vay"
      fields={[
        { key: "product", label: "Sản phẩm", type: "text" },
        { key: "purpose", label: "Mục đích vay", type: "text" },
        { key: "amount_vnd", label: "Số tiền đề nghị (VND)", type: "number" },
        { key: "tenor_months", label: "Thời hạn (tháng)", type: "number" },
        { key: "annual_rate", label: "Lãi suất dự kiến (thập phân, vd 0.1 = 10%/năm)", type: "number" },
        { key: "existing_monthly_obligation_vnd", label: "Nghĩa vụ trả nợ hiện tại (VND/tháng, nhập 0 nếu không có)", type: "number" },
        { key: "repayment_method", label: "Phương thức trả nợ", type: "text" },
      ]}
    />
  );
}
