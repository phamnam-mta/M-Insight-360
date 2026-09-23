"""Fills the real MB02a/QT.RR.037 bank template (docs/templates/
template_MB02a.docx) by label search (instruction §S2: "dò theo nhãn
dòng, không bám số thứ tự bảng"), never by hard-coded table/cell
coordinates — a future MSB template edit that shifts a table index must
not silently mis-fill a cell."""

import io
import unicodedata
from pathlib import Path

import docx
from docx.table import Table, _Cell

_TEMPLATE_PATH = Path(__file__).resolve().parents[3] / "docs" / "templates" / "template_MB02a.docx"

_MISSING_PLACEHOLDER = "[Chưa xác định từ hồ sơ tải lên]"


def _nfc(text: str) -> str:
    """The real template mixes Unicode-normalization forms for Vietnamese
    diacritics within the same document (some precomposed, e.g. 'Ô' as one
    codepoint; others decomposed, e.g. 'Á' as 'A' + a combining accent) —
    confirmed by direct inspection of table 2's own heading text. Every
    label comparison in this module must normalize both sides through this
    function first, or an otherwise-correct label string silently fails
    to match."""
    return unicodedata.normalize("NFC", text)

DISCLAIMER = "Khuyến nghị sơ bộ từ dữ liệu BCTC — cần phê duyệt theo quy trình tín dụng MSB."


def _format_number_vn(value: float | None, decimals: int) -> str:
    """S1.2 — Vietnamese locale: '.' thousands, ',' decimal."""
    if value is None:
        return _MISSING_PLACEHOLDER
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _set_cell_text(cell: _Cell, text: str) -> None:
    paragraph = cell.paragraphs[0]
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(text)
    for extra_paragraph in cell.paragraphs[1:]:
        for run in extra_paragraph.runs:
            run.text = ""


def _find_row_by_label(table: Table, label: str, label_col: int = 0):
    target = _nfc(label)
    for row in table.rows:
        if _nfc(row.cells[label_col].text.strip()) == target:
            return row
    return None


def _fill_cell(
    table: Table, row_label: str, col_index: int, value_vnd: float | None,
    field_code: str, fill_log: list[dict], *, decimals: int = 0, unit_convert: bool = True,
    label_col: int = 0,
) -> None:
    row = _find_row_by_label(table, row_label, label_col)
    if row is None:
        fill_log.append({"field_code": field_code, "row_label": row_label, "status": "ROW_NOT_FOUND"})
        return
    if value_vnd is None:
        text = _MISSING_PLACEHOLDER
        status = "MISSING"
    else:
        display_value = value_vnd / 1_000_000 if unit_convert else value_vnd
        text = _format_number_vn(display_value, decimals)
        status = "FILLED"
    _set_cell_text(row.cells[col_index], text)
    fill_log.append({"field_code": field_code, "row_label": row_label, "value_vnd": value_vnd, "status": status})


def _find_table_after_heading(document, heading_text: str) -> Table | None:
    target = _nfc(heading_text)
    body_children = list(document.element.body.iterchildren())
    for i, child in enumerate(body_children):
        if child.tag.endswith("}p"):
            text = "".join(node.text or "" for node in child.iter() if node.tag.endswith("}t"))
            if target in _nfc(text.strip()):
                for later in body_children[i + 1:]:
                    if later.tag.endswith("}tbl"):
                        return Table(later, document)
                    if later.tag.endswith("}p"):
                        continue
        continue
    return None


def _find_table_by_own_first_cell(document, heading_text: str) -> Table | None:
    """Some template tables carry their section heading as a merged row
    INSIDE the table itself (e.g. table 2's "THÔNG TIN KHÁCH HÀNG"), not a
    preceding paragraph — _find_table_after_heading doesn't match those."""
    target = _nfc(heading_text)
    for table in document.tables:
        if table.rows and _nfc(table.rows[0].cells[0].text.strip()) == target:
            return table
    return None


def _fill_s2_1_customer_info(document, computed: dict, fill_log: list[dict]) -> None:
    table = _find_table_by_own_first_cell(document, "THÔNG TIN KHÁCH HÀNG")
    if table is None:
        fill_log.append({"field_code": "S2.1", "status": "TABLE_NOT_FOUND"})
        return
    profile = computed.get("customer_profile") or {}
    customer_name = profile.get("customer_name")
    row = _find_row_by_label(table, "Tên Doanh nghiệp")
    if row is not None:
        _set_cell_text(row.cells[1], customer_name or _MISSING_PLACEHOLDER)
        fill_log.append({"field_code": "customer_name", "row_label": "Tên Doanh nghiệp", "status": "FILLED" if customer_name else "MISSING"})

    charter_capital = (computed.get("financial_inputs") or {}).get("charter_capital_vnd")
    row = _find_row_by_label(table, "Vốn điều lệ")
    if row is not None:
        amount = _format_number_vn(charter_capital / 1_000_000 if charter_capital is not None else None, 0)
        _set_cell_text(
            row.cells[1],
            f"Vốn đăng ký: {amount} triệu đồng (theo CĐKT, cần đối chiếu ĐKKD) / Vốn thực góp: …. triệu đồng (tính đến ngày…..)",
        )
        fill_log.append({"field_code": "BS_CHARTER_CAPITAL", "row_label": "Vốn điều lệ", "value_vnd": charter_capital, "status": "FILLED" if charter_capital is not None else "MISSING"})


