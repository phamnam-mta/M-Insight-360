"use client";

import { useState } from "react";
import Image from "next/image";
import AssessmentForm from "@/components/AssessmentForm";
import EbResultPanel from "@/components/EbResultPanel";
import HistoryPanel from "@/components/HistoryPanel";
import ResultPanel from "@/components/ResultPanel";
import CrossSellPanel from "@/components/CrossSellPanel";
import { AssessmentResult } from "@/lib/api";

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
      <header className="relative overflow-hidden bg-gradient-to-r from-msb-navy to-msb-navy/90">
        <div className="relative px-6 py-5 md:py-6 max-w-5xl mx-auto flex items-center gap-4">
          <Image
            src="/msb-logo-white.svg"
            alt="MSB"
            width={72}
            height={18}
            className="shrink-0 hidden sm:block"
            priority
          />
          <div className="min-w-0">
            <h1 className="text-lg md:text-xl font-bold text-white leading-snug">
              TRỢ LÝ THẨM ĐỊNH TÍN DỤNG TOÀN DIỆN MSB
            </h1>
            <p className="text-sm font-semibold text-msb-orange mt-0.5">
              Nhanh hơn. Sâu hơn. Chính xác hơn.
            </p>
            <p className="text-xs text-white/75 mt-1 max-w-2xl leading-relaxed">
              Thẩm định Tín dụng KHDN (EB) &amp; KHCN (RB) Hộ kinh doanh · Tự động bóc tách BCTC, tính
              NWC, DSCR, ICR, Cross-sell và xuất Tờ trình chỉ trong vài giây.
            </p>
          </div>
        </div>
      </header>

      <div className={`mx-auto px-4 py-8 ${tab === "eb" ? "max-w-6xl" : "max-w-3xl"}`}>
        <div className="flex gap-2 mb-6">
          {(["rb", "eb", "crosssell"] as const).map((t) => (
            <button
              key={t}
              onClick={() => {
                setTab(t);
                setResult(null);
              }}
              className={`px-4 py-2 rounded-full font-semibold transition-colors ${
                tab === t
                  ? "bg-msb-orange text-white shadow"
                  : "bg-white text-msb-navy hover:bg-msb-bg"
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
