import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class Settings:
    llm_api_key: str
    llm_base_url: str
    ocr_vision_model: str
    narrative_model: str
    db_path: str
    case_files_dir: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        llm_api_key=os.environ.get("LLM_API_KEY", ""),
        llm_base_url=os.environ.get(
            "LLM_BASE_URL", "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1"
        ),
        ocr_vision_model=os.environ.get("OCR_VISION_MODEL", "qwen/qwen3.6-flash"),
        narrative_model=os.environ.get("NARRATIVE_MODEL", "z-ai/glm-5.2-hackathon"),
        db_path=os.environ.get("DB_PATH", "data/m_insight.db"),
        case_files_dir=os.environ.get("CASE_FILES_DIR", "data/eb_files"),
    )
