# 004 - Tối ưu Token Usage cho SLM + Re-run Worker

## 1. Tổng quan

### 1.1 User Problem

1. **Token lãng phí nghiêm trọng**: System prompt ~1800 ký tự gửi mỗi request. Context không giới hạn — 20 articles × 1500 chars = 30.000 chars gửi thẳng vào LLM mà không truncate. Mỗi câu hỏi đơn giản cũng tốn ~8.000-12.000 tokens input.
2. **Không kiểm soát chi phí**: Không có token counting, không có budget. Nếu chuyển sang SLM (Small Language Model — Haiku/Sonnet) thì context window nhỏ hơn, dễ bị tràn.
3. **Nhiều LLM call redundant**: Validate 1 field tốn 1 LLM call (200 tokens). Hợp đồng 34 fields = 34 LLM calls chỉ cho validation. Search term extraction gọi LLM mỗi query.
4. **Prompt chưa tối ưu**: System prompt dài, lặp instructions, ví dụ mẫu chiếm ~40% prompt. Không phân biệt prompt cho task nhẹ vs task nặng.
5. **Worker chưa re-run**: Data đất đai đã cũ, chưa chạy lại worker để cập nhật. Contract templates cần refresh.

### 1.2 Giải pháp

**3 trụ cột tối ưu + 1 operational task:**

```
1. DATA PRE-PROCESSING  → Giảm context size trước khi gửi LLM
2. RAG STRATEGY          → Lấy đúng, lấy đủ, không lấy thừa
3. PROMPT OPTIMIZATION   → Prompt ngắn hơn, hiệu quả hơn, phân tier
4. RE-RUN WORKER         → Cập nhật data mới nhất cho tất cả categories
```

```
TRƯỚC (003): 20 articles × full text → 30K chars → LLM (no limit) → 4096 tokens output
SAU  (004): 5-10 articles × summarized → 6K chars → LLM (tiered) → 1024-2048 tokens output
```

### 1.3 Definition of Done (DOD)

| # | Tiêu chí | Cách kiểm tra |
|---|----------|---------------|
| 1 | Giảm ≥50% tokens/request so với hiện tại | So sánh token count trước/sau trên cùng 10 câu hỏi |
| 2 | Context luôn ≤ budget (chars limit per tier) | Chạy 20 queries khác nhau → không có request nào vượt limit |
| 3 | System prompt ≤ 800 chars (giảm ~55%) | Đo length prompt mới |
| 4 | Field validation không gọi LLM cho pattern rõ ràng | Validate date/phone/CCCD → 0 LLM calls, chỉ regex |
| 5 | Chat quality không giảm | Test 10 câu pháp lý → so response quality trước/sau |
| 6 | Worker re-run thành công cho tất cả categories | `pipeline status` hiện data mới + last_worker_run updated |
| 7 | Contract templates được refresh | Templates có required_fields mới từ data mới |

### 1.4 Token Audit hiện tại

**Bảng phân tích tất cả LLM calls trong hệ thống:**

| File | Mục đích | max_tokens | temp | System Prompt | Input ước tính | Ghi chú |
|------|----------|-----------|------|---------------|----------------|---------|
| `interactive_chat.py` | Chat response | 4096 | 0.7 | ~1800 chars | 6K-30K chars | **Lớn nhất** — context không giới hạn |
| `interactive_chat.py` | Stream response | 4096 | 0.7 | ~1800 chars | 6K-30K chars | Tương tự chat |
| `interactive_chat.py` | Field validation | 200 | 0.0 | ~300 chars | ~800 chars | **34 calls/contract** |
| `interactive_chat.py` | Search term extraction | 150 | 0.1 | ~200 chars | ~200 chars | Mỗi query 1 call |
| `interactive_chat.py` | Contract type detect | 30 | 0.1 | ~400 chars | ~100 chars | Nhẹ, OK |
| `interactive_chat.py` | Generate articles | 4000 | 0.3 | ~600 chars | 2K+ chars | **Nặng** |
| `interactive_chat.py` | Field extraction | 500 | 0.1 | ~400 chars | 1K+ chars | Upload flow |
| `chat.py` | Main RAG | 4096 | 0.3 | ~700 chars | 1K-10K chars | Vector search path |
| `chat.py` | Category detect | 20 | 0 | ~200 chars | ~200 chars | Nhẹ, OK |
| `pipeline.py` | Category validation | 50 | 0 | ~200 chars | ~200 chars | Pipeline only |
| `pipeline.py` | Contract discovery | 2000 | 0.1 | ~300 chars | 3K+ chars | Pipeline only |
| `pipeline.py` | Field generation | 4000 | 0.1 | ~300 chars | 3K+ chars | Pipeline only |
| `crawler.py` | Web URL search | 4000 | — | — | ~100 chars | Web search tool |

