/* The header's model group: the model the shown tab works on and what Aspen last said of it
 * (#modelstat, modelStatus), Save model and Run simulation (runSim, saveModel), the model panel that
 * #modelstat opens (modelPanel; its restore points: app-undo.js cpItems). While Aspen calculates
 * on the model (the heartbeat: aspenBusy, app-conn.js) the capsule counts its seconds, and says
 * so while it saves a restore point or restores one (busyWords). #ai-bar, what the AI is doing, is app-conn.js;
 * the block program's own run bar is app-status.js (renderProgBar).
 *
 * Each Run simulation and Save model also leaves a line in the run log of the tabs on its model
 * (modelLogOf; app-run.js draws them among the program's lines).
 *
 * Where the server's change journal measures the model's state (modelSum:
 * sessions[s].journal's stale, unsaved, run, save, backup, ext) the capsule's "Input changed"
 * is the journal's net count (an input set back does not count), a chip "Unsaved · 7" after the file's
 * name says it changed since the last save (the numbers in its tooltip), the last run is the
 * journal's whoever ran it, and the panel says how the model stands against its file (only when
 * it differs), which inputs changed since the last run, the last run, and recent edits found made
 * in Aspen's own window (a toast when one is found: watchExt).
 * The panel holds state and actions only: what explains a line is its
 * tooltip; a default state (nothing unsaved, no restore points) is not drawn. The AI's review
 * is the header's (app-brake.js), not the panel's.
 *
 * Shared state it keeps on wb: simWait and saveWait, a Run simulation or Save model sent
 * from here and not yet answered ({session, at: the sim's or saved's stamp when sent, until});
 * runSeen, per session the last run with a known outcome and Aspen's block marks when it was
 * first seen ({key, sig}: lastRun); modelLog, per session the run log's model lines
 * ({key, kind, t, o: the sim or saved it was made of}: noteModelLog); extSeen, per model the
 * latest edit in Aspen's window already told of (watchExt).
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { $, busy, canon, dialog, duration, esc, ghost, hhmm, icon, isOpen, prefs, sessOf, setDock,
    showPanel, shownTab, soon, t, tn, toast, wb, when, who } = WBA;
  const { aspenBusy, busyWords, callWords, cpItems, editsOf, gotoChange, holderOf, pick, revealTab, since, staleAt, whoWord } = WBA.later;

  /** The model's file: its name (the session's, where this server gives no file) and its path. */
  function modelFile(tab) {
    const m = sessOf(tab).model, f = m && m.file ? String(m.file) : "";
    return { name: f ? f.split(/[\\/]/).pop() : String(tab.session), path: f };
  }
  /** A long name keeps its end whole (" Oil - 1.bkp": about its last eight letters, from a
   *  word's start where one is near, and the extension); its head gives way to an ellipsis. */
  function nameParts(name) {
    const m = /^(.*?)(\.[A-Za-z0-9]{1,5})?$/.exec(name), stem = m[1], ext = m[2] || "";
    if (name.length <= 16 || stem.length <= 8) return [name, ""];
    let at = stem.length - 8;
    const sp = stem.indexOf(" ", at);
    if (sp >= 0 && sp < stem.length - 2) at = sp;
    return [stem.slice(0, at), stem.slice(at) + ext];
  }

  // ------------------------------------------------------------------ the model's state, from the change journal
  /** The session's journal summary (stale, unsaved, run, save, backup, ext) where
   *  the journal records (journal_on); else null, and the page says what it said before (staleAt
   *  from the times, the last run from the window's own). */
  function modelSum(sess) {
    const j = sess && sess.journal;
    if (!j || typeof j !== "object") return null;
    return ((wb.state && wb.state.catalog) || {}).journal_on === false ? null : j;
  }
  /** A count, "2000+" where the journal stopped counting. */
  const cnt = (o) => `${Number(o && o.n) || 0}${o && o.more ? "+" : ""}`;
  const ACTORS = ["ai", "user", "program", "optimizer", "external"];
  /** A run's outcome in words: converged, converged with 2 warnings, errors; a run status that
   *  could not be read is said so, never "converged". */
  function runHow(r) {
    const w = Number(r.warnings) || 0;
    return r.status === "ok" ? t("ch_o_ok") : r.status === "warn" ? (w ? tn("ch_o_warn", w) : t("ch_o_warn_n"))
      : r.status === "error" ? t("ch_o_error") : r.status === "unknown" ? t("rw_unknown") : t("ch_o_unknown");
  }
  /** The last run the journal recorded, in one line: "Run #7 · 14:05 · converged with 2
   *  warnings · AI · 3.2 s" (who ran it only when it was not the user). */
  function runLine(r) {
    const by = ACTORS.includes(r.actor) && r.actor !== "user" ? t(`mp_run_by_${r.actor}`) : "";
    return [typeof r.seq === "number" ? t("mp_run_n", r.seq) : "", when(r.t), runHow(r), by,
      typeof r.secs === "number" ? `${r.secs < 10 ? r.secs.toFixed(1) : Math.round(r.secs)} s` : ""].filter(Boolean).join(" · ");
  }
  /** What the journal says of the model against its file, in words: changes since the last
   *  sync point (a save; none yet: since it was opened) and runs since. {n, more, runs, line,
   *  tip: the capsule's line} or null. */
  function unsavedOf(js) {
    const u = js && js.unsaved;
    if (!u || typeof u !== "object") return null;
    const n = Number(u.n) || 0, runs = Number(u.runs) || 0, sv = js.save || null, open = !sv || sv.how === "open";
    const line = n ? (u.more ? t(open ? "ms_uns_open" : "ms_uns", cnt(u)) : tn(open ? "ms_uns_open" : "ms_uns", n))
      : t(open ? "ms_uns_none_open" : "ms_uns_none");
    const rl = runs ? tn("ms_uns_runs", runs) : "";
    return { n, more: !!u.more, runs, line, rl, tip: n ? [line, rl].filter(Boolean).join(" · ") : "" };
  }
  /** Who made a save, in words, when it was not the user: "AI", "Program". */
  const saveWho = (sv) => (ACTORS.includes(sv.actor) && sv.actor !== "external" && sv.actor !== "user" ? t(`mp_sv_${sv.actor}`) : "");
  /** The last sync point in words: "Last saved 13:40", "Last saved 13:40 (AI)" (an empty
   *  actor's brackets dropped). */
  function saveLine(sv) {
    const how = ["save", "saveas", "patch", "open", "external", "restore"].includes(sv.how) ? sv.how : "save";
    return t(`mp_save_${how}`, typeof sv.t === "number" ? when(sv.t) : "", saveWho(sv), sv.file || "")
      .replace(/\s*(?:（\s*）|\(\s*\))/g, "").trim();
  }
  /** Edits found made in Aspen's own window: {t, n, recent: within EXT_RECENT} or null. */
  const EXT_RECENT = 600;
  function extOf(js) {
    const x = js && js.ext;
    if (!x || typeof x.t !== "number") return null;
    return { t: x.t, n: Number((js.by || {}).external) || 0, recent: Date.now() / 1000 - x.t < EXT_RECENT };
  }
  /** An input changed since the last run, in words (WBL's short label; an object added or
   *  removed, a port's connections) and where it is on the flowsheet ({kind, name}, or null). */
  function inputOf(it, session) {
    const p = String(it.path || ""), m = /^\\Data\\(Blocks|Streams)\\([^\\]+)(?:\\(.*))?$/i.exec(p);
    const tg = m ? { kind: /^b/i.test(m[1]) ? "block" : "stream", name: m[2] } : null;
    const port = m && /^Ports\\(.+)$/i.exec(m[3] || "");
    let word;
    if (it.op === "add" || it.op === "remove") word = t(`mp_st_${it.op}`, m ? m[2] : p.split("\\").pop());
    else if (it.op === "connect" || port) word = t("mp_st_connect", m ? m[2] : p.split("\\").pop());
    else word = WBL.say(p, session);
    const field = !!(m && m[3] && !port);
    return { word, tg, path: field ? p : null, full: field ? WBL.full(p, session) : word };
  }
  /** The Changes tab, shown (the dock opened where it is folded). */
  function openChanges(pane) {
    if (!pane || !WBC.on()) return;
    if (prefs().dockMode === "min") setDock(pane, "split");
    showPanel(pane, "changes");
  }
  /** Edits made in Aspen's own window found while the page shows the model: a toast, once
   *  for each new find (wb.extSeen: per model, the latest seen; the first look only notes it). */
  function watchExt(tab, js) {
    if (!js) return;
    const seen = wb.extSeen || (wb.extSeen = {}), id = (sessOf(tab).model || {}).id || js.model || tab.session;
    const x = extOf(js), was = seen[id];
    seen[id] = Math.max(was || 0, x ? x.t : 0);
    if (!x || was === undefined || x.t <= was) return;
    toast(t("ms_ext_toast"), 6000, WBC.on() ? { label: t("ms_ext_see"), run: () => openChanges(wb.pane) } : undefined);
  }

  /** When Aspen's word on the model was last read: the last run that ran on it (the window's
   *  Run simulation, a program's real run, an applied point's re-run), 0 when none is known. */
  function readAt(tab) {
    const sim = sessOf(tab).sim, jr = (modelSum(sessOf(tab)) || {}).run;
    let at = sim && sim.finished ? sim.finished : 0;
    if (jr && typeof jr.t === "number") at = Math.max(at, jr.t);   // (the journal's: the AI's run too)
    ((wb.state && wb.state.tabs) || []).forEach((x) => {
      if (x.session !== tab.session) return;
      if (x.run && x.run.finished && !x.run.dry_run) at = Math.max(at, x.run.finished);
      const ap = appliedRun(x);
      if (ap) at = Math.max(at, ap.t);
    });
    return at;
  }

  // ------------------------------------------------------------------ the last run's outcome
  const OUTCOMES = ["ok", "warn", "error", "unknown"];
  const SAME_RUN = 5;          // the window's run and the journal's record this close (s): one run
  /** A run's warnings as the server keeps them (tools/probes.run_warnings): its first_warn and the
   *  next few (warns_more), each {kind, objs, where, line, n}. */
  const warnsOf = (o) => [o && o.first_warn].concat(Array.isArray(o && o.warns_more) ? o.warns_more : [])
    .filter((w) => w && typeof w === "object" && w.kind);
  /** A run's words as the server wrote them (sim.text): its sentence (the first line, without
   *  a closing colon), Aspen's run-level messages (the server's sim.msgs where it gives them,
   *  else the "Run status message:" lines of Aspen's answer inside the text), and the whole
   *  text for a tooltip, without the paragraph addressed to the AI ("⚠ STOP — …"). */
  function simWords(sim) {
    const text = String((sim && sim.text) || "").replace(/\r/g, "").trim();
    const head = (text.split("\n")[0] || "").trim().replace(/\s*[：:]$/, "");
    const m = /Run status message:\n((?:[ \t]+\S.*(?:\n|$))+)/.exec(text);
    const lines = Array.isArray(sim && sim.msgs) ? sim.msgs.map((s) => String(s).trim()).filter(Boolean)
      : m ? m[1].split("\n").map((s) => s.trim()).filter(Boolean) : [];
    const full = text.split(/\n[ \t]*\n/).filter((p) => !/^⚠\s*STOP/.test(p.trim())).join("\n\n").trim();
    return { head, lines, full };
  }
  /** A tab's applied point whose re-run ran ({t, outcome, text}), or null. */
  function appliedRun(x) {
    const st = (x.results || {}).state;
    if (!st || st.source === undefined || st.source === null || !Array.isArray(st.values)) return null;
    return OUTCOMES.includes(st.run) && typeof st.t === "number" ? { t: st.t, outcome: st.run, text: String(st.text || "") } : null;
  }
  /** The last run on the model whose outcome the page knows, while no later run is known: the
   *  window's Run simulation (sess.sim that ran: its outcome, Aspen's run-level messages too, so a
   *  recycle that did not converge is an error though no block reports one) or an applied
   *  point's re-run (a tab's results.state). null where a later run's outcome is not known (a
   *  program's run; the AI's, as the change journal dates it), or where Aspen's block marks
   *  changed since that run was first seen here (a run the page did not see). The window's run
   *  and the journal's record of it (within SAME_RUN) are one run with one verdict, the
   *  record's. {src ("sim" | "apply" | "journal"), t, outcome (ok | warn | error | unknown: the
   *  run status unreadable), head, said (the server's sentence on the window's run), lines,
   *  full, warns (warnsOf)}. */
  function lastRun(tab) {
    const sess = sessOf(tab), sim = sess.sim;
    let best = null, other = 0;
    // (a Run refused while another writer held the model, "busy", keeps the last run's record)
    if (sim && (sim.status === "done" || sim.status === "busy") && sim.finished && OUTCOMES.includes(sim.outcome)) {
      best = Object.assign({ src: "sim", t: sim.finished, outcome: sim.outcome, warns: warnsOf(sim) }, simWords(sim));
      best.said = best.head;
    }
    ((wb.state && wb.state.tabs) || []).forEach((x) => {
      if (x.session !== tab.session) return;
      const ap = appliedRun(x), run = x.run || {};
      if (ap && ap.t > (best ? best.t : 0)) {
        const head = ap.outcome === "unknown" ? t("rw_unknown") : t(`ms_run_${ap.outcome}`);
        best = { src: "apply", t: ap.t, outcome: ap.outcome, head, said: head, lines: [], full: ap.text, warns: [] };
      }
      if (run.finished && !run.dry_run) other = Math.max(other, run.finished);
    });
    const j = sess.journal;
    if (j) other = Math.max(other, Number(j.last_run_t) || 0);   // (a run's record is written before its end is stamped)
    // where the journal measures the model, its last run is known whoever ran it (the AI's
    // run_simulation too); the window's own run and its record are one run: the record's verdict,
    // the window's words (they are richer)
    const js = modelSum(sess), jr = js && js.run;
    if (jr && OUTCOMES.includes(jr.status) && typeof jr.t === "number") {
      const lines = Array.isArray(jr.msgs) ? jr.msgs.map((s) => String(s).trim()).filter(Boolean) : [];
      const rec = { src: "journal", t: jr.t, outcome: jr.status, head: t("mp_lastrun", runLine(jr)), said: "", lines,
                    full: lines.join("\n"), warns: warnsOf(jr) };
      if (best && best.src === "sim" && Math.abs(best.t - jr.t) < SAME_RUN) {
        best = Object.assign(rec, { t: Math.max(best.t, jr.t), said: best.said, lines: best.lines.length ? best.lines : lines,
                                    full: best.full || rec.full, warns: best.warns.length ? best.warns : rec.warns });
      } else if (jr.t > (best ? best.t : 0)) best = rec;
    }
    if (!best || other > best.t) return null;
    if (best.src === "journal") return best;     // (every later run moves the journal's: no marks to watch)
    const seen = wb.runSeen || (wb.runSeen = {}), key = `${best.src}:${best.t}`, sig = canon(sess.status || {});
    if (!seen[tab.session] || seen[tab.session].key !== key) seen[tab.session] = { key, sig };
    return seen[tab.session].sig === sig ? best : null;
  }

  /** Aspen's own words for each state, as its status bar says them (tooltips only: never beside
   *  the window's own word). None for warnings: what its status bar says then is not confirmed. */
  const ASPEN = { running: "Running", stale: "Input changed", error: "Results with errors",
    none: "No results", ok: "Results available", incomplete: "Required Input Incomplete" };
  /** The model's state, the first of these that holds: Aspen calculating
   *  on it now, counting (the server's heartbeat: the AI's call, the window's Run simulation or
   *  Save model, a program's step holding the server up); not open; being calculated (Run
   *  simulation, or a program on it or holding it); an input changed since the last run;
   *  results with errors, with warnings (on blocks, counted; else the last run's own, lastRun:
   *  a recycle that did not converge); the last run's status unreadable (unread); none yet;
   *  results available. What Aspen reported, as last read: never a guess at "converged". {key,
   *  word, aspen, more (a line for the tooltip)}. */
  function modelStatus(tab) {
    const sess = sessOf(tab), sim = sess.sim || {}, st = sess.status || {};
    const S = (key, word, more) => ({ key, word, aspen: ASPEN[key] || "", more: more || "" });
    const a = aspenBusy(tab.session);
    // a restore point being saved, the model being restored: said so, counting; it cannot be stopped midway
    if (a && (a.tool === "checkpoint" || a.tool === "restore")) {
      return S("running", busyWords(a, since(a.since)), [t("ms_aspen_tip", whoWord(a.actor), callWords(a), when(a.since)), t("tip_ms_cp")].join("\n"));
    }
    if (a) return S("running", t("conn_busy_aspen", since(a.since)), t("ms_aspen_tip", whoWord(a.actor), callWords(a), when(a.since)));
    if (!isOpen(tab)) return S("closed", t("ms_closed"));
    if (simPending(tab.session)) return S("running", t("ms_sending"));
    if (sim.status === "running") return S("running", t("ms_sim_running"));
    if (wb.state.tabs.some((x) => x.session === tab.session && busy(x)) || (holderOf(tab.session) || {}).actor === "program") {
      return S("running", t("ms_prog_running"));
    }
    // what Aspen still needs (missing.js): it cannot run, so this comes before "input changed"
    const miss = window.WBM ? WBM.of(sess) : null;
    if (miss) {
      const names = (miss.objects || []).slice(0, 4).map((o) => WBM.objName(o)).join(I18N.lang === "zh" ? "、" : ", ");
      return S("incomplete", t("ms_incomplete", (Number(miss.n) || 0) + (Number(miss.more) || 0)), t("tip_ms_incomplete", names));
    }
    const stale = staleAt(tab.session);
    if (stale) return S("stale", t("ms_stale"), [staleLine(modelSum(sess)), lastChange(sess, stale)].filter(Boolean).join("\n"));
    const n = (lvl) => Object.values(st).filter((v) => v && v.level === lvl).length, e = n("error");
    const run = lastRun(tab), ro = run ? run.outcome : "", said = run && ro !== "ok" ? run.said || run.head : "";
    // where blocks carry warnings, the count is the model panel's ⚠ warning rows: the blocks',
    // and the last run's own warning that no block row names (runRow: one row, however many it describes)
    const nw = n("warn"), w = nw ? nw + (runWarns(run, new Set(markedOf(sess).map(([name]) => name))).length ? 1 : 0) : 0;
    if (e) return S("error", t("ms_error", e), said);
    if (ro === "error") return S("error", t("ms_error_run"), said);
    if (w) return S("warn", t("ms_warn", w), said);
    if (ro === "warn") return S("warn", t("ms_warn_run"), said);
    if (ro === "unknown") return S("unread", t("rw_unknown"), said);
    if (!Object.keys(sess.values || {}).length && !sess.sim) return S("none", t("ms_none"));
    return S("ok", t("ms_ok"));
  }

  /** Who made the change that left the results stale, where the server's change journal made
   *  it so (sess.journal): "Last change: AI · set_value ·
   *  ESTCOL › Reflux ratio"; "" otherwise. */
  const INPUT_OPS = ["value", "attr", "add", "remove", "connect", "patch", "restore", "summary"];
  /** "Results out of date: 3 inputs changed since the last run" (the journal's net count:
   *  an input set back to its value does not count), "" where none is or it is not measured. */
  function staleLine(js) {
    const st = js && js.stale, n = Number(st && st.n) || 0;
    return !n ? "" : st.more ? t("mp_stale", cnt(st)) : tn("mp_stale", n);
  }
  function lastChange(sess, stale) {
    const j = sess.journal, l = j && j.last;
    if (!l || j.last_input_t !== stale || !INPUT_OPS.includes(l.op)) return "";
    // (the window's own undo, restore and restore point in words, not their tool names)
    const own = { restore: "act_restore", revert: "act_revert", checkpoint: "act_checkpoint" }[l.tool];
    return t("ms_last_change", whoWord(l.actor), [own ? t(own) : l.tool, l.path && WBL.say(l.path)].filter(Boolean).join(" · "));
  }

  // ------------------------------------------------------------------ Run simulation, Save model
  /** A Run simulation sent from here the server has not taken up yet. */
  function simPending(session) {
    const w = wb.simWait;
    if (!w || w.seen || w.session !== session || Date.now() > w.until) return false;
    return ((sessOf({ session }).sim || {}).at || 0) === w.at;
  }
  /** Why Run simulation cannot go now, or "". */
  function simWhy(tab) {
    if (!wb.connected) return t("why_off");
    if (!isOpen(tab)) return t("why_closed", tab.session);
    if (wb.state.tabs.some((x) => x.session === tab.session && busy(x))) return t("why_sim_busy");
    if ((sessOf(tab).sim || {}).status === "running" || simPending(tab.session) || aspenBusy(tab.session)) return t("why_sim_running");
    return "";
  }
  /** Aspen's Run on the tab's model (reinit: Reinitialize first); the block program does not
   *  run. Says why where it cannot go. */
  function runSim(tab, reinit) {
    if (!tab) return;
    const why = simWhy(tab);
    if (why) { toast(why); return; }
    wb.simWait = { session: tab.session, at: (sessOf(tab).sim || {}).at || 0, until: Date.now() + 6000, seen: false };
    wb.post(Object.assign({ type: "run_sim", tab: tab.id }, reinit ? { reinit: true } : {}));
    setTimeout(renderModelBar, 6100);            // no answer: the button comes back
    renderModelBar();
  }
  /** The answer to a Run simulation sent from here: one that did not run says why. */
  function watchSim() {
    const w = wb.simWait;
    if (!w) return;
    const sim = (wb.state.sessions[w.session] || {}).sim || {};
    if ((sim.at || 0) === w.at) { if (!w.seen && Date.now() > w.until) wb.simWait = null; return; }
    if (sim.status === "running") { w.at = sim.at; w.seen = true; return; }   // taken up: its end is the next change
    wb.simWait = null;
    const tab = shownTab();
    if (sim.status === "error" && sim.incomplete && tab && tab.session === w.session) {
      toast(t("sim_refused_missing"), 8000, { label: t("show"), run: () => WBM.open(shownTab()) });
    } else if (sim.status === "error" && sim.text) toast(sim.text, 6000);
    else if (sim.status === "busy") toast(t("why_sim_busy"), 5000);
  }

  function savePending(session) {
    const w = wb.saveWait;
    return !!w && w.session === session && Date.now() < w.until;
  }
  function saveWhy(tab) {
    if (!wb.connected) return t("why_off");
    if (!isOpen(tab)) return t("why_closed", tab.session);
    if (wb.state.tabs.some((x) => x.session === tab.session && busy(x))) return t("why_save_busy");
    if (savePending(tab.session)) return t("why_save_wait");
    return "";
  }
  /** Save the tab's model (.bkp): the server backs the old file up first. path: a Save As (a
   *  name beside the model's file). */
  function saveModel(tab, path) {
    if (!tab) return;
    const why = saveWhy(tab);
    if (why) { toast(why); return; }
    wb.saveWait = { session: tab.session, at: (sessOf(tab).saved || {}).at || 0, until: Date.now() + 30000 };
    wb.post(Object.assign({ type: "save_model", tab: tab.id }, path ? { path } : {}));
    toast(t("save_sending"), 4000);
    setTimeout(renderModelBar, 30100);
    renderModelBar();
  }
  function saveModelAs(tab) {
    const f = modelFile(tab), m = /^(.*?)(\.(bkp|apw|apwz))?$/i.exec(f.name);
    dialog({ title: t("save_as_title"), text: `${m[1]} (2)${m[2] || ".bkp"}`, single: true, help: t("save_as_help"),
             ok: t("save"), onOk: (v) => { const p = v.trim(); if (p) saveModel(tab, p); } });
  }
  /** The answer to a Save model sent from here: where it went, and that the old file was kept. */
  function watchSave() {
    const w = wb.saveWait;
    if (!w) return;
    const saved = (wb.state.sessions[w.session] || {}).saved || {};
    if ((saved.at || 0) > w.at) {
      wb.saveWait = null;
      toast(t(saved.backup ? "save_done_bk" : "save_done", saved.path || ""), 5000);
    } else if (Date.now() > w.until) wb.saveWait = null;   // a failure is a line in the chat
  }

  // ------------------------------------------------------------------ the run log's model lines
  /** Each Run simulation and Save model made from here leaves a line in the run log of every tab
   *  on its model: taken from what the state says of the last of each (sess.sim ended, run or
   *  not; sess.saved), kept per session while the page is open (so a reload keeps the last
   *  one of each), in time order, the last MODEL_LOG of them. */
  const MODEL_LOG = 40;
  function noteModelLog() {
    const all = wb.modelLog || (wb.modelLog = {});
    Object.entries((wb.state && wb.state.sessions) || {}).forEach(([session, sess]) => {
      const add = (e) => {
        const list = all[session] || (all[session] = []);
        if (list.some((x) => x.key === e.key)) return;
        list.push(e);
        list.sort((a, b) => a.t - b.t);
        if (list.length > MODEL_LOG) list.shift();
      };
      const sim = sess && sess.sim, saved = sess && sess.saved;
      if (sim && sim.status === "done" && sim.finished) add({ key: `sim:${sim.finished}`, kind: "sim", t: sim.finished, o: sim });
      else if (sim && sim.status === "error" && sim.at && sim.text) add({ key: `sim:${sim.at}`, kind: "sim", t: sim.at, o: sim });
      if (saved && saved.at) add({ key: `save:${saved.at}`, kind: "save", t: saved.at, o: saved });
    });
  }
  /** The run log's model lines of a session, in words: {key, t, cls ("" | "warn" | "bad"),
   *  text, tip}. A run says the server's sentence ("HH:MM Run simulation: Simulation
   *  finished"), then Aspen's run-level messages and the blocks with errors; a save, the file
   *  it went to and whether the old one was backed up first. */
  function modelLogOf(session) {
    noteModelLog();
    return ((wb.modelLog || {})[session] || []).map((e) => {
      const o = e.o, at = hhmm(e.t);
      if (e.kind === "save") {
        const file = String(o.path || "").split(/[\\/]/).pop() || String(o.path || "");
        const bk = o.backup && o.backup.path ? `\n${t("log_backup_at", o.backup.path)}` : "";
        return { key: e.key, t: e.t, cls: "", text: t(o.backup ? "log_saved_bk" : "log_saved", at, file), tip: `${o.path || ""}${bk}` };
      }
      const w = simWords(o), ran = o.status === "done", outcome = ran ? o.outcome : "error";
      const errs = ran && Array.isArray(o.errors) && o.errors.length ? [t("log_sim_blocks", o.errors.join(", "))] : [];
      const more = w.lines.slice(0, 8).concat(errs).map((l) => `\n  ${l}`).join("");
      return { key: e.key, t: e.t, cls: outcome === "error" ? "bad" : outcome === "warn" ? "warn" : "",
               text: t(o.reinit ? "log_sim_reinit" : "log_sim", at, w.head || t(ran ? "log_sim_done" : "log_sim_not")) + more,
               tip: w.full };
    });
  }
  /** The run log, shown (the dock opened where it is folded), at a model line. */
  function showLogAt(pane, key) {
    if (!pane) return;
    if (prefs().dockMode === "min") setDock(pane, "split");
    showPanel(pane, "log");
    const el = [...pane.q(".tab-log").querySelectorAll(".log.sim")].find((x) => x.dataset.k === key);
    if (el) el.scrollIntoView({ block: "nearest" });
  }

  // ------------------------------------------------------------------ the header's model group
  /** #modelstat, Save model and Run simulation for the shown tab. Another model shown than a
   *  moment ago: the capsule flashes once. */
  /** The model's states the header shows as its dot alone (the word in the tooltip). */
  const QUIET = ["ok", "none"];
  function renderModelBar() {
    const bar = $("bar"), tab = shownTab();
    if (!tab || !wb.state) return;
    watchSim();
    watchSave();
    const el = $("modelstat"), s = modelStatus(tab), f = modelFile(tab), at = readAt(tab);
    const js = modelSum(sessOf(tab)), u = unsavedOf(js), x = extOf(js);
    watchExt(tab, js);
    // the objects came: an open panel shows them, unless the keyboard walks it
    const ot = (sessOf(tab).objects || {}).t || 0;
    if (ot !== wb.objSeen) {
      wb.objSeen = ot;
      if (WBA.menuOpen() && wb.menuAt === el && wb.pane && !$("menu").querySelector(":focus-visible")) WBA.openMenu(el, modelPanel(wb.pane, tab));
    }
    const sig = JSON.stringify([I18N.lang, s, f, wb.connected, at, u, x && [x.t, x.n, x.recent]]);
    if (el.dataset.sig !== sig) {
      el.dataset.sig = sig;
      // (the word only where something is to be done or waited for -- inputs changed, errors,
      // warnings, missing inputs, calculating, closed; results available, none yet: the dot alone,
      // its word the tooltip's first line)
      const said = !QUIET.includes(s.key);
      el.className = `modelstat ${s.key}${wb.connected ? "" : " unknown"}${said ? "" : " quiet"}`;
      const [h, tl] = nameParts(f.name);
      el.querySelector(".ms-h").textContent = h;
      el.querySelector(".ms-t").textContent = tl;
      el.querySelector(".ms-st").textContent = said ? s.word : "";
      // changed since the file was saved (the journal's count): a small chip after its name,
      // "Unsaved · 7", with its own tooltip (what it counts, how to save); the panel says the rest
      let dot = el.querySelector(".ms-uns");
      if (!dot && u) el.querySelector(".ms-name").after(dot = Object.assign(document.createElement("span"), { className: "ms-uns hidden" }));
      if (dot) {
        dot.classList.toggle("hidden", !(u && u.n));
        if (u && u.n) {
          dot.textContent = t("ms_uns_chip", cnt({ n: u.n, more: u.more }));
          dot.title = t(u.n === 1 && !u.more && I18N.lang !== "zh" ? "tip_ms_uns_1" : "tip_ms_uns", cnt(u), u.runs ? tn("tip_ms_uns_runs", u.runs) : "")
            + t("tip_ms_uns_save");
        }
      }
      el.title = [said ? "" : s.word, f.path || f.name, [s.aspen ? t("mp_aspen", s.aspen) : "", at ? t("ms_read_at", when(at)) : ""].filter(Boolean).join(" · "),
        s.more, u && u.tip, x && x.recent ? t("mp_ext_new", when(x.t)) : "",
        wb.connected ? "" : t("ms_unknown"), t("tip_modelstat")].filter(Boolean).join("\n");
      soon("reveal", revealTab);                 // its width is the tab strip's too
    }
    if (el.dataset.sess && el.dataset.sess !== tab.session) {
      const g = ghost(el, 600);                  // another model: a bright copy over it fades out
      g.style.width = `${el.offsetWidth}px`;
    }
    el.dataset.sess = tab.session;
    const save = bar.querySelector('[data-a="save_model"]'), saveNo = saveWhy(tab), tip = saveNo || t("tip_save", f.path || f.name);
    save.classList.remove("hidden");
    save.disabled = !!saveNo;
    if (save.title !== tip) save.title = tip;
    const sim = bar.querySelector(".simrun"), simNo = simWhy(tab), run = sim.querySelector('[data-a="run_sim"]'), more = sim.querySelector('[data-a="run_sim_menu"]');
    sim.classList.remove("hidden");
    run.disabled = more.disabled = !!simNo;
    run.title = simNo || (editsOf(tab) ? `${t("tip_run_sim")}
${t("tip_run_sim_edits")}` : t("tip_run_sim"));   // (block edits: the proposal card's)
    more.title = simNo || t("tip_run_sim_menu");
  }

  /** Run simulation's ▾: the other way to run it. */
  function simItems(tab) {
    const why = simWhy(tab);
    return [{ label: t("m_run_reinit"), icon: "refresh", disabled: !!why, tip: why || t("tip_run_reinit"), run: () => runSim(tab, true) }];
  }

  // ------------------------------------------------------------------ the model panel
  /** A line of the panel: its words, a class, a tooltip. */
  const line = (text, cls, tip) => `<div class="mp-line${cls ? ` ${cls}` : ""}"${tip ? ` title="${esc(tip)}"` : ""}>${esc(text)}</div>`;
  /** The file's name and its path. */
  const fileHtml = (f) => `<div class="mp-file"><b>${esc(f.name)}</b><small>${esc(f.path || t("mp_no_path"))}</small></div>`;
  /** The state's line: its dot and the window's word; Aspen's own word, when it was read (not
   *  where the last run's line says that time: runT) and who is calculating in its tooltip. */
  function stateHtml(s, at, runT) {
    const read = at && !(runT && Math.abs(at - runT) < SAME_RUN) ? t("ms_read_at", when(at)) : "";
    const tip = [[s.aspen ? t("mp_aspen", s.aspen) : "", read].filter(Boolean).join(" · "),
      ["running", "stale", "incomplete"].includes(s.key) ? s.more : ""].filter(Boolean).join("\n");
    return `<div class="mp-state ${esc(s.key)}"${tip ? ` title="${esc(tip)}"` : ""}><i class="dot"></i><b>${esc(s.word)}</b></div>`;
  }

  /** The model panel (#modelstat's menu), state and actions only:
   *  "Model file" (the file and its path; changes not saved, only when there are some), "State" (the
   *  state; the inputs changed since the last run; the last run; a recent edit in Aspen's window;
   *  the last run's own warning or error, each block Aspen reports on, the diagnosis, what Aspen
   *  still needs: stateRows), "Model objects" (objItems: what is set outside the flowsheet), restore points (only
 *  when there are some: app-undo.js cpItems) and actions. */
  function modelPanel(pane, tab) {
    const f = modelFile(tab), s = modelStatus(tab), sess = sessOf(tab), sim = sess.sim, saved = sess.saved, at = readAt(tab);
    const js = modelSum(sess);
    if (js) return modelPanelJ(pane, tab, js);
    const lines = [sim && sim.finished && t("mp_last_sim", when(sim.finished), duration({ started: sim.started, finished: sim.finished })),
      saved && saved.at && t("mp_last_saved", when(saved.at)), !wb.connected && t("ms_unknown")].filter(Boolean);
    const items = [{ title: t("mp_file") }, { html: fileHtml(f) }, { sep: true }, { title: t("mp_state") },
      { html: stateHtml(s, at, sim && sim.finished) + lines.map((x) => line(x)).join("") }];
    return items.concat(stateRows(pane, tab, sess), panelTail(pane, tab, f, sess));
  }
  /** The model panel where the journal measures the model's state: under the file, the
   *  changes not saved and the last save (only when there are some: a click shows them in the
   *  Changes tab; the backup and the runs since in its tooltip); under the state, which inputs
   *  changed since the last run (each a link to its field), the last run (its number, time,
   *  outcome, who started it when not the user) and a recent edit found in Aspen's own window. */
  function modelPanelJ(pane, tab, js) {
    const f = modelFile(tab), s = modelStatus(tab), sess = sessOf(tab), sim = sess.sim, saved = sess.saved, at = readAt(tab);
    const u = unsavedOf(js), sv = js.save, bk = js.backup, x = extOf(js), jr = js.run, st = js.stale || {};
    const items = [{ title: t("mp_file") }, { html: fileHtml(f) }];
    if (u && u.n) {
      const text = [u.line, sv && sv.how !== "open" ? saveLine(sv) : ""].filter(Boolean).join(" · ");
      let back = "";
      if (bk && typeof bk.t === "number") {
        const b = saved && saved.backup, where = b && b.id === bk.id && b.path ? b.path
          : `~/.aspen-mcp/checkpoints/${(sess.model && sess.model.id) || js.model || ""}`;
        back = `${t("mp_backup", when(bk.t))}\n${where}`;
      }
      const tip = [back, u.rl].filter(Boolean).join("\n");
      items.push(WBC.on() ? { label: text, cls: "mp-uns", tip: [tip, t("tip_mp_see_changes")].filter(Boolean).join("\n"), run: () => openChanges(pane) }
        : { html: line(text, "mp-uns on", tip) });
    }
    const runT = jr && typeof jr.t === "number" ? jr.t : sim && sim.finished;
    items.push({ sep: true }, { title: t("mp_state") }, { html: stateHtml(s, at, runT) + (staleLine(js) ? line(staleLine(js), "mp-stale") : "") });
    // the inputs changed since the last run, the latest first: a click shows the field
    const top = Array.isArray(st.top) && Number(st.n) ? st.top : [];
    top.forEach((it) => {
      const o = inputOf(it, tab.session), by = who(it.actor);
      const tip = [o.full, o.path].filter(Boolean).join("\n");
      items.push(o.tg ? { label: `${o.word} · ${by}`, cls: "mp-sti", tip: `${tip}\n${t("tip_mp_st", by)}`, run: () => gotoChange(pane, o.tg, o.path) }
        : { html: line(`${o.word} · ${by}`, "mp-sti", tip) });
    });
    if (top.length && (Number(st.n) || 0) > top.length) items.push({ html: line(t("mp_st_more", (Number(st.n) - top.length) + (st.more ? "+" : "")), "mp-sti") });
    const lines = [jr && typeof jr.t === "number" ? t("mp_lastrun", runLine(jr))
        : sim && sim.finished ? t("mp_last_sim", when(sim.finished), duration({ started: sim.started, finished: sim.finished })) : "",
      !wb.connected && t("ms_unknown")].filter(Boolean);
    let tail = lines.map((x2) => line(x2)).join("");
    if (x && x.recent) tail += line(t("mp_ext_new", when(x.t)), "mp-ext new", t("tip_mp_ext", x.n));
    if (tail) items.push({ html: tail });
    return items.concat(stateRows(pane, tab, sess), panelTail(pane, tab, f, sess));
  }

  // ------------------------------------------------------------------ the last run's warning, under the state
  /** Where Aspen's own window shows each kind of warning (probes.WARN_WHERE: blk, conv, cp, rs),
   *  in the names of Aspen's GUI, the same in both languages. */
  const WHERE = { blk: (o) => (o ? `${o} › Results › Status` : ""), conv: (o) => (o ? `Convergence › ${o} › Results` : "Convergence"),
    cp: () => "Control Panel (F7)", rs: () => "Results Summary › Run Status" };
  const RW_KINDS = ["block", "conv", "flash", "input", "calc", "prop", "other"];
  /** A warning in a few words: its kind, then the objects Aspen lists (three, then +N) or how
   *  many messages it stands for. */
  function warnWords(w) {
    const objs = Array.isArray(w.objs) ? w.objs.map(String).filter(Boolean) : [], n = Number(w.n) || 0;
    const names = objs.length > 3 ? `${objs.slice(0, 3).join(", ")} +${objs.length - 3}` : objs.join(", ");
    return [t(`rw_${RW_KINDS.includes(w.kind) ? w.kind : "other"}`), names || (n > 1 ? String(n) : "")].filter(Boolean).join(" · ");
  }
  const whereOf = (w) => { const f = WHERE[w.where]; return f ? f(Array.isArray(w.objs) ? w.objs[0] : "") : ""; };
  const chipHtml = (where) => (where ? `<span class="mp-where" title="${esc(t("rw_where"))}">${esc(where)}</span>` : "");
  let rwOpen = null;             // the run whose Aspen lines are shown (a redraw of the panel keeps them)
  /** The last run's warnings the server described that no block row names already (a block's
   *  warning has a row of its own): a run with any of these is a warning row of its own. */
  function runWarns(bad, marked) {
    if (!bad || bad.outcome !== "warn") return [];
    return bad.warns.filter((w) => !(w.kind === "block" && Array.isArray(w.objs) && w.objs.length && w.objs.every((o) => marked.has(String(o)))));
  }
  /** The blocks the model panel gives a row of their own: Aspen's errors and warnings on them. */
  const markedOf = (sess) => Object.entries(sess.status || {}).filter(([, v]) => v && (v.level === "error" || v.level === "warn"));
  /** The last run's own row (where the capsule counts, "Warnings · N" is its ⚠ rows; each fact once):
   *  - a warning the server described that no block row names (runWarns): ⚠, the first one's kind
   *    and objects and where Aspen shows it; a click shows or hides the others and Aspen's lines;
   *  - else, where blocks have rows of their own (they say what is wrong): Aspen's run-status lines,
   *    not a warning of their own, as "Aspen status messages" · Control Panel (F7) with no ⚠, a click showing
   *    or hiding them (six at most); none without lines;
   *  - else (the run as a whole is what went wrong, and the capsule counts nothing): ⚠ "Simulation (overall)"
   *    · warning / error, a click showing Aspen's lines, or with none going where the run is (the run
   *    log, the applied point's result, the Changes tab).
   *  The server's sentence is its tooltip. null: nothing to say. */
  function runRow(pane, tab, bad, marked) {
    const lvl = bad.outcome === "error" ? "error" : "warn";
    const ws = runWarns(bad, marked), msgs = !ws.length && marked.size > 0;
    if (msgs && !bad.lines.length) return null;
    const head = ws.length ? warnWords(ws[0]) : msgs ? t("mp_run_msgs") : `${t("mp_run")} · ${t(lvl === "error" ? "lvl_error" : "lvl_warn")}`;
    const more = ws.slice(1).map((w) => `<div class="mp-rwm">${esc(warnWords(w))}${chipHtml(whereOf(w))}</div>`).join("");
    const pre = bad.lines.length ? `<pre>${esc(bad.lines.slice(0, 6).join("\n"))}</pre>` : "";
    const key = `${bad.src}:${bad.t}`, has = !!(more || pre), open = has && rwOpen === key;
    const said = bad.said || (bad.src === "journal" ? "" : bad.head);     // (the journal's own head is the last-run line)
    const tip = [said, bad.src === "apply" ? bad.full : "", has ? t("rw_details") : ""].filter(Boolean).join("\n");
    const where = ws.length ? whereOf(ws[0]) : msgs ? WHERE.cp() : "";
    const btn = `<button type="button" class="mi mp-rw ${msgs ? "mp-msgs" : `mp-${lvl}`}${open ? " open" : ""}" role="menuitem"${has ? ` aria-expanded="${open}"` : ""}`
      + `${tip ? ` title="${esc(tip)}"` : ""}>${icon(msgs ? "info" : "warn")}<span class="bt">${esc(head)}</span>${chipHtml(where)}`
      + `${has ? icon("chevron-down") : ""}</button>`;
    const sim = sessOf(tab).sim, go = () => {
      if (bad.src === "sim") showLogAt(pane, sim ? `sim:${sim.finished}` : "");
      else if (bad.src === "apply") { if (prefs().dockMode === "min") setDock(pane, "split"); showPanel(pane, "results"); }
      else openChanges(pane);
    };
    return { html: btn + (has ? `<div class="mp-rwd"${open ? "" : " hidden"}>${more}${pre}</div>` : ""), wire: (box) => {
      const b = box.querySelector(".mp-rw"), d = box.querySelector(".mp-rwd");
      b.addEventListener("click", () => {
        if (!d) { WBA.closeMenus(); go(); return; }
        rwOpen = d.hidden ? key : null;
        d.hidden = !d.hidden;
        b.classList.toggle("open", !d.hidden);
        b.setAttribute("aria-expanded", String(!d.hidden));
      });
    } };
  }
  /** Under the state: the last run's own warning or error (runRow), each block Aspen reports an
   *  error or a warning on (a click shows it and opens its inspector), the last run's diagnosis
   *  (diag.js) and what Aspen still needs (missing.js), each only where there is one. */
  function stateRows(pane, tab, sess) {
    const items = [];
    const msgs = markedOf(sess).sort((a, b) => (a[1].level === b[1].level ? a[0].localeCompare(b[0]) : a[1].level === "error" ? -1 : 1));
    const run = lastRun(tab), bad = run && (run.outcome === "error" || run.outcome === "warn") ? run : null;
    const row = bad && runRow(pane, tab, bad, new Set(msgs.map(([name]) => name)));
    if (row) items.push(row);
    msgs.forEach(([name, v]) => items.push({
      label: `${name} · ${t(v.level === "error" ? "lvl_error" : "lvl_warn")} · ${v.msg || ""}`, icon: "warn", cls: `mp-${v.level}`,
      tip: `${t("tip_log_show", name)}\n${(v.lines || []).join("\n").trim() || v.msg || ""}`,
      run: () => pick(pane, { kind: "block", name }, { ring: true }) }));
    // (⚠ marks the warnings and errors only, so "Warnings · N" counts what it shows: the diagnosis its own)
    const d = window.WBD ? WBD.panelItem(pane, tab) : null;
    if (d) items.push(d.icon === "warn" ? Object.assign({}, d, { icon: "search" }) : d);
    if (window.WBM) items.push(...WBM.panelItems(pane, tab));
    return items;
  }
  // ------------------------------------------------------------------ the model's objects
  /** The groups of Aspen's navigation pane, in its order (the server's objects carry one). */
  const GROUPS = ["setup", "components", "properties", "reactions", "convergence", "flowsheeting", "analysis"];
  const OBJ_ASK = 3000;          // the list is asked for again when the panel opens this long after
  /** The server's list of the session's objects, asked for when the panel opens (event objects). */
  function askObjects(tab, open) {
    const at = wb.objAsk || (wb.objAsk = {});
    if (!open && Date.now() - (at[tab.session] || 0) < OBJ_ASK) return;
    at[tab.session] = Date.now();
    if (wb.connected && isOpen(tab)) wb.post(Object.assign({ type: "objects", tab: tab.id }, open ? { open } : {}));
  }
  /** "Model objects": a line a group of Aspen's navigation pane (Aspen's English, a translation beside it in Chinese: WBL.title), its
   *  objects as capsules -- an amber dot where Aspen flags one incomplete; a click opens it in the
   *  inspector. A folder whose objects cost a read (Sensitivity after a run) is one capsule with
   *  its count, listed when clicked. Nothing until the list came. */
  function objItems(pane, tab, sess) {
    askObjects(tab);
    const items = ((sess.objects || {}).items || []).filter((o) => o && GROUPS.includes(o.g));
    if (!items.length) return [];
    const cap = (o) => {
      const g = I18N.en(`mo_${o.g}`), where = o.name !== o.c ? `${o.c} › ${o.name}` : g === o.c ? g : `${g} › ${o.c}`;
      const tip = [where, o.type, o.todo ? t("tip_mo_todo") : "", o.folder ? t("tip_mo_folder") : ""].filter(Boolean).join("\n");
      return `<button class="mo-o" data-path="${esc(o.path)}" title="${esc(tip)}">${WBL.title(o.name)}${o.folder ? `<small>${o.n}</small>` : ""}`
        + `${o.todo ? '<i class="mo-dot" aria-hidden="true"></i>' : ""}</button>`;
    };
    const html = GROUPS.map((g) => {
      const os = items.filter((o) => o.g === g);
      return os.length ? `<div class="mo-g"><span class="mo-t">${WBL.title(t(`mo_${g}`))}</span>`
        + `<span class="mo-l">${os.map(cap).join("")}</span></div>` : "";
    }).join("");
    return [{ sep: true }, { title: t("mp_objects") }, { html: `<div class="mo">${html}</div>`, wire: (box) => {
      box.addEventListener("click", (ev) => {
        const b = ev.target.closest && ev.target.closest(".mo-o"), o = b && items.find((x) => x.path === b.dataset.path);
        if (!o) return;
        if (o.folder) { askObjects(tab, o.path); return; }
        WBA.closeMenus();
        pick(pane, { kind: "object", path: o.path, name: o.name, type: o.type || o.c });
      });
    } }];
  }

  /** The panel after the state: the restore points (only where there are some), then the
   *  actions (Create restore point… among them). */
  function panelTail(pane, tab, f, sess) {
    const items = [...objItems(pane, tab, sess), ...cpItems(pane, tab)];
    items.push({ sep: true }, { title: t("mp_do") });
    const simNo = simWhy(tab), saveNo = saveWhy(tab);
    items.push({ label: t("run_sim"), icon: "play", keys: "F5", disabled: !!simNo, tip: simNo || t("tip_run_sim"), run: () => runSim(tab) },
               { label: t("m_run_reinit"), icon: "refresh", disabled: !!simNo, tip: simNo || t("tip_run_reinit"), run: () => runSim(tab, true) },
               { label: t("m_save_model"), icon: "save", keys: "Ctrl+S", disabled: !!saveNo, tip: saveNo || t("tip_save", f.path || f.name), run: () => saveModel(tab) },
               { label: t("m_save_model_as"), icon: "save", disabled: !!saveNo, tip: saveNo || t("tip_save_as"), run: () => saveModelAs(tab) });
    items.push(...cpItems(pane, tab, "save"));
    const why = !wb.connected ? t("why_off") : !isOpen(tab) ? t("why_closed", tab.session) : "";
    const ms = (sess.missing || {}).state;
    if (ms === "off" || ms === "unknown") {        // (the automatic scan is off, or has not run yet)
      items.push({ label: t("m_check_missing"), icon: "search", disabled: !!why, tip: why || t("tip_m_check_missing"), run: () => WBM.check(tab) });
    }
    items.push({ label: t("m_refresh"), icon: "refresh", disabled: !!why, tip: why || t("tip_refresh"), run: () => wb.post({ type: "refresh", tab: tab.id }) });
    return items;
  }

  Object.assign(WBA, { modelLogOf, modelPanel, modelSum, renderModelBar, runSim, saveModel, simItems });
})();
