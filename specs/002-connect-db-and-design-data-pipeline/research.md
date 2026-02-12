# Research: Kết nối Database & Thiết kế Data Pipeline

**Date**: 2026-02-10 | **Spec**: [spec.md](./spec.md)

## Phase 0: Research Findings

### 1. Supabase + pgvector Integration

#### 1.1 supabase-py SDK

**Version**: `supabase>=2.0.0` (latest 2.27.3). Pulls in `postgrest-py`, `storage3`, `gotrue`, `httpx`.

**Client initialization**:
```python
from supabase import create_client, Client, ClientOptions

supabase: Client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"],
    options=ClientOptions(
        postgrest_client_timeout=10,
        storage_client_timeout=30,
    )
)
```

**CRUD operations** — fluent builder pattern:
- Insert: `supabase.table("articles").insert(data).execute()`
- Select: `supabase.table("articles").select("*, legal_documents(title)").execute()`
- Update: `supabase.table("articles").update({...}).eq("id", id).execute()`
- Upsert (batch): `supabase.table("articles").upsert(list_of_dicts).execute()`

**Filters**: `.eq()`, `.neq()`, `.gt()`, `.lt()`, `.in_()`, `.like()`, `.ilike()`, `.contains()` (JSONB), `.order()`, `.limit()`, `.range()`

#### 1.2 pgvector Setup

**Enable extension** (one-time):
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**Decision: HNSW index (NOT IVFFlat)**

| Feature | HNSW | IVFFlat |
|---------|------|---------|
| Self-updating | Yes | No (needs REINDEX) |
| Needs existing data | No | Yes |
| Query speed | Slightly slower | Faster after rebuild |
| **Verdict** | **Recommended** | Not recommended |

```sql
CREATE INDEX articles_embedding_idx
ON articles USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Distance operators**:
- `<=>` — Cosine distance (0 = identical, 2 = opposite). Similarity = `1 - distance`
- `<#>` — Negative inner product (faster with normalized vectors)
- `<->` — L2 Euclidean

#### 1.3 Critical Finding: Vector Search MUST Use RPC

**PostgREST does NOT support pgvector operators.** Cannot do vector search via supabase-py REST builder. Must create PostgreSQL function + call via `supabase.rpc()`.

**RPC function for semantic search**:
```sql
CREATE OR REPLACE FUNCTION match_articles(
    query_embedding VECTOR(768),
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 5,
    filter_status TEXT DEFAULT 'active'
)
RETURNS TABLE (
    id UUID, document_id UUID, article_number INT,
    title TEXT, content TEXT, chapter TEXT, similarity FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT a.id, a.document_id, a.article_number, a.title, a.content, a.chapter,
           1 - (a.embedding <=> query_embedding) AS similarity
    FROM articles a
    JOIN legal_documents d ON a.document_id = d.id
    WHERE d.status = filter_status
      AND 1 - (a.embedding <=> query_embedding) > match_threshold
    ORDER BY a.embedding <=> query_embedding
    LIMIT match_count;
END; $$;
```

**Python call**:
```python
result = supabase.rpc("match_articles", {
    "query_embedding": embedding_list,
    "match_threshold": 0.5,
    "match_count": 10,
    "filter_status": "active",
}).execute()
```

#### 1.4 Supabase Storage

```python
# Create bucket
supabase.storage.create_bucket("legal-raw-documents", options={
    "public": False,
    "allowed_mime_types": ["text/html", "application/pdf"],
    "file_size_limit": 10 * 1024 * 1024,
})

# Upload — CRITICAL: use lowercase "content-type"
supabase.storage.from_("legal-raw-documents").upload(
    path="luat/luat-dat-dai-2024.html",
    file=content_bytes,
    file_options={"content-type": "text/html; charset=utf-8", "upsert": "true"},
)
```

#### 1.5 Best Practices

- **Singleton client**: Use `@lru_cache(maxsize=1)` for client instance
- **Service role key**: Use for pipeline/admin ops (bypasses RLS); anon key for user queries
- **Error handling**: Catch `postgrest.exceptions.APIError` (codes: 23505 = unique violation, 23503 = FK violation, 22000 = wrong vector dimension)
- **Batch inserts**: Chunk 50-100 rows per upsert call, 0.5s delay between chunks
- **Connection pooling**: Supavisor handles server-side; no client-side config needed

---

### 2. Crawling thuvienphapluat.vn

#### 2.1 URL Patterns (Verified)

```
# Individual document
https://thuvienphapluat.vn/van-ban/{Category}/{Slug}-{NumericID}.aspx

# Category listing
https://thuvienphapluat.vn/van-ban-moi/{Category}?ft=1

# Search
https://thuvienphapluat.vn/page/tim-van-ban.aspx?keyword=...
```

