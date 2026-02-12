"""Document indexer service"""

import re
import json
import uuid as _uuid
from pathlib import Path
from typing import Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel

from legal_chatbot.utils.config import get_settings
from legal_chatbot.utils.vietnamese import normalize_vietnamese, clean_text, extract_article_number
from legal_chatbot.db.sqlite import init_db, insert_document, insert_article, get_all_articles
from legal_chatbot.db.chroma import add_articles, init_chroma


class IndexConfig(BaseModel):
    """Configuration for indexing"""
    input_dir: str = "./data/raw"
    chunk_overlap: int = 100


class ParsedArticle(BaseModel):
    """A parsed article from a legal document"""
    id: str
    document_id: str
    article_number: int
    title: Optional[str] = None
    content: str
    chapter: Optional[str] = None


class IndexResult(BaseModel):
    """Result of indexing operation"""
    documents_processed: int
    articles_indexed: int
    errors: list[str] = []


class IndexerService:
    """Service for indexing legal documents"""

    def __init__(self, config: Optional[IndexConfig] = None):
        self.config = config or IndexConfig()
        self.input_dir = Path(self.config.input_dir)

    def parse_html_articles(self, html_content: str, document_id: str) -> list[ParsedArticle]:
        """
        Parse HTML content to extract individual articles (Điều).
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        for br in soup.find_all('br'):
            br.replace_with(' ')
        text = soup.get_text(separator='\n')

        # HTML uses single \n for word-wrap, \n\n+ for paragraph breaks.
        # Step 1: Mark paragraph breaks (2+ newlines) with placeholder
        text = re.sub(r'\n\s*\n', '\n\n', text)
        # Step 2: Join word-wrapped lines (single \n) with space
        lines = text.split('\n')
        merged = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                # Empty line = paragraph break, keep as newline
                if merged and merged[-1] != '':
                    merged.append('')
            else:
                # Non-empty line: merge with previous if it was also non-empty
                if merged and merged[-1] != '':
                    merged[-1] = merged[-1] + ' ' + stripped
                else:
                    merged.append(stripped)
        text = '\n'.join(line for line in merged if line)
        text = re.sub(r'[ \t]+', ' ', text)

        articles = []
        current_chapter = None

        # Pattern: Điều N. Title\nContent...until next Điều
        article_pattern = r'(Điều\s+(\d+)\.?\s*([^\n]*))\n(.*?)(?=Điều\s+\d+\.|$)'

        # Find chapter headers
        chapter_pattern = r'(Chương\s+[IVXLCDM]+[:\.\s]+[^\n]+)'

        # Split text by chapters first
        parts = re.split(chapter_pattern, text, flags=re.IGNORECASE)

        for i, part in enumerate(parts):
            # Check if this is a chapter header
            if re.match(chapter_pattern, part, re.IGNORECASE):
                current_chapter = clean_text(part)
                continue

            # Find articles in this part
            matches = re.finditer(article_pattern, part, re.DOTALL | re.IGNORECASE)

            for match in matches:
                full_match = match.group(0)
                article_num = int(match.group(2))
                article_title = clean_text(match.group(3)) if match.group(3) else None
                article_content = clean_text(full_match)

                if len(article_content) > 50:  # Skip very short/empty articles
                    article_id = str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"{document_id}_dieu_{article_num}"))

                    articles.append(ParsedArticle(
                        id=article_id,
                        document_id=document_id,
                        article_number=article_num,
                        title=article_title,
                        content=article_content,
                        chapter=current_chapter,
                    ))

        return articles

    def index_document(self, doc_path: Path) -> tuple[int, list[str]]:
        """
        Index a single document from JSON file.

        Returns:
            Tuple of (articles_indexed, errors)
        """
        errors = []

        try:
            with open(doc_path, 'r', encoding='utf-8') as f:
                doc_data = json.load(f)

            # Insert document into SQLite
            doc_id = doc_data.get('document_number', doc_path.stem).replace('/', '_')
            doc_record = {
                'id': doc_id,
                'document_type': doc_data.get('document_type', 'luat'),
                'document_number': doc_data.get('document_number', 'Unknown'),
                'title': doc_data.get('title', 'Unknown'),
                'effective_date': doc_data.get('effective_date'),
                'issuing_authority': doc_data.get('issuing_authority'),
                'source_url': doc_data.get('url'),
                'raw_content': doc_data.get('html_content'),
                'status': 'active',
            }
            insert_document(doc_record)

            # Parse articles from HTML content
            html_content = doc_data.get('html_content', '')
            articles = self.parse_html_articles(html_content, doc_id)

            if not articles:
                errors.append(f"No articles found in {doc_path.name}")
                return 0, errors

            # Insert articles into SQLite
            for article in articles:
                article_record = {
                    'id': article.id,
                    'document_id': article.document_id,
                    'article_number': article.article_number,
                    'title': article.title,
                    'content': article.content,
                    'chapter': article.chapter,
                }
                insert_article(article_record)

            # Add to vector store
            articles_for_chroma = [
                {
                    'id': a.id,
                    'content': a.content,
                    'document_id': a.document_id,
                    'document_title': doc_data.get('title', 'Unknown'),
                    'article_number': a.article_number,
                    'title': a.title,
                    'document_type': doc_data.get('document_type', 'luat'),
                    'chapter': a.chapter,
                }
                for a in articles
            ]
            add_articles(articles_for_chroma)

            return len(articles), errors

        except Exception as e:
            errors.append(f"Error processing {doc_path.name}: {str(e)}")
            return 0, errors

    def index_from_directory(self) -> IndexResult:
        """
        Process all documents in input directory.
        """
        # Initialize databases
        init_db()
        init_chroma()

        total_documents = 0
        total_articles = 0
        all_errors = []

        # Find all JSON files in input directory
        json_files = list(self.input_dir.glob("*.json"))

        if not json_files:
            all_errors.append(f"No JSON files found in {self.input_dir}")
            return IndexResult(
                documents_processed=0,
                articles_indexed=0,
                errors=all_errors,
            )

        for json_file in json_files:
            articles_count, errors = self.index_document(json_file)
            total_documents += 1
            total_articles += articles_count
            all_errors.extend(errors)

        return IndexResult(
            documents_processed=total_documents,
            articles_indexed=total_articles,
            errors=all_errors,
        )

    def get_index_stats(self) -> dict:
        """Get statistics about the current index"""
        articles = get_all_articles()
        return {
            'total_articles': len(articles),
            'documents': len(set(a['document_id'] for a in articles)),
        }


def index_documents(input_dir: str = "./data/raw") -> IndexResult:
    """Convenience function to index documents"""
    config = IndexConfig(input_dir=input_dir)
    indexer = IndexerService(config)
    return indexer.index_from_directory()
