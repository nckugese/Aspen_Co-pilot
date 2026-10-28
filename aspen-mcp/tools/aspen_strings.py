"""AspenTech's display strings, read once from the user's own Aspen Plus installation.

The strings belong to AspenTech, so this project never ships them:
the repo and the wheel hold only this extractor. On first use it reads the form-engine
catalog ``AspenTech.AspenPlus.Localization.dll`` of the Aspen that COM starts, with
PowerShell reflection in a subprocess, and writes

    ~/.aspen-mcp/aspen-strings/
        status.json          {"state": running|ok|failed, "aspen", "why", "t", "dir", "counts"}
        extract.lock         O_CREAT|O_EXCL; one extraction at a time across servers
        <version>/           e.g. V15.0; the newest KEEP folders are kept
            source.json      {dll, size, mtime, file_version, extractor, counts}: a changed DLL
                             (a patch) or a new EXTRACTOR means extract again
            labels.json      {"v", "aspen", "types", "options", "vars", "headers"} (see build())
            prompts.tsv.gz   <filepnum>\\t<prompt id>\\t<text>: the GUI's prompt and rule texts,
                             the catalog of tools/gui_rules.py (prompts_file())

``ensure()`` returns at once and extracts on a daemon thread; nothing here touches COM or
the event loop. A failure is recorded in status.json and nothing else changes: labels fall
back to the glossary and the codes. Pure stdlib, no I/O at import.
"""
from __future__ import annotations

import base64
import gzip
import io
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

try:
    import winreg
except ImportError:                    # not Windows: no Aspen, extraction reports failed
    winreg = None

logger = logging.getLogger(__name__)

ROOT = Path.home() / ".aspen-mcp"      # read at call time, so it can be pointed elsewhere
EXTRACTOR = 4                          # bump when build() or the header keys the sheet table names change: every folder re-extracts
KEEP = 2                               # version folders kept
TIMEOUT_S = 600
LOCK_STALE_S = 900
RETRY_FAILED_S = 86400                 # ensure() retries a failed extraction after this
DESC_MAX = 160
MATCH_NAMES = True                     # fill display names at all
DLL_NAME = "AspenTech.AspenPlus.Localization.dll"
CONTAINERS = ("ApwnRecTypeResource", "ApwnComboResource", "ApwnComboPromptResource",
              "ManipulatedVariablesResources", "PromptResources", "Properties.Resources",
              "WpfFormsResources", "ApwnResources", "SolidBlocksResources")
_VARS = "sensitivity_fvn_variable_"
_PROMPT_KEY = re.compile(r"FILEPNUM_(\d+)_Prompt_(\d+)")
_FORM_TYPE = re.compile(r"MM([A-Za-z0-9]+?)_")
_SEG = re.compile(r"[A-Za-z0-9]+")
_VER = re.compile(r"\bV(\d+(?:\.\d+)*)\b")
_CAMEL = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")
_NAV = "Browser"                       # ApwnResources' navigation-pane titles: BrowserTraySizing -> "Tray Sizing"

_LOCK = threading.Lock()
_thread: threading.Thread | None = None
_done = False                          # this process already ran (or skipped) its extraction

# Container short names and the output path are substituted; values are written only when
# they are strings; the two form containers are read for their *_Display_* keys only.
_SCRIPT = r"""
$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'
try {
  $dll = '@DLL@'; $out = '@OUT@'
  $want = @(@WANT@)
  $asm = [Reflection.Assembly]::LoadFile($dll)
  $sw = New-Object IO.StreamWriter($out, $false, (New-Object Text.UTF8Encoding($false)))
  $sw.WriteLine("#meta`tfile_version`t" + [Diagnostics.FileVersionInfo]::GetVersionInfo($dll).FileVersion)
  foreach ($n in $asm.GetManifestResourceNames()) {
    $short = $null
    foreach ($w in $want) { if ($n.EndsWith('.' + $w + '.resources')) { $short = $w } }
    if (-not $short) { continue }
    $disp = ($short -eq 'Properties.Resources') -or ($short -eq 'WpfFormsResources')
    $r = New-Object Resources.ResourceReader($asm.GetManifestResourceStream($n))
    $e = $r.GetEnumerator()
    while ($e.MoveNext()) {
      try { $k = [string]$e.Key; $v = $e.Value } catch { continue }
      if (-not ($v -is [string])) { continue }
      if ($disp -and $k.IndexOf('_Display_') -lt 0) { continue }
      $sw.WriteLine($short + "`t" + ($k -replace "[`r`n`t]", ' ') + "`t" + ($v -replace "[`r`n`t]", ' '))
    }
    $r.Close()
  }
  $sw.Close()
} catch { [Console]::Error.WriteLine($_.Exception.Message); exit 3 }
"""


