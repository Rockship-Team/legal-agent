---
description: Display all available SpecLedger commands with descriptions and workflow guidance
---

## Purpose

Quick reference for all available SpecLedger commands, organized by workflow stage. Use this when you need to discover what commands are available or understand the recommended workflow.

## Output

### Core Workflow (specify → plan → tasks → implement)

| Command | Description |
|---------|-------------|
| `/specledger.specify` | Create feature specification from natural language description |
| `/specledger.plan` | Generate implementation plan from spec with architecture decisions |
| `/specledger.tasks` | Create actionable, dependency-ordered tasks from plan |
| `/specledger.implement` | Execute tasks in order following the task plan |

### Analysis & Validation

| Command | Description |
|---------|-------------|
| `/specledger.analyze` | Cross-artifact consistency check across spec, plan, and tasks |
| `/specledger.audit` | Quick reconnaissance scan of codebase structure |
| `/specledger.audit-deep` | Full module analysis with dependency graphs (after audit) |
| `/specledger.clarify` | Identify and resolve spec ambiguities via targeted questions |
| `/specledger.checklist` | Generate custom validation checklist for the feature |

### Setup & Configuration

| Command | Description |
|---------|-------------|
| `/specledger.constitution` | Define project principles and coding standards |
| `/specledger.adopt` | Create spec from existing branch or audit output |
| `/specledger.webhook` | Configure GitHub webhook for Supabase integration |

### Collaboration

| Command | Description |
|---------|-------------|
| `/specledger.sync` | Pull tasks/issues from Supabase to local .beads/issues.jsonl |
| `/specledger.fetch-comments` | Pull review comments from Supabase for spec files |

## Workflow Guide

**New Feature Development:**
```
/specledger.specify → /specledger.plan → /specledger.tasks → /specledger.implement
```

**Existing Codebase Analysis:**
```
/specledger.audit → /specledger.audit-deep → /specledger.adopt
```

**Spec Quality Improvement:**
```
/specledger.clarify → /specledger.checklist → /specledger.analyze
```

## Quick Tips

- Start with `/specledger.specify` for new features
- Use `/specledger.sync` to get latest team task updates
- Use `/specledger.fetch-comments` for code review feedback
- Run `/specledger.analyze` after task generation to verify consistency
