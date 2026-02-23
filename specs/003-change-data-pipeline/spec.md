# 003 - Thiết kế lại Data Pipeline: DB-First + Background Worker

## 1. Tổng quan

### 1.1 Vấn đề hiện tại

Hệ thống pipeline hiện tại (002) có những hạn chế nghiêm trọng:

1. **Pipeline chạy thủ công**: Không có scheduler/worker — admin phải gõ CLI mỗi lần muốn cập nhật luật
2. **Chat vẫn phụ thuộc web search**: `research.py` luôn crawl real-time từ thuvienphapluat.vn → chậm, không ổn định, bị Cloudflare block
3. **Không phân biệt "có data" vs "chưa có data"**: Khi user hỏi về bộ luật chưa crawl, hệ thống vẫn cố search → trả kết quả sai hoặc trống
4. **Pipeline crawl theo category chung**: Không target cụ thể một bộ luật → crawl dư thừa, thiếu kiểm soát
5. **Không có cơ chế detect thay đổi tự động**: Phải manual compare content hash
6. **Create-contract phụ thuộc web search**: `legal.create-contract` phải WebSearch tìm điều luật → chậm, không ổn định, kết quả không đồng nhất giữa các lần tạo
7. **Không có contract templates sẵn**: Mỗi lần tạo hợp đồng phải research lại từ đầu, dù cùng lĩnh vực (ví dụ: tạo 2 hợp đồng thuê đất khác nhau phải search lại 2 lần)

### 1.2 Mục tiêu thiết kế lại

```
TRƯỚC (002):
  User hỏi → Web Search + DB Search → LLM → Response
  Pipeline: Manual CLI → Crawl category → Index

SAU (003):
  User hỏi → DB Search ONLY → LLM → Response (hoặc "Chưa đủ dữ liệu")
  Create-contract → DB Search ONLY → LLM → Hợp đồng (hoặc "Chưa đủ dữ liệu")
  Pipeline: Background Worker → Crawl bộ luật cụ thể → Index → Daily Update
```

| Mục tiêu | Mô tả |
|-----------|--------|
| **DB-First** | Chat/Research CHỈ query từ Supabase, KHÔNG web search |
| **Background Worker** | Worker chạy ngầm, tự động cập nhật luật hàng ngày |
| **Target cụ thể** | Pipeline build data cho từng bộ luật nhất định (không crawl tràn lan) |
| **Graceful "No Data"** | Khi chưa có data → trả lời rõ ràng, gợi ý admin sync |
| **Change Detection** | Tự động phát hiện luật sửa đổi/bổ sung/thay thế |

### 1.3 Ví dụ Use Case

```
═══ Scenario 1: Bộ luật ĐÃ CÓ data ═══

Admin đã chạy:  /legal.pipeline crawl dat_dai
Worker chạy ngầm: cập nhật Luật Đất đai mỗi ngày lúc 2:00 AM

User: "Điều kiện chuyển nhượng quyền sử dụng đất?"

Agent:
  1. Vector search Supabase → tìm Điều 45 Luật Đất đai 2024
  2. KHÔNG web search (đã có data đầy đủ trong DB)
  3. Trả lời với citations chính xác
  4. Lưu audit trail

═══ Scenario 2: Bộ luật CHƯA CÓ data ═══

User: "Quy định về bảo hiểm xã hội?"

Agent:
  1. Vector search Supabase → 0 results (category 'bao_hiem' chưa crawl)
  2. Trả lời: "⚠ Hệ thống chưa có dữ liệu về lĩnh vực Bảo hiểm xã hội.
              Vui lòng liên hệ admin để đồng bộ bộ luật này,
              hoặc thử hỏi về các lĩnh vực đã có: Đất đai, Nhà ở, Dân sự..."
  3. KHÔNG cố web search hay trả lời bừa

═══ Scenario 3: Worker phát hiện luật thay đổi ═══

Worker (2:00 AM daily):
  1. Check thuvienphapluat.vn → Luật Đất đai có nghị định mới
  2. Crawl nghị định mới → parse → embed → upsert
  3. Cập nhật status văn bản cũ (nếu bị thay thế)
  4. Log vào pipeline_runs table
  5. Sáng hôm sau user hỏi → đã có data mới nhất

═══ Scenario 4: Create-contract cho lĩnh vực ĐÃ CÓ data ═══

Admin đã crawl: /legal.pipeline crawl dat_dai
→ DB có sẵn: Luật Đất đai 2024, BLDS 2015, NĐ hướng dẫn...
→ Contract templates cho dat_dai: mua_ban_dat, cho_thue_dat, chuyen_nhuong_dat

User: /legal.create-contract mua bán đất

Agent:
  1. Detect category = "dat_dai", contract_type = "mua_ban_dat"
  2. Load contract template "mua_ban_dat" → biết cần những điều luật nào
  3. Vector search Supabase → lấy Điều 45, 167, 188 Luật Đất đai 2024
     + Điều 430, 440 BLDS 2015 (phần hợp đồng mua bán)
  4. KHÔNG web search — đã có đầy đủ trong DB
  5. Hỏi user từng thông tin (bên A, bên B, thửa đất...)
  6. Tạo hợp đồng với articles dựa trên điều luật đã lưu
  7. Save → Supabase contract_audits

═══ Scenario 5: Create-contract cho lĩnh vực CHƯA CÓ data ═══

User: /legal.create-contract hợp đồng bảo hiểm

Agent:
  1. Detect category = "bao_hiem" → CHƯA có data
  2. Trả lời: "⚠ Chưa đủ dữ liệu pháp luật về lĩnh vực Bảo hiểm
              để tạo hợp đồng. Vui lòng liên hệ admin để đồng bộ
              Luật Kinh doanh bảo hiểm trước.

              Hiện có thể tạo hợp đồng cho:
                • Đất đai: mua bán đất, cho thuê đất, chuyển nhượng
                • Nhà ở: thuê nhà, mua bán nhà
                • Lao động: hợp đồng lao động, thử việc"
  3. KHÔNG cố tạo hợp đồng bằng web search
```

---

## 2. Yêu cầu chức năng

### 2.1 Loại bỏ Web Search khỏi Chat Flow

| Yêu cầu | Mô tả |
|----------|--------|
| **Xóa web search trong chat** | `chat.py` chỉ query Supabase pgvector, không gọi `research.py` |
| **Xóa web search trong research** | `research.py` đổi sang query DB thay vì crawl real-time |
| **DB-only RAG** | Context cho LLM chỉ đến từ articles đã index trong Supabase |
| **Citation từ DB** | Mọi citation đều trỏ về article có `id` trong DB (verifiable) |

### 2.2 Graceful "No Data" Response

| Yêu cầu | Mô tả |
|----------|--------|
| **Detect no-data** | Khi vector search trả 0 results hoặc score < threshold → "chưa đủ data" |
| **Response rõ ràng** | Thông báo user lĩnh vực nào chưa có, gợi ý lĩnh vực đã có |
| **Không hallucinate** | TUYỆT ĐỐI không trả lời khi không có data nguồn |
| **List available** | Kèm danh sách categories đã có data để user chọn |