**Ước tính chi phí 1 session chat (5 câu hỏi):**
- Input: 5 × ~15K chars ≈ 75K chars ≈ 19K tokens
- Output: 5 × 4096 max ≈ 20K tokens
- System prompt: 5 × 1800 chars ≈ 2.3K tokens (lặp mỗi request)
- **Tổng: ~41K tokens/session**

---

## 2. Tối ưu hóa cấu trúc dữ liệu (Data Pre-processing)

### 2.1 Article Summary Cache

Thêm field `summary` vào bảng `articles` — tóm tắt ngắn gọn nội dung điều luật (~200 chars thay vì 500-2000 chars full text).

| Yêu cầu | Mô tả |
|----------|--------|
| Generate summary | Khi index, tạo summary 1-2 câu cho mỗi article bằng LLM (1 lần duy nhất) |
| Dùng summary cho context | Chat RAG gửi summary thay vì full text → giảm ~70% context size |
| Full text khi cần | Nếu user hỏi chi tiết hoặc trích dẫn nguyên văn → load full text cho top 3 articles |
| Batch generate | Chạy 1 lần cho articles hiện tại, sau đó tự động khi index mới |

```sql
ALTER TABLE articles ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS token_count INT;
```

**Ví dụ:**
```
TRƯỚC (full text gửi LLM):
"Điều 138. Điều kiện chuyển nhượng quyền sử dụng đất
1. Người sử dụng đất được chuyển nhượng quyền sử dụng đất khi có đủ các điều kiện sau đây:
a) Có Giấy chứng nhận, trừ trường hợp quy định tại khoản 3 Điều 168...
b) Đất không có tranh chấp...
c) Quyền sử dụng đất không bị kê biên...
d) Trong thời hạn sử dụng đất..."
→ ~800 chars

SAU (summary gửi LLM):
"Điều 138 (Luật Đất đai 2024): Điều kiện chuyển nhượng QSD đất — cần có GCN, đất không tranh chấp, không bị kê biên, trong thời hạn sử dụng."
→ ~150 chars (giảm 81%)
```

### 2.2 Context Budget System

Giới hạn cứng context size gửi LLM theo tier:

| Tier | Mục đích | Max Context (chars) | Max Output (tokens) | Khi nào dùng |
|------|----------|--------------------|--------------------|--------------|
| **light** | Greeting, đơn giản | 0 | 512 | Chào hỏi, câu hỏi không pháp lý |
| **standard** | Chat Q&A pháp lý | 8.000 | 2048 | Câu hỏi pháp lý thông thường |
| **deep** | Phân tích chi tiết | 15.000 | 4096 | User yêu cầu chi tiết, nhiều điều luật |
| **contract** | Tạo hợp đồng | 12.000 | 4000 | Generate contract articles |

```python
CONTEXT_TIERS = {
    "light":    {"max_context_chars": 0,     "max_output_tokens": 512},
    "standard": {"max_context_chars": 8000,  "max_output_tokens": 2048},
    "deep":     {"max_context_chars": 15000, "max_output_tokens": 4096},
    "contract": {"max_context_chars": 12000, "max_output_tokens": 4000},
}
```

**Truncation strategy khi vượt budget:**
1. Ưu tiên articles có similarity score cao nhất
2. Dùng summary cho articles rank thấp, full text cho top 3
3. Cắt từ cuối danh sách articles cho đến khi fit budget

### 2.3 Chunk Optimization

Hiện tại chunk max 380 chars (tuned cho PhoBERT). Cần review:

| Yêu cầu | Mô tả |
|----------|--------|
| Tăng chunk size | 380 → 512 chars — giảm số chunks, tăng context per embedding |
| Smart splitting | Split theo Khoản (clause) boundaries, không cắt giữa câu |
| Metadata enrichment | Mỗi chunk ghi rõ: document_title, article_number, chunk_index |

---

## 3. Chiến lược RAG (Retrieval-Augmented Generation)

### 3.1 Hybrid Search (thay thế keyword-only)

Hiện tại `interactive_chat.py` chỉ dùng keyword search (LLM extract → SQL ILIKE). Cần bổ sung vector search:

| Yêu cầu | Mô tả |
|----------|--------|
| Vector search primary | Dùng pgvector (đã có) làm tier 1 thay vì LLM keyword extraction |
| Keyword fallback | Giữ keyword search làm tier 2 khi vector search < 3 results |
| Loại bỏ LLM search term extraction | Tiết kiệm 1 LLM call/query (~150 tokens) — dùng embedding trực tiếp |

