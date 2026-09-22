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
        <div className="absolute inset-0 bg-msb-navy/95" />
        <div className="relative px-8 py-8 max-w-5xl mx-auto">
          <Image
            src="/msb-logo-white.svg"
            alt="MSB"
            width={110}
            height={27}
            className="mb-4"
            priority
          />
          <h1 className="text-3xl font-bold text-white">M-Insight 360</h1>
          <p className="text-sm text-white/80 mt-1">
            Trợ lý AI Thẩm định tín dụng &amp; Bán chéo — MSB x GreenNode AI Hackathon
          </p>
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