class _Fail(Exception):
    """An extraction failure; its text is the status's "why"."""


# ----------------------------------------------------------------------------- locating
def _reg_default(subkey: str) -> str | None:
    """HKEY_CLASSES_ROOT\\<subkey> default value, or None (a module attribute so it can be overridden)."""
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, subkey) as k:
            v = winreg.QueryValueEx(k, "")[0]
        return v if isinstance(v, str) and v else None
    except OSError:
        return None


def _vkey(text: str) -> tuple:
    m = _VER.search(text)
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def _version(text: str) -> str | None:
    m = _VER.search(text)
    return "V" + m.group(1) if m else None


def find_dll() -> dict | None:
    """{"dll", "aspen", "how"} for the Aspen whose strings to use, or None. In order:
    env ASPEN_LOCALIZATION_DLL (returned even when missing: extraction then fails); the
    AspenPlus.exe that COM starts for Apwn.Document (so several installs follow COM); the
    newest %ProgramFiles%\\AspenTech\\AprSystem V*\\GUI\\Xeq."""
    env = os.environ.get("ASPEN_LOCALIZATION_DLL")
    if env:
        return {"dll": env, "aspen": _version(env) or "custom", "how": "env"}
    clsid = _reg_default(r"Apwn.Document\CLSID")
    server = _reg_default(rf"CLSID\{clsid}\LocalServer32") if clsid else None
    m = re.match(r'\s*"?(.+?\.exe)', server or "", re.I)     # "<...>\aspenplus.exe" -Automation
    if m:
        exe = Path(m.group(1))                                # ...\AspenTech\Aspen Plus V15.0\GUI\Xeq\
        product = next((p for p in exe.parents if _version(p.name)), None)
        if product:
            ver = _version(product.name)
            for cand in (exe.parent / DLL_NAME, product.parent / f"AprSystem {ver}" / "GUI" / "Xeq" / DLL_NAME):
                if cand.is_file():
                    return {"dll": str(cand), "aspen": ver, "how": "registry"}
    best = None                                               # (version key, folder, dll)
    for var in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        base = os.environ.get(var)
        if not base or not os.path.isdir(os.path.join(base, "AspenTech")):
            continue
        for d in Path(base, "AspenTech").glob("AprSystem V*"):
            f = d / "GUI" / "Xeq" / DLL_NAME
            if f.is_file() and (best is None or _vkey(d.name) > best[0]):
                best = (_vkey(d.name), d, f)
    if best:
        return {"dll": str(best[2]), "aspen": _version(best[1].name), "how": "glob"}
    return None


# ----------------------------------------------------------------------------- files
def _base() -> Path:
    return Path(ROOT) / "aspen-strings"


def _safe(ver: str) -> str:
    return re.sub(r"[^\w.-]", "_", ver) or "custom"


def _read_json(p: Path) -> dict | None:
    try:
        v = json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else None
    except (OSError, ValueError):
        return None


def _write_atomic(p: Path, data: bytes) -> None:
    tmp = p.with_name(p.name + f".{os.getpid()}.tmp")
    try:
        tmp.write_bytes(data)
        for i in range(10):                     # (Windows refuses the replace while a reader has the file open)
            try:
                os.replace(tmp, p)
                break
            except PermissionError:
                if i == 9:
                    raise
                time.sleep(0.3)
    finally:
        tmp.unlink(missing_ok=True)


