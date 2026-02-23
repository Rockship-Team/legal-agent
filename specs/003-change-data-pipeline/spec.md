# 003 - Thiết kế lại Data Pipeline: DB-First + Background Worker

## 1. Tổng quan

### 1.1 User Problem

**User gặp phải 3 vấn đề chính khi sử dụng hệ thống hiện tại:**

1. **Chat chậm và không ổn định**: Mỗi câu hỏi pháp luật phải chờ web search (5-15s), thường bị Cloudflare block → timeout hoặc trả kết quả sai
2. **Tạo hợp đồng không nhất quán**: Cùng loại hợp đồng, tạo 2 lần cho kết quả khác nhau vì mỗi lần web search ra kết quả khác
3. **Không biết hệ thống hỗ trợ gì**: Khi hỏi về bộ luật chưa có data, hệ thống vẫn cố trả lời → kết quả sai, mất tin tưởng

### 1.2 Giải pháp

Chuyển sang **DB-First**: Mọi tương tác (chat, research, tạo hợp đồng) chỉ dùng data đã index trong Supabase. Background worker tự động cập nhật data.

### 1.3 Definition of Done (DOD)

| # | Tiêu chí | Cách kiểm tra |
|---|----------|---------------|
| 1 | Chat trả lời < 3s (không web search) | Đo response time khi chat về lĩnh vực đã có data |
| 2 | Chat trả "chưa đủ dữ liệu" khi không có data | Hỏi về bảo hiểm xã hội (chưa crawl) → nhận thông báo rõ ràng |
| 3 | Create-contract cho kết quả nhất quán | Tạo 2 HĐ mua bán đất → cùng citations, cùng điều luật |
| 4 | Create-contract không web search | Toàn bộ flow không gọi web, chỉ DB |
| 5 | Worker tự động cập nhật luật | Để worker chạy → kiểm tra pipeline_runs có log mới |
| 6 | Incremental crawl hoạt động | Chạy crawl 2 lần → lần 2 skip docs unchanged |
| 7 | App hiển thị rõ hỗ trợ bộ luật nào | User thấy danh sách categories + số articles đã có |

### 1.4 Vấn đề kỹ thuật hiện tại (002)

1. **Pipeline chạy thủ công**: Không có scheduler — admin phải gõ CLI mỗi lần muốn cập nhật
2. **Chat phụ thuộc web search**: `research.py` crawl real-time → chậm, bị Cloudflare block
3. **Không phân biệt "có data" vs "chưa có data"**: Hệ thống cố search → trả kết quả sai
4. **Pipeline crawl theo category chung**: Không target cụ thể bộ luật
5. **Create-contract phụ thuộc web search**: Kết quả không đồng nhất giữa các lần tạo
6. **Không có contract templates sẵn**: Mỗi lần tạo HĐ phải research lại từ đầu

### 1.5 Thống kê bộ luật Việt Nam vs App Coverage

Việt Nam hiện có **~266 luật/bộ luật** đang có hiệu lực, trong đó **6 bộ luật lớn** và ~260 luật riêng lẻ. Cho mục đích **tư vấn pháp luật và tạo hợp đồng**, có khoảng **36 luật quan trọng** nhất.

#### App hiện đang hỗ trợ (đã crawl/có thể crawl)

| Category | Bộ luật chính | Trạng thái | Contract types |
|----------|---------------|-----------|----------------|
| `dat_dai` | Luật Đất đai 2024 (31/2024/QH15) | **Đã crawl** | mua bán đất, cho thuê, chuyển nhượng, thế chấp |
| `nha_o` | Luật Nhà ở 2023 (27/2023/QH15) | **Đã crawl** | mua bán nhà, thuê nhà, đặt cọc |
| `dan_su` | Bộ luật Dân sự 2015 (91/2015/QH13) | **Đã crawl** | vay tiền, ủy quyền, dịch vụ, mua bán tài sản |
| `lao_dong` | Bộ luật Lao động 2019 (45/2019/QH14) | **Đã crawl** | HĐLĐ, thử việc, chấm dứt HĐLĐ |
| `doanh_nghiep` | Luật Doanh nghiệp 2020 (59/2020/QH14) | Chưa crawl | - |
| `thuong_mai` | Luật Thương mại 2005 (36/2005/QH11) | Chưa crawl | - |

#### App chưa hỗ trợ (có thể mở rộng sau)

