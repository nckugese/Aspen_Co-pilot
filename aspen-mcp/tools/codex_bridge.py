"""Ask AI into a running Codex session, through Codex's app-server (the Codex side of the
Claude Code channel in server.py).

Codex drops what an MCP server pushes, but its app-server takes a turn from any client.
plugin/scripts/codex-workbench.ps1 runs Codex as

    codex app-server --listen ws://127.0.0.1:<port>        (the agent; it starts this server)
    codex --remote ws://127.0.0.1:<port>                   (the screen the user types in)

and records the app-server in ~/.aspen-mcp/codex-app-servers/<pid>.json as {"url", "pid"}.
Codex passes an MCP server a filtered environment (not even CODEX_HOME), so this server finds
its app-server by that record: the one whose process is its own ancestor. An Ask AI request
then starts a turn (``turn/start``) in the conversation loaded there, or joins the running
one (``turn/steer``). The screen shows it as the user's message and the AI answers at once;
an approval it needs is asked on that screen. Checked on Codex CLI 0.146 and 0.159.

This relies on Codex's app-server, which Codex marks experimental: a later Codex may change
or drop it. The Ask AI text is sent as the user's own turn, so Codex treats it exactly as if
the user had typed it.

A minimal websocket client (RFC 6455, client side, text frames only) keeps this on the
standard library: the server's own dependencies bring none.
"""
from __future__ import annotations

import asyncio
import base64
import ctypes
import importlib.metadata
import json
import os
import struct
import time
from pathlib import Path
from urllib.parse import urlsplit

URL_ENV = "ASPEN_MCP_CODEX_APP_SERVER"          # overrides the record (other launchers)
RECORDS = Path.home() / ".aspen-mcp" / "codex-app-servers"
TIMEOUT = 15.0
RETRY_S = 3.0
MAX_FRAME = 16 * 1024 * 1024                    # refuse a frame or message larger than this
_retry = {"at": 0.0}
_found: dict = {}

try:
    _VERSION = importlib.metadata.version("aspen-mcp")
except importlib.metadata.PackageNotFoundError:
    _VERSION = "unknown"


def _loopback(u: str) -> str | None:
    """Loopback only: the app-server takes turns from anyone who reaches it."""
    p = urlsplit(u.strip())
    ok = p.scheme == "ws" and p.hostname in ("127.0.0.1", "localhost", "::1") and p.port
    return u.strip() if ok else None


