from dataclasses import dataclass, field


@dataclass
class ExtractedTable:
    rows: list[list[str]]
    sheet_or_page: str


@dataclass
class ExtractedDocument:
    filename: str
    doc_type: str  # "pdf" | "docx" | "xlsx" | "csv"
    text: str
    tables: list[ExtractedTable]
    extraction_method: str  # "text_layer" | "docx" | "spreadsheet" | "vision_llm" | "no_text_layer" | "ocr_failed"
    confidence: float  # 0.0-1.0
    warnings: list[str] = field(default_factory=list)
