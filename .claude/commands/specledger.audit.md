---
description: Quick reconnaissance scan of codebase structure to identify tech stack, architecture, and entry points
---

## User Input

```text
$ARGUMENTS
```

Optional flags:
- `--format json|markdown`: Output format (default: markdown)
- `--scope [PATH]`: Only analyze specific directory

## Purpose

Perform a quick reconnaissance scan of a codebase to identify the tech stack, architecture pattern, and entry points. This is a fast first-pass analysis (~15 minutes) that provides an overview without deep code analysis.

**For detailed module analysis**, run `/specledger.audit-deep` after this command.

## When to Use

- First encounter with an unfamiliar codebase
- Quick project overview before starting work
- Validating tech stack assumptions
- Preparing context for `/specledger.adopt`

## Execution Flow

### Phase 1: Tech Stack Detection (5 minutes)

1. **Detect Language & Framework**
   ```bash
   # Scan root for identifying files
   ls -la | grep -E "package.json|go.mod|requirements.txt|pyproject.toml|pom.xml|build.gradle|composer.json|Cargo.toml|Gemfile"
   ```

   Apply detection patterns from `.specify/templates/partials/language-detection.md`:
   - **JavaScript/TypeScript**: `package.json`, `tsconfig.json`
   - **Python**: `requirements.txt`, `pyproject.toml`
   - **Go**: `go.mod`, `go.sum`
   - **Java/Kotlin**: `pom.xml`, `build.gradle`
   - **PHP**: `composer.json`
   - **Rust**: `Cargo.toml`
   - **Ruby**: `Gemfile`

2. **Extract Framework Information**
   ```bash
   # For Node.js projects
   cat package.json | jq '{name, dependencies, devDependencies, scripts}' 2>/dev/null

   # For Go projects
   cat go.mod | grep "^module\|^require" 2>/dev/null
   ```

### Phase 2: Directory Structure Mapping (5 minutes)

1. **Get Project Tree**
   ```bash
   tree -L 3 -d -I 'node_modules|.git|dist|build|vendor|target|__pycache__|coverage|.next'
   ```

2. **Identify Architecture Pattern**
   - **Monorepo**: `packages/`, `apps/`, `libs/`, `pnpm-workspace.yaml`
   - **Clean Architecture**: `domain/`, `infrastructure/`, `application/`
   - **MVC**: `controllers/`, `models/`, `views/`
   - **Feature-Sliced**: `features/`, `entities/`, `shared/`
   - **Microservices**: Multiple `cmd/` or `services/` directories

3. **Count Files by Type**
   ```bash
   find . -type f -name "*.ts" -o -name "*.tsx" -o -name "*.go" -o -name "*.py" 2>/dev/null | wc -l
   ```

### Phase 3: Entry Point Detection (5 minutes)

1. **Find Entry Points**
   ```bash
   find . -name "main.go" -o -name "main.ts" -o -name "index.ts" -o -name "app.py" -o -name "server.js" 2>/dev/null
   ```

2. **Check Build Scripts**
   ```bash
   cat package.json | jq '.scripts' 2>/dev/null
   grep "^[a-z].*:" Makefile 2>/dev/null
   ```

## Output

Generate a quick overview in the requested format:

### Markdown Output (default)

```markdown
# Project Overview: [PROJECT_NAME]

## Tech Stack
- **Language**: [Primary language]
- **Framework**: [Framework name]
- **Build Tool**: [npm/yarn/go/etc]

## Architecture
- **Pattern**: [Monorepo/MVC/Clean/etc]
- **Structure**: [Brief description]

## Entry Points
- [List of main entry files]

## File Statistics
- Total source files: [count]
- Primary directories: [list]

## Next Steps
For detailed module analysis, run:
\`/specledger.audit-deep\`
```

### JSON Output (--format json)

```json
{
  "project_name": "...",
  "tech_stack": {
    "language": "...",
    "framework": "...",
    "build_tool": "..."
  },
  "architecture": {
    "pattern": "...",
    "key_directories": []
  },
  "entry_points": [],
  "file_count": 0,
  "audit_type": "quick"
}
```

Save JSON output to `scripts/audit-quick.json` for use by `/specledger.audit-deep`.

## Error Handling

- **No recognizable project files**: "Cannot detect project type. Ensure you're in a project root directory."
- **Empty directory**: "No source files found in the specified scope."
- **Permission denied**: "Cannot read some directories. Check file permissions."

## Examples

```bash
# Quick scan of current directory
/specledger.audit

# Scan specific subdirectory
/specledger.audit --scope src/api

# Output as JSON for scripting
/specledger.audit --format json
```
