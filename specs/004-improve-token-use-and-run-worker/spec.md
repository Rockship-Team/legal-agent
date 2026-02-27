# 004 - Tiered Model Routing + Contract Form Mode

## 1. Tổng quan

### 1.1 User Problems

1. **Chi phí LLM cao**: Mọi LLM call (greeting, contract type detect, search terms, legal Q&A) đều dùng Sonnet — quá tốn cho utility tasks.
2. **Cheap models hallucinate**: Đã test Haiku, GPT-4.1-mini, Gemini flash-lite cho legal Q&A — tất cả đều suy diễn điều luật không có trong CONTEXT. Chỉ Sonnet đáng tin cậy.
3. **Contract flow chậm**: Phải điền từng field qua chat (hỏi-đáp 20+ lượt). Không thể xem tổng thể, không sửa được sau khi điền xong.
4. **Validation không cần thiết**: LLM validation mỗi field tốn 1 call × 34 fields = 34 calls lãng phí. Basic empty check là đủ.
5. **Worker chưa re-run**: Data đã cũ, cần cập nhật.

### 1.2 Giải pháp

**3 trụ cột:**

```
1. TIERED MODEL ROUTING  → Sonnet cho legal Q&A, Haiku cho utility tasks
2. CONTRACT FORM MODE    → Form UI điền tất cả fields cùng lúc + sửa sau khi điền
3. RE-RUN WORKER         → Cập nhật data mới nhất cho tất cả categories
```

### 1.3 Definition of Done (DOD)

| # | Tiêu chí | Cách kiểm tra |
|---|----------|---------------|
| 1 | Legal Q&A dùng Sonnet, utility dùng Haiku | Log model name per request |
| 2 | Chi phí giảm ≥40% so với all-Sonnet | So sánh token cost trên 10 sessions hỗn hợp |
| 3 | Legal Q&A quality không giảm | Test 10 câu pháp lý → response quality giữ nguyên |
| 4 | Form mode: điền tất cả fields cùng lúc | POST /api/contract/fields → 200 OK |
| 5 | Form mode: sửa fields sau khi điền | PATCH /api/contract/fields → regenerate PDF |
| 6 | Field validation chỉ check empty | Không có LLM call nào khi validate |
| 7 | Worker re-run thành công | `pipeline status` hiện data mới |

### 1.4 Token Audit hiện tại

**Tất cả LLM calls trong hệ thống:**

| Vị trí | Mục đích | Model hiện tại | Model mới | Lý do |
|--------|----------|---------------|-----------|-------|
| `_handle_natural_input()` | Legal Q&A response | Sonnet | **Sonnet** | Cần chính xác, không hallucinate |
| `stream_llm_response()` | Legal Q&A streaming | Sonnet | **Sonnet** | Tương tự |
| `_detect_contract_type_with_llm()` | Phân loại hợp đồng | Sonnet | **Haiku** | Task đơn giản, output 1 slug |
| `_extract_search_terms_with_llm()` | Trích search terms | Sonnet | **Haiku** | Task đơn giản, output JSON array |
| `_validate_field_input()` | Validate field | ~~Sonnet~~ | **Xóa** | Không cần — basic empty check |
| `_generate_articles_with_llm()` | Generate contract articles | Sonnet | **Sonnet** | Cần chính xác pháp lý |
| `_extract_fields_from_text()` | Extract fields từ text | Sonnet | **Haiku** | Parse text, không cần suy luận |
| `call_llm_json()` (search terms) | JSON parsing | Sonnet | **Haiku** | Utility task |
| `_is_greeting()` (nếu dùng LLM) | Detect greeting | N/A | **Haiku** | Nếu cần LLM, dùng Haiku |

**Ước tính savings (10 requests hỗn hợp: 7 utility + 3 legal Q&A):**

```
TRƯỚC: 10 × Sonnet cost = 10x
SAU:   7 × Haiku cost + 3 × Sonnet cost ≈ 7 × 0.04x + 3 × 1x = 3.28x
GIẢM:  ~67% chi phí
```

---

## 2. Tiered Model Routing

### 2.1 Kiến trúc