def _metric_value(computed: dict, metric_name: str) -> float | None:
    metric = (computed.get("credit_engine") or {}).get(metric_name)
    if not isinstance(metric, dict) or metric.get("status") != "OK":
        return None
    return metric.get("value")


def _fill_s2_2_general_metrics(document, computed: dict, fill_log: list[dict]) -> None:
    table = _find_table_after_heading(document, "Các chỉ tiêu tài chính tổng quát")
    if table is None:
        fill_log.append({"field_code": "S2.2", "status": "TABLE_NOT_FOUND"})
        return
    fi = computed.get("financial_inputs") or {}
    equity = fi.get("equity_vnd")
    total_borrowings = _metric_value(computed, "total_borrowings")
    revenue = fi.get("net_revenue_vnd")
    pbt = fi.get("pbt_vnd")
    interest = fi.get("interest_expense_vnd")
    ebit = None
    if pbt is not None and interest is not None:
        ebit = pbt + interest
    total_assets = None
    if fi.get("current_assets_vnd") is not None and fi.get("non_current_assets_vnd") is not None:
        total_assets = fi["current_assets_vnd"] + fi["non_current_assets_vnd"]
    leverage = round(total_borrowings / equity, 4) if total_borrowings is not None and equity else None
    opm = round(ebit / revenue * 100, 2) if ebit is not None and revenue else None

    _fill_cell(table, "- Tổng doanh thu (triệu đồng)", 3, revenue, "IS_REVENUE", fill_log)
    _fill_cell(table, "- Tổng tài sản (triệu đồng)", 3, total_assets, "BS_TOTAL_ASSETS", fill_log)
    _fill_cell(table, "- Vốn CSH (triệu đồng)", 3, equity, "BS_EQUITY", fill_log)
    _fill_cell(table, "- Lợi nhuận sau thuế (triệu đồng)", 3, fi.get("pat_vnd"), "IS_PAT", fill_log)
    _fill_cell(table, "- Tổng vay và nợ ngắn + dài hạn (triệu đồng)", 3, total_borrowings, "BS_TOTAL_BORROWINGS", fill_log)
    _fill_cell(table, "- Hệ số đòn bẩy (lần)", 3, leverage, "CALC_LEVERAGE", fill_log, decimals=2, unit_convert=False)
    _fill_cell(table, "- Operating Profit", 3, ebit, "CALC_EBIT", fill_log)
    _fill_cell(table, "- Operating Profit Margin", 3, opm, "CALC_OPM", fill_log, decimals=2, unit_convert=False)
    row = _find_row_by_label(table, "- KNTT hiện hành (lần)")
    current_ratio = _metric_value(computed, "current_ratio")
    if row is not None:
        _set_cell_text(row.cells[3], _format_number_vn(current_ratio, 2) if current_ratio is not None else _MISSING_PLACEHOLDER)
        fill_log.append({"field_code": "CALC_CURRENT_RATIO", "row_label": "- KNTT hiện hành (lần)", "status": "FILLED" if current_ratio is not None else "MISSING"})
    for not_computed_label in (
        "- Vòng quay VLĐ (vòng)", "- Vòng quay kinh doanh (vòng)",
        "- Số ngày thiếu tiền (ngày)", "- Nhu cầu vốn 1 chu kỳ",
    ):
        row = _find_row_by_label(table, not_computed_label)
        if row is not None:
            _set_cell_text(row.cells[3], _MISSING_PLACEHOLDER)
            fill_log.append({"field_code": "NOT_COMPUTED", "row_label": not_computed_label, "status": "NOT_COMPUTED_BY_DESIGN"})

    # S2.2's scope ruling (Task 9): only "Năm N" (col 3) is ever sourced —
    # N-2/N-1 (cols 1/2) never borrow another period's number (H7). Mark
    # every data row's N-2/N-1 cells with the explicit missing placeholder
    # rather than leaving them silently blank (S1.1).
    for row in table.rows[1:]:
        for col in (1, 2):
            if row.cells[col].text.strip() == "":
                _set_cell_text(row.cells[col], _MISSING_PLACEHOLDER)


