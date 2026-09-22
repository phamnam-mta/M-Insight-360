"use client";

import { useState } from "react";
import {
  AlertTriangle,
  Badge as BadgeIcon,
  Ban,
  Building2,
  CheckCircle2,
  ClipboardCopy,
  Clock,
  Download,
  FileText,
  Info,
  Layers,
  Mail,
  Users,
} from "lucide-react";
import {
  AssessmentResult,
  CrossSellEvidenceBlock,
  CrossSellOpportunity,
  CrossSellPartnerRow,
} from "@/lib/api";
import { InfoBar, InfoBarItem } from "./shared/InfoBar";
import { SectionHeader } from "./shared/SectionHeader";

function formatVnd(n: number | undefined | null): string {
  if (n === undefined || n === null) return "—";
  return n.toLocaleString("vi-VN") + " VND";
}

const BADGE_TONE: Record<string, string> = {
  ok: "bg-emerald-50 text-emerald-700",
  warn: "bg-amber-50 text-amber-700",
  err: "bg-red-50 text-red-700",
  info: "bg-slate-100 text-slate-600",
  na: "bg-slate-100 text-slate-500",
};

const PRIORITY_TONE: Record<string, { border: string; bg: string; chip: string; amount: string }> = {
  P1: { border: "border-red-300", bg: "bg-gradient-to-br from-white to-red-50/60", chip: "bg-red-50 text-red-600", amount: "text-msb-orange" },
  P2: { border: "border-orange-200", bg: "bg-white", chip: "bg-orange-50 text-orange-600", amount: "text-msb-navy" },
  P3: { border: "border-blue-200", bg: "bg-white", chip: "bg-blue-50 text-blue-600", amount: "text-msb-navy" },
  "P-NA": { border: "border-gray-200", bg: "bg-white opacity-80", chip: "bg-gray-100 text-gray-500", amount: "text-gray-400" },
};

function CopyButton({ text, label = "Sao chép" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1800);
        } catch {
          // Clipboard API unavailable (insecure context, permissions) — the
          // scenario text is already visible on screen for manual copy.
        }
      }}
      className="absolute top-2.5 right-2.5 inline-flex items-center gap-1 text-[11px] font-semibold border border-gray-200 bg-white rounded-md px-2.5 py-1 text-gray-500 hover:border-msb-orange hover:text-msb-orange"
    >
      <ClipboardCopy className="h-3 w-3" />
      {copied ? "Đã sao chép" : label}
    </button>
  );
}

