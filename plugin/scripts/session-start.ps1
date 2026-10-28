#Requires -Version 5.1
<#
    SessionStart hook for the aspen-plus plugin.

    Contract, in priority order:

      1. NEVER break a session. Every failure path exits 0 and says nothing.
         A broken update-notifier is worse than no update-notifier.
      2. NEVER touch the network. This runs on the session-start critical path,
         so it only *reads* a cache that check-update.ps1 refreshes out of band.
      3. Say nothing when there is nothing to say. Silence is the common case.

    It emits at most one of two messages:
      - setup has not completed for the pinned server version
      - a newer release exists and the user has not already declined it
    -Client names the client that runs the hook: hooks/hooks.json (Claude Code) passes
    nothing, hooks/codex.json passes 'codex'. The two differ in what reaches the model:
    Claude Code takes systemMessage, Codex only hookSpecificOutput.additionalContext.
    On Codex this hook also installs the aspen-doc subagent (Install-CodexAgent), since a
    Codex plugin cannot bundle one.
#>
param([string]$Client = 'claude')

$ErrorActionPreference = 'Stop'

$PluginRoot = Split-Path -Parent $PSScriptRoot
$StateFile  = Join-Path $env:USERPROFILE '.aspen-mcp\setup-state.json'
$CheckTtlHours = 24
$IsCodex = $Client -eq 'codex'
$ClientName = if ($IsCodex) { 'Codex' } else { 'Claude Code' }
$UpdateCmd  = if ($IsCodex) { 'codex plugin marketplace upgrade aspen-mcp' } else { 'claude plugin update aspen-plus@aspen-mcp' }

function Send-Result {
    param([string]$Message)

    if ($IsCodex) {
        # Codex: silence is no output at all; systemMessage never reaches the model there.
        if ($script:AgentNote) { $Message = (@($Message, $script:AgentNote) | Where-Object { $_ }) -join "`r`n`r`n" }
        if ([string]::IsNullOrWhiteSpace($Message)) { return }
        $payload = [ordered]@{
            hookSpecificOutput = [ordered]@{
                hookEventName     = 'SessionStart'
                additionalContext = $Message
            }
        }
        Write-Output ($payload | ConvertTo-Json -Compress -Depth 4)
        return
    }

    if ([string]::IsNullOrWhiteSpace($Message)) {
        Write-Output '{"continue":true,"suppressOutput":true}'
        return
    }

    $payload = [ordered]@{
        continue       = $true
        suppressOutput = $true
        systemMessage  = $Message
    }
    Write-Output ($payload | ConvertTo-Json -Compress -Depth 3)
}

function Get-PinnedRef {
    # The pinned tag lives in .mcp.json and nowhere else -- it is the single
    # source of truth for "which server version is this plugin supposed to run".
    $mcpPath = Join-Path $PluginRoot '.mcp.json'
    if (-not (Test-Path $mcpPath)) { return $null }

    $cfg  = Get-Content -LiteralPath $mcpPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $spec = $cfg.mcpServers.'aspen-plus'.args | Where-Object { $_ -like '*git+*' } | Select-Object -First 1
    if (-not $spec) { return $null }

    if ($spec -match '@(v\d+\.\d+\.\d+)(#|$)') { return $Matches[1] }
    return $null
}

function ConvertTo-Comparable {
    param([string]$Tag)
    if ([string]::IsNullOrWhiteSpace($Tag)) { return $null }
    try { return [version]($Tag.TrimStart('v')) } catch { return $null }
}

function Start-BackgroundUpdateCheck {
    # Fire and forget. The result lands in the state file for a LATER session --
    # this one deliberately does not wait for it.
    $script = Join-Path $PluginRoot 'scripts\check-update.ps1'
    if (-not (Test-Path $script)) { return }

    Start-Process -FilePath 'powershell' `
        -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', "`"$script`"" `
        -WindowStyle Hidden | Out-Null
}

