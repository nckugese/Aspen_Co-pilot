"""Pinch-analysis runner — executed by a Python >=3.14 with OpenPinch, NOT the MCP server.

Reads a JSON job on stdin, runs OpenPinch targeting, writes a JSON result on stdout.
Runs in its own process so the MCP server never imports OpenPinch (a heavy import in the
server would stall the event loop and freeze Aspen COM). tools/pinch_tools.py starts it as

    uv run --python 3.14 --with OpenPinch==0.4.5 --no-project python tools/pinch_runner.py < job.json

Job format:
    {
      "project_name": "Plant",
      "dt_cont_default": 5.0,          # per-side dT contribution (dTmin = hot + cold side)
      "include_curves": false,
      "streams": [
        {"name": "PREHEAT", "t_supply": 40, "t_target": 130, "heat_flow_kw": 2100,
         "dt_cont": 5, "type": "cold", "zone": "Plant"}
      ],
      "utilities": [...]               # optional, raw OpenPinch UtilitySchema dicts
    }

Isothermal duties (condenser/reboiler, t_supply == t_target) are rejected by OpenPinch;
this runner represents them with a 1 degC span, direction taken from `type`
('hot' = releases heat, 'cold' = absorbs heat).
"""
from __future__ import annotations

import json
import sys
import traceback

ISO_SPAN_C = 1.0


def _v(x):
    """Unwrap OpenPinch {'value':..,'unit':..} dicts to the bare value."""
    if isinstance(x, dict) and "value" in x:
        return x["value"]
    return x


def _stream(raw: dict, dt_default: float):
    name = raw["name"]
    ts, tt = float(raw["t_supply"]), float(raw["t_target"])
    q = abs(float(raw["heat_flow_kw"]))
    note = None
    if ts == tt:
        typ = (raw.get("type") or "").lower()
        if typ == "hot":
            tt = ts - ISO_SPAN_C
        elif typ == "cold":
            tt = ts + ISO_SPAN_C
        else:
            raise ValueError(
                f"stream '{name}': isothermal (t_supply == t_target) needs "
                f"type='hot' or type='cold' to fix the direction"
            )
        note = f"isothermal duty represented as {ts}->{tt} degC"
    return {
        "zone": raw.get("zone", "Plant"),
        "name": name,
        "t_supply": {"value": ts, "unit": "degC"},
        "t_target": {"value": tt, "unit": "degC"},
        "heat_flow": {"value": q, "unit": "kW"},
        "dt_cont": {"value": float(raw.get("dt_cont", dt_default)), "unit": "degC"},
        "htc": {"value": float(raw.get("htc", 1.0)), "unit": "kW/m^2/degC"},
    }, note


def main() -> None:
    job = json.load(sys.stdin)
    from OpenPinch import pinch_analysis_service  # only in the runner's own environment

    dt_default = float(job.get("dt_cont_default", 5.0))
    streams, notes = [], []
    for raw in job["streams"]:
        s, note = _stream(raw, dt_default)
        streams.append(s)
        if note:
            notes.append(f"{raw['name']}: {note}")

    data = {"streams": streams}
    if job.get("utilities"):
        data["utilities"] = job["utilities"]

    out = pinch_analysis_service(data, project_name=job.get("project_name", "Plant"))
    d = out.model_dump(mode="json")

    targets, seen = [], set()
    for t in d.get("targets", []):
        pt = t.get("pinch_temp") or {}
        row = {
            "name": t.get("name"),
            "Qh_kW": _v(t.get("Qh")),
            "Qc_kW": _v(t.get("Qc")),
            "Qrecovery_kW": _v(t.get("Qr")),
            "pinch_shifted_C": {"hot": _v(pt.get("hot_temp")), "cold": _v(pt.get("cold_temp"))},
            "degree_of_integration_pct": _v(t.get("degree_of_integration")),
            "hot_utilities": [
                {"name": u.get("name"), "kW": _v(u.get("heat_flow"))}
                for u in (t.get("hot_utilities") or [])
            ],
            "cold_utilities": [
                {"name": u.get("name"), "kW": _v(u.get("heat_flow"))}
                for u in (t.get("cold_utilities") or [])
            ],
            "utility_cost": _v(t.get("utility_cost")),
            "num_units_target": _v(t.get("num_units")),
            "area_target": _v(t.get("area")),
        }
        # OpenPinch reports the project's targets, then each zone's: with one zone (every stream's
        # default) the zone's repeat the project's figures under the zone's name.
        key = json.dumps({**row, "name": str(row["name"]).split("/", 1)[-1]}, sort_keys=True)
        if key not in seen:
            seen.add(key)
            targets.append(row)

    result = {"ok": True, "targets": targets, "notes": notes}
    if job.get("include_curves"):
        result["curves"] = d.get("graphs")
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 — report everything to the MCP side
        json.dump(
            {"ok": False, "error": f"{type(exc).__name__}: {exc}",
             "trace": traceback.format_exc(limit=3)},
            sys.stdout,
        )
