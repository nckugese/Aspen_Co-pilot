#Requires -Version 5.1
<#
    Shared read/merge/write helpers for the setup state file.

    Dot-sourced by install.ps1 and check-update.ps1. Deliberately NOT used by
    session-start.ps1, which stays dependency-free so that nothing on the
    session-start critical path can fail to load.

    State lives beside the user's own Aspen data, which the server already owns:

        %USERPROFILE%\.aspen-mcp\setup-state.json

        {
          "setupCompletedFor":  "v0.1.7",   // pinned ref install.ps1 last completed
          "lastUpdateCheck":    "2026-08-11T05:40:00.0000000Z",
          "latestKnownVersion": "v0.1.7",   // highest release tag seen on origin
          "declinedVersion":    "v0.1.8"    // release the user said no to
        }

    Both writers merge into whatever is already there, so neither can clobber the
    other's fields. Keep this the only place that knows the schema.
#>

$script:AspenStateFile = Join-Path $env:USERPROFILE '.aspen-mcp\setup-state.json'

function Get-AspenState {
    if (-not (Test-Path -LiteralPath $script:AspenStateFile)) { return [ordered]@{} }
    try {
        $raw = Get-Content -LiteralPath $script:AspenStateFile -Raw -Encoding UTF8
        if ([string]::IsNullOrWhiteSpace($raw)) { return [ordered]@{} }

        $obj    = $raw | ConvertFrom-Json
        $result = [ordered]@{}
        foreach ($p in $obj.PSObject.Properties) { $result[$p.Name] = $p.Value }
        return $result
    } catch {
        # Corrupt state reads as empty, which makes the caller re-derive it.
        return [ordered]@{}
    }
}

function Set-AspenState {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Values
    )

    $state = Get-AspenState
    foreach ($k in $Values.Keys) { $state[$k] = $Values[$k] }

    $dir = Split-Path -Parent $script:AspenStateFile
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    ($state | ConvertTo-Json -Depth 5) |
        Out-File -FilePath $script:AspenStateFile -Encoding utf8 -Force
}