### 2.3 Background Worker

| Yêu cầu | Mô tả |
|----------|--------|
| **Chạy ngầm** | Worker process chạy liên tục, không cần CLI trigger |
| **Schedule** | Mỗi bộ luật có lịch cập nhật riêng (mặc định daily 2:00 AM) |
| **Incremental** | Chỉ crawl/update văn bản mới hoặc thay đổi (content hash compare) |
| **Logging** | Ghi log mỗi lần chạy vào `pipeline_runs` table |
| **Error recovery** | Nếu worker fail → retry 3 lần → log error → tiếp tục bộ luật khác |
| **Resource-aware** | Không chạy khi CPU/memory cao, rate limit chuẩn |

### 2.4 Pipeline Target Cụ Thể

| Yêu cầu | Mô tả |
|----------|--------|
| **Target bộ luật** | Mỗi pipeline run target 1 bộ luật cụ thể + các văn bản liên quan |
| **Document registry** | Danh sách URL cụ thể cho từng bộ luật (không crawl random) |
| **Related documents** | Tự động crawl nghị định, thông tư hướng dẫn của bộ luật đó |
| **Relationship tracking** | Map quan hệ: replaces, amends, guides, references |

### 2.5 Create-Contract DB-Only (Loại bỏ Web Search)

| Yêu cầu | Mô tả |
|----------|--------|
| **Xóa web search trong create-contract** | `legal.create-contract` chỉ query Supabase, KHÔNG gọi WebSearch |
| **Contract templates per category** | Mỗi category có danh sách contract types sẵn (ví dụ: `dat_dai` → `mua_ban_dat`, `cho_thue_dat`) |
| **Pre-mapped legal references** | Mỗi contract template biết trước cần những điều luật nào (query terms) |
| **No-data = Không tạo** | Nếu category chưa crawl → KHÔNG tạo hợp đồng, thông báo rõ ràng |
| **Articles từ DB** | Nội dung các ĐIỀU trong hợp đồng phải dựa trên articles đã lưu trong Supabase |
| **Audit verifiable** | Mọi `legal_references` trong contract đều trỏ về article `id` trong DB |

#### Contract Templates per Category

```
dat_dai:
  ├── mua_ban_dat          (Hợp đồng mua bán đất)
  ├── cho_thue_dat         (Hợp đồng cho thuê đất)
  ├── chuyen_nhuong_dat    (Hợp đồng chuyển nhượng QSDĐ)
  └── the_chap_dat         (Hợp đồng thế chấp QSDĐ)

nha_o:
  ├── mua_ban_nha          (Hợp đồng mua bán nhà ở)
  ├── cho_thue_nha         (Hợp đồng thuê nhà ở)
  └── dat_coc_nha          (Hợp đồng đặt cọc mua nhà)

lao_dong:
  ├── hop_dong_lao_dong    (Hợp đồng lao động)
  ├── thu_viec             (Hợp đồng thử việc)
  └── cham_dut_hdld        (Thỏa thuận chấm dứt HĐLĐ)

dan_su:
  ├── vay_tien             (Hợp đồng vay tiền)
  ├── uy_quyen             (Hợp đồng ủy quyền)
  ├── dich_vu              (Hợp đồng dịch vụ)
  └── mua_ban_tai_san      (Hợp đồng mua bán tài sản)
```

#### Pre-mapped Query Terms per Contract Template

Mỗi contract template định nghĩa sẵn các search queries để tìm điều luật trong DB:

```
mua_ban_dat:
  queries:
    - "điều kiện chuyển nhượng quyền sử dụng đất"
    - "hợp đồng chuyển nhượng quyền sử dụng đất"
    - "quyền nghĩa vụ bên chuyển nhượng bên nhận"
    - "giá đất thanh toán"
    - "thủ tục đăng ký biến động đất đai"
  required_laws:
    - "Luật Đất đai 2024"
    - "Bộ luật Dân sự 2015"
  min_articles: 10    # Cần ít nhất 10 articles liên quan

cho_thue_nha:
  queries:
    - "hợp đồng thuê nhà ở"
    - "quyền nghĩa vụ bên cho thuê bên thuê"
    - "giá thuê phương thức thanh toán"
    - "chấm dứt hợp đồng thuê"
  required_laws:
    - "Luật Nhà ở 2023"
    - "Bộ luật Dân sự 2015"
  min_articles: 8
```

### 2.6 Slash Commands cập nhật

```bash
# Pipeline commands (giữ nguyên + bổ sung)
/legal.pipeline crawl dat_dai              # Crawl & index bộ luật đất đai
/legal.pipeline crawl dat_dai --force      # Force re-crawl (bỏ qua content hash)
/legal.pipeline status                     # Trạng thái pipeline + worker
/legal.pipeline categories                 # Liệt kê categories đã có data

# Worker commands (MỚI)
/legal.pipeline worker start               # Khởi động background worker
/legal.pipeline worker stop                # Dừng background worker
/legal.pipeline worker status              # Xem trạng thái worker + last run
/legal.pipeline worker schedule            # Xem lịch cập nhật từng bộ luật

# Database commands (giữ nguyên)
/legal.db status                           # Kiểm tra kết nối & stats
/legal.db migrate                          # Migrate schema

# Chat (thay đổi behavior — không cần command mới)
# Chat giờ chỉ dùng DB, tự trả "chưa đủ data" khi cần
```

---

## 3. Kiến trúc hệ thống

### 3.1 Tổng quan kiến trúc mới

```
┌──────────────────────────────────────────────────────────────────────┐
│                          CLI INTERFACE                                │
│                  (Typer + Rich — unchanged)                           │
└──────────────────────────────────────────────────────────────────────┘
                               │
               ┌───────────────┼────────────────┐
               ▼               ▼                ▼
┌────────────────────┐  ┌──────────────┐  ┌─────────────────────────┐
│    CHAT SERVICE    │  │  DOCUMENT    │  │  BACKGROUND WORKER ←NEW │
│    (DB-Only RAG)   │  │  GENERATOR   │  │                         │
│                    │  │              │  │  ┌───────────────────┐  │
│  ┌──────────────┐  │  │  - PDF       │  │  │   SCHEDULER       │  │
│  │ Query Router │  │  │  - Templates │  │  │   (APScheduler)   │  │
│  │              │  │  │  - Audit     │  │  └────────┬──────────┘  │
│  │ Has data? ─┐ │  │  │              │  │           │             │
│  │  YES → RAG │ │  │  │              │  │  ┌────────▼──────────┐  │
│  │  NO → Msg  │ │  │  │              │  │  │  PIPELINE RUNNER  │  │
│  └────────────┘  │  │              │  │  │  (per bộ luật)    │  │
│                    │  │              │  │  └────────┬──────────┘  │
│  ❌ No Web Search  │  │              │  │           │             │
│  ❌ No research.py │  │              │  │  Discovery → Crawl     │
│                    │  │              │  │  → Parse → Embed       │
└────────────────────┘  └──────────────┘  │  → Upsert → Validate  │
         │                                 └─────────────────────────┘
         ▼                                           │
┌──────────────────────────────────────────────────────────────────────┐
│                         SUPABASE (Cloud)                              │
│   ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐  │
│   │  PostgreSQL   │  │   Storage    │  │   pgvector (Embeddings)   │  │
│   │  - documents  │  │   - raw HTML │  │   - semantic search       │  │
│   │  - articles   │  │              │  │   - match_articles RPC    │  │
│   │  - categories │  │              │  │   - threshold = 0.3       │  │
│   │  - pipeline_  │  │              │  │                           │  │
│   │    runs       │  │              │  │                           │  │
│   │  - audits     │  │              │  │                           │  │
│   └──────────────┘  └──────────────┘  └───────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 Chat Flow mới (DB-Only)

```
User Question
     │
     ▼