```
User input
    │
    ├─ Legal Q&A (vector search có context) ──→ call_llm_sonnet()     → Sonnet
    ├─ Streaming Q&A ──────────────────────→ call_llm_stream_sonnet_async() → Sonnet
    ├─ Generate contract articles ─────────→ call_llm_sonnet()         → Sonnet
    │
    ├─ Detect contract type ───────────────→ call_llm() (Haiku)        → Haiku
    ├─ Extract search terms ───────────────→ call_llm_json() (Haiku)   → Haiku
    ├─ Extract fields from text ───────────→ call_llm_json() (Haiku)   → Haiku
    └─ Category validation (pipeline) ─────→ call_llm() (Haiku)        → Haiku
```

**Routing logic**: Không dùng classifier. Routing dựa trên code path:
- Hàm nào gọi `call_llm_sonnet()` → Sonnet (hardcoded model)
- Hàm nào gọi `call_llm()` → Haiku (từ `LLM_MODEL` env var)

### 2.2 Changes to `utils/llm.py`

Thêm 2 hàm Sonnet-specific (hardcoded `claude-sonnet-4-20250514`):

```python
SONNET_MODEL = "claude-sonnet-4-20250514"

def call_llm_sonnet(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 4096,
    system: str = "",
) -> str:
    """Call Sonnet specifically — for legal Q&A where accuracy is critical."""
    # Same logic as call_llm() but uses SONNET_MODEL instead of get_model()
    ...

async def call_llm_stream_sonnet_async(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 4096,
    system: str = "",
):
    """Stream Sonnet response — for legal Q&A streaming."""
    # Same logic as call_llm_stream_async() but uses SONNET_MODEL
    ...
```

Các hàm hiện tại (`call_llm`, `call_llm_json`, `call_llm_stream_async`) giữ nguyên — dùng `get_model()` → trả về `LLM_MODEL` từ `.env` (= `claude-haiku-4-5-20251001`).

### 2.3 Changes to `.env`

```bash
# Haiku cho utility tasks (default model)
LLM_MODEL=claude-haiku-4-5-20251001

# Sonnet hardcoded trong code cho legal Q&A — không cần env var
```

### 2.4 Changes to `services/interactive_chat.py`

| Hàm | Trước | Sau |
|-----|-------|-----|
| `_handle_natural_input()` | `self._call_llm(msgs, temp=0.7, max_tokens=4096)` | `call_llm_sonnet(msgs, temp=0.3, max_tokens=4096)` |
| `stream_llm_response()` | `call_llm_stream_async(msgs, temp=0.7)` | `call_llm_stream_sonnet_async(msgs, temp=0.3)` |
| `_generate_articles_with_llm()` | `call_llm(msgs)` | `call_llm_sonnet(msgs)` |
| `_detect_contract_type_with_llm()` | `self._call_llm(msgs, temp=0.1, max_tokens=30)` | Giữ nguyên (dùng Haiku) |
| `_extract_search_terms_with_llm()` | `call_llm_json(msgs)` | Giữ nguyên (dùng Haiku) |
| `_extract_fields_from_text()` | `call_llm_json(msgs)` | Giữ nguyên (dùng Haiku) |
| `_validate_field_input()` | Basic empty check | Giữ nguyên (không LLM) |

### 2.5 Temperature

- **Sonnet (legal Q&A)**: `temperature=0.3` — cần consistent, accurate
- **Haiku (utility)**: `temperature=0.1` — cần deterministic cho classification/extraction

---

## 3. Contract Form Mode

### 3.1 User Problem

**Hiện tại (chat-only flow):**
```
Bot: Họ tên bên A?
User: Nguyễn Văn A
Bot: OK! Số CCCD?
User: 001234567890
Bot: Được! Địa chỉ?
User: 123 Lê Lợi, Q.1, HCM
... (20+ lượt hỏi-đáp, mất 5-10 phút)
```

**Problems:**
- Chậm: 20+ round-trips qua chat
- Không thấy tổng thể fields
- Không sửa được field đã điền (phải làm lại từ đầu)
- UX tệ cho mobile

**Giải pháp: Form Mode**
- Sau khi chọn loại hợp đồng → trả về danh sách fields → frontend render form
- User điền hết → submit 1 lần → tạo PDF
- Sau khi tạo → có thể sửa fields → regenerate PDF
- Vẫn giữ chat flow cũ (backward compatible)

