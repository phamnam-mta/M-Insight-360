import { Handshake } from "lucide-react";
import { OpportunityCard } from "@/lib/api";
import { SectionHeader } from "./SectionHeader";

export function CrossSellOpportunities({
  opportunities,
  title = "Cơ hội bán chéo",
}: {
  opportunities: OpportunityCard[];
  title?: string;
}) {
  if (opportunities.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6">
        <SectionHeader
          icon={Handshake}
          title={title}
          subtitle="Chưa phát hiện dấu hiệu nhu cầu rõ ràng từ chứng từ hiện có."
        />
      </div>
    );
  }
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-3">
      <SectionHeader icon={Handshake} title={title} />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {opportunities.map((o, i) => (
          <div key={i} className="border border-gray-100 rounded-lg p-3 text-sm space-y-1">
            <p className="font-semibold text-msb-navy">{o.product_suggestion}</p>
            <p className="text-gray-600">{o.formula_note}</p>
            {o.basis_documents.length > 0 && (
              <ul className="text-xs text-gray-500 list-disc list-inside">
                {o.basis_documents.map((b, j) => (
                  <li key={j}>{b}</li>
                ))}
              </ul>
            )}
            {o.unverified_conditions && (
              <p className="text-xs text-amber-700">Chưa xác minh: {o.unverified_conditions}</p>
            )}
            <p className="text-xs text-gray-500">
              Mức ưu tiên: {o.priority} · Người rà soát: {o.reviewer}
            </p>
            {o.recommended_action && <p className="text-xs font-medium">{o.recommended_action}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
