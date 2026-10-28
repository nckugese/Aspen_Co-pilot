#Requires -Version 5.1
<#
    Stop / UserPromptSubmit hook: hand the AI the Aspen Workbench's waiting Ask AI requests
    when the client takes no message the server pushes -- Codex started as plain `codex`, or
    Claude Code without channels -- and record the AI's turn for the window.

      -Event stop    the AI is about to end its turn: keep it going with the requests
                     (decision "block" + reason: both clients continue with the reason as the
                     next prompt)
      -Event prompt  the user typed something: the requests ride along as additionalContext

    A request is handed once. It is left alone when the window says the client takes pushed
    requests (state.json "listening") and this one was pushed ("delivered"). The hook acts only
    in the session whose aspen-plus server serves the window: owner.json's pid and this hook
    must share an ancestor that is the client itself (claude / codex / node), so another
    Claude Code or Codex session on the machine never takes the requests.
    Handed requests go to ~/.aspen-mcp/workbench/asks-handed.json ({note_id: time}); the server
    marks them delivered from it (aspen-mcp/tools/workbench_tools.py _handed).

    The AI's turn, while a server serves the window (its heartbeat is fresh): a prompt, or a stop
    that hands requests (the turn goes on), is its start; any other stop its end. Written to
    ~/.aspen-mcp/workbench/ai_turn.json {start, begin, stop, client, owner, mine} (begin: the
    turn's first start since its last stop; start moves on with a stop that hands requests); the server shows it
    in state.json (ai_turn), and the chat's "still working" line reads it (static/app-wait.js).
    "mine" caches, per client session_id, whether that session is the one serving the window,
    so the process walk below runs once per session and server, not on every prompt; a new
    server (owner) starts the file afresh. A stop while no server serves the window (closed)
    is still written for a session "mine" names, so a reopened window shows no stale turn.

    Contract: never break a session. Every failure path exits 0 and says nothing.
#>
param([string]$Event = 'stop', [string]$Client = 'claude')

$ErrorActionPreference = 'Stop'

function Out-Json($obj) {
    # ASCII only: the console code page must not mangle the text.
    $json = $obj | ConvertTo-Json -Compress -Depth 5
    $sb = New-Object System.Text.StringBuilder
    foreach ($ch in $json.ToCharArray()) {
        if ([int]$ch -gt 127) { [void]$sb.AppendFormat('\u{0:x4}', [int]$ch) } else { [void]$sb.Append($ch) }
    }
    Write-Output $sb.ToString()
}

function Save-Turn($path, $turn, [int]$ownerPid, $known) {
    # one small file, replaced whole (another session's hook may write it too: its own tmp);
    # a failure here never keeps the requests from being handed
    $tmp = "$path.$PID.tmp"
    try {
        $turn['owner'] = $ownerPid
        $turn['mine'] = $known
        [System.IO.File]::WriteAllText($tmp, ($turn | ConvertTo-Json -Compress -Depth 3))
        Move-Item -LiteralPath $tmp -Destination $path -Force
    } catch { try { [System.IO.File]::Delete($tmp) } catch {} }
}

function Save-StopUnseen($dir, $sid) {
    # No server serves the window (closed): a Stop of the session known to serve it last still
    # ends the turn, so a window reopened later does not show a turn long over as running.
    $path = Join-Path $dir 'ai_turn.json'
    $tmp = "$path.$PID.tmp"
    try {
        if (-not $sid -or -not (Test-Path -LiteralPath $path)) { return }
        $tj = [System.IO.File]::ReadAllText($path) | ConvertFrom-Json
        if (-not $tj.mine -or $tj.mine.$sid -ne $true) { return }
        $turn = [ordered]@{}
        foreach ($p in $tj.PSObject.Properties) { $turn[$p.Name] = $p.Value }
        $turn['stop'] = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
        [System.IO.File]::WriteAllText($tmp, ($turn | ConvertTo-Json -Compress -Depth 3))
        Move-Item -LiteralPath $tmp -Destination $path -Force
    } catch { try { [System.IO.File]::Delete($tmp) } catch {} }
}

try {
    $raw = ''
    try { $raw = [Console]::In.ReadToEnd() } catch {}
    $hook = $null
    if ($raw) { try { $hook = $raw | ConvertFrom-Json } catch {} }

    $sid = ''
    if ($hook -and $hook.session_id) { $sid = [string]$hook.session_id }

    $dir = Join-Path $env:USERPROFILE '.aspen-mcp\workbench'
    $statePath = Join-Path $dir 'state.json'
    $ownerPath = Join-Path $dir 'owner.json'
    # a server serves the window now: its heartbeat is seconds old (the turn is recorded only then)
    $live = $false
    try { $live = ([DateTime]::UtcNow - [System.IO.File]::GetLastWriteTimeUtc((Join-Path $dir 'heartbeat'))).TotalSeconds -lt 15 } catch {}
    if (-not $live -and $Event -eq 'stop') { Save-StopUnseen $dir $sid }
    if (-not (Test-Path -LiteralPath $statePath) -or -not (Test-Path -LiteralPath $ownerPath)) { exit 0 }

    $text = [System.IO.File]::ReadAllText($statePath)
    $asks = @()
    $open = @{}
    $handedPath = Join-Path $dir 'asks-handed.json'
    $handed = @{}
    if ($text -match '"status":\s*"open"') {                  # (the common case: nothing waits)
        $state = $text | ConvertFrom-Json
        if (Test-Path -LiteralPath $handedPath) {
            try {
                $h = [System.IO.File]::ReadAllText($handedPath) | ConvertFrom-Json
                foreach ($p in $h.PSObject.Properties) { $handed[$p.Name] = $p.Value }
            } catch {}
        }
        foreach ($s in $state.sessions.PSObject.Properties) {
            foreach ($n in @($s.Value.notes)) {
                if ($n -and $n.status -eq 'open') { $open[[string]$n.id] = $true }
                if (-not $n -or $n.status -ne 'open' -or $handed.ContainsKey([string]$n.id)) { continue }
                if ($state.listening -and $n.delivered) { continue }
                $asks += [pscustomobject]@{ id = [string]$n.id; session = $s.Name; text = [string]$n.text; target = $n.target
                                            event = [string]$n.event; answer_to = [string]$n.answer_to }
            }
        }
    }
    if ($asks.Count -eq 0 -and -not $live) { exit 0 }

    # Only the session whose server serves the window (known per client session: ai_turn.json "mine").
    $owner = [System.IO.File]::ReadAllText($ownerPath) | ConvertFrom-Json
    $ownerPid = [int]$owner.pid
    $turnPath = Join-Path $dir 'ai_turn.json'
    $turn = [ordered]@{}
    if (Test-Path -LiteralPath $turnPath) {
        try {
            $tj = [System.IO.File]::ReadAllText($turnPath) | ConvertFrom-Json
            foreach ($p in $tj.PSObject.Properties) { $turn[$p.Name] = $p.Value }
        } catch {}
    }
    $known = @{}
    if ($turn['owner'] -ne $ownerPid) {
        $turn = [ordered]@{}                                   # (a new server: its turn, and asked again)
    } elseif ($turn['mine']) {
        foreach ($p in $turn['mine'].PSObject.Properties) { $known[$p.Name] = [bool]$p.Value }
    }
    if ($sid -and $known.ContainsKey($sid)) {
        $isMine = $known[$sid]
    } else {
        $procs = @{}
        foreach ($p in Get-CimInstance Win32_Process -Property ProcessId, ParentProcessId, Name) { $procs[[int]$p.ProcessId] = $p }
        function Get-Chain([int]$id) {
            $chain = @(); $seen = @{}
            while ($procs.ContainsKey($id) -and -not $seen.ContainsKey($id) -and $chain.Count -lt 32) {
                $seen[$id] = $true
                $id = [int]$procs[$id].ParentProcessId
                if ($procs.ContainsKey($id)) { $chain += $id }
            }
            return $chain
        }
        $clientNames = 'claude.exe', 'codex.exe', 'node.exe'
        $mine = Get-Chain $PID | Where-Object { $clientNames -contains $procs[$_].Name }
        $server = Get-Chain $ownerPid
        $isMine = [bool]($mine | Where-Object { $server -contains $_ })
        if ($sid) {
            if ($known.Count -ge 16) { $known = @{} }
            $known[$sid] = $isMine
            if (-not $isMine -and $live) { Save-Turn $turnPath $turn $ownerPid $known }   # (asked once)
        }
    }
    if (-not $isMine) { exit 0 }

    $now = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
    if ($live) {
        # a stop that hands requests does not end the turn: the AI goes on with them
        if ($Event -eq 'stop' -and $asks.Count -eq 0) { $turn['stop'] = $now } else {
            # "begin": the turn's first start since its last stop (the window counts from it)
            $was = 0.0; $end = 0.0
            try { if ($turn['start']) { $was = [double]$turn['start'] }; if ($turn['stop']) { $end = [double]$turn['stop'] } } catch {}
            if (-not $turn['begin'] -or $end -ge $was) { $turn['begin'] = $now }
            $turn['start'] = $now
        }
        $turn['client'] = $Client
        Save-Turn $turnPath $turn $ownerPid $known
    }
    if ($asks.Count -eq 0) { exit 0 }

    $lines = foreach ($a in $asks) {
        $where = ''
        if ($a.target -and $a.target.kind) {
            $name = $a.target.name
            if (-not $name) { $name = $a.target.path }
            $where = ", $($a.target.kind) $name".TrimEnd()
        }
        # an event is the window telling (a proposal ended), a pick answers the AI's choices
        $kind = ''
        if ($a.event) { $kind = " [workbench event, not a user request: go on with the workflow, then close it with done]" }
        elseif ($a.answer_to) { $kind = " [the user's pick from the choices you gave on $($a.answer_to)]" }
        "- note_id $($a.id) (session $($a.session)$where)$($kind): $($a.text)"
    }
    $msg = "Ask AI from the Aspen Workbench: the user sent these requests from the workbench window.`n" +
           ($lines -join "`n") +
           "`nRead each one's tab with workbench_read, then answer in the window with " +
           'workbench_edit(note_replies=[{"id": note_id, "reply": ...}]) in the language of the request ' +
           '(an event: {"id": note_id, "done": true}).'

    foreach ($k in @($handed.Keys)) { if (-not $open.ContainsKey($k)) { $handed.Remove($k) } }   # answered: forget
    foreach ($a in $asks) { $handed[$a.id] = $now }
    $tmp = "$handedPath.tmp"
    [System.IO.File]::WriteAllText($tmp, ($handed | ConvertTo-Json -Compress))
    Move-Item -LiteralPath $tmp -Destination $handedPath -Force

    if ($Event -eq 'stop') {
        Out-Json ([ordered]@{ decision = 'block'; reason = $msg })
    } else {
        Out-Json ([ordered]@{ hookSpecificOutput = [ordered]@{ hookEventName = 'UserPromptSubmit'; additionalContext = $msg } })
    }
    exit 0
}
catch {
    exit 0
}
