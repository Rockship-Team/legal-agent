"""Database modules"""

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

__all__ = [
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
]
