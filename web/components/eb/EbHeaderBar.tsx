"use client";

import { AssessmentResult } from "@/lib/api";
import { computeCoverage } from "@/lib/eb-red-flags";

type BadgeTone = "ok" | "warn" | "bad" | "info";

const BADGE_TONE_CLASS: Record<BadgeTone, string> = {
  ok: "bg-[rgba(60,210,150,.14)] text-[#6fe0b0] border-[rgba(60,210,150,.4)]",
  warn: "bg-[rgba(255,196,80,.16)] text-[#ffcf70] border-[rgba(255,196,80,.45)]",
  bad: "bg-[rgba(224,54,44,.2)] text-[#ff9d96] border-[rgba(224,54,44,.5)]",
  info: "bg-white/10 text-[#cfe0f5] border-white/20",
};

function Badge({ tone, children }: { tone: BadgeTone; children: React.ReactNode }) {
  return (
    <span className={`text-[11.5px] font-bold px-2.5 py-1 rounded-full border whitespace-nowrap ${BADGE_TONE_CLASS[tone]}`}>
      {children}
    </span>
  );
}

export function EbHeaderBar({ result }: { result: AssessmentResult }) {
  const period = result.ho_so_period;
  const doc = (result.documents ?? [])[0];
  const coverage = computeCoverage(result.financial_inputs as Record<string, number> | undefined);
  const preCheckOk = !result.sanity_check?.balance_mismatch && !!period?.selected;

  return (
    <header className="bg-gradient-to-br from-[#12284c] to-[#1d3f72] text-white rounded-xl px-5 py-4">
      <div className="flex items-start gap-5 flex-wrap">
        <div>
          <div className="font-extrabold text-[19px] tracking-tight">
            MSB · M-Insight<span className="text-[#ff6b3d]"> 360</span>
          </div>
          <div className="text-[18px] font-bold mt-1.5">
            {(result.customer_profile?.customer_name as string) ?? "—"}
          </div>
          <div className="text-[12px] text-[#a9c0e0] mt-0.5">
            Kỳ báo cáo {period?.selected ?? "—"} · BCTC {doc?.doc_type ?? "Chưa xác định từ hồ sơ tải lên"} ·{" "}
            {doc?.filename ?? "Chưa có tệp"}
          </div>
        </div>
        <div className="ml-auto flex gap-1.5 flex-wrap items-center">
          <Badge tone={preCheckOk ? "ok" : "warn"}>
            Tiền kiểm hồ sơ: {preCheckOk ? "PASS" : "CẦN RÀ SOÁT"}
          </Badge>
          <Badge tone="info">Độ phủ dữ liệu {coverage}%</Badge>
          <Badge tone="info">Đơn vị: VND</Badge>
        </div>
      </div>
    </header>
  );
}
