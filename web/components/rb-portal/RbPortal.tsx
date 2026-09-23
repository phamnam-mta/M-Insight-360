"use client";

import { useState } from "react";
import {
  Banknote, ClipboardCheck, FileText, FolderOpen, Home, IdCard, Landmark,
  ListChecks, PiggyBank, ScrollText, UploadCloud, MessageCircle,
} from "lucide-react";
import { OverviewTab } from "./tabs/OverviewTab";
import { CustomerTab } from "./tabs/CustomerTab";
import { LegalTab } from "./tabs/LegalTab";
import { IncomeTab } from "./tabs/IncomeTab";
import { LoanTab } from "./tabs/LoanTab";
import { CollateralTab } from "./tabs/CollateralTab";
import { OtherDocsTab } from "./tabs/OtherDocsTab";
import { ZaloBotModal } from "./ZaloBotModal";

const TABS = [
  { key: "overview", label: "Tổng quan", icon: Home },
  { key: "customer", label: "Hồ sơ khách hàng", icon: IdCard },
  { key: "legal", label: "Pháp lý", icon: ScrollText },
  { key: "income", label: "Nguồn thu", icon: Banknote },
  { key: "loan", label: "Khoản vay", icon: Landmark },
  { key: "collateral", label: "Tài sản bảo đảm", icon: PiggyBank },
  { key: "other", label: "Hồ sơ khác", icon: FolderOpen },
  { key: "documents", label: "Tải lên chứng từ", icon: UploadCloud },
  { key: "assessment", label: "Thẩm định", icon: ClipboardCheck },
  { key: "summary", label: "Tổng hợp", icon: FileText },
  { key: "history", label: "Lịch sử", icon: ListChecks },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function RbPortal() {
  const [caseId, setCaseId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [zaloOpen, setZaloOpen] = useState(false);

  function selectCase(id: string) {
    setCaseId(id);
    setActiveTab("customer");
  }

  return (
    <div className="mt-6 grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-5">
      <aside className="bg-white rounded-xl border border-gray-100 p-3 space-y-1 h-fit">
        {TABS.map(({ key, label, icon: Icon }) => {
          const disabled = key !== "overview" && !caseId;
          return (
            <button
              key={key}
              disabled={disabled}
              onClick={() => setActiveTab(key)}
              className={`w-full flex items-center gap-2.5 text-left text-sm px-3 py-2 rounded-lg transition-colors ${
                activeTab === key ? "bg-msb-orange text-white" : "text-msb-navy hover:bg-msb-bg"
              } ${disabled ? "opacity-40 cursor-not-allowed" : ""}`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </button>
          );
        })}
        <button
          onClick={() => setZaloOpen(true)}
          className="w-full flex items-center gap-2.5 text-left text-sm px-3 py-2 rounded-lg text-msb-navy hover:bg-msb-bg mt-2 border-t border-gray-100 pt-3"
        >
          <MessageCircle className="h-4 w-4 shrink-0" />
          Zalo Chat Bot
        </button>
      </aside>

      <div className="min-w-0">
        {activeTab === "overview" && <OverviewTab onSelectCase={selectCase} />}
        {activeTab !== "overview" && !caseId && (
          <p className="text-sm text-gray-500">Chọn hoặc tạo hồ sơ ở tab Tổng quan trước.</p>
        )}
        {activeTab === "customer" && caseId && <CustomerTab caseId={caseId} />}
        {activeTab === "legal" && caseId && <LegalTab caseId={caseId} />}
        {activeTab === "income" && caseId && <IncomeTab caseId={caseId} />}
        {activeTab === "loan" && caseId && <LoanTab caseId={caseId} />}
        {activeTab === "collateral" && caseId && <CollateralTab caseId={caseId} />}
        {activeTab === "other" && caseId && <OtherDocsTab caseId={caseId} />}
        {/* Tasks 16-19 render the remaining tabs here */}
      </div>

      <ZaloBotModal open={zaloOpen} onClose={() => setZaloOpen(false)} />
    </div>
  );
}
