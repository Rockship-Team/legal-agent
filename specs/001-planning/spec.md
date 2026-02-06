# Legal Chatbot - Specification

## 1. Tổng quan dự án

### 1.1 Mô tả
Xây dựng một chatbot CLI cho công ty luật, cho phép người dùng hỏi các vấn đề pháp lý và nhận được tư vấn chính xác cùng với các mẫu hợp đồng/văn bản pháp lý phù hợp.

### 1.2 Ví dụ Use Case
- Người dùng hỏi: "Điều kiện cho thuê nhà là gì?"
- Agent sẽ:
  1. Truy xuất các điều luật liên quan từ database
  2. Tổng hợp và giải thích điều kiện pháp lý
  3. Đề xuất và generate mẫu hợp đồng cho thuê nhà phù hợp

## 2. Yêu cầu chức năng

### 2.1 CLI Interface
- Giao diện command line đơn giản
- Test output qua terminal
- Hỗ trợ tiếng Việt

### 2.2 Knowledge Base (Cơ sở dữ liệu pháp luật)
- **Nguồn dữ liệu**: Thu thập từ [Thư viện Pháp luật](https://thuvienphapluat.vn/)
- **Loại dữ liệu cần thu thập**:
  - Bộ luật Dân sự
  - Luật Nhà ở
  - Luật Kinh doanh bất động sản
  - Luật Hợp đồng
  - Các nghị định, thông tư hướng dẫn
  - Các mẫu hợp đồng chuẩn

### 2.3 Document Generation
- Generate file PDF hợp đồng/văn bản pháp lý
- Tự động điền thông tin từ context hội thoại
- Đảm bảo format chuẩn theo quy định pháp luật

## 3. Kiến trúc hệ thống

### 3.1 Nguyên tắc thiết kế

> **QUAN TRỌNG**: Hạn chế sử dụng search/retrieval interface trực tiếp vì dễ gây sai sót.

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI INTERFACE                           │
│                    (Python Command Line)                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AGENT ORCHESTRATOR                         │
│  - Intent Classification                                        │
│  - Context Management                                           │
│  - Response Generation (Groq LLM)                               │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  LEGAL KNOWLEDGE│ │   DOCUMENT      │ │   DATA          │
│  BASE           │ │   GENERATOR     │ │   COLLECTOR     │
│                 │ │                 │ │                 │
│ - Pre-indexed   │ │ - PDF Export    │ │ - User Info     │
│   legal docs    │ │ - Contract      │ │ - Case Details  │
│ - Structured    │ │   Templates     │ │ - Requirements  │
│   data format   │ │                 │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### 3.2 Data Pipeline

```
[thuvienphapluat.vn]
        │
        ▼ (Crawl & Extract)
┌─────────────────┐
│  Raw Legal Data │
│  - HTML content │
│  - PDF files    │
└─────────────────┘
        │
        ▼ (Process & Structure)
┌─────────────────┐
│ Structured Data │
│ - JSON/YAML     │
│ - Categorized   │
│ - Indexed       │
└─────────────────┘
        │
        ▼ (Store)
┌─────────────────┐
│  Knowledge Base │
│ - Vector DB     │
│ - SQLite        │
└─────────────────┘
```

## 4. Chiến lược đảm bảo độ chính xác

### 4.1 Pre-indexed Knowledge Base
- **KHÔNG** sử dụng real-time search/retrieval từ internet
- Xây dựng database nội bộ với dữ liệu đã được verify
- Cập nhật định kỳ khi có thay đổi pháp luật

### 4.2 Data Collaboration Flow
Khi generate document, agent phải:
1. **Thu thập thông tin** từ người dùng qua hội thoại
2. **Xác nhận** các thông tin quan trọng trước khi generate
3. **Cross-reference** với knowledge base để đảm bảo tuân thủ pháp luật
4. **Review** output trước khi trả về người dùng

### 4.3 Document Generation Requirements
- Template-based generation với các trường có thể điền
- Validate dữ liệu đầu vào theo quy định pháp luật
- Watermark hoặc disclaimer cho bản draft
- Export formats: PDF

## 5. Các module cần phát triển

### 5.1 Data Crawler (Python)
- Crawl dữ liệu từ thuvienphapluat.vn
- Parse và extract nội dung luật
- Lưu trữ có cấu trúc

### 5.2 Knowledge Indexer (Python)
- Index dữ liệu cho semantic search
- Categorize theo lĩnh vực pháp luật
- Build relationship graph giữa các điều luật

### 5.3 Chat Agent (Python)
- Intent recognition
- Context management
- Response generation với citations
- Sử dụng Groq API (LLaMA models)

### 5.4 Document Generator (Python)
- Template engine
- PDF generation
- Data validation

## 6. Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Database | SQLite + ChromaDB (vector) |
| LLM | Groq API (LLaMA 3) |
| Document Gen | ReportLab / WeasyPrint |
| Crawler | Playwright / BeautifulSoup |
| CLI | Click / Typer |

## 7. Groq API Configuration

```
GROQ_API_KEY=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
```

Supported models:
- `llama-3.3-70b-versatile` - Best for complex reasoning
- `llama-3.1-8b-instant` - Fast responses
- `mixtral-8x7b-32768` - Good for long context

## 8. Testing Strategy

### 8.1 CLI Test Commands
```bash
# Test crawler
python -m legal_chatbot crawl --source thuvienphapluat --limit 10

# Test indexer
python -m legal_chatbot index --input ./data/raw

# Test chat
python -m legal_chatbot chat "Điều kiện cho thuê nhà là gì?"

# Test document generation
python -m legal_chatbot generate --template rental_contract --output contract.pdf
```

### 8.2 Output Verification
- Kiểm tra response có citations từ knowledge base
- Verify document PDF được tạo đúng format
- Check độ chính xác thông tin pháp lý

## 9. Lưu ý quan trọng

1. **Bản quyền dữ liệu**: Cần xem xét điều khoản sử dụng của thuvienphapluat.vn
2. **Disclaimer**: Chatbot chỉ mang tính chất tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp
3. **Cập nhật**: Cần cơ chế cập nhật khi có thay đổi pháp luật
4. **Accuracy**: Ưu tiên độ chính xác hơn tốc độ - verify trước khi trả lời

## 10. Phases phát triển

### Phase 1: Foundation
- [ ] Setup Python project structure
- [ ] Implement crawler module
- [ ] Basic CLI interface

### Phase 2: Knowledge Base
- [ ] Index dữ liệu pháp luật
- [ ] Implement vector search với ChromaDB
- [ ] Test retrieval accuracy

### Phase 3: Chat Agent
- [ ] Integrate Groq API
- [ ] Implement RAG pipeline
- [ ] Test Q&A với citations

### Phase 4: Document Generation
- [ ] Create contract templates
- [ ] PDF generation
- [ ] Variable substitution