┌─────────────────────┐
│ 1. Detect Category  │  ← LLM classify: user hỏi về lĩnh vực nào?
│    (intent + topic)  │     (đất đai? nhà ở? lao động? ...)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ 2. Check Data       │  ← Query legal_categories + đếm articles
│    Availability      │     cho category đó
└────────┬────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌──────────────────────────────────┐
│ NO     │ │ YES — Data available              │
│ DATA   │ │                                   │
│        │ │  3. Vector Search (pgvector)      │
│ Return │ │     → Top-K articles              │
│ "Chưa  │ │                                   │
│  đủ    │ │  4. Filter: status = 'active'     │
│  dữ    │ │     + score ≥ 0.3                 │
│  liệu" │ │                                   │
│        │ │  5. Build RAG Context              │
│ + List │ │     (articles + metadata)          │
│ avail- │ │                                   │
│ able   │ │  6. LLM Generate Response         │
│ cats   │ │     (Groq — DB context only)       │
│        │ │                                   │
└────────┘ │  7. Save Audit Log                │
           └──────────────────────────────────┘
```

### 3.3 Create-Contract Flow mới (DB-Only)

```
User: /legal.create-contract [loại hợp đồng]
     │
     ▼
┌──────────────────────────┐
│ 1. Parse Contract Type   │  ← "mua bán đất" → contract_type = "mua_ban_dat"
│    + Detect Category     │     → category = "dat_dai"
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│ 2. Check Data            │  ← Query legal_categories
│    Availability          │     + đếm articles cho category
└────────┬─────────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
 NO DATA    HAS DATA
    │            │
    ▼            ▼
┌────────┐  ┌──────────────────────────────────────┐
│ Return │  │ 3. Load Contract Template Config     │
│ "Chưa  │  │    → queries, required_laws,         │
│  đủ    │  │       min_articles                   │
│  dữ    │  └────────┬─────────────────────────────┘
│  liệu  │           │
│  để    │           ▼
│  tạo   │  ┌──────────────────────────────────────┐
│  HĐ"  │  │ 4. Multi-query Vector Search (DB)    │
│        │  │    → Search từng query term           │
│ + List │  │    → Merge + dedup articles           │
│ avail- │  │    → Filter status = 'active'         │
│ able   │  │    → Check ≥ min_articles             │
│ types  │  └────────┬─────────────────────────────┘
└────────┘           │
                ┌────┴────┐
                │         │
                ▼         ▼
          < min_arts   ≥ min_arts
                │         │
                ▼         ▼
          ┌────────┐  ┌──────────────────────────────┐
          │ Warn:  │  │ 5. Hỏi user từng thông tin   │
          │ "Data  │  │    (bên A, bên B, tài sản...) │
          │ thiếu, │  └────────┬─────────────────────┘
          │ HĐ có  │           │
          │ thể    │           ▼
          │ chưa   │  ┌──────────────────────────────┐
          │ đầy    │  │ 6. Generate Contract         │
          │ đủ"    │  │    articles (ĐIỀU 1-9)        │
          │        │  │    dựa trên DB articles        │
          │ Tiếp   │  │    ❌ KHÔNG web search         │
          │ tục?   │  └────────┬─────────────────────┘
          └────────┘           │
                               ▼
                     ┌──────────────────────────────┐
                     │ 7. Save JSON + Supabase      │
                     │    contract_audits            │
                     │    (legal_references → DB id) │
                     └──────────────────────────────┘
```

### 3.4 Background Worker Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    BACKGROUND WORKER                          │
│                                                              │
│  Khởi động khi:                                               │
│    - CLI: /legal.pipeline worker start                       │
│    - Hoặc tự động khi chạy chatbot (optional flag)           │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  APScheduler (BackgroundScheduler)                     │  │
│  │                                                        │  │
│  │  Cron Jobs:                                            │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │ dat_dai    │ daily  │ 02:00 AM │ active │ 6 URLs │  │  │
│  │  │ nha_o      │ daily  │ 02:30 AM │ active │ 3 URLs │  │  │
│  │  │ dan_su     │ weekly │ Sun 3AM  │ active │ 2 URLs │  │  │
│  │  │ lao_dong   │ daily  │ 03:00 AM │ paused │ 4 URLs │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
│                          │                                    │
│                          ▼ (trigger)                          │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Pipeline Runner (per category)                        │  │
│  │                                                        │  │
│  │  1. Load document_urls cho category                    │  │
│  │  2. Với mỗi URL:                                      │  │
│  │     a. HEAD request → check Last-Modified / ETag       │  │
│  │     b. Nếu unchanged → skip                           │  │
│  │     c. Nếu changed → crawl → parse → compare hash     │  │
│  │     d. Nếu content hash khác → re-embed → upsert      │  │
│  │  3. Check listing page → phát hiện văn bản mới         │  │
│  │  4. Cập nhật status văn bản cũ (nếu bị thay thế)      │  │
│  │  5. Log kết quả vào pipeline_runs                      │  │
│  └────────────────────────────────────────────────────────┘  │
│                          │                                    │
│                          ▼                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Error Handling                                        │  │
│  │                                                        │  │
│  │  - Retry: 3 lần, exponential backoff (30s, 60s, 120s) │  │
│  │  - Nếu crawl fail → log error → skip document         │  │
│  │  - Nếu cả category fail → log → tiếp category khác    │  │
│  │  - Alert: ghi vào pipeline_runs với status = 'failed'  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 3.4 Pipeline per Bộ Luật — Document Registry

```
┌──────────────────────────────────────────────────────────────┐
│  DOCUMENT REGISTRY (per category)                             │
│                                                              │
│  Mỗi category có danh sách URL cụ thể (không crawl random): │
│                                                              │
│  dat_dai:                                                    │
│    primary:                                                  │
│      - Luật Đất đai 2024 (31/2024/QH15)                     │
│        url: thuvienphapluat.vn/van-ban/...                   │
│    related:                                                  │
│      - NĐ 101/2024/NĐ-CP (hướng dẫn)                       │
│      - NĐ 96/2024/NĐ-CP (kinh doanh BĐS)                   │
│      - Luật Kinh doanh BĐS 2023                             │
│      - Luật Nhà ở 2023                                       │
│    base:                                                     │
│      - Bộ luật Dân sự 2015 (phần hợp đồng)                  │
│    listing_url: thuvienphapluat.vn/van-ban/Bat-dong-san/     │
│    schedule: daily 02:00                                      │
│                                                              │
│  dan_su:                                                     │
│    primary:                                                  │
│      - Bộ luật Dân sự 2015 (91/2015/QH13)                   │
│    related: [...]                                            │
│    schedule: weekly Sun 03:00                                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. Thay đổi Data Model

