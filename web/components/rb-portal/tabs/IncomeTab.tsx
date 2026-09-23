"use client";

import { useEffect, useState } from "react";
import { getCase, updateCaseSection } from "@/lib/rb-portal-api";

const SOURCE_TYPES = [
  { value: "salary", label: "Lương" },
  { value: "business", label: "Kinh doanh" },
  { value: "self_employed", label: "Tự doanh" },
  { value: "household_business", label: "Hộ kinh doanh" },
];

const _BUSINESS_TYPES = new Set(["business", "self_employed", "household_business"]);

type IncomeState = Record<string, string> & { tax_declaration_present: string };

export function IncomeTab({ caseId }: { caseId: string }) {
  const [values, setValues] = useState<IncomeState>({ tax_declaration_present: "false" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getCase(caseId)
      .then((c) => {
        const income = (c.income as Record<string, unknown> | null) ?? {};
        const asStrings: IncomeState = { tax_declaration_present: "false" };
        for (const [k, v] of Object.entries(income)) {
          asStrings[k] = v === null || v === undefined ? "" : String(v);
        }
        setValues(asStrings);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Không tải được dữ liệu"))
      .finally(() => setLoading(false));
  }, [caseId]);

  const sourceType = values.source_type ?? "";
  const isBusiness = _BUSINESS_TYPES.has(sourceType);

  function set(key: string, value: string) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const numberKeys = [
        "business_years", "employment_years", "income_salary_vnd", "income_rental_vnd",
        "income_business_vnd", "income_guarantor_vnd", "expense_living_vnd",
        "expense_other_debt_vnd", "expense_other_vnd", "dependents_count",
      ];
      const payload: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(values)) {
        if (k === "tax_declaration_present") { payload[k] = v === "true"; continue; }
        if (numberKeys.includes(k)) { payload[k] = v === "" ? null : Number(v); continue; }
        payload[k] = v || null;
      }
      await updateCaseSection(caseId, "income", payload);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lưu thất bại");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="text-sm text-gray-500">Đang tải...</p>;

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-4">
      <h3 className="text-sm font-semibold text-msb-navy">Nguồn thu</h3>

      <div>
        <label className="block text-xs font-medium text-msb-navy mb-1">Nguồn thu nhập chính</label>
        <select
          className="w-full sm:w-64 border border-gray-200 rounded-lg px-3 py-2 text-sm"
          value={sourceType}
          onChange={(e) => set("source_type", e.target.value)}
        >
          <option value="">— Chọn —</option>
          {SOURCE_TYPES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
      </div>

      {isBusiness && (
        <div className="border-t pt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-msb-navy mb-1">Tên cơ sở kinh doanh</label>
            <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values.business_name ?? ""} onChange={(e) => set("business_name", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-msb-navy mb-1">Ngành nghề kinh doanh</label>
            <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values.business_sector ?? ""} onChange={(e) => set("business_sector", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-msb-navy mb-1">Thời gian kinh doanh (năm)</label>
            <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values.business_years ?? ""} onChange={(e) => set("business_years", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-msb-navy mb-1">Địa điểm kinh doanh</label>
            <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values.business_address ?? ""} onChange={(e) => set("business_address", e.target.value)} />
          </div>

          <div className="sm:col-span-2 bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={values.tax_declaration_present === "true"}
              onChange={(e) => set("tax_declaration_present", String(e.target.checked))}
            />
            <div>
              <p className="text-sm font-medium text-amber-900">Đã có tờ khai thuế</p>
              <p className="text-xs text-amber-700">
                Bắt buộc với khách hàng có nguồn thu kinh doanh/tự doanh/hộ kinh doanh — nếu chưa
                tick, hồ sơ sẽ hiện thiếu ở tab Tổng hợp và không đủ điều kiện thẩm định đầy đủ.
              </p>
            </div>
          </div>
        </div>
      )}

      {sourceType === "salary" && (
        <div className="border-t pt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-msb-navy mb-1">Tên đơn vị công tác</label>
            <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values.employer_name ?? ""} onChange={(e) => set("employer_name", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-msb-navy mb-1">Chức vụ hiện tại</label>
            <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values.position ?? ""} onChange={(e) => set("position", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-msb-navy mb-1">Địa chỉ cơ quan</label>
            <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values.employer_address ?? ""} onChange={(e) => set("employer_address", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-msb-navy mb-1">Thời gian làm việc (năm)</label>
            <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values.employment_years ?? ""} onChange={(e) => set("employment_years", e.target.value)} />
          </div>
        </div>
      )}

      <div className="border-t pt-4 space-y-2">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Thông tin tài chính (VND/tháng)</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            ["income_salary_vnd", "Thu nhập từ lương"], ["income_rental_vnd", "Thu nhập từ cho thuê tài sản"],
            ["income_business_vnd", "Thu nhập từ kinh doanh"], ["income_guarantor_vnd", "Thu nhập người bảo lãnh"],
            ["expense_living_vnd", "Chi phí sinh hoạt, tiêu dùng"], ["expense_other_debt_vnd", "Nghĩa vụ trả nợ khác"],
            ["expense_other_vnd", "Chi phí khác"], ["dependents_count", "Số người phụ thuộc"],
          ].map(([key, label]) => (
            <div key={key}>
              <label className="block text-xs font-medium text-msb-navy mb-1">{label}</label>
              <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values[key] ?? ""} onChange={(e) => set(key, e.target.value)} />
            </div>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex items-center gap-3">
        <button onClick={handleSave} disabled={saving} className="bg-msb-orange text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50">
          {saving ? "Đang lưu..." : "Lưu"}
        </button>
        {saved && <span className="text-xs text-green-600">Đã lưu.</span>}
      </div>
    </div>
  );
}
