# Chat Agent Module Contract

## Overview
The Chat Agent handles user interactions, retrieves relevant legal information, and generates responses using Groq LLM.

## Interface

### ChatService

```python
from abc import ABC, abstractmethod
from typing import List, Optional, AsyncIterator
from pydantic import BaseModel

class ChatConfig(BaseModel):
    model: str = "llama-3.3-70b-versatile"
    temperature: float = 0.3
    max_tokens: int = 4096
    top_k_retrieval: int = 5

class Citation(BaseModel):
    article_id: str
    article_number: int
    document_title: str
    relevance_score: float
    excerpt: str

class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]
    suggested_templates: List[str]
    follow_up_questions: List[str]

class ChatService(ABC):
    @abstractmethod
    async def chat(
        self,
        query: str,
        session_id: Optional[str] = None,
        config: Optional[ChatConfig] = None
    ) -> ChatResponse:
        """
        Process user query and return response with citations.

        1. Retrieve relevant articles from knowledge base
        2. Build RAG context
        3. Generate response via Groq LLM
        4. Extract citations and suggestions
        """
        pass

    @abstractmethod
    async def stream_chat(
        self,
        query: str,
        session_id: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        Stream response tokens for real-time display.
        """
        pass

    @abstractmethod
    def get_session_context(self, session_id: str) -> dict:
        """
        Get collected context from chat session.
        Used for document generation.
        """
        pass
```

## CLI Contract

```bash
# Interactive chat
legal-chatbot chat "Điều kiện cho thuê nhà là gì?"

# Output: Formatted response
╭─ Legal Assistant ─────────────────────────────────────────╮
│ Theo quy định pháp luật, điều kiện cho thuê nhà bao gồm:  │
│                                                            │
│ 1. Người cho thuê phải là chủ sở hữu hợp pháp...          │
│ 2. Nhà ở phải đảm bảo chất lượng...                       │
│                                                            │
│ 📚 Nguồn:                                                  │
│ - Điều 121, Luật Nhà ở 2014                               │
│ - Điều 472, Bộ luật Dân sự 2015                           │
│                                                            │
│ 📝 Bạn có muốn tạo hợp đồng thuê nhà không?               │
╰───────────────────────────────────────────────────────────╯

# JSON output mode
legal-chatbot chat "Điều kiện cho thuê nhà?" --json
{
  "answer": "...",
  "citations": [...],
  "suggested_templates": ["rental"]
}
```

## RAG Pipeline

```
User Query
    │
    ▼
┌─────────────────┐
│ Query Analysis  │ → Intent, entities, legal domain
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Vector Search   │ → ChromaDB semantic search
│ (top-k=5)       │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Context Builder │ → Format retrieved articles
│                 │ → Apply token limit
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Groq LLM        │ → Generate grounded response
│                 │ → Include citations
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Post-process    │ → Extract citations
│                 │ → Suggest templates
└─────────────────┘
```

## System Prompt Template

```python
SYSTEM_PROMPT = """
Bạn là trợ lý pháp lý của một công ty luật Việt Nam.
Nhiệm vụ của bạn là:

1. Trả lời câu hỏi pháp lý dựa HOÀN TOÀN vào các điều luật được cung cấp
2. LUÔN trích dẫn nguồn (số Điều, tên văn bản pháp luật)
3. Nếu không tìm thấy thông tin liên quan, nói rõ "Tôi không tìm thấy thông tin"
4. Đề xuất mẫu hợp đồng nếu phù hợp với câu hỏi

Các điều luật liên quan:
{context}

Lưu ý: Đây chỉ là thông tin tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp.
"""
```

## Dependencies
- groq: Groq API client
- chromadb: Vector retrieval

## Testing Contract

```python
async def test_chat_returns_citations():
    """Chat should include relevant citations"""
    response = await chat_service.chat("Điều kiện cho thuê nhà?")
    assert response.citations
    assert all(c.article_number for c in response.citations)

async def test_chat_grounds_in_context():
    """Chat should only use information from retrieved context"""
    # Mock retrieval to return specific articles
    # Verify response only contains info from those articles
```