### 4.1 Bảng `legal_categories` — Bổ sung schedule fields

```sql
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS
  worker_schedule TEXT DEFAULT 'daily';          -- 'daily', 'weekly', 'monthly'

ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS
  worker_time TEXT DEFAULT '02:00';              -- Giờ chạy (HH:MM, UTC+7)

ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS
  worker_status TEXT DEFAULT 'active';           -- 'active', 'paused', 'disabled'

ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS
  document_count INT DEFAULT 0;                  -- Cache: số documents đã crawl

ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS
  article_count INT DEFAULT 0;                   -- Cache: số articles đã index

ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS
  last_worker_run_at TIMESTAMPTZ;                -- Lần cuối worker chạy

ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS
  last_worker_status TEXT;                       -- 'success', 'partial', 'failed'
```

### 4.2 Bảng `pipeline_runs` — Bổ sung worker metadata

```sql
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS
  trigger_type TEXT DEFAULT 'manual';            -- 'manual', 'scheduled', 'forced'

ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS
  documents_skipped INT DEFAULT 0;               -- Số docs bỏ qua (unchanged)

ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS
  duration_seconds FLOAT;                        -- Thời gian chạy
```

### 4.3 Bảng `document_registry` — Danh sách URL cụ thể (MỚI)

```sql
CREATE TABLE IF NOT EXISTS document_registry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id UUID REFERENCES legal_categories(id),
  url TEXT NOT NULL UNIQUE,                      -- URL trên thuvienphapluat.vn
  document_number TEXT,                          -- Số hiệu (nếu biết trước)
  title TEXT,                                    -- Tên văn bản
  role TEXT DEFAULT 'primary',                   -- 'primary', 'related', 'base'
  priority INT DEFAULT 1,                        -- Thứ tự crawl (1 = cao nhất)
  is_active BOOLEAN DEFAULT true,                -- Có crawl không
  last_checked_at TIMESTAMPTZ,                   -- Lần cuối check
  last_content_hash TEXT,                        -- Hash lần cuối → detect change
  last_etag TEXT,                                -- HTTP ETag header
  last_modified TEXT,                            -- HTTP Last-Modified header
  notes TEXT,                                    -- Ghi chú (sửa đổi, thay thế...)
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_registry_category ON document_registry(category_id);
CREATE INDEX idx_registry_active ON document_registry(is_active);
```

### 4.4 Bảng `contract_templates` — Mẫu hợp đồng per category (MỚI)

```sql
CREATE TABLE IF NOT EXISTS contract_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id UUID REFERENCES legal_categories(id),
  contract_type TEXT NOT NULL,                   -- 'mua_ban_dat', 'cho_thue_nha'
  display_name TEXT NOT NULL,                    -- 'Hợp đồng mua bán đất'
  description TEXT,                              -- Mô tả ngắn
  search_queries JSONB NOT NULL,                 -- ["điều kiện chuyển nhượng...", ...]
  required_laws JSONB,                           -- ["Luật Đất đai 2024", "BLDS 2015"]
  min_articles INT DEFAULT 5,                    -- Số articles tối thiểu cần có
  required_fields JSONB,                         -- {"ben_a": {...}, "ben_b": {...}}
  article_outline JSONB,                         -- Template ĐIỀU 1-9 skeleton
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(category_id, contract_type)
);

CREATE INDEX IF NOT EXISTS idx_contract_templates_category
  ON contract_templates(category_id);
CREATE INDEX IF NOT EXISTS idx_contract_templates_type
  ON contract_templates(contract_type);
```

**Ví dụ data:**

```json
{
  "category_id": "<uuid_dat_dai>",
  "contract_type": "mua_ban_dat",
  "display_name": "Hợp đồng mua bán đất",
  "search_queries": [
    "điều kiện chuyển nhượng quyền sử dụng đất",
    "hợp đồng chuyển nhượng quyền sử dụng đất hình thức",
    "nghĩa vụ bên chuyển nhượng bên nhận chuyển nhượng",
    "giá đất phương thức thanh toán",
    "đăng ký biến động quyền sử dụng đất"
  ],
  "required_laws": ["Luật Đất đai 2024", "Bộ luật Dân sự 2015"],
  "min_articles": 10,
  "required_fields": {
    "ben_ban": {"label": "BÊN BÁN (BÊN A)", "fields": ["ho_ten", "ngay_sinh", "cccd", "dia_chi"]},
    "ben_mua": {"label": "BÊN MUA (BÊN B)", "fields": ["ho_ten", "ngay_sinh", "cccd", "dia_chi"]},
    "thua_dat": {"label": "THÔNG TIN THỬA ĐẤT", "fields": ["dia_chi", "dien_tich", "so_thua", "to_ban_do", "muc_dich_su_dung"]},
    "tai_chinh": {"label": "TÀI CHÍNH", "fields": ["gia_ban", "phuong_thuc_thanh_toan"]}
  },
  "article_outline": [
    "ĐIỀU 1: ĐỐI TƯỢNG CHUYỂN NHƯỢNG",
    "ĐIỀU 2: GIÁ CHUYỂN NHƯỢNG VÀ PHƯƠNG THỨC THANH TOÁN",
    "ĐIỀU 3: THỜI HẠN VÀ PHƯƠNG THỨC GIAO ĐẤT",
    "ĐIỀU 4: QUYỀN VÀ NGHĨA VỤ CỦA BÊN CHUYỂN NHƯỢNG",
    "ĐIỀU 5: QUYỀN VÀ NGHĨA VỤ CỦA BÊN NHẬN CHUYỂN NHƯỢNG",
    "ĐIỀU 6: CAM KẾT CỦA CÁC BÊN",
    "ĐIỀU 7: TRÁCH NHIỆM DO VI PHẠM HỢP ĐỒNG",
    "ĐIỀU 8: GIẢI QUYẾT TRANH CHẤP",
    "ĐIỀU 9: ĐIỀU KHOẢN CHUNG"
  ]
}
```

### 4.5 Schema tổng quan (không thay đổi)

Các bảng sau giữ nguyên từ 002:
- `legal_documents` — Metadata văn bản
- `articles` — Điều luật + embeddings
- `document_relations` — Quan hệ văn bản
- `research_audits` — Audit trail research
- `contract_audits` — Audit trail hợp đồng

---

## 5. Chi tiết thay đổi Code

### 5.1 `services/chat.py` — DB-Only RAG

**Thay đổi chính**: Loại bỏ mọi web search, thêm logic "no data".