**Known category slugs**: `Bat-dong-san`, `Thuong-mai`, `Bo-may-hanh-chinh`, `Xay-dung-Do-thi`, `Giao-duc`, `Tai-nguyen-Moi-truong` (27 total)

**Cross-categorization caveat**: Documents may appear under unexpected categories (e.g., Luật KDBĐS 2014 under `Thuong-mai` instead of `Bat-dong-san`).

#### 2.2 Verified Land Law URLs

| Document | URL slug (appended to base) |
|----------|-----------------------------|
| Luật Đất đai 2024 | `Luat-Dat-dai-2024-31-2024-QH15-523642.aspx` |
| Luật KDBĐS 2023 | `Luat-Kinh-doanh-bat-dong-san-29-2023-QH15-530116.aspx` |
| NĐ 102/2024 (hướng dẫn chung) | `Nghi-dinh-102-2024-ND-CP-huong-dan-Luat-Dat-dai-603982.aspx` |
| NĐ 101/2024 (đăng ký đất đai) | `Nghi-dinh-101-2024-ND-CP-dang-ky-cap-giay-chung-nhan-...-613131.aspx` |
| NĐ 88/2024 (bồi thường) | `Nghi-dinh-88-2024-ND-CP-boi-thuong-ho-tro-tai-dinh-cu-...-600715.aspx` |
| NĐ 71/2024 (giá đất) | `Nghi-dinh-71-2024-ND-CP-quy-dinh-gia-dat-599145.aspx` |

Base: `https://thuvienphapluat.vn/van-ban/Bat-dong-san/`

#### 2.3 Anti-Bot Measures: Cloudflare Active

**Direct HTTP requests return 403 Forbidden.** Must use:
- **Playwright with Firefox** (less fingerprinted than Chromium)
- **`playwright-stealth` plugin** to mask `navigator.webdriver`
- Realistic viewport, locale (`vi-VN`), timezone (`Asia/Ho_Chi_Minh`)
- Wait 5-10s for Cloudflare challenge resolution

