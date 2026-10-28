/* Aspen Workbench page: wires tabs, panes, Blockly, the flowsheet and the panels to the
 * server.
 *
 * The server owns state.json; window.py pushes every new version into wb.applyState().
 * The page never edits that state directly. It posts events (program edits, notes, tab
 * changes, run requests, values typed into the inspector) through pywebview.api.post(),
 * and the server's answer comes back as the next state. So a change made by the LLM and a
 * change made here take the same path.
 *
 * Every tab owns a Blockly workspace. The pane shows one tab: its blocks down the left
 * column, under the program's own run bar (what it is doing, Check program, Run program,
 * Stop while it runs), the column folded to a strip while there is no program; on the right
 * its session's flowsheet, and under it the dock with the AI chat, run log and results, and
 * the composer to ask the AI under all three. The header runs the model: the tabs, the model
 * shown and its state, Save model and Run simulation.
 * Workspaces of the other tabs wait off screen in #ws-store.
 */
/* The page's script is split by feature into these files, loaded in this order by index.html:
 *
 *   util.js           the namespace WBA and the helpers every script uses (loaded first)
 *   app-core.js       wb, icons in markup, prefs, posting, state accessors
 *   app-glass.js      glide, liquid glass lenses, the glint (no app state)
 *   app-widgets.js    menus, the one dialog, toast, ghost, copyText, saveFile
 *   app-state.js      a new state: language, one record per tab, the tab shown
 *   app-layout.js     columns and dock: sizes, modes, splitters, panels, results
 *   app-pane.js       the pane: made, a tab shown, its listeners, act(), renderPane
 *   app-program.js    block program: versions, the AI version held, canvas, categories
 *   app-run.js        Run / Check / Stop, a failed run, the run log, the run cursor
 *   app-status.js     the program's run bar: its status capsule, buttons, the strip, progress
 *   app-proposal.js   the AI's proposal: its card under the run bar, the decision, each step
 *   app-step.js       stepping through: the run bar while paused, the card beside the step, breakpoints
 *   app-turn.js       a manual step: the run bar and the card beside the step while a run waits for input
 *   app-model.js      the header's model group: the model's state, Run simulation, Save model
 *   app-fsl.js        flowsheet arrangement: Aspen layout, drags, undo / redo
 *   app-flowsheet.js  around the drawing: fsView, AI marks, stale, peek, toolbar, chip, edges
 *   app-preview.js    a proposal's preview on the drawing: its pill, tags, kept places
 *   app-group.js      a proposal applied by group: the group card, its marks, F10
 *   app-effects.js    a run's result tags on the drawing: what moved, the goal first
 *   app-flows.js      the flow width layer: bands by a component's flow, its button and menu
 *   app-comp.js       a stream's composition: the inspector's section, the hover card's line, the Values layer's line
 *   app-pins.js       the annotations layer: the AI's reasons, replies and notes as markers and a card
 *   app-heat.js       heat plans and the heat plan card
 *   app-chat.js       AI chat, the composer, editing a request
 *   app-wait.js       the wait for the AI's answer: the line under a request, the games
 *   app-inspector.js  pick / reveal, the selection hub, the inspector and its rows
 *   app-undo.js       undo / redo previews, restoring a restore point, the model's restore points
 *   app-replay.js     the timeline made into blocks, Aspen's own drawing redrawn: requests and answers
 *   app-tabs.js       tab strip (one tab per model), what can be done to a tab, .awb files
 *   app-subtabs.js    a model's sub-tabs over the program (its programs, the AI's proposals) and its History
 *   app-conn.js       the connection capsule, #ai-bar, wb.setConnected and wb.setServer
 *   app-brake.js      the AI's brakes beside #ai-bar: its mode, Pause AI / Resume AI
 *   app-follow.js     following the AI's edits on the flowsheet (a switch in the review menu)
 *   learn.js          learning mode (a switch in the review menu, its tag) and predictions (WBLP)
 *   app-tour.js       help: the beginner tour, the flowsheet legend, what a first launch shows
 *   app-main.js       the ... menu, the keyboard, startup (loaded last)
 *
 * They share one namespace, WBA (window.WBA, util.js). Each file is an IIFE: it takes what it
 * uses from files loaded before it by value (const { a, b } = WBA), and the functions it calls
 * from files loaded after it through WBA.later (a forwarder that looks the name up at call
 * time), and puts what the others use on WBA at its end (Object.assign(WBA, {...})). A
 * value that is not a function is only taken from a file loaded before. The page's public
 * face is window.wb, as before (applyState, setConnected, setServer, post, and the state; takeFaults,
 * what failed in them, for window.py's log). */
