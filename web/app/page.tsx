"use client";

import { useState } from "react";
import Image from "next/image";
import AssessmentForm from "@/components/AssessmentForm";
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

  return (
    <main className="min-h-screen bg-msb-bg">
      <header
        className="relative overflow-hidden bg-msb-navy bg-cover bg-center"
        style={{ backgroundImage: "url(/msb-hero-banner.jpg)" }}
      >
        <div className="absolute inset-0 bg-gradient-to-br from-msb-navy/97 via-msb-navy/95 to-msb-navy/90" />
        <div className="relative px-8 py-10 md:py-14 max-w-5xl mx-auto">
          <Image
            src="/msb-logo-white.svg"
            alt="MSB"
            width={110}
            height={27}
            className="mb-6"
            priority
          />
          <span className="inline-block text-[11px] font-semibold tracking-widest uppercase text-msb-orange bg-white/10 rounded-full px-3 py-1 mb-4">
            MSB × GreenNode AI Hackathon
          </span>
          <h1 className="text-3xl md:text-4xl font-extrabold text-white leading-tight">
            TRỢ LÝ THẨM ĐỊNH TÍN DỤNG TOÀN DIỆN MSB
          </h1>
          <p className="text-lg md:text-xl font-semibold text-msb-orange mt-2">
            Nhanh hơn. Sâu hơn. Chính xác hơn.
          </p>
          <p className="text-sm md:text-base text-white/80 mt-4 max-w-3xl leading-relaxed">
            Đột phá phân luồng kép: Thẩm định Tín dụng KHDN (EB) &amp; KHCN (RB) Hộ kinh doanh.
            Tự động bóc tách BCTC, tính NWC, DSCR, ICR, Cross-sell và xuất Tờ trình chỉ trong vài giây.
          </p>
          <div className="flex flex-wrap gap-2 mt-5">
            {["Thẩm định KHDN (EB)", "Thẩm định KHCN (RB)", "Cross-sell", "NWC · DSCR · ICR", "Tờ trình tự động"].map(
              (label) => (
                <span
                  key={label}
                  className="text-xs font-medium text-white/90 bg-white/10 border border-white/20 rounded-full px-3 py-1"
                >
                  {label}
                </span>
              )
            )}
          </div>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-4 py-8">
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

        <AssessmentForm agentType={tab} onResult={setResult} />
        {result && (tab === "crosssell" ? <CrossSellPanel result={result} /> : <ResultPanel result={result} />)}
      </div>

      <footer className="text-center text-xs text-msb-navy/60 py-6">
        © MSB — Ngân hàng TMCP Hàng Hải Việt Nam · M-Insight 360 (nội bộ, POC hackathon)
      </footer>
    </main>
  );
}
