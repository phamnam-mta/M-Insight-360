import { AssessmentResult } from "@/lib/api";

export default function ResultPanel({ result }: { result: AssessmentResult }) {
  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-4 mt-6">
      <h2 className="text-lg font-semibold text-msb-navy">
        Kết quả thẩm định gần nhất
      </h2>

      <div className="flex gap-4">
        <div>
          <span className="text-sm text-gray-500">Mức độ sẵn sàng hồ sơ</span>
          <p className="font-semibold">{result.credit_readiness ?? "—"}</p>
        </div>
        <div>
          <span className="text-sm text-gray-500">Khuyến nghị</span>
          <p className="font-semibold">{result.recommendation ?? "—"}</p>
        </div>
      </div>

      {result.risk_flags && result.risk_flags.length > 0 && (
        <div>
          <h3 className="font-medium text-msb-navy mb-1">Cảnh báo rủi ro</h3>
          <ul className="list-disc list-inside text-sm space-y-1">
            {result.risk_flags.map((f, i) => (
              <li key={i}>
                <span className="font-semibold">{f.rule_id}</span> ({f.severity}):{" "}
                {f.impact}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.missing_data && result.missing_data.length > 0 && (
        <div>
          <h3 className="font-medium text-msb-navy mb-1">Hồ sơ còn thiếu</h3>
          <ul className="list-disc list-inside text-sm">
            {result.missing_data.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      {result.why && result.why.length > 0 && (
        <div>
          <h3 className="font-medium text-msb-navy mb-1">Vì sao?</h3>
          <ul className="list-disc list-inside text-sm">
            {result.why.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {result.export_available && (
        <button className="border border-msb-navy text-msb-navy font-semibold px-4 py-2 rounded">
          Xuất tờ trình MB02
        </button>
      )}
    </div>
  );
}
