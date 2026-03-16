# Feature Specification: Contract Suggestion Examples & Type Fix

**Feature Branch**: `005-contract-suggestion-data`
**Created**: 2026-03-12
**Status**: Draft
**Input**: "When chatting to create a contract, each field question needs suggestion examples. BE has no sample data — use LLM to generate sample data per template. Also fix bug where system creates wrong contract type (e.g., user asks for car rental contract but gets money lending contract)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Correct Contract Type Resolution (Priority: P1)

When a user requests a specific contract type (e.g., "tạo hợp đồng cho thuê xe tự lái"), the system MUST correctly identify and select the matching template. Currently the system sometimes maps to the wrong type (e.g., car rental request produces a money lending contract).

**Why this priority**: This is the most critical bug — if the system picks the wrong contract type, every field, clause, and legal reference is wrong. The entire user experience breaks.

**Independent Test**: Send contract creation requests for each available type (car rental, house rental, land purchase, money lending) and verify 100% correct mapping.

**Acceptance Scenarios**:

1. **Given** user sends "tôi muốn tạo hợp đồng cho thuê xe tự lái", **When** the system classifies the contract type, **Then** it selects the car rental template (not money lending or any other type)
2. **Given** user sends "tạo hợp đồng thuê nhà", **When** the system classifies, **Then** it selects the house rental template
3. **Given** user sends an ambiguous request like "tạo hợp đồng", **When** the system cannot determine the type, **Then** it asks the user which type they want and displays all available types
4. **Given** user requests a contract type not in the DB, **When** no matching template is found, **Then** the system informs the user clearly and suggests the closest available types

---

### User Story 2 - Field Suggestion Examples During Contract Creation (Priority: P1)

When the system asks for each field during contract creation, every question MUST include suggestion examples so the user knows what to enter and in what format.

**Why this priority**: Same level as P1 — this is the user's primary request to improve the contract filling experience.

**Independent Test**: Start any contract creation flow and verify every field question includes a relevant suggestion example.

**Acceptance Scenarios**:

1. **Given** the system asks for "Tên bên A" (Party A name), **When** the question is displayed, **Then** it includes a suggestion like "Ví dụ: Nguyễn Văn A"
2. **Given** the system asks for "Số CCCD" (ID number), **When** the question is displayed, **Then** it includes a format-correct suggestion like "Ví dụ: 001234567890"
3. **Given** the system asks for "Địa chỉ" (Address), **When** the question is displayed, **Then** it includes a full address example like "Ví dụ: 123 Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP.HCM"
4. **Given** different contract types (car rental vs house rental), **When** asking for "Mô tả tài sản" (Asset description), **Then** the suggestion must match the contract type (car: "Toyota Vios 2024, BKS: 51A-12345" vs house: "Căn hộ 2PN, tầng 10, chung cư ABC")

---

### User Story 3 - Seed Suggestion Data via CLI Command (Priority: P2)

A CLI command (similar to `pipeline crawl`) allows seeding/generating suggestion example data for all contract templates. The command uses LLM to generate realistic Vietnamese sample data per template and persists it to the database.

**Why this priority**: This is the backend mechanism that powers User Story 2. It provides the data pipeline to populate suggestions without manual data entry.

**Independent Test**: Run the seed command, then start a contract creation flow and verify suggestions appear from the seeded data.

**Acceptance Scenarios**:

1. **Given** a contract template in the DB with no sample data, **When** running `python -m legal_chatbot seed-suggestions`, **Then** the LLM generates 2-3 example sets per field and saves them to the DB
2. **Given** a specific template type, **When** running `python -m legal_chatbot seed-suggestions --type cho_thue_xe`, **Then** only that template's sample data is generated
3. **Given** sample data already exists for a template, **When** running the seed command with `--force`, **Then** existing data is regenerated; without `--force`, it skips already-seeded templates
4. **Given** a template has sample data in the DB, **When** a user creates a contract of that type, **Then** suggestions are loaded from DB (no real-time LLM call needed)
5. **Given** running `python -m legal_chatbot seed-suggestions --status`, **Then** the system shows which templates have sample data and which are missing

---

### Edge Cases

- User types contract type without diacritics ("hop dong thue xe" instead of "hợp đồng thuê xe") — system must still resolve correctly
- User uses synonyms ("mướn xe" instead of "thuê xe") — system must map correctly
- New template with no sample data yet — system must fallback to showing field label without crashing
- Multiple templates with similar names (e.g., "cho thuê nhà" vs "cho thuê nhà xưởng") — system must disambiguate based on full user input context
- Seed command runs when DB is empty (no templates) — should warn gracefully, not error

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accurately identify the contract type from natural language user input, including synonyms, abbreviations, and text without diacritics
- **FR-002**: When multiple similar contract types exist, the system MUST prioritize the most accurate match based on full input context (not just substring matching)
- **FR-003**: When the contract type cannot be determined, the system MUST ask the user to choose from a list of available types
- **FR-004**: Every field question during contract creation MUST include at least 1 suggestion example relevant to the contract type
- **FR-005**: Suggestion examples MUST be context-aware — matched to the specific contract type (e.g., "asset description" in a car rental contract suggests a car, not a house)
- **FR-006**: System MUST provide a CLI command to seed/generate sample data for contract templates using LLM
- **FR-007**: The seed command MUST support: all templates (default), single template (`--type`), force regeneration (`--force`), and status check (`--status`)
- **FR-008**: Sample data MUST be persisted to the database for reuse — no LLM call needed at suggestion display time
- **FR-009**: System MUST function normally when a template has no sample data (graceful fallback to field label only)

### Key Entities

- **ContractTemplate (extended)**: Existing contract template entity, extended with `sample_data` containing field-level examples specific to the contract type
- **SampleDataSet**: A set of example data for one template, containing 2-3 variation sets per field (e.g., different names, addresses, asset descriptions)
- **FieldSuggestion**: A suggestion for a specific field, including: example value, format hint, and optional validation note

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of contract creation requests with clear type intent (car rental, house rental, land purchase, money lending) are mapped to the correct template
- **SC-002**: 100% of field questions include relevant suggestion examples (when template has sample data)
- **SC-003**: Users complete contract field entry faster with fewer corrections/re-entries due to clear suggestions
- **SC-004**: The seed command successfully generates sample data for all existing templates without manual intervention

### Previous work

- **spec 001-planning (US4)**: Contract generation CLI — template loader, PDF generator, contract template JSON files
- **spec 003-change-data-pipeline**: DB-First architecture, contract templates auto-discovered from crawled content, `contract_templates` table schema
- **chatbot-bxd**: Implement template loader and validator
- **chatbot-g5f**: Create contract template JSON files
- **chatbot-dwi**: Integrate document generation with chat context

## Assumptions

- Contract templates already exist in Supabase `contract_templates` table (established in spec 003)
- LLM (DeepSeek or Anthropic) can generate realistic Vietnamese contract sample data
- Sample data only needs to be generated once per template and stored in DB; no frequent regeneration needed
- Sample data is illustrative (fake/example data) — not real customer data
- The seed command follows the same pattern as existing `pipeline crawl` command (Typer CLI, rich output)
