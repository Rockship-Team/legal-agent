# 003 - Thiết kế lại Data Pipeline: DB-First + Background Worker

## 1. Tổng quan

### 1.1 User Problem

1. **Chat chậm và không ổn định**: Mỗi câu hỏi phải chờ web search (5-15s), thường bị Cloudflare block → timeout hoặc kết quả sai
2. **Tạo hợp đồng không nhất quán**: Cùng loại hợp đồng, tạo 2 lần cho kết quả khác nhau (web search mỗi lần ra kết quả khác)
3. **Không biết hệ thống hỗ trợ gì**: Hỏi về bộ luật chưa có data, hệ thống vẫn cố trả lời → kết quả sai, mất tin tưởng

### 1.2 Giải pháp

Chuyển sang **DB-First**: Mọi tương tác (chat, research, tạo hợp đồng) chỉ dùng data đã index trong Supabase. Background worker tự động cập nhật data hàng tuần.

```
TRƯỚC (002): User hỏi → Web Search + DB → LLM → Response
SAU  (003): User hỏi → DB ONLY → LLM → Response (hoặc "Chưa đủ dữ liệu")
```

### 1.3 Definition of Done (DOD)

| # | Tiêu chí | Cách kiểm tra |
|---|----------|---------------|
| 1 | Chat trả lời < 3s (không web search) | Đo response time khi chat về lĩnh vực đã có data |
| 2 | Chat trả "chưa đủ dữ liệu" khi không có data | Hỏi về bảo hiểm xã hội (chưa crawl) → thông báo rõ ràng |
| 3 | Create-contract cho kết quả nhất quán | Tạo 2 HĐ mua bán đất → cùng citations, cùng điều luật |
| 4 | Create-contract không web search | Toàn bộ flow không gọi web, chỉ DB |
| 5 | Worker tự động cập nhật luật | Để worker chạy → kiểm tra `pipeline_runs` có log mới |
| 6 | Incremental crawl hoạt động | Chạy crawl 2 lần → lần 2 skip docs unchanged |
| 7 | App hiển thị rõ hỗ trợ bộ luật nào | User thấy danh sách categories + số articles |

### 1.4 Thống kê bộ luật VN vs App Coverage

VN có **~266 luật** đang hiệu lực. Cho **tư vấn + tạo hợp đồng**, có **36 luật quan trọng** nhất.

| Category | Bộ luật chính | Trạng thái | Contract types |
|----------|---------------|-----------|----------------|
| `dat_dai` | Luật Đất đai 2024 (31/2024/QH15) | **Đã crawl** | mua bán đất, cho thuê, chuyển nhượng, thế chấp |
| `nha_o` | Luật Nhà ở 2023 (27/2023/QH15) | **Đã crawl** | mua bán nhà, thuê nhà, đặt cọc |
| `dan_su` | Bộ luật Dân sự 2015 (91/2015/QH13) | **Đã crawl** | vay tiền, ủy quyền, dịch vụ, mua bán tài sản |
| `lao_dong` | Bộ luật Lao động 2019 (45/2019/QH14) | **Đã crawl** | HĐLĐ, thử việc, chấm dứt HĐLĐ |
| `doanh_nghiep` | Luật Doanh nghiệp 2020 (59/2020/QH14) | Chưa crawl | - |
| `thuong_mai` | Luật Thương mại 2005 (36/2005/QH11) | Chưa crawl | - |

**Chưa hỗ trợ** (có thể mở rộng): Bảo hiểm xã hội, Thuế, Sở hữu trí tuệ, Xây dựng, Hình sự (ngoài scope).

**Tổng kết**: App target **6 lĩnh vực** / 36 luật. Đã crawl **4/6**.

---

## 2. Yêu cầu chức năng

### 2.1 Loại bỏ Web Search

| Yêu cầu | Mô tả |
|----------|--------|
| Xóa web search trong chat | `chat.py` chỉ query Supabase pgvector, không gọi `research.py` |
| Xóa web search trong research | `research.py` query DB thay vì crawl real-time |
| Xóa web search trong create-contract | `legal.create-contract` chỉ query Supabase |
| DB-only RAG | Context cho LLM chỉ từ articles đã index. Citation trỏ về article `id` trong DB |

### 2.2 Graceful "No Data" Response

| Yêu cầu | Mô tả |
|----------|--------|
| Detect no-data | Vector search trả 0 results hoặc score < threshold → "chưa đủ data" |
| Response tự nhiên | Giọng AI chat thân thiện, không cứng nhắc. Gợi ý lĩnh vực đã có |
| Không hallucinate | TUYỆT ĐỐI không trả lời khi không có data nguồn |