```
TRƯỚC: User query → LLM extract terms (150 tokens) → SQL ILIKE → articles
SAU:   User query → Embed (local model, 0 tokens) → pgvector search → articles
       Fallback: → N-gram keyword SQL ILIKE
```

**Tiết kiệm: ~150 tokens × N queries/session**

### 3.2 Smart Top-K Selection

| Yêu cầu | Mô tả |
|----------|--------|
| Dynamic top_k | Câu hỏi đơn giản → top 3, phức tạp → top 8 (dựa vào query length + keyword count) |
| Relevance cutoff | Chỉ lấy articles có similarity > 0.35 (tăng từ 0.3 → giảm noise) |
| Dedup by document | Nếu 3 chunks cùng 1 article, merge lại thành 1 entry (giảm redundancy) |

```python
def _dynamic_top_k(query: str) -> int:
    """Fewer results for simple queries, more for complex ones."""
    word_count = len(query.split())
    if word_count <= 5:
        return 3   # "Điều kiện cho thuê đất?"
    elif word_count <= 15:
        return 5   # "Thủ tục chuyển nhượng quyền sử dụng đất cần những gì?"
    else:
        return 8   # Long, multi-aspect questions
```

### 3.3 Context Assembly Strategy

```
Cho mỗi query:
1. Vector search → top_k articles (ranked by similarity)
2. Phân loại:
   - Top 3: Gửi FULL TEXT (user có thể cần trích dẫn nguyên văn)
   - Còn lại: Gửi SUMMARY only (đủ để LLM tham khảo)
3. Truncate nếu vượt budget tier
4. Attach metadata: [Điều X - Luật Y - Similarity: 0.xx]
```

**Ước tính context sau tối ưu:**
- Top 3 full: 3 × 1000 chars = 3.000 chars
- Top 5 summary: 5 × 200 chars = 1.000 chars
- Metadata: ~500 chars
- **Tổng: ~4.500 chars** (giảm từ ~15.000-30.000 chars → **giảm 70-85%**)

---

## 4. Tối ưu hóa Prompt

### 4.1 System Prompt Compression

Hiện tại SYSTEM_PROMPT = ~1800 chars với ví dụ mẫu dài. Cần rút gọn:

**TRƯỚC (~1800 chars):**
```
- Phong cách, formatting rules chi tiết
- Ví dụ cấu trúc trả lời mẫu (~40% prompt)
- Nguyên tắc 6 điểm
- Lưu ý
```

**SAU (~800 chars):**
```
Bạn là chuyên viên tư vấn pháp lý Việt Nam. Thân thiện, chuyên sâu.

FORMAT:
- [SECTION: Tên] ... [/SECTION] cho mỗi phần
- [QUOTE]nguyên văn[/QUOTE] cho trích dẫn luật
- [HL]giá trị[/HL] cho số quan trọng
- **bold**, Điều X (Luật Y), ⚠️ Lưu ý:

QUY TẮC:
- DỰA HOÀN TOÀN vào CONTEXT, không tự suy diễn
- Liệt kê TẤT CẢ điều luật liên quan
- Kết thúc bằng [SECTION: Tóm tắt & Gợi ý]
- Chưa đủ data → nói thẳng, gợi ý lĩnh vực có

{dynamic_data_section}
```

**Tiết kiệm: ~1000 chars × mỗi request ≈ 250 tokens/request**

### 4.2 Tiered Prompts

Không dùng 1 system prompt cho mọi loại request:

| Tier | System Prompt | Max chars | Khi nào |
|------|--------------|-----------|---------|
| `greeting` | Minimal (200 chars) | 200 | Chào hỏi, small talk |
| `legal_qa` | Standard (800 chars) | 800 | Câu hỏi pháp lý |
| `contract` | Contract-specific (600 chars) | 600 | Tạo hợp đồng |
| `validation` | None (inline instruction) | 0 | Field validation |

```python
def _get_tier(self, user_input: str, session: ChatSession) -> str:
    """Detect request tier for prompt/budget selection."""
    if session.mode == 'contract_creation':
        return 'contract'
    if self._is_greeting(user_input):
        return 'greeting'
    return 'legal_qa'
```

### 4.3 Hybrid Validation (Regex + LLM fallback)

Hiện tại MỌI field validation đều gọi LLM. Tối ưu: regex cho pattern rõ ràng, LLM chỉ cho trường hợp mơ hồ.