### 3.2 Flow mới

```
User: "Tạo hợp đồng thuê nhà"
    │
    ├─ Chat flow (giữ nguyên): Bot hỏi từng field
    │
    └─ Form flow (MỚI):
         1. API trả về action="contract_created" + contract_fields trong response
         2. Frontend detect action → mở Form modal/panel
         3. User điền tất cả fields trong form
         4. Submit → POST /api/contract/submit
         5. Backend generate PDF → trả về pdf_url
         6. User xem PDF → muốn sửa → click "Sửa"
         7. Form mở lại với giá trị đã điền → sửa → Submit lại
         8. Backend regenerate PDF → trả về pdf_url mới
```

### 3.3 API Endpoints mới

#### 3.3.1 `GET /api/contract/templates`

Trả về danh sách loại hợp đồng có sẵn.

```json
// Response
{
  "templates": [
    {
      "type": "cho_thue_nha",
      "name": "Hợp đồng thuê nhà ở",
      "description": "Hợp đồng cho thuê nhà ở giữa bên cho thuê và bên thuê",
      "field_count": 22
    },
    {
      "type": "chuyen_nhuong_dat",
      "name": "Hợp đồng chuyển nhượng quyền sử dụng đất",
      "description": "...",
      "field_count": 25
    }
  ]
}
```

#### 3.3.2 `POST /api/contract/create`

Tạo contract draft mới và trả về danh sách fields.

```json
// Request
{
  "session_id": "abc-123",
  "contract_type": "cho_thue_nha"
}

// Response
{
  "session_id": "abc-123",
  "draft_id": "draft-456",
  "contract_type": "cho_thue_nha",
  "contract_name": "Hợp đồng thuê nhà ở",
  "field_groups": [
    {
      "group": "Bên cho thuê (Bên A)",
      "fields": [
        {
          "name": "ben_a_ho_ten",
          "label": "Họ và tên",
          "field_type": "text",
          "required": true,
          "description": "Họ tên đầy đủ bên cho thuê",
          "default_value": null
        },
        {
          "name": "ben_a_cccd",
          "label": "Số CCCD",
          "field_type": "text",
          "required": true,
          "description": "Số căn cước công dân 12 số"
        },
        {
          "name": "ben_a_ngay_cap",
          "label": "Ngày cấp CCCD",
          "field_type": "date",
          "required": true
        }
      ]
    },
    {
      "group": "Bên thuê (Bên B)",
      "fields": [...]
    },
    {
      "group": "Thông tin nhà cho thuê",
      "fields": [...]
    },
    {
      "group": "Điều khoản hợp đồng",
      "fields": [...]
    }
  ]
}
```

#### 3.3.3 `POST /api/contract/submit`

Submit tất cả field values → generate PDF.

```json
// Request
{
  "session_id": "abc-123",
  "draft_id": "draft-456",
  "field_values": {
    "ben_a_ho_ten": "Nguyễn Văn A",
    "ben_a_cccd": "001234567890",
    "ben_a_ngay_cap": "15/03/2020",
    "ben_b_ho_ten": "Trần Thị B",
    "dia_chi_nha": "123 Lê Lợi, Q.1, TP.HCM",
    "gia_thue": "5000000",
    "thoi_han": "12 tháng"
  }
}

// Response
{
  "session_id": "abc-123",
  "draft_id": "draft-456",
  "message": "Đã tạo hợp đồng thành công!",
  "pdf_url": "/api/files/contract_cho_thue_nha_20260227_143022.pdf",
  "field_values": { ... }  // echo back for frontend state
}
```

#### 3.3.4 `PATCH /api/contract/submit`

Sửa fields và regenerate PDF.

```json
// Request (chỉ gửi fields cần sửa)
{
  "session_id": "abc-123",
  "draft_id": "draft-456",
  "field_values": {
    "gia_thue": "6000000",
    "thoi_han": "24 tháng"
  }
}

// Response (same format as POST)
{
  "session_id": "abc-123",
  "draft_id": "draft-456",
  "message": "Đã cập nhật hợp đồng!",
  "pdf_url": "/api/files/contract_cho_thue_nha_20260227_143512.pdf",
  "field_values": { ... }  // full merged values
}
```

