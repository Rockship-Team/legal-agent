# Research: Contract Suggestion Examples & Type Fix

**Date**: 2026-03-12 | **Feature**: 005-contract-suggestion-data

## Prior Work

- **spec 001 (US4)**: Original contract generation via CLI — template loader, PDF generator
- **spec 003**: DB-First architecture, `contract_templates` table with `required_fields` JSONB
- **chatbot-bxd / chatbot-g5f / chatbot-dwi**: Template loader, JSON files, chat integration

## Research 1: Contract Type Resolution Bug

### Root Cause

The bug is in `_resolve_contract_type()` at `interactive_chat.py:306`:

```python
if display_normalized in input_normalized or input_normalized in display_normalized:
    return t["type"]  # Returns FIRST match — no specificity check
```

**Problems identified:**
1. **No word-boundary checking** — "cho" in "cho thuê" partially overlaps with "cho vay"
2. **Returns on first match** — doesn't rank by specificity; DB insertion order determines result
3. **Bidirectional substring too loose** — both `A in B` and `B in A` can match unrelated templates
4. **LLM fallback never reached** — substring match fires first, so the accurate LLM classification is bypassed

### Decision: Replace substring matching with scored matching + LLM verification

**Rationale:** Substring matching is fundamentally unreliable for Vietnamese legal terms where words like "cho", "thuê", "bán" overlap across contract types. A scored approach (word overlap count + longest common subsequence) with LLM verification for low-confidence matches provides accuracy without LLM cost for obvious matches.

**Alternatives considered:**
- Pure LLM classification for every request — rejected: too slow (adds ~1-2s per request)
- Fuzzy string matching (edit distance) — rejected: doesn't capture semantic meaning of Vietnamese compound words
- Embedding similarity — rejected: overkill, requires loading embedding model for a simple classification task

### Fix Approach

1. Score each template by word overlap ratio (intersection of words in input vs display_name)
2. Return best match only if score > 0.6 (high confidence)
3. If best score ≤ 0.6 or top-2 scores are close (within 0.1), use LLM to disambiguate
4. If LLM returns None, ask user to choose from available types

## Research 2: Field Suggestion Mechanism

### Current State

- `DynamicField` model already has `description` field — loaded from DB but **never shown in chat mode**
- Chat questions use only `field.label` via `_random_response('field_ask', label=...)`
- API form endpoints already return `description` to frontend
- `required_fields` JSONB in DB stores per-field: `name`, `label`, `field_type`, `required`, `description`, `default_value`

### Decision: Add `sample_data` JSONB column to `contract_templates` table

**Rationale:** Store sample data alongside the template definition. Each template gets a `sample_data` field containing 2-3 example sets per field. This keeps the data model simple (no new tables) and allows the seed command to populate data once.

**Alternatives considered:**
- Separate `template_sample_data` table — rejected: adds join complexity for a simple 1:1 relationship
- Store examples in `DynamicField.description` — rejected: description is for explanatory text, not structured examples
- Generate examples on-the-fly with LLM — rejected: adds latency to every field question

### Sample Data Structure

```json
{
  "sample_data": {
    "ben_a_ten": {
      "examples": ["Nguyễn Văn A", "Công ty TNHH ABC"],
      "format_hint": "Họ và tên đầy đủ hoặc tên doanh nghiệp"
    },
    "ben_a_cccd": {
      "examples": ["001234567890", "079123456789"],
      "format_hint": "12 chữ số"
    },
    "mo_ta_tai_san": {
      "examples": ["Toyota Vios 2024, BKS: 51A-12345, màu trắng"],
      "format_hint": "Loại xe, năm sản xuất, biển số, màu sắc"
    }
  }
}
```

## Research 3: Seed Command Design

### Decision: Add `seed-suggestions` CLI command following `pipeline crawl` pattern

**Rationale:** Consistent with existing CLI commands. Uses Typer + Rich for output. LLM generates context-aware examples per template.

**Flow:**
1. Load all active templates from DB
2. For each template (or `--type` filtered):
   - Skip if sample_data exists (unless `--force`)
   - Build LLM prompt with template fields + contract type context
   - Parse LLM JSON response into `sample_data` structure
   - Update `contract_templates.sample_data` in DB
3. Show rich summary table

**Alternatives considered:**
- Web crawl for real contract examples — rejected: privacy concerns, unreliable data quality
- Manual seed data files (JSON) — rejected: doesn't scale, requires maintenance per template