**Updated rate limiting** (increased from spec's 2-3s):
```
Delay between requests:     3-5 seconds + random 0-2s jitter
Max pages per session:      20
Concurrent requests:        1 (sequential only)
Session cooldown:           5 minutes between sessions
Max retries:                3 (30s delay on failure)
```

#### 2.4 HTML Structure

Metadata extracted from compact HTML properties table (~2KB):
- `so_hieu`: Document number (e.g., `31/2024/QH15`)
- `loai_van_ban`: Type (28 types: Luật, Nghị định, Thông tư...)
- `ngay_ban_hanh`: Issue date
- `ngay_hieu_luc`: Effective date
- `tinh_trang`: Status (`còn hiệu lực` / `hết hiệu lực`)
- `noi_ban_hanh`: Issuing authority

Content: `div.content1` → main content area (needs verification post-Cloudflare bypass)

#### 2.5 Vietnamese Legal Document Hierarchy

```
Phần (Part)           — Roman numerals, optional
  Chương (Chapter)    — Roman numerals, optional
    Mục (Section)     — Arabic numerals, restarts per Chương
      Điều (Article)  — Arabic numerals, ALWAYS present, continuous
        Khoản (Clause) — Arabic numerals (1, 2, 3...), restarts per Điều
          Điểm (Point) — Lowercase letters (a, b, c...), restarts per Khoản
```

**Regex patterns**:
```python
DIEU_PATTERN   = r'Điều\s+(\d+)\.\s*(.*?)(?=\nĐiều\s+\d+\.|\Z)'
CHUONG_PATTERN = r'Chương\s+([IVXLCDM]+|\d+)\s*[:\.\n]\s*(.*)'
MUC_PATTERN    = r'Mục\s+(\d+)\s*[:\.\n]\s*(.*)'
KHOAN_PATTERN  = r'(?:^|\n)\s*(\d+)\.\s+(.*?)(?=\n\s*\d+\.|\Z)'
DIEM_PATTERN   = r'(?:^|\n)\s*([a-zđ])\)\s+(.*?)(?=\n\s*[a-zđ]\)|\Z)'
```

#### 2.6 Bootstrap Shortcut: HuggingFace Dataset

**Dataset**: `sontungkieu/ThuVienPhapLuat` — 222,000 pre-crawled documents with full HTML + metadata.

```python
from datasets import load_dataset
dataset = load_dataset("sontungkieu/ThuVienPhapLuat")
land_docs = [d for d in dataset["train"] if d["category"] == "Bat-dong-san"]
```

**Use case**: Bootstrap DB without mass crawling. May not include latest 2024-2025 documents → live crawler still needed for delta updates.

---

### 3. Embedding Model Selection

#### 3.1 Model Comparison

| Model | Dim | Max Tokens | Vietnamese Legal Retrieval | Notes |
|-------|-----|------------|---------------------------|-------|
| `bkai-foundation-models/vietnamese-bi-encoder` | 768 | 256 | Acc@10: 93.59% | **Trained on Zalo Legal Retrieval** |
| `dangvantuan/vietnamese-embedding` | 768 | 512 | Not benchmarked | Highest STS score (84.87) |
| `dangvantuan/vietnamese-embedding-LongContext` | 768 | 8096 | Not benchmarked | For very long documents |
| `paraphrase-multilingual-MiniLM-L12-v2` | 384 | 128 | Not benchmarked | Current spec — suboptimal |

#### 3.2 Decision: `bkai-foundation-models/vietnamese-bi-encoder`

**Rationale**:
1. **Only model trained on Vietnamese legal text** (Zalo 2021 Legal Text Retrieval)
2. **PhoBERT-v2 backbone** — pre-trained on 20GB Vietnamese text
3. **93.59% Acc@10** on legal retrieval benchmark
4. 256-token limit covers most legal articles (100-500 tokens typical)

**Why not `paraphrase-multilingual-MiniLM-L12-v2`** (original spec):
- 128-token max → silently truncates most legal articles
- Multilingual dilution (50+ languages)
- 384 dim → less expressive

**Fallback**: `dangvantuan/vietnamese-embedding` (512-token, highest STS)

#### 3.3 Schema Impact

```sql
-- CHANGED from spec: 384 → 768 dimensions
embedding VECTOR(768)
```

#### 3.4 Critical: NFC Normalization (NOT NFD)

Existing `normalize_vietnamese()` uses NFD. **Wrong for embeddings.**

- **NFD** decomposes: `"ồ"` → `"o"` + `"̂"` + `"̀"` (3 code points)
- **NFC** composes: `"ồ"` stays as `"ồ"` (1 code point)
- PhoBERT tokenizer trained on **NFC** → NFD produces wrong token sequences

**Solution**: New function for embedding pipeline:
```python
def normalize_for_embedding(text: str) -> str:
    """NFC normalize for PhoBERT-based models."""
    text = unicodedata.normalize("NFC", text)
    text = " ".join(text.split())
    return text.strip()
    # Do NOT lowercase. Do NOT remove diacritics.
```

#### 3.5 Chunking Strategy

- **Primary unit**: Điều (Article) — matches citation granularity + DB schema
- **Long articles** (>256 tokens): Split by Khoản, prepend `"Điều X. {title}"` header
- **Batch size**: 64 (CPU), sort by length to minimize padding waste
- **Memory**: ~1.6 GB peak (1.1 GB model + 500 MB tokenizer buffers)

---

## Resolved Unknowns

| Question | Resolution |
|----------|------------|
| Vector search via REST API? | **No.** Must use RPC function via `supabase.rpc()` |
| Which vector index? | **HNSW** (`vector_cosine_ops`). Self-updating, no rebuilds |
| Embedding model? | **`bkai-foundation-models/vietnamese-bi-encoder`** (768d) |
| Embedding dimension? | **768** (changed from spec's 384) |
| Text normalization? | **NFC** for embeddings (NOT NFD) |
| Cloudflare bypass? | **Playwright + Firefox + stealth plugin** |
| Rate limiting? | **3-5s + 0-2s jitter** (increased from 2-3s) |
| Bootstrap data? | **HuggingFace dataset** (222K docs) + live crawler |
| Storage SDK gotcha? | Lowercase `"content-type"` in `file_options` |
| Connection pooling? | Server-side (Supavisor). Client: singleton |
| Batch strategy? | 50-100 rows per upsert, 0.5s delay |
| `vecs` library? | **Not needed.** Use `supabase-py` directly |

## Spec Updates Required

| Section | Change |
|---------|--------|
| 4.1 `articles` embedding | `VECTOR(384)` → `VECTOR(768)` |
| 4.1 `articles` index | IVFFlat → HNSW |
| 5.2 Rate limiting | 2-3s → 3-5s + jitter |
| 8 Dependencies | Remove `vecs`, add `playwright-stealth`, add `datasets` |
| 8 Embedding model | → `bkai-foundation-models/vietnamese-bi-encoder` |
| 9 `EMBEDDING_DIMENSION` | 384 → 768 |

## Open Risks

| Risk | Mitigation |
|------|------------|
| Cloudflare blocks crawler | Playwright + stealth + conservative rate limiting |
| 256-token limit | Split long articles by Khoản with header context |
| Supabase free tier (1GB storage) | Compress HTML, prioritize essential documents |
| Model download (~1.1 GB) | One-time, cache locally |
| HuggingFace dataset outdated | Bootstrap only, live crawler for 2024-2025 |

## New Dependencies

```
supabase>=2.0.0
sentence-transformers>=2.2.0
playwright>=1.40.0
playwright-stealth>=1.0.0    # NEW: Cloudflare bypass
apscheduler>=3.10.0
datasets>=2.0.0               # Optional: HuggingFace bootstrap
# REMOVED: vecs (not needed)
```
