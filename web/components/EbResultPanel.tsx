"use client";

import {
  ClipboardList,
  File,
  FileDown,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  TrendingUp,
} from "lucide-react";
import {
  AssessmentResult,
  ConditionRow,
  DocumentStatus,
  evidenceFileUrl,
  exportMb02,
} from "@/lib/api";
import { computeCoverage, missingRequiredFieldLabels, REQUIRED_FIELD_LABELS, splitRiskFlags } from "@/lib/eb-red-flags";
import { AiInsightSection } from "./shared/AiInsightSection";
import { MetricCard, MetricTone, MetricValue } from "./shared/MetricCard";
import { SectionHeader } from "./shared/SectionHeader";
import { useState } from "react";
import { CompanyInfoBlock } from "./eb/CompanyInfoBlock";
import { EbHeaderBar } from "./eb/EbHeaderBar";
import { PreCheckCard } from "./eb/PreCheckCard";
import { FinancialDataTable } from "./eb/FinancialDataTable";
import { CapitalBalanceDiagram } from "./eb/CapitalBalanceDiagram";
import { ExportGateScreen } from "./eb/ExportGateScreen";
import { ExportGateSummaryCard } from "./eb/ExportGateSummaryCard";
import { Qd039Card } from "./eb/Qd039Card";
import { EbRiskFlagsPriorityList } from "./eb/EbRiskFlagsPriorityList";
import { RmChecklistCard } from "./eb/RmChecklistCard";
import { LockedPlaceholders } from "./eb/LockedPlaceholders";
import { StressTestDrawer } from "./eb/StressTestDrawer";

// M1 falls back to this when overall_conclusion is null (no pending
// overview rows) — must never surface the raw backend enum string.
const CREDIT_READINESS_LABELS: Record<string, string> = {
  READY: "Đủ điều kiện thẩm định",
  READY_WITH_CONDITIONS: "Đủ điều kiện thẩm định, kèm điều kiện lưu ý",
  MANUAL_REVIEW_REQUIRED: "Cần chuyên viên tín dụng rà soát thủ công",
  NOT_READY: "Chưa đủ hồ sơ để thẩm định",
};

function fileIconFor(filename: string) {
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "csv" || ext === "xlsx") return FileSpreadsheet;
  if (ext === "pdf" || ext === "docx") return FileText;
  return File;
}

const RESULT_LABEL: Record<string, string> = {
  PASS: "Đạt",
  FAIL: "Không đạt",
  INSUFFICIENT_DATA: "Chưa đủ dữ liệu",
  PENDING_INTERNAL_CHECK: "Chờ kiểm tra trên hệ thống nội bộ",
  NOT_APPLICABLE: "Không áp dụng",
};

const RESULT_STYLE: Record<string, string> = {
  PASS: "bg-green-100 text-green-800",
  FAIL: "bg-red-100 text-red-800",
  INSUFFICIENT_DATA: "bg-gray-100 text-gray-600",
  PENDING_INTERNAL_CHECK: "bg-amber-100 text-amber-800",
  NOT_APPLICABLE: "bg-gray-100 text-gray-500",
};

function ResultBadge({ result }: { result: string }) {
  return (
    <span
      className={`inline-block text-xs font-semibold px-2.5 py-1 rounded-full whitespace-nowrap ${
        RESULT_STYLE[result] ?? "bg-gray-100 text-gray-600"
      }`}
    >
      {RESULT_LABEL[result] ?? result}
    </span>
  );
}

function formatObservedValue(row: ConditionRow): string {
  const v = row.observed.value;
  if (v === null || v === undefined) return "Chưa có dữ liệu";
  if (typeof v === "number") {
    return row.observed.unit === "VND" ? `${v.toLocaleString("vi-VN")} VND` : v.toLocaleString("vi-VN");
  }
  return String(v);
}

