from app.engine.core.types import ConditionRow, Metric
from app.extraction.types import ExtractedDocument


def build_document_status_list(
    documents: list[ExtractedDocument],
    extraction_warnings: list[str],
    condition_rows: list[ConditionRow],
    metrics: dict[str, Metric],
) -> list[dict]:
    cited_ok: set[str] = set()
    cited_pending: set[str] = set()

    for row in condition_rows:
        target = cited_ok if row.observed.status in ("COMPUTED", "VERIFIED") else cited_pending
        for ref in row.observed.evidence:
            target.add(ref.file_id)

    for metric in metrics.values():
        for refs in metric.evidence.values():
            for ref in refs:
                cited_ok.add(ref.file_id)

    result: list[dict] = []
    for name in extraction_warnings:
        filename = name.split(":", 1)[0]
        result.append({"filename": filename, "status": "KHÔNG_ĐỌC_ĐƯỢC", "cited_field_count": 0, "warnings": [name]})

    for doc in documents:
        file_id = getattr(doc, "file_id", doc.filename)
        if file_id in cited_pending:
            status = "CHỜ_XÁC_MINH"
        elif file_id in cited_ok:
            status = "ĐÃ_TRÍCH_XUẤT"
        else:
            status = "ĐÃ_TẢI_LÊN"
        result.append({
            "filename": doc.filename, "doc_type": doc.doc_type, "status": status,
            "cited_field_count": sum(
                1 for r in condition_rows for ref in r.observed.evidence if ref.file_id == file_id
            ),
            "warnings": list(doc.warnings),
        })
    return result
