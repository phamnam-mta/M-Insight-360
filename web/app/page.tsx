"use client";

import { useState } from "react";
import Image from "next/image";
import dynamic from "next/dynamic";
import AssessmentForm from "@/components/AssessmentForm";
import EbResultPanel from "@/components/EbResultPanel";
import HistoryPanel from "@/components/HistoryPanel";
import CrossSellPanel from "@/components/CrossSellPanel";
import { AssessmentResult, finishHistoryPlaceholder, runAssessment, startHistoryPlaceholder } from "@/lib/api";

const RbPortal = dynamic(() => import("@/components/rb-portal/RbPortal"), { ssr: false });

const TAB_LABELS: Record<"rb" | "eb" | "crosssell", string> = {
  rb: "RB",
  eb: "EB",
  crosssell: "Cross-sell",
};

export default function Home() {
  const [tab, setTab] = useState<"rb" | "eb" | "crosssell">("eb");
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const [lastEbFiles, setLastEbFiles] = useState<{ files: File[]; customerName: string; taxId: string } | null>(null);

  async function handleRerunWithPeriod(period: string) {
    if (!lastEbFiles) return;
    const r = await runAssessment("eb", lastEbFiles.customerName, lastEbFiles.taxId, lastEbFiles.files, { report_period: period });
    setResult(r);
  }

  return (
    <main className="min-h-screen bg-msb-bg">
      <header className="relative overflow-hidden bg-gradient-to-br from-[#eef1fa] via-[#eef1fa] to-[#e4e9f7]">
        <div
          className="pointer-events-none absolute -right-16 -top-24 h-72 w-72 rounded-full bg-indigo-300/25 blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute right-24 top-10 h-40 w-40 rounded-full bg-msb-orange/10 blur-2xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute right-0 top-0 hidden h-full md:block"
          aria-hidden
        >
          <svg width="320" height="170" viewBox="0 0 320 170" fill="none">
            <path
              d="M0 100C60 50 110 140 160 80C200 32 250 70 320 20"
              stroke="#6E7FCB"
              strokeOpacity="0.35"
              strokeWidth="2"
            />
            <path
              d="M20 140C80 100 120 170 170 120C210 80 260 110 320 60"
              stroke="#F4600C"
              strokeOpacity="0.25"
              strokeWidth="2"
            />
          </svg>
        </div>

        <div className="relative px-6 py-6 md:py-7 max-w-5xl mx-auto">
          <div className="flex items-center justify-between gap-4 mb-5">
            <div className="flex items-center gap-3 min-w-0">
              <Image
                src="/mi360-logo.jpg"
                alt="MI360"
                width={52}
                height={52}
                className="shrink-0 rounded-2xl shadow-sm ring-1 ring-black/5"
                priority
              />
              <div className="min-w-0 leading-tight">
                <p className="text-sm font-extrabold text-msb-navy tracking-tight">MI360</p>
                <p className="text-[10px] text-gray-400">M-Insight 360</p>
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <p className="text-right text-[11px] leading-tight text-gray-400 hidden sm:block">
                Smarter Data
                <br />
                Bigger Opportunities
              </p>
              <Image
                src="/msb-logo-color.svg"
                alt="MSB"
                width={60}
                height={15}
                className="shrink-0"
              />
            </div>
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold tracking-widest text-msb-orange uppercase">
              Nền tảng MI360
            </p>
            <h1 className="text-xl md:text-2xl font-bold text-msb-navy leading-snug mt-1">
              Khai thác Dòng tiền &amp; Thẩm định Tín dụng toàn diện
            </h1>
            <p className="text-xs md:text-sm text-msb-orange font-semibold mt-2 max-w-2xl leading-relaxed">
              Thẩm định nhanh hơn – cảnh báo sớm hơn – bán chéo thông minh hơn
            </p>
          </div>
        </div>
      </header>

      <div className="border-b border-gray-200/70" />

      <div className="mx-auto px-4 py-8 max-w-6xl">
        <div className="flex gap-2 mb-6">
          {(["eb", "rb", "crosssell"] as const).map((t) => (
            <button
              key={t}
              onClick={() => {
                setTab(t);
                setResult(null);
              }}
              className={`px-5 py-2 rounded-full text-sm font-semibold transition-colors ${
                tab === t
                  ? "bg-msb-orange text-white shadow-sm"
                  : "bg-white text-msb-navy border border-gray-100 hover:bg-msb-bg"
              }`}
            >
              {TAB_LABELS[t]}
            </button>
          ))}
        </div>

        {tab === "rb" ? (
          <RbPortal />
        ) : (
          <>
            <AssessmentForm
              agentType={tab}
              onStart={(customerName, taxId) => {
                const id = startHistoryPlaceholder(tab, customerName, taxId);
                setHistoryRefreshKey((k) => k + 1);
                return id;
              }}
              onResult={(r, historyId) => {
                setResult(r);
                if (historyId !== undefined) {
                  finishHistoryPlaceholder(tab, historyId, { status: "success", result: r });
                }
                setHistoryRefreshKey((k) => k + 1);
              }}
              onError={(message, historyId) => {
                if (historyId !== undefined) {
                  finishHistoryPlaceholder(tab, historyId, { status: "failed", errorMessage: message });
                }
                setHistoryRefreshKey((k) => k + 1);
              }}
              onSubmitted={
                tab === "eb"
                  ? (files, customerName, taxId) => setLastEbFiles({ files, customerName, taxId })
                  : undefined
              }
            />
            <HistoryPanel agentType={tab} onSelect={setResult} refreshKey={historyRefreshKey} />
            {result && tab === "crosssell" && <CrossSellPanel result={result} />}
            {result && tab === "eb" && <EbResultPanel result={result} onRerunWithPeriod={handleRerunWithPeriod} />}
          </>
        )}
      </div>

      <footer className="text-center text-xs text-msb-navy/60 py-6">
        © MSB — Ngân hàng TMCP Hàng Hải Việt Nam · M-Insight 360 (nội bộ, POC hackathon)
      </footer>
    </main>
  );
}