```python
def _validate_field_input(self, field, value):
    # Tier 1: Regex cho pattern rõ ràng (0 tokens)
    quick_result = self._regex_validate(field.name, value)
    if quick_result is not None:
        return quick_result  # None = valid, string = error

    # Tier 2: LLM chỉ cho trường hợp mơ hồ
    return self._llm_validate(field, value)
```

**Regex patterns (xử lý ~70% fields):**
- `*date*` → DD/MM/YYYY regex
- `*phone*` → 10-11 digits
- `*id_number*`, `*cccd*` → 9 hoặc 12 digits
- `*email*` → email regex
- `*name*` → không chỉ toàn số, ≥ 2 ký tự

**LLM chỉ cho (~30% fields):**
- Địa chỉ (cần hiểu context)
- Mục đích sử dụng đất (cần hiểu pháp lý)
- Các trường tự do khác

**Tiết kiệm: 34 fields × 70% regex = 24 LLM calls tiết kiệm ≈ 4.800 tokens/contract**

### 4.4 Response Length Control

| Loại câu hỏi | max_tokens hiện tại | max_tokens mới | Ghi chú |
|---------------|--------------------|--------------------|---------|
| Chào hỏi | 4096 | 512 | Chỉ cần 2-3 câu |
| Câu hỏi đơn giản | 4096 | 1024 | 1 section |
| Câu hỏi phức tạp | 4096 | 2048 | 2-3 sections |
| Phân tích chi tiết | 4096 | 4096 | Giữ nguyên |
| Field validation | 200 | 100 | Chỉ cần valid/error |
| Search terms | 150 | 0 | **Loại bỏ** — dùng embedding |

---

## 5. Re-run Worker

### 5.1 Yêu cầu

| Yêu cầu | Mô tả |
|----------|--------|
| Re-crawl tất cả categories | Chạy pipeline cho dat_dai, dan_su, lao_dong, nha_o |
| Force mode | Bỏ qua content hash, crawl lại toàn bộ |
| Generate summaries | Sau khi index xong, chạy batch summary generation cho articles mới |
| Refresh contract templates | Sau khi data mới → re-discover contract types + regenerate fields |
| Verify data quality | Kiểm tra article count, embedding coverage, template completeness |

### 5.2 Execution Plan

```bash
# Step 1: Re-crawl tất cả categories
python -m legal_chatbot pipeline crawl -t "đất đai" --force
python -m legal_chatbot pipeline crawl -t "dân sự" --force
python -m legal_chatbot pipeline crawl -t "lao động" --force
python -m legal_chatbot pipeline crawl -t "nhà ở" --force

# Step 2: Verify data
python -m legal_chatbot pipeline status
python -m legal_chatbot pipeline categories

# Step 3: Generate article summaries (NEW command)
python -m legal_chatbot db generate-summaries

# Step 4: Start worker for automatic updates
python -m legal_chatbot pipeline worker --category start
python -m legal_chatbot pipeline worker --category status
```

### 5.3 New CLI Command: `generate-summaries`

```bash
python -m legal_chatbot db generate-summaries          # All articles without summary
python -m legal_chatbot db generate-summaries --category dat_dai  # Specific category
python -m legal_chatbot db generate-summaries --batch-size 20     # Control batch size
```

**Implementation:** Batch load articles where `summary IS NULL` → LLM summarize (batch of 10) → UPDATE articles SET summary = '...'

---

## 6. Code Changes

### 6.1 Files thay đổi

| File | Thay đổi |
|------|----------|
| `services/interactive_chat.py` | Rút gọn SYSTEM_PROMPT, thêm `_get_tier()`, context budget, hybrid validation, dynamic top_k, loại bỏ `_extract_search_terms_with_llm()` |
| `services/chat.py` | Thêm context budget cho vector search path, dùng summary |
| `services/embedding.py` | Tăng chunk size 380 → 512 |
| `services/pipeline.py` | Thêm summary generation sau index, refresh templates |
| `db/supabase.py` | Thêm `update_article_summary()`, `get_articles_without_summary()`, `get_article_full_text()` |
| `db/migrations/004_token_optimization.sql` | ALTER articles ADD summary, token_count |
| `cli/main.py` | Thêm `generate-summaries` command |
| `utils/config.py` | Thêm CONTEXT_TIERS config |

### 6.2 Files KHÔNG thay đổi

| File | Lý do |
|------|-------|
| `services/worker.py` | Worker logic giữ nguyên, chỉ re-run |
| `services/crawler.py` | Crawl logic không đổi |
| `services/indexer.py` | Parse logic không đổi |
| `db/migrations/002_supabase.sql`, `003_worker.sql` | Giữ nguyên |

