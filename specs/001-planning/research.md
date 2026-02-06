# Research: Legal Chatbot

**Date**: 2026-02-05 | **Spec**: [spec.md](./spec.md)

## Phase 0: Research Findings

### 1. Groq API Integration

**Selected Model**: `llama-3.3-70b-versatile`
- Best for complex legal reasoning and Vietnamese language understanding
- 32K context window sufficient for legal document analysis
- Fast inference speeds (Groq's specialty)

**Alternative Models**:
- `llama-3.1-8b-instant` - For quick follow-up questions
- `mixtral-8x7b-32768` - Extended context for long documents

**API Usage Pattern**:
```python
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
completion = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[...],
    temperature=0.3,  # Lower for factual legal responses
    max_tokens=4096
)
```

### 2. Data Source Analysis: thuvienphapluat.vn

**Structure Observed**:
- Legal documents organized by category (Bộ luật, Luật, Nghị định, Thông tư)
- Each document has unique identifier and metadata
- HTML content with structured sections (Điều, Khoản, Điểm)

**Crawling Considerations**:
- Rate limiting required (respect robots.txt)
- Session management for pagination
- PDF downloads may require authentication
- Vietnamese text encoding: UTF-8 with proper normalization

**Data Categories to Crawl**:
1. Bộ luật Dân sự 2015 (Civil Code)
2. Luật Nhà ở 2014 (Housing Law)
3. Luật Kinh doanh bất động sản 2014 (Real Estate Business Law)
4. Related Nghị định and Thông tư

### 3. RAG Pipeline Design

**Vector Database**: ChromaDB
- Lightweight, embedded, perfect for CLI application
- Python native with good Vietnamese text support
- Persistent storage to SQLite backend

**Embedding Strategy**:
- Use `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Supports Vietnamese text natively
- 384-dimensional vectors

**Chunking Strategy for Legal Documents**:
```
Document → Articles (Điều) → Clauses (Khoản) → Points (Điểm)
```
- Chunk at Article level (Điều) for context preservation
- Include metadata: document name, article number, effective date
- Overlap: 100 tokens between chunks

**Retrieval Strategy**:
1. Semantic search with ChromaDB (top-k=5)
2. Re-rank based on document relevance and recency
3. Filter by legal category if specified

### 4. PDF Generation

**Selected Library**: ReportLab
- Pure Python, no external dependencies
- Full Unicode/Vietnamese support
- Programmatic PDF generation
- Template-based approach possible

**Alternative**: WeasyPrint
- HTML/CSS to PDF conversion
- Better for complex layouts
- Requires external dependencies (GTK)

**Decision**: Start with ReportLab for simplicity, migrate to WeasyPrint if complex templates needed.

### 5. CLI Framework

**Selected**: Typer
- Built on Click, modern Python typing
- Automatic help generation
- Rich terminal output support

**Commands Structure**:
```bash
legal-chatbot crawl [--source] [--limit]
legal-chatbot index [--input]
legal-chatbot chat "question"
legal-chatbot generate [--template] [--output]
```

### 6. Vietnamese Language Processing

**Challenges**:
- Diacritics handling (Tổ hợp vs Dựng sẵn encoding)
- Legal terminology standardization
- Question understanding in natural Vietnamese

**Solutions**:
- NFD normalization for consistent text comparison
- Custom legal term dictionary for embeddings
- Prompt engineering for Vietnamese Q&A

## Resolved Unknowns

| Question | Resolution |
|----------|------------|
| Which LLM provider? | Groq API with LLaMA 3.3 70B |
| Vector database? | ChromaDB (embedded, SQLite backend) |
| PDF generation? | ReportLab (pure Python) |
| Embedding model? | paraphrase-multilingual-MiniLM-L12-v2 |
| CLI framework? | Typer |
| How to handle Vietnamese? | UTF-8 + NFD normalization |

## Open Risks

| Risk | Mitigation |
|------|------------|
| Copyright of legal content | Add disclaimer, cite sources |
| Crawling rate limits | Implement backoff, cache aggressively |
| LLM hallucination | Ground responses in retrieved documents only |
| Vietnamese embedding quality | Test with legal-specific queries |

## Dependencies to Install

```
groq>=0.4.0
chromadb>=0.4.0
sentence-transformers>=2.2.0
typer>=0.9.0
reportlab>=4.0.0
playwright>=1.40.0
beautifulsoup4>=4.12.0
pydantic>=2.0.0
python-dotenv>=1.0.0
```
