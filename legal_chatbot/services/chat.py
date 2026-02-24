"""Chat agent service with DB-only RAG (no web search)"""

import logging
from typing import Optional

from legal_chatbot.utils.config import get_settings
from legal_chatbot.utils.llm import call_llm
from legal_chatbot.models.chat import ChatResponse, Citation
from legal_chatbot.utils.vietnamese import extract_all_article_references

logger = logging.getLogger(__name__)


# Category detection keywords (Vietnamese)
CATEGORY_KEYWORDS = {
    "dat_dai": ["đất", "đất đai", "quyền sử dụng đất", "chuyển nhượng đất", "thửa đất"],
    "nha_o": ["nhà", "nhà ở", "thuê nhà", "mua nhà", "căn hộ", "chung cư"],
    "lao_dong": ["lao động", "việc làm", "hợp đồng lao động", "tiền lương", "sa thải", "thử việc", "nghỉ việc"],
    "dan_su": ["dân sự", "vay", "ủy quyền", "dịch vụ", "mua bán", "hợp đồng", "bồi thường"],
    "doanh_nghiep": ["doanh nghiệp", "công ty", "cổ đông", "thành lập công ty"],
    "thuong_mai": ["thương mại", "xuất khẩu", "nhập khẩu", "mua bán hàng hóa"],
}

# System prompt for Vietnamese legal assistant
SYSTEM_PROMPT = """Bạn là trợ lý pháp lý của một công ty luật Việt Nam.
Nhiệm vụ của bạn là:

1. Trả lời câu hỏi pháp lý dựa HOÀN TOÀN vào các điều luật được cung cấp trong phần CONTEXT
2. LUÔN trích dẫn nguồn (số Điều, tên văn bản pháp luật) khi đưa ra thông tin
3. Nếu không tìm thấy thông tin liên quan trong CONTEXT, nói rõ "Tôi không tìm thấy thông tin liên quan trong cơ sở dữ liệu"
4. Đề xuất mẫu hợp đồng phù hợp nếu câu hỏi liên quan đến giao dịch (thuê nhà, mua bán, dịch vụ)
5. Trả lời bằng tiếng Việt, rõ ràng và dễ hiểu

Lưu ý quan trọng:
- Đây chỉ là thông tin tham khảo, KHÔNG thay thế tư vấn pháp lý chuyên nghiệp
- Chỉ sử dụng thông tin từ CONTEXT, không tự suy diễn hoặc thêm thông tin ngoài
- Nếu được hỏi về vấn đề ngoài phạm vi pháp luật, từ chối lịch sự"""