| Lĩnh vực | Luật chính | Lý do chưa hỗ trợ |
|-----------|-----------|-------------------|
| Bảo hiểm xã hội | Luật BHXH 2024 (41/2024/QH15) | Ít liên quan đến hợp đồng dân sự |
| Thuế | Luật Thuế GTGT 2024, Thuế TNDN | Chuyên biệt, cần domain expert |
| Sở hữu trí tuệ | Luật SHTT 2005 (sửa đổi 2022) | Chuyên biệt |
| Xây dựng | Luật Xây dựng 2014 (sửa đổi 2020) | Có thể thêm phase sau |
| Kinh doanh BĐS | Luật KDBĐS 2023 (29/2023/QH15) | Đã là `related` trong `dat_dai` |
| Hình sự | Bộ luật Hình sự 2015 | Ngoài scope (không tạo HĐ) |

**Tổng kết**: App target **6 lĩnh vực chính** / 36 luật quan trọng cho hợp đồng. Hiện đã crawl **4/6 lĩnh vực**.

---

### 1.6 Mục tiêu thiết kế lại

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
Worker chạy ngầm: check cập nhật Luật Đất đai mỗi tuần (Chủ nhật 2:00 AM)

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
  2. Trả lời tự nhiên (giọng AI chat, không cứng nhắc):
     "Hiện tại mình chưa có dữ liệu về lĩnh vực Bảo hiểm xã hội
      nên không thể tư vấn chính xác được. 😊

      Mình có thể giúp bạn về:
      • Đất đai (2,450 điều luật)
      • Nhà ở (1,200 điều luật)
      • Dân sự (689 điều luật)
      • Lao động (220 điều luật)

      Bạn muốn hỏi về lĩnh vực nào?"
  3. KHÔNG cố web search hay trả lời bừa

═══ Scenario 3: Worker phát hiện luật thay đổi ═══

Worker (Chủ nhật 2:00 AM weekly):
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
  2. Trả lời tự nhiên:
     "Mình chưa có đủ dữ liệu về Luật Bảo hiểm để tạo hợp đồng
      chính xác cho bạn. 😊

      Hiện mình có thể tạo các loại hợp đồng sau:
      • Đất đai: mua bán đất, cho thuê đất, chuyển nhượng QSDĐ
      • Nhà ở: thuê nhà, mua bán nhà, đặt cọc
      • Lao động: HĐLĐ, thử việc
      • Dân sự: vay tiền, ủy quyền, dịch vụ

      Bạn muốn tạo loại nào?"
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
| **Schedule** | Mỗi bộ luật có lịch cập nhật riêng (mặc định **weekly** — luật ít thay đổi) |
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
│  │  │ dat_dai    │ weekly │ Sun 2AM  │ active │ 6 URLs │  │  │
│  │  │ nha_o      │ weekly │ Sun 2:30 │ active │ 3 URLs │  │  │
│  │  │ dan_su     │ weekly │ Sun 3AM  │ active │ 2 URLs │  │  │
│  │  │ lao_dong   │ weekly │ Sun 3:30 │ paused │ 4 URLs │  │  │
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
│    schedule: weekly Sun 02:00                                      │
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
  worker_schedule TEXT DEFAULT 'weekly';          -- 'daily', 'weekly', 'monthly'

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

## 5. Thay đổi chính (WHAT, không phải HOW)

> Chi tiết implementation: xem `specs/003-change-data-pipeline/contracts/` và `plan.md`

### 5.1 `services/chat.py` — DB-Only RAG

| Thay đổi | Mô tả |
|----------|--------|
| **Xóa** web search fallback | Chat chỉ query Supabase, không gọi `research.py` |
| **Thêm** `_detect_category(query)` | Keyword + LLM classify → xác định lĩnh vực |
| **Thêm** `_check_data_availability()` | Check `article_count > 0` → trả no-data message nếu thiếu |
| **Xóa** `_build_context_legacy()` | Không dùng ChromaDB nữa |

### 5.2 `services/research.py` — DB-Only Deep Search

| Thay đổi | Mô tả |
|----------|--------|
| **Xóa** web crawl | Không crawl thuvienphapluat.vn real-time nữa |
| **Thêm** deep DB search | `top_k=20` (nhiều hơn chat), cross-reference giữa văn bản |
| **Thêm** no-data response | Trả danh sách categories khả dụng khi không có data |

### 5.3 `services/worker.py` — Background Worker (MỚI)

| Tính năng | Mô tả |
|-----------|--------|
| APScheduler AsyncIOScheduler | Mỗi category = 1 cron job, schedule đọc từ DB |
| Retry logic | 3 lần, exponential backoff (30s, 60s, 120s) |
| Graceful shutdown | SIGINT/SIGBREAK handler, `scheduler.shutdown(wait=True)` |
| Status/Schedule API | `get_status()`, `get_schedule()` cho CLI hiển thị |

