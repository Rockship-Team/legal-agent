"""Chat agent service with RAG"""

from groq import Groq
from typing import Optional
import re

from legal_chatbot.utils.config import get_settings
from legal_chatbot.db.chroma import search_articles
from legal_chatbot.db.sqlite import search_articles_by_ids
from legal_chatbot.models.chat import ChatResponse, Citation
from legal_chatbot.utils.vietnamese import extract_all_article_references


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
    """Chat service with RAG capabilities"""

    def __init__(self):
        settings = get_settings()
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self.top_k = settings.search_top_k

    def _build_context(self, query: str) -> tuple[str, list[dict]]:
        """
        Build RAG context from search results.

        Returns:
            Tuple of (context_string, search_results)
        """
        # Search for relevant articles
        search_results = search_articles(query, top_k=self.top_k)

        if not search_results:
            return "", []

        # Get full article content from SQLite
        article_ids = [r['id'] for r in search_results]
        articles = search_articles_by_ids(article_ids)

        # Build context string
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

        # Merge search results with full articles
        enriched_results = []
        for result in search_results:
            for article in articles:
                if article['id'] == result['id']:
                    enriched_results.append({
                        **result,
                        **article
                    })
                    break

        return context, enriched_results

    def _extract_citations(self, answer: str, search_results: list[dict]) -> list[Citation]:
        """Extract citations from the answer text"""
        citations = []

        # Extract article references from answer
        refs = extract_all_article_references(answer)

        for article_num, full_match in refs:
            # Find matching article in search results
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

        # Remove duplicates
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
        """
        Process a user query and return a response with citations.

        Args:
            query: User's question

        Returns:
            ChatResponse with answer, citations, and suggestions
        """
        # Build RAG context
        context, search_results = self._build_context(query)

        # Build messages
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

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

        # Call Groq API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        answer = response.choices[0].message.content

        # Extract citations and suggestions
        citations = self._extract_citations(answer, search_results)
        suggestions = self._suggest_templates(query, answer)

        return ChatResponse(
            answer=answer,
            citations=citations,
            suggested_templates=suggestions,
            follow_up_questions=[]
        )


# Singleton instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get or create chat service singleton"""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