**Response templates** (giọng AI chat, thân thiện):

- **Chat không có data**: "Hiện tại mình chưa có dữ liệu về {lĩnh vực} nên không thể tư vấn chính xác. Mình có thể giúp về: {danh sách categories + số điều luật}. Bạn muốn hỏi về lĩnh vực nào?"
- **Create-contract không có data**: "Mình chưa có đủ dữ liệu để tạo hợp đồng {loại}. Hiện mình có thể tạo: {danh sách contract types}. Bạn muốn tạo loại nào?"
- **Create-contract thiếu data** (< min_articles): Cảnh báo thiếu + hỏi user muốn tiếp tục hay dừng bổ sung
- **Search không khớp**: "Mình không tìm thấy điều luật phù hợp. Bạn thử diễn đạt cụ thể hơn?"

### 2.3 Background Worker

| Yêu cầu | Mô tả |
|----------|--------|
| Chạy ngầm | Worker process chạy liên tục, không cần CLI trigger |
| Schedule | Mỗi bộ luật có lịch riêng (mặc định **weekly** — luật ít thay đổi) |
| Incremental | Chỉ crawl/update văn bản thay đổi (content hash SHA-256) |
| Logging | Ghi log mỗi lần chạy vào `pipeline_runs` table |
| Error recovery | Retry 3 lần, exponential backoff → log error → tiếp bộ luật khác |
| Không chạy mặc định | Phải explicit start bằng command |

> **Tại sao weekly?** Bộ luật VN thường chỉ sửa đổi vài lần/năm. Crawl daily lãng phí tài nguyên. Admin có thể force crawl bất cứ lúc nào.

### 2.4 Pipeline Target Cụ Thể

| Yêu cầu | Mô tả |
|----------|--------|
| Target bộ luật | Mỗi pipeline run target 1 bộ luật cụ thể + văn bản liên quan |
| Document registry | Danh sách URL cụ thể cho từng bộ luật (không crawl random) |
| Related documents | Tự động crawl nghị định, thông tư hướng dẫn |
| Relationship tracking | Map quan hệ: replaces, amends, guides, references |

### 2.5 Contract Templates per Category

| Yêu cầu | Mô tả |
|----------|--------|
| Template sẵn per category | Mỗi category có danh sách contract types (ví dụ: `dat_dai` → `mua_ban_dat`, `cho_thue_dat`) |
| Pre-mapped queries | Mỗi template biết trước search queries để tìm điều luật trong DB |
| No-data = Không tạo | Nếu category chưa crawl → thông báo, không cố tạo |
| Audit verifiable | Mọi `legal_references` trỏ về article `id` trong DB |

**Contract types per category:**

| Category | Contract Types |
|----------|---------------|
| `dat_dai` | `mua_ban_dat`, `cho_thue_dat`, `chuyen_nhuong_dat`, `the_chap_dat` |
| `nha_o` | `mua_ban_nha`, `cho_thue_nha`, `dat_coc_nha` |
| `lao_dong` | `hop_dong_lao_dong`, `thu_viec`, `cham_dut_hdld` |
| `dan_su` | `vay_tien`, `uy_quyen`, `dich_vu`, `mua_ban_tai_san` |

### 2.6 Slash Commands

```bash
# Pipeline (giữ nguyên + bổ sung)
/legal.pipeline crawl dat_dai              # Crawl & index bộ luật
/legal.pipeline crawl dat_dai --force      # Force re-crawl (bỏ qua content hash)
/legal.pipeline status                     # Trạng thái pipeline + worker
/legal.pipeline categories                 # Liệt kê categories đã có data

# Worker (MỚI)
/legal.pipeline worker start|stop|status|schedule
```

---

## 3. Kiến trúc

### 3.1 Tổng quan

```
CLI (Typer + Rich)
  ├── Chat Service (DB-Only RAG) ──→ Supabase pgvector
  ├── Contract Service (MỚI) ─────→ Supabase pgvector + contract_templates
  └── Background Worker (MỚI) ────→ Pipeline Runner → Crawl → Index → Supabase
```

**Chat Flow**: User Question → Detect Category → Check Data Availability → (có data) Vector Search → RAG → LLM Response / (không data) No-Data Message + List Categories

**Create-Contract Flow**: Parse Contract Type → Detect Category → Check Data → Load Template Config → Multi-query Vector Search → Check ≥ min_articles → Hỏi User Info → Generate Contract → Save Audit

