"use client";

import { useState } from "react";
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
      <header className="bg-msb-navy text-white px-8 py-6">
        <h1 className="text-2xl font-bold">M-Insight 360</h1>
        <p className="text-sm opacity-80">Trợ lý AI Thẩm định tín dụng MSB</p>
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
              className={`px-4 py-2 rounded font-semibold ${
                tab === t ? "bg-msb-navy text-white" : "bg-white text-msb-navy"
              }`}
            >
              {TAB_LABELS[t]}
            </button>
          ))}
        </div>

        <AssessmentForm agentType={tab} onResult={setResult} />
        {result && (tab === "crosssell" ? <CrossSellPanel result={result} /> : <ResultPanel result={result} />)}
      </div>
    </main>
  );
}
