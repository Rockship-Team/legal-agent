"""Research service — DB-only deep search (no LLM, no web crawling)"""

import logging
from typing import Optional
from pydantic import BaseModel

from legal_chatbot.utils.config import get_settings

logger = logging.getLogger(__name__)


class ResearchResult(BaseModel):
    """Result from research service"""
    query: str
    raw_content: str = ""
    analyzed_content: str = ""
    legal_articles: list[dict] = []
    suggested_contract_type: Optional[str] = None
    has_data: bool = True
    available_categories: list[dict] = []


class ResearchService:
    """DB-only research service — deep vector search, no LLM."""

    def __init__(self):
        self._db = None
        self._embedding = None

    @property
    def db(self):
        """Lazy-load database client."""
        if self._db is None:
            from legal_chatbot.db.supabase import get_database
            self._db = get_database()
        return self._db

    @property
    def embedding(self):
        """Lazy-load embedding service."""
        if self._embedding is None:
            from legal_chatbot.services.embedding import EmbeddingService
            self._embedding = EmbeddingService()
        return self._embedding

    async def research(self, query: str, max_sources: int = 20) -> ResearchResult:
        """Research a legal topic using DB-only deep search.

        Flow:
        1. Vector search with top_k (deep)
        2. Structure results by document
        3. Return raw articles for caller to analyze

        No web crawling, no LLM — all data from Supabase pgvector.
        """
        result = ResearchResult(query=query)

        settings = get_settings()
        if settings.db_mode != "supabase":
            result.analyzed_content = "Research requires db_mode=supabase."
            result.has_data = False
            return result

        # Get available categories for no-data response
        try:
            result.available_categories = self._get_available_categories()
        except Exception:
            pass

        # Step 1: Deep vector search
        try:
            query_embedding = self.embedding.embed_single(query)
            articles = self.db.search_articles(
                query_embedding=query_embedding,
                top_k=max_sources,
            )
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            result.analyzed_content = f"Lỗi tìm kiếm: {e}"
            result.has_data = False
            return result

        if not articles:
            cats = result.available_categories
            if cats:
                cat_list = ", ".join(f"{c['display_name']} ({c['article_count']} điều)" for c in cats)
                result.analyzed_content = (
                    f"Mình chưa có dữ liệu về chủ đề này. "
                    f"Hiện mình có thể giúp về: {cat_list}."
                )
            else:
                result.analyzed_content = "Chưa có dữ liệu pháp luật nào trong hệ thống."
            result.has_data = False
            return result

        # Step 2: Structure results
        result.legal_articles = [
            {
                "article_id": a.get("id", ""),
                "article_number": a.get("article_number", 0),
                "title": a.get("title", ""),
                "content": a.get("content", ""),
                "document_title": a.get("document_title", ""),
                "document_number": a.get("document_number", ""),
                "similarity": a.get("similarity", 0),
            }
            for a in articles
        ]

        # Build raw content (formatted for display/analysis)
        context_parts = []
        for a in articles:
            doc_title = a.get("document_title", "Văn bản pháp luật")
            article_num = a.get("article_number", "")
            title = a.get("title", "")
            content = a.get("content", "")
            header = f"Điều {article_num}" + (f": {title}" if title else "")
            context_parts.append(f"**{header}** ({doc_title})\n{content}")

        result.raw_content = "\n\n---\n\n".join(context_parts)
        result.analyzed_content = result.raw_content

        # Step 3: Contract relevance (simple keyword match)
        result.suggested_contract_type = self._detect_contract_type(query)

        return result

    def _detect_contract_type(self, query: str) -> Optional[str]:
        """Detect if query relates to a contract type."""
        query_lower = query.lower()

        mappings = [
            (["thuê nhà", "cho thuê nhà", "thuê phòng"], "cho_thue_nha"),
            (["thuê đất", "cho thuê đất"], "cho_thue_dat"),
            (["mua bán đất", "mua đất", "bán đất", "chuyển nhượng đất"], "mua_ban_dat"),
            (["mua bán nhà", "mua nhà", "bán nhà"], "mua_ban_nha"),
            (["lao động", "tuyển dụng", "nhân viên"], "hop_dong_lao_dong"),
            (["thử việc"], "thu_viec"),
            (["vay tiền", "vay tài sản", "cho vay"], "vay_tien"),
            (["ủy quyền"], "uy_quyen"),
            (["dịch vụ"], "dich_vu"),
        ]

        for keywords, contract_type in mappings:
            if any(kw in query_lower for kw in keywords):
                return contract_type

        return None

    def _get_available_categories(self) -> list[dict]:
        """Get categories that have articles in DB."""
        try:
            client = self.db._read()
            cats = (
                client.table("legal_categories")
                .select("name, display_name, article_count")
                .order("name")
                .execute()
            )
            return [
                {
                    "name": c["name"],
                    "display_name": c["display_name"],
                    "article_count": c.get("article_count", 0),
                }
                for c in (cats.data or [])
                if c.get("article_count", 0) > 0
            ]
        except Exception:
            return []


async def research_legal_topic(query: str, max_sources: int = 20) -> ResearchResult:
    """Convenience function for legal research"""
    service = ResearchService()
    return await service.research(query, max_sources)
