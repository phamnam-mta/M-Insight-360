"use client";

import { useState } from "react";
import Image from "next/image";
import AssessmentForm from "@/components/AssessmentForm";
import EbResultPanel from "@/components/EbResultPanel";
import HistoryPanel from "@/components/HistoryPanel";
import ResultPanel from "@/components/ResultPanel";
import CrossSellPanel from "@/components/CrossSellPanel";
import { AssessmentResult, saveHistoryItemLocally } from "@/lib/api";

const TAB_LABELS: Record<"rb" | "eb" | "crosssell", string> = {
  rb: "RB",
  eb: "EB",
  crosssell: "Cross-sell",
};

export default function Home() {
  const [tab, setTab] = useState<"rb" | "eb" | "crosssell">("rb");
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

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
          <div className="flex items-center justify-between gap-4 mb-4">
            <Image
              src="/msb-logo-color.svg"
              alt="MSB"
              width={72}
              height={18}
              className="shrink-0"
              priority
            />
            <p className="text-right text-[11px] leading-tight text-gray-400 hidden sm:block">
              Smarter Data
              <br />
              Bigger Opportunities
            </p>
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold tracking-widest text-msb-orange uppercase">
              Hệ thống quản lý công tác
            </p>
            <h1 className="text-xl md:text-2xl font-bold text-msb-navy leading-snug mt-1">
              Trợ lý thẩm định tín dụng
              <br className="hidden sm:block" /> Toàn diện MSB
            </h1>
            <p className="text-xs text-gray-500 mt-2 max-w-2xl leading-relaxed">
              Thẩm định Tín dụng KHDN (EB) &amp; KHCN (RB) Hộ kinh doanh · Tự động bóc tách BCTC, tính
              NWC, DSCR, ICR, Cross-sell và xuất Tờ trình chỉ trong vài giây.
            </p>
          </div>
        </div>
      </header>

      <div className="border-b border-gray-200/70" />

      <div className={`mx-auto px-4 py-8 ${tab === "eb" ? "max-w-6xl" : "max-w-3xl"}`}>
        <div className="flex gap-2 mb-6">
          {(["rb", "eb", "crosssell"] as const).map((t) => (
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

        <AssessmentForm
          agentType={tab}
          onResult={(r) => {
            setResult(r);
            saveHistoryItemLocally(
              tab,
              (r.customer_profile?.customer_name as string) ?? "",
              (r.customer_profile?.tax_id as string) ?? "",
              r
            );
            setHistoryRefreshKey((k) => k + 1);
          }}
        />
        <HistoryPanel agentType={tab} onSelect={setResult} refreshKey={historyRefreshKey} />
        {result && tab === "crosssell" && <CrossSellPanel result={result} />}
        {result && tab === "eb" && <EbResultPanel result={result} />}
        {result && tab === "rb" && <ResultPanel result={result} />}
      </div>

      <footer className="text-center text-xs text-msb-navy/60 py-6">
        © MSB — Ngân hàng TMCP Hàng Hải Việt Nam · M-Insight 360 (nội bộ, POC hackathon)
      </footer>
    </main>
  );
}
