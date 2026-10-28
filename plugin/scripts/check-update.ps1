#Requires -Version 5.1
<#
.SYNOPSIS
    Refreshes the cached "latest release" marker, or records a declined release.

.DESCRIPTION
    Normally launched detached by the SessionStart hook, at most once every 24 hours.
    Its result is read by a LATER session -- nothing ever waits on this.

    Being one session behind on an update notice costs nothing. Blocking a session
    start on a network call costs something every single time. Hence the split.

    Release tags are read with `git ls-remote`, not the GitHub API: ls-remote needs no
    token and is not subject to the API's 60-requests-per-hour unauthenticated limit,
    which many machines behind one address would hit.

    Silent by design, including on failure -- no network, a proxy, or a missing git all
    mean "say nothing this time". lastUpdateCheck is stamped regardless of outcome so a
    persistent failure backs off for 24 hours instead of retrying every session.

.PARAMETER Decline
    Record that the user does not want this release, so they are not asked again.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File check-update.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File check-update.ps1 -Decline v0.1.8
#>
[CmdletBinding()]
param(
    [string]$Decline,
    [string]$PluginRoot
)

$ErrorActionPreference = 'Stop'

# $PSScriptRoot is not populated while param() defaults are evaluated under
# PowerShell 5.1, so this has to be resolved in the body.
if (-not $PluginRoot) { $PluginRoot = Split-Path -Parent $PSScriptRoot }

. (Join-Path $PSScriptRoot '_state.ps1')

# --- decline mode: record and leave -----------------------------------------
if ($Decline) {
    try {
        Set-AspenState @{ declinedVersion = $Decline }
        Write-Host "Recorded: will not prompt again for $Decline."
    } catch {
        Write-Host "Could not record the declined version -- $($_.Exception.Message)"
        exit 1
    }
    exit 0
}

# --- check mode: everything below is best-effort and silent ------------------
try {
    $mcpPath = Join-Path $PluginRoot '.mcp.json'
    if (-not (Test-Path -LiteralPath $mcpPath)) { exit 0 }

    $cfg  = Get-Content -LiteralPath $mcpPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $spec = $cfg.mcpServers.'aspen-plus'.args | Where-Object { $_ -like '*git+*' } | Select-Object -First 1
    if (-not $spec) { exit 0 }

    # "aspen-mcp[all] @ git+https://host/owner/repo@v0.1.7#subdirectory=aspen-mcp"
    if ($spec -notmatch 'git\+(?<url>[^@#]+)') { exit 0 }
    $repoUrl = $Matches['url']

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Set-AspenState @{ lastUpdateCheck = (Get-Date).ToUniversalTime().ToString('o') }
        exit 0
    }

    # 'Continue' for the native call: git writes to stderr whenever the remote is
    # unreachable, and under 'Stop' that terminates before lastUpdateCheck is
    # stamped -- which would make an offline machine re-spawn this every session.
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $refs = git ls-remote --tags $repoUrl 2>$null
        $gitExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEap
    }

    if ($gitExit -ne 0 -or -not $refs) {
        Set-AspenState @{ lastUpdateCheck = (Get-Date).ToUniversalTime().ToString('o') }
        exit 0
    }

    $highest    = $null
    $highestTag = $null
    foreach ($line in $refs) {
        # "<sha>\trefs/tags/v0.1.7"  and the peeled "...^{}" variant
        if ($line -match 'refs/tags/(v\d+\.\d+\.\d+)(\^\{\})?$') {
            $tag = $Matches[1]
            try { $v = [version]$tag.TrimStart('v') } catch { continue }
            if (-not $highest -or $v -gt $highest) {
                $highest    = $v
                $highestTag = $tag
            }
        }
    }

    $update = @{ lastUpdateCheck = (Get-Date).ToUniversalTime().ToString('o') }
    if ($highestTag) { $update['latestKnownVersion'] = $highestTag }
    Set-AspenState $update
    exit 0
}
catch {
    exit 0
}