def _dump(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _set_status(st: dict) -> dict:
    st = {"t": int(time.time() * 1000) / 1000, **st}      # rounded down: never in the future
    try:
        _base().mkdir(parents=True, exist_ok=True)
        _write_atomic(_base() / "status.json", _dump(st))
    except OSError as exc:
        logger.warning("aspen-strings: cannot write status: %s", exc)
    return st


def _lock_path() -> Path:
    return _base() / "extract.lock"


def _lock_age() -> float | None:
    try:
        return time.time() - _lock_path().stat().st_mtime
    except OSError:
        return None


def status() -> dict:
    """The last extraction's status.json ({"state": "none"} before any); a "running" whose
    extractor died (no live lock) reads as failed."""
    st = _read_json(_base() / "status.json") or {"state": "none"}
    if st.get("state") == "running":
        age = _lock_age()
        if age is None or age > LOCK_STALE_S:
            st = {**st, "state": "failed", "why": "extraction interrupted"}
    return st


def _newest(name: str) -> Path | None:
    """<name> of the status's Aspen version, else the newest one on disk, else None."""
    base, ver = _base(), status().get("aspen")
    if ver and (base / _safe(ver) / name).is_file():
        return base / _safe(ver) / name
    try:
        found = [p for p in base.glob(f"*/{name}") if p.is_file()]
        return max(found, key=lambda p: p.stat().st_mtime) if found else None
    except OSError:
        return None


def labels_file() -> Path | None:
    """labels.json of the status's Aspen version, else the newest one on disk, else None."""
    return _newest("labels.json")


def prompts_file() -> Path | None:
    """prompts.tsv.gz (tools/gui_rules.py's catalog), found the way labels_file() is."""
    return _newest("prompts.tsv.gz")


def _sig(dll: str) -> dict:
    st = os.stat(dll)
    return {"dll": dll, "size": st.st_size, "mtime": st.st_mtime_ns}


def _fresh(ver: str, sig: dict) -> dict | None:
    """source.json of this version folder when it matches the DLL and the extractor."""
    d = _base() / _safe(ver)
    src = _read_json(d / "source.json")
    if (src and src.get("extractor") == EXTRACTOR and src.get("size") == sig["size"]
            and src.get("mtime") == sig["mtime"] and (d / "labels.json").is_file()):
        return src
    return None


def prune(current: str, keep: int = KEEP) -> None:
    """Keep the current version folder and the newest others, up to `keep` in all."""
    try:
        dirs = [d for d in _base().iterdir() if d.is_dir() and d.name != _safe(current)]
    except OSError:
        return
    dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    for d in dirs[max(keep - 1, 0):]:
        shutil.rmtree(d, ignore_errors=True)


# ----------------------------------------------------------------------------- extraction
def _powershell() -> str | None:
    p = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32",
                     "WindowsPowerShell", "v1.0", "powershell.exe")
    return p if os.path.isfile(p) else shutil.which("powershell")


