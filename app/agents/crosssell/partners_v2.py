"""Danh sách đối tác tiềm năng — chấm điểm + trạng thái CIF theo AGENT_CrossSell v3.1 §Danh sách đối tác.

Toàn bộ đối tác luôn mang trạng thái "Chua kiem tra CIF" — hệ thống không thể
xác định đối tác có phải KH MSB hay không (tên tự gõ, bảng công nợ không có
MST). Không bao giờ gắn nhãn "đủ điều kiện".
"""

import re
import unicodedata
from dataclasses import dataclass

CIF_STATUS = "Chua kiem tra CIF"
CIF_WARNING = (
    "LƯU Ý: Danh sách dưới đây được lọc từ giao dịch trên sao kê/bảng công nợ. Hệ thống CHƯA kiểm "
    "tra được các đối tác này đã là khách hàng MSB hay chưa. Trước khi tiếp cận, RM vui lòng tra CIF "
    "trên hệ thống core để tránh trùng khách đang có RM khác phụ trách. Nếu đã có CIF, chuyển hướng "
    "sang bán chéo thay vì chào mở mới."
)

_PERSON_PREFIXES = ("CA NHAN", "ONG ", "BA ", "MR ", "MRS ")
_JUNK_SUBSTRINGS = ("DON VI THU HUONG", "DON VI CHUYEN", "NGUOI THU HUONG", "SO DU", "BALANCE", "TOTAL")
# "TONG"/"CONG" alone mark a balance-summary row ("CỘNG", "TỔNG CỘNG") per spec
# §0B, but matching them as a substring also nukes every ordinary business name
# starting with "CÔNG TY" (company) or "TỔNG CÔNG TY" (corporation) — §0B's own
# heading is "CẨN THẬN KẺO LỌC OAN" (careful not to wrongly filter). Only treat
# them as junk when NOT immediately followed by "TY"/"CONG".
_SUMMARY_ROW_WORDS = ("TONG", "CONG")


def _strip_accents_upper(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c)).upper()


def is_junk_partner_name(name: str) -> bool:
    upper = _strip_accents_upper(name.strip())
    if not upper or len(upper) < 4:
        return True
    if upper.replace(" ", "").isdigit():
        return True
    # "TK" must never be filtered — in construction-company names TK means
    # THIẾT KẾ (design), not a balance/account-summary row.
    if any(p in upper for p in _JUNK_SUBSTRINGS):
        return True
    words = upper.split()
    if words and words[0] in _SUMMARY_ROW_WORDS and "CONG TY" not in upper:
        return True
    return False


def is_person_partner(name: str) -> bool:
    upper = _strip_accents_upper(name.strip())
    return upper.startswith(_PERSON_PREFIXES)


@dataclass
class PartnerRow:
    ten: str
    chieu: str  # "Dau ra (Nguoi mua)" | "Dau vao (NCC)" | "Ca hai"
    so_gd: int
    tong_gt: float
    diem: float
    trang_thai: str = CIF_STATUS
    co_canh_bao: bool = False
    nhan_canh_bao: str | None = None
    sp_de_xuat: str = ""


def score_partner(total_value: float, max_partner_value: float, months_active: int, total_period_months: int, freq_per_month: float) -> float:
    diem = 40 * (total_value / max_partner_value if max_partner_value else 0)
    diem += 30 * min(freq_per_month / 4, 1)
    diem += 20 * (months_active / total_period_months if total_period_months else 0)
    return round(diem, 1)


def build_partner_row(
    name: str, direction: str, transaction_count: int, total_value: float,
    score: float, related_party_warning: str | None = None,
) -> PartnerRow:
    is_person = is_person_partner(name)
    if is_person:
        nhan_canh_bao = "Cá nhân → sản phẩm RB"
        sp = "RB: TK thanh toán, thẻ, tiền gửi (KHÔNG chào SCF/L/C)"
        co_canh_bao = True
    elif related_party_warning:
        nhan_canh_bao = related_party_warning
        sp = "Tạm dừng — xác minh quan hệ sở hữu trước khi chào SCF/L/C"
        co_canh_bao = True
    else:
        nhan_canh_bao = None
        co_canh_bao = False
        sp = {
            "Dau ra (Nguoi mua)": "Tài trợ khoản phải thu, Điều 7",
            "Dau vao (NCC)": "SCF, L/C, bảo lãnh thanh toán",
            "Ca hai": "Tài trợ khoản phải thu, Điều 7 · SCF, L/C, bảo lãnh thanh toán",
        }.get(direction, "")

    return PartnerRow(
        ten=name, chieu=direction, so_gd=transaction_count, tong_gt=round(total_value),
        diem=score, trang_thai=CIF_STATUS, co_canh_bao=co_canh_bao,
        nhan_canh_bao=nhan_canh_bao, sp_de_xuat=sp,
    )
