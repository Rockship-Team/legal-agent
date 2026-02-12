# Branch: 002-connect-db-and-design-data-pipeline

## Muc tieu

Chuyen tu SQLite + ChromaDB (local) sang **Supabase PostgreSQL + pgvector** (cloud) va xay dung **data pipeline** tu dong crawl, parse, index luat phap Viet Nam.

---

## Nhung gi da lam

### 1. Supabase Integration

| File | Mo ta |
|------|-------|
| `legal_chatbot/db/base.py` | Abstract DB interface (strategy pattern) — cho phep switch giua SQLite va Supabase |
| `legal_chatbot/db/supabase.py` | Supabase client: CRUD documents, articles, vector search (pgvector), audit ops |
| `legal_chatbot/db/sqlite_client.py` | SQLite client implement cung interface (offline fallback) |
| `legal_chatbot/db/migrations/002_supabase.sql` | Full schema: 7 tables, RLS policies, RPC functions, HNSW index |

**Dual mode**: `DB_MODE=supabase` (production) hoac `DB_MODE=sqlite` (local dev).

### 2. Data Pipeline

| File | Mo ta |
|------|-------|
| `legal_chatbot/services/pipeline.py` | Pipeline orchestrator: Discovery → Crawl → Index → Validate |
| `legal_chatbot/services/embedding.py` | Embedding service: `vietnamese-bi-encoder` (768d), batch embed + store |
| `legal_chatbot/services/crawler.py` | Mo rong: Playwright + stealth (Firefox) de bypass Cloudflare |
| `legal_chatbot/services/indexer.py` | Mo rong: parse HTML articles, dedup, embed vao Supabase |
| `legal_chatbot/models/pipeline.py` | Models: CrawlResult, PipelineRun, CategoryConfig, PipelineStatus |

**Pipeline flow**: Crawl HTML tu thuvienphapluat.vn → Parse Dieu luat (regex) → Generate embeddings → Upsert vao Supabase pgvector.

### 3. Category System (6-layer validation)

| Layer | Logic |
|-------|-------|
| 1. Normalize | Bo dau, lowercase, tach tu (`normalize_category_name`) |
| 2. Exact match | Tim trong cache/DB |
| 3. Fuzzy match | Edit distance ≤ 2 (xu ly typo: "vaytien" → "vay_tien") |
| 4. Subject match | Strip transaction verbs, so domain ("thue_xe" = "mua_xe") |
| 5. Keyword check | Kiem tra co chua tu khoa phap ly hop le |
| 6. LLM fallback | Hoi Groq LLM neu khong match duoc |

**Dac biet**: `category_from_document_title()` — tu dong xac dinh category tu ten van ban luat, KHONG phai tu loai hop dong cua user. Vi du:
- "Bo luat Dan su 2015" → `dan_su`
- "Luat Duong bo 2024" → `duong_bo`

### 4. Audit Trail

| File | Mo ta |
|------|-------|
| `legal_chatbot/services/audit.py` | Audit service: save/query research & contract audits |
| `legal_chatbot/models/audit.py` | Models: ResearchAudit, ContractAudit, ArticleSource, LawVersion |

Moi research/contract deu luu: query, sources (dieu luat nao), law_versions (phien ban luat), response. Cho phep verify sau: luat con hieu luc khong.

### 5. CLI Commands moi

| Command | Chuc nang |
|---------|-----------|
| `sync-articles <file.json>` | Upsert articles + embeddings tu JSON vao Supabase |
| `save-contract <file.json>` | Luu contract JSON → documents + articles + audit |
| `search <query>` | Vector search articles (pgvector) khong qua LLM |
| `pipeline crawl/browse/categories/fix-data` | Quan ly pipeline crawl |
| `db migrate/status` | Quan ly database |
| `audit list/show/verify` | Xem va verify audit trail |

### 6. Slash Commands moi

| Command | File |
|---------|------|
| `/legal.pipeline` | `.claude/commands/legal.pipeline.md` |
| `/legal.db` | `.claude/commands/legal.db.md` |
| `/legal.audit` | `.claude/commands/legal.audit.md` |
| `/legal.create-contract` | Cap nhat: research DB + web + sync + save audit |
| `/legal.help` | Cap nhat: them command moi |

### 7. Cac file modified khac

| File | Thay doi |
|------|----------|
| `services/chat.py` | Query Supabase pgvector thay vi ChromaDB |
| `services/pdf_generator.py` | Universal PDF (ReportLab), ho tro Paragraph wrapping |
| `services/generator.py` | Save contract audit khi generate |
| `utils/config.py` | Them Supabase settings, embedding config |
| `utils/vietnamese.py` | Them `edit_distance()`, `normalize_category_name()`, `remove_diacritics()` |
| `models/document.py` | Mo rong fields cho Supabase schema |

---

## Database Schema

```
legal_categories (1) ──→ (N) legal_documents (1) ──→ (N) articles
                                                           ↑ embedding VECTOR(768)
research_audits ← luu ket qua research
contract_audits ← luu ket qua contract generation
pipeline_runs   ← log pipeline execution
```

**Vector search**: `match_articles` RPC function, cosine similarity, threshold=0.3, HNSW index.

---

## Tech Stack bo sung

| Component | Technology |
|-----------|-----------|
| Cloud DB | Supabase PostgreSQL + pgvector |
| Embeddings | `bkai-foundation-models/vietnamese-bi-encoder` (768d) |
| Crawl | Playwright + stealth (Firefox) |
| PDF | ReportLab (universal generator) |

---

## Env Variables moi

```bash
DB_MODE=supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...          # anon key (read)
SUPABASE_SERVICE_KEY=eyJ...  # service role key (write, bypass RLS)
LLM_MODEL=llama-3.3-70b-versatile
EMBEDDING_MODEL=bkai-foundation-models/vietnamese-bi-encoder
```

---

## Quickstart

```bash
# 1. Setup
pip install supabase sentence-transformers playwright-stealth
playwright install firefox

# 2. Migrate (chay SQL trong Supabase SQL Editor)
python -m legal_chatbot db migrate

# 3. Crawl
python -m legal_chatbot pipeline crawl --category dat_dai --limit 3

# 4. Test search
python -m legal_chatbot search "dieu kien chuyen nhuong dat"

# 5. Create contract (slash command)
# /legal.create-contract thue nha
```

Chi tiet setup: [quickstart.md](./quickstart.md)