**Worker Flow**: APScheduler cron jobs per category (weekly) → Load URLs từ document_registry → HEAD request check → Content hash compare → Re-crawl if changed → Parse → Embed → Upsert → Log pipeline_runs

**Incremental Update**: HEAD request (ETag/Last-Modified) → unchanged: skip / changed: full crawl → SHA-256 hash compare → same: skip / different: re-parse + re-embed + upsert

---

## 4. Data Model Changes

### 4.1 `legal_categories` — Bổ sung worker fields

```sql
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS worker_schedule TEXT DEFAULT 'weekly';
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS worker_time TEXT DEFAULT '02:00';
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS worker_status TEXT DEFAULT 'active';
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS document_count INT DEFAULT 0;
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS article_count INT DEFAULT 0;
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS last_worker_run_at TIMESTAMPTZ;
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS last_worker_status TEXT;
```

### 4.2 `pipeline_runs` — Bổ sung worker metadata

```sql
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS trigger_type TEXT DEFAULT 'manual';
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS documents_skipped INT DEFAULT 0;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS duration_seconds FLOAT;
```

### 4.3 `document_registry` (MỚI) — Danh sách URL per category

```sql
CREATE TABLE IF NOT EXISTS document_registry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id UUID REFERENCES legal_categories(id),
  url TEXT NOT NULL UNIQUE,
  document_number TEXT,
  title TEXT,
  role TEXT DEFAULT 'primary',     -- 'primary', 'related', 'base'
  priority INT DEFAULT 1,
  is_active BOOLEAN DEFAULT true,
  last_checked_at TIMESTAMPTZ,
  last_content_hash TEXT,
  last_etag TEXT,
  last_modified TEXT,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### 4.4 `contract_templates` (MỚI) — Mẫu hợp đồng per category

```sql
CREATE TABLE IF NOT EXISTS contract_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id UUID REFERENCES legal_categories(id),
  contract_type TEXT NOT NULL,          -- 'mua_ban_dat'
  display_name TEXT NOT NULL,           -- 'Hợp đồng mua bán đất'
  search_queries JSONB NOT NULL,        -- ["điều kiện chuyển nhượng...", ...]
  required_laws JSONB,                  -- ["Luật Đất đai 2024", "BLDS 2015"]
  min_articles INT DEFAULT 5,
  required_fields JSONB,                -- {"ben_a": {...}, "ben_b": {...}}
  article_outline JSONB,                -- ["ĐIỀU 1: ...", "ĐIỀU 2: ..."]
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(category_id, contract_type)
);
```

### 4.5 Bảng giữ nguyên từ 002

`legal_documents`, `articles`, `document_relations`, `research_audits`, `contract_audits`

---

## 5. Code Changes (WHAT)

> Chi tiết implementation: xem `contracts/` và `plan.md`

### 5.1 Files thay đổi

| File | Thay đổi |
|------|----------|
| `services/chat.py` | Xóa web search fallback, thêm `_detect_category()`, `_check_data_availability()`, xóa `_build_context_legacy()` |
| `services/research.py` | Xóa web crawl, thêm deep DB search (`top_k=20`), thêm no-data response |
| `services/pipeline.py` | Đọc URLs từ `document_registry`, content hash comparison, trigger_type tracking |
| `services/worker.py` | **MỚI** — APScheduler AsyncIOScheduler, retry logic, graceful shutdown |
| `services/contract.py` | **MỚI** — Load template từ DB, multi-query search, data validation |
| `db/supabase.py` | Thêm document_registry CRUD, contract_templates CRUD, category stats |
| `db/migrations/003_worker.sql` | **MỚI** — ALTER tables + CREATE document_registry + contract_templates + RLS + function |
| `models/pipeline.py` | Thêm WorkerStatus, DocumentRegistryEntry |
| `models/chat.py` | Thêm has_data field, NoDataResponse |
| `cli/main.py` | Thêm worker commands, update chat behavior |
| `utils/config.py` | Thêm worker settings |

### 5.2 `legal.create-contract` Slash Command Changes

| Bước cũ | Thay đổi |
|---------|----------|
| Search web (luôn luôn) | **XÓA** |
| So sánh & sync từ web | **XÓA** — Worker đã tự động sync |
| Search Supabase | **GIỮ** — Dùng pre-mapped queries từ template |
| Fallback WebSearch | **XÓA** — Trả "chưa đủ data" |

---

## 6. Document Registry — Dữ liệu ban đầu

| Category | Role | Văn bản | Số hiệu |
|----------|------|---------|----------|
| `dat_dai` | primary | Luật Đất đai 2024 | 31/2024/QH15 |
| `dat_dai` | related | NĐ hướng dẫn | 101/2024/NĐ-CP |
| `dat_dai` | related | NĐ KDBĐS | 96/2024/NĐ-CP |
| `dat_dai` | related | Luật KDBĐS 2023 | 29/2023/QH15 |
| `dat_dai` | base | Bộ luật Dân sự 2015 | 91/2015/QH13 |
| `dan_su` | primary | Bộ luật Dân sự 2015 | 91/2015/QH13 |
| `lao_dong` | primary | Bộ luật Lao động 2019 | 45/2019/QH14 |
| `lao_dong` | related | NĐ hướng dẫn BLLĐ | 145/2020/NĐ-CP |

---

## 7. Configuration

### 7.1 Environment Variables mới

```bash
# Worker (NEW)
WORKER_ENABLED=true
WORKER_DEFAULT_SCHEDULE=weekly
WORKER_DEFAULT_TIME=02:00               # UTC+7, Chủ nhật
WORKER_RETRY_COUNT=3
WORKER_RETRY_BACKOFF=30                 # Base seconds, exponential

