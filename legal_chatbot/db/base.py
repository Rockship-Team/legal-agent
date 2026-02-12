"""Abstract database interface — strategy pattern for SQLite/Supabase switching"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class DatabaseInterface(ABC):
    """Abstract interface for database operations.
    Implemented by both SQLite and Supabase backends."""

    @abstractmethod
    def init_db(self) -> None:
        """Initialize database schema (create tables, indexes)."""

    @abstractmethod
    def insert_document(self, document: dict) -> str:
        """Insert a legal document. Returns document ID."""

    @abstractmethod
    def insert_articles(self, articles: List[dict]) -> int:
        """Batch insert articles. Returns count inserted."""

    @abstractmethod
    def get_document(self, document_id: str) -> Optional[dict]:
        """Get document by ID."""

    @abstractmethod
    def get_documents_by_category(self, category_name: str) -> List[dict]:
        """Get all documents in a category."""

    @abstractmethod
    def search_articles(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        status: str = "active",
    ) -> List[dict]:
        """Semantic search via embeddings. Returns articles with similarity."""

    @abstractmethod
    def get_document_by_hash(self, content_hash: str) -> Optional[dict]:
        """Find document by content hash (for change detection)."""

    @abstractmethod
    def upsert_document(self, document: dict) -> str:
        """Insert or update document. Returns document ID."""

    @abstractmethod
    def upsert_articles(self, articles: List[dict]) -> int:
        """Batch upsert articles (with embeddings). Returns count."""

    @abstractmethod
    def get_status(self) -> dict:
        """Get database status info (table counts, connection status)."""

    @abstractmethod
    def browse_categories(self) -> List[dict]:
        """List categories with document/article counts."""

    @abstractmethod
    def browse_documents(self, category_name: str) -> List[dict]:
        """List documents in a category with article counts."""

    @abstractmethod
    def browse_articles(self, document_id: str) -> List[dict]:
        """List articles in a document, ordered by chapter + article_number."""