---

## 7. Data Model Changes

### 7.1 `articles` — Bổ sung summary + token tracking

```sql
-- 004_token_optimization.sql
ALTER TABLE articles ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS token_count INT;

-- Index for batch summary generation
CREATE INDEX IF NOT EXISTS idx_articles_summary_null
ON articles (document_id) WHERE summary IS NULL;
```

### 7.2 Không tạo bảng mới

Tối ưu token không cần bảng mới — chỉ bổ sung columns vào `articles`.

---

## 8. Configuration

### 8.1 Environment Variables mới

```bash
# Token Optimization (NEW)
CONTEXT_MAX_CHARS_STANDARD=8000     # Budget cho câu hỏi thông thường
CONTEXT_MAX_CHARS_DEEP=15000        # Budget cho phân tích chi tiết
SUMMARY_BATCH_SIZE=10               # Số articles summarize mỗi batch
SUMMARY_MAX_CHARS=200               # Max length summary per article
```

### 8.2 Giữ nguyên từ 003

Tất cả env vars từ 003 (WORKER_*, CHAT_MODE, DB_MODE) giữ nguyên không đổi.

---

## 9. Testing Strategy

### Unit Tests

| Test file | Test cases |
|-----------|------------|
| `test_context_budget.py` | Context ≤ budget cho mỗi tier, truncation giữ articles quan trọng nhất |
| `test_tier_detection.py` | Greeting → light, pháp lý → standard, chi tiết → deep |
| `test_hybrid_validation.py` | Regex fields → 0 LLM calls, ambiguous fields → 1 LLM call |
| `test_summary_generation.py` | Summary ≤ 200 chars, giữ thông tin quan trọng |
| `test_prompt_compression.py` | System prompt ≤ 800 chars, response quality không giảm |

### Acceptance Tests

```bash
# Token optimization
# Chat "Điều kiện cho thuê đất?" → context ≤ 8000 chars, response quality OK
# Chat "chào" → max_tokens = 512, không gửi context

# Hybrid validation
# Validate date "15/03/1990" → pass (regex, no LLM call)
# Validate address "abc" → fail (regex: too short)
# Validate "mục đích sử dụng" → LLM validate

# Summary
# db generate-summaries → articles.summary populated
# Chat dùng summary cho context → token count giảm ≥50%

# Worker re-run
# pipeline crawl -t "đất đai" --force → data refreshed
# pipeline status → updated timestamps
```

---

## 10. Ước tính Token Savings

### Per-request savings

| Optimization | Tokens saved/request | Ghi chú |
|-------------|---------------------|---------|
| System prompt compression | ~250 | 1800 → 800 chars |
| Context budget (summary-first) | ~2500-5000 | 15K → 4.5K chars |
| Loại bỏ search term extraction | ~150 | 1 LLM call eliminated |
| Response length control | ~1000-2000 | 4096 → 1024-2048 |
| **Tổng per request** | **~4000-7400** | |

### Per-session savings (5 câu hỏi)

```
TRƯỚC: ~41.000 tokens/session
SAU:   ~15.000-20.000 tokens/session
GIẢM:  ~50-63%
```

### Per-contract savings (34 fields)

```
TRƯỚC: 34 LLM validation calls × 200 tokens = 6.800 tokens
SAU:   10 LLM calls (30%) × 150 tokens = 1.500 tokens
GIẢM:  ~78%
```

---

## 11. Lưu ý quan trọng

1. **Quality trước, optimize sau**: Chạy A/B test trên 10 câu hỏi pháp lý trước/sau. Nếu quality giảm → rollback optimization cụ thể đó.
2. **Summary generation = 1 lần**: Tốn LLM calls lúc đầu, nhưng tiết kiệm lâu dài. ~500 articles × 100 tokens = 50K tokens one-time cost.
3. **Regex validation = majority**: 70% fields có pattern rõ ràng (date, phone, ID). LLM chỉ cho edge cases.
4. **Context budget là HARD LIMIT**: Không bao giờ vượt budget. Truncate articles rank thấp thay vì fail request.
5. **Worker re-run TRƯỚC optimize**: Cần data mới nhất trước khi generate summaries.
6. **Backwards compatible**: API response format không đổi. Frontend không cần update.
7. **Chunk size thay đổi = Re-embed**: Tăng 380 → 512 chars cần re-embed affected articles. Chạy trong worker re-run.
8. **Monitor token usage**: Log actual token count per request (từ Anthropic API response `usage` field) để verify savings.
