"""Aspen Workbench: a Scratch-style block editor over live Aspen sessions.

The window (``workbench/window.py``) is a separate process. This module is the server
side: it owns the workspace state, snapshots flowsheets, runs block programs, and applies
what the window and the LLM change.

One window serves every session, in tabs: one tab per model (``kind`` "model", ``mkey``
the model's id), its extra programs and the AI's proposals its sub-tabs (``parent``); finished
proposals no longer shown are kept per model in tools/prop_archive.py (History), and so is the model
tab's chat when it closes. A tab holds one program and shows the flowsheet of the session it is
bound to; its tabs share that session's Ask AI requests (notes). Runs belong to a tab. Tabs on
different sessions run at the same time, interleaved statement by statement (every COM call stays on one thread); a tab
whose session is busy waits in a queue, because two programs writing the same model would
spoil each other's results.

Workspace folder ``~/.aspen-mcp/workbench/``:

  state.json    written only here. The window renders it as soon as it changes.
  heartbeat     written every second while the sync loop runs, by a thread that keeps
                going while a call holds the loop: what the AI and programs are doing and
                when the loop last came round (tools/activity.py).
  events.jsonl  appended only by the window: edits, notes, tab changes, run requests.
  prefs.json    written only by the window: its panel sizes, drafts and one-time hints.
  runs/<tab>/   optimization results.

Every COM call stays on the MCP server's event-loop thread. Sync tools already run there,
and the sync loop that serves the window is an asyncio task on that loop, so nothing here
marshals Aspen objects across threads.

A program is a list of statements, each ``{"do": ..., "id": ...}``:

  set       {"path", "value" | "expr", "unit"?}   write an input (a number, text, or an
                                                   expression over variables)
  run       {"reinit"?}                            run the simulation; with reinit, from
                                                   initial estimates rather than the last results
  read      {"path", "as"}                         read a value into a variable
  calc      {"as", "expr", "unit"?}                compute a variable (tools/workbench_expr.py)
  def       {"name", "params", "expr"}             a function for expressions; defs apply
                                                   to the whole program wherever they sit
  log       {"text"}                               write a line to the run log
  if        {"left": {"path"}|{"var"}|{"expr"}, "op", "right", "then": [...], "else": [...]}
  repeat    {"times", "body": [...]}
  until     {"cond", "max"?, "body": [...]}        repeat until cond holds (checked first)
  sweep     {"path", "from", "to", "steps", "unit"?, "as"?, "finish"?, "body": [...]}
            steps = number of points, both ends included
  seek      {"path", "lower", "upper", "measure", "target", "unit"?, "tol"?, "max"?, "as"?,
             "finish"?, "body": [...]}             design spec: find the input value that
                                                   brings the measure expression to target
  optimize  {"algorithm", "eval_budget", "variables": [{"path", "lower", "upper"}],
             "objectives": [{"path", "direction"}], "constraints": [{"path", "lower"|"upper"}],
             "options"?, "seed"?, "finish"?}
            an objective or constraint may instead be {"expr", "paths"?, ...}: an expression
            over names given their own paths ("paths": {"q1": path, ...}) or over variables
            that read and calc statements set before the step; the optimizer re-reads the
            paths and recomputes it after every simulation
  table     {"title", "rows"?, "row_label"?, "columns": [{"label", "path" | "expr", "unit"?}]}
            a results table: one row per name in rows, "{row}" in a column's path or
            expression standing for that name; or {"title", "loop", "vars"?}: a loop's results
  plot      {"title", "x_from"?, "x_to"?, "y_from"?, "y_to"?, "xlabel"?, "ylabel"?, "var"? ("x"),
             "points"? (60), "series": [{"loop", "ycols", "xcol"?, "label"?, "color"?, "dash"?}
                                        | {"label", "expr", "from"?, "to"?, "color"?, "dash"?}
                                        | {"label", "x", "color"?, "dash"?}]}
            a chart of a loop's results (data lines), curves y = expr(x) and vertical lines at
            x; ranges are expressions, no x range the data lines' extent
  save      {"path"?}                              save the model: to its own file, or as path
                                                   (relative to the model's folder; {name}
                                                   takes a variable's value), which the session
                                                   then continues in, as Aspen's Save As does
  pinch     {"dtmin"? (10), "auto"? (true), "exclude"?, "streams"?: [{"name", "t_in", "t_out",
             "duty", "type"?}], "matches"? (true), "as"? ("pinch"), "title"?}
                                                   heat integration targets from the live
                                                   model: auto takes every heater's duty and
                                                   its inlet and outlet temperatures, and every
                                                   column's condenser and reboiler; a stream's
                                                   fields are paths (converted to C and kW) or
                                                   expressions (in C and kW)
  proc      {"name", "params"?, "body": [...]}     a named group of statements, top level only;
                                                   like def it applies wherever it sits
  call      {"name", "args"?}                      run a proc; each arg (an expression) sets the
                                                   matching param as a program variable first
  place, connect, remove, component, method        the flowsheet's shape: names, types and
            ports only (tools/wb_plan.py has their form); each runs the MCP tool's own code,
            measured and journaled as that tool (intercept.measured: the tool's restore point,
            once per run; its records with the statement's sid). Never inside a loop.
  yourturn  {"path", "hint", "expect"?: {"op", "value"}, "answer"?, "as"?, "unit"?}
            "your turn": the run stops and waits for the user to set this input
            themselves -- in the workbench's inspector or in Aspen's own window -- and press Done;
            the value is recorded as theirs (actor user, via yourturn) and the variable "as"
            (default yourturn_value) holds it. ``expect`` is checked when they press Done (op of
            if's, value a number, a {variable} or an option code); after YT_TRIES misses the
            window may ask for ``answer``, which the program then writes. Never inside a loop.

Every loop (repeat, until, sweep, seek) records a table: one row per pass with the loop
variable and every program variable, or only those its "record" list names. A table or
plot statement records one, and an optimize step its evaluations and Pareto set. All show
in the window's Results panel and in workbench_read / workbench_run.

Where the model is left ("finish"): the statements after a sweep, seek or optimize step see
the values it left, and when the program ends (done, stopped or failed) every input such a
step changed is written back once, then the model runs once if it ran since (the restore
ledger, _Runner.restore). A step keeps its result instead with finish "last" (optimize also
"best"); a seek keeps its answer unless finish is "restore"; a later set of the same path
keeps that value. A step stopped or failed part-way is always put back. The window can then
write a result's row or best point into the model (event apply_point).

The window also works the model directly: a value typed into its inspector (set_value),
Aspen's Run (run_sim: the session's ``sim``) and saving the model, backed up first
(save_model: the session's ``saved``), saving a named restore point of the model or keeping an
automatic one for good (checkpoint, keep_checkpoint: the session's ``cp``; tools/restore_points.py
-- the AI's structural changes and optimizations get automatic ones, tools/intercept.py, and so
does a program's optimize step), and putting the model back to one of them in place (restore:
the session's ``restore_req``; AspenPlusManager.restore -- tabs, blocks and notes stay), and
taking changes back -- one record, several or a whole change group, and an undo itself (a
redo) -- previewed first (revert, mode dry | apply: the session's ``undo_req``; tools/undo.py
from the journal's before values). Its inspector's "check for edits made in Aspen"
(ext_deep) reads every input of one block or stream in turns that let the loop run
(tools/external.py ``Deep``): the first press notes them, a later one journals what changed
there that the journal does not explain (the tab's ``ext_deep``).

Fields are named in words (tools/aspen_labels.py): every inspector row carries ``loc``, and a
field no label names yet is named by its GUI prompt, read once -- at most _LEARN_MAX per
inspect, or what the window's labels_learn asks for -- and kept in learned.json, never while
Aspen works for a program, an optimize or a call on the session. The window reads the change
journal and the labels itself (workbench/window.py), so its timeline works while Aspen holds
this loop.

One writer per session at a time (tools/activity.py): a real program run holds its session
from start to end, whoever started it, and so does the AI's optimize. Meanwhile the
window's own writes are refused (a line in the chat), a program started on the session is
queued, and the AI's changing calls wait up to 10 s, then are refused; reads always pass.

The change journal (tools/journal.py) keeps what all of this changed and who did it. A program
run is one change group, actor ``program``: a record per statement, one summary per loop and
one for the restore at its end; an optimize step is one summary by the ``optimizer``. What the
window writes itself is the user's: every window job that changes the model runs inside
``Workspace.as_user`` (``@_by_user``). Each session's ``journal`` in state.json is the
journal's summary of its model (count, last input and run times), kept current after every
call, program statement and window job. workbench_read hands the AI the latest change groups
as short lines (journal.digest), and under ``brief`` what others changed since its last call
(tools/brief.py; any other result carries that at its top). An Ask AI request pushed to the
AI, or shown by workbench_read, is the one its next changes are grouped under
(``current_note``) until it is answered done. A request may be about a block or stream, a
change record, a change group, an inspector field or a program step: the AI is told
what that is in words (``_target_text``), and the note keeps the newest change group it led
to (``group``, ``group_model``), for the window's "caused N changes" and its jump there.

Every MCP call ends in ``after_tool`` (tools/intercept.py). An open window is served by a
server that never called open_workbench -- after a /mcp reconnect, from its first call or
already at start (server.py's lifespan) -- and what the call changed is re-read about a
second after the last call of a burst (``Workspace.later``), not while Aspen works for a
program or an optimize.

The brakes (tools/brake.py): the workspace's ``brake`` -- AI mode, pause, confirmation
cards -- is what tools/intercept.py's gate asks (``gate``). It acts only while this server
owns the live window (``Workspace.brake_live``: its sync loop runs, the window is open, and
``owner.json`` names this process -- another server's open_workbench is refused meanwhile);
otherwise a call passes as in auto, its records saying so. The window's brake_* events go to
Brake.on_event (``_brake_event``): their records into every open model's journal, a late
approval replayed as the user's (intercept.late; a workbench_run card's tab is queued as the
window's Run instead, ``late_apply``), a pause, a resume and a late decision told to the AI on
the channel (``_tell``). The AI's own records feed tools/stuck.py (``on_records``); a
trigger pauses it, said at the end of that call's answer (``gate_done``). state.json's
``brake`` is Brake.view().

Proposals (tools/proposals.py): workbench_edit(proposal=...) writes the AI's program
as a proposal tab (``kind`` "proposal", its ``proposal``), or revises one; an open one is
checked as soon as its session is idle (``check_soon``: a dry run in ``pending``, ``auto_checks``).
Only the user runs it -- the run is the approval --: the AI's real run of one is refused before
the brakes (``refuse_call``, intercept's Hooks.refuse) and in workbench_run. The user's edits of
it are told apart from the AI's version (``edited``); workbench_read lists the session's
proposals with their check. The window's run of a proposal tab -- any, an old window's too -- is
the approval (``execute(approve=)``): refused at once when it cannot be one (a draft, running,
withdrawn, nothing turned on); pre-checked with the flowsheet check too (an error: nothing saved,
nothing run); a restore point (before-proposal, however slow; ``approve: "no_cp"`` skips it, and
one that fails refuses the run); then run as the program, its records ``proposal`` / ``approved:
user``, its change group's header ``proposal`` / ``proposed_in`` and, at the end, ``outcome``
(the AI's brief tells it). The proposal ends applied, partial, failed or stopped (``run``: the
restore point to go back to, the group to undo -- both mark it ``undone``). proposal_reply
(reject) sends it back: an Ask AI note pushed to the AI and a milestone in the journal.

Explanations on the flowsheet: a workbench_edit highlight item with a ``note``
also pins that note on its block or stream, per model -- ``pins/<model id>.json``, at most
_PINS_MAX, following the model's identity like its arrangement (a Save As keeps them) -- and
the session's ``pins`` mirrors that file for the model it shows; the event pin_hide removes
one. The AI's reasons and its replies to notes the window reads itself (the journal, the
notes). Learning mode (tools/learn.py): the event learn_mode switches it for both servers
(its own file); state.json's ``learn`` is learn.view(); workbench_read says ``learning``; in it,
workbench_edit and a check name the writing steps that have no ``why``. A prediction: the
window keeps the user's guesses to itself and sends only the results to watch (predict_watch):
runlog.watch reads them, the session's next run reads them again, whoever made it, and the
session's ``predict`` shows both; never in workbench_read.

Your turn: a yourturn statement stops the run and waits for the user (the run's ``wait``;
_Runner.do_yourturn), with no timeout and not inside a loop. Meanwhile the program keeps the
session, marked waiting for the user (tools/activity.py ``waiting_user``): the user's inspector,
Run, Save and restore points pass, the AI's changes are refused at once saying why, and the
AI's workbench_run returns at that point while the run goes on. Done (yourturn_done) checks the
value; the answer (yourturn_answer) has the program write it.
"""

from __future__ import annotations

import ast
import asyncio
import contextlib
import copy
import csv
import functools
import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from searcher import unit_table
from searcher.discover_ports import PORTS as _PORT_TABLE     # the merged port table (flowsheet_tools')
from tools import activity, aspen_labels, aspen_strings, brief, journal, main_tools, pfsv, pinch_tools, probes, recorder
from tools import checkpoints, dispid, doc_index, external, gui_sheets, intercept, knowledge_tools, report, restore_points, runlog, undo
from tools import inputs_check as IC                         # what the model still lacks
from tools import diagnose                                   # why a run failed
from tools import learn                                      # learning mode
from tools import brake, brake_effects, flowsheet_tools, properties_tools, stuck, wb_plan
from tools import ids                                        # a new block or stream ID that fits
from tools import replay                                     # the timeline as blocks
from tools import proposals                                  # the AI's proposals
from tools import prop_archive                               # proposals kept out of state.json
from tools import notable                                    # the result tags
from tools import flows                                      # the flow width layer's reads
from tools import principles                                 # the principle cards
from tools import workbench_expr as X
from tools._common_eval import confirm_run, progress_sink, read_value
from tools.optimize_dispatch import _best as best_point  # the ranking run_optimize's finish="best" uses
from tools.optimize_dispatch import run_optimize

logger = logging.getLogger("tools.workbench_tools")

try:                                   # the window's help cards (workbench/window.py Api.fieldhelp)
    from tools import fieldhelp  # noqa: F401 -- stdlib + tools.*; importing it is the feature's test
    _FIELD_HELP = True
except Exception:  # noqa: BLE001 -- no help cards; the rest of the workbench is as before
    logger.warning("workbench: help cards unavailable", exc_info=True)
    _FIELD_HELP = False



def principle_keys() -> set | None:
    """The principle library's keys (``docs/principles/<key>.md`` listed in its
    index.md; tools/principles.py, read again when the files change); None while there is no
    library -- the check then does not judge a principle key."""
    return principles.keys()


def groups_on() -> bool:
    """Group headings and runs by group (``catalog.features`` ``groups``) --
    ``ASPEN_MCP_GROUPS`` not 0 / off / false / no (read at every call). Off, a group statement is
    an unknown one, a run asked by group runs as a plain run, and a check has no ``groups``."""
    return os.environ.get("ASPEN_MCP_GROUPS", "1").strip().lower() not in ("0", "off", "false", "no")


def preview_on() -> bool:
    """The flowsheet's preview of a proposal (``catalog.features`` ``preview``) --
    ``ASPEN_MCP_PREVIEW`` not 0 / off / false / no (read at every call). Off, a check has no
    ``shadow``."""
    return os.environ.get("ASPEN_MCP_PREVIEW", "1").strip().lower() not in ("0", "off", "false", "no")


_PKG = Path(__file__).resolve().parent.parent
_WINDOW = _PKG / "workbench" / "window.py"
_ROOT = Path.home() / ".aspen-mcp" / "workbench"
_TMP = Path.home() / ".aspen-mcp" / "tmp"       # Aspen's exports of the model, read and deleted at once
_PYWEBVIEW = "pywebview==6.2.1"
_OPEN_MAX = 8            # files one Open model may ask for
_SYNC_S = 0.3
_BEAT_S = 2.0
_AUTO_S = 0.8            # an auto refresh runs this long after the last call asking for it...
_AUTO_MAX_S = 3.0        # ... and no later than this after the first (Workspace.later)
_LIVE_S = 5.0            # "no window to serve" is believed this long (ensure_live)
_WATCH_RETRY_S = 30.0    # a session's baseline the sync loop could not read is tried again after this
_EXT_JOBS = ("run_sim", "save_model", "apply_point", "set_value", "struct", "inspect", "checkpoint", "restore",
             "revert")   # Aspen-window edits are journaled first
_CP_LIST = 5             # restore points workbench_read shows the AI
_CP_NAME_MAX = 120       # characters of a restore point's name
_REVERT_MAX = 500        # records a restore's then_revert, or a revert event, may name
_SEEN_MAX = 5000         # step keys a revert event's ``seen`` may list (else it sends the preview's sig)
_UNDO_STEPS = 50         # steps of an applied undo undo_req shows (its counts cover them all)
_STALE_S = 6.0           # a heartbeat older than this: its server is gone (window.py STALE_S)
_LANGS = ("en", "zh")
_HISTORY = 50            # program versions kept per tab for undo
_LOG_LINES = 2000        # run log lines kept: a long iteration logs hundreds per pass
STANDALONE = False       # tools/standalone.py sets it: this process serves the window with no AI client
_OWNER = "owner.json"    # {"pid", "srv", "root", "t"} of the server whose sync loop serves the window
_TELL_MAX = 10           # brake messages kept for the AI while no client session is known
_TELL_LINES = 6          # changes a resume message lists
_PAUSE_S = 0.2           # a paused program looks for the window's press this often
_BREAKS_MAX = 50         # ... a tab keeps this many breakpoints (``breaks``)
_PRESSES_MAX = 20        # ... and this many step presses wait to be taken
_HIST_LOADED = 8         # finished proposals a model keeps loaded (the oldest archived past it)
_HIST_STATE = 200        # ... and its History entries state.json lists (the latest)
GC_ROWS = 12             # the group card's live rows at most (one read each)
_EDIT_WAIT_S = 2.0       # a press waits this long for an inspector edit posted before it (the sync loop)
YT_TRIES = 3             # a your-turn step's missed checks before its answer may be asked for
_YT_HINT = 300           # ... characters of its hint
_YT_VAR = "yourturn_value"   # ... the variable that holds the user's value, unless it names one ("as")
# Where in Aspen's own window a step without a path acts (the paused cursor card)
_STEP_WHERE = {"run": ("Run (Control Panel)", "Run（Control Panel）"),
               "place": ("Flowsheet (Model Palette)", "Flowsheet（Model Palette）"),
               "connect": ("Flowsheet (Model Palette)", "Flowsheet（Model Palette）"),
               "remove": ("Flowsheet (Model Palette)", "Flowsheet（Model Palette）"),
               "component": ("Components › Specifications", "Components › Specifications"),
               "method": ("Methods › Specifications", "Methods › Specifications"),
               "save": ("File › Save As", "File › Save As")}

# ---------------------------------------------------------------------------
# Messages. The window has its own strings (static/i18n.js); these are the ones the
# server writes: run log lines and validation errors.
# ---------------------------------------------------------------------------

_MSG = {
    "set_dry": ("Set {path} = {value}{unit}", "設定 {path} = {value}{unit}"),
    "set_fail": ("Set failed: {res}", "設定失敗：{res}"),
    "run_dry": ("Run simulation", "執行模擬"),
    "run_dry_reinit": ("Reinitialize, then run the simulation", "Reinitialize 後執行模擬"),
    "reinit_fail": ("Reinitialize failed: {res}", "Reinitialize 失敗：{res}"),
    "run_ok": ("Simulation finished", "模擬完成"),
    "run_warn": ("Simulation failed or ended in errors:\n{res}", "模擬失敗或有錯誤：\n{res}"),
    "run_warned": ("Simulation finished with warnings in {blocks}", "模擬完成：{blocks} 有警告"),
    "run_warned_global": ("Simulation finished with a warning: {what}", "模擬完成，有警告：{what}"),
    "run_unknown": ("Simulation finished, but its run status could not be read: convergence unknown",
                    "模擬完成，但無法讀取執行狀態，收斂與否不明"),
    "sim_fail": ("The simulation did not run: {res}", "模擬未執行：{res}"),
    # sim_fail's known reasons in the window's own words (_sim_fail); Aspen's answer stays in the log
    "sim_incomplete": ("Not run: inputs incomplete ({objs})", "模擬未執行：輸入不完整（{objs}）"),
    "sim_incomplete0": ("Not run: inputs incomplete", "模擬未執行：輸入不完整"),
    "sim_objs_more": ("{names} and {n} more", "{names} 等 {total} 項"),
    "sim_comps": ("components", "成分"),
    "sim_method": ("property method", "物性方法"),
    "sim_fault": ("Not run: Aspen reported an internal fault in this model; save a copy, then close and reopen it",
                  "模擬未執行：Aspen 回報此模型內部錯誤；請另存副本，再關閉並重新開啟模型"),
    "read": ("{name} = {value}{unit}  ({path})", "{name} = {value}{unit}  ({path})"),
    "read_dry": ("{name} = {value}{unit}  ({path}) -- current value; check mode does not run the simulation",
                 "{name} = {value}{unit}  ({path})——目前的值；檢查模式不會執行模擬"),
    "var_missing": ("No value yet for {names}; shown as ?", "{names} 還沒有值，先顯示為 ?"),
    "if_unreadable": ("If: the left side could not be read, so the else branch runs",
                      "如果：讀不到左邊的值，當作不成立"),
    "if_result": ("If {left} {op} {right} -> {verdict}", "如果 {left} {op} {right} → {verdict}"),
    "true": ("true", "成立"),
    "false": ("false", "不成立"),
    "sweep": ("Sweep {path}{unit}: {values}", "掃描 {path}{unit}：{values}"),
    "opt_preview": ("Optimization preview:\n", "優化設定預覽：\n"),
    "opt_result": ("Optimization result:\n", "優化結果：\n"),
    "no_session": ("No open model '{session}'", "未開啟模型「{session}」"),
    "empty": ("The program is empty: attach blocks under \"when Run program is pressed\"",
              "程式是空的：請把積木接在「當按下「執行程式」」下方"),
    "bad_writes": ("{n} problem(s) in the program. Stopped before anything ran; "
                   "the simulation was not changed",
                   "程式裡有 {n} 個問題，開始前就停下了，模擬沒有被改動"),
    "calc": ("{name} = {value}{unit}  (= {expr})", "{name} = {value}{unit}  （= {expr}）"),
    "calc_none": ("{name} has no value: {why}  (= {expr})", "{name} 沒有值：{why}（= {expr}）"),
    "def": ("Function {name}({params}) = {expr}", "函數 {name}({params}) = {expr}"),
    "bad_name": ("'{name}' is not a valid name: use letters, digits and _, not starting with a digit",
                 "「{name}」不是合法的名稱：只能用英文字母、數字和底線，而且不能以數字開頭"),
    "expr_none": ("Cannot set {path}: {why}  (= {expr})", "不能設定 {path}：{why}（= {expr}）"),
    "until_done": ("Loop ended after {n} pass(es): {cond}", "迴圈執行 {n} 次後結束：{cond}"),
    "until_max": ("Stopped after {n} passes: {cond} never held", "執行 {n} 次仍未達成：{cond}"),
    "seek_start": ("Design spec: {path} in [{lo}, {hi}]{unit} until {measure} = {target}",
                   "調整到目標：{path} 在 [{lo}, {hi}]{unit} 之間，直到 {measure} = {target}"),
    "seek_step": ("  {name} = {x} -> {measure} = {m}", "  {name} = {x} → {measure} = {m}"),
    "seek_done": ("Design spec met: {path} = {x}{unit} after {n} runs ({measure} = {m})",
                  "達到目標：{path} = {x}{unit}，共執行 {n} 次（{measure} = {m}）"),
    "seek_nobracket": ("{measure} does not cross {target} between {lo} and {hi} (it is {mlo} and {mhi}); "
                       "widen the range", "{measure} 在 {lo} 和 {hi} 之間沒有跨過 {target}（兩端分別是 {mlo} 和 "
                       "{mhi}），請放寬範圍"),
    "seek_noval": ("{measure} has no value at {path} = {x}: {why}", "{path} = {x} 時 {measure} 沒有值：{why}"),
    "seek_max": ("Design spec did not converge in {n} runs; closest {path} = {x} ({measure} = {m})",
                 "執行 {n} 次仍未收斂；最接近的是 {path} = {x}（{measure} = {m}）"),
    "edit_ok": ("{label}: {old} → {value}{unit}", "{label}：{old} → {value}{unit}"),
    "edit_empty": ("(empty)", "（空）"),
    "edit_busy": ("Model {session} is running a program; edit again when it finishes",
                  "模型 {session} 正在執行程式，完成後再修改"),
    "save_busy": ("Model {session} is running a program; save the model when it finishes",
                  "模型 {session} 正在執行程式，完成後再儲存"),
    "edit_held": ("Model {session} is being changed by {who}; edit again when it finishes",
                  "模型 {session} 正由{who}修改，完成後再修改"),
    "save_held": ("Model {session} is being changed by {who}; save the model when it finishes",
                  "模型 {session} 正由{who}修改，完成後再儲存"),
    "who_optimizer": ("the AI's optimization", "AI 的優化"),
    "who_other": ("the AI", "AI"),
    "ai_edit": ("The AI changed the block program: {parts}", "AI 修改了積木程式：{parts}"),
    "ai_edit_parts": ("{a} added, {c} changed, {r} removed", "新增 {a} 步、修改 {c} 步、刪除 {r} 步"),
    "edit_fail": ("Could not set {path}: {res}", "無法設定 {path}：{res}"),
    "row_add": ("{label}: row {row} added", "{label}：新增列 {row}"),
    "row_del": ("{label}: row {row} removed", "{label}：刪除列 {row}"),
    "sub_add": ("{label} added", "已新增 {label}"),
    "sub_del": ("{label} removed", "已刪除 {label}"),
    "insp_struct_fail": ("Could not change {label}: {res}", "無法變更 {label}：{res}"),
    "not_found": ("Path not found: {path}", "找不到路徑 {path}"),
    "result_hint": (" (result paths appear only after the simulation has run once)",
                    "（結果路徑要執行模擬後才會出現）"),
    "is_result": ("{path} is a result the simulation computes: it can be read, not set",
                  "{path} 是模擬算出來的結果，只能讀，不能設定"),
    "twin": (". If this is a feed stream, the input you want is \"{label}\" ({path})",
             "。如果這是進料物流，要改的應該是「{label}」（{path}）"),
    "no_unit": ("{path} has no unit, so the unit {unit} cannot apply", "{path} 沒有單位，不能指定 {unit}"),
    "bad_unit": ("{unit} is not a unit of {path} (current {cur}; allowed: {units})",
                 "{path} 不能用單位 {unit}（目前是 {cur}；可用：{units}）"),
    # a check's problem as the window's main line: the object, then what is wrong -- the
    # messages above are its explanation (``help``)
    "s_not_found": ("{path}: not found", "{path}：找不到"),
    "s_not_input": ("{path}: not an input", "{path}：非輸入欄位"),
    "s_no_unit": ("{path}: no unit", "{path}：無單位"),
    "s_bad_unit": ("{path}: unit {unit} not allowed", "{path}：不接受單位 {unit}"),
    "s_bad_name": ("{name}: invalid name", "{name}：名稱不合法"),
    "s_def": ("{name}: invalid definition", "{name}：定義無效"),
    "s_expr": ("{expr}: invalid expression", "{expr}：算式無效"),
    "s_no_proc": ("{name}: procedure not defined", "{name}：子程序未定義"),
    "s_proc_dup": ("{name}: procedure defined twice", "{name}：子程序重複定義"),
    "s_call_args": ("{name}: argument count mismatch", "{name}：參數數目不符"),
    "s_save_ext": ("{path}: invalid file type", "{path}：檔案類型不符"),
    "s_pinch_row": ("Pinch {title}, stream {name}: incomplete", "Pinch {title} 物流 {name}：資料不全"),
    "s_opt_expr": ("Optimize {what} {expr}: invalid", "優化{what} {expr}：無法使用"),
    "s_opt_nopath": ("Optimize {what}: no path or expression", "優化{what}：缺路徑或算式"),
    "s_table_nocols": ("Table {title}: no columns", "表格 {title}：無欄位"),
    "s_table_col": ("Table {title}, column {label}: no path or expression", "表格 {title} 欄位 {label}：缺路徑或算式"),
    "s_yt_off": ("{label}: not enabled", "{label}：未啟用"),
    "s_bad_writes": ("{n} problem(s): not run", "{n} 個問題：未執行"),
    "table": ("Table {title}: {n} row(s) x {m} column(s){empty}", "表格 {title}：{n} 列 × {m} 欄{empty}"),
    "table_empty": (", {k} cell(s) without a value", "，{k} 格沒有值"),
    "table_dry": (" -- current values; check mode does not run the simulation",
                  "——目前的值；檢查模式不會執行模擬"),
    "table_nocols": ("Table {title} has no columns", "表格 {title} 沒有欄位"),
    "opt_obj": ("objective", "目標"),
    "pinch_title": ("Pinch", "Pinch 熱整合"),
    "pinch_row": ("Pinch {title}: stream {name} needs a name, both temperatures and a duty",
                  "Pinch {title}：物流 {name} 要有名稱、進出口溫度與熱負荷"),
    "pinch_streams": ("{title}: {n} stream(s), {hot} hot and {cold} cold{auto}: {names}",
                      "{title}：{n} 條物流（熱 {hot}、冷 {cold}）{auto}：{names}"),
    "pinch_auto": (", heaters and columns from the flowsheet", "，加熱器與塔從流程圖帶入"),
    "pinch_skip": ("{title}: left out {names} (a heater needs one inlet and one outlet stream)",
                   "{title}：略過 {names}（加熱器要剛好一條進口與出口物流）"),
    "pinch_bad": ("{title}: stream {why}", "{title}：物流 {why}"),
    "pinch_none": ("{title}: no streams with a duty to analyse", "{title}：沒有帶熱負荷的物流可以分析"),
    "pinch_dry": (" -- check mode lists the streams but does not compute", "——檢查模式只列出物流，不計算"),
    "pinch_fail": ("{title} failed: {why}", "{title} 失敗：{why}"),
    "pinch_done": ("{title} (ΔTmin {dt} C): least heating {qh} kW (now {hn}), least cooling {qc} kW (now {cn}), "
                   "recovery {rec} kW, pinch {th} / {tc} C (hot / cold side)",
                   "{title}（ΔTmin {dt} C）：最小加熱 {qh} kW（目前 {hn}）、最小冷卻 {qc} kW（目前 {cn}）、"
                   "可回收 {rec} kW、夾點 {th} / {tc} C（熱側／冷側）"),
    "pinch_nomatch": ("{title}: match suggestions failed: {why}", "{title}：配對建議失敗：{why}"),
    "pinch_targets": ("targets", "目標"),
    "pinch_list": ("streams", "物流"),
    "pinch_cc": ("composite curves", "組合曲線"),
    "pinch_gcc": ("grand composite curve", "總組合曲線"),
    "pinch_matches": ("match suggestions", "配對建議"),
    "pc_qh": ("least heating", "最小加熱"), "pc_qh_now": ("heating now", "目前加熱"),
    "pc_qc": ("least cooling", "最小冷卻"), "pc_qc_now": ("cooling now", "目前冷卻"),
    "pc_rec": ("recovery", "可回收"), "pc_th": ("pinch, hot side", "夾點 熱側"),
    "pc_tc": ("pinch, cold side", "夾點 冷側"), "pc_name": ("stream", "物流"), "pc_type": ("type", "類型"),
    "pc_tin": ("T in", "進口溫度"), "pc_tout": ("T out", "出口溫度"), "pc_duty": ("duty", "熱負荷"),
    "pc_hotcc": ("hot composite", "熱組合曲線"), "pc_coldcc": ("cold composite", "冷組合曲線"),
    "pc_heat": ("heat flow", "熱流"), "pc_t": ("T", "溫度"), "pc_ts": ("shifted T", "位移溫度"),
    "pc_region": ("region", "區域"), "pc_option": ("option", "方案"), "pc_hs": ("hot stream", "熱物流"),
    "pc_cs": ("cold stream", "冷物流"), "pc_note": ("note", "備註"), "pc_above": ("above pinch", "夾點以上"),
    "pc_below": ("below pinch", "夾點以下"), "pc_util": ("utility", "公用設施"), "pc_ok": ("pinch ok", "夾點 OK"),
    "pc_split": ("needs a split", "需分流"), "pc_none": ("no solution", "無解"),
    "pc_hot": ("hot", "熱"), "pc_cold": ("cold", "冷"),
    "opt_con": ("constraint", "限制"),
    "opt_expr": ("Optimize {what} {expr}: {why}", "優化的{what} {expr}：{why}"),
    "opt_nopath": ("An optimize {what} has no path or expression", "優化有一個{what}沒有路徑或算式"),
    "opt_untraced": ("{name} is not set by a read or calc before this optimize step, so the optimizer "
                     "cannot recompute it after each of its simulations",
                     "{name} 不是在這個優化之前用「讀取」或「計算」算出來的，優化器每次模擬後沒辦法重算它"),
    "opt_func": ("{name}() cannot be used in an optimize objective or constraint; these can: {names}",
                 "優化的目標或限制不能用 {name}()，可以用：{names}"),
    "opt_nopaths": ("it reads nothing from the simulation", "它沒有讀取任何模擬結果"),
    "opt_nameless": ("{name} has no path", "{name} 沒有路徑"),
    "table_col": ("Column {label} of table {title} needs a path or an expression",
                  "表格 {title} 的欄位 {label} 要有路徑或算式"),
    "row": ("row", "列"),
    "table_title": ("Table", "表格"),
    "plot": ("Plot {title}: {k} line(s){empty}", "圖 {title}：{k} 條線{empty}"),
    "plot_empty": (", {k} point(s) without a value", "，{k} 個點沒有值"),
    "plot_range": ("Plot {title} not drawn: its x range has no value ({why})", "圖 {title} 沒畫：x 範圍沒有值（{why}）"),
    "plot_title": ("Plot", "圖"),
    "plot_noloop": ("Plot {title}: the loop of line {label} has not run yet, so it has no points",
                    "圖 {title}：線 {label} 的迴圈還沒執行，沒有資料點"),
    "plot_nocol": ("Plot {title}: the loop's results have no column {col}", "圖 {title}：迴圈結果沒有欄位 {col}"),
    "plot_noseries": ("Plot {title} has no lines", "圖 {title} 沒有任何線"),
    "s_plot_noseries": ("Plot {title}: no lines", "圖 {title}：沒有線"),
    "plot_loop": ("Plot {title}: a data line names no loop of this program", "圖 {title}：資料線沒有指定本程式中的迴圈"),
    "s_plot_loop": ("Plot {title}: data line without a loop", "圖 {title}：資料線未指定迴圈"),
    "plot_ycol": ("Plot {title}: a data line has no y column", "圖 {title}：資料線沒有選縱軸欄位"),
    "s_plot_ycol": ("Plot {title}: data line without y", "圖 {title}：資料線未選縱軸"),
    "plot_norange": ("Plot {title} needs an x range: it has no data line to take one from",
                     "圖 {title} 要有 x 範圍：沒有資料線可以自動決定範圍"),
    "s_plot_norange": ("Plot {title}: no x range", "圖 {title}：缺 x 範圍"),
    "from_loop_dry": ("{title}: made from the loop's results when the program runs", "{title}：執行程式時由迴圈結果產生"),
    "table_loop": ("Table {title} names no loop of this program", "表格 {title} 沒有指定本程式中的迴圈"),
    "s_table_loop": ("Table {title}: no loop", "表格 {title}：未指定迴圈"),
    "table_noloop": ("Table {title}: its loop has not run yet, so it has no rows", "表格 {title}：迴圈還沒執行，沒有資料列"),
    "save_dry": ("Save the model {where}", "存檔{where}"),
    "save_own": ("to its own file", "（存回原本的檔案）"),
    "save_as": ("as {path}", "，另存為 {path}"),
    "save_ok": ("Saved: {res}", "已存檔：{res}"),
    "model_saved": ("Saved the model to {file}{backup}", "模型已存到 {file}{backup}"),
    "model_saved_bk": (" (the previous file backed up first)", "（舊檔已先備份）"),
    "save_fail": ("Save failed: {res}", "存檔失敗：{res}"),
    # restore points: the window's "Save restore point..." and "Keep", an optimize step's
    "cp_default": ("restore point {hm}", "還原點 {hm}"),
    "cp_busy": ("Model {session} is running a program; create a restore point when it finishes",
                "模型 {session} 正在執行程式，完成後再建立還原點"),
    "cp_held": ("Model {session} is being changed by {who}; create a restore point when it finishes",
                "模型 {session} 正由{who}修改，完成後再建立還原點"),
    "cp_saved": ("Created restore point \"{name}\" ({how}, {secs}); a named one is kept for good",
                 "已建立還原點「{name}」（{how}，{secs}）；具名還原點永久保留"),
    "cp_how_copy": ("a copy of the model file, as last opened or saved", "複製模型檔，也就是上次開啟或存檔時的內容"),
    "cp_how_export": ("the model as it is in Aspen now", "Aspen 裡當下的模型"),
    "cp_fail": ("Could not create restore point \"{name}\": {why}", "無法建立還原點「{name}」：{why}"),
    "cp_keep_fail": ("That restore point is no longer there, so it could not be kept", "那個還原點已經不在了，無法保留"),
    "cp_why_slow": ("creating one for this model takes about {est}", "此模型建立一次約需 {est}"),
    "cp_why_failed": ("it could not be created", "無法建立"),
    "opt_nocp": ("No restore point was made before this optimization: {why}", "這次優化前沒有建立還原點：{why}"),
    # the five flowsheet statements
    "st_place_block": ("Place block {block} ({type})", "放置單元 {block}（{type}）"),
    "st_place_stream": ("Place stream {stream} ({type})", "放置物流 {stream}（{type}）"),
    "st_connect": ("Connect {stream} to {block} {port}", "把 {stream} 接到 {block} 的 {port}"),
    "st_remove_block": ("Remove block {block}", "移除單元 {block}"),
    "st_remove_stream": ("Remove stream {stream}", "移除物流 {stream}"),
    "st_disconnect": ("Disconnect {stream} from {block} {port}", "把 {stream} 從 {block} 的 {port} 拆下"),
    "st_comp_add": ("Add component {name}", "加入成分 {name}"),
    "st_comp_remove": ("Remove component {name}", "移除成分 {name}"),
    "st_method": ("Property method {method}", "物性方法改成 {method}"),
    "struct_fail": ("{what} failed: {res}", "{what}失敗：{res}"),
    "struct_in_loop": ("{what}: a flowsheet change cannot run in a loop (each pass would change it again)",
                       "{what}：流程圖的修改不能在迴圈裡執行（每一圈都會再改一次）"),
    "struct_nocp": ("No restore point was made before this flowsheet change: {why}",
                    "這次修改流程圖前沒有建立還原點：{why}"),
    # restoring a restore point in place: the window's "Restore to here", "Undo this restore"
    "rs_busy": ("Model {session} is running a program; restore the model when it finishes",
                "模型 {session} 正在執行程式，完成後再還原"),
    "rs_held": ("Model {session} is being changed by {who}; restore the model when it finishes",
                "模型 {session} 正由{who}修改，完成後再還原"),
    "rs_done": ("Restored the model to restore point \"{name}\" ({when}); {file} now holds it{backup}. {undo}",
                "已把模型還原到還原點「{name}」（{when}），{file} 現在是它的內容{backup}。{undo}"),
    "rs_backup": (" (the file before it is backed up)", "（原本的檔案已先備份）"),
    "rs_undo": ("\"Undo this restore\" goes back to how it was just before.", "「復原這次還原」可以回到還原前的樣子。"),
    "rs_noundo": ("Nothing was saved first, so this restore cannot be undone.", "還原前沒有保存，這次還原無法反悔。"),
    "rs_fail": ("Could not restore \"{name}\": {why}", "無法還原「{name}」：{why}"),
    "rs_recovered": ("Could not restore \"{name}\" ({why}). The model is back as it was: {where}.",
                     "無法還原「{name}」（{why}）。模型已回到還原前的樣子：{where}。"),
    "rs_at_before": ("reopened from the point saved just before, which {file} now holds",
                     "從還原前保存的還原點重新開啟，{file} 現在是它的內容"),
    "rs_at_file": ("reopened from {file} as it was", "從原本的 {file} 重新開啟"),
    "rs_closed": ("Could not restore \"{name}\" ({why}), and Aspen could not reopen the model. {file} is as it "
                  "was: open it again.", "無法還原「{name}」（{why}），Aspen 也沒能重新開啟模型。{file} 維持原樣，請重新開啟。"),
    "rs_why_not_found": ("that restore point is no longer there, or is not this model's",
                         "那個還原點已經不在了，或不是這個模型的"),
    "rs_why_damaged": ("its file is incomplete", "它的檔案不完整"),
    "rs_why_not_bkp": ("{file} is not a .bkp file: save the model as .bkp first", "{file} 不是 .bkp 檔：請先另存成 .bkp"),
    "rs_why_save_failed": ("the model could not be saved first ({err}), so nothing was changed. Untick "
                           "\"save first\" to restore anyway", "無法先保存目前的模型（{err}），所以沒有做任何改動。"
                           "取消勾選「還原前先保存」才能直接還原"),
    "rs_why_backup_failed": ("the file could not be backed up, so nothing was changed ({err})",
                             "無法備份檔案，所以沒有做任何改動（{err}）"),
    "rs_ai_note": ("I restored the model to the restore point of {when} ({name}). Please continue from the model "
                   "as it is now.", "我把模型還原到 {when} 的還原點（{name}），請以現在的模型為準繼續。"),
    # taking changes back: the window's "Undo", "Undo this group", "Redo" (event revert)
    "rv_busy": ("Model {session} is running a program; undo when it finishes",
                "模型 {session} 正在執行程式，完成後再復原"),
    "rv_held": ("Model {session} is being changed by {who}; undo when it finishes",
                "模型 {session} 正由{who}修改，完成後再復原"),
    "rv_wrong_model": ("'{session}' now holds another model, so nothing was undone",
                       "「{session}」現在開啟的是另一個模型，未復原任何修改"),
    "rv_plan": ("{n} change{s} to undo", "要復原 {n} 項修改"),
    "rv_plan_redo": ("{n} change{s} to redo", "要重做 {n} 項修改"),
    "rv_nothing": ("Nothing to undo", "沒有可以復原的修改"),
    "rv_undid": ("Undid {n} change{s}", "已復原 {n} 項修改"),
    "rv_redid": ("Redid {n} change{s}", "已重做 {n} 項修改"),
    "rv_none": ("Nothing was undone", "沒有復原任何修改"),
    "rv_conflict": ("Nothing undone: {n} of them changed since. Skip those or overwrite them",
                    "沒有復原：其中 {n} 項之後被改過，請選擇跳過或蓋掉"),
    "rv_changed": ("Nothing undone: the model changed since the preview. Look at the undo again",
                   "沒有復原：預覽之後模型又改過了，請重新看一次"),
    "rv_failed": ("The undo failed: {why}", "復原失敗：{why}"),
    "rv_n_approx": ("{k} only approximately", "{k} 項只能近似"),
    "rv_n_already": ("{k} already as before", "{k} 項本來就是原值"),
    "rv_n_conflict": ("{k} changed since", "{k} 項之後被改過"),
    "rv_n_skipped": ("{k} skipped", "{k} 項略過"),
    "rv_n_failed": ("{k} failed", "{k} 項失敗"),
    "rv_n_blocked": ("{k} only a restore point can take back", "{k} 項只能靠還原點收回"),
    "rv_side": ("the inputs of {names} are incomplete now", "{names} 的輸入變得不完整"),
    "rv_bits": (" ({bits}).", "（{bits}）。"),
    "rv_end": (".", "。"),
    "rv_sep": ("; ", "；"),
    # a restore point without a name, by what it was kept before (checkpoints ``reason``)
    "cpr_before-structure": ("before the AI changed the structure", "AI 改結構之前"),
    "cpr_before-optimize": ("before an optimization", "優化之前"),
    "cpr_before-proposal": ("before a proposal ran", "提案執行之前"),
    "cpr_before-restore": ("before a restore", "還原之前"),
    "cpr_before-patch": ("before a file edit", "改檔之前"),
    "cpr_before-overwrite": ("the file before it was overwritten", "覆寫檔案之前"),
    "cpr_manual": ("restore point", "還原點"),
    "secs": ("{n} s", "{n} 秒"),
    "mins": ("{n} min", "{n} 分鐘"),
    "save_ext": ("{path}: the file must end in .bkp, .apw or .apwz", "{path}：檔名要以 .bkp、.apw 或 .apwz 結尾"),
    "save_outside": ("{path} is an existing file outside the model's folder, and a program does not "
                     "overwrite it; nothing was saved. Ask the user to save it from the workbench window instead.",
                     "{path} 是模型資料夾以外的既有檔案，程式不會覆寫它；沒有存檔。請改由使用者在工作台視窗存檔。"),
    "call": ("Call {name}{args}", "呼叫 {name}{args}"),
    "call_deep": ("Procedures call each other more than {n} levels deep", "子程序互相呼叫超過 {n} 層"),
    "no_proc": ("No procedure named '{name}'", "沒有叫做「{name}」的子程序"),
    "proc_dup": ("Procedure '{name}' is defined more than once", "子程序「{name}」定義了不只一次"),
    "call_args": ("{name} takes {n} value(s) ({params}); {k} given", "{name} 要 {n} 個值（{params}），給了 {k} 個"),
    "stopped": ("Stopped", "已停止"),
    # stepping: a program paused before a step, in the window's hands
    "why_paused": ("The program on tab \"{tab}\" is paused: continue or stop it first",
                   "程式已暫停（分頁「{tab}」）：請先繼續或停止"),
    "step_break": ("Paused before step {n} (breakpoint)", "停在第 {n} 步之前（中斷點）"),
    "step_closed": ("The window was closed while the program was paused: stopped there",
                    "程式暫停期間視窗已關閉：於該處停止"),
    # your turn: the run waits for the user to set a field
    "why_waiting": ("The program on tab \"{tab}\" is waiting for input ({label}): press Done, or Stop, first",
                    "程式（分頁「{tab}」）等待輸入 {label}：請先按「完成」或「停止」"),
    "yt_dry": ("Manual step: the run pauses here for the user to set {label} ({hint})",
               "手動步驟：執行到此暫停，由使用者設定 {label}（{hint}）"),
    "yt_off": ("{label} is not enabled now: the user may have to change another setting first",
               "{label} 目前未啟用：可能需先修改其他設定"),
    "yt_wait": ("Manual input: set {label}, then press Done. Hint: {hint}",
                "手動輸入：設定 {label}，完成後按「完成」。提示：{hint}"),
    "yt_retry": ("Not met: {label} is {value}; it should be {op} {want}",
                 "不符合：{label} 為 {value}，應 {op} {want}"),
    "yt_done": ("{label} set to {value} (was {old})", "{label} 設為 {value}（原 {old}）"),
    "yt_kept": ("{label} left at {value}", "{label} 維持 {value}"),
    "yt_answer": ("The answer, written by the program: {label} = {value}",
                  "答案（由程式寫入）：{label} = {value}"),
    "yt_loop": ("A manual step ({label}) cannot run in a loop: each pass would pause again",
                "手動步驟（{label}）不能放在迴圈內：每一圈都會再次暫停"),
    "yt_novar": ("The check of {label} needs {name}, which has no value yet: not checked",
                 "檢查 {label} 需要 {name}，但它尚無值：未檢查"),
    "error": ("Error: {exc}", "錯誤：{exc}"),
    "queued": ("Waiting: tab \"{other}\" is running on model {session}",
               "等待中：分頁「{other}」正在模型 {session} 上執行"),
    "queued_held": ("Waiting: {who} is changing model {session}",
                    "等待中：{who}正在修改模型 {session}"),
    # one tab per model, its proposals as sub-tabs (Workspace.close_model, prop_*)
    "close_busy": ("\"{tab}\" is running: stop it, then close this model's tab.",
                   "「{tab}」正在執行：停止後才能關閉這個模型的分頁。"),
    "close_prop_active": ("This proposal is still in progress: use Close proposal on its card first.",
                          "提案仍在進行中：請先在提案卡上按「關閉提案」。"),
    "stale_run": ("Not run: tab \"{tab}\" is for a model session {session} no longer holds; close it.",
                  "未執行：分頁「{tab}」的模型已不是工作階段 {session} 開啟的模型；請關閉此分頁。"),
    "prop_reopened": ("Reopened from History: the AI revised this proposal.", "AI 改寫了提案，已從歷史提案重新開啟。"),
    "prop_del_refused": ("A proposal that is running or still in progress cannot be deleted.",
                         "執行中或待處理的提案不能刪除。"),
    "prop_deleted": ("Proposal record \"{title}\" deleted.", "已刪除提案紀錄「{title}」。"),
    # where the model is left when a program ends (the restore ledger) or a point is applied
    "opt_until_end": ("Model state: the steps that follow see the last evaluated point; the start values "
                      "come back when the program ends.",
                      "模型狀態：後面的步驟看到的是最後一次評估的點；程式結束時會還原起始值。"),
    "ms_head": ("Model: {parts}.", "模型：{parts}。"),
    "ms_restored": ("restored {items}", "已還原 {items}"),
    "ms_sweep": ("left at the sweep's last value: {items}", "停在掃描的最後一點：{items}"),
    "ms_seek": ("left at the design spec's answer: {items}", "停在調整到目標的答案：{items}"),
    "ms_opt_last": ("left at the optimization's last evaluated point: {items}", "停在優化最後一次評估的點：{items}"),
    "ms_opt_best": ("set to the optimization's best point: {items}", "設在優化的最佳點：{items}"),
    "ms_set": ("kept at the value a later set gave it: {items}", "保留後面「設定」積木給的值：{items}"),
    "ms_user": ("kept as the user changed it while the program was paused: {items}", "保留暫停期間的使用者修改：{items}"),
    "ms_empty": ("not restored, empty before the step: {items}", "未還原（步驟之前是空的）：{items}"),
    "ms_failed": ("could not be restored: {items}", "無法還原：{items}"),
    "ms_gone": ("the Aspen model is gone, so nothing was restored", "Aspen 模型已不在，沒有還原任何值"),
    "ms_run_ok": (" Re-run: converged.", "重新執行：收斂。"),
    "ms_run_warn": (" Re-run: warnings ({detail}).", "重新執行：有警告（{detail}）。"),
    "ms_run_error": (" Re-run failed ({detail}): the results do not match the inputs.",
                     "重新執行失敗（{detail}）：結果與輸入不符。"),
    "ms_run_unknown": (" Re-run: finished; the run status could not be read, so convergence is unknown.",
                       "重新執行：完成，但無法讀取執行狀態，收斂與否不明。"),
    "ms_run_refused": (" Not re-run ({detail}): the results do not match the inputs.",
                       "未重新執行（{detail}）：結果與輸入不符。"),
    "ap_row": ("row {n} of {label}", "{label} 的第 {n} 列"),
    "ap_best": ("the best point of {label}", "{label} 的最佳點"),
    "ap_eval": ("evaluation {n} of {label}", "{label} 的第 {n} 次評估"),
    "ap_ok": ("Applied {what}: {items}.{run}", "已套用{what}：{items}。{run}"),
    "ap_fail": ("Could not apply {what}: {why}", "無法套用{what}：{why}"),
    "ap_nosource": ("no result '{source}' on this tab", "這個分頁沒有結果「{source}」"),
    "ap_norow": ("it has no row {row}", "沒有第 {row} 列"),
    "ap_nobest": ("it has no best point", "沒有最佳點"),
    "ap_novalue": ("that row has no value", "那一列沒有值"),
    # the deep compare (ext_deep): the tab's ext_deep "text"
    "deep_new": ("Noted the {n} input fields of {name}. Change it in the Aspen window, then check again to "
                 "find the edits.", "已記下 {name} 的 {n} 個輸入欄位。之後在 Aspen 視窗改了它，再按一次就能找出來。"),
    "deep_found": ("Found {k} edit(s) to {name} made in the Aspen window (compared {n} fields); they are in "
                   "Changes.", "找到 {name} 的 {k} 處在 Aspen 視窗的修改（比對了 {n} 個欄位），已列在「變更」。"),
    "deep_none": ("{name}: the same as noted before, no new edits (compared {n} fields).",
                  "{name}：和上次記下的一樣，沒有新的修改（比對了 {n} 個欄位）。"),
    "deep_partial": (" Too many fields: only the first {n} were read.", "欄位太多，只讀了前 {n} 個。"),
    "deep_afresh": (" (The earlier note no longer applied: the model was opened again, or {name} replaced, since.)",
                    "（先前記下的已不適用：之後模型重新開啟過，或 {name} 被換掉了。）"),
    "deep_changed": ("{name}: the model's structure changed during the check; check again.",
                     "{name}：檢查期間模型的結構變了，請再按一次。"),
    "deep_missing": ("No {name} in the Aspen model.", "Aspen 模型裡沒有 {name}。"),
    "deep_pick": ("Select a block or stream to check first.", "請先選一個單元或物流再檢查。"),
    "deep_off": ("Edits made in the Aspen window are not tracked (ASPEN_MCP_EXTERNAL=0, or the change log is off).",
                 "沒有追蹤 Aspen 視窗裡的修改（ASPEN_MCP_EXTERNAL=0，或變更紀錄已關閉）。"),
    "deep_fail": ("Checking {name} failed: {why}", "檢查 {name} 失敗：{why}"),
    # learning mode: a check lists the writing steps that give no reason
    "learn_why": ("Learning mode: steps {ids} change the model but give no reason.",
                  "學習模式：步驟 {ids} 會修改模型但未填寫理由。"),
    # a proposal's watched results (its result tags)
    "watch_missing": ("Watched result not found: {path} (no result tag for it)",
                      "找不到要追蹤的結果 {path}（不會有它的結果標籤）"),
    # the AI's words on a run's result tags (proposal.explain)
    "explain_digits": ("Dropped for containing a number (the numbers on the flowsheet are the measured ones): {what}.",
                       "含數字而未採用（流程圖上的數字一律用量測值）：{what}。"),
    "explain_run": ("Explanation not kept: run {run} is not the run the result tags show now ({now}).",
                    "說明未保存：執行 {run} 不是目前結果標籤所屬的那次執行（{now}）。"),
    # the window's own labels (static/i18n.js aspen_place, ai_think), named in answers to the AI
    "ui_aspen_place": ("Apply arrangement to Aspen", "排列套用到 Aspen"),
    "ui_ai_think": ("AI is thinking…", "AI 思考中…"),
}


def _t(lang: str, key: str, **kw) -> str:
    en, zh = _MSG[key]
    return (zh if lang == "zh" else en).format(**kw)


_SIM_UNDER = re.compile(r"incomplete under:\s*(.*?)\.\s*(?:Use check_inputs|$)", re.S)
_SIM_NAMES = 4           # objects sim_fail names before "and N more"


def _sim_fail(lang: str, res) -> str:
    """A run that did not start, in the window's words: refused for inputs incomplete --
    "Not run: inputs incomplete (ESTCOL, B4)" (``sim_incomplete``), the objects run_simulation's
    refusal names (the components and the property method by name, a container by its own) --,
    refused for Aspen's internal fault (diagnose._FAULT_SAID), else sim_fail with Aspen's own answer."""
    text = " ".join(str(res or "").split())
    if _MISS_REFUSED in text:
        m = _SIM_UNDER.search(text)
        paths = [p.strip() for p in (m.group(1) if m else "").split(", ") if p.strip()]
        names = []
        for p in dict.fromkeys(paths):
            key = {IC._SCAN_SINGLETONS[0]: "sim_comps", IC._SCAN_SINGLETONS[1]: "sim_method"}.get(p)
            names.append(_t(lang, key) if key else p.rstrip("\\").rsplit("\\", 1)[-1])
        if not names:
            return _t(lang, "sim_incomplete0")
        sep = "、" if lang == "zh" else ", "
        shown = sep.join(names[:_SIM_NAMES])
        if len(names) > _SIM_NAMES:
            shown = _t(lang, "sim_objs_more", names=shown, n=len(names) - _SIM_NAMES, total=len(names))
        return _t(lang, "sim_incomplete", objs=shown)
    if diagnose._FAULT_SAID in text:
        return _t(lang, "sim_fault")
    return _t(lang, "sim_fail", res=text[:600])


def _langs(say) -> dict:
    """``say(lang)`` in both of the window's languages, {"en", "zh"}: a check's problem keeps
    both (wb_plan.note's ``texts`` / ``help``), so it reads right after the user switches language."""
    return {x: say(x) for x in wb_plan.LANGS}


def _tt(key: str, **kw) -> dict:
    """_MSG ``key`` in both languages (_langs)."""
    return _langs(lambda x: _t(x, key, **kw))


def _dur(lang: str, s) -> str:
    """A duration in the window's words: "3 s", "2 min" ("?" unknown)."""
    if not isinstance(s, (int, float)):
        return "?"
    return _t(lang, "secs", n="<1" if s < 0.5 else round(s)) if s < 90 else _t(lang, "mins", n=round(s / 60))


# ---------------------------------------------------------------------------
# Field catalog: the window's stream / block reporter menus, the inspector's rows, the run
# fingerprint's block results and the external check's first inputs, all from the docs' tables
# (tools/doc_index.py: each object type's general file, docs/blocks/radfrac.md,
# docs/streams/streams.md). A path not there is entered as a raw path block (or by the LLM, which
# looks paths up in the docs). Every row the inspector shows also carries ``loc``, where it is in
# words (aspen_labels.loc).
# ---------------------------------------------------------------------------

_LEARN_MAX = 60          # GUI prompts (attr 19) one inspect reads for fields no label names yet
_LEARN_EVENT_MAX = 30    # ... and one labels_learn request from the window
_FIELD_INFO_Q = 4        # field_info jobs (help cards) waiting at once
_STUCK_DETAIL = 512      # bytes of a stuck pause's detail (brake._small keeps no more)
_DOC_IDS = 60            # entries an inspector row with an {id} segment reads (a feed stage per feed) ...
_DOC_SHOW = 24           # ... and shows, those holding a value first (a feed's components, a column's stages)
_SHEET_MS = 20.0         # reads one pass of an inspect_sheet job makes (the sync loop's next passes go on) ...
_INSPECT_MS = 20.0       # ... and of an inspect job (inspect_steps)
_SHEET_GAP_S = 0.06      # ... the loop's sleep between them
_SHEET_KIDS = 60         # entries a list field of a sheet shows
_ID_SEG = re.compile(r"\{[^{}\\]*\}")
_BLOCK_TYPES = {t.upper(): t for t in _PORT_TABLE}
# Aspen's model palette tabs, the most used first (catalog.palette); a tab not named keeps its docs place after these
_COMMON_USE = ("Exchangers", "Mixers/Splitters", "Separators", "Columns", "Reactors", "Pressure Changers",
               "Manipulators", "Solids Separators", "Solids", "Batch", "User Models")


def _doc_text(text) -> str:
    """A docs cell as plain words: no backticks, a link its text."""
    return re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", str(text or "")).replace("`", "")


def _doc_named(lc: dict, why) -> dict:
    """A loc still named by its code (aspen_labels: no glossary word, prompt or variable for it)
    named by what the docs say the field is for, cut to a name (src "docs", our zh-TW for it in
    ``gl``: aspen_labels.term) -- not where that opens with an option code (`YES`: ...)."""
    name = "" if lc.get("src") != "code" or str(why or "").lstrip().startswith("`") else \
        aspen_labels.short_prompt(_doc_text(why))
    return dict(lc, field=name, src="docs", gl=aspen_labels.term(name)) if name else lc


def _doc_fields(scope=None) -> dict:
    """{scope: [(rel, io, purpose)]}: every object type's general docs rows (one type's, with
    ``scope``) that name one field -- a stream's {comp} kept as {C}, the menus' component; any
    other {id} row left out."""
    out: dict = {}
    for g in doc_index.rows_for(scope, "general"):
        for r in g["rows"]:
            rel = r["rel"].replace("{comp}", "{C}") if g["scope"] == "STREAM" else r["rel"]
            if not _ID_SEG.search(rel.replace("{C}", "")):
                out.setdefault(g["scope"], []).append((rel, r["io"], r.get("row") or ""))
    return out


def _menu_rows(fields: dict, scope: str, base: str, typ=None) -> list[dict]:
    """A reporter menu's items: {path, label {en, zh?}, input}; the label is the field's
    (aspen_labels), else what the docs say it is for cut to a name (not where that opens with an
    option code), else the code; a result's says so; zh only with our gloss."""
    rows = fields.get(scope) or ()
    locs = aspen_labels.labels([f"{base}\\{rel}" for rel, *_ in rows], {scope: typ} if typ else None)
    out = []
    for rel, io, why in rows:
        lc = _doc_named(locs.get(f"{base}\\{rel}") or {}, why)
        en = lc.get("field") or rel
        label = {"en": en, "zh": lc["gl"]} if lc.get("gl") else {"en": en}
        if io == "out":
            label = {k: f"{v}（結果）" if k == "zh" else f"{v} (result)" for k, v in label.items()}
        out.append({"path": rel, "input": io == "in", "label": label})
    return out


def _palette() -> list:
    """catalog()["palette"]: [{"title", "types"}] -- the docs' block index (doc_index.palette: Aspen's
    model palette tabs), the most used tab first (_COMMON_USE), each type as the port table writes it
    (one the table lacks left out)."""
    rank = {h: i for i, h in enumerate(_COMMON_USE)}
    tabs = sorted(doc_index.palette(), key=lambda ht: rank.get(ht[0], len(rank)))
    return [{"title": h, "types": [_BLOCK_TYPES[t] for t in ts if t in _BLOCK_TYPES]} for h, ts in tabs]


def _strings_state(st: dict | None = None) -> dict:
    """catalog()["strings"]: {"state": none|running|ok|failed, "aspen", "why"} of the field names
    read from the user's Aspen (tools/aspen_strings.py). The window asks Api.strings() for the
    current one; this is how it stood when the catalog was made."""
    st = aspen_strings.status() if st is None else st
    return {k: st.get(k) for k in ("state", "aspen", "why") if st.get(k) is not None}


def catalog() -> dict:
    """What the window offers, rebuilt on every load. ``features`` names the parts this server can
    be without, so the window hides a control nobody would answer (the rest it always serves):
    ``external``: edits made in Aspen's own window are found and journaled, and the event ext_deep
    checks one block's or stream's every input (tools/external.py; absent with
    ASPEN_MCP_EXTERNAL=0 or the journal off). ``undo``: the event revert takes changes back --
    previewed (mode dry), then applied -- answered in the session's ``undo_req``, and a hand edit's
    chat line carries its ``record`` (absent with the journal off: nothing to take back
    from); it also turns on ``coverage.flags.undo``. ``to_blocks``: the event to_blocks turns a
    change group's or picked records into a program in a new tab (``_to_blocks``; the journal
    on). ``brake``: state.json's ``brake`` (tools/brake.py's view) and the events brake_mode,
    brake_pause, brake_resume, brake_card, brake_dismiss, brake_stuck (absent with
    ASPEN_MCP_BRAKE=0); ``stuck``: the AI is paused when it looks stuck, its thresholds
    brake_stuck's (the journal on too). ``field_help``: the window's help cards (window.py
    Api.fieldhelp, tools/fieldhelp.py) -- an inspector input row carries ``prompt`` (and
    ``basis``), and the event field_info reads one field for a card into the tab's ``field_info``.
    ``predict``: a prediction's results -- the event predict_watch {id?, paths} (at most 3;
    never a guess) reads them into the session's ``predict`` {"id", "t", "model", "paths", "b":
    {path: [value, unit] | null}, "state": waiting | failed | done, then "a" like b, "run", "seq",
    "status", "by" {actor, via}, "at"; "failed" {run, seq?, status, by, at} after a run that went
    wrong}, the event predict_clear puts it away (the journal on: the run records measure it).
    ``groups`` (absent with ASPEN_MCP_GROUPS=0): the statement group (a heading) is
    accepted, a check's ``tab.check`` has ``groups`` and each row ``g`` / ``tech`` / ``obj``
    (wb_plan.groups), and a run event's ``mode`` group pauses before each group's first step that
    changes the model (``run.paused.why`` "group", ``paused.group``). ``preview`` (absent
    with ASPEN_MCP_PREVIEW=0): a check's ``tab.check`` has ``shadow`` (wb_plan.shadow: what
    its top-level structure steps leave drawn), which the window draws over the flowsheet before
    the proposal is approved. ``effects`` (the journal on): an approved proposal's
    run ends with ``tab.run.effects`` (what its run moved, tools/notable.py: the proposal's
    ``watch`` first, its goal leading), the window's Run simulation with the session's
    ``effects``; ``notable`` the thresholds a result tag goes by. ``principles``
    (absent with no library): the catalog's ``principles`` [{key, title {en, zh}}] and
    ``principle_rules`` [{types, fields, key}] (tools/principles.py: docs/principles' index.md and
    rules.md), and window.py's Api.principle(key) a card. ``journal_on`` false: nothing is being
    recorded (ASPEN_MCP_JOURNAL=0). ``terms``: our zh-TW for the titles the window shows -- forms,
    sheets, subobject collections, model objects, palette tabs -- keyed by the English in lower
    case (aspen_labels.terms)."""
    features = []
    if external.enabled():
        features.append("external")
    if journal.enabled():
        features += ["undo", "to_blocks", "predict", "effects"]
    if brake.enabled():
        features += ["brake", "stuck"] if journal.enabled() else ["brake"]
    if _FIELD_HELP:
        features.append("field_help")
    if groups_on():
        features.append("groups")                        # wb_plan.groups
    if preview_on():
        features.append("preview")                       # tab.check.shadow
    lib = principles.index()
    if lib:
        features.append("principles")                    # Api.principle, the cards' chips
    fields = _doc_fields()
    return {
        "notable": dict(notable.CATALOG),
        "principles": lib,
        "principle_rules": principles.rules() if lib else [],
        "stream_props": [dict(r, key=r["path"], comp="{C}" in r["path"]) for r in _menu_rows(fields, "STREAM", r"\Data\Streams\S")],
        "block_params": {T: [{"path": r["path"], "label": r["label"]} for r in _menu_rows(fields, T, rf"\Data\Blocks\{T}", t)]
                         for T, t in _BLOCK_TYPES.items() if T in fields},
        "features": features,
        "journal_on": journal.enabled(),
        "strings": _strings_state(),
        "coverage": coverage(features),
        "ports": {t: list(p) for t, p in _PORT_TABLE.items()},
        "palette": _palette(),
        "terms": aspen_labels.terms(),
    }


def coverage(features=()) -> dict:
    """catalog()["coverage"], from tools/intercept.py's classification: every tool that is
    not a read, in the one bucket of how its change could be taken back -- ``value`` (one at a
    time), ``inverse`` (what it added removed again), ``checkpoint`` (only by going back to a
    restore point), ``none`` (runs, opening and closing: never rolled back), ``program`` (the
    block program's own versions; a program run's steps are recorded one by one), ``other``
    (changes nothing in the model); ``unrec``: those the journal does not list. ``flags``:
    ``external`` -- edits made in Aspen's own window are found (the feature
    ``external``), ``undo`` -- taking back is live (the feature ``undo``), ``brake`` -- the AI's
    changes go through the brakes. About 1 KB."""
    out = {k: list(v) for k, v in intercept.coverage().items()}
    have = {n for v in out.values() for n in v}
    for name, spec in intercept.TOOLS.items():
        if spec.kind != "read" and name not in have:
            out.setdefault("program" if spec.probe == "prog" else "other", []).append(name)
    out["unrec"] = [n for n, s in intercept.TOOLS.items() if s.kind != "read" and not s.records and s.probe != "prog"]
    out["flags"] = {"external": "external" in features, "undo": "undo" in features, "brake": "brake" in features}
    return out


def key_outputs() -> dict:
    """{block type: [its Output rows]}: the docs' result rows of each block type, which a run's
    result fingerprint reads (tools/runlog.py, configured by server.py)."""
    return {T: [rel for rel, io, _ in rows if io == "out"] for T, rows in _doc_fields().items() if T in _BLOCK_TYPES}


_WATCH_PENDING, _WATCH_COMPS = 50, 15       # journaled inputs, feed components watch_paths takes


def watch_paths(manager, session: str) -> list[str]:
    """The inputs the Aspen-window watch compares a session by when nothing else says (tools/external.py's
    ``base``, configured by server.py), first things first: the input rows the session's open
    inspectors show, the inputs the journal has changed since the last run (at most
    _WATCH_PENDING), each block's docs input rows by type (_doc_fields), then the feed streams'
    docs inputs, their component flows last (at most _WATCH_COMPS components) -- at most
    external.BASE_MAX. The blocks and streams are the window's
    flowsheet when current, else Aspen's (runlog.topology: read once, the run log goes by it too)."""
    out: dict = {}
    ws = _WS
    for t in ws.tabs_for(session) if ws is not None else ():
        out.update((r["path"], None) for r in (t.get("inspect") or {}).get("rows") or ()
                   if r.get("input") and not r.get("extra") and r.get("path"))
    model = manager.model_id(session) if journal.enabled() else None
    pend = (journal.pending(model) or {}).get("items") or () if model else ()
    out.update((it["path"], None) for it in list(pend)[:_WATCH_PENDING] if it.get("op") == "value" and it.get("path"))
    topo = runlog.topology(manager, session) or {}
    fields = _doc_fields()
    for name, typ in topo.get("blocks") or ():
        out.update((rf"\Data\Blocks\{name}\{rel}", None) for rel, io, _ in fields.get(str(typ).upper(), ()) if io == "in")
    rows = [rel for rel, io, _ in fields.get("STREAM", ()) if io == "in"]
    comps = list(topo.get("comps") or ())[:_WATCH_COMPS]
    for comp in (False, True):
        for s in topo.get("feeds") or ():
            for rel in rows:
                if ("{C}" in rel) == comp:
                    out.update((rf"\Data\Streams\{s}\{rel.replace('{C}', x)}", None) for x in (comps if comp else ("",)))
    return list(out)[:external.BASE_MAX]


def _label_of(fs: dict, path: str, lang: str) -> str:
    """A field as people name it: "ESTCOL › Reflux ratio", in Chinese with our gloss beside
    Aspen's English, "ESTCOL › Reflux ratio" followed by the zh gloss in brackets (tools/aspen_labels.py, ``say``); never a
    backslash. The block's type comes from the flowsheet ``fs``."""
    m = re.match(r"^\\Data\\Blocks\\([^\\]+)\\", str(path or ""), re.I)
    btype = next((b.get("type") for b in (fs or {}).get("blocks") or [] if m and b.get("name") == m.group(1)), None)
    return aspen_labels.say(path, btype or None, lang)


# A stream result and the feed input a user most likely meant when they tried to set it.
_INPUT_TWIN = [("\\Output\\RES_TEMP", "\\Input\\TEMP\\MIXED"), ("\\Output\\RES_PRES", "\\Input\\PRES\\MIXED"),
               ("\\Output\\TOT_FLOW", "\\Input\\TOTFLOW\\MIXED"), ("\\Output\\MOLEFLOW\\MIXED\\", "\\Input\\FLOW\\MIXED\\")]


# ---------------------------------------------------------------------------
# Program model
# ---------------------------------------------------------------------------

_KINDS = {"set", "run", "read", "calc", "def", "log", "if", "repeat", "until", "sweep", "seek", "optimize",
          "table", "plot", "save", "proc", "call", "pinch", "group", *wb_plan.STRUCTURE, *wb_plan.PAUSING}
_PINCH_FIELDS = (("t_in", "t"), ("t_out", "t"), ("duty", "q"))
_SAVE_EXT = (".bkp", ".apw", ".apwz")
_LOOPS = ("repeat", "until", "sweep", "seek")
# statements that keep the event loop waiting, and their phase in the heartbeat (tools/activity.py)
_BLOCKING = {"run": "aspen", "save": "aspen", "optimize": "aspen", "pinch": "compute"}
# Where a step that writes inputs leaves them (see the module docstring): the choices, the
# first being the default. A seek finds and sets a value, so it keeps its answer.
_FINISH = {"sweep": ("restore", "last"), "seek": ("last", "restore"), "optimize": ("restore", "best", "last")}
_NESTED = ("then", "else", "body")
_ROW = "{row}"
_MAX_DEPTH = 20          # procedures calling procedures
_WHY_MAX = 300           # a statement's "why": the note under its block, and its records' reason
_OPS = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "<": lambda a, b: a < b,
        "<=": lambda a, b: a <= b, "==": lambda a, b: a == b, "!=": lambda a, b: a != b}
_VAR_REF = re.compile(r"\{(\w+)\}")


def _new_id(prefix: str = "s") -> str:
    return prefix + uuid.uuid4().hex[:7]


def split_args(text: str) -> list[str]:
    """Split "a, max(b, c), 2" at the commas outside brackets."""
    out, depth, cur = [], 0, ""
    for ch in str(text):
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
            continue
        depth += (ch in "([") - (ch in ")]")
        cur += ch
    out.append(cur)
    return [a.strip() for a in out if a.strip()]


def _names(value) -> list[str]:
    """A list of names from a list or a comma-separated string."""
    if isinstance(value, str):
        value = value.split(",")
    return [str(v).strip() for v in value or [] if str(v).strip()]


def normalize(program, seen: set | None = None, top: bool = True) -> list[dict]:
    """Validate a program and give every statement a unique id. Raises ValueError."""
    if program is None:
        return []
    if not isinstance(program, list):
        raise ValueError("program must be a list of statements")
    seen = set() if seen is None else seen
    out = []
    grouping = groups_on()
    kinds = _KINDS if grouping else _KINDS - {"group"}
    for st in program:
        if not isinstance(st, dict) or st.get("do") not in kinds:
            raise ValueError(f"unknown statement {st!r}; 'do' must be one of {sorted(kinds)}")
        if st["do"] == "proc" and not top:
            raise ValueError(f"proc '{st.get('name')}' must sit at the top level of the program")
        st = dict(st)
        sid = str(st.get("id") or "")
        if not sid or sid in seen:
            sid = _new_id()
        st["id"] = sid
        seen.add(sid)
        for key in _NESTED:
            if key in st:
                st[key] = normalize(st[key], seen, top=False)
        if st["do"] == "optimize":
            for key in ("variables", "objectives", "constraints"):
                st[key] = [dict(e) for e in st.get(key) or [] if isinstance(e, dict)]
            for e in st["objectives"] + st["constraints"]:
                e.pop("expr" if e.get("expr") in (None, "") else "path", None)
                paths = e.get("paths") if e.get("expr") and isinstance(e.get("paths"), dict) else None
                if paths:
                    e["paths"] = {str(k).strip(): str(v or "") for k, v in paths.items()}
                else:
                    e.pop("paths", None)
        if st["do"] in ("def", "proc") and "params" in st:
            st["params"] = _names(st["params"])
        if st["do"] == "call" and isinstance(st.get("args"), str):
            st["args"] = split_args(st["args"])
        if st["do"] in _LOOPS:
            rec = [n for n in _names(st.get("record")) if n != "*"]
            if rec:
                st["record"] = rec
            else:
                st.pop("record", None)
        if st["do"] in _FINISH:                           # a value the step does not take is dropped
            fin = str(st.get("finish") or "").strip().lower()
            if fin in _FINISH[st["do"]]:
                st["finish"] = fin
            else:
                st.pop("finish", None)
        if st["do"] == "table":
            st["rows"] = _names(st.get("rows"))
            st["columns"] = [dict(c) for c in st.get("columns") or [] if isinstance(c, dict)]
            if st.get("loop") not in (None, ""):          # a loop's results: its columns by name
                st["loop"], st["vars"] = str(st["loop"]), _names(st.get("vars"))
                for k in ("vars", "rows", "columns"):
                    if not st[k]:
                        st.pop(k)
            else:
                st.pop("loop", None)
        if st["do"] == "plot":
            st["series"] = [dict(s) for s in st.get("series") or [] if isinstance(s, dict)]
            for s in st["series"]:                        # a data line: a loop's columns
                if s.get("loop") not in (None, ""):
                    s["loop"], s["ycols"] = str(s["loop"]), _names(s.get("ycols"))
        if st["do"] == "pinch":
            st["streams"] = [dict(r) for r in st.get("streams") or [] if isinstance(r, dict)]
            st["exclude"] = _names(st.get("exclude"))
        if st["do"] == "set" and st.get("expr") not in (None, ""):
            st.pop("value", None)
        elif st["do"] == "set":
            st.pop("expr", None)
        if st["do"] == "set":                             # a flow's basis (MOLE, MASS...), as given
            basis = str(st.get("basis") or "").strip()
            if basis:
                st["basis"] = basis
            else:
                st.pop("basis", None)
        if st["do"] in wb_plan.STRUCTURE:                 # names, types and ports only (ValueError)
            wb_plan.shape(st)
        if st["do"] == "yourturn":                        # an input, a hint (ValueError)
            _yourturn_shape(st)
        if grouping:                                      # a heading; principle, tech
            if st["do"] == "group":
                wb_plan.shape_group(st)
            wb_plan.shape_extra(st)
        if st.get("off") is not True:                     # a turned-off step; only true is kept
            st.pop("off", None)
        if not st.get("unit"):
            st.pop("unit", None)
        why = " ".join(str(st.get("why") or "").split())[:_WHY_MAX]   # one line under the block
        if why:
            st["why"] = why
        else:
            st.pop("why", None)
        out.append(st)
    return out


_YT_FORM = ('{"do": "yourturn", "path": "\\\\Data\\\\Blocks\\\\B1\\\\Input\\\\TEMP", "hint": "Which outlet '
            'temperature boils off the water?", "expect": {"op": ">=", "value": 100}, "answer": 110} '
            '(expect and answer optional)')


def _yourturn_shape(st: dict) -> dict:
    """A yourturn statement's fields as normalize keeps them: ``path`` an input's tree
    path; ``hint`` one line of at most _YT_HINT characters; ``expect`` {"op" (one of _OPS; ">=" by
    default, "==" for a text), "value"} only when it has a value; ``answer`` only when given; ``as``
    stripped. ``st`` is changed in place and returned. Raises ValueError naming what is wrong and
    the statement's form. (Not in a loop: the check's rule, wb_plan.pause_errors.)"""
    def bad(what):
        return ValueError(f"yourturn: {what}; write it as {_YT_FORM}")
    path = str(st.get("path") or "").strip()
    parts = [p.lower() for p in path.split("\\") if p]
    if not path:
        raise bad("'path' is missing (the input the user sets)")
    if not path.startswith("\\") or parts[:1] != ["data"] or "input" not in parts[1:-1] or "output" in parts:
        raise bad(f"{path} is not an input's path (\\Data\\...\\Input\\<field>): the user sets an input")
    st["path"] = path
    hint = " ".join(str(st.get("hint") or "").split())[:_YT_HINT]
    if not hint:
        raise bad("'hint' is missing (what the user reads while the run waits for them)")
    st["hint"] = hint
    exp = st.get("expect")
    if exp in (None, "", {}):
        st.pop("expect", None)
    elif not isinstance(exp, dict):
        raise bad("'expect' must be {\"op\": \">=\", \"value\": ...}")
    else:
        v = exp.get("value")
        if isinstance(v, (dict, list)):
            raise bad("expect's value must be a number, a {variable} or an option code")
        if v is None or (isinstance(v, str) and not v.strip()):
            st.pop("expect", None)
        else:
            v = v.strip() if isinstance(v, str) else v
            op = str(exp.get("op") or "").strip() or (">=" if _num(v) is not None or _VAR_REF.fullmatch(str(v))
                                                       else "==")
            if op not in _OPS:
                raise bad(f"expect's op {op!r} is not one of {', '.join(_OPS)}")
            st["expect"] = {"op": op, "value": v}
    ans = st.get("answer")
    if ans is None or (isinstance(ans, str) and not ans.strip()) or isinstance(ans, (dict, list)):
        st.pop("answer", None)
    elif isinstance(ans, str):
        st["answer"] = ans.strip()
    name = str(st.get("as") or "").strip()
    if name:
        st["as"] = name
    else:
        st.pop("as", None)
    return st


def _walk(program):
    for st in program:
        yield st
        for key in _NESTED:
            yield from _walk(st.get(key) or [])


def _live_charts(program) -> dict[str, list[dict]]:
    """The charts a loop's passes draw as they come -- each chart with a data line, under
    every loop it takes that comes before it in the program (a chart ahead of its loop waits)."""
    seen, out = set(), {}
    for st in _walk(program):
        if st.get("do") == "plot":
            for loop in dict.fromkeys(str(s.get("loop")) for s in st.get("series") or ()
                                      if isinstance(s, dict) and s.get("loop") not in (None, "")):
                if loop in seen:
                    out.setdefault(loop, []).append(st)
        seen.add(str(st.get("id")))
    return out


def _find(program, sid):
    """(list, index) holding statement ``sid``, searching nested bodies."""
    for i, st in enumerate(program):
        if st.get("id") == sid:
            return program, i
        for key in _NESTED:
            hit = _find(st.get(key) or [], sid)
            if hit:
                return hit
    return None


def _program_diff(old, new) -> tuple[list[str], list[str], int]:
    """What an edit did, by statement id: (added ids, changed ids, how many removed). A kept
    statement changed when its own fields changed, it moved into another statement, or it
    left the order of the statements both versions share where it sits."""
    def places(program):
        out, seqs = {}, {}

        def walk(sts, parent):
            for st in sts:
                out[st["id"]] = ({k: v for k, v in st.items() if k not in _NESTED}, parent)
                seqs.setdefault(parent, []).append(st["id"])
                for key in _NESTED:
                    walk(st.get(key) or [], (st["id"], key))
        walk(program or [], None)
        return out, seqs

    (a, sa), (b, sb) = places(old), places(new)
    changed = {sid for sid in b if sid in a and a[sid] != b[sid]}
    for parent, seq in sb.items():               # moved: off a longest run kept in order
        pos = {sid: i for i, sid in enumerate(sa.get(parent) or [])}
        xs = [sid for sid in seq if sid in pos and a[sid][1] == parent]
        run, back = [1] * len(xs), [-1] * len(xs)
        for i in range(len(xs)):
            for j in range(i):
                if pos[xs[j]] < pos[xs[i]] and run[j] + 1 > run[i]:
                    run[i], back[i] = run[j] + 1, j
        keep, i = set(), max(range(len(xs)), key=run.__getitem__, default=-1)
        while i >= 0:
            keep.add(xs[i])
            i = back[i]
        changed |= set(xs) - keep
    return ([sid for sid in b if sid not in a], [sid for sid in b if sid in changed],
            sum(1 for sid in a if sid not in b))


def _writes(program) -> list[tuple[str, str, str | None, str | None]]:
    """(path, statement id, unit, basis) for every path the program writes to."""
    out = []
    for st in _walk(program):
        if st["do"] in ("set", "sweep", "seek") and st.get("path"):
            out.append((st["path"], st["id"], st.get("unit"), st.get("basis") if st["do"] == "set" else None))
        if st["do"] == "optimize":
            out += [(v["path"], st["id"], None, None) for v in st.get("variables") or [] if v.get("path")]
    return out


def _exprs(program) -> list[tuple[str, str]]:
    """(expression, statement id) for every expression outside a def."""
    out = []
    for st in _walk(program):
        text = {"set": st.get("expr"), "calc": st.get("expr"), "until": st.get("cond"),
                "seek": st.get("measure")}.get(st["do"])
        if st["do"] == "if" and isinstance(st.get("left"), dict):
            text = st["left"].get("expr")
        if st["do"] == "if" and isinstance(st.get("right"), str) and st["right"].strip():
            try:                                          # (a number written as text is a number)
                float(st["right"])
            except ValueError:
                out.append((st["right"], st["id"]))
        if text not in (None, ""):
            out.append((str(text), st["id"]))
        elif st["do"] in ("calc", "until", "seek"):
            out.append(("", st["id"]))              # a missing expression is a problem too
        if st["do"] == "call":
            out += [(str(a), st["id"]) for a in st.get("args") or []]
        if st["do"] == "pinch":
            out += [(str(r[k]), st["id"]) for r in st.get("streams") or [] for k, _ in _PINCH_FIELDS
                    if str(r.get(k) or "").strip() and not str(r[k]).strip().startswith("\\")]
        if st["do"] == "table":
            out += [(cell, st["id"]) for c in st.get("columns") or [] if c.get("expr") not in (None, "")
                    for cell in _cells(st, str(c["expr"]))]
        if st["do"] == "plot":
            # (no x range: taken from the data lines, or a problem of its own -- _static_problems)
            out += [(str(st[k]), st["id"]) for k in ("x_from", "x_to", "y_from", "y_to") if st.get(k) not in (None, "")]
            for s in st.get("series") or []:
                if s.get("loop") not in (None, ""):
                    continue
                if s.get("x") not in (None, ""):
                    out.append((str(s["x"]), st["id"]))
                    continue
                out.append(("" if s.get("expr") in (None, "") else str(s["expr"]), st["id"]))
                out += [(str(s[k]), st["id"]) for k in ("from", "to") if s.get(k) not in (None, "")]
    return out


def _cells(st: dict, template: str) -> list[str]:
    """A table column's path or expression for each of the table's rows."""
    rows = st.get("rows") or []
    return [template.replace(_ROW, r) for r in rows] if rows else [template]


def _procs(program, lang: str) -> tuple[dict, list[tuple[str, str, str]]]:
    """The program's procedures by name, plus (statement id, problem, its short line) for
    every bad proc and every call that cannot be made."""
    procs, bad = {}, []
    for st in program:
        if st["do"] != "proc":
            continue
        name = str(st.get("name") or "")
        wrong = next((n for n in [name] + list(st.get("params") or []) if not X.is_name(n)), None)
        if wrong is not None:
            bad.append((st["id"], _t(lang, "bad_name", name=wrong), _t(lang, "s_bad_name", name=wrong)))
        elif name in procs:
            bad.append((st["id"], _t(lang, "proc_dup", name=name), _t(lang, "s_proc_dup", name=name)))
        else:
            procs[name] = st
    for st in _walk(program):
        if st["do"] != "call":
            continue
        proc = procs.get(str(st.get("name") or ""))
        if proc is None:
            name = st.get("name") or ""
            bad.append((st["id"], _t(lang, "no_proc", name=name), _t(lang, "s_no_proc", name=name)))
            continue
        params, args = list(proc.get("params") or []), list(st.get("args") or [])
        if len(args) != len(params):
            bad.append((st["id"], _t(lang, "call_args", name=proc["name"], n=len(params),
                                     params=", ".join(params) or "-", k=len(args)),
                        _t(lang, "s_call_args", name=proc["name"])))
    return procs, bad


def _functions(program, lang: str) -> tuple[dict, list[tuple[str, str, str]]]:
    """The program's def statements as {name: (params, tree)}, plus (statement id, problem,
    its short line) for every def that is wrong. Defs apply everywhere, wherever they sit."""
    defs = [st for st in _walk(program) if st["do"] == "def"]
    funcs, bad = {}, []
    for st in defs:
        name, params = str(st.get("name") or ""), [str(p) for p in st.get("params") or []]
        wrong = next((n for n in [name] + params if not X.is_name(n)), None)
        if wrong is not None:
            bad.append((st["id"], _t(lang, "bad_name", name=wrong), _t(lang, "s_bad_name", name=wrong)))
        else:
            funcs[name] = (params, None)
    for st in defs:
        name = str(st.get("name") or "")
        if name in funcs:
            try:
                funcs[name] = (funcs[name][0], X.parse(st.get("expr"), funcs))
            except X.ExprError as exc:
                bad.append((st["id"], f"{name}: {exc}", _t(lang, "s_def", name=name)))
                funcs.pop(name)
    return funcs, bad


def _paths(program) -> list[str]:
    out = []
    for st in _walk(program):
        if st.get("path") and st["do"] != "save":         # a save's path is a file, not the tree
            out.append(st["path"])
        if isinstance(st.get("left"), dict) and st["left"].get("path"):
            out.append(st["left"]["path"])
        for key in ("variables", "objectives", "constraints"):
            out += [e["path"] for e in st.get(key) or [] if e.get("path")]
            out += [p for e in st.get(key) or [] for p in (e.get("paths") or {}).values() if p]
        if st["do"] == "table":
            out += [p for c in st.get("columns") or [] if c.get("path") for p in _cells(st, str(c["path"]))]
        if st["do"] == "pinch":
            out += [str(r[k]).strip() for r in st.get("streams") or [] for k, _ in _PINCH_FIELDS
                    if str(r.get(k) or "").strip().startswith("\\")]
    return out


# An optimize objective or constraint written as an expression over program variables.
# The optimizer runs its own simulations and knows nothing of the program, so each
# variable is traced back to the read and calc statements that set it before the step,
# and the expression becomes the optimizer's own form: paths, and arithmetic over
# v0, v1, ... with the functions its evaluator knows (tools/_common_eval.py).
_OPT_FUNCS = {"abs": "abs", "min": "min", "max": "max", "sqrt": "sqrt", "exp": "exp", "log": "log",
              "ln": "log", "log10": "log10", "sin": "sin", "cos": "cos", "tan": "tan", "pow": "pow",
              "floor": "floor", "ceil": "ceil"}
_PATH_MARK = "\0"                                  # a traced name: \0 + the path it reads


def _trail(program, sid):
    """What runs before statement ``sid``: (statement, whole) pairs, where whole=False
    marks a statement that holds ``sid`` and is only partly run first."""
    for i, st in enumerate(program):
        if st.get("id") == sid:
            return [(x, True) for x in program[:i]]
        for key in _NESTED:
            sub = _trail(st.get(key) or [], sid)
            if sub is not None:
                return [(x, True) for x in program[:i]] + [(st, False)] + sub
    return None


def _sets(st, procs, whole=True, seen=()) -> set:
    """The variable names a statement sets; with whole=False only its own, not its body's."""
    d, out = st["do"], set()
    if d in ("read", "calc"):
        out.add(st.get("as") or "value")
    elif d == "sweep":
        out.add(st.get("as") or "sweep_value")
    elif d == "seek":
        out |= {st.get("as") or "seek_value", "measure"}
    elif d in ("repeat", "until"):
        out.add("i")
    elif d == "run":
        out.add("last_run_ok")
    elif d == "call" and st.get("name") in procs and st["name"] not in seen:
        proc = procs[st["name"]]
        out |= set(proc.get("params") or [])
        for x in proc.get("body") or []:
            out |= _sets(x, procs, True, (*seen, st["name"]))
    if whole and d != "proc":                      # a proc runs only when called
        for key in _NESTED:
            for x in st.get(key) or []:
                out |= _sets(x, procs, True, seen)
    return out


class _Trace:
    """What each program variable stands for, in terms of the paths it was read from."""

    def __init__(self, funcs: dict, lang: str, unit_of=None):
        self.funcs, self.lang = funcs, lang
        self.unit_of = unit_of or (lambda path: None)
        self.defs: dict = {}                       # name -> (tree, unit) or (None, why)

    def untraced(self, name):
        self.defs[name] = (None, _t(self.lang, "opt_untraced", name=name))

    def read(self, name, path):
        self.defs[name] = (ast.Name(id=_PATH_MARK + str(path), ctx=ast.Load()), self.unit_of(path))

    def calc(self, name, text, unit=None):
        try:
            self.defs[name] = (self.expand(X.parse(text, self.funcs).body), unit or None)
        except X.ExprError as exc:
            self.defs[name] = (None, f"{name}: {exc}")

    def expand(self, node, bound=None, depth=0):
        """A copy of ``node`` with every variable replaced by what it stands for."""
        if depth > X.MAX_DEPTH:
            raise X.ExprError("functions call each other too deeply")
        bound = bound or {}

        def walk(n):
            if isinstance(n, ast.Name):
                if n.id in bound:
                    return copy.deepcopy(bound[n.id])
                if n.id in self.defs:
                    tree, why = self.defs[n.id]
                    if tree is None:
                        raise X.ExprError(why)
                    return copy.deepcopy(tree)
                if n.id in X.CONSTS:
                    return ast.Constant(X.CONSTS[n.id])
                raise X.ExprError(_t(self.lang, "opt_untraced", name=n.id))
            if isinstance(n, ast.Call):
                args = [walk(a) for a in n.args]
                name = n.func.id
                if name in self.funcs:             # a def: its body, with the arguments in place
                    params, body = self.funcs[name]
                    return self.expand(body.body, dict(zip(params, args)), depth + 1)
                if name not in _OPT_FUNCS:
                    raise X.ExprError(_t(self.lang, "opt_func", name=name,
                                         names=", ".join(sorted(_OPT_FUNCS))))
                return ast.Call(func=ast.Name(id=_OPT_FUNCS[name], ctx=ast.Load()), args=args, keywords=[])
            n = copy.copy(n)
            for field, value in ast.iter_fields(n):
                if isinstance(value, list):
                    setattr(n, field, [walk(v) if isinstance(v, ast.AST) else v for v in value])
                elif isinstance(value, ast.expr):
                    setattr(n, field, walk(value))
            return n

        return walk(node)

    def optimizer_form(self, text, own=None) -> dict:
        """{"aspen_paths", "expression"} for the optimizer; ``own`` gives names their
        paths for this expression alone, ahead of program variables. Raises ExprError."""
        bound = {}
        for name, path in (own or {}).items():
            if not X.is_name(name):
                raise X.ExprError(_t(self.lang, "bad_name", name=name))
            if not str(path).strip():
                raise X.ExprError(_t(self.lang, "opt_nameless", name=name))
            bound[name] = ast.Name(id=_PATH_MARK + str(path), ctx=ast.Load())
        tree = self.expand(X.parse(text, self.funcs).body, bound)
        paths: list = []

        class Number(ast.NodeTransformer):
            def visit_Name(self, n):
                if not n.id.startswith(_PATH_MARK):  # a function's name
                    return n
                path = n.id[len(_PATH_MARK):]
                if path not in paths:
                    paths.append(path)
                return ast.Name(id=f"v{paths.index(path)}", ctx=ast.Load())

        tree = ast.fix_missing_locations(Number().visit(tree))
        if not paths:
            raise X.ExprError(_t(self.lang, "opt_nopaths"))
        return {"aspen_paths": paths, "expression": ast.unparse(tree)}

    def unit(self, text, own=None):
        """The unit of an expression that is a single name, else None."""
        name = str(text).strip()
        if name in (own or {}):
            return self.unit_of(own[name])
        tree, unit = self.defs.get(name, (None, None))
        return unit if tree is not None else None


def _trace(program, sid, funcs, lang, unit_of=None) -> _Trace:
    """What the variables stand for when statement ``sid`` starts."""
    tr = _Trace(funcs, lang, unit_of)
    procs = {st.get("name"): st for st in program if st["do"] == "proc"}
    for st, whole in _trail(program, sid) or []:
        if whole and st["do"] == "read":
            tr.read(st.get("as") or "value", st.get("path"))
        elif whole and st["do"] == "calc":
            tr.calc(st.get("as") or "value", st.get("expr"), st.get("unit"))
        else:
            for name in _sets(st, procs, whole):
                tr.untraced(name)
    return tr


# ---------------------------------------------------------------------------
# Reading the Aspen tree (all on the event-loop thread)
# ---------------------------------------------------------------------------

def _node(app, path: str):
    try:
        return app.Tree.FindNode(path)
    except Exception:
        return None


def _plain(v):
    """A COM value the window can show: numbers and strings pass, anything else is text."""
    return v if v is None or isinstance(v, (bool, int, float, str)) else str(v)


# The pinch tools take C and kW; Aspen reports a field in the unit its unit set gives it.
_TO_C = {"C": lambda v: v, "K": lambda v: v - 273.15, "F": lambda v: (v - 32) / 1.8,
         "R": lambda v: v / 1.8 - 273.15}
# kW per unit of Aspen's ENTHALPY-FLO dimension (International Table calorie and Btu)
_CAL, _BTU = 4.1868, 1.05505585                   # kJ
_KW = {"watt": 1e-3, "w": 1e-3, "j/sec": 1e-3, "kj/sec": 1.0, "kw": 1.0, "mw": 1e3, "gw": 1e6,
       "kj/hr": 1 / 3600, "mj/hr": 1e3 / 3600, "gj/hr": 1e6 / 3600,
       "cal/sec": _CAL / 1e3, "kcal/hr": _CAL / 3600, "mcal/hr": _CAL * 1e3 / 3600,
       "gcal/hr": _CAL * 1e6 / 3600, "mmkcal/hr": _CAL * 1e6 / 3600,
       "gcal/day": _CAL * 1e6 / 86400, "mmkcal/day": _CAL * 1e6 / 86400,
       "btu/hr": _BTU / 3600, "mbtu/hr": _BTU * 1e3 / 3600, "mmbtu/hr": _BTU * 1e6 / 3600,
       "mmbtu/day": _BTU * 1e6 / 86400, "pcu/hr": 1.8 * _BTU / 3600, "mmpcu/hr": 1.8 * _BTU * 1e6 / 3600}


def _to_pinch_unit(kind: str, v, unit):
    """v in C (kind "t") or kW (kind "q"), or None when the unit is not one of these."""
    if v is None:
        return None
    if kind == "t":
        f = _TO_C.get(str(unit or "C").strip().upper())
        return f(v) if f else None
    k = _KW.get(str(unit or "kW").strip().lower())
    return v * k if k is not None else None


def _pinch_auto(fs: dict, exclude, read) -> tuple[list[dict], list[str]]:
    """Stream rows (paths) for the flowsheet's heaters, from inlet to outlet with the block's
    duty, and its columns' condensers and reboilers, isothermal at the top and bottom stage.
    ``read(path)`` gives a value or None. Returns the rows and the heaters left out."""
    rows, skipped, streams = [], [], fs.get("streams") or []
    temp = lambda name: f"\\Data\\Streams\\{name}\\Output\\TEMP_OUT\\MIXED"
    for b in fs.get("blocks") or []:
        name, kind = b.get("name"), str(b.get("type") or "").upper()
        if not name or name in exclude:
            continue
        base = f"\\Data\\Blocks\\{name}\\"
        if kind == "HEATER":                        # heat streams have no temperature
            ins = [x["name"] for x in streams if x.get("to") == name and read(temp(x["name"])) is not None]
            outs = [x["name"] for x in streams if x.get("from") == name and read(temp(x["name"])) is not None]
            if len(ins) == 1 and len(outs) == 1:
                rows.append({"name": name, "t_in": temp(ins[0]), "t_out": temp(outs[0]),
                             "duty": base + "Output\\QCALC", "block": name})
            else:
                skipped.append(name)
        elif kind == "RADFRAC":
            n = read(base + "Input\\NSTAGE")
            for part, duty, stage in (("cond", "COND_DUTY", 1), ("reb", "REB_DUTY", n)):
                q = read(base + "Output\\" + duty)
                if stage is None or not q:          # no such heat exchanger on this column
                    continue
                t = base + f"Output\\B_TEMP\\{int(stage)}"
                rows.append({"name": f"{name}-{part}", "t_in": t, "t_out": t, "duty": base + "Output\\" + duty,
                             "block": name, "part": part})
    return rows, skipped


_BASIS_ROW = {"MOLE": "MOLE", "MASS": "MASS", "STDVOL": "VOLUME"}   # basis -> its rows' name prefix


def _basis_row(node, row: int, basis: str | None) -> int:
    """The unit row ``node`` takes once its basis is ``basis`` (MOLE-FLOW -> MASS-FLOW): a
    node's row follows its basis (attr 13), and a check must not write it to see. ``row`` when
    the basis is that one already or no sibling row is known."""
    def kind(b):                                      # MASS, MASS-FLOW, MASS-FRAC -> MASS
        return str(b or "").strip().upper().split("-")[0]
    try:
        cur = kind(node.AttributeValue(13))
    except Exception:
        cur = ""
    new = _BASIS_ROW.get(kind(basis))
    name = unit_table.dimension_name(row)
    old = next((p for p in _BASIS_ROW.values() if name.startswith(p)), None)
    if not cur or not new or not old or cur == kind(basis):
        return row
    want = new + name[len(old):]
    return next((r for r, d in unit_table.get_dimensions().items() if d.get("name") == want), row)


def _unit_info(node, basis: str | None = None) -> dict:
    """{"unit", "units"} of a node: its current unit and every unit of its dimension (the
    dimension it takes with ``basis``, when given)."""
    try:
        unit = node.UnitString or None
    except Exception:
        unit = None
    if not unit:
        return {"unit": None, "units": []}
    try:
        row = int(node.AttributeValue(2) or 0)        # HAP_UNITROW: the physical quantity
    except Exception:
        row = 0
    if not row:
        row = unit_table.find_dimension_by_unit(unit) or 0
    if row and basis:
        row = _basis_row(node, row, basis)
    units = unit_table.list_units_for_dimension(row) if row else []
    return {"unit": unit, "units": list(dict.fromkeys(units))}   # the unit table repeats a few names


def _enterable(node) -> bool | None:
    try:
        return bool(node.AttributeValue(7))           # HAP_ENTERABLE
    except Exception:
        return None


def _unwritable(app, path: str, unit: str | None, lang: str) -> str | None:
    """Why ``path`` (optionally in ``unit``) cannot be written, or None if it can."""
    why = _unwritable_as(app, path, unit, lang)
    return why and why[1]


def _unwritable_as(app, path: str, unit: str | None, lang: str,
                   basis: str | None = None) -> tuple[str, str, dict, dict] | None:
    """(code, why, texts, help) ``path`` (optionally in ``unit``, with ``basis``: the unit is one
    of that basis's) cannot be written -- code
    not_found, not_enterable or bad_unit (a check's problem, tab.check), ``why`` in ``lang``;
    ``texts`` the window's short line and ``help`` ``why`` in both languages (_langs) -- or
    None if it can."""
    def said(code, short, say):
        return code, say(lang), _tt(short, path=path, unit=unit), _langs(say)
    node = _node(app, path)
    if node is None:
        return said("not_found", "s_not_found", lambda x: _t(x, "not_found", path=path))
    if _enterable(node) is False:
        twin = next((path.replace(result, inp, 1) for result, inp in _INPUT_TWIN if path.startswith("\\Data\\Streams\\")
                     and (path.endswith(result) or (result.endswith("\\") and result in path))), None)
        return said("not_enterable", "s_not_input", lambda x: _t(x, "is_result", path=path) + (
            _t(x, "twin", label=aspen_labels.say(twin, None, x), path=twin) if twin else ""))
    if unit:
        info = _unit_info(node, basis)
        if not info["unit"]:
            return said("bad_unit", "s_no_unit", lambda x: _t(x, "no_unit", path=path, unit=unit))
        if info["units"] and unit.lower() not in (u.lower() for u in info["units"]):
            units = ", ".join(info["units"][:12]) + (" ..." if len(info["units"]) > 12 else "")
            return said("bad_unit", "s_bad_unit",
                        lambda x: _t(x, "bad_unit", unit=unit, path=path, cur=info["unit"], units=units))
    return None


def _children(app, path: str) -> list:
    node = _node(app, path)
    if node is None:
        return []
    els = node.Elements
    return [els.Item(i) for i in range(els.Count)]


def _kids(app, path: str) -> list:
    """The children of a node not known in advance, by its enumerator: Item(i) faults Aspen on
    some label-keyed tables (knowledge_tools._children). ``_children`` is for fixed folders."""
    node = _node(app, path)
    return [] if node is None else [c for c in knowledge_tools._children(node.Elements) if c is not None]


def snapshot(manager, session: str) -> dict:
    """The session's blocks, streams and components, and ``model``: the id of the model it
    holds, which the window's flowsheet arrangement is kept for. A stream's connected end also
    names its port (``from_port`` / ``to_port``: the block's Connections value, V15 "F(IN)")."""
    app = manager.get_app(session)
    src, dst, blocks = {}, {}, []
    for b in _children(app, r"\Data\Blocks"):
        name = str(b.Name)
        try:
            btype = str(b.AttributeValue(6) or "")      # RECORDTYPE, e.g. RadFrac
        except Exception:
            btype = ""
        blocks.append({"name": name, "type": btype})
        for c in _children(app, rf"\Data\Blocks\{name}\Connections"):
            raw = str(c.Value or "").strip()
            port = raw.upper()
            if "(IN)" in port:
                dst[str(c.Name)] = (name, raw)
            elif "(OUT)" in port:
                src[str(c.Name)] = (name, raw)
    streams = []
    for s in _children(app, r"\Data\Streams"):
        n = str(s.Name)
        a, b = src.get(n), dst.get(n)
        streams.append({"name": n, "from": a and a[0], "to": b and b[0],
                        **({"from_port": a[1]} if a else {}), **({"to_port": b[1]} if b else {})})
    comps = [str(c.Name) for c in _children(app, r"\Data\Components\Specifications\Input\TYPE")]
    return {"blocks": blocks, "streams": streams, "components": comps, "taken_at": time.time(),
            "model": _model_of(manager, session)}


def taken_names(app) -> dict:
    """What place_block and add_component refuse besides a name taken in its own folder, for a
    program's check (tools/wb_plan.Shadow, merged into the flowsheet): ``component_names``
    {label: {"aname", "dbname"}} -- a component is refused by any of them -- and ``flowsheeting``
    {"Design-Spec" | "Calculator" | "Transfer" | "Measurement": [names]} -- a block named like one
    crashed V15. Read when a check needs it, not with every snapshot (on a mid-size model ~0.1 s,
    a quarter of a snapshot)."""
    names: dict = {}
    for key in ("aname", "dbname"):
        for c in _children(app, rf"\Data\Components\Specifications\Input\{key.upper()}"):
            try:
                v = dispid.get(c, "Value")
            except Exception:
                continue
            if isinstance(v, str) and v.strip():
                names.setdefault(str(dispid.get(c, "Name")), {})[key] = v.strip()
    rivals: dict = {}
    for folder, kind in flowsheet_tools._BLOCK_RIVALS:
        have = [str(dispid.get(c, "Name")) for c in _children(app, folder)]
        if have:
            rivals[kind] = have
    return {"component_names": names, "flowsheeting": rivals}


def _model_of(manager, session: str) -> str | None:
    """The id of the model a session holds: ``manager.model_id`` (tools/model_registry.py),
    which a Save As, a reopen and a server restart keep, so the window's arrangement survives
    them; else a hash of the file on record (the same id for a file that never moved)."""
    ident = getattr(manager, "model_id", None)
    if callable(ident):
        try:
            mid = ident(session)
            if mid:
                return mid
        except Exception:
            logger.warning("workbench: no model id for %s", session, exc_info=True)
    return pfsv.model_id(_model_file(manager, session))


def _model_file(manager, session: str) -> str | None:
    """The file the session's model is bound to (where the server saves it), or None. Not
    Aspen's ``FullName``: that is the program, never the model."""
    get = getattr(manager, "session_file", None)
    if callable(get):
        try:
            return get(session)
        except Exception:
            logger.warning("workbench: no model file for %s", session, exc_info=True)
            return None
    files = getattr(manager, "_session_files", None) or {}
    return (files.get(session) or (None,))[0]


def block_status(app) -> dict:
    """{block: {"level": "error"|"warn", "msg", "lines"}} for every block whose last run
    did not end cleanly. Clean blocks are left out."""
    out = {}
    for b in _children(app, r"\Data\Blocks"):
        name = str(b.Name)
        stat = _node(app, rf"\Data\Blocks\{name}\Output\BLKSTAT")
        try:
            if stat is None or not stat.Value:
                continue
        except Exception:
            continue
        msg_node = _node(app, rf"\Data\Blocks\{name}\Output\BLKMSG")
        msg = " ".join(str(msg_node.Value or "").split()) if msg_node is not None else ""
        lines = [str(c.Value).rstrip() for c in _children(app, rf"\Data\Blocks\{name}\Output\PER_ERROR")
                 if c is not None and c.Value is not None][:40]
        text = (msg + " " + " ".join(lines)).upper()
        out[name] = {"level": "error" if "ERROR" in text else "warn", "msg": msg, "lines": lines}
    return out


_STREAM_VALUES = (("t", r"Output\RES_TEMP"), ("p", r"Output\RES_PRES"), ("f", r"Output\TOT_FLOW"))


def stream_values(app, flowsheet: dict | None) -> dict:
    """{stream: {"t"|"p"|"f": [value, unit]}}: the result labels the flowsheet can show."""
    out = {}
    for s in (flowsheet or {}).get("streams", []):
        vals = {}
        for key, rel in _STREAM_VALUES:
            node = _node(app, rf"\Data\Streams\{s['name']}\{rel}")
            if node is None:
                continue
            try:
                v = node.Value
            except Exception:
                v = None
            if isinstance(v, (int, float)):
                vals[key] = [v, _unit_info(node)["unit"]]
        out[s["name"]] = vals
    return out


_FRACS: dict = {}       # run record id -> _run_fracs' answer (the last few)


def _run_fracs(delta: dict) -> dict:
    """{stream: {component: [before, after]}}: the mole fractions the run of ``delta``
    (runlog.last_delta) moved, as its journal record lists them (a reflux change moves a
    product's purity, not its T / P / F); not the ones within Aspen's tolerances. Read once
    per run; {} when there are none."""
    rid, model = delta.get("id"), delta.get("model")
    if not rid or not model:
        return {}
    if rid not in _FRACS:
        try:
            rec, out = journal.find(model, rid, scan=500), {}
        except Exception:  # noqa: BLE001 -- the values layer goes on without them
            return {}
        if rec is None:
            return {}                             # (not written yet: asked again next time)
        for it in ((rec.get("delta") or {}).get("items") or []) if isinstance(rec.get("delta"), dict) else []:
            p = str(it.get("path") or "").split("\\") if isinstance(it, dict) else []
            if len(p) == 8 and p[2] == "Streams" and p[4:7] == ["Output", "MOLEFRAC", "MIXED"] and not it.get("small"):
                out.setdefault(p[3], {})[p[7]] = [it.get("b"), it.get("a")]
        while len(_FRACS) >= 8:
            _FRACS.pop(next(iter(_FRACS)))
        _FRACS[rid] = out
    return {s: dict(c) for s, c in _FRACS[rid].items()}


def _num(text: str):
    try:
        v = float(text)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def opt_result(run_dir: Path, st: dict, app, trace=None) -> dict | None:
    """An optimize step's evaluations and Pareto set, read back from the files the
    optimizer wrote (evaluations.csv, pareto.csv), with each column's unit. ``trace``
    gives the unit of an expression objective that names a single variable."""
    try:
        with open(run_dir / "evaluations.csv", encoding="utf-8") as f:
            rows = list(csv.reader(f))
    except OSError:
        return None
    if not rows:
        return None
    nv, no = len(st.get("variables") or []), len(st.get("objectives") or [])
    head = rows[0]

    def unit(path):
        node = _node(app, path or "")
        return _unit_info(node)["unit"] if node is not None else None

    variables = [{"name": head[3 + i], "path": v.get("path"), "unit": unit(v.get("path"))}
                 for i, v in enumerate(st.get("variables") or [])]
    objectives = [{"name": o.get("expr") or head[3 + nv + j], "path": o.get("path"),
                   "unit": unit(o["path"]) if o.get("path") else trace.unit(o.get("expr"), o.get("paths")) if trace else None,
                   "direction": o.get("direction", "minimize")} for j, o in enumerate(st.get("objectives") or [])]
    evals = [{"x": [_num(c) for c in r[3:3 + nv]], "f": [_num(c) for c in r[3 + nv:3 + nv + no]],
              "ok": (r[3 + nv + no] if len(r) > 3 + nv + no else "0") == "1"} for r in rows[1:3001]]
    pareto = []
    try:
        with open(run_dir / "pareto.csv", encoding="utf-8") as f:
            prows = list(csv.reader(f))[1:]
        pareto = [{"x": [_num(c) for c in r[:nv]], "f": [_num(c) for c in r[nv:nv + no]],
                   "best": len(r) > nv + no and r[nv + no] == "1"} for r in prows]
    except OSError:
        pass
    return {"id": st["id"], "kind": "opt", "algorithm": st.get("algorithm"), "run_dir": str(run_dir),
            "variables": variables, "objectives": objectives, "evals": evals, "pareto": pareto}


def _row(app, path: str, label, nodes: dict | None = None, ask: bool = False) -> dict | None:
    node = _node(app, path)
    if node is not None and nodes is not None:
        nodes[path] = node
    return None if node is None else _row_of(node, path, label, ask=ask)


_ROW_PROMPT = 600        # characters of an inspector row's prompt (the help card's)


def _attr_text(node, n: int, limit: int) -> str:
    """Attribute ``n`` of a node as one line of at most ``limit`` characters; "" when it has none.
    By DISPID (tools/dispid.py: ~0.06 ms live, late-bound ~0.5 ms and more)."""
    try:
        v = dispid.get(node, "AttributeValue", n)
    except Exception:
        return ""
    return " ".join(str(v).split())[:limit] if v not in (None, "") else ""


def _row_of(node, path: str, label, extra: bool = False, ask: bool = False) -> dict:
    """An inspector row. ``ask`` (Aspen idle on the session): an input row also carries its GUI
    prompt (attr 19, "" when Aspen has none) and its basis (attr 13, when it has one) -- what the
    window's help card shows without asking Aspen again."""
    try:
        value = _plain(node.Value)
    except Exception:
        value = None
    row = {"path": path, "label": label, "value": value, "input": "\\Input\\" in path}
    info = _unit_info(node)
    row["unit"] = info["unit"]
    if row["input"]:
        row["enterable"] = _enterable(node) is not False
        row["units"] = info["units"]
        if ask:
            row["prompt"] = _attr_text(node, 19, _ROW_PROMPT)
            basis = _attr_text(node, 13, 40)
            if basis:
                row["basis"] = basis
    if extra:
        row["extra"] = True
    return row


def _leaves(app, base: str, depth: int, limit: int, skip_zero: bool, nodes: dict | None = None,
            ask: bool = False, shown=()):
    """Rows for the scalar nodes under ``base`` that hold a value, ``depth`` levels deep: a
    generator of the rows so far, after each node read (inspect_steps), the last the whole list.
    ``skip_zero`` drops zeros, which is most of an Output branch's unused slots. ``nodes``
    collects {path: node} of the rows; ``ask``: _row_of's, except for the paths in ``shown``
    (rows the caller has already)."""
    rows: list[dict] = []

    def walk(path: str, rel: str, level: int):
        for child in _kids(app, path):
            if len(rows) >= limit:
                return
            name = str(child.Name)
            try:
                kids = child.Elements.Count
            except Exception:
                kids = 0
            if kids:
                if level < depth:
                    yield from walk(f"{path}\\{name}", f"{rel}{name}\\", level + 1)
                continue
            try:
                value = child.Value
            except Exception:
                continue
            if value is None or value == "" or (skip_zero and value == 0):
                continue
            if nodes is not None:
                nodes[f"{path}\\{name}"] = child
            p = f"{path}\\{name}"
            rows.append(_row_of(child, p, f"{rel}{name}", extra=True, ask=ask and p not in shown))
            yield rows

    yield from walk(base, "", 1)
    yield rows


def _learn_prompts(app, nodes: dict, types: dict, cap: int, known: dict | None = None) -> int:
    """Read the GUI prompt (attr 19, HAP_PROMPT; ~0.05 ms a field) of at most ``cap`` fields
    that no label names yet and keep it in learned.json (aspen_labels.learn): from then on the
    field is named by it, for this block type, here and in the timeline. A field without a
    prompt is kept as tried. ``nodes``: {path: node, or None to look it up}; ``types``: {block
    name: type}; ``known``: {path: prompt} already read (an inspector row's), not read again.
    Returns how many prompts were learned."""
    want = aspen_labels.learn_keys(list(nodes), types, cap)
    if not want:
        return 0
    got = {}
    for key, path in want.items():
        if known is not None and path in known:
            text = known[path]
        else:
            node = nodes.get(path) or _node(app, path)
            try:
                text = node.AttributeValue(19) if node is not None else None
            except Exception:
                text = None
        got[key] = " ".join(str(text).split()) if text else ""
    aspen_labels.learn(got)
    return len(got)


def _expand(app, base: str, rel: str) -> list[str]:
    """A docs row's path as Aspen has it under ``base``: itself, or its one {id} segment as each
    entry there (at most _DOC_IDS); a row with two such segments is a table, not rows: none."""
    segs = rel.split("\\")
    at = [i for i, s in enumerate(segs) if _ID_SEG.fullmatch(s)]
    if len(at) != 1:
        return [] if at else [rel]
    i = at[0]
    kids = _kids(app, "\\".join([base, *segs[:i]]))[:_DOC_IDS]
    return ["\\".join([*segs[:i], str(c.Name), *segs[i + 1:]]) for c in kids]


def _doc_rows(app, base: str, scope, nodes: dict, ask: bool, inputs: bool = True):
    """The inspector's rows from the docs (doc_index.rows_for): the object's general file -- else
    the first other file with a row here -- table by table, the rows Aspen has (_expand). Each
    row has ``g``, the heading of its table (radfrac.md's "Setup | Configuration"), and ``doc``,
    what the docs say it is for; ``inputs`` False: the results alone. A generator of the rows of
    the docs rows done so far, after each node read (inspect_steps), the last the whole list."""
    out, seen, file = [], set(), None
    for g in doc_index.rows_for(scope):
        if out and g["adv"] and g["file"] != file:
            break
        got = []
        for d in g["rows"] if inputs else [d for d in g["rows"] if d["io"] == "out"]:
            one, rels = [], _expand(app, base, d["rel"])
            yield out + got                                # (a list's entries read: a pass may end here)
            for rel in rels:
                path = f"{base}\\{rel}"
                r = None if path in seen else _row(app, path, rel, nodes, ask)
                seen.add(path)
                if r is not None:
                    one.append(_listed(dict(r, g=g["head"], doc=_doc_text(d.get("row"))), d, scope))
                yield out + got
            got += sorted(one, key=lambda r: r["value"] in (None, "", 0))[:_DOC_SHOW] if len(one) > _DOC_SHOW else one
        if got:
            file = g["file"]
            out += got
    yield out


def _forms(app, base: str, typ, scope, ask: bool) -> dict:
    """The inspector's ``forms`` and ``subs`` when the sheet layer applies (V15): the object's GUI
    forms in order (gui_sheets.outline), ``adv`` when the docs' general file of ``scope`` has no
    table under the form, each sheet's ``state`` done | todo | hidden -- a collection's or an
    id's sheet ``of`` each member, {"P-1": state} -- from its CC flags (gui_sheets.status; read
    only when ``ask``); ``subs``: the collections, their ``ids`` (None: not read) and forms."""
    cont = gui_sheets.container_of(base)
    if typ is None and cont == r"\Data\Streams":      # a stream: its record type (MATERIAL, HEAT, WORK)
        node = _node(app, base)
        typ = str(node.AttributeValue(6) or "") if node is not None else ""
    outline = gui_sheets.outline(typ, cont)
    if not outline:
        return {}
    st = IC.sheet_status(app, base, typ) if ask else None
    got: dict = {}
    for s in (st or {}).get("sheets") or ():
        got.setdefault((s["form"], s["sheet"] or "", s["header"] or ""), {})["/".join(s["ids"])] = s["state"]
    named = {g["head"].split("|")[0].strip().lower() for g in doc_index.rows_for(scope, "general")} if scope else set()
    forms = []
    for f in outline:
        if st and f["form"] in st.get("absent", ()):
            continue
        sheets = []
        for sh in f["sheets"]:
            one = {k: sh[k] for k in ("cls", "header", "title")}
            states = got.get((f["form"], sh["cls"], sh["header"] or ""), {})
            if "" in states:
                one["state"] = states.pop("")
            if states:
                one["of"] = states
            sheets.append(one)
        forms.append({"form": f["form"], "title": f["title"], "coll": f["coll"],
                      "adv": bool(named) and f["title"].lower() not in named, "sheets": sheets})
    subs = [{"coll": c, "ids": (st["subs"].get(c) if st else None), "forms": fs}
            for c, fs in gui_sheets.collections(typ, cont).items()]
    return {"forms": forms, "subs": subs, **({"forms_ms": st["ms"], "forms_cut": st["cut"]} if st else {})}


def _list_info(node) -> dict | None:
    """A sheet's list of values as the inspector draws it, a small table: ``dn`` the dimension
    name of its rows (DimensionName 0: FEED-SID, HEATER-STAGE, KLA-CID; "" rows without labels)
    and ``lk`` what labels them -- stage, stream, comp, text or none. None for a list with a
    second dimension (FRACS: stream x substream), drawn as rows."""
    try:                                             # (by DISPID: ~0.06 ms a read live, a refusal too)
        els = dispid.get(node, "Elements")
        dn = str(dispid.get(els, "DimensionName", 0) or "")
    except Exception:
        return None
    try:
        dispid.get(els, "DimensionName", 1)
        return None
    except Exception:
        pass
    up = dn.upper()
    lk = "none" if not dn else "stage" if up.endswith("STAGE") else "stream" if up.endswith(("STREAM", "SID")) \
        else "comp" if up.endswith("CID") else "text"
    return {"dn": dn, "lk": lk}


def _sheet_rows(app, base: str, path: str, nodes: dict, depth: int = 0, lists: list | None = None) -> list[dict]:
    """A sheet field's inspector row (_row_of, asked), or its entries' rows where it is a list
    (Dimension > 0; two levels, _SHEET_KIDS entries at most; a list with none: its own row); []
    when Aspen has no such node. A list of values goes into ``lists`` too (_list_info, its path)."""
    node = _node(app, path)
    if node is None:
        return []
    try:
        dim = dispid.get(node, "Dimension")
    except Exception:
        dim = 0
    if dim and depth == 0 and lists is not None:
        li = _list_info(node)
        if li is not None:
            lists.append(dict(li, path=path))
    kids = _kids(app, path)[:_SHEET_KIDS] if dim and depth < 2 else []
    if not kids:
        nodes[path] = node
        return [_row_of(node, path, path[len(base) + 1:], ask=True)]
    return [r for c in kids for r in _sheet_rows(app, base, path + "\\" + str(c.Name), nodes, depth + 1)]


_STRUCT_OPS = ("row_add", "row_del", "sub_add", "sub_del")
_STRUCT_LISTS = 8        # lists of one table (they share its rows) a struct event may name


def _said(res: str) -> str:
    """The words of Aspen's refusal in a tool's answer (its COM error's description), else the answer."""
    hits = re.findall(r"\((?:-?\d+), (?:None|'[^']*'), '([^']+)', None, -?\d+, -?\d+\)", str(res))
    return hits[-1].strip() if hits else " ".join(str(res).split())[:300]


def _rows_change(manager, session: str, add: bool, lists: list, label: str) -> str:
    """Row ``label`` added to (insert_row, then set_label; "" or "#n": a list without labels) or
    taken out of (remove_row) the lists of one table, the first first: a list that shares its rows
    has followed it by then and is left alone (common.md: a row is inserted once). A label Aspen
    refuses leaves a row without one (live V15: a word or 40 on a stage list of 10, a stream or
    component that is not there): it is removed again. One Aspen changes (stage 2.5: 2) goes on as
    Aspen keeps it. Returns the tool's answer, the label as kept -- an "Error ..." / "Index ..." one
    when Aspen refused."""
    app, done = manager.get_app(session), []
    plain = not label or label.startswith("#")
    if (_list_info(_node(app, lists[0])) or {}).get("lk") in ("stream", "comp"):
        label = label.upper()                          # (live V15 refuses "f2", "benzene": IDs are upper-case)
    before = {p: [str(c.Name) for c in _kids(app, p)] for p in lists}
    for p in lists:
        now = [str(c.Name) for c in _kids(app, p)]
        at = next((i for i, n in enumerate(now) if n.upper() == label.upper()), None)
        if add:
            if (len(now) > len(before[p])) if plain else at is not None:
                continue
            res = manager.insert_row(session, p)
            m = re.search(r"index=(\d+)", res)
            if not m:
                return res
            if not plain:
                i = int(m.group(1))
                lab = manager.set_label(session, p, i, label)
                if not lab.startswith("Set label"):
                    manager.remove_row(session, p, i)
                    return lab
                now = [str(c.Name) for c in _kids(app, p)]
                label = now[i] if i < len(now) and now[i] else label     # as Aspen keeps it (stage 2.5: 2)
        else:
            if at is None or (plain and len(now) < len(before[p])):
                continue
            res = manager.remove_row(session, p, at)
            if not res.startswith("Removed"):
                return res
        done.append(p)
    return (f"{'Inserted' if add else 'Removed'} row '{label}' at {', '.join(done)}." if done
            else f"Error: row '{label}' {'is there already' if add else 'is not there'}.")


def _tkey(tg) -> tuple:
    """An inspector target as a key: a block's or a stream's name, a model object's path (any case)."""
    if not isinstance(tg, dict):
        return (None, "")
    return (tg.get("kind"), str(tg.get("path" if tg.get("kind") == "object" else "name") or "").upper())


def _in_place(old: list, got: list) -> list:
    """Rows (or lists) read so far laid over the ones shown before, by path, in the shown order: a
    row read takes its old one's place (still greyed where the old one was: the settings that grey
    it are read last), one not read yet stays, a new one comes after -- a view read again neither
    shrinks nor reorders while it is read."""
    new = {r.get("path"): r for r in got}
    out = []
    for r in old:
        n = new.pop(r.get("path"), None)
        out.append(r if n is None else dict(n, enterable=False, off=r["off"]) if r.get("off") and not n.get("off") else n)
    return out + [r for r in got if r.get("path") in new]


def _base(tg) -> str | None:
    """The tree path of an inspector target: a block's, a stream's, or a model object's own
    ``path`` (an object the form table's kinds name: a singleton, or in one of its containers)."""
    if not isinstance(tg, dict):
        return None
    kind, name, path = tg.get("kind"), str(tg.get("name") or ""), str(tg.get("path") or "")
    if kind in ("block", "stream") and name and "\\" not in name:
        return f"\\Data\\{'Blocks' if kind == 'block' else 'Streams'}\\{name}"
    if kind == "object" and path.startswith("\\Data\\") and len(path) <= 300:
        return path if gui_sheets.container_of(path) in gui_sheets.kinds() else None
    return None


def inspect(manager, sess: dict, session: str, target: dict, all_fields: bool) -> dict:
    """The parameters of one block, stream or model object (a target {kind: object, path},
    gone when Aspen no longer has it), with current values and units, each row with
    ``loc`` (aspen_labels.loc: where it is, in words): the docs' rows of its type (_doc_rows,
    each with its table's heading ``g``), with ``all_fields`` its other fields too. Fields no
    label names yet get their GUI prompt read first (_learn_prompts, at most _LEARN_MAX) -- not
    while Aspen works for a program, an optimize or a call on the session (_computing); then
    too, and only then, an input row carries its prompt and basis for the window's help card
    (_row_of ``ask``), and the learning takes those rows' prompts without reading them again; a
    field still named by its code is named by its docs row (_doc_named). An object the last
    cheap scan flags incomplete carries ``missing`` -- its deep look, done now when Aspen
    is idle and none is current -- and its empty fields as rows (_inspect_missing). On V15 the
    view also has ``forms`` and ``subs`` (_forms). All at once; the window's inspect job reads
    it a pass at a time (inspect_steps)."""
    for view in inspect_steps(manager, sess, session, target, all_fields):
        pass
    return view


def _named(rows: list, types: dict, all_: bool = True) -> None:
    """Each row's ``loc`` (aspen_labels.labels, no COM; a field named by its code: _doc_named) --
    only the rows without one where not ``all_`` -- and an input holding an option code its
    ``opt`` (_opts)."""
    rows = rows if all_ else [r for r in rows if "loc" not in r]
    locs = aspen_labels.labels([r["path"] for r in rows], types)
    for r in rows:
        lc = locs.get(r["path"])
        r["loc"] = _doc_named(lc, r.get("doc")) if lc else lc
    _opts(rows, types)


def _opts(rows: list, types: dict) -> None:
    """An input row holding an option code (PD, TOTAL) gets ``opt``, what the code means in words
    (aspen_labels.meaning, no COM): the inspector shows it in place of the code; a unitless
    input with no ``choices`` yet (a sheet's row) the list Aspen's extraction gives (_listed)."""
    for r in rows:
        m = aspen_labels.meaning(r["path"], r.get("value"), types) if r.get("input") else None
        if m:
            r["opt"] = m
        else:
            r.pop("opt", None)
        if "choices" not in r:
            _listed(r, {}, types)


def _off(rows: list, off: dict | None) -> None:
    """The inputs the current settings turn off (inputs_check.off_fields: a CC condition at 0, as
    the GUI greys them; Aspen's HAP_ENTERABLE stays 1 there) marked as Aspen marks the ones it
    refuses: ``enterable`` false, and ``off`` "cc" (the window names the option that does it)."""
    if not off:
        return
    for r in rows:
        rel = str(r.get("path") or "").split("\\Input\\", 1)
        if r.get("input") and len(rel) == 2 and rel[1] in off:
            r.update(enterable=False, off="cc")


def _listed(r: dict, d: dict, types) -> dict:
    """A unitless input's ``choices``, the values it takes from a list (aspen_labels.choices: the
    docs row ``d``'s codes, the extraction's, our own words), for the inspector's menu; one the docs
    type as a component or stream ID its ``pick`` (comp | stream: the window offers the model's).
    ``types``: {block: type}, or a block or stream type. No COM. Returns ``r``."""
    if not r.get("input") or r.get("unit"):
        return r
    t = types if isinstance(types, dict) else {aspen_labels._block_of(r["path"]): types}   # noqa: SLF001 -- its own path parser
    ch = aspen_labels.choices(r["path"], r.get("value"), t, d.get("options") or ())
    if ch:
        r["choices"] = ch
    vt = str(d.get("vtype") or "").strip("` ").lower()
    if not ch and vt in ("component", "component id", "stream", "stream id"):
        r["pick"] = "comp" if vt.startswith("component") else "stream"
    return r


def inspect_steps(manager, sess: dict, session: str, target: dict, all_fields: bool, ms=None, was=None):
    """inspect() a pass at a time (a stream's 136 rows took 1.4 s of the sync loop): a
    generator of the view, after every ``ms`` of node reads (None: never) the rows read so far,
    named, with ``reading`` -- laid over the rows ``was`` (the view shown before, of the same target)
    in their places (_in_place), so a view read again neither shrinks nor reorders -- and at the end the whole
    view. The forms, the missing marks and the prompts' learning come with the last."""
    app = manager.get_app(session)
    kind, name = (target or {}).get("kind"), (target or {}).get("name")
    fs = sess.get("flowsheet") or {}
    view = {"target": target, "all": all_fields, "t": time.time(), "rows": []}
    base = _base(target)
    if app is None or base is None:
        yield view
        return
    nodes: dict = {}
    types: dict = {}
    ask = not _computing(session)
    old = [r for r in (was or {}).get("rows") or () if isinstance(r, dict)] \
        if _tkey((was or {}).get("target")) == _tkey(target) else []
    due = [time.perf_counter() + ms / 1000] if ms else None

    def rounds(gen, skip=()):
        """The rows of a row generator (but the paths in ``skip``) after the view's, the view so far
        yielded each time ``ms`` is spent."""
        rows = []
        for rows in gen:
            if due and time.perf_counter() > due[0]:
                part = view["rows"] + [r for r in rows if r["path"] not in skip]
                _named(part, types, False)
                yield dict(view, rows=_in_place(old, part), reading=True, t=time.time())
                due[0] = time.perf_counter() + ms / 1000
        view["rows"] = view["rows"] + [r for r in rows if r["path"] not in skip]

    if kind == "block":
        typ = scope = next((b["type"] for b in fs.get("blocks", []) if b["name"] == name), "")
        view["type"] = typ
        types = {name: typ} if typ else {}
        yield from rounds(_doc_rows(app, base, typ, nodes, ask))
    elif kind == "stream":
        typ, scope = None, "STREAM"
        stream = next((s for s in fs.get("streams", []) if s["name"] == name), {})
        yield from rounds(_doc_rows(app, base, scope, nodes, ask, inputs=not stream.get("from")))   # a feed's inputs only
    else:                                                # a model object: its docs scope, its record type
        node = _node(app, base)
        if node is None:
            view["gone"] = True
            yield view
            return
        typ, scope = _attr_text(node, 6, 40) or None, doc_index.scope_of(base)
        view["type"] = typ
        if scope:
            yield from rounds(_doc_rows(app, base, scope, nodes, ask))
    if gui_sheets.applies():
        try:
            view.update(_forms(app, base, typ, scope, ask))
            if ask:
                _off(view["rows"], IC.off_fields(app, base, typ or (_attr_text(_node(app, base), 6, 40) if kind == "stream" else None)))
        except Exception:
            logger.warning("workbench: the forms of %s not read", base, exc_info=True)
    if all_fields:
        depth, shown = (2 if kind == "stream" else 1), {r["path"] for r in view["rows"]}
        if not view.get("forms"):
            yield from rounds(_leaves(app, f"{base}\\Input", depth, 400, skip_zero=False, nodes=nodes, ask=ask, shown=shown), shown)
        yield from rounds(_leaves(app, f"{base}\\Output", depth, 400, skip_zero=True, nodes=nodes), shown)
    try:
        _inspect_missing(manager, session, base, view, nodes, ask, types.get(name) if kind == "block" else typ)
    except Exception:
        logger.warning("workbench: what %s still lacks not shown", base, exc_info=True)
    try:
        if ask:
            _learn_prompts(app, {r["path"]: nodes.get(r["path"]) for r in view["rows"]}, types, _LEARN_MAX,
                           known={r["path"]: r["prompt"] for r in view["rows"] if "prompt" in r})
    except Exception:
        logger.warning("workbench: field prompts of %s not read", base, exc_info=True)
    _named(view["rows"], types)
    yield view


# ---------------------------------------------------------------------------
# What the model still lacks before Aspen can run -- the window's "Missing inputs" panel,
# like Aspen's Next. Two layers (tools/inputs_check.py): a cheap scan (COMPSTATUS only, <= ~25
# ms) after runs and edits -- debounced, on the sync loop, never while a program or another
# writer holds the session or Aspen works for a call -- decides the session's ``missing``; a
# deep look at an object (its empty fields, the rules the server can decide, its ports) runs
# only when the window asks: an inspector on an incomplete object, or the event missing (the
# panel), at most _MISS_DEEP_MAX objects, one at a time. Only what the server can decide counts
# as required -- an empty field a GUI rule names unconditionally, a port Aspen flags open --;
# other empty fields are counted (``n_values``, ``n_lists``: a RadFrac has ~1270 fields and no
# attribute marks the required ones), and the rules matched by keyword overlap are kept apart
# (``cands``, Aspen's own text, conditions unchecked).
#
# The session's ``missing`` (state.json, at most _MISS_MAX bytes):
#   {"v": 1, "t" (the scan), "state": complete | incomplete | unknown (not scanned yet) | off
#    (ASPEN_MCP_MISSING_SCAN=0 and no check asked), "auto", "runnable" (run_simulation would start:
#    an open required port stops it, but counts only when the scan read the ports), "flowsheet" (Aspen flags a required port
#    open), "n", "objects": [{"path", "sec", "name", "type", "kind" (block | stream: the
#    inspector's target kind; None: not inspectable), "what"? (components | method | ports | folder
#    | flowsheet), "open_ports"?, and once looked at in depth _miss_fold's counts, "first" (at most
#    _MISS_FIRST items, _miss_item), "cands", "hints"}] (at most _MISS_OBJECTS), "more", "scan_ms",
#    "cut"? (the automatic scan stopped listing at _MISS_SCAN_MS: the event missing lists all),
#    "stale"? (a scan waits: edits since, or the session held), "partial", "pending" (the objects
#    of the latest missing event not looked at: it stopped for a writer), "deep" {"status":
#    running | done | partial | waiting, "n", "done", "t"}}
# ---------------------------------------------------------------------------
_MISS_DEBOUNCE_S = 2.0   # a cheap scan waits this long after the last edit ...
_MISS_WAIT_MAX_S = 10.0  # ... and no longer than this after the first still waiting
_MISS_PORT_BLOCKS = 8    # the cheap scan finds open required ports (~2 ms a block) in models this small
_MISS_SCAN_MS = 16.0     # ... and reads no more children after this (the containers' own bits after it: ~5 ms)
_MISS_REFRESH_READS = 3  # values a scan reads the GUI's way per flagged block (inputs_check.refresh), once each ...
_MISS_REFRESH_MS = 150.0  # ... within this for all (a fresh MIXER clears on the first, ~3-5 ms a read)
_MISS_DEEP_MAX = 10      # objects one missing event looks at in depth
_MISS_DEEP_MS = 250.0    # ... each at most this long (inputs_check.deep budget_ms, cap LIGHT_CAP)
_MISS_OBJECTS = 40       # objects the session's ``missing`` lists (the rest counted in ``more``)
_MISS_FIRST = 3          # items an object shows there
_MISS_ITEMS = 12         # items an inspector's ``missing`` shows, and empty fields it adds as rows
_MISS_CANDS = 3          # candidate rules kept per object
_MISS_TEXT = 300         # characters of a rule
_MISS_MAX = 12 * 1024    # bytes of the session's ``missing`` (JSON, UTF-8)
_MISS_REFUSED = "required inputs are incomplete"            # main_tools.run_simulation's refusal
_MISS_WHAT = {r"\Data\Components\Specifications": "components", r"\Data\Properties\Specifications": "method"}

# ---------------------------------------------------------------------------
# Why the last run failed (tools/diagnose.py). Every run record this server writes --
# the AI's run_simulation, the window's Run, a program's run step, a run found made in Aspen's
# window -- reaches _diag_runs (journal.listen); the sync loop's next pass (Workspace.diag_tick)
# builds the card of a session a tab shows once its block status was read after that run (a run
# that ran: the results refresh every run already has, asked for when it is not due), from what
# the run itself read -- no COM of its own but the property method, read once per session and
# again after a record touched \Data\Properties (the error history's third score).
#
# The session's ``diag`` (state.json, at most _DIAG_MAX bytes; None until a run failed): the card
# of diagnose.card ("v", "level" error | warn | refused, "run" -- that run's record in
# brief {"id", "t", "op", "status", "seq", "actor", "via", "first_error"?} --, "blocks", "explain",
# "general", "lore", "suspects", "missing" -- a refused run's {"n", "objects", "more"?, "stale"?})
# plus "model", "session", "lang" (of its words; rebuilt when the window's changes), "t" (built),
# "ms" (to build), "pop" (the user's own run -- the window's Run, a program the window started:
# the window may show its one-line bar once), "cut"? (_diag_fit shortened it) and, once a later
# run ended ok or warn, "fixed": that run in brief. The session's ``run_msgs``: the latest run's
# Run-Status lines (<= 20), its ``pm``: the global property method.
_DIAG_MAX = 12 * 1024    # bytes of the session's ``diag``
_DIAG_READ = 600         # characters of workbench_read's ``diagnosis`` text
_DIAG_LEVELS = frozenset({"error", "warn", "refused"})
_RUNS: dict = {}         # model -> the newest run record this server wrote (slim), from _diag_runs
_PM_DIRTY: set = set()   # models a record touched \Data\Properties of since their pm was read
_RUNS_LOCK = threading.Lock()
_RUN_KEYS = ("id", "t", "op", "status", "seq", "actor", "via", "session", "group", "blocks", "msgs", "nmsgs",
             "result", "first_error", "errors", "warnings", "first_warn")


def _diag_runs(model: str, recs) -> None:
    """journal.listen (any thread, no I/O): the newest run record of each model for the sync
    loop's diag_tick; a record about the property method has it read again."""
    for r in recs:
        if r.get("kind") != "change":
            continue
        tg = r.get("target") if isinstance(r.get("target"), dict) else {}
        if "\\properties\\" in str(tg.get("path") or r.get("path") or "").lower() or r.get("tool") == "set_property_method":
            with _RUNS_LOCK:
                _PM_DIRTY.add(model)
        if r.get("op") == "run" and r.get("status") in ("ok", "warn", "error", "refused"):
            with _RUNS_LOCK:
                _RUNS[model] = {k: r[k] for k in _RUN_KEYS if r.get(k) is not None}
                while len(_RUNS) > 64:
                    _RUNS.pop(next(iter(_RUNS)))


journal.listen(_diag_runs)


def _diag_inherit(new: str, old: str) -> None:
    """journal.on_split: a failed run's diagnose group split the AI's group ``old`` mid-request --
    what the user granted ``old`` goes on for ``new``: a stuck rule they muted (tools/stuck.py)
    and the risky calls they let through for it (the brakes' ``allow``)."""
    for rule in stuck.muted(old):
        stuck.mute(new, rule)
    ws = _WS
    allow = getattr(getattr(ws, "brake", None), "allow", None)
    if isinstance(allow, dict) and allow.get(old):
        allow.setdefault(new, set()).update(allow[old])


journal.on_split(_diag_inherit)


def _diag_size(x) -> int:
    return len(json.dumps(x, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8"))


def _diag_fit(d: dict) -> dict:
    """The session's ``diag`` within _DIAG_MAX bytes: each block's lines past 8 go first, then
    the error-history texts cut to 200 characters, the suspects past 8 (counted in ``more``), the
    blocks past 6, the general checks; ``cut`` says so."""
    if _diag_size(d) <= _DIAG_MAX:
        return d
    sus = d.get("suspects") if isinstance(d.get("suspects"), dict) else {}

    def fewer_suspects():
        for k in ("items", "struct"):
            xs = sus.get(k) or []
            if len(xs) > 8:
                sus["more"] = (sus.get("more") or 0) + len(xs) - 8
                sus[k] = xs[:8]

    for shrink in (lambda: [b.__setitem__("lines", b["lines"][:8]) for b in d.get("blocks") or ()],
                   lambda: [lo.__setitem__(k, str(lo[k])[:200]) for lo in d.get("lore") or ()
                            for k in ("cause", "fix", "note", "title") if lo.get(k)],
                   fewer_suspects,
                   lambda: d.__setitem__("blocks", (d.get("blocks") or [])[:6]),
                   lambda: d.__setitem__("general", []),
                   lambda: [b.__setitem__("lines", b["lines"][:2]) for b in d.get("blocks") or ()]):
        shrink()
        d["cut"] = True
        if _diag_size(d) <= _DIAG_MAX:
            break
    return d


def _miss_auto() -> bool:
    """The automatic cheap scan is on (ASPEN_MCP_MISSING_SCAN=0 turns it off; the panel's own
    check -- the event missing -- still works)."""
    return os.environ.get("ASPEN_MCP_MISSING_SCAN", "1").strip() != "0"


def _miss_text(text, n: int) -> str:
    """One line of at most ``n`` characters, tree paths' backslashes written as ›."""
    s = " ".join(str(text or "").split()).replace("\\", " › ")
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def _miss_item(x: dict, typ) -> dict:
    """One missing item (inputs_check.deep's ``missing``) as the window shows it, with what it
    needs to act on it: ``path`` (a field: open the inspector on the object and focus that row,
    which _inspect_missing adds; a port: the port node), ``label`` and ``where`` (Aspen's English
    words, tools/aspen_labels.py; ``gl`` the zh-TW gloss), ``rule`` (the rule text that makes it
    required, or None: Aspen's own, or a sentence of this server's, which also has ``rule_zh``),
    ``rule_by`` "server" (only when the requirement is this project's rule, not Aspen's: a column's
    operating spec count), ``certainty`` required | unset, ``source`` rule | port | spec | empty |
    object | field | sheet (empty on the form sheet Aspen marks incomplete, named in ``sheet``),
    ``kind`` value | list | None, ``set`` (a scalar input: a set block or the inspector can fill
    it); a port item its ``port`` and the ``ports`` any one of which will do."""
    path = str(x.get("path") or "")
    it = {"path": path, "field": x.get("field"), "certainty": x.get("certainty"), "source": x.get("source"),
          "kind": x.get("kind")}
    lc = aspen_labels.loc(path, typ)
    if x.get("source") == "port":
        it.update(label=x.get("port"), port=x.get("port"), ports=list(x.get("ports") or [])[:6])
    else:
        name = lc.get("field") if lc.get("src") != "code" else \
            (aspen_labels.short_prompt(x.get("prompt")) or lc.get("field"))
        it["label"] = _miss_text(aspen_labels.DOT.join([str(name or x.get("field") or "?")]
                                                         + [str(q) for q in lc.get("q") or []]), 80)
        if lc.get("gl"):
            it["gl"] = lc["gl"]
    it["where"] = _miss_text(aspen_labels.text(lc, "full", "en"), 160)
    it["rule"] = _miss_text(x.get("rule"), _MISS_TEXT) or None
    if it["rule"] and x.get("rule_zh"):
        it["rule_zh"] = _miss_text(x["rule_zh"], _MISS_TEXT)
    if it["rule"] and x.get("rule_by"):
        it["rule_by"] = x["rule_by"]
    it["set"] = x.get("source") != "port" and x.get("kind") != "list" and "\\Input\\" in path
    if x.get("sheet"):
        it["sheet"] = _miss_text(x["sheet"], 80)          # the form sheet Aspen marks incomplete
    at = x.get("at") or (_sheet_at(path, typ) if it["set"] else None)
    if at:                                                # the sheet the inspector opens for it
        it["at"] = {"form": at["form"], "sheet": at["sheet"], "ids": "/".join(at.get("ids") or ())}
    return it


def _sheet_at(path: str, typ):
    """{form, sheet} of the first sheet the workbench shows that binds a field of a block or a
    stream (gui_sheets.sheet_of), or None."""
    seg = path.split("\\")
    if len(seg) < 6 or seg[2] not in ("Blocks", "Streams") or not gui_sheets.applies():
        return None
    hit = gui_sheets.sheet_of(typ or ("MATERIAL" if seg[2] == "Streams" else None), "\\".join(seg[:3]),
                              "\\".join(seg[4:]))
    return {"form": hit[0], "sheet": hit[1]} if hit else None


def _miss_fold(d: dict, typ, n_items: int, key: str = "first") -> dict:
    """An object's deep look (inputs_check.deep) as the window shows it: ``deep`` ok | error; the
    counts -- ``n_required`` (what the server can decide: an empty field a rule names, a required
    port Aspen flags open), ``n_values`` (other empty fields that take one value), ``n_lists``
    (empty tables and lists), ``n_missing`` all of them; ``more_fields``: the walk stopped at its
    cap or time budget, so they are lower bounds --; the first ``n_items`` items under ``key``
    (_miss_item: required first, then values, then lists); ``cands`` (at most _MISS_CANDS rules
    matched by keyword overlap: Aspen's own text, its conditions unchecked) and ``n_cands``;
    ``hints`` (material ports with nothing connected that Aspen does not require: mostly
    optional); ``rules`` when the rule catalog is not there (loading | unavailable); ``ms``."""
    items = d.get("missing") or []
    n_all, n_req, n_val = d.get("n_missing") or 0, d.get("n_required") or 0, d.get("n_values") or 0
    f = {"deep": "error" if d.get("error") else "ok", "n_missing": n_all, "n_required": n_req,
         "n_values": n_val, "n_lists": max(0, n_all - n_req - n_val),
         key: [_miss_item(x, typ) for x in items[:n_items]]}
    if d.get("truncated") or (d.get("n_unset") or 0) >= IC.LIGHT_CAP:
        f["more_fields"] = True
    cands = d.get("candidates") or []
    if cands:
        f["n_cands"] = len(cands)
        f["cands"] = [{"rule": _miss_text(c.get("rule"), _MISS_TEXT), "score": c.get("score")}
                      for c in cands[:_MISS_CANDS]]
    p = d.get("ports") or {}
    req = set(p.get("required_open") or ())
    hints = [x for x in list(p.get("open_in") or ()) + list(p.get("open_out") or ()) if x not in req]
    if hints:
        f["hints"] = hints[:8]
    if d.get("rules") in ("loading", "unavailable"):
        f["rules"] = d["rules"]
    f["ms"] = d.get("ms")
    return f


def _miss_objects(sc: dict) -> list[dict]:
    """The objects a cheap scan flags, as the session's ``missing`` lists them: the components
    and the property method first (a blank model's first steps), then Aspen's order; a flagged
    folder none of whose children is listed (the Sensitivity folder: its children are never
    read by the scan) as itself, ``what`` folder; \\Data\\Flowsheet, ``what`` flowsheet, while
    Aspen flags an open required port and the scan did not read the ports."""
    out = []
    for o in sc.get("objects") or []:
        p = o["path"]
        e = {"path": p, "sec": o.get("sec"), "name": o.get("name"), "type": o.get("type"),
             "kind": {"Blocks": "block", "Streams": "stream"}.get(o.get("sec")) if p.count("\\") == 3 else None}
        if e["kind"] is None and _base({"kind": "object", "path": p}):
            e["kind"] = "object"                              # (its inspector, as a model object)
        what = _MISS_WHAT.get(p) or ("ports" if o.get("ports_only") else None)
        if what:
            e["what"] = what
        if o.get("open_ports"):
            e["open_ports"] = list(o["open_ports"])[:6]
        out.append(e)
    out.sort(key=lambda e: e.get("what") not in ("components", "method"))       # (stable)
    listed = [o["path"] for o in sc.get("objects") or []]
    for cont in sc.get("containers") or []:
        if not any(p.startswith(cont + "\\") for p in listed):
            parts = cont.split("\\")
            out.append({"path": cont, "sec": parts[-2], "name": parts[-1], "type": None, "kind": None,
                        "what": "folder"})
    if sc.get("flowsheet") and not sc.get("ports_read"):
        out.append({"path": IC._FLOWSHEET, "sec": "Data", "name": "Flowsheet", "type": None, "kind": None,
                    "what": "flowsheet"})
    return out


def _miss_size(x) -> int:
    return len(json.dumps(x, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _miss_fit(m: dict) -> dict:
    """The session's ``missing`` within _MISS_MAX bytes: the items' ``where`` go first (the
    window names a path itself), then the candidate texts (``n_cands`` stays), the items past an
    object's first, the port hints, the rules cut to 100 characters; last, objects from the end
    (counted in ``more``)."""
    if _miss_size(m) <= _MISS_MAX:
        return m
    objs = m["objects"]

    def items():
        return [it for o in objs for it in o.get("first") or ()]
    for shrink in (lambda: [it.pop("where", None) for it in items()],
                   lambda: [o.pop("cands", None) for o in objs],
                   lambda: [o.__setitem__("first", o["first"][:1]) for o in objs if o.get("first")],
                   lambda: [o.pop("hints", None) for o in objs],
                   lambda: [it.update({k: _miss_text(it[k], 100) for k in ("rule", "rule_zh") if it.get(k)})
                            for it in items() if it.get("rule")]):
        shrink()
        if _miss_size(m) <= _MISS_MAX:
            return m
    while objs and _miss_size(m) > _MISS_MAX:
        cut = max(1, len(objs) // 5)
        del objs[-cut:]
        m["more"] = m.get("more", 0) + cut
    return m


def _types_of(sess) -> dict:
    fs = (sess.get("flowsheet") if isinstance(sess, dict) else None) or {}
    return {b["name"]: b.get("type") for b in fs.get("blocks") or [] if isinstance(b, dict) and b.get("name")}


def _diag_read(sess) -> dict | None:
    """workbench_read's ``diagnosis``: the session's diagnosis card as one line for the AI
    (diagnose.say: where the run failed, the failure kind in plain words, Aspen's line, what
    changed since the last good run -- fields by label and path), at most _DIAG_READ
    characters; None while no run failed."""
    d = sess.get("diag") if isinstance(sess, dict) else None
    if not isinstance(d, dict) or d.get("level") not in _DIAG_LEVELS:
        return None
    types = _types_of(sess)
    text = diagnose.say(d, lambda p: aspen_labels.named(p, types, "path"))
    out = {"level": d["level"], "run": (d.get("run") or {}).get("id"), "text": _fit(text, _DIAG_READ)}
    if d.get("fixed"):
        out["fixed"] = True
    return out


def _miss_read(m) -> dict | None:
    """workbench_read's ``missing``: what the user's panel says the model still lacks, in at
    most ~600 characters (check_inputs has the details); None before a scan."""
    if not isinstance(m, dict) or m.get("state") not in ("complete", "incomplete"):
        return None
    out = {"state": m["state"], "n": m.get("n", 0), "runnable": m.get("runnable")}
    names, keep = [f"{o.get('name')} ({o['type']})" if o.get("type") else f"{o.get('sec')} › {o.get('name')}"
                   for o in m.get("objects") or []], []
    for s in names:
        if len(", ".join(keep + [s])) > 400:
            break
        keep.append(_miss_text(s, 80))
    if keep:
        out["objects"] = keep
        if out["n"] > len(keep):
            out["more"] = out["n"] - len(keep)
        out["hint"] = "check_inputs gives the details"
    if m.get("stale"):
        out["stale"] = True
    return out


def _inspect_missing(manager, session: str, base: str, view: dict, nodes: dict, ask: bool, typ) -> None:
    """The completeness scan on an inspector: when the last cheap scan flags ``base``, its deep look
    (Workspace.miss_deep_of: the current one, else one now if ``ask``) as ``view["missing"]``
    (_miss_fold, at most _MISS_ITEMS ``items``; ``deep`` waiting while Aspen is busy), and the
    empty scalar input fields among those items as rows marked ``missing`` (with ``certainty``
    and ``rule``): a row shown already gets the marks, one not shown is read and put after the
    docs' rows, before the ones "all fields" added."""
    ws = _WS
    sc = ws.miss_sc.get(session) if ws is not None else None
    if sc is None or not any(o["path"] == base for o in sc["objects"]):
        return
    d = ws.miss_deep_of(manager, session, base, ask)
    if d is None:
        view["missing"] = {"path": base, "deep": "waiting"}
        return
    view["missing"] = dict(_miss_fold(d, typ, _MISS_ITEMS, "items"), path=base)
    app, rows = manager.get_app(session), view["rows"]
    at, added = {r["path"]: r for r in rows}, []
    for x in (d.get("missing") or [])[:_MISS_ITEMS]:
        path = str(x.get("path") or "")
        if x.get("source") == "port" or x.get("kind") == "list" or "\\Input\\" not in path:
            continue
        r = at.get(path)
        if r is None and app is not None and not view.get("forms"):     # (else its sheet shows it)
            r = _row(app, path, x.get("field") or path.rsplit("\\", 1)[-1], nodes, ask)
            if r is not None:
                at[path] = r
                added.append(r)
        if r is not None:
            r.update(missing=True, certainty=x.get("certainty"))
            if x.get("rule"):
                r["rule"] = _miss_text(x["rule"], _MISS_TEXT)
                r.update({k: (_miss_text(x[k], _MISS_TEXT) if k == "rule_zh" else x[k])
                          for k in ("rule_zh", "rule_by") if x.get(k)})
    if added:
        view["rows"] = [r for r in rows if not r.get("extra")] + added + [r for r in rows if r.get("extra")]


# ---------------------------------------------------------------------------
# Flowsheet arrangement. The window decides how the flowsheet is arranged (automatic,
# as drawn in Aspen, or moved by hand) and keeps the undo history; the server keeps the
# current arrangement ("fs_layout", stored as the window sent it) and the last drawing
# read from Aspen ("aspen_layout", tools/pfsv.py). Aspen's own drawing is written only on request (layout_flowsheet:
# Redraw, or the window's arrangement applied to Aspen, aspen_place).
# ---------------------------------------------------------------------------

_FSL_MODES = ("auto", "aspen", "custom")
_FSL_BYTES = 65536               # compact JSON; the largest example model needs under 10 KB
_FSL_INNER = 32                  # inner segments of one stream (6 seen)


def _coord(v, limit: float) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and abs(v) <= limit


def _end_spec(e) -> bool:
    """A stream end: null (a feed or product's own circle) or [side, offset along it]."""
    return e is None or (isinstance(e, list) and len(e) == 2 and e[0] in ("l", "r", "u", "d")
                         and _coord(e[1], 1e4))


def _fsl_stream(s) -> dict | None:
    if not isinstance(s, dict) or "a" not in s or "b" not in s:
        return None
    n, h, c = s.get("n"), s.get("h"), s.get("c")
    if not (isinstance(n, list) and len(n) == 2 and all(isinstance(x, str) for x in n)):
        return None
    if not (_end_spec(s["a"]) and _end_spec(s["b"])):
        return None
    if isinstance(h, bool) or h not in (0, 1):
        return None
    if not (isinstance(c, list) and len(c) <= _FSL_INNER and all(_coord(x, 1e6) for x in c)):
        return None
    return {"n": n, "a": s["a"], "b": s["b"], "h": h, "c": c}


def _clean_layout(obj) -> dict | None:
    """The window's flowsheet arrangement as it is stored, or None when it is not one.
    Numbers stay as sent (the window rounds them), so the echo equals the window's own copy.
    A node or stream entry that is wrong is dropped: the window places or routes it again."""
    if not isinstance(obj, dict):
        return None
    try:
        if len(json.dumps(obj, separators=(",", ":"))) > _FSL_BYTES:
            return None
    except (TypeError, ValueError):
        return None
    mode, lid, model = obj.get("mode"), obj.get("id"), obj.get("model")
    if not isinstance(mode, str) or mode not in _FSL_MODES or not isinstance(lid, str) or len(lid) > 40:
        return None
    if model is not None and not (isinstance(model, str) and len(model) <= 16):
        return None
    out = {"v": 1, "id": lid, "mode": mode, "model": model}
    if mode == "custom":
        nodes, streams = obj.get("nodes"), obj.get("streams")
        if not isinstance(nodes, dict) or not isinstance(streams, dict):
            return None
        out["base"] = obj.get("base") if obj.get("base") in ("auto", "aspen") else "auto"
        out["nodes"] = {k: v for k, v in nodes.items() if isinstance(k, str) and len(k) <= 210
                        and isinstance(v, list) and len(v) == 2 and all(_coord(x, 1e6) for x in v)}
        out["streams"] = {k: e for k, e in ((k, _fsl_stream(s)) for k, s in streams.items()) if e is not None}
    out["at"] = time.time()
    return out


_PLACE_MAX = 2000        # blocks one arrangement into Aspen names


def _place_nodes(blocks) -> dict | None:
    """The window's block centres for Aspen's drawing ({name: [x, y]}, px): the well-formed ones."""
    if not isinstance(blocks, dict):
        return None
    out = {k: [float(v[0]), float(v[1])] for k, v in list(blocks.items())[:_PLACE_MAX]
           if isinstance(k, str) and 0 < len(k) <= 210 and isinstance(v, list) and len(v) == 2
           and all(_coord(x, 1e6) for x in v)}
    return out or None


def _stream_ends(sess: dict) -> dict:
    """{stream: [source block, destination block]} of the session's flowsheet as the window has it."""
    return {s["name"]: [s.get("from") or None, s.get("to") or None]
            for s in (sess.get("flowsheet") or {}).get("streams") or [] if isinstance(s, dict) and s.get("name")}


def aspen_arrangement(session: str) -> tuple[dict | None, str]:
    """layout_flowsheet(from_workbench=true): the session's arrangement in the window as an
    ``arrange`` for flowsheet_tools.layout_flowsheet, or (None, why not). Only an arrangement moved
    by hand is kept by the server (fs_layout custom); the automatic one and Aspen's own are drawn
    by the window, which writes them with its own "Apply arrangement to Aspen" (``ui_aspen_place``)."""
    ws = _WS
    sess = ws.state["sessions"].get(session) if ws is not None else None
    if not isinstance(sess, dict):
        return None, "Error: the workbench has no session '" + session + "' (open_workbench first)."
    lay, fs = sess.get("fs_layout"), sess.get("flowsheet") or {}
    if isinstance(lay, dict) and lay.get("mode") == "custom" and not (lay.get("model") and fs.get("model")
                                                                      and lay["model"] != fs["model"]):
        nodes = _place_nodes({k[2:]: v for k, v in (lay.get("nodes") or {}).items() if k.startswith("B:")})
        if nodes:
            return {"blocks": nodes, "ends": _stream_ends(sess)}, ""
    how = _arrangement(sess)
    if how == "aspen":
        return None, "Nothing to write: the workbench shows Aspen's own drawing, unmoved."
    return None, ("Error: the workbench shows its automatic arrangement, which the window draws; the server "
                  f"keeps only one moved by hand. Ask the user to press {_t(ws.lang, 'ui_aspen_place')} in the "
                  "flowsheet's ⋯ menu, or move a block there first.")


def _arrangement(sess: dict) -> str:
    """How the window shows the session's flowsheet, for workbench_read: the stored
    arrangement, read as the window reads it (another model's counts as automatic, and so
    does Aspen's when no drawing of this model was read)."""
    fs, lay = sess.get("flowsheet") or {}, sess.get("fs_layout")
    if not isinstance(lay, dict):
        return "auto"
    a, b = lay.get("model"), fs.get("model")          # an unknown model on either side matches
    if a and b and a != b:
        return "auto"
    if lay.get("mode") == "custom":
        return f"custom (moved from {'aspen' if lay.get('base') == 'aspen' else 'auto'})"
    imp = sess.get("aspen_layout")
    usable = (isinstance(imp, dict) and bool(imp.get("blocks"))
              and (imp.get("model") is None or fs.get("model") is None or imp.get("model") == fs.get("model")))
    return "aspen" if lay.get("mode") == "aspen" and usable else "auto"


# The arrangement belongs to the model, not to the session name or the tab: each model's
# latest fs_layout and aspen_layout are also kept in layouts/<model id>.json, and a session
# whose flowsheet shows a model it has no arrangement of gets them back from there. So a
# closed tab, a session opened under another name (after a Save As, a moved file) and a
# server restart all keep it. state.json still carries the session's copy for the window.
_LAYOUT_KEYS = ("fs_layout", "aspen_layout")
_MODEL_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _layout_file(model) -> Path | None:
    if not isinstance(model, str) or not _MODEL_ID.match(model):
        return None                                   # the id also names the file: nothing else
    return Path(_ROOT) / "layouts" / f"{model}.json"


def _kept_layouts(model) -> dict:
    """{"fs_layout", "aspen_layout"} kept for a model (either may be missing); {} if none."""
    f = _layout_file(model)
    if f is None:
        return {}
    try:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if k in _LAYOUT_KEYS and isinstance(v, dict)
            and v.get("model") == model} if isinstance(data, dict) else {}


def _keep_layout(key: str, lay) -> None:
    """Keep one arrangement in the file of the model it names. Never raises: the session's
    copy in state.json still holds it."""
    model = lay.get("model") if isinstance(lay, dict) else None
    f = _layout_file(model)
    if f is None:
        return
    data = _kept_layouts(model)
    if data.get(key) == lay:
        return
    data[key] = lay
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(f"{f.stem}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        for _ in range(20):                           # the other server may be reading it
            try:
                os.replace(tmp, f)
                return
            except PermissionError:
                time.sleep(0.05)
        tmp.unlink(missing_ok=True)
        logger.warning("workbench: could not replace %s", f)
    except (OSError, TypeError, ValueError):
        logger.warning("workbench: could not keep the arrangement of %s", model, exc_info=True)


def _restore_layouts(sess: dict) -> None:
    """After a snapshot: the kept arrangements of the model the session now shows, where the
    session has none, or another model's."""
    model = (sess.get("flowsheet") or {}).get("model")
    if not model:
        return
    kept = None
    for key in _LAYOUT_KEYS:
        cur = sess.get(key)
        if isinstance(cur, dict) and cur.get("model") in (None, model):
            continue                                  # this model's (or any model's) already
        if kept is None:
            kept = _kept_layouts(model)
        if key in kept:
            sess[key] = kept[key]


# ---------------------------------------------------------------------------
# The AI's notes pinned on blocks and streams (workbench_edit highlight[].note)
# ---------------------------------------------------------------------------
_PINS_MAX = 60           # pins kept per model: the oldest go first
_PIN_TEXT = 300          # characters of one
_PIN_KINDS = ("block", "stream")


def _pins_file(model) -> Path | None:
    if not isinstance(model, str) or not _MODEL_ID.match(model):
        return None                                   # the id also names the file: nothing else
    return Path(_ROOT) / "pins" / f"{model}.json"


def _pins_of(model) -> dict:
    """{"v": 1, "model", "pins": [{"id", "kind", "name", "text", "t", "tab", "group"?}]}, oldest
    first, kept for a model (no file, or a bad one: none)."""
    out = {"v": 1, "model": model, "pins": []}
    f = _pins_file(model)
    if f is None:
        return out
    try:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return out
    if isinstance(data, dict) and data.get("model") == model and isinstance(data.get("pins"), list):
        out["pins"] = [p for p in data["pins"] if isinstance(p, dict) and p.get("id") and p.get("kind") in _PIN_KINDS
                       and p.get("name") and p.get("text")][-_PINS_MAX:]
    return out


def _pins_keep(data: dict) -> None:
    """Write a model's pins (a tmp file, then replace, as _keep_layout). Never raises: the
    session's copy in state.json still holds them."""
    f = _pins_file(data.get("model"))
    if f is None:
        return
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(f"{f.stem}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        for _ in range(20):                           # the window may be reading it
            try:
                os.replace(tmp, f)
                return
            except PermissionError:
                time.sleep(0.05)
        tmp.unlink(missing_ok=True)
        logger.warning("workbench: could not replace %s", f)
    except (OSError, TypeError, ValueError):
        logger.warning("workbench: could not keep the pins of %s", data.get("model"), exc_info=True)


def _pin_text(note) -> str:
    """A note as a pin holds it: one line, at most _PIN_TEXT characters ("" none)."""
    return " ".join(str(note or "").split())[:_PIN_TEXT] if note is not None else ""


def _highlight(items) -> list:
    """workbench_edit's highlight as the tab keeps it: a ``note`` in one line, cut (none: dropped)."""
    out = []
    for x in items if isinstance(items, list) else []:
        if isinstance(x, dict) and "note" in x:
            text = _pin_text(x.get("note"))
            x = {**{k: v for k, v in x.items() if k != "note"}, **({"note": text} if text else {})}
        out.append(x)
    return out


def _pin_notes(ws: "Workspace", manager, tab: dict, items: list) -> int:
    """The highlight items with a note, pinned on the model the tab's session holds -- a note
    already on that object stays as it was; the object named as the flowsheet names it. Returns
    how many were added."""
    sess = ws.session(tab["session"])
    fs = sess.get("flowsheet") or {}
    names = {k: {str(o.get("name") or "").upper(): o["name"] for o in fs.get(k + "s") or [] if o.get("name")}
             for k in _PIN_KINDS}
    new = []
    for x in items:
        if isinstance(x, dict) and x.get("kind") in _PIN_KINDS and x.get("note") and str(x.get("name") or "").strip():
            name = str(x["name"]).strip()[:64]
            new.append((x["kind"], names[x["kind"]].get(name.upper(), name), x["note"]))
    if not new:
        return 0
    model = _model_of(manager, tab["session"]) if manager.get_app(tab["session"]) is not None else \
        (sess.get("model") or {}).get("id")
    if not model:
        return 0
    data, g, now, n = _pins_of(model), journal.GROUPS.current(), round(time.time(), 3), 0
    have = {(p["kind"], p["name"], p["text"]) for p in data["pins"]}
    for kind, name, text in new:
        if (kind, name, text) in have:
            continue
        have.add((kind, name, text))
        data["pins"].append({"id": "p" + uuid.uuid4().hex[:6], "kind": kind, "name": name, "text": text, "t": now,
                             "tab": tab["id"], **({"group": g["id"]} if isinstance(g, dict) and g.get("id") else {})})
        n += 1
    if n:
        data["pins"] = data["pins"][-_PINS_MAX:]
        _pins_keep(data)
    sess["pins"] = data
    return n


def _pins_sync(sess: dict, model) -> bool:
    """The session's ``pins``: the kept pins of the model it now holds (another model's, or
    none, replaced). Returns whether it changed."""
    cur = sess.get("pins")
    if (cur is None) if not model else (isinstance(cur, dict) and cur.get("model") == model):
        return False
    sess["pins"] = _pins_of(model) if model else None
    return True


def _why(exc: Exception) -> str:
    """An exception as a line the user can read: a COM error's own description if it has one."""
    info = getattr(exc, "excepinfo", None)
    if isinstance(info, tuple) and len(info) > 2 and info[2]:
        return str(info[2]).strip()
    return str(exc) or type(exc).__name__


# ---------------------------------------------------------------------------
# Workspace (state.json + events.jsonl)
# ---------------------------------------------------------------------------

def _version(tab: dict) -> dict:
    return {"program": tab["program"], "loose": tab.get("loose") or []}


def _unplaced(loose: list) -> list:
    """Loose stacks without their positions: moving one is not a change worth an undo step."""
    return [{k: v for k, v in b.items() if k not in ("x", "y")} if isinstance(b, dict) else b for b in loose]


def _pid_alive(pid: int) -> bool:
    import ctypes
    k32 = ctypes.windll.kernel32
    handle = k32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    code = ctypes.c_ulong()
    ok = k32.GetExitCodeProcess(handle, ctypes.byref(code))
    k32.CloseHandle(handle)
    return bool(ok) and code.value == 259               # STILL_ACTIVE


def _idle_run() -> dict:
    return {"status": "idle", "log": [], "step": None, "tables": [], "opts": []}


def _by_user(via: str = "window"):
    """A window job that may change the model (``fn(self, manager, tab, job)``): what it
    changes is recorded as the user's (``Workspace.as_user``), and the session's journal
    summary follows it. An inspector edit while a program is paused on the session goes
    into that run's change group, ``paused_at`` the step it waits before."""
    def deco(fn):
        @functools.wraps(fn)
        def job(self, manager, tab, *a, **k):
            try:
                extra = self.paused_scope(tab["session"]) if via == "inspector" else {}
                with self.as_user(manager, tab, via, **extra):
                    return fn(self, manager, tab, *a, **k)
            finally:
                self.note_journal(manager, tab["session"])
        return job
    return deco


@contextlib.contextmanager
def _in_aspen(tool: str, tab: dict, target=None):
    """A window job inside Aspen (its Run, Save, a point's run): the user's call in flight,
    so the heartbeat says Aspen is calculating, not that the server is gone (tools/activity.py)."""
    act = activity.begin("user", tool, session=tab["session"], phase="aspen", target=target, via="window",
                         tab=tab["id"])
    status = "error"
    try:
        yield
        status = "ok"
    finally:
        activity.end(act, status)


def _cp_summary(model) -> dict:
    """{"n", "bytes", "last"} of a model's restore points on disk (tools/checkpoints; no COM):
    how many, their size with the .apw / .def kept beside them, and the newest one's {"id",
    "t", "name", "reason", "state", "class", "pinned"}."""
    cps = checkpoints.list_checkpoints(model) if model else []
    size = 0
    for c in cps:
        for p in (c.get("path"), *(c.get("sidecars") or {}).values()):
            try:
                size += os.path.getsize(p)
            except (OSError, TypeError):
                pass
    last = cps[0] if cps else {}
    return {"n": len(cps), "bytes": size,
            "last": {k: last[k] for k in ("id", "t", "name", "reason", "state", "class", "pinned")
                     if last.get(k) is not None} or None}


def _when(t) -> str:
    """A restore point's time as the window says it: 14:02 today, else 09-24 14:02."""
    if not isinstance(t, (int, float)):
        return "?"
    lt = time.localtime(t)
    return time.strftime("%H:%M" if lt[:3] == time.localtime()[:3] else "%m-%d %H:%M", lt)


def _own_group(session: str, title: str | None, source: str = "checkpoint") -> dict | None:
    """A change group of its own for one action the user takes from the window (a named restore
    point, titled by its name; a restore): hand edits share a group per idle spell
    (journal.GROUPS.user), so the next one starts a new group after it (journal.GROUPS.own).
    None when it cannot be had."""
    g = journal.GROUPS.own(session=session, title=title, source=source)
    if g is None:
        logger.warning("workbench: no change group of its own for %s on %s", source, session)
    return g


def _undo_preview(pv, chk: dict) -> dict | None:
    """undo.preview (fixed size) with each shown step's live check (undo.check, in the plan's
    order): ``state`` -- ok | already | conflict | blocked | restore | pending --, ``state_code``
    and ``now``."""
    if not isinstance(pv, dict):
        return None
    live, steps = list((chk or {}).get("steps") or ()), []
    for i, s in enumerate(pv.get("steps") or ()):
        c = live[i] if i < len(live) and live[i].get("key") == s.get("key") else None
        if c is not None:
            s = dict(s, state=c.get("state"))
            if c.get("code"):
                s["state_code"] = c["code"]
            if "now" in c:
                s["now"] = c["now"]
        steps.append(s)
    return dict(pv, steps=steps)


_UNDO_STEP = ("key", "kind", "path", "attr", "name", "block", "port", "why", "status", "code", "exact", "approx",
              "now", "checkpoint")


def _undo_result(res: dict) -> dict:
    """An applied undo (undo_apply's result) for ``undo_req.result``, a fixed size: its status,
    counts, group and call, whether it was a redo, the restore point it kept first, the blocks
    whose inputs are incomplete now (``side``), what to read again, and its first _UNDO_STEPS
    steps (``steps_n``: all of them) -- a step's ``result`` only when it did not get done."""
    steps = []
    for s in (res.get("steps") or [])[:_UNDO_STEPS]:
        v = {k: s[k] for k in _UNDO_STEP if k in s}
        if s.get("status") in ("failed", "blocked") and s.get("result"):
            v["result"] = str(s["result"])[:200]
        steps.append(v)
    out = {k: res.get(k) for k in ("status", "code", "group", "call", "redo", "checkpoint", "side", "refresh", "n")}
    out.update(steps=steps, steps_n=len(res.get("steps") or ()))
    return out


def _recorded(op) -> str | None:
    """The id of the newest ``op`` record the current recording scope measured -- written now,
    so a chat line can name it (a hand edit's: the window's "Undo" there); ``op`` a tuple: the
    ids of every such record, comma-separated. None with nothing recorded (the journal off)."""
    s = recorder.current()
    if not isinstance(s, recorder.Scope):             # (none, or a loop's summary: not flushed here)
        return None
    try:
        recs = s.flush()
    except Exception:
        return None
    if isinstance(op, tuple):
        return ",".join(r["id"] for r in recs if r.get("op") in op and r.get("id")) or None
    return next((r.get("id") for r in reversed(recs) if r.get("op") == op and r.get("id")), None)


def _record_run(run: str, detail: str = "", secs: float | None = None, msgs: dict | None = None,
                warn: dict | None = None) -> None:
    """A run tools._common_eval.confirm_run made (``run``: ok | warn | error | unknown | refused --
    Aspen not asked: no time taken), for the journal; ``msgs``: probes.run_msgs of its run status;
    ``warn``: its _sim_warn after a warn."""
    s = recorder.current()
    if s is not None:
        s.add("run", status=run, result=" ".join(str(detail).split())[:journal.RESULT_MAX] if run != "ok" and detail
              else None, secs=None if secs is None or run == "refused" else round(secs, 2), **(msgs or {}),
              **(warn if run == "warn" and warn else {}))


# What a session's ``sim`` says about the last run that ran: kept through a later attempt that
# did not run (incomplete input, no session, a failed Reinitialize), so the window still shows
# what the model's results are.
_SIM_LAST = ("outcome", "errors", "warns", "msgs", "nmsgs", "finished", "first_warn", "warns_more")


def _last_run(old: dict) -> dict:
    """The fields of ``old`` (a session's ``sim``) that describe the last run that ran; {} when
    none ran yet (no ``finished``)."""
    return {k: old[k] for k in _SIM_LAST if k in old} if old.get("finished") else {}


def _load_of(manager, session: str) -> str | None:
    """Which load of the session's model its Aspen holds (manager.load_id: new at every open,
    reopen and restore, unique to this server process): a session's ``sim`` carries it as
    ``load``. None: the session is not open here."""
    get = getattr(manager, "load_id", None)
    try:
        return get(session) if callable(get) and session else None
    except Exception:
        return None


def _sim_warn(st: dict) -> dict:
    """A run's warnings for its ``sim`` / record (tools/probes.run_state after a warn):
    ``first_warn`` {"kind", "objs", "where", "line"(, "n")} and ``warns_more``, when there are."""
    return {k: st[k] for k in ("first_warn", "warns_more") if isinstance(st, dict) and st.get(k)}


def _run_mode(mode) -> str:
    """A run's mode as asked: step, group (a plain run with the feature off) or run."""
    return "step" if mode == "step" else "group" if mode == "group" and groups_on() else "run"


class _Pend(tuple):
    """A run waiting to start: (tab id, dry run) -- equal to that pair, as it always was -- and
    how the window asked for it: ``mode`` run | step, ``approve`` True | "no_cp" (the
    user chose to run a proposal without a restore point) | "edits" (just the user's edits to an
    applied one: proposals.unapplied) | None; ``resume``: the step a
    stopped approved run is continued from (proposals.resumable), or None."""

    def __new__(cls, tab_id: str, dry: bool, mode: str = "run", approve=None, resume=None):
        self = super().__new__(cls, (tab_id, dry))
        self.mode, self.approve, self.resume = mode, approve, resume
        return self


class Workspace:
    def __init__(self):
        self.dir = _ROOT
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / "state.json"
        self.events_path = self.dir / "events.jsonl"
        try:
            with open(self.state_path, encoding="utf-8") as f:
                self.state = json.load(f)
        except (FileNotFoundError, ValueError):
            self.state = {}
        s = self.state
        for key, default in (("rev", 0), ("lang", "en"), ("tabs", []), ("active", None),
                             ("sessions", {}), ("open_sessions", []), ("events_offset", 0)):
            s.setdefault(key, default)
        s["catalog"] = catalog()
        self.arch = prop_archive.Archive(self.dir / "proposals")   # proposals not loaded
        self.arch.scan()
        for tab in s["tabs"]:
            if tab["run"].get("status") in ("running", "queued"):   # a server that died mid-run
                tab["run"]["status"] = "stopped"
            tab["run"].pop("paused", None)                # (... or while it was paused)
            tab["run"].pop("wait", None)                  # (... or waiting for the user)
            if tab.get("kind") == "proposal" and isinstance(tab.get("proposal"), dict):
                proposals.interrupted(tab["proposal"], time.time())   # (its approved run, then)
        shown = {tab.get("session") for tab in s["tabs"]}
        for name, sess in s["sessions"].items():         # arrangements are kept for sessions a tab shows
            if not isinstance(sess, dict):
                continue
            if (sess.get("sim") or {}).get("status") == "running":   # (the server died mid-run)
                sess["sim"] = dict(sess["sim"], status="error", outcome="error")
            if isinstance(sess.get("missing"), dict):     # another server's scan, until this one's
                sess["missing"]["stale"] = True
            sess.pop("flows", None)                      # (the window asks again; requests live in memory)
            sess.pop("stream_comp", None)                # (so does the inspector)
            for key in _LAYOUT_KEYS:                     # (and per model: one kept before that existed)
                lay = sess.get(key)
                if isinstance(lay, dict) and key not in _kept_layouts(lay.get("model")):
                    _keep_layout(key, lay)
            if name not in shown:
                sess.update(aspen_layout=None, aspen_layout_req=None, fs_layout=None)
        self.proc: subprocess.Popen | None = None
        self.task: asyncio.Task | None = None
        self.pending: list[tuple[str, bool]] = []       # (tab id, dry run) waiting to start (a _Pend)
        self.auto_checks: set[str] = set()               # ... of them, a proposal's automatic check
        self.auto_runs: set[str] = set()                 # tab ids whose run is (or was last) such a check
        self.runs: dict[str, asyncio.Task] = {}          # tab id -> running program
        self.runners: dict[str, "_Runner"] = {}          # ... its runner, while it runs (paused_on)
        self.steps: dict[str, list] = {}                 # tab id -> the window's step presses not taken yet
        self.turns: dict[str, list] = {}                 # tab id -> its your-turn presses (Done, the answer)
        self.stops: set[str] = set()
        self.jobs: list[dict] = []                       # COM work the sync loop does next
        self.reading: dict = {}                          # tab id -> [req, inspect_steps] of its inspector
        self.auto: dict[str, dict] = {}                  # session -> auto refresh due (later)
        self.asks: list[dict] = []                       # Ask AI requests not yet announced
        self.watch_tried: dict[str, float] = {}          # session -> when the Aspen-window watch may try its baseline again
        self.deeps: dict[str, asyncio.Task] = {}         # tab id -> its deep compare (ext_deep), in turns
        # what the model still lacks (the sessions' ``missing``; miss_*)
        self.miss_due: dict[str, dict] = {}              # session -> {"first", "due"}: a cheap scan to make
        self.miss_gen: dict[str, int] = {}               # session -> its inputs changed (a deep look's key)
        self.miss_sc: dict[str, dict] = {}               # session -> the last cheap scan (inputs_check.scan)
        self.miss_deep: dict[str, dict] = {}             # session -> {path: (key, inputs_check.deep)}
        self.miss_fresh: dict[str, set] = {}             # session -> flagged blocks already refresh()ed
        self.fx_told: set[str] = set()                   # runs whose result tags the AI was told it may explain
        self.flows = flows.Flows()                       # the flow width layer's requests and reads
        self.miss_run: dict[str, dict] = {}              # session -> the latest missing event's deep looks
        self.miss_tasks: dict[str, asyncio.Task] = {}    # session -> those looks in turns (a running loop)
        # why the last run failed (the sessions' ``diag``; diag_tick)
        self.status_t: dict[str, float] = {}             # session -> when its block status was read (journal.now)
        self.diag_done: dict[str, str] = {}              # session -> the run record its diag is about
        self.diag_asked: dict[str, str] = {}             # session -> the run a results refresh was asked for
        self.pm_of: dict[str, str] = {}                  # session -> the model its ``pm`` was read on
        self.closed = False
        # the brakes (tools/brake.py), their mode, pause and cards kept in state.json
        self.proposed: dict[str, dict] = {}              # tab id -> a program card's late apply, queued
        self.late_q: list[tuple[int, bool]] = []         # (card, restore point first) approved late, to run
        self.says: list[dict] = []                       # what the AI is told on the channel (_tell)
        self.brake_dirty = False
        self.brake = brake.Brake(store=s.get("brake"), save=self._brake_changed, live=self.brake_live,
                                 cond=brake_effects.cond, client=_CLIENT["name"])
        self.told = {c["id"] for c in self.brake.cards}  # cards whose late decision the AI was told of
        stuck.configure(self.brake.stuck)                # the stuck watch's thresholds, as the user last set them
        s["brake"] = self.brake.view()

    # -- persistence ------------------------------------------------------
    def save(self) -> None:
        self.state["rev"] += 1
        self.state["saved_at"] = time.time()
        self.state["listening"] = channel is not None and listening   # the window: Ask AI arrives at once
        self.state["channel"] = channel is not None      # Ask AI is pushed (each note: delivered / undelivered)
        self.state["channel_cmd"] = channel_cmd()        # the page's tooltip on connecting it
        self.state["brake"], self.brake_dirty = self.brake.view(), False   # (live may have moved: always)
        self.state["learn"] = learn.view()               # its own file, either server may switch it
        self.state["history"] = self._history()           # the open models' finished proposals
        shown = self.tab(self.state.get("active"))        # ... and a model tab's front: its tab last shown
        root = self.root_of(shown)
        if root is not None and (shown is root or shown.get("parent") == root["id"]):
            root["front"] = shown["id"]
        text = json.dumps(self.state, ensure_ascii=False)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        for _ in range(20):                # the window may be reading the old file
            try:
                os.replace(tmp, self.state_path)
                return
            except PermissionError:
                time.sleep(0.05)
        logger.warning("workbench: could not replace %s", self.state_path)

    def beat(self) -> None:
        """The loop came round: the beacon writes the heartbeat soon; with no beacon (a
        workspace driven by hand) it is written here."""
        activity.tick()
        path = self.dir / "heartbeat"
        if activity.beating(path):
            activity.poke()
        else:
            activity.write_heartbeat(path)

    def window_alive(self) -> bool:
        """True while a window is open, including one left over from a previous server:
        it keeps watching the same folder and reconnects on its own."""
        if self.proc is not None and self.proc.poll() is None:
            return True
        try:
            pid = int((self.dir / "window.pid").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return _pid_alive(pid)

    # -- the brakes (tools/brake.py) --------------------------------------
    def _brake_changed(self) -> None:
        """The Brake changed: its view is saved on the sync loop's next pass (within _SYNC_S)."""
        self.brake_dirty = True

    def brake_live(self) -> bool:
        """The brakes act: this server's sync loop serves the open window and owner.json names
        this process. Otherwise every call passes as in auto, its records saying so."""
        t = self.task
        return (t is not None and not t.done() and not self.closed and self.window_alive()
                and (_owner() or {}).get("pid") == os.getpid())

    def _brake_event(self, ev: dict) -> None:
        """A brake_* event of the window (Brake.on_event): its records into the journal; the
        thresholds to the stuck watch; a resume starts its counts again (``mute``: that rule off for
        the paused group); an approval after its call's wait queued (``late_now``); a pause or a
        resume told to the AI (``says``; a late decision is told once it ran, _tell)."""
        out = self.brake.on_event(ev)
        if not out:
            return
        if not out.get("ok"):
            logger.info("workbench: %s not taken (%s)", ev.get("type"), out.get("error"))
            return
        what, card, recs = out.get("what"), out.get("card"), out.get("records") or []
        if what == "stuck":
            stuck.configure(out.get("stuck"))
        elif what == "resume":
            stuck.resume(mute=out.get("mute"), group=recs[0].get("group") if recs else None)
            if recs:                                      # how many changes others made while it was paused
                recs[0]["changes"] = n = len(_since_lines(_manager(), recs[0].get("since")))
                if self.brake.last and self.brake.last.get("since") == recs[0].get("since"):
                    self.brake.last["changes"] = n
        elif what == "card" and out.get("late") and out.get("decision") == "apply":
            self.late_q.append((card["id"], bool(out.get("slow_cp"))))
            self.late_now()
        if what in ("pause", "resume") and recs:
            self.says.append(dict(recs[0], t=time.time()))
        self._brake_log(recs, card)

    def late_now(self) -> None:
        """Run the late approvals the window sent (intercept.late: the call replayed as the
        user's, a workbench_run card's tab queued -- late_apply); on the event loop only, else
        they wait for the sync loop's next pass."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        todo, self.late_q = self.late_q, []
        for cid, slow in todo:
            try:
                intercept.late(self.brake, cid, allow_slow=slow)
            except Exception:
                logger.warning("workbench: late apply of card #%s failed", cid, exc_info=True)

    def _brake_log(self, recs, card=None, model=None, session=None) -> None:
        """Brake records into the journal: op brake (mode, pause, resume, stuck) in every open
        model's -- timeline milestones, never inputs -- or ``model``'s; op proposal (a late
        decline) in its card's model's."""
        recs = [r for r in recs or () if isinstance(r, dict)]
        m = _manager()
        if not recs or m is None or not journal.enabled():
            return
        try:
            every = [(s, m.model_id(s)) for s in m.session_names()]
        except Exception:
            every = []
        for rec in recs:
            where = [(card.get("session"), card.get("model"))] if rec.get("op") == "proposal" and card else \
                [(session, model)] if model else every
            actor = "workbench" if "stuck" in (rec.get("by"), rec.get("what")) else "user"
            if "group" in rec:                            # a resume's: the paused group, not this record's
                rec = {("paused_group" if k == "group" else k): v for k, v in rec.items()}
            t = journal.now()                             # one time in every model: the brief tells it once
            for s, mid in {mid: (s, mid) for s, mid in where if mid}.values():
                try:
                    journal.append(mid, [journal.entry("change", t=t, actor=actor, via="window", session=s, **rec)],
                                   path=m.session_file(s) if s else None, groups=False)
                except Exception:
                    logger.warning("workbench: brake record %s lost", rec.get("op"), exc_info=True)

    def stuck_pause(self, call, model, session, trig: dict, told: bool = True) -> str:
        """The stuck watch acted on (a trigger of the AI's records): pause the AI, by stuck, when the brakes
        are live -- its record in every open model; else only a record in its model that it was
        noted. The line for the end of the AI's answer; ``told``: that answer carries it (the
        record's ``told_in``: the brief does not tell it again). The detail names the evidence --
        ``ids`` (the records, newest last), ``model``, ``group`` -- for the window's "see these
        records", within brake's detail size: the group goes first, then the oldest ids."""
        detail = dict(trig.get("detail") or {}, n=trig.get("limit"), why=trig.get("why"))
        if isinstance(trig.get("model"), str) and trig["model"]:
            detail["model"] = trig["model"]
        detail = _with_evidence(detail, [str(i) for i in trig.get("ids") or () if i], trig.get("group"))
        rule = brake.rule_text(trig.get("rule"), detail)
        told_in = call if told else None
        if self.brake.live():
            rec = self.brake.pause(by="stuck", rule=trig.get("rule"), detail=detail, group=trig.get("group"))
            self._brake_log([dict(rec, told_in=told_in)] if rec else [])
            return brake.text("stuck_note", rule=rule)
        self._brake_log([{"op": "brake", "what": "stuck", "by": "stuck", "rule": trig.get("rule"),
                          "detail": detail, "fallback": "no_window", "told_in": told_in}], model=model, session=session)
        return brake.text("stuck_nowindow", rule=rule)

    def brake_tick(self, manager) -> None:
        """The sync loop's beat: cards past their time expire, and open ones whose session
        closed or holds another model (their calls are gone); the open ones' since_changes
        (tools/brake_effects); the pause ends once no window is left to resume it."""
        b = self.brake
        b.tick()
        if any(c["status"] in brake.PENDING for c in b.cards):
            names = set(manager.session_names())

            def gone(c):
                s = c.get("session")
                return c["status"] in brake.PENDING and bool(c.get("model")) and bool(s) and (
                    s not in names or manager.model_id(s) != c["model"])
            for c in b.expire(gone, "session"):
                intercept.PENDING.pop(c["id"], None)
            if brake_effects.refresh(b):
                self.brake_dirty = True
        if b.paused and not self.window_alive():
            self._brake_log(b.closed())

    def queue_proposal(self, cid: int, p) -> asyncio.Future | None:
        """A workbench_run card approved late (hooks.late): its tab queued as the window's Run
        queues one (start_runs), the run's records carrying ``proposed`` (AI proposed, the user
        ran it); the card applied / failed when it ends. A Future of its answer; None -- no such
        tab, or it runs or waits already -- and the call is replayed instead."""
        t, _ = _resolve(self, p.kw.get("session_name"), p.kw.get("tab"))
        if t is None or self.running(t["id"]) or t["id"] in self.proposed or any(x[0] == t["id"] for x in self.pending):
            return None
        fut = asyncio.get_running_loop().create_future()
        c = self.brake.get(cid) or {}
        self.proposed[t["id"]] = {"card": cid, "fut": fut, "proposed": {"by": "ai", "card": cid, "call": p.call,
                                                                        "group": p.group, "t": c.get("t")}}
        self.pending.append((t["id"], False))
        return fut

    def _proposal_ran(self, prop: dict, tab: dict, task: asyncio.Task) -> None:
        run = None if task.cancelled() or task.exception() is not None else task.result()
        status = (run or {}).get("status") or "error"
        err = next((e["text"] for e in reversed((run or {}).get("log") or []) if e.get("level") == "error"), None)
        text = f"Run {status} (tab '{tab.get('title')}')." + (f" {err}" if err else "")
        intercept.late_done(self.brake, prop["card"], status == "done", text)
        if not prop["fut"].done():
            prop["fut"].set_result(text)

    def _drop_proposal(self, tab_id: str, why: str) -> None:
        """A queued proposal that never started (stopped, its tab closed): its card open again."""
        prop = self.proposed.pop(tab_id, None)
        if prop is not None:
            intercept.late_done(self.brake, prop["card"], None, why=why)
            if not prop["fut"].done():
                prop["fut"].set_result(None)

    # -- tabs and sessions -------------------------------------------------
    @property
    def lang(self) -> str:
        return self.state.get("lang", "en")

    def tab(self, tab_id: str | None) -> dict | None:
        return next((t for t in self.state["tabs"] if t["id"] == tab_id), None)

    def tabs_for(self, session: str) -> list[dict]:
        return [t for t in self.state["tabs"] if t["session"] == session]

    def session(self, name: str) -> dict:
        sess = self.state["sessions"].setdefault(name, {})
        for key, default in (("flowsheet", None), ("notes", []), ("status", {}), ("units", {}),
                             ("values", {}), ("aspen_layout", None), ("aspen_layout_req", None),
                             ("fs_layout", None), ("model", None), ("sim", None), ("saved", None),
                             ("cp", None), ("restore_req", None), ("undo_req", None)):
            sess.setdefault(key, default)
        return sess

    def note_model(self, manager, session: str) -> bool:
        """The session's ``model``: {"id", "file"}, the model it holds and the file the server
        saves it to (a Save As moves it) -- and its ``pins``, that model's; its ``sim`` dropped
        when it is about another load of the model (``sim_fresh``). Returns whether it changed."""
        model = {"id": _model_of(manager, session), "file": _model_file(manager, session)}
        sess = self.session(session)
        pins = _pins_sync(sess, model["id"]) | self.sim_fresh(manager, session)
        if sess.get("model") == model:
            return pins
        sess["model"] = model
        if model["id"]:                                   # an untitled model's tab and records
            self._rekey(session)
        return True

    def sim_fresh(self, manager, session: str) -> bool:
        """A session's ``sim`` is about one load of its model (its ``load``: _load_of when it was
        written). Once the session holds another -- reopened, restored, opened again by a new
        server; a sim written before loads were stamped has none -- it says nothing of the results
        there and is dropped (None: the window shows no run until one is made). A session not open
        here keeps a sim this server made and drops one another server process made (its Aspen is
        gone with it). Returns whether it dropped one. No COM."""
        sess = self.state["sessions"].get(session)
        sim = sess.get("sim") if isinstance(sess, dict) else None
        if not isinstance(sim, dict):
            return False
        key, load = _load_of(manager, session), sim.get("load")
        if key is not None:
            stale = load != key
        else:                                             # (None: written while it was not open)
            boot = getattr(manager, "boot", None)
            stale = isinstance(boot, str) and bool(boot) and (
                "load" not in sim or (isinstance(load, str) and not load.startswith(boot + "-")))
        if stale:
            sess["sim"] = None
        return stale

    def refresh_results(self, app, session: str) -> None:
        """Block error marks and stream value labels after the model changed, and ``run_delta``:
        the stream values the last run moved (runlog.last_delta; no COM), once there is one --
        with ``x``, the mole fractions that run's record lists as moved (_run_fracs). And a
        cheap completeness scan at the sync loop's next pass that finds the session free."""
        sess = self.session(session)
        sess["status"] = block_status(app)
        self.status_t[session] = journal.now()           # (a run's card waits for its block status)
        sess["values"] = stream_values(app, sess.get("flowsheet"))
        delta = runlog.last_delta(session, (sess.get("model") or {}).get("id"))
        x = _run_fracs(delta) if delta is not None else None
        if x:
            delta["x"] = x
        if delta is not None or sess.get("run_delta") is not None:
            sess["run_delta"] = delta
        self.miss_touch(session, 0, edit=False)
        self.fx_tick(session)
        self.flows.ran(session)                          # (a component's flows read again, off the run path)

    def fx_tick(self, session: str) -> bool:
        """An applied proposal that ran no simulation (``run.fx_wait``) takes the
        session's next measured run as its own -- its effects then (_fx_set) -- when the run's inputs
        are only what was pending as it ended; an input changed before such a run, or other inputs in
        it: no effects. No COM (runlog read the watched results after the run). Returns whether a
        tab changed."""
        changed = False
        for t in self.tabs_for(session):
            run = t.get("run") if isinstance(t.get("run"), dict) else None
            w = run.get("fx_wait") if run else None
            if not isinstance(w, dict):
                continue
            try:
                f = runlog.followed(session, w.get("key"))
                fr = (f or {}).get("run")
                if fr:
                    inp, paths = fr.get("inputs") or {}, set(w.get("paths") or ())
                    seen = [x.get("path") for x in (inp.get("items") or []) + (inp.get("objs") or [])]
                    if (inp.get("n") or 0) <= len(paths) and all(p in paths for p in seen):
                        _fx_set(self, t, f)
                elif f is not None:
                    model = f.get("model")
                    s = (journal.summary(model) if model else None) or {}
                    if (s.get("last_input_t") or 0) <= (w.get("input_t") or 0) + 0.001:
                        continue                          # (still waiting for the run)
            except Exception:
                logger.warning("workbench: the result tags of %s not made", t.get("id"), exc_info=True)
            run.pop("fx_wait", None)
            run.pop("values0", None)                       # (applied: no resume needs it)
            runlog.unfollow(session, w.get("key"))
            changed = True
        return changed

    def note_journal(self, manager, session: str) -> bool:
        """The session's ``journal``: the change journal's summary of its model (journal.summary,
        a fixed size: count, last input / run times, the latest group and record), for the
        window's stale marks. No COM. Returns whether it changed. An input changed (its
        ``last_input_t`` moved: whoever changed it, in Aspen's window too): a cheap completeness
        scan soon (miss_touch)."""
        try:
            model = manager.model_id(session) if journal.enabled() else None
            s = journal.summary(model) if model else None
            old = self.state["sessions"].get(session, {}).get("journal")
            if s is None or old == s:
                return False
            if (old or {}).get("last_input_t") != s.get("last_input_t"):
                self.miss_touch(session)
            self.session(session)["journal"] = s
            self.fx_tick(session)                         # (an input before the awaited run)
            return True
        except Exception:
            logger.warning("workbench: journal summary of %s not taken", session, exc_info=True)
            return False

    def note_cp(self, manager, session: str, req: dict | None = None) -> bool:
        """The session's ``cp`` (a fixed size): ``_cp_summary`` of its model's restore
        points -- {"n", "bytes", "last"} -- and ``req``, the answer to the window's latest
        checkpoint / keep_checkpoint event (kept until the next one). The whole list is the
        window's to read from the checkpoint index itself. No COM. Returns whether it changed."""
        try:
            sess = self.session(session)
            model = manager.model_id(session) if manager.get_app(session) is not None else \
                (sess.get("model") or {}).get("id")
            old = sess.get("cp") or {}
            cp = dict(_cp_summary(model), req=req if req is not None else old.get("req"))
            if cp == old:
                return False
            sess["cp"] = cp
            return True
        except Exception:
            logger.warning("workbench: restore points of %s not listed", session, exc_info=True)
            return False

    # -- what was changed in Aspen's own window (tools/external.py) -----------------
    def external(self, manager, session: str, why: str) -> bool:
        """Before a window job that runs, saves, writes or shows the model, or a program run:
        compare what Aspen's own window may have changed (external.check: gated, nothing while
        a writer holds the session), so the job's own records -- a run's inputs, the unsaved
        count -- come after those edits. Only reported, never waited on.
        Returns whether the session's journal summary changed."""
        try:
            return bool(external.check(manager, session, why=why)) and self.note_journal(manager, session)
        except Exception:
            logger.warning("workbench: Aspen-window check of %s failed", session, exc_info=True)
            return False

    def watch(self, manager) -> bool:
        """The sync loop's Aspen-window watch tick for the sessions a tab shows: one the watch has not read yet
        is read as the baseline once the window has its flowsheet (external.WATCH.base, whose
        paths then need no topology read; not while Aspen works on it, retried at most every
        _WATCH_RETRY_S), a read one compared once Aspen has left the front
        (external.idle_check) -- a change made there shows in the timeline ~2 s after the user
        comes back, with no AI call. ~4 us a session while the gate is shut. Returns whether a
        session's journal summary changed."""
        if not external.enabled():
            return False
        live, changed, now = getattr(manager, "_sessions", None) or {}, False, time.monotonic()
        for s in {t["session"] for t in self.state["tabs"]}:
            if s not in live:                             # (no COM: the manager's own table)
                continue
            st = external.WATCH._s.get(s)
            if st is None or not st.based:
                if now >= self.watch_tried.get(s, 0.0) and (self.state["sessions"].get(s) or {}).get("flowsheet") \
                        and not _computing(s):
                    self.watch_tried[s] = now + _WATCH_RETRY_S
                    external.WATCH.base(manager, s)
            elif external.idle_check(manager, [s]):
                changed |= self.note_journal(manager, s)
        return changed

    def _ext_deep(self, manager, tab: dict, job: dict) -> bool:
        """The window's "check for edits made in Aspen" on the block or stream ``job["target"]``
        (external.Deep; only on a press, never when an inspector opens): refused while a writer
        has the session (a chat line, as the other jobs), dropped while one runs on the session;
        else a task reading in turns of external.DEEP_TURN_MS with this loop running between
        them (V15: ~1300 input nodes of a RadFrac in ~2 s), or at once with no loop running (a
        direct call). The tab's ``ext_deep``: {"obj", "status": "running"}, then the result
        (external.Deep) with ``text`` in the window's language."""
        session, obj = tab["session"], job.get("target") or {}
        if any((self.tab(k) or {}).get("session") == session and not task.done() for k, task in self.deeps.items()):
            return False
        why = self.writer(session, t=job.get("t"))
        if why is not None:
            tab["ext_deep"] = {"obj": obj, "status": "busy", "t": time.time(), "text": why}
            self.message(tab, why, "system")
            return True
        d = external.Deep(manager, session, obj)
        tab["ext_deep"] = {"obj": d.obj, "status": "running", "t": time.time()}
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is None:
            while not d.step():
                pass
            self._deep_done(manager, tab, d)
        else:
            self.deeps[tab["id"]] = loop.create_task(self._deep(manager, tab, d))
        return True

    async def _deep(self, manager, tab: dict, d) -> None:
        try:
            while not d.step():
                await asyncio.sleep(0)               # the loop runs: tool calls, the sync loop, other tabs
        finally:
            d.stop()                                 # (cancelled part-way: nothing noted)
            if self.deeps.get(tab["id"]) is asyncio.current_task():
                del self.deeps[tab["id"]]
            self._deep_done(manager, tab, d)
            self.save()

    def _deep_done(self, manager, tab: dict, d) -> None:
        r = d.result
        tab["ext_deep"] = dict(r, text=self._deep_text(tab["session"], r))
        if r.get("found"):
            self.note_journal(manager, tab["session"])

    def _deep_text(self, session: str, r: dict) -> str:
        lang, st = self.lang, r.get("status")
        name = (r.get("obj") or {}).get("name") or "?"
        if st == "done" and r.get("noted") is False and not r.get("found"):
            return _t(lang, "deep_fail", name=name, why="~/.aspen-mcp/journal (not writable)")
        if st == "done":
            if r.get("baseline") == "new":
                text = _t(lang, "deep_new", n=r["n"], name=name)
                text += _t(lang, "deep_afresh", name=name) if r.get("reason") in ("reopened", "replaced") else ""
            else:
                text = _t(lang, "deep_found" if r.get("found") else "deep_none", k=r.get("found"), n=r["n"], name=name)
            return text + (_t(lang, "deep_partial", n=r["n"]) if r.get("partial") else "")
        keys = {"bad": "deep_pick", "missing": "deep_missing", "changed": "deep_changed", "off": "deep_off",
                "gone": "no_session", "busy": "edit_busy"}
        if st in keys:
            return _t(lang, keys[st], name=name, session=session)
        return _t(lang, "deep_fail", name=name, why=r.get("error") or st)

    # -- what the model still lacks before Aspen can run ----------------------
    def miss_touch(self, session: str, delay: float | None = None, edit: bool = True) -> None:
        """A cheap scan of ``session`` is due ``delay`` s from now (by default _MISS_DEBOUNCE_S:
        an edit, so a burst of them is one scan), never later than _MISS_WAIT_MAX_S after the
        first touch still waiting. ``edit``: inputs may have changed, so no deep look taken
        before is current any more (``miss_gen``, part of its key), and the session's
        ``missing`` says ``stale`` until the scan. No COM."""
        now = time.time()
        d = self.miss_due.get(session)
        first = d["first"] if d else now
        self.miss_due[session] = {"first": first, "due": min(first + _MISS_WAIT_MAX_S,
                                                              now + (_MISS_DEBOUNCE_S if delay is None else delay))}
        if edit:
            self.miss_gen[session] = self.miss_gen.get(session, 0) + 1
            m = (self.state["sessions"].get(session) or {}).get("missing")
            if isinstance(m, dict) and m.get("state") in ("complete", "incomplete"):
                m["stale"] = True

    def _miss_key(self, session: str) -> tuple:
        """A deep look is current while this stays: the model, its last input change as the
        journal has it, and the edits this server saw (miss_touch)."""
        sess = self.state["sessions"].get(session) or {}
        return ((sess.get("model") or {}).get("id"), (sess.get("journal") or {}).get("last_input_t"),
                self.miss_gen.get(session, 0))

    def _miss_blocked(self, session: str) -> bool:
        """Nothing is read for the completeness scan now: a program runs on the session (or waits, paused), another
        writer holds it (the AI's optimize), or Aspen works for a call on it (_computing)."""
        return self.busy(session) is not None or _computing(session)

    def miss_tick(self, manager) -> bool:
        """The sync loop's completeness-scan pass: every due cheap scan of a session a tab shows, unless the
        session is blocked (_miss_blocked: the scan waits and ``missing`` says ``stale``).
        ASPEN_MCP_MISSING_SCAN=0: none (``missing`` says ``off``, or ``stale`` after a check the
        panel asked for). Returns whether a session's ``missing`` changed."""
        if not self.miss_due:
            return False
        now, auto, changed = time.time(), _miss_auto(), False
        for session, d in list(self.miss_due.items()):
            if d["due"] > now:
                continue
            if not self.tabs_for(session) or manager.get_app(session) is None:
                del self.miss_due[session]
                continue
            if not auto:
                del self.miss_due[session]
                changed |= self._miss_show(session, stale=session in self.miss_sc)
            elif self._miss_blocked(session):
                m = self.session(session).get("missing")
                if isinstance(m, dict) and not m.get("stale"):
                    m["stale"] = changed = True
            else:
                changed |= self.miss_scan(manager, session)
        return changed

    def miss_scan(self, manager, session: str, full: bool = False) -> bool:
        """The cheap scan (inputs_check.scan: COMPSTATUS only) into the session's ``missing``:
        a container whose own bit is clear is not opened (``trust``; ~8 ms live on a mid-size model), no child
        is read past _MISS_SCAN_MS (``cut``: the state stays exact, the list may be short), and
        the blocks whose required port is open are found (~2 ms a block) only in a model of at
        most _MISS_PORT_BLOCKS blocks -- else ``missing`` lists \\Data\\Flowsheet until the
        event missing finds them. ``full`` (that event): every container opened, every port read.
        Flagged blocks it has not yet read the GUI's way are (_miss_refresh), and scanned again.
        Deep looks of objects no longer flagged are dropped, and an inspector on one loses its
        marks (no COM). Returns whether ``missing`` changed."""
        self.miss_due.pop(session, None)
        app = manager.get_app(session)
        if app is None:
            return False
        ports = full
        if not full:
            fs = (self.state["sessions"].get(session) or {}).get("flowsheet") or {}
            ports = bool(fs) and len(fs.get("blocks") or ()) <= _MISS_PORT_BLOCKS
        try:
            sc = IC.scan(app, ports=bool(ports), trust=not full, budget_ms=None if full else _MISS_SCAN_MS)
            if self._miss_refresh(app, session, sc):
                sc = IC.scan(app, ports=bool(ports), trust=not full, budget_ms=None if full else _MISS_SCAN_MS)
        except Exception:
            logger.warning("workbench: the completeness scan of %s failed", session, exc_info=True)
            return False
        sc["ports_read"] = (bool(ports) and not sc.get("cut")) or not sc.get("flowsheet")
        if sc.get("cut") and not (self.miss_sc.get(session) or {}).get("cut"):
            self.miss_touch(session, 1.0, edit=False)     # (a model's first reads are slow: once more, warm)
        self.miss_sc[session] = sc
        flagged = {o["path"] for o in sc["objects"]}
        cache = self.miss_deep.get(session) or {}
        for p in [p for p in cache if p not in flagged]:
            del cache[p]
        for t in self.tabs_for(session):
            v = t.get("inspect")
            if isinstance(v, dict) and isinstance(v.get("missing"), dict) and v["missing"].get("path") not in flagged:
                v.pop("missing")
                for r in v.get("rows") or ():
                    for k in ("missing", "certainty", "rule", "rule_zh", "rule_by"):
                        r.pop(k, None)
        return self._miss_show(session)

    def _miss_refresh(self, app, session: str, sc: dict) -> bool:
        """inputs_check.refresh for the flagged blocks this session has not refreshed yet, as
        run_simulation and check_inputs do: a block placed and connected but never written keeps
        its bit until read the GUI's way (a fresh MIXER clears on the first read). Each at most
        _MISS_REFRESH_READS values, _MISS_REFRESH_MS for all; a block not reached in time is read
        on a later scan, one no longer flagged is forgotten (a later flag is read again). True:
        a block cleared, scan again."""
        done = self.miss_fresh.setdefault(session, set())
        done &= {o["path"] for o in sc["objects"]}
        todo = [o for o in sc["objects"] if o["path"].startswith(IC._BLOCKS + "\\") and not o.get("ports_only")
                and o["path"] not in done]
        deadline, cleared = time.perf_counter() + _MISS_REFRESH_MS / 1000, False
        for o in todo:
            left = (deadline - time.perf_counter()) * 1000
            if left <= 0:
                break
            cleared |= IC.refresh(app, {"objects": [o]}, budget_ms=left, reads=_MISS_REFRESH_READS)
            done.add(o["path"])
        return cleared

    def _miss_show(self, session: str, stale: bool = False) -> bool:
        """The session's ``missing`` (see the completeness-scan section) from the last scan, the current deep
        looks and the latest missing event's progress; within _MISS_MAX bytes. No COM."""
        sc, auto = self.miss_sc.get(session), _miss_auto()
        if sc is None:
            m = {"v": 1, "state": "unknown" if auto else "off", "auto": auto, "n": 0, "objects": []}
        else:
            key, cache = self._miss_key(session), self.miss_deep.get(session) or {}
            objs = _miss_objects(sc)
            for o in objs:
                c = cache.get(o["path"])
                if c is not None and c[0] == key:
                    o.update(_miss_fold(c[1], o.get("type"), _MISS_FIRST))
            run = self.miss_run.get(session) or {}
            m = {"v": 1, "t": round(sc["t"], 3), "state": "complete" if sc["complete"] else "incomplete",
                 "auto": auto, "runnable": bool(sc["runnable"]), "flowsheet": bool(sc.get("flowsheet")),
                 "n": len(objs), "objects": objs[:_MISS_OBJECTS], "more": max(0, len(objs) - _MISS_OBJECTS),
                 "scan_ms": sc.get("scan_ms"), "partial": bool(run.get("pending")) and run.get("status") != "running",
                 "pending": list(run.get("pending") or ())[:_MISS_DEEP_MAX],
                 "deep": {k: run[k] for k in ("status", "n", "done", "t") if k in run} or None}
            if sc.get("cut"):
                m["cut"] = True                            # the list may be short: the panel's check lists all
            if stale or session in self.miss_due:
                m["stale"] = True
        m = _miss_fit(m)
        sess = self.session(session)
        if sess.get("missing") == m:
            return False
        sess["missing"] = m
        return True

    def _miss_one(self, manager, session: str, path: str, key: tuple) -> dict:
        """One object's deep look (inputs_check.deep: at most LIGHT_CAP empty fields and
        _MISS_DEEP_MS), kept under ``key``; Aspen's internal fault in its walk flags the session."""
        d = IC.deep(manager.get_app(session), path, cap=IC.LIGHT_CAP, budget_ms=_MISS_DEEP_MS,
                    fault=main_tools.fault_note(manager, session, "workbench"))
        self.miss_deep.setdefault(session, {})[path] = (key, d)
        return d

    def miss_deep_of(self, manager, session: str, path: str, ask: bool) -> dict | None:
        """The current deep look of one flagged object (an inspector's): kept, else made now
        when ``ask`` and nothing blocks the session; else None."""
        key = self._miss_key(session)
        c = (self.miss_deep.get(session) or {}).get(path)
        if c is not None and c[0] == key:
            return c[1]
        if not ask or self._miss_blocked(session) or manager.get_app(session) is None:
            return None
        d = self._miss_one(manager, session, path, key)
        self._miss_show(session)
        return d

    def _missing(self, manager, tab: dict, job: dict) -> bool:
        """The window's missing event (the "Missing inputs" panel): a fresh full scan -- every
        container opened, open required ports found --, then a deep look at ``paths`` (those still flagged), or
        without them at the flagged objects no current look covers; at most _MISS_DEEP_MAX, one
        at a time -- with a running loop in turns (a task: tool calls and the sync loop go
        between objects) -- and before each it stops when a program or another writer takes the
        session, Aspen works for a call, or an edit came: the session's ``missing`` then says
        ``partial`` and ``pending`` (the next event goes on from there). While the session is
        blocked the job waits (``deep.status`` waiting); a session that is not open: state unknown."""
        session = tab["session"]
        if manager.get_app(session) is None:
            self.miss_sc.pop(session, None)
            self.miss_run.pop(session, None)
            return self._miss_show(session)
        task = self.miss_tasks.get(session)
        if (task is not None and not task.done()) or self._miss_blocked(session):
            self.jobs.append(job)
            run = self.miss_run.setdefault(session, {})
            if run.get("status") in ("waiting", "running"):
                return False
            run.update(status="waiting", t=round(time.time(), 3))
            return self._miss_show(session)
        self.miss_scan(manager, session, full=True)
        sc = self.miss_sc.get(session)
        if sc is None:
            return True
        key, cache = self._miss_key(session), self.miss_deep.get(session) or {}
        flagged = [o["path"] for o in sc["objects"]]
        current = lambda p: (cache.get(p) or (None,))[0] == key       # noqa: E731
        want = job.get("paths")
        todo = [p for p in dict.fromkeys(want) if p in flagged and not current(p)] if want else \
            [p for p in flagged if not current(p)]
        todo = todo[:_MISS_DEEP_MAX]
        self.miss_run[session] = {"status": "running" if todo else "done", "n": len(todo), "done": 0,
                                  "t": round(time.time(), 3), "pending": list(todo)}
        steps = self._miss_steps(manager, session, todo, key)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is None or not todo:
            for _ in steps:
                self.beat()
        else:
            self.miss_tasks[session] = loop.create_task(self._miss_turns(session, steps))
        self._miss_show(session)
        return True

    def _miss_steps(self, manager, session: str, todo: list, key: tuple):
        """The deep looks of a missing event, one object per step (a generator: the caller
        goes on between them); each first checks that the session is still open and free and
        nothing was edited since the event (``key``)."""
        run = self.miss_run[session]
        try:
            for i, path in enumerate(todo):
                if i:
                    yield
                if manager.get_app(session) is None or self._miss_blocked(session) or self._miss_key(session) != key:
                    break
                self._miss_one(manager, session, path, key)
                run.update(done=i + 1, pending=todo[i + 1:])
                self._miss_show(session)
        finally:
            run.update(status="partial" if run["pending"] else "done", t=round(time.time(), 3))
            self._miss_show(session)

    async def _miss_turns(self, session: str, steps) -> None:
        try:
            for _ in steps:
                self.save()                          # the window shows how far it got
                await asyncio.sleep(0)               # the loop runs: tool calls, the sync loop, other tabs
        finally:
            steps.close()
            if self.miss_tasks.get(session) is asyncio.current_task():
                del self.miss_tasks[session]
            self.save()

    # -- auto refresh: what a call changed, re-read soon after, once per burst -----
    # -- why the last run failed (the sessions' ``diag``) ------------------------
    def diag_tick(self, manager) -> bool:
        """The sync loop's diagnosis pass, for each session a tab shows: the newest run record of its
        model (_RUNS) not seen yet -- error / warn once the session's block status was read after
        it (a results refresh asked for once, when none is due: the refresh every run has), a
        refused one at once -- becomes the session's ``diag`` (_diag_build); an ok run, or a warn
        one after a failure, marks the card ``fixed`` instead. A card is built again when the
        window's language changed, and a refused run's when the completeness scan it lists the objects of
        is newer. No COM but _diag_pm. Returns whether a session's ``diag`` changed."""
        changed = False
        with _RUNS_LOCK:
            runs = dict(_RUNS)
        for session in dict.fromkeys(t["session"] for t in self.state["tabs"]):
            sess = self.state["sessions"].get(session)
            if not isinstance(sess, dict):
                continue
            model = (sess.get("model") or {}).get("id")
            d = sess.get("diag") if isinstance(sess.get("diag"), dict) else None
            if d is not None and model and d.get("model") not in (None, model):       # another model now
                sess["diag"], d, changed = None, None, True
            rec = runs.get(model) if model else None
            if rec is not None and rec.get("id") != self.diag_done.get(session):
                st = rec.get("status")
                # (a record's t is rounded to the ms, journal.entry: the status read's time the same way)
                if st in ("error", "warn") and round(self.status_t.get(session, float("-inf")), 3) < float(rec.get("t") or 0):
                    if self.diag_asked.get(session) != rec.get("id") and session not in self.auto:
                        self.later(session, "results")    # (Aspen's window ran it: no refresh was asked)
                    self.diag_asked[session] = rec.get("id")
                    continue
                self.diag_done[session] = rec.get("id")
                if st != "refused":
                    sess["run_msgs"] = list(rec.get("msgs") or [])[:probes.MSGS_MAX]
                old = d if d is not None and d.get("level") in _DIAG_LEVELS and not d.get("fixed") else None
                if st == "ok" or (st == "warn" and old is not None and old.get("level") != "warn"):
                    if old is not None:
                        old["fixed"] = {k: rec[k] for k in ("id", "t", "status", "seq", "actor", "via") if rec.get(k)}
                        diagnose.remember(model, old)
                        changed = True
                    continue
                changed |= self._diag_build(manager, session, sess, rec, model)
                continue
            if d is None or d.get("fixed") or (d.get("run") or {}).get("id") != (rec or {}).get("id", "-"):
                continue
            if d.get("lang") != self.lang or (d.get("level") == "refused" and
                                              (sess.get("missing") or {}).get("t") != d.get("missing_t")):
                changed |= self._diag_build(manager, session, sess, rec, model)
        return changed

    def _diag_build(self, manager, session: str, sess: dict, rec: dict, model) -> bool:
        """The card of run record ``rec`` (tools/diagnose.session_card: the session's block
        status, run messages, flowsheet, missing and property method, and the journal), in the
        window's language, into the session's ``diag`` (_diag_fit) and diagnose.remember -- the
        brief and an Ask AI note about the run tell the AI from it."""
        t0 = time.perf_counter()
        try:
            self._diag_pm(manager, session, model)
            c = diagnose.session_card(sess, rec, self.lang, model)
        except Exception:
            logger.warning("workbench: the diagnosis of %s's run not built", session, exc_info=True)
            return False
        c.update(model=model, session=session, lang=self.lang, t=round(time.time(), 3),
                 pop=(rec.get("actor") == "user" and rec.get("via") in ("window", "inspector"))
                 or (rec.get("actor") == "program" and rec.get("via") == "window"))
        if c["level"] == "refused":
            c["missing_t"] = (sess.get("missing") or {}).get("t")
        if not c.get("run") and rec.get("id"):          # (the journal off: the run as the window saw it)
            c["run"] = {k: rec[k] for k in ("id", "t", "status", "actor", "via") if rec.get(k)}
        c["ms"] = round((time.perf_counter() - t0) * 1e3, 1)
        if c["level"] not in _DIAG_LEVELS:              # (nothing failed after all: no card)
            return False
        sess["diag"] = _diag_fit(c)
        diagnose.remember(model, sess["diag"])
        return True

    def _diag_pm(self, manager, session: str, model) -> None:
        """The session's ``pm`` (the error history scores the property method): read once per
        session and model -- \\Data\\Properties\\Specifications GBASEOPSET, else GOPSETNAME --
        and again after a record touched \\Data\\Properties (_PM_DIRTY); never while a program
        or the AI's optimize holds the session or Aspen works on it (the old value stays)."""
        sess = self.session(session)
        with _RUNS_LOCK:
            dirty = model in _PM_DIRTY
        if not dirty and self.pm_of.get(session) == model and "pm" in sess:
            return
        app = manager.get_app(session) if manager is not None else None
        if app is None or self._miss_blocked(session):
            return
        pm = None
        for p in (r"\Data\Properties\Specifications\Input\GBASEOPSET", r"\Data\Properties\Specifications\Input\GOPSETNAME"):
            try:
                node = _node(app, p)
                v = node.Value if node is not None else None
            except Exception:
                v = None
            if isinstance(v, str) and v.strip():
                pm = v.strip()
                break
        sess["pm"], self.pm_of[session] = pm, model
        with _RUNS_LOCK:
            _PM_DIRTY.discard(model)

    def later(self, session: str, what: str) -> None:
        """Re-read ``what`` of ``session`` -- topology (the flowsheet, then results), results,
        values (open inspectors, units) -- _AUTO_S after the last call asking, at most
        _AUTO_MAX_S after the first: a burst of calls is one refresh (a batch is one call). A
        call that may have changed inputs has a cheap completeness scan follow (debounced)."""
        now = time.time()
        job = self.auto.setdefault(session, {"what": set(), "first": now})
        job["what"].add(what)
        job["due"] = min(job["first"] + _AUTO_MAX_S, now + _AUTO_S)
        if what != "results":
            self.miss_touch(session)

    def _auto_waits(self, session: str) -> bool:
        """An auto refresh of ``session`` waits now: Aspen works on it for another caller
        (_computing) -- but a program paused before a step, or waiting for the user, is
        read: nothing computes then, unless a call in flight is inside Aspen."""
        if self.paused_on(session) is not None:
            return _call_in_aspen(session)
        return _computing(session)

    def refresh_paused(self, manager, session: str) -> bool:
        """A program on ``session`` pauses (a group's, a step's, a breakpoint's): the topology
        its flowsheet statements asked for (later) is read now, before the pause is shown, so the
        window draws what the steps so far placed, connected or removed -- and a group's card
        frames them -- while it waits. Only when a structure change is pending (one refresh for
        the whole burst); never while a call is inside Aspen (the sync loop's pass does it then)."""
        job = self.auto.get(session)
        if not job or "topology" not in job["what"] or _call_in_aspen(session):
            return False
        del self.auto[session]
        try:
            return self._refresh(manager, session, job["what"])
        except Exception:
            logger.warning("workbench: the refresh of %s at a pause failed", session, exc_info=True)
            return False

    def nap(self) -> float:
        """The sync loop's sleep: _SYNC_S, shorter when an auto refresh falls due sooner, and
        _SHEET_GAP_S while a sheet's fields or an inspector's rows are being read (_inspect_sheet's and
        _inspect's passes, not their waiting)."""
        now = time.time()
        sheet = [_SHEET_GAP_S] if any((j["kind"] == "inspect_sheet" and "paths" in j)
                                      or (j["kind"] == "inspect" and j["tab"] in self.reading) for j in self.jobs) else []
        return max(0.01, min([_SYNC_S, *sheet] + [j["due"] - now for j in self.auto.values() if j["due"] > now]))

    def _refresh(self, manager, session: str, what: set) -> bool:
        changed = self.note_journal(manager, session)
        if "topology" in what:                           # (an open or close: the session list too)
            changed |= self.check_sessions(manager)
        app = manager.get_app(session)
        if app is None:
            return changed
        if "topology" in what:
            self._job(manager, {"kind": "refresh", "session": session})
        elif "results" in what:
            self.refresh_results(app, session)
            self.note_cp(manager, session)               # (an optimize: its restore point)
        for t in self.tabs_for(session):
            self._job(manager, {"kind": "units", "tab": t["id"]})
            self.reinspect(manager, t)
        return True

    # -- program history: every change (window, LLM, undo) is one step ----------
    # A version is the program plus the loose stacks lying beside it on the workspace (as the
    # window serialized them), so undo puts back exactly what was on screen: a block dragged
    # out of the program comes back as the loose stack it was, not as nothing or as a copy.

    def commit(self, tab: dict, program: list[dict], origin: str, flash=(), loose: list | None = None) -> bool:
        """Replace a tab's program (and, from the window, its loose stacks), remembering
        the old version for undo. Loose stacks that only moved update in place."""
        if loose is None:                                 # the LLM's edits leave loose stacks be
            loose = tab.get("loose") or []
        if program == tab["program"] and _unplaced(loose) == _unplaced(tab.get("loose") or []):
            tab["loose"] = loose
            return False
        old = tab["program"]
        tab["past"] = (tab.get("past") or [])[-(_HISTORY - 1):] + [_version(tab)]
        tab["future"] = []
        self._show(tab, program, origin, flash, loose)
        if tab.get("breaks"):                             # a deleted block's breakpoint goes with it
            ids = {st.get("id") for st in _walk(program)}
            tab["breaks"] = [b for b in tab["breaks"] if b in ids]
        if origin == "llm":                               # a lasting line in the AI chat (the toast fades)
            added, changed, removed = _program_diff(old, program)
            parts = _t(self.lang, "ai_edit_parts", a=len(added), c=len(changed), r=removed)
            self.message(tab, _t(self.lang, "ai_edit", parts=parts), "ai_edit", added=added, changed=changed,
                         removed=removed, rev=tab["program_rev"])
        return True

    def step(self, tab: dict, back: bool) -> bool:
        """Undo (back) or redo one program change."""
        src, dst = ("past", "future") if back else ("future", "past")
        stack = tab.get(src) or []
        if not stack:
            return False
        tab[dst] = (tab.get(dst) or [])[-(_HISTORY - 1):] + [_version(tab)]
        v = stack.pop()
        tab[src] = stack
        if isinstance(v, list):                           # saved before versions held loose stacks
            v = {"program": v, "loose": tab.get("loose") or []}
        self._show(tab, v["program"], "history", (), v.get("loose") or [])
        return True

    def _show(self, tab: dict, program: list[dict], origin: str, flash, loose: list | None = None) -> None:
        tab["program"] = program
        if loose is not None:
            tab["loose"] = loose
        tab["program_rev"] += 1
        tab["program_origin"] = origin
        tab["flash"] = list(flash)
        tab["history"] = {"undo": len(tab.get("past") or []), "redo": len(tab.get("future") or [])}
        self.jobs.append({"kind": "units", "tab": tab["id"]})

    def _title(self, title: str, skip: str | None = None) -> str:
        """``title``, made unique among the loaded tabs (" (2)", " (3)" ...)."""
        used = {t["title"] for t in self.state["tabs"] if t["id"] != skip}
        base, n = title, 2
        while title in used:
            title, n = f"{base} ({n})", n + 1
        return title

    def _make_tab(self, session: str, title: str | None, kind: str, parent: str | None = None,
                  mkey: str | None = None) -> dict:
        tab = {"id": _new_id("t"), "title": self._title(title or session), "session": session, "kind": kind,
               "program": [], "program_rev": 0, "program_origin": "llm", "flash": [], "run": _idle_run(),
               "messages": [], "highlight": [], "selection": None, "inspect": None, "results": None}
        if kind == "model":
            tab["mkey"], tab["front"] = mkey or self.mkey_of(session), tab["id"]
        else:
            tab["parent"] = parent
        return tab

    def _add(self, tab: dict) -> None:
        self.state["tabs"].append(tab)
        if self.session(tab["session"])["flowsheet"] is None:     # a session no tab has shown yet
            self.jobs.append({"kind": "refresh", "session": tab["session"]})
        self.jobs.append({"kind": "units", "tab": tab["id"]})

    def new_tab(self, session: str, title: str | None = None, kind: str | None = None,
                parent: str | None = None) -> dict:
        """A new tab on ``session``: a sub-tab (``kind`` program or proposal) of the model
        tab ``parent`` -- by default the session's, a program --, or the model tab itself when the
        session's model has none yet (_new_root: its History and chat come back)."""
        if kind is None:
            root = self.root_of(self.tab(parent)) if parent else self.root_for(session)
            kind, parent = ("program", root["id"]) if root is not None else ("model", None)
        if kind == "model":
            return self._new_root(session, title)
        tab = self._make_tab(session, title, kind, parent)
        self._add(tab)
        return tab

    # -- one tab per model; its extra programs and proposals as sub-tabs --------------
    # tabs[] stays flat, every tab keeps its id. A model tab {kind "model", mkey, front: the sub-tab
    # last shown} is the model's own program ("My program"); a sub-tab {kind "program" | "proposal",
    # parent: the model tab's id}. Proposals no longer loaded live in tools/prop_archive.py.
    def mkey_of(self, session) -> str:
        """The model a session holds, as tabs key it: its model id once known, else "s:<session>"."""
        sess = self.state["sessions"].get(session) if session else None
        mid = ((sess.get("model") or {}).get("id")) if isinstance(sess, dict) else None
        return mid if isinstance(mid, str) and mid else f"s:{session}"

    def root_for(self, session: str, create: bool = False, title: str | None = None) -> dict | None:
        """The model tab of the model ``session`` holds now; ``create``: made when there is none."""
        key = self.mkey_of(session)
        roots = [t for t in self.state["tabs"] if t.get("kind") == "model"]
        hit = next((t for t in roots if t.get("mkey") == key), None)
        if hit is None and key.startswith("s:"):         # (no id known yet: the session's own)
            hit = next((t for t in roots if t.get("session") == session), None)
        if hit is None and create:
            hit = self._new_root(session, title)
        return hit

    def root_of(self, tab: dict | None) -> dict | None:
        """A tab's model tab: itself, its parent, else (an older state) its session's."""
        if not isinstance(tab, dict):
            return None
        if tab.get("kind") == "model":
            return tab
        p = self.tab(tab.get("parent"))
        if p is not None and p.get("kind") == "model":
            return p
        return self.root_for(tab.get("session")) if tab.get("session") else None

    def children(self, root: dict) -> list[dict]:
        rid = root["id"]
        return [t for t in self.state["tabs"] if t.get("parent") == rid and t["id"] != rid]

    def family(self, root: dict) -> list[dict]:
        return [root] + self.children(root)

    def stale(self, tab: dict | None) -> bool:
        """A tab of a model tab whose model its session no longer holds (another file of the same
        name opened there): hollow, its runs refused, until the user closes it."""
        root = self.root_of(tab)
        if root is None:
            return False
        key, now = str(root.get("mkey") or ""), self.mkey_of(root.get("session"))
        return bool(key) and not key.startswith("s:") and not now.startswith("s:") and key != now

    def _new_root(self, session: str, title: str | None = None, mkey: str | None = None) -> dict:
        root = self._make_tab(session, title, "model", mkey=mkey)
        self._add(root)
        self._restore_into(root)
        return root

    def _restore_into(self, root: dict) -> None:
        """A model's tab (re)made: its chat as it was when it closed (slice 4: model.json), and the
        proposals it had in progress (the active lane) back as its sub-tabs; the finished ones stay in
        History (``history`` in state.json)."""
        key = root["mkey"]
        if not root.get("messages"):
            root["messages"] = self.arch.chat(key)
        for e in list(self.arch.index(key)):
            if e.get("lane") != "history" and self.tab(e["tab"]) is None:
                self.load_tab(e["tab"], root=root)

    def _unlist(self, tab: dict) -> None:
        """Take a tab out of tabs[]; the active tab and its model tab's ``front`` move to the model tab."""
        s, tid = self.state, tab["id"]
        root = self.root_of(tab) if tab.get("kind") != "model" else None
        s["tabs"] = [t for t in s["tabs"] if t["id"] != tid]
        if root is not None and root.get("front") == tid:
            root["front"] = root["id"]
        if s.get("active") == tid:
            s["active"] = root["id"] if root is not None else s["tabs"][0]["id"] if s["tabs"] else None

    def _drop_tab(self, tab: dict) -> None:
        """A tab gone from the window: out of tabs[], and nothing queued or kept for it any more."""
        tid = tab["id"]
        self._unlist(tab)
        self.pending = [p for p in self.pending if p[0] != tid]
        self.auto_checks.discard(tid)
        self._drop_proposal(tid, "tab_closed")
        self.flows.drop_tab(tid)                          # (its flow width request)
        self.steps.pop(tid, None)
        self.turns.pop(tid, None)

    def _shelve(self, tab: dict, root: dict | None, mkey: str, copy: bool = True) -> bool:
        """Keep a proposal tab in the archive and take it out of tabs[] (no runtime state: also at
        boot). ``copy``: its chat lines (not an AI edit's, whose Undo is the proposal's program) go to
        its model's tab, marked with its title (``prop``) and id (``prop_tab``: taken back when it is
        loaded again). False -- not kept (a write failed): it stays loaded."""
        keep = {k: v for k, v in tab.items() if k not in ("parent", "pinned")}
        try:
            self.arch.save(mkey, keep, proposals.history_entry(keep))
        except (OSError, TypeError, ValueError):
            logger.warning("workbench: proposal tab %s not archived", tab.get("id"), exc_info=True)
            return False
        if copy and root is not None and tab.get("messages"):
            title = (tab.get("proposal") or {}).get("title") or tab.get("title") or ""
            kept = [dict(m, prop=title, prop_tab=tab["id"]) for m in tab["messages"] if m.get("from") != "ai_edit"]
            root["messages"] = sorted((root.get("messages") or []) + kept, key=lambda m: m.get("t") or 0)[-50:]
        self._unlist(tab)
        return True

    def archive_tab(self, tab: dict, copy: bool = True) -> bool:
        """A loaded proposal tab into the archive (shelved, past the cap, its model's tab closing)."""
        root = self.root_of(tab)
        mkey = (root or {}).get("mkey") or self.mkey_of(tab.get("session"))
        if not self._shelve(tab, root, mkey, copy):
            return False
        self._drop_tab(tab)
        return True

    def load_tab(self, tid, pin: bool = False, root: dict | None = None) -> dict | None:
        """An archived proposal back as a sub-tab of its model's tab -- made (with its History) when
        that is closed --, as it was kept: titled anew if its title is in use; ``pin``: opened from
        History (the cap leaves it loaded). None when there is no such record."""
        mkey = self.arch.find(tid)
        tab = self.arch.load(mkey, tid) if mkey else None
        if tab is None:
            return None
        if root is None:
            root = next((t for t in self.state["tabs"] if t.get("kind") == "model" and t.get("mkey") == mkey), None)
            if root is None:
                holds = [n for n, x in self.state["sessions"].items()
                         if isinstance(x, dict) and (x.get("model") or {}).get("id") == mkey]
                root = self._new_root(tab.get("session") if tab.get("session") in holds or not holds else holds[0],
                                      mkey=mkey)
                if self.tab(tid) is not None:             # (in progress: back with its model's tab)
                    got = self.tab(tid)
                    if pin and proposals.lane(got.get("proposal")) == "history":
                        got["pinned"] = True
                    return got
        tab.update(kind="proposal", parent=root["id"], title=self._title(tab.get("title") or tid))
        run = tab.get("run") if isinstance(tab.get("run"), dict) else _idle_run()
        if run.get("status") in ("running", "queued"):
            run["status"] = "stopped"
        run.pop("paused", None)
        run.pop("wait", None)
        tab["run"] = run
        if pin and proposals.lane(tab.get("proposal")) == "history":
            tab["pinned"] = True
        self.state["tabs"].append(tab)
        try:
            self.arch.remove(mkey, tid)
        except OSError:                                   # (both: the loaded one wins, _history)
            logger.warning("workbench: archived %s not removed", tid, exc_info=True)
        root["messages"] = [m for m in root.get("messages") or [] if m.get("prop_tab") != tid]
        self.jobs.append({"kind": "units", "tab": tid})
        return tab

    def arch_tab(self, tid) -> tuple[str | None, dict | None]:
        """(model key, the archived tab) of a tab id kept in the archive, else (None, None)."""
        mkey = self.arch.find(tid) if tid else None
        return (mkey, self.arch.load(mkey, tid)) if mkey else (None, None)

    def close_model(self, root: dict) -> bool:
        """The model's tab closes (the user confirmed in the window): its proposals archived -- the
        finished ones' lines kept in its chat --, its programs deleted, its chat kept for next time
        (model.json), the active tab to the next model's. False: a proposal could not be kept, and
        nothing else closed."""
        for c in self.children(root):
            if c.get("kind") == "proposal" and isinstance(c.get("proposal"), dict):
                if not self.archive_tab(c, copy=proposals.lane(c["proposal"]) == "history"):
                    self.message(root, _t(self.lang, "error", exc="a proposal could not be kept"), "system")
                    return False
        fam = self.children(root)
        chat = sorted([m for t in [root] + fam for m in t.get("messages") or []], key=lambda m: m.get("t") or 0)
        try:
            self.arch.save_chat(root["mkey"], chat)
        except OSError:
            logger.warning("workbench: the chat of %s not kept", root.get("mkey"), exc_info=True)
        was = self.state.get("active")
        roots = [t for t in self.state["tabs"] if t.get("kind") == "model"]
        i = next((k for k, t in enumerate(roots) if t is root), 0)
        for c in fam:
            self._drop_tab(c)
        self._drop_tab(root)
        if was in {t["id"] for t in [root] + fam}:
            rest = [t for t in roots if t is not root]
            nxt = rest[min(i, len(rest) - 1)] if rest else None
            front = self.tab((nxt or {}).get("front"))
            self.state["active"] = None if nxt is None else front["id"] if front is not None else nxt["id"]
        return True

    def _tab_close(self, tab: dict, ev: dict) -> None:
        """The window's tab_close {tab, stop?}. A model's tab: refused while a tab of
        its runs (a chat line) -- with ``stop``, its runs stopped and the tab closes once they end
        (``closing``) --; else close_model (the window asked about its programs first). A sub-tab
        program: dropped.
        A proposal: only a finished one (shelved to History); one in progress gets a chat line."""
        if tab.get("kind") == "model":
            fam = self.family(tab)
            busy = [t for t in fam if self.running(t["id"])]
            if busy and ev.get("stop") is not True:
                self.message(tab, _t(self.lang, "close_busy", tab=busy[0]["title"]), "system")
                return
            ids = {t["id"] for t in fam}
            for p in [p for p in self.pending if p[0] in ids]:
                self.pending.remove(p)
                self.auto_checks.discard(p[0])
                t = self.tab(p[0])
                if t is not None and t["run"].get("status") == "queued":
                    t["run"]["status"] = "stopped"
                self._drop_proposal(p[0], "stopped")
            if busy:
                self.stops.update(t["id"] for t in busy)
                tab["closing"] = {"t": time.time()}
                return
            self.close_model(tab)
        elif tab.get("kind") == "proposal" and isinstance(tab.get("proposal"), dict):
            if self.running(tab["id"]):
                return
            if proposals.lane(tab["proposal"]) != "history":
                self.message(tab, _t(self.lang, "close_prop_active"), "system")
                return
            self.archive_tab(tab)
        elif not self.running(tab["id"]):
            self._drop_tab(tab)

    def _closing_tick(self) -> bool:
        """Model tabs closing once their runs end (tab_close with stop): closed now that none runs."""
        changed = False
        for root in [t for t in self.state["tabs"] if t.get("kind") == "model" and t.get("closing")]:
            ids = {t["id"] for t in self.family(root)}
            if any(self.running(i) for i in ids) or any(p[0] in ids for p in self.pending):
                continue
            root.pop("closing", None)
            self.close_model(root)
            changed = True
        return changed

    def _prop_history(self, kind: str, tid: str) -> None:
        """The window's History: prop_open {tab} -- shown (loaded from the archive, or kept loaded:
        ``pinned``), active, its model tab's front --; prop_delete {tab} -- a finished proposal's
        record deleted for good (loaded or archived; its lines in the model's chat too), a tombstone
        left, a journal milestone (op proposal, status deleted); refused for one running or in
        progress. The journal, change groups and restore points are never touched."""
        if not tid:
            return
        t = self.tab(tid)
        if kind == "prop_open":
            if t is None:
                t = self.load_tab(tid, pin=True)
            elif t.get("kind") == "proposal" and proposals.lane(t.get("proposal")) == "history":
                t["pinned"] = True
            if t is not None:
                self.state["active"] = t["id"]
                root = self.root_of(t)
                if root is not None:
                    root["front"] = t["id"]
            return
        if t is not None:
            root = self.root_of(t)
            if t.get("kind") != "proposal":
                return
            if self.running(tid) or proposals.lane(t.get("proposal")) != "history":
                self.message(root or t, _t(self.lang, "prop_del_refused"), "system")
                return
            mkey, e = (root or {}).get("mkey") or self.mkey_of(t.get("session")), proposals.history_entry(t)
            self._drop_tab(t)
        else:
            mkey, e = self.arch.find(tid), self.arch.entry(tid)
            if mkey is None or e is None:
                return
            root = next((x for x in self.state["tabs"] if x.get("kind") == "model" and x.get("mkey") == mkey), None)
            if e.get("lane") != "history":
                if root is not None:
                    self.message(root, _t(self.lang, "prop_del_refused"), "system")
                return
        try:
            self.arch.delete(mkey, tid, e.get("pid"))
        except OSError:
            logger.warning("workbench: the record of %s not deleted", tid, exc_info=True)
            return
        if root is not None:
            root["messages"] = [m for m in root.get("messages") or [] if m.get("prop_tab") != tid]
            self.message(root, _t(self.lang, "prop_deleted", title=e.get("title") or tid), "system")
        if not str(mkey).startswith("s:"):
            self._brake_log([{"op": "proposal", "status": "deleted", "proposal": e.get("pid"), "title": e.get("title"),
                              "tab": tid}], model=mkey, session=e.get("session"))

    def _cap_all(self) -> bool:
        changed = False
        for root in [t for t in self.state["tabs"] if t.get("kind") == "model"]:
            changed |= self._cap(root)
        return changed

    def _cap(self, root: dict) -> bool:
        """More than _HIST_LOADED finished proposals loaded under a model's tab: the oldest archived
        (not one pinned, shown, the tab's front or running)."""
        hist = [c for c in self.children(root) if c.get("kind") == "proposal"
                and proposals.lane(c.get("proposal")) == "history"]
        extra = len(hist) - _HIST_LOADED
        keep = {self.state.get("active"), root.get("front")}
        changed = False
        for c in sorted(hist, key=lambda c: (c.get("proposal") or {}).get("t") or 0):
            if extra <= 0:
                break
            if c.get("pinned") or c["id"] in keep or self.running(c["id"]) or any(p[0] == c["id"] for p in self.pending):
                continue
            if self.archive_tab(c):
                extra -= 1
                changed = True
        return changed

    def _history(self) -> dict:
        """state.json's ``history``: per open model tab, its proposals in History -- the archived ones
        and the finished ones still loaded (``loaded``) --, the latest first (_HIST_STATE)."""
        out = {}
        for root in self.state["tabs"]:
            key = root.get("mkey") if root.get("kind") == "model" else None
            if not key or key in out:
                continue
            rows = [dict(proposals.history_entry(c), loaded=True) for c in self.children(root)
                    if c.get("kind") == "proposal" and proposals.lane(c.get("proposal")) == "history"]
            rows += [dict(e, loaded=False) for e in self.arch.index(key) if self.tab(e["tab"]) is None]
            out[key] = sorted(rows, key=lambda e: -(e.get("t") or 0))[:_HIST_STATE]
        return out

    def _rekey(self, session: str) -> None:
        """The session's model got its id: the model tab and records kept as "s:<session>" go to it
        (merged into that model's tab when one is open)."""
        new, old = self.mkey_of(session), f"s:{session}"
        if new == old:
            return
        olds = [t for t in self.state["tabs"] if t.get("kind") == "model" and t.get("mkey") == old]
        if olds or self.arch.has(old):
            try:
                self.arch.rekey(old, new)
            except OSError:
                logger.warning("workbench: records of %s not moved to %s", old, new, exc_info=True)
        for r in olds:
            there = next((t for t in self.state["tabs"] if t.get("kind") == "model" and t.get("mkey") == new
                          and t is not r), None)
            if there is None:
                r["mkey"] = new
                self._restore_into(r)
                continue
            for c in self.children(r):
                c["parent"] = there["id"]
            r.pop("mkey", None)
            r.pop("front", None)
            r.update(kind="program", parent=there["id"])

    # -- the AI's proposals (tools/proposals.py) ------------------------------
    def prop_touched(self, tab: dict) -> None:
        """The user changed a proposal tab's program (an edit, an undo or a redo): its
        ``edited``, what differs from the AI's last version."""
        if tab.get("kind") == "proposal" and isinstance(tab.get("proposal"), dict):
            proposals.touched(tab["proposal"], tab["program"], _program_diff, time.time())

    def check_soon(self, manager, tab: dict) -> bool:
        """An open proposal is checked at once when its session is open and idle -- no program
        runs or waits on it, no other writer holds it: a dry run queued (``pending``) as the
        window's Check is, marked automatic (``auto_checks``: its run says ``auto``). Busy: not
        queued -- the user presses Check. Returns whether it was queued."""
        tid, session = tab["id"], tab["session"]
        if (tab.get("proposal") or {}).get("status") != "open" or self.running(tid) or \
                any(p[0] == tid for p in self.pending):
            return False
        if self.busy(session) is not None or any(self.tab(p[0]) and self.tab(p[0])["session"] == session
                                                 for p in self.pending):
            return False
        if activity.holder(session) is not None or manager.get_app(session) is None:
            return False
        self.pending.append(_Pend(tid, True))
        self.auto_checks.add(tid)
        return True

    def _proposal_reply(self, tab: dict, ev: dict) -> None:
        """The window's proposal_reply: ``action`` reject -- the user sends the AI's
        proposal back with ``text`` (may be empty): status rejected, ``reply``; an Ask AI note
        about it (``target.kind`` proposal; an older open one of the tab done) pushed to the AI
        (_announce says it is its proposal sent back) -- workbench_read shows it too --; a
        chat line; the journal's milestone (op proposal, status rejected: the AI's brief says
        it). Refused (a chat line) while it runs or once the AI withdrew it."""
        prop = tab.get("proposal") if tab.get("kind") == "proposal" else None
        if not isinstance(prop, dict):
            return
        lang, now = self.lang, time.time()
        if ev.get("action") == "dismiss":                  # the card's Close proposal: it does not run
            try:
                if proposals.dismiss(prop, now):
                    self.message(tab, proposals.say(lang, "dismissed"), "system", kind="proposal", what="dismissed",
                                 proposal=prop["id"])
            except ValueError:
                self.message(tab, proposals.say(lang, "dismiss_running"), "system", kind="proposal",
                             what="refused", proposal=prop["id"])
            return
        if ev.get("action") != "reject":
            return
        try:
            reply = proposals.reject(prop, str(ev.get("text") or ""), now)
        except ValueError as exc:
            self.message(tab, proposals.say(lang, f"reject_{exc}"), "system", kind="proposal", what="refused",
                         proposal=prop["id"])
            return
        notes = self.session(tab["session"])["notes"]
        for n in notes:                                   # (sent back again: the newer comment counts)
            tg = n.get("target") if isinstance(n.get("target"), dict) else {}
            if tg.get("kind") == "proposal" and tg.get("tab") == tab["id"] and n.get("status") == "open":
                n["status"] = "done"
        note = proposals.note(tab, reply["text"], lang, ev.get("t") or now)
        notes.append(note)
        self.asks.append({"session": tab["session"], "tab": tab, "note": note})
        self.message(tab, proposals.say(lang, "rejected"), "system", kind="proposal", what="rejected",
                     proposal=prop["id"])
        m = _manager()
        model = m.model_id(tab["session"]) if m is not None else None
        if model:
            self._brake_log([{"op": "proposal", "status": "rejected", "proposal": prop["id"], "title": prop["title"],
                              "tab": tab["id"], "rev": prop.get("rev"), "comment": reply["text"] or None,
                              "note_id": note["id"]}], model=model, session=tab["session"])

    def busy(self, session: str) -> dict | None:
        """The tab running a program on ``session`` right now, if any."""
        for tab_id, task in self.runs.items():
            tab = self.tab(tab_id)
            if tab and tab["session"] == session and not task.done():
                return tab
        return None

    def writer(self, session: str, key: str = "edit", t=None, paused_ok: bool = False,
               waiting_ok: bool = False) -> str | None:
        """Why the window may not change ``session`` now, in the chat's words (``key``: edit or
        save): a program runs on it, or another writer holds it (tools/activity.py: the AI's
        optimize), or held it when the window posted the event at ``t`` (its wall-clock time:
        an optimizer that never let the loop read the event before it ended). None: it is free.
        A program paused before a step lets the inspector write (``paused_ok``); anything
        else is told to continue or stop it first. One waiting for the user at a your-turn step
        lets the inspector write too, and ``waiting_ok`` (Run, Save, a restore point); the
        rest is told to press Done or Stop first."""
        other = self.busy(session)
        if other is not None:
            run = other.get("run") or {}
            if run.get("paused"):
                return None if paused_ok else _t(self.lang, "why_paused", tab=other.get("title"))
            if isinstance(run.get("wait"), dict):
                return None if paused_ok or waiting_ok else _t(self.lang, "why_waiting", tab=other.get("title"),
                                                               label=run["wait"].get("label") or "?")
            return _t(self.lang, key + "_busy", session=session)
        held = activity.holder(session)
        if held is None:
            held = activity.held_then(session, t)
            if held is not None and held.get("actor") == "program" and held.get("via") != "mcp":
                return _t(self.lang, key + "_busy", session=session)
        return None if held is None else _t(self.lang, key + "_held", session=session, who=self.who(held))

    def who(self, held: dict) -> str:
        """A holder (tools/activity.py) that is not this window's program, in words."""
        return _t(self.lang, "who_optimizer" if held.get("actor") == "optimizer" else "who_other")

    def running(self, tab_id: str) -> bool:
        task = self.runs.get(tab_id)
        return task is not None and not task.done()

    def paused_on(self, session: str) -> "_Runner | None":
        """The runner of the program paused before a step on ``session``, or waiting for
        the user at a your-turn step, if one is."""
        tab = self.busy(session)
        r = self.runners.get(tab["id"]) if tab is not None else None
        return r if r is not None and r.stopped_at() is not None else None

    def paused_scope(self, session: str) -> dict:
        """What an inspector edit's recording scope takes while a program is paused on
        ``session``: the run's change group and ``paused_at`` (the step it waits before, or the
        your-turn step waiting for the user); {} when none is (or the run records nothing: the
        journal off)."""
        r = self.paused_on(session)
        if r is None or r.book is None or not r.book.group:
            return {}
        return {"group": r.book.group, "paused_at": r.stopped_at()}

    @staticmethod
    def as_user(manager, tab: dict, via: str = "window", group=None, **extra) -> recorder.Scope:
        """The recording scope of a change the user makes from the window (``via`` window, or
        inspector for a typed value): every window job that writes the model runs inside one.
        ``group``: the change group it goes into (else the user's own); ``extra`` on its records."""
        s = recorder.scope(actor="user", via=via, session=tab["session"],
                           group=group or journal.GROUPS.user(session=tab["session"]), **extra)
        s.manager = manager                      # the model id is looked up when something is recorded
        return s

    def message(self, tab: dict, text: str, who: str = "llm", **extra) -> None:
        tab["messages"].append({"t": time.time(), "from": who, "text": text, **extra})
        tab["messages"] = tab["messages"][-50:]

    # -- window -> server --------------------------------------------------
    def drain(self) -> bool:
        """Apply the window's new events. Returns True (and saves) if state changed. Not while
        another live server owns the window (owner.json): its events are that server's."""
        if _owner_other() is not None:
            return False
        try:
            with open(self.events_path, "rb") as f:
                f.seek(self.state["events_offset"])
                data = f.read()
        except FileNotFoundError:
            return False
        if not data:
            return False
        end = data.rfind(b"\n")
        if end < 0:
            return False                     # a line still being written
        chunk = data[: end + 1]
        self.state["events_offset"] += len(chunk)
        for line in chunk.decode("utf-8", errors="replace").splitlines():
            try:
                self._apply(json.loads(line))
            except Exception:
                logger.warning("workbench: bad event %r", line[:200], exc_info=True)
        self._cap_all()
        self.save()
        return True

    def _apply(self, ev: dict) -> None:
        s, kind = self.state, ev.get("type")
        tab = self.tab(ev.get("tab"))
        if kind == "lang":
            if ev.get("lang") in _LANGS:
                s["lang"] = ev["lang"]
        elif kind == "closed":
            self.closed = True
            self.flows.clear()                            # (the layer's reads end with the window)
            self._brake_log(self.brake.closed())          # held calls not applied, the pause ended
        elif isinstance(kind, str) and kind.startswith("brake_"):
            self._brake_event(ev)
        elif kind == "tab_new":
            # {session, parent?, title?}. Neither parent nor title: the model's tab, focused (made with
            # its History and chat when closed); else a program sub-tab of it (the window then sends
            # the new tab's program, if any, as a program event).
            par = self.root_of(self.tab(ev.get("parent"))) if ev.get("parent") else None
            session = par["session"] if par is not None else str(ev.get("session") or "")
            title = str(ev["title"])[:60] if ev.get("title") else None
            if session and par is None and title is None:
                root = self.root_for(session, create=True)
                front = self.tab(root.get("front"))
                s["active"] = front["id"] if front is not None and self.root_of(front) is root else root["id"]
            elif session:
                par = par or self.root_for(session)
                new = self.new_tab(session, title, kind="program" if par else "model",
                                   parent=par["id"] if par else None)
                s["active"] = new["id"]
                if par is not None:
                    par["front"] = new["id"]
        elif kind in ("note_edit", "note_delete"):
            for name, sess in s["sessions"].items():
                notes = sess.get("notes", [])
                if kind == "note_delete":
                    sess["notes"] = [n for n in notes if n["id"] != ev.get("id")]
                else:
                    for n in notes:
                        if n["id"] == ev.get("id"):
                            n["text"] = str(ev.get("text", n["text"]))
                            n["status"] = "open"
                            for k in ("delivered", "undelivered", "pushed", "handed", "read"):
                                n.pop(k, None)                # (pushed again: its own flags)
                            self.asks.append({"session": name, "note": n})
        elif kind == "learn_mode":                          # the user switches learning mode (both servers)
            s["learn"] = learn.switch(bool(ev.get("on")), by="user")
        elif kind == "pin_hide":                            # the user removes one of the AI's notes
            self._pin_hide(tab, ev)
        elif kind == "labels_learn":                        # fields the timeline could only name by code
            session = str(ev.get("session") or (tab or {}).get("session") or "")
            paths = [p for p in ev.get("paths") or [] if isinstance(p, str) and p.startswith("\\Data\\")]
            if session and paths and sum(j["kind"] == "labels_learn" for j in self.jobs) < 8:
                self.jobs.append({"kind": "labels_learn", "session": session, "paths": paths[:_LEARN_EVENT_MAX]})
        elif kind in ("prop_open", "prop_delete"):          # History (the tab may be archived)
            self._prop_history(kind, str(ev.get("tab") or "")[:64])
        elif kind == "open_model":                          # the + menu's Open Aspen model: .bkp files the user picked
            for path in [p for p in ev.get("paths") or [] if isinstance(p, str) and p
                         and p.strip().lower().endswith(_SAVE_EXT)][:_OPEN_MAX]:
                self.jobs.append({"kind": "open_model", "path": path[:1000], "req": str(ev.get("req") or "")[:40]})
        elif tab is None:
            return                           # an event for a tab that is gone
        elif kind == "program":
            loose = ev.get("loose")
            if self.commit(tab, normalize(ev.get("program")), "user",
                           loose=loose if isinstance(loose, list) else None):
                self.prop_touched(tab)
        elif kind in ("undo", "redo"):
            if self.step(tab, back=kind == "undo"):
                self.prop_touched(tab)
        elif kind == "results":                            # a workbench file's results, opened
            res = ev.get("results")
            if isinstance(res, dict):
                tab["results"] = {"tables": [x for x in res.get("tables") or [] if isinstance(x, dict)],
                                  "opts": [x for x in res.get("opts") or [] if isinstance(x, dict)],
                                  "finished": res.get("finished")}
        # A window write carries when it was posted (``t``): one made while a writer held the
        # session is refused even when it is read after the hold ended (Workspace.writer).
        elif kind == "set_value":
            self.jobs.append({"kind": "set_value", "tab": tab["id"], "path": str(ev.get("path") or ""),
                              "value": ev.get("value"), "unit": ev.get("unit") or None, "t": ev.get("t")})
        elif kind == "struct" and ev.get("op") in _STRUCT_OPS:   # a list's row or a subobject, in the inspector
            lists = [str(p)[:400] for p in ev.get("lists") or [] if str(p).startswith("\\Data\\")]
            self.jobs.append({"kind": "struct", "tab": tab["id"], "op": ev["op"], "lists": lists[:_STRUCT_LISTS],
                              "path": str(ev.get("path") or "")[:400], "label": str(ev.get("label") or "").strip()[:40],
                              "t": ev.get("t")})
        elif kind == "apply_point":                         # write a result's row / best point, run once
            num = lambda v: isinstance(v, int) and not isinstance(v, bool)
            row = ev.get("row")
            row = {"eval": ev["eval"]} if num(ev.get("eval")) else row if row == "best" or num(row) else None
            self.jobs.append({"kind": "apply_point", "tab": tab["id"], "source": str(ev.get("source") or ""),
                              "row": row, "t": ev.get("t")})
        elif kind == "run_sim":                             # Aspen's Run, from the window
            self.jobs.append({"kind": "run_sim", "tab": tab["id"], "reinit": bool(ev.get("reinit")), "t": ev.get("t")})
        elif kind == "save_model":                          # save the model (.bkp), from the window
            self.jobs.append({"kind": "save_model", "tab": tab["id"], "path": str(ev.get("path") or "").strip(),
                              "t": ev.get("t")})
        elif kind in ("checkpoint", "keep_checkpoint"):     # save a named restore point / keep one
            self.jobs.append({"kind": kind, "tab": tab["id"], "req": str(ev.get("req") or "")[:40],
                              "name": " ".join(str(ev.get("name") or "").split())[:_CP_NAME_MAX] or None,
                              "checkpoint": str(ev.get("checkpoint") or "")[:64] or None, "t": ev.get("t")})
        elif kind == "restore":                             # put the model back to a restore point
            ids = ev.get("then_revert") if isinstance(ev.get("then_revert"), list) else []
            self.jobs.append({"kind": "restore", "tab": tab["id"], "req": str(ev.get("req") or "")[:40],
                              "checkpoint": str(ev.get("checkpoint") or "")[:64] or None,
                              "save_first": ev.get("save_first") is not False, "tell_ai": bool(ev.get("tell_ai")),
                              "then_revert": [str(x)[:64] for x in ids if isinstance(x, str) and x][:_REVERT_MAX],
                              "t": ev.get("t")})
        elif kind == "revert":                              # take records or a change group back
            ids, seen = ev.get("ids") if isinstance(ev.get("ids"), list) else [], ev.get("seen")
            self.jobs.append({"kind": "revert", "tab": tab["id"], "req": str(ev.get("req") or "")[:40],
                              "model": str(ev.get("model") or "")[:64] or None,
                              "ids": [str(x)[:64] for x in ids if isinstance(x, str) and x][:_REVERT_MAX],
                              "group": str(ev.get("group") or "")[:64] or None,
                              "mode": "apply" if ev.get("mode") == "apply" else "dry",
                              "on_conflict": str(ev.get("on_conflict") or "abort").lower()[:12],
                              "seen": seen[:64] if isinstance(seen, str) else
                              [str(x)[:200] for x in seen][:_SEEN_MAX] if isinstance(seen, list) else None,
                              "t": ev.get("t")})
        elif kind == "note_add":
            note = {"id": "n" + uuid.uuid4().hex[:6], "target": _note_target(ev.get("target"), tab),
                    "text": str(ev.get("text", "")), "status": "open", "reply": "", "t": ev.get("t"),
                    "tab": tab["id"]}
            self.session(tab["session"])["notes"].append(note)
            self.asks.append({"session": tab["session"], "tab": tab, "note": note})
        elif kind == "note_choose":                         # the user picked from an answer's choices
            self._note_choose(tab, ev)
        elif kind == "select":
            tab["selection"] = ev.get("target")
        elif kind == "inspect":
            self._ask_inspect(tab, ev.get("target"), bool(ev.get("all")))
        elif kind == "inspect_sheet":                       # one form sheet's fields, read when clicked
            sheet = {k: str(ev.get(k) or "")[:200] for k in ("form", "sheet", "ids")}
            tg = ev.get("target") if isinstance(ev.get("target"), dict) else {}
            self.jobs = [j for j in self.jobs if not (j["kind"] == "inspect_sheet" and j["tab"] == tab["id"])]
            if sheet["sheet"] and _base(tg):
                self.jobs.append({"kind": "inspect_sheet", "tab": tab["id"], "req": uuid.uuid4().hex[:6],
                                  "target": {k: str(tg[k]) for k in ("kind", "name", "path") if tg.get(k)}, **sheet})
        elif kind == "objects":                             # the model panel's objects, read when it opens
            op = ev.get("open")
            if not any(j["kind"] == "objects" and j["tab"] == tab["id"] for j in self.jobs):
                self.jobs.append({"kind": "objects", "tab": tab["id"],
                                  "open": str(op)[:300] if isinstance(op, str) and op.startswith("\\Data\\") else None})
        elif kind == "field_info":                          # one field read for a help card
            path = str(ev.get("path") or "")
            if path.startswith("\\Data\\") and len(path) <= 400 and \
                    sum(j["kind"] == "field_info" for j in self.jobs) < _FIELD_INFO_Q:
                self.jobs.append({"kind": "field_info", "tab": tab["id"], "path": path})
        elif kind == "missing":                             # look at incomplete objects in depth
            paths = ev.get("paths") if isinstance(ev.get("paths"), list) else []
            paths = [p for p in paths if isinstance(p, str) and p.startswith("\\Data\\") and len(p) <= 400]
            self.jobs.append({"kind": "missing", "tab": tab["id"], "paths": paths[:_MISS_DEEP_MAX] or None})
        elif kind == "ext_deep":                            # "check for edits made in Aspen" (only on a press)
            tg = ev.get("target")
            if not (isinstance(tg, dict) and tg.get("name")):   # the selected block or stream by default
                tg = tab.get("selection") or (tab.get("inspect") or {}).get("target")
            tg = {"kind": tg.get("kind"), "name": tg.get("name")} if isinstance(tg, dict) else None
            self.jobs.append({"kind": "ext_deep", "tab": tab["id"], "target": tg, "t": ev.get("t")})
        elif kind == "close_inspect":
            tab["inspect"] = tab["isheet"] = None
            tab["selection"] = None
            self.reading.pop(tab["id"], None)
        elif kind == "run":
            if tab["id"] in self.auto_checks:              # the user's own press replaces an automatic check
                self.auto_checks.discard(tab["id"])
                self.pending = [p for p in self.pending if p[0] != tab["id"]]
            if not self.running(tab["id"]) and all(p[0] != tab["id"] for p in self.pending):
                self.pending.append(_Pend(tab["id"], bool(ev.get("dry_run")), _run_mode(ev.get("mode")),
                                          ev["approve"] if ev.get("approve") in ("no_cp", "edits")
                                          else True if ev.get("approve") else None,
                                          str(ev.get("resume"))[:64] if isinstance(ev.get("resume"), str)
                                          and ev.get("resume") else None))
        elif kind == "step":                                # run the next step / on to the end
            if ev.get("action") in ("next", "cont") and self.running(tab["id"]):
                self.steps.setdefault(tab["id"], []).append(ev["action"])   # (each press: one step)
                del self.steps[tab["id"]][:-_PRESSES_MAX]
        elif kind in ("yourturn_done", "yourturn_answer"):  # the user's Done (force: as it is) / the answer
            if self.running(tab["id"]):
                self.turns.setdefault(tab["id"], []).append(
                    {"kind": "answer" if kind == "yourturn_answer" else "done", "force": ev.get("force") is True,
                     "sid": str(ev.get("sid") or "")[:64] or None})
                del self.turns[tab["id"]][:-_PRESSES_MAX]
        elif kind == "predict_watch":                       # the results a prediction compares (no guess)
            paths = ev.get("paths") if isinstance(ev.get("paths"), list) else []
            paths = [p for p in paths if isinstance(p, str) and p.startswith("\\Data\\") and len(p) <= 400]
            self.jobs = [j for j in self.jobs if not (j["kind"] == "predict_watch" and j.get("tab") == tab["id"])]
            self.jobs.append({"kind": "predict_watch", "tab": tab["id"], "paths": paths[:runlog.WATCH_MAX],
                              "id": str(ev.get("id") or "")[:40] or None})
        elif kind == "flows":                               # a component's flow in every stream
            comps = (self.session(tab["session"]).get("flowsheet") or {}).get("components")
            self.flows.ask(tab["session"], tab["id"], ev.get("on") is True, ev.get("comp"),
                           comps if isinstance(comps, list) else None)
        elif kind == "stream_comp":                         # one stream's composition
            fs = self.session(tab["session"]).get("flowsheet") or {}
            names = [x.get("name") for x in fs["streams"] if isinstance(x, dict)] if isinstance(fs.get("streams"), list) else None
            self.flows.ask_stream(tab["session"], ev.get("stream"), names)
        elif kind == "predict_clear":                       # the prediction put away
            self.jobs = [j for j in self.jobs if not (j["kind"] == "predict_watch" and j.get("tab") == tab["id"])]
            runlog.unwatch(tab["session"])
            self.session(tab["session"])["predict"] = None
        elif kind == "breaks":                              # pause before these steps
            ids = ev.get("ids") if isinstance(ev.get("ids"), list) else []
            tab["breaks"] = list(dict.fromkeys(str(x)[:64] for x in ids if isinstance(x, str) and x))[:_BREAKS_MAX]
        elif kind == "proposal_reply":                      # the user sends the AI's proposal back
            self._proposal_reply(tab, ev)
        elif kind == "stop":
            self.stops.add(tab["id"])
            self.auto_checks.discard(tab["id"])
            if any(p[0] == tab["id"] for p in self.pending):
                self.pending = [p for p in self.pending if p[0] != tab["id"]]
                tab["run"]["status"] = "stopped"
                self._drop_proposal(tab["id"], "stopped")
        elif kind == "refresh":
            self.jobs.append({"kind": "refresh", "session": tab["session"]})
        elif kind == "aspen_layout":                        # read the drawing from Aspen
            self.jobs.append({"kind": "aspen_layout", "tab": tab["id"], "session": tab["session"],
                              "req": str(ev.get("req") or "")[:40]})
        elif kind == "fs_layout":                           # the window's arrangement of the flowsheet
            lay = _clean_layout(ev.get("layout"))
            if lay is None:
                logger.warning("workbench: flowsheet arrangement refused: %.200r", ev.get("layout"))
            else:
                self.session(tab["session"])["fs_layout"] = lay
                _keep_layout("fs_layout", lay)
        elif kind == "tab_close":
            self._tab_close(tab, ev)
        elif kind == "tab_close_cancel":                    # the model's tab stays after all
            tab.pop("closing", None)
        elif kind == "prop_shelve":                         # a finished proposal back to History
            if tab.get("kind") == "proposal" and not self.running(tab["id"]):
                if proposals.lane(tab.get("proposal")) == "history":
                    self.archive_tab(tab)
                else:
                    self.message(tab, _t(self.lang, "close_prop_active"), "system")
        elif kind == "tab_rename":
            title = str(ev.get("title") or "").strip()
            if title:
                tab["title"] = title[:60]
        elif kind == "tab_active":
            s["active"] = tab["id"]
            root = self.root_of(tab)
            if root is not None:
                root["front"] = tab["id"]
        elif kind == "to_blocks":                           # records -> a new tab (no COM)
            self._to_blocks(tab, ev)
        elif kind == "aspen_redraw":                        # lay out Aspen's own drawing
            self.jobs.append({"kind": "aspen_redraw", "tab": tab["id"], "req": str(ev.get("req") or "")[:40],
                              "t": ev.get("t")})
        elif kind == "aspen_place":                         # the window's arrangement into Aspen's drawing
            nodes = _place_nodes(ev.get("blocks"))
            if nodes:
                self.jobs.append({"kind": "aspen_redraw", "tab": tab["id"], "req": str(ev.get("req") or "")[:40],
                                  "t": ev.get("t"), "blocks": nodes})

    def _note_choose(self, tab: dict | None, ev: dict) -> None:
        """The event note_choose {id, picks: [index, ...]}: the user's pick among the choices of
        the AI's answer to request ``id``. The request is marked with it (``picked``) and closes;
        the pick goes to the AI as a request of its own -- its text the labels, ``answer_to`` the
        request asked, ``picked`` the labels -- on the same target. One pick per question (the
        window greys the options after it), exactly one unless the answer allows several. A
        request the AI closed after asking (an event it closes with done, as the skill says)
        still takes its pick: only a pick or a new answer ends the question."""
        if tab is None:
            return
        note = next((n for n in self.session(tab["session"])["notes"] if n["id"] == ev.get("id")), None)
        choices = note.get("choices") if note else None
        if not choices or note.get("picked"):
            return
        picks = ev.get("picks") if isinstance(ev.get("picks"), list) else []
        idx = sorted({p for p in picks if isinstance(p, int) and not isinstance(p, bool) and 0 <= p < len(choices)})
        if not idx or (len(idx) > 1 and not note.get("multi")):
            return
        labels = [choices[i]["label"] for i in idx]
        note["picked"], note["status"] = labels, "done"
        journal.GROUPS.close(note["id"])                  # the pick's request starts the next group
        answer = {"id": "n" + uuid.uuid4().hex[:6], "target": note.get("target"),
                  "text": ("、" if self.lang == "zh" else "; ").join(labels), "status": "open", "reply": "",
                  "t": ev.get("t"), "tab": tab["id"], "answer_to": note["id"], "picked": labels}
        self.session(tab["session"])["notes"].append(answer)
        self.asks.append({"session": tab["session"], "tab": tab, "note": answer})

    def _pin_hide(self, tab: dict | None, ev: dict) -> None:
        """The event pin_hide {id, model?}: that pin gone from its model's file and from every
        session showing that model (``model`` defaults to the tab's session's)."""
        pid = str(ev.get("id") or "")[:16]
        model = ev.get("model") if isinstance(ev.get("model"), str) else None
        if model is None and tab is not None:
            model = ((self.state["sessions"].get(tab["session"]) or {}).get("pins") or {}).get("model")
        if not pid or not model:
            return
        data = _pins_of(model)
        keep = [p for p in data["pins"] if p.get("id") != pid]
        if len(keep) != len(data["pins"]):
            data["pins"] = keep
            _pins_keep(data)
        for sess in self.state["sessions"].values():
            if isinstance(sess, dict) and (sess.get("pins") or {}).get("model") == model:
                sess["pins"] = data

    # -- COM work queued by events or runs ------------------------------------
    def work(self, manager) -> bool:
        jobs, self.jobs, changed = self.jobs, [], False
        done = set()
        for job in jobs:
            key = json.dumps({k: v for k, v in job.items() if k != "t"}, sort_keys=True)   # (posted twice: once)
            if key in done:
                continue
            done.add(key)
            try:
                changed |= self._job(manager, job)
            except Exception:
                logger.warning("workbench job %r failed", job, exc_info=True)
        now = time.time()
        for session, job in list(self.auto.items()):     # due, and Aspen not busy for another
            if job["due"] > now or self._auto_waits(session):
                continue
            del self.auto[session]
            try:
                changed |= self._refresh(manager, session, job["what"])
            except Exception:
                logger.warning("workbench: auto refresh of %s failed", session, exc_info=True)
        try:
            changed |= self.miss_tick(manager)            # the due completeness scans
        except Exception:
            logger.warning("workbench: completeness scan failed", exc_info=True)
        try:
            changed |= self.diag_tick(manager)            # the card of a run that failed
        except Exception:
            logger.warning("workbench: run diagnosis failed", exc_info=True)
        try:
            changed |= self.predict_tick(manager)         # a prediction measured by a run
        except Exception:
            logger.warning("workbench: the prediction's state not read", exc_info=True)
        changed |= self.flows.tick(manager, self.state["sessions"], self._flows_block)   # last, low priority
        return changed

    def _flows_block(self, session: str):
        """Why the flow width layer reads nothing on ``session`` now -- "busy" while a
        program or the AI's optimize holds it or Aspen computes for a call; "call" while any tool call
        is in flight or one ended within flows.QUIET_S (the AI's next call goes first) --, or None."""
        if self.busy(session) is not None or _computing(session):
            return "busy"
        return None if flows.quiet(activity.snapshot(), activity.now()) else "call"

    def check_sessions(self, manager) -> bool:
        """Keep the list of open sessions (the window's "new tab" menu) current, and the file
        each shown session's model is saved to (a Save As by the AI moves it), and its journal
        summary (a refused call, another server: what no refresh asked for); a closed session's
        ``sim`` another server process made is dropped (``sim_fresh``)."""
        names = manager.session_names()
        changed = False
        for name in names:
            if name in self.state["sessions"]:
                changed |= self.note_model(manager, name) | self.note_journal(manager, name)
        for name in [n for n in self.state["sessions"] if n not in names]:
            changed |= self.sim_fresh(manager, name)
        if names == self.state["open_sessions"]:
            return changed
        self.state["open_sessions"] = names
        return True

    def _open_model(self, manager, job: dict) -> bool:
        """The window's Open model: the file opened (or the Aspen that already has it open taken)
        as a session of the server that serves the window -- with an AI client that is the AI's
        server, so the AI works on what the user opened -- and shown in its model's tab. What
        became of each file is in state ``open_req`` {req, t, done: [{path, state ok | error,
        text}]}, one entry per file of the request so far."""
        path, before = job["path"], manager.session_names()
        act = activity.begin("user", "open_model", phase="aspen", target={"file": os.path.basename(path)},
                             via="window")
        status, text, ok = "error", "", False
        try:
            if not path.strip().lower().endswith(_SAVE_EXT):
                raise ValueError(_t(self.lang, "save_ext", path=path))
            text = main_tools.open_or_attach(manager, path)
            name = manager._session_name(path)
            if name in manager.session_names():
                if name not in before:
                    set_session_mode(name, "workbench")
                shown = open_workbench_now(manager, name)
                ok = shown.startswith("Workbench open")
                text = text if ok else shown
            status = "ok" if ok else "error"
        except Exception as exc:
            logger.warning("workbench: %s not opened", path, exc_info=True)
            text = _why(exc)
        finally:
            activity.end(act, status)
        req = self.state.get("open_req") if isinstance(self.state.get("open_req"), dict) else {}
        done = list(req.get("done") or []) if req.get("req") == (job.get("req") or "") else []
        done.append({"path": path, "state": "ok" if ok else "error", "text": str(text)[:600]})
        self.state["open_req"] = {"req": job.get("req") or "", "t": time.time(), "done": done[-_OPEN_MAX:]}
        return True

    def _job(self, manager, job: dict) -> bool:
        if job["kind"] == "open_model":
            return self._open_model(manager, job)
        if job["kind"] == "refresh":
            session = job["session"]
            app = manager.get_app(session)
            if app is None:
                return False
            self.session(session)["flowsheet"] = snapshot(manager, session)
            _restore_layouts(self.session(session))
            self.note_model(manager, session)
            self.refresh_results(app, session)
            self.note_cp(manager, session)
            self.miss_touch(session, 0)                  # opened or re-read -- any deep look is old
            return True
        if job["kind"] == "aspen_layout":    # answered even without Aspen: the window waits for it
            return self._aspen_layout(manager, job)
        if job["kind"] == "labels_learn":
            return self._labels_learn(manager, job)
        tab = self.tab(job.get("tab"))
        if tab is None:
            return False
        if job["kind"] == "field_info":                  # a help card's field (waits while Aspen is busy)
            return self._field_info(manager, tab, job)
        if job["kind"] == "inspect_sheet":
            return self._inspect_sheet(manager, tab, job)
        if job["kind"] == "objects":
            return self._objects(manager, tab, job)
        if job["kind"] == "missing":                     # the panel's deep looks (wait while blocked)
            return self._missing(manager, tab, job)
        if job["kind"] == "predict_watch":               # a prediction's results, read now
            return self._predict_watch(manager, tab, job)
        if job["kind"] == "ext_deep":                    # answered even without Aspen: the user pressed a button
            return self._ext_deep(manager, tab, job)
        if job["kind"] == "aspen_redraw":                # the same
            self._aspen_redraw(manager, tab, job)
            return True
        if job["kind"] in _EXT_JOBS:                     # Aspen-window edits journaled first
            self.external(manager, tab["session"], job["kind"])
        if job["kind"] in ("apply_point", "run_sim", "save_model", "checkpoint", "keep_checkpoint", "restore",
                           "revert"):
            getattr(self, "_" + job["kind"])(manager, tab, job)          # answered even without Aspen:
            return True                                                  # the user pressed a button
        app = manager.get_app(tab["session"])
        if app is None:
            return False
        sess = self.session(tab["session"])
        if job["kind"] == "inspect":
            return self._inspect(manager, tab, job)
        if job["kind"] == "units":           # current unit + unit choices of every written path
            for path, _sid, _unit, _basis in _writes(tab["program"]):
                node = _node(app, path)
                if node is not None:
                    sess["units"][path] = _unit_info(node)
            return True
        if job["kind"] in ("set_value", "struct"):      # a value typed, a row or subobject added in the inspector
            (self._set_by_hand if job["kind"] == "set_value" else self._struct_by_hand)(manager, tab, job)
            self.reinspect(manager, tab)
            sh = tab.get("isheet")
            if sh:                                       # the sheet shown, read again
                self.jobs.append({"kind": "inspect_sheet", "tab": tab["id"], "req": uuid.uuid4().hex[:6],
                                  **{k: sh[k] for k in ("target", "form", "sheet", "ids")}})
            return True
        return False

    def _labels_learn(self, manager, job: dict) -> bool:
        """The window's labels_learn: read the GUI prompts of paths its timeline could only name
        by their code (_learn_prompts; ~30 FindNode + attr 19, ~40 ms). While a program or the
        AI's optimize holds the session, or Aspen works on it, the job waits for the next pass;
        a session that is not open drops it. Nothing in state.json changes: the window sees
        learned.json change (Api.strings)."""
        session = job["session"]
        app = manager.get_app(session)
        if app is None:
            return False
        if _computing(session) or (self.busy(session) is not None and self.paused_on(session) is None):
            self.jobs.append(job)                         # (a paused program: reads are fine)
            return False
        fs = (self.state["sessions"].get(session) or {}).get("flowsheet") or {}
        types = {b.get("name"): b.get("type") for b in fs.get("blocks") or [] if b.get("name")}
        _learn_prompts(app, dict.fromkeys(job["paths"]), types, _LEARN_EVENT_MAX)
        return False

    def _field_info(self, manager, tab: dict, job: dict) -> bool:
        """The window's field_info: what a help card could not know without Aspen -- the
        field's prompt (attr 19), value, unit and units, basis (attr 13), whether it takes input
        -- read with one FindNode into the tab's ``field_info`` {path, t, status: ok | waiting |
        closed, found, prompt, value, unit, units, basis, enterable}. Never while a program or
        the optimizer holds the session or Aspen works on it (_computing): the job waits for the
        next pass, the answer saying ``waiting`` meanwhile -- but a program paused before a step
        or waiting for the user (your turn) is read. A prompt no label has yet is learned
        (learned.json), as the inspector's are."""
        session, path, now = tab["session"], job["path"], round(time.time(), 3)
        app = manager.get_app(session)
        if app is None:
            tab["field_info"] = {"path": path, "t": now, "status": "closed"}
            return True
        if self.paused_on(session) is None and (_computing(session) or self.busy(session) is not None):
            self.jobs.append(job)                         # (a program paused, or waiting for the user: read)
            fi = tab.get("field_info")
            if isinstance(fi, dict) and fi.get("path") == path and fi.get("status") == "waiting":
                return False
            tab["field_info"] = {"path": path, "t": now, "status": "waiting"}
            return True
        node = _node(app, path)
        info = {"path": path, "t": now, "status": "ok", "found": node is not None}
        if node is not None:
            row = _row_of(node, path, None, ask=True)
            info.update({k: row.get(k) for k in ("value", "unit", "units", "enterable", "prompt", "basis")})
            if not row["input"]:                          # a result: its prompt all the same
                info["prompt"] = _attr_text(node, 19, _ROW_PROMPT)
            try:
                fs = self.session(session).get("flowsheet") or {}
                types = {b.get("name"): b.get("type") for b in fs.get("blocks") or [] if b.get("name")}
                key = aspen_labels.learn_keys([path], types, 1)
                if key:
                    aspen_labels.learn({k: info.get("prompt") or "" for k in key})
            except Exception:
                logger.warning("workbench: the prompt of %s not learned", path, exc_info=True)
        tab["field_info"] = info
        return True

    def _objects(self, manager, tab: dict, job: dict) -> bool:
        """The window's objects (the model panel opened): the session's ``objects`` {t, items
        (inputs_check.model_objects), open (the heavy containers the user opened)}. Waits while a
        program or the optimizer holds the session or Aspen computes (a program paused: read)."""
        session = tab["session"]
        app = manager.get_app(session)
        if app is None:
            return False
        if self.paused_on(session) is None and (_computing(session) or self.busy(session) is not None):
            self.jobs.append(job)
            return False
        sess = self.session(session)
        was = sess.get("objects") if isinstance(sess.get("objects"), dict) else {}
        opened = [p for p in was.get("open") or () if isinstance(p, str)][:8]
        if job.get("open") and job["open"] not in opened:
            opened.append(job["open"])
        items = IC.model_objects(app, opened)
        if was.get("items") == items and was.get("open") == opened:
            return False
        sess["objects"] = {"t": time.time(), "items": items, "open": opened}
        return True

    def _ask_inspect(self, tab: dict, target, all_fields: bool) -> dict:
        """An inspect job for the tab (the window's inspect, reinspect, a program's end): a new request,
        the one the tab reads from now on (_inspect drops an older one)."""
        job = {"kind": "inspect", "tab": tab["id"], "target": target, "all": all_fields, "req": uuid.uuid4().hex[:6]}
        self.jobs.append(job)
        self.reading[tab["id"]] = [job["req"], None]
        return job

    def reinspect(self, manager, tab: dict) -> bool:
        """The tab's inspector read again (a value written, a run, a refresh), the way a pick reads it:
        an inspect job, its first pass now (the rows shown stay until read anew: inspect_steps ``was``)."""
        v = tab.get("inspect")
        if not v:
            return False
        job = self._ask_inspect(tab, v["target"], v.get("all", False))
        self.jobs.remove(job)
        return self._inspect(manager, tab, job)

    def _inspect(self, manager, tab: dict, job: dict) -> bool:
        """The window's inspect: inspect_steps a pass at a time -- _INSPECT_MS of reads, the sync
        loop's next passes go on -- into the tab's ``inspect``: the rows read so far with ``reading``,
        then the whole view. A request the tab no longer reads (another pick, a close) is dropped."""
        cur = self.reading.get(tab["id"])
        if not cur or cur[0] != job["req"]:
            return False
        if cur[1] is None:
            if _tkey(job["target"]) != _tkey((tab.get("isheet") or {}).get("target")):
                tab["isheet"] = None
            tab["selection"] = job["target"]
            cur[1] = inspect_steps(manager, self.session(tab["session"]), tab["session"], job["target"], job["all"],
                                   _INSPECT_MS, tab.get("inspect"))
        try:
            view = next(cur[1])
        except Exception:
            self.reading.pop(tab["id"], None)
            raise
        tab["inspect"] = view
        if view.get("reading"):
            self.jobs.append(job)
        else:
            self.reading.pop(tab["id"], None)
        return True

    def _inspect_sheet(self, manager, tab: dict, job: dict) -> bool:
        """The window's inspect_sheet: one form sheet's fields as inspector rows into the tab's
        ``isheet`` {target, form, sheet, ids, req, t, status reading | done | waiting, n (paths),
        rows}: the paths first (gui_sheets.sheet_paths), then _SHEET_MS of reads a pass
        (_sheet_rows), the rest on the next passes; the fields holding no value last. It waits
        while a program or the optimizer holds the session or Aspen works on it (a program
        paused: read), and is dropped once the inspector shows another object or another sheet
        was asked for."""
        session, tg = tab["session"], job["target"]
        if _tkey(tg) != _tkey((tab.get("inspect") or {}).get("target") or tab.get("selection")):
            return False
        app, sh = manager.get_app(session), tab.get("isheet")
        if app is None:
            return False
        head = {k: job[k] for k in ("target", "form", "sheet", "ids", "req")}
        # the same sheet read again (a value written): its rows stay shown, in place, till each is read anew
        same = isinstance(sh, dict) and all(sh.get(k) == head[k] for k in ("target", "form", "sheet", "ids"))
        was = {k: list(sh.get(k) or ()) if same else [] for k in ("rows", "lists")}
        if self.paused_on(session) is None and (_computing(session) or self.busy(session) is not None):
            self.jobs.append(job)
            if isinstance(sh, dict) and sh.get("req") == job["req"]:
                return False
            tab["isheet"] = dict(head, t=time.time(), status="waiting", n=0, **was)
            return True
        base = _base(tg)
        if "paths" not in job:
            job["paths"] = IC.sheet_paths(app, base, job["sheet"], [i for i in job["ids"].split("/") if i])
            job.update(at=0, was=was, got=[], lists=[])
            sh = tab["isheet"] = dict(head, status="reading", n=len(job["paths"]), **was)
        elif not (isinstance(sh, dict) and sh.get("req") == job["req"]):
            return False
        end, nodes, new = time.perf_counter() + _SHEET_MS / 1000, {}, []
        lists = job["lists"]
        n0 = len(lists)
        while job["at"] < len(job["paths"]):             # (one field at least each pass)
            job["at"] += 1
            new += _sheet_rows(app, base, job["paths"][job["at"] - 1], nodes, lists=lists)
            if time.perf_counter() > end:
                break
        types = _types_of(self.session(session))
        _learn_prompts(app, {r["path"]: nodes.get(r["path"]) for r in new}, types, _LEARN_MAX,
                       known={r["path"]: r["prompt"] for r in new if "prompt" in r})
        locs = aspen_labels.labels([r["path"] for r in new + lists[n0:]], types)
        for r in new + lists[n0:]:
            r["loc"] = locs.get(r["path"])
        _opts(new, types)
        job["got"] = sorted(job["got"] + new, key=lambda r: r["value"] in (None, ""))
        sh["t"], sh["status"] = time.time(), "reading" if job["at"] < len(job["paths"]) else "done"
        sh["rows"], sh["lists"] = job["got"], lists
        if sh["status"] == "reading":
            sh["rows"], sh["lists"] = _in_place(job["was"]["rows"], job["got"]), _in_place(job["was"]["lists"], lists)
            self.jobs.append(job)
        else:                                            # (the fields its settings turn off: greyed, as the inspector's)
            typ = (tab.get("inspect") or {}).get("type") or (_attr_text(_node(app, base), 6, 40) if tg.get("kind") == "stream" else None)
            _off(sh["rows"], IC.off_fields(app, base, typ))
        return True

    def _predict_watch(self, manager, tab: dict, job: dict) -> bool:
        """The window's predict_watch -- the results a prediction compares (at most
        runlog.WATCH_MAX paths; the guesses stay in the window) -- read now (runlog.watch, one
        lookup each) into the session's ``predict``; its next run reads them again. While a
        program or the optimizer works on the session the job waits for the next pass (a program
        paused or waiting for the user: reads are fine). No paths: the prediction is put away."""
        session = tab["session"]
        if manager.get_app(session) is None:
            return False
        if self.paused_on(session) is None and (_computing(session) or self.busy(session) is not None):
            self.jobs.append(job)
            return False
        self.session(session)["predict"] = runlog.watch(manager, session, job["paths"], job.get("id"))
        return True

    def predict_tick(self, manager) -> bool:
        """The sync loop's prediction pass: each session's ``predict`` follows its runlog watch -- measured
        by the session's next run, whoever made it; gone after runlog.WATCH_TTL_S, or once the
        session holds another model. No COM. Returns whether one changed."""
        changed = False
        for name, sess in self.state["sessions"].items():
            if not isinstance(sess, dict):
                continue
            w = runlog.watching(name)
            if w is not None and w.get("model") != manager.model_id(name):
                runlog.unwatch(name)
                w = None
            if w != sess.get("predict") and (w is not None or sess.get("predict") is not None):
                sess["predict"] = w
                changed = True
        return changed

    def _aspen_layout(self, manager, job: dict) -> bool:
        """Read the model's drawing from Aspen for the window's Aspen layout. Every request
        gets an answer (``aspen_layout_req``, matched by ``req``); only a good import replaces
        the one kept (``aspen_layout``), and both arrive in the same save. A tab closed before
        the job ran still gets its session an answer: the window waits on the session."""
        tab = self.tab(job.get("tab"))
        session = tab["session"] if tab is not None else job.get("session")
        if not session or session not in self.state.get("sessions", {}):
            return False
        req, now = job.get("req") or "", time.time()
        sess = self.session(session)
        app = manager.get_app(session)
        if app is None:
            sess["aspen_layout_req"] = {"req": req, "status": "closed", "at": now}
            return True
        try:
            # each phase can take seconds on a large model: beat before each, or the window
            # takes the server for gone
            self.beat()
            fs, old = snapshot(manager, session), sess.get("flowsheet") or {}
            if all(old.get(k) == fs.get(k) for k in ("blocks", "streams", "components", "model")):
                fs["taken_at"] = old.get("taken_at", fs["taken_at"])   # unchanged: no new layout, no refit
            sess["flowsheet"] = fs
            _restore_layouts(sess)
            self.beat()
            self.refresh_results(app, session)
            self.beat()
            text = pfsv.export_text(app, _TMP)
            lay = pfsv.aspen_layout(pfsv.parse_pfsvdata(text), fs, req, fs.get("model"))
        except Exception as exc:
            logger.warning("workbench: reading the layout from Aspen failed", exc_info=True)
            sess["aspen_layout_req"] = {"req": req, "status": "failed", "error": _why(exc)[:300], "at": now}
            return True
        if lay["status"] == "ok":
            sess["aspen_layout"] = lay
            _keep_layout("aspen_layout", lay)
        sess["aspen_layout_req"] = {"req": req, "status": lay["status"], "at": now}
        return True

    @_by_user("inspector")
    def _set_by_hand(self, manager, tab: dict, job: dict) -> None:
        """A value typed into the inspector: written as the user's. While a program is paused on
        the session too -- in that run's change group (_by_user), taken off its restore
        ledger (the program's end keeps it: _Runner.user_wrote) and its next step read again."""
        path, unit, lang = job["path"], job["unit"], self.lang
        why = self.writer(tab["session"], t=job.get("t"), paused_ok=True)
        if why is not None:
            self.message(tab, why, "system")
            return
        value = job["value"]
        if isinstance(value, str):
            num = _num(value.strip())
            value = num if num is not None else value.strip()
        app = manager.get_app(tab["session"])
        why = _unwritable(app, path, unit, lang)
        old, old_unit = _held(app, path) if why is None else (None, None)
        res = why or manager.set_node_value(tab["session"], path, value=value, unit=unit)
        if why or not res.startswith("Set "):
            self.message(tab, _t(lang, "edit_fail", path=path, res=res), "system")
            return
        node = _node(app, path)
        shown = _unit_info(node)["unit"] if node is not None else unit
        was = _t(lang, "edit_empty") if old is None or old == "" else _fmt(old)
        if old_unit and old_unit != shown and old is not None:
            was += f" {old_unit}"
        sess = self.session(tab["session"])
        rec = _recorded("value")                          # the window's "Undo" on this line
        paused = self.paused_on(tab["session"])
        self.message(tab, _t(lang, "edit_ok", label=_label_of(sess.get("flowsheet") or {}, path, lang), old=was,
                             value=_fmt(value), unit=f" {shown}" if shown else ""), "user",
                     **({"record": rec} if rec else {}),
                     **({"paused_at": paused.stopped_at()} if paused is not None else {}))
        sess["units"][path] = _unit_info(node) if node is not None else {}
        self.miss_touch(tab["session"])                   # a completeness scan once the typing stops
        if paused is not None:
            paused.user_wrote(path)

    @_by_user("inspector")
    def _struct_by_hand(self, manager, tab: dict, job: dict) -> None:
        """A list's row or a block's subobject added or taken out in the inspector (event
        struct {op row_add | row_del | sub_add | sub_del, lists | path, label}): measured as the
        AI's insert_row / remove_row / add_element / remove_element are -- a restore point before the
        user's first structural change of the group, one add / remove record per row or object --
        so the chat line's Undo takes it back as a typed value's. A row goes into the lists of one
        table (_rows_change); a subobject ``label`` into the collection ``path``. Refused while a
        program or another writer holds the session, or one is paused on it."""
        session, op, label, lang = tab["session"], job["op"], job["label"], self.lang
        why = self.writer(session, t=job.get("t"))
        if why is not None:
            self.message(tab, why, "system")
            return
        app, sc = manager.get_app(session), recorder.current()
        if op.startswith("row"):
            lists = [p for p in job["lists"] if _node(app, p) is not None]
            tool, where = ("insert_row" if op == "row_add" else "remove_row"), (lists or [""])[0]
            probe = "+".join("rows:" + p for p in lists)
            fn = lambda: _rows_change(manager, session, op == "row_add", lists, label)  # noqa: E731
        else:
            tool, where = ("add_element" if op == "sub_add" else "remove_element"), job["path"]
            probe = intercept.TOOLS[tool].probe
            fn = lambda: getattr(manager, tool)(session, where, label)  # noqa: E731
        if not where or (not label and op != "row_add") or _node(app, where) is None:
            return
        args = {"session_name": session, "aspen_path": where, ("name" if op.startswith("sub") else "label"): label}
        if sc is not None and getattr(sc, "on", False):
            sc.tool = tool                                # (its records are that tool's: the timeline, the undo)
            intercept.restore_point(manager, session, "before-structure", group=sc.group, dedup=True,
                                    actor="user", via="inspector", tool=tool)
            p = probes.Probe(manager, sc, tool, probe, args,
                             describe=lambda a: (intercept.target_of(tool, a), intercept.args_summary(a)))
            p.before()
            res = fn()
            p.done(res)
        else:
            res = fn()
        ok = str(res).startswith(("Inserted", "Removed", "Added"))
        segs = where.split("\\")
        name = _label_of(self.session(session).get("flowsheet") or {}, where, lang) if op.startswith("row") \
            else f"{segs[3]} › {segs[-1]} {label}"
        rec, row = _recorded(("add", "remove")), next(iter(re.findall(r"row '([^']*)'", str(res))), label)
        self.message(tab, _t(lang, op if ok else "insp_struct_fail", label=name, row=row or "#", res=_said(res)),
                     "user" if ok else "system", **({"record": rec} if ok and rec else {}))
        if ok:
            self.miss_touch(session)

    @_by_user()
    def _run_sim(self, manager, tab: dict, job: dict) -> None:
        """The window's Run simulation: the model runs once as it stands (Reinitialize first
        with ``reinit``), as Aspen's Run does; the tab's program and run log stay as they are.
        The outcome goes to the session's ``sim``: status "running", then "done" (Aspen ran to
        its end, errors or not: see ``outcome``, and ``msgs``, Aspen's run-status lines) or
        "error" (it did not run, said in the chat too); "busy", refused while another writer
        has the session (``writer``). An attempt that did not run keeps what the last run that
        ran said (``_last_run``: outcome, blocks, msgs, finished). ``outcome`` ok | warn | error |
        unknown (the run status unreadable), after a warn ``first_warn`` / ``warns_more``
        (_simulate); ``load``: the load of the model it is about (sim_fresh)."""
        lang, session, now = self.lang, tab["session"], time.time()
        sess = self.session(session)
        self.sim_fresh(manager, session)                  # (a run of an earlier load says nothing now)
        old = sess.get("sim") or {}
        last = _last_run(old)
        load = _load_of(manager, session)
        why = self.writer(session, t=job.get("t"), waiting_ok=True)     # (the user tries their value)
        if why is not None:
            sess["sim"] = dict(old, status="busy", at=now, load=load)
            self.message(tab, why, "system")
            return
        base = {"started": now, "reinit": bool(job.get("reinit")), "errors": [], "warns": [], "msgs": [],
                "load": load}
        if manager.get_app(session) is None:
            text = _t(lang, "no_session", session=session)
            sess["sim"] = {**base, "outcome": "error", **last, "status": "error", "at": now, "text": text}
            self.message(tab, text, "system")
            return
        sess["sim"] = {**base, **last, "status": "running", "at": now}
        self.save()                                       # the window shows it: a run holds this loop
        self.beat()
        with _in_aspen("run_sim", tab, {"reinit": True} if base["reinit"] else None):
            sim = _simulate(self, manager, session, base["reinit"])
        end = time.time()
        waiting = self.paused_on(session) if sim["ran"] else None
        if waiting is not None:                           # a program's ledger re-runs after its restores
            waiting.nrun += 1
        if sim["reinit_error"] is not None:
            text = _t(lang, "reinit_fail", res=sim["reinit_error"])
        elif not sim["ran"]:
            text = _sim_fail(lang, sim["res"])
        else:
            text = _sim_text(lang, sim)
        rec = dict(base, errors=sim["errors"], warns=sim["warns"], msgs=sim["msgs"], outcome=sim["outcome"], at=end,
                   text=text[:1500], **_sim_warn(sim))
        if sim.get("nmsgs"):
            rec["nmsgs"] = sim["nmsgs"]
        if sim["ran"]:
            sess["sim"] = dict(rec, status="done", finished=end)
            _fx_own(sess, sim.get("rec"))
        else:
            sess["sim"] = {**rec, **last, "status": "error"}
            if _MISS_REFUSED in sim["res"]:               # refused, inputs incomplete -- scan at once
                sess["sim"]["incomplete"] = True
                self.miss_touch(session, 0, edit=False)
            self.message(tab, text, "system")
        self.beat()
        for t in self.tabs_for(session):                  # the inspectors show the new results
            self.reinspect(manager, t)

    @_by_user()
    def _save_model(self, manager, tab: dict, job: dict) -> None:
        """The window's Save model: the session's model to the file on record for it, backed up
        first (manager.save, tools/checkpoints.py), or with ``path`` (relative: beside that file)
        a Save As the session then continues in. Done: the session's ``saved`` and a system
        line in the chat; refused while another writer has the session; a failure is a line in
        the chat and a warning in the server's log."""
        lang, session = self.lang, tab["session"]
        why = self.writer(session, "save", t=job.get("t"), waiting_ok=True)
        if why is not None:
            self.message(tab, why, "system")
            return
        path = _beside_model(manager, session, job.get("path") or "") if job.get("path") else None
        try:
            if manager.get_app(session) is None:
                raise RuntimeError(_t(lang, "no_session", session=session))
            if path and not path.lower().endswith(_SAVE_EXT):
                raise ValueError(_t(lang, "save_ext", path=path))
            self.beat()                                   # a model with many results saves slowly
            with _in_aspen("save_model", tab, {"file": os.path.basename(path)} if path else None):
                res = (manager.save_as(session, path, tool="workbench") if path
                       else manager.save(session, tool="workbench"))
        except Exception as exc:
            logger.warning("workbench: saving session %s%s failed: %s", session, f" as {path}" if path else "",
                           _why(exc))
            self.message(tab, _t(lang, "save_fail", res=_why(exc)), "system")
            return
        b = res.get("backup")
        self.session(session)["saved"] = {
            "at": time.time(), "path": res["path"],
            "backup": {k: b[k] for k in ("id", "path", "warning") if b.get(k)} if b else None}
        self.message(tab, _t(lang, "model_saved", file=os.path.basename(str(res["path"])),
                             backup=_t(lang, "model_saved_bk") if b else ""), "system")
        self.note_model(manager, session)
        self.beat()

    def _checkpoint(self, manager, tab: dict, job: dict) -> None:
        """The window's "Save restore point...": a named restore point of the session's
        model, kept for good (intercept.restore_point -> restore_points.make): a copy of the file
        when the model is its file, else Export(1) however long it takes -- the heartbeat's
        activity "checkpoint" counts it meanwhile. The user's, in a change group of its own (the
        timeline's milestone). Answered in the session's ``cp.req``: {"req", "status": running,
        then done | failed | busy, "name", "est_s", "id", "state", "secs", "text", "at"}, and a
        chat line; refused while another writer has the session."""
        lang, session = self.lang, tab["session"]
        req = {"req": job.get("req") or "", "at": time.time()}
        name = job.get("name") or _t(lang, "cp_default", hm=time.strftime("%H:%M"))
        why, status = self.writer(session, "cp", t=job.get("t"), waiting_ok=True), "busy"
        if why is None and manager.get_app(session) is None:
            why, status = _t(lang, "no_session", session=session), "failed"
        if why is not None:
            self.note_cp(manager, session, dict(req, status=status, name=name, text=why))
            self.message(tab, why, "system")
            return
        est = restore_points.estimate(manager.model_id(session), manager.session_file(session)).get("s")
        self.note_cp(manager, session, dict(req, status="running", name=name, est_s=est))
        self.save()                                       # the window shows it: an export holds this loop
        self.beat()
        rp = intercept.restore_point(manager, session, "manual", name=name, group=_own_group(session, name),
                                     actor="user", via="window", tool="checkpoint")
        done = rp.get("status") in ("copied", "exported")
        if done:
            how = _t(lang, "cp_how_copy" if rp["status"] == "copied" else "cp_how_export")
            text = _t(lang, "cp_saved", name=name, how=how, secs=_dur(lang, rp.get("secs")))
        else:
            text = _t(lang, "cp_fail", name=name, why=" ".join(str(rp.get("error") or rp.get("why") or "?").split())[:300])
        self.note_cp(manager, session, dict(req, status="done" if done else "failed", name=name, est_s=est,
                                            id=rp.get("id"), state=rp.get("state"), secs=rp.get("secs"),
                                            text=text, at=time.time()))
        self.message(tab, text, "system")
        self.note_journal(manager, session)
        self.beat()

    def _keep_checkpoint(self, manager, tab: dict, job: dict) -> None:
        """The window's "Keep" on an automatic restore point: kept for good, out of the
        rotation of each model's newest checkpoints.AUTO_KEEP -- a ``named`` event in its index
        (restore_points.keep), with the name given. No COM and no model change, so a writer
        holding the session does not stop it. Answered in ``cp.req``; a chat line when the
        point is gone."""
        session, cid = tab["session"], job.get("checkpoint")
        sess = self.session(session)
        model = manager.model_id(session) if manager.get_app(session) is not None else \
            (sess.get("model") or {}).get("id")
        kept = restore_points.keep(model, cid, job.get("name")) if model and cid else None
        req = {"req": job.get("req") or "", "at": time.time(), "id": cid, "status": "done" if kept else "failed"}
        if kept:
            req["name"] = kept.get("name")
        else:
            req["text"] = _t(self.lang, "cp_keep_fail")
            self.message(tab, req["text"], "system")
        self.note_cp(manager, session, req)

    def _restore(self, manager, tab: dict, job: dict) -> None:
        """The window's "Restore to here", and "Undo this restore" (the same, to its
        ``before_cp``): AspenPlusManager.restore on the session's model -- kept first when
        ``save_first`` (intercept.restore_point, reason before-restore, an Export however slow:
        the user chose it; the activity "checkpoint" counts it), the user's file backed up, the
        point's content put in its place and the session reopened under the same name and model
        id (activity "restore", ``est_s``: about an Export's time). The user's, in a change group
        of its own: the before-restore milestone, then the restore record. Tabs, blocks, notes
        and arrangements stay; the flowsheet, results and every open inspector are read again.
        ``tell_ai``: an Ask AI note says so too (the AI's brief tells it in any case);
        ``then_revert``: a revert job of those records follows into the same group ("restore to
        before this group" -- the revert job answers it). Answered in the session's
        ``restore_req``: {"req", "status": running, then done | recovered | failed | refused |
        busy, "checkpoint", "name", "est_s", "save_first", "code", "before_cp", "now", "secs",
        "record", "group", "text", "at"}, and a chat line. Refused while another writer has the
        session."""
        lang, session, cid = self.lang, tab["session"], job.get("checkpoint")
        sess = self.session(session)
        req = {"req": job.get("req") or "", "checkpoint": cid, "save_first": bool(job.get("save_first")),
               "at": time.time()}
        model = manager.model_id(session) if manager.get_app(session) is not None else None
        cp = checkpoints.get(model, cid) if model and cid else None
        name = self._cp_name(cp) if cp else (cid or "?")
        why, status = self.writer(session, "rs", t=job.get("t")), "busy"
        if why is None and model is None:
            why, status = _t(lang, "no_session", session=session), "failed"
        if why is not None:
            sess["restore_req"] = dict(req, status=status, name=name, text=why)
            self.message(tab, why, "system")
            return
        est = restore_points.restore_estimate(model, cp["path"]) if cp else None
        sess["restore_req"] = dict(req, status="running", name=name, est_s=est)
        self.save()                                       # the window shows it: Aspen holds this loop meanwhile
        self.beat()
        group = _own_group(session, None, "restore")
        before = (lambda: intercept.restore_point(manager, session, "before-restore", group=group, dedup=False,
                                                  actor="user", via="window", tool="restore", allow_slow=True)) \
            if job.get("save_first") else None
        res = manager.restore(session, cid or "", before=before, tool="restore", actor="user", via="window",
                              group=group, act={"tab": tab["id"]})
        text = self._restore_text(manager, session, res, cp, name)
        sess["restore_req"] = dict(req, status=res["status"], name=name, est_s=est, code=res.get("code"),
                                   before_cp=res.get("before_cp"), now=res.get("now"), secs=res.get("secs"),
                                   record=res.get("record"), group=(group or {}).get("id"), text=text,
                                   at=time.time())
        self.message(tab, text, "system")
        self.beat()
        if res.get("reopened"):
            self._refresh(manager, session, {"topology"})     # flowsheet, results, units, every open inspector
        else:
            self.check_sessions(manager)
        self.note_cp(manager, session)
        if res["status"] == "done":
            self._prop_undone(session, "restore", cp=cid)       # "restore to before the proposal"
            if job.get("tell_ai"):
                note = {"id": "n" + uuid.uuid4().hex[:6], "target": None, "status": "open", "reply": "",
                        "text": _t(lang, "rs_ai_note", when=_when(cp.get("t")), name=name), "t": time.time(),
                        "tab": tab["id"]}
                sess["notes"].append(note)
                self.asks.append({"session": session, "tab": tab, "note": note})
            if job.get("then_revert"):
                self.jobs.append({"kind": "revert", "tab": tab["id"], "model": model, "ids": job["then_revert"],
                                  "group": None, "mode": "apply", "on_conflict": "skip", "req": req["req"],
                                  "into": (group or {}).get("id"), "after": res.get("record"), "t": time.time()})

    def _prop_undone(self, session: str, how: str, cp: str | None = None, group: str | None = None) -> None:
        """The model put back to an approved proposal's restore point (``cp``), or its change
        group undone (``group``): that proposal's run is marked taken back (proposals.undone)."""
        for t in self.tabs_for(session):
            r = (t.get("proposal") or {}).get("run") if t.get("kind") == "proposal" else None
            if isinstance(r, dict) and ((cp and (r.get("cp") or {}).get("id") == cp) or (group and r.get("group") == group)):
                proposals.undone(t["proposal"], how, time.time())
        key, now = self.mkey_of(session), time.time()     # ... and one kept in History
        for e in list(self.arch.index(key)):
            if not e.get("undone") and ((cp and e.get("cp") == cp) or (group and e.get("group") == group)):
                try:
                    self.arch.update(key, e["tab"], lambda tb: proposals.undone(tb.get("proposal") or {}, how, now),
                                     proposals.history_entry)
                except OSError:
                    logger.warning("workbench: archived proposal %s not marked undone", e["tab"], exc_info=True)

    def _cp_name(self, cp: dict) -> str:
        """A restore point as the window names it: its name, else what it was kept before."""
        key = f"cpr_{cp.get('reason')}"
        return cp.get("name") or _t(self.lang, key if key in _MSG else "cpr_manual")

    def _restore_text(self, manager, session: str, res: dict, cp: dict | None, name: str) -> str:
        """AspenPlusManager.restore's result as the chat line (the window's language)."""
        lang, st, code = self.lang, res["status"], res.get("code")
        file = os.path.basename(manager.session_file(session) or (self.session(session).get("model") or {}).get("file")
                                or "?")
        err = " ".join(str(res.get("error") or res.get("text") or "?").split())[:300]
        if st == "done":
            return _t(lang, "rs_done", name=name, when=_when((cp or {}).get("t")), file=file,
                      backup=_t(lang, "rs_backup") if res.get("backup") else "",
                      undo=_t(lang, "rs_undo" if res.get("before_cp") else "rs_noundo"))
        if st == "recovered":
            where = _t(lang, "rs_at_before" if res.get("now") == "before_cp" else "rs_at_file", file=file)
            return _t(lang, "rs_recovered", name=name, why=err, where=where)
        if st == "failed":
            return _t(lang, "rs_closed", name=name, why=err, file=file)
        if code == "busy":
            return _t(lang, "rs_busy", session=session)
        if code == "no_session":
            return _t(lang, "no_session", session=session)
        key = f"rs_why_{code}"
        why = _t(lang, key, file=file, err=err) if key in _MSG else err
        return _t(lang, "rs_fail", name=name, why=why)

    def _revert(self, manager, tab: dict, job: dict) -> None:
        """The window's "Undo", "Undo this group" and "Redo" (a redo is the undo of an
        undo): tools/undo.py's revert of records ``ids`` or change group ``group`` of the tab's
        session's model (``model``: the one the window meant -- another one open there now is
        refused). ``mode`` "dry": planned from the journal and checked against the live model,
        nothing written -- the preview; "apply": carried out, a conflict as ``on_conflict`` says
        (abort -- the default, also "ask" --, skip, force / overwrite), and only while the plan's
        steps are those of the preview the user confirmed (``seen``: the preview's ``sig``, or
        its step keys; else nothing is done, code plan_changed, with the fresh preview). Written
        as the user's (via window, tool revert) in a change group of its own -- ``into``: the
        restore's, with ``after`` its record, for "restore to before this group" (_restore's
        then_revert: only what came after the restore counts as changed since). Undoing a
        restore restores the point kept before it, keeping the model first so that can be undone
        too (``_undo_restore``). Answered in the session's ``undo_req`` (fixed size): {"req",
        "mode", "ids" (at most undo.IDS_MAX; ``ids_n``), "group", "after", "status": planned
        (dry) | running, then done | partial | conflict | nothing | failed, or refused | busy,
        "code", "preview": undo.preview with each shown step's live ``state`` (ok | already |
        conflict | blocked | restore | pending), ``state_code`` and ``now``, "sig" (send it back
        as ``seen``), "live": the live check's counts by state, "conflicts" (live, at most
        undo.CONFLICTS_MAX) and "conflicts_more", "result" (applied: _undo_result), "text",
        "at"}; applied, not a conflict: a chat line too. Refused (busy) while a program or the
        AI's optimize holds the session. What the result says changed is read again
        (``refresh``: the flowsheet, or the open inspectors' values)."""
        lang, session = self.lang, tab["session"]
        sess = self.session(session)
        mode = "apply" if job.get("mode") == "apply" else "dry"
        ids = list(job.get("ids") or [])
        req = {"req": job.get("req") or "", "mode": mode, "ids": ids[:undo.IDS_MAX] or None,
               "group": job.get("group"), "at": time.time()}
        if len(ids) > undo.IDS_MAX:
            req["ids_n"] = len(ids)
        if job.get("after"):
            req["after"] = job["after"]
        model = manager.model_id(session) if manager.get_app(session) is not None else None
        why, status = self.writer(session, "rv", t=job.get("t")), "busy"
        if why is None and model is None:
            why, status, req["code"] = _t(lang, "no_session", session=session), "refused", "no_session"
        elif why is None and job.get("model") and job["model"] != model:
            why, status, req["code"] = _t(lang, "rv_wrong_model", session=session), "refused", "wrong_model"
        if why is not None:
            sess["undo_req"] = dict(req, status=status, text=why)
            self.message(tab, why, "system")
            return
        if mode == "apply":
            sess["undo_req"] = dict(req, status="running")
            self.save()                                   # the window shows it: a structural undo keeps the model first
            self.beat()
        out = undo.revert(manager, session, model=model, ids=ids or None, group=job.get("group"),
                          on_conflict=job.get("on_conflict") or "abort", dry=mode == "dry", seen=job.get("seen"),
                          restore=self._undo_restore(manager, tab), into=job.get("into"), after=job.get("after"))
        chk, res = out.get("check") or {}, out.get("result")
        pv = _undo_preview(out.get("plan"), chk)
        q = dict(req, preview=pv, sig=(pv or {}).get("sig"), live=chk.get("n") or {})
        if mode == "dry":
            q.update(conflicts=list(chk.get("conflicts") or [])[:undo.CONFLICTS_MAX],
                     conflicts_more=chk.get("conflicts_more") or 0)
            if pv is None:
                q.update(status="failed", text=_t(lang, "rv_failed", why=(res or {}).get("text") or "?"))
            elif chk.get("error"):
                q.update(status="refused", code="no_session", text=_t(lang, "no_session", session=session))
            else:
                q.update(status="planned", text=self._undo_plan_text(pv, q["live"]))
        else:
            res = res or {"status": "failed", "text": "?"}
            conf = list(res.get("conflicts") or [])
            q.update(status=res.get("status"), code=res.get("code"), conflicts=conf[:undo.CONFLICTS_MAX],
                     conflicts_more=max(0, len(conf) - undo.CONFLICTS_MAX), result=_undo_result(res),
                     text=self._revert_text(res, session))
            if res.get("status") != "conflict":
                self.message(tab, q["text"], "system")
            if res.get("status") in ("done", "partial") and job.get("group"):
                self._prop_undone(session, "revert", group=job["group"])   # "undo this group"
        q["at"] = time.time()
        sess["undo_req"] = q
        self.beat()
        steps = (res or {}).get("steps") or ()
        refresh = "topology" if any(s.get("kind") == "restore" for s in steps) else (res or {}).get("refresh")
        if mode == "apply" and refresh:
            self._refresh(manager, session, {refresh})    # the flowsheet and results, or the inspectors' values
        else:
            self.note_journal(manager, session)

    def _undo_restore(self, manager, tab: dict):
        """undo.revert's ``restore`` hook: a restore step -- undoing a restore -- restores the point
        kept before it (manager.restore), keeping the model first (reason before-restore, however
        slow: the user asked, and so this undo can be undone in turn), journaled in the undo's
        group and call with ``revert_of``; the heartbeat shows the activity "restore" meanwhile."""
        session = tab["session"]

        def hook(step: dict, group, call) -> dict:
            gid = group.get("id") if isinstance(group, dict) else group
            self.beat()
            return manager.restore(
                session, step.get("checkpoint") or "", tool="restore", actor="user", via="window", group=gid,
                call=call, act={"tab": tab["id"]}, fields={"revert_of": step.get("of")},
                before=lambda: intercept.restore_point(manager, session, "before-restore", group=gid, dedup=False,
                                                       actor="user", via="window", tool="restore", call=call,
                                                       allow_slow=True))
        return hook

    def _undo_plan_text(self, pv: dict, live: dict) -> str:
        """A preview in one line (the window's language): how many changes it would take back,
        and what stands in the way."""
        lang, n = self.lang, (pv.get("n") or {})
        k = n.get("steps") or 0
        if not k:
            return _t(lang, "rv_nothing") + _t(lang, "rv_end")
        head = _t(lang, "rv_plan_redo" if pv.get("redo") else "rv_plan", n=k, s="s" * (k != 1))
        return head + self._undo_bits({"approx": n.get("approx"), "already": live.get("already"),
                                       "conflict": live.get("conflict"),
                                       "blocked": (n.get("blocked") or 0) + (live.get("blocked") or 0)})

    def _revert_text(self, res: dict, session: str) -> str:
        """undo.revert's result as the chat line (the window's language)."""
        lang, st, code, n = self.lang, res.get("status"), res.get("code"), res.get("n") or {}
        if st == "refused":
            if code == "edit_busy":
                held = activity.holder(session)
                return _t(lang, "rv_held", session=session, who=self.who(held)) if held else \
                    _t(lang, "rv_busy", session=session)
            return _t(lang, "rv_wrong_model" if code == "wrong_model" else "no_session", session=session)
        if st == "conflict":
            if code == "plan_changed":
                return _t(lang, "rv_changed")
            k = len(res.get("conflicts") or ())
            return _t(lang, "rv_conflict", n=k)
        if st == "failed" and not n.get("done"):
            return _t(lang, "rv_failed", why=" ".join(str(res.get("error") or res.get("text") or "?").split())[:300])
        k = n.get("done") or 0
        head = _t(lang, "rv_redid" if res.get("redo") else "rv_undid", n=k, s="s" * (k != 1)) if k else \
            _t(lang, "rv_none")
        return head + self._undo_bits({x: n.get(x) for x in ("approx", "already", "skipped", "failed", "blocked")},
                                      res.get("side"))

    def _undo_bits(self, counts: dict, side=None) -> str:
        lang = self.lang
        bits = [_t(lang, "rv_n_" + k, k=v) for k, v in counts.items() if v]
        if side:
            bits.append(_t(lang, "rv_side", names=", ".join(str(o.get("name")) for o in side[:3])))
        return _t(lang, "rv_bits", bits=_t(lang, "rv_sep").join(bits)) if bits else _t(lang, "rv_end")

    @_by_user()
    def _apply_point(self, manager, tab: dict, job: dict) -> None:
        """The window's "apply this point": write a loop row's or an optimization point's
        inputs into the model, run it once so the results match, and record where the model
        now is in ``results.state`` -- and, like the window's Run, the run in the session's
        ``sim`` (``source`` "apply_point"). Its chat line is the system's, not the user's: the
        run it made is newer than the values it wrote. Refused while another writer has the
        session."""
        lang, session = self.lang, tab["session"]
        why = self.writer(session, t=job.get("t"))
        if why is not None:
            self.message(tab, why, "system")
            return
        results = tab.get("results") or {}
        what, entries, why = _point(results, job.get("source") or "", job.get("row"), lang)
        app = manager.get_app(session)
        if why is None and app is None:
            why = _t(lang, "no_session", session=session)
        if why is None:                                   # its run would never return: nothing written
            why = main_tools.fault_refusal(manager, session)
        failed = []
        for e in entries if why is None else []:
            res = _put(manager, session, app, e["path"], e["value"], e.get("unit"))
            if not res.startswith("Set "):
                failed.append(f"{_short(e['path'])} ({' '.join(res.split())})")
        if why is None and len(failed) == len(entries):
            why = "; ".join(failed)
        if why is not None:
            self.message(tab, _t(lang, "ap_fail", what=what, why=why), "system")
            return
        self.beat()                                       # a run takes a while; the window watches the beat
        sess, t, started = self.session(session), time.perf_counter(), time.time()
        self.sim_fresh(manager, session)                  # (a run of an earlier load says nothing now)
        last = _last_run(sess.get("sim") or {})
        with _in_aspen("apply_point", tab, {"n": len(entries)}):
            run, detail = confirm_run(app, manager, session)
        # None: Aspen never got as far as its status (or was not asked: refused)
        seen = None if run == "refused" else probes.status_lines(app, since=t, read=False)
        msgs = probes.run_msgs(seen)
        warn = _sim_warn(probes.run_state(None, lines=seen)) if run == "warn" and seen is not None else {}
        _record_run(run, detail, time.perf_counter() - t, msgs, warn)
        self.refresh_results(app, session)
        end = time.time()
        status = sess.get("status") or {}
        errors = sorted(k for k, s in status.items() if s.get("level") == "error")
        sim = {"failed": run in ("error", "refused"), "warned": run == "warn", "outcome": run, "res": detail,
               "warns": sorted(k for k in status if k not in errors), **warn}
        rec = {"started": started, "reinit": False, "source": "apply_point", "errors": errors, "warns": sim["warns"],
               "msgs": [], **msgs, "outcome": run, "at": end, "text": _sim_text(lang, sim)[:1500],
               "load": _load_of(manager, session), **warn}
        sess["sim"] = dict(rec, status="done", finished=end) if seen is not None else {**rec, **last, "status": "error"}
        values = [{"path": e["path"], **dict(zip(("value", "unit"), _held(app, e["path"])))} for e in entries]
        text = _t(lang, "ap_ok", what=what, items=_items(values), run=_run_text(lang, run, detail))
        if failed:
            text += " " + _t(lang, "ap_fail", what=what, why="; ".join(failed))
        results["state"] = {"kind": "partial" if failed else "applied", "source": job.get("source"),
                            "row": job.get("row"), "values": values, "run": run, "t": time.time(), "text": text}
        self.message(tab, text, "system")    # not "user": a user line reads as a hand edit newer than the run
        self.jobs.append({"kind": "units", "tab": tab["id"]})
        self.reinspect(manager, tab)

    # -- the timeline as blocks (tools/replay.py); Aspen's drawing ------------
    def _to_blocks(self, tab: dict, ev: dict) -> None:
        """The window's "Turn into blocks" (event to_blocks {model, group | ids, req}): the change
        group's records, or the records picked, of ``model`` (journal.pick -- no COM) made into a
        program (replay.build, then normalize) in a new tab, as a tab_new's program is -- on the
        session holding that model, else this tab's --, made the active one, ``origin`` {"kind":
        "journal", "model", "group", "ids"}; a chat line there says what was skipped. Answered in
        this tab's session's ``to_blocks_req``: {"req", "status": done | none (nothing had a
        block: no tab, the window's toast) | failed, "tab", "n", "steps", "skipped": [{"code",
        "n"}], "missing", "text", "at"}."""
        lang, sess = self.lang, self.session(tab["session"])
        model = str(ev.get("model") or "")[:64] or (sess.get("model") or {}).get("id")
        raw = ev.get("ids") if isinstance(ev.get("ids"), list) else []
        ids = list(dict.fromkeys(str(x)[:64] for x in raw if isinstance(x, str) and x))[:_REVERT_MAX]
        group = str(ev.get("group") or "")[:64] or None
        req = {"req": str(ev.get("req") or "")[:40], "at": time.time()}
        got = journal.pick(model, ids=ids, group=group) if model and (ids or group) else \
            {"records": [], "heads": {}, "missing": ids}
        res = replay.build(got["records"], lang)
        try:
            prog = normalize(res["program"])
        except ValueError as exc:                         # (a record normalize refuses: nothing made)
            logger.warning("workbench: the timeline's program refused: %s", exc)
            sess["to_blocks_req"] = dict(req, status="failed", text=_t(lang, "error", exc=exc))
            return
        answer = dict(req, n=res["n"], steps=len(prog), skipped=replay.counts(res["skipped"]),
                      missing=len(got["missing"]))
        if not prog:
            sess["to_blocks_req"] = dict(answer, status="none", text=replay.say(lang, "tb_none"))
            return
        holds = {n: (x.get("model") or {}).get("id") for n, x in self.state["sessions"].items()}
        session = tab["session"] if holds.get(tab["session"]) in (None, model) else \
            next((n for n, m in holds.items() if m == model), tab["session"])
        head = got["heads"].get(group) if group else \
            next(iter(got["heads"].values()), None) if len(got["heads"]) == 1 else None
        new = self.new_tab(session, replay.title(lang, (head or {}).get("title"), res["n"]))
        new["origin"] = {"kind": "journal", "model": model, "group": group, "ids": ids[:50]}
        self.commit(new, prog, "journal")
        text = replay.text(lang, res, len(got["missing"]), group=bool(group))
        self.message(new, text, "system", kind="to_blocks", model=model, group=group)
        self.state["active"] = new["id"]
        sess["to_blocks_req"] = dict(answer, status="done", tab=new["id"], text=text)

    @_by_user()
    def _aspen_redraw(self, manager, tab: dict, job: dict) -> None:
        """The window's "Redraw Aspen's diagram": layout_flowsheet as the user's, in the
        user's scope, measured as the MCP tool is (intercept.measured: its backup, its patch
        record) after the Aspen-window check. It rewrites the model file and reopens Aspen,
        so not while a program or another writer holds the session; the flowsheet is read again
        and the AI's reminder to lay it out is dropped. Answered in the session's ``redraw_req``:
        {"req", "status": running, then done | failed | busy | closed, "text", "at"}, and a chat
        line."""
        lang, session = self.lang, tab["session"]
        sess, req = self.session(session), {"req": job.get("req") or "", "at": time.time()}
        arrange = {"blocks": job["blocks"], "ends": _stream_ends(sess)} if job.get("blocks") else None
        why, status = self.writer(session, t=job.get("t")), "busy"
        if why is not None and self.busy(session) is not None:
            why = replay.say(lang, "rd_busy", session=session)
        if why is None and manager.get_app(session) is None:
            why, status = _t(lang, "no_session", session=session), "closed"
        if why is not None:
            sess["redraw_req"] = dict(req, status=status, text=why)
            self.message(tab, why, "system")
            return
        self.external(manager, session, "aspen_redraw")
        sess["redraw_req"] = dict(req, status="running")
        self.save()                                       # the window shows it: a reopen holds this loop
        self.beat()
        try:
            with _in_aspen("layout_flowsheet", tab):
                args = {"session_name": session, **({"from_workbench": True} if arrange else {})}
                res, _ = intercept.measured(manager, recorder.current(), "layout_flowsheet", args,
                                            lambda: flowsheet_tools.layout_flowsheet(manager, session, arrange=arrange),
                                            actor="user", via="window")
        except Exception as exc:
            logger.warning("workbench: redrawing %s failed", session, exc_info=True)
            res = f"Layout failed: {_why(exc)}"
        ok = not probes.failed(res) and not (arrange and not str(res or "").startswith(("Flowsheet diagram arranged",
                                                                                         "Nothing to change")))
        if ok:
            intercept._LAYOUT.pop(session, None)          # the AI's "run layout_flowsheet" is done
        key = ("rd_placed" if ok else "rd_place_fail") if arrange else "rd_done" if ok else "rd_fail"
        text = replay.say(lang, key, res=" ".join(str(res or "").split())[:300], n=len((arrange or {}).get("blocks") or ()))
        sess["redraw_req"] = dict(req, status="done" if ok else "failed", text=text, at=time.time())
        self.message(tab, text, "system")
        self._job(manager, {"kind": "refresh", "session": session})
        self.beat()

    # -- runs ----------------------------------------------------------------
    def start_runs(self, manager) -> bool:
        changed = False
        for pend in list(self.pending):
            tab_id, dry = pend[0], pend[1]
            tab = self.tab(tab_id)
            if tab is None:
                self.pending.remove((tab_id, dry))
                self.auto_checks.discard(tab_id)
                self._drop_proposal(tab_id, "tab_closed")
                continue
            if self.stale(tab):                                  # its model is no longer there
                self.pending.remove((tab_id, dry))
                self.auto_checks.discard(tab_id)
                self._drop_proposal(tab_id, "stale")
                self.message(tab, _t(self.lang, "stale_run", tab=self.root_of(tab)["title"], session=tab["session"]),
                             "system")
                changed = True
                continue
            approving = not dry and tab.get("kind") == "proposal" and isinstance(tab.get("proposal"), dict)
            why = proposals.why_not(tab["proposal"], wb_plan.active(tab["program"])) if approving else None
            res = getattr(pend, "resume", None) if approving else None
            if why is None and res:                               # continuing a stopped run: still the same one
                ok = proposals.resumable(tab["proposal"], tab.get("program_rev"), wb_plan.active(tab["program"]))
                why = None if ok is not None and ok["at"] == res else "resume"
            if why is not None:                                  # this run cannot be the approval
                self.pending.remove((tab_id, dry))
                proposals.refused(tab["proposal"], why, time.time())
                self.message(tab, proposals.say(self.lang, "not_" + why), "system", kind="proposal",
                             what="refused", proposal=tab["proposal"]["id"])
                changed = True
                continue
            other = self.busy(tab["session"])
            held = activity.holder(tab["session"]) if other is None else None   # the AI's optimize
            if other is not None or held is not None:
                if dry and tab_id in self.auto_checks:           # busy after all -- the user checks it
                    self.pending.remove((tab_id, dry))
                    self.auto_checks.discard(tab_id)
                    continue
                if tab["run"].get("status") != "queued":
                    text = (_t(self.lang, "queued", other=other["title"], session=tab["session"]) if other else
                            _t(self.lang, "queued_held", who=self.who(held), session=tab["session"]))
                    tab["run"] = dict(_idle_run(), status="queued", dry_run=dry, log=[{
                        "t": time.time(), "level": "info", "id": None, "text": text}])
                    changed = True
                continue
            self.pending.remove((tab_id, dry))
            via = "auto" if dry and tab_id in self.auto_checks else "window"   # a proposal's own check
            self.auto_checks.discard(tab_id)
            (self.auto_runs.add if via == "auto" else self.auto_runs.discard)(tab_id)
            if not dry:                                          # Aspen-window edits before its records
                self.external(manager, tab["session"], "program")
            hold = None if dry else _hold(tab, "window")       # now: nothing may slip in before it starts
            prop = None if dry else self.proposed.pop(tab_id, None)   # the AI's proposal the user approved
            task = self.runs[tab_id] = asyncio.get_running_loop().create_task(
                execute(self, manager, tab, dry, via=via, hold=hold, proposed=prop["proposed"] if prop else None,
                        approve=(getattr(pend, "approve", None) or True) if approving else None,
                        mode=getattr(pend, "mode", "run"), resume=getattr(pend, "resume", None) if approving else None))
            if prop is not None:
                task.add_done_callback(functools.partial(self._proposal_ran, prop, tab))
            changed = True
        ended = False
        for tab_id in [k for k, task in self.runs.items() if task.done()]:
            del self.runs[tab_id]
            ended = True
            t = self.tab(tab_id)
            if t is not None:                                    # what the run changed, scanned now
                self.miss_touch(t["session"], 0, edit=not (t.get("run") or {}).get("dry_run"))
        if ended:                                                # a model's tab waiting for its runs
            changed |= self._closing_tick() | self._cap_all()
        return changed


_WS: Workspace | None = None


def _workspace() -> Workspace:
    global _WS
    if _WS is None:
        _WS = Workspace()
    return _WS


# ---------------------------------------------------------------------------
# Window process
# ---------------------------------------------------------------------------

def _window_cmd(ws: Workspace) -> list[str] | None:
    title = "Aspen Workbench"
    try:
        import webview  # noqa: F401  (a source checkout that already has pywebview)
        return [sys.executable, str(_WINDOW), str(ws.dir), title]
    except ImportError:
        pass
    uv = os.environ.get("UV") if os.path.isfile(os.environ.get("UV", "")) else shutil.which("uv")
    if not uv:
        return None
    py = f"{sys.version_info.major}.{sys.version_info.minor}"
    return [uv, "run", "-q", "--python", py, "--with", _PYWEBVIEW, "--no-project",
            "python", str(_WINDOW), str(ws.dir), title]


def _launch(ws: Workspace) -> str | None:
    cmd = _window_cmd(ws)
    if cmd is None:
        return "no Python with pywebview and no uv to provision one"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with open(ws.dir / "window.log", "ab") as log:       # the child keeps its own handle; ours closes
        ws.proc = subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                                   creationflags=flags)
    ws.closed = False
    return None


# ---------------------------------------------------------------------------
# Program execution
# ---------------------------------------------------------------------------

class _Stopped(Exception):
    pass


class _Refused(Exception):
    """The user's approval could not start (no restore point): nothing ran."""


def _fmt(v) -> str:
    return f"{v:.6g}" if isinstance(v, float) else "?" if v is None else str(v)


# -- where the model is left: the restore ledger and applying a result's point --------------

def _key(path: str) -> str:
    return str(path or "").strip().lower()             # Aspen finds paths case-insensitively


def _short(path: str) -> str:
    """A path as people say it: \\Data\\Blocks\\COL1\\Input\\BASIS_RR -> COL1 BASIS_RR."""
    parts = [p for p in str(path or "").split("\\") if p]
    if parts[:1] == ["Data"] and len(parts) > 2:
        parts = parts[2:]
    return " ".join(p for p in parts if p not in ("Input", "Output")) or str(path)


def _items(entries) -> str:
    return ", ".join(f"{_short(e['path'])} = {_fmt(e.get('value'))}" + (f" {e['unit']}" if e.get("unit") else "")
                     for e in entries)


def _same_held(value, unit, want, want_unit) -> bool:
    """Whether a field holding ``value`` [``unit``] holds what a set writes (``want`` [``want_unit``],
    the group card's conflict): the same number (or text), in the same unit or none asked for."""
    if want_unit and unit and str(want_unit).strip().lower() != str(unit).strip().lower():
        return False
    try:
        a, b = float(value), float(want)
        return abs(a - b) <= 1e-9 * max(1.0, abs(b))
    except (TypeError, ValueError):
        return str(value) == str(want)


def _held(app, path: str) -> tuple:
    """(value, unit) the model holds at ``path`` now; (None, None) when it cannot be read."""
    node = _node(app, path) if app is not None else None
    if node is None:
        return None, None
    try:
        return _plain(node.Value), (node.UnitString or None)
    except Exception:
        return None, None


def _put(manager, session: str, app, path: str, value, unit) -> str:
    """Write ``value`` to ``path``; ``unit`` goes along only when the field's unit now differs,
    and a whole number goes to an integer field as an int. Returns Aspen's answer ("Set ..."
    when it worked)."""
    cur, cur_unit = _held(app, path)
    if isinstance(cur, int) and not isinstance(cur, bool) and isinstance(value, float) and value.is_integer():
        value = int(value)
    try:
        return str(manager.set_node_value(session, path, value=value,
                                          unit=unit if unit and unit != cur_unit else None))
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def _run_text(lang: str, run: str, detail: str) -> str:
    """The re-run's outcome (tools._common_eval.confirm_run) in words; nothing when skipped."""
    return "" if run == "skipped" else _t(lang, "ms_run_" + run, detail=detail[:300] or "-")


def _simulate(ws: Workspace, manager, session: str, reinit: bool = False) -> dict:
    """One run of the model, as a program's run step and the window's Run simulation make it:
    Reinitialize first when asked, run, refresh the session's block marks and stream values,
    and judge it -- as the journal's run record does (probes.run_state, its record's when the
    journal is on): a run fails on errors, Aspen's or a block's; warnings alone leave it done; a
    line every clean run carries ("Properties estimation was never executed") is no warning.
    Returns {"ran" (Aspen ran to its end), "failed", "warned", "outcome" (error | warn | unknown:
    its run status unreadable | ok), "res" (Aspen's answer), "rec" (its run record's fields, or
    None: not recorded), "errors", "warns" (blocks), "msgs"
    (Aspen's run-status lines, probes.run_msgs; "nmsgs" when there were more), "first_warn" /
    "warns_more" (after a warn, probes.run_warnings), "reinit_error" (None, or why Reinitialize
    failed: no run)}."""
    out = {"ran": False, "failed": True, "warned": False, "outcome": "error", "res": "", "errors": [], "warns": [],
           "msgs": [], "reinit_error": None}
    rec = recorder.current()                              # the journal's: a run / reinit record
    if rec is not None:
        rec.settle()                                      # the writes before it, measured before it
    t = time.perf_counter()
    fp = runlog.before_run(manager, session, rec)         # before Reinitialize clears the results
    if fp is not None:
        rec.jt += time.perf_counter() - t
    if reinit:
        res = main_tools.reinit_simulation(manager, session)
        probes.run_entry(manager, session, res, op="reinit", scope=rec)
        if not res.endswith("reinitialized."):
            return dict(out, res=res, reinit_error=res)
    t = time.perf_counter()
    res = main_tools.run_simulation(manager, session)
    f = probes.run_entry(manager, session, res, secs=time.perf_counter() - t, scope=rec, since=t, fp=fp)
    app = manager.get_app(session)
    ran = "run completed" in res
    msgs = probes.run_msgs(probes.status_lines(app, since=t, read=False)) if ran and app is not None else {}
    lines = probes.said_lines(app, res, t) if ran else []
    st = probes.run_state(None, lines=lines) if lines is not None else {"status": "unknown"}
    if isinstance(f, dict) and f.get("status") in ("ok", "warn", "error", "unknown"):
        st = dict(st, status=f["status"], **_sim_warn(f))  # (the journal's record: its verdict)
    if app is not None:
        ws.refresh_results(app, session)
    status = ws.session(session).get("status") or {}
    errors = sorted(k for k, s in status.items() if s.get("level") == "error")
    failed = not ran or st["status"] == "error" or bool(errors)
    warned = not failed and st["status"] == "warn"
    outcome = "error" if failed else "warn" if warned else "unknown" if st["status"] == "unknown" else "ok"
    warn = _sim_warn(st) if warned else {}
    if not journal.enabled():                             # no run record tells diag_tick of it
        _note_run(manager, session, rec, "refused" if res.startswith("Cannot run") else
                  None if not ran else outcome, res, msgs, status, warn)
    return dict(out, ran=ran, failed=failed, warned=warned, outcome=outcome, res=res,
                errors=errors, warns=sorted(k for k in status if k not in errors), rec=f, **msgs, **warn)


_NOTED = [0]


def _note_run(manager, session: str, scope, status, res: str, msgs: dict, blocks: dict,
              warn: dict | None = None) -> None:
    """A run of the window or a program with the journal off: the record _diag_runs would have
    had (its id ``w<n>``: no journal to find it in), so the run still gets its card. ``warn``:
    its first_warn / warns_more (_sim_warn)."""
    if status is None:
        return
    try:
        model = manager.model_id(session)
    except Exception:
        model = None
    if not model:
        return
    _NOTED[0] += 1
    rec = {"id": f"w{_NOTED[0]}", "t": journal.now(), "op": "run", "status": status, "session": session,
           "actor": getattr(scope, "actor", None) or "user", "via": getattr(scope, "via", None) or "window",
           "blocks": {k: s.get("level") for k, s in (blocks or {}).items()}, **(msgs or {}), **(warn or {})}
    if status != "ok":
        rec["result"] = str(res or "")[:journal.RESULT_MAX]
    _diag_runs(model, [dict(rec, kind="change")])


_WARN_SAY = 90           # characters of a warning's words in a run's log line


def _sim_text(lang: str, sim: dict) -> str:
    """A run's outcome (_simulate) as its log line: a warning not on a block names Aspen's
    first warning (``first_warn``'s line)."""
    if sim["failed"]:
        return _t(lang, "run_warn", res=sim["res"][:4000])
    if sim["warned"]:
        if sim["warns"]:
            return _t(lang, "run_warned", blocks=", ".join(sim["warns"]))
        what = str((sim.get("first_warn") or {}).get("line") or "-")
        return _t(lang, "run_warned_global", what=what if len(what) <= _WARN_SAY else what[:_WARN_SAY - 1] + "…")
    if sim.get("outcome") == "unknown":
        return _t(lang, "run_unknown")
    return _t(lang, "run_ok")


def _beside_model(manager, session: str, path: str) -> str:
    """A model file's path; a relative one lands in the folder of the session's file on record."""
    path = str(path).strip()
    if not os.path.isabs(path):
        here = _model_file(manager, session)
        if here:
            path = os.path.join(os.path.dirname(here), path)
    return os.path.abspath(path)


def _save_refused(manager, session: str, path: str, lang: str) -> str | None:
    """Why a program's Save As to ``path`` is refused, or None: the target is an existing file that
    is not the session's own model and lies outside the model's folder (or the model has no file
    on record). Saves into the model's folder keep save_as's own backup of the file replaced."""
    if not os.path.isfile(path):
        return None
    norm = lambda p: os.path.normcase(os.path.abspath(p))  # noqa: E731
    here = _model_file(manager, session)
    if here and norm(path) == norm(here):
        return None
    folder = os.path.dirname(norm(here)) if here else None
    with contextlib.suppress(ValueError):                # (another drive: outside)
        if folder and os.path.commonpath([norm(path), folder]) == folder:
            return None
    return _t(lang, "save_outside", path=path)


def _nth(row) -> str:
    """A row index as people count it (from 1)."""
    return str(row + 1) if isinstance(row, int) and not isinstance(row, bool) else str(row)


def _point(results: dict, source: str, row, lang: str) -> tuple[str, list[dict], str | None]:
    """What apply_point writes: (a phrase naming the point, [{path, value, unit}], None), or
    (phrase, [], why not). ``row`` is an index into a sweep's or design spec's rows or an
    optimization's Pareto set, {"eval": index} an optimization's evaluation, or "best": the
    design spec's answer, the optimization's best compromise (else its best feasible
    evaluation, ranked as run_optimize's finish="best" ranks them)."""
    for o in results.get("opts") or []:
        if o.get("id") != source:
            continue
        label, pareto, evals = str(o.get("algorithm") or source), o.get("pareto") or [], o.get("evals") or []
        if row == "best":
            what = _t(lang, "ap_best", label=label)
            p = next((p for p in pareto if p.get("best")), None)
            if p is None:
                hit = best_point([(e.get("x") or [], e.get("f") or []) for e in evals if e.get("ok")],
                                 o.get("objectives") or [])
                p = {"x": hit[0]} if hit else None
            if p is None:
                return what, [], _t(lang, "ap_nobest")
        elif isinstance(row, dict) and isinstance(row.get("eval"), int) and 0 <= row["eval"] < len(evals):
            what, p = _t(lang, "ap_eval", n=row["eval"] + 1, label=label), evals[row["eval"]]
        elif isinstance(row, int) and not isinstance(row, bool) and 0 <= row < len(pareto):
            what, p = _t(lang, "ap_row", n=row + 1, label=label), pareto[row]
        else:
            n = _nth(row["eval"] if isinstance(row, dict) else row)
            return _t(lang, "ap_row", n=n, label=label), [], _t(lang, "ap_norow", row=n)
        entries = [{"path": v.get("path"), "value": x, "unit": v.get("unit")}
                   for v, x in zip(o.get("variables") or [], p.get("x") or [])]
        if not entries or any(e["value"] is None or not e["path"] for e in entries):
            return what, [], _t(lang, "ap_novalue")
        return what, entries, None
    for tb in results.get("tables") or []:
        if tb.get("id") != source or tb.get("kind") not in ("sweep", "seek") or not tb.get("path") or not tb.get("var"):
            continue
        label = str(tb.get("label") or source)
        label = _short(label) if label.startswith("\\") else label
        rows = tb.get("rows") or []
        if row == "best":
            what, value = _t(lang, "ap_best", label=label), tb.get("answer")
            if value is None:
                return what, [], _t(lang, "ap_nobest")
        elif isinstance(row, int) and not isinstance(row, bool) and 0 <= row < len(rows):
            what, value = _t(lang, "ap_row", n=row + 1, label=label), rows[row].get(tb["var"])
        else:
            n = _nth(row["eval"] if isinstance(row, dict) else row)
            return _t(lang, "ap_row", n=n, label=label), [], _t(lang, "ap_norow", row=n)
        if value is None:
            return what, [], _t(lang, "ap_novalue")
        return what, [{"path": tb["path"], "value": value, "unit": tb.get("unit")}], None
    return f"'{source}'", [], _t(lang, "ap_nosource", source=source)


class _Runner:
    def __init__(self, ws: Workspace, manager, tab: dict, dry_run: bool):
        self.ws, self.manager, self.tab, self.dry = ws, manager, tab, dry_run
        self.session = tab["session"]
        self.run = tab["run"]
        self.vars: dict[str, float | None] = {}
        self.units: dict[str, str | None] = {}           # variable -> unit of the path it was read from
        self.paths: dict[str, str] = {}                  # variable -> the path a read took it from (the window names it)
        self.tables: dict[str, dict] = {}
        self.funcs: dict = {}                            # the program's def statements, parsed
        self.procs: dict = {}                            # the program's proc statements by name
        self.depth = 0                                   # procedure calls in progress
        self.trees: dict = {}                            # expression text -> parsed tree
        # The restore ledger: every input a sweep, seek or optimize step writes, with its value
        # and unit before the first such step, in first-write order; put back when the program
        # ends (settle). ``kept``: the ones a step kept at its result, or a later set wrote.
        self.restore: dict[str, dict] = {}
        self.kept: dict[str, dict] = {}
        self.nrun = 0                                    # Aspen runs so far (runs and optimize steps)
        self.book: recorder.Scope | None = None          # the journal's scope of this run (execute)
        self.via = "window"                              # who started it: window | mcp (execute)
        self.agg = 0                                     # loops in progress (a flowsheet change refuses)
        self.shadow: dict | None = None                  # the offline check's problems by sid (a dry run)
        # the window's run of an AI proposal -- the user's approval (execute; _approval_*)
        self.approval: dict | None = None                # {"prop", "no_cp", "mode", "started", "info", ...}
        self.began: str | None = None                    # the begin record's call id (its end the same)
        self.bad: list = []                              # sids the pre-check refused
        self.error: str | None = None                    # what stopped the run with an error
        self.sim_out: str | None = None                  # the last simulation run: ok | warn | error | unknown
        self.done_n, self.wrote = 0, False               # top-level steps finished; one changing the model
        # stepping. mode step pauses before every step outside a loop; ``breaks`` (the tab's,
        # read as each step starts) pause a run the window started; ``level``: statements in
        # progress (0: a top-level one starts); ``nums``: sid -> its number as the check numbers
        # the program (a nested step shows its top-level one's, ``top_sid``); ``hold``: the run's
        # hold on the session (tools/activity.py), which says it is paused.
        self.mode = "run"
        self.breaks_on = False
        self.level = 0
        self.nums: dict = {}
        self.top_sid: str | None = None
        self.hold: int | None = None
        self.paused_st: dict | None = None               # the step it is paused before
        self.quiet = False                               # a step run again as a stopped approval continues
        # a your-turn step waiting for the user (the run's ``wait``); what the inspector wrote
        # to its field meanwhile (key -> (value, unit)): recorded already, not again at Done
        self.yt_user: dict = {}
        # the program's groups (wb_plan.groups, the check's numbers) -- ``g_at``: the
        # step a run by group pauses before -> its group; ``g_key``: a top-level sid -> its group's
        # key, the journal's ``gsid`` (only when the program has headings or runs by group);
        # ``g_why``: a top-level sid -> its heading's why, the reason of a step that gives none
        self.groups: list = []
        self.g_at: dict = {}
        self.g_key: dict = {}
        self.g_why: dict = {}
        # a top-level sid -> its group (the run's ``gcur``); the group's steps that
        # change the model (key -> [statement]: the card's live rows); the fields the user wrote
        # since the approval (key -> path: a row's conflict)
        self.g_of: dict = {}
        self.g_steps: dict = {}
        self.user_keys: dict = {}
        # the program's charts with a data line, by the loop it takes (_live_charts): drawn in
        # Results after each of the loop's passes, before their own step finalizes them (``live``:
        # the keys of the ones drawn so, not finalized yet)
        self.charts: dict[str, list[dict]] = {}
        self.live: set[str] = set()

    def t(self, key: str, **kw) -> str:
        return _t(self.ws.lang, key, **kw)

    def set_groups(self, program) -> None:
        """The program's groups for a real run: where a run by group pauses, each
        step's gsid and its heading's why; nothing with the feature off, or for a program without
        headings that does not run by group (its records as before)."""
        if not groups_on():
            return
        heads = any(st.get("do") == "group" and st.get("off") is not True for st in program or ())
        if not heads and self.mode != "group":
            return
        self.groups = wb_plan.groups(program, principle_keys())
        self.g_at = {g["at"]: g for g in self.groups if g["at"]} if self.mode == "group" else {}
        why_of = {st.get("id"): st.get("why") for st in program or () if st.get("do") == "group"}
        by_id = {st.get("id"): st for st in wb_plan.active(program) if isinstance(st, dict)}
        chg = wb_plan.changing(program)
        for g in self.groups:
            why = why_of.get(g["sid"]) if g["sid"] else None
            for sid in g["ids"] + g["heads"]:
                self.g_key[sid] = g["key"]
                self.g_of[sid] = g
                if why:
                    self.g_why[sid] = why
            # what the card's rows read, and what its main button says: a group that runs the
            # simulation "Apply and run", one with a sweep, seek or optimize "Apply and start"
            steps = [by_id[sid] for sid in g["ids"] if sid in chg and sid in by_id]
            self.g_steps[g["key"]] = steps
            kinds = {st.get("do") for st in steps}
            g["does"] = "start" if kinds & {"sweep", "seek", "optimize"} else "run" if "run" in kinds else None

    def stopped_at(self) -> str | None:
        """The step the run is stopped at for the window: paused before it, or a your-turn
        step waiting for the user; None while it runs."""
        p, w = self.run.get("paused"), self.run.get("wait")
        return p.get("at") if isinstance(p, dict) else w.get("sid") if isinstance(w, dict) else None

    def begin(self, manager, tab: dict) -> None:
        """The run's begin record (its end: execute), in the journal when it is on."""
        self.began = journal.new_id("c")
        if not _mark(manager, tab, self.book, "begin", self.began):
            self.began = None

    async def top(self, program: list[dict]) -> None:
        """The program's top-level steps, in order (``block``): an approved run counts them --
        which one is about to start, how many finished, whether one that changes the model did
        (proposals.stepped)."""
        a = self.approval
        info = (a or {}).get("info")
        if not info:
            await self.block(program)
            return
        prop, changing, quiet = a["prop"], set(info["changing"]), set(a.get("quiet") or ())
        if a.get("skip"):                                 # continuing a stopped approval, the user's edits (_resume_plan)
            key = "edits_skipped" if a.get("edits") else "resume_skipped"
            self.log(proposals.say(self.ws.lang, key, n=len(a["skip"]), ids=", ".join(a["skip"][:10])), "info")
        for st in program:
            step = st["do"] not in ("def", "proc")
            if step:
                proposals.stepped(prop, self.done_n, self.wrote, at=(info["n"].get(st["id"]), st["id"]))
            self.quiet = st["id"] in quiet                # (run again before the step it continues from: no pause)
            try:
                await self.step(st)
            finally:
                self.quiet = False
            if step:
                self.done_n += 1
                self.wrote |= st["id"] in changing
                if st["id"] in changing:
                    proposals.ran_step(prop, st)          # (a revision after a partial run: not run again)
                proposals.stepped(prop, self.done_n, self.wrote)

    def finish(self, st: dict) -> str:
        """Where a sweep, seek or optimize step leaves what it wrote: its finish, else the default."""
        choices = _FINISH[st["do"]]
        return st.get("finish") if st.get("finish") in choices else choices[0]

    def touch(self, st: dict, paths) -> None:
        """A sweep, seek or optimize step is about to write ``paths``: note each one's value
        before it, unless an earlier step already did (the earliest value wins)."""
        if self.dry:
            return
        app = self.manager.get_app(self.session)
        for path in paths:
            key = _key(path)
            self.kept.pop(key, None)                     # the latest writer decides
            if key not in self.restore:
                value, unit = _held(app, path)
                self.restore[key] = {"path": path, "value": value, "unit": unit, "sid": st["id"], "nrun": self.nrun}

    def done(self, st: dict, paths, why: str) -> None:
        """The step finished: unless it restores, its paths stay at its result (``why``)."""
        if self.dry or self.finish(st) == "restore":
            return
        for path in paths:
            self.restore.pop(_key(path), None)
            self.kept[_key(path)] = {"path": path, "sid": st["id"], "why": why}

    def written(self, st: dict, path: str) -> None:
        """A set wrote ``path``: the value it gave wins over a restore still pending."""
        key = _key(path)
        if key in self.restore or key in self.kept:
            self.restore.pop(key, None)
            self.kept[key] = {"path": path, "sid": st["id"], "why": "set"}

    def user_wrote(self, path: str) -> None:
        """The user wrote ``path`` in the inspector while this run was paused: the program's
        end keeps their value (off the restore ledger, kept as the user's), and the paused step's
        preview is read again (it may be the path it writes)."""
        key, st = _key(path), self.paused_st
        self.user_keys[key] = path                        # (a group's row on it says so)
        if key in self.restore or key in self.kept:
            self.restore.pop(key, None)
            self.kept[key] = {"path": path, "sid": st["id"] if st else None, "why": "user"}
        wait = self.run.get("wait")
        if isinstance(wait, dict) and _key(wait.get("path")) == key:     # journaled already
            self.yt_user[key] = _held(self.manager.get_app(self.session), path)
        paused = self.run.get("paused")
        if st is not None and isinstance(paused, dict):
            try:
                paused["next"] = self._next(st)
                if isinstance(paused.get("group"), dict):     # the group card's rows read again
                    self._group_rows(paused["group"])
            except Exception:
                logger.warning("workbench: the paused step's preview not read again", exc_info=True)

    def settle(self) -> dict | None:
        """Program end (done, stopped or failed): write back every input still on the ledger,
        in reverse order; run once if Aspen ran since the first of them was noted, so the
        results match the inputs; and say where the model is. None when no step changed any."""
        if self.dry or not (self.restore or self.kept):
            return None
        app = self.manager.get_app(self.session)
        restored, failed, rerun = [], [], False
        for e in reversed(list(self.restore.values())):
            entry = {"path": e["path"], "value": e["value"], "unit": e["unit"], "sid": e["sid"]}
            if app is None or e["value"] is None:
                failed.append(dict(entry, why="empty" if app is not None else "gone"))
                continue
            if _held(app, e["path"]) != (e["value"], e["unit"]):
                res = _put(self.manager, self.session, app, e["path"], e["value"], e["unit"])
                if not res.startswith("Set "):
                    failed.append(dict(entry, why=" ".join(res.split())))
                    continue
                rerun |= self.nrun > e["nrun"]
            restored.insert(0, entry)
        run, detail = "skipped", ""
        if rerun:
            self.ws.beat()
            t = time.perf_counter()
            run, detail = confirm_run(app, self.manager, self.session)
            seen = probes.status_lines(app, since=t, read=False) if run == "warn" else None
            _record_run(run, detail, time.perf_counter() - t,
                        warn=_sim_warn(probes.run_state(None, lines=seen)) if seen is not None else None)
            self.ws.refresh_results(app, self.session)
        kept = [{"path": k["path"], **dict(zip(("value", "unit"), _held(app, k["path"]))), "sid": k["sid"],
                 "why": k["why"]} for k in self.kept.values()]
        parts = [self.t("ms_restored", items=_items(restored))] if restored else []
        for why in ("sweep", "seek", "opt_last", "opt_best", "set", "user"):
            group = [k for k in kept if k["why"] == why]
            if group:
                parts.append(self.t("ms_" + why, items=_items(group)))
        empty = [f for f in failed if f["why"] == "empty"]
        if empty:
            parts.append(self.t("ms_empty", items=", ".join(_short(f["path"]) for f in empty)))
        if len(empty) < len(failed):
            parts.append(self.t("ms_failed", items="; ".join(f"{_short(f['path'])} ({f['why']})"
                                                             for f in failed if f["why"] != "empty")))
        if app is None:
            kind, parts = "unknown", [self.t("ms_gone")]
        elif failed:
            kind = "partial"
        else:
            kind = "mixed" if restored and kept else "restored" if restored else "kept"
        text = self.t("ms_head", parts="; ".join(parts)) + _run_text(self.ws.lang, run, detail)
        return {"kind": kind, "restored": restored, "kept": kept, "failed": failed, "run": run,
                "t": time.time(), "text": text}

    def calc(self, text) -> tuple[float | None, str | None]:
        """(value, None) or (None, why) for an expression over the program's variables."""
        text = str(text)
        if text not in self.trees:
            self.trees[text] = X.parse(text, self.funcs)
        try:
            return X.evaluate(self.trees[text], self.vars, self.funcs), None
        except X.NoValue as exc:
            return None, exc.why

    def record(self, st: dict, key: str, value, kind: str, label: str, keep=(), **meta) -> None:
        """One row of a loop's table: the loop variable, then every program variable, or
        the ones the loop's record list names (plus ``keep``, which the chart needs)."""
        if self.dry:
            return
        table = self.tables.get(st["id"])
        if table is None:
            table = {"id": st["id"], "kind": kind, "label": label, "path": st.get("path"), "var": key,
                     "unit": self.units.get(key), "columns": [key], "units": {key: self.units.get(key)},
                     "rows": [], **meta}
            if st["do"] in _FINISH and st.get("path"):   # a row's input can be written back (apply_point)
                table["apply"] = True
            self.tables[st["id"]] = table
            self.run["tables"].append(table)
        row = {key: value}
        wanted = st.get("record")
        if wanted:                                        # failed passes stay marked on the chart
            ok = ["last_run_ok"] if "last_run_ok" in self.vars else []
            names = list(dict.fromkeys(list(wanted) + list(keep) + ok))
        else:
            names = list(self.vars)
        for name in names:
            if name == key or name == "i":                # the loop variable leads; "i" only as a key
                continue
            val = self.vars.get(name)
            row[name] = val
            if name not in table["columns"]:
                table["columns"].append(name)
            if self.units.get(name):
                table["units"][name] = self.units[name]
            if self.paths.get(name):
                table.setdefault("paths", {})[name] = self.paths[name]
        table["rows"].append(row)
        for chart in self.charts.get(st["id"], ()):       # its charts gain the point now
            try:
                drawn = self._plot(chart, live=True)
            except Exception:
                logger.warning("workbench: a live chart was not drawn", exc_info=True)
                continue
            if drawn is not None:
                self._keep(chart, drawn)
                self.live.add(chart["id"])

    def unlive(self) -> None:
        """A run that ended done: a chart drawn while its loop ran whose own step never ran (a branch
        not taken) leaves Results; a stopped or failed run keeps it, the points it had."""
        for key in self.live:
            old = self.tables.pop(key, None)
            if old is not None and old in self.run["tables"]:
                self.run["tables"].remove(old)
        self.live.clear()

    def log(self, text: str, level: str = "info", sid: str | None = None) -> None:
        self.run["log"].append({"t": time.time(), "level": level, "text": text, "id": sid})
        self.run["log"] = self.run["log"][-_LOG_LINES:]

    async def step(self, st: dict) -> None:
        self.ws.drain()
        if self.tab["id"] in self.ws.stops:
            raise _Stopped()
        if self.level == 0:
            self.top_sid = st["id"]
        # The stepping gate: a step outside a loop -- at any depth of an if's branch or a called
        # procedure; a loop or an optimize is one step, run whole -- waits for the window when
        # stepping, or when it carries a breakpoint of a run the window started (a your-turn step
        # is a stop of its own)
        # (by group: before each group's first step that changes the model; a heading is no step)
        at_group = self.mode == "group" and self.level == 0 and st["id"] in self.g_at
        if not self.dry and self.agg == 0 and not self.quiet and st["do"] not in ("def", "proc", "group",
                                                                              *wb_plan.PAUSING) and (
                self.mode == "step" or at_group or (self.breaks_on and st["id"] in (self.tab.get("breaks") or ()))):
            await self.pause(st, "step" if self.mode == "step" else "group" if at_group else "break")
        if self.level == 0 and self.g_of and self.run.get("mode") == "group":
            g, cur = self.g_of.get(st["id"]), self.run.get("gcur")   # the group it applies now (the card)
            # (pausing by group, a group's heading and the technical steps ahead of its pause are not
            # "applying" it yet: the pause names it, so the card never says "Applying…" before it was pressed)
            ahead = g is not None and self.mode == "group" and g.get("at") is not None \
                and (self.nums.get(st["id"]) or 0) < (self.nums.get(g["at"]) or 0)
            if g is not None and not ahead and (not isinstance(cur, dict) or cur.get("n") != g["n"]):
                self.run["gcur"] = dict(self._group_head(g), t=round(time.time(), 3))
        self.run["step"] = st["id"]
        self.ws.save()
        await asyncio.sleep(0)
        book = self.book
        if book is None or recorder.current() is not book:    # (in a loop: its summary counts it)
            with self.blocking(st):
                await self._do(st)
            return
        # A statement is one call in the journal: its records written when it ends, marked
        # with its id -- the after side of a write is read then, before the next statement.
        was = book.call, book.extra.get("sid"), book.extra.get("gsid")
        book.call, book.extra["sid"] = journal.new_id("c"), st["id"]
        if self.level == 0 and st["id"] in self.g_key:    # the group it belongs to
            book.extra["gsid"] = self.g_key[st["id"]]
        # the note on the block is the reason of what it writes (reason_src "why": not the AI's
        # words); a top-level step without one takes its group heading's
        said = book.reason, getattr(book, "_told", False), book.extra.get("reason_src")
        why = st.get("why") or (self.g_why.get(st["id"]) if self.level == 0 else None)
        if why:
            book.reason, book._told, book.extra["reason_src"] = why, False, "why"
        t = time.perf_counter()
        try:
            if st["do"] in _LOOPS:                  # all it writes and runs: one summary record
                with recorder.Aggregate(do=st["do"], target=st.get("path")):
                    await self._do(st)
            else:
                with self.blocking(st, book.call):
                    await self._do(st)
        finally:
            book.flush(ms=(time.perf_counter() - t) * 1e3)
            self.ws.note_journal(self.manager, self.session)   # saved with the next step
            book.call = was[0]
            for k, v in (("sid", was[1]), ("gsid", was[2])):
                if v is None:
                    book.extra.pop(k, None)
                else:
                    book.extra[k] = v
            book.reason, book._told = said[0], said[1]
            if said[2] is None:
                book.extra.pop("reason_src", None)
            else:
                book.extra["reason_src"] = said[2]

    async def _do(self, st: dict) -> None:
        loop = st["do"] in _LOOPS                         # (a flowsheet change refuses inside one)
        self.agg += loop
        self.level += 1
        try:
            await getattr(self, "do_" + st["do"])(st)
        finally:
            self.agg -= loop
            self.level -= 1

    # -- stepping: paused before a step, the window's press goes on ------------
    async def pause(self, st: dict, why: str) -> None:
        """Wait before ``st`` for the window: the run's ``paused`` {at, n, depth, since, why (step |
        break), next (_next), loc, where} and the session's hold say so (the AI's refusal names the
        step: tools/activity.refusal) -- no timeout. Every _PAUSE_S the window's events are read:
        a stop raises _Stopped; a press goes on -- next: this step, then pause again (a Run paused
        at a breakpoint steps from there); cont: on to the end, pausing only at breakpoints. A
        window that is gone (closed, or its process dead twice running) stops the run too: nobody
        is left to press anything. An inspector edit posted before a press is written first (the
        sync loop; _EDIT_WAIT_S at most)."""
        ws, tid = self.ws, self.tab["id"]
        n = self.nums.get(self.top_sid)
        self.paused_st = st
        self.run["step"] = st["id"]
        paused = self.run["paused"] = {"at": st["id"], "n": n, "depth": self.level, "since": round(time.time(), 3),
                                       "why": why, "next": None, "loc": None, "where": None}
        if why == "group":                                # the group it is about to apply
            paused["group"] = self._group_head(self.g_at[st["id"]])
            self.run["gcur"] = dict(paused["group"], t=paused["since"])
        try:
            paused["next"] = self._next(st)
            paused["loc"], paused["where"] = self._where(st)
        except Exception:                                 # (a preview that cannot be read: paused all the same)
            logger.warning("workbench: the preview of step %s not read", st.get("id"), exc_info=True)
        if why == "group":
            try:                                          # its rows as the model holds them now
                self._group_rows(paused["group"])
            except Exception:
                logger.warning("workbench: the rows of group %s not read", paused["group"].get("n"), exc_info=True)
        if why == "break":
            self.log(self.t("step_break", n=n if n is not None else "?"), sid=st["id"])
        ws.refresh_paused(self.manager, self.session)     # (what the steps so far placed: drawn while it waits)
        pg = paused.get("group") if why == "group" else None    # (the AI's refusal names the group)
        activity.note(self.hold, paused=st["id"], paused_n=n, paused_since=activity.now(),
                      paused_group=f"{pg.get('n')} of {pg.get('of')}" if isinstance(pg, dict) else False)
        ws.save()
        gone, held = 0, None
        try:
            while True:
                ws.drain()
                presses = ws.steps.get(tid)
                if (presses or tid in ws.stops) and self._edits_pending():
                    held = held if held is not None else time.monotonic()
                    if time.monotonic() - held < _EDIT_WAIT_S:
                        await asyncio.sleep(_PAUSE_S / 4)
                        continue
                if tid in ws.stops:
                    raise _Stopped()
                if presses:
                    if presses.pop(0) == "cont":
                        self.mode = "run"
                        presses.clear()                   # (presses after it mean nothing now)
                    elif self.mode != "group":            # (at a breakpoint of a Run: stepping from here;
                        self.mode = "step"                # by group: this group, then the next one's pause)
                    if not presses:
                        ws.steps.pop(tid, None)
                    return
                gone = 0 if ws.window_alive() else gone + 1
                if gone >= (1 if ws.closed else 2):
                    self.log(self.t("step_closed"), "warn", st["id"])
                    raise _Stopped()
                await asyncio.sleep(_PAUSE_S)
        finally:
            self.run.pop("paused", None)
            self.paused_st = None
            if why == "group" and isinstance(self.run.get("gcur"), dict):
                self.run["gcur"]["t"] = round(time.time(), 3)   # (the group's application starts now)
            activity.note(self.hold, paused=False, paused_n=False, paused_since=False, paused_group=False)

    def _group_head(self, g: dict) -> dict:
        """A group as the window's group card has it: {n, of, sid, key, title, tpl,
        auto, why, principle, tech, tech_kinds, objs, does (run | start | None: the main button's
        words)} -- the run's ``gcur`` and its pause's ``paused.group`` (which adds rows, conflict)."""
        return {"of": len(self.groups), **{k: g[k] for k in (
            "n", "sid", "key", "title", "tpl", "auto", "why", "principle", "tech", "tech_kinds", "objs", "does") if k in g}}

    def _group_rows(self, pg: dict) -> None:
        """The group card's live rows into ``pg`` (paused.group): each step of the
        group that changes the model, at most GC_ROWS -- {n, id, kind, obj, path | what, cur (what
        the model holds there now), new (what it writes; an expression's value computed now)} --
        and ``conflict`` [{path, user, new}]: a field the group sets that the user wrote since the
        approval (the inspector, while the run waited), holding something else than the group
        writes. One read a row with a path, nothing else from Aspen."""
        app = self.manager.get_app(self.session)
        rows, conflict = [], []
        for st in self.g_steps.get(pg.get("key")) or ():
            if len(rows) >= GC_ROWS:
                break
            do, paths = st.get("do"), wb_plan._paths(st)
            row = {"n": self.nums.get(st["id"]), "id": st["id"], "kind": do}
            obj, desc = wb_plan.obj_of(st), wb_plan.what(st)
            if obj:
                row["obj"] = obj
            if desc is not None:
                row["what"] = desc
            if paths:
                row["path"] = wb_plan._cut(paths[0])
            new = wb_plan._new(st)
            if do == "set" and st.get("expr") not in (None, ""):
                v, _why = self.calc(st["expr"])
                new = {"value": v, "expr": wb_plan._cut(str(st["expr"])), "unit": wb_plan._unit(st)}
            if new is not None:
                row["new"] = new
            if do in wb_plan.PREVIEW and paths and app is not None:
                node = _node(app, paths[0])
                v, u = _held(app, paths[0]) if node is not None else (None, None)
                row["cur"] = None if node is None else {"value": wb_plan._cut(v), "unit": u}
                if do == "set" and node is not None and _key(paths[0]) in self.user_keys and isinstance(new, dict) \
                        and new.get("value") is not None and not _same_held(v, u, new["value"], new.get("unit")):
                    conflict.append({"path": row["path"], "user": row["cur"], "new": {"value": new["value"], "unit": new.get("unit")}})
            rows.append(row)
        pg["rows"], pg["conflict"] = rows, conflict

    def _edits_pending(self) -> bool:
        """An inspector edit of this session is queued and a sync loop runs to write it."""
        t = self.ws.task
        return t is not None and not t.done() and any(
            j.get("kind") == "set_value" and (self.ws.tab(j.get("tab")) or {}).get("session") == self.session
            for j in self.ws.jobs)

    def _next(self, st: dict) -> dict:
        """The step the run is paused before, as tab.check's rows have it (wb_plan.check / view)
        but read now, the steps before it done: ``cur`` what the model holds at its path, ``new``
        what it writes -- an expression's value computed from the program's variables --, a
        loop's range, a run's last outcome, an if's condition as it stands, a call's values; its
        problems as they are now (a field not enterable, the flowsheet check of a flowsheet
        statement against the flowsheet as it is)."""
        do, lang, app = st["do"], self.ws.lang, self.manager.get_app(self.session)
        row = {"id": st["id"], "n": self.nums.get(st["id"]), "depth": self.level, "kind": do}
        desc = wb_plan.what(st)
        if desc is not None:
            row["what"] = desc
        paths = wb_plan._paths(st)
        if paths:
            row["path"] = wb_plan._cut(paths[0])
        new, problems = wb_plan._new(st), []
        if do == "set" and st.get("expr") not in (None, ""):
            v, why = self.calc(st["expr"])
            new = {"value": v, "expr": wb_plan._cut(str(st["expr"])), "unit": wb_plan._unit(st)}
            if v is None:
                new["why"] = wb_plan._cut(str(why))
        elif do == "repeat":
            new = {"times": st.get("times")}
        elif do == "until":
            new = {"cond": wb_plan._cut(str(st.get("cond") or "")), "max": st.get("max") or 100}
        if new is not None:
            row["new"] = new
        if do in wb_plan.PREVIEW and paths:
            node = _node(app, paths[0]) if app is not None else None
            v, u = _held(app, paths[0]) if node is not None else (None, None)
            row["cur"] = None if node is None else {"value": wb_plan._cut(v), "unit": u}
        if do == "set" and st.get("path"):
            bad = _unwritable_as(app, st["path"], st.get("unit"), lang, st.get("basis")) if app is not None else None
            if bad:
                problems.append(wb_plan.note(bad[0], bad[1], texts=bad[2], help=bad[3], path=st["path"]))
        elif do == "run":
            row["last"] = self.sim_out or (self.ws.session(self.session).get("sim") or {}).get("outcome")
            row["reinit"] = bool(st.get("reinit"))
        elif do == "if":
            left = self._value(st.get("left") or {})
            op, right = st.get("op", ">"), self._right(st)
            row["cond"] = {"left": left, "op": op, "right": right,
                           "hit": None if left is None or right is None else bool(_OPS.get(op, _OPS[">"])(float(left), right))}
        elif do == "call":
            row["what"] = {"name": st.get("name"), "args": [self.calc(a)[0] for a in st.get("args") or []]}
        elif do in wb_plan.STRUCTURE and app is not None:
            fs = snapshot(self.manager, self.session)
            fs.update(taken_names(app))
            problems += wb_plan.check([st], fs, _PORT_TABLE, lang)["steps"][0].get("problems") or []
        if problems or do == "set" or do in wb_plan.STRUCTURE:
            row["problems"] = problems[:wb_plan.ROW_PROBLEMS]
        return row

    def _where(self, st: dict) -> tuple:
        """(loc, where): the step's place in Aspen's own window -- its first path's location
        (aspen_labels.loc, the block's type from the flowsheet) and that as one line -- or, for a
        step without a path, the pane it acts in (_STEP_WHERE); (None, None) for a step only the
        workbench does (a calc, a log...)."""
        paths = wb_plan._paths(st)
        if paths:
            fs = self.ws.session(self.session).get("flowsheet") or {}
            types = {b.get("name"): b.get("type") for b in fs.get("blocks") or [] if b.get("name")}
            loc = aspen_labels.labels([paths[0]], types).get(paths[0])
            return loc, aspen_labels.text(loc, "full", self.ws.lang) if loc else None
        pair = _STEP_WHERE.get(st["do"])
        return None, (pair[1] if self.ws.lang == "zh" else pair[0]) if pair else None

    @contextlib.contextmanager
    def blocking(self, st: dict, call: str | None = None):
        """A statement that keeps the event loop waiting (run, save, optimize, pinch) is the
        program's call in flight while it runs (tools/activity.py: the window's heartbeat)."""
        kind = None if self.dry else _BLOCKING.get(st["do"])
        if kind is None:
            yield
            return
        do = st["do"]
        target = ({"file": re.split(r"[\\/]", str(st["path"]))[-1]} if do == "save" and st.get("path")
                  else {"algorithm": st.get("algorithm"), "n": len(st.get("variables") or [])} if do == "optimize"
                  else None)
        act = activity.begin("program", do, session=self.session, phase=kind, target=target,
                             call=call, via=self.via, tab=self.tab["id"], sid=st["id"])
        status = "error"
        try:
            yield
            status = "ok"
        finally:
            activity.end(act, status)

    def restore_point(self, st: dict) -> None:
        """A restore point of the model before an optimize step (intercept.restore_point: a
        record of its own, the step's sid, a call id of its own -- a change record of the step's
        call would end the optimization's begin record) -- one per program run, which is one
        change group, so an optimize in a loop makes one before its first pass; none made, the
        run log says why."""
        book = self.book
        rp = intercept.restore_point(self.manager, self.session, "before-optimize",
                                     group=book.group if book is not None else None, actor="program",
                                     via=self.via, tool="optimize", call=journal.new_id("c"), sid=st["id"])
        if rp.get("why") in ("slow", "failed") and rp.get("status") in ("skipped", "failed"):
            why = self.t("cp_why_slow", est=_dur(self.ws.lang, rp.get("est_s"))) if rp["why"] == "slow" \
                else self.t("cp_why_failed")
            self.log(self.t("opt_nocp", why=why), "info", st["id"])

    def aggregate(self, do: str, **kw):
        """The journal's scope of an optimize step or the restore: one record for all it
        writes and runs (joining the loop it is in). Nothing on a check (dry run)."""
        return contextlib.nullcontext() if self.book is None else recorder.Aggregate(do=do, **kw)

    async def block(self, program: list[dict]) -> None:
        for st in program:
            await self.step(st)

    def _value(self, left: dict):
        if left.get("var") is not None:
            return self.vars.get(left["var"])
        if left.get("expr") not in (None, ""):
            return self.calc(left["expr"])[0]
        return read_value(self.manager, self.session, left.get("path", ""))

    def _unit_of(self, path: str) -> str | None:
        node = _node(self.manager.get_app(self.session), path or "")
        return _unit_info(node)["unit"] if node is not None else None

    def _write(self, path: str, value, unit: str | None, basis: str | None = None) -> str:
        res = self.manager.set_node_value(self.session, path, value=value, unit=unit, basis=basis or None)
        if not res.startswith("Set "):
            raise RuntimeError(self.t("set_fail", res=res))
        return res

    # -- statements ----------------------------------------------------------
    async def do_set(self, st):
        path, value, unit, expr = st.get("path"), st.get("value"), st.get("unit"), st.get("expr")
        shown = f" {unit}" if unit else ""
        if expr not in (None, ""):
            value, why = self.calc(expr)
            if self.dry:
                self.log(self.t("set_dry", path=path, value=f"{_fmt(value)} (= {expr})", unit=shown), sid=st["id"])
                return
            if value is None:
                raise RuntimeError(self.t("expr_none", path=path, why=why, expr=expr))
            self.log(f"{self._write(path, value, unit, st.get('basis'))}  (= {expr})", sid=st["id"])
            self.written(st, path)
            return
        if self.dry:
            self.log(self.t("set_dry", path=path, value=value, unit=shown), sid=st["id"])
            return
        self.log(self._write(path, value, unit, st.get("basis")), sid=st["id"])
        self.written(st, path)

    async def do_run(self, st):
        if self.dry:
            self.log(self.t("run_dry_reinit" if st.get("reinit") else "run_dry"), sid=st["id"])
            return
        sim = _simulate(self.ws, self.manager, self.session, bool(st.get("reinit")))
        if sim["reinit_error"] is not None:
            raise RuntimeError(self.t("reinit_fail", res=sim["reinit_error"]))
        self.nrun += 1
        self.vars["last_run_ok"] = 1.0 if sim["outcome"] in ("ok", "warn") else 0.0   # (unknown: not known ok)
        self.sim_out = sim["outcome"]
        self.log(_sim_text(self.ws.lang, sim), "info" if sim["outcome"] == "ok" else "warn", st["id"])

    async def do_calc(self, st):
        name, expr = st.get("as") or "value", st.get("expr")
        v, why = self.calc(expr)
        self.vars[name] = v
        self.units[name] = st.get("unit") or None
        unit = f" {st['unit']}" if st.get("unit") and v is not None else ""
        if v is None:
            self.log(self.t("calc_none", name=name, why=why, expr=expr), "warn", st["id"])
        else:
            self.log(self.t("calc", name=name, value=_fmt(v), unit=unit, expr=expr), sid=st["id"])

    async def do_def(self, st):
        self.log(self.t("def", name=st.get("name"), params=", ".join(st.get("params") or []),
                        expr=st.get("expr")), sid=st["id"])

    async def do_until(self, st):
        cond, most = st.get("cond"), max(1, int(st.get("max") or 100))
        n = 0
        while True:
            held = bool(self.calc(cond)[0])
            if held or n >= (1 if self.dry else most):
                break
            n += 1
            self.vars["i"] = float(n)
            await self.block(st.get("body") or [])
            self.record(st, "i", float(n), "until", cond)
        if self.dry:
            return
        if held:
            self.log(self.t("until_done", n=n, cond=cond), sid=st["id"])
        else:
            self.log(self.t("until_max", n=n, cond=cond), "warn", st["id"])

    async def do_seek(self, st):
        """Design spec: bracketed false position (Illinois), bisecting past failed runs."""
        path, unit = st.get("path"), st.get("unit")
        lo, hi = float(st.get("lower", 0)), float(st.get("upper", 0))
        measure, target = st.get("measure"), float(st.get("target", 0))
        tol = float(st.get("tol") or 1e-6 * max(1.0, abs(target)))
        most, name = max(3, int(st.get("max") or 30)), st.get("as") or "seek_value"
        self.units[name] = shown = unit or self._unit_of(path)
        u = f" {shown}" if shown else ""
        self.log(self.t("seek_start", path=path, lo=f"{lo:g}", hi=f"{hi:g}", unit=u, measure=measure,
                        target=f"{target:g}"), sid=st["id"])
        if self.dry:
            self.vars[name] = lo
            await self.block(st.get("body") or [])
            return
        self.touch(st, [path])
        runs, last = 0, None
        plain = X.is_name(str(measure))

        async def f(x):
            nonlocal runs, last
            runs, last = runs + 1, x
            self.vars[name] = x
            self._write(path, x, unit)
            await self.block(st.get("body") or [])
            m, why = self.calc(measure)
            if not plain:
                self.vars["measure"] = m
            col = measure if plain else "measure"
            self.record(st, name, x, "seek", f"{measure} = {target:g}", keep=[col], measure=col, target=target)
            self.log(self.t("seek_step", name=name, x=_fmt(x), measure=measure, m=_fmt(m)), sid=st["id"])
            return (None if m is None else m - target), why

        def fail(x, why):
            return RuntimeError(self.t("seek_noval", measure=measure, path=path, x=_fmt(x), why=why))

        fa, why = await f(lo)
        if fa is None:
            raise fail(lo, why)
        best = (lo, fa)
        if abs(fa) > tol:
            fb, why = await f(hi)
            if fb is None:
                raise fail(hi, why)
            if abs(fb) < abs(fa):
                best = (hi, fb)
            if abs(fb) > tol and fa * fb > 0:
                raise RuntimeError(self.t("seek_nobracket", measure=measure, target=f"{target:g}",
                                          lo=f"{lo:g}", hi=f"{hi:g}", mlo=_fmt(fa + target),
                                          mhi=_fmt(fb + target)))
            a, b = lo, hi
            while abs(best[1]) > tol and runs < most and abs(b - a) > 1e-12 * max(1.0, abs(b)):
                x = b - fb * (b - a) / (fb - fa) if fb != fa else (a + b) / 2
                if not min(a, b) < x < max(a, b):
                    x = (a + b) / 2
                fx, why = await f(x)
                if fx is None:                     # a failed run: step to the midpoint instead
                    x = (a + b) / 2
                    fx, why = await f(x)
                    if fx is None:
                        raise fail(x, why)
                if abs(fx) < abs(best[1]):
                    best = (x, fx)
                if fx * fb < 0:
                    a, fa = b, fb
                else:
                    fa /= 2                        # Illinois: keep the stale end from stalling
                b, fb = x, fx
        x, fx = best
        if last != x:                              # leave the model at the answer
            await f(x)
        self.vars[name] = x
        if st["id"] in self.tables:
            self.tables[st["id"]]["answer"] = x
        met = abs(fx) <= tol
        self.log(self.t("seek_done" if met else "seek_max", path=path, x=_fmt(x), unit=u, n=runs,
                        measure=measure, m=_fmt(fx + target)), "info" if met else "warn", st["id"])
        self.done(st, [path], "seek")

    async def do_read(self, st):
        v = read_value(self.manager, self.session, st.get("path", ""))
        name = st.get("as") or "value"
        self.vars[name] = v
        self.units[name] = unit = self._unit_of(st.get("path"))
        if st.get("path"):
            self.paths[name] = st["path"]
        self.log(self.t("read_dry" if self.dry else "read", name=name, value=_fmt(v),
                        unit=f" {unit}" if unit and v is not None else "", path=st.get("path")),
                 "info" if v is not None else "warn", st["id"])

    # -- your turn: the run waits for the user to set a field --------------------
    async def do_yourturn(self, st):
        """Stop and wait for the user to set ``path`` -- in the inspector or in Aspen's own window
        -- and press Done: the run's ``wait`` says so, and the session's hold says waiting_user
        (the AI's changes are refused at once, the user's pass). No timeout; a Stop ends it, a
        closed window does not (the user may set it in Aspen and come back). Done reads the field
        (_yt_press): unchanged -> ``msg`` unchanged, and a Done with force goes on as it is;
        ``expect`` not met -> ``msg`` expect, ``tries`` + 1 (after YT_TRIES, with an ``answer``,
        ``can_answer``: yourturn_answer has the program write it); met -> the value is the
        user's, journaled once (_yt_record) and held by the variable ``as`` (yourturn_value). A
        check only says what it would ask. Never in a loop (the check refuses it first)."""
        sid, path = st["id"], st["path"]
        fs = self.ws.session(self.session).get("flowsheet") or {}
        label = _label_of(fs, path, self.ws.lang)
        if self.dry:
            self.log(self.t("yt_dry", label=label, hint=st.get("hint") or ""), sid=sid)
            node = _node(self.manager.get_app(self.session), path)
            if node is not None and _enterable(node) is False:
                self.log(self.t("yt_off", label=label), "warn", sid)
            return
        if self.agg:
            raise RuntimeError(self.t("yt_loop", label=label))
        app = self.manager.get_app(self.session)
        node = _node(app, path) if app is not None else None
        if node is None:
            raise RuntimeError(self.t("not_found", path=path))
        v0, u0 = _held(app, path)
        loc, where = self._where(st)
        wait = {"sid": sid, "n": self.nums.get(self.top_sid), "path": path, "label": label, "hint": st.get("hint"),
                "before": {"value": v0, "unit": u0}, "t": round(time.time(), 3), "tries": 0, "msg": None,
                "has_answer": st.get("answer") is not None, "can_answer": False, "loc": loc, "where": where,
                "enterable": _enterable(node)}
        if st.get("expect"):
            wait["expect"] = {"op": st["expect"]["op"], "value": self._yt_want(st["expect"])[0]}
        self.run["wait"], self.run["step"], self.paused_st, self.yt_user = wait, sid, st, {}
        self.log(self.t("yt_wait", label=label, hint=st.get("hint") or ""), sid=sid)
        activity.note(self.hold, waiting_user=True, wait_sid=sid, wait_n=wait["n"], wait_since=activity.now(),
                      wait_label=_label_of(fs, path, "en"))
        ws, tid = self.ws, self.tab["id"]
        ws.turns.pop(tid, None)                           # (a press left from before: not this step's)
        ws.save()
        held = None
        try:
            while True:
                ws.drain()
                if tid in ws.stops:
                    raise _Stopped()
                presses = ws.turns.get(tid)
                if presses and self._edits_pending():     # an inspector edit posted before Done: written first
                    held = held if held is not None else time.monotonic()
                    if time.monotonic() - held < _EDIT_WAIT_S:
                        await asyncio.sleep(_PAUSE_S / 4)
                        continue
                held = None
                if presses:
                    press = presses.pop(0)
                    if not presses:
                        ws.turns.pop(tid, None)
                    if press.get("sid") in (None, sid) and self._yt_press(st, wait, press, label):
                        return
                    ws.save()
                    continue
                await asyncio.sleep(_PAUSE_S)
        finally:
            self.run.pop("wait", None)
            self.paused_st, self.yt_user = None, {}
            activity.note(self.hold, waiting_user=False, wait_sid=False, wait_n=False, wait_since=False,
                          wait_label=False)

    def _yt_want(self, exp: dict) -> tuple:
        """(the value a your-turn step's ``expect`` compares with, the variable it names or None):
        "{name}" is that variable's value now (None: it has none yet)."""
        v = exp.get("value")
        m = _VAR_REF.fullmatch(v.strip()) if isinstance(v, str) else None
        return (self.vars.get(m.group(1)), m.group(1)) if m else (v, None)

    @staticmethod
    def _yt_ok(v, op: str, want) -> bool:
        """``v`` op ``want``: as numbers when both are; else == / != compare the text (an option
        code), any case; another op on a text never holds."""
        a, b = _num(v), _num(want)
        if a is not None and b is not None:
            return bool(_OPS.get(op, _OPS[">="])(a, b))
        if op in ("==", "!="):
            return (str("" if v is None else v).strip().upper() == str(want).strip().upper()) == (op == "==")
        return False

    def _yt_press(self, st: dict, wait: dict, press: dict, label: str) -> bool:
        """One press while a your-turn step waits (the run's ``wait`` updated): True when the run
        goes on -- the value passed (or the answer was written) and the variable holds it."""
        sid, path, name = st["id"], st["path"], st.get("as") or _YT_VAR
        app = self.manager.get_app(self.session)
        if app is None:                                  # (Aspen gone: nothing to read or write)
            raise RuntimeError(self.t("no_session", session=self.session))
        if press.get("kind") == "answer":
            if not wait.get("can_answer"):
                return False
            value = st["answer"]
            num = _num(value) if isinstance(value, str) else None
            value = num if num is not None else value
            try:
                res = self._write(path, value, st.get("unit"))
            except RuntimeError as exc:                  # (the answer does not take: the user is still asked)
                self.log(str(exc), "error", sid)
                return False
            self.written(st, path)
            v, u = _held(app, path)
            self.vars[name], self.units[name] = _num(v), u
            self.log(self.t("yt_answer", label=label, value=_fmt(v) + (f" {u}" if u else "")) + f"  ({res})",
                     sid=sid)
            return True
        v, u = _held(app, path)
        wait["now"] = {"value": v, "unit": u}
        before = wait["before"]
        same = (v, u) == (before.get("value"), before.get("unit"))
        if same and not press.get("force"):
            wait["msg"] = "unchanged"
            return False
        exp = st.get("expect")
        if exp:
            want, var = self._yt_want(exp)
            if want is None and var:                     # its variable has no value: nothing to check against
                self.log(self.t("yt_novar", label=label, name=var), "warn", sid)
            elif not self._yt_ok(v, exp["op"], want):
                wait.update(tries=wait["tries"] + 1, msg="expect")
                wait["can_answer"] = bool(wait.get("has_answer")) and wait["tries"] >= YT_TRIES
                self.log(self.t("yt_retry", label=label, value=_fmt(v) + (f" {u}" if u else ""), op=exp["op"],
                                want=_fmt(want)), "warn", sid)
                return False
        wait["msg"] = None
        key = _key(path)
        if not same:
            self._yt_record(st, wait, v, u)
            if key in self.restore or key in self.kept:  # the program's end keeps the user's value
                self.restore.pop(key, None)
                self.kept[key] = {"path": path, "sid": sid, "why": "user"}
        self.vars[name], self.units[name] = _num(v), u
        shown = _fmt(v) + (f" {u}" if u else "")
        self.log(self.t("yt_kept", label=label, value=shown) if same else
                 self.t("yt_done", label=label, value=shown, old=_fmt(before.get("value"))), sid=sid)
        return True

    def _yt_record(self, st: dict, wait: dict, v, u) -> None:
        """The user's value at Done, journaled as theirs -- op value, actor user, via yourturn, in
        the run's change group with the step's sid, before as the step found it -- unless the
        inspector's record of it during the wait already ends at this value (then it says so
        already). The Aspen-window watch learns it from the record (journal.listen): not reported again as an
        edit made in Aspen's window. Nothing with the journal off."""
        book = self.book
        if book is None or not book.on:
            return
        seen = self.yt_user.get(_key(st["path"]))
        if seen is not None and tuple(seen) == (v, u):
            return
        b = {"value": seen[0], "unit": seen[1]} if seen is not None else wait["before"]
        with self.ws.as_user(self.manager, self.tab, "yourturn", group=book.group, call=journal.new_id("c"),
                             sid=st["id"]) as s:
            s.add("value", target=journal.label(st["path"]), status="changed",
                  before={k: x for k, x in b.items() if x is not None},
                  after={k: x for k, x in (("value", v), ("unit", u)) if x is not None})

    async def do_log(self, st):
        missing: list[str] = []

        def fill(m):
            name = m.group(1)
            if name in self.vars and self.vars[name] is not None:
                return _fmt(self.vars[name])
            missing.append(name)
            return "?"

        self.log(_VAR_REF.sub(fill, str(st.get("text", ""))), sid=st["id"])
        if missing:
            self.log(self.t("var_missing", names=", ".join(dict.fromkeys(missing))), "warn", st["id"])

    async def do_table(self, st):
        """A results table: a row per name in rows, "{row}" standing for it in the columns; or a
        loop's results (``loop``): a row per point, the loop's variable then ``vars`` (none: all)."""
        if st.get("loop"):
            self._loop_table(st)
            return
        cols, rows = st.get("columns") or [], st.get("rows") or []
        title = st.get("title") or self.t("table_title")
        key = st.get("row_label") or self.t("row")
        labels: list[str] = []
        for c in cols:                                    # unique headings, never the row column's
            base = str(c.get("label") or c.get("path") or c.get("expr") or "?")
            lab, n = base, 2
            while lab in labels or (rows and lab == key):
                lab, n = f"{base} ({n})", n + 1
            labels.append(lab)
        table = {"id": st["id"], "kind": "table", "label": title, "var": key if rows else None,
                 "columns": ([key] if rows else []) + labels, "units": {}, "rows": []}
        empty = 0
        for r in rows or [None]:
            row = {key: r} if rows else {}
            for c, lab in zip(cols, labels):
                if c.get("path"):
                    path = str(c["path"]) if r is None else str(c["path"]).replace(_ROW, r)
                    v, unit = read_value(self.manager, self.session, path), self._unit_of(path)
                else:
                    v, _ = self.calc(str(c.get("expr")) if r is None else str(c.get("expr")).replace(_ROW, r))
                    unit = c.get("unit") or None
                row[lab] = v
                empty += v is None
                if unit and v is not None:
                    table["units"].setdefault(lab, unit)
            table["rows"].append(row)
        self.log(self.t("table", title=title, n=len(table["rows"]), m=len(cols),
                        empty=self.t("table_empty", k=empty) if empty else "")
                 + (self.t("table_dry") if self.dry else ""), "warn" if empty else "info", st["id"])
        if not self.dry:
            self._keep(st, table)

    def _at(self, line: dict, x, var: str):
        """A chart line's y at x: a data line's point there, a formula computed there (None: none)."""
        if line.get("data") or not line.get("expr"):
            return next((p[1] for p in line["pts"] if p[0] == x), None)
        had, before = var in self.vars, self.vars.get(var)
        self.vars[var] = x
        try:
            return self.calc(line["expr"])[0]
        finally:
            if had:
                self.vars[var] = before
            else:
                self.vars.pop(var, None)

    def _loop_table(self, st: dict) -> None:
        title, src = st.get("title") or self.t("table_title"), self.tables.get(str(st["loop"]))
        if self.dry:                                      # (a check records no loop rows)
            self.log(self.t("from_loop_dry", title=title), sid=st["id"])
            return
        if src is None:
            self.log(self.t("table_noloop", title=title), "warn", st["id"])
            return
        key = src["var"]
        want = [c for c in st.get("vars") or [c for c in src["columns"] if c not in (key, "last_run_ok")] if c != key]
        cols = [key] + list(dict.fromkeys(want))
        rows = [{c: r.get(c) for c in cols} for r in src["rows"]]
        empty = sum(1 for r in rows for c in cols if r[c] is None)
        self.log(self.t("table", title=title, n=len(rows), m=len(cols),
                        empty=self.t("table_empty", k=empty) if empty else ""), "warn" if empty else "info", st["id"])
        if not self.dry:
            self._keep(st, {"id": st["id"], "kind": "table", "label": title, "var": key, "path": src.get("path"),
                            "columns": cols, "units": {c: u for c, u in (src.get("units") or {}).items() if c in cols and u},
                            "paths": {c: q for c, q in (src.get("paths") or {}).items() if c in cols},
                            "rows": rows})

    def _keep(self, st: dict, table: dict, part: str = "") -> None:
        """Put a table or plot in Results; run again (in a loop), the latest wins. A
        statement with several results names each ``part``."""
        key = st["id"] + (":" + part if part else "")
        old = self.tables.get(key)
        self.live.discard(key)
        self.tables[key] = table
        if old is not None and old in self.run["tables"]:     # (in its place: Results does not reorder)
            self.run["tables"][self.run["tables"].index(old)] = table
        else:
            self.run["tables"].append(table)

    async def do_plot(self, st):
        drawn = self._plot(st)
        if drawn is not None:
            self._keep(st, drawn)

    def _plot(self, st, live: bool = False) -> dict | None:
        """A chart: data lines -- a loop's results, one line per y column against its x column (the
        loop's own variable unless ``xcol``) -- and curves y = expr(x) sampled over the x range, plus
        vertical lines at x. With no x range given it is the data lines' x extent. ``live``: drawn
        after a pass of a loop it takes -- from the rows so far, saying nothing; None when it
        has nothing to draw yet."""
        title, var = st.get("title") or self.t("plot_title"), st.get("var") or "x"
        series = st.get("series") or []
        lines, vlines, empty, units, paths = [], [], 0, {}, {}
        xname, xpath = None, None
        num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)  # noqa: E731
        if self.dry and any(s.get("loop") not in (None, "") for s in series):   # (a check records no loop rows)
            self.log(self.t("from_loop_dry", title=title), sid=st["id"])
            return None
        for s in series:
            if s.get("loop") in (None, ""):
                continue
            src, ycols = self.tables.get(str(s["loop"])), list(s.get("ycols") or [])
            if src is None:
                if live:
                    continue
                self.log(self.t("plot_noloop", title=title, label=s.get("label") or ", ".join(ycols)), "warn", st["id"])
                continue
            xc = s.get("xcol") or src["var"]
            if xname is None:
                xname, xpath = xc, src.get("path") if xc == src["var"] else None
            for yc in [c for c in ycols if c not in src["columns"] and not live]:
                self.log(self.t("plot_nocol", title=title, col=yc), "warn", st["id"])
            for k, yc in enumerate(ycols):
                pts = sorted(([r.get(xc), r.get(yc)] for r in src["rows"] if num(r.get(xc))), key=lambda p: p[0])
                empty += sum(1 for p in pts if not num(p[1]))
                label = s.get("label") or yc
                if s.get("label") and len(ycols) > 1:
                    label = f"{s['label']} · {yc}"
                line = {"label": label, "pts": pts, "color": s.get("color") if k == 0 else None, "dash": bool(s.get("dash")),
                        "data": True}
                ypath = (src.get("paths") or {}).get(yc)
                if ypath:                                 # (named by the window in words, the label kept as given)
                    line["path"] = ypath
                    if not s.get("label"):
                        paths[label] = ypath
                lines.append(line)
                for c, as_ in ((xc, xc), (yc, label)):
                    if (src.get("units") or {}).get(c):
                        units[as_] = src["units"][c]
        xs_data = [p[0] for ln in lines for p in ln["pts"]]
        given = [st.get(k) not in (None, "") for k in ("x_from", "x_to")]
        lo, why = self.calc(st.get("x_from")) if given[0] else ((min(xs_data), None) if xs_data else (None, None))
        hi, why2 = self.calc(st.get("x_to")) if given[1] else ((max(xs_data), None) if xs_data else (None, None))
        formulas = [s for s in series if s.get("loop") in (None, "")]
        if live and not xs_data:
            return None
        if (lo is None or hi is None) and (formulas or not lines):
            if not live:
                self.log(self.t("plot_range", title=title, why=why or why2 or "—"), "warn", st["id"])
            return None
        yr = [self.calc(st[k])[0] if st.get(k) not in (None, "") else None for k in ("y_from", "y_to")]
        n = max(2, min(400, int(st.get("points") or 60)))
        had, before = var in self.vars, self.vars.get(var)
        try:
            for s in formulas:
                label = str(s.get("label") or s.get("expr") or s.get("x") or "?")
                if s.get("x") not in (None, ""):
                    x, _ = self.calc(s["x"])
                    empty += x is None
                    vlines.append({"label": label, "x": x, "color": s.get("color"), "dash": bool(s.get("dash"))})
                    continue
                a = self.calc(s["from"])[0] if s.get("from") not in (None, "") else lo
                b = self.calc(s["to"])[0] if s.get("to") not in (None, "") else hi
                pts = []
                if a is not None and b is not None:
                    for k in range(n):
                        x = a + (b - a) * k / (n - 1)
                        self.vars[var] = x
                        y, _ = self.calc(s.get("expr"))
                        empty += y is None
                        pts.append([x, y])
                else:
                    empty += n
                lines.append({"label": label, "pts": pts, "color": s.get("color"), "dash": bool(s.get("dash")),
                              "expr": s.get("expr")})
        finally:                                          # x belongs to the plot, not the program
            if had:
                self.vars[var] = before
            else:
                self.vars.pop(var, None)
        if not live:
            self.log(self.t("plot", title=title, k=len(lines) + len(vlines),
                            empty=self.t("plot_empty", k=empty) if empty else ""),
                     "warn" if empty else "info", st["id"])
        if self.dry:
            return None
        # the same curves as a table, one row per x, for the table view, CSV and the LLM; a data
        # chart's x column is the loop's (its input, named in words by the window: path)
        key = xname or var
        xs = sorted({p[0] for ln in lines for p in ln["pts"] if ln.get("data")} if xname else {p[0] for ln in lines for p in ln["pts"]})
        rows = [{key: x, **{ln["label"]: self._at(ln, x, var) for ln in lines}} for x in xs]
        for ln in lines:                                  # (the table's own: not drawn)
            ln.pop("data", None)
            ln.pop("expr", None)
        return {"id": st["id"], "kind": "plot", "label": title, "var": key, "path": xpath, "paths": paths,
                "columns": [key] + [ln["label"] for ln in lines], "units": units, "rows": rows,
                "lines": lines, "vlines": vlines, "xrange": [lo, hi], "yrange": yr,
                "xlabel": st.get("xlabel") or "", "ylabel": st.get("ylabel") or ""}

    def _save_path(self, text: str) -> str:
        """{name} filled in; a relative path lands in the folder of the model's file."""
        return _beside_model(self.manager, self.session, _VAR_REF.sub(lambda m: _fmt(self.vars.get(m.group(1))),
                                                                      text.strip()))

    async def do_save(self, st):
        text = str(st.get("path") or "").strip()
        path = self._save_path(text) if text else None
        where = self.t("save_as", path=path) if path else self.t("save_own")
        if path and not path.lower().endswith(_SAVE_EXT):
            raise RuntimeError(self.t("save_ext", path=path))
        why = _save_refused(self.manager, self.session, path, self.ws.lang) if path else None
        if why is not None:
            raise RuntimeError(why)
        if self.dry:
            self.log(self.t("save_dry", where=where), sid=st["id"])
            return
        res = main_tools.save_simulation(self.manager, self.session, path)
        if "saved" not in res:
            raise RuntimeError(self.t("save_fail", res=res))
        self.ws.note_model(self.manager, self.session)    # a save as moves the session's file
        self.log(self.t("save_ok", res=path or res), sid=st["id"])

    # -- the five flowsheet statements: the MCP tools' own code, measured alike
    def _what(self, st: dict) -> str:
        """A flowsheet statement in the run log's words."""
        do, t = st["do"], self.t
        if do == "place":
            return (t("st_place_block", block=st["block"], type=st.get("type")) if st.get("block")
                    else t("st_place_stream", stream=st["stream"], type=st.get("type") or "MATERIAL"))
        if do == "connect":
            return t("st_connect", stream=st["stream"], block=st["block"], port=st["port"])
        if do == "remove":
            if st.get("port"):
                return t("st_disconnect", stream=st["stream"], block=st["block"], port=st["port"])
            return t("st_remove_block", block=st["block"]) if st.get("block") else \
                t("st_remove_stream", stream=st["stream"])
        if do == "component":
            return t("st_comp_add", name=st["add"]) if st.get("add") else t("st_comp_remove", name=st["remove"])
        return t("st_method", method=st["method"])

    def _shadow(self, st: dict) -> list:
        """A check's problems of this statement: wb_plan.check over the program that runs and the
        flowsheet as it is now (snapshot and taken_names, the port table), once per dry run --
        tab.check's (_check_view, made before the steps run), else its own."""
        if self.shadow is None:
            self.shadow = {}
            try:
                fs = snapshot(self.manager, self.session)
                fs.update(taken_names(self.manager.get_app(self.session)))
                chk = wb_plan.check(wb_plan.active(self.tab["program"]), fs, _PORT_TABLE, self.ws.lang)
                self.shadow = {r["id"]: r.get("problems") or [] for r in chk["steps"]}
            except Exception:
                logger.warning("workbench: the flowsheet check of %s failed", self.tab.get("id"), exc_info=True)
        return self.shadow.get(st["id"], [])

    async def _structure(self, st: dict, tool: str, args: dict, fn, spec=None) -> str | None:
        """One flowsheet statement: a check lists what it would do and its problems; a real run
        calls ``fn`` -- the tool's own implementation -- through intercept.measured (the MCP
        tool's restore point, probes and records, the statement's sid on them), has the window
        re-read what it changed and stops the program when the tool did not do it. Never in
        a loop: each pass would change the flowsheet again (wb_plan's in_loop, statically)."""
        what = self._what(st)
        if self.dry:
            self.log(what, sid=st["id"])
            for p in self._shadow(st):
                self.log(p["text"], p["level"] if p["level"] in ("error", "warn") else "info", st["id"])
            return None
        if self.agg:
            raise RuntimeError(self.t("struct_in_loop", what=what))
        spec = spec if spec is not None else intercept.TOOLS[tool]
        args = {"session_name": self.session, **args}
        book = self.book
        extra = {k: v for k, v in ((book.extra if book is not None else None) or {}).items() if k != "reason_src"}
        extra["sid"] = st["id"]
        res, rp = intercept.measured(self.manager, book, tool, args, fn, spec=spec, actor="program", via=self.via,
                                     **extra)
        if rp and rp.get("status") in ("skipped", "failed") and rp.get("why") in ("slow", "failed"):
            why = self.t("cp_why_slow", est=_dur(self.ws.lang, rp.get("est_s"))) if rp["why"] == "slow" \
                else self.t("cp_why_failed")
            self.log(self.t("struct_nocp", why=why), "info", st["id"])
        refresh = intercept.refresh_of(spec, args)
        if refresh:
            self.ws.later(self.session, refresh)
        text = " ".join(str(res or "").split())
        if probes.failed(res):
            raise RuntimeError(self.t("struct_fail", what=what, res=text))
        self.log(text, sid=st["id"])
        return res

    async def do_place(self, st):
        m, s = self.manager, self.session
        if st.get("block"):
            name, typ = st["block"], str(st.get("type") or "")
            await self._structure(st, "place_block", {"block_name": name, "block_type": typ},
                                  lambda: flowsheet_tools.place_block(m, s, name, typ))
        else:
            name, typ = st["stream"], str(st.get("type") or "MATERIAL")
            await self._structure(st, "place_stream", {"stream_name": name, "stream_type": typ},
                                  lambda: flowsheet_tools.place_stream(m, s, name, typ))

    async def do_connect(self, st):
        m, s, stream, block, port = self.manager, self.session, st["stream"], st["block"], st["port"]
        await self._structure(st, "connect_stream", {"block_name": block, "stream_name": stream, "port_name": port},
                              lambda: flowsheet_tools.connect_stream(m, s, block, stream, port))

    async def do_remove(self, st):
        m, s = self.manager, self.session
        if st.get("port"):                                # a disconnect: the stream stays, that end free
            stream, block, port = st["stream"], st["block"], st["port"]
            await self._structure(st, "disconnect_stream",
                                  {"block_name": block, "stream_name": stream, "port_name": port},
                                  lambda: self._disconnect(block, stream, port))
        elif st.get("block"):
            name = st["block"]
            await self._structure(st, "remove_block", {"block_name": name},
                                  lambda: flowsheet_tools.remove_block(m, s, name))
        else:
            name = st["stream"]
            await self._structure(st, "remove_stream", {"stream_name": name},
                                  lambda: flowsheet_tools.remove_stream(m, s, name))

    def _disconnect(self, block: str, stream: str, port: str) -> str:
        """Take ``stream`` off ``block``'s ``port`` -- the port's Elements.Remove, as an undo's
        disconnect does (V15: inlet or outlet, the stream stays, that end free)."""
        app = self.manager.get_app(self.session)
        if app is None:
            return f"No active session named '{self.session}'."
        name, node = probes._port(probes._tree(app), block, port)
        if node is None:
            return f"Failed to disconnect '{stream}': block '{block}' has no port {port}."
        hit = next((x for x in probes._names(node) or () if x.upper() == stream.upper()), None)
        if hit is None:
            return f"Failed to disconnect '{stream}': it is not on {block} port {name}."
        res = self.manager.remove_element(self.session, rf"\Data\Blocks\{block}\Ports\{name}", hit)
        return f"Stream '{hit}' disconnected from {block} port {name}." if str(res).startswith("Removed") else res

    async def do_component(self, st):
        m, s = self.manager, self.session
        if st.get("add"):
            name = st["add"]
            await self._structure(st, "add_component", {"component_id": name},
                                  lambda: properties_tools.add_component(m, s, name))
        else:
            name = st["remove"]
            await self._structure(st, "remove_component", {"component_id": name},
                                  lambda: properties_tools.remove_component(m, s, name))

    async def do_method(self, st):
        m, s, method = self.manager, self.session, st["method"]
        await self._structure(st, "set_property_method", {"method": method},
                              lambda: properties_tools.set_property_method(m, s, method))

    async def do_proc(self, st):
        pass                                              # a definition: runs only when called

    async def do_group(self, st):
        pass                                              # a heading -- the steps after it are its group

    async def do_call(self, st):
        proc = self.procs.get(st.get("name"))
        if proc is None:                                  # reported before the run (a check goes on)
            return
        if self.depth >= _MAX_DEPTH:
            raise RuntimeError(self.t("call_deep", n=_MAX_DEPTH))
        shown = []
        for p, a in zip(proc.get("params") or [], st.get("args") or []):
            v, _ = self.calc(a)
            self.vars[p], self.units[p] = v, None
            shown.append(f"{p} = {_fmt(v)}")
        self.log(self.t("call", name=proc["name"], args=f" ({', '.join(shown)})" if shown else ""), sid=st["id"])
        self.depth += 1
        try:
            await self.block(proc.get("body") or [])
        finally:
            self.depth -= 1

    def _right(self, st: dict):
        """An if's right side: a number, or an expression over the program's variables (None: no value)."""
        r = st.get("right", 0)
        try:
            return float(r)
        except (TypeError, ValueError):
            v = self.calc(str(r))[0]
            return None if v is None else float(v)

    async def do_if(self, st):
        left = self._value(st.get("left") or {})
        op, right = st.get("op", ">"), self._right(st)
        if left is None or right is None:
            self.log(self.t("if_unreadable"), "warn", st["id"])
            await self.block(st.get("else") or [])
            return
        hit = _OPS.get(op, _OPS[">"])(float(left), right)
        self.log(self.t("if_result", left=_fmt(float(left)), op=op, right=f"{right:g}",
                        verdict=self.t("true" if hit else "false")), sid=st["id"])
        await self.block(st.get("then" if hit else "else") or [])

    async def do_repeat(self, st):
        n = int(st.get("times", 1))
        for i in range(1 if self.dry else n):
            self.vars["i"] = float(i + 1)
            await self.block(st.get("body") or [])
            self.record(st, "i", float(i + 1), "repeat", f"× {n}")

    async def do_sweep(self, st):
        a, b, n = float(st.get("from", 0)), float(st.get("to", 0)), max(1, int(st.get("steps", 2)))
        path, unit, name = st.get("path"), st.get("unit"), st.get("as") or "sweep_value"
        values = [a + (b - a) * k / (n - 1) for k in range(n)] if n > 1 else [a]
        unit = unit or self._unit_of(path)
        self.units[name] = unit
        self.log(self.t("sweep", path=path, unit=f" [{unit}]" if unit else "",
                        values=", ".join(f"{v:.4g}" for v in values)), sid=st["id"])
        self.touch(st, [path])
        for v in values[:1] if self.dry else values:
            self.vars[name] = v
            if not self.dry:
                self._write(path, v, st.get("unit"))
            await self.block(st.get("body") or [])
            self.record(st, name, v, "sweep", path)
        self.done(st, [path], "sweep")

    def _pinch_field(self, text, kind: str):
        """(value in C or kW, None) or (None, why) for a stream field: a path or an expression."""
        text = str(text or "").strip()
        if not text.startswith("\\"):
            return self.calc(text)
        v = read_value(self.manager, self.session, text)
        if v is None:
            return None, self.t("not_found", path=text)
        unit = self._unit_of(text)
        out = _to_pinch_unit(kind, v, unit)
        return (out, None) if out is not None else (None, f"{text} [{unit}]")

    async def do_pinch(self, st):
        """Heat integration targets, composite curves and match suggestions for the model as
        it stands: the thermal streams are read from it each time."""
        sid, title = st["id"], st.get("title") or self.t("pinch_title")
        dtmin, prefix = float(st.get("dtmin") or 10), st.get("as") or "pinch"
        for k, u in (("qh", "kW"), ("qc", "kW"), ("recovery", "kW"), ("hot_now", "kW"), ("cold_now", "kW"),
                     ("t_hot", "C"), ("t_cold", "C")):
            self.vars[f"{prefix}_{k}"], self.units[f"{prefix}_{k}"] = None, u
        read = lambda path: read_value(self.manager, self.session, path)
        rows, skipped = ([], [])
        if st.get("auto", True):
            rows, skipped = _pinch_auto(self.ws.session(self.session).get("flowsheet") or {},
                                        set(st.get("exclude") or []), read)
        if skipped:
            self.log(self.t("pinch_skip", title=title, names=", ".join(skipped)), "warn", sid)
        streams, seen, places = [], set(), {}
        blocks = {b.get("name") for b in (self.ws.session(self.session).get("flowsheet") or {}).get("blocks") or []}
        for r in rows + list(st.get("streams") or []):
            vals, why = {}, None
            for key, kind in _PINCH_FIELDS:
                vals[key], why = self._pinch_field(r.get(key), kind)
                if vals[key] is None:
                    break
            if vals.get("duty") is None or vals.get("t_out") is None or vals.get("t_in") is None:
                self.log(self.t("pinch_bad", title=title, why=f"{r.get('name')}: {why}"), "warn", sid)
                continue
            if abs(vals["duty"]) < 1e-9:                     # idle: nothing to integrate
                continue
            name, n = str(r.get("name") or "?"), 2
            while name in seen:
                name, n = f"{r.get('name')} ({n})", n + 1
            seen.add(name)
            block = r.get("block") or (r.get("name") if r.get("name") in blocks else None)
            if block:                                        # for the flowsheet's heat view
                places[name] = {"block": block, "part": r.get("part")}
            t1, t2, q = vals["t_in"], vals["t_out"], vals["duty"]
            kind = r.get("type") if r.get("type") in ("hot", "cold") else (
                "hot" if t1 > t2 else "cold" if t1 < t2 else "hot" if q < 0 else "cold")
            streams.append({"name": name, "t_supply": t1, "t_target": t2, "heat_flow_kw": abs(q), "type": kind})
        hot = [x for x in streams if x["type"] == "hot"]
        self.log(self.t("pinch_streams", title=title, n=len(streams), hot=len(hot), cold=len(streams) - len(hot),
                        auto=self.t("pinch_auto") if st.get("auto", True) else "",
                        names=", ".join(x["name"] for x in streams) or "-")
                 + (self.t("pinch_dry") if self.dry else ""), sid=sid)
        if self.dry:
            return
        if not hot or len(hot) == len(streams):
            self.log(self.t("pinch_none", title=title), "warn", sid)
            return
        dt = dtmin / 2                                        # the tools take each side's share
        job = [{k: v for k, v in x.items() if k != "type" or x["t_supply"] == x["t_target"]} for x in streams]
        res = await asyncio.to_thread(pinch_tools.targets, job, dt, "Plant", True)
        if isinstance(res, str):
            self.log(self.t("pinch_fail", title=title, why=res), "error", sid)
            return
        tg = res["targets"][0]
        shifted = (tg.get("pinch_shifted_C") or {}).get("hot")
        hot_now = sum(x["heat_flow_kw"] for x in streams if x["type"] == "cold")
        cold_now = sum(x["heat_flow_kw"] for x in hot)
        got = {"qh": tg.get("Qh_kW"), "qc": tg.get("Qc_kW"), "recovery": tg.get("Qrecovery_kW"),
               "hot_now": hot_now, "cold_now": cold_now,
               "t_hot": None if shifted is None else shifted + dt, "t_cold": None if shifted is None else shifted - dt}
        for k, v in got.items():
            self.vars[f"{prefix}_{k}"] = v
        rec = recorder.current()
        if rec is not None:                               # the journal: what it found, nothing changed
            rec.add("analysis", target={"kind": "pinch", "title": title}, status="unchanged", dtmin=dtmin,
                    streams=len(streams), qh=got["qh"], qc=got["qc"], recovery=got["recovery"])
        f = lambda v: _fmt(v) if v is not None else "?"
        self.log(self.t("pinch_done", title=title, dt=_fmt(dtmin), qh=f(got["qh"]), hn=f(hot_now), qc=f(got["qc"]),
                        cn=f(cold_now), rec=f(got["recovery"]), th=f(got["t_hot"]), tc=f(got["t_cold"])), sid=sid)
        T = self.t
        cols = ["ΔTmin", T("pc_qh"), T("pc_qh_now"), T("pc_qc"), T("pc_qc_now"), T("pc_rec"), T("pc_th"), T("pc_tc")]
        vals = [dtmin, got["qh"], hot_now, got["qc"], cold_now, got["recovery"], got["t_hot"], got["t_cold"]]
        units = ["C", "kW", "kW", "kW", "kW", "kW", "C", "C"]
        self._keep(st, {"id": sid + ":targets", "kind": "table", "label": f"{title}: {T('pinch_targets')}", "var": None,
                        "columns": cols, "units": dict(zip(cols, units)), "rows": [dict(zip(cols, vals))]}, "targets")
        cols = [T("pc_name"), T("pc_type"), T("pc_tin"), T("pc_tout"), T("pc_duty")]
        self._keep(st, {"id": sid + ":streams", "kind": "table", "label": f"{title}: {T('pinch_list')}", "var": None,
                        "columns": cols, "units": dict(zip(cols[2:], ["C", "C", "kW"])),
                        "rows": [dict(zip(cols, [x["name"], T("pc_" + x["type"]), x["t_supply"], x["t_target"],
                                                 x["heat_flow_kw"]])) for x in streams]}, "streams")
        graphs = {g.get("type"): g for z in (res.get("curves") or {}).values() for g in z.get("graphs") or []}
        for part, gtype, ylabel, pick in (
                ("cc", "Composite Curves", T("pc_t"), lambda seg: (T("pc_hotcc"), "#d9534f") if "Hot" in seg
                 else (T("pc_coldcc"), "#2f7ed8")),
                ("gcc", "Grand Composite Curve", T("pc_ts"), lambda seg: None if "No Pockets" in seg
                 else ("GCC", "#8e5cc7"))):
            g = graphs.get(gtype)
            if not g:
                continue
            lines = []
            for seg in g.get("segments") or []:
                look = pick(str(seg.get("title") or ""))
                if look:
                    lines.append({"label": look[0], "color": look[1], "dash": False,
                                  "pts": [[p["x"], p["y"]] for p in seg.get("data_points") or []]})
            xs = sorted({p[0] for ln in lines for p in ln["pts"]})
            if not xs:
                continue
            heat = T("pc_heat")
            labels = list(dict.fromkeys(ln["label"] for ln in lines))
            rows = [{heat: x, **{lab: next((p[1] for ln in lines if ln["label"] == lab for p in ln["pts"] if p[0] == x), None)
                                 for lab in labels}} for x in xs]
            self._keep(st, {"id": f"{sid}:{part}", "kind": "plot", "label": f"{title}: {T('pinch_' + part)}",
                            "var": heat, "columns": [heat] + labels, "units": {heat: "kW", **{lab: "C" for lab in labels}},
                            "rows": rows, "lines": lines, "vlines": [], "xrange": [min(0, xs[0]), xs[-1]],
                            "yrange": [None, None], "xlabel": f"{heat} [kW]", "ylabel": f"{ylabel} [C]"}, part)
        if not st.get("matches", True):
            return
        res = await asyncio.to_thread(pinch_tools.matches, job, dt, None, None, 0, 3)
        if isinstance(res, str):
            self.log(self.t("pinch_nomatch", title=title, why=res), "warn", sid)
            return
        cols = [T("pc_region"), T("pc_option"), T("pc_hs"), T("pc_cs"), T("pc_duty"), T("pc_note")]
        rows, regions = [], []
        for reg in res.get("regions") or []:
            regions.append({"above": bool(reg.get("above_pinch")), "alts": [
                [{"hot": m.get("hot"), "cold": m.get("cold"), "duty": m.get("duty_kw"),
                  "utility": bool(m.get("is_utility")), "check": m.get("pinch_check")}
                 for m in alt.get("matches") or []] for alt in reg.get("alternatives") or []]})
            where = T("pc_above") if reg.get("above_pinch") else T("pc_below")
            if reg.get("n_min") is None:
                rows.append(dict(zip(cols, [where, None, None, None, None, T("pc_none")])))
            for k, alt in enumerate(reg.get("alternatives") or [], 1):
                for m in alt.get("matches") or []:
                    note = T("pc_util") if m.get("is_utility") else T("pc_ok") if m.get("pinch_check") == "ok" \
                        else T("pc_split") if m.get("pinch_check") == "needs_split" else ""
                    rows.append(dict(zip(cols, [where, k, m.get("hot"), m.get("cold"), m.get("duty_kw"), note])))
        self._keep(st, {"id": sid + ":matches", "kind": "table", "label": f"{title}: {T('pinch_matches')}",
                        "var": None, "columns": cols, "units": {T("pc_duty"): "kW"}, "rows": rows,
                        "heat": {"regions": regions, "where": places, "recovery": got["recovery"],
                                 "qh": got["qh"], "qc": got["qc"]}}, "matches")

    async def do_optimize(self, st):
        variables = [{"aspen_path": v["path"], "lower": v.get("lower"), "upper": v.get("upper"),
                      **({"type": v["type"]} if v.get("type") else {})}
                     for v in st.get("variables") or []]
        tr = _trace(wb_plan.active(self.tab["program"]), st["id"], self.funcs, self.ws.lang, self._unit_of)
        where = lambda e: (tr.optimizer_form(e["expr"], e.get("paths")) if e.get("expr")
                           else {"aspen_path": e.get("path")})
        objectives = [dict(where(o), direction=o.get("direction", "minimize"))
                      for o in st.get("objectives") or []]
        constraints = []
        for c in st.get("constraints") or []:
            entry = where(c)
            for k in ("lower", "upper"):
                if c.get(k) is not None:
                    entry[k] = c[k]
            constraints.append(entry)
        out_dir = self.ws.dir / "runs" / self.tab["id"]
        before = {p.name for p in out_dir.iterdir()} if out_dir.is_dir() else set()

        def show(path):                  # the window draws its progress bar from this file
            self.run["progress"] = {"file": path, "id": st["id"], "algorithm": st.get("algorithm")}
            self.ws.save()

        # The step's own finish applies only to "best" and "last": a restore waits for the
        # program's end (settle), so the statements after this one see the last point.
        finish, report = self.finish(st), {}
        paths = [v["aspen_path"] for v in variables if v.get("aspen_path")]
        self.touch(st, paths)
        if not self.dry:
            self.restore_point(st)
        token = progress_sink.set(show)
        agg = self.aggregate("optimize", actor="optimizer", via="program")
        try:
            with agg as own:                     # own: this step's record, not a loop's it joined
                try:
                    res = await run_optimize(
                        self.manager, self.session, st.get("algorithm", "afmcbo"),
                        variables=variables, objectives=objectives, constraints=constraints or None,
                        eval_budget=st.get("eval_budget"), options=st.get("options") or None,
                        seed=st.get("seed"), dry_run=self.dry, output_dir=None if self.dry else str(out_dir),
                        finish="best" if finish == "best" else "last", report=report,
                    )
                finally:
                    if own is agg:
                        agg.report = dict(report, finish=finish) if report else None
                if own is agg and res.startswith("Error"):
                    agg.status, agg.extra["result"] = "failed", res.splitlines()[0][:journal.RESULT_MAX]
        finally:
            progress_sink.reset(token)
            if not self.dry:
                self.nrun += 1
            if self.run.pop("progress", None) is not None:
                self.ws.drain()          # a Stop pressed during the optimization counts now
                self.ws.save()
        failed = res.startswith("Error")
        if finish == "restore" and not self.dry and not failed:
            res = res.split("\n\nModel state:")[0] + "\n\n" + self.t("opt_until_end")
        self.log(self.t("opt_preview" if self.dry else "opt_result") + res[:3000],
                 "error" if failed else "info", st["id"])
        if failed and not self.dry:
            raise RuntimeError(res.splitlines()[0])
        if report.get("state") in ("best", "last"):      # (best falls back to the start without a best point)
            self.done(st, paths, "opt_" + report["state"])
        if not self.dry and out_dir.is_dir():     # the run folder this step just wrote
            new = [p for p in out_dir.iterdir() if p.is_dir() and p.name not in before]
            if new:
                opt = opt_result(max(new, key=lambda p: p.stat().st_mtime), st,
                                 self.manager.get_app(self.session), tr)
                if opt:
                    opt.update(apply=True, finish=finish)  # a point can be written back (apply_point)
                    self.run.setdefault("opts", []).append(opt)
            app = self.manager.get_app(self.session)
            if app is not None:
                self.ws.refresh_results(app, self.session)


def _book(manager, tab: dict, via: str, ai_group: str | None, proposed: dict | None = None,
          approval: dict | None = None) -> recorder.Scope:
    """The journal's scope of one program run: its own change group, titled by the tab;
    ``proposed``: the AI's proposal the user approved (a card), on each of its records;
    ``approval``: the AI's proposal tab the user runs -- the group titled by the proposal,
    its header ``proposal`` / ``proposed_in``, every record ``proposal`` and ``approved: user``.
    The group itself is the scope's ``head`` (its end goes into it: _approval_end)."""
    prop = (approval or {}).get("prop") or {}
    g = journal.GROUPS.program(run=journal.new_id("r"), title=prop.get("title") or tab.get("title"),
                               ai_group=ai_group, session=tab["session"], **proposals.head(prop) if prop else {})
    s = recorder.scope(actor="program", via=via, session=tab["session"], group=g, proposed=proposed,
                       proposal=prop.get("id"), approved="user" if prop else None)
    s.manager, s.head = manager, g
    return s


def _hold(tab: dict, via: str) -> int:
    """A real program run's hold on its session (tools/activity.py)."""
    return activity.hold(tab["session"], "program", tab=tab["id"], title=tab.get("title"), via=via)


def _mark(manager, tab: dict, book, kind: str, call: str, **fields) -> bool:
    """A program run's ``begin`` record, written as it starts (a server that dies during it
    leaves "started, no end recorded" in the timeline), or its ``end`` (same ``call``).
    Nothing with the journal off; never raises."""
    try:
        if book is None or not book.on:
            return False
        model = manager.model_id(tab["session"])
        if not model:
            return False
        extra = book.extra or {}
        rec = journal.entry(kind, model=model, session=tab["session"], actor="program", via=book.via,
                            group=book.group, call=call, title=tab.get("title"), tab=tab["id"],
                            proposed=extra.get("proposed"), proposal=extra.get("proposal"),
                            approved=extra.get("approved"), **fields)
        return journal.append(model, [rec], path=manager.session_file(tab["session"])) is not None
    except Exception:
        logger.warning("workbench: %s record of the program on %s lost", kind, tab.get("session"), exc_info=True)
        return False


async def execute(ws: Workspace, manager, tab: dict, dry_run: bool, via: str = "window",
                  ai_group: str | None = None, hold: int | None = None, proposed: dict | None = None,
                  approve=None, mode: str = "run", resume: str | None = None) -> dict:
    """Run (or check) a tab's program. ``via``: who started it, the window or the AI (mcp,
    whose change group is ``ai_group``); the journal records a real run as the program's,
    between a ``begin`` and an ``end`` record. A real run holds its session until it ends:
    ``hold``, taken by the caller in the step that found the session free (start_runs,
    workbench_run), else taken here. Every real run is pre-checked -- paths, expressions, and
    the flowsheet check of a program that changes the flowsheet -- and refused whole on an
    error, before any write or restore point. ``proposed``: the AI's workbench_run the user approved
    after its call (a confirmation card), on every record of the run. ``approve``: the window's
    run of an AI proposal tab -- the user's approval (True, or "no_cp": without a restore
    point; "edits": only the user's edits to an applied or partly applied one, proposals.kept) --:
    pre-checked the same way, then a restore point (before-proposal,
    however slow: the user pressed it), then run as "approved by the user" (_approval_*);
    ``mode``: run | step (as the window asked; step pauses before every step, and a run the
    window started pauses at the tab's breakpoints -- _Runner.pause). ``resume``: an approval
    that continues a stopped one from that step (proposals.resumable; anything else: from the
    start) -- the steps before it that change the model are not run again (_resume_plan)."""
    token = hold if hold is not None or dry_run else _hold(tab, via)
    r = None
    try:
        ws.stops.discard(tab["id"])
        ws.steps.pop(tab["id"], None)                      # (a press left from an earlier run)
        prev = tab.get("run") if isinstance(tab.get("run"), dict) else {}
        tab["run"] = run = dict(_idle_run(), status="running", dry_run=dry_run, started=time.time())
        if via == "auto":                                  # a proposal's check the server started
            run["auto"] = True
        r = _Runner(ws, manager, tab, dry_run)
        r.via, r.hold = via, token
        if not dry_run:                                    # stepping, breakpoints (the window's own runs)
            r.mode = run["mode"] = _run_mode(mode)
            r.breaks_on = via == "window" and proposed is None
            r.nums = {row["id"]: row["n"] for row in wb_plan.outline(tab["program"]) if row.get("n")}
            r.set_groups(tab["program"])
            ws.runners[tab["id"]] = r
        prop = tab.get("proposal") if approve and not dry_run and tab.get("kind") == "proposal" else None
        if isinstance(prop, dict):
            r.approval = {"prop": prop, "no_cp": approve == "no_cp", "mode": _run_mode(mode), "started": False,
                          "edits": approve == "edits" and prop.get("status") in proposals.EDITS,
                          "resume": proposals.resumable(prop, tab.get("program_rev"),
                                                        wb_plan.active(tab["program"])) if resume else None,
                          "prev": {k: prev[k] for k in ("values0", "watch", "fx_pre") if k in prev}}
            if r.approval["resume"] is not None and r.approval["resume"]["at"] != resume:
                r.approval["resume"] = None                # (start_runs refused one that moved meanwhile)
            run.update(approved=True, mode=_run_mode(mode))
        if not dry_run:
            r.book = _book(manager, tab, via, ai_group, proposed, r.approval)
            if r.book.group:
                run["group"] = r.book.group                # the journal's change group of this run
            if r.approval is None:                         # (an approval's: once its restore point is kept)
                r.begin(manager, tab)
        with r.book or contextlib.nullcontext():
            run = await _execute(ws, manager, tab, dry_run, r, run)
        return run
    finally:
        if ws.runners.get(tab["id"]) is r:
            del ws.runners[tab["id"]]
        ws.steps.pop(tab["id"], None)
        if r is not None and r.began is not None:
            _mark(manager, tab, r.book, "end", r.began, status=(tab.get("run") or {}).get("status"))
        if r is not None and r.approval is not None:
            _approval_end(ws, manager, tab, r)
        if not dry_run and ws.note_journal(manager, tab["session"]):   # the run's last records
            ws.save()
        activity.release(token)


def _resume_plan(tab: dict, r: "_Runner", program: list) -> list:
    """An approval that continues a stopped one from its step ``resume.at``: the top-level steps
    before it that change the model (proposals.steps' ``changing``) ran already and are left out
    -- of the pre-check too: a block they placed is there now --; the others before it (a read,
    a calc) run again without pausing, so the variables they set are there. An approval of the
    user's edits to an applied or partly applied one (``edits``) leaves out the steps that applied
    and are unchanged (proposals.kept) the same way, its first edited step in place of
    ``resume.at``; so does a run that continues one (a step after the stop that it left out).
    Returns the program that runs; ``r.approval`` gets ``skip`` and ``quiet`` (sids)."""
    a = r.approval
    ran, new = proposals.kept(a["prop"], tab["program"], proposals.EDITS)
    at = a["resume"]["at"] if a.get("resume") else new[0] if new else None
    skip, a["quiet"] = _applied(tab, program, at) if at else ([], [])
    skip = set(skip) | set(ran)
    a["skip"] = [st["id"] for st in program if st.get("id") in skip]
    return [st for st in program if st.get("id") not in skip]


def _applied(tab: dict, program: list, at: str) -> tuple[list, list]:
    """(skip, quiet): the top-level steps before ``at`` of a stopped approval that changed the
    model -- applied already, not run nor checked again -- and the others before it (a read, a
    calc: run again, unpaused). ``program``: the steps that run (wb_plan.active)."""
    info = proposals.steps(tab["program"], program)
    before = []
    for sid in info["top"]:
        if sid == at:
            break
        before.append(sid)
    changing = set(info["changing"])
    return [x for x in before if x in changing], [x for x in before if x not in changing]


def _approval_start(ws: Workspace, manager, tab: dict, r: "_Runner") -> None:
    """The approved run passed its pre-check; before its first step, a restore point of the
    model (before-proposal, in the run's change group -- its first record -- allowed however slow:
    the user pressed it; the structure statements' own find it: one per group) unless the user
    chose to run without one. None could be saved: _Refused, nothing runs. Then the begin record,
    the proposal running (``run``: group, model, mode, cp, total...), a chat line and the turned-off
    steps named in the run log."""
    a, prop, lang, session = r.approval, r.approval["prop"], ws.lang, tab["session"]
    program = tab["program"]
    info = proposals.steps(program, wb_plan.active(program))
    a.update(info=info)
    res = a.get("resume")
    prev = prop.get("run") if isinstance(prop.get("run"), dict) else {}
    if res and isinstance(prev.get("cp"), dict) and prev["cp"]:
        cp = dict(prev["cp"])                              # continuing: the first approval's restore point
    elif a["no_cp"]:
        cp = {"skipped": "user"}
    else:
        ws.save()                                          # the window shows it running meanwhile
        ws.beat()
        rp = intercept.restore_point(manager, session, "before-proposal", group=r.book.group if r.book else None,
                                     actor="program", via=r.via, call=journal.new_id("c"), allow_slow=True,
                                     proposal=prop["id"], approved="user")
        if rp.get("status") not in ("dedup", "reused", "copied", "exported") or not rp.get("id"):
            why = " ".join(str(rp.get("error") or rp.get("why") or "?").split())[:200]
            a["refused"] = ("cp", why)
            raise _Refused(proposals.say(lang, "not_cp", why=why))
        cp = {k: rp.get(k) for k in ("id", "status", "state", "secs", "tier") if rp.get(k) is not None}
        cp["t"] = round(time.time(), 3)
    r.begin(manager, tab)
    model = manager.model_id(session) if journal.enabled() else None
    more = {}
    if res or a.get("edits"):                              # (the steps it does not run again count as done)
        runs = set() if res else set(info["top"]) - set(a.get("skip") or ())   # (the edits': applied once they run)
        more = {"done": len(a.get("skip") or ()), "wrote": bool(a.get("skip")) or bool(prev.get("wrote")),
                "applied": {k: v for k, v in (prev.get("applied") or {}).items() if k not in runs}}
    if res:
        more["resumed"] = {"n": res["n"], "at": res["at"], "skipped": len(a.get("skip") or ()), "group": prev.get("group")}
    proposals.approve(prop, {"group": r.book.group if r.book else None, "model": model, "mode": a["mode"],
                             "cp": cp, "total": len(info["top"]), "off": len(info["off"]), **more}, time.time())
    a["started"] = True
    r.done_n, r.wrote = prop["run"]["done"], prop["run"]["wrote"]
    _fx_start(ws, manager, tab, a, model)
    if res:
        text = proposals.say(lang, "approved_resume", n=res["n"], done=len(a.get("skip") or ()))
    elif a.get("edits"):
        text = proposals.say(lang, "approved_edits", done=len(a.get("skip") or ()))
    else:
        text = proposals.say(lang, "approved_nocp" if a["no_cp"] else "approved", n=len(info["top"]))
    ws.message(tab, text, "system", kind="proposal", what="approved", proposal=prop["id"])
    if info["off"]:
        r.log(proposals.say(lang, "off_skipped", n=len(info["off"]), ids=", ".join(info["off"][:10])), "info")
    ws.save()


def _moved_on(tab: dict, at, mode, wrote) -> bool:
    """Whether a Stop before ``at`` leaves a place to continue from: not when only group
    headings ran before it, nor, by group, when nothing has changed the model yet -- the steps
    ahead of group 1's pause run by themselves, so starting again is the same."""
    if mode == "group" and not wrote:
        return False
    for st in wb_plan.active(tab.get("program") or []):
        if st.get("id") == at:
            return False
        if st.get("do") not in ("def", "proc", "group"):
            return True
    return False


def _approval_end(ws: Workspace, manager, tab: dict, r: "_Runner") -> None:
    """The approved run ended -- the proposal applied / partial / failed / stopped
    (proposals.finish), the end in its change group's header (``outcome``, a header written
    again: the AI's brief tells it) and a chat line -- or never started: ``refused`` (the
    pre-check's errors, no restore point) and the chat line why."""
    a, prop, lang, now = r.approval, r.approval["prop"], ws.lang, time.time()
    run = tab.get("run") or {}
    try:
        if not a["started"]:
            why, text = a.get("refused") or ("check" if r.bad else "error", None)
            two = {"texts": _tt("s_bad_writes", n=len(r.bad)), "help": _tt("bad_writes", n=len(r.bad))} \
                if why == "check" else {}                  # in the window's language, whichever
            proposals.refused(prop, why, now, errors=len(r.bad) or None, text=text or r.error, **two)
            key = "not_cp" if why == "cp" else "not_check" if why == "check" else None
            msg = proposals.say(lang, key, why=text, n=len(r.bad)) if key else _t(lang, "error", exc=r.error or "?")
            ws.message(tab, msg, "system", kind="proposal", what="refused", proposal=prop["id"])
            return
        at = (prop.get("run") or {}).get("at")
        proposals.finish(prop, run.get("status") or "error", now, error=r.error, outcome=r.sim_out)
        # the user's Stop: continue from there; and a run by group that failed part way: from
        # the step that failed, once what made it fail is put right (the steps applied not run again)
        ended = run.get("status")
        if (ended == "stopped" or (ended == "error" and a.get("mode") == "group")) \
                and _moved_on(tab, at, a.get("mode"), (prop.get("run") or {}).get("wrote")):
            proposals.stopped_at(prop, at, tab.get("program_rev"), a.get("mode"))
        ws.message(tab, proposals.end_text(prop, lang), "system", kind="proposal", what=prop["status"],
                   proposal=prop["id"])
        _fx_end(ws, manager, tab, prop)
        _tell_ai_ended(ws, tab, prop, proposals.end_text(prop, "en"), now)
        g = getattr(r.book, "head", None)
        model = (prop.get("run") or {}).get("model")
        if isinstance(g, dict) and model and journal.enabled():
            g["outcome"] = proposals.outcome(prop)
            journal.append(model, [journal.GROUPS.line(g)], path=manager.session_file(tab["session"]), groups=False)
    except Exception:
        logger.warning("workbench: the end of the approved proposal on %s not kept", tab.get("id"), exc_info=True)
    finally:
        ws.save()                                          # (the run's own save came before this)


# ---------------------------------------------------------------------------
# what an approved proposal's run moved (the window's result tags)
_TWINS = (("\\MASSFRAC\\", "\\MOLEFRAC\\"), ("\\MASSFLOW\\", "\\MOLEFLOW\\"))


def _watch_path(app, path: str) -> str | None:
    """The path a watched result is read at: as written, else -- a mass-basis result the model does not
    give -- its mole-basis twin; None when Aspen has neither."""
    if app is None:
        return None
    if _node(app, path) is not None:
        return path
    for mass, mole in _TWINS:
        if mass in path.upper():
            i = path.upper().index(mass)
            twin = path[:i] + mole + path[i + len(mass):]
            return twin if _node(app, twin) is not None else None
    return None


def _fx_start(ws: Workspace, manager, tab: dict, a: dict, model) -> None:
    """The approved run starts (feature effects): ``run.values0`` (the stream values the window has --
    no COM), ``run.watch`` (the proposal's watched results read now, ``b``: at most 3 lookups and their
    mole-basis twins), ``run.fx_pre`` (inputs changed before the approval and not run since: the result
    is not the proposal's alone), and runlog follows the session's runs for it. Continuing a stopped
    approval keeps the first approval's."""
    if not journal.enabled() or not model:
        return
    try:
        run, session, prop = tab["run"], tab["session"], a["prop"]
        prev = a.get("prev") or {}
        if a.get("resume") and "values0" in prev:
            run.update(copy.deepcopy(prev))
        else:
            run["values0"] = copy.deepcopy(ws.session(session).get("values") or {})
            run["fx_pre"] = bool((journal.pending(model) or {}).get("items"))
            app, watch = manager.get_app(session), []
            for i, w in enumerate(prop.get("watch") or []):
                p = _watch_path(app, w["path"]) or w["path"]
                vu = runlog.read(manager, session, [p]).get(p)
                item = {"path": p, "goal": i == 0, "b": vu[0] if vu else None, "u": vu[1] if vu else None}
                if p != w["path"]:
                    item["asked"] = w["path"]
                if w.get("label"):
                    item["label"] = w["label"]
                watch.append(item)
            run["watch"] = watch
        runlog.follow(session, prop["id"], model, [w["path"] for w in run.get("watch") or []])
    except Exception:
        logger.warning("workbench: the result tags of the proposal on %s not prepared", tab.get("id"), exc_info=True)


def _fx_set(ws: Workspace, tab: dict, f: dict) -> None:
    """``run.effects`` from the follow's last run (one that went well; else none): the watched results
    read after it, the record's delta, the stream values against ``values0``; ``joint_outside``: inputs
    from outside the proposal took effect in the same run."""
    run, fr = tab["run"], f.get("run") or {}
    run.pop("fx_wait", None)
    if fr.get("status") not in ("ok", "warn"):
        run.pop("effects", None)
        return
    after = f.get("a") or {}
    for w in run.get("watch") or []:
        vu = after.get(w["path"])
        w["a"] = vu[0] if vu else None
        w["u"] = w.get("u") or (vu[1] if vu else None)
    inputs = fr.get("inputs") or {}
    joint = bool(run.get("fx_pre")) or any(it.get("actor") not in (None, "program")
                                           for it in inputs.get("items") or [])
    values = ws.session(tab["session"]).get("values") or {}
    # (where each result's path starts -- what the proposal's groups change, the earliest first;
    # a run that stopped or failed partway: the groups it got to change, those before the step it ended at)
    pr = (tab.get("proposal") or {}).get("run") if isinstance(tab.get("proposal"), dict) else None
    stop = pr.get("n") if (tab.get("proposal") or {}).get("status") == "partial" and isinstance(pr, dict) else None
    changed = []
    for g in wb_plan.groups(tab.get("program") or []):
        at = g.get("at")
        if isinstance(stop, int) and (at is None or at not in (g.get("ids") or [])
                                      or g["rows"][g["ids"].index(at)] >= stop):
            continue
        changed += g.get("objs") or []
    run["effects"] = notable.build(fr.get("id"), fr.get("seq"), time.time(), watch=run.get("watch"),
                                   delta=fr.get("delta"), seg_=notable.seg(run.get("values0"), values),
                                   joint_outside=joint, changed=changed)
    run.pop("values0", None)


def _fx_own(sess: dict, rec) -> None:
    """The window's Run simulation (feature effects): the session's ``effects`` -- what the run moved,
    from its record's delta and the stream values runlog compared (``run_delta``) -- for the window
    to tag in learning mode; a run that did not go well, or was not measured, leaves none."""
    try:
        if not journal.enabled() or not isinstance(rec, dict) or rec.get("status") not in ("ok", "warn") \
                or not isinstance(rec.get("delta"), dict) or rec["delta"].get("first"):
            sess["effects"] = None
            return
        d = sess.get("run_delta") if isinstance(sess.get("run_delta"), dict) else None
        seg_ = notable.seg_of_delta(d) if d and d.get("id") == rec.get("id") else {}
        sess["effects"] = notable.build(rec.get("id"), rec.get("seq"), time.time(), delta=rec["delta"], seg_=seg_,
                                        changed=notable.changed_of(rec.get("inputs")))
    except Exception:
        logger.warning("workbench: the result tags of the run not made", exc_info=True)
        sess["effects"] = None


def _fx_end(ws: Workspace, manager, tab: dict, prop: dict) -> None:
    """The approved run ended: applied or partly applied after a run -- its effects now; applied with
    no run in it -- ``run.fx_wait`` until the session's next measured run, which is the proposal's when
    no other input changed in between (Workspace.fx_tick); otherwise no effects."""
    session = tab["session"]
    try:
        f = runlog.followed(session, prop["id"])
        if f is None:
            return
        if prop.get("status") in ("applied", "partial") and f.get("run"):
            _fx_set(ws, tab, f)
        elif prop.get("status") == "applied":
            model = f.get("model")
            pend = (journal.pending(model) if model else None) or {}
            tab["run"]["fx_wait"] = {"key": prop["id"], "t": round(time.time(), 3),
                                     "input_t": ((journal.summary(model) if model else None) or {}).get("last_input_t"),
                                     "paths": [it.get("path") for it in pend.get("items") or [] if it.get("path")]}
            return
    except Exception:
        logger.warning("workbench: the result tags of the proposal on %s not made", tab.get("id"), exc_info=True)
    runlog.unfollow(session, prop["id"])


_ENDS_TOLD = ("applied", "partial", "failed")      # a proposal's ends the AI is told of


def _tell_ai_ended(ws: Workspace, tab: dict, prop: dict, text: str, now: float) -> None:
    """An approved proposal ended (applied, partly applied, failed): the AI is told as it is
    told a request -- a note with ``event`` "proposal_end", pushed on the channel or handed by
    the hooks -- so a workflow in phases goes on to its next step without the user saying so.
    The chat does not show it (the window's own proposal line says it); the AI closes it with
    note_replies {"id", "done": true}, no reply needed. A stop by the user is not told: the user
    is already deciding."""
    if prop.get("status") not in _ENDS_TOLD:
        return
    note = {"id": "n" + uuid.uuid4().hex[:6], "target": {"kind": "proposal", "tab": tab["id"], "name": prop.get("title")},
            "text": f"Proposal \"{prop.get('title')}\" (tab {tab['id']}) {prop['status']}: {text}", "status": "open",
            "reply": "", "t": now, "tab": tab["id"], "event": "proposal_end", "outcome": prop["status"]}
    ws.session(tab["session"])["notes"].append(note)
    ws.asks.append({"session": tab["session"], "tab": tab, "note": note})


def _static_problems(program, lang: str) -> tuple[dict, dict, dict, list[tuple[str, str, str, str]]]:
    """The pre-check's problems no Aspen read decides, in ``lang``: (the defs parsed -- _functions
    --, the procedures -- _procs --, every expression parsed {text: tree}, [(sid, why, code, its
    short line)] -- code expr, call, name, save_ext, pinch, optimize or table). Pure: _execute
    runs it again in the other language for the problems' ``texts`` / ``help``, the same
    problems in the same order."""
    def t(key, **kw):
        return _t(lang, key, **kw)
    funcs, wrong = _functions(program, lang)
    wrong = [(sid, why, "expr", short) for sid, why, short in wrong]
    trees = {}
    for text, sid in _exprs(program):
        try:
            trees[text] = X.parse(text, funcs)
        except X.ExprError as exc:
            wrong.append((sid, str(exc), "expr", t("s_expr", expr=wb_plan._cut(text, 60) or "\"\"")))
    procs, bad_calls = _procs(program, lang)
    wrong += [(sid, why, "call", short) for sid, why, short in bad_calls]
    loops = {st["id"] for st in _walk(program) if st["do"] in _LOOPS}
    for st in _walk(program):
        names = [st["as"]] if st["do"] in ("calc", "read", "sweep", "seek", "yourturn") and st.get("as") else []
        names += list(st.get("record") or []) if st["do"] in _LOOPS else []
        wrong += [(st["id"], t("bad_name", name=n), "name", t("s_bad_name", name=n)) for n in names
                  if not X.is_name(n)]
        if st["do"] == "save" and str(st.get("path") or "").strip():
            if not str(st["path"]).strip().lower().endswith(_SAVE_EXT):
                wrong.append((st["id"], t("save_ext", path=st["path"]), "save_ext", t("s_save_ext", path=st["path"])))
        if st["do"] == "pinch":
            for row in st.get("streams") or []:
                if not str(row.get("name") or "").strip() or any(not str(row.get(k) or "").strip()
                                                                 for k, _ in _PINCH_FIELDS):
                    kw = {"title": st.get("title") or "", "name": row.get("name") or "?"}
                    wrong.append((st["id"], t("pinch_row", **kw), "pinch", t("s_pinch_row", **kw)))
        if st["do"] == "optimize":
            tr = _trace(program, st["id"], funcs, lang)
            for key, what in (("objectives", "opt_obj"), ("constraints", "opt_con")):
                for e in st.get(key) or []:
                    if e.get("expr"):
                        try:
                            tr.optimizer_form(e["expr"], e.get("paths"))
                        except X.ExprError as exc:
                            wrong.append((st["id"], t("opt_expr", what=t(what), expr=e["expr"], why=exc), "optimize",
                                          t("s_opt_expr", what=t(what), expr=wb_plan._cut(str(e["expr"]), 60))))
                    elif not e.get("path"):
                        wrong.append((st["id"], t("opt_nopath", what=t(what)), "optimize",
                                      t("s_opt_nopath", what=t(what))))
        if st["do"] == "plot":
            title, series = st.get("title") or t("plot_title"), st.get("series") or []
            data = [s for s in series if s.get("loop") not in (None, "")]
            for code, bad in (("plot_noseries", not series),
                              ("plot_loop", any(s["loop"] not in loops for s in data)),
                              ("plot_ycol", any(not s.get("ycols") for s in data)),
                              ("plot_norange", not data and any(st.get(k) in (None, "") for k in ("x_from", "x_to")))):
                if bad:
                    wrong.append((st["id"], t(code, title=title), "plot", t("s_" + code, title=title)))
        if st["do"] == "table" and st.get("loop"):
            title = st.get("title") or t("table_title")
            if st["loop"] not in loops:
                wrong.append((st["id"], t("table_loop", title=title), "table", t("s_table_loop", title=title)))
        elif st["do"] == "table":
            title = st.get("title") or t("table_title")
            if not st.get("columns"):
                wrong.append((st["id"], t("table_nocols", title=title), "table", t("s_table_nocols", title=title)))
            for c in st.get("columns") or []:
                if not c.get("path") and c.get("expr") in (None, ""):
                    kw = {"title": title, "label": c.get("label") or "?"}
                    wrong.append((st["id"], t("table_col", **kw), "table", t("s_table_col", **kw)))
    return funcs, procs, trees, wrong


async def _execute(ws: Workspace, manager, tab: dict, dry_run: bool, r: _Runner, run: dict) -> dict:
    program, lang = wb_plan.active(tab["program"]), ws.lang     # a turned-off step neither runs nor is checked
    bad, applied = [], ()
    if not dry_run and r.approval is not None and (r.approval.get("resume") or r.approval.get("edits")):
        program = _resume_plan(tab, r, program)       # continuing a stopped approval, the user's edits: what applied is not run again
    elif dry_run and tab.get("kind") == "proposal" and isinstance(tab.get("proposal"), dict):
        res = proposals.resumable(tab["proposal"], tab.get("program_rev"), program)
        if res is not None:                            # a check of one that can continue checks what is left
            applied = set(_applied(tab, program, res["at"])[0])
            program = [st for st in program if st.get("id") not in applied]
    try:
        app = manager.get_app(tab["session"])
        if app is None:
            raise RuntimeError(_t(lang, "no_session", session=tab["session"]))
        if not program:
            r.log(_t(lang, "empty"), "warn")
        # a path whose block / stream / component an earlier step places is judged when it runs
        made = {k for k, v in wb_plan.created(program).items() if "created" in v}
        pre, verdict = {}, {}                          # tab.check's problems by sid; _unwritable_as by (path, unit, basis)
        for path, sid, unit, basis in _writes(program):
            if (sid, path) in made:
                continue
            first = (path, unit, basis) not in verdict
            if first:
                verdict[(path, unit, basis)] = _unwritable_as(app, path, unit, lang, basis)
            why = verdict[(path, unit, basis)]
            if why:
                pre.setdefault(sid, []).append(wb_plan.note(why[0], why[1], texts=why[2], help=why[3], path=path))
                if first:                              # the run log names the first step writing it
                    bad.append(sid)
                    r.log(why[1], "error", sid)
        r.funcs, r.procs, trees, wrong = _static_problems(program, lang)
        r.trees.update(trees)
        other = "en" if lang == "zh" else "zh"         # the same problems in the other language
        theirs = _static_problems(program, other)[3] if wrong else []
        mine = "zh" if lang == "zh" else "en"
        for i, (sid, why, code, short) in enumerate(wrong):
            bad.append(sid)
            r.log(why, "error", sid)
            twin = theirs[i] if i < len(theirs) and theirs[i][0] == sid and theirs[i][2] == code else None
            texts, help_ = {mine: short}, {mine: why}
            if twin:
                texts[other], help_[other] = twin[3], twin[1]
            pre.setdefault(sid, []).append(wb_plan.note(code, why, texts=texts, help=help_))
        for sid, why in wb_plan.pause_errors(program, lang):   # a your-turn step in a loop (tab.check has it)
            bad.append(sid)
            r.log(why, "error", sid)
        for st in _walk(program):                      # the field a your-turn step asks the user for
            if st["do"] not in wb_plan.PAUSING or (st["id"], st["path"]) in made:
                continue
            node = _node(app, st["path"])
            if node is None:
                why = _t(lang, "not_found", path=st["path"])
                pre.setdefault(st["id"], []).append(wb_plan.note(
                    "not_found", why, texts=_tt("s_not_found", path=st["path"]),
                    help=_tt("not_found", path=st["path"]), path=st["path"]))
                bad.append(st["id"])
                r.log(why, "error", st["id"])
            elif _enterable(node) is False:            # (a mode field may enable it first: said, not refused)
                fs = ws.session(tab["session"]).get("flowsheet") or {}
                help_ = _langs(lambda x, p=st["path"]: _t(x, "yt_off", label=_label_of(fs, p, x)))
                texts = _langs(lambda x, p=st["path"]: _t(x, "s_yt_off", label=_label_of(fs, p, x)))
                pre.setdefault(st["id"], []).append(wb_plan.note("not_enterable", help_[mine], "warn", texts=texts,
                                                                 help=help_, path=st["path"]))
        if not dry_run:                                # the flowsheet check's errors refuse every real
            for sid, why in _struct_errors(manager, tab["session"], app, program, lang):   # run -- an approval's,
                bad.append(sid)                        # a plain tab's, the AI's workbench_run -- before it writes
                r.log(why, "error", sid)
        r.bad = bad
        if bad and not dry_run:
            run["step"] = bad[0]
            raise RuntimeError(_t(lang, "bad_writes", n=len(bad)))
        if r.approval is not None and not dry_run:     # the restore point, then the approved run
            _approval_start(ws, manager, tab, r)
        if dry_run:
            later = {p for _, p in made}
            for p in dict.fromkeys(_paths(program)):
                if p not in later and _node(app, p) is None:
                    hint = _t(lang, "result_hint") if "\\Output\\" in p else ""
                    r.log(_t(lang, "not_found", path=p) + hint, "warn")
            if learn.on():                             # a reminder, not an error
                ids = _no_why(program)
                if ids:
                    r.log(_t(lang, "learn_why", ids=_id_list(ids)), "warn", ids[0])
            tab["check"] = _check_view(ws, manager, tab, app, r, pre, made, applied)
            if tab.get("kind") == "proposal" and isinstance(tab.get("proposal"), dict):
                proposals.checked(tab["proposal"], tab["check"], {"mcp": "ai", "auto": "auto"}.get(r.via, "user"),
                                  time.time())
        r.charts = _live_charts(program)
        await r.top(program)
        run["status"] = "error" if bad else "done"
        if not bad:
            r.unlive()
        if bad:
            run["step"] = bad[0]                       # the window marks the offending block
    except _Stopped:
        run["status"] = "stopped"
        r.log(_t(lang, "stopped"), "warn")
    except _Refused as exc:                            # an approval that could not start
        run["status"] = "error"
        r.error = str(exc)
        r.log(str(exc), "error")
    except Exception as exc:
        run["status"] = "error"
        r.error = str(exc)
        r.log(_t(lang, "error", exc=exc), "error", run.get("step"))
        logger.warning("workbench run failed", exc_info=True)
    finally:
        try:                                           # a Stop or an error puts the inputs back too
            agg = r.aggregate("restore", op="restore")
            if isinstance(agg, recorder.Aggregate):
                agg.begin = None                       # (short, mostly empty: the program's own begin covers it)
            with agg:
                state = r.settle()
        except Exception as exc:
            logger.warning("workbench: putting the model back failed", exc_info=True)
            state = {"kind": "unknown", "restored": [], "kept": [], "failed": [], "run": "skipped",
                     "t": time.time(), "text": _t(lang, "error", exc=exc)}
        if state is not None:
            run["model_state"] = state
            r.log(state["text"], "info" if state["kind"] in ("restored", "kept", "mixed")
                  and state["run"] in ("ok", "skipped") else "warn")
        run["step"] = None if run["status"] == "done" else run.get("step")
        run["finished"] = time.time()
        run["vars"] = r.vars
        ws.stops.discard(tab["id"])
        if not dry_run and (run["tables"] or run.get("opts")):   # survives later checks
            tab["results"] = {"tables": run["tables"], "opts": run.get("opts", []), "finished": run["finished"]}
        if not dry_run and tab.get("results"):          # where the model is now (the Results card says)
            tab["results"]["state"] = state
        if not dry_run:
            ws.jobs.append({"kind": "units", "tab": tab["id"]})
            if tab.get("inspect"):
                ws._ask_inspect(tab, tab["inspect"]["target"], tab["inspect"].get("all", False))
        ws.save()
    return run


def _struct_errors(manager, session: str, app, program, lang: str) -> list[tuple[str, str]]:
    """The flowsheet check's errors of a program that changes the flowsheet (wb_plan.check over
    it as it is now: snapshot, taken_names, the port table) -- [(sid, text)]; nothing read when
    no step changes it. Every real run is refused on them before anything is written or a
    restore point kept (a plain tab's and the AI's workbench_run too, not only an approval --
    a refused ``loop`` connect has already taken the stream's end off in V15)."""
    if not any(st["do"] in wb_plan.STRUCTURE for st in _walk(program)):
        return []
    fs = snapshot(manager, session)
    fs.update(taken_names(app))
    res = wb_plan.check(program, fs, _PORT_TABLE, lang)
    return [(row["id"], p["text"]) for row in res["steps"] for p in row.get("problems") or ()
            if p.get("level") == "error"]


def _check_view(ws: Workspace, manager, tab: dict, app, r: _Runner, pre: dict, made: set,
                applied=()) -> dict | None:
    """tab.check, which only a check (dry run) writes: every step, the
    turned-off ones listed, with what it proposes against what the model holds now
    (wb_plan.view), wb_plan.check's problems (the flowsheet read only when a step changes it:
    snapshot, taken_names), the pre-check's (``pre``, by sid) and a read of a path that is not
    there (warn not_found) -- never a path whose object an earlier step creates (``made``).
    ``rev``: the program version it checked; ``input_t``: the journal's latest input then (the
    window calls it stale once that moves); ``est_cp_s``: what the restore point an approval
    makes first would take (restore_points.plan). The runner's flowsheet lines (_shadow) use
    the same check. ``applied``: the steps a stopped approval applied before it can continue
    (_applied): rows marked ``applied``, not checked. With the feature on it has ``groups``
    and each row ``g`` / ``tech`` / ``obj`` (wb_plan.check ``grouping``), and (feature preview)
    ``shadow``, what its structure steps leave drawn. None when it could not be made (logged)."""
    lang, session, program = ws.lang, tab["session"], tab["program"]
    try:
        runs = [st for st in wb_plan.active(program) if st.get("id") not in applied]
        fs = None
        if any(st["do"] in wb_plan.STRUCTURE for st in _walk(runs)):
            fs = snapshot(manager, session)
            fs.update(taken_names(app))
        res = wb_plan.check(program, fs, _PORT_TABLE, lang, skip=applied, grouping=groups_on(),
                            principles=principle_keys(), preview=preview_on(),
                            ran=set((tab.get("proposal") or {}).get("ran") or ()))
        r.shadow = {row["id"]: row.get("problems") or [] for row in res["steps"]}
        writes, found = {(sid, p) for p, sid, _, _ in _writes(runs)}, {}
        writes |= {(st["id"], st.get("path")) for st in _walk(runs) if st["do"] in wb_plan.PAUSING}   # (pre's)
        for st in _walk(runs):
            for p in wb_plan._paths(st):
                if (st["id"], p) in made or (st["id"], p) in writes:
                    continue
                if p not in found:
                    found[p] = _node(app, p) is not None
                if not found[p]:
                    help_ = _langs(lambda x, p=p: _t(x, "not_found", path=p)
                                   + (_t(x, "result_hint") if "\\Output\\" in p else ""))
                    pre.setdefault(st["id"], []).append(
                        wb_plan.note("not_found", help_["zh" if lang == "zh" else "en"], "warn",
                                     texts=_tt("s_not_found", path=p), help=help_, path=p))

        def held(path):
            node = _node(app, path)
            if node is None:
                return None
            try:
                return _plain(node.Value), (node.UnitString or None)
            except Exception:
                return None
        wb_plan.view(res, program, held, pre)
        prop = tab.get("proposal") if tab.get("kind") == "proposal" else None
        if isinstance(prop, dict) and prop.get("watch"):  # (the results it tags after its run)
            placed = {f"{k}:{str(st[k]).upper()}" for st in _walk(runs) if st["do"] == "place"
                      for k in ("block", "stream") if st.get(k)}
            miss = [w["path"] for w in prop["watch"] if notable.key_of(w["path"]) not in placed
                    and _watch_path(app, w["path"]) is None]
            for p in miss:
                r.log(_t(lang, "watch_missing", path=p) + (_t(lang, "result_hint") if "\\Output\\" in p else ""), "warn")
            if miss:
                res["watch_missing"] = miss
        model = manager.model_id(session) if journal.enabled() else None
        s = (journal.summary(model) if model else None) or {}
        est = restore_points.plan(manager, session, "before-proposal", allow_slow=True).get("est_s")
        res.update(rev=tab.get("program_rev", 0), t=round(time.time(), 3), input_t=s.get("last_input_t"),
                   est_cp_s=est)
        return res
    except Exception:
        logger.warning("workbench: the check view of %s failed", tab.get("id"), exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Ask AI about anything: what a note is about, told in words, and what it led to
# ---------------------------------------------------------------------------

# A note's target by kind: the keys the window may send, each a string of at most _TARGET_STR
# characters, and (_NOTE_KEY) the one it is found by. change: a journal record (``model`` the
# journal's model id; ``label`` the window's words for it; ``obj`` / ``name`` the block or
# stream it is about, ``path`` its field); group: a change group; field: an inspector row;
# stmt: a statement of a tab's program (``sid``; ``tab`` the note's own by default); proposal:
# the AI's proposal tab (a proposal the user sent back -- ``name`` its title).
_NOTE_TARGETS = {"block": ("name",), "stream": ("name",),
                 "change": ("id", "model", "label", "obj", "name", "path"),
                 "group": ("id", "model", "label"),
                 "field": ("path", "label", "obj", "name"),
                 "stmt": ("tab", "sid", "label"),
                 "proposal": ("tab", "name"),
                 "run": ("id", "model", "label"),         # a run record ("Find the cause of this failure and fix it")
                 "object": ("path", "name", "type")}      # a model object (Setup, a reaction, a design spec)
_NOTE_KEY = {"block": "name", "stream": "name", "change": "id", "group": "id", "field": "path", "stmt": "sid",
             "proposal": "tab", "run": "id", "object": "path"}
_TARGET_STR = 200        # characters of one target key
_TARGET_TEXT = 600       # characters of what the AI is told a note is about
_STEP_TEXT = 300         # ... of the statement in it, its why included
_BOUND: dict = {}        # note id -> (group id, model, t): the AI's group naming it wrote records
_BOUND_LOCK = threading.Lock()


def _note_target(tg, tab=None) -> dict | None:
    """A note_add target as the window sent it, kept to its kind's keys, each a string cut to
    _TARGET_STR; ``obj`` only block or stream. None: no target, a kind not in _NOTE_TARGETS,
    or one without the key it is found by."""
    if not isinstance(tg, dict) or tg.get("kind") not in _NOTE_TARGETS:
        return None
    out = {"kind": tg["kind"]}
    for k in _NOTE_TARGETS[out["kind"]]:
        v = tg.get(k)
        if isinstance(v, (str, int, float)) and not isinstance(v, bool) and str(v).strip():
            out[k] = str(v).strip()[:_TARGET_STR]
    if out.get("obj") not in (None, "block", "stream"):
        del out["obj"]
    if out["kind"] == "stmt" and "tab" not in out and tab:
        out["tab"] = tab["id"]
    return out if _NOTE_KEY[out["kind"]] in out else None


def _fit(text: str, n: int) -> str:
    return text if len(text) <= n else text[:max(0, n - 1)] + "…"


def _hhmm(t) -> str:
    return time.strftime("%H:%M", time.localtime(t)) if isinstance(t, (int, float)) else "--:--"


def _target_text(ws: Workspace, manager, session: str, target, note: dict | None = None) -> str:
    """What an Ask AI note is about, for the AI (_announce; workbench_read's ``target_text``):
    one English line of at most _TARGET_TEXT characters, a field named in words with its path.
    A change as the journal measured it, a change group's counts (report.tally, as the window
    counts them) and first lines, a field's value as the window last read it with its last
    change, a program step's statement. No COM; "" without a target."""
    tg = target if isinstance(target, dict) else {}
    kind = tg.get("kind")
    if kind not in _NOTE_TARGETS or not tg.get(_NOTE_KEY[kind]):
        return ""
    sess = ws.state["sessions"].get(session) if session else None
    fs = (sess.get("flowsheet") if isinstance(sess, dict) else None) or {}
    types = {b["name"]: b.get("type") for b in fs.get("blocks") or [] if isinstance(b, dict) and b.get("name")}
    model = tg.get("model") or ((sess or {}).get("model") or {}).get("id")
    if not tg.get("model") and manager is not None and session:
        with contextlib.suppress(Exception):
            model = manager.model_id(session) or model
    try:
        if kind in ("block", "stream"):
            t = types.get(tg["name"]) if kind == "block" else None
            text = f"about {kind} {tg['name']}" + (f" ({t})" if t else "")
        elif kind == "change":
            text = _about_change(model, tg, types)
        elif kind == "group":
            text = _about_group(model, tg, types)
        elif kind == "field":
            text = _about_field(ws, model, session, tg, types, note)
        elif kind == "proposal":
            t, kept = ws.tab(tg["tab"]), ""
            if t is None:                                 # kept in History
                t, kept = ws.arch_tab(tg["tab"])[1], "; kept in History"
            text = proposals.about(t) + kept if t is not None and isinstance(t.get("proposal"), dict) else \
                f"about proposal '{tg.get('name') or '?'}' (tab {tg['tab']}, " + \
                ("its record deleted by the user)" if ws.arch.deleted(tg["tab"]) else "closed)")
        elif kind == "run":
            text = _about_run(sess, model, tg, types)
        elif kind == "object":
            text = f"about model object {tg['path']}" + (f" ({tg['type']})" if tg.get("type") else "")
        else:
            text = _about_step(ws, tg, note)
    except Exception:
        logger.warning("workbench: what a note is about not told", exc_info=True)
        text = f"about {kind} {tg.get('label') or tg[_NOTE_KEY[kind]]}"
    return _fit(text, _TARGET_TEXT)


def _about_run(sess, model, tg, types) -> str:
    """A note about a run (the diagnosis card's "Find the cause of this failure and fix it"): its diagnosis card in
    one line -- the session's own when it is that run's, else one the workbench kept
    (diagnose.recall), else built from the run's record (its blocks and messages) -- and the
    troubleshooting workflow to follow."""
    rid, sess = tg["id"], sess if isinstance(sess, dict) else {}
    d = sess.get("diag") if isinstance(sess.get("diag"), dict) else None
    if d is None or (d.get("run") or {}).get("id") != rid:
        d = diagnose.recall(model, rid) if model else None
    if d is None and model and journal.enabled():
        r = journal.find(model, rid)
        if isinstance(r, dict) and r.get("kind") == "change" and r.get("op") == "run":
            d = diagnose.session_card(sess, r, "en", model, latest=False)
    if not isinstance(d, dict):
        gone = "record not found" if journal.enabled() else "the change journal is off"
        return f"about a run: {tg.get('label') or ''} (record {rid}; {gone})".replace(":  (", ": (")
    what = {"error": "a failed run", "refused": "a refused run", "warn": "a run with warnings"}.get(d.get("level"), "a run")
    text = diagnose.say(d, lambda p: aspen_labels.named(p, types, "path"))
    tail = "; follow the aspen-error-troubleshooting workflow" if d.get("level") in ("error", "refused") else ""
    return _fit(f"about {what}: {text}", _TARGET_TEXT - len(tail)) + tail


def _about_change(model, tg, types) -> str:
    r = journal.find(model, tg["id"]) if model and journal.enabled() else None
    if not isinstance(r, dict) or r.get("kind") == "group":
        what = " ".join(x for x in (tg.get("label"), f"[{tg['path']}]" if tg.get("path") else None) if x)
        gone = "record archived" if journal.enabled() else "the change journal is off"
        return f"about a change: {what or '?'} (record {tg['id']}; {gone})"
    tail = f" (record {r.get('id')})"
    who = "user (Aspen window)" if r.get("actor") == "external" else \
        " ".join(str(x) for x in (r.get("actor"), r.get("tool")) if x) or "someone"
    did = runlog.line(r, 2) if r.get("op") == "run" and r.get("kind") == "change" else \
        journal.what(r, lambda p: aspen_labels.named(p, types, "path"))
    text = f"about a change: {_hhmm(r.get('t'))} {who} {did}"
    why = " ".join(str(r.get("reason") or "").split())
    if why:
        own = "the step's note" if r.get("reason_src") == "why" else \
            "the AI's own reason" if r.get("actor") == "ai" else "reason given"
        text += f" ({own}: {_fit(why, 160)})"
    return _fit(text, _TARGET_TEXT - len(tail)) + tail


def _about_group(model, tg, types) -> str:
    gid, on = tg["id"], bool(model) and journal.enabled()
    p = journal.page(model, limit=200, group=gid) if on else {}
    head = (p.get("groups") or {}).get(gid) or (journal.find(model, gid) if on else None) or {}
    recs = [r for r in p.get("records") or [] if r.get("kind") == "change"]
    title = head.get("title") or tg.get("label")
    who = ", ".join(x for x in (gid, head.get("actor") or (recs[0].get("actor") if recs else None),
                                "started by the AI" if head.get("ai_group") else None) if x)
    text = f"about change group \"{title}\" ({who})" if title else f"about change group ({who})"
    if not recs:
        return text + (": no records found (archived)" if on else ": the change journal is off")
    c, parts = report.tally(recs, skip_actors=()), []
    plural = lambda n, w: f"{n} {w}{'s' * (n != 1)}"          # noqa: E731
    if c["values"]:
        parts.append(plural(c["values"], "value"))
    for key, verb in (("added", "added"), ("removed", "removed")):
        parts += [f"{plural(e['n'], k)} {verb}" + (f" ({', '.join(e['names'])})" if e["names"] else "")
                  for k, e in c[key].items()]
    parts += [plural(n, w) for n, w in ((c["connects"], "connection"), (c["saves"], "save")) if n]
    parts += [plural(n, str(d)) for d, n in c["studies"].items()]
    runs = c["runs"]
    if runs.get("n"):
        last = runs.get("last") or {}
        how = ", ".join([str(last.get("status"))] + [plural(last[k], k[:-1]) for k in ("errors", "warnings")
                                                       if last.get(k)])
        parts.append(plural(runs["n"], "run") + f" ({'last: ' if runs['n'] > 1 else ''}{how})")
    parts += [f"{c[k]} {k}" for k in ("failed", "refused") if c[k]]
    text += ": " + ("at least " if p.get("more") else "") + (", ".join(parts) or "no changes")
    named = lambda x: aspen_labels.named(x, types, "path")   # noqa: E731
    for r in reversed(recs):                                  # the first lines, as many as fit
        ln = "; " + journal.line(r, named)
        if len(text) + len(ln) > _TARGET_TEXT:
            return text + "; …"
        text += ln
    return text


def _about_field(ws: Workspace, model, session, tg, types, note) -> str:
    path, obj, name = tg["path"], tg.get("obj"), tg.get("name")
    seg = [s.lower() for s in path.split("\\")[1:4]]              # (Aspen paths: any case)
    if not (obj and name) and len(seg) == 3 and seg[0] == "data" and seg[1] in ("blocks", "streams"):
        obj, name = ("block" if seg[1] == "blocks" else "stream"), path.split("\\")[3]
    words = aspen_labels.say(path, types.get(name) if obj == "block" else None, "en", "full")
    text = f"about the field {words or tg.get('label') or path} [{path}]"
    val, key = None, path.lower()
    mine = ws.tab((note or {}).get("tab"))
    for t in ([mine] if mine else []) + ws.tabs_for(session):      # an inspector showing it, the note's first
        row = next((r for r in (t.get("inspect") or {}).get("rows") or () if str(r.get("path")).lower() == key), None)
        if row is not None:
            val = {"value": row.get("value"), "unit": row.get("unit")}
            break
    if val is None and obj == "stream":                             # a stream label the flowsheet shows
        shown = (((ws.state["sessions"].get(session) or {}).get("values") or {}).get(name)) or {}
        v = next((shown.get(k) for k, rel in _STREAM_VALUES if key.endswith("\\" + rel.lower())), None)
        val = {"value": v[0], "unit": v[1]} if isinstance(v, list) and len(v) == 2 else None
    last = None
    if obj and name and model and journal.enabled():
        last = (journal.latest_by_path(model, (obj, name), per=1, scan=1000).get(key) or [None])[0]
    if val is None and last is not None:
        text += f" = {journal._val(last.get('after'))} (as last recorded)"
    elif val is not None:
        text += f" = {journal._val(val)} (as the window last read it)"
    if last is not None:
        text += f"; last changed by {last.get('actor')} {_hhmm(last.get('t'))}, was {journal._val(last.get('before'))}"
    return text


def _about_step(ws: Workspace, tg, note) -> str:
    tid = tg.get("tab") or (note or {}).get("tab")
    tab = ws.tab(tid) or ws.arch_tab(tid)[1]                  # (a proposal kept in History)
    steps = list(_walk(tab.get("program") or [])) if tab else []
    i = next((k for k, st in enumerate(steps) if st.get("id") == tg["sid"]), None)
    where = f"tab '{tab['title']}'" if tab else "a tab no longer open"
    if i is None:
        return f"about a program step no longer in {where} ({tg['sid']})" + (f": {tg['label']}" if tg.get("label") else "")
    st = steps[i]
    body = {"do": st.get("do"), **({"why": st["why"]} if st.get("why") else {}),
            **{k: v for k, v in st.items() if k not in ("id", "do", "why")}}
    return f"about step {i + 1} of {len(steps)} in {where} ({tg['sid']}): " \
           + _fit(json.dumps(body, ensure_ascii=False, default=str), _STEP_TEXT)


def _note_heads(model: str, recs) -> None:
    """journal.listen: the AI's change group naming an Ask AI note had records written (its
    header comes with the first) -- the note's newest effect. Any thread: kept in _BOUND, put
    on the note by ``_bind`` on the loop."""
    heads = [r for r in recs if r.get("kind") == "group" and r.get("note") and r.get("actor") == "ai" and r.get("id")]
    if not heads:
        return
    with _BOUND_LOCK:
        for r in heads:
            old, t = _BOUND.get(str(r["note"])), float(r.get("t") or 0)
            if old is None or t >= old[2]:
                _BOUND[str(r["note"])] = (r["id"], model, t)
        while len(_BOUND) > 64:
            _BOUND.pop(next(iter(_BOUND)))


journal.listen(_note_heads)


def _bind(ws: Workspace) -> bool:
    """Put the groups _note_heads found on their notes: ``group`` (the id the window jumps to)
    and ``group_model`` (the journal it is in). Returns whether a note changed."""
    if not _BOUND:
        return False
    with _BOUND_LOCK:
        bound = dict(_BOUND)
        _BOUND.clear()
    changed = False
    for sess in ws.state["sessions"].values():
        for n in (sess.get("notes") or []) if isinstance(sess, dict) else ():
            b = bound.get(n.get("id"))
            if b and (n.get("group"), n.get("group_model")) != b[:2]:
                n["group"], n["group_model"] = b[0], b[1]
                changed = True
    return changed


# ---------------------------------------------------------------------------
# Sync loop: serves the window while the server lives
# ---------------------------------------------------------------------------

# Set by the server when its client can take pushed messages (Claude Code channels): an
# async callable(content, meta) that puts a message into the running session, so an Ask AI
# request reaches the AI when the user sends it, not when they next mention the workbench.
channel = None
# Whether the client is known to deliver those messages. Pushing succeeds either way (a
# client without channels drops them), so only an explicit opt-in lets the window say that
# a request reaches the AI at once; without it the window says what to tell the AI.
listening = False
# Whether ``listening`` was checked (the Codex bridge) rather than claimed (ASPEN_MCP_CHANNELS,
# which may be left set while Claude Code runs without channels): a claim still gets the
# channel hint, and the window still waits only a while for the AI to take a request.
listening_checked = False
_ASKED_MAX = 160          # characters of the question a pick answers, quoted in its push


def _asked_text(ws: Workspace, session, note_id) -> str:
    """The question a pick answers, as the AI asked it (the answer's first characters)."""
    notes = (ws.state["sessions"].get(str(session or "")) or {}).get("notes") or []
    asked = next((n for n in notes if n.get("id") == note_id), None)
    q = " ".join(str((asked or {}).get("reply") or "").split())
    return f'"{q[:_ASKED_MAX]}{"…" if len(q) > _ASKED_MAX else ""}"' if q else "(no longer there)"


async def _announce(ws: Workspace, manager=None) -> bool:
    """Push the new Ask AI requests to the AI. One the channel could not take -- it answers
    False: no client session known yet, as after a /mcp reconnect -- waits for the next pass;
    the next tool call makes the session known (tools/intercept.py). One it took is the
    request the AI's next changes are for (journal.GROUPS.note_seen). One about a change,
    group, field or step says what that is on a second line (_target_text).

    Each note says how its push went, for the window's waiting line (app-wait.js): ``delivered``
    (the channel took it and the client is said to deliver: ``listening``, a claim unless
    ``listening_checked`` -- the window waits a while for the AI, then says to tell it), ``pushed`` (the
    channel took it but the client may drop it -- Claude Code without channels takes and drops
    a push, which the server cannot see: the window waits a moment for the AI to pick it up,
    then says to tell the AI) or ``undelivered`` (when it could not: kept for the next pass, or
    an error). Returns whether a note's flag changed (the state is saved then)."""
    asks, ws.asks = ws.asks, []
    if channel is None:
        return False
    kept, changed = [], False
    for a in asks:
        note, tab = a["note"], a.get("tab")
        target = note.get("target") if isinstance(note.get("target"), dict) else {}
        kind = target.get("kind")
        where = f"{kind or ''} {target.get(_NOTE_KEY.get(kind, 'name'), '')}".strip()
        meta = {"note_id": note["id"], "session": str(a.get("session") or ""),
                "tab": tab["id"] if tab else "", "target": where}
        about = "" if kind in (None, "block", "stream") else _target_text(ws, manager, meta["session"], target, note)
        text = (f"Ask AI from the Aspen Workbench (session {meta['session']}"
                + (f", {where}" if where and not about else "") + f"): {note.get('text', '')}"
                + (f"\nThe user asks this {about}" if about else ""))
        if note.get("event"):                            # the window telling, not the user asking
            text = (f"Aspen Workbench event (session {meta['session']}), not a request from the user: "
                    f"{note.get('text', '')}\nGo on with the workflow (aspen-process-workflow skill), then close "
                    f"it with workbench_edit(note_replies=[{{\"id\": \"{note['id']}\", \"done\": true}}]).")
            meta["event"] = str(note["event"])
        elif note.get("answer_to"):                      # a pick from the choices of an answer
            meta["answer_to"] = str(note["answer_to"])
            text += (f"\nThis is the user's pick ({'; '.join(note.get('picked') or [])}) from the choices "
                     f"you gave on request {note['answer_to']}: {_asked_text(ws, a.get('session'), note['answer_to'])}")
        pt = (ws.tab(target.get("tab")) or ws.arch_tab(target.get("tab"))[1]) \
            if kind == "proposal" and "comment" in note else None
        if pt is not None and isinstance(pt.get("proposal"), dict):    # the user sent a proposal back
            meta["proposal"] = pt["proposal"].get("id")
            text = (f"Ask AI from the Aspen Workbench (session {meta['session']}): "
                    f"{proposals.pushed(pt, note, ws.root_of(pt))}")
        if not note.get("event") and "note_replies" not in text:   # how to answer travels with the request
            text += (f"\nAnswer in the window: read its tab with workbench_read, then "
                     f"workbench_edit(note_replies=[{{\"id\": \"{note['id']}\", \"reply\": ...}}]) in the "
                     f"request's language; to have the user pick, add \"choices\".")
        try:
            ok = await channel(text, meta) is not False
            if not ok:
                kept.append(a)
            else:
                journal.GROUPS.note_seen(note["id"], note.get("text"), a.get("session"))
        except Exception:
            ok = False
            logger.warning("workbench: could not announce an Ask AI request", exc_info=True)
        if ok:
            note["delivered" if listening else "pushed"] = round(time.time(), 3)
            note.pop("undelivered", None)
            changed = True
        elif not note.get("undelivered"):
            note["undelivered"] = round(time.time(), 3)
            changed = True
    later = {a["note"]["id"] for a in ws.asks}          # (edited again meanwhile: the newer one)
    ws.asks[:0] = [a for i, a in {a["note"]["id"]: a for a in kept}.items() if i not in later]
    return changed


# plugin/scripts/workbench-asks.ps1 (the Stop and UserPromptSubmit hooks) hands a waiting
# request to the AI when the client takes no pushed message -- Codex, or Claude Code without
# channels -- and records it here: {note_id: time}. The request then counts as delivered.
HANDED = "asks-handed.json"


def _handed(ws: Workspace) -> bool:
    """Requests a hook handed to the AI: delivered (the window's waiting line), the request the
    AI's next changes are for, and no longer pushed. Returns whether a note changed."""
    path = ws.state_path.parent / HANDED
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return False
    if mtime == getattr(ws, "_handed_mtime", None):
        return False
    ws._handed_mtime = mtime
    try:
        handed = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False
    if not isinstance(handed, dict):
        return False
    changed = False
    for name, sess in (ws.state.get("sessions") or {}).items():
        for n in (sess.get("notes") or []) if isinstance(sess, dict) else ():
            t = handed.get(n.get("id"))
            if not isinstance(t, (int, float)) or n.get("status") != "open" or n.get("delivered"):
                continue
            n["delivered"] = n["handed"] = round(float(t), 3)     # handed: the client needed a hook
            n.pop("undelivered", None)
            journal.GROUPS.note_seen(n["id"], n.get("text"), name)
            changed = True
    ws.asks = [a for a in ws.asks if a["note"].get("id") not in handed]
    return changed


# The same hooks record when the AI's turn starts (UserPromptSubmit, or a Stop that hands it
# requests) and ends (Stop), in the session whose server serves the window: {start, begin (the
# turn's first start since its last stop), stop, client} (and the hook's own cache of which client
# sessions are that one). The window shows "AI is thinking…" while the turn runs, in its header and on
# the chat's waiting line, from one state (app-conn.js, app-wait.js).
TURN = "ai_turn.json"


def _turn(ws: Workspace) -> bool:
    """The AI's turn as the hooks last recorded it for this server (the file's ``owner``), into
    state ``ai_turn``. Returns whether it changed. No file, or one of another server (an older
    plugin, a client without the hooks, a turn recorded before a reconnect): no ``ai_turn``."""
    path = ws.state_path.parent / TURN
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = None
    if mtime is not None and mtime == getattr(ws, "_turn_mtime", None):
        return False
    turn = {}
    if mtime is not None:
        try:
            got = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return False                                  # (being replaced: the next beat reads it)
        if isinstance(got, dict) and got.get("owner") == os.getpid():
            turn = {k: round(float(got[k]), 3) for k in ("start", "begin", "stop")
                    if isinstance(got.get(k), (int, float)) and not isinstance(got.get(k), bool)}
            if turn and isinstance(got.get("client"), str):
                turn["client"] = got["client"][:20]
    ws._turn_mtime = mtime
    if turn == (ws.state.get("ai_turn") or {}):
        return False
    if turn:
        ws.state["ai_turn"] = turn
    else:
        ws.state.pop("ai_turn", None)
    return True


def _serve(ws: Workspace, manager) -> None:
    """Start the sync loop unless it runs, and the heartbeat beacon beside it: the thread
    writes the heartbeat for as long as the loop task lives, also while a call holds the loop."""
    if ws.task is not None and not ws.task.done():
        return
    task = ws.task = asyncio.get_running_loop().create_task(_sync_loop(ws, manager))
    beat = ws.dir / "heartbeat"
    activity.beacon(beat)
    task.add_done_callback(lambda t: activity.stop_beacon(beat) if ws.task is t else None)


async def _sync_loop(ws: Workspace, manager) -> None:
    last_beat = 0.0
    if not _claim():                                      # one server serves the window
        logger.warning("workbench: the window is served by another server (%s)", _owner_other())
        return
    ws.brake_dirty = True                                 # the brakes are live now: the window shows it
    try:
        while True:
            activity.tick()
            ws.drain()
            ws.late_now()
            pushed = await _announce(ws, manager) if ws.asks else False
            changed = pushed | ws.work(manager) | ws.start_runs(manager) | _bind(ws)
            changed |= ws.watch(manager)                  # Aspen-window edits, the user back
            now = time.time()
            if now - last_beat >= _BEAT_S:
                ws.beat()
                last_beat = now
                changed |= ws.check_sessions(manager) | _handed(ws) | _turn(ws)
                ws.brake_tick(manager)
                if _owner_other() is not None:            # another server took the window over
                    return
            _stuck_left(ws)
            if ws.says or ws.brake.cards:
                await _tell(ws, manager)
            if changed or ws.brake_dirty:
                ws.save()
            if ws.closed and not ws.runs and not ws.window_alive():
                return
            await asyncio.sleep(ws.nap())
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.error("workbench sync loop died", exc_info=True)
    finally:
        _release()


# ---------------------------------------------------------------------------
# The brakes: who owns the window, the gate's hooks, the stuck watch, what the AI is told
# ---------------------------------------------------------------------------

_CLIENT = {"name": None}          # the MCP client's clientInfo.name (server.py's _hold): how long a call is held
_MGR = {"get": None}              # () -> the AspenPlusManager (wire_brakes)
_STUCK: list = []                 # stuck-watch triggers not acted on yet: (call, model, session, trigger, monotonic)
_STUCK_LOCK = threading.Lock()


def wire_brakes(get_manager) -> None:
    """server.py, once: the manager getter; the stuck watch over every journal append
    (``on_records``); the tab a workbench_run call runs, for its card's program condition
    (tools/brake_effects.py)."""
    _MGR["get"] = get_manager
    journal.listen(on_records)
    brake_effects.configure(tab_of=_tab_of)


def _manager():
    try:
        return _MGR["get"]() if _MGR["get"] is not None else None
    except Exception:
        return None


def _owner() -> dict | None:
    """owner.json: the server whose sync loop serves the window ({"pid", "srv", "root", "t"})."""
    try:
        d = json.loads((_ROOT / _OWNER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and isinstance(d.get("pid"), int) else None


def _owner_other() -> dict | None:
    """owner.json when it names another server that is alive, else None."""
    o = _owner()
    return o if o is not None and o["pid"] != os.getpid() and _pid_alive(o["pid"]) else None


def _claim() -> bool:
    """The sync loop's start: owner.json names this process unless another live server owns
    the window (False). A file that cannot be written leaves the brakes off, the window served."""
    if _owner_other() is not None:
        return False
    path = _ROOT / _OWNER
    tmp = path.with_name(f"{_OWNER}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps({"pid": os.getpid(), "srv": journal.srv(), "root": str(_PKG),
                                   "t": round(time.time(), 3), **({"standalone": True} if STANDALONE else {})}),
                       encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        logger.warning("workbench: %s not written", path, exc_info=True)
    return True


def _release() -> None:
    """The sync loop ended: owner.json no longer names this process."""
    if (_owner() or {}).get("pid") == os.getpid():
        try:
            (_ROOT / _OWNER).unlink()
        except OSError:
            pass


def _refused_owner(o: dict) -> str:
    return (f"Error: the workbench window is served by another Aspen server (pid {o.get('pid')}, running from "
            f"{o.get('root') or o.get('srv') or '?'}). Use that server's tools, or close its window first.")


def _served(ws) -> bool:
    """This process has the window in hand: it has served one (its sync loop started) or one is open."""
    return ws is not None and (ws.task is not None or ws.window_alive())


def gate():
    """tools/intercept.py's hooks.gate: the workspace's Brake; None -- nothing added -- without a
    workspace, or with one that never served a window while none is open (batch scripts or
    another server, plain MCP: the calls behave as without a workbench)."""
    ws = _WS
    return ws.brake if _served(ws) else None


def late_apply(brk, cid, p):
    """hooks.late: a workbench_run card approved after its call is its tab queued as the
    window's Run (Workspace.queue_proposal); None for any other call (intercept replays it)."""
    ws = _WS
    if ws is None or brk is not ws.brake or p.name != "workbench_run":
        return None
    return ws.queue_proposal(cid, p)


def note_client(name) -> None:
    """server.py's _hold: the MCP client's name (how long it lets a call be held)."""
    if name and name != _CLIENT["name"]:
        _CLIENT["name"] = name
        ws = _WS
        if ws is not None and ws.brake.client != name:
            ws.brake.client, ws.brake_dirty = name, True


def _tab_of(kw) -> dict | None:
    """brake_effects' tab_of: the tab a workbench_run call runs (its program's saves)."""
    ws, kw = _WS, kw or {}
    return None if ws is None else _resolve(ws, kw.get("session_name"), kw.get("tab"))[0]


def on_records(model, recs) -> None:
    """journal.listen (any thread, no I/O): the stuck watch -- the records into tools/stuck.py while this
    server has the window in hand; a trigger is acted on at the end of the AI call whose
    records made it (``gate_done``), else on the sync loop's next pass (``_stuck_left``)."""
    ws = _WS
    if not brake.enabled() or not _served(ws):
        return
    trigs = stuck.check(model, recs)
    if not trigs:
        return
    recs = [r for r in ([recs] if isinstance(recs, dict) else recs or ()) if isinstance(r, dict)]
    ids = {r.get("id"): r for r in recs}
    with _STUCK_LOCK:
        for tr in trigs:
            r = ids.get((tr.get("ids") or [None])[-1]) or (recs[-1] if recs else {})
            _STUCK.append((r.get("call"), model, r.get("session"), tr, time.monotonic()))
        del _STUCK[:-16]


def _with_evidence(detail: dict, ids: list, group) -> dict:
    """A stuck pause's detail with its evidence -- ``ids`` newest last, ``group`` -- as much as fits
    _STUCK_DETAIL bytes (brake keeps no more): every id and the group; else every id; else the
    newest ids that fit. A detail too big without them is left as it is."""
    g = group.get("id") if isinstance(group, dict) else group
    size = lambda d: len(json.dumps(d, ensure_ascii=False, default=str).encode("utf-8"))  # noqa: E731
    tries = [dict(detail, group=g, **({"ids": ids} if ids else {}))] if isinstance(g, str) and g else []
    tries += [dict(detail, ids=ids[k:]) for k in range(len(ids))]
    return next((d for d in tries if size(d) <= _STUCK_DETAIL), detail)


def _stuck_take(pred) -> list:
    with _STUCK_LOCK:
        out = [x for x in _STUCK if pred(x)]
        _STUCK[:] = [x for x in _STUCK if not pred(x)]
    return out


def gate_done(name, session, call, res, kw=None):
    """hooks.gate_done: a changing AI call ran. A row it inserted or took back is counted as the
    AI's own (brake_effects.note_rows: taking one back asks no card). A stuck-watch trigger its
    records made pauses the AI (tools/brake.py; only noted while the brakes are not live), and
    its answer ends saying so."""
    if kw is not None:
        try:
            if name in ("insert_row", "remove_row"):
                brake_effects.note_rows(name, kw, res)
        except Exception:
            logger.warning("workbench: %s not noted", name, exc_info=True)
    if not _STUCK or _WS is None:
        return None
    mine = _stuck_take(lambda x: x[0] == call)
    return _WS.stuck_pause(*mine[-1][:4]) if mine else None


def _stuck_left(ws: Workspace) -> None:
    """Triggers no AI call's end took (it raised): acted on here, with no answer to say it in."""
    if _STUCK:
        for call, model, session, tr, _ in _stuck_take(lambda x: time.monotonic() - x[4] > 2.0):
            ws.stuck_pause(call, model, session, tr, told=False)


def _brake_read(ws: Workspace) -> dict:
    """workbench_read's ``brake``: the mode, the pause (why, when it was automatic), the latest
    cards, the stuck watch's thresholds -- how a client without channels learns what the brakes did."""
    b = ws.brake
    p = b.paused
    return {"mode": b.mode, "live": b.live(),
            "paused": None if not p else {"since": p.get("since"), "by": p.get("by"), "rule": p.get("rule"),
                                          "why": brake.rule_text(p.get("rule"), p.get("detail"))
                                          if p.get("by") == "stuck" else None},
            "cards": [{"id": c["id"], "tool": c["tool"], "target": c.get("target"), "session": c.get("session"),
                       "status": c["status"], "how": (c.get("decided") or {}).get("how"),
                       "comment": (c.get("decided") or {}).get("comment"), "t": c.get("t")} for c in b.cards[-5:]],
            "stuck": {**{k: b.stuck[k] for k in brake.STUCK}, "on": dict(b.stuck["on"])}}


def _since_lines(manager, since) -> list[str]:
    """What others changed in the open models after ``since`` (the brief's words), newest last."""
    found = []
    if manager is None or not since or not journal.enabled():
        return found
    for s in manager.session_names():
        model = manager.model_id(s)
        pg = journal.page(model, limit=brief.READ, after=since) if model else {}
        recs = pg.get("records") or []
        if recs:
            found += brief._items(list(reversed(recs)), pg.get("groups") or {}, block_types(s))
    found.sort(key=lambda x: x[0])
    return [f"- {brake.at(t)} {text}" for t, text in found if t]


def _tell_text(ws: Workspace, manager, s: dict) -> tuple[str, dict] | None:
    b, what = ws.brake, s.get("what")
    if what == "pause":
        return (f"The user paused you in the Aspen Workbench at {brake.at(s['t'])}. Your changes to the model "
                "now wait for them and are not applied; reads still work. Stop changing the model and end your "
                "turn; the user resumes you from the workbench.", {"brake": "pause"})
    if what == "resume":
        lines = _since_lines(manager, s.get("since"))
        more = len(lines) - _TELL_LINES
        body = ("Changes made meanwhile (not by you):\n" + "\n".join(lines[-_TELL_LINES:])
                + (f"\n- ({more} earlier not shown: workbench_read lists them)" if more > 0 else "")
                if lines else "Nothing was changed meanwhile.")
        note = f"\nTheir note: \"{s['note']}\"" if s.get("note") else ""
        return (f"The user resumed you in the Aspen Workbench (paused {brake.at(s.get('since'))}-{brake.at(s['t'])}). "
                + body + note, {"brake": "resume"})
    c = b.get(s.get("card"))
    if c is None:
        return None
    w = brake.what(c.get("tool"), c.get("target"), c.get("session"))
    meta = {"brake": "card", "card": str(c["id"]), "session": str(c.get("session") or "")}
    if c["status"] == "declined":
        comment = (c.get("decided") or {}).get("comment")
        return (f"The user declined your proposal #{c['id']} ({w}) in the Aspen Workbench"
                + (f". Their note: \"{comment}\"" if comment else "") + ". Do not retry it.", meta)
    res = (c.get("result") or {}).get("text") or ""
    how = "applied" if c["status"] == "applied" else "tried to apply, and it failed,"
    return (f"The user {how} your proposal #{c['id']} ({w}) in the Aspen Workbench after your call had ended; it "
            f"ran as theirs. Its answer: {res}", meta)


async def _tell(ws: Workspace, manager) -> None:
    """Tell the AI on the channel what the brakes did that no answer of its own carries: the
    user paused or resumed it (with what changed meanwhile), decided a card after its call's
    wait -- declined it, or applied it (once it ran). Kept while no client session is known
    (at most _TELL_MAX); dropped with no channel -- workbench_read's ``brake`` and the brief
    carry it too."""
    for c in ws.brake.cards:
        if c["id"] not in ws.told and c["status"] in ("applied", "failed", "declined"):
            ws.told.add(c["id"])
            if (c.get("decided") or {}).get("how") == "late":
                ws.says.append({"what": "card", "card": c["id"]})
    if len(ws.told) > 4 * brake.CARDS_MAX:
        ws.told &= {c["id"] for c in ws.brake.cards}
    if not ws.says:
        return
    says, ws.says, kept = ws.says, [], []
    if channel is None:
        return
    for s in says:
        try:
            msg = _tell_text(ws, manager, s)
            if msg is not None and await channel(*msg) is False:
                kept.append(s)
        except Exception:
            logger.warning("workbench: could not tell the AI about the brakes (%s)", s.get("what"), exc_info=True)
    ws.says[:0] = kept[-_TELL_MAX:]


# ---------------------------------------------------------------------------
# Auto refresh and reconnect: every MCP call ends in after_tool
# ---------------------------------------------------------------------------

def _computing(session: str) -> bool:
    """Aspen works for another caller on ``session``: a program or an optimize holds it, or a
    call in flight is inside Aspen (tools/activity.py). An auto refresh's reads wait for it."""
    if activity.holder(session) is not None:
        return True
    return _call_in_aspen(session)


def _call_in_aspen(session: str) -> bool:
    """A call in flight is inside Aspen on ``session`` (tools/activity.py)."""
    return any(a.get("phase") == "aspen" and a.get("session") in (None, session)
               for a in activity.snapshot()["act"])


def _served_elsewhere() -> bool:
    """Another live server beats the window's heartbeat: another registration of this server, or
    the process a /mcp reconnect replaces, until it has exited. An old-style heartbeat (a number)
    names no process: fresh, it is taken to be alive."""
    beat = _ROOT / "heartbeat"
    try:
        if time.time() - beat.stat().st_mtime >= _STALE_S:
            return False
        hb = json.loads(beat.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(hb, dict):
        return True
    pid = hb.get("pid")
    return isinstance(pid, int) and pid != os.getpid() and _pid_alive(pid)


_NO_WINDOW = {"key": None, "until": 0.0}                # the last "nothing to serve", for _LIVE_S


def _window_up(fresh: bool = False) -> bool:
    """A window is open for this server to serve: window.pid names a live process and no other
    server serves it. No window.pid costs one stat; a "no" for the same file is kept _LIVE_S."""
    pid_file = _ROOT / "window.pid"
    try:
        st = pid_file.stat()
    except OSError:
        return False
    key = (st.st_mtime_ns, st.st_size)
    if not fresh and _NO_WINDOW["key"] == key and time.monotonic() < _NO_WINDOW["until"]:
        return False
    try:
        up = _pid_alive(int(pid_file.read_text(encoding="utf-8"))) and not _served_elsewhere() \
            and _owner_other() is None
    except (OSError, ValueError):
        up = False
    if not up:
        _NO_WINDOW.update(key=key, until=time.monotonic() + _LIVE_S)
    return up


def ensure_live(manager, fresh: bool = False) -> Workspace | None:
    """The workspace, served (sync loop and heartbeat), whenever a window is open: a new server
    process -- a /mcp reconnect -- takes over the window the old one left on its first tool
    call, or at start through the lifespan, without open_workbench; the sessions it has that
    a tab shows are re-read. None, making no workspace and writing nothing, when no window
    is open. ``fresh``: look again even if "no window" was seen less than _LIVE_S ago."""
    ws = _WS
    if ws is not None and ws.task is not None and not ws.task.done():
        return ws
    try:
        asyncio.get_running_loop()
    except RuntimeError:                                  # (a direct call: no loop to serve from)
        return None
    if not _window_up(fresh):
        return None
    made = ws is None
    ws = _workspace()
    _serve(ws, manager)
    for name in manager.session_names():
        if ws.tabs_for(name):
            ws.later(name, "topology")
    if made:
        _strings(ws)
        ws.save()                                         # the window: this server's catalog
    return ws


def _strings(ws: Workspace) -> None:
    """Make sure the field names of the user's Aspen are extracted (aspen_strings.ensure: a
    background thread the first time, no COM, returns at once) and put where that stands in
    the catalog."""
    try:
        ws.state.setdefault("catalog", {})["strings"] = _strings_state(aspen_strings.ensure())
    except Exception:
        logger.warning("workbench: the Aspen strings check failed", exc_info=True)


def after_tool(manager, session: str | None, refresh: str | None) -> None:
    """After every MCP tool call (tools/intercept.py, hooks.after): serve an open window
    (ensure_live), then have it re-read what the call changed -- ``refresh`` topology |
    results | values, None: nothing -- once the burst of calls is over (Workspace.later). A
    call that names no session (open, create, close) refreshes every session a tab shows.
    First the change group an Ask AI note led to goes on the note (_bind)."""
    if _WS is not None and _bind(_WS):
        _WS.save()
    ws = ensure_live(manager)
    if ws is None or not refresh:
        return
    for name in [session] if session else list(ws.state["sessions"]):
        if ws.tabs_for(name):
            ws.later(name, refresh)


async def reconnect(manager, tries: int = 10, every: float = 1.0) -> None:
    """At server start (server.py's lifespan): serve a window left open by the previous server
    before any tool call. While that server is still going away, look again, ~10 s at most."""
    try:
        for _ in range(tries):
            if ensure_live(manager, fresh=True) is not None or not (_ROOT / "window.pid").exists():
                return
            await asyncio.sleep(every)
    except Exception:
        logger.warning("workbench: taking the open window back failed", exc_info=True)


# ---------------------------------------------------------------------------
# MCP tool entry points
# ---------------------------------------------------------------------------

def _resolve(ws: Workspace, session_name: str | None, tab: str | None) -> tuple[dict | None, str | None]:
    """The loaded tab a tool call means: ``tab`` (id or title), else the active tab of
    ``session_name``, else the tab of the model it holds, else that session's first
    tab, else the active tab. A proposal kept in History, or deleted by the user, is named so."""
    tabs, active = ws.state["tabs"], ws.tab(ws.state.get("active"))
    listing = ", ".join(f"{t['title']} ({t['id']}, {t['session']})" for t in tabs) or "none"
    if tab:
        hit = ws.tab(tab) or next((t for t in tabs if t["title"] == tab), None)
        if hit is None:
            return None, _not_loaded(ws, tab) or f"Error: no tab '{tab}'. Tabs: {listing}."
        if session_name and hit["session"] != session_name:
            return None, f"Error: tab '{tab}' is on session '{hit['session']}', not '{session_name}'."
        return hit, None
    if session_name:
        if active and active["session"] == session_name and not ws.stale(active):
            return active, None
        hit = ws.root_for(session_name) or next(iter(ws.tabs_for(session_name)), None)
        if hit is None:
            return None, (f"Error: no workbench tab for session '{session_name}'. "
                          f"open_workbench('{session_name}') creates one.")
        return hit, None
    if active or tabs:
        return active or tabs[0], None
    return None, "Error: the workbench has no tabs. Call open_workbench(session_name) first."


def _not_loaded(ws: Workspace, tid) -> str:
    """Why tab id ``tid`` is not loaded: a proposal kept in History, or one whose record
    the user deleted; "" for neither."""
    e = ws.arch.entry(tid)
    if e is not None:
        return (f"Error: tab '{tid}' is the proposal '{e.get('title')}' kept in History ({e.get('status')}), not open "
                f"in the window. workbench_read(tab='{tid}') reads it; workbench_edit(tab='{tid}') with a revision "
                "reopens it.")
    if ws.arch.deleted(tid):
        return f"Error: the user deleted proposal record {tid}; write a new proposal."
    return ""


def _tabs_view(ws: Workspace) -> list[dict]:
    """workbench_read's ``tabs``: the model tabs, each with its sub-tabs (``children``)."""
    def one(x):
        out = {"id": x["id"], "title": x["title"], "session": x["session"], "run": (x.get("run") or {}).get("status")}
        if x.get("kind"):
            out["kind"] = x["kind"]
        if isinstance(x.get("proposal"), dict):
            out["status"] = x["proposal"].get("status")
        return out
    roots = [t for t in ws.state["tabs"] if t.get("kind") == "model"]
    view = [dict(one(r), **({"stale": True} if ws.stale(r) else {}),
                 children=[one(c) for c in ws.children(r)]) for r in roots]
    seen = {x["id"] for r in roots for x in ws.family(r)}
    return view + [one(t) for t in ws.state["tabs"] if t["id"] not in seen]


def session_of(tool: str, args: dict) -> str | None:
    """The session a workbench call that names none works on, its tab's (tools/intercept.py:
    what the call waits for and the activity bar shows); None for any other call."""
    if not tool.startswith("workbench_"):
        return None
    t, _ = _resolve(_workspace(), None, args.get("tab"))
    return t["session"] if t else None


def refuse_call(tool: str, args: dict) -> str | None:
    """tools/intercept.py's Hooks.refuse: the AI's real run of a proposal tab is refused before
    the brakes, whatever the mode -- only the user runs a proposal, and that is the approval;
    its check (dry run) passes. None for any other call. No COM."""
    if tool != "workbench_run" or (args or {}).get("dry_run", True) or _WS is None:
        return None
    t, _ = _resolve(_WS, args.get("session_name"), args.get("tab"))
    return proposals.refusal(t) if t is not None and t.get("kind") == "proposal" else None


def current_note() -> dict | None:
    """The Ask AI note the AI's changes are for (tools/intercept.py's hooks.note_state):
    the one last pushed to it or shown by workbench_read, while the window still has it. One
    the user deleted, or one answered done, ends its change group."""
    n, ws = journal.GROUPS.note, _WS
    if n is None or ws is None:
        return n
    hit = next((x for sess in ws.state["sessions"].values() if isinstance(sess, dict)
                for x in sess.get("notes") or [] if x.get("id") == n["id"]), None)
    if hit is not None and hit.get("status") == "open":
        return n
    journal.GROUPS.close(n["id"])
    return None


async def open_workbench(manager, session_name: str, new_tab: bool = False,
                         title: str | None = None, lang: str | None = None) -> str:
    return open_workbench_now(manager, session_name, new_tab=new_tab, title=title, lang=lang)


def open_workbench_now(manager, session_name: str, new_tab: bool = False,
                       title: str | None = None, lang: str | None = None) -> str:
    """open_workbench's work (no await in it): called on the event loop's thread, whose running
    loop the sync loop's task goes on."""
    app = manager.get_app(session_name)
    if app is None:
        return (f"Error: no active Aspen session '{session_name}' in this server. Open it with "
                f"open_aspen_plus from the same server that provides open_workbench: a session "
                f"opened by another Aspen server lives in that server's process.")
    other = _owner_other()                    # one server serves the window (its brakes)
    if other is not None:
        return _refused_owner(other)
    ws = _workspace()
    ws.drain()
    if lang in _LANGS:
        ws.state["lang"] = lang
    sess = ws.session(session_name)
    sess["mode"] = "workbench"                # opening it is choosing to work there (session_mode)
    sess["flowsheet"] = snapshot(manager, session_name)
    _restore_layouts(sess)
    ws.note_model(manager, session_name)
    ws.refresh_results(app, session_name)
    # one tab per model -- focused, else made (with its History and chat); new_tab adds a
    # program sub-tab in it, never a second model tab
    root, active = ws.root_for(session_name), ws.tab(ws.state.get("active"))
    if root is None:
        tab = root = ws.root_for(session_name, create=True, title=title)
    elif new_tab:
        tab = ws.new_tab(session_name, title, kind="program", parent=root["id"])
    else:
        fam = {x["id"] for x in ws.family(root)}
        tab = active if active is not None and active["id"] in fam else \
            ws.tab(root.get("front")) if root.get("front") in fam else root
    ws.state["active"] = root["front"] = tab["id"]
    ws.state["open_sessions"] = manager.session_names()
    _strings(ws)
    ws.save()
    ws.beat()
    if not ws.window_alive():
        err = _launch(ws)
        if err:
            return f"Error: cannot open the workbench window: {err}."
    _serve(ws, manager)
    fs = sess["flowsheet"]
    others = [f"{t['title']} ({t['id']}, {t['session']})" for t in ws.state["tabs"]
              if t.get("kind") == "model" and t is not root]
    subs = [f"{t['title']} ({t['id']}, {t.get('kind')})" for t in ws.children(root) if t is not tab]
    return (f"Workbench open on tab '{tab['title']}' (id {tab['id']}, session '{session_name}', "
            f"{len(fs['blocks'])} blocks, {len(fs['streams'])} streams, language {ws.lang})"
            + ("" if tab is root else f", a sub-tab of model tab '{root['title']}' (id {root['id']})") + ". "
            + (f"Sub-tabs: {', '.join(subs)}. " if subs else "")
            + (f"Other model tabs: {', '.join(others)}. " if others else "")
            + f"Workspace: {ws.dir}. Use workbench_read to see the user's notes and program, "
              f"workbench_edit to change the window live.")


# The workbench opens by itself with every session a tool opens (open_aspen_plus,
# create_new_simulation): the plugin's baseline. ASPEN_MCP_WORKBENCH_AUTO=0 turns that off
# (open_workbench still opens it on request). Never fails the call that opened the session.
AUTO_ENV = "ASPEN_MCP_WORKBENCH_AUTO"
# How to have Ask AI requests arrive at once, as INSTALL.md / docs/mcp/workbench/requests.md give it. The
# server cannot know the name its client gave it: the plugin's is fixed; run from a source
# checkout it is the .mcp.json entry that starts this server.py; ASPEN_MCP_CHANNEL_SPEC overrides.
CHANNEL_SPEC_ENV = "ASPEN_MCP_CHANNEL_SPEC"
CHANNEL_PLUGIN = "plugin:aspen-plus@aspen-mcp"


def _from_source(pkg: Path) -> bool:
    """The package runs from a git checkout (the plugin's install is a uv cache / site-packages)."""
    return any((d / ".git").exists() for d in (pkg, *pkg.parents))


@functools.lru_cache(maxsize=1)
def channel_spec() -> str:
    """The --dangerously-load-development-channels argument that names this server."""
    spec = os.environ.get(CHANNEL_SPEC_ENV, "").strip()
    if spec:
        return spec
    pkg = _PKG
    if not _from_source(pkg):
        return CHANNEL_PLUGIN
    me = pkg / "server.py"
    for cfg in dict.fromkeys((Path.cwd() / ".mcp.json", pkg.parent / ".mcp.json")):
        try:
            servers = json.loads(cfg.read_text(encoding="utf-8")).get("mcpServers") or {}
        except Exception:
            continue
        for name, entry in servers.items():
            for a in (entry or {}).get("args") or []:
                try:
                    if str(a).endswith("server.py") and Path(a).resolve() == me:
                        return f"server:{name}"
                except Exception:
                    pass
    return "server:<this server's name in your .mcp.json>"


def channel_cmd() -> str:
    """One PowerShell line that starts Claude Code with the channel (channels are a research
    preview of Claude Code). A background Claude Code session already running drops channel
    pushes, so any such session has to be ended first; the hint says so in words."""
    return f'$env:ASPEN_MCP_CHANNELS = "1"; claude --dangerously-load-development-channels {channel_spec()}'


CHANNEL_CODEX = r"%USERPROFILE%\.aspen-mcp\codex-aspen.cmd"
_HINTED = {"channel": False}      # the AI was told how to connect the channel (once a process)


def auto_on() -> bool:
    return os.environ.get(AUTO_ENV, "1").strip().lower() not in ("0", "off", "false", "no")


def channel_hint() -> str:
    """For the AI, once per server process while Ask AI is not known to be delivered at once:
    what to tell the user to connect it ("" when it is, or was said already). ASPEN_MCP_CHANNELS
    only claims the client takes pushed messages (it may be left set while Claude Code runs
    without channels): then the hint is said too, as a check the AI can make."""
    if (channel is not None and listening and listening_checked) or _HINTED["channel"]:
        return ""
    _HINTED["channel"] = True
    if "codex" in str(_CLIENT["name"] or "").lower():
        how = f"start Codex with `{CHANNEL_CODEX}`."
    else:
        how = ("start Claude Code with the channel (channels are a research preview of Claude Code) by "
               "running this line in PowerShell, given as one code block to copy; if background Claude Code "
               "sessions are running, the user should end them first, or the pushes are dropped:"
               f"\n```powershell\n{channel_cmd()}\n```")
    if channel is not None and listening:
        return ("ASPEN_MCP_CHANNELS is set, so Ask AI requests from the workbench are pushed to you as channel "
                "messages. If none reaches you when the user sends one, the client was started without the "
                f"channel: tell the user once that to have them arrive at once, {how}")
    return ("Ask AI requests sent from the workbench reach you only when your turn ends or the user next "
            f"writes here. Tell the user once: to have them arrive at once, {how}")


# How the user chose to work on a session (asked once per session, before it is opened: the
# aspen-process-workflow skill): "workbench" -- proposals and blocks in the window, questions as
# choices -- or "chat" -- the AI works in the conversation and the window stays shut. Kept in
# the workspace state (sessions[name]["mode"]), so a later conversation on the same model knows
# it; open_workbench switches a session to "workbench". None: not asked yet.
SESSION_MODES = ("workbench", "chat")
MODE_WORKBENCH = ("[workbench] Mode: workbench (the user works in the window). Follow the "
                  "aspen-process-workflow skill: ask with note_replies choices, build the process as "
                  "proposals phase by phase, write reasons and replies in the user's language.")
MODE_CHAT = ("[workbench] Mode: chat (the user chose to work in this conversation): the workbench was "
             "not opened. open_workbench opens it if the user asks, and switches this session to "
             "workbench mode.")
MODE_UNSET = ("[workbench] No working mode is recorded for this session. Before building or changing "
              "the process, ask the user (aspen-process-workflow skill) and pass mode= next time a "
              "session is opened.")


def session_mode(name: str | None) -> str | None:
    """The mode recorded for a session ("workbench" | "chat"), None when none is."""
    try:
        ws = _WS if _WS is not None else _workspace()
        m = (ws.state["sessions"].get(str(name or "")) or {}).get("mode")
    except Exception:
        return None
    return m if m in SESSION_MODES else None


def set_session_mode(name: str, mode: str) -> None:
    """Record the user's choice for a session (not while another server serves the window:
    its state is that server's)."""
    if mode not in SESSION_MODES or _owner_other() is not None:
        return
    ws = _workspace()
    ws.drain()
    ws.session(name)["mode"] = mode
    ws.save()


def auto_open(manager, before, guess: str | None = None, mode: str | None = None) -> str:
    """After a tool opened a session (``before``: the session names before it; ``guess``: the
    name it should have; ``mode``: how the user chose to work, else the one recorded for the
    session): open the workbench on it, unless the mode is "chat", ASPEN_MCP_WORKBENCH_AUTO=0 or
    the window already shows it. Returns lines to add to the tool's answer ("" none); never raises."""
    try:
        now = manager.session_names()
        new = [n for n in now if n not in set(before or ())]
        name = guess if guess in now else (new[-1] if new else None)
        if name is None:
            return ""
        if mode is not None and mode not in SESSION_MODES:
            return f"\n[workbench] mode must be one of {', '.join(SESSION_MODES)}, not {mode!r}: nothing recorded."
        if mode is not None:
            set_session_mode(name, mode)
        mode = mode or session_mode(name)
        if mode == "chat":
            return "\n" + MODE_CHAT
        if not auto_on():
            return ""
        ws = _WS
        if ws is not None and ws.window_alive() and ws.root_for(name) is not None:
            return "\n" + (MODE_WORKBENCH if mode == "workbench" else MODE_UNSET)
        res = open_workbench_now(manager, name) if mode == "workbench" else _open_unset(manager, name)
    except Exception as exc:
        logger.warning("workbench: not opened with the session", exc_info=True)
        res = f"Error: {type(exc).__name__}: {exc}"
    if not res.startswith("Workbench open"):
        return (f"\n[workbench] The workbench did not open by itself ({res.strip()[:300]}). "
                "open_workbench(session_name) opens it.")
    hint = channel_hint()
    return (f"\n[workbench] Opened by default with this session. {res} Pass lang=\"zh\" to "
            "open_workbench when the user writes Chinese." + (f"\n[workbench] {hint}" if hint else "")
            + "\n" + (MODE_WORKBENCH if mode == "workbench" else MODE_UNSET))


def _open_unset(manager, name: str) -> str:
    """The window opened for a session whose mode was never asked (the baseline, as before
    modes): it shows the session, and the mode stays unrecorded."""
    res = open_workbench_now(manager, name)
    try:
        sess = _WS.state["sessions"].get(name) if _WS is not None else None
        if sess is not None and res.startswith("Workbench open"):
            sess.pop("mode", None)
            _WS.save()
    except Exception:
        pass
    return res


def _log_text(e: dict) -> str:
    return e["text"][:400] if e.get("level") == "info" else e["text"][:3000]


def changes(manager, session: str) -> dict | None:
    """The latest change groups of the session's model, as the journal measured them
    (journal.digest, fields named by the flowsheet's block types); None when the session has
    no model."""
    try:
        model = manager.model_id(session) if session else None
    except Exception:
        model = None
    if not model:
        return None
    types = block_types(session)
    return journal.digest(model, name=lambda path: aspen_labels.named(path, types))


_STALE_PATHS = 10        # model_status: the inputs changed since the last run it names


def model_status(manager, session: str) -> dict | None:
    """workbench_read's ``model_status``: where the session's model stands, in the change
    journal's numbers (journal.summary; the window's model capsule shows the same) -- {"file",
    "unsaved": inputs changed since the file was last in step with Aspen ("2000+": more than
    the journal keeps), "runs_since_save", "stale": {"n", "paths"}: inputs changed since the
    last run that ran (the latest first, at most _STALE_PATHS), "last_run": {"seq", "status",
    "t", "actor", "via", "errors", "warnings", "delta_top": its record's first results that
    moved}, "last_save": {"t", "actor", "via", "how"}, "external_checked": when edits made in
    the Aspen window were last looked for (tools/external.py), or null}. None when the journal
    is off or the session has no model (or reading it failed: logged). No COM."""
    try:
        return _model_status(manager, session)
    except Exception:
        logger.warning("workbench: model status of %s not taken", session, exc_info=True)
        return None


def _model_status(manager, session: str) -> dict | None:
    model = manager.model_id(session) if session and journal.enabled() else None
    s = journal.summary(model) if model else None
    if not s:
        return None
    un, st, run, save = s.get("unsaved") or {}, s.get("stale") or {}, s.get("run"), s.get("save")
    items = (journal.pending(model) or {}).get("items") or [] if st.get("n") else []
    last_run = None
    if run:
        last_run = {k: run.get(k) for k in ("seq", "status", "t", "actor", "via", "errors", "warnings")}
        rec = journal.find(model, run.get("id"), scan=2000) if run.get("id") else None
        d = (rec or {}).get("delta") if isinstance((rec or {}).get("delta"), dict) else {}
        last_run["delta_top"] = [runlog.item_text(i) for i in (d.get("items") or [])[:3]]
        if d.get("first"):
            last_run["first"] = True
    f = manager.session_file(session) or (save or {}).get("file")
    return {"file": os.path.basename(f) if f else None,
            "unsaved": f"{un['n']}+" if un.get("more") else un.get("n", 0),
            "runs_since_save": un.get("runs", 0),
            "stale": {"n": f"{st['n']}+" if st.get("more") else st.get("n", 0),
                      "paths": [it["path"] for it in items[:_STALE_PATHS] if it.get("path")]},
            "last_run": last_run,
            "last_save": {k: save.get(k) for k in ("t", "actor", "via", "how")} if save else None,
            "external_checked": external.checked(session) if external.enabled() else None}


def restore_list(manager, session: str) -> list | None:
    """workbench_read's ``checkpoints``: the session model's newest _CP_LIST restore
    points, newest first -- {"id", "at" (local time), "name" (a named one), "reason"
    (before-structure, before-optimize, before-patch, before-overwrite, manual...), "state"
    (saved: the file as last opened or saved; live: the model as it was in Aspen), "kept"
    (never removed automatically)} -- about 0.5 KB, so the AI knows what the user can go back
    to. None without a model; no COM."""
    try:
        model = manager.model_id(session) if session else None
        out = []
        for c in checkpoints.list_checkpoints(model)[:_CP_LIST] if model else ():
            e = {"id": c.get("id"), "at": time.strftime("%Y-%m-%d %H:%M", time.localtime(c["t"]))
                 if isinstance(c.get("t"), (int, float)) else None}
            e.update({k: c[k] for k in ("name", "reason", "state") if c.get(k)})
            if c.get("class") == "named" or c.get("pinned"):
                e["kept"] = True
            out.append(e)
        return out if model else None
    except Exception:
        logger.warning("workbench: restore points of %s not listed", session, exc_info=True)
        return None


def flowsheet_of(session: str) -> dict | None:
    """The session's flowsheet as the window last read it (``snapshot``: blocks and types,
    streams with from / to, components, ``taken_at``, ``model``), or None; no COM. What a
    run's result fingerprint takes its product streams from (tools/runlog.py)."""
    ws = _WS
    sess = ws.state["sessions"].get(session) if ws is not None and session else None
    fs = (sess or {}).get("flowsheet") if isinstance(sess, dict) else None
    return fs if isinstance(fs, dict) else None


def block_types(session: str) -> dict:
    """{block: type} of a session's flowsheet as the window last read it; no COM ({} without
    a workspace). tools/intercept.py's hooks.types."""
    ws = _WS
    sess = ws.state["sessions"].get(session) if ws is not None and session else None
    fs = (sess or {}).get("flowsheet") or {}
    return {b["name"]: b.get("type") for b in fs.get("blocks") or [] if isinstance(b, dict) and b.get("name")}


def _read_notes(ws: Workspace, asked: list) -> None:
    """The AI read these open requests (workbench_read): read and delivered -- the window's
    waiting line stops asking the user to tell the AI (a channel's ``delivered`` alone is a
    claim: the window waits only a while on it) -- and no longer pushed."""
    fresh = [n for n in asked if not n.get("read")]
    if not fresh:
        return
    now = round(time.time(), 3)
    for n in fresh:
        n["read"] = now
        n.setdefault("delivered", now)
        n.pop("undelivered", None)
    ids = {n.get("id") for n in fresh}
    ws.asks = [a for a in ws.asks if a["note"].get("id") not in ids]
    ws.save()


def workbench_read(manager, session_name: str | None = None, tab: str | None = None) -> str:
    ws = _workspace()
    ws.drain()
    if _bind(ws):
        ws.save()
    t, err = _resolve(ws, session_name, tab)
    mkey, kept = ws.arch_tab(tab) if err and tab else (None, None)
    if kept is not None and not (session_name and kept.get("session") != session_name):
        t, err = kept, None                              # a proposal kept in History, read there
    if err and not tab and session_name and manager.get_app(session_name) is not None:
        # an open session no tab shows: what changed it all the same
        return json.dumps({"tab": None, "session": session_name, "window_open": ws.window_alive(),
                           "tabs": _tabs_view(ws),
                           "brief": brief.take(),
                           "model_status": model_status(manager, session_name),
                           "checkpoints": restore_list(manager, session_name),
                           "changes": changes(manager, session_name),
                           "brake": _brake_read(ws)}, ensure_ascii=False, indent=1)
    if err:
        return err
    sess = ws.session(t["session"])
    fs = sess.get("flowsheet") or {}
    run = t.get("run") or {}
    asked = [n for n in sess.get("notes") or [] if n.get("status") == "open"]
    if asked:                      # the newest open request is the one the AI's next changes are for
        journal.GROUPS.note_seen(asked[-1]["id"], asked[-1].get("text"), t["session"])
        _read_notes(ws, asked)
    root = next((x for x in ws.state["tabs"] if x.get("kind") == "model" and x.get("mkey") == mkey), None) \
        if kept is not None else ws.root_of(t)
    key = mkey if kept is not None else (root or {}).get("mkey")
    hist = (ws._history().get(key) or [dict(e, loaded=False) for e in ws.arch.index(key)]) if key else []
    view = {
        "tab": {"id": t["id"], "title": t["title"], "session": t["session"],
                **{k: t[k] for k in ("kind", "parent") if t.get(k)}},
        **({"archived": True} if kept is not None else {}),
        # one tab per model; its programs and proposals are its sub-tabs
        "model_tab": {"id": root["id"], "title": root["title"], **({"stale": True} if ws.stale(root) else {})}
        if root is not None else None,
        "tabs": _tabs_view(ws),
        # your proposals on this model loaded in the window: status, the user's edits, the latest check
        "proposals": proposals.listing(ws.state["tabs"], (root or {}).get("id"), t["session"]),
        "proposal_history": proposals.history_listing(hist),   # finished ones (History), the latest first
        "closed_proposals": proposals.closed_listing(hist),
        "window_open": ws.window_alive(),
        "lang": ws.lang,
        "mode": sess.get("mode"),                        # how the user chose to work (session_mode)
        "selection": t.get("selection"),
        # an open request with a target says what that is, as it was pushed
        "notes": None if sess.get("notes") is None else
        [dict(n, target_text=_target_text(ws, manager, t["session"], n["target"], n))
         if n.get("status") == "open" and isinstance(n.get("target"), dict) else n for n in sess["notes"]],
        "program": t.get("program"),
        "program_origin": t.get("program_origin"),
        "flowsheet": {
            "blocks": [f"{b['name']} ({b['type']})" for b in fs.get("blocks", [])],
            "streams": [f"{st['from'] or '(in)'} -[{st['name']}]-> {st['to'] or '(out)'}"
                        for st in fs.get("streams", [])],
            "components": fs.get("components", []),
            "block_errors": {k: v["msg"] or v["level"] for k, v in sess.get("status", {}).items()},
            "arrangement": _arrangement(sess),              # how the window draws it (only the picture)
            "model": {"id": fs.get("model"), "file": _model_file(manager, t["session"])},
        },
        "last_run": {"status": run.get("status"), "dry_run": run.get("dry_run"),
                     # the user is stepping through it: the step it waits before
                     **({"paused": {k: run["paused"].get(k) for k in ("at", "n", "since", "why", "next")}}
                        if isinstance(run.get("paused"), dict) else {}),
                     # waiting for the user to set a field (your turn), with no timeout
                     **({"wait": {k: run["wait"][k] for k in ("sid", "n", "path", "hint", "t", "tries", "msg",
                                                              "expect", "before", "now") if k in run["wait"]}}
                        if isinstance(run.get("wait"), dict) else {}),
                     "vars": run.get("vars"),
                     "log_tail": [_log_text(e) for e in (run.get("log") or [])[-20:]],
                     "tables": [{**{k: v for k, v in tb.items() if k != "lines"},   # a plot's curves are its rows
                                 "rows": tb["rows"][:60], "rows_total": len(tb["rows"])}
                                for tb in run.get("tables") or []],
                     "optimizations": [_opt_summary(o) for o in run.get("opts") or []]},
        # where the last real run (or a point applied since) left the model
        "model_state": (t.get("results") or {}).get("state") or run.get("model_state"),
        # the window's own Run simulation and Save model on this session, the last of each
        "window_sim": sess.get("sim"),
        "window_saved": sess.get("saved"),
        # saved? results current? by the change journal, whoever changed or ran it
        "model_status": model_status(manager, t["session"]),
        # what the user's "Missing inputs" panel says the model still lacks (check_inputs has the details)
        "missing": _miss_read(sess.get("missing")),
        # why the last run failed, as the user's diagnosis card says it
        "diagnosis": _diag_read(sess),
        # what the user can go back to (restoring is theirs, from the workbench)
        "checkpoints": restore_list(manager, t["session"]),
        "history": t.get("history") or {"undo": 0, "redo": 0},
        # what others changed since the AI's last call, and lately who changed what, measured
        "brief": brief.take(),
        "changes": changes(manager, t["session"]),
        # the user's brakes on you: mode, pause, your latest confirmation cards
        "brake": _brake_read(ws),
    }
    if learn.on():                 # every change needs a reason that explains the process principle
        view["learning"] = True
    hint = _explain_hint(ws)       # a proposal's run tagged, not explained yet
    if hint:
        view["hint"] = hint.strip()
    return json.dumps(view, ensure_ascii=False, indent=1)


def _opt_summary(o: dict) -> dict:
    """An optimize step's result for the LLM: counts and the Pareto set, not every eval."""
    ok = sum(1 for e in o["evals"] if e["ok"])
    return {"id": o["id"], "algorithm": o["algorithm"], "run_dir": o["run_dir"],
            "evaluations": len(o["evals"]), "feasible": ok,
            "variables": [f"{v['name']}" + (f" [{v['unit']}]" if v.get("unit") else "") for v in o["variables"]],
            "objectives": [f"{b['name']} ({b['direction']})" + (f" [{b['unit']}]" if b.get("unit") else "")
                           for b in o["objectives"]],
            "pareto": o["pareto"][:30]}


def workbench_edit(
    manager,
    session_name: str | None = None,
    tab: str | None = None,
    program: list[dict] | None = None,
    insert: list[dict] | None = None,
    after_id: str | None = None,
    remove_ids: list[str] | None = None,
    highlight: list[dict] | None = None,
    message: str | None = None,
    note_replies: list[dict] | None = None,
    refresh_flowsheet: bool = False,
    lang: str | None = None,
    proposal: dict | None = None,
) -> str:
    ws = _workspace()
    ws.drain()
    try:
        sp = proposals.spec(proposal) if proposal is not None else None
    except ValueError as exc:
        return f"Error: {exc}"
    t, err = _resolve(ws, session_name, tab)
    # a proposal kept in History -- a revision (its program, title, reason or status) opens
    # it again in its model's tab; anything else (withdraw, explain, watch, a message) is written there
    mkey, kept = ws.arch_tab(tab) if err and tab else (None, None)
    reopened = False
    if kept is not None and not (session_name and kept.get("session") != session_name):
        p0 = kept.get("proposal") or {}
        if program is not None or insert or remove_ids or (sp is not None and sp.get("status") != "withdrawn" and (
                sp.get("status") is not None or any(sp.get(k) and sp[k] != p0.get(k) for k in ("title", "reason")))):
            t, err, kept, reopened = ws.load_tab(tab), None, None, True
            if t is None:
                return _not_loaded(ws, tab) or f"Error: no tab '{tab}'."
            ws.message(t, _t(ws.lang, "prop_reopened"), "system", kind="proposal", what="reopened",
                       proposal=(t.get("proposal") or {}).get("id"))
        else:
            t, err = kept, None
    # a proposal goes into a tab of its own -- a new one unless ``tab`` names a proposal, which
    # it revises (so does any program change on a proposal tab); a new one takes the program of the
    # tab ``tab`` names, else none, before the edits below
    fresh = sp is not None and not (tab and t is not None and t.get("kind") == "proposal")
    if err and not (fresh and not tab and session_name and manager.get_app(session_name) is not None):
        return err
    if fresh and sp.get("explain"):                       # (words on a run's results)
        return "Error: proposal explain is written after the proposal's run: give its tab. Nothing was changed."
    explained = _explain_take(t, sp, ws.lang) if sp is not None and "explain" in sp else ""
    flash, prop, now = [], None, time.time()
    edited = json.loads(json.dumps(t["program"] if t is not None and (tab or not fresh) else []))
    try:
        if program is not None:
            edited = normalize(program)
            flash = [st["id"] for st in _walk(edited)]
        for sid in remove_ids or []:
            hit = _find(edited, sid)
            if hit:
                hit[0].pop(hit[1])
        if insert:
            existing = {st["id"] for st in _walk(edited)}
            new = normalize(insert, seen=set(existing))
            if after_id:
                hit = _find(edited, after_id)
                if not hit:
                    return f"Error: no statement with id '{after_id}'."
                hit[0][hit[1] + 1:hit[1] + 1] = new
            else:
                edited.extend(new)
            flash += [st["id"] for st in _walk(new)]
        loops = [(sid, why) for sid, why in wb_plan.pause_errors(edited) if sid in flash]
        if loops:                                         # a your-turn step this edit put in a loop
            return "Error: " + "; ".join(f"step {sid}: {why}" for sid, why in loops) + ". Nothing was changed."
        bad_ids = _bad_places(edited, set(flash), t["program"] if t is not None else [])
        if bad_ids:                                       # a new ID Aspen refuses or cuts (tools/ids.py)
            return "Error: " + "; ".join(bad_ids) + ". Nothing was changed."
        if fresh:
            session = t["session"] if t is not None else session_name
            note, g = current_note(), journal.GROUPS.current()
            prop = proposals.new(sp, edited, None, now, proposed_in=(g or {}).get("id"),
                                 note=(note or {}).get("id"), base=_prop_base(manager, session))
        elif t.get("kind") == "proposal" and (sp is not None or edited != t["program"]):
            proposals.status_after(t["proposal"], sp, edited, edited != t["program"])   # (refused: nothing changed)
    except ValueError as exc:
        return f"Error: {exc}"
    ran = []
    if not fresh and t.get("kind") == "proposal" and edited != t["program"]:
        ran = proposals.mark_ran(t["proposal"], edited)   # (a revision after a partial run: those steps start off)
    if fresh:                                            # a sub-tab of its model's tab (made when closed)
        root = ws.root_of(t) if t is not None else None
        if root is None or ws.stale(root) or root.get("session") != session:
            root = ws.root_for(session, create=True)
        t = ws.new_tab(session, prop["title"][:60], kind="proposal", parent=root["id"])
        t["proposal"] = prop
        ws.state["active"] = root["front"] = t["id"]
        flash = flash or [st["id"] for st in _walk(edited)]
    changed = ws.commit(t, edited, "llm", flash)
    said = _prop_edited(ws, manager, t, sp, changed, fresh, now) if t.get("kind") == "proposal" else ""
    if ran:
        said = (said + " " if said else "") + (
            f"Step(s) {', '.join(ran[:12])}{' ...' if len(ran) > 12 else ''} applied in the last run and are "
            "unchanged: they start turned off, marked already run in the window (the user may turn them back on).")
    if sp is not None and "watch" in sp and t.get("kind") == "proposal":   # the results it tags after its run
        w = t["proposal"].get("watch") or []
        said = (said + " " if said else "") + (
            f"Watching {len(w)} result(s) after its run, the goal {w[0]['path']}: the window tags their values "
            "measured before and after it; the check warns of a path not found." if w else "No results watched.")
    if explained:
        said = (said + " " if said else "") + explained
    if lang in _LANGS:
        ws.state["lang"] = lang
    if highlight is not None:
        t["highlight"] = _highlight(highlight)
        t["highlight_at"] = time.time()                  # the window: marks newer than the last run show
        _pin_notes(ws, manager, t, t["highlight"])       # a note stays pinned on its object
    notes = ws.session(t["session"])["notes"]
    if message or sp is not None:                        # the AI's next word: "more is coming" ends
        _working_end(notes)
    if message:
        ws.message(t, message)
    replied = _note_replies(notes, note_replies, ws.lang)
    if refresh_flowsheet:
        ws.jobs.append({"kind": "refresh", "session": t["session"]})
        ws.work(manager)
    if kept is not None:                                 # written back into History
        try:
            ws.arch.save(mkey, t, proposals.history_entry(t))
        except (OSError, TypeError, ValueError) as exc:
            return f"Error: the proposal kept in History could not be written ({exc}). Nothing was changed."
    ws.save()
    live = "window updated" if ws.window_alive() else "saved (window not open; open_workbench shows it)"
    if kept is not None:
        live = "kept in History (not open in the window)"
    elif reopened:
        live += ", reopened from History"
    why = _why_hint(t["program"], flash)
    prn = _principle_hint(ws, t, flash)
    return (f"OK, {live} (tab '{t['title']}'). Program has {sum(1 for _ in _walk(t['program']))} statements"
            + (f"; inserted/changed ids: {', '.join(flash)}" if flash else "") + "." + (" " + said if said else "")
            + (f"\nLearning mode: add a \"why\" to steps {why} (the user reads it under each block)." if why else "")
            + (f"\nLearning mode: no principle card for group(s) {prn}; where one fits, add \"principle\": [key] "
               "to the heading (docs/principles/index.md)." if prn else "")
            + replied + _explain_hint(ws))


_REPLY_KEYS = ("id", "reply", "done", "choices", "multi", "working")
_REPLY_SHAPE = '[{"id", "reply", "done"?, "choices"?: [{"label", "detail"?}, ...], "multi"?, "working"?}]'
_CHOICES_MIN, _CHOICES_MAX = 2, 6          # the options one answer offers
_CHOICE_LABEL_MAX, _CHOICE_DETAIL_MAX = 80, 240


def _bad_places(program, sids: set, before) -> list[str]:
    """The place steps an AI edit wrote (``sids``) whose new block or stream ID Aspen refuses or
    cuts (tools/ids.py), each as "step <id>: ..." with an ID that fits. An ID the program placed
    already (``before``) passes, so an older proposal can still be revised; the user's own edits
    are not refused here (the check marks them, and a real run refuses them before writing)."""
    def placed(prog):
        return {(k, str(st[k]).upper()) for st in _walk(prog) if st.get("do") == "place"
                for k in ("block", "stream") if st.get(k)}
    old, names, out = placed(before), placed(program), []
    for st in _walk(program):
        if st.get("id") not in sids or st.get("do") != "place":
            continue
        kind = "block" if st.get("block") else "stream"
        name = str(st.get(kind) or "")
        why = ids.problem(name)
        if why is None or (kind, name.upper()) in old:
            continue
        fit = ids.suggest(name, [n for k, n in names if k == kind], "B" if kind == "block" else "S")
        out.append(f"step {st['id']}: {kind} ID '{name}' has {why}, and an ID takes at most {ids.MAX} "
                   f"characters: letters, digits and -. Use '{fit}' (and the same ID in the steps that name it)")
    return out


def _choices_problem(choices, multi) -> str:
    """Why an answer's ``choices`` / ``multi`` are refused ("" when fine): 2-6 options, each
    {"label", "detail"?}, no label blank or given twice."""
    if multi is not None and not isinstance(multi, bool):
        return '"multi" must be true or false'
    if choices is None:
        return '"multi" needs "choices"' if multi is not None else ""
    if not isinstance(choices, list) or not _CHOICES_MIN <= len(choices) <= _CHOICES_MAX:
        return f'"choices" must be a list of {_CHOICES_MIN}-{_CHOICES_MAX} options'
    seen = set()
    for i, c in enumerate(choices, 1):
        if not isinstance(c, dict) or any(k not in ("label", "detail") for k in c):
            return f'choice {i} must be {{"label", "detail"?}}'
        label, detail = c.get("label"), c.get("detail")
        if not isinstance(label, str) or not label.strip():
            return f'choice {i}: "label" missing or blank'
        if len(label.strip()) > _CHOICE_LABEL_MAX:
            return f'choice {i}: "label" is over {_CHOICE_LABEL_MAX} characters -- put the rest in "detail"'
        if detail is not None and (not isinstance(detail, str) or len(detail.strip()) > _CHOICE_DETAIL_MAX):
            return f'choice {i}: "detail" must be text of at most {_CHOICE_DETAIL_MAX} characters'
        if label.strip() in seen:
            return f'choice {i}: the label "{label.strip()}" is given twice'
        seen.add(label.strip())
    return ""


def _reply_problem(rep, note: dict | None) -> str:
    """Why a note_replies item is refused ("" when it can be applied). The shape is {"id",
    "reply", "done"?, "choices"?, "multi"?}; a blank reply may only close a request that already
    has an answer; choices come with the question they answer (a reply in the same item) and
    leave the request open, since the user's pick closes it."""
    if not isinstance(rep, dict):
        return "not an object"
    extra = [str(k) for k in rep if k not in _REPLY_KEYS]
    if extra:
        return ("unknown key" + ("s " if len(extra) > 1 else " ") + ", ".join(f'"{k}"' for k in extra)
                + (' -- use "reply", not "text"' if "text" in extra else "")
                + (' -- use "choices", not "options"' if "options" in extra else ""))
    if not isinstance(rep.get("id"), str) or not rep["id"]:
        return '"id" missing'
    if note is None:
        return "no request with this id"
    done, reply = rep.get("done"), rep.get("reply")
    if done is not None and not isinstance(done, bool):
        return '"done" must be true or false'
    if rep.get("working") is not None and not isinstance(rep["working"], bool):
        return '"working" must be true or false'
    if reply is not None and not isinstance(reply, str):
        return '"reply" must be text'
    if not (reply or "").strip() and not (done is True and (str(note.get("reply") or "").strip() or note.get("event"))):
        return '"reply" missing or blank (only a request already answered, or an event, closes without one)'
    why = _choices_problem(rep.get("choices"), rep.get("multi"))
    if why:
        return why
    if rep.get("choices") is not None and not (reply or "").strip():
        return '"choices" need their question in "reply"'
    if rep.get("choices") is not None and done is True:
        return '"choices" wait for the user\'s pick, which closes the request: leave "done" out'
    return ""


def _set_choices(note: dict, rep: dict) -> None:
    """A new answer's options on its note: they replace the last answer's (and any pick); an
    answer without options leaves none."""
    for k in ("choices", "multi", "picked"):
        note.pop(k, None)
    if rep.get("choices") is not None:
        note["choices"] = [{"label": c["label"].strip(), **({"detail": c["detail"].strip()}
                            if (c.get("detail") or "").strip() else {})} for c in rep["choices"]]
        if rep.get("multi"):
            note["multi"] = True


def _working_end(notes: list) -> None:
    """The AI said something new (a reply, a message, a proposal): an earlier reply's "more is
    coming" (``working``) no longer holds."""
    for n in notes:
        n.pop("working", None)


def _note_replies(notes: list, items, lang: str = "en") -> str:
    """workbench_edit's note_replies: each well-formed item answers and/or closes its request; a
    malformed one changes nothing for its request. Returns the result's lines for the AI ("" when
    no item was given). An answer is stamped ``replied``; one with ``"working": true`` (more work
    follows: a sign of the AI's turn, the window's "AI is thinking…") also ``working``, until the AI's next
    reply, message or proposal without it, the request closed without it, or the window's age limit."""
    if not items:
        return ""
    applied, refused, asked = [], [], False
    now, spoke, still = round(time.time(), 3), False, []
    for i, rep in enumerate(items if isinstance(items, list) else [items]):
        rid = rep.get("id") if isinstance(rep, dict) else None
        note = next((n for n in notes if n["id"] == rid), None) if isinstance(rid, str) else None
        why = _reply_problem(rep, note)
        if why:
            refused.append(f"{rid if isinstance(rid, str) and rid else f'item {i + 1}'}: {why}")
            continue
        if (rep.get("reply") or "").strip():
            note["reply"] = rep["reply"]
            note["replied"] = now
            _set_choices(note, rep)
            spoke = True
        if rep.get("working") is not None:
            spoke = True
            if rep["working"]:
                still.append(note)
        if rep.get("done") is not None:
            note["status"] = "done" if rep["done"] else "open"
            if rep["done"]:
                journal.GROUPS.close(note["id"])          # the AI's next change starts a new group
                if not rep.get("working"):
                    note.pop("working", None)             # (closed: its "more is coming" too)
        asked = asked or rep.get("choices") is not None
        applied.append(rid + (f" ({len(note['choices'])} choices shown)" if rep.get("choices") is not None else "")
                       + (f" (the window shows {_t(lang, 'ui_ai_think')} while your turn runs)" if rep.get("working") else ""))
    if spoke:
        _working_end(notes)
        for note in still:
            note["working"] = now
    return ((f"\nNote replies applied: {', '.join(applied)}." if applied else "")
            + ("\nThe user's pick arrives as a new request whose \"answer_to\" names the request asked and "
               "\"picked\" the labels chosen; wait for it (the user may also type an answer instead)."
               if asked else "")
            + (f"\nNote replies refused, nothing changed for these requests: {'; '.join(refused)}. "
               f"Expected note_replies={_REPLY_SHAPE}." if refused else ""))


_WHY_STEPS =("set", "sweep", "seek", "optimize", *wb_plan.STRUCTURE)    # statements that change the model
_WHY_LIST = 8            # step ids a learning-mode hint names


def _no_why(program, ids=None) -> list[str]:
    """The steps (of ``ids``, else all) that change the model and give no ``why``; turned-off ones
    left out, and those of a group whose heading gives one."""
    want = None if ids is None else set(ids)
    act = wb_plan.active(program or [])
    covered = set()
    if groups_on() and any(st.get("do") == "group" and st.get("why") for st in act):
        top = {st.get("id"): st for st in act}
        for g in wb_plan.groups(program or []):
            if g["sid"] and (top.get(g["sid"]) or {}).get("why"):
                covered |= {x.get("id") for sid in g["ids"] if sid in top for x in _walk([top[sid]])}
    return [st["id"] for st in _walk(act) if st.get("do") in _WHY_STEPS and not st.get("why")
            and st["id"] not in covered and (want is None or st["id"] in want)]


def _id_list(ids: list[str]) -> str:
    more = len(ids) - _WHY_LIST
    return ", ".join(ids[:_WHY_LIST]) + (f" +{more} more" if more > 0 else "")


def _why_hint(program, flash) -> str:
    """Learning mode: the steps this edit wrote that change the model without a ``why``, as
    the line workbench_edit ends with says them ("" none, or learning mode off)."""
    if not flash or not learn.on():
        return ""
    ids = _no_why(program, flash)
    return _id_list(ids) if ids else ""


_PRN_FIELDS = ("set", "sweep")          # the steps whose field the rules table reads (principles.infer)
_BLOCK_OF = re.compile(r"^\\Data\\Blocks\\([^\\]+)\\", re.I)


def _principle_hint(ws, t: dict, flash) -> str:
    """In learning mode, the headed groups this edit wrote in that change
    the model with no principle key -- their heading's or their steps' -- and none that the rules table
    finds for a field they set (by the block's type: the session's flowsheet, or the program's own
    place); "" none. A hint, never a refusal."""
    if not flash or not learn.on() or not groups_on():
        return ""
    lib = principle_keys()
    if not lib:
        return ""
    program = t.get("program") or []
    fs = ((ws.state.get("sessions") or {}).get(t.get("session")) or {}).get("flowsheet") or {}   # (read only)
    types = {str(b.get("name")).upper(): b.get("type") for b in fs.get("blocks") or [] if isinstance(b, dict)}
    types.update({str(st.get("block")).upper(): st.get("type") for st in _walk(program)
                  if st.get("do") == "place" and st.get("block") and st.get("type")})
    top, want, out = {st.get("id"): st for st in program if isinstance(st, dict)}, set(flash), []
    for g in wb_plan.groups(program, lib):
        if not g["sid"] or not g["at"] or g["principle"]:
            continue                                     # (an automatic group: the AI wrote no heading to put a key on)
        sts = [x for sid in g["heads"] + g["ids"] if sid in top for x in _walk([top[sid]])]
        if not any(x.get("id") in want for x in sts):
            continue
        paths = [str(x.get("path") or "") for x in sts if x.get("do") in _PRN_FIELDS]
        if any(principles.infer(types.get(m.group(1).upper()), p) for p in paths for m in [_BLOCK_OF.match(p)] if m):
            continue
        out.append(f"{g['n']}" + (f" ({g['title']})" if g.get("title") else ""))
    return _id_list(out) if out else ""


def _twin_key(path) -> str:
    """A result path compared with its mass / mole twin alike (a watch read at its twin, _watch_path)."""
    p = str(path or "").strip().upper()
    for mass, mole in _TWINS:
        p = p.replace(mole, mass)
    return p


def _explain_take(t: dict | None, sp: dict, lang: str) -> str:
    """workbench_edit's ``proposal.explain`` on a proposal tab, before it is stored
    (proposals.revise): kept only for the run the result tags show now -- else taken out of ``sp``
    (explain_run) --; the words and sentences dropped for a number said back (explain_digits), and a
    result that is none of the run's. Returns the sentence for the AI."""
    ex, dropped = sp.get("explain"), sp.pop("explain_dropped", None) or []
    if t is None or t.get("kind") != "proposal":
        return ""
    if not ex:
        return "Explanation cleared."
    fx = (t.get("run") or {}).get("effects") or {}
    if not fx.get("items") or ex.get("run") != fx.get("run"):
        sp.pop("explain", None)
        return _t("en", "explain_run", run=ex.get("run"), now=fx.get("run") or "none")
    have = {_twin_key(it.get("path")) for it in fx["items"]}
    stray = [str(i) for i, it in enumerate(ex["items"], 1) if _twin_key(it["result"]) not in have]
    return (f"Explanation kept for {len(ex['items'])} result(s) of run {ex['run']}: the window shows it on each "
            "result tag's path and tooltip."
            + (" " + _t("en", "explain_digits", what=", ".join(dropped)) if dropped else "")
            + (f" Item(s) {', '.join(stray)}: not a result of this run (proposals[].effects.items), no tag shows it."
               if stray else ""))


def _explain_hint(ws: Workspace) -> str:
    """Once per run, the line any workbench tool's answer ends with after an approved
    proposal's run tagged results the AI has not explained yet ("" none)."""
    told, runs = ws.fx_told, []
    for tab in ws.state.get("tabs") or []:
        fx = (tab.get("run") or {}).get("effects") if tab.get("kind") == "proposal" else None
        if not isinstance(fx, dict) or not fx.get("items") or not fx.get("run") or fx["run"] in told:
            continue
        told.add(fx["run"])
        prop = tab.get("proposal") or {}
        j = (ws.state.get("sessions") or {}).get(tab.get("session"), {}).get("journal") or {}
        later = (j.get("run") or {}).get("seq") if isinstance(j.get("run"), dict) else None
        if prop.get("status") not in ("applied", "partial") \
                or (isinstance(later, int) and isinstance(fx.get("seq"), int) and later > fx["seq"]) \
                or float(j.get("last_input_t") or 0) > float(fx.get("at") or 0) + 0.001:
            continue                                     # (its tags are no longer shown: the window's rule)
        if (prop.get("explain") or {}).get("run") != fx["run"]:
            runs.append(f"tab {tab['id']} (run {fx['run']})")
    if not runs:
        return ""
    return ("\nResult tags: the run of proposal " + ", ".join(runs) + " is tagged on the flowsheet "
            "(workbench_read: proposals[].effects), each result with a path from the change. To say why, "
            "workbench_edit(tab, proposal={\"explain\": {\"run\", \"items\": [{\"result\": its path, \"via\"?: "
            "[objects in flow order], \"words\"?: {\"OBJECT\": \"a few words\"}, \"text\"?: \"one sentence\"}]}}) "
            "-- no numbers (a name like HX1 is fine): the numbers shown are the measured ones.")


def _prop_base(manager, session: str) -> dict | None:
    """A new proposal's ``base``: the model it was written against, and the journal's latest input
    then (a later one: the model changed after the AI proposed it)."""
    try:
        model = manager.model_id(session)
        s = (journal.summary(model) if model and journal.enabled() else None) or {}
        return {"model": model, "input_t": s.get("last_input_t")}
    except Exception:
        logger.warning("workbench: the base of a proposal on %s not taken", session, exc_info=True)
        return None


def _prop_edited(ws: Workspace, manager, t: dict, sp: dict | None, changed: bool, fresh: bool, now: float) -> str:
    """workbench_edit on a proposal tab, its program committed: a new proposal's AI version kept, or
    the revision (proposals.revise); the chat line; a note sending it back (``target.kind``
    proposal) done once it is revised; an open one checked when its session is idle. Returns the
    sentence for the AI ("" when nothing about the proposal changed)."""
    prop, lang = t["proposal"], ws.lang
    if fresh:
        prop["ai"]["program_rev"] = t["program_rev"]
        what, replaced = "proposed", None
        ws.message(t, proposals.say(lang, "drafted" if prop["status"] == "draft" else "proposed", title=prop["title"]),
                   "system", kind="proposal", what="proposed", proposal=prop["id"])
    else:
        if sp is None and not changed:                   # a message, a highlight, a note reply
            return ""
        title = prop.get("title")
        res = proposals.revise(prop, sp, t["program"], t["program_rev"], changed, now)
        what, replaced = res["what"], res["replaced"]
        if what is None:
            return ""
        key = "withdrawn" if what == "withdrawn" else "revised_mine" if replaced else "revised" if res["rev"] else \
            "ready" if prop["status"] == "open" else "revised"
        if prop.get("title") != title:                  # a new title names the tab again
            t["title"] = prop["title"][:60]
        ws.message(t, proposals.say(lang, key, rev=prop["rev"]), "system", kind="proposal", what=what,
                   proposal=prop["id"])
        if res["was"] == "rejected" and prop["status"] == "open":
            for n in ws.session(t["session"])["notes"]:
                tg = n.get("target") if isinstance(n.get("target"), dict) else {}
                if tg.get("kind") == "proposal" and tg.get("tab") == t["id"] and n.get("status") == "open":
                    n["status"] = "done"
                    journal.GROUPS.close(n["id"])
    checking = prop["status"] == "open" and what != "withdrawn" and ws.check_soon(manager, t)
    return proposals.answer(t, what, replaced, checking, ws.root_of(t))


def _tables_text(tables: list[dict]) -> str:
    out = []
    for tb in tables:
        cols, units, kind, rows = tb["columns"], tb.get("units") or {}, tb.get("kind", "sweep"), tb["rows"]
        if kind in ("table", "plot"):
            head = f"{kind.title()} '{tb.get('label')}' ({tb['id']})"
        else:
            head = f"Table for {kind} {tb['id']} ({tb.get('label') or tb.get('path')})"
        if kind == "plot":                                # a dozen samples of each curve is enough to read
            rows = rows[::max(1, len(rows) // 12)] + rows[-1:]
            head += "".join(f"; vertical line {v['label']} at x = {_fmt(v['x'])}" for v in tb.get("vlines") or [])
        lines = ["\t".join(f"{c} [{units[c]}]" if units.get(c) else c for c in cols)]
        lines += ["\t".join(_fmt(r.get(c)) for c in cols) for r in rows]
        out.append(head + ":\n" + "\n".join(lines))
    return "\n\n".join(out)


def _paused_text(tab: dict) -> str:
    """Stepping: ", paused at step 3 -- the user is stepping through it" for a tab whose run waits
    before a step; your turn: ", paused at step 3 (your turn) -- waiting for the user to set ..." for one
    waiting for the user; "" otherwise."""
    run = tab.get("run") or {}
    p, w = run.get("paused"), run.get("wait")
    if isinstance(w, dict):
        at = f"step {w['n']}" if w.get("n") is not None else f"statement {w.get('sid')}"
        return f", paused at {at} (your turn) — waiting for the user to set {_yt_label(w)}"
    if not isinstance(p, dict):
        return ""
    at = f"step {p['n']}" if p.get("n") is not None else f"statement {p.get('at')}"
    g = p.get("group")
    if p.get("why") == "group" and isinstance(g, dict):   # (the window's group card shows it; no chat line per group)
        return f", paused at {at} before group {g.get('n')} of {g.get('of')} — the user is applying it group by group"
    return f", paused at {at} — the user is stepping through it"


def _yt_label(w: dict) -> str:
    """A waiting your-turn step's field for the AI: its label in English (the session's hold
    has it), else the short path."""
    for h in activity.snapshot()["holders"].values():
        if h.get("wait_sid") == w.get("sid") and h.get("wait_label"):
            return h["wait_label"]
    return _short(w.get("path") or "")


def _waiting_line(tab: dict) -> str:
    """What workbench_run says when the run it started stops at a your-turn step."""
    w = (tab.get("run") or {}).get("wait") or {}
    at = f"step {w['n']}" if w.get("n") is not None else f"statement {w.get('sid')}"
    return (f"Paused at {at} ({w.get('sid')}, your turn): waiting for the user to set {_yt_label(w)} in the "
            f"workbench. The run continues when they press Done; workbench_read shows it (last_run.wait).")


async def _run_or_wait(task: asyncio.Task, tab: dict):
    """The run ``task`` workbench_run started, awaited until it ends -- its run -- or waits for
    the user at a your-turn step (the run's ``wait``) -- None, and the task goes on. The caller
    cancelled: the run is cancelled too, as awaiting it did."""
    try:
        while not task.done():
            if isinstance((tab.get("run") or {}).get("wait"), dict):
                return None
            await asyncio.wait({task}, timeout=_PAUSE_S)
        return task.result()
    except asyncio.CancelledError:
        task.cancel()
        raise


async def workbench_run(manager, session_name: str | None = None, tab: str | None = None,
                        dry_run: bool = True) -> str:
    ws = _workspace()
    ws.drain()
    t, err = _resolve(ws, session_name, tab)
    if err:
        kept = ws.arch_tab(tab)[1] if tab else None       # a proposal kept in History
        if kept is not None and not dry_run:
            return proposals.refusal(kept)
        if kept is not None:
            return (f"Error: proposal tab '{tab}' is kept in History, not open in the window: a check needs it "
                    f"open. A revision (workbench_edit(tab='{tab}', ...)) reopens it, or the user opens it from History.")
        return err
    if ws.stale(t):                                      # its model is no longer in the session
        return "Error: " + _t("en", "stale_run", tab=ws.root_of(t)["title"], session=t["session"])
    if not dry_run and t.get("kind") == "proposal":      # running it is the user's approval
        return proposals.refusal(t)
    if dry_run and t["id"] in ws.auto_checks:            # this check instead of the automatic one
        ws.auto_checks.discard(t["id"])
        ws.pending = [p for p in ws.pending if p[0] != t["id"]]
    if dry_run and ws.running(t["id"]) and t["id"] in ws.auto_runs:
        run = await asyncio.shield(ws.runs[t["id"]])    # its automatic check, under way: that one's answer
    else:
        ws.auto_runs.discard(t["id"])
        if ws.running(t["id"]):
            return f"Error: tab '{t['title']}' is already running its program{_paused_text(t)}."
        other = ws.busy(t["session"])
        if other is not None:
            return (f"Error: session '{t['session']}' is busy with tab '{other['title']}'{_paused_text(other)}. "
                    f"Wait for it, or run a tab on another session.")
        held = None if dry_run else activity.holder(t["session"])   # (the tool wrapper waited for it)
        if held is not None:
            return activity.refusal(held)
        g = journal.GROUPS.current()                     # the AI's change group this call joined
        hold = None if dry_run else _hold(t, "mcp")      # now: nothing may slip in before it starts
        task = asyncio.get_running_loop().create_task(
            execute(ws, manager, t, dry_run, via="mcp", ai_group=g.get("id") if g else None, hold=hold))
        ws.runs[t["id"]] = task
        run = await _run_or_wait(task, t)
        if run is None:                                  # waiting for the user; the run goes on
            run = t["run"]
            lines = [f"[{e['level']}] {e['text']}" for e in run["log"]] + [_waiting_line(t)]
            log = f"Run paused (tab '{t['title']}').\n" + "\n".join(lines)
            return log if len(log) <= 9000 else "...\n" + log[-9000:]
    lines = [f"[{e['level']}] {e['text']}" for e in run["log"]]
    log = (f"{'Check' if dry_run else 'Run'} {run['status']} (tab '{t['title']}').\n" + "\n".join(lines))
    tables = _tables_text(run.get("tables") or []) if not dry_run else ""
    for o in ([] if dry_run else run.get("opts") or []):
        s = _opt_summary(o)
        tables += (f"\n\nOptimization {s['id']} ({s['algorithm']}): {s['feasible']}/{s['evaluations']} feasible; "
                   f"Pareto set ({len(o['pareto'])}):\n"
                   + "\t".join(s["variables"] + s["objectives"] + ["best"]) + "\n"
                   + "\n".join("\t".join([_fmt(v) for v in p["x"] + p["f"]] + ["*" if p["best"] else ""])
                               for p in s["pareto"]))
    budget = 9000 - len(tables)
    return (log if len(log) <= budget else "...\n" + log[-budget:]) + ("\n\n" + tables if tables else "") \
        + _explain_hint(ws)
