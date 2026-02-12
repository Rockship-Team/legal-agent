"""Supabase database client implementing DatabaseInterface"""

import logging
from pathlib import Path
from typing import List, Optional

from legal_chatbot.db.base import DatabaseInterface
from legal_chatbot.utils.config import get_settings

logger = logging.getLogger(__name__)

# Lazy imports to avoid requiring supabase when using sqlite mode
_supabase_client = None
_service_client = None


def _get_supabase_client():
    """Get or create the singleton Supabase client (anon key)."""
    global _supabase_client
    if _supabase_client is None:
        from supabase import Client, ClientOptions, create_client

        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY must be set when DB_MODE=supabase"
            )
        _supabase_client = create_client(
            settings.supabase_url,
            settings.supabase_key,
            options=ClientOptions(
                postgrest_client_timeout=10,
                storage_client_timeout=30,
            ),
        )
    return _supabase_client


def _get_service_client():
    """Get or create the singleton Supabase service-role client (bypasses RLS)."""
    global _service_client
    if _service_client is None:
        from supabase import ClientOptions, create_client

        settings = get_settings()
        key = settings.supabase_service_key or settings.supabase_key
        if not settings.supabase_url or not key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set for write operations"
            )
        _service_client = create_client(
            settings.supabase_url,
            key,
            options=ClientOptions(
                postgrest_client_timeout=10,
                storage_client_timeout=30,
            ),
        )
    return _service_client