def _fill_s2_3_capital_adequacy(document, computed: dict, fill_log: list[dict]) -> None:
    table = _find_table_after_heading(document, "Các chỉ tiêu khả năng đảm bảo vốn kinh doanh")
    if table is None:
        fill_log.append({"field_code": "S2.3", "status": "TABLE_NOT_FOUND"})
        return
    fi = computed.get("financial_inputs") or {}
    long_term_capital = _metric_value(computed, "long_term_capital")
    nwc = _metric_value(computed, "nwc")
    _fill_cell(table, "1. Nguồn vốn dài hạn", 3, long_term_capital, "BS_LONG_TERM_CAPITAL", fill_log)
    _fill_cell(table, "- Vốn CSH", 3, fi.get("equity_vnd"), "BS_EQUITY", fill_log)
    _fill_cell(table, "- Vay dài hạn", 3, fi.get("long_term_debt_vnd"), "BS_LT_BORROWINGS", fill_log)
    _fill_cell(table, "2. Tài sản cố định và đầu tư tài chính dài hạn", 3, fi.get("non_current_assets_vnd"), "BS_NON_CURRENT_ASSETS", fill_log)
    _fill_cell(table, "3. Vốn lưu động thường xuyên", 3, nwc, "CALC_NWC", fill_log)

    for row in table.rows[1:]:
        for col in (1, 2):
            if row.cells[col].text.strip() == "":
                _set_cell_text(row.cells[col], _MISSING_PLACEHOLDER)

    target = _nfc("Nhận xét, đánh giá về sức khỏe tài chính")
    for paragraph in document.paragraphs:
        if target in _nfc(paragraph.text):
            why = computed.get("why") or []
            commentary = " ".join(why) if why else "Chưa có nhận định — hồ sơ chưa đủ dữ liệu để đưa kết luận thẩm định."
            new_text = f"{commentary} {DISCLAIMER}"
            if paragraph.runs:
                paragraph.runs[0].text = new_text
                for run in paragraph.runs[1:]:
                    run.text = ""
            else:
                paragraph.add_run(new_text)
            fill_log.append({"field_code": "S2.3_COMMENTARY", "status": "FILLED"})
            break


def _fill_s2_5_business_plan(document, computed: dict, fill_log: list[dict]) -> None:
    table = _find_table_after_heading(document, "Kế hoạch kinh doanh")
    if table is None:
        fill_log.append({"field_code": "S2.5", "status": "TABLE_NOT_FOUND"})
        return
    fi = computed.get("financial_inputs") or {}
    _fill_cell(table, "Tổng doanh thu", 2, fi.get("net_revenue_vnd"), "IS_REVENUE", fill_log, label_col=1)
    _fill_cell(table, "Lợi nhuận trước thuế (3)= (2)- (1)", 2, fi.get("pbt_vnd"), "IS_PBT", fill_log, label_col=1)
    _fill_cell(table, "Chi phí khấu hao", 2, fi.get("depreciation_vnd"), "IS_DEPRECIATION", fill_log, label_col=1)
    _fill_cell(table, "Chi phí lãi vay vốn", 2, fi.get("interest_expense_vnd"), "IS_INTEREST", fill_log, label_col=1)


def _fill_s2_4_qd_eb_039(document, computed: dict, fill_log: list[dict]) -> None:
    receivables = (computed.get("financial_inputs") or {}).get("receivables_vnd")
    target = _nfc("Hạn mức tài trợ theo phương án đầu ra dự kiến:")
    for paragraph in document.paragraphs:
        if _nfc(paragraph.text.strip()).startswith(target):
            if receivables is None:
                limit_text = _MISSING_PLACEHOLDER
                status = "MISSING"
            else:
                limit_trieu = round(receivables * 0.80 / 1_000_000)
                limit_text = f"{_format_number_vn(limit_trieu, 0)} triệu đồng (80% Số dư phải thu cuối kỳ, Giá trị tham chiếu từ BCTC)"
                status = "FILLED"
            new_text = f"Hạn mức tài trợ theo phương án đầu ra dự kiến: {limit_text}"
            if paragraph.runs:
                paragraph.runs[0].text = new_text
                for run in paragraph.runs[1:]:
                    run.text = ""
            else:
                paragraph.add_run(new_text)
            fill_log.append({"field_code": "QD039_REFERENCE_LIMIT", "value_vnd": receivables, "status": status})
            break


def build_mb02_docx(computed: dict, *, force: bool = False, actor: str | None = None) -> tuple[bytes, dict]:
    computed = computed or {}
    document = docx.Document(str(_TEMPLATE_PATH))
    fill_log: dict = {
        "verdict": (computed.get("export_gate") or {}).get("verdict", "XUAT"),
        "xuat_theo_force": force,
        "actor": actor,
        "cells": [],
    }

    gate = computed.get("export_gate") or {}
    if force and gate.get("verdict") == "KHONG_XUAT_TU_DONG":
        signal_lines = "; ".join(
            f"{s.get('rule_name', s.get('rule_id'))}: {s.get('observed_value', '?')}"
            for s in gate.get("signals") or []
        ) or "; ".join(gate.get("reasons") or [])
        banner = document.paragraphs[0].insert_paragraph_before(
            f"[BẢN NHÁP XUẤT THEO YÊU CẦU CỦA CÁN BỘ — HỆ THỐNG KHÔNG TỰ XUẤT] {signal_lines}"
        )
        banner.runs[0].bold = True

    _fill_s2_1_customer_info(document, computed, fill_log["cells"])
    _fill_s2_2_general_metrics(document, computed, fill_log["cells"])
    _fill_s2_3_capital_adequacy(document, computed, fill_log["cells"])
    _fill_s2_5_business_plan(document, computed, fill_log["cells"])
    _fill_s2_4_qd_eb_039(document, computed, fill_log["cells"])

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue(), fill_log
