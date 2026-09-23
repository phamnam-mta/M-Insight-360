"use client";

import { Lock } from "lucide-react";

const PLACEHOLDERS = [
  { title: "Nợ thuế", body: "Chờ kết nối Tổng cục Thuế — chưa khả dụng." },
  { title: "Mua sắm công", body: "Chờ kết nối Cổng đấu thầu quốc gia — chưa khả dụng." },
  { title: "Trinh sát dữ liệu công khai", body: "Chờ kết nối nguồn dữ liệu công khai — chưa khả dụng." },
];

export function LockedPlaceholders() {
  return (
    <div className="space-y-2.5">
      {PLACEHOLDERS.map((p) => (
        <div key={p.title} className="bg-gray-50 rounded-lg border border-gray-100 p-3.5 flex items-start gap-2.5">
          <Lock className="h-3.5 w-3.5 text-gray-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-gray-500">{p.title}</p>
            <p className="text-xs text-gray-400 mt-0.5">{p.body}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