function OpportunityCard({ opp }: { opp: CrossSellOpportunity }) {
  const [openPanel, setOpenPanel] = useState<"detail" | "scenario" | null>(null);
  const tone = PRIORITY_TONE[opp.priority] ?? PRIORITY_TONE["P-NA"];
  const isP1 = opp.priority === "P1";

  return (
    <div
      className={`bg-white rounded-2xl border overflow-hidden flex flex-col transition hover:shadow-md ${tone.border} ${tone.bg} ${
        isP1 ? "md:col-span-2" : ""
      }`}
    >
      <div className="p-5 pb-4">
        <div className="flex flex-wrap gap-1.5 mb-2.5">
          <span className={`text-[10.5px] font-bold px-2.5 py-1 rounded-md ${tone.chip}`}>{opp.priority}</span>
          <span className="text-[10.5px] font-bold px-2.5 py-1 rounded-md bg-gray-100 text-gray-500">{opp.segment}</span>
          {opp.confidence && (
            <span className="text-[10.5px] font-bold px-2.5 py-1 rounded-md bg-white border border-gray-200 text-gray-500">
              Confidence {opp.confidence}
            </span>
          )}
        </div>
        <h3 className="text-[15px] font-bold text-msb-navy leading-snug">{opp.san_pham}</h3>
        <div className={`font-bold tracking-tight mt-2.5 leading-none ${tone.amount} ${isP1 ? "text-[38px]" : "text-[28px]"} ${opp.deal_size ? "" : "text-lg text-gray-400"}`}>
          {opp.deal_size_headline}
        </div>
        {opp.deal_size_exact && <div className="text-[11px] text-gray-400 mt-1 tabular-nums">{opp.deal_size_exact}</div>}
        <div className="text-[13.5px] text-gray-600 mt-3 pt-3 border-t border-gray-100">{opp.signal_1dong}</div>
      </div>

      <div className="mt-auto border-t border-gray-100 flex">
        <button
          type="button"
          onClick={() => setOpenPanel(openPanel === "detail" ? null : "detail")}
          className={`flex-1 py-3 text-[12.5px] font-semibold border-r border-gray-100 hover:bg-orange-50/60 hover:text-msb-orange ${
            openPanel === "detail" ? "text-msb-orange bg-orange-50/60" : "text-gray-600"
          }`}
        >
          Căn cứ &amp; bằng chứng
        </button>
        {opp.kich_ban.length > 0 && (
          <button
            type="button"
            onClick={() => setOpenPanel(openPanel === "scenario" ? null : "scenario")}
            className={`flex-1 py-3 text-[12.5px] font-semibold hover:bg-orange-50/60 hover:text-msb-orange ${
              openPanel === "scenario" ? "text-msb-orange bg-orange-50/60" : "text-gray-600"
            }`}
          >
            Kịch bản tiếp cận
          </button>
        )}
      </div>

      {openPanel === "detail" && (
        <div className="p-5 bg-gray-50/60 border-t border-gray-100 text-[13px] space-y-3">
          {opp.chi_tiet.map((block, i) => (
            <div key={i}>
              <dt className="text-[10.5px] font-bold text-gray-400 uppercase tracking-wide">{block.tieu_de}</dt>
              <dd className="mt-1 text-gray-600 leading-relaxed">{block.noi_dung}</dd>
            </div>
          ))}
          {opp.ly_do_confidence && (
            <div>
              <dt className="text-[10.5px] font-bold text-gray-400 uppercase tracking-wide">Confidence</dt>
              <dd className="mt-1 text-gray-600 leading-relaxed">
                {opp.confidence} — {opp.ly_do_confidence}
              </dd>
            </div>
          )}
          {opp.canh_bao.map((w, i) => (
            <div key={i} className="flex items-start gap-2 bg-amber-50 text-amber-800 rounded-lg px-3.5 py-2.5 text-[12.5px]">
              <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              {w}
            </div>
          ))}
        </div>
      )}

      {openPanel === "scenario" && (
        <div className="p-5 bg-gray-50/60 border-t border-gray-100 space-y-3">
          {opp.kich_ban.map((s, i) => (
            <div key={i} className="relative bg-white border border-gray-200 rounded-xl p-4 pr-20">
              <CopyButton text={s.noi_dung} />
              <div className="text-[10.5px] font-bold uppercase tracking-wide text-msb-orange">
                Kịch bản {s.loai} · nói với {s.doi_tuong}
              </div>
              <p className="mt-2 text-[13px] leading-relaxed text-gray-600">{s.noi_dung}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PartnerTable({ partners }: { partners: CrossSellPartnerRow[] }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 overflow-x-auto">
      <table className="w-full text-[13px] border-collapse min-w-[640px]">
        <thead>
          <tr className="text-left bg-gray-50/70 text-[10.5px] uppercase tracking-wide text-gray-400 font-bold">
            <th className="py-3 px-4">#</th>
            <th className="py-3 px-4">Đối tác</th>
            <th className="py-3 px-4">Chiều</th>
            <th className="py-3 px-4 text-right">GD</th>
            <th className="py-3 px-4 text-right">Tổng giá trị</th>
            <th className="py-3 px-4 text-right">Điểm</th>
            <th className="py-3 px-4">Trạng thái</th>
          </tr>
        </thead>
        <tbody>
          {partners.map((p, i) => {
            const statusLabel = p.nhan_canh_bao || p.trang_thai;
            const statusTone = p.nhan_canh_bao
              ? p.nhan_canh_bao.includes("RB")
                ? "bg-emerald-50 text-emerald-700"
                : "bg-red-50 text-red-600"
              : "bg-slate-100 text-slate-500";
            return (
              <tr key={i} className="border-b border-gray-50 last:border-0 hover:bg-gray-50/60">
                <td className="py-2.5 px-4 text-gray-400">{i + 1}</td>
                <td className="py-2.5 px-4 font-semibold text-msb-navy">{p.ten}</td>
                <td className="py-2.5 px-4 text-gray-600">{p.chieu}</td>
                <td className="py-2.5 px-4 text-right tabular-nums">{p.so_gd}</td>
                <td className="py-2.5 px-4 text-right tabular-nums">{formatVnd(p.tong_gt)}</td>
                <td className="py-2.5 px-4 text-right">
                  <span
                    className={`inline-block min-w-[36px] text-center font-bold text-xs px-2 py-1 rounded-md ${
                      p.diem >= 90 ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-600"
                    }`}
                  >
                    {p.diem}
                  </span>
                </td>
                <td className="py-2.5 px-4">
                  <span className={`text-[11px] font-semibold px-2.5 py-1 rounded-md ${statusTone}`}>{statusLabel}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function EvidenceAccordion({ block }: { block: CrossSellEvidenceBlock }) {
  const entries = Object.entries(block.noi_dung ?? {});
  return (
    <details className="bg-white rounded-xl border border-gray-100 overflow-hidden group">
      <summary className="px-5 py-3.5 cursor-pointer font-semibold text-sm flex items-center gap-3 list-none [&::-webkit-details-marker]:hidden">
        <span>{block.tieu_de}</span>
        <span className="ml-auto text-xs font-normal text-gray-400">{block.tom_tat}</span>
      </summary>
      {entries.length > 0 && (
        <div className="px-5 pb-4 text-[13px] text-gray-600 space-y-1.5">
          {entries.map(([k, v]) => (
            <div key={k} className="flex justify-between gap-4 border-b border-gray-50 py-1.5 last:border-0">
              <span className="text-gray-400 shrink-0">{k}</span>
              <span className="text-right font-medium text-msb-navy break-all">
                {typeof v === "object" ? JSON.stringify(v) : String(v)}
              </span>
            </div>
          ))}
        </div>
      )}
    </details>
  );
}

export default function CrossSellPanel({ result }: { result: AssessmentResult }) {
  const [mailCopied, setMailCopied] = useState(false);

  const hoSo = result.ho_so;
  const badges = result.badges ?? [];
  const kpi = result.kpi ?? [];
  const coHoi = result.co_hoi ?? [];
  const doiTac = result.doi_tac;
  const evidence = result.evidence ?? {};
  const banGiao = result.ban_giao;

  if (!hoSo || kpi.length === 0) {
    // Old-shape or malformed response (e.g. before this schema shipped) —
    // nothing meaningful to render.
    return null;
  }

  const infoItems: InfoBarItem[] = [
    { icon: BadgeIcon, label: "Mã hồ sơ", value: result.ma_lo ?? "—" },
    { icon: Building2, label: "Khách hàng", value: hoSo.ten_kh },
    { icon: FileText, label: "MST", value: hoSo.mst },
    { icon: Clock, label: "Kỳ sao kê", value: hoSo.ky_sao_ke },
    { icon: Layers, label: "Số giao dịch", value: `${hoSo.so_gd} · ${hoSo.so_ngan_hang} ngân hàng` },
  ];

  async function copyMail() {
    if (!banGiao?.noi_dung_mail) return;
    try {
      await navigator.clipboard.writeText(banGiao.noi_dung_mail);
      setMailCopied(true);
      setTimeout(() => setMailCopied(false), 1800);
    } catch {
      // ignore — clipboard unavailable
    }
  }

  function downloadJson() {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${result.ma_lo ?? "crosssell"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6 mt-6">
      <InfoBar items={infoItems} />

      {(badges.length > 0 || hoSo.nganh_suy_doan) && (
        <div className="flex flex-wrap gap-2">
          {badges.map((b, i) => (
            <span key={i} className={`text-xs font-semibold px-3 py-1.5 rounded-lg ${BADGE_TONE[b.loai] ?? BADGE_TONE.na}`}>
              {b.nhan}
            </span>
          ))}
          {hoSo.nganh_suy_doan && (
            <span className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-slate-100 text-slate-500">{hoSo.nganh_suy_doan}</span>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
        {kpi.map((k, i) => (
          <div
            key={i}
            className={`rounded-2xl border p-4 ${
              k.nhan_manh ? "bg-gradient-to-br from-white to-orange-50/70 border-orange-200" : "bg-white border-gray-100"
            }`}
          >
            <div className="text-[11px] uppercase tracking-wide text-gray-400 font-bold">{k.nhan}</div>
            <div className={`text-[26px] font-bold tracking-tight mt-1 leading-tight ${k.nhan_manh ? "text-msb-orange" : "text-msb-navy"}`}>
              {k.gia_tri}
            </div>
            {k.phu && <div className="text-xs text-gray-400 mt-1">{k.phu}</div>}
          </div>
        ))}
      </div>

      {result.status === "blocked" && (
        <div className="flex items-start gap-2 rounded-lg border border-red-300 bg-red-50 text-red-900 p-3 text-sm font-semibold">
          <Ban className="h-4 w-4 mt-0.5 shrink-0" />
          Hồ sơ bị chặn ở bước kiểm tra tính toàn vẹn chứng từ — xem chi tiết trong khối bằng chứng &quot;Pre-check chứng từ&quot; bên dưới.
        </div>
      )}

      {coHoi.length > 0 && (
        <section>
          <SectionHeader
            icon={Layers}
            title="Cơ hội bán chéo"
            subtitle={`${coHoi.length} cơ hội · sắp theo deal size · bấm để xem công thức`}
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 mt-3">
            {coHoi.map((c, i) => (
              <OpportunityCard key={c.rule_id ?? i} opp={c} />
            ))}
          </div>
        </section>
      )}

      {doiTac && doiTac.danh_sach.length > 0 && (
        <section>
          <SectionHeader icon={Users} title="Đối tác tiềm năng" subtitle={`${doiTac.danh_sach.length} đối tác · lọc ≥ 3 GD và ≥ 500 triệu`} />
          <div className="mt-3 space-y-3">
            <div className="flex items-start gap-2 bg-amber-50 text-amber-800 rounded-xl px-4 py-3 text-[12.8px] leading-relaxed">
              <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
              <span>
                <b>LƯU Ý:</b> {doiTac.canh_bao_cif}
              </span>
            </div>
            <PartnerTable partners={doiTac.danh_sach} />
          </div>
        </section>
      )}

      {Object.keys(evidence).length > 0 && (
        <section>
          <SectionHeader icon={Info} title="Bằng chứng & kiểm toán" subtitle="Gập sẵn — mở khi cần đối chiếu" />
          <div className="mt-3 space-y-2.5">
            {Object.entries(evidence).map(([key, block]) => (
              <EvidenceAccordion key={key} block={block} />
            ))}
          </div>
        </section>
      )}

      {result.warnings && result.warnings.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-2">
          <SectionHeader icon={AlertTriangle} title="Cảnh báo hệ thống" />
          <ul className="text-sm list-disc list-inside text-gray-600">
            {result.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {result.extraction_warnings && result.extraction_warnings.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-2">
          <SectionHeader icon={FileText} title="Cảnh báo trích xuất dữ liệu" />
          <ul className="text-sm list-disc list-inside text-gray-600">
            {result.extraction_warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {banGiao && (
        <div className="bg-white rounded-2xl border border-gray-100 p-6">
          <h3 className="text-base font-bold text-msb-navy">Bàn giao cho RM</h3>
          <p className="text-xs text-gray-400 mt-1">
            Nội dung do AI sinh — khâu chuyển phát do Power Automate đảm nhiệm khi vận hành thật.
          </p>
          <div className="flex flex-wrap gap-2.5 mt-4">
            <button
              type="button"
              onClick={copyMail}
              className="inline-flex items-center gap-2 bg-msb-orange text-white text-sm font-semibold px-4 py-2.5 rounded-lg hover:brightness-105"
            >
              <Mail className="h-4 w-4" />
              {mailCopied ? "Đã sao chép" : "Sao chép nội dung mail"}
            </button>
            <button
              type="button"
              onClick={downloadJson}
              className="inline-flex items-center gap-2 bg-white text-msb-navy text-sm font-semibold px-4 py-2.5 rounded-lg border border-gray-200 hover:bg-gray-50"
            >
              <Download className="h-4 w-4" />
              Tải JSON kết quả
            </button>
            <button
              type="button"
              disabled
              title={banGiao.ghi_chu_plumbing}
              className="inline-flex items-center gap-2 bg-gray-50 text-gray-400 text-sm font-semibold px-4 py-2.5 rounded-lg border border-dashed border-gray-200 cursor-not-allowed"
            >
              <CheckCircle2 className="h-4 w-4" />
              Gửi Outlook · Ghi SharePoint
            </button>
          </div>
          <p className="text-xs text-gray-400 bg-gray-50/70 border border-gray-100 rounded-lg px-4 py-3 mt-4 leading-relaxed">
            <b>Vì sao hai chức năng cuối bị khoá:</b> {banGiao.ghi_chu_plumbing}
          </p>
        </div>
      )}
    </div>
  );
}
