---
description: Full module analysis with dependency graphs, code analysis, and detailed JSON cache generation
---

## User Input

```text
$ARGUMENTS
```

Optional flags:
- `--module [NAME]`: Analyze specific module only
- `--force`: Re-analyze even if cache exists

## Purpose

Perform deep code analysis to discover logical modules, extract key functions, data models, and build dependency graphs. This command requires `/specledger.audit` to run first.

**Prerequisite**: Run `/specledger.audit --format json` first to generate `scripts/audit-quick.json`.

## When to Use

- After `/specledger.audit` identifies the tech stack
- Before `/specledger.adopt --from-audit` to create specs
- When you need detailed module understanding
- Building comprehensive codebase documentation

## Execution Flow

### Phase 1: Load Quick Audit Results (2 minutes)

1. **Read Quick Audit Output**
   ```bash
   cat scripts/audit-quick.json
   ```

   If file missing: ERROR "Run /specledger.audit --format json first"

2. **Extract Context**
   - Project name and type
   - Primary language and framework
   - Key directories for analysis

### Phase 2: Module Discovery (15-30 minutes per module)

Apply clustering strategies from `.specify/templates/partials/module-clustering.md`:

1. **If Clear Structure Exists** (e.g., `src/modules/`, `packages/`):
   - Each top-level directory = one module
   - Use directory name as module ID

2. **If Unstructured** (flat files):
   - Apply filename prefix clustering
   - Apply import/dependency analysis
   - Apply route/URL clustering
   - Apply database table clustering

3. **For Each Module, Extract:**

   **Go Projects:**
   ```bash
   grep -r "^package " [MODULE_PATH] | cut -d: -f2 | sort -u
   grep -r "^func [A-Z]" [MODULE_PATH]
   grep -r "^type [A-Z]" [MODULE_PATH]
   grep -A 5 "^type .* struct" [MODULE_PATH]
   ```

   **TypeScript Projects:**
   ```bash
   grep -r "^export " [MODULE_PATH] | head -30
   grep -r "export.*function\|export.*Component" [MODULE_PATH]
   find [MODULE_PATH] -path "*/api/*" -name "*.ts"
   grep -r "^export type\|^export interface" [MODULE_PATH]
   ```

   **Python Projects:**
   ```bash
   grep -r "^class " [MODULE_PATH]
   grep -r "@app.get\|@app.post\|path(" [MODULE_PATH]
   grep -r "@dataclass\|BaseModel" [MODULE_PATH]
   ```

### Phase 3: Dependency Graph Building (10 minutes)

1. **Extract Imports**
   ```bash
   # Go
   grep -r "^import " [MODULE_PATH] | grep -o '".*"' | sort -u

   # TypeScript
   grep -r "^import .* from" [MODULE_PATH] | grep -o "from ['\"].*['\"]" | sort -u

   # Python
   grep -r "^import \|^from " [MODULE_PATH] | sort -u
   ```

2. **Identify Integration Points**
   - Database access patterns
   - External API calls
   - Message queues, event buses
   - File system operations

3. **Detect Cross-Cutting Concerns**
   - Authentication/Authorization
   - Logging, Monitoring
   - Error handling patterns
   - Configuration management

### Phase 4: Generate JSON Cache (5 minutes)

Create `scripts/audit-cache.json`:

```json
{
  "metadata": {
    "project_name": "...",
    "project_type": "monorepo|single-package|microservices",
    "language": "typescript|go|python|...",
    "framework": "nextjs|express|gin|fastapi|...",
    "analyzed_at": "ISO timestamp",
    "total_loc": 0,
    "file_count": 0
  },
  "global_context": {
    "architecture_style": "...",
    "api_pattern": "REST|GraphQL|gRPC",
    "auth_pattern": "...",
    "database": "...",
    "common_patterns": []
  },
  "modules": [
    {
      "id": "module-id",
      "name": "Human Readable Name",
      "description": "What this module does",
      "type": "core-domain|infrastructure|api|integration|ui|utility",
      "paths": ["path/to/files"],
      "entry_point": "main file",
      "loc": 0,
      "key_functions": [],
      "data_models": [],
      "api_contracts": [],
      "dependencies": []
    }
  ]
}
```

## Output

1. **Console**: Summary of discovered modules with key statistics
2. **File**: `scripts/audit-cache.json` with full analysis data

```markdown
# Deep Audit Complete

## Modules Discovered: [COUNT]

| Module | Type | Files | LOC | Key Functions |
|--------|------|-------|-----|---------------|
| [name] | [type] | [n] | [loc] | [count] |

## Dependency Graph
[Module A] → [Module B] → [Module C]

## Next Steps
Run `/specledger.adopt --module-id [ID] --from-audit` to create specs.
```

## Error Handling

- **No quick audit**: "Run /specledger.audit --format json first"
- **Stale cache**: "Quick audit older than 24h. Run /specledger.audit --force"
- **No modules found**: "Could not identify module boundaries. Project may be too flat."
- **Analysis timeout**: "Module [X] analysis exceeded time limit. Skipping detailed analysis."

## Examples

```bash
# Full analysis after quick audit
/specledger.audit-deep

# Analyze specific module only
/specledger.audit-deep --module user-management

# Force re-analysis
/specledger.audit-deep --force
```