def _spawn(args: list, timeout: float):
    """The one subprocess this module starts (a module attribute so it can be overridden)."""
    return subprocess.run(args, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _run_powershell(dll: str, out: Path) -> None:
    """Dump the CONTAINERS of `dll` to `out` as <container>\\t<key>\\t<value> lines."""
    exe = _powershell()
    if not exe:
        raise _Fail("PowerShell not found")
    q = lambda s: str(s).replace("'", "''")  # noqa: E731
    script = (_SCRIPT.replace("@DLL@", q(dll)).replace("@OUT@", q(out))
              .replace("@WANT@", ",".join(f"'{c}'" for c in CONTAINERS)))
    enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        p = _spawn([exe, "-NoProfile", "-NonInteractive", "-EncodedCommand", enc], TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise _Fail(f"PowerShell timed out after {TIMEOUT_S} s") from None
    except OSError as exc:
        raise _Fail(f"PowerShell did not start: {exc}") from None
    if p.returncode != 0:
        err = (p.stderr or b"").decode("utf-8", "replace") if isinstance(p.stderr, bytes) else str(p.stderr or "")
        err = " ".join(re.sub(r"<[^>]+>|#< CLIXML|_x000D__x000A_", " ", err).split())
        raise _Fail(f"PowerShell exit {p.returncode}: {err[:200] or 'no message'}")
    if not out.is_file() or out.stat().st_size == 0:
        raise _Fail("PowerShell wrote nothing")


def _rows(raw: Path):
    with open(raw, encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\r\n").split("\t", 2)
            if len(parts) == 3:
                yield parts


def _clip(s: str | None) -> str | None:
    if not s:
        return None
    s = " ".join(s.split())
    return s if len(s) <= DESC_MAX else s[:DESC_MAX - 1].rstrip() + "\u2026"


def _norm(v: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", v.lower())


def _display(code: str, texts, desc: str | None) -> str | None:
    """The one form display text this code abbreviates, only when certain: every code
    segment has >= 3 characters and prefixes the same-position segment of exactly one of
    the block type's display texts, and every segment the text spells out further (TEMP ->
    Temperature) is a word of the option's own description. The last rule is ours: without
    it STD -> "StdVol" (it means Standard) and LOCAL -> "Localscript" slip through."""
    segs = _SEG.findall(code)
    if not MATCH_NAMES or not segs or any(len(s) < 3 for s in segs):
        return None
    hits = set()
    for t in texts:
        ts = _SEG.findall(t)
        if len(ts) == len(segs) and all(b.lower().startswith(a.lower()) for a, b in zip(segs, ts)):
            hits.add(t)
            if len(hits) > 1:
                return None
    if not hits:
        return None
    text = hits.pop()
    words = {w.lower() for w in _SEG.findall(desc or "")}
    longer = [b.lower() for a, b in zip(segs, _SEG.findall(text)) if a.lower() != b.lower()]
    return text if all(w in words for w in longer) else None


def _words(ident: str) -> list[str]:
    """'TraSiz' -> ['tra', 'siz']; 'Spec_Input' -> ['spec', 'input']; 'BlockO' -> ['block', 'o']."""
    return [w.lower() for w in _CAMEL.findall(ident)]


def nav_title(tail: str, nav: dict) -> str | None:
    """The navigation-pane title a form's class part abbreviates, only when one alone fits: each
    of its words begins the same-position word of one title key (TraSiz -> TraySizing: "Tray
    Sizing"), else, run together, it begins one key run together (Blocko -> BlockOptions). ``nav``:
    {key without "Browser": title}; a title all in capitals (USER, PURE-COMP: record types) is not one."""
    segs = _words(tail)
    if not segs:
        return None
    cands = [(_words(k), v) for k, v in nav.items() if v != v.upper()]
    hits = {v for ws, v in cands if len(ws) == len(segs) and all(w.startswith(s) for s, w in zip(segs, ws))}
    if not hits and len("".join(segs)) >= 4:
        hits = {v for ws, v in cands if "".join(ws).startswith("".join(segs))}
    return hits.pop() if len(hits) == 1 else None


def build(rows, aspen: str) -> tuple[dict, list, dict]:
    """(labels, prompts, counts) from <container, key, value> rows.

    labels = {"v": 1, "aspen", "types": {"RADFRAC": "RadFrac"},
              "options": {TYPE: {FIELD: {code: [display name | None, description | None]}}},
              "vars": {"NSTAGE": "How many stages the column has"},
              "headers": {"MMRCSTR_Setup_MMFHeader2": "Kinetics"},
              "forms": {"MMRadfrac_TraSiz": "Tray Sizing"}}
    An option comes from ApwnComboResource ``block_<type>_<field>_<norm(code)>`` -> code: the
    type is the longest known block type prefix, the key must end in norm(value), else the
    row is dropped. A header is the title of a form sheet (ApwnResources; the solids blocks'
    in SolidBlocksResources), kept only for the keys tools/gui_sheets.py's table names; a form's
    is the navigation pane's title its class abbreviates (nav_title of the Browser* keys).
    prompts = [(filepnum, prompt id, text)] of PromptResources."""
    from tools import gui_sheets                     # (it imports this module)
    want = gui_sheets.header_keys()
    types, combo, cprompt, vars_, prompts, display, headers, nav = {}, [], {}, {}, [], {}, {}, {}
    for short, key, val in rows:
        if short == "ApwnRecTypeResource":
            if key.startswith("rectype_blocks_") and val.strip():
                types[key[15:].upper()] = val.strip()
        elif short == "ApwnComboResource":
            if key.startswith("block_"):
                combo.append((key[6:], val))
        elif short == "ApwnComboPromptResource":
            if key.startswith("block_") and key.endswith("_prompt"):
                cprompt[key[6:-7]] = val
        elif short == "ManipulatedVariablesResources":
            if key.startswith(_VARS) and key.endswith("_prompt") and val.strip():
                vars_[key[len(_VARS):-7].upper()] = _clip(val)
        elif short in ("ApwnResources", "SolidBlocksResources"):
            if key in want and val.strip() and key not in headers:
                headers[key] = _clip(val)
            if short == "ApwnResources" and key.startswith(_NAV) and val.strip()[:1].isalnum():
                nav[key[len(_NAV):].lstrip("_")] = _clip(val)
        elif short == "PromptResources":
            m = _PROMPT_KEY.fullmatch(key)
            if m:
                prompts.append((int(m.group(1)), int(m.group(2)), val.strip()))
        elif "_Display_" in key:
            m, text = _FORM_TYPE.match(key), val.strip()
            if m and text and not text.endswith(":"):
                display.setdefault(m.group(1).upper(), set()).add(text)
    prefixes = sorted((t.lower() for t in types), key=len, reverse=True)
    options, named, fields = {}, 0, set()
    for rest, code in combo:
        t = next((p for p in prefixes if rest.startswith(p + "_")), None)
        tail = "_" + _norm(code)
        body = rest[len(t) + 1:] if t else ""
        if not t or not code.strip() or not body.endswith(tail) or len(body) <= len(tail):
            continue
        T, field = t.upper(), body[:-len(tail)].upper()
        name = _display(code, display.get(T, ()), cprompt.get(rest))
        named += name is not None
        fields.add((T, field))
        options.setdefault(T, {}).setdefault(field, {})[code] = [name, _clip(cprompt.get(rest))]
    forms = {f: t for f, t in ((f, nav_title(tail, nav)) for f, tail in gui_sheets.form_tails().items()) if t}
    counts = {"types": len(types), "options": sum(len(c) for f in options.values() for c in f.values()),
              "named": named, "fields": len(fields), "vars": len(vars_), "prompts": len(prompts),
              "headers": len(headers), "forms": len(forms)}
    labels = {"v": 1, "aspen": aspen, "types": types, "options": options, "vars": vars_, "headers": headers,
              "forms": forms}
    return labels, prompts, counts


def _gz(prompts: list) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as g:   # mtime 0: same input, same bytes
        g.write("".join(f"{fp}\t{pid}\t{text}\n" for fp, pid, text in prompts).encode("utf-8"))
    return buf.getvalue()


def _acquire() -> bool:
    _base().mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(_lock_path(), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            age = _lock_age()
            if age is None or age <= LOCK_STALE_S:
                return False
            _lock_path().unlink(missing_ok=True)               # its extractor died
    return False


def extract(force: bool = False, auto: bool = False) -> dict:
    """Extract now, in this thread (the CLI's --extract-strings; ensure()'s worker). Returns
    the new status, or {"state": "busy"} when another process holds the lock. Never raises."""
    try:
        found = find_dll()
        if not found:
            return _skip_or_fail(auto, None, None, "no Aspen Plus installation found")
        ver, dll = _safe(found["aspen"] or "custom"), found["dll"]
        try:
            sig = _sig(dll)
        except OSError:
            return _skip_or_fail(auto, ver, None, f"{DLL_NAME} not found at {dll}")
        if not force and _fresh(ver, sig):
            st = status()
            return st if st.get("state") == "ok" and st.get("aspen") == ver else _ok(ver)
        if auto:
            prev = status()
            if prev.get("state") == "failed" and prev.get("sig") == sig and prev.get("extractor") == EXTRACTOR \
                    and time.time() - prev.get("t", 0) < RETRY_FAILED_S:
                return prev
        if not _acquire():
            return {"state": "busy", "aspen": ver, "why": "another process is extracting"}
    except Exception as exc:  # noqa: BLE001 -- extraction never fails a caller
        logger.warning("aspen-strings: %s", exc)
        return _set_status({"state": "failed", "why": f"{type(exc).__name__}: {exc}"})
    d, t0 = _base() / ver, time.time()
    raw = d / "raw.tsv.tmp"
    try:
        if not force and _fresh(ver, sig):                   # another process just finished
            return _ok(ver)
        _set_status({"state": "running", "aspen": ver})
        d.mkdir(parents=True, exist_ok=True)
        _run_powershell(dll, raw)
        meta, rows = {}, []
        for r in _rows(raw):
            if r[0] == "#meta":
                meta[r[1]] = r[2]
            else:
                rows.append(r)
        labels, prompts, counts = build(rows, found["aspen"] or ver)
        if not counts["types"] or not counts["options"]:
            raise _Fail(f"no block options in {DLL_NAME} (a different container layout?)")
        _write_atomic(d / "labels.json", _dump(labels))
        _write_atomic(d / "prompts.tsv.gz", _gz(prompts))
        _write_atomic(d / "source.json", _dump({**sig, "file_version": meta.get("file_version"),
                                                "extractor": EXTRACTOR, "counts": counts,
                                                "seconds": round(time.time() - t0, 1)}))
        prune(ver)
        return _ok(ver)
    except Exception as exc:  # noqa: BLE001
        why = str(exc) if isinstance(exc, _Fail) else f"{type(exc).__name__}: {exc}"
        logger.warning("aspen-strings: extraction failed: %s", why)
        return _set_status({"state": "failed", "aspen": ver, "why": why, "sig": sig, "extractor": EXTRACTOR})
    finally:
        raw.unlink(missing_ok=True)
        _lock_path().unlink(missing_ok=True)


def _ok(ver: str) -> dict:
    d = _base() / ver
    src = _read_json(d / "source.json") or {}
    return _set_status({"state": "ok", "aspen": ver, "dir": str(d), "counts": src.get("counts", {})})


def _skip_or_fail(auto: bool, ver, sig, why: str) -> dict:
    prev = status()
    if auto and prev.get("state") == "failed" and prev.get("why") == why \
            and time.time() - prev.get("t", 0) < RETRY_FAILED_S:
        return prev
    return _set_status({"state": "failed", "aspen": ver, "why": why, "sig": sig, "extractor": EXTRACTOR})


def _worker() -> None:
    global _done
    r = extract(auto=True)
    if r.get("state") != "busy":                            # busy: let a later ensure() look again
        _done = True


def ensure() -> dict:
    """Make sure the strings of the current Aspen are on disk: starts the extraction on a
    daemon thread when this process has not yet, and returns the status at once."""
    global _thread
    try:
        with _LOCK:
            if not _done and (_thread is None or not _thread.is_alive()):
                _thread = threading.Thread(target=_worker, name="aspen-strings", daemon=True)
                _thread.start()
        return status()
    except Exception as exc:  # noqa: BLE001
        return {"state": "failed", "why": f"{type(exc).__name__}: {exc}"}


def check_line() -> str:
    """One line for `aspen-mcp --check`."""
    st = status()
    s = st.get("state", "none")
    if s == "ok":
        c = st.get("counts", {})
        return (f"aspen-strings {st.get('aspen')} ok ({c.get('options', 0):,} options, "
                f"{c.get('vars', 0):,} vars) {st.get('dir')}")
    if s == "failed":
        return f"aspen-strings failed: {st.get('why')}"
    if s == "running":
        since = time.strftime("%H:%M", time.localtime(st.get("t", 0)))
        return f"aspen-strings {st.get('aspen')} running (since {since})"
    return (f"aspen-strings none (read from your Aspen on first use; `aspen-mcp --extract-strings` "
            f"does it now) {_base()}")
