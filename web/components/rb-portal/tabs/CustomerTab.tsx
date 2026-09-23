"use client";

import { SectionForm } from "./SectionForm";

export function CustomerTab({ caseId }: { caseId: string }) {
  return (
    <SectionForm
      caseId={caseId}
      section="customer"
      title="Hồ sơ khách hàng"
      fields={[
        { key: "full_name", label: "Họ tên", type: "text" },
        {
          key: "gender", label: "Giới tính", type: "select",
          options: [{ value: "male", label: "Nam" }, { value: "female", label: "Nữ" }],
        },
        { key: "date_of_birth", label: "Ngày sinh", type: "date" },
        { key: "nationality", label: "Quốc tịch", type: "text" },
        { key: "id_number", label: "Số CCCD/Hộ chiếu", type: "text" },
        { key: "tax_id", label: "Mã số thuế", type: "text" },
        { key: "permanent_address", label: "Địa chỉ thường trú", type: "text" },
        { key: "temporary_address", label: "Địa chỉ tạm trú", type: "text" },
        { key: "contact_address", label: "Địa chỉ liên lạc", type: "text" },
        { key: "phone_mobile", label: "Điện thoại di động", type: "text" },
        { key: "phone_home", label: "Điện thoại nhà riêng", type: "text" },
        { key: "email", label: "Email", type: "text" },
        {
          key: "marital_status", label: "Tình trạng hôn nhân", type: "select",
          options: [
            { value: "single", label: "Độc thân" }, { value: "married", label: "Có gia đình" },
            { value: "divorced", label: "Ly hôn" }, { value: "widowed", label: "Góa" },
          ],
        },
        { key: "education_level", label: "Trình độ học vấn", type: "text" },
      ]}
    />
  );
}
