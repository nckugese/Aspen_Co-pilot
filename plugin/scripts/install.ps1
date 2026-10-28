#Requires -Version 5.1
<#
.SYNOPSIS
    One-time environment setup for the aspen-plus MCP server.

.DESCRIPTION
    Downloads and warms the pinned server build so the MCP client never has to do it
    inside its ~60 second startup budget. Safe to re-run: uv resolves from cache once
    the download has happened, so a second run costs seconds and repairs a partial one.

    The version installed is whatever .mcp.json pins -- this script never chooses a
    version of its own, so the plugin and the server can never disagree.

    Run by the agent AFTER asking the user, or by the user directly from any terminal.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1
#>
[CmdletBinding()]
param(
    # Defaults to the plugin root (this script's parent's parent).
    [string]$PluginRoot
)

$ErrorActionPreference = 'Stop'

# $PSScriptRoot is not populated while param() defaults are evaluated under
# PowerShell 5.1, so this has to be resolved in the body.
if (-not $PluginRoot) { $PluginRoot = Split-Path -Parent $PSScriptRoot }

. (Join-Path $PSScriptRoot '_state.ps1')

function Write-Step { param([string]$Text) Write-Host "`n== $Text" }
function Write-Ok   { param([string]$Text) Write-Host "OK    $Text" }
function Write-Fail { param([string]$Text) Write-Host "FAIL  $Text" }

Write-Host "Aspen Plus MCP -- environment setup"

# --- 1. what are we installing? ---------------------------------------------
Write-Step "Reading the pinned server version"

$mcpPath = Join-Path $PluginRoot '.mcp.json'
if (-not (Test-Path -LiteralPath $mcpPath)) {
    Write-Fail "Cannot find .mcp.json at: $mcpPath"
    Write-Host "  Pass the plugin directory explicitly:  -PluginRoot <path>"
    exit 1
}

try {
    $cfg  = Get-Content -LiteralPath $mcpPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $spec = $cfg.mcpServers.'aspen-plus'.args | Where-Object { $_ -like '*git+*' } | Select-Object -First 1
} catch {
    Write-Fail "Could not parse $mcpPath -- $($_.Exception.Message)"
    exit 1
}

if (-not $spec) {
    Write-Fail "No git package spec found in $mcpPath"
    exit 1
}

$pinned = $null
if ($spec -match '@(v\d+\.\d+\.\d+)(#|$)') { $pinned = $Matches[1] }
if (-not $pinned) {
    Write-Fail "The spec in .mcp.json is not pinned to a release tag:"
    Write-Host "  $spec"
    Write-Host "  A floating ref cannot be set up reliably -- it may change between runs."
    exit 1
}
Write-Ok "Target: $pinned"

# --- 2. is uv available? -----------------------------------------------------
Write-Step "Checking uv"

# Check uvx, not uv: a bare `uvx` is the name .mcp.json invokes, so that is the
# name that has to resolve.
if (-not (Get-Command uvx -ErrorAction SilentlyContinue)) {
    # Two very different states look identical from here, and the wrong repair
    # wastes the user's time. Separate them before recommending anything.
    $installed = $null
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $installed = winget list --id astral-sh.uv -e 2>$null | Select-String 'astral-sh.uv'
    } catch {
        # advisory only -- absence of an answer is handled below
    } finally {
        $ErrorActionPreference = $prevEap
    }
    $onPath = @([Environment]::GetEnvironmentVariable('Path', 'User') -split ';' | Where-Object { $_ -like '*uv*' })

    Write-Fail "uvx is not resolvable from this process."
    if ($installed -or $onPath.Count -gt 0) {
        Write-Host ""
        Write-Host "  uv IS installed and on the persisted PATH -- installing it again changes nothing."
        Write-Host "  This process inherited a stale environment. Fix it with ONE of:"
        Write-Host "    - sign out of Windows and back in  (most reliable)"
        Write-Host "    - restart Explorer, then relaunch the client"
        Write-Host "    - launch the client from a terminal where 'uvx --version' already works"
    } else {
        Write-Host ""
        Write-Host "  uv is not installed. Install it, then open a NEW terminal:"
        Write-Host "    winget install --id=astral-sh.uv -e"
        Write-Host ""
        Write-Host "  winget updates PATH only for processes started afterwards, so this"
        Write-Host "  session -- and the client that spawned it -- still cannot see uvx."
    }
    Write-Host ""
    Write-Host "  Re-run this script once uvx --version works."
    exit 1
}
Write-Ok ((uvx --version 2>&1 | Select-Object -First 1) -replace '\s+$', '')

# --- 3. download and verify --------------------------------------------------
Write-Step "Downloading and verifying (about 200 MB on a cold cache; 1-3 minutes)"
Write-Host "  Progress appears below. A long pause with no output is the download running."
Write-Host ""

# uv reports progress on stderr. Under $ErrorActionPreference = 'Stop' the first
# stderr line from a native command becomes a terminating NativeCommandError, which
# would abort this script mid-download -- on SUCCESS as well as on failure, leaving
# the state file unwritten and the user prompted to install forever. Drop to
# 'Continue' for the call and judge the outcome by the exit code alone.
$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    & uvx --from $spec aspen-mcp --check
    $checkExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $prevEap
}

if ($checkExit -ne 0) {
    Write-Host ""
    Write-Fail "aspen-mcp --check exited $checkExit"
    Write-Host "  Re-run this script once. If it fails the same way twice, the cause is"
    Write-Host "  network or proxy rather than anything a third attempt will fix -- open"
    Write-Host "  an issue on github.com/nckugese/Aspen_Co-pilot with the output above."
    exit 1
}

# --- 4. record it ------------------------------------------------------------
Set-AspenState @{ setupCompletedFor = $pinned }

Write-Host ""
Write-Ok "Setup complete for $pinned"
Write-Host ""
Write-Host "Restart the client (Claude Code or Codex) so it starts the server from the warm cache."
Write-Host "Then run the aspen-doctor skill if you want the full pass/fail check."
exit 0
