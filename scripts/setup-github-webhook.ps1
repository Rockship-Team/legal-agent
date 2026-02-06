# ============================================================================
# AUTO-SETUP GITHUB WEBHOOK
# Purpose: Automatically configure webhook for a repository using GitHub API
# ============================================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$RepoOwner,
    
    [Parameter(Mandatory=$true)]
    [string]$RepoName,
    
    [Parameter(Mandatory=$true)]
    [string]$WebhookUrl,
    
    [Parameter(Mandatory=$true)]
    [string]$WebhookSecret,
    
    [Parameter(Mandatory=$true)]
    [string]$GitHubToken
)

$ErrorActionPreference = "Stop"

Write-Host "Setting up webhook for $RepoOwner/$RepoName" -ForegroundColor Cyan

# GitHub API endpoint
$apiUrl = "https://api.github.com/repos/$RepoOwner/$RepoName/hooks"

# Webhook configuration
$webhookConfig = @{
    name = "web"
    active = $true
    events = @("push")
    config = @{
        url = $WebhookUrl
        content_type = "json"
        secret = $WebhookSecret
        insecure_ssl = "0"
    }
} | ConvertTo-Json -Depth 10

# Headers
$headers = @{
    "Authorization" = "token $GitHubToken"
    "Accept" = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

try {
    Write-Host "Checking existing webhooks..." -ForegroundColor Yellow
    $existingHooks = Invoke-RestMethod -Uri $apiUrl -Headers $headers -Method Get
    
    $existingHook = $existingHooks | Where-Object { $_.config.url -eq $WebhookUrl }
    
    $result = $null
    
    if ($existingHook) {
        Write-Host "Webhook already exists (ID: $($existingHook.id))" -ForegroundColor Yellow
        Write-Host "  URL: $($existingHook.config.url)"
        Write-Host "  Events: $($existingHook.events -join ', ')"
        Write-Host "  Active: $($existingHook.active)"
        
        $update = Read-Host "Update existing webhook? (y/n)"
        if ($update -eq 'y') {
            $updateUrl = "$apiUrl/$($existingHook.id)"
            $result = Invoke-RestMethod -Uri $updateUrl -Headers $headers -Method Patch -Body $webhookConfig
            Write-Host "Webhook updated successfully!" -ForegroundColor Green
        } else {
            Write-Host "Skipped update" -ForegroundColor Gray
            $result = $existingHook
        }
    } else {
        Write-Host "Creating webhook..." -ForegroundColor Yellow
        $result = Invoke-RestMethod -Uri $apiUrl -Headers $headers -Method Post -Body $webhookConfig
        Write-Host "Webhook created successfully!" -ForegroundColor Green
        Write-Host "  ID: $($result.id)"
        Write-Host "  URL: $($result.config.url)"
        Write-Host "  Events: $($result.events -join ', ')"
    }
    
    if ($result) {
        Write-Host "`nTesting webhook (sending ping)..." -ForegroundColor Yellow
        $pingUrl = "$apiUrl/$($result.id)/pings"
        Invoke-RestMethod -Uri $pingUrl -Headers $headers -Method Post | Out-Null
        Write-Host "Ping sent! Check your Supabase logs to verify webhook is working." -ForegroundColor Green
    }
    
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    
    if ($_.Exception.Response) {
        $statusCode = [int]$_.Exception.Response.StatusCode
        if ($statusCode -eq 404) {
            Write-Host "  Repository not found or token does not have access" -ForegroundColor Red
        } elseif ($statusCode -eq 403) {
            Write-Host "  Permission denied - token needs admin:repo_hook scope" -ForegroundColor Red
        }
    }
    
    exit 1
}

Write-Host "`nDone! Webhook is configured for $RepoOwner/$RepoName" -ForegroundColor Green
Write-Host "Next: Make a commit to test it!" -ForegroundColor Gray
