# 002 - Kết nối Database & Thiết kế Data Pipeline

## 1. Tổng quan

### 1.1 Vấn đề hiện tại

Hệ thống hiện tại có các hạn chế:

1. **Dữ liệu tĩnh**: Chỉ có 4 articles mẫu (Luật Nhà ở 2014), không đủ để tư vấn chính xác
2. **Không cập nhật**: Luật pháp Việt Nam thay đổi liên tục (sửa đổi, bổ sung, thay thế) — dữ liệu cũ = tư vấn sai
3. **Lưu trữ local**: SQLite + JSON file-based ChromaDB không scale, không verify được
4. **Không có pipeline**: Crawl thủ công, không có cơ chế tự động cập nhật luật mới
5. **Thiếu traceability**: Khi generate hợp đồng hoặc research, không lưu lại kết quả để kiểm chứng

### 1.2 Mục tiêu

- Kết nối **Supabase** (PostgreSQL + Storage) làm database chính để lưu trữ và verify dữ liệu
- Xây dựng **data pipeline** tự động crawl, parse, và index luật mới nhất theo từng lĩnh vực
- Crawl thử **luật mua bán đất** (Luật Đất đai 2024, Luật Kinh doanh BĐS 2023) làm test case
- Khi người dùng hỏi, hệ thống sử dụng dữ liệu crawl được để research **chính xác hơn**
- Lưu kết quả research & contract vào DB để **check-in** và audit

### 1.3 Ví dụ Use Case

```
Người dùng: "Điều kiện mua bán đất ở Việt Nam hiện tại là gì?"

Pipeline đã crawl:
  ✓ Luật Đất đai 2024 (có hiệu lực 01/01/2025)
  ✓ Nghị định 101/2024/NĐ-CP hướng dẫn
  ✓ Luật Kinh doanh BĐS 2023

Agent sẽ:
  1. Query Supabase → tìm articles liên quan từ Luật Đất đai 2024
  2. Cross-reference với nghị định hướng dẫn
  3. Tổng hợp điều kiện pháp lý HIỆN HÀNH (không dùng luật cũ đã hết hiệu lực)
  4. Đề xuất mẫu hợp đồng mua bán phù hợp
  5. Lưu kết quả research vào Supabase để audit
```

---

## 2. Yêu cầu chức năng

### 2.1 Supabase Integration

| Yêu cầu | Mô tả |
|----------|--------|
| Kết nối Supabase | Sử dụng `supabase-py` SDK, hỗ trợ cả REST API và Realtime |
| PostgreSQL tables | Migrate schema từ SQLite sang Supabase PostgreSQL |
| Row Level Security | Bảo vệ dữ liệu, phân quyền read/write |
| Storage | Lưu raw HTML/PDF của văn bản gốc vào Supabase Storage |
| Dual mode | Hỗ trợ cả Supabase (production) và SQLite (local dev/offline) |

### 2.2 Data Pipeline

| Yêu cầu | Mô tả |
|----------|--------|
| Crawl theo lĩnh vực | Tự động tìm và crawl luật mới nhất cho từng ngành (đất đai, nhà ở, dân sự, thương mại...) |
| Phát hiện luật mới | So sánh với DB hiện tại, chỉ crawl/update khi có thay đổi |
| Parse cấu trúc | Extract: Chương → Mục → Điều → Khoản → Điểm |
| Quản lý hiệu lực | Track trạng thái: `còn hiệu lực`, `hết hiệu lực`, `sửa đổi bổ sung` |
| Liên kết văn bản | Map quan hệ: văn bản A thay thế B, bổ sung C, hướng dẫn D |
| Scheduled crawl | Chạy định kỳ (daily/weekly) để cập nhật |
| Vector embedding | Tạo embeddings cho semantic search qua Supabase pgvector |

### 2.3 Research & Contract Audit Trail

