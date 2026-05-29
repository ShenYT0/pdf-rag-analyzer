"""
Application Configuration Module - Loads all configuration items from .env file
Supports automatic switching between online/local modes
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    """Global configuration, automatically loaded from .env file"""

    # ── OCR Configuration ──
    OCR_MODEL: str = "glm-ocr"
    OCR_API_KEY: str = ""
    OCR_BASE_URL: str = "http://localhost:11434/v1"

    # ── Embedding Configuration ──
    EMBEDDING_MODEL: str = "nomic-embed-text-v2-moe"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = "http://localhost:11434/v1"

    # ── LLM Configuration ──
    LLM_MODEL: str = "llama3.2"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "http://localhost:11434/v1"

    # ── Neo4j Configuration ──
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # ── Milvus Configuration ──
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530

    # ── Application Configuration ──
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # ── File Upload Configuration ──
    # Maximum upload file size in bytes (default: 50MB)
    MAX_FILE_SIZE: int = 50 * 1024 * 1024

    # ── RAG Parameters ──
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    TOP_K: int = 5
    EMBEDDING_DIMENSION: int = 768

    model_config = {
        "env_file": str(Path(__file__).resolve().parent.parent.parent / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

@lru_cache()
def get_settings() -> Settings:
    """Get the global configuration singleton"""
    return Settings()