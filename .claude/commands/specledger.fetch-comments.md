---
description: Fetch and address review comments from Supabase directly by file path (no commit memory needed)
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

This command fetches review comments for spec file(s) **directly from Supabase** without requiring previous commit information in conversation memory. It queries by project/spec path to get all open review comments.

**When to use**:
- After pushing changes to GitHub (via any method - git push, /specledger.commit, etc.)
- When starting a new session and need to check for comments
- When team members have added comments to your specs
- To address feedback without needing to re-run /specledger.commit

**NOT for**: Task/issue synchronization (use `/specledger.sync` instead)

**Key difference from /specledger.revise**:
- `/specledger.revise` - Requires commit info in conversation memory
- `/specledger.fetch-comments` - Queries directly by project/path (independent)

**Required Environment Variables**:
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Your Supabase service role key

See README.md for configuration instructions.

## Prerequisites

1. Repository exists in Supabase database (added via UI)
2. Files have been pushed to GitHub (webhook synced)
3. Node.js installed (for querying Supabase)
4. `@supabase/supabase-js` package installed

## Input Options

### Option 1: No arguments (auto-detect from git remote)
```
/specledger.fetch-comments
```
→ Auto-detects repo owner/name from git remote and fetches all open review comments

### Option 2: Spec Folder Path
```
/specledger.fetch-comments "specs/001-connect-superbase"
```
→ Filters comments for files in this folder

### Option 3: Explicit repo owner/name
```
/specledger.fetch-comments "Rockship-Team/upwork-crawl-job"
```
→ Fetches comments for this specific repository

## Execution Flow

### 1. Parse Arguments & Detect Repository

**Step 1a: Get repo info from git remote (if not provided)**:
```bash
# Get repo owner and name from git remote
git remote get-url origin
# Parse: https://github.com/OWNER/REPO.git or git@github.com:OWNER/REPO.git
```

**Step 1b: Parse arguments**:
- If `$ARGUMENTS` is empty → use auto-detected repo
- If `$ARGUMENTS` contains `/` without `specs/` → treat as `owner/repo`
- If `$ARGUMENTS` starts with `specs/` → treat as filter path

### 2. Query Supabase for Review Comments

Use the `scripts/get-review-comments.js` script:

```bash
# Query by project
node scripts/get-review-comments.js by-project <repo-owner> <repo-name>
```

**Expected output structure**:
```json
[
  {
    "change": {
      "id": "uuid",
      "head_branch": "change/spec-plan-tasks",
      "base_branch": "001-connect-superbase",
      "state": "open"
    },
    "comments": [
      {
        "id": "uuid",
        "content": "comment text",
        "file_path": "specs/001-connect-superbase/spec.md",
        "selected_text": "text that was selected",
        "start_line": null,
        "line": null,
        "is_resolved": false,
        "author_id": "uuid",
        "created_at": "timestamp"
      }
    ]
  }
]
```

### 3. Display Comments Summary

Show all unresolved comments grouped by change/branch:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📬 Review Comments for {repo_owner}/{repo_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Change: {head_branch} → {base_branch} ({state})
Comments: {count}

┌─ {file_path}
│  Comment #{id (8 chars)}
│  Content: "{content}"
│  Selected: "{selected_text (truncated)}"
│  Resolved: {is_resolved}
└─
```

### 4. Process Each Comment Interactively

For each comment:

1. **Read the file** at `file_path`
2. **Find the selected_text** in the file (if available)
3. **Analyze the comment** content and context
4. **Generate 2-3 options** for addressing the feedback
5. **Use askUserQuestion** to get user preference
6. **Apply the edit** to the file
7. **Confirm** and move to next comment

**CRITICAL RULES:**
- MUST use askUserQuestion before making ANY edit
- If `selected_text` is provided, locate it in the file for context
- If `line` is provided, show that line in context
- Present clear, distinct options for each comment
- Apply edits incrementally, one comment at a time

### 5. Mark Comments as Resolved

After user confirms changes for each comment, mark it as resolved in Supabase:

```javascript
// Update review_comments table
await supabase
  .from('review_comments')
  .update({ is_resolved: true })
  .eq('id', commentId)
```

### 6. Commit Changes (Optional)

After all comments are addressed:

```
📝 Ready to commit changes?

Options:
A) Yes, commit and push changes
B) No, I'll commit manually later
```

If user chooses A:
```bash
git add <modified-files>
git commit -m "feat: address review comments

Updated files: <list>
Comments resolved: <count>"
git push origin HEAD
```

### 7. Summary Report

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Review Session Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 Repository: {repo_owner}/{repo_name}
🌿 Branch: {head_branch}
💬 Comments Addressed: {count}
📄 Files Updated: {count}

Files:
  ✓ {file_path} ({comment_count} comments)
  ...

✓ All comments marked as resolved in Supabase
✓ Changes committed and pushed (if chosen)

Next Steps:
- View changes: git diff HEAD~1
- Continue with /specledger.implement
- Check new comments: /specledger.fetch-comments
```

## Script: get-review-comments.js

The command uses `scripts/get-review-comments.js` which queries:
- `review_comments` table - contains the actual comments
- `changes` table - contains branch/PR info
- `specs` table - links to project
- `projects` table - contains repo_owner/repo_name

### Usage Examples:
```bash
# Get all comments for a project
node scripts/get-review-comments.js by-project Rockship-Team upwork-crawl-job

# Get comments for files matching a path pattern
node scripts/get-review-comments.js by-path specs/001-connect-superbase

# Get comments for a specific change
node scripts/get-review-comments.js by-change <change-id>
```

## Example Session

```
User: /specledger.fetch-comments

Claude:
🔍 Detecting repository from git remote...
   Repository: Rockship-Team/upwork-crawl-job

📬 Querying Supabase for review comments...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📬 Found 2 unresolved review comments
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Change: change/spec-plan-tasks → 001-connect-superbase (open)

┌─ .beads/issues.jsonl
│  Comment #c843faf9
│  Content: "good"
│  Selected: {"id":"upwork-crawl-job-0gv"...
└─

┌─ specs/001-connect-superbase/contracts/interfaces.md
│  Comment #0592374b
│  Content: "look good"
│  Selected: "API Contracts: Check Rockship Experience via Supabase"
└─

Let me process these comments...

[For each comment with actionable feedback, Claude will use askUserQuestion
 to confirm changes. Comments like "good" or "look good" are acknowledgments
 and can be marked as resolved without changes.]

Do you want me to mark these acknowledgment comments as resolved?

A) Yes, mark "good" and "look good" as resolved (no changes needed)
B) No, let me review them first
```

## Error Handling

### Repository not found
**Error:** "Project not found: owner/repo"
**Solution:** Ensure repository is added to SpecLedger UI first

### No changes found
**Message:** "No open changes found"
**Meaning:** No active branches/PRs with review comments

### No comments found
**Message:** "No unresolved comments found"
**Meaning:** All comments have been resolved or no one has commented yet

### Script not found
**Error:** "Cannot find scripts/get-review-comments.js"
**Solution:** Ensure you're in the project root directory

## Notes

- This command is **stateless** - it doesn't rely on conversation memory
- Comments are fetched from `review_comments` table in Supabase
- Comments with `selected_text` show what text the reviewer highlighted
- Some comments are acknowledgments (like "good") and don't require file changes
- Works with any push method (git push, /specledger.commit, GitHub UI, etc.)
