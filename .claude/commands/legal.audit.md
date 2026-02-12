---
description: View and verify audit trails for research and contract generation
---

## User Input

```text
$ARGUMENTS
```

## Purpose

Xem va kiem tra audit trail cho cac lan research va tao hop dong. Ho tro:
- Liet ke lich su research/contract gan day
- Xem chi tiet mot audit entry
- Verify xem luat da dung con hieu luc khong

## Workflow

### Step 1: Xac dinh action

Parse `$ARGUMENTS`:
- `list` (mac dinh) — Liet ke cac audit gan day
- `show [audit-id]` — Xem chi tiet mot audit
- `verify [audit-id]` — Kiem tra luat da dung con hieu luc khong

Neu `$ARGUMENTS` rong, chay `list`.

### Step 2: Thuc hien

#### Action: list

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot audit list --limit [LIMIT] --type [TYPE]
```

Options:
- `--limit N` (mac dinh 20)
- `--type research|contract|all` (mac dinh all)

Vi du: `/legal.audit list --limit 5 --type research`

Hien thi bang:
```
Recent Audits:
ID         Type       Summary                    Date
a1b2c3...  research   "Dieu kien mua dat?"       2026-02-10 14:30
d4e5f6...  contract   sale_land                  2026-02-10 13:15
```

#### Action: show

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot audit show [AUDIT_ID]
```

Hien thi chi tiet:
- Type (research/contract)
- Query hoac contract type
- Sources su dung
- Law versions
- Thoi gian tao

#### Action: verify

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot audit verify [AUDIT_ID]
```

Kiem tra tung law version da su dung:
```
Audit Verification:
- Audit: a1b2c3... (research)
- Laws checked: 2
- Status: All law versions current | Some laws outdated
- Verified: 2026-02-10 15:00
```

Neu co luat het hieu luc:
```
Outdated laws:
- 31/2024/QH15: active -> repealed
```

### Step 3: Bao cao

Sau khi hien thi, goi y:
```
Ban co the:
- Xem chi tiet: /legal.audit show [id]
- Verify: /legal.audit verify [id]
- Research lai: /legal.research [topic]
```

## Error Handling

- Neu khong tim thay audit: "Khong tim thay audit voi ID nay"
- Neu chua co du lieu: "Chua co audit nao. Thu chat hoac tao hop dong truoc"
- Neu DB khong ket noi: Huong dan chay `/legal.db status`