### 3.4 Frontend Changes

#### 3.4.1 Contract Form Component

Khi `ChatAPIResponse.action === "contract_created"` VÀ response có `contract_fields`:

```
┌─────────────────────────────────────────────┐
│  Hợp đồng thuê nhà ở                    ✕  │
├─────────────────────────────────────────────┤
│                                             │
│  ── Bên cho thuê (Bên A) ──                │
│                                             │
│  Họ và tên *          [________________]    │
│  Số CCCD *            [________________]    │
│  Ngày cấp CCCD *      [____/____/____]      │
│  Nơi cấp *            [________________]    │
│  Địa chỉ *            [________________]    │
│                                             │
│  ── Bên thuê (Bên B) ──                    │
│                                             │
│  Họ và tên *          [________________]    │
│  Số CCCD *            [________________]    │
│  ...                                        │
│                                             │
│  ── Thông tin nhà cho thuê ──               │
│                                             │
│  Địa chỉ nhà *        [________________]   │
│  Diện tích (m²) *      [________________]   │
│  ...                                        │
│                                             │
│  ── Điều khoản ──                           │
│                                             │
│  Giá thuê/tháng *      [________________]   │
│  Thời hạn thuê *       [________________]   │
│  ...                                        │
│                                             │
├─────────────────────────────────────────────┤
│              [Hủy]     [Tạo hợp đồng]      │
└─────────────────────────────────────────────┘
```

**Design:**
- Modal/slide-over panel (không replace chat)
- Fields nhóm theo `field_groups`
- Required fields có dấu `*`
- Validation client-side: empty check, date format
- Submit button disabled nếu chưa điền hết required fields

#### 3.4.2 Edit Mode

Sau khi tạo PDF xong, trong chat response hiện:
```
✅ Đã tạo hợp đồng thành công!
[📄 Tải PDF]  [✏️ Sửa thông tin]
```

Click "Sửa thông tin" → mở lại form với giá trị đã điền → sửa → Submit → regenerate PDF.

#### 3.4.3 Files Frontend mới

| File | Mô tả |
|------|--------|
| `components/Contract/ContractFormModal.tsx` | **Mới** — Form modal chứa tất cả fields |
| `components/Contract/FieldGroup.tsx` | **Mới** — Render 1 nhóm fields |
| `components/Contract/FieldInput.tsx` | **Mới** — Render 1 field input (text, date, number, textarea) |
| `hooks/useContractForm.ts` | **Mới** — State management cho form (values, validation, submit) |
| `lib/api.ts` | Thêm contract API functions |
| `components/Chat/ChatMessage.tsx` | Thêm "Sửa thông tin" button khi có contract |

### 3.5 Backend Changes

#### 3.5.1 Schemas mới (`api/schemas.py`)

```python
class ContractTemplateItem(BaseModel):
    type: str
    name: str
    description: str = ""
    field_count: int = 0

class ContractTemplatesResponse(BaseModel):
    templates: list[ContractTemplateItem]

class ContractFieldItem(BaseModel):
    name: str
    label: str
    field_type: str = "text"  # text, date, number, textarea
    required: bool = True
    description: Optional[str] = None
    default_value: Optional[str] = None

class ContractFieldGroup(BaseModel):
    group: str
    fields: list[ContractFieldItem]

class ContractCreateRequest(BaseModel):
    session_id: Optional[str] = None
    contract_type: str

class ContractCreateResponse(BaseModel):
    session_id: str
    draft_id: str
    contract_type: str
    contract_name: str
    field_groups: list[ContractFieldGroup]

class ContractSubmitRequest(BaseModel):
    session_id: str
    draft_id: str
    field_values: dict[str, str]

class ContractSubmitResponse(BaseModel):
    session_id: str
    draft_id: str
    message: str
    pdf_url: Optional[str] = None
    field_values: dict[str, str] = {}
```

#### 3.5.2 Routes mới (`api/routes/contract.py`)

