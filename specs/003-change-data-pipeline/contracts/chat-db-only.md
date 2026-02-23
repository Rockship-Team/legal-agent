# Contract: Chat Service (DB-Only)

**Module**: `legal_chatbot/services/chat.py` (modified)

## Interface Changes

```python
class ChatService:
    """Modified: DB-only RAG, no web search fallback."""

    async def chat(self, query: str) -> ChatResponse:
        """Answer legal question using DB data only.

        Changes from 002:
        - REMOVED: web search fallback
        - REMOVED: research.py integration
        - ADDED: category detection
        - ADDED: data availability check
        - ADDED: no-data response

        Flow:
        1. _detect_category(query) → category name
        2. _check_data_availability(category) → DataAvailability
        3. If no data → return no-data message + available categories
        4. _build_context_supabase(query) → RAG context
        5. If empty results → return insufficient-data message
        6. _call_llm(context, query) → response
        7. _save_audit(query, context, response)

        Returns:
            ChatResponse with has_data=True/False
        """

    async def _detect_category(self, query: str) -> Optional[str]:
        """Detect legal domain from user query.

        Strategy:
        1. Keyword matching (fast, no API call):
           - 'đất' → 'dat_dai'
           - 'nhà', 'thuê nhà' → 'nha_o'
           - 'lao động', 'việc làm' → 'lao_dong'
        2. LLM classification (fallback):
           - Send query + category list to Groq
           - Return classified category

        Returns:
            Category name or None if can't determine
        """

    async def _check_data_availability(
        self, category: Optional[str]
    ) -> DataAvailability:
        """Check if category has indexed data.

        Args:
            category: Category name or None

        Returns:
            DataAvailability with has_data, article_count, available_categories

        Implementation:
        - Query legal_categories table
        - Check article_count > 0
        - Cache results for 5 minutes
        """

    def _build_no_data_message(
        self, category: Optional[str], available: List[CategoryInfo]
    ) -> str:
        """Generate user-friendly no-data message.

        Template:
        '⚠ Hệ thống chưa có dữ liệu về lĩnh vực {category}.
         Hiện có: {list of available categories with counts}'
        """

    def _build_insufficient_data_message(
        self, query: str, category: str
    ) -> str:
        """Generate message when search returns 0 results.

        Template:
        'Không tìm thấy điều luật phù hợp cho câu hỏi...'
        """
```

## Removed Methods

| Method | Reason |
|--------|--------|
| `_build_context_legacy()` | ChromaDB no longer used |
| All `research.py` references | No web search in chat flow |

## Dependencies

- `db/supabase.py` (vector search, category stats)
- `services/embedding.py` (query embedding)
- `utils/config.py` (Settings — `CHAT_MODE=db_only`)
