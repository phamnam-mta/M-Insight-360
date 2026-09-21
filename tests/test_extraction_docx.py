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


from app.extraction.docx_parser import extract_docx

def test_extract_docx_reads_paragraphs_and_tables(fixtures_dir):
    doc = extract_docx(str(fixtures_dir / "sample.docx"), "sample.docx")
    assert "CONG TY TNHH TEST" in doc.text
    assert doc.doc_type == "docx"
    assert doc.extraction_method == "docx"
    assert doc.confidence == 1.0
    assert len(doc.tables) == 1
    assert doc.tables[0].rows[1] == ["Von dieu le", "500000000"]
