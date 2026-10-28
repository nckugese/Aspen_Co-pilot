/* Run, Check and Stop: the press (a long program confirmed first: estimate, confirmLong) and
 * the server's answer (settle), a failed run (its step marked and centred, the log at its first
 * error, the Aspen error behind it: causeOf), the run log (renderRun, logAct) and the run
 * cursor beside the running step.
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { busy, changed, cut, dialog, editing, esc, feature, icon, isOpen, looseTops, prefGet,
    prefs, prefSet, renderPane, sendProgram, sentences, sessOf, setDock, setProg, settleHeld, shownTab,
    showPanel, steps, t, tabOf, toast, wb } = WBA;
  const { approveWhy, composerIdle, findStmt, focusComposer, modelLogOf, pausedOf, pick, placeStepCard, propOf, renderRunbar,
    stepName } = WBA.later;

  /** Why Run and Check cannot start on this tab now ({long, short}), or null. */
  function blocker(tab, rec) {
    if (!wb.connected) return { long: t("why_off"), short: t("why_off_s"), off: true };   // (off: the header's #conn says so)
    if (busy(tab)) return { long: t("why_busy"), short: t("why_busy"), busy: true };
    if (!isOpen(tab)) return { long: t("why_closed", tab.session), short: t("why_closed_s") };
    if (!steps(rec).main) return { long: t("why_empty"), short: t("why_empty_s") };
    return null;
  }

  /** About how many simulations a program runs: a run step one; a loop its body's times its
   *  passes (a sweep's points, a repeat's count, the cap of an until or a design spec); an
   *  optimize step its evaluations; a branch the larger of its two; a call its procedure's
   *  (a procedure calling itself counts once). Also its optimize steps, and whether it writes
   *  the model's inputs. */
  function estimate(program) {
    const procs = {}, out = { n: 0, opts: [], writes: false }, inCall = new Set(), optIds = new Set();
    (program || []).forEach((s) => { if (s.do === "proc" && s.name) procs[s.name] = s; });
    const count = (list) => (list || []).reduce((n, s) => n + one(s), 0);
    const times = (v, d) => Math.max(1, Number(v) || d);
    function one(s) {
      switch (s.do) {
        case "run": return 1;
        case "set": out.writes = true; return 0;
        case "sweep": out.writes = true; return times(s.steps, 2) * count(s.body);
        case "seek": out.writes = true; return Math.max(3, Number(s.max) || 30) * count(s.body);
        case "repeat": return times(s.times, 1) * count(s.body);
        case "until": return times(s.max, 100) * count(s.body);
        case "if": return Math.max(count(s.then), count(s.else));
        case "optimize": {
          out.writes = true;
          const budget = times(s.eval_budget, 100);
          if (!optIds.has(s.id)) { optIds.add(s.id); out.opts.push({ alg: WB.algName(s.algorithm || "afmcbo"), budget }); }
          return budget;
        }
        case "call": {
          const p = procs[s.name];
          if (!p || inCall.has(s.name)) return 0;
          inCall.add(s.name);
          const n = count(p.body);
          inCall.delete(s.name);
          return n;
        }
        default: return 0;
      }
    }
    out.n = count((program || []).filter((s) => s.do !== "proc"));
    return out;
  }
  /** A program that runs the simulation more than ten times, or optimizes, is confirmed once
   *  before it starts (the window's pref wb.confirm.long "off": never). Returns whether it
   *  asked; go starts the run once the user agrees. A run the AI starts is not asked about. */
  const LONG_RUNS = 10;
  function confirmLong(rec, go) {
    if (prefGet("wb.confirm.long") === "off") return false;
    const est = estimate(WB.workspaceToProgram(rec.ws));
    if (!est.opts.length && est.n <= LONG_RUNS) return false;
    const opts = est.opts.map((o) => t("long_opt", o.alg, o.budget)).join(t("long_and"));
    const body = sentences(t("long_body", est.n, opts ? t("long_with", opts) : "", est.writes ? t("long_writes") : ""), t("long_sim"));
    dialog({ title: t("long_title"), ok: t("run_prog"), focus: "ok",
      html: `<p>${esc(body)}</p><label class="mcheck"><input type="checkbox" class="long-never"> <span>${esc(t("long_never"))}</span></label>`,
      onOk: () => {
        const never = document.querySelector("#modal-body .long-never");
        if (never && never.checked) prefSet("wb.confirm.long", "off");
        go();
      } });
    return true;
  }

  /** Run (dry: Check) the shown tab's program; how.mode "step" steps through it, pausing before
   *  each step (app-step.js). On the AI's proposal a run is the approval:
   *  how {approve: true | "no_cp", mode: "run" | "step" | "group", resume: the step a stopped
   *  approval continues from}; a plain Run there (F6) approves
   *  it too, as the server takes any run of the window there. */
  function startRun(dry, sure, how) {
    const pane = wb.pane, tab = shownTab(), rec = tab && wb.recs.get(tab.id);
    if (!tab || !rec || rec.pending) return;
    settleHeld(rec);                             // what runs is what shows
    const prop = !dry && !!propOf(tab);
    const why = blocker(tab, rec) || (prop ? approveWhy(tab, rec) : null);
    if (why) { toast(why.long); return; }
    if (!dry && !sure && confirmLong(rec, () => startRun(false, true, how))) return;
    setProg(pane, true);                         // a folded program column opens on its run
    sendProgram(rec);
    // stacks beside the program do not run: say so, since they look like part of it
    const loose = looseTops(rec).length;
    if (loose) toast(t(loose === 1 ? "loose_1" : "loose_n", loose, Blockly.Msg.WB_START || ""), 5000);
    const run = tab.run || {};
    const p = (rec.pending = { kind: dry ? "check" : "run", status: run.status, started: run.started, rev: wb.rev });
    p.timer = setTimeout(() => noReply(rec, p), 5000);
    rec.mine = false;
    rec.runFrom = Date.now();                    // (a dock tab picked after this keeps the dock where it is)
    rec.noReply = 0;
    rec.late = null;
    rec.toErr = false;
    rec.center = null;
    const ev = { type: "run", tab: tab.id, dry_run: dry };
    if (!dry && how && how.mode === "step") ev.mode = "step";
    // (by group: where the server groups steps; else as one run)
    const mode = how && (how.mode === "step" || (how.mode === "group" && feature("groups"))) ? how.mode : "run";
    if (prop) Object.assign(ev, { approve: (how && how.approve) || true, mode });
    if (prop && how && how.resume) ev.resume = how.resume;   // continue a stopped approval from that step
    wb.post(ev);
    if (composerIdle(pane)) showPanel(pane, "log");   // only a run started here moves the dock
    renderRun(pane, tab, rec);
    renderRunbar();
  }

  function stopRun() {
    const tab = shownTab(), rec = tab && wb.recs.get(tab.id);
    if (!tab || !rec || !busy(tab) || !wb.connected || (rec.pending && rec.pending.kind === "stop")) return;
    const api = window.pywebview && window.pywebview.api;
    if (tab.run.progress && api && api.cancel_progress) api.cancel_progress(tab.run.progress.file);   // an optimization: cancel it now
    const p = (rec.pending = { kind: "stop", rev: wb.rev });
    p.timer = setTimeout(() => noReply(rec, p), 5000);
    wb.post({ type: "stop", tab: tab.id });
    renderRunbar();
  }

  /** Five seconds after a press. A stop the server has heard waits for the step to end. The
   *  press stays late for a minute: events are durable, so a busy server may still act on it. */
  function noReply(rec, p) {
    if (rec.pending !== p || (p.kind === "stop" && wb.rev !== p.rev)) return;
    rec.pending = null;
    rec.late = p;
    p.at = rec.noReply = Date.now();
    setTimeout(() => { if (wb.pane && wb.pane.tabId === rec.id) renderRunbar(); }, 8100);
    if (wb.pane && wb.pane.tabId === rec.id) { wb.pane.sigs.log = null; renderPane(wb.pane); renderRunbar(); }
  }

  /** Clear what the server has answered, for every tab (a late answer too: the capsule
   *  drops "no answer"); a run that ended shows what came of it: any run seen running here
   *  (the AI's, a proposal's) that made a table or a chart opens the dock on its results, and
   *  a run that started here and failed, on its log at the first error, with the failed step
   *  centred once (renderRun). Nothing moves while the composer is in use or after a dock tab
   *  was picked by hand during the run (the failed step is centred all the same: that is the
   *  block canvas, not the dock); a stop moves nothing. A failure seen while the window is
   *  open is said in a toast when its tab shows, whoever started the run. */
  /** A failure not yet said in a toast, said once its tab shows (the capsule keeps the words;
   *  the toast only draws the eye to them). */
  function sayFailure(rec, tab) {
    if (!rec.errToSay || !wb.pane || wb.pane.tabId !== rec.id) return;
    rec.errToSay = false;
    toast(t("st_error_at", failedName(tab, rec)));
  }

  function settle() {
    wb.recs.forEach((rec) => {
      const tab = tabOf(rec.id), p = rec.pending, late = rec.late;
      if (!tab) return;
      const run = tab.run || {};
      const ek = run.status === "error" ? `${run.started}|${run.step}` : "";
      if (ek !== rec.errKey) {
        rec.errToSay = !!ek && rec.errKey !== undefined;   // (not a failure the window opened on)
        rec.errKey = ek;
      }
      sayFailure(rec, tab);
      const answered = (q) => (q.kind === "stop" ? !busy(tab) : run.status !== q.status || run.started !== q.started);
      if (p && answered(p)) {
        clearTimeout(p.timer);
        rec.pending = null;
        if (p.kind !== "stop") { rec.mine = true; rec.noReply = 0; }
      }
      if (late && Date.now() - late.at > 60000) rec.late = null;
      else if (late && answered(late)) {
        rec.late = null;
        rec.noReply = 0;
        if (late.kind !== "stop") rec.mine = true;
      }
      if (busy(tab) && !rec.runFrom) rec.runFrom = Date.now();   // a run seen running here, whoever started it
      const ended = !busy(tab) && !rec.pending && ["done", "error", "stopped"].includes(run.status);
      if (ended && (rec.mine || rec.runFrom)) {
        const mine = rec.mine, from = rec.runFrom || 0;
        rec.mine = false;
        rec.runFrom = 0;
        const pane = wb.pane;
        if (!pane || pane.tabId !== rec.id) return;
        if (mine && run.status === "error" && run.step) rec.center = run.step;
        if (!composerIdle(pane)) return;
        const has = !run.dry_run && ((run.tables || []).length || (run.opts || []).length);
        if (mine && run.status === "error") { showPanel(pane, "log"); rec.toErr = true; }
        else if (run.status === "done" && has && !((pane.navAt || 0) > from)) showRunResults(pane, tab);
      }
    });
  }

  /** The failed step, named as the capsule names it, else its log line. */
  function failedName(tab, rec) {
    const run = tab.run || {}, first = (run.log || []).find((e) => e.level === "error");
    return stepName(rec, run.step) || cut(first && first.text, 40);
  }
  /** The log line a failed step left: the first error on it, else the run's first error. */
  function failedLine(run) {
    const log = run.log || [], err = (e) => e.level === "error";
    const hit = log.find((e) => err(e) && e.id && e.id === run.step) || log.find(err);
    return hit ? String(hit.text) : "";
  }

  /** The failed step (run status error) carries its log line as a Blockly warning (its icon
   *  on the block, the line in its bubble) until a new run starts: pressing Run or Check
   *  here, or a run the AI starts. Its own warning id, so the warning a result in a slot that
   *  writes carries (blocks.js) stays. Idempotent: a version loaded makes the blocks again. */
  const RUN_WARN = "wb-run-error";
  function markFailed(rec, run, starting) {
    const blk = run.status === "error" && !starting && run.step ? rec.ws.getBlockById(run.step) : null;
    const text = blk ? failedLine(run) || t("st_error") : "";
    const w = rec.warn;
    if (w && w.blk === blk && w.text === text) return;
    if (w && !w.blk.isDeadOrDying()) w.blk.setWarningText(null, RUN_WARN);
    rec.warn = blk ? { blk, text } : null;
    if (blk) blk.setWarningText(text, RUN_WARN);
  }

  /** Bring a step into the middle of the block canvas (its own box, not what it holds). One
   *  wider than the view shows from its left edge, where its words start; one taller (an
   *  optimize step with many rows), from its top, clear of the block capsule. */
  function showStep(rec, id) {
    const ws = rec.ws, blk = ws.getBlockById(id);
    if (!blk) return;
    Blockly.renderManagement.triggerQueuedRenders(ws);   // a block just added: at its real size and place
    ws.resizeContents();
    ws.centerOnBlock(id, true);
    const m = ws.getMetrics(), s = ws.scale, at = blk.getRelativeToSurfaceXY();
    const wide = blk.width * s > m.viewWidth - 40, tall = blk.height * s > m.viewHeight - 80;
    if (wide || tall) ws.scroll(wide ? 20 - at.x * s : ws.scrollX, tall ? 56 - at.y * s : ws.scrollY);
  }

  /** Scroll the run log so its first error line shows, with a little of what came before. */
  function toFirstError(pane) {
    const list = pane.q(".tab-log"), first = list.querySelector(".log.err");
    if (!first || !list.clientHeight) return;
    const L = list.getBoundingClientRect(), r = first.getBoundingClientRect();
    if (r.top < L.top || r.bottom > L.bottom) list.scrollTop += r.top - L.top - Math.min(40, list.clientHeight / 4);
  }

  /** What a failed run shows, on a click on its capsule: the log at the first error line, and
   *  the failed step centred in the block canvas. */
  function errorFlow(pane, tab, rec) {
    if (prefs().dockMode === "min") setDock(pane, "split");
    showPanel(pane, "log");
    toFirstError(pane);
    const run = tab.run || {};
    if (run.step && !editing(rec)) showStep(rec, run.step);
  }

  /** The results of a run, open on the item it made last: the latest line of its log that
   *  belongs to one of the results (a loop's or an optimize step's id; a statement that made
   *  several, as a pinch run does, "id:part": the first of them, its summary). */
  function showRunResults(pane, tab) {
    const res = tab.results || {}, keys = [...(res.tables || []), ...(res.opts || [])].map((x) => x.id).filter((k) => typeof k === "string");
    const log = (tab.run && tab.run.log) || [];
    let key = null;
    for (let i = log.length - 1; i >= 0 && !key; i--) {
      const id = log[i].id;
      if (id) key = keys.find((k) => k === id) || keys.find((k) => k.startsWith(`${id}:`)) || null;
    }
    if (key) WBR.choice[tab.id] = Object.assign(WBR.choice[tab.id] || {}, { item: key });
    else if (WBR.choice[tab.id]) delete WBR.choice[tab.id].item;   // (none named: the newest, not one picked before)
    showPanel(pane, "results");
  }

  /** The Aspen error behind a failed step: the block its path names, where Aspen reports an
   *  error on that block ({name, msg, lines}), else null. The path is the step's own, else the
   *  one in the log line's words. */
  function causeOf(tab, e) {
    if (!e || e.level !== "error") return null;
    const st = e.id ? findStmt(tab.program, e.id) : null;
    const m = /\\Data\\Blocks\\([^\\\s]+)/i.exec(`${(st && st.path) || ""} ${e.text || ""}`);
    const s = m && (sessOf(tab).status || {})[m[1]];
    return s && s.level === "error" ? { name: m[1], msg: s.msg || "", lines: s.lines || [] } : null;
  }

  const LEVEL = { info: "", warn: "warn", error: "err" };
  /** The run log, and the log segment's dot (the capsule's words are its tooltip). While a
   *  Run or Check is on its way, the log starts over with a quiet "Starting…". A line from a
   *  step that is in the program shows that step when clicked; an error line also offers to
   *  ask the AI about it. A failed run started here shows its first error line and centres the
   *  failed step, once (settle sets that up). Each Run simulation and Save model on the model
   *  is a line among them, by time (modelLogOf, app-model.js; not a step: a click does nothing). */
  function renderRun(pane, tab, rec) {
    const run = tab.run || {}, q = pane.q, starting = !!rec.pending && rec.pending.kind !== "stop";
    q(".run-dot").className = `run-dot ${starting || run.status === "queued" ? "running" : run.status || "idle"}`;
    // the running step is outlined in the run colour (not while the connection is lost: what
    // runs is then unknown); the step that failed, in red, with its log line as a warning,
    // until a new run starts
    rec.el.classList.toggle("run-err", run.status === "error");
    const at = (pausedOf(tab) || {}).at || run.step;          // (paused: the step it waits before)
    rec.ws.highlightBlock((run.status === "running" && wb.connected) || (run.status === "error" && !starting) ? at || null : null);
    markFailed(rec, run, starting);
    const log = run.log || [];
    // (an error line under which Aspen's own error on the block it names is said: a new status
    // of the session's blocks redraws the log)
    const errs = Object.entries(sessOf(tab).status || {}).filter(([, s]) => s.level === "error").map(([k, s]) => `${k}:${s.msg}`).join("|");
    // each Run simulation and Save model on the model: a line among the program's, by time
    const ml = modelLogOf(tab.session);
    // the Aspen paths in the lines by their names (labels.js; each path in its name's tooltip),
    // never as backslash paths
    const words = (s) => WBL.rich(s, tab.session);
    const logSig = [tab.id, I18N.lang, log.length, log.length && log[log.length - 1].t, run.status, starting, errs,
      ml.length, ml.length && ml[ml.length - 1].key, WBL.ver];
    if (changed(pane, "log", logSig)) {
      const line = (e, i) => {
        const err = e.level === "error", c = err ? causeOf(tab, e) : null;
        return `<div class="log ${LEVEL[e.level] || ""}" data-id="${esc(e.id || "")}" data-n="${i}">`
          + `<span class="lt">${words(e.text)}</span>`
          // (its "Ask AI": an icon, shown under the pointer or the keyboard, as a Changes row's)
          + (err ? `<button class="lask flat icon" data-l="ask" title="${esc(t("tip_log_ask"))}" aria-label="${esc(t("tip_log_ask"))}">${icon("chat")}</button>` : "")
          + `</div>`
          // where Aspen reports an error on the block the step names: that is likely why
          + (c ? `<div class="log cause" data-n="${i}"><span class="lt">${esc(t("log_cause", c.name, c.msg))}</span>`
            + `<button class="lask show" data-l="show" title="${esc(t("tip_log_show", c.name))}">${icon("block")}<span class="bt">${esc(t("log_show"))}</span></button></div>` : "");
      };
      const mline = (m) => `<div class="log sim${m.cls ? ` ${m.cls}` : ""}" data-k="${esc(m.key)}"${m.tip ? ` title="${esc(m.tip)}"` : ""}>`
        + `<span class="lt">${esc(m.text)}</span></div>`;
      let j = 0, html = "";
      const upTo = (at) => { while (j < ml.length && ml[j].t <= at) html += mline(ml[j++]); };
      if (!starting) log.forEach((e, i) => { upTo(typeof e.t === "number" ? e.t : -Infinity); html += line(e, i); });
      upTo(Infinity);
      q(".tab-log").innerHTML = starting ? `${html}<div class="log dim">${esc(t("log_starting"))}</div>`
        : html || `<div class="hint">${esc(t("log_hint"))}</div>`;
      q(".tab-log").scrollTop = 1e9;
      // a hidden log cannot scroll: it goes to its newest lines (a failed run's first error)
      // when it shows
      pane.logTo = q(".tab-log").clientHeight || starting ? null : run.status === "error" ? "error" : "end";
    }
    // which lines name a step in the program: marked in place, so an edit does not redraw the
    // log (nor move it)
    if (changed(pane, "logGo", logSig.concat(tab.program_rev))) {
      q(".tab-log").querySelectorAll(".log[data-n]").forEach((el) => {
        const go = !!(el.dataset.id && rec.ws.getBlockById(el.dataset.id));
        el.classList.toggle("go", go);
        el.title = go ? t("tip_log_go") : "";
      });
    }
    if (rec.toErr) { rec.toErr = false; toFirstError(pane); }
    if (rec.center) {
      const id = rec.center;
      rec.center = null;
      if (!editing(rec)) showStep(rec, id);
    }
    renderCursor(pane, "state");
  }

  /** A click in the run log: a line from a step in the program selects that step and centres
   *  it; an error line's Ask AI puts the line in the composer (with Aspen's own words on the
   *  block behind it, where there are some), the chip on the stream or block the step's path
   *  names (else that block, else the whole tab); the line under it that names that block
   *  shows it on the flowsheet. Selecting text to copy is no click. */
  function logAct(pane, ev) {
    const el = ev.target.closest(".log[data-n]"), tab = tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id);
    if (!el || !rec) return;
    const e = ((tab.run || {}).log || [])[Number(el.dataset.n)];
    if (!e) return;
    const c = causeOf(tab, e);
    if (ev.target.closest("[data-l=show]")) {
      if (c) pick(pane, { kind: "block", name: c.name }, { ring: true });
      return;
    }
    if (ev.target.closest("[data-l=ask]")) {
      const st = e.id ? findStmt(tab.program, e.id) : null;
      const m = /^\\Data\\(Streams|Blocks)\\([^\\]+)/i.exec((st && st.path) || "");
      const target = m ? { kind: m[1].toLowerCase() === "streams" ? "stream" : "block", name: m[2] } : c ? { kind: "block", name: c.name } : null;
      focusComposer(pane, { pin: { target }, text: c ? t("c_err_cause", e.text, c.name, c.lines.join("\n").trim() || c.msg) : t("c_err_text", e.text) });
      return;
    }
    if (el.classList.contains("cause")) return;
    const blk = e.id && rec.ws.getBlockById(e.id);
    if (!blk || String(window.getSelection() || "")) return;
    Blockly.common.setSelected(blk);             // (focused first: Blockly scrolls to what it focuses)
    showStep(rec, e.id);
  }

  /** The run cursor: a frost pill beside the step running now, an HTML overlay in the block
   *  card (nothing inside the SVG moves). It glides to a new step (transform only); a scroll,
   *  a zoom or an edit moves it at once (why "view"); it fades out when the run ends or the
   *  connection is lost (the capsule then says the run's state is unknown), and is hidden
   *  while its step is out of view. A new step of the shown tab is scrolled into view
   *  unless the user pressed on the canvas or turned the wheel there in the last ten seconds,
   *  or is editing. Placed right of the step's own shape (a C-shaped step's too, not what it
   *  holds), level with its first row; left of it where the card has no room. A run paused
   *  before the step shows a card there instead (app-step.js, placeStepCard). */
  function renderCursor(pane, why) {
    const el = pane && pane.q(".run-cur");
    if (!el) return;
    const tab = tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id), run = (tab && tab.run) || {};
    const at = (pausedOf(tab) || {}).at || run.step;          // (paused: the step it waits before)
    const blk = rec && run.status === "running" && at && wb.connected ? rec.ws.getBlockById(at) : null;
    const path = blk && blk.pathObject && blk.pathObject.svgPath;
    // the same tab as last time: its steps glide and scroll; a tab just shown (or a window
    // just opened on a run) puts the cursor in place and leaves the view alone
    const same = !!tab && pane.curTab === tab.id;
    pane.curTab = tab ? tab.id : null;
    if (!path) {
      placeStepCard(pane, null);
      if (pane.curStep && !el.classList.contains("hidden")) {    // the run ended: fade out
        el.classList.remove("step");
        el.classList.add("out");
        clearTimeout(pane.curTimer);
        pane.curTimer = setTimeout(() => el.classList.add("hidden"), 220);
      }
      pane.curStep = null;
      return;
    }
    const step = `${tab.id}|${at}`, moved = step !== pane.curStep && why === "state";
    const box = pane.q(".blockly").getBoundingClientRect(), s = rec.ws.scale;
    const bar = pane.q(".blk-bar").getBoundingClientRect();     // a held version's pill, top right
    // (the canvas's own top: under the proposal's window where it sits over the blocks, app-proposal.js insetBlocks)
    const top0 = rec.el.getBoundingClientRect().top;
    if (moved && same && Date.now() - (pane.touchAt || 0) > 10000 && !editing(rec) && !rec.ws.isDragging()) {
      // (clear of the capsule, and a row more, 56 units, so the step before it shows whole too:
      // a step scrolled to the top would sit under it)
      // (paused: room over it for the card beside it, app-step.js)
      const b = blk.getBoundingRectangleWithoutChildren(), top = Math.max(0, bar.bottom - top0 + 8 - 24) / s + (pausedOf(tab) ? Math.max(56, 124 / s) : 56);
      rec.ws.scrollBoundsIntoView(new Blockly.utils.Rect(b.top - top, b.bottom, b.left, b.right), 24);
    }
    const r = path.getBoundingClientRect();
    const tb = rec.ws.getToolbox(), minX = rec.ws.getParentSvg().getBoundingClientRect().left - box.left + (tb ? tb.getWidth() : 0);
    if (pausedOf(tab) && placeStepCard(pane, { blk, path, box, bar, minX, scale: s, top: top0 - box.top })) {   // paused: the card, not the pill
      clearTimeout(pane.curTimer);
      el.classList.remove("step");
      el.classList.add("hidden");
      pane.curStep = step;
      return;
    }
    placeStepCard(pane, null);
    const rowH = Math.min(r.height, 48 * s);
    let x = r.right - box.left + 6;
    const y = r.top - box.top + Math.min(8, Math.max(0, (rowH - 18) / 2));
    const under = (cx) => bar.height && box.left + cx + 22 > bar.left - 4 && box.top + y < bar.bottom + 4 && box.top + y + 18 > bar.top - 4;
    if (x + 22 > box.width - 8 || under(x)) x = r.left - box.left - 28;   // no room at its right: at its left
    x = Math.round(Math.max(minX + 2, Math.min(x, box.width - 30)));
    const off = r.bottom < top0 + 4 || r.top > box.bottom - 12 || r.right < box.left + minX || r.left > box.right - 8;
    const xy = `translate3d(${x}px, ${Math.round(y)}px, 0)`, was = el.classList.contains("hidden") || el.classList.contains("out");
    clearTimeout(pane.curTimer);
    el.classList.remove("out");
    el.classList.toggle("hidden", off);
    if (moved && same && !was && !off) el.classList.add("step");   // glide to the new step
    else if (el.style.transform !== xy) el.classList.remove("step");   // the view moved: at once
    el.style.transform = xy;
    pane.curStep = step;
  }

  Object.assign(WBA, { blocker, errorFlow, logAct, renderCursor, renderRun, sayFailure, settle,
    showRunResults, showStep, startRun, stopRun, toFirstError });
})();
