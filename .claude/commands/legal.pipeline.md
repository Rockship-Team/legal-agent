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
- Sua du lieu hien tai (gan category cho documents)
- Xem danh sach categories co san
- Kiem tra trang thai pipeline

## Workflow

### Step 1: Xac dinh action

Parse `$ARGUMENTS` de xac dinh:
- `browse [options]` — Duyet du lieu theo cau truc phan cap
- `crawl [category]` — Crawl va index van ban phap luat
- `fix-data` — Sync categories + gan category_id cho documents
- `categories` — Liet ke cac linh vuc co san
- `status` — Kiem tra trang thai pipeline gan day

Neu `$ARGUMENTS` rong, hoi nguoi dung:
```
Ban muon lam gi?
- Duyet du lieu: /legal.pipeline browse
- Crawl du lieu moi: /legal.pipeline crawl dat_dai
- Sua du lieu: /legal.pipeline fix-data
- Xem categories: /legal.pipeline categories
- Kiem tra trang thai: /legal.pipeline status
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

Se thuc hien:
1. Sync 6 categories vao bang `legal_categories`
2. Gan `category_id` cho cac documents dua tren `source_url`

#### Action: categories

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot pipeline categories
```

Hien thi bang danh sach categories voi mo ta.

#### Action: crawl

Yeu cau `--category`. Parse tu `$ARGUMENTS`, vi du:
- `/legal.pipeline crawl dat_dai` -> category=dat_dai
- `/legal.pipeline crawl nha_o --limit 5` -> category=nha_o, limit=5

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot pipeline crawl --category [CATEGORY] --limit [LIMIT]
```

Mac dinh limit=20 neu khong chi dinh.

Bao cao ket qua:
```
Pipeline hoan thanh!

Category: [ten]
Documents: N moi / M tim thay
Articles: N da index
Embeddings: N da tao

Ban co the:
- Duyet du lieu: /legal.pipeline browse -c [category]
- Chat de test: /legal.research [chu de]
- Kiem tra DB: /legal.db status
```

#### Action: status

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot pipeline status
```

### Step 3: Xu ly loi

Neu crawl that bai:
1. Kiem tra ket noi internet
2. Kiem tra Supabase connection: `/legal.db status`
3. Thu giam limit: `/legal.pipeline crawl dat_dai --limit 3`
4. Kiem tra `playwright install firefox` da chay chua

## Available Categories

| Category | Mo ta | URLs |
|----------|-------|------|
| `dat_dai` | Luat Dat dai, ND huong dan | 3 |
| `nha_o` | Luat Nha o, ND huong dan | 0 |
| `lao_dong` | Bo luat Lao dong, ND huong dan | 0 |
| `dan_su` | Bo luat Dan su, hop dong, tai san | 0 |
| `doanh_nghiep` | Luat Doanh nghiep, Dau tu | 0 |
| `thuong_mai` | Luat Thuong mai | 0 |

## Error Handling

- Cloudflare block: Doi 5 phut va thu lai. Dam bao `playwright-stealth` da cai dat
- Embedding model: Lan dau chay se download ~1.1GB. Can internet
- Out of memory: Giam batch size hoac dong cac ung dung khac
