"""Shared data model for the v3.1 output — one card per cross-sell opportunity.

Mirrors OUTPUT FORMAT §C `co_hoi[]` in AGENT_CrossSell_INSTRUCTION_FINAL.md.
"""

from dataclasses import dataclass, field


@dataclass
class DetailBlock:
    tieu_de: str
    noi_dung: str


@dataclass
class Scenario:
    loai: str  # "A" | "B"
    doi_tuong: str
    noi_dung: str


@dataclass
class Opportunity:
    rule_id: str
    san_pham: str
    segment: str  # "EB" | "RB"
    deal_size: int | None  # VND, rounded integer; None only when priority == "P-NA"
    deal_size_headline: str
    deal_size_exact: str | None
    priority: str  # "P1" | "P2" | "P3" | "P-NA"
    confidence: str | None  # "H" | "M" | "L" | None when P-NA
    ly_do_confidence: str | None
    signal_1dong: str
    chi_tiet: list[DetailBlock] = field(default_factory=list)
    canh_bao: list[str] = field(default_factory=list)
    kich_ban: list[Scenario] = field(default_factory=list)


def format_deal_size_headline(amount: float | None) -> str:
    """Spec §D1: rounded-for-scanning headline, always paired with the exact figure."""
    if amount is None:
        return "Chưa xác định"
    a = abs(amount)
    if a >= 1_000_000_000_000:
        val = amount / 1_000_000_000_000
        return f"{val:.1f}".replace(".", ",") + " nghìn tỷ"
    if a >= 1_000_000_000:
        val = amount / 1_000_000_000
        return f"{val:.1f}".replace(".", ",") + " tỷ" if val >= 10 else f"{val:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " tỷ"
    if a >= 1_000_000:
        val = round(amount / 1_000_000)
        return f"{val} triệu"
    return f"{round(amount):,}".replace(",", ".") + " VND"


def format_deal_size_exact(amount: int | None) -> str | None:
    if amount is None:
        return None
    return f"{amount:,}".replace(",", ".")


def priority_from_deal_size(deal_size: int | None) -> str:
    """Spec §CHẤM PRIORITY & CONFIDENCE."""
    if deal_size is None:
        return "P-NA"
    if deal_size >= 20_000_000_000:
        return "P1"
    if deal_size >= 5_000_000_000:
        return "P2"
    return "P3"


def confidence_with_cap(base: str, cap: str) -> str:
    """Confidence can only be lowered by a cap, never raised. Order: H > M > L."""
    order = {"H": 2, "M": 1, "L": 0}
    return base if order[base] <= order[cap] else cap