function Install-CodexAgent {
    # A Codex plugin cannot bundle a subagent (openai/codex#18988), and Codex reads
    # ~/.codex/agents when a session starts -- before this hook. So the agent is written
    # there now and is usable from the next session on. It is built from agents/aspen-doc.md,
    # the one copy of its instructions, and rewritten only when that changes.
    $src = Join-Path $PluginRoot 'agents\aspen-doc.md'
    if (-not (Test-Path -LiteralPath $src)) { return $null }
    $md = Get-Content -LiteralPath $src -Raw -Encoding UTF8
    if ($md -notmatch '(?s)^---\r?\n(?<front>.*?)\r?\n---\r?\n(?<body>.*)$') { return $null }
    $body  = $Matches['body'].Trim()
    $front = $Matches['front']
    $desc  = 'Aspen Plus documentation lookup.'
    if ($front -match '(?m)^description:\s*(?<d>.+?)\s*$') { $desc = $Matches['d'] }
    $q = "'''"
    if ($body.Contains($q) -or $desc.Contains($q)) { return $null }
    $nl = "`n"
    $toml = '# Written by the aspen-plus plugin from its agents/aspen-doc.md; edits are overwritten.' + $nl +
            'name = "aspen-doc"' + $nl +
            'description = ' + $q + $desc + $q + $nl +
            'model_reasoning_effort = "low"' + $nl +
            'sandbox_mode = "read-only"' + $nl +
            'developer_instructions = ' + $q + $nl + ($body -replace "`r`n", $nl) + $nl + $q + $nl

    $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
    $dir = Join-Path $codexHome 'agents'
    $dst = Join-Path $dir 'aspen-doc.toml'
    $had = Test-Path -LiteralPath $dst
    if ($had -and ([System.IO.File]::ReadAllText($dst) -eq $toml)) { return $null }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    [System.IO.File]::WriteAllText($dst, $toml, (New-Object System.Text.UTF8Encoding $false))
    if ($had) { return $null }
    return @"
The aspen-doc subagent was just installed at $dst. Codex loads subagents when a session
starts, so it is available from the next session on. In this session, read the docs under
ASPEN_DOCS_ROOT directly: aspen.md first, then only the section the task needs.
"@
}

function Install-CodexLauncher {
    # ~/.aspen-mcp/codex-aspen.cmd starts Codex through scripts/codex-workbench.ps1, so an
    # Ask AI request reaches it at once. Rewritten each session: the plugin path moves with
    # every update. Records of app-servers no longer running are dropped.
    $dir = Join-Path $env:USERPROFILE '.aspen-mcp'
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $ps1 = Join-Path $PluginRoot 'scripts\codex-workbench.ps1'
    $cmd = "@echo off`r`npowershell -NoProfile -ExecutionPolicy Bypass -File `"$ps1`" %*`r`n"
    $dst = Join-Path $dir 'codex-aspen.cmd'
    if (-not (Test-Path -LiteralPath $dst) -or ([System.IO.File]::ReadAllText($dst) -ne $cmd)) {
        [System.IO.File]::WriteAllText($dst, $cmd)
    }
    $records = Join-Path $dir 'codex-app-servers'
    if (Test-Path -LiteralPath $records) {
        foreach ($f in Get-ChildItem -LiteralPath $records -Filter '*.json') {
            $id = 0
            if ([int]::TryParse($f.BaseName, [ref]$id) -and -not (Get-Process -Id $id -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

function Install-WorkbenchLauncher {
    # ~/.aspen-mcp/aspen-workbench.cmd opens the workbench with no AI client, through
    # scripts/aspen-workbench.ps1 (double-click it, or drop .bkp files on it). Rewritten each
    # session: the plugin path moves with every update.
    $dir = Join-Path $env:USERPROFILE '.aspen-mcp'
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $ps1 = Join-Path $PluginRoot 'scripts\aspen-workbench.ps1'
    $cmd = "@echo off`r`npowershell -NoProfile -ExecutionPolicy Bypass -File `"$ps1`" %*`r`nif errorlevel 1 pause`r`n"
    $dst = Join-Path $dir 'aspen-workbench.cmd'
    if (-not (Test-Path -LiteralPath $dst) -or ([System.IO.File]::ReadAllText($dst) -ne $cmd)) {
        [System.IO.File]::WriteAllText($dst, $cmd)
    }
}

