"""Configuration management using pydantic-settings"""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # API keys - support both Anthropic and Groq
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key for Claude")
    groq_api_key: Optional[str] = Field(default=None, description="Groq API key for LLM access")

    # LLM provider: 'anthropic' or 'groq'
    llm_provider: str = Field(default="anthropic", description="LLM provider to use")

    database_path: str = Field(default="./data/legal.db", description="Path to SQLite database")
    chroma_path: str = Field(default="./data/chroma", description="Path to ChromaDB storage")
    log_level: str = Field(default="INFO", description="Logging level")

    # LLM settings
    llm_model: str = Field(default="claude-sonnet-4-20250514", description="LLM model to use")
    llm_temperature: float = Field(default=0.3, description="LLM temperature")
    llm_max_tokens: int = Field(default=4096, description="Max tokens in response")

    # Search settings
    search_top_k: int = Field(default=5, description="Number of results for semantic search")

    # Database mode: 'supabase' or 'sqlite'
    db_mode: str = Field(default="sqlite", description="Database backend: 'supabase' or 'sqlite'")

    # Supabase settings
    supabase_url: Optional[str] = Field(default=None, description="Supabase project URL")
    supabase_key: Optional[str] = Field(default=None, description="Supabase anon key")
    supabase_service_key: Optional[str] = Field(default=None, description="Supabase service role key")

    # Pipeline settings
    pipeline_crawl_interval: int = Field(default=168, description="Crawl interval in hours")
    pipeline_rate_limit: float = Field(default=4.0, description="Seconds between crawl requests")
    pipeline_max_pages: int = Field(default=20, description="Max pages per crawl session")

    # Embedding settings
    embedding_model: str = Field(
        default="bkai-foundation-models/vietnamese-bi-encoder",
        description="Sentence transformer model for embeddings",
    )
    embedding_dimension: int = Field(default=768, description="Embedding vector dimension")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def get_settings() -> Settings:
    """Get application settings"""
    return Settings()
