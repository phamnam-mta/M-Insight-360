"use client";

export function ZaloBotModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div className="bg-white rounded-xl p-6 max-w-sm w-full mx-4" onClick={(e) => e.stopPropagation()}>
        <p className="text-sm text-gray-500">Đang tải...</p>
      </div>
    </div>
  );
}