class ChatService:
    """Chat service with DB-only RAG capabilities (no web search)."""

    def __init__(self):
        settings = get_settings()
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self.top_k = settings.search_top_k
        self._audit = None
        self._db = None
        self._embedding = None

    @property
    def audit(self):
        """Lazy-load audit service to avoid import cycles."""
        if self._audit is None:
            try:
                from legal_chatbot.db.supabase import get_database
                from legal_chatbot.services.audit import AuditService
                self._audit = AuditService(get_database())
            except Exception:
                self._audit = None
        return self._audit

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

    def _detect_category(self, query: str) -> Optional[str]:
        """Detect legal domain from user query.

        Strategy:
        1. Keyword matching (fast, no API call)
        2. LLM classification (fallback)
        """
        query_lower = query.lower()

        # Layer 1: Keyword matching
        best_match = None
        best_score = 0
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > best_score:
                best_score = score
                best_match = category

        if best_score > 0:
            return best_match

        # Layer 2: LLM classification fallback
        try:
            categories_str = ", ".join(CATEGORY_KEYWORDS.keys())
            result = call_llm(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"Phân loại câu hỏi pháp lý vào một trong các lĩnh vực: {categories_str}. "
                            "Chỉ trả về TÊN lĩnh vực, không giải thích. "
                            "Nếu không xác định được, trả về 'unknown'."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                temperature=0,
                max_tokens=20,
            ).strip().lower()
            if result in CATEGORY_KEYWORDS:
                return result
        except Exception as e:
            logger.warning(f"LLM category detection failed: {e}")

        return None

    def _check_data_availability(self, category: Optional[str]) -> dict:
        """Check if category has indexed data.

        Returns dict with has_data, article_count, available_categories.
        """
        settings = get_settings()
        if settings.db_mode != "supabase":
            return {"has_data": True, "article_count": 0, "available_categories": []}

        try:
            all_cats = self.db.get_all_categories_with_stats()

            available = [
                {
                    "name": c["name"],
                    "display_name": c["display_name"],
                    "article_count": c.get("article_count", 0),
                    "document_count": c.get("document_count", 0),
                }
                for c in all_cats
                if c.get("article_count", 0) > 0
            ]

            if category:
                cat_stats = next(
                    (c for c in all_cats if c["name"] == category), None
                )
                if cat_stats and cat_stats.get("article_count", 0) > 0:
                    return {
                        "has_data": True,
                        "article_count": cat_stats["article_count"],
                        "available_categories": available,
                    }
                else:
                    return {
                        "has_data": False,
                        "article_count": 0,
                        "available_categories": available,
                    }

            # No category detected — still have data if any category has articles
            return {
                "has_data": len(available) > 0,
                "article_count": sum(c["article_count"] for c in available),
                "available_categories": available,
            }
        except Exception as e:
            logger.warning(f"Data availability check failed: {e}")
            return {"has_data": True, "article_count": 0, "available_categories": []}

    def _build_no_data_message(
        self, category: Optional[str], available: list[dict]
    ) -> str:
        """Generate natural, friendly no-data message."""
        if category:
            category_display = category.replace("_", " ")
            msg = f"Hiện tại mình chưa có dữ liệu về lĩnh vực {category_display} nên không thể tư vấn chính xác được."
        else:
            msg = "Mình chưa xác định được lĩnh vực pháp lý của câu hỏi này."

        if available:
            cat_list = ", ".join(
                f"{c['display_name']} ({c['article_count']} điều luật)"
                for c in available
            )
            msg += f"\n\nMình có thể giúp bạn về: {cat_list}."
            msg += "\n\nBạn muốn hỏi về lĩnh vực nào?"

        return msg

    def _build_insufficient_data_message(self, query: str, category: str) -> str:
        """Generate friendly message when search returns 0 results."""
        return "Mình không tìm thấy điều luật phù hợp với câu hỏi này. Bạn thử diễn đạt cụ thể hơn?"

    def _build_context_supabase(self, query: str) -> tuple[str, list[dict]]:
        """Build context using Supabase vector search."""
        try:
            query_embedding = self.embedding.embed_single(query)

            articles = self.db.search_articles(
                query_embedding=query_embedding,
                top_k=self.top_k,
            )

            if not articles:
                return "", []

            context_parts = []
            for article in articles:
                doc_title = article.get('document_title', 'Văn bản pháp luật')
                article_num = article.get('article_number', '')
                article_title = article.get('title', '')
                content = article.get('content', '')

                header = f"[{doc_title} - Điều {article_num}"
                if article_title:
                    header += f": {article_title}"
                header += "]"

                context_parts.append(f"{header}\n{content}")

            context = "\n\n---\n\n".join(context_parts)

            for article in articles:
                if 'similarity' in article and 'score' not in article:
                    article['score'] = article['similarity']

            return context, articles
        except Exception as e:
            logger.error(f"Supabase search failed: {e}")
            return "", []

    def _extract_citations(self, answer: str, search_results: list[dict]) -> list[Citation]:
        """Extract citations from the answer text"""
        citations = []

        refs = extract_all_article_references(answer)

        for article_num, full_match in refs:
            for result in search_results:
                if result.get('article_number') == article_num:
                    citations.append(Citation(
                        article_id=result['id'],
                        article_number=article_num,
                        document_title=result.get('document_title', ''),
                        relevance_score=result.get('score', 0),
                        excerpt=result.get('content', '')[:200] + '...' if result.get('content') else None
                    ))
                    break

        seen = set()
        unique_citations = []
        for c in citations:
            key = (c.article_id, c.article_number)
            if key not in seen:
                seen.add(key)
                unique_citations.append(c)

        return unique_citations

    def _suggest_templates(self, query: str, answer: str) -> list[str]:
        """Suggest relevant contract templates based on query and answer"""
        suggestions = []

        query_lower = query.lower()
        answer_lower = answer.lower()
        combined = query_lower + " " + answer_lower

        if any(kw in combined for kw in ['thuê', 'cho thuê', 'thuê nhà', 'thuê phòng']):
            suggestions.append('rental')
        if any(kw in combined for kw in ['mua bán', 'mua', 'bán', 'chuyển nhượng']):
            suggestions.append('sale')
        if any(kw in combined for kw in ['dịch vụ', 'cung cấp', 'thực hiện']):
            suggestions.append('service')
        if any(kw in combined for kw in ['lao động', 'tuyển dụng', 'nhân viên', 'công việc']):
            suggestions.append('employment')

        return suggestions

    def chat(self, query: str) -> ChatResponse:
        """Process a user query using DB-only RAG.

        Flow:
        1. Detect category from query
        2. Check data availability
        3. If no data → return no-data message
        4. Build context from Supabase
        5. If empty results → insufficient data message
        6. Call LLM → response
        7. Save audit
        """
        settings = get_settings()

        # Step 1: Detect category
        category = self._detect_category(query)

        # Step 2: Check data availability (supabase mode only)
        if settings.db_mode == "supabase":
            availability = self._check_data_availability(category)

            # Step 3: No data → friendly message
            if not availability["has_data"]:
                no_data_msg = self._build_no_data_message(
                    category, availability["available_categories"]
                )
                return ChatResponse(
                    answer=no_data_msg,
                    citations=[],
                    suggested_templates=[],
                    follow_up_questions=[],
                    has_data=False,
                    category=category,
                )

        # Step 4: Build RAG context (DB-only)
        context, search_results = self._build_context_supabase(query)

        # Step 5: Empty results → insufficient data
        if not context:
            if settings.db_mode == "supabase":
                msg = self._build_insufficient_data_message(query, category or "")
                return ChatResponse(
                    answer=msg,
                    citations=[],
                    suggested_templates=[],
                    follow_up_questions=[],
                    has_data=False,
                    category=category,
                )
            # SQLite fallback: still try LLM without context
            context = ""
            search_results = []

        # Step 6: Build messages and call LLM
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if context:
            user_content = f"""CONTEXT (Các điều luật liên quan):
{context}

---

CÂU HỎI CỦA NGƯỜI DÙNG:
{query}

Hãy trả lời dựa trên các điều luật trong CONTEXT ở trên."""
        else:
            user_content = f"""CÂU HỎI CỦA NGƯỜI DÙNG:
{query}

Lưu ý: Không tìm thấy điều luật liên quan trong cơ sở dữ liệu. Vui lòng thông báo cho người dùng."""

        messages.append({"role": "user", "content": user_content})

        answer = call_llm(
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        citations = self._extract_citations(answer, search_results)
        suggestions = self._suggest_templates(query, answer)

        chat_response = ChatResponse(
            answer=answer,
            citations=citations,
            suggested_templates=suggestions,
            follow_up_questions=[],
            has_data=True,
            category=category,
        )

        # Step 7: Save audit trail
        try:
            if self.audit:
                from legal_chatbot.models.audit import ArticleSource, ResearchAudit
                sources = [
                    ArticleSource(
                        article_id=r.get("id", ""),
                        article_number=r.get("article_number", 0),
                        document_title=r.get("document_title", ""),
                        similarity=r.get("score", 0.0),
                    )
                    for r in search_results
                ]
                audit_entry = ResearchAudit(
                    query=query,
                    sources=sources,
                    response=answer,
                    law_versions=self.audit.build_law_versions(
                        [r.get("id", "") for r in search_results]
                    ),
                )
                self.audit.save_research_audit(audit_entry)
        except Exception as e:
            logger.warning(f"Audit save failed (non-critical): {e}")

        return chat_response


# Singleton instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get or create chat service singleton"""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
