/* The AI's proposal. A tab of kind "proposal" holds a change the AI
 * wrote as a block program for the user to review (tools/proposals.py). Its card sits under the
 * program's run bar, over the blocks (.prop-card): the title, the AI's reason, what it does in
 * short, its status and version, and the decision -- Approve and run (the approval: a restore
 * point first, then the steps; the restore point in its tooltip), Step through, Send back… with a
 * comment (the AI gets it word for word). A refused approval says why (the check's errors; no
 * restore point: "Run without a restore point"); after a run, what came of it, with Undo this
 * group and Restore to before the proposal (app-undo.js's previews, nothing done before their own
 * button) -- edited since, a line saying so and Apply my changes and run (only the edits: approve
 * "edits"); sent back, the comment until the AI revises it. The decision's row shows at most three
 * actions, the likeliest next; the rest are behind ⋯ in the head (actList). Under it, each step (the server's
 * check, tab.check): the current value → the proposed one ("computed when it runs" in a loop,
 * "depends on a condition" in an if), flowsheet steps in words, problems on their row, the user's
 * edits marked, turned-off steps greyed; a tick box turns a step off as the block's own menu does;
 * while it runs, the steps done ticked and the one it runs (or is paused before) marked. A row's
 * words select its block and pick what it names on the flowsheet. Rows below the list's view: a
 * fade and a count. A new check (the automatic one included) shows as it comes; one older than
 * the blocks or the model says so; one older than a successful run since is not shown (chkPast).
 * Where the server groups the steps (catalog.features groups: tab.check.groups),
 * the list is by group: each group a line (its number, its title -- the AI's as written, else
 * the server's gc_auto_* template), ⌄ shows its steps (shown at first: a single group, one with a
 * problem, the one a run is in); the technical steps (read, calc, ...) are left to the list's
 * foot ("2 more steps: read, calculate", gc_tech; each in its tooltip) unless one has a problem.
 *
 * Nothing here writes the model: the server acts on events (run {approve, mode}, proposal_reply).
 * While it is stepped through, the run bar holds Run next step and Continue, and a card
 * beside the paused step says what comes next (app-step.js). A tab that is no proposal shows no card.
 *
 *   propOf(tab)            the tab's proposal, else null
 *   propWord(tab)          its status in words (the tab's pill, the run bar), or ""
 *   approveWhy(tab, rec)   why it cannot be approved now ({long, short}), or null
 *   editsOf(tab)           how many of the user's edits its run did not apply (the header's Run simulation tooltip)
 *   renderProposal(pane)   the card of the shown tab (hidden for any other)
 *   stepWords(tab, row)    a step's words as the card's rows say them (html; app-step.js's card)
 *   probHtml(p, session)   a problem on its row (html)
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { busy, changed, cut, esc, feature, fmtVal, icon, isObj, learning, num, prefGet, prefs, prefSet, sessOf, setDock, setHtml, showPanel, t,
    tabOf, tn, toast, toggleMenu, track, wb, when } = WBA;
  const { blocker, changesCtx, closeTab, fitHeld, gcNow, gotoChange, renderBlkEmpty, renderCursor, restoreOpen, showStep, startRun, undoOpen } = WBA.later;

  const STATUSES = ["draft", "open", "running", "applied", "partial", "failed", "stopped", "rejected", "withdrawn", "dismissed"];
  const SHUT = ["withdrawn", "dismissed"];             // no longer to be run: the card offers Close tab
  const ENDED = ["applied", "partial", "failed", "stopped"];
  const REVIEW = ["open", "rejected"];                 // waiting for the user's decision
  const STRUCT = ["place", "connect", "remove", "component", "method"];
  const LOOPS = ["repeat", "until", "sweep", "seek"];
  const NESTED = ["then", "else", "body"];
  const OFF = "wb_off";                                // blocks.js: a step turned off (off: true)
  const SENT_MS = 6000;                                // a send-back not seen answered in this long: the buttons come back

  // ------------------------------------------------------------------ what the proposal is
  const propOf = (tab) => (tab && tab.kind === "proposal" && isObj(tab.proposal) ? tab.proposal : null);
  /** Approved and under way, the proposal not yet marked running (its restore point first). */
  const approving = (tab, p) => { const run = tab.run || {}; return run.status === "running" && !run.dry_run && (!!run.approved || p.status === "running"); };
  /** Its status, for the words: paused while it is stepped through; running from the approval on. */
  function stOf(tab, p) {
    if (p.status === "running" && isObj((tab.run || {}).paused)) return "paused";
    if (REVIEW.includes(p.status) && approving(tab, p)) return "running";
    return STATUSES.includes(p.status) ? p.status : "open";
  }
  const propWord = (tab) => { const p = propOf(tab); return p ? t(`prop_st_${stOf(tab, p)}`) : ""; };
  /** The tab's pill: its status in a word or two ({key, word}), or null. */
  const propPill = (tab) => { const p = propOf(tab), k = p && stOf(tab, p); return k ? { key: k, word: t(`prop_pill_${k}`) } : null; };
  /** Each tab's own conveniences here: the card folded, the send-back box open (its words kept
   *  while the card is drawn anew), a send-back on its way, the check last shown. */
  const LOCAL = new Map();
  const loc = (id) => { if (!LOCAL.has(id)) LOCAL.set(id, { fold: false, form: false, draft: "", sent: 0, chkT: null, hide: false, gopen: {}, gnow: null }); return LOCAL.get(id); };

  /** The program's statements by id. */
  function byId(program) {
    const out = new Map();
    const walk = (list) => (list || []).forEach((s) => { if (isObj(s)) { if (s.id) out.set(s.id, s); NESTED.forEach((k) => walk(s[k])); } });
    walk(program);
    return out;
  }
  /** The rows of a program not checked yet, as tools/wb_plan.outline makes them (no current
   *  values): top-level steps numbered, the rest indented; runtime in a loop or a procedure. */
  function outline(program) {
    const rows = [];
    let n = 0;
    const walk = (list, depth, loop, branch, proc, dead) => (list || []).forEach((s) => {
      if (!isObj(s)) return;
      const row = { id: s.id, n: null, depth, kind: s.do };
      if (depth === 0 && s.do !== "def" && s.do !== "proc") row.n = ++n;
      const off = dead || s.off === true;
      if (off) row.off = true;
      else row.when = loop || proc || (s.do === "set" && s.expr != null && s.expr !== "") ? "runtime" : branch ? "branch" : "now";
      if (STRUCT.includes(s.do)) {
        row.what = {};
        ["block", "stream", "type", "port", "add", "remove", "method"].forEach((k) => { if (s[k] != null && s[k] !== "") row.what[k] = s[k]; });
      } else if (typeof s.path === "string") row.path = s.path;
      if (s.do === "set") row.new = s.expr != null && s.expr !== "" ? { expr: s.expr, unit: s.unit || null } : { value: s.value, unit: s.unit || null };
      if (s.do === "sweep") row.new = { from: s.from, to: s.to, steps: s.steps, unit: s.unit || null };
      rows.push(row);
      NESTED.forEach((k) => walk(s[k], depth + 1, loop || LOOPS.includes(s.do), branch || s.do === "if", proc || s.do === "proc", off));
    });
    walk(program, 0, false, false, false, false);
    return rows;
  }
  /** What the list shows: the server's check (tab.check) where there is one, else the outline. */
  function rowsOf(tab) {
    const c = isObj(tab.check) && Array.isArray(tab.check.steps) ? tab.check : null;
    return c ? { rows: c.steps.filter(isObj), more: Number(c.more) || 0, chk: c } : { rows: outline(tab.program), more: 0, chk: null };
  }
  /** A row's step turned off: its block's own reason (the user's tick box, its menu), or a step
   *  around it off; the server's row where the block is not there. live: its block is. */
  function offOf(rec, row) {
    const b = rec && row.id ? rec.ws.getBlockById(row.id) : null;
    if (!b) return { own: !!row.off, inh: false, live: false };
    const own = b.hasDisabledReason(OFF);
    return { own, inh: !own && b.getInheritedDisabled(), live: true };
  }

  // ------------------------------------------------------------------ words
  const typeWords = (ty) => { const g = WB.gloss("WB_GLOSS_TYPE")[String(ty || "").toUpperCase()]; return g ? `${ty} ${g}` : String(ty || "?"); };
  /** A field by its path: labels.js's words (Aspen's English, our gloss quieter), never a backslash. */
  const label = (path, type, session) => WBL.html(WBL.of(path, type || null, session), "short");
  const unitOf = (d) => (isObj(d) && d.unit ? ` ${d.unit}` : "");
  const valHtml = (d) => (isObj(d) && d.expr != null ? `<code class="pr-x">${esc(cut(d.expr, 48))}</code>`
    : `${esc(cut(fmtVal(isObj(d) ? d.value : d), 40))}${esc(unitOf(d))}`);
  /** What a set statement writes, from the statement itself (a check reads no values of a step off). */
  const stmtNew = (st) => (isObj(st) && st.do === "set" ? (st.expr != null && st.expr !== "" ? { expr: st.expr, unit: st.unit || null }
    : st.value != null ? { value: st.value, unit: st.unit || null } : null) : null);
  /** A set step's values: current → proposed; computed when it runs; depends on a condition. A
   *  step off: the proposed value only (no current value was read for it). */
  function valLine(row, x, off) {
    const nw = row.new || (off ? stmtNew(x.idx.get(row.id)) : null);
    if (off) return nw ? `<span class="pr-v">→ <b class="pr-new">${valHtml(nw)}</b></span>` : "";
    if (row.when === "runtime") {
      const tip = isObj(nw) && nw.expr != null ? ` title="${esc(nw.expr)}"` : "";
      return `<span class="pr-v"${tip}>→ <span class="pr-q">${esc(t("prop_runtime"))}</span></span>`;
    }
    const to = nw ? `<b class="pr-new">${valHtml(nw)}</b>` : "";
    let from = "";
    if (x.values) {
      from = isObj(row.cur) ? `<span class="pr-cur">${valHtml(row.cur)}</span> `
        : row.created ? `<span class="pr-cur pr-q">${esc(t("prop_new_obj"))}</span> ` : `<span class="pr-cur pr-q">—</span> `;
    }
    return `<span class="pr-v">${from}→ ${to}</span>${row.when === "branch" ? ` <small class="pr-q">${esc(t("prop_branch"))}</small>` : ""}`;
  }
  /** What a step does, in words (html); off: a step turned off. */
  function whatHtml(row, st, x, off) {
    const k = row.kind, w = isObj(row.what) ? row.what : null, e = esc;
    if (w && k === "place") {
      if (w.block) return e(t("pw_place_b", w.block, typeWords(w.type)));
      return e(w.type && String(w.type).toUpperCase() !== "MATERIAL" ? t("pw_place_st", w.stream, w.type) : t("pw_place_s", w.stream));
    }
    if (w && k === "connect") return e(t("pw_connect", w.stream, w.block, WB.portLabel(w.port)));
    if (w && k === "remove") return e(w.port ? t("pw_rm_c", w.stream, w.block, WB.portLabel(w.port)) : w.block ? t("pw_rm_b", w.block) : t("pw_rm_s", w.stream));
    if (w && k === "component") return e(w.add ? t("pw_comp_add", w.add) : t("pw_comp_rm", w.remove));
    if (w && k === "method") return e(t("pw_method", w.method));
    if (k === "group") return `${e(t("stp_group"))} ${e(cut((st && st.title) || "", 60))}`;
    const lab = row.path ? label(row.path, x.typeOf(row.path), x.session) : "";
    if (k === "set") return `${lab || e(t("stp_set"))} ${valLine(row, x, off)}`;
    if (k === "sweep") {
      const nw = isObj(row.new) ? row.new : {};
      const range = nw.from != null && nw.to != null ? ` <span class="pr-v">${e(t("pw_range", fmtVal(nw.from), fmtVal(nw.to), nw.steps ?? "?", nw.unit ? ` ${nw.unit}` : ""))}</span>` : "";
      return `${e(t("stp_sweep"))} ${lab}${range}`;
    }
    if (k === "log") return e(t("pw_log", cut((st && st.text) || "", 60)));
    if (k === "call") return e(t("pw_call", (st && st.name) || "?"));
    if ((k === "calc" && st && st.as) || (k === "def" && st && st.name)) return `${e(t(`stp_${k}`))} ${e(cut(String(k === "calc" ? st.as : st.name), 40))}`;
    if (k === "proc") return e(t("pw_proc", (st && st.name) || "?"));
    if (k === "repeat" && st && st.times != null) return e(t("pw_repeat", st.times));
    if (k === "optimize") { const n = isObj(row.new) && num(row.new.vars) ? row.new.vars : ((st && st.variables) || []).length; return e(t("pw_opt", n)); }
    const word = I18N.t(`stp_${k}`) !== `stp_${k}` ? t(`stp_${k}`) : t("stp_other");
    return `${e(word)}${lab ? ` ${lab}` : ""}`;
  }
  /** A problem on its row: an error red, a warning amber; the server's words (a path in them named). */
  function probHtml(p, session) {
    const lv = p.level === "error" ? "err" : p.level === "warn" ? "warn" : "info";
    const L = I18N.lang, line = String((isObj(p.texts) && p.texts[L]) || p.text || p.code || ""), more = (isObj(p.help) && p.help[L]) || "";
    const words = window.WBL ? WBL.rich(line, session) : esc(line);
    const tip = more && more !== line ? ` title="${esc(more)}"` : "";
    return `<div class="pr-pb ${lv}"${tip}>${icon(lv === "info" ? "info" : "warn")}<span>${words}</span></div>`;
  }

  // ------------------------------------------------------------------ the decision
  /** The steps that will run (top level, not turned off), from the blocks as they are. */
  function activeCount(rec, tab) {
    const prog = rec ? WB.workspaceToProgram(rec.ws) : tab.program || [];
    return prog.filter((s) => isObj(s) && s.off !== true && s.do !== "def" && s.do !== "proc" && s.do !== "group").length;
  }
  /** Why the proposal cannot be approved now, beyond why no run can start (blocker): a draft,
   *  withdrawn, running; every step off; errors in a check of the blocks as they are. */
  function approveWhy(tab, rec) {
    const p = propOf(tab);
    if (!p) return null;
    const W = (key, ...a) => ({ long: t(key, ...a), short: t(`${key}_s`) });
    if (p.status === "draft") return W("why_prop_draft");
    if (p.status === "withdrawn") return W("why_prop_withdrawn");
    if (p.status === "dismissed") return W("why_prop_dismissed");
    if (p.status === "running") return W("why_prop_running");
    if (!activeCount(rec, tab)) return W("why_prop_empty");
    const c = isObj(tab.check) ? tab.check : null;
    if (c && num(c.errors) && c.errors > 0 && c.rev === tab.program_rev && !(rec && rec.timer)) {
      const row = (c.steps || []).find((r) => isObj(r) && (r.problems || []).some((q) => q.level === "error")) || {};
      const pb = (row.problems || []).find((q) => q.level === "error") || {};
      const n = row.n ?? nOf(c.steps, row.id) ?? "?";
      return { long: tn("why_prop_errors", c.errors, n, cut((isObj(pb.texts) && pb.texts[I18N.lang]) || pb.text || pb.code || "", 70)), short: t("why_prop_errors_s") };
    }
    return null;
  }
  /** A stopped approval that can continue where it stopped (the server's proposals.resumable):
   *  {at, n, mode, last} -- the blocks as the run left them (no edit since, none waiting to go
   *  out), not taken back --, else null. */
  function resumeOf(tab, rec, p) {
    const r = isObj(p.run) ? p.run : null, res = r && isObj(r.resume) ? r.resume : null;
    if (!res || !["partial", "stopped"].includes(p.status) || r.undone || res.rev !== tab.program_rev || (rec && rec.timer)) return null;
    const top = (tab.program || []).filter((s) => isObj(s) && s.off !== true && s.do !== "def" && s.do !== "proc").map((s) => s.id);
    const i = top.indexOf(res.at);
    if (i <= 0) return null;
    const mode = res.mode === "step" ? "step" : res.mode === "group" && modeOk("group") ? "group" : "run";
    return { at: res.at, n: num(res.n) ? res.n : i + 1, mode, last: num(r.total) ? r.total : top.length };
  }
  /** The user's edits to an applied or partly applied proposal its run did not apply (the server's
   *  proposals.unapplied): how many, while the change is kept (not taken back); else 0. */
  function editsOf(tab) {
    const p = propOf(tab), r = p && isObj(p.run) ? p.run : {};
    return p && ["applied", "partial"].includes(p.status) && !r.undone && Array.isArray(p.unapplied) ? p.unapplied.length : 0;
  }
  /** The top-level step a statement is (or sits in): its number. */
  function nOf(rows, sid) {
    let n = null;
    for (const r of rows || []) {
      if (!isObj(r)) continue;
      if (r.n != null) n = r.n;
      if (r.id === sid) return r.n ?? n;
    }
    return null;
  }

  // ------------------------------------------------------------------ the card
  /** What the rows need: the program, the types of blocks the steps place, the values shown. */
  function context(tab, rec, p, rows, chk) {
    const session = tab.session, fs = sessOf(tab).flowsheet || {}, placed = {};
    rows.forEach((r) => { if (r.kind === "place" && isObj(r.what) && r.what.block) placed[String(r.what.block).toUpperCase()] = r.what.type; });
    const typeOf = (path) => {
      const m = /^\\Data\\Blocks\\([^\\]+)/i.exec(String(path || ""));
      if (!m) return null;
      const b = (fs.blocks || []).find((x) => x && String(x.name).toUpperCase() === m[1].toUpperCase());
      return (b && b.type) || placed[m[1].toUpperCase()] || null;
    };
    const e = isObj(p.edited) && !p.edited.unknown ? p.edited : null;
    return { session, typeOf, idx: byId(tab.program), offs: rows.map((r) => offOf(rec, r)), marks: marksOf(tab, rows), past: chkPast(tab, p, chk),
      values: !!chk, editable: !busy(tab), ask: typeof WB.onAsk === "function",
      // (a revision after a partial run: the steps that applied then, unchanged, start off -- marked already run)
      ran: new Set(Array.isArray(p.ran) ? p.ran.map(String) : []),
      edited: e ? { changed: e.changed || [], added: e.added || [], off: e.off || [], removed: Number(e.removed) || 0 } : null };
  }
  /** A check older than a successful run since -- the proposal applied after it, or the tab's
   *  program run to its end after it: what it warned of is behind the model now, so neither its
   *  line nor its problems show (its rows still do: the steps and the values they set). */
  function chkPast(tab, p, chk) {
    if (!isObj(chk) || !num(chk.t)) return false;
    const r = isObj(p.run) ? p.run : null, run = tab.run || {};
    if (p.status === "applied" && r && num(r.t0) && r.t0 >= chk.t) return true;
    return !run.dry_run && run.status === "done" && num(run.started) && run.started >= chk.t;
  }
  /** "9 steps · add 2 · connect 4 · change 2 values · run once · 1 turned off". */
  function sumWords(rows, offs) {
    const c = { top: 0, off: 0, place: 0, connect: 0, remove: 0, component: 0, method: 0, set: 0, run: 0, loop: 0 };
    rows.forEach((r, i) => {
      const o = offs[i];
      if (o.own && !o.inh) c.off++;
      if (o.own || o.inh || r.kind === "group") return;
      if (r.n != null) c.top++;
      if (["place", "connect", "remove", "component", "method", "set", "run"].includes(r.kind)) c[r.kind]++;
      else if (LOOPS.includes(r.kind) || r.kind === "optimize") c.loop++;
    });
    const parts = [tn("prop_n", c.top)];
    [["place", "ps_place"], ["connect", "ps_connect"], ["remove", "ps_remove"], ["component", "ps_comp"], ["method", "ps_method"],
     ["set", "ps_set"], ["loop", "ps_loop"], ["run", "ps_run"], ["off", "ps_off"]].forEach(([k, key]) => { if (c[k]) parts.push(tn(key, c[k])); });
    return parts.join(" · ");
  }
  const note = (cls, ic, html, btns) => `<div class="pc-note ${cls}">${ic ? icon(ic) : ""}<span class="pc-nt">${html}</span>`
    + `${btns ? `<span class="pc-nb">${btns}</span>` : ""}</div>`;
  const btn = (p, label, o = {}) => `<button class="${o.cls || ""}" data-p="${p}"${o.off ? " disabled" : ""}${o.tip ? ` title="${esc(o.tip)}"` : ""}>`
    + `${o.icon ? icon(o.icon) : ""}<span class="bt">${esc(label)}</span></button>`;

  /** The step number a run stopped or failed at, the error it left. */
  function endAt(tab, r, rows) {
    const sid = r.failed_id || (typeof r.failed_at === "string" ? r.failed_at : null) || r.at || null;
    const n = num(r.failed_at) ? r.failed_at : num(r.n) ? r.n : sid ? nOf(rows, sid) : null;
    const log = ((tab.run || {}).log || []).filter((l) => isObj(l) && l.level === "error");
    const hit = (sid && log.find((l) => l.id === sid)) || log[0];
    return { n: n ?? "?", err: cut(r.error || (hit && hit.text) || "?", 160).replace(/[.。]$/, "") };   // (the sentence's own stop follows)
  }
  /** After an approved run: what came of it; undo it as a group or restore to before it. */
  function resultHtml(tab, p, rows) {
    const r = isObj(p.run) ? p.run : {}, st = p.status, cp = isObj(r.cp) ? r.cp : {}, done = Number(r.done) || 0;
    let text, cls, ic;
    if (st === "applied") {
      text = t("prop_done", when(r.t1 || p.t), r.done ?? r.total ?? "?") + (cp.id ? t("prop_cp_at", when(cp.t || r.t0 || p.t)) : cp.skipped ? t("prop_nocp") : "");
      cls = "ok"; ic = "check";
    } else {
      const e = endAt(tab, r, rows);
      const failed = r.failed_at != null || !!r.failed_id || st === "failed";
      text = failed ? (st === "partial" && done ? t("prop_failed_at", e.n, e.err, done) : t("prop_failed_none", e.n, e.err))
        : st === "partial" && done ? t("prop_stopped_at", e.n, done) : t("prop_stopped_none", e.n);
      cls = st === "partial" ? "warn" : st === "failed" ? "err" : "q"; ic = st === "stopped" ? "stop" : "warn";
    }
    const u = isObj(r.undone) ? r.undone : null;
    if (u) return note(cls, ic, esc(text)) + note("q", "undo", esc(t(u.how === "restore" ? "prop_undone_restore" : "prop_undone_revert", when(u.t))));
    return note(cls, ic, esc(text));          // (what can be done with it: the decision's row, actList)
  }
  /** An approval the server did not run: why, and what can be done. */
  function refusedHtml(tab, p) {
    const f = isObj(p.refused) ? p.refused : null, c = isObj(tab.check) ? tab.check : null;
    if (!f || ENDED.includes(p.status) || p.status === "running") return "";
    if (c && num(c.t) && num(f.t) && c.t > f.t && f.why === "check") return "";   // checked again since
    if (f.why === "cp") {
      return note("warn", "warn", esc(t("prop_ref_cp", cut(f.text || "?", 120))),
        btn("no_cp", t("btn_no_cp"), { tip: t("tip_no_cp") }));
    }
    if (f.why === "check") return note("err", "warn", esc(tn("prop_ref_check", Number(f.errors) || 1)), btn("log", t("run_log"), { cls: "flat pc-lk" }));
    const why = ["draft", "withdrawn", "empty", "running"].includes(f.why) ? t(`why_prop_${f.why}`) : cut((isObj(f.texts) && f.texts[I18N.lang]) || f.text || "?", 160);
    return note("warn", "warn", esc(t("prop_ref", why)));
  }
  /** Sent back: the comment until the AI revises it; revised after it: the version that answers it. */
  function replyHtml(p) {
    const r = isObj(p.reply) ? p.reply : null;
    if (!r) return "";
    if (p.status === "rejected") {
      return note("back", "reply", esc(r.text ? t("prop_rejected_line", when(r.t), cut(r.text, 300)) : t("prop_rejected_line0", when(r.t))));
    }
    const log = Array.isArray(p.log) ? p.log : [], last = (w) => log.map((x) => x && x.what).lastIndexOf(w);
    if (p.status === "open" && last("revised") > last("rejected") && last("rejected") >= 0) {
      return note("q", "sparkle", esc(r.text ? t("prop_revised_line", p.rev || "?", cut(r.text, 160)) : t("prop_revised_line0", p.rev || "?")));
    }
    return "";
  }
  /** The top of the card: the head, then the reason, what it does, where it stands (a draft: the
   *  pill says it; the restore point: the approval's tooltip). */
  function infoHtml(tab, rec, p, rows, x, l) {
    const run = tab.run || {}, sess = sessOf(tab), j = isObj(sess.journal) ? sess.journal : null, st = p.status;
    const out = [], going = approving(tab, p);
    if (p.reason) out.push(`<p class="pc-reason" title="${esc(p.reason)}">${esc(t("reason", p.reason))}</p>`);
    if (st === "withdrawn") out.push(note("q", "close", esc(t("prop_withdrawn_line"))));
    if (st === "dismissed") out.push(note("q", "close", esc(t("prop_dismissed_line", when((isObj(p.dismissed) && p.dismissed.t) || p.t)))));
    out.push(replyHtml(p));
    if (going && st !== "running") {             // (approved without one: no restore point to wait for)
      out.push(l.noCp ? note("busy", "play", esc(t("prop_running0"))) : note("busy", "save", esc(t("prop_cp_saving"))));
    } else if (st === "running" && gcNow(tab)) {
      // (applied by group: where it stands is the group card's, app-group.js -- said once)
    } else if (st === "running" && isObj(run.paused)) {
      const pa = run.paused, row = rows.find((r) => r.id === pa.at), what = row ? ` · ${whatHtml(row, x.idx.get(row.id), x)}` : "";
      out.push(note("busy", "pause", esc(t("prop_paused", pa.n ?? nOf(rows, pa.at) ?? "?")) + what));
    } else if (st === "running") {
      const r = isObj(p.run) ? p.run : {};
      out.push(note("busy", "play", esc(num(r.n) && num(r.total) ? t("prop_running", r.n, r.total) : t("prop_running0"))));
    }
    if (ENDED.includes(st)) out.push(resultHtml(tab, p, rows));
    if (editsOf(tab)) out.push(note("warn", "info", esc(tn("prop_unapplied", editsOf(tab)))));
    if (!going) out.push(refusedHtml(tab, p));
    if (REVIEW.includes(st) && !going) {
      const b = isObj(p.base) ? p.base : null, model = (sess.model && sess.model.id) || (j && j.model) || null;
      if (b && num(b.input_t) && j && num(j.last_input_t) && j.last_input_t > b.input_t + 1e-3 && (!b.model || !model || b.model === model)) {
        out.push(note("warn", "info", esc(t("prop_base_stale"))));
      }
    }
    return out.filter(Boolean).join("");
  }
  /** The restore point an approval makes first, for the approval's tooltips: about how long. */
  function cpEstimate(tab) {
    const est = isObj(tab.check) && num(tab.check.est_cp_s) ? tab.check.est_cp_s : null;
    return est ? t("prop_cp", window.WBC && WBC.est ? WBC.est(est) : `${Math.round(est)} s`) : t("prop_cp0");
  }
  /** How an approval runs, this viewer's choice (pref wb.run.mode, the approval's ▾): "group",
   *  a pause before each group (where the server groups and steps), "step", one
   *  step each press, or "run", all at once. Not chosen: by group while learning mode is on, else
   *  all at once; a mode the server cannot run: all at once. */
  const MODES = ["group", "step", "run"];
  const MODE_WORD = { group: "run_by_group", step: "btn_approve_step", run: "btn_approve" };
  const MODE_ICON = { group: "step", step: "chevron-right", run: "play" };
  const MODE_TIP = { group: "tip_mode_group", step: "tip_mode_step", run: "tip_mode_run" };
  const modeOk = (m) => m !== "group" || feature("groups");
  const modeOf = () => {
    const m = prefGet("wb.run.mode");
    return MODES.includes(m) && modeOk(m) ? m : learning() && modeOk("group") ? "group" : "run";
  };
  /** The approval's tooltip in a mode: what pressing it does (n: the steps that will run). */
  function modeTip(tab, mode, n) {
    if (mode === "step") return t("tip_step_prop");
    if (mode === "run") return t("tip_approve", n);
    const gs = groupsOf(isObj(tab.check) ? tab.check : null);
    return gs ? t("tip_approve_group", gs.length) : t("tip_mode_group");
  }
  /** What can be done now, the likeliest next first: {shown, over, wait} -- at most three
   *  shown, the rest behind ⋯ (over, "sep" between kinds), none of them dropped; null while it
   *  runs (stepped through: the run bar's Run next step and Continue). Awaiting review: Approve
   *  and run (the primary button while open), Step through, Send back…; Close proposal behind
   *  ⋯. After a run that changed the model: see its changes and undo them as a group (Continue
   *  first where it stopped part way; Apply my changes and run first once the user edited it since,
   *  editsOf); Restore to before the proposal, Run again, Step through
   *  and the rest behind ⋯. After one that changed nothing: Run again and Send back…. An action
   *  with `end` sits at the row's right. */
  function actList(tab, rec, p, l) {
    const st = p.status;
    if (st === "running" || approving(tab, p)) return null;
    const A = (k, label, o) => Object.assign({ p: k, label }, o);
    const rOff = !wb.connected ? t("why_off") : "";
    if (SHUT.includes(st)) {                     // withdrawn or closed: nothing to decide, it can go (to History)
      return { shown: [A("close_tab", t("prop_close_hist"), { icon: "clock", tip: t("tip_prop_close_hist"), end: true })], over: [] };
    }
    if (l.sent && Date.now() - l.sent < SENT_MS && st !== "rejected") return { wait: t("prop_rejecting"), shown: [], over: [] };
    const pend = rec.pending && rec.pending.kind !== "stop";
    const why = pend ? { long: t("st_sending") } : blocker(tab, rec) || approveWhy(tab, rec);
    const n = activeCount(rec, tab), again = ENDED.includes(st), cp = `\n${cpEstimate(tab)}`;
    // stopped part way: continue from the step it stopped at (the steps applied are not run
    // again), the first button; Run again and Step through then start over from step 1
    const res = resumeOf(tab, rec, p), all = res ? `\n${t("tip_rerun_all")}` : cp;
    const resume = res && A("resume", t("btn_resume_prop", res.n), { cls: "primary", icon: MODE_ICON[res.mode], off: !!why,
      tip: why ? why.long : res.mode === "step" ? t("tip_resume_prop_step", res.n) : res.mode === "group" ? t("tip_resume_prop_group", res.n)
        : t("tip_resume_prop", res.n, res.last) });
    const approve = A("approve", t(again ? "btn_rerun_prop" : "btn_approve"), { cls: st === "open" ? "primary" : "", icon: again ? "refresh" : "play",
      off: !!why, tip: why ? why.long : (again ? t("tip_rerun_prop", n) : t("tip_approve", n)) + all });
    const step = A("step", t("btn_step_prop"), { icon: "chevron-right", off: !!why, tip: why ? why.long : t("tip_step_prop") + all });
    const reject = A("reject", t(st === "rejected" ? "btn_reject_again" : "btn_reject"), { cls: "pc-rej", icon: "reply", off: !!rOff, tip: rOff || t("tip_reject") });
    const dismiss = A("dismiss", t("btn_dismiss_prop"), { cls: "pc-dis", icon: "close", off: !!rOff, tip: rOff || t("tip_dismiss_prop") });
    if (!again) {
      // awaiting review: the approval in the mode chosen (its words are the mode; ▾ picks another,
      // where the server steps), then Send back…; Close proposal behind ⋯
      const mode = modeOf();
      const go = A("approve", t(MODE_WORD[mode]), { cls: st === "open" ? "primary" : "", icon: MODE_ICON[mode],
        off: !!why, split: !!step, tip: why ? why.long : modeTip(tab, mode, n) + all });
      return { shown: [go, reject], over: [dismiss] };
    }
    // the run's changes, kept (not taken back): see them, undo them as a group, restore to before
    const r = isObj(p.run) ? p.run : {}, kept = (st === "applied" || st === "partial") && !r.undone, rcp = isObj(r.cp) ? r.cp : {};
    const group = kept && r.group && WBC.on() && A("group", t("btn_prop_group"), { cls: "flat pc-lk", tip: t("tip_prop_group") });
    const revert = kept && r.group && feature("undo") && A("revert", t("btn_prop_revert"), { icon: "undo", tip: t("tip_prop_revert") });
    const restore = kept && rcp.id && A("restore", t("btn_prop_restore"), { icon: "restore", tip: t("tip_prop_restore") });
    const pick = (shown, rest) => ({ shown: shown.filter(Boolean), over: rest.filter((x) => x && !shown.includes(x)) });
    // edited since it ran: apply just the edits (the steps that applied and are unchanged are not run again)
    const edits = !res && editsOf(tab) && A("edits", t("btn_prop_edits"), { cls: "primary", icon: "play", off: !!why,
      tip: why ? why.long : t("tip_prop_edits") + cp });
    if (edits) return pick([edits, revert || group], [group, revert, restore, "sep", approve, step, "sep", reject, dismiss]);
    if (group || revert) {
      return pick(res ? [resume, revert || group] : [group, revert], [group, revert, restore, "sep", approve, step, "sep", reject, dismiss]);
    }
    return pick(res ? [resume, approve] : [approve, Object.assign(reject, { end: true })], [restore, "sep", approve, step, "sep", reject, dismiss]);
  }
  /** The decision's row: the shown actions (a: actList's; the rest: ⋯ in the head). */
  function actHtml(a) {
    if (!a) return "";
    if (a.wait) return `<span class="pc-wait">${esc(a.wait)}</span>`;
    let h = "", grown = false;
    a.shown.forEach((d) => {
      if (d.end && !grown) { h += `<span class="grow"></span>`; grown = true; }
      // (split: one control, the action and its ▾ -- how it runs)
      h += d.split ? `<span class="pc-mode split">${btn(d.p, d.label, d)}<button class="${d.cls || ""} pc-mm" data-p="mode" aria-haspopup="menu"${d.off ? " disabled" : ""}`
        + ` title="${esc(t("tip_prop_mode"))}" aria-label="${esc(t("tip_prop_mode"))}">${icon("chevron-down")}</button></span>` : btn(d.p, d.label, d);
    });
    return h;
  }
  /** ⋯ in the head, beside fold and ×, where actions are not shown (a: actList's); else nothing. */
  const ovHtml = (a) => (a && !a.wait && a.over.some((d) => d !== "sep")
    ? `<button class="pc-ov flat icon" data-p="acts" aria-haspopup="menu" title="${esc(t("tip_more"))}" aria-label="${esc(t("tip_more"))}">${icon("more")}</button>` : "");
  /** ⋯'s menu: the actions not shown, by kind (the run's result, running it, the decision). */
  function actMenu(pane, anchor, ev) {
    const tab = tabOf(pane.tabId), p = propOf(tab), rec = tab && wb.recs.get(tab.id);
    if (!p || !rec) return;
    toggleMenu(anchor, () => {
      const a = actList(tab, rec, p, loc(tab.id)), items = [];
      ((a && a.over) || []).forEach((d) => {
        if (d === "sep") { if (items.length && !items[items.length - 1].sep) items.push({ sep: true }); return; }
        items.push({ label: d.label, icon: d.icon, disabled: !!d.off, tip: d.tip, run: () => doAct(pane, d.p, anchor.isConnected ? anchor : pane.q('.prop-card [data-p="acts"]') || anchor) });
      });
      while (items.length && items[items.length - 1].sep) items.pop();
      return items;
    }, ev);
  }
  /** The list's head: "Step ── Checked 14:02 · 1 warning" (what a check cannot see: its tooltip), or
   *  checking now, or not checked yet. */
  function listHead(tab, rec, p, chk) {
    const run = tab.run || {}, checking = run.status === "running" && run.dry_run;
    let words, cls = "", button = "", tip = "";
    if (checking) { words = t("prop_checking"); cls = "busy"; }
    else if (chk && chkPast(tab, p, chk)) words = "";   // (a run since: the check is history)
    else if (chk) {
      const e = Number(chk.errors) || 0, w = Number(chk.warns) || 0;
      const parts = [e ? tn("prop_chk_err", e) : "", w ? tn("prop_chk_warn", w) : ""].filter(Boolean);
      words = t("prop_chk", when(chk.t), parts.length ? parts.join(t("ps_and")) : t("prop_chk_ok"));
      cls = e ? "err" : w ? "warn" : "ok";
      tip = t("prop_limit");
    } else {
      words = t(p.status === "draft" ? "prop_chk_draft" : "prop_chk_none");
      const why = rec.pending ? { long: t("st_sending") } : blocker(tab, rec);
      if (p.status !== "draft") button = btn("check", t("check_prog"), { cls: "pc-cb", icon: "check", off: !!why, tip: why ? why.long : t("tip_check") });
    }
    // (checked, with nothing to say: no line. A check shows only while it runs, where there is
    // none yet, or where it found something; an old one says so in a line of its own, staleOf)
    if (cls === "ok" || (!words && !button)) return "";
    return `<div class="pc-lh">`
      + (words ? `<span class="pc-chk ${cls}"${tip ? ` title="${esc(tip)}"` : ""}>${esc(words)}</span>` : "") + `${button}</div>`;
  }
  /** The check older than the blocks (an edit since, one waiting to go out) or than the model. */
  function staleOf(tab, rec, p, chk) {
    if (!chk || ENDED.includes(p.status) || p.status === "running") return false;
    if (chk.rev !== tab.program_rev || rec.timer) return true;
    const j = sessOf(tab).journal;
    return isObj(j) && num(j.last_input_t) && num(chk.input_t) && j.last_input_t > chk.input_t + 1e-3;
  }
  /** While it runs: the row it runs now or is paused before (k, its index; paused), the rows
   *  before it done. Null at any other time. */
  function marksOf(tab, rows) {
    const run = tab.run || {};
    if (run.status !== "running" || run.dry_run) return null;
    const pa = isObj(run.paused) ? run.paused : null, at = pa ? pa.at : run.step;
    const k = at ? rows.findIndex((r) => r.id === at) : -1;
    return k < 0 ? null : { k, at, paused: !!pa };
  }
  /** The rows' lines (only: the indices of those to draw, in order; all of them without). */
  function rowsHtml(rows, x, only) {
    const ed = x.edited, mk = x.marks;
    return (only || rows.map((r, i) => i)).map((i) => {
      const row = rows[i];
      const st = x.idx.get(row.id), o = x.offs[i], off = o.own || o.inh;
      const probs = off || x.past ? [] : (Array.isArray(row.problems) ? row.problems : []).filter(isObj);
      const lvl = probs.some((q) => q.level === "error") ? " err" : probs.some((q) => q.level === "warn") ? " warn" : "";
      const tag = !ed ? "" : ed.added.includes(row.id) ? "prop_mine_added" : off ? ""   // (off: its own words say so)
        : ed.changed.includes(row.id) ? "prop_mine_changed" : "";
      const ran = x.ran.has(String(row.id)) && !mk;
      const tip = ran ? t(off ? "tip_prop_ran_off" : "tip_prop_ran_on") : off ? t(o.inh ? "tip_prop_inh" : "tip_prop_off") : t("tip_prop_on");
      const mark = !mk || off ? "" : i < mk.k ? "done" : i === mk.k ? "now" : "";
      const mtip = mark === "done" ? t("prop_row_done") : mark === "now" ? t(mk.paused ? "prop_row_next" : "prop_st_running") : "";
      const box = mark
        ? `<span class="pr-on pr-mk" title="${esc(mtip)}" role="img" aria-label="${esc(mtip)}">${icon(mark === "done" ? "check" : mk.paused ? "step" : "play")}</span>`
        : `<label class="pr-on" title="${esc(tip)}"><input type="checkbox" data-p="off"${off ? "" : " checked"}`
          + `${o.inh || !o.live || !x.editable ? " disabled" : ""} aria-label="${esc(tip)}"></label>`;
      const words = whatHtml(row, st, x, off);
      const main = o.live ? `<button class="pr-t" data-p="go" title="${esc(t("tip_prop_row"))}">${words}</button>` : `<span class="pr-t">${words}</span>`;
      const why = st && st.why && !off ? `<div class="pr-why" title="${esc(st.why)}">${esc(t("reason", cut(st.why, 140)))}</div>` : "";
      const ask = x.ask && o.live && !off ? `<button class="pr-ask flat icon" data-p="ask" title="${esc(t("prop_ask_step"))}">${icon("sparkle")}</button>` : "";
      return `<li class="pr${off ? " off" : ""}${lvl}${mark ? ` ${mark}` : ""}" data-id="${esc(row.id || "")}" style="--d:${Math.min(Number(row.depth) || 0, 6)}">`
        + `${box}<span class="pr-n">${row.n ?? ""}</span><div class="pr-m">${main}`
        + (ran ? ` <span class="pr-tag pr-ran" title="${esc(t(off ? "tip_prop_ran_off" : "tip_prop_ran_on"))}">${esc(t("prop_ran"))}</span>`
          : off ? ` <small class="pr-q pr-offw">${esc(t("prop_off"))}</small>` : "")
        + (tag ? ` <span class="pr-tag">${esc(t(tag))}</span>` : "")
        + probs.map((q) => probHtml(q, x.session)).join("") + why + `</div>${ask}</li>`;
    }).join("");
  }
  function listHtml(tab, rec, p, got, x) {
    const { rows, more, chk } = got, stale = staleOf(tab, rec, p, chk);
    let h = listHead(tab, rec, p, chk);
    if (stale) {
      const why = rec.pending ? { long: t("st_sending") } : blocker(tab, rec);
      h += `<div class="pc-stale">${icon("refresh")}<span>${esc(t("prop_stale"))}</span>`
        + btn("check", t("btn_recheck"), { off: !!why, tip: why ? why.long : t("tip_check") }) + `</div>`;
    }
    const gs = groupsOf(chk), by = gs ? byGroup(rows, gs, x) : null;
    h += by ? groupsHtml(tab, rows, by, x, stale) : `<ol class="pc-rows${stale ? " stale" : ""}">${rowsHtml(rows, x)}</ol>`;
    const foot = (by ? techHtml(rows, by.tech, x) : "") + (more > 0 ? `<p>${esc(tn("prop_more", more))}</p>` : "")
      + (x.edited && x.edited.removed ? `<p>${esc(tn("prop_removed", x.edited.removed))}</p>` : "");
    return foot ? `${h}<div class="pc-foot${by ? " g" : ""}">${foot}</div>` : h;
  }

  // ------------------------------------------------------------------ by group
  /** The check's groups (the server's wb_plan.groups: the same the run pauses by), else null. */
  function groupsOf(chk) {
    const gs = isObj(chk) && feature("groups") && Array.isArray(chk.groups) ? chk.groups.filter((g) => isObj(g) && num(g.n)) : [];
    return gs.length ? gs : null;
  }
  /** A group's name: the AI's title as written (never translated), else the server's template. */
  function gTitle(g) {
    if (typeof g.title === "string" && g.title.trim()) return g.title;
    const tp = isObj(g.tpl) && typeof g.tpl.key === "string" && /^gc_auto_\w+$/.test(g.tpl.key) ? g.tpl : null;
    if (!tp || I18N.t(tp.key) === tp.key) return t("gc_auto_prep");
    // (settings of several objects: named for what they are -- units, streams, or both)
    const objs = Array.isArray(g.objs) ? g.objs.map(String) : [];
    const sb = objs.some((o) => o.startsWith("block:")), ss = objs.some((o) => o.startsWith("stream:"));
    const key = tp.key === "gc_auto_sets" && ss ? (sb ? "gc_auto_sets_m" : "gc_auto_sets_s") : tp.key;
    return t(key, ...(Array.isArray(tp.args) ? tp.args : []));
  }
  /** A row's problems as its line shows them: none for a step off, or once a run made the check history. */
  const probsOf = (row, o, x) => (o.own || o.inh || x.past ? [] : (Array.isArray(row.problems) ? row.problems : []).filter(isObj));
  /** The rows by the check's groups: {groups: [{g, heads, idx, all}], loose, tech} -- a group's
   *  heading row (heads: its problems go under the group's line), its other rows (idx, a step's
   *  nested rows with it) and every row it holds (all: the heading's and the foot's too); the rows
   *  of no group (a procedure; loose); the technical steps left to the foot (tech: top level, on,
   *  with nothing to say -- a problem in it or a run at it keeps its rows, and so does a step
   *  turned off: its tick box turns it back on). Indices into rows. */
  function byGroup(rows, gs, x) {
    const own = new Map(gs.map((g) => [g.n, { g, heads: [], idx: [], all: [] }])), loose = [], tech = [];
    const spans = [];                            // (each top-level row with the nested rows under it)
    rows.forEach((r, i) => { if (!(Number(r.depth) > 0) || !spans.length) spans.push([i]); else spans[spans.length - 1].push(i); });
    const mk = x.marks;
    spans.forEach((span) => {
      const i = span[0], r = rows[i], o = x.offs[i], box = r.g != null ? own.get(r.g) : null;
      if (box) box.all.push(...span);
      if (r.kind === "group" && box) { box.heads.push(i); return; }
      if (r.tech && !o.own && !o.inh && !span.some((k) => probsOf(rows[k], x.offs[k], x).length || (mk && mk.k === k))) { tech.push(i); return; }
      (box ? box.idx : loose).push(...span);
    });
    return { groups: [...own.values()], loose, tech };
  }
  /** Each group's line -- its number (✓ once a run is past it; the run's colour while in it), its
   *  title, the why in its tooltip, ⌄ to show its steps -- and its steps when shown; then the
   *  rows of no group. A group is shown at first when it is the only one or has a problem; while a
   *  run goes, the one it is in (each time it enters another); the viewer's ⌄ is kept per tab. */
  function groupsHtml(tab, rows, by, x, stale) {
    const l = loc(tab.id), mk = x.marks, single = by.groups.length === 1;
    let h = `<ol class="pc-groups${stale ? " stale" : ""}">`;
    by.groups.forEach(({ g, heads, idx, all }) => {
      // (the problems of its steps: the heading's own always show under its line)
      const ps = idx.flatMap((i) => probsOf(rows[i], x.offs[i], x));
      const lv = ps.some((q) => q.level === "error") ? "err" : ps.some((q) => q.level === "warn") ? "warn" : "";
      const key = String(g.key || g.n), now = !!mk && idx.includes(mk.k);
      const done = !!mk && !now && all.length > 0 && all.every((i) => i < mk.k);
      const tops = idx.filter((i) => !(Number(rows[i].depth) > 0));
      const ran = !mk && tops.length > 0 && tops.every((i) => x.ran.has(String(rows[i].id)));
      if (now && l.gnow !== key) { l.gnow = key; delete l.gopen[key]; }   // (the run entered it: shown again)
      const open = idx.length > 0 && (key in l.gopen ? !!l.gopen[key] : mk ? now : single || !!lv);
      const title = gTitle(g), why = typeof g.why === "string" ? g.why.trim() : "";
      const num0 = done ? `<span class="pg-n" role="img" aria-label="${esc(t("pg_done"))}">${icon("check")}</span>` : `<span class="pg-n">${g.n}</span>`;
      // (⚠ while its steps are hidden -- shown, their own rows say it -- and before a run is past it)
      // (learning mode: the group's principle chip -- E, principle.js; a spacer in the line keeps its room)
      const prn = window.WBPN ? WBPN.chip(`pc|${tab.id}|${key}`, WBPN.of(g, all.filter((i) => !x.offs[i].own && !x.offs[i].inh).map((i) => rows[i]), tab)) : "";
      const sp = prn ? `<span class="prn-sp" aria-hidden="true">${esc(t("prn_chip"))}</span>` : "";
      const inner = `${num0}<span class="pg-t">${esc(title)}</span>${lv && !open && !done ? `<span class="pg-w">${icon("warn")}</span>` : ""}`
        + `${ran ? `<span class="pr-tag pr-ran pg-ran" title="${esc(t("tip_pg_ran"))}">${esc(t("prop_ran"))}</span>` : ""}${sp}`;
      const tip = [why, idx.length ? t(open ? "tip_pg_close" : "tip_pg_open") : ""].filter(Boolean).join("\n");
      h += `<li class="pg${lv ? ` ${lv}` : ""}${now ? " now" : ""}${done ? " done" : ""}${open ? " open" : ""}" data-g="${esc(key)}">`
        + (idx.length ? `<button class="pg-h" data-p="gfold" aria-expanded="${open}" title="${esc(tip)}">${inner}${icon(open ? "chevron-down" : "chevron-right")}</button>`
          : `<div class="pg-h"${tip ? ` title="${esc(tip)}"` : ""}>${inner}</div>`) + prn
        + heads.flatMap((i) => probsOf(rows[i], x.offs[i], x)).map((q) => probHtml(q, x.session)).join("")
        + (open ? `<ol class="pc-rows pg-rows">${rowsHtml(rows, x, idx)}</ol>` : "") + `</li>`;
    });
    h += `</ol>`;
    return by.loose.length ? `${h}<ol class="pc-rows${stale ? " stale" : ""}">${rowsHtml(rows, x, by.loose)}</ol>` : h;
  }
  const PLAIN = document.createElement("div");
  const plain = (html) => { PLAIN.innerHTML = html; return PLAIN.textContent.replace(/\s+/g, " ").trim(); };
  const TECH_TIP = 24;                         // (the foot's tooltip: at most this many steps, then a count)
  /** The foot's "2 more steps: read, calculate" (gc_tech): the technical steps the groups leave out, by kind; each in its tooltip. */
  function techHtml(rows, tech, x) {
    if (!tech.length) return "";
    const word = (k) => { const w = I18N.t(`stp_${k}`) !== `stp_${k}` ? t(`stp_${k}`) : t("stp_other"); return I18N.lang === "zh" ? w : w.toLowerCase(); };
    const kinds = [...new Set(tech.map((i) => rows[i].kind))].map(word);
    const lines = tech.slice(0, TECH_TIP).map((i) => plain(whatHtml(rows[i], x.idx.get(rows[i].id), x)));
    if (tech.length > TECH_TIP) lines.push(tn("prop_more", tech.length - TECH_TIP));
    const tip = lines.join("\n");
    return `<p class="pc-tech" title="${esc(tip)}">${esc(tn("gc_tech", tech.length, kinds.join(t("ps_and"))))}</p>`;
  }
  /** The list's overflow: its foot fades where more rows lie below, and a chip counts them
   *  ("5 more steps"; a press scrolls the first of them in under the list's head). */
  function hiddenRows(list) {                        // (a row whose first line the list's foot cuts counts)
    const edge = list.getBoundingClientRect().bottom - 20;
    return [...list.querySelectorAll(".pc-rows > .pr")].filter((li) => li.getBoundingClientRect().top > edge);
  }
  /** By group: the group lines below the view ("3 more groups"), where there are; else the steps. */
  function hiddenLines(list) {
    const edge = list.getBoundingClientRect().bottom - 20;
    const gs = [...list.querySelectorAll(".pc-groups > .pg")].filter((li) => li.getBoundingClientRect().top > edge);
    return gs.length ? { els: gs, key: "prop_rest_g" } : { els: hiddenRows(list), key: "prop_rest" };
  }
  function renderMore(card) {
    const list = card.querySelector(".pc-list"), chip = card.querySelector(".pc-more");
    if (!list || !chip) return;
    const shown = !card.classList.contains("fold") && !card.classList.contains("hidden") && list.clientHeight > 0;
    let hid = shown ? hiddenLines(list) : { els: [], key: "prop_rest" }, n = hid.els.length;
    if (n && chip.classList.contains("hidden")) { chip.classList.remove("hidden"); hid = hiddenLines(list); n = hid.els.length || 1; }   // (its line takes the list's room)
    list.classList.toggle("fb", n > 0);
    chip.classList.toggle("hidden", !n);
    if (!n) return;
    const words = tn(hid.key, n);
    if (chip._w !== words) { chip._w = words; chip.querySelector(".bt").textContent = words; }
  }
  function moreDown(card) {
    const list = card.querySelector(".pc-list"), first = list && hiddenLines(list).els[0];
    if (!first) return;
    const head = list.querySelector(".pc-lh"), top = first.getBoundingClientRect().top - list.getBoundingClientRect().top + list.scrollTop;
    list.scrollTo({ top: Math.max(0, top - (head ? head.offsetHeight : 0) - 2), behavior: "smooth" });
  }
  /** The row it runs now or is paused before, scrolled into the list's view once each time it moves. */
  function showNow(card, l, mk) {
    const at = mk ? mk.at : null;
    if (l.nowAt === at) return;
    l.nowAt = at;
    const list = card.querySelector(".pc-list"), li = at && list.querySelector(`.pr[data-id="${CSS.escape(at)}"]`);
    if (!li || !list.clientHeight) return;
    const head = list.querySelector(".pc-lh"), hh = head ? head.offsetHeight : 0, L = list.getBoundingClientRect(), r = li.getBoundingClientRect();
    if (r.top < L.top + hh) list.scrollTop -= L.top + hh + 4 - r.top;
    else if (r.bottom > L.bottom - 30) list.scrollTop += r.bottom - L.bottom + 34;   // (clear of the chip)
  }

  /** The shown tab's card: hidden on a tab that is no proposal. Drawn again only when what it
   *  shows moved (the proposal, its check, the run, the blocks' turned-off steps, the words). */
  function renderProposal(pane) {
    const card = pane && pane.q(".prop-card");
    if (!card) return;
    const tab = tabOf(pane.tabId), p = propOf(tab), rec = tab && wb.recs.get(tab.id);
    if (!p || !rec) {
      if (!card.classList.contains("hidden")) card.classList.add("hidden");
      pane.sigs.prop = null;
      insetBlocks(pane);
      return;
    }
    wire(pane, card);
    const l0 = loc(tab.id);
    if (l0.hide) {                               // × on its window: hidden until its sub-tab, pressed again, brings it back
      if (!card.classList.contains("hidden")) card.classList.add("hidden");
      pane.sigs.prop = null;
      insetBlocks(pane);
      return;
    }
    const wasHidden = card.classList.contains("hidden");
    const l = l0, got = rowsOf(tab), x = context(tab, rec, p, got.rows, got.chk), run = tab.run || {}, sess = sessOf(tab);
    if (l.sent && (p.status === "rejected" || Date.now() - l.sent >= SENT_MS)) l.sent = 0;
    const c = got.chk || {};
    const sig = JSON.stringify([I18N.lang, tab.id, p, [c.t, c.rev, c.errors, c.warns, c.est_cp_s], tab.program_rev, x.offs,
      [run.status, run.dry_run, run.approved, run.step, isObj(run.paused) ? run.paused.at : null, (run.log || []).length],
      wb.connected, !!rec.timer, rec.pending && rec.pending.kind, l.fold, l.form, !!l.sent, l.gopen, modeOf(),
      (sess.journal || {}).last_input_t, sess.model && sess.model.id, window.WBL ? WBL.ver : 0, (wb.state.catalog || {}).features,
      busy(tab), blocker(tab, rec) && blocker(tab, rec).long, WBPN.on()]);
    card.classList.remove("hidden");
    if (wasHidden) placeCard(pane, card);
    if (!changed(pane, "prop", sig)) return;
    card.classList.toggle("fold", l.fold);
    card.setAttribute("aria-label", t("prop_title"));
    const q = (s) => card.querySelector(s), sk = stOf(tab, p);
    // the version only once revised (a first one is the default), the time it was written in a tooltip:
    // the version's, else the title's
    const rev = Number(p.rev) || 1, meta = t("tip_prop_meta", when(p.t0), rev);
    const form = l.form && p.status !== "running" && !SHUT.includes(p.status);
    if (!form && l.form) l.form = false;
    const a = form ? null : actList(tab, rec, p, l);
    // the head: its title, then ⋯ ⌃ ✕ only; where it stands (the tab's pill, the decision's buttons),
    // its version and what it does in short are the title's tooltip
    const ttip = [p.title, t(`prop_st_${sk}`) + (rev > 1 ? ` · ${t("prop_meta", rev)}` : ""), sumWords(got.rows, x.offs), meta].join("\n");
    setHtml(q(".pc-head"), `${icon("sparkle")}<b class="pc-title" title="${esc(ttip)}">${esc(p.title)}</b><span class="grow"></span>` + ovHtml(a)
      + `<button class="pc-fold flat icon" data-p="fold" aria-expanded="${!l.fold}" title="${esc(t(l.fold ? "tip_prop_unfold" : "tip_prop_fold"))}">`
      + `${icon(l.fold ? "chevron-down" : "chevron-up")}</button>`
      + `<button class="pc-x flat icon" data-p="hide" title="${esc(t("tip_prop_hide"))}">${icon("close")}</button>`);
    setHtml(q(".pc-info"), infoHtml(tab, rec, p, got.rows, x, l));
    const acts = actHtml(a);
    q(".pc-act").classList.toggle("hidden", !acts);
    setHtml(q(".pc-act"), acts);
    const f = q(".pc-form"), was = !f.classList.contains("hidden") && f.dataset.tab === tab.id;
    f.dataset.tab = tab.id;                      // (one box a pane: another tab's words are that tab's)
    f.classList.toggle("hidden", !form);
    q(".pc-fl").textContent = t("reject_lead");
    const inp = q(".pc-in");
    inp.placeholder = t("reject_ph");
    inp.setAttribute("aria-label", t("reject_ph"));
    inp.disabled = !wb.connected;
    q('.pc-form [data-p="send"] .bt').textContent = t("btn_reject_send");
    q('.pc-form [data-p="cancel"] .bt').textContent = t("cancel");
    q('.pc-form [data-p="send"]').disabled = !wb.connected;
    if (form && !was) {
      inp.value = l.draft;
      if (l.focus) inp.focus({ preventScroll: true });   // (opened by its button, not by showing the tab)
    }
    l.focus = false;
    const list = q(".pc-list");
    setHtml(list, listHtml(tab, rec, p, got, x));
    // a new check (the automatic one too) shows as it comes: its rows fade in once -- by group, the
    // groups' list (every group folded and no loose rows: there are no rows on screen at all)
    const fade = got.chk && num(got.chk.t) && l.chkT !== null && l.chkT !== got.chk.t && list.querySelector(".pc-groups, .pc-rows");
    if (fade) fade.animate([{ opacity: 0.35 }, { opacity: 1 }], { duration: 260, easing: "cubic-bezier(.2, .8, .2, 1)" });
    l.chkT = got.chk && num(got.chk.t) ? got.chk.t : l.chkT === null ? 0 : l.chkT;
    showNow(card, l, x.marks);
    renderMore(card);
  }


  // ------------------------------------------------------------------ the floating window
  /** Where the window stands, kept for the next time (per window, in this browser): {v: 2, x,
   *  y} from a drag, w and h only once the user sized it (from an edge or a corner: an edge
   *  across keeps w alone). Without h it is as tall as what it
   *  holds, down to the foot of the area it floats over at most. (Before v 2 every first
   *  showing kept its size: such a record keeps its place and width, not its height.) */
  const GEO_KEY = "wb.propCard", GEO_W = 380, GEO_GAP = 8, TOP_MOST = 0.5, MIN_W = 300, MIN_H = 180;
  function geoGet() {
    let g = null;
    try { g = JSON.parse(localStorage.getItem(GEO_KEY) || "null"); } catch (e) { return null; }
    if (!isObj(g) || !num(g.x) || !num(g.y)) return null;
    return g.v === 2 ? g : { v: 2, x: g.x, y: g.y, ...(num(g.w) ? { w: g.w } : {}) };
  }
  const geoSet = (g) => { try { localStorage.setItem(GEO_KEY, JSON.stringify({ ...g, v: 2 })); } catch (e) { /* private mode: not kept */ } };
  /** Keep the window inside the page body: its head always reachable; no height given (fit): as
   *  tall as what it holds, down to the body's foot at most. */
  function clampCard(pane, card, g) {
    const box = pane.q(".pbody"), W = box.clientWidth, H = box.clientHeight;
    const y = Math.max(rowFoot(pane, g.x, g.w || GEO_W), Math.min(g.y, H - 48));
    // (at its first place, over the top of the blocks: half the area at most, so the blocks it
    // proposes keep the rest; moved by the user, down to the area's foot)
    const most = g.top ? Math.min(H - y - GEO_GAP, Math.round(H * TOP_MOST)) : H - y - GEO_GAP;
    // (its foot inside the area too: a top held under the sub-tab row takes from the height, not past the foot)
    const w = Math.max(MIN_W, Math.min(g.w || GEO_W, W - 2 * GEO_GAP)), h = Math.max(MIN_H, Math.min(g.h || most, H - 2 * GEO_GAP, H - y - GEO_GAP));
    const x = Math.max(GEO_GAP, Math.min(g.x, W - w - GEO_GAP));
    return { x, y, w, h, fit: !g.h };
  }
  /** The highest the window may stand at x (w wide): clear of the sub-tab row where it
   *  lies over the program's column, so the sub-tabs stay in reach; else GEO_GAP. */
  function rowFoot(pane, x, w) {
    const row = pane.q(".subtabs"), left = pane.q(".pleft");
    if (!row || row.classList.contains("hidden") || left.classList.contains("closed") || !row.offsetHeight) return GEO_GAP;
    const b0 = pane.q(".pbody").getBoundingClientRect(), r = row.getBoundingClientRect(), L = left.getBoundingClientRect();
    if (x > L.right - b0.left || x + w < L.left - b0.left) return GEO_GAP;
    return Math.round(r.bottom - b0.top) + GEO_GAP;
  }
  function applyGeo(card, g) {
    card.style.setProperty("--pc-x", `${g.x}px`);
    card.style.setProperty("--pc-y", `${g.y}px`);
    card.style.setProperty("--pc-w", `${g.w}px`);
    card.style.setProperty("--pc-h", `${g.h}px`);   // (fit: the most it may take)
    card.classList.toggle("fit", !!g.fit);
  }
  /** Where it stands until the user moves it: at the top of the program's canvas, under its run
   *  bar and as wide as the column (the canvas then starts under it: insetBlocks), half the
   *  area tall at most; the column folded, beside it over the flowsheet's left edge, below its
   *  toolbar. */
  function homeGeo(pane) {
    const b0 = pane.q(".pbody").getBoundingClientRect(), left = pane.q(".pleft"), blk = pane.q(".blockly");
    if (!left.classList.contains("closed") && blk.clientWidth > 300) {
      const r = blk.getBoundingClientRect();
      return { x: Math.round(r.left - b0.left) + 10, y: Math.round(r.top - b0.top) + 8, w: Math.round(Math.min(r.width - 20, 560)), top: true };
    }
    const f = (pane.q(".fs-wrap") || pane.q(".pright")).getBoundingClientRect();
    return { x: Math.round(f.left - b0.left) + 12, y: Math.round(f.top - b0.top) + 52 };
  }
  /** Shown again: where the user left it, or at its home (homeGeo); as tall as what it holds, the
   *  area below that at most (over the dock too: it moves), unless the user sized its height. */
  function placeCard(pane, card) {
    applyGeo(card, clampCard(pane, card, geoGet() || homeGeo(pane)));
    insetBlocks(pane);
  }
  /** The blocks never lie under the window (T15): where it sits over the top of the program's
   *  canvas, the canvas and its category list start under its foot (folded: under its head);
   *  hidden, moved off the canvas's top, or the column folded: no inset. The canvas is measured
   *  again when the inset moves (Blockly sizes its SVG only when told). */
  function insetBlocks(pane) {
    const card = pane.q(".prop-card"), blk = pane.q(".blockly"), rec = wb.recs.get(pane.tabId);
    let inset = 0;
    if (card && !card.classList.contains("hidden") && !pane.q(".pleft").classList.contains("closed")) {
      // (its box as laid out, not as drawn: its spring in scales it a moment, which no observer sees end)
      const p0 = pane.q(".pbody").getBoundingClientRect(), b = blk.getBoundingClientRect();
      const c = { left: p0.left + card.offsetLeft, top: p0.top + card.offsetTop };
      c.right = c.left + card.offsetWidth;
      c.bottom = c.top + card.offsetHeight;
      const over = Math.min(c.right, b.right) - Math.max(c.left, b.left);
      if (b.height > 0 && over > b.width / 2 && c.top < b.top + 48 && c.bottom > b.top) inset = Math.round(Math.min(c.bottom - b.top + 6, b.height - 120));
    }
    inset = Math.max(0, inset);
    if (pane.blkInset === inset) return;
    pane.blkInset = inset;
    blk.style.setProperty("--blk-inset", `${inset}px`);
    if (!rec) return;
    Blockly.svgResize(rec.ws);
    renderCursor(pane, "view");
    renderBlkEmpty(pane);
  }
  /** Dragged by its head (not its buttons); sized from any edge or corner (resizeCard). */
  function dragCard(pane, card) {
    card.addEventListener("pointerdown", (ev) => {
      const head = ev.target.closest(".pc-head");
      if (!head || ev.target.closest("button") || ev.button !== 0) return;
      ev.preventDefault();
      const r0 = { x: card.offsetLeft, y: card.offsetTop, w: card.offsetWidth, h: card.offsetHeight }, x0 = ev.clientX, y0 = ev.clientY;
      card.classList.add("drag");
      track(head, ev, (e) => applyGeo(card, clampCard(pane, card, { ...r0, x: r0.x + e.clientX - x0, y: r0.y + e.clientY - y0 })), () => {
        card.classList.remove("drag");
        // the place kept; a size only as the user left it (none: as tall as it needs, the foot from here at most)
        const g = { ...(geoGet() || {}), x: card.offsetLeft, y: card.offsetTop };
        delete g.top;                                // (moved: down to the area's foot at most, not half of it)
        geoSet(g);
        if (!g.h && !card.classList.contains("fold")) applyGeo(card, clampCard(pane, card, g));
        insetBlocks(pane);
      });
    });
    resizeCard(pane, card);
    // the area under it resized (the window, the program column): kept inside it, and one not
    // sized by the user still down to its foot (once a frame at most: the observer's delivery)
    const ro = new ResizeObserver(() => {
      if (card.classList.contains("hidden") || card.classList.contains("drag") || card.classList.contains("sizing")) return;
      const g = geoGet();
      applyGeo(card, clampCard(pane, card, g ? { ...g, x: card.offsetLeft, y: card.offsetTop } : homeGeo(pane)));
      insetBlocks(pane);
    });
    ro.observe(pane.q(".pbody"));
    ro.observe(pane.q(".pleft"));                // (the column folded, opened or dragged wider: its home moves)
  }
  /** Sized from its four edges and four corners: invisible strips along its rim (.pc-grip, 6 px; the
   *  corners 18 px), each with its resize pointer. The edge opposite the one dragged stays put; it
   *  keeps MIN_W x MIN_H and stays inside the area (GEO_GAP clear). What the user sized is kept
   *  when the pointer lets go: an edge across keeps the width alone (a height not sized before
   *  still fits what it holds -- at its first place, half the area at most, as before); folded
   *  to its head, only the side edges show. */
  const GRIPS = ["n", "s", "e", "w", "ne", "nw", "se", "sw"];
  function resizeCard(pane, card) {
    card.insertAdjacentHTML("beforeend", GRIPS.map((d) => `<div class="pc-grip ${d}" data-grip="${d}" aria-hidden="true"></div>`).join(""));
    card.addEventListener("pointerdown", (ev) => {
      const grip = ev.target.closest(".pc-grip");
      if (!grip || ev.button !== 0) return;
      ev.preventDefault();
      ev.stopPropagation();
      const d = grip.dataset.grip, box = pane.q(".pbody"), W = box.clientWidth, H = box.clientHeight;
      const r0 = { x: card.offsetLeft, y: card.offsetTop, w: card.offsetWidth, h: card.offsetHeight }, x0 = ev.clientX, y0 = ev.clientY;
      const right = r0.x + r0.w, foot = r0.y + r0.h, tall = /[ns]/.test(d), kept = geoGet() || { top: true };
      const lim = (v, lo, hi) => Math.max(lo, Math.min(v, hi));
      let g = null;
      card.classList.add("sizing");
      track(grip, ev, (e) => {
        const dx = e.clientX - x0, dy = e.clientY - y0;
        let { x, y, w, h } = r0;
        if (d.includes("e")) w = lim(r0.w + dx, MIN_W, W - GEO_GAP - r0.x);
        if (d.includes("w")) { x = lim(r0.x + dx, GEO_GAP, right - MIN_W); w = right - x; }
        if (d.includes("s")) h = lim(r0.h + dy, MIN_H, H - GEO_GAP - r0.y);
        if (d.includes("n")) { y = lim(r0.y + dy, rowFoot(pane, x, w), foot - MIN_H); h = foot - y; }
        // (sized across only: a height the user never set still fits what it holds)
        g = tall || num(kept.h) ? { x, y, w, h: tall ? h : kept.h } : { x, y, w, ...(kept.top ? { top: true } : {}) };
        applyGeo(card, clampCard(pane, card, g));
      }, () => {
        card.classList.remove("sizing");
        if (g) geoSet({ ...kept, ...g, x: card.offsetLeft, y: card.offsetTop });   // (a press without a move keeps nothing)
        insetBlocks(pane);
      });
    });
  }
  /** The proposal's sub-tab pressed while it is shown (app-subtabs.js): shows the window again
   *  (hidden by its ×), or brings it to the front. */
  function showCard(pane) {
    const tab = tabOf(pane.tabId);
    if (!propOf(tab)) return;
    const l = loc(tab.id);
    l.hide = false;
    l.fold = false;
    renderProposal(pane);
    const card = pane.q(".prop-card");
    card.animate([{ transform: "scale(.98)", opacity: 0.6 }, { transform: "none", opacity: 1 }], { duration: 160, easing: "ease-out" });
  }
  /** The proposal's window hidden by its × (its sub-tab, pressed again, shows it). */
  const propHidden = (id) => loc(id).hide;

  // ------------------------------------------------------------------ what the card does
  /** The card's listeners, once a pane; its parts made once (the send-back box keeps its words
   *  and caret while the rest is drawn anew). The block canvas under it is measured again when
   *  the card's height moves (Blockly sizes its SVG only when told). */
  function wire(pane, card) {
    if (card.dataset.wired) return;
    card.dataset.wired = "1";
    card.innerHTML = `<div class="pc-top"><div class="pc-head"></div><div class="pc-info"></div><div class="pc-act"></div>`
      + `<div class="pc-form hidden" role="group"><label class="pc-fl"></label><div class="pc-fr">`
      + `<input class="pc-in" type="text" maxlength="1000" spellcheck="false">`
      + `<button class="primary" data-p="send">${icon("reply")}<span class="bt"></span></button>`
      + `<button data-p="cancel"><span class="bt"></span></button></div></div></div><div class="pc-list"></div>`
      + `<button class="pc-more hidden" data-p="more">${icon("chevron-down")}<span class="bt"></span></button>`;
    card.addEventListener("click", (ev) => act(pane, ev));
    dragCard(pane, card);
    let fresh = false;                                  // (the chip counts again as the list scrolls: once a frame)
    card.querySelector(".pc-list").addEventListener("scroll", () => {
      if (fresh) return;
      fresh = true;
      requestAnimationFrame(() => { fresh = false; renderMore(card); });
    }, { passive: true });
    card.addEventListener("change", (ev) => {
      const cb = ev.target.closest('input[data-p="off"]'), li = cb && cb.closest(".pr");
      if (li) setOff(pane, li.dataset.id, !cb.checked);
    });
    card.addEventListener("input", (ev) => { if (ev.target.classList.contains("pc-in") && pane.tabId) loc(pane.tabId).draft = ev.target.value; });
    card.addEventListener("keydown", (ev) => {
      if (!ev.target.classList.contains("pc-in") || ev.isComposing) return;
      if (ev.key === "Enter") { ev.preventDefault(); sendBack(pane); }
      else if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); closeForm(pane, true); }
    });
    let h = -1;
    const ro = new ResizeObserver(() => requestAnimationFrame(() => {
      renderMore(card);                          // (the list's room moved: what lies below it counted again)
      insetBlocks(pane);                         // (folded, unfolded, grown: the canvas starts under it)
      const rec = wb.recs.get(pane.tabId), now = pane.q(".blockly").clientHeight;
      if (!rec || now === h) return;
      h = now;
      Blockly.svgResize(rec.ws);                 // (outside the observer's delivery: nothing it observes moves)
      renderCursor(pane, "view");
      renderBlkEmpty(pane);
      if (!pane.q(".blk-held").classList.contains("hidden")) fitHeld(pane);
    }));
    ro.observe(card);
    ro.observe(card.querySelector(".pc-list"));  // (its own room moved inside a card of a kept size: counted again)
    // (what it holds rises in a moment, which no observer sees end: what lies below is counted again after it)
    card.addEventListener("animationend", (ev) => { if (ev.target.parentNode === card) { renderMore(card); insetBlocks(pane); } });
  }
  function act(pane, ev) {
    const b = ev.target.closest("[data-p]");
    if (!b || b.disabled || b.tagName === "INPUT") return;
    if (b.dataset.p === "acts") { actMenu(pane, b, ev); return; }
    doAct(pane, b.dataset.p, b);
  }
  /** One action, by its key: from its button, or from ⋯'s menu (b: then ⋯, where a preview opens). */
  function doAct(pane, k, b) {
    const tab = tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id), p = propOf(tab);
    if (!p || !rec) return;
    const l = loc(tab.id), li = b.closest(".pr"), id = li && li.dataset.id;
    if (k === "fold") { l.fold = !l.fold; renderProposal(pane); return; }
    if (k === "hide") { l.hide = true; renderProposal(pane); return; }
    if (k === "more") { moreDown(pane.q(".prop-card")); return; }
    if (k === "gfold") {                         // a group's steps shown or hidden (kept for this tab)
      const g = b.closest(".pg");
      if (g) { l.gopen[g.dataset.g] = !g.classList.contains("open"); renderProposal(pane); }
      return;
    }
    if (k === "approve") {                       // (awaiting review: in the mode chosen; after a run, Run again: all at once)
      l.noCp = false;
      startRun(false, false, { approve: true, mode: ENDED.includes(p.status) ? "run" : modeOf() });
      return;
    }
    if (k === "mode") { modeMenu(pane, b); return; }
    if (k === "step") { l.noCp = false; startRun(false, false, { approve: true, mode: "step" }); return; }
    if (k === "edits") { l.noCp = false; startRun(false, false, { approve: "edits", mode: "run" }); return; }
    if (k === "resume") {                        // continue a stopped approval where it stopped
      const res = resumeOf(tab, rec, p);
      if (res) { l.noCp = false; startRun(false, false, { approve: true, mode: res.mode, resume: res.at }); }
      return;
    }
    if (k === "dismiss") { if (wb.connected) wb.post({ type: "proposal_reply", tab: tab.id, action: "dismiss" }); return; }
    if (k === "close_tab") { closeTab(tab.id); return; }
    if (k === "no_cp") { l.noCp = true; startRun(false, true, { approve: "no_cp", mode: "run" }); return; }
    if (k === "check") { startRun(true); return; }
    if (k === "reject") { l.form = l.focus = true; renderProposal(pane); return; }
    if (k === "send") { sendBack(pane); return; }
    if (k === "cancel") { closeForm(pane, true); return; }
    if (k === "log") { if (prefs().dockMode === "min") setDock(pane, "split"); showPanel(pane, "log"); return; }
    if (k === "group") { seeGroup(pane, tab, (p.run || {}).group); return; }
    if (k === "revert") { undoOpen(tab, { group: p.run.group, anchor: b, label: p.title }); return; }
    if (k === "restore") { const cp = p.run.cp || {}; restoreOpen(tab, { checkpoint: cp.id, anchor: b, t: cp.t }); return; }
    if (k === "go" && id) { goStep(pane, tab, rec, id); return; }
    if (k === "ask" && id) { const blk = rec.ws.getBlockById(id); if (blk && typeof WB.onAsk === "function") WB.onAsk(blk); }
  }
  /** The approval's ▾: how it runs -- all at once, or one step each press -- this viewer's
   *  choice, kept; the button's words follow (nothing runs until it is pressed). */
  function modeMenu(pane, b) {
    // (the choice kept as made: learning mode's default is by group, so all at once is a choice too)
    toggleMenu(b.closest(".pc-mode") || b, () => MODES.filter(modeOk).map((m) => ({
      label: t(MODE_WORD[m]), icon: MODE_ICON[m], check: modeOf() === m, tip: t(MODE_TIP[m]),
      run: () => { prefSet("wb.run.mode", m); pane.sigs.prop = null; renderProposal(pane); } })));
  }
  /** A step turned off or on from its tick box: its block's own reason, as its menu sets it; the
   *  edit goes out as any other (the check is then older than the blocks, and says so). */
  function setOff(pane, id, off) {
    const rec = wb.recs.get(pane.tabId), blk = rec && rec.ws.getBlockById(id);
    if (!blk || blk.getInheritedDisabled()) { renderProposal(pane); return; }
    Blockly.Events.setGroup(true);
    try { blk.setDisabledReason(off, OFF); } finally { Blockly.Events.setGroup(false); }
    pane.sigs.prop = null;
    renderProposal(pane);
  }
  /** What a row names on the flowsheet, where it is drawn: {target, path} (a field's object and
   *  the field; a flowsheet step's stream, else its block), or null. */
  function rowTarget(tab, row) {
    const fs = sessOf(tab).flowsheet || {}, has = (kind, name) => !!name && ((kind === "stream" ? fs.streams : fs.blocks) || [])
      .some((x) => x && String(x.name).toUpperCase() === String(name).toUpperCase());
    const m = row && typeof row.path === "string" ? /^\\Data\\(Streams|Blocks)\\([^\\]+)/i.exec(row.path) : null;
    if (m) { const kind = m[1].toLowerCase() === "streams" ? "stream" : "block"; return has(kind, m[2]) ? { target: { kind, name: m[2] }, path: row.path } : null; }
    const w = row && isObj(row.what) ? row.what : null;
    if (!w || !STRUCT.includes(row.kind)) return null;
    if (has("stream", w.stream)) return { target: { kind: "stream", name: w.stream }, path: null };
    return has("block", w.block) ? { target: { kind: "block", name: w.block }, path: null } : null;
  }
  /** A row's words clicked: its block selected and centred, and what it names picked on the
   *  flowsheet (the inspector at its field, a ring where it is), where it is drawn. */
  function goStep(pane, tab, rec, id) {
    const blk = rec.ws.getBlockById(id);
    if (blk) {
      Blockly.common.setSelected(blk);
      showStep(rec, id);
    }
    const hit = rowTarget(tab, rowsOf(tab).rows.find((r) => r.id === id));
    if (hit) gotoChange(pane, hit.target, hit.path);
  }
  /** The run's change group in the Changes tab: its card opened and flashed. */
  function seeGroup(pane, tab, gid) {
    if (!gid || !window.WBC || !WBC.on()) return;
    if (prefs().dockMode === "min") setDock(pane, "split");
    showPanel(pane, "changes");
    WBC.showGroup(pane.q(".tab-changes"), changesCtx(pane, tab), gid);
  }
  /** Send the proposal back with the comment (it may be empty): the AI gets it as written. */
  function sendBack(pane) {
    const tab = tabOf(pane.tabId), p = propOf(tab);
    if (!p || !wb.connected) return;
    const l = loc(tab.id), inp = pane.q(".prop-card .pc-in"), text = String((inp && inp.value) || "").trim();
    wb.post({ type: "proposal_reply", tab: tab.id, action: "reject", text });
    l.sent = Date.now();
    l.form = false;
    l.draft = "";
    if (inp) inp.value = "";
    setTimeout(() => { if (wb.pane === pane) { pane.sigs.prop = null; renderProposal(pane); } }, SENT_MS + 50);
    toast(t("toast_rejected"), 4000);
    renderProposal(pane);
  }
  function closeForm(pane, back) {
    const tab = tabOf(pane.tabId);
    if (!tab) return;
    loc(tab.id).form = false;
    renderProposal(pane);
    const b = back && (pane.q('.prop-card [data-p="reject"]') || pane.q('.prop-card [data-p="acts"]'));   // (Send back… in ⋯: ⋯)
    if (b) b.focus({ preventScroll: true });
  }

  /** A group's steps shown in the card (a preview's tag clicked): the card shown
   *  and unfolded, the group's line opened (kept for this tab as ⌄ keeps it) and scrolled into
   *  the list's view. key: the group's key (its line's data-g). */
  function openGroup(pane, key) {
    const tab = tabOf(pane.tabId), card = pane.q(".prop-card");
    if (!propOf(tab) || !card) return;
    const l = loc(tab.id);
    l.gopen[String(key)] = true;
    if (l.fold) l.fold = false;
    if (l.hide) l.hide = false;
    pane.sigs.prop = null;
    renderProposal(pane);
    const li = card.querySelector(`.pg[data-g="${CSS.escape(String(key))}"]`), list = card.querySelector(".pc-list");
    if (li && list && list.clientHeight) {
      const L = list.getBoundingClientRect(), r = li.getBoundingClientRect();
      if (r.top < L.top || r.top > L.bottom - 40) list.scrollTop += r.top - L.top - 4;
    }
  }

  /** A step's words for the card beside a paused step (app-step.js): what it does and its
   *  current → new value, as a row here says them (the values always: the server read them). */
  function stepWords(tab, row) {
    const x = context(tab, null, {}, [row], null);
    x.values = true;
    return whatHtml(row, x.idx.get(row.id), x);
  }

  Object.assign(WBA, { approveWhy, editsOf, gTitle, openGroup, probHtml, propHidden, propOf, propPill, propWord, renderProposal, resumeOf, rowTarget, seeGroup, showCard,
    stepWords, typeWords });
})();
