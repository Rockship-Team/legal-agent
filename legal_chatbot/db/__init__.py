"""Database modules"""

# Legacy exports (backward compatibility with 001 code)
from legal_chatbot.db.sqlite import (
    init_db,
    get_connection,
    insert_document,
    insert_article,
    get_document,
    get_article,
    get_articles_by_document,
    search_articles_by_ids,
)
from legal_chatbot.db.chroma import (
    init_chroma,
    get_collection,
    add_articles,
    search_articles,
)

# New exports (002)
from legal_chatbot.db.base import DatabaseInterface
from legal_chatbot.db.supabase import get_database

__all__ = [
    # Legacy
    "init_db",
    "get_connection",
    "insert_document",
    "insert_article",
    "get_document",
    "get_article",
    "get_articles_by_document",
    "search_articles_by_ids",
    "init_chroma",
    "get_collection",
    "add_articles",
    "search_articles",
    # New
    "DatabaseInterface",
    "get_database",
]