```python
router = APIRouter()

@router.get("/api/contract/templates")
async def list_templates():
    """List available contract templates"""
    ...

@router.post("/api/contract/create")
async def create_contract(request: ContractCreateRequest):
    """Create draft and return field definitions"""
    # 1. Load template from DB
    # 2. Create ContractDraft in session store
    # 3. Return field_groups with field definitions
    ...

@router.post("/api/contract/submit")
async def submit_contract(request: ContractSubmitRequest):
    """Submit all fields and generate PDF"""
    # 1. Load draft from session
    # 2. Set all field_values
    # 3. Generate PDF (reuse _finalize_contract logic)
    # 4. Return pdf_url
    ...

@router.patch("/api/contract/submit")
async def update_contract(request: ContractSubmitRequest):
    """Update fields and regenerate PDF"""
    # 1. Load draft from session
    # 2. Merge new field_values
    # 3. Regenerate PDF
    # 4. Return new pdf_url
    ...
```

### 3.6 Chat Flow vẫn hoạt động

Chat flow (hỏi-đáp từng field) giữ nguyên 100%. Form mode là **bổ sung**, không thay thế.

Frontend detect cách hiển thị:
- Nếu user dùng chat → `action="contract_created"` → tiếp tục hỏi-đáp
- Nếu user click nút "Tạo hợp đồng" trên UI → call `/api/contract/create` → mở form

---

## 4. Validation

### 4.1 Approach: Không dùng LLM

Đã loại bỏ hoàn toàn LLM validation. Chỉ check basic:

```python
def _validate_field_input(self, field: DynamicField, value: str) -> Optional[str]:
    """Basic empty check only — no LLM call."""
    if not value or not value.strip():
        return f"Vui lòng nhập {field.label.lower()}."
    return None
```

**Lý do:**
- LLM validation tốn 34 calls/contract (~6800 tokens)
- User tự biết thông tin của mình đúng hay sai
- Frontend form có thể thêm client-side validation (format date, phone) nếu cần
- Tiết kiệm ~$0.02/contract

### 4.2 Client-side Validation (Frontend)

Form component tự validate trước khi submit:

| Field type | Validation |
|-----------|-----------|
| `text` | Non-empty |
| `date` | Format DD/MM/YYYY |
| `number` | Là số hợp lệ |
| `textarea` | Non-empty |

Không validate nội dung (tên, địa chỉ, CCCD...) — user tự chịu trách nhiệm.

---

## 5. Worker

### 5.1 Approach

Không cần re-crawl thủ công. Chỉ cần start worker chạy tự động dựa trên categories đã có sẵn trong Supabase.

### 5.2 Execution

```bash
# Start worker — tự động crawl theo schedule (1 tuần/lần) cho tất cả categories có trong DB
python -m legal_chatbot pipeline worker --category start

# Verify
python -m legal_chatbot pipeline worker --category status
```

Worker sẽ tự động:
- Lấy danh sách categories từ Supabase
- Crawl + index cho mỗi category theo schedule (weekly)
- Refresh contract templates nếu có data mới

---

## 6. Code Changes Summary

### 6.1 Backend (chatbot repo)

| File | Thay đổi |
|------|----------|
| `utils/llm.py` | Thêm `call_llm_sonnet()`, `call_llm_stream_sonnet_async()` (hardcoded Sonnet model) |
| `utils/config.py` | Không đổi (LLM_MODEL dùng cho Haiku) |
| `services/interactive_chat.py` | Import Sonnet functions, `_handle_natural_input()` → `call_llm_sonnet()`, `stream_llm_response()` → `call_llm_stream_sonnet_async()`, temperature 0.7→0.3 |
| `api/schemas.py` | Thêm Contract form schemas (ContractCreateRequest, ContractSubmitRequest, etc.) |
| `api/routes/contract.py` | **Mới** — 4 endpoints: templates, create, submit, update |
| `api/app.py` | Register contract router |
| `.env` | `LLM_MODEL=claude-haiku-4-5-20251001` |

### 6.2 Frontend (ui-chatbot-legal repo)