$script:AgentNote = $null
try { Install-WorkbenchLauncher } catch {}
if ($IsCodex) { try { $script:AgentNote = Install-CodexAgent } catch { $script:AgentNote = $null } }
if ($IsCodex) { try { Install-CodexLauncher } catch {} }

try {
    $pinned = Get-PinnedRef
    if (-not $pinned) {
        # An unpinned or unreadable .mcp.json is not this hook's problem to report.
        Send-Result $null
        exit 0
    }

    $state = $null
    if (Test-Path -LiteralPath $StateFile) {
        try {
            $state = Get-Content -LiteralPath $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        } catch {
            $state = $null   # corrupt state reads as "never set up"
        }
    }

    # --- refresh the update cache out of band, if it is stale ---------------
    $needsCheck = $true
    if ($state -and $state.lastUpdateCheck) {
        try {
            $age = (Get-Date).ToUniversalTime() - ([datetime]$state.lastUpdateCheck).ToUniversalTime()
            if ($age.TotalHours -lt $CheckTtlHours) { $needsCheck = $false }
        } catch { $needsCheck = $true }
    }
    if ($needsCheck) { Start-BackgroundUpdateCheck }

    # --- 1. setup incomplete for the pinned version ------------------------
    $setupFor = $null
    if ($state) { $setupFor = $state.setupCompletedFor }

    if ($setupFor -ne $pinned) {
        $installScript = Join-Path $PluginRoot 'scripts\install.ps1'
        $verb = 'has not been set up yet'
        if ($setupFor) { $verb = "is set up for $setupFor, but this plugin now runs $pinned" }

        Send-Result @"
The Aspen Plus MCP environment $verb.

Until setup completes, every Aspen tool in this session will fail to start.

Ask the user -- in your own words -- whether to run the one-time setup now. Tell them it
downloads about 200 MB and takes roughly one to three minutes. Do NOT run it without
asking first.

If they agree, run exactly this and show them the output:

  powershell -NoProfile -ExecutionPolicy Bypass -File "$installScript"

If they decline, say plainly that Aspen tools will not work until it is run, and drop the
subject for the rest of the session -- do not ask again.
"@
        exit 0
    }

    # --- 2. an update is available -----------------------------------------
    $latest   = $null
    $declined = $null
    if ($state) {
        $latest   = $state.latestKnownVersion
        $declined = $state.declinedVersion
    }

    $latestV = ConvertTo-Comparable $latest
    $pinnedV = ConvertTo-Comparable $pinned

    if ($latestV -and $pinnedV -and ($latestV -gt $pinnedV) -and ($latest -ne $declined)) {
        $declineScript = Join-Path $PluginRoot 'scripts\check-update.ps1'

        Send-Result @"
A newer Aspen Plus plugin release is available: $latest (this session runs $pinned).

This is informational -- nothing is broken. Do NOT interrupt work in progress for it. Raise
it only at a natural pause, or if the user brings up Aspen setup or versions themselves.

When you do raise it, ask whether they want to update. If they agree:

  1. Run: $UpdateCmd
  2. Tell them to restart $ClientName.
     The next session detects the new version and offers to finish setup by itself.

If they decline, run this so they are not asked again for this release:

  powershell -NoProfile -ExecutionPolicy Bypass -File "$declineScript" -Decline $latest
"@
        exit 0
    }

    Send-Result $null
    exit 0
}
catch {
    # Rule 1. Whatever went wrong, it is not worth degrading the session over.
    Send-Result $null
    exit 0
}
