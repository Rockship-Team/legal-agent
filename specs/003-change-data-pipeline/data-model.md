# Data Model: 003 - Thiết kế lại Data Pipeline

**Date**: 2026-02-23 | **Branch**: `003-change-data-pipeline`

## Entity Overview

```
┌─────────────────────┐     ┌─────────────────────┐
│  legal_categories   │────<│  contract_templates  │  NEW
│  (extended)         │     │                      │
└─────────┬───────────┘     └──────────────────────┘
          │
          │ 1:N
          ▼
┌─────────────────────┐     ┌─────────────────────┐
│  document_registry  │────>│  legal_documents     │
│  NEW                │     │  (unchanged)         │
└─────────────────────┘     └──────────┬──────────┘
                                       │ 1:N
                                       ▼
                            ┌─────────────────────┐
                            │  articles            │
                            │  (unchanged)         │
                            └──────────────────────┘

┌─────────────────────┐
│  pipeline_runs      │
│  (extended)         │
└─────────────────────┘
```

---

## New Entities

### 1. `document_registry` — Danh sách URL cụ thể per category

Tracks specific URLs to crawl for each law category, their last-known state, and change detection metadata.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, default gen_random_uuid() | |
| `category_id` | UUID | FK → legal_categories(id) | Lĩnh vực pháp luật |
| `url` | TEXT | NOT NULL, UNIQUE | URL trên thuvienphapluat.vn |
| `document_number` | TEXT | | Số hiệu (nếu biết trước) |
| `title` | TEXT | | Tên văn bản |
| `role` | TEXT | DEFAULT 'primary' | 'primary', 'related', 'base' |
| `priority` | INT | DEFAULT 1 | Thứ tự crawl (1 = cao nhất) |
| `is_active` | BOOLEAN | DEFAULT true | Có crawl không |
| `last_checked_at` | TIMESTAMPTZ | | Lần cuối check |
| `last_content_hash` | TEXT | | SHA-256 hash lần cuối |
| `last_etag` | TEXT | | HTTP ETag (nếu có) |
| `last_modified` | TEXT | | HTTP Last-Modified (nếu có) |
| `notes` | TEXT | | Ghi chú |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: `category_id`, `is_active`

**Relationships**:
- `category_id` → `legal_categories.id` (N:1)

---

### 2. `contract_templates` — Mẫu hợp đồng per category

Pre-configured templates for contract creation, including search queries and field definitions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, default gen_random_uuid() | |
| `category_id` | UUID | FK → legal_categories(id) | Lĩnh vực pháp luật |
| `contract_type` | TEXT | NOT NULL | 'mua_ban_dat', 'cho_thue_nha' |
| `display_name` | TEXT | NOT NULL | 'Hợp đồng mua bán đất' |
| `description` | TEXT | | Mô tả ngắn |
| `search_queries` | JSONB | NOT NULL | Pre-mapped vector search terms |
| `required_laws` | JSONB | | Expected law documents |
| `min_articles` | INT | DEFAULT 5 | Minimum articles needed |
| `required_fields` | JSONB | | User data collection template |
| `article_outline` | JSONB | | ĐIỀU 1-9 skeleton |
| `is_active` | BOOLEAN | DEFAULT true | |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | |

**Constraints**: UNIQUE(`category_id`, `contract_type`)

**Indexes**: `category_id`, `contract_type`

---

## Extended Entities

### 3. `legal_categories` — Bổ sung worker schedule fields

New columns added to existing table:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `worker_schedule` | TEXT | 'daily' | 'daily', 'weekly', 'monthly' |
| `worker_time` | TEXT | '02:00' | Giờ chạy (HH:MM, UTC+7) |
| `worker_status` | TEXT | 'active' | 'active', 'paused', 'disabled' |
| `document_count` | INT | 0 | Cache: số documents đã crawl |
| `article_count` | INT | 0 | Cache: số articles đã index |
| `last_worker_run_at` | TIMESTAMPTZ | NULL | Lần cuối worker chạy |
| `last_worker_status` | TEXT | NULL | 'success', 'partial', 'failed' |

---

### 4. `pipeline_runs` — Bổ sung worker metadata

New columns added to existing table:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `trigger_type` | TEXT | 'manual' | 'manual', 'scheduled', 'forced' |
| `documents_skipped` | INT | 0 | Docs bỏ qua (unchanged hash) |
| `duration_seconds` | FLOAT | NULL | Thời gian chạy |

---

## Unchanged Entities (from 002)

These tables remain unchanged:
- `legal_documents` — Document metadata + content_hash
- `articles` — Individual articles + embeddings (vector 768d)
- `document_relations` — Relationships between documents
- `research_audits` — Audit trail for research queries
- `contract_audits` — Audit trail for generated contracts

---

## Pydantic Models

### New Models

