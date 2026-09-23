"use client";

import { useEffect, useState } from "react";
import { X, MessageCircle } from "lucide-react";
import { getZaloQrStatus } from "@/lib/rb-portal-api";

export function ZaloBotModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [status, setStatus] = useState<{ status: string; qr_url: string | null; message: string } | null>(null);

  useEffect(() => {
    if (open) getZaloQrStatus().then(setStatus).catch(() => setStatus(null));
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div className="bg-white rounded-xl p-6 max-w-sm w-full mx-4 space-y-3 text-center" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-end">
          <button onClick={onClose}><X className="h-5 w-5 text-gray-400" /></button>
        </div>
        <MessageCircle className="h-10 w-10 text-msb-navy mx-auto" />
        <h3 className="text-sm font-semibold text-msb-navy">Trợ lý Zalo M-Insight360</h3>
        {status?.qr_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={status.qr_url} alt="Zalo QR" className="mx-auto w-40 h-40" />
        ) : (
          <div className="mx-auto w-40 h-40 rounded-lg bg-gray-100 flex items-center justify-center text-xs text-gray-400 px-3">
            Chưa có mã QR
          </div>
        )}
        <p className="text-xs text-gray-500">{status?.message ?? "Đang tải..."}</p>
      </div>
    </div>
  );
}