```python
# TRƯỚC (002):
async def chat(query):
    context = await _build_context(query)          # Vector search
    # Nếu ít results → gọi thêm web search (research.py)
    response = await _call_llm(context, query)
    return response

# SAU (003):
async def chat(query):
    # Step 1: Detect topic/category
    category = await _detect_category(query)

    # Step 2: Check data availability
    availability = await _check_data_availability(category)

    if not availability.has_data:
        return ChatResponse(
            answer=_build_no_data_message(category, availability.available_categories),
            citations=[],
            has_data=False
        )

    # Step 3: Vector search (DB only)
    context = await _build_context_supabase(query)

    if not context.articles:
        return ChatResponse(
            answer=_build_insufficient_data_message(query, category),
            citations=[],
            has_data=False
        )

    # Step 4: LLM with DB context only
    response = await _call_llm(context, query)

    # Step 5: Audit
    await _save_audit(query, context, response)

    return response
```

**Methods mới**:

| Method | Mô tả |
|--------|--------|
| `_detect_category(query)` | Dùng keyword matching + LLM classify để xác định lĩnh vực |
| `_check_data_availability(category)` | Query `legal_categories` → check `article_count > 0` |
| `_build_no_data_message(category, available)` | Sinh message "Chưa đủ dữ liệu" + gợi ý |
| `_build_insufficient_data_message(query, cat)` | Khi có category nhưng search 0 results |

**Xóa/Deprecate**:
- `_build_context_legacy()` — Không dùng ChromaDB nữa
- Tất cả tham chiếu đến `research.py` trong chat flow

### 5.2 `services/research.py` — Chuyển sang DB-Only

**Thay đổi chính**: Không crawl web nữa, chỉ deep query từ DB.

```python
# TRƯỚC (002):
async def research(query):
    urls = _search_documents(query)        # Construct search URLs
    content = await _fetch_and_parse(urls)  # Crawl thuvienphapluat.vn
    articles = _extract_legal_articles(content)
    analysis = await _analyze_with_llm(articles, query)
    return analysis

# SAU (003):
async def research(query):
    # Deep search trong DB (nhiều results hơn chat)
    articles = await _deep_search_db(query, top_k=20)

    if not articles:
        return ResearchResult(
            answer="Chưa đủ dữ liệu để nghiên cứu chủ đề này.",
            available_categories=await _get_available_categories()
        )

    # Cross-reference giữa các văn bản
    related_docs = await _find_related_documents(articles)

    # LLM deep analysis
    analysis = await _analyze_with_llm(articles, related_docs, query)

    return analysis
```

### 5.3 `services/worker.py` — Background Worker (MỚI)

```python
"""
Background worker chạy pipeline tự động.

Sử dụng APScheduler với BackgroundScheduler:
- Mỗi category có 1 cron job riêng
- Schedule đọc từ legal_categories table
- Retry logic: 3 lần, exponential backoff
- Graceful shutdown khi nhận SIGTERM/SIGINT
"""

class PipelineWorker:
    def __init__(self, config: Settings):
        self.scheduler = BackgroundScheduler(
            timezone="Asia/Ho_Chi_Minh",
            job_defaults={
                'coalesce': True,           # Gộp missed runs
                'max_instances': 1,          # Không chạy song song
                'misfire_grace_time': 3600   # Cho phép trễ 1 giờ
            }
        )
        self.pipeline = PipelineService(config)
        self.is_running = False

    async def start(self):
        """Khởi động worker, load schedule từ DB."""
        categories = await self._load_active_categories()
        for cat in categories:
            self._add_job(cat)
        self.scheduler.start()
        self.is_running = True

    def stop(self):
        """Dừng worker gracefully."""
        self.scheduler.shutdown(wait=True)
        self.is_running = False

    def _add_job(self, category: CategoryConfig):
        """Thêm cron job cho 1 category."""
        if category.worker_schedule == 'daily':
            trigger = CronTrigger(
                hour=int(category.worker_time.split(':')[0]),
                minute=int(category.worker_time.split(':')[1])
            )
        elif category.worker_schedule == 'weekly':
            trigger = CronTrigger(day_of_week='sun', hour=3)
        # ...

        self.scheduler.add_job(
            self._run_pipeline_for_category,
            trigger=trigger,
            id=f"pipeline_{category.name}",
            name=f"Update {category.display_name}",
            args=[category.name],
            replace_existing=True
        )

    async def _run_pipeline_for_category(self, category_name: str):
        """Chạy pipeline cho 1 category với retry."""
        for attempt in range(3):
            try:
                result = await self.pipeline.run(
                    category=category_name,
                    trigger_type='scheduled'
                )
                await self._update_category_stats(category_name, result)
                return
            except Exception as e:
                wait = 30 * (2 ** attempt)  # 30s, 60s, 120s
                logger.error(f"Attempt {attempt+1} failed for {category_name}: {e}")
                if attempt < 2:
                    await asyncio.sleep(wait)

        # Tất cả retry fail
        await self._log_failure(category_name)

    def get_status(self) -> dict:
        """Trả về trạng thái worker + lịch chạy."""
        jobs = self.scheduler.get_jobs()
        return {
            'is_running': self.is_running,
            'jobs': [
                {
                    'id': job.id,
                    'name': job.name,
                    'next_run': str(job.next_run_time),
                    'last_run': str(getattr(job, 'last_run_time', None))
                }
                for job in jobs
            ]
        }
```

### 5.4 `services/pipeline.py` — Bổ sung incremental update

**Thay đổi chính**: Hỗ trợ incremental crawl + document registry.

```python
# Thêm vào pipeline.run():
async def run(self, category: str, trigger_type: str = 'manual', force: bool = False):
    """
    Chạy pipeline cho 1 category.

    Thay đổi so với 002:
    - Đọc URLs từ document_registry table (không hardcode)
    - Incremental: check ETag/Last-Modified trước khi crawl
    - Ghi trigger_type vào pipeline_runs
    - Cập nhật category stats sau khi xong
    """
    run_id = await self._create_pipeline_run(category, trigger_type)

    # Lấy document URLs từ registry
    registry = await self._get_document_registry(category)

    skipped = 0
    for doc_entry in registry:
        if not force:
            # Check if content changed (HEAD request)
            changed = await self._check_document_changed(doc_entry)
            if not changed:
                skipped += 1
                continue

        # Crawl → Parse → Embed → Upsert (giữ logic hiện tại)
        await self._process_document(doc_entry)

    # Cập nhật stats
    await self._finalize_run(run_id, skipped=skipped)
    await self._update_category_counts(category)
```

### 5.5 `cli/main.py` — Thêm worker commands

```python
@pipeline_app.command("worker")
def worker_command(
    action: str = typer.Argument(help="start | stop | status | schedule"),
):
    """Quản lý background worker."""
    if action == "start":
        # Khởi động worker trong background thread
        worker = PipelineWorker(get_settings())
        asyncio.run(worker.start())
        console.print("[green]✓ Worker started[/green]")

    elif action == "stop":
        # Signal worker dừng
        ...

    elif action == "status":
        # Hiển thị trạng thái
        status = worker.get_status()
        _display_worker_status(status)

    elif action == "schedule":
        # Hiển thị lịch chạy
        _display_schedule()
```