(function () {
  "use strict";
  const { icon, sessOf } = WBA;
  const { layout } = WBA.later;

  const $ = (id) => document.getElementById(id);
  const canon = (v) => JSON.stringify(v, (k, x) => (x && typeof x === "object" && !Array.isArray(x)
    ? Object.keys(x).sort().reduce((o, key) => ((o[key] = x[key]), o), {}) : x));
  // sentences in a row: a space between them in English, none after a Chinese full stop
  const sentences = (...a) => a.filter(Boolean).join(I18N.lang === "zh" ? "" : " ");

  // An element with data-icon="save" gets icon("save") in front of its text, which moves into a
  // span (.bt) so that I18N.apply can change the text without dropping the icon.
  function dressIcons(root) {
    root.querySelectorAll("[data-icon]").forEach((el) => {
      if (el.querySelector(":scope > svg.ic")) return;
      if (!el.querySelector(":scope > .bt")) {
        const bt = document.createElement("span");
        bt.className = "bt";
        bt.append(...el.childNodes);
        el.append(bt);
      }
      el.insertAdjacentHTML("afterbegin", icon(el.dataset.icon));
    });
  }
  function setIcon(el, name) {
    if (!el || el.dataset.icon === name) return;
    el.dataset.icon = name;
    const use = el.querySelector(":scope > svg.ic use");
    if (use) use.setAttribute("href", `#i-${name}`);
    else dressIcons(el.parentNode);
  }

  // prog: the last progress read for each running optimization, by tab id ({file, s});
  // awaitTabs: the tabs asked of the server (tab_new) and what to do once each exists (newTab)
  const wb = (window.wb = { state: null, rev: -1, connected: false, lang: null, recs: new Map(), pane: null,
    units: {}, pendingActive: null, lastActive: null, dragRow: null, heat: {}, prog: new Map(), awaitTabs: [], icon,
    expanded: new Set(), outN: 0 });                // requests shown whole in the chat; requests sent here

  // This viewer's own conveniences (the layout, drafts, one-time hints), by key. The real
  // window forgets its localStorage on every launch (pywebview runs WebView2 in private
  // mode, on a new port each time), so the window keeps them in its prefs file: read once
  // when the bridge comes up, before the first state is applied (loadPrefs), and written
  // back a moment after each change. Elsewhere (a browser preview) localStorage when it
  // works. prefGet: the text, null when unset, undefined when nothing can keep it.
  const PREF = { file: null, dirty: {}, timer: 0 };  // file: the prefs file's keys, once read
  function prefGet(k) {
    if (PREF.file) return Object.prototype.hasOwnProperty.call(PREF.file, k) ? PREF.file[k] : null;
    try { return localStorage.getItem(k); } catch (e) { return undefined; }
  }
  function prefSet(k, v) {                           // v null: forget k
    const s = v == null ? null : String(v);
    try { if (s === null) localStorage.removeItem(k); else localStorage.setItem(k, s); } catch (e) { /* private mode */ }
    if (!PREF.file) return;
    if (s === null) delete PREF.file[k]; else PREF.file[k] = s;
    PREF.dirty[k] = s;
    clearTimeout(PREF.timer);
    PREF.timer = setTimeout(flushPrefs, 400);        // a draft changes with every key
  }
  function flushPrefs() {
    clearTimeout(PREF.timer);
    const api = window.pywebview && window.pywebview.api, dirty = PREF.dirty;
    if (!Object.keys(dirty).length || !(api && api.set_prefs)) return;
    PREF.dirty = {};
    try { api.set_prefs(dirty).catch(() => {}); } catch (e) { /* the window is closing */ }
  }
  /** Read the window's prefs file, then take the sizes and hints from it; a state that
   *  comes meanwhile waits (wb.prefsWait), so drafts and the one-time notice see the file.
   *  A bridge that does not answer holds nothing up for long. */
  function loadPrefs(api) {
    const wait = (wb.prefsWait = { s: null });
    const done = (all) => {
      if (wb.prefsWait !== wait) return;
      wb.prefsWait = null;
      if (all && typeof all === "object" && !Array.isArray(all)) {
        PREF.file = Object.fromEntries(Object.entries(all).filter(([, v]) => typeof v === "string"));
      }
      readPrefs();
      layout();
      if (wait.s) wb.applyState(wait.s);
      if (PREF.file && wb.state) {                   // drafts and program folds of tabs closed while the window was not open
        const ids = new Set(wb.state.tabs.map((x) => x.id));
        Object.keys(PREF.file).forEach((k) => {
          const m = /^wb\.(draft|prog)\.(.+)$/.exec(k);
          if (m && !ids.has(m[2])) prefSet(k, null);
        });
      }
    };
    setTimeout(done, 2000);
    return Promise.resolve().then(() => api.prefs()).then(done, () => done(null));
  }
  function readPrefs() {
    wb.layout2 = normLayout((() => { try { return JSON.parse(prefGet(LAYOUT_KEY) || "null"); } catch (e) { return null; } })());
    wb.everPicked = prefGet("wb.fs.picked") === "1";
    const n = prefGet("wb.insp.opens");
    wb.inspOpens = n === undefined ? 99 : Number(n) || 0;
    setInspW(Number(prefGet(INSP_W)) || null);
  }
  /** The width the viewer dragged the inspector to (px; null: the default), for every tab: a
   *  property on the page, which style.css holds to what each flowsheet card fits (--insp-now). */
  const INSP_W = "wb.insp.w";
  function setInspW(w) {
    const st = document.documentElement.style;
    if (w > 0) st.setProperty("--insp-w", `${Math.round(w)}px`); else st.removeProperty("--insp-w");
  }

  // wb.layout2: the program column's share of the width (left), whether it folds to a strip
  // (prog: "auto", "open" or "closed"; app-layout.js, setProg), the dock's share of the
  // right column (dock) and its mode: "split" under the flowsheet, "max" over it, "min" one
  // row. layout() holds each to a pixel floor, so saved values can never squeeze a part out.
  // The old px-based "wb.layout" key is ignored; a column folded to its narrowest the old way
  // (left 0, leftSaved) opens at the share it had.
  const LAYOUT_KEY = "wb.layout2";
  function normLayout(o) {
    const p = o && typeof o === "object" ? o : {};
    const frac = (v, d) => (typeof v === "number" && v >= 0 && v <= 1 ? v : d);
    p.left = frac(p.left, 0.45);
    if (p.left === 0 && typeof p.leftSaved === "number" && p.leftSaved > 0 && p.leftSaved <= 1) p.left = p.leftSaved;   // (folded the old way)
    delete p.leftSaved;
    if (!["auto", "open", "closed"].includes(p.prog)) p.prog = "auto";
    p.dock = frac(p.dock, 0.42);
    if (!["split", "max", "min"].includes(p.dockMode)) p.dockMode = "split";
    p.values = !!p.values;
    return p;
  }
  wb.layout2 = normLayout((() => { try { return JSON.parse(prefGet(LAYOUT_KEY) || "null"); } catch (e) { return null; } })());
  setInspW(Number(prefGet(INSP_W)) || null);
  const prefs = () => (wb.layout2 = normLayout(wb.layout2));
  const savePrefs = () => prefSet(LAYOUT_KEY, JSON.stringify(prefs()));

  wb.post = function (ev) {
    if (window.pywebview && window.pywebview.api) return window.pywebview.api.post(ev);
    console.debug("post (no bridge)", ev);
    return Promise.resolve(false);
  };

  const tabOf = (id) => ((wb.state && wb.state.tabs) || []).find((x) => x.id === id);
  const shownTab = () => wb.pane && tabOf(wb.pane.tabId);
  const busy = (tab) => tab && tab.run && (tab.run.status === "running" || tab.run.status === "queued");
  /** The sessions open in Aspen now. */
  const openSet = () => (wb.state && Array.isArray(wb.state.open_sessions) ? new Set(wb.state.open_sessions) : null);
  const isOpen = (tab) => { const o = openSet(); return !o || o.has(tab.session); };

  // ------------------------------------------------------------------ one tab per model
  // tabs[] is flat: a model tab (kind "model", the model's own program, "My program") and its sub-tabs
  // (kind "program" | "proposal", parent: the model tab's id).
  const isPropTab = (x) => !!x && x.kind === "proposal";
  /** A sub-tab's model tab, or null (a model tab, or a tab with none). */
  function parentOf(tab) {
    if (!tab || tab.kind === "model") return null;
    const p = tab.parent ? tabOf(tab.parent) : null;
    return p && p.id !== tab.id && !p.parent ? p : null;
  }
  const rootOf = (tab) => (tab ? parentOf(tab) || tab : null);
  /** A model tab's sub-tabs, in tabs[] order. */
  const kidsOf = (root) => (root ? ((wb.state && wb.state.tabs) || []).filter((x) => x.id !== root.id && (parentOf(x) || {}).id === root.id) : []);
  /** A tab's model tab and every sub-tab of it: one chat, one model. */
  const familyOf = (tab) => { const r = rootOf(tab); return r ? [r, ...kidsOf(r)] : []; };

  /** Where the AI's proposal is now (its id pid, or its tab id tid): {state: "loaded", tab, title}
   *  while a tab holds it; {state: "hist", tab, title} kept in a model's History (state.history,
   *  prop_open brings it back); {state: "gone", title} when its record was deleted --
   *  named in ``dead`` (ids of the change log's deletions), or known nowhere --; null for neither. */
  function propWhere(pid, tid, dead) {
    const tabs = (wb.state && wb.state.tabs) || [];
    const isP = (x) => isPropTab(x) && !!x.proposal && typeof x.proposal === "object";
    const x = (pid && tabs.find((y) => isP(y) && y.proposal.id === pid)) || (tid && tabs.find((y) => isP(y) && y.id === tid));
    if (x) return { state: "loaded", tab: x.id, title: x.proposal.title || x.title || "" };
    if (!pid && !tid) return null;
    if (dead && ((pid && dead.has(pid)) || (tid && dead.has(tid)))) return { state: "gone", title: "" };
    const hist = (wb.state && wb.state.history) || {};
    for (const rows of Object.values(hist)) {
      const e = (Array.isArray(rows) ? rows : []).find((r) => r && r.tab && ((pid && r.pid === pid) || (tid && r.tab === tid)));
      if (e) return { state: "hist", tab: e.tab, title: e.title || "" };
    }
    return { state: "gone", title: "" };
  }

  /** Point the block definitions at a tab's session: its flowsheet, components, units. */
  function useSession(tab) {
    const sess = sessOf(tab);
    WB.data.catalog = wb.state.catalog || WB.data.catalog;
    WB.data.flowsheet = sess.flowsheet || { blocks: [], streams: [], components: [] };
    const cache = (wb.units[tab.session] = wb.units[tab.session] || {});
    Object.assign(cache, sess.units || {});
    WB.data.units = cache;
  }

  /** Run the function once in the next animation frame, however often this is called. */
  const soonIds = {};
  function soon(key, fn) {
    if (soonIds[key]) return;
    soonIds[key] = requestAnimationFrame(() => { soonIds[key] = 0; fn(); });
  }

  // ------------------------------------------------------------------ faults
  // One part of an update that throws (a panel's drawing, a tab's sync) must not take the rest of
  // the update with it, nor the next one: guard(where, fn) runs fn and keeps its error. Each
  // distinct error goes to the console once and waits for window.py, which takes them after every
  // update it hands the page (wb.takeFaults) and writes them to window.log. faults() counts them
  // all, repeats too (app-state.js: an update that failed, the notice after a few in a row).
  const FAULT = { seen: new Set(), out: [], n: 0 };
  function fault(where, e) {
    FAULT.n++;
    const msg = `${where}: ${(e && e.message) || e}`;
    if (FAULT.seen.has(msg) || FAULT.seen.size >= 100) return;
    FAULT.seen.add(msg);
    console.error(`[workbench] ${msg}`, e);
    const at = e && e.stack ? String(e.stack).split("\n").slice(1, 4).map((x) => x.trim()).join(" < ") : "";
    if (FAULT.out.length < 20) FAULT.out.push(at ? `${msg} (${at})` : msg);
  }
  function guard(where, fn) {
    try { fn(); return true; } catch (e) { fault(where, e); return false; }
  }
  const faults = () => FAULT.n;
  wb.takeFaults = () => (FAULT.out.length ? FAULT.out.splice(0) : null);

  /** Whether a scrolled list shows its end; and how far down its content reaches. */
  function atEnd(list) { return list.scrollHeight - list.scrollTop - list.clientHeight < 4; }
  function contentBottom(list) {
    const last = list.lastElementChild;
    return last ? last.getBoundingClientRect().bottom - list.getBoundingClientRect().top + list.scrollTop : 0;
  }

  // ------------------------------------------------------------------ the status capsule
  function changed(pane, key, value) {
    const sig = JSON.stringify(value);
    if (pane.sigs[key] === sig) return false;
    pane.sigs[key] = sig;
    return true;
  }
  /** Fade the list's top or bottom where more lies. */
  function listFades(box) {
    box.classList.toggle("ft", box.scrollTop > 1);
    box.classList.toggle("fb", box.scrollTop + box.clientHeight < box.scrollHeight - 1);
  }

  // ------------------------------------------------------------------ inspector
  // a stream or block by its name; what else an Ask AI request can be about by what
  // finds it: a change record's or group's id, a field's path, a program step's id
  const keyOf = (tg) => (!tg ? "" : !tg.kind || tg.kind === "block" || tg.kind === "stream" ? `${tg.kind}:${tg.name}`
    : `${tg.kind}:${tg.id || tg.path || tg.sid || tg.name || ""}`);

  Object.assign(WBA, { $, atEnd, busy, canon, changed, contentBottom, dressIcons, familyOf, faults, flushPrefs, guard,
    INSP_W, isOpen, keyOf, kidsOf, listFades, loadPrefs, normLayout, openSet, parentOf, prefGet, propWhere, prefs, prefSet, rootOf, setInspW,
    savePrefs, sentences, setIcon, shownTab, soon, tabOf, useSession, wb });
})();
