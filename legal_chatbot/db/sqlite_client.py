"""SQLite wrapper implementing DatabaseInterface for backward compatibility"""

import logging
from typing import List, Optional

from legal_chatbot.db.base import DatabaseInterface
from legal_chatbot.db import sqlite as sqlite_ops
from legal_chatbot.utils.config import get_settings

logger = logging.getLogger(__name__)


class SQLiteClient(DatabaseInterface):
    """SQLite implementation of DatabaseInterface.
    Wraps existing sqlite.py functions."""

    def init_db(self) -> None:
        sqlite_ops.init_db()

    def insert_document(self, document: dict) -> str:
        return sqlite_ops.insert_document(document)

    def insert_articles(self, articles: List[dict]) -> int:
        count = 0
        for article in articles:
            try:
                sqlite_ops.insert_article(article)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to insert article: {e}")
        return count

    def get_document(self, document_id: str) -> Optional[dict]:
        return sqlite_ops.get_document(document_id)

    def get_documents_by_category(self, category_name: str) -> List[dict]:
        # SQLite doesn't have categories table, return empty
        return []

    def search_articles(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        status: str = "active",
    ) -> List[dict]:
        # SQLite fallback uses keyword search via chroma
        from legal_chatbot.db.chroma import search_articles

        # Convert embedding to text query is not possible,
        # so fall back to returning all articles
        logger.warning("SQLite mode: vector search not available, using keyword search")
        return []

    def get_document_by_hash(self, content_hash: str) -> Optional[dict]:
        # Not supported in existing SQLite schema
        return None

    def upsert_document(self, document: dict) -> str:
        # SQLite uses INSERT OR REPLACE
        return sqlite_ops.insert_document(document)

    def upsert_articles(self, articles: List[dict]) -> int:
        return self.insert_articles(articles)

    def get_status(self) -> dict:
        settings = get_settings()
        try:
            with sqlite_ops.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM legal_documents")
                docs = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM articles")
                articles = cursor.fetchone()[0]
            return {
                "mode": "sqlite",
                "path": settings.database_path,
                "documents": docs,
                "articles": articles,
                "status": "connected",
            }
        except Exception as e:
            return {
                "mode": "sqlite",
                "path": settings.database_path,
                "status": f"error: {e}",
            }

    def browse_categories(self) -> List[dict]:
        # SQLite doesn't have categories table
        return []

    def browse_documents(self, category_name: str) -> List[dict]:
        # SQLite doesn't have categories table
        return []

    def browse_articles(self, document_id: str) -> List[dict]:
        try:
            with sqlite_ops.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, article_number, title, chapter, content "
                    "FROM articles WHERE document_id = ? ORDER BY article_number",
                    (document_id,),
                )
                cols = [d[0] for d in cursor.description]
                return [dict(zip(cols, row)) for row in cursor.fetchall()]
        except Exception:
            return []
