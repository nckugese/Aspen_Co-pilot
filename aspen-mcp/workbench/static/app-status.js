/* The block program's run bar, at the top of the program column (.prog-bar): the status
 * capsule (statusOf: what the tab is doing, the step's name, a loop's pass, an optimization's
 * progress), Run program/Stop/Check program's state and tooltips, a click on the capsule, the
 * folded column's strip, and polling the progress of running optimizations. renderRunbar
 * draws both bars: the header's model group (app-model.js) and this one.
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { blocker, busy, cut, errorFlow, guard, prefs, sentences, setDock, showPanel, showRunResults,
    steps, t, tabOf, wb } = WBA;
  const { pausedOf, propOf, propWord, renderGroup, renderModelBar, renderProposal, renderStepBar, underline } = WBA.later;
  /** A number in a few characters: 1051, 0.52, 3.18e5. */
  const fmtNum = (v) => {
    if (typeof v !== "number" || !isFinite(v)) return String(v ?? "—");
    const a = Math.abs(v);
    return a && (a >= 1e5 || a < 1e-3) ? v.toExponential(2).replace("e+", "e") : String(Number(v.toPrecision(4)));
  };
  /** What a step block says, and the blocks plugged into it (not the steps inside it), less
   *  what does not name the step: a menu choice's "(RadFrac)" or "(kg/hr)", a tick box (an
   *  unticked one takes its " · clause" along), an empty field (and its label), the variable
   *  a read stores into. Cut at 48 characters; the capsule's ellipsis takes what does not fit. */
  function stepName(rec, id) {
    const blk = id && rec.ws.getBlockById(id);
    if (!blk) return "";
    const words = [], label = () => { const w = words[words.length - 1]; return w && !w.f.name ? w : null; };
    let head = true;                  // a C block is named by its head: its bodies (and their labels) are steps of their own
    const walk = (b) => b.inputList.forEach((inp) => {
      if (inp.connection && inp.connection.type === Blockly.ConnectionType.NEXT_STATEMENT) head = false;
      if (!head || !inp.isVisible()) return;
      inp.fieldRow.forEach((f) => {
        if (!f.isVisible()) return;
        if (f instanceof Blockly.FieldCheckbox) {
          if (f.getValue() !== "TRUE" && label()) label().w = label().w.replace(/\s·\s[^·]*$/, "");
          return;
        }
        let w = f.getText().trim();
        if (f instanceof Blockly.FieldDropdown) w = w.replace(/\s*[(（][^()（）]*[)）]$/, "");
        if (w && w !== "—") words.push({ f, w });
        else if (f.name && label()) words.pop();
      });
      const c = inp.connection && inp.connection.type === Blockly.ConnectionType.INPUT_VALUE && inp.connection.targetBlock();
      if (c) walk(c);
    });
    walk(blk);
    const n = words.length;           // "into variable x" at the end says where, not what
    if (n > 1 && words[n - 1].f.name === "AS" && !words[n - 2].f.name) words.length = n - 2;
    return cut(words.map((x) => x.w).join(" "), 48);
  }
  function findStmt(list, id) {
    for (const s of list || []) {
      if (s.id === id) return s;
      const hit = findStmt(s.body, id) || findStmt(s.then, id) || findStmt(s.else, id);
      if (hit) return hit;
    }
    return null;
  }
  /** A value block's name, as its block shows it: a variable or an expression, a stream's or
   *  block's name and the quantity picked in its menu (without "(result)" and the like). */
  function valueName(v) {
    if (!v) return "";
    const f = (n) => { const x = v.getField(n); return x ? x.getText().replace(/\s*[(（][^()（）]*[)）]$/, "").trim() : ""; };
    if (v.type === "wb_var") return v.getFieldValue("NAME");
    if (v.type === "wb_expr") return v.getFieldValue("EXPR");
    if (v.type === "wb_stream") return [v.getFieldValue("S"), f("P"), v.getField("C").isVisible() ? f("C") : ""].filter(Boolean).join(" ");
    if (v.type === "wb_block") return [v.getFieldValue("B"), f("P")].filter(Boolean).join(" ");
    return pathName(v.getFieldValue("RAW"));
  }
  /** A raw path's name: a stream's or block's name and the quantity (\Data\Streams\PRODUCT\Output\
   *  MASSFLMX\MIXED: "PRODUCT MASSFLMX"); else its last two parts. */
  function pathName(p) {
    const parts = String(p || "").split("\\").filter(Boolean);
    return /^(Streams|Blocks)$/i.test(parts[1] || "") ? [parts[2], parts[4]].filter(Boolean).join(" ") : parts.slice(-2).join(" ");
  }
  /** The objectives of an optimize step, named as its blocks name them (the goal blocks under
   *  the running wb_optimize: an expression's text, a path's object and quantity); from the
   *  program when the block is not there. A unit only where the program gives one. */
  function objectives(tab, rec, id) {
    const st = findStmt(tab.program, id), blk = rec.ws.getBlockById(id), goals = [];
    for (let g = blk && blk.getInputTargetBlock("OBJS"); g; g = g.getNextBlock()) goals.push(g);
    return ((st && st.objectives) || []).map((o, i) => {
      const g = goals[i];
      const shown = g ? (g.type === "wb_optobjx" ? g.getFieldValue("EXPR") : valueName(g.getInputTargetBlock("PATH"))) : "";
      return { name: cut(shown || (o.expr ? o.expr : pathName(o.path)), 16), unit: o.unit || "" };
    });
  }

  /** How far the loop around the running step has gone, where the run tells it for sure: a
   *  loop's table (run.tables, by its id) gets a row as each pass ends, so a sweep or repeat
   *  is on pass rows mod n + 1 of n (nested, and called again from a procedure, too); a
   *  repeat-until only where nothing repeats it (its passes restart), on pass rows + 1 of at
   *  most max. A design spec's passes have no total: it is passed over for a loop around it.
   *  Null when no loop tells (a check records no rows). */
  function loopAt(tab, run) {
    const trail = (function find(list, up) {
      for (const s of list || []) {
        if (s.id === run.step) return up.concat(s);
        for (const k of ["body", "then", "else"]) { const hit = find(s[k], up.concat(s)); if (hit) return hit; }
      }
      return null;
    })(tab.program, []);
    if (!trail || run.dry_run) return null;
    const loops = trail.filter((s) => ["sweep", "repeat", "until", "seek"].includes(s.do));
    const rows = (s) => { const tb = (run.tables || []).find((x) => x.id === s.id); return tb && tb.rows ? tb.rows.length : 0; };
    for (let i = loops.length - 1; i >= 0; i--) {
      const s = loops[i];
      if (s.do === "sweep" || s.do === "repeat") {
        const n = Math.max(1, Math.floor(Number(s.do === "sweep" ? s.steps : s.times) || 1)), done = rows(s) % n;
        return { text: t(s.do === "sweep" ? "lp_sweep" : "lp_repeat", done + 1, n), short: `${done + 1}/${n}`, frac: done / n };
      }
      if (s.do === "until" && i === 0 && trail[0].do !== "proc") {
        const most = Math.max(1, Math.floor(Number(s.max) || 100)), n = Math.min(rows(s) + 1, most);
        return { text: t("lp_until", n, most), short: t("lp_until_s", n), frac: null };   // no total: no bar
      }
    }
    return null;
  }
  function duration(run) {
    const s = run.finished && run.started ? run.finished - run.started : null;
    if (s === null || s < 0) return "";
    return s < 60 ? t("dur_s", s.toFixed(1)) : t("n_min", (s / 60).toFixed(1));
  }

  /** What the shown tab is doing, for the capsule: cls (its colour), long text, short text
   *  (a narrow window), go (the dock panel a click opens), frac (progress, 0..1) and tip (its
   *  tooltip: the long text, or more where that is short); quiet: ready with nothing to report,
   *  the default state, which the capsule does not show. */
  function statusOf(tab, rec) {
    const run = tab.run || {}, st = run.status || "idle", p = rec.pending, dry = !!run.dry_run;
    const S = (cls, long, short, go, frac, tip) => ({ cls, long, short: short || long, go: go || "", frac: frac ?? null, tip: tip || long });
    if (busy(tab) && !wb.connected) return S("lost", t("st_lost"), t("st_lost_s"), "log");
    if (p && p.kind === "stop") return S("busy", run.progress ? t("opt_cancelling") : t("st_stopping"), t("st_stopping_s"), "log");
    if (p) return S("pending", t("st_sending"), null, "log");
    // before the running words: an unanswered Stop says so too, then the run shows again
    if (rec.noReply && Date.now() - rec.noReply < 8000) return S("error", t("st_noreply"), t("st_noreply_s"));
    if (st === "running" && run.progress) {
      const got = wb.prog.get(tab.id), pr = got && got.file === run.progress.file ? got.s : null;
      const algo = (pr && pr.algorithm) || run.progress.algorithm || "";
      if (!pr) return S("busy", `${algo} · ${t("st_running")}`, t("st_running"), "log", 0);
      const total = Math.max(1, pr.total || 1), n = Math.min(pr.eval_count || 0, total);
      const parts = [`${algo} ${n}/${total}`], objs = objectives(tab, rec, run.progress.id);
      if (pr.n_gen > 1) parts.push(t("opt_round", pr.gen || 0, pr.n_gen));
      (pr.best_objs || []).forEach((v, i) => {
        const o = objs[i] || { name: "", unit: "" };
        parts.push([o.name, fmtNum(v), o.unit].filter(Boolean).join(" "));
      });
      return S("busy", parts.join(" · "), `${n}/${total}`, "log", n / total);
    }
    const pa = pausedOf(tab);
    if (pa) {                                    // stepped through: waiting for the user's press
      const long = t(pa.why === "break" ? "st_paused_brk" : "st_paused", pa.n ?? "?");
      return S("paused", long, t("st_paused_s", pa.n ?? "?"), "log", null, `${long}
${t("tip_st_paused")}`);
    }
    if (st === "running") {
      const name = stepName(rec, run.step), word = t(dry ? "st_checking" : "st_running"), loop = loopAt(tab, run);
      if (loop) return S("busy", name ? t("st_run_loop", loop.text, name) : t("st_run_step", loop.text), loop.short, "log", loop.frac);
      return S("busy", name ? t(dry ? "st_check_step" : "st_run_step", name) : word, word, "log");
    }
    if (st === "queued") {
      const other = wb.state.tabs.find((x) => x.id !== tab.id && x.session === tab.session && x.run.status === "running");
      return S("busy", other ? t("st_queued_on", other.title) : t("st_queued"), t("st_queued"), "log");
    }
    if (st === "error") {
      const first = (run.log || []).find((e) => e.level === "error");
      const what = stepName(rec, run.step) || cut(first && first.text, 40);
      return S("error", what ? t("st_error_at", what) : t("st_error"), t("st_error"), "log");
    }
    // (not connected: the header's indicator is the one place that says so; the capsule keeps the last state)
    const why = blocker(tab, rec);
    if (why && !why.off) return S("blocked", why.short, why.short, "", null, why.long);   // the tooltip says what to do
    const dur = duration(run);
    // a run or check that ended well, or was stopped: not shown; Run program's tooltip says
    // it (ended). A check that found something stays: it is something to look at
    const quiet = (x, ended) => Object.assign(x, { quiet: true, ended });
    if (st === "done" && dry) {
      const warns = (run.log || []).filter((e) => e.level === "warn").length;
      const x = S("done", warns ? t(warns === 1 ? "st_check_warn_1" : "st_check_warn", warns) : t("st_check_ok", dur), t("st_checked"), "log");
      return warns ? x : quiet(x, x.long);
    }
    if (st === "done") {
      const res = tab.results || {}, n = res.finished && res.finished === run.finished ? (res.tables || []).length + (res.opts || []).length : 0;
      return quiet(S("done", n ? t(n === 1 ? "st_done_res_1" : "st_done_res", dur, n) : t("st_done_t", dur), t("st_done"), n ? "results" : "log"),
        n ? t(n === 1 ? "st_done_res_1" : "st_done_res", dur, n) : t("st_done_t", dur));
    }
    if (st === "stopped") { const w = dur ? t("st_stopped_t", dur) : t("st_stopped"); return quiet(S("stopped", w, t("st_stopped"), "log"), w); }
    const n = steps(rec).all, pw = propWord(tab);
    // the AI's proposal: where it stands is its window's and its tab's to say
    if (pw) return Object.assign(S("idle", t(n === 1 ? "st_prop_ready_1" : "st_prop_ready", pw, n), pw), { quiet: true });
    // ready, with nothing to report: the default state, not shown (quiet: the capsule hides,
    // and the log tab's tooltip leaves it out)
    return Object.assign(S("idle", t(n === 1 ? "st_ready_1" : "st_ready", n), t("st_ready_s")), { quiet: true });
  }

  /** The program's run bar for the tab the pane shows: Run program or Stop (one place), Check
   *  program, the status capsule; and the folded column's strip, which keeps a dot while the
   *  program runs or failed. A button that cannot act says why in its tooltip. Run program is
   *  F6 (F5 is Run simulation). */
  function renderProgBar(pane) {
    const tab = pane && tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id);
    if (!tab || !rec) return;
    const bar = pane.q(".prog-bar"), b = busy(tab), p = rec.pending, why = blocker(tab, rec);
    const q = (a) => bar.querySelector(`[data-a="${a}"]`), run = q("run"), check = q("check"), stop = q("stop");
    bar.classList.toggle("busy", !!b);
    // the AI's proposal: its window holds the decision (Approve and run), so the bar
    // keeps Check, and Stop while it runs; which proposal is shown is the sub-tab row's (app-subtabs.js)
    const prop = !!propOf(tab);
    if (bar.classList.contains("prop") !== prop) bar.classList.toggle("prop", prop);
    run.disabled = check.disabled = !!(why || p);
    // Run program is a plain button (Run simulation is the header's one primary action): its tooltip
    // says how the two differ, and how the last run ended (the capsule leaves a run that ended
    // well to it)
    const dot = I18N.lang === "zh" ? "。" : ".", s = statusOf(tab, rec);
    run.title = p && p.kind !== "stop" ? t("st_sending") : why ? why.long
      : [sentences(t("tip_run", "F6") + dot, t("tip_run_more") + dot), s.ended || ""].filter(Boolean).join("\n");
    check.title = p && p.kind !== "stop" ? t("st_sending") : why ? why.long : t("tip_check");
    stop.disabled = !wb.connected || !!(p && p.kind === "stop");
    stop.title = !wb.connected ? t("why_stop_off") : p && p.kind === "stop" ? t("st_stopping") : t("tip_stop");
    run.tabIndex = b ? -1 : 0;                   // the one hidden stays out of the tab order
    stop.tabIndex = b ? 0 : -1;
    run.setAttribute("aria-hidden", String(!!b));
    stop.setAttribute("aria-hidden", String(!b));
    const el = pane.q(".prog-stat"), sig = JSON.stringify([I18N.lang, s.cls, s.long, s.short, s.go, s.tip, !!s.quiet]);
    if (el.dataset.sig !== sig) {
      const txt = el.querySelector(".st");
      // a new state, not a new number: the old words rise out (a copy where they were), the new
      // ones rise in; not from or to the ready state, which is not shown
      if (el.dataset.cls && el.dataset.cls !== s.cls && !s.quiet && el.dataset.quiet !== "1") {
        const old = txt.cloneNode(true);
        old.classList.add("st-old");
        old.setAttribute("aria-hidden", "true");
        el.appendChild(old);
        old.animate([{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateY(-4px)" }],
          { duration: 120, easing: "cubic-bezier(.4, 0, 1, 1)", fill: "forwards" }).onfinish = () => old.remove();
        txt.animate([{ opacity: 0, transform: "translateY(4px)" }, { opacity: 1, transform: "none" }],
          { duration: 200, easing: "cubic-bezier(.2, .8, .2, 1)" });
      }
      el.className = `runstat prog-stat ${s.cls}${s.go ? " go" : ""}${s.quiet ? " hidden" : ""}`;
      el.dataset.quiet = s.quiet ? "1" : "";
      el.querySelector(".st-long").textContent = s.long;
      el.querySelector(".st-short").textContent = s.short;
      // (a capsule that opens something says what: the run log, or Tables & charts)
      el.title = [s.tip, s.go === "log" ? t("tip_stat_go_log") : s.go === "results" ? t("tip_stat_go_res") : ""].filter(Boolean).join("\n");
      el.dataset.cls = s.cls;
      el.dataset.sig = sig;
      // the strip: a dot while it runs, is stopping, or failed; its words in the tooltip (its
      // title alone otherwise)
      const strip = pane.q(".prog-strip"), mark = ["busy", "pending", "error", "lost", "paused"].includes(s.cls);
      strip.querySelector(".dot").className = `dot${mark ? ` ${s.cls}` : ""}`;
      strip.title = [t("prog_title"), mark ? s.long : ""].filter(Boolean).join("\n");
    }
    const line = el.querySelector(".st-bar");
    line.classList.toggle("on", s.frac !== null);
    if (s.frac !== null) line.firstElementChild.style.transform = `scaleX(${s.frac})`;
    const log = pane.q('.panel nav [data-tab="log"]'), ltip = s.quiet ? t("tip_tab_log") : `${t("tip_tab_log")}\n${s.long}`;
    if (log.title !== ltip) log.title = ltip;
    // (each on its own: guard)
    guard("renderStepBar", () => renderStepBar(pane));   // Step; paused: Run to the end, Run next step; the breakpoints
    guard("renderGroup", () => renderGroup(pane));       // a run by group: its card, and the bar keeps only its line (app-group.js)
    guard("renderProposal", () => renderProposal(pane)); // (drawn again only where it moved)
    fitStat(el);
    if (!bar.fitObs) {                           // the column's width changes: fitted again
      bar.fitObs = new ResizeObserver(() => fitStat(bar.querySelector(".prog-stat")));
      bar.fitObs.observe(bar);
    }
  }
  /** The capsule's words where the bar leaves room, never cut to a stub: the long ones while
   *  they fit, or show at least the short word and a little more (a long step name keeps its
   *  ellipsis), else the short word whole; still not, the bar gives way as a narrow column's does
   *  (style.css @container prog): the title first (.fit-nt, the long words tried again), then
   *  Check program's and Step's labels (.fit-slim, their tooltips name them); last, the capsule's
   *  dot alone (.tight, the words in its tooltip). */
  const FIT = [[], ["short"], ["nt"], ["nt", "short"], ["nt", "short", "slim"], ["nt", "short", "slim", "tight"]];
  function fitStat(el) {
    const bar = el && el.closest(".prog-bar");
    if (!bar) return;
    const set = (on) => {
      el.classList.toggle("short", on.includes("short"));
      el.classList.toggle("tight", on.includes("tight"));
      bar.classList.toggle("fit-nt", on.includes("nt"));
      bar.classList.toggle("fit-slim", on.includes("slim"));
    };
    if (el.classList.contains("hidden")) { set([]); return; }
    const st = el.querySelector(".st");
    set(["short"]);
    const word = st.scrollWidth;                 // the short word's own width
    FIT.find((on) => {
      set(on);
      const w = st.clientWidth;
      return on.includes("tight") || st.scrollWidth <= w + 1 || (!on.includes("short") && w >= word + 16);
    });
  }

  /** Both run bars: the header's model group and the shown program's. */
  function renderRunbar() {
    guard("renderModelBar", () => renderModelBar());
    if (wb.pane) guard("renderProgBar", () => renderProgBar(wb.pane));
  }

  /** A click on the capsule opens what it talks about: the log while a run goes; after an
   *  error, the log at its first error line with the failed step centred (errorFlow); the
   *  results after a run that made some, on the item it made last. */
  function openStatus(pane, tab, rec) {
    const s = statusOf(tab, rec);
    if (!s.go) return;
    if (prefs().dockMode === "min") setDock(pane, "split");
    if (s.cls === "error" && (tab.run || {}).status === "error") errorFlow(pane, tab, rec);
    else if (s.go === "results") showRunResults(pane, tab);
    else showPanel(pane, s.go);
  }

  /** Poll the progress file of every optimization running now (the capsule and the tabs'
   *  underlines read it); nothing is polled while none runs. */
  function pollProgress() {
    const files = new Map(), api = window.pywebview && window.pywebview.api;
    ((wb.state && wb.state.tabs) || []).forEach((x) => {
      if (x.run && x.run.status === "running" && x.run.progress && x.run.progress.file) files.set(x.id, x.run.progress.file);
    });
    [...wb.prog.keys()].forEach((id) => { if (files.get(id) !== (wb.prog.get(id) || {}).file) wb.prog.delete(id); });
    wb.progFiles = files;
    if (!files.size || !(api && api.progress)) { clearInterval(wb.progTimer); wb.progTimer = 0; return; }
    if (wb.progTimer) return;
    const tick = () => wb.progFiles.forEach((file, id) => api.progress(file).then((s) => {
      if (!s || wb.progFiles.get(id) !== file) return;
      wb.prog.set(id, { file, s });
      underline(id);
      if (wb.pane && wb.pane.tabId === id) renderProgBar(wb.pane);
    }).catch(() => {}));
    tick();
    wb.progTimer = setInterval(tick, 700);
  }

  Object.assign(WBA, { duration, findStmt, openStatus, pollProgress, renderRunbar, stepName });
})();
