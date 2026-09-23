"""Fills the real MB02a/QT.RR.037 bank template (docs/templates/
template_MB02a.docx) by label search (instruction §S2: "dò theo nhãn
dòng, không bám số thứ tự bảng"), never by hard-coded table/cell
coordinates — a future MSB template edit that shifts a table index must
not silently mis-fill a cell."""

import io
from pathlib import Path

import docx
from docx.table import Table, _Cell

_TEMPLATE_PATH = Path(__file__).resolve().parents[3] / "docs" / "templates" / "template_MB02a.docx"

_MISSING_PLACEHOLDER = "[Chưa xác định từ hồ sơ tải lên]"

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
    for row in table.rows:
        if row.cells[label_col].text.strip() == label:
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


def build_mb02_docx(computed: dict, *, force: bool = False, actor: str | None = None) -> tuple[bytes, dict]:
    computed = computed or {}
    document = docx.Document(str(_TEMPLATE_PATH))
    fill_log: dict = {
        "verdict": (computed.get("export_gate") or {}).get("verdict", "XUAT"),
        "xuat_theo_force": force,
        "actor": actor,
        "cells": [],
    }

    # Force-override banner (S7.4) added by Task 12.

    # S2.x fill calls added by Tasks 9-11 go here, each appending to
    # fill_log["cells"].

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue(), fill_log