| File | Thay đổi |
|------|----------|
| `components/Contract/ContractFormModal.tsx` | **Mới** — Form modal |
| `components/Contract/FieldGroup.tsx` | **Mới** — Field group component |
| `components/Contract/FieldInput.tsx` | **Mới** — Individual field input |
| `hooks/useContractForm.ts` | **Mới** — Form state management |
| `lib/api.ts` | Thêm contract API calls |
| `components/Chat/ChatMessage.tsx` | Thêm "Sửa thông tin" button |

### 6.3 Files KHÔNG đổi

| File | Lý do |
|------|-------|
| `services/worker.py` | Worker logic giữ nguyên, chỉ re-run |
| `services/crawler.py` | Crawl logic không đổi |
| `services/pipeline.py` | Pipeline logic không đổi |
| `services/pdf_generator.py` | PDF logic không đổi — reuse cho form submit |
| `db/supabase.py` | Không cần schema mới |

---

## 7. Testing Strategy

### Tiered Routing Tests

```bash
# Legal Q&A → Sonnet
# Chat "Điều kiện cho thuê đất?" → log shows model=claude-sonnet-4-20250514
# Response không hallucinate, chỉ cite articles trong CONTEXT

# Utility → Haiku
# Detect contract type "thuê nhà" → log shows model=claude-haiku-4-5-20251001
# Extract search terms → log shows model=claude-haiku-4-5-20251001
```

### Contract Form Tests

```bash
# GET /api/contract/templates → list of templates with field counts
# POST /api/contract/create {contract_type: "cho_thue_nha"} → field_groups
# POST /api/contract/submit {field_values: {...}} → pdf_url
# PATCH /api/contract/submit {field_values: {gia_thue: "6000000"}} → new pdf_url

# Chat flow vẫn hoạt động song song
# Chat "tạo hợp đồng thuê nhà" → hỏi từng field → vẫn OK
```

### Worker Tests

```bash
# pipeline crawl -t "đất đai" --force → data refreshed
# pipeline status → updated timestamps
# pipeline categories → article counts updated
```

---

## 8. Ước tính Savings

### Chi phí per session (5 requests: 3 legal Q&A + 2 utility)

```
TRƯỚC (all Sonnet):
  3 Q&A × ~15K input tokens × $3/M  = $0.135
  2 utility × ~1K tokens × $3/M     = $0.006
  Output: 5 × ~2K tokens × $15/M    = $0.150
  TỔNG: ~$0.29/session

SAU (tiered):
  3 Q&A × ~15K input × $3/M         = $0.135  (Sonnet, giữ nguyên)
  2 utility × ~1K tokens × $0.80/M  = $0.002  (Haiku, giảm 73%)
  Output Q&A: 3 × ~2K × $15/M       = $0.090
  Output utility: 2 × ~0.1K × $4/M  = $0.001
  TỔNG: ~$0.23/session

GIẢM: ~21% per session (chủ yếu nhờ Haiku cho utility)
```

### Chi phí per contract (form mode vs chat mode)

```
TRƯỚC (chat mode, 20 fields):
  20 round-trips × greeting/confirm LLM calls = 0 (no LLM for confirms)
  0 validation LLM calls (đã loại bỏ)
  1 generate articles call (Sonnet)
  TỔNG: ~1 Sonnet call

SAU (form mode):
  0 round-trips (form submit 1 lần)
  0 validation calls
  1 generate articles call (Sonnet)
  TỔNG: ~1 Sonnet call (same cost, nhưng UX tốt hơn rất nhiều)
```

---

## 9. Lưu ý quan trọng

1. **Sonnet cho accuracy, Haiku cho speed**: Legal Q&A PHẢI dùng Sonnet — tất cả cheap models đều hallucinate legal articles.
2. **Routing = code path, không phải classifier**: Không cần ML model để phân loại request. Hàm nào thuộc legal Q&A → hardcode Sonnet.
3. **Form mode = bổ sung, không thay thế**: Chat flow (hỏi-đáp từng field) vẫn hoạt động 100%. Form là option thêm.
4. **No validation = intentional**: User tự biết thông tin của mình. Không cần LLM validate tên/địa chỉ/CCCD.
5. **Worker re-run TRƯỚC khi test**: Cần data mới nhất để test legal Q&A quality.
6. **Backward compatible**: API response format không đổi. Messages cũ render bình thường.