### 5.6 `legal.create-contract` Slash Command — DB-Only

**Thay đổi chính**: Loại bỏ WebSearch (step 2b cũ), thay bằng DB-only flow.

```python
# TRƯỚC (002 — legal.create-contract.md):
# Step 2a: Search Supabase articles
# Step 2b: LUÔN search web (WebSearch) ← XÓA
# Step 2c: Check hợp đồng cũ trong Supabase
# Step 2d: So sánh & sync điều luật mới ← XÓA (worker đã làm)

# SAU (003):
# Step 1: Detect contract_type + category
# Step 2: Check data availability (category có data không?)
# Step 3: Load contract template config (queries, required_laws, min_articles)
# Step 4: Multi-query DB search (dùng pre-mapped queries)
# Step 5: Validate đủ articles (≥ min_articles)
# Step 6: Hỏi user thông tin (dùng required_fields từ template)
# Step 7: Generate articles (ĐIỀU 1-9) từ DB data
# Step 8: Save JSON + Supabase audit
```

**Thay đổi trong slash command file** (`legal.create-contract.md`):

| Bước cũ | Thay đổi |
|---------|----------|
| Step 2b: LUÔN search web | **XÓA** — Không web search nữa |
| Step 2d: So sánh & sync từ web | **XÓA** — Worker đã tự động sync hàng ngày |
| Step 2a: Search Supabase | **GIỮ** — Nhưng dùng pre-mapped queries từ template |
| Step 2c: Check hợp đồng cũ | **GIỮ** — Vẫn check contract_audits |
| Fallback WebSearch | **XÓA** — Không fallback, trả "chưa đủ data" |

**Flow mới cho slash command:**

```
/legal.create-contract mua bán đất

1. Parse → contract_type = "mua_ban_dat", category = "dat_dai"

2. Check category "dat_dai" trong DB:
   → Có 2,450 articles từ 6 văn bản ✓

3. Load template "mua_ban_dat":
   → search_queries: ["điều kiện chuyển nhượng...", ...]
   → required_laws: ["Luật Đất đai 2024", "BLDS 2015"]
   → min_articles: 10

4. Multi-query search:
   → Query 1: "điều kiện chuyển nhượng" → 5 articles
   → Query 2: "hợp đồng chuyển nhượng"  → 4 articles
   → Query 3: "nghĩa vụ bên chuyển nhượng" → 6 articles
   → Query 4: "giá đất thanh toán" → 3 articles
   → Merge + dedup → 15 unique articles ✓ (≥ 10)

5. Thông báo:
   "Đã tìm thấy 15 điều luật liên quan trong cơ sở dữ liệu!
    - Luật Đất đai 2024: 10 điều
    - BLDS 2015: 5 điều
    Bắt đầu thu thập thông tin..."

6. Hỏi user → Generate → Save
```

---

## 6. Document Registry — Dữ liệu ban đầu

### 6.1 Category: Đất đai (`dat_dai`)

| Role | Văn bản | Số hiệu | URL |
|------|---------|----------|-----|
| primary | Luật Đất đai 2024 | 31/2024/QH15 | thuvienphapluat.vn/van-ban/Bat-dong-san/Luat-Dat-dai-2024-... |
| related | NĐ hướng dẫn Luật Đất đai | 101/2024/NĐ-CP | thuvienphapluat.vn/van-ban/... |
| related | NĐ KDBĐS | 96/2024/NĐ-CP | thuvienphapluat.vn/van-ban/... |
| related | Luật Kinh doanh BĐS 2023 | 29/2023/QH15 | thuvienphapluat.vn/van-ban/... |
| related | Luật Nhà ở 2023 | 27/2023/QH15 | thuvienphapluat.vn/van-ban/... |
| base | Bộ luật Dân sự 2015 | 91/2015/QH13 | thuvienphapluat.vn/van-ban/... |

### 6.2 Category: Dân sự (`dan_su`)

| Role | Văn bản | Số hiệu |
|------|---------|----------|
| primary | Bộ luật Dân sự 2015 | 91/2015/QH13 |
| related | NĐ hướng dẫn BLDS | Các NĐ liên quan |

### 6.3 Category: Lao động (`lao_dong`)

| Role | Văn bản | Số hiệu |
|------|---------|----------|
| primary | Bộ luật Lao động 2019 | 45/2019/QH14 |
| related | NĐ 145/2020/NĐ-CP | Hướng dẫn BLLĐ |
| related | NĐ 135/2020/NĐ-CP | Tuổi nghỉ hưu |

---

## 7. "No Data" Response Templates

### 7.1 Khi category không tồn tại hoặc chưa crawl

```
⚠ Hệ thống chưa có dữ liệu về lĩnh vực "{category_display_name}".

Hiện tại hệ thống đã có dữ liệu cho các lĩnh vực sau:
  • Đất đai (2,450 điều luật từ 6 văn bản)
  • Dân sự (689 điều luật từ 2 văn bản)
  • Lao động (220 điều luật từ 4 văn bản)

Bạn có thể:
  1. Hỏi về các lĩnh vực trên
  2. Liên hệ admin để bổ sung bộ luật mới

Lưu ý: Hệ thống chỉ trả lời dựa trên dữ liệu pháp luật đã được
xác minh trong cơ sở dữ liệu, không sử dụng nguồn bên ngoài.
```

### 7.2 Khi create-contract nhưng chưa có data

```
⚠ Chưa đủ dữ liệu pháp luật để tạo hợp đồng "{contract_type_vn}".

Lĩnh vực "{category_display_name}" chưa được đồng bộ vào hệ thống.
Vui lòng liên hệ admin chạy: /legal.pipeline crawl {category_name}

Hiện có thể tạo các loại hợp đồng sau:
  Đất đai:
    • Mua bán đất    • Cho thuê đất    • Chuyển nhượng QSDĐ
  Nhà ở:
    • Mua bán nhà    • Thuê nhà        • Đặt cọc mua nhà
  Lao động:
    • Hợp đồng lao động    • Thử việc
  Dân sự:
    • Vay tiền    • Ủy quyền    • Dịch vụ
```

### 7.3 Khi create-contract nhưng data không đủ (< min_articles)

```
⚠ Dữ liệu pháp luật cho "{contract_type_vn}" chưa đầy đủ.

Tìm thấy {found} điều luật, cần tối thiểu {min_articles} điều.
Thiếu dữ liệu từ: {missing_laws}

Bạn có muốn:
  1. Tiếp tục tạo hợp đồng (có thể thiếu một số điều khoản)
  2. Hủy và đợi admin bổ sung dữ liệu
```

### 7.4 Khi có category nhưng search không ra kết quả phù hợp

```
Không tìm thấy điều luật phù hợp cho câu hỏi của bạn trong
lĩnh vực "{category_display_name}".

Hệ thống có {article_count} điều luật trong lĩnh vực này.
Bạn có thể thử:
  • Diễn đạt câu hỏi khác
  • Hỏi cụ thể hơn (ví dụ: "Điều 45 Luật Đất đai 2024")
```

