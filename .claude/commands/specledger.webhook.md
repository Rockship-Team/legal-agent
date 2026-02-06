---
description: Automatically set up GitHub webhook for a repository to sync with Supabase.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

This command automates the setup of GitHub webhooks for repositories, enabling automatic synchronization of push events to the Supabase backend. The webhook will trigger on push events and send data to the configured Supabase function.

## Prerequisites

Before running this command, ensure:
1. The repository has been created on GitHub
2. The repository information has been added to the database via the UI
3. You have a GitHub Personal Access Token with `admin:repo_hook` scope

## Execution Flow

### 1. Parse Arguments

The command expects the following parameters in the format:
```
/specledger.webhook -RepoOwner "<owner>" -RepoName "<repo>" -WebhookSecret "<secret>" -GitHubToken "<token>"
```

**Required Parameters**:
- `RepoOwner`: GitHub repository owner/organization (e.g., "Ne4nf")
- `RepoName`: Repository name (e.g., "taxi-app")
- `WebhookSecret`: Webhook secret for signature verification (32+ character hex string)
- `GitHubToken`: GitHub Personal Access Token with admin:repo_hook scope

**Environment Variable (Required)**:
- `SUPABASE_URL`: Your Supabase project URL (e.g., `https://your-project.supabase.co`)
  - The webhook URL is derived as: `${SUPABASE_URL}/functions/v1/github-webhook`

### 2. Parameter Validation

Check if all required parameters are provided in `$ARGUMENTS`:

a. If `$ARGUMENTS` is empty or missing parameters:
   - List the missing parameters
   - Provide examples for each parameter:
     ```
     RepoOwner: The GitHub username or organization (e.g., "Ne4nf")
     RepoName: The repository name (e.g., "taxi-app")
     WebhookSecret: A secure random string (generate with: `openssl rand -hex 32`)
     GitHubToken: GitHub Personal Access Token (create at: https://github.com/settings/tokens)
     ```
   - Ask user to provide the missing values in this format (each on a new line with bullet points):
     ```
     Please provide the parameters:

     - RepoOwner: "your-owner"
     - RepoName: "your-repo"
     - WebhookSecret: "your-secret" (generate with: openssl rand -hex 32)
     - GitHubToken: "your-token"

     Example:
     - RepoOwner: "Ne4nf"
     - RepoName: "taxi-app"
     - WebhookSecret: "355a3ed0d3a3f4241efc556e79a620dbf04c918f6910bfd54b2c6b37bee14c1b"
     - GitHubToken: "ghp_YOUR_TOKEN_HERE"
     ```
   - **STOP** and wait for user response

b. If all parameters are provided:
   - Parse and extract each parameter value
   - Validate format:
     - RepoOwner: Non-empty string
     - RepoName: Non-empty string
     - WebhookSecret: Minimum 32 characters
     - GitHubToken: Starts with "ghp_" or "github_pat_"
   - If validation fails, show the error and ask user to correct it
   - Proceed to step 3

### 3. Execute Webhook Setup Script

Run the PowerShell script with the provided parameters:

```powershell
# Read Supabase URL from environment
$supabaseUrl = $env:SUPABASE_URL

if (-not $supabaseUrl) {
    Write-Host "❌ Error: SUPABASE_URL environment variable is required" -ForegroundColor Red
    Write-Host "   Set this in .env file or shell environment." -ForegroundColor Yellow
    Write-Host "   See README.md for configuration instructions." -ForegroundColor Yellow
    exit 1
}

$webhookUrl = "$supabaseUrl/functions/v1/github-webhook"

.\scripts\setup-github-webhook.ps1 `
  -RepoOwner "<owner>" `
  -RepoName "<repo>" `
  -WebhookUrl "$webhookUrl" `
  -WebhookSecret "<secret>" `
  -GitHubToken "<token>"
```

**Important Notes**:
- Use backticks (`) for line continuation in PowerShell
- Ensure all parameter values are properly quoted
- The WebhookUrl is derived from the SUPABASE_URL environment variable

### 4. Handle Script Output

The script will:
- Check for existing webhooks with the same URL
- If found: Ask if you want to update it (respond 'y' or 'n')
- If not found: Create a new webhook
- Send a test ping to verify the webhook is working

**Success Indicators**:
- "Webhook created successfully!" or "Webhook updated successfully!"
- "Ping sent! Check your Supabase logs to verify webhook is working."
- Webhook ID is displayed

**Error Handling**:
- **404 Error**: Repository not found or token doesn't have access
  - Verify RepoOwner and RepoName are correct
  - Check that the token has access to the repository
- **403 Error**: Permission denied
  - Token needs `admin:repo_hook` scope
  - Go to: https://github.com/settings/tokens
  - Generate new token with required scope
- **Other errors**: Display the error message and suggest solutions

### 5. Verify Setup

After successful setup, guide the user to verify:

1. **Check GitHub**:
   - Go to: `https://github.com/<owner>/<repo>/settings/hooks`
   - Webhook should appear with:
     - URL: `${SUPABASE_URL}/functions/v1/github-webhook`
     - Events: "push"
     - Active: ✓

2. **Check Supabase Logs**:
   - Go to Supabase Dashboard → Functions → github-webhook → Logs
   - Look for the ping event
   - Should show status 200 and "Ping received" in response

3. **Test with Real Push**:
   - Make a commit to the repository
   - Push to GitHub
   - Check Supabase logs for the push event
   - Verify the webhook data was processed

### 6. Report Completion

Provide a summary:

```
✅ GitHub Webhook Setup Complete

Repository: <owner>/<repo>
Webhook ID: <id>
Webhook URL: ${SUPABASE_URL}/functions/v1/github-webhook
Events: push
Status: Active

Next Steps:
- If repository already has code: Run `/specledger.adopt` to adopt existing feature branch
- If repository is new/empty: Run `/specledger.constitution` to set up project structure

Verification:
- Webhook logs: https://github.com/<owner>/<repo>/settings/hooks/<id>/deliveries
- Supabase logs: [Supabase Dashboard] → Functions → github-webhook → Logs
```

## Security Reminders

- **Never commit tokens or secrets to the repository**
- Store WebhookSecret and GitHubToken in a secure location (e.g., password manager)
- Rotate tokens regularly
- Use different secrets for different repositories
- Revoke tokens immediately if compromised

## Common Issues

### Issue: "Permission denied"
**Solution**: Token needs `admin:repo_hook` scope. Create new token at https://github.com/settings/tokens

### Issue: "Repository not found"
**Solution**: Verify repository name and ensure token has access

### Issue: "Webhook already exists"
**Solution**: Script will ask if you want to update it. Choose 'y' to update with new settings

### Issue: "Ping failed"
**Solution**: 
- Check Supabase function is deployed and running
- Verify WebhookUrl is correct
- Check Supabase logs for errors

## Example Usage

```
/specledger.webhook -RepoOwner "Ne4nf" -RepoName "taxi-app" -WebhookSecret "355a3ed0d3a3f4241efc556e79a620dbf04c918f6910bfd54b2c6b37bee14c1b" -GitHubToken "ghp_YOUR_TOKEN_HERE"
```

This will:
1. Set up webhook for repository `Ne4nf/taxi-app`
2. Configure it to send push events to Supabase
3. Send a test ping to verify connectivity
4. Provide verification steps