| Yêu cầu | Mô tả |
|----------|--------|
| Lưu research results | Mỗi lần research, lưu query + sources + kết quả vào DB |
| Lưu generated contracts | Lưu metadata + nội dung hợp đồng đã generate |
| Version tracking | Track phiên bản luật được sử dụng cho mỗi kết quả |
| Audit log | Ghi lại ai hỏi gì, dùng nguồn nào, kết quả ra sao |

### 2.4 Slash Commands mới

```bash
# Pipeline commands
/legal.pipeline crawl dat_dai              # Crawl & index luật đất đai
/legal.pipeline crawl dat_dai --limit 5    # Giới hạn số documents
/legal.pipeline categories                 # Liệt kê các lĩnh vực có sẵn
/legal.pipeline status                     # Kiểm tra trạng thái pipeline

# Database commands
/legal.db migrate                          # Migrate schema lên Supabase
/legal.db status                           # Kiểm tra kết nối & stats

# Audit commands
/legal.audit list                          # Xem lịch sử research/contract
/legal.audit list --limit 5 --type research  # Lọc theo loại
/legal.audit show <id>                     # Xem chi tiết audit entry
/legal.audit verify <id>                   # Verify luật còn hiệu lực không
```

---

## 3. Kiến trúc hệ thống

### 3.1 Tổng quan kiến trúc mới

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLI INTERFACE                              │
│                 (Typer + Rich — unchanged)                            │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        AGENT ORCHESTRATOR                            │
│  - Intent Classification                                             │
│  - Context Management                                                │
│  - Response Generation (Groq LLM)                                    │
│  - Audit Logging ← NEW                                               │
└─────────────────────────────────────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
┌───────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐
│  KNOWLEDGE BASE   │ │   DOCUMENT      │ │   DATA PIPELINE ← NEW  │
│                   │ │   GENERATOR     │ │                         │
│ - Supabase DB     │ │ - PDF Export    │ │ - Scheduled Crawler     │
│ - pgvector search │ │ - Templates     │ │ - Parser & Indexer      │
│ - SQLite fallback │ │ - Audit trail   │ │ - Change Detector       │
│                   │ │                 │ │ - Embedding Generator   │
└───────────────────┘ └─────────────────┘ └─────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SUPABASE (Cloud)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  PostgreSQL   │  │   Storage    │  │   pgvector (Embeddings)  │  │
│  │  - documents  │  │   - raw HTML │  │   - semantic search      │  │
│  │  - articles   │  │   - raw PDF  │  │   - multilingual model   │  │
│  │  - audits     │  │              │  │                          │  │
│  │  - sessions   │  │              │  │                          │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Pipeline Flow

```
                    ┌──────────────────────┐
                    │   SCHEDULER          │
                    │   (daily/weekly)     │
                    └──────────┬───────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 1: DISCOVERY                                              │
│                                                                  │
│  Với mỗi category (đất đai, nhà ở, dân sự...):                  │
│  1. Crawl trang danh sách văn bản trên thuvienphapluat.vn        │
│  2. Extract metadata: số hiệu, ngày ban hành, tình trạng        │
│  3. So sánh với DB → xác định văn bản mới/cập nhật               │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 2: CRAWL & PARSE                                          │
│                                                                  │
│  Với mỗi văn bản mới/cập nhật:                                   │
│  1. Crawl full content (HTML)                                    │
│  2. Lưu raw HTML vào Supabase Storage (backup)                   │
│  3. Parse cấu trúc: Phần → Chương → Mục → Điều → Khoản → Điểm  │
│  4. Extract metadata: hiệu lực, cơ quan ban hành, references    │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 3: INDEX & EMBED                                          │
│                                                                  │
│  1. Lưu structured data vào Supabase PostgreSQL                  │
│  2. Generate embeddings (sentence-transformers)                  │
│  3. Lưu vectors vào Supabase pgvector                            │
│  4. Cập nhật trạng thái hiệu lực các văn bản cũ                 │
│  5. Build relationship graph (thay thế, bổ sung, hướng dẫn)     │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 4: VALIDATE                                               │
│                                                                  │
│  1. Verify data integrity (no missing articles)                  │
│  2. Cross-check references giữa các văn bản                     │
│  3. Log pipeline run results vào audit table                     │
└──────────────────────────────────────────────────────────────────┘
```

