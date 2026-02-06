# Module Clustering Strategies

Reusable patterns for grouping files into modules when clear directory structure doesn't exist.

## When to Use

Apply these strategies when the codebase has:
- Flat file structure (no clear `src/modules/` or `packages/`)
- Legacy codebases with mixed organization
- Single-directory projects with many files

## Strategy 1: Filename Prefix Clustering

```bash
# Find files sharing common prefixes
ls src/ | cut -d'_' -f1 | sort | uniq -c | sort -rn
# Example: user_controller.py, user_service.py, user_repository.py → Module: "User Management"
```

## Strategy 2: Import/Dependency Analysis

```bash
# Build dependency graph
grep -r "^import " src/ | grep -o "from [^ ]*" | sort | uniq -c
# If files A, B, C heavily import each other but rarely import D → Group A+B+C as one module
```

## Strategy 3: URL/Route Clustering

```bash
# For web apps, cluster by API routes
grep -r "@app.route\|@router.get\|router.GET\|Route" src/
# Paths like /api/billing/* → "Billing Module"
# Paths like /api/users/* → "User Module"
```

## Strategy 4: Database Table Clustering

```bash
# Group by database models
grep -r "class.*Model\|CREATE TABLE\|@Entity" src/
# Tables: orders, order_items, order_history → "Order Management Module"
```

## Output Format for Clustered Modules

```json
{
  "id": "user-management",
  "name": "User Management",
  "detection_method": "filename-clustering",
  "paths": ["src/user_controller.py", "src/user_service.py", "src/user_repo.py"],
  "confidence": "medium",
  "notes": ["Detected via filename prefix 'user_'. Consider refactoring into src/modules/user/"]
}
```

## Warning Conditions

- If no clustering strategy succeeds → Warn user: "Project too flat. Consider reorganization"
- If confidence < 50% → Mark module as "needs manual review"
- High file count (>50 files) without clear structure → Suggest running `/specledger.audit-deep` for detailed analysis
