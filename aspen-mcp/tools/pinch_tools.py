"""Pinch analysis tool — minimum-utility targets via OpenPinch in a dedicated subprocess.

The MCP server process never imports OpenPinch (needs Python >=3.14 and a heavy import
would stall the event loop / freeze Aspen COM). Computation runs out-of-process through
tools/pinch_runner.py. Full usage guide: docs/mcp/pinch-analysis.md.

The backend is `uv run --python 3.14 --with OpenPinch==0.4.5`, which provisions Python 3.14
and OpenPinch on first use and caches them -- nothing to install by hand beyond uv. A
`.venv-pinch/` beside the package is used instead when one is present (an optional override
for working on this code from a source checkout).

The first uv-backed call pays for that provisioning, so it is given a longer timeout than
the caller asked for; subsequent calls use the caller's timeout unchanged.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("tools.pinch_tools")

_ASPEN_MCP_DIR = Path(__file__).resolve().parent.parent
_VENV_PY = _ASPEN_MCP_DIR / ".venv-pinch" / "Scripts" / "python.exe"   # optional dev override
_RUNNER = _ASPEN_MCP_DIR / "tools" / "pinch_runner.py"
_MATCHES_RUNNER = _ASPEN_MCP_DIR / "tools" / "pinch_matches_runner.py"

# OpenPinch release the runner is written against. 0.5.4 and later removed
# ``pinch_analysis_service``, so an unpinned install fails with ImportError on every call.
# 0.4.5 is also the release the Linnhoff 4-stream check in docs/mcp/pinch-analysis.md was
# verified with.
_OPENPINCH = "OpenPinch==0.4.5"

# Seconds allowed on top of the caller's timeout for the one-off `uv` provisioning of
# Python 3.14 + OpenPinch. Flipped off once any uv-backed run has succeeded.
_PROVISION_GRACE = 420
_uv_warmed = False

_SETUP_HINT = (
    "no pinch backend available. Install uv, which provisions Python 3.14 and OpenPinch\n"
    "automatically on first use:\n"
    "  winget install --id=astral-sh.uv -e\n"
    "Then restart the MCP client."
)


def _find_uv() -> str | None:
    """Absolute path to the uv executable, or None.

    `UV` first: uv exports its own path to child processes, so when this server was
    launched through `uvx` the variable is both present and exact. PATH is checked only as
    a fallback -- a fresh `winget install` updates PATH for *new* shells and creates no
    shim, so an already-running client inherits a PATH without uv on it and
    `shutil.which` would say uv is missing while uv is in fact the thing running us.
    """
    env_uv = os.environ.get("UV")
    if env_uv and os.path.isfile(env_uv):
        return env_uv
    return shutil.which("uv")


def _runner_cmd(runner: Path) -> list[str] | None:
    """argv that executes `runner` under a Python that has OpenPinch (uv, or a dev
    `.venv-pinch` when present), or None if neither is available."""
    if _VENV_PY.exists():
        return [str(_VENV_PY), str(runner)]
    uv = _find_uv()
    if uv:
        # --no-project stops uv from adopting aspen-mcp/pyproject.toml as the project,
        # which would pin the interpreter to the server's own environment.
        return [uv, "run", "--python", "3.14", "--with", _OPENPINCH, "--no-project",
                "python", str(runner)]
    return None


def _effective_timeout(cmd: list[str], timeout: int) -> int:
    """Caller's timeout, plus a one-off grace period while uv provisions its environment."""
    if _uv_warmed or _VENV_PY.exists():
        return timeout
    return timeout + _PROVISION_GRACE if cmd and cmd[0].endswith(("uv", "uv.exe")) else timeout


def _mark_warmed(cmd: list[str]) -> None:
    global _uv_warmed
    if cmd and cmd[0].endswith(("uv", "uv.exe")):
        _uv_warmed = True


def _check(streams: list[dict]) -> str | None:
    if not streams:
        return "Error: 'streams' is empty — provide the thermal stream table."
    for i, s in enumerate(streams):
        missing = [k for k in ("name", "t_supply", "t_target", "heat_flow_kw") if k not in s]
        if missing:
            return f"Error: stream #{i} ({s.get('name', '?')}) missing fields {missing}."
    return None


def _run(runner: Path, job: dict, timeout: int, what: str, error_from: str) -> dict | str:
    """The runner's JSON result, or an "Error: ..." string. It blocks: async code calls it
    through asyncio.to_thread."""
    cmd = _runner_cmd(runner)
    if cmd is None:
        return f"Error: {_SETUP_HINT}"
    limit = _effective_timeout(cmd, timeout)
    try:
        proc = subprocess.run(cmd, input=json.dumps(job), capture_output=True, text=True, timeout=limit)
    except subprocess.TimeoutExpired:
        if limit > timeout:
            return (f"Error: {what} exceeded {limit}s while uv was provisioning "
                    "Python 3.14 + OpenPinch. Retry — provisioning resumes from cache.")
        return f"Error: {what} exceeded {timeout}s."
    _mark_warmed(cmd)
    if proc.returncode != 0:
        logger.error("%s rc=%s stderr=%s", what, proc.returncode, proc.stderr[-2000:])
        return f"Error: {what} failed (rc={proc.returncode}): {proc.stderr[-800:]}"
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return f"Error: {what} returned non-JSON output: {proc.stdout[:500]}"
    if not result.get("ok"):
        logger.error("%s error: %s\n%s", error_from, result.get("error"), result.get("trace", ""))
        return f"Error from {error_from}: {result.get('error')}"
    return result