### 3.3 Query Flow (khi người dùng hỏi)

```
User Question
     │
     ▼
┌─────────────────┐
│ Semantic Search  │ ← pgvector similarity search trên Supabase
│ (Top-K articles) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Filter by Status │ ← Chỉ lấy văn bản "còn hiệu lực"
│ & Relevance      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Build RAG Context│ ← Kèm metadata: số hiệu, ngày, hiệu lực
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ LLM Generate    │ ← Groq API với context đã verified
│ Response        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Save Audit Log  │ ← Lưu query + sources + response vào Supabase
└─────────────────┘
```

---

## 4. Data Model

### 4.1 Supabase PostgreSQL Schema

#### Bảng `legal_categories` — Danh mục lĩnh vực pháp luật

```sql
CREATE TABLE legal_categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,          -- 'dat_dai', 'nha_o', 'dan_su'
  display_name TEXT NOT NULL,          -- 'Đất đai', 'Nhà ở', 'Dân sự'
  description TEXT,
  crawl_url TEXT,                      -- URL trang danh sách trên TVPL
  last_crawled_at TIMESTAMPTZ,
  crawl_interval_hours INT DEFAULT 168, -- 7 ngày
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

#### Bảng `legal_documents` — Văn bản pháp luật (mở rộng)

```sql
CREATE TABLE legal_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id UUID REFERENCES legal_categories(id),
  document_type TEXT NOT NULL,         -- 'LUAT', 'NGHI_DINH', 'THONG_TU'
  document_number TEXT NOT NULL,       -- '31/2024/QH15'
  title TEXT NOT NULL,
  effective_date DATE,
  expiry_date DATE,                    -- Ngày hết hiệu lực (nếu có)
  issuing_authority TEXT,              -- 'Quốc hội', 'Chính phủ'
  source_url TEXT,
  raw_storage_path TEXT,               -- Path trên Supabase Storage
  status TEXT DEFAULT 'active',        -- 'active', 'amended', 'repealed', 'expired'
  replaces_document_id UUID REFERENCES legal_documents(id),
  amended_by_document_id UUID REFERENCES legal_documents(id),
  metadata JSONB,                      -- Flexible metadata
  content_hash TEXT,                   -- Hash để detect changes
  crawled_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(document_number, document_type)
);
```

#### Bảng `articles` — Điều luật (mở rộng)

```sql
CREATE TABLE articles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID REFERENCES legal_documents(id) ON DELETE CASCADE,
  article_number INT NOT NULL,
  title TEXT,
  content TEXT NOT NULL,
  chapter TEXT,                         -- Chương
  section TEXT,                         -- Mục
  part TEXT,                            -- Phần
  embedding VECTOR(768),               -- vietnamese-bi-encoder embedding
  content_hash TEXT,                    -- Hash để detect changes
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(document_id, article_number)
);

-- HNSW index cho semantic search (self-updating, không cần rebuild)
CREATE INDEX articles_embedding_idx ON articles
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
```

#### Bảng `document_relations` — Quan hệ giữa các văn bản

```sql
CREATE TABLE document_relations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_document_id UUID REFERENCES legal_documents(id),
  target_document_id UUID REFERENCES legal_documents(id),
  relation_type TEXT NOT NULL,        -- 'replaces', 'amends', 'guides', 'references'
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

#### Bảng `pipeline_runs` — Log pipeline chạy

