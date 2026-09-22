from app.agents.crosssell.assembler import assemble_response
from app.agents.crosssell.statement_parser import Transaction


def _t(date, entry_no, debit=0.0, credit=0.0, description="", partner="", currency="VND", balance=None, source=""):
    return Transaction(
        date=date, entry_no=entry_no, debit=debit, credit=credit, description=description,
        partner=partner, partner_account="", partner_bank="", currency=currency, source=source,
        balance=balance,
    )


def _base_transactions():
    txns = []
    # Payroll signal — 3 months.
    for i, month in enumerate(["01", "02", "03"], start=1):
        txns.append(_t(f"25/{month}/2026", f"PAY{i}", debit=100_000_000, description="Chi luong thang"))

    # Partner "CONG TY DOI TAC B" — qualifies for Rule 2 / partner list.
    for i, month in enumerate(["05", "10", "15", "20", "25"], start=1):
        txns.append(_t(f"{month}/01/2026", f"PB{i}", credit=600_000_000, description="Thanh toan hop dong", partner="CONG TY DOI TAC B"))

    # Idle balance — 12 distinct days above the 5B threshold.
    for day in range(1, 13):
        txns.append(_t(f"{day:02d}/04/2026", f"BAL{day}", credit=1_000, description="So du cuoi ngay", balance=6_000_000_000))

    # FX signal.
    txns.append(_t("02/05/2026", "FX1", credit=200_000_000, description="Thanh toan XNK", currency="USD"))

    # Loan-elsewhere signal.
    txns.append(_t("03/05/2026", "LN1", debit=500_000_000, description="Tra no vay ngan hang khac"))

    return txns


def _assemble(**overrides):
    kwargs = dict(
        customer_name="CONG TY TNHH ALPHA",
        tax_id="0123456789",
        raw_transactions=_base_transactions(),
        opening_balance=None,
        closing_balance=None,
    )
    kwargs.update(overrides)
    return assemble_response(**kwargs)


def test_returns_all_top_level_schema_keys():
    result = _assemble()
    for key in ("status", "request_id", "ma_lo", "ho_so", "badges", "kpi", "co_hoi", "doi_tac", "evidence", "ban_giao", "warnings", "error_code"):
        assert key in result


def test_kpi_has_exactly_four_entries_first_emphasized():
    result = _assemble()
    assert len(result["kpi"]) == 4
    assert result["kpi"][0]["nhan_manh"] is True
    assert all(k.get("nhan_manh", False) is False for k in result["kpi"][1:])


def test_co_hoi_sorted_descending_with_na_last():
    result = _assemble()
    sizes = [c["deal_size"] for c in result["co_hoi"]]
    non_na = [s for s in sizes if s is not None]
    assert non_na == sorted(non_na, reverse=True)
    na_positions = [i for i, s in enumerate(sizes) if s is None]
    non_na_positions = [i for i, s in enumerate(sizes) if s is not None]
    if na_positions and non_na_positions:
        assert min(na_positions) > max(non_na_positions)


def test_deal_size_sum_matches_kpi_total():
    result = _assemble()
    total = sum(c["deal_size"] for c in result["co_hoi"] if c["deal_size"] is not None)
    headline = result["kpi"][0]["gia_tri"]
    from app.agents.crosssell.card_types import format_deal_size_headline
    assert headline == format_deal_size_headline(total)


def test_partner_list_always_marked_chua_kiem_tra_cif():
    result = _assemble()
    assert result["doi_tac"]["danh_sach"], "fixture partner should qualify and appear"
    for p in result["doi_tac"]["danh_sach"]:
        assert p["trang_thai"] == "Chua kiem tra CIF"
    assert "LƯU Ý" in result["doi_tac"]["canh_bao_cif"]


def test_block_precheck_collapses_kpi_and_empties_co_hoi():
    result = _assemble(opening_balance=0, closing_balance=999_999_999_999)
    assert result["status"] == "blocked"
    assert len(result["kpi"]) == 1
    assert result["kpi"][0]["nhan"] == "Cần bổ sung chứng từ"
    assert result["co_hoi"] == []


def test_evidence_tom_tat_fields_truncated_to_70_chars():
    result = _assemble()
    for block in result["evidence"].values():
        assert len(block["tom_tat"]) <= 70


def test_self_check_warnings_empty_for_clean_fixture():
    result = _assemble()
    assert result["warnings"] == []


def test_rule3_idle_opportunity_present_and_p2_or_p1():
    result = _assemble()
    rule3 = next(c for c in result["co_hoi"] if c["rule_id"] == "RULE3_IDLE")
    assert rule3["priority"] in ("P1", "P2")
    assert rule3["deal_size"] is not None