def _ancestors() -> list[int]:
    """This process's parent chain (Windows toolhelp snapshot); [] elsewhere or on error."""
    if os.name != "nt":
        return []

    class PE(ctypes.Structure):
        _fields_ = [("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong),
                    ("th32ProcessID", ctypes.c_ulong), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", ctypes.c_ulong), ("cntThreads", ctypes.c_ulong),
                    ("th32ParentProcessID", ctypes.c_ulong), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", ctypes.c_ulong), ("szExeFile", ctypes.c_wchar * 260)]
    k32 = ctypes.windll.kernel32
    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    if not snap or snap == ctypes.c_void_p(-1).value:
        return []
    parent = {}
    try:
        e = PE()
        e.dwSize = ctypes.sizeof(PE)
        more = k32.Process32FirstW(ctypes.c_void_p(snap), ctypes.byref(e))
        while more:
            parent[e.th32ProcessID] = e.th32ParentProcessID
            more = k32.Process32NextW(ctypes.c_void_p(snap), ctypes.byref(e))
    finally:
        k32.CloseHandle(ctypes.c_void_p(snap))
    chain, pid = [], os.getpid()
    while pid in parent and len(chain) < 32:
        pid = parent[pid]
        if not pid or pid in chain:
            break
        chain.append(pid)
    return chain


def url() -> str | None:
    """The app-server this server runs under, or None (plain ``codex`` or another client).
    Looked up once: the process tree does not change under a running server."""
    if "url" not in _found:
        u = os.environ.get(URL_ENV, "")
        _found["url"] = _loopback(u) if u.strip() else None
        if _found["url"] is None and RECORDS.is_dir():
            up = set(_ancestors())
            for f in RECORDS.glob("*.json"):
                try:
                    r = json.loads(f.read_text(encoding="utf-8-sig"))
                    if int(r.get("pid", 0)) in up:
                        _found["url"] = _loopback(str(r.get("url", "")))
                        break
                except (OSError, ValueError, TypeError):
                    continue
    return _found["url"]


class _WS:
    def __init__(self, reader, writer):
        self.r, self.w = reader, writer

    @classmethod
    async def connect(cls, u: str) -> "_WS":
        p = urlsplit(u)
        reader, writer = await asyncio.open_connection(p.hostname, p.port)
        key = base64.b64encode(os.urandom(16)).decode()
        writer.write((f"GET {p.path or '/'} HTTP/1.1\r\nHost: {p.hostname}:{p.port}\r\n"
                      "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        await writer.drain()
        head = await reader.readuntil(b"\r\n\r\n")
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            writer.close()
            raise ConnectionError(head.split(b"\r\n", 1)[0].decode(errors="replace"))
        return cls(reader, writer)

    async def _frame(self, op: int, data: bytes) -> None:
        mask = os.urandom(4)
        n = len(data)
        hdr = bytes([0x80 | op]) + (bytes([0x80 | n]) if n < 126 else
                                    bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536 else
                                    bytes([0x80 | 127]) + struct.pack(">Q", n))
        self.w.write(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
        await self.w.drain()

    async def send(self, obj: dict) -> None:
        await self._frame(0x1, json.dumps(obj).encode())

    async def recv(self) -> dict:
        buf = b""
        while True:
            b0, b1 = await self.r.readexactly(2)
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", await self.r.readexactly(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", await self.r.readexactly(8))[0]
            if n > MAX_FRAME or len(buf) + n > MAX_FRAME:
                raise ConnectionError(f"frame larger than {MAX_FRAME} bytes")
            mask = await self.r.readexactly(4) if b1 & 0x80 else None
            data = await self.r.readexactly(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            op = b0 & 0x0F
            if op == 0x8:
                raise ConnectionError("closed by the app-server")
            if op == 0x9:
                await self._frame(0xA, data)
                continue
            if op in (0x1, 0x0):
                buf += data
                if b0 & 0x80:
                    return json.loads(buf)

    def close(self) -> None:
        try:
            self.w.close()
        except Exception:
            pass


class _Rpc:
    """JSON-RPC over the socket; notifications and server requests are skipped, never answered
    (an approval belongs to the screen the user types in)."""

    def __init__(self, ws: _WS):
        self.ws, self.n = ws, 0

    async def call(self, method: str, params: dict) -> dict:
        self.n += 1
        await self.ws.send({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params})
        while True:
            m = await self.ws.recv()
            if m.get("id") == self.n and "method" not in m:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error'].get('message', m['error'])}")
                return m.get("result") or {}


def _pick(threads: list[dict]) -> dict | None:
    """The conversation the user is in: the most recently updated top-level thread. Not an
    ephemeral one -- Codex loads those for its own side work (0.159: one appears while an
    approval waits) -- nor a subagent's, which carries an agent role."""
    top = [t for t in threads if not t.get("ephemeral") and not t.get("agentRole") and not t.get("agentNickname")]
    return max(top, key=lambda t: t.get("updatedAt") or 0, default=None)


async def _push(u: str, text: str) -> str:
    ws = await _WS.connect(u)
    try:
        rpc = _Rpc(ws)
        await rpc.call("initialize", {"clientInfo": {"name": "aspen-workbench", "version": _VERSION}})
        await ws.send({"jsonrpc": "2.0", "method": "initialized"})
        ids = (await rpc.call("thread/loaded/list", {})).get("data") or []
        threads = []
        for tid in ids:
            t = {"id": tid}                          # a new, empty conversation has no rollout yet
            for turns in (True, False):              # (0.159: "list_turns is not supported yet")
                try:
                    t = (await rpc.call("thread/read", {"threadId": tid, "includeTurns": turns}))["thread"]
                    break
                except Exception:
                    pass
            threads.append(t)
        t = _pick(threads)
        if t is None:
            return "no-thread"
        inp = [{"type": "text", "text": text}]
        if (t.get("status") or {}).get("type") == "active":      # the AI is at work
            running = [x for x in t.get("turns") or [] if x.get("status") == "inProgress"]
            if not running:
                return "busy"                        # try again on a later pass
            await rpc.call("turn/steer", {"threadId": t["id"], "expectedTurnId": running[-1]["id"], "input": inp})
            return "steered"
        await rpc.call("turn/start", {"threadId": t["id"], "input": inp})
        return "started"
    finally:
        ws.close()


async def push(text: str) -> bool:
    """Put ``text`` into the Codex conversation as the user's message. False when there is no
    app-server, no conversation, or it failed: the workbench keeps the request for a later
    pass, and the plugin's Stop / UserPromptSubmit hooks hand it over otherwise."""
    u = url()
    if u is None or time.monotonic() < _retry["at"]:
        return False
    try:
        ok = await asyncio.wait_for(_push(u, text), TIMEOUT) in ("started", "steered")
    except Exception:
        ok = False
    _retry["at"] = 0.0 if ok else time.monotonic() + RETRY_S      # the sync loop asks every pass
    return ok
