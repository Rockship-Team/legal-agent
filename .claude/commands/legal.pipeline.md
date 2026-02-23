---
description: Run data pipeline to crawl and index legal documents by category
---

## User Input

```text
$ARGUMENTS
```

## Purpose

Chay data pipeline de crawl, parse, va index cac van ban phap luat tu thuvienphapluat.vn. Ho tro:
- Duyet du lieu theo cau truc phan cap: Linh vuc -> Van ban -> Chuong -> Dieu
- Crawl van ban theo linh vuc (dat dai, nha o, lao dong, ...)
- Incremental crawl (chi update van ban thay doi)
- Sua du lieu hien tai (gan category cho documents)
- Xem danh sach categories co san
- Kiem tra trang thai pipeline + worker
- Background worker: start, stop, status, schedule

## Workflow

### Step 1: Xac dinh action

Parse `$ARGUMENTS` de xac dinh:
- `browse [options]` — Duyet du lieu theo cau truc phan cap
- `crawl [category]` — Crawl va index van ban phap luat (incremental)
- `crawl [category] --force` — Force re-crawl (bo qua content hash)
- `fix-data` — Sync categories + gan category_id cho documents
- `categories` — Liet ke cac linh vuc co san
- `status` — Kiem tra trang thai pipeline + worker + category stats
- `worker start|stop|status|schedule` — Background worker management

Neu `$ARGUMENTS` rong, hoi nguoi dung:
```
Ban muon lam gi?
- Duyet du lieu: /legal.pipeline browse
- Crawl du lieu moi: /legal.pipeline crawl dat_dai
- Force re-crawl: /legal.pipeline crawl dat_dai --force
- Sua du lieu: /legal.pipeline fix-data
- Xem categories: /legal.pipeline categories
- Kiem tra trang thai: /legal.pipeline status
- Worker: /legal.pipeline worker start
```

### Step 2: Thuc hien

#### Action: browse

Duyet du lieu theo 3 cap do:

**Cap 1 - Tat ca linh vuc:**
```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot pipeline browse
```

**Cap 2 - Van ban trong 1 linh vuc:**
```bash
python -m legal_chatbot pipeline browse --category dat_dai
```

**Cap 3 - Dieu luat trong 1 van ban:**
```bash
python -m legal_chatbot pipeline browse --category dat_dai --doc "31/2024/QH15"
```

#### Action: fix-data

Chay khi data hien tai chua co category:
```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot pipeline fix-data
```

#### Action: categories

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot pipeline categories
```

#### Action: crawl

Yeu cau `--category`. Parse tu `$ARGUMENTS`:
- `/legal.pipeline crawl dat_dai` -> category=dat_dai
- `/legal.pipeline crawl dat_dai --force` -> force re-crawl
- `/legal.pipeline crawl nha_o --limit 5` -> category=nha_o, limit=5

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot pipeline crawl --category [CATEGORY] --limit [LIMIT]
```

**Incremental**: Mac dinh chi crawl van ban thay doi (content hash). Dung `--force` de re-crawl tat ca.

Bao cao ket qua:
```
Pipeline hoan thanh!

Category: [ten]
Documents: N moi / M tim thay / K bo qua (unchanged)
Articles: N da index
Duration: Xs

Ban co the:
- Duyet du lieu: /legal.pipeline browse -c [category]
- Chat de test: /legal.research [chu de]
- Kiem tra DB: /legal.db status
```

#### Action: status

Hien thi thong tin tong hop: DB stats + category stats + worker schedule:
```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot pipeline status
```

#### Action: worker

Background worker management:

```bash
# Start worker (chay lien tuc, Ctrl+C de dung)
python -m legal_chatbot pipeline worker --category start

# Stop worker
python -m legal_chatbot pipeline worker --category stop

# Xem trang thai worker
python -m legal_chatbot pipeline worker --category status

# Xem lich crawl
python -m legal_chatbot pipeline worker --category schedule
```

**Luu y**: Worker KHONG chay mac dinh, phai explicit start. Lịch crawl weekly.

#### Seed commands (1 lan)

```bash
# Seed contract templates
python -m legal_chatbot seed-templates

# Seed document registry
python -m legal_chatbot seed-registry
```

### Step 3: Xu ly loi

Neu crawl that bai:
1. Kiem tra ket noi internet
2. Kiem tra Supabase connection: `/legal.db status`
3. Thu giam limit: `/legal.pipeline crawl dat_dai --limit 3`
4. Kiem tra `playwright install firefox` da chay chua
5. Kiem tra document registry: co URLs chua? (`seed-registry`)

## Available Categories

| Category | Mo ta | Status |
|----------|-------|--------|
| `dat_dai` | Luat Dat dai, ND huong dan | Da crawl |
| `nha_o` | Luat Nha o, ND huong dan | Da crawl |
| `lao_dong` | Bo luat Lao dong, ND huong dan | Da crawl |
| `dan_su` | Bo luat Dan su, hop dong, tai san | Da crawl |
| `doanh_nghiep` | Luat Doanh nghiep, Dau tu | Chua crawl |
| `thuong_mai` | Luat Thuong mai | Chua crawl |

## Error Handling

- Cloudflare block: Doi 5 phut va thu lai. Dam bao `playwright-stealth` da cai dat
- Embedding model: Lan dau chay se download ~1.1GB. Can internet
- Out of memory: Giam batch size hoac dong cac ung dung khac
- Worker failed: Kiem tra logs, retry tu dong 3 lan voi exponential backoff