function EvidenceCell({ row, caseId }: { row: ConditionRow; caseId?: string }) {
  if (row.observed.evidence.length === 0) {
    return <span className="text-xs text-gray-400">—</span>;
  }
  return (
    <ul className="text-xs space-y-1">
      {row.observed.evidence.map((ev, i) => (
        <li key={i}>
          {caseId ? (
            <a
              href={evidenceFileUrl(caseId, ev.file_id)}
              target="_blank"
              rel="noopener noreferrer"
              className="text-msb-navy underline"
            >
              {ev.filename} — {ev.location}
            </a>
          ) : (
            <span>{ev.filename} — {ev.location}</span>
          )}
          <div className="text-gray-500 italic">&quot;{ev.original_text}&quot;</div>
        </li>
      ))}
    </ul>
  );
}

function OverviewTable({ rows, caseId }: { rows: ConditionRow[]; caseId?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] text-sm border-collapse table-fixed">
        <colgroup>
          <col className="w-[14%]" />
          <col className="w-[14%]" />
          <col className="w-[18%]" />
          <col className="w-[8%]" />
          <col className="w-[24%]" />
          <col className="w-[22%]" />
        </colgroup>
        <thead>
          <tr className="text-left border-b border-gray-200 text-gray-500">
            <th className="py-2 px-2 font-semibold break-words">Tên điều kiện</th>
            <th className="py-2 px-2 font-semibold break-words">Giá trị/hiện trạng thực tế</th>
            <th className="py-2 px-2 font-semibold break-words">Điều kiện đối chiếu</th>
            <th className="py-2 px-2 font-semibold break-words">Kết quả</th>
            <th className="py-2 px-2 font-semibold break-words">Nguồn chứng cứ và ngày dữ liệu</th>
            <th className="py-2 px-2 font-semibold break-words">Lý do/chứng từ còn thiếu</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.condition_id} className="border-b border-gray-100 align-top hover:bg-gray-50/60">
              <td className="py-2.5 px-2 font-medium text-msb-navy break-words">{row.condition_name}</td>
              <td className="py-2.5 px-2 break-words">{formatObservedValue(row)}</td>
              <td className="py-2.5 px-2 text-gray-600 break-words">{row.compare_rule}</td>
              <td className="py-2.5 px-2 break-words"><ResultBadge result={row.result} /></td>
              <td className="py-2.5 px-2 break-words"><EvidenceCell row={row} caseId={caseId} /></td>
              <td className="py-2.5 px-2 text-gray-600 break-words">{row.reason_if_incomplete ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const DOC_STATUS_LABEL: Record<string, string> = {
  "KHÔNG_ĐỌC_ĐƯỢC": "Không đọc được",
  "ĐÃ_TRÍCH_XUẤT": "Đã trích xuất",
  "CHỜ_XÁC_MINH": "Chờ xác minh",
  "ĐÃ_TẢI_LÊN": "Đã tải lên",
};

const DOC_STATUS_STYLE: Record<string, string> = {
  "KHÔNG_ĐỌC_ĐƯỢC": "bg-red-100 text-red-700",
  "ĐÃ_TRÍCH_XUẤT": "bg-green-100 text-green-800",
  "CHỜ_XÁC_MINH": "bg-amber-100 text-amber-800",
  "ĐÃ_TẢI_LÊN": "bg-gray-100 text-gray-600",
};

function DocumentPanel({ documents }: { documents: DocumentStatus[] }) {
  if (documents.length === 0) return null;
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-2">
      <SectionHeader icon={FolderOpen} title="D. Hồ sơ khách hàng" />
      <ul className="text-sm divide-y">
        {documents.map((d, i) => {
          const FileIcon = fileIconFor(d.filename);
          return (
            <li key={i} className="py-2.5 flex justify-between items-center gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <FileIcon className="h-4 w-4 text-gray-400 shrink-0" />
                <div className="min-w-0">
                  <p className="font-medium truncate">{d.filename}</p>
                  <p className="text-xs text-gray-500">{d.doc_type ?? "—"} · {d.cited_field_count} trường đã trích xuất</p>
                  {d.warnings.length > 0 && <p className="text-xs text-red-600">{d.warnings.join("; ")}</p>}
                </div>
              </div>
              <span
                className={`text-xs font-semibold px-2.5 py-1 rounded-full whitespace-nowrap shrink-0 ${
                  DOC_STATUS_STYLE[d.status] ?? "bg-gray-100 text-gray-600"
                }`}
              >
                {DOC_STATUS_LABEL[d.status] ?? d.status}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function EbResultPanel({
  result, onRerunWithPeriod,
}: {
  result: AssessmentResult;
  onRerunWithPeriod?: (period: string) => void;
}) {
  const overview = result.overview ?? [];
  const summary = result.overview_summary;
  const [stressOpen, setStressOpen] = useState(false);
  const gate = result.export_gate;
  const [gateScreenOpen, setGateScreenOpen] = useState(false);
  const [exporting, setExporting] = useState(false);

  async function doExport(force: boolean) {
    setExporting(true);
    try {
      const outcome = await exportMb02(result, force);
      if (outcome.blocked) {
        setGateScreenOpen(true);
      } else {
        const url = URL.createObjectURL(outcome.blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = outcome.filename;
        a.click();
        URL.revokeObjectURL(url);
        setGateScreenOpen(false);
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "Xuất tờ trình thất bại.");
    } finally {
      setExporting(false);
    }
  }

  function exportButtonProps(): { label: string; sub?: string; cls: string; disabled: boolean } {
    if (!gate || gate.verdict === "XUAT") {
      return { label: "Xuất tờ trình MB02a", sub: gate ? `Điền sẵn dữ liệu từ BCTC kỳ ${result.ho_so_period?.selected ?? "—"}` : undefined, cls: "bg-msb-orange text-white", disabled: false };
    }
    if (gate.verdict === "XUAT_KEM_CANH_BAO") {
      return { label: "Xuất tờ trình MB02a ⚠", sub: `${gate.signal_count} tín hiệu cần thẩm định thêm — bản nháp sẽ có banner cảnh báo`, cls: "bg-msb-orange text-white", disabled: false };
    }
    if (gate.block_type === "HARD") {
      return { label: "Xuất tờ trình MB02a", sub: "Hồ sơ khách hàng cung cấp chưa đầy đủ — đề nghị bổ sung bản chuẩn", cls: "bg-gray-200 text-gray-400", disabled: true };
    }
    return { label: "Xuất tờ trình MB02a", sub: `Chưa xuất tự động — ${gate.signal_count} tín hiệu cần thẩm định thêm`, cls: "bg-gray-200 text-gray-600", disabled: false };
  }

  const coverage = computeCoverage(result.financial_inputs as Record<string, number> | undefined);
  const lowCoverageMode = coverage < 30;
  const { nhomA, nhomB } = splitRiskFlags(result.risk_flags ?? []);
  const ce = result.credit_engine as Record<string, MetricValue> | undefined;
  const missingFields = missingRequiredFieldLabels(result.financial_inputs as Record<string, number> | undefined);
  // The Nhôm A rule tied to each KPI, if any — drives the KPI card's
  // top-border tone (ok/warn/bad) alongside its own OK/NEED_MORE_DATA status.
  const KPI_ORDER: { key: string; label: string; unit: string; ruleId?: string }[] = [
    { key: "nwc", label: "Vốn lưu động ròng", unit: "VND", ruleId: "RF01" },
    { key: "liquidity_balance", label: "Cân đối thanh khoản", unit: "" },
    { key: "dscr", label: "DSCR", unit: "lần", ruleId: "RF05" },
    { key: "icr", label: "ICR", unit: "lần", ruleId: "RF09" },
  ];
  function kpiTone(key: string, ruleId?: string): MetricTone {
    const metric = ce?.[key] as MetricValue | undefined;
    if (metric?.status !== "OK") return "neutral";
    if (!ruleId) return "ok";
    const flag = (result.risk_flags ?? []).find((f) => f.rule_id === ruleId);
    return flag?.status === "KÍCH HOẠT" ? "bad" : "ok";
  }

  const overallTone: "ok" | "warn" | "bad" =
    result.credit_readiness === "MANUAL_REVIEW_REQUIRED" || gate?.verdict === "KHONG_XUAT_TU_DONG"
      ? "bad"
      : result.credit_readiness === "READY" && missingFields.length === 0
        ? "ok"
        : "warn";
  const BANNER_BORDER: Record<typeof overallTone, string> = {
    ok: "border-l-[#17976b]",
    warn: "border-l-[#c8892a]",
    bad: "border-l-[#e0362c]",
  };

  return (
    <div className="mt-6 space-y-4">
      <EbHeaderBar result={result} />

      <div className={`bg-white border-l-[5px] rounded-lg px-4.5 py-3.5 text-sm shadow-sm ${BANNER_BORDER[overallTone]}`}>
        <p>
          <b>
            {result.overall_conclusion ??
              (result.credit_readiness ? CREDIT_READINESS_LABELS[result.credit_readiness] ?? result.credit_readiness : "—")}
          </b>{" "}
          Hồ sơ khách hàng cung cấp đọc được {Object.keys(REQUIRED_FIELD_LABELS).length - missingFields.length}/
          {Object.keys(REQUIRED_FIELD_LABELS).length} trường bắt buộc ({coverage}%).
          {missingFields.length > 0 && (
            <>
              {" "}
              Chưa đọc được: <b>{missingFields.join(", ")}</b>.
            </>
          )}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr_330px] gap-5 min-w-0">
        {/* Cột trái (L1/L2) */}
        <div className="space-y-5 order-4 lg:order-1 min-w-0">
          <CompanyInfoBlock result={result} onPeriodChange={(y) => onRerunWithPeriod?.(y)} />
          <PreCheckCard result={result} />
          <FinancialDataTable
            creditEngine={ce}
            financialInputs={result.financial_inputs}
            sanityCheck={result.sanity_check}
          />
        </div>

        {/* Cột giữa — PHẦN 1: Kết luận & sức khỏe tài chính */}
        <div className="space-y-5 order-2 min-w-0">
          {/* M1 */}
          <div className="bg-white rounded-xl border border-gray-100 p-6 space-y-3">
            <SectionHeader
              icon={ClipboardList}
              title="Kết luận thẩm định"
              subtitle={`Kỳ ${result.ho_so_period?.selected ?? "—"} · Độ phủ dữ liệu ${coverage}%`}
            />
            <p className="text-sm font-semibold text-msb-navy">
              {result.overall_conclusion ??
                (result.credit_readiness ? CREDIT_READINESS_LABELS[result.credit_readiness] ?? result.credit_readiness : "—")}
            </p>
            <p className="text-[11px] text-gray-400">
              Khuyến nghị sơ bộ từ dữ liệu BCTC — cần phê duyệt theo quy trình tín dụng MSB.
            </p>
          </div>

          {/* M2 — chỉ khi độ phủ < 30% */}
          {lowCoverageMode && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 space-y-2">
              <h3 className="text-sm font-semibold text-amber-800">Cần bổ sung để chạy thẩm định</h3>
              <p className="text-xs text-amber-700">
                Hồ sơ mới đọc được {coverage}% chỉ tiêu bắt buộc — bổ sung các trường còn thiếu để
                hệ thống đưa kết luận thẩm định đầy đủ.
              </p>
            </div>
          )}

          {/* M3 — 4 thẻ KPI cố định */}
          <div className="grid grid-cols-4 gap-3 items-start">
            {KPI_ORDER.map(({ key, label, unit, ruleId }) => (
              <MetricCard
                key={key}
                label={label}
                unit={unit}
                metric={(ce?.[key] as MetricValue) ?? { value: null, status: "NEED_MORE_DATA" }}
                compact={lowCoverageMode}
                tone={kpiTone(key, ruleId)}
              />
            ))}
          </div>

          {/* M4 */}
          <CapitalBalanceDiagram check={result.capital_balance_check} />
          {/* M5 */}
          <Qd039Card creditEngine={ce} receivablesVnd={result.financial_inputs?.receivables_vnd ?? null} />

          {/* PHẦN 2 — Cảnh báo rủi ro */}
          {/* M6 */}
          <EbRiskFlagsPriorityList flags={nhomA} variant="nhom_a" />
          {/* M7 */}
          <EbRiskFlagsPriorityList flags={nhomB} variant="nhom_b" />

          <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-3">
            <SectionHeader
              icon={ClipboardList}
              title="Thông tin tổng quan"
              subtitle={
                summary
                  ? `${summary.checked}/${summary.total} điều kiện đã kiểm tra đủ dữ liệu; ${summary.passed} đạt, ${summary.failed} không đạt, ${summary.pending} chờ xác minh.`
                  : undefined
              }
            />
            <OverviewTable rows={overview} caseId={result.case_id} />
          </div>
          <DocumentPanel documents={result.documents ?? []} />
        </div>

        {/* Cột phải — R1 (một panel duy nhất) + R2 */}
        <div className="space-y-5 order-3 min-w-0">
          {gate && (
            <ExportGateSummaryCard
              gate={gate}
              equityVnd={result.financial_inputs?.equity_vnd ?? null}
              exportFilename={`TTTD_..._${result.ho_so_period?.selected ?? ""}_..._BANNHAP.docx`}
            />
          )}
          <div data-testid="eb-r1-panel" className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-3">
            <AiInsightSection
              why={result.why ?? []}
              creditMemo={result.credit_memo}
              title="M-Insight AI"
              onRetry={
                result.ho_so_period?.selected
                  ? () => onRerunWithPeriod?.(result.ho_so_period!.selected!)
                  : undefined
              }
            />
            {/* R1.4 — hàng nút hành động, TRONG CÙNG panel */}
            <div className="flex flex-wrap gap-2 border-t border-gray-100 pt-3">
              <button
                onClick={() => setStressOpen(true)}
                className="text-xs font-semibold px-3 py-2 rounded-lg bg-msb-navy text-white"
              >
                Stress Test
              </button>
              {result.export_available && (() => {
                const btn = exportButtonProps();
                return (
                  <button
                    onClick={() => (gate?.verdict === "KHONG_XUAT_TU_DONG" ? setGateScreenOpen(true) : doExport(false))}
                    disabled={btn.disabled || exporting}
                    className={`text-xs font-semibold px-3 py-2 rounded-lg disabled:opacity-50 ${btn.cls}`}
                  >
                    <span className="inline-flex items-center gap-1.5">
                      <FileDown className="h-3.5 w-3.5" />
                      {btn.label}
                    </span>
                    {btn.sub && <span className="block text-[10px] opacity-80 mt-0.5">{btn.sub}</span>}
                  </button>
                );
              })()}
            </div>
          </div>

          {/* R2 */}
          <RmChecklistCard financialInputs={result.financial_inputs} />
          <LockedPlaceholders />
        </div>
      </div>

      <StressTestDrawer open={stressOpen} onClose={() => setStressOpen(false)} result={result} />
      {gateScreenOpen && gate && (
        <ExportGateScreen
          gate={gate}
          onClose={() => setGateScreenOpen(false)}
          onForceExport={() => doExport(true)}
          onRerun={
            result.ho_so_period?.selected
              ? () => onRerunWithPeriod?.(result.ho_so_period!.selected!)
              : undefined
          }
          exporting={exporting}
        />
      )}
    </div>
  );
}