```sql
CREATE TABLE pipeline_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id UUID REFERENCES legal_categories(id),
  status TEXT NOT NULL,                -- 'running', 'completed', 'failed'
  documents_found INT DEFAULT 0,
  documents_new INT DEFAULT 0,
  documents_updated INT DEFAULT 0,
  articles_indexed INT DEFAULT 0,
  error_message TEXT,
  started_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ
);
```

#### Bảng `research_audits` — Audit trail cho research

```sql
CREATE TABLE research_audits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT,
  query TEXT NOT NULL,                 -- Câu hỏi của người dùng
  sources JSONB,                       -- Danh sách articles đã sử dụng
  response TEXT,                       -- Câu trả lời
  law_versions JSONB,                  -- Phiên bản luật đã dùng
  confidence_score FLOAT,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

#### Bảng `contract_audits` — Audit trail cho hợp đồng

```sql
CREATE TABLE contract_audits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT,
  contract_type TEXT NOT NULL,
  input_data JSONB,                    -- Dữ liệu đầu vào
  generated_content TEXT,              -- Nội dung hợp đồng
  legal_references JSONB,             -- Các điều luật tham chiếu
  law_versions JSONB,                  -- Phiên bản luật tại thời điểm generate
  pdf_storage_path TEXT,               -- Path file PDF trên Storage
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### 4.2 Supabase Storage Buckets

```
legal-raw-documents/
  ├── luat/                   # Raw HTML/PDF của Luật
  │   ├── luat-dat-dai-2024.html
  │   └── luat-nha-o-2023.html
  ├── nghi-dinh/              # Nghị định
  ├── thong-tu/               # Thông tư
  └── bo-luat/                # Bộ luật

generated-contracts/
  ├── 2026-02/
  │   ├── <uuid>-mua-ban-dat.pdf
  │   └── <uuid>-cho-thue-nha.pdf
```

---

## 5. Crawl Categories — Test Case: Luật Mua bán Đất

### 5.1 Danh sách văn bản cần crawl (đất đai)

| STT | Văn bản | Số hiệu | Hiệu lực |
|-----|---------|----------|-----------|
| 1 | Luật Đất đai 2024 | 31/2024/QH15 | 01/01/2025 |
| 2 | Luật Kinh doanh BĐS 2023 | 29/2023/QH15 | 01/01/2025 |
| 3 | Luật Nhà ở 2023 | 27/2023/QH15 | 01/01/2025 |
| 4 | NĐ hướng dẫn Luật Đất đai | 101/2024/NĐ-CP | 01/01/2025 |
| 5 | NĐ hướng dẫn Luật KDBĐS | 96/2024/NĐ-CP | 01/01/2025 |
| 6 | Bộ luật Dân sự 2015 (phần HĐ) | 91/2015/QH13 | 01/01/2017 |

### 5.2 Crawl Strategy cho thuvienphapluat.vn

```
1. Entry point:
   https://thuvienphapluat.vn/van-ban/Bat-dong-san/
   → Lấy danh sách văn bản mới nhất về BĐS

2. Với mỗi văn bản:
   https://thuvienphapluat.vn/van-ban/Bat-dong-san/<slug>-<id>.aspx
   → Crawl full content

3. Parse HTML structure:
   - div.content1 → Nội dung chính
   - Regex pattern: "Điều \d+" → Tách từng điều
   - Extract metadata từ header table

4. Rate limiting:
   - 3-5 seconds + random 0-2s jitter giữa mỗi request
   - Max 20 pages per run
   - Playwright + stealth plugin (Cloudflare active)
   - Respect robots.txt
```

### 5.3 Kết quả mong đợi sau khi crawl

```
Supabase DB sau khi crawl "đất đai":
├── legal_documents: ~6 documents
├── articles: ~500+ articles (Luật Đất đai 2024 có 260 điều)
├── embeddings: ~500+ vectors
└── storage: ~6 raw HTML files

Khi user hỏi "Điều kiện chuyển nhượng quyền sử dụng đất?":
→ Semantic search → Điều 45 Luật Đất đai 2024
→ Cross-ref → Điều 27 NĐ 101/2024
→ Response với citations chính xác + điều luật hiện hành
```

