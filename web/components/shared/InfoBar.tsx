import { AlertTriangle, CheckCircle2 } from "lucide-react";

export type InfoBarItem = {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
};

export type BannerTone = "amber" | "green" | "red";

const BANNER_STYLE: Record<BannerTone, string> = {
  amber: "bg-amber-50 border-amber-300 text-amber-900",
  green: "bg-green-50 border-green-300 text-green-900",
  red: "bg-red-50 border-red-300 text-red-900",
};

export function InfoBar({
  items,
  banner,
  bannerTone = "amber",
}: {
  items: InfoBarItem[];
  banner?: string | null;
  bannerTone?: BannerTone;
}) {
  const BannerIcon = bannerTone === "green" ? CheckCircle2 : AlertTriangle;
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 space-y-3">
      <div className="flex flex-wrap gap-x-8 gap-y-3 text-sm">
        {items.map(({ icon: Icon, label, value }) => (
          <div key={label} className="flex items-center gap-2">
            <Icon className="h-4 w-4 text-gray-400 shrink-0" />
            <div>
              <span className="text-gray-500 text-xs">{label}</span>
              <p className="font-semibold text-msb-navy">{value}</p>
            </div>
          </div>
        ))}
      </div>
      {banner && (
        <div className={`flex items-start gap-2 rounded-lg border p-3 text-sm font-semibold ${BANNER_STYLE[bannerTone]}`}>
          <BannerIcon className="h-4 w-4 mt-0.5 shrink-0" />
          {banner}
        </div>
      )}
    </div>
  );
}
