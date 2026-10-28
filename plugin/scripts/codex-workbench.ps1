#Requires -Version 5.1
<#
    Start Codex so that an Ask AI request from the Aspen Workbench reaches it at once.

    Codex ignores what an MCP server pushes, but its app-server (experimental) takes a turn
    from any local client. This runs the agent as an app-server on a free loopback port and
    the screen the user types in against it (codex --remote), and records the app-server in
    ~/.aspen-mcp/codex-app-servers/<pid>.json. The aspen-plus server Codex starts finds that
    record by its own process tree (aspen-mcp/tools/codex_bridge.py) and puts each request
    into the conversation as the user's message.

    Any arguments go to the Codex screen (e.g. a first prompt). Plain `codex` still works; its
    requests reach the AI through the Stop / UserPromptSubmit hooks instead, when the AI ends
    a turn or the user types.

    The SessionStart hook keeps a shortcut to this script at ~/.aspen-mcp/codex-aspen.cmd.
#>
param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$CodexArgs)

$ErrorActionPreference = 'Stop'

$codex = Get-Command codex -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $codex) {
    Write-Host 'Codex CLI not found on PATH (npm install -g @openai/codex).'
    exit 1
}

$l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$l.Start(); $port = $l.LocalEndpoint.Port; $l.Stop()
$url = "ws://127.0.0.1:$port"

$records = Join-Path $env:USERPROFILE '.aspen-mcp\codex-app-servers'
New-Item -ItemType Directory -Force -Path $records | Out-Null
$srv = $null
$record = $null
try {
    $srv = Start-Process -FilePath $codex.Source -ArgumentList 'app-server', '--listen', $url `
        -WorkingDirectory (Get-Location).Path -WindowStyle Hidden -PassThru
    $record = Join-Path $records "$($srv.Id).json"
    [System.IO.File]::WriteAllText($record, (@{ url = $url; pid = $srv.Id; t = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() } | ConvertTo-Json -Compress))

    $ready = $false
    for ($i = 0; $i -lt 60 -and -not $ready; $i++) {
        Start-Sleep -Milliseconds 500
        if ($srv.HasExited) { break }
        try { $ready = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://127.0.0.1:$port/readyz").StatusCode -eq 200 } catch {}
    }
    if (-not $ready) {
        Write-Host "The Codex app-server did not start on $url; run plain 'codex' instead."
        exit 1
    }
    & $codex.Source --remote $url @CodexArgs
}
finally {
    if ($srv -and -not $srv.HasExited) { & taskkill.exe /PID $srv.Id /T /F 2>&1 | Out-Null }
    if ($record) { Remove-Item -LiteralPath $record -Force -ErrorAction SilentlyContinue }
}