---

## 6. Chiến lược đảm bảo độ chính xác

### 6.1 Luật mới nhất luôn được ưu tiên

```
Priority khi search:
1. Văn bản status = 'active' + effective_date mới nhất
2. Nghị định/thông tư hướng dẫn của văn bản đó
3. Bộ luật gốc (Dân sự, Hình sự) nếu relevant
4. KHÔNG BAO GIỜ trả về văn bản status = 'repealed'
```

### 6.2 Content Hash để detect thay đổi

- Mỗi article và document có `content_hash` (SHA-256)
- Khi re-crawl, so sánh hash → chỉ update nếu thay đổi
- Tránh re-index không cần thiết

### 6.3 Audit Trail

- Mỗi response đều lưu `law_versions` — phiên bản luật nào được dùng
- Nếu luật thay đổi sau đó, có thể query lại: "Kết quả này dùng luật cũ, cần review"
- Contract audit cho phép verify hợp đồng đã generate có dùng đúng luật

### 6.4 Dual Mode (Online/Offline)

```python
# Config trong .env
DB_MODE=supabase          # hoặc 'sqlite' cho offline/dev
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
```

- **Supabase mode**: Dữ liệu cloud, luôn cập nhật, audit trail đầy đủ
- **SQLite mode**: Local development, offline, demo — giữ nguyên code hiện tại

---

## 7. Project Structure mới

```
legal_chatbot/
  db/
    sqlite.py              # Giữ nguyên (local/offline mode)
    chroma.py              # Giữ nguyên (fallback search)
    supabase.py            # ← NEW: Supabase client & operations
    base.py                # ← NEW: Abstract DB interface (strategy pattern)
  services/
    crawler.py             # Mở rộng: crawl theo category, detect changes
    indexer.py             # Mở rộng: embedding + Supabase pgvector
    pipeline.py            # ← NEW: Pipeline orchestrator
    scheduler.py           # ← NEW: Scheduled pipeline runs
    audit.py               # ← NEW: Audit trail service
    chat.py                # Cập nhật: query Supabase, save audit
    research.py            # Cập nhật: dùng indexed data thay vì real-time
    generator.py           # Cập nhật: save contract audit
  models/
    document.py            # Mở rộng: thêm fields mới
    pipeline.py            # ← NEW: Pipeline models
    audit.py               # ← NEW: Audit models
  cli/
    main.py                # Thêm commands: pipeline, db, audit
```

---

## 8. Tech Stack bổ sung

| Component | Technology | Lý do chọn |
|-----------|-----------|-------------|
| Cloud DB | Supabase (PostgreSQL) | Free tier tốt, có pgvector, Storage, Realtime |
| Vector Search | pgvector (Supabase) | Tích hợp sẵn, không cần service riêng |
| Embeddings | sentence-transformers `bkai-foundation-models/vietnamese-bi-encoder` | Legal-trained, PhoBERT backbone, dim=768 |
| Python SDK | `supabase-py` | Official SDK |
| Scheduler | `APScheduler` hoặc `schedule` | Lightweight, chạy trong process |
| Hashing | `hashlib` (SHA-256) | Built-in Python, detect changes |

### Dependencies mới

```
supabase>=2.0.0
sentence-transformers>=2.2.0
playwright-stealth>=1.0.0    # Cloudflare bypass
apscheduler>=3.10.0
```

---

## 9. Environment Variables mới

```bash
# Existing
GROQ_API_KEY=gsk_...
DATABASE_PATH=./data/legal.db
CHROMA_PATH=./data/chroma
LOG_LEVEL=INFO

# New - Supabase
DB_MODE=supabase                              # 'supabase' | 'sqlite'
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIs...          # anon key
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIs...   # service role key (for admin ops)

# New - Pipeline
PIPELINE_CRAWL_INTERVAL=168                    # hours (default 7 days)
PIPELINE_RATE_LIMIT=4                          # seconds between requests (3-5 range)
PIPELINE_MAX_PAGES=50                          # max pages per category per run
EMBEDDING_MODEL=bkai-foundation-models/vietnamese-bi-encoder
EMBEDDING_DIMENSION=768
```

