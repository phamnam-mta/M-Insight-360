"use client";

import { SectionForm } from "./SectionForm";

export function LegalTab({ caseId }: { caseId: string }) {
  return (
    <SectionForm
      caseId={caseId}
      section="legal"
      title="Pháp lý"
      fields={[
        {
          key: "id_type", label: "Loại giấy tờ định danh", type: "select",
          options: [
            { value: "CCCD", label: "CCCD" }, { value: "CMND", label: "CMND" },
            { value: "PASSPORT", label: "Hộ chiếu" },
          ],
        },
        { key: "id_issue_date", label: "Ngày cấp", type: "date" },
        { key: "id_issue_place", label: "Nơi cấp", type: "text" },
        { key: "business_registration_number", label: "Số đăng ký kinh doanh", type: "text" },
        { key: "business_registration_issue_date", label: "Ngày cấp ĐKKD", type: "date" },
        { key: "business_registration_issue_place", label: "Nơi cấp ĐKKD", type: "text" },
      ]}
    />
  );
}
