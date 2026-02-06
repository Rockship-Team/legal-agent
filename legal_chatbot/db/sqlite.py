"""SQLite database operations"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional
import json

from legal_chatbot.utils.config import get_settings


def get_db_path() -> Path:
    """Get database path from settings"""
    settings = get_settings()
    return Path(settings.database_path)


@contextmanager
def get_connection():
    """Get a database connection as context manager"""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database with schema"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Legal documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS legal_documents (
                id TEXT PRIMARY KEY,
                document_type TEXT NOT NULL,
                document_number TEXT NOT NULL,
                title TEXT NOT NULL,
                effective_date DATE,
                issuing_authority TEXT,
                source_url TEXT,
                crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                raw_content TEXT,
                status TEXT DEFAULT 'active'
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_type
            ON legal_documents(document_type)
        """)

        # Articles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES legal_documents(id),
                article_number INTEGER NOT NULL,
                title TEXT,
                content TEXT NOT NULL,
                chapter TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(document_id, article_number)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_articles_document
            ON articles(document_id)
        """)

        # Contract templates table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contract_templates (
                id TEXT PRIMARY KEY,
                template_type TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                template_content TEXT NOT NULL,
                required_fields TEXT,
                legal_references TEXT,
                version INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Chat sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_message_at TIMESTAMP,
                context TEXT
            )
        """)

        # Chat messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES chat_sessions(id),
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session
            ON chat_messages(session_id)
        """)


def insert_document(doc: dict) -> str:
    """Insert a legal document"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO legal_documents
            (id, document_type, document_number, title, effective_date,
             issuing_authority, source_url, raw_content, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc['id'],
            doc['document_type'],
            doc['document_number'],
            doc['title'],
            doc.get('effective_date'),
            doc.get('issuing_authority'),
            doc.get('source_url'),
            doc.get('raw_content'),
            doc.get('status', 'active'),
        ))
        return doc['id']


def insert_article(article: dict) -> str:
    """Insert an article"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO articles
            (id, document_id, article_number, title, content, chapter)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            article['id'],
            article['document_id'],
            article['article_number'],
            article.get('title'),
            article['content'],
            article.get('chapter'),
        ))
        return article['id']


def get_document(doc_id: str) -> Optional[dict]:
    """Get a document by ID"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM legal_documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_article(article_id: str) -> Optional[dict]:
    """Get an article by ID"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_articles_by_document(doc_id: str) -> list[dict]:
    """Get all articles for a document"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM articles WHERE document_id = ? ORDER BY article_number",
            (doc_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def search_articles_by_ids(article_ids: list[str]) -> list[dict]:
    """Get articles by their IDs with document context"""
    if not article_ids:
        return []

    with get_connection() as conn:
        cursor = conn.cursor()
        placeholders = ','.join(['?' for _ in article_ids])
        cursor.execute(f"""
            SELECT
                a.*,
                d.title as document_title,
                d.document_type,
                d.effective_date
            FROM articles a
            JOIN legal_documents d ON a.document_id = d.id
            WHERE a.id IN ({placeholders})
        """, article_ids)
        return [dict(row) for row in cursor.fetchall()]


def get_all_articles() -> list[dict]:
    """Get all articles with document context"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                a.*,
                d.title as document_title,
                d.document_type,
                d.effective_date
            FROM articles a
            JOIN legal_documents d ON a.document_id = d.id
            ORDER BY d.title, a.article_number
        """)
        return [dict(row) for row in cursor.fetchall()]
