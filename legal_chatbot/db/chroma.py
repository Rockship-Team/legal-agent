"""Simple keyword-based search (fallback for when ChromaDB is unavailable)

Note: This is a simplified implementation that uses keyword matching instead of
semantic search. For production, consider using ChromaDB when Python 3.14 support
is available.
"""

import re
import json
from pathlib import Path
from typing import Optional

from legal_chatbot.utils.config import get_settings
from legal_chatbot.utils.vietnamese import normalize_vietnamese

# Global storage (in-memory + file persistence)
_articles: dict[str, dict] = {}
_storage_path: Optional[Path] = None


def get_chroma_path() -> Path:
    """Get storage path from settings"""
    settings = get_settings()
    return Path(settings.chroma_path)


def init_chroma():
    """Initialize storage"""
    global _storage_path, _articles

    _storage_path = get_chroma_path()
    _storage_path.mkdir(parents=True, exist_ok=True)

    # Load existing data if any
    data_file = _storage_path / "articles.json"
    if data_file.exists():
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                _articles = json.load(f)
        except Exception:
            _articles = {}

    return _storage_path


def get_collection(name: str = "legal_articles"):
    """Get collection (compatibility function)"""
    init_chroma()
    return name


def _save_articles():
    """Save articles to disk"""
    if _storage_path:
        data_file = _storage_path / "articles.json"
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(_articles, f, ensure_ascii=False, indent=2)


def add_articles(
    articles: list[dict],
    collection_name: str = "legal_articles"
) -> int:
    """
    Add articles to the storage.

    Args:
        articles: List of article dicts with 'id', 'content', and metadata
        collection_name: Name of the collection (unused, for compatibility)

    Returns:
        Number of articles added
    """
    global _articles

    init_chroma()

    for article in articles:
        _articles[article['id']] = {
            'id': article['id'],
            'content': article.get('content', ''),
            'document_id': article.get('document_id', ''),
            'document_title': article.get('document_title', ''),
            'article_number': article.get('article_number', 0),
            'article_title': article.get('title', ''),
            'document_type': article.get('document_type', ''),
            'chapter': article.get('chapter', ''),
        }

    _save_articles()
    return len(articles)


def _tokenize(text: str) -> list[str]:
    """Simple tokenization for Vietnamese text"""
    text = normalize_vietnamese(text.lower())
    # Split on whitespace and punctuation
    tokens = re.findall(r'\b\w+\b', text)
    return tokens


def _calculate_score(query_tokens: list[str], content: str) -> float:
    """Calculate relevance score using keyword matching"""
    content_lower = normalize_vietnamese(content.lower())
    content_tokens = set(_tokenize(content_lower))

    if not query_tokens or not content_tokens:
        return 0.0

    # Count matching tokens
    matches = sum(1 for token in query_tokens if token in content_tokens)

    # Bonus for exact phrase matches
    query_text = ' '.join(query_tokens)
    if query_text in content_lower:
        matches += len(query_tokens)

    # Normalize score
    score = matches / (len(query_tokens) + 1)

    return min(score, 1.0)


def search_articles(
    query: str,
    top_k: int = 5,
    collection_name: str = "legal_articles"
) -> list[dict]:
    """
    Search for articles using keyword matching.

    Args:
        query: Search query
        top_k: Number of results to return
        collection_name: Name of the collection (unused)

    Returns:
        List of search results with scores
    """
    init_chroma()

    if not _articles:
        return []

    query_tokens = _tokenize(query)

    # Calculate scores for all articles
    scored_results = []
    for article_id, article in _articles.items():
        content = article.get('content', '')
        title = article.get('article_title', '')

        # Score based on content and title
        content_score = _calculate_score(query_tokens, content)
        title_score = _calculate_score(query_tokens, title) * 1.5  # Boost title matches

        total_score = max(content_score, title_score)

        if total_score > 0:
            scored_results.append({
                'id': article_id,
                'score': total_score,
                'content': content,
                'metadata': {
                    'document_id': article.get('document_id', ''),
                    'document_title': article.get('document_title', ''),
                    'article_number': article.get('article_number', 0),
                    'article_title': article.get('article_title', ''),
                    'document_type': article.get('document_type', ''),
                    'chapter': article.get('chapter', ''),
                }
            })

    # Sort by score and return top_k
    scored_results.sort(key=lambda x: x['score'], reverse=True)
    return scored_results[:top_k]


def delete_collection(name: str = "legal_articles"):
    """Delete all articles"""
    global _articles
    _articles = {}
    if _storage_path:
        data_file = _storage_path / "articles.json"
        if data_file.exists():
            data_file.unlink()
