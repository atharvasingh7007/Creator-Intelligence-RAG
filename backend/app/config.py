"""
Creator Intelligence RAG Platform - Configuration
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # LLM
    gemini_api_key: str = ""

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "video_chunks"

    # PostgreSQL
    postgres_url: str = "postgresql+asyncpg://rag:ragpassword@localhost:5432/rag_platform"

    # Models
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # Chunking
    chunk_size: int = 400
    chunk_overlap: int = 50

    # Retrieval
    retrieval_top_k: int = 20
    rerank_top_k: int = 5

    # Embedding dimension (BGE small)
    embedding_dim: int = 384

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