---

## 8. Incremental Update Strategy

### 8.1 Change Detection Flow

```
Worker check document:
     │
     ▼
┌──────────────────────┐
│ 1. HTTP HEAD request │  ← Check ETag + Last-Modified header
│    (không tải nội    │
│     dung)            │
└────────┬─────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
 Unchanged   Changed (hoặc không có ETag)
    │              │
    ▼              ▼
  SKIP       ┌──────────────────────┐
  (log)      │ 2. Full crawl        │
             │    (Playwright)      │
             └────────┬─────────────┘
                      │
                      ▼
             ┌──────────────────────┐
             │ 3. Compute SHA-256   │
             │    content hash      │
             └────────┬─────────────┘
                      │
                 ┌────┴────┐
                 │         │
                 ▼         ▼
              Same hash   Different hash
                 │              │
                 ▼              ▼
               SKIP       ┌──────────────┐
               (update     │ 4. Re-parse  │
                etag       │    articles   │
                only)      │ 5. Re-embed  │
                           │ 6. Upsert DB │
                           └──────────────┘
```

### 8.2 Phát hiện văn bản mới

```
Worker check listing page:
     │
     ▼
┌──────────────────────────────┐
│ Crawl listing page:          │
│ thuvienphapluat.vn/van-ban/  │
│ Bat-dong-san/                │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ Extract danh sách văn bản    │
│ trên trang listing           │
│                              │
│ So sánh với document_registry│
│ → phát hiện URL mới          │
└────────┬─────────────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
  No new    New documents found
  docs           │
    │            ▼
  DONE    ┌──────────────────────┐
          │ 1. Add vào registry  │
          │    (role = 'related')│
          │ 2. Crawl + parse     │
          │ 3. Embed + upsert   │
          │ 4. Log discovery     │
          └──────────────────────┘
```

---

## 9. Configuration

### 9.1 Environment Variables mới

```bash
# Worker settings (NEW)
WORKER_ENABLED=true                           # Bật/tắt worker khi start app
WORKER_DEFAULT_SCHEDULE=daily                 # 'daily', 'weekly'
WORKER_DEFAULT_TIME=02:00                     # UTC+7
WORKER_RETRY_COUNT=3                          # Số lần retry khi fail
WORKER_RETRY_BACKOFF=30                       # Base seconds cho exponential backoff

# Pipeline settings (unchanged)
PIPELINE_RATE_LIMIT=4                         # seconds between requests
PIPELINE_MAX_PAGES=50                         # max pages per run

# Chat settings (NEW behavior)
CHAT_MODE=db_only                             # 'db_only' (003) — loại bỏ 'hybrid'
CHAT_NO_DATA_BEHAVIOR=inform                  # 'inform' = trả lời rõ ràng
```

### 9.2 Category Schedule Configuration

Schedule cho mỗi category được lưu trong `legal_categories` table:

```
dat_dai:     daily   02:00   active
nha_o:       daily   02:30   active
dan_su:      weekly  Sun 03  active
lao_dong:    daily   03:00   active
doanh_nghiep: weekly  Mon 03  paused
thuong_mai:  weekly  Mon 04  paused
```

---

## 10. Project Structure thay đổi

```
legal_chatbot/
  services/
    chat.py              # ← THAY ĐỔI: DB-only, no web search, + no-data handling
    research.py          # ← THAY ĐỔI: DB-only deep search, no crawl
    contract.py          # ← MỚI: Contract creation service (DB-only, template-based)
    pipeline.py          # ← THAY ĐỔI: incremental update, document registry
    worker.py            # ← MỚI: Background worker (APScheduler)
    crawler.py           # Giữ nguyên (dùng bởi worker/pipeline)
    indexer.py           # Giữ nguyên
    embedding.py         # Giữ nguyên
    audit.py             # Giữ nguyên
  db/
    supabase.py          # ← THAY ĐỔI: thêm document_registry CRUD, category stats
    migrations/
      003_worker.sql     # ← MỚI: ALTER tables + CREATE document_registry
  models/
    pipeline.py          # ← THAY ĐỔI: thêm WorkerStatus, DocumentRegistryEntry
    chat.py              # ← THAY ĐỔI: thêm has_data field, NoDataResponse
  cli/
    main.py              # ← THAY ĐỔI: thêm worker commands, update chat behavior
  utils/
    config.py            # ← THAY ĐỔI: thêm worker settings
```

---

## 11. Migration SQL — `003_worker.sql`

```sql
-- =============================================
-- Migration 003: Background Worker + DB-Only Chat
-- =============================================

-- 1. Bổ sung legal_categories
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS
  worker_schedule TEXT DEFAULT 'daily';
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS
  worker_time TEXT DEFAULT '02:00';
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS
  worker_status TEXT DEFAULT 'active';
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS
  document_count INT DEFAULT 0;
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS
  article_count INT DEFAULT 0;
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS
  last_worker_run_at TIMESTAMPTZ;
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS
  last_worker_status TEXT;

-- 2. Bổ sung pipeline_runs
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS
  trigger_type TEXT DEFAULT 'manual';
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS
  documents_skipped INT DEFAULT 0;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS
  duration_seconds FLOAT;

-- 3. Tạo document_registry
CREATE TABLE IF NOT EXISTS document_registry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id UUID REFERENCES legal_categories(id),
  url TEXT NOT NULL UNIQUE,
  document_number TEXT,
  title TEXT,
  role TEXT DEFAULT 'primary',
  priority INT DEFAULT 1,
  is_active BOOLEAN DEFAULT true,
  last_checked_at TIMESTAMPTZ,
  last_content_hash TEXT,
  last_etag TEXT,
  last_modified TEXT,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_registry_category
  ON document_registry(category_id);
CREATE INDEX IF NOT EXISTS idx_registry_active
  ON document_registry(is_active);

-- 4. Tạo contract_templates
CREATE TABLE IF NOT EXISTS contract_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id UUID REFERENCES legal_categories(id),
  contract_type TEXT NOT NULL,
  display_name TEXT NOT NULL,
  description TEXT,
  search_queries JSONB NOT NULL,
  required_laws JSONB,
  min_articles INT DEFAULT 5,
  required_fields JSONB,
  article_outline JSONB,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(category_id, contract_type)
);

CREATE INDEX IF NOT EXISTS idx_contract_templates_category
  ON contract_templates(category_id);
CREATE INDEX IF NOT EXISTS idx_contract_templates_type
  ON contract_templates(contract_type);

-- 5. RLS cho document_registry
ALTER TABLE document_registry ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read document_registry" ON document_registry
  FOR SELECT USING (true);

CREATE POLICY "Allow service role write document_registry" ON document_registry
  FOR ALL USING (auth.role() = 'service_role');

-- 6. RLS cho contract_templates
ALTER TABLE contract_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read contract_templates" ON contract_templates
  FOR SELECT USING (true);

CREATE POLICY "Allow service role write contract_templates" ON contract_templates
  FOR ALL USING (auth.role() = 'service_role');

-- 7. Cập nhật category counts (function)
CREATE OR REPLACE FUNCTION update_category_counts(cat_id UUID)
RETURNS VOID AS $$
BEGIN
  UPDATE legal_categories SET
    document_count = (
      SELECT COUNT(*) FROM legal_documents WHERE category_id = cat_id
    ),
    article_count = (
      SELECT COUNT(*) FROM articles a
      JOIN legal_documents d ON a.document_id = d.id
      WHERE d.category_id = cat_id
    )
  WHERE id = cat_id;
END;
$$ LANGUAGE plpgsql;
```