# Chat (NEW behavior)
CHAT_MODE=db_only
CHAT_NO_DATA_BEHAVIOR=inform
```

### 7.2 Category Schedule

```
dat_dai:      weekly  Sun 02:00  active
nha_o:        weekly  Sun 02:30  active
dan_su:       weekly  Sun 03:00  active
lao_dong:     weekly  Sun 03:30  active
doanh_nghiep: monthly 1st 03:00 paused
thuong_mai:   monthly 1st 04:00 paused
```

---

## 8. Project Structure Changes

```
legal_chatbot/
  services/
    chat.py              # ← SỬA: DB-only, no web search, + no-data handling
    research.py          # ← SỬA: DB-only deep search
    contract.py          # ← MỚI: Contract creation (DB-only, template-based)
    pipeline.py          # ← SỬA: incremental update, document registry
    worker.py            # ← MỚI: Background worker (APScheduler)
  db/
    supabase.py          # ← SỬA: document_registry CRUD, category stats
    migrations/
      003_worker.sql     # ← MỚI
  models/
    pipeline.py          # ← SỬA: WorkerStatus, DocumentRegistryEntry
    chat.py              # ← SỬA: has_data, NoDataResponse
  cli/main.py            # ← SỬA: worker commands
  utils/config.py        # ← SỬA: worker settings
```

---

## 9. Testing Strategy

### Unit Tests

| Test file | Test cases |
|-----------|------------|
| `test_chat_db_only.py` | chat with data → RAG, no data → message, detect category |
| `test_contract_db_only.py` | create with data, no data → message, insufficient articles → warn, template loading, multi-query merge |
| `test_worker.py` | start/stop, schedule from DB, retry on failure, graceful shutdown |
| `test_pipeline_incremental.py` | skip unchanged, detect change, registry CRUD |

### Acceptance Tests

```bash
/legal.db migrate                              # Run 003_worker.sql
/legal.pipeline crawl dat_dai                  # Crawl initial data
/legal.db status                               # Verify data exists

# Chat: có data → Response with citations, NO web search
# Chat: "bảo hiểm xã hội?" → "Chưa đủ dữ liệu" + list categories

/legal.pipeline worker start                   # Start worker
/legal.pipeline worker status                  # Verify running

# Create-contract: "mua bán đất" → DB search → hỏi info → tạo HĐ (no web)
# Create-contract: "bảo hiểm" → "Chưa đủ dữ liệu" + list types
```

---

## 10. Lưu ý quan trọng

1. **KHÔNG web search** trong chat, research, VÀ create-contract — chỉ dùng DB. Không data → nói thẳng
2. **Contract templates = cấu hình sẵn** — pre-mapped queries per category, user không cần tự nghĩ search term
3. **Data phải có TRƯỚC** khi tạo hợp đồng — admin crawl → worker cập nhật weekly → user tạo HĐ
4. **Worker KHÔNG chạy mặc định** — phải explicit start. Tránh surprise resource usage
5. **Rate limiting** — Worker crawl ban đêm (2-3 AM), 4-6s/request
6. **Document Registry = Single Source of Truth** — Pipeline chỉ crawl URLs có trong registry
7. **Incremental trước, full crawl khi cần** — Mặc định skip unchanged. Dùng `--force` khi cần
8. **Backwards compatible** — Giữ nguyên interface hiện tại, chỉ ADD không BREAK
9. **SQLite mode** — Worker VÀ contract templates KHÔNG hỗ trợ SQLite, chỉ Supabase