```python
# legal_chatbot/models/pipeline.py (additions)

class DocumentRegistryEntry(BaseModel):
    """Entry in the document registry."""
    id: Optional[str] = None
    category_id: str
    url: str
    document_number: Optional[str] = None
    title: Optional[str] = None
    role: str = "primary"           # primary, related, base
    priority: int = 1
    is_active: bool = True
    last_checked_at: Optional[datetime] = None
    last_content_hash: Optional[str] = None
    last_etag: Optional[str] = None
    last_modified: Optional[str] = None
    notes: Optional[str] = None

class WorkerStatus(BaseModel):
    """Status of the background worker."""
    is_running: bool
    jobs: List[WorkerJob]
    last_check: datetime

class WorkerJob(BaseModel):
    """Individual scheduled job."""
    id: str
    name: str
    category: str
    next_run: Optional[datetime]
    last_run: Optional[datetime]
    trigger: str                    # 'daily 02:00', 'weekly Sun 03:00'
    status: str                     # 'active', 'paused'


# legal_chatbot/models/contract.py (new file)

class ContractTemplate(BaseModel):
    """Pre-configured contract template."""
    id: Optional[str] = None
    category_id: str
    contract_type: str              # 'mua_ban_dat', 'cho_thue_nha'
    display_name: str               # 'Hợp đồng mua bán đất'
    description: Optional[str] = None
    search_queries: List[str]       # Pre-mapped vector search terms
    required_laws: List[str] = []   # Expected law documents
    min_articles: int = 5
    required_fields: Optional[dict] = None  # User data template
    article_outline: Optional[List[str]] = None  # ĐIỀU 1-9 skeleton
    is_active: bool = True

class DataAvailability(BaseModel):
    """Data availability check result."""
    category: Optional[str]
    has_data: bool
    article_count: int = 0
    document_count: int = 0
    available_categories: List[CategoryInfo] = []
    available_contract_types: List[str] = []

class CategoryInfo(BaseModel):
    """Category info for no-data response."""
    name: str
    display_name: str
    article_count: int
    document_count: int
    contract_types: List[str] = []
```

### Modified Models

```python
# legal_chatbot/models/chat.py (additions)

class ChatResponse(BaseModel):
    """Extended with has_data flag."""
    answer: str
    citations: List[Citation] = []
    suggestions: List[str] = []
    has_data: bool = True           # NEW: False when no data available
    category: Optional[str] = None  # NEW: Detected category
```

---

## RPC Functions

### Existing (unchanged)
- `match_articles(query_embedding, match_threshold, match_count, filter_status)` — pgvector semantic search

### New
```sql
-- Get category with article/document counts
CREATE OR REPLACE FUNCTION get_category_stats(cat_name TEXT)
RETURNS TABLE (
  id UUID, name TEXT, display_name TEXT,
  document_count INT, article_count INT,
  worker_status TEXT, last_worker_run_at TIMESTAMPTZ
) AS $$
BEGIN
  RETURN QUERY
  SELECT c.id, c.name, c.display_name,
         c.document_count, c.article_count,
         c.worker_status, c.last_worker_run_at
  FROM legal_categories c
  WHERE c.name = cat_name;
END;
$$ LANGUAGE plpgsql;

-- Update category counts (called after pipeline run)
CREATE OR REPLACE FUNCTION update_category_counts(cat_id UUID)
RETURNS VOID AS $$
BEGIN
  UPDATE legal_categories SET
    document_count = (SELECT COUNT(*) FROM legal_documents WHERE category_id = cat_id),
    article_count = (SELECT COUNT(*) FROM articles a
                     JOIN legal_documents d ON a.document_id = d.id
                     WHERE d.category_id = cat_id)
  WHERE id = cat_id;
END;
$$ LANGUAGE plpgsql;
```

---

## Seed Data

### Contract Templates (initial seed)