---

## 12. Testing Strategy

### 12.1 Unit Tests

```bash
# Test worker scheduler
pytest tests/unit/test_worker.py
  - test_worker_start_stop
  - test_schedule_loading_from_db
  - test_retry_on_failure
  - test_graceful_shutdown

# Test DB-only chat
pytest tests/unit/test_chat_db_only.py
  - test_chat_with_data_returns_rag
  - test_chat_no_data_returns_message
  - test_chat_insufficient_results
  - test_detect_category

# Test incremental pipeline
pytest tests/unit/test_pipeline_incremental.py
  - test_skip_unchanged_document
  - test_detect_content_change
  - test_document_registry_crud

# Test DB-only contract creation
pytest tests/unit/test_contract_db_only.py
  - test_create_contract_with_data
  - test_create_contract_no_data_returns_message
  - test_create_contract_insufficient_articles_warns
  - test_contract_template_loading
  - test_multi_query_search_merge_dedup
  - test_contract_legal_references_from_db
```

### 12.2 Integration Tests

```bash
# Test end-to-end: worker → pipeline → DB → chat
pytest tests/integration/test_worker_e2e.py

# Test no-data response
pytest tests/integration/test_no_data_response.py

# Test create-contract e2e (DB-only)
pytest tests/integration/test_contract_db_only_e2e.py
```

### 12.3 Acceptance Tests

```bash
# 1. Setup
/legal.db migrate                              # Run 003_worker.sql

# 2. Crawl initial data
/legal.pipeline crawl dat_dai

# 3. Verify data
/legal.db status
# Expected: dat_dai category has documents + articles

# 4. Test DB-only chat (có data)
/legal.research "Điều kiện chuyển nhượng đất"
# Expected: Response with citations from DB, NO web search

# 5. Test no-data response
# Chat: "Quy định bảo hiểm xã hội?"
# Expected: "Chưa đủ dữ liệu" message + list available categories

# 6. Start worker
/legal.pipeline worker start
/legal.pipeline worker status
# Expected: Worker running, jobs scheduled

# 7. Force trigger (test)
/legal.pipeline crawl dat_dai --force
# Expected: Re-crawl all documents, re-embed if changed

# 8. Test create-contract DB-only (có data)
/legal.create-contract mua bán đất
# Expected: Search DB → 15+ articles → hỏi thông tin → tạo hợp đồng
#           KHÔNG web search trong toàn bộ quá trình

# 9. Test create-contract no-data
/legal.create-contract hợp đồng bảo hiểm
# Expected: "Chưa đủ dữ liệu" + list contract types có sẵn
```

---

## 13. Phases phát triển

### Phase 1: DB-Only Chat + Create-Contract (ưu tiên cao nhất)
- [ ] Sửa `services/chat.py` — loại bỏ web search
- [ ] Thêm `_detect_category()` và `_check_data_availability()`
- [ ] Implement no-data response templates (chat + contract)
- [ ] Sửa `services/research.py` — DB-only deep search
- [ ] Implement `services/contract.py` — DB-only contract creation
- [ ] Update `models/chat.py` — thêm `has_data` field
- [ ] Sửa `legal.create-contract.md` — xóa WebSearch steps
- [ ] Test: chat có data vs không data
- [ ] Test: create-contract có data vs không data

### Phase 2: Contract Templates + Document Registry
- [ ] Tạo migration `003_worker.sql` (bao gồm `contract_templates` table)
- [ ] Implement `contract_templates` CRUD trong `db/supabase.py`
- [ ] Seed contract templates cho: đất đai, nhà ở, lao động, dân sự
- [ ] Implement multi-query search (dùng pre-mapped queries từ template)
- [ ] Implement `document_registry` CRUD trong `db/supabase.py`
- [ ] Sửa `services/pipeline.py` — đọc URLs từ registry
- [ ] Implement HEAD request check (ETag, Last-Modified)
- [ ] Implement content hash comparison
- [ ] Seed initial registry data (đất đai, dân sự, lao động)

### Phase 3: Background Worker
- [ ] Implement `services/worker.py` với APScheduler
- [ ] Load schedule từ `legal_categories` table
- [ ] Retry logic (3x, exponential backoff)
- [ ] Graceful shutdown (SIGTERM/SIGINT)
- [ ] CLI commands: worker start/stop/status/schedule
- [ ] Logging pipeline runs với trigger_type

### Phase 4: Listing Page Discovery
- [ ] Worker crawl listing pages để phát hiện văn bản mới
- [ ] Tự động thêm vào document_registry
- [ ] Tự động crawl + index văn bản mới
- [ ] Cập nhật status văn bản cũ khi bị thay thế

### Phase 5: Polish & Monitoring
- [ ] Category stats dashboard (document_count, article_count)
- [ ] Contract templates management (list, add, update)
- [ ] Worker health check
- [ ] Alert khi worker fail liên tục
- [ ] End-to-end testing
- [ ] Update CLAUDE.md + slash commands

---

## 14. Lưu ý quan trọng

1. **KHÔNG web search trong chat VÀ create-contract**: Đây là thay đổi lớn nhất — chat, research, VÀ tạo hợp đồng chỉ dùng DB. Nếu không có data → nói thẳng, không cố tìm
2. **Contract templates = cấu hình sẵn**: Mỗi category có danh sách contract types + pre-mapped queries. Không cần user tự nghĩ search term
3. **Data phải có TRƯỚC khi tạo hợp đồng**: Admin phải crawl bộ luật trước → worker cập nhật hàng ngày → khi user tạo HĐ thì data đã sẵn sàng
4. **Worker KHÔNG chạy mặc định**: Phải explicit start bằng command. Tránh surprise resource usage
5. **Rate limiting nghiêm ngặt**: Worker crawl ban đêm (2-3 AM) với rate limit 4-6s/request — không tạo load cho thuvienphapluat.vn
6. **Document Registry = Single Source of Truth**: Pipeline chỉ crawl URLs có trong registry, không crawl random
7. **Incremental trước, full crawl khi cần**: Mặc định skip unchanged docs. Dùng `--force` khi cần full re-crawl
8. **Backwards compatible**: Tất cả changes phải giữ nguyên interface hiện tại (CLI commands, DB schema). Chỉ ADD, không BREAK
9. **SQLite mode**: Worker VÀ contract templates KHÔNG hỗ trợ SQLite mode. Chỉ chạy với Supabase
