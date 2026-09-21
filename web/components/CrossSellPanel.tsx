import { ACTIVATED_STATUS, AssessmentResult, INSUFFICIENT_DATA_STATUS } from "@/lib/api";

function formatVnd(n: number | undefined): string {
  if (n === undefined || n === null) return "—";
  return n.toLocaleString("vi-VN") + " VND";
}

export default function CrossSellPanel({ result }: { result: AssessmentResult }) {
  const precheck = result.precheck;
  const activated = (result.opportunities ?? []).filter((o) => o.status === ACTIVATED_STATUS);
  const insufficient = (result.opportunities ?? []).filter((o) => o.status === INSUFFICIENT_DATA_STATUS);

  return (
    <div className="space-y-6 mt-6">
      {precheck && (
        <div
          className={`rounded-lg shadow p-6 ${
            precheck.verdict === "BLOCK"
              ? "bg-red-50 border border-red-300"
              : precheck.verdict === "WARN"
              ? "bg-amber-50 border border-amber-300"
              : "bg-green-50 border border-green-300"
          }`}
        >
          <h2 className="text-lg font-semibold text-msb-navy mb-1">
            Kiểm tra tính toàn vẹn sao kê: {precheck.verdict}
          </h2>
          {precheck.reason && <p className="text-sm">{precheck.reason}</p>}
        </div>
      )}

      {result.extraction_warnings && result.extraction_warnings.length > 0 && (
        <div className="bg-amber-50 border border-amber-300 rounded-lg p-4 text-sm">
          <h3 className="font-medium text-msb-navy mb-1">Cảnh báo trích xuất dữ liệu</h3>
          <ul className="list-disc list-inside">
            {result.extraction_warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {result.dashboard && result.dashboard.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-msb-navy mb-3">Dòng tiền theo tháng</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="py-1">Tháng</th>
                <th className="py-1">Số GD</th>
                <th className="py-1">Tiền vào</th>
                <th className="py-1">Tiền ra</th>
                <th className="py-1">Ròng</th>
              </tr>
            </thead>
            <tbody>
              {result.dashboard.map((row) => (
                <tr key={row.month} className="border-b last:border-0">
                  <td className="py-1">{row.month}</td>
                  <td className="py-1">{row.transaction_count}</td>
                  <td className="py-1">{formatVnd(row.total_in)}</td>
                  <td className="py-1">{formatVnd(row.total_out)}</td>
                  <td className={`py-1 ${row.net < 0 ? "text-red-600" : ""}`}>{formatVnd(row.net)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {result.top_partners && result.top_partners.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-msb-navy mb-3">Đối tác giao dịch nhiều nhất</h2>
          <ul className="text-sm space-y-1">
            {result.top_partners.map((p, i) => (
              <li key={i} className="flex justify-between">
                <span>
                  {p.partner} ({p.transaction_count} GD){p.qualifies && (
                    <span className="ml-2 text-msb-orange font-semibold">Đủ điều kiện SCF</span>
                  )}
                </span>
                <span>{formatVnd(p.total_value)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-msb-navy mb-3">
          Cơ hội bán chéo {result.confidence_ceiling ? `(độ tin cậy: ${result.confidence_ceiling})` : ""}
        </h2>
        {activated.length > 0 ? (
          <ul className="list-disc list-inside text-sm space-y-1">
            {activated.map((o, i) => (
              <li key={i}>
                <span className="font-semibold">{o.rule_id}</span>: {o.impact}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-gray-500">Không phát hiện cơ hội bán chéo rõ ràng từ dữ liệu hiện có.</p>
        )}
        {insufficient.length > 0 && (
          <div className="mt-3 pt-3 border-t">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Chưa đủ dữ liệu để đánh giá</h3>
            <ul className="list-disc list-inside text-sm text-gray-500 space-y-1">
              {insufficient.map((o, i) => (
                <li key={i}>{o.rule_id}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {result.why && result.why.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-msb-navy mb-3">Vì sao?</h2>
          <ul className="list-disc list-inside text-sm">
            {result.why.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
