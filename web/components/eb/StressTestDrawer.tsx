"use client";

import { AssessmentResult } from "@/lib/api";

// Stub for Task 20's typecheck — replaced with the full drawer in Task 21.
export function StressTestDrawer({
  open,
  onClose,
  result,
}: {
  open: boolean;
  onClose: () => void;
  result: AssessmentResult;
}) {
  void result;
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div className="w-full sm:w-[560px] max-w-full h-full bg-white p-6" onClick={(e) => e.stopPropagation()} />
    </div>
  );
}