def targets(streams: list[dict], dt_cont_default: float = 5.0, project_name: str = "Plant",
            include_curves: bool = False, utilities: list[dict] | None = None,
            timeout: int = 120) -> dict | str:
    """OpenPinch's targets (and composite curves) as data, or an "Error: ..." string."""
    bad = _check(streams)
    if bad:
        return bad
    job: dict = {"streams": streams, "dt_cont_default": dt_cont_default,
                 "project_name": project_name, "include_curves": include_curves}
    if utilities:
        job["utilities"] = utilities
    return _run(_RUNNER, job, timeout, "pinch runner", "OpenPinch")


def matches(streams: list[dict], dt_cont_default: float = 5.0,
            forbidden_pairs: list[list[str]] | None = None, weights: dict | None = None,
            extra_units: int = 0, n_alternatives: int = 8, timeout: int = 180) -> dict | str:
    """Minimum-match suggestions per pinch region as data, or an "Error: ..." string."""
    bad = _check(streams)
    if bad:
        return bad
    job: dict = {"streams": streams, "dt_cont_default": dt_cont_default,
                 "extra_units": extra_units, "n_alternatives": n_alternatives}
    if forbidden_pairs:
        job["forbidden_pairs"] = forbidden_pairs
    if weights:
        job["weights"] = weights
    return _run(_MATCHES_RUNNER, job, timeout, "matches runner", "matches MILP")


def pinch_analysis(
    streams: list[dict],
    dt_cont_default: float = 5.0,
    project_name: str = "Plant",
    include_curves: bool = False,
    utilities: list[dict] | None = None,
    timeout: int = 120,
) -> str:
    result = targets(streams, dt_cont_default, project_name, include_curves, utilities, timeout)
    if isinstance(result, str):
        return result

    lines = [
        f"Pinch targeting '{project_name}' "
        f"({len(streams)} streams, default dt_cont={dt_cont_default} C per side):"
    ]
    for t in result["targets"]:
        pin = t.get("pinch_shifted_C") or {}
        lines.append(
            f"  [{t['name']}] Qh_min={_fmt(t['Qh_kW'])} kW | Qc_min={_fmt(t['Qc_kW'])} kW | "
            f"max recovery={_fmt(t['Qrecovery_kW'])} kW | pinch(shifted)={_fmt(pin.get('hot'))} C"
        )
        hu, cu = t.get("hot_utilities") or [], t.get("cold_utilities") or []
        if hu:
            lines.append("    hot utilities: " + ", ".join(f"{u['name']}={_fmt(u['kW'])} kW" for u in hu))
        if cu:
            lines.append("    cold utilities: " + ", ".join(f"{u['name']}={_fmt(u['kW'])} kW" for u in cu))
    if result.get("notes"):
        lines.append("  notes: " + "; ".join(result["notes"]))
    lines.append(
        "Actual pinch temps = shifted +/- dt_cont (hot side above, cold side below). "
        "Compare Qh_min/Qc_min against current utility duties for savings potential."
    )
    lines.append("JSON: " + json.dumps({"targets": result["targets"]}, ensure_ascii=False))
    if include_curves and result.get("curves"):
        lines.append("CURVES_JSON: " + json.dumps(result["curves"], ensure_ascii=False))
    return "\n".join(lines)


def _fmt(x) -> str:
    if x is None:
        return "?"
    try:
        return f"{float(x):,.1f}"
    except (TypeError, ValueError):
        return str(x)


def pinch_matches(
    streams: list[dict],
    dt_cont_default: float = 5.0,
    forbidden_pairs: list[list[str]] | None = None,
    weights: dict | None = None,
    extra_units: int = 0,
    n_alternatives: int = 8,
    timeout: int = 180,
) -> str:
    result = matches(streams, dt_cont_default, forbidden_pairs, weights, extra_units,
                     n_alternatives, timeout)
    if isinstance(result, str):
        return result

    lines = [
        f"Match suggestions (min-matches transshipment MILP, exhaustive enumeration) — "
        f"Qh_min={_fmt(result['Qh_min_kW'])} kW | Qc_min={_fmt(result['Qc_min_kW'])} kW | "
        f"pinch(shifted)={result['pinch_shifted_C']} C"
    ]
    for reg in result["regions"]:
        tag = "above pinch" if reg.get("above_pinch") else f"region {reg['region']}"
        if reg["n_min"] is None:
            lines.append(
                f"  [{tag} | shifted {reg['shifted_temp_range_C'][0]}→{reg['shifted_temp_range_C'][1]} C] "
                "INFEASIBLE under the given forbidden_pairs — the minimum-utility target "
                "cannot be met in this region; relax an exclusion or accept extra utility."
            )
            continue
        lines.append(
            f"  [{tag} | shifted {reg['shifted_temp_range_C'][0]}→{reg['shifted_temp_range_C'][1]} C] "
            f"minimum matches = {reg['n_min']}; alternatives found = {len(reg['alternatives'])}"
        )
        for a_no, alt in enumerate(reg["alternatives"], 1):
            parts = []
            for m in alt["matches"]:
                tag = ""
                if m["is_utility"]:
                    tag = " [utility]"
                elif m.get("pinch_check") == "ok":
                    tag = " [pinch: ok]"
                elif m.get("pinch_check") == "needs_split":
                    tag = " [pinch: NEEDS SPLIT]"
                parts.append(f"{m['hot']} ↔ {m['cold']} ({_fmt(m['duty_kw'])} kW){tag}")
            lines.append(f"    option {a_no}: " + "; ".join(parts))
    lines.append(
        "Every alternative meets the minimum-utility targets; the per-region lists are "
        "mathematically exhaustive (integer-cut enumeration). Rank them by implementability "
        "(recycle-loop crossing, distance, materials) before implementing — see "
        "docs/mcp/pinch-analysis.md."
    )
    lines.append("JSON: " + json.dumps(result, ensure_ascii=False))
    return "\n".join(lines)
