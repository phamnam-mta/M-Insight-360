from app.extraction.types import ExtractedDocument, ExtractedTable

def test_extracted_document_constructs_with_defaults():
    doc = ExtractedDocument(
        filename="a.docx", doc_type="docx", text="hello",
        tables=[], extraction_method="docx", confidence=1.0,
    )
    assert doc.warnings == []
    assert doc.filename == "a.docx"

def test_extracted_table_holds_rows():
    t = ExtractedTable(rows=[["a", "b"], ["1", "2"]], sheet_or_page="Sheet1")
    assert t.rows[1] == ["1", "2"]
