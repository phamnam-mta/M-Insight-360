from app.engine.core.types import ConditionRow
from app.extraction.types import ExtractedDocument

from .credit_history import evaluate_credit_history
from .customer_status import evaluate_customer_segment, evaluate_operating_status
from .equity_profit import evaluate_equity, evaluate_gross_profit_less_interest, evaluate_lnst_pakd
from .industry import evaluate_industry
from .operating_history import evaluate_operating_history
from .partners import evaluate_top_partners
from .revenue import evaluate_revenue_12m, evaluate_revenue_6m_statement


def evaluate_overview(documents: list[ExtractedDocument]) -> tuple[list[ConditionRow], dict]:
    rows = [
        evaluate_customer_segment(),
        evaluate_revenue_12m(documents),
        evaluate_revenue_6m_statement(documents),
        evaluate_industry(documents),
        evaluate_operating_status(documents),
        evaluate_top_partners(documents),
        evaluate_operating_history(documents),
        evaluate_equity(documents),
        evaluate_lnst_pakd(documents),
        evaluate_gross_profit_less_interest(documents),
        evaluate_credit_history(),
    ]
    passed = sum(1 for r in rows if r.result == "PASS")
    failed = sum(1 for r in rows if r.result == "FAIL")
    pending = sum(1 for r in rows if r.result in ("INSUFFICIENT_DATA", "PENDING_INTERNAL_CHECK"))
    summary = {
        "checked": passed + failed, "total": len(rows),
        "passed": passed, "failed": failed, "pending": pending,
    }
    return rows, summary