### 5.4 `services/pipeline.py` — Incremental Update

| Thay đổi | Mô tả |
|----------|--------|
| **Đọc URLs từ `document_registry`** | Không hardcode URLs nữa |
| **Content hash comparison** | SHA-256, skip unchanged docs |
| **trigger_type tracking** | `manual`, `scheduled`, `forced` |
| **Category stats update** | Cập nhật `document_count`, `article_count` sau mỗi run |

### 5.5 `services/contract.py` — Contract Service (MỚI)

| Tính năng | Mô tả |
|-----------|--------|
| Load template từ DB | Pre-mapped search queries, required_laws, min_articles |
| Multi-query vector search | Search từng query → merge + dedup articles |
| Data validation | Check ≥ min_articles trước khi tạo HĐ |
| No-data handling | Trả danh sách contract types khả dụng |

### 5.6 `legal.create-contract` Slash Command

| Bước cũ | Thay đổi |
|---------|----------|
| Step 2b: LUÔN search web | **XÓA** — Không web search nữa |
| Step 2d: So sánh & sync từ web | **XÓA** — Worker đã tự động sync |
| Step 2a: Search Supabase | **GIỮ** — Dùng pre-mapped queries từ template |
| Fallback WebSearch | **XÓA** — Trả "chưa đủ data" thay vì cố search |

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

**Nguyên tắc**: Response phải tự nhiên, thân thiện — đây là AI chat, không phải error message. Giọng điệu: helpful assistant, không cứng nhắc.

```
Hiện tại mình chưa có dữ liệu về lĩnh vực {category_display_name}
nên không thể tư vấn chính xác được. 😊

Mình có thể giúp bạn về:
  • Đất đai ({article_count} điều luật)
  • Nhà ở ({article_count} điều luật)
  • Dân sự ({article_count} điều luật)
  • Lao động ({article_count} điều luật)

Bạn muốn hỏi về lĩnh vực nào?
```

### 7.2 Khi create-contract nhưng chưa có data

```
Mình chưa có đủ dữ liệu pháp luật về {category_display_name}
để tạo hợp đồng {contract_type_vn} chính xác cho bạn.

Hiện mình có thể tạo:
  • Đất đai: mua bán đất, cho thuê đất, chuyển nhượng, thế chấp
  • Nhà ở: mua bán nhà, thuê nhà, đặt cọc
  • Lao động: HĐLĐ, thử việc, chấm dứt HĐLĐ
  • Dân sự: vay tiền, ủy quyền, dịch vụ, mua bán tài sản

Bạn muốn tạo loại nào?
```

### 7.3 Khi create-contract nhưng data không đủ (< min_articles)

```
Mình tìm được {found} điều luật liên quan, nhưng thường cần
ít nhất {min_articles} điều để tạo hợp đồng đầy đủ.

Có thể thiếu một số điều khoản từ: {missing_laws}

Bạn muốn:
  1. Tiếp tục tạo (mình sẽ ghi chú phần nào cần bổ sung)
  2. Dừng lại để bổ sung dữ liệu trước
```

### 7.4 Khi có category nhưng search không ra kết quả phù hợp

```
Mình không tìm thấy điều luật phù hợp với câu hỏi này trong
lĩnh vực {category_display_name} ({article_count} điều luật).

Bạn thử:
  • Diễn đạt cụ thể hơn (ví dụ: "Điều 45 Luật Đất đai 2024")
  • Hỏi theo hướng khác

Mình sẵn sàng hỗ trợ! 😊
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
WORKER_DEFAULT_SCHEDULE=weekly                # 'weekly', 'monthly' (luật ít thay đổi)
WORKER_DEFAULT_TIME=02:00                     # UTC+7, chạy Chủ nhật
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
dat_dai:     weekly  Sun 02:00  active
nha_o:       weekly  Sun 02:30  active
dan_su:      weekly  Sun 03:00  active
lao_dong:    weekly  Sun 03:30  active
doanh_nghiep: monthly 1st 03:00 paused
thuong_mai:  monthly 1st 04:00 paused
```

> **Tại sao weekly thay vì daily?** Bộ luật VN thường chỉ sửa đổi/bổ sung
> vài lần mỗi năm (qua Nghị định, Thông tư). Crawl daily lãng phí tài nguyên
> và tạo load không cần thiết lên thuvienphapluat.vn. Weekly đủ để phát hiện
> thay đổi kịp thời. Admin có thể force crawl bất cứ lúc nào nếu cần.

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
  worker_schedule TEXT DEFAULT 'weekly';
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