class SupabaseClient(DatabaseInterface):
    """Supabase implementation of DatabaseInterface."""

    def __init__(self):
        self._read = _get_supabase_client
        self._write = _get_service_client

    def init_db(self) -> None:
        """Run migration SQL against Supabase.
        In practice, users run the SQL in Supabase SQL Editor.
        This method verifies the schema exists."""
        client = self._read()
        try:
            result = client.table("legal_categories").select("id").limit(1).execute()
            logger.info("Supabase schema verified: tables accessible")
        except Exception as e:
            migration_path = (
                Path(__file__).parent / "migrations" / "002_supabase.sql"
            )
            logger.error(
                f"Schema not found. Run migration SQL in Supabase SQL Editor: {migration_path}"
            )
            raise RuntimeError(
                f"Supabase schema not initialized. Run 002_supabase.sql in SQL Editor. Error: {e}"
            ) from e

    def insert_document(self, document: dict) -> str:
        """Insert a legal document. Returns document ID."""
        client = self._write()
        # Remove None values and fields Supabase doesn't need
        data = {k: v for k, v in document.items() if v is not None and k != "raw_content"}
        if "embedding" in data:
            del data["embedding"]
        result = client.table("legal_documents").insert(data).execute()
        return result.data[0]["id"]

    def insert_articles(self, articles: List[dict]) -> int:
        """Batch insert articles. Returns count inserted."""
        if not articles:
            return 0
        client = self._write()
        # Clean up data for Supabase
        # Only include columns that exist in the articles table
        valid_cols = {
            "id", "document_id", "article_number", "title", "content",
            "chapter", "section", "part", "embedding", "content_hash", "chunk_index",
        }
        clean = []
        for a in articles:
            row = {k: v for k, v in a.items() if v is not None and k in valid_cols}
            # Convert embedding list to string format for pgvector if present
            if "embedding" in row and isinstance(row["embedding"], list):
                row["embedding"] = str(row["embedding"])
            clean.append(row)
        # Deduplicate by id within the batch (keep last occurrence)
        deduped = {row["id"]: row for row in clean if "id" in row}
        clean = list(deduped.values())
        # Upsert in chunks of 50
        count = 0
        for i in range(0, len(clean), 50):
            chunk = clean[i : i + 50]
            result = client.table("articles").upsert(chunk, on_conflict="document_id,article_number,chunk_index").execute()
            count += len(result.data)
        return count

    def get_document(self, document_id: str) -> Optional[dict]:
        """Get document by ID."""
        client = self._read()
        result = (
            client.table("legal_documents")
            .select("*")
            .eq("id", document_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def get_documents_by_category(self, category_name: str) -> List[dict]:
        """Get all documents in a category."""
        client = self._read()
        # First get category ID
        cat_result = (
            client.table("legal_categories")
            .select("id")
            .eq("name", category_name)
            .execute()
        )
        if not cat_result.data:
            return []
        category_id = cat_result.data[0]["id"]
        result = (
            client.table("legal_documents")
            .select("*")
            .eq("category_id", category_id)
            .execute()
        )
        return result.data

    def search_articles(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        status: str = "active",
    ) -> List[dict]:
        """Semantic search via search_legal_articles RPC function.

        Uses search_legal_articles instead of match_articles to also return
        document_title and document_type from the joined legal_documents table.
        """
        client = self._read()
        result = client.rpc(
            "search_legal_articles",
            {
                "query_embedding": str(query_embedding),
                "match_threshold": 0.3,
                "match_count": top_k,
                "filter_status": status,
            },
        ).execute()
        # Normalize field names to match existing callers
        normalized = []
        for row in result.data:
            normalized.append({
                "id": row.get("article_id"),
                "document_id": row.get("document_id"),
                "article_number": row.get("article_number"),
                "title": row.get("article_title", ""),
                "content": row.get("article_content", ""),
                "chapter": row.get("chapter", ""),
                "document_title": row.get("document_title", ""),
                "document_type": row.get("document_type", ""),
                "document_number": row.get("document_number", ""),
                "similarity": row.get("similarity", 0),
            })
        return normalized

    def get_document_by_hash(self, content_hash: str) -> Optional[dict]:
        """Find document by content hash."""
        client = self._read()
        result = (
            client.table("legal_documents")
            .select("*")
            .eq("content_hash", content_hash)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def upsert_document(self, document: dict) -> str:
        """Insert or update document. Returns document ID."""
        client = self._write()
        data = {k: v for k, v in document.items() if v is not None and k != "raw_content"}
        if "embedding" in data:
            del data["embedding"]
        # Check if document already exists by (document_number, document_type)
        doc_num = data.get("document_number", "")
        doc_type = data.get("document_type", "")
        existing = None
        if doc_num and doc_type:
            existing = (
                client.table("legal_documents")
                .select("id")
                .eq("document_number", doc_num)
                .eq("document_type", doc_type)
                .limit(1)
                .execute()
            )
        # Fallback: match by title when document_number is empty
        if not (existing and existing.data) and data.get("title"):
            existing = (
                client.table("legal_documents")
                .select("id")
                .eq("title", data["title"])
                .limit(1)
                .execute()
            )
        if existing and existing.data:
            # Reuse existing document id to avoid FK conflicts
            data["id"] = existing.data[0]["id"]
        result = client.table("legal_documents").upsert(data).execute()
        return result.data[0]["id"]

    def upsert_articles(self, articles: List[dict]) -> int:
        """Batch upsert articles with embeddings. Returns count."""
        return self.insert_articles(articles)

    def get_status(self) -> dict:
        """Get database status info."""
        client = self._read()
        settings = get_settings()
        try:
            docs = client.table("legal_documents").select("id", count="exact").execute()
            articles = client.table("articles").select("id", count="exact").execute()
            categories = (
                client.table("legal_categories").select("id", count="exact").execute()
            )
            return {
                "mode": "supabase",
                "url": settings.supabase_url,
                "documents": docs.count or 0,
                "articles": articles.count or 0,
                "categories": categories.count or 0,
                "status": "connected",
            }
        except Exception as e:
            return {
                "mode": "supabase",
                "url": settings.supabase_url,
                "status": f"error: {e}",
            }

    # Browse operations

    def browse_categories(self) -> List[dict]:
        """List categories with document/article counts."""
        client = self._read()
        # Get all categories
        cats = client.table("legal_categories").select("*").order("name").execute()
        results = []
        for cat in cats.data:
            # Count documents in this category
            docs = (
                client.table("legal_documents")
                .select("id", count="exact")
                .eq("category_id", cat["id"])
                .execute()
            )
            # Count articles in those documents
            articles = (
                client.table("articles")
                .select("id, document_id, legal_documents!inner(category_id)")
                .eq("legal_documents.category_id", cat["id"])
                .execute()
            )
            results.append({
                "id": cat["id"],
                "name": cat["name"],
                "display_name": cat["display_name"],
                "description": cat.get("description", ""),
                "document_count": docs.count or 0,
                "article_count": len(articles.data) if articles.data else 0,
            })
        return results

    def browse_documents(self, category_name: str) -> List[dict]:
        """List documents in a category with article counts."""
        client = self._read()
        # Get category ID
        cat = (
            client.table("legal_categories")
            .select("id, display_name")
            .eq("name", category_name)
            .limit(1)
            .execute()
        )
        if not cat.data:
            return []
        category_id = cat.data[0]["id"]
        # Get documents in this category
        docs = (
            client.table("legal_documents")
            .select("id, document_number, document_type, title, effective_date, status")
            .eq("category_id", category_id)
            .order("document_type")
            .execute()
        )
        results = []
        for doc in docs.data:
            # Count articles per document
            arts = (
                client.table("articles")
                .select("id", count="exact")
                .eq("document_id", doc["id"])
                .execute()
            )
            results.append({
                **doc,
                "article_count": arts.count or 0,
            })
        return results

    def browse_articles(self, document_id: str) -> List[dict]:
        """List articles in a document, ordered by chapter + article_number."""
        client = self._read()
        result = (
            client.table("articles")
            .select("id, article_number, title, chapter, content")
            .eq("document_id", document_id)
            .order("article_number")
            .execute()
        )
        return result.data

    # Storage operations

    def upload_raw_document(
        self, path: str, content: bytes, mime_type: str = "text/html"
    ) -> str:
        """Upload raw document to Supabase Storage."""
        client = self._write()
        client.storage.from_("legal-raw-documents").upload(
            path=path,
            file=content,
            file_options={
                "content-type": f"{mime_type}; charset=utf-8",
                "upsert": "true",
            },
        )
        return path

    def download_raw_document(self, path: str) -> bytes:
        """Download raw document from Supabase Storage."""
        client = self._read()
        return client.storage.from_("legal-raw-documents").download(path)


def get_database(mode: str = None) -> DatabaseInterface:
    """Factory: returns appropriate database implementation.

    mode: 'supabase' or 'sqlite'. Defaults to DB_MODE env var.
    """
    if mode is None:
        mode = get_settings().db_mode

    if mode == "supabase":
        return SupabaseClient()
    else:
        # Import here to avoid circular imports
        from legal_chatbot.db.sqlite_client import SQLiteClient

        return SQLiteClient()
