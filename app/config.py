from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    groq_api_key: str
    jina_api_key: str
    # Groq retires models without much notice - override via GROQ_MODEL / GROQ_CHART_MODEL
    groq_model: str = "openai/gpt-oss-120b"
    groq_chart_model: str = "openai/gpt-oss-120b"
    # Used when the main model hits its daily quota or is retired - each Groq model
    # has its own free-tier limits (e.g. 200k tokens/day)
    groq_fallback_model: str = "openai/gpt-oss-20b"
    chroma_path: str = str(BASE_DIR / "data" / "chroma")
    chroma_collection: str = "nbp_gus_docs"
    top_k: int = 5
    chunk_size: int = 800
    chunk_overlap: int = 100

    class Config:
        env_file = ".env"


settings = Settings()