---

## 10. Testing Strategy

### 10.1 Unit Tests

```bash
# Test Supabase connection
pytest tests/unit/test_supabase.py

# Test pipeline phases
pytest tests/unit/test_pipeline.py

# Test crawler with mock data
pytest tests/unit/test_crawler_v2.py

# Test embedding generation
pytest tests/unit/test_embeddings.py
```

### 10.2 Integration Tests

```bash
# Test full pipeline: crawl → parse → index → query
pytest tests/integration/test_pipeline_e2e.py

# Test Supabase CRUD operations
pytest tests/integration/test_supabase_crud.py

# Test audit trail
pytest tests/integration/test_audit.py
```

### 10.3 Acceptance Test — Crawl đất đai

```bash
# 1. Setup Supabase tables
/legal.db migrate

# 2. Crawl luật đất đai
/legal.pipeline crawl dat_dai --limit 5

# 3. Verify data
/legal.db status
# Expected: ~5 documents, ~200+ articles, embeddings generated

# 4. Test query
/legal.research Điều kiện chuyển nhượng quyền sử dụng đất?
# Expected: Response citing Luật Đất đai 2024, Điều 45

# 5. Check audit
/legal.audit list --limit 5
# Expected: Audit entry with query, sources, response
```

---

## 11. Phases phát triển

### Phase 1: Supabase Foundation
- [ ] Setup Supabase project + tables
- [ ] Implement `db/supabase.py` client
- [ ] Implement `db/base.py` abstract interface
- [ ] Cập nhật `utils/config.py` với Supabase settings
- [ ] Dual mode: switch giữa SQLite và Supabase

### Phase 2: Data Pipeline Core
- [ ] Implement `services/pipeline.py` orchestrator
- [ ] Mở rộng `services/crawler.py` — crawl theo category
- [ ] Implement change detection (content hash)
- [ ] Mở rộng `services/indexer.py` — Supabase + embeddings
- [ ] Implement `models/pipeline.py`

### Phase 3: Crawl Test Case — Đất đai
- [ ] Configure crawl URLs cho category "đất đai"
- [ ] Crawl Luật Đất đai 2024 + nghị định hướng dẫn
- [ ] Verify parsed data quality
- [ ] Test semantic search trên dữ liệu đã crawl

### Phase 4: Audit Trail
- [ ] Implement `services/audit.py`
- [ ] Implement `models/audit.py`
- [ ] Cập nhật `services/chat.py` — save research audit
- [ ] Cập nhật `services/generator.py` — save contract audit
- [ ] CLI commands: audit list, audit verify

### Phase 5: Integration & Polish
- [ ] Cập nhật CLI commands (pipeline, db, audit)
- [ ] Implement scheduler (optional — manual trigger trước)
- [ ] End-to-end testing
- [ ] Documentation cập nhật

---

## 12. Lưu ý quan trọng

1. **Rate limiting**: Tôn trọng robots.txt và giới hạn tốc độ crawl (2-3s/request)
2. **Bản quyền**: Dữ liệu pháp luật là public domain, nhưng cần tôn trọng website nguồn
3. **Data quality**: Validate parsed data — thiếu 1 điều luật = tư vấn sai
4. **Fallback**: Nếu Supabase down, fallback về SQLite local
5. **Privacy**: Không lưu thông tin cá nhân của người dùng trong audit (chỉ lưu query + response)
6. **Cost**: Supabase free tier: 500MB DB, 1GB Storage — đủ cho MVP
7. **Embeddings**: Model `paraphrase-multilingual-MiniLM-L12-v2` chạy local, không tốn API cost