```json
[
  {
    "category": "dat_dai",
    "templates": [
      {
        "contract_type": "mua_ban_dat",
        "display_name": "Hợp đồng mua bán đất",
        "search_queries": [
          "điều kiện chuyển nhượng quyền sử dụng đất",
          "hợp đồng chuyển nhượng quyền sử dụng đất",
          "quyền nghĩa vụ bên chuyển nhượng bên nhận",
          "giá đất thanh toán chuyển nhượng",
          "thủ tục đăng ký biến động đất đai"
        ],
        "required_laws": ["Luật Đất đai 2024", "Bộ luật Dân sự 2015"],
        "min_articles": 10
      },
      {
        "contract_type": "cho_thue_dat",
        "display_name": "Hợp đồng cho thuê đất",
        "search_queries": [
          "cho thuê quyền sử dụng đất",
          "hợp đồng thuê đất điều kiện",
          "quyền nghĩa vụ bên cho thuê bên thuê đất"
        ],
        "required_laws": ["Luật Đất đai 2024", "Bộ luật Dân sự 2015"],
        "min_articles": 8
      },
      {
        "contract_type": "chuyen_nhuong_dat",
        "display_name": "Hợp đồng chuyển nhượng QSDĐ",
        "search_queries": [
          "chuyển nhượng quyền sử dụng đất",
          "điều kiện chuyển nhượng đất",
          "thủ tục chuyển nhượng đất đai"
        ],
        "required_laws": ["Luật Đất đai 2024", "Bộ luật Dân sự 2015"],
        "min_articles": 10
      }
    ]
  },
  {
    "category": "nha_o",
    "templates": [
      {
        "contract_type": "cho_thue_nha",
        "display_name": "Hợp đồng thuê nhà ở",
        "search_queries": [
          "hợp đồng thuê nhà ở",
          "quyền nghĩa vụ bên cho thuê bên thuê nhà",
          "giá thuê phương thức thanh toán nhà",
          "chấm dứt hợp đồng thuê nhà"
        ],
        "required_laws": ["Luật Nhà ở 2023", "Bộ luật Dân sự 2015"],
        "min_articles": 8
      },
      {
        "contract_type": "mua_ban_nha",
        "display_name": "Hợp đồng mua bán nhà ở",
        "search_queries": [
          "mua bán nhà ở điều kiện",
          "hợp đồng mua bán nhà",
          "quyền sở hữu nhà ở chuyển nhượng"
        ],
        "required_laws": ["Luật Nhà ở 2023", "Bộ luật Dân sự 2015"],
        "min_articles": 8
      }
    ]
  },
  {
    "category": "lao_dong",
    "templates": [
      {
        "contract_type": "hop_dong_lao_dong",
        "display_name": "Hợp đồng lao động",
        "search_queries": [
          "hợp đồng lao động nội dung hình thức",
          "quyền nghĩa vụ người lao động",
          "quyền nghĩa vụ người sử dụng lao động",
          "thời giờ làm việc nghỉ ngơi",
          "tiền lương chế độ"
        ],
        "required_laws": ["Bộ luật Lao động 2019"],
        "min_articles": 10
      },
      {
        "contract_type": "thu_viec",
        "display_name": "Hợp đồng thử việc",
        "search_queries": [
          "thử việc thời gian điều kiện",
          "tiền lương thử việc",
          "kết thúc thử việc"
        ],
        "required_laws": ["Bộ luật Lao động 2019"],
        "min_articles": 5
      }
    ]
  },
  {
    "category": "dan_su",
    "templates": [
      {
        "contract_type": "vay_tien",
        "display_name": "Hợp đồng vay tiền",
        "search_queries": [
          "hợp đồng vay tài sản",
          "lãi suất vay quy định",
          "nghĩa vụ trả nợ bên vay",
          "thời hạn vay"
        ],
        "required_laws": ["Bộ luật Dân sự 2015"],
        "min_articles": 5
      },
      {
        "contract_type": "uy_quyen",
        "display_name": "Hợp đồng ủy quyền",
        "search_queries": [
          "hợp đồng ủy quyền",
          "phạm vi ủy quyền",
          "nghĩa vụ bên ủy quyền bên được ủy quyền"
        ],
        "required_laws": ["Bộ luật Dân sự 2015"],
        "min_articles": 5
      },
      {
        "contract_type": "dich_vu",
        "display_name": "Hợp đồng dịch vụ",
        "search_queries": [
          "hợp đồng dịch vụ",
          "quyền nghĩa vụ bên cung ứng bên sử dụng dịch vụ",
          "giá dịch vụ thanh toán"
        ],
        "required_laws": ["Bộ luật Dân sự 2015"],
        "min_articles": 5
      }
    ]
  }
]
```

### Document Registry (initial seed — đất đai)

```json
[
  {
    "category": "dat_dai",
    "url": "https://thuvienphapluat.vn/van-ban/Bat-dong-san/Luat-Dat-dai-2024-31-2024-QH15-...",
    "document_number": "31/2024/QH15",
    "title": "Luật Đất đai 2024",
    "role": "primary",
    "priority": 1
  },
  {
    "category": "dat_dai",
    "url": "https://thuvienphapluat.vn/van-ban/Bat-dong-san/Nghi-dinh-101-2024-ND-CP-...",
    "document_number": "101/2024/NĐ-CP",
    "title": "NĐ hướng dẫn Luật Đất đai",
    "role": "related",
    "priority": 2
  },
  {
    "category": "dat_dai",
    "url": "https://thuvienphapluat.vn/van-ban/Dan-su/Bo-luat-Dan-su-2015-91-2015-QH13-...",
    "document_number": "91/2015/QH13",
    "title": "Bộ luật Dân sự 2015",
    "role": "base",
    "priority": 3
  }
]
```
