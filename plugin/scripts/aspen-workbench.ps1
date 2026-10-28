#Requires -Version 5.1
<#
.SYNOPSIS
    Opens the Aspen Workbench with no AI client and no network.

.DESCRIPTION
    Runs `aspen-mcp --workbench` from the server environment uv already built for this plugin
    (scripts/install.ps1), found in uv's cache -- uvx is not asked, so nothing is resolved or
    downloaded and it works offline. Files given (or dropped on the .cmd) are opened; with none
    the window opens on the tabs it had, and its + menu's "Open Aspen model..." opens one.

    The SessionStart hook keeps a shortcut to this script at ~/.aspen-mcp/aspen-workbench.cmd.

    ASPEN_WORKBENCH_PYTHON names the environment's python.exe outright, for one kept elsewhere.

.EXAMPLE
    %USERPROFILE%\.aspen-mcp\aspen-workbench.cmd C:\models\plant.bkp
#>

$ErrorActionPreference = 'Stop'
$min = [version]'0.5.1'          # the first version with --workbench

function Stop-With([string]$Text) {
    Write-Host $Text
    exit 1
}

$exe = $null
if ($env:ASPEN_WORKBENCH_PYTHON) {
    $exe = Join-Path (Split-Path -Parent $env:ASPEN_WORKBENCH_PYTHON) 'aspen-mcp.exe'
} else {
    # Where the cache is: uv itself says (it knows a cache-dir set in uv.toml); else
    # UV_CACHE_DIR; else uv's default for this user.
    $cache = $null
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        try { $cache = (& uv cache dir 2>$null | Select-Object -First 1) } catch { $cache = $null }
    }
    if (-not $cache) {
        $cache = if ($env:UV_CACHE_DIR) { $env:UV_CACHE_DIR } else { Join-Path $env:LOCALAPPDATA 'uv\cache' }
    }
    # The highest aspen-mcp version there; among equals the newest folder.
    $envs = @(Get-ChildItem (Join-Path $cache 'archive-v0') -Directory -ErrorAction SilentlyContinue |
        Where-Object { (Test-Path (Join-Path $_.FullName 'Scripts\aspen-mcp.exe')) -and
                       (Test-Path (Join-Path $_.FullName 'Lib\site-packages\aspen_mcp\server.py')) } |
        ForEach-Object {
            $di = Get-ChildItem (Join-Path $_.FullName 'Lib\site-packages') -Directory -Filter 'aspen_mcp-*.dist-info' |
                Select-Object -First 1
            $ver = [version]'0.0'
            if ($di -and $di.Name -match '^aspen_mcp-(\d+(\.\d+)+)') { $ver = [version]$Matches[1] }
            [pscustomobject]@{ Dir = $_.FullName; Version = $ver; Time = $_.LastWriteTime }
        } | Sort-Object Version, Time -Descending)
    if (-not $envs) {
        Stop-With "No installed aspen-mcp environment was found under $cache for user $env:USERNAME.`nRun the plugin's setup once (online): scripts\install.ps1."
    }
    if ($envs[0].Version -lt $min) {
        Stop-With "The installed aspen-mcp is $($envs[0].Version); the workbench without an AI client needs $min or later.`nUpdate the plugin and run its setup once (online): scripts\install.ps1."
    }
    $exe = Join-Path $envs[0].Dir 'Scripts\aspen-mcp.exe'
}
if (-not (Test-Path -LiteralPath $exe)) { Stop-With "Not found: $exe" }

$env:UV_OFFLINE = '1'            # the window's pywebview comes from uv's cache, never the network
$env:PYTHONWARNINGS = 'ignore'
$env:PYTHONUNBUFFERED = '1'
$ErrorActionPreference = 'Continue'   # the server's stderr lines are not errors of this script
& $exe --workbench @args
exit $LASTEXITCODE
