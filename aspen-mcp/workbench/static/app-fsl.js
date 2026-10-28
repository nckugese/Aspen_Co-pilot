/* The flowsheet's arrangement: automatic, Aspen's (read from Aspen on request) or moved by
 * hand; kept per session and posted as fs_layout, with this window's undo/redo (fslStep);
 * the Aspen layout toggle, a drop (fslDrop), the echoes and answers in each state (fslSync).
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { isOpen, prefGet, prefSet, renderPane, shownTab, t, tabOf, toast, wb } = WBA;

  // ------------------------------------------------------------------ flowsheet arrangement
  // The flowsheet can be drawn as Aspen draws it (Aspen layout: the server reads the drawing from
  // Aspen on request, into the session's aspen_layout), and its blocks, feeds, products and
  // bends moved by hand; Aspen's own drawing is written only by Redraw and Apply arrangement to Aspen (app-replay.js). The arrangement is the
  // session's: every tab on it shows it (each keeps its own view), and the server keeps it as
  // this window sends it (fs_layout, echoed with its id). Its undo history is this window's,
  // per session, in memory (50 steps): a step is a drop, a switch, an import that switched,
  // an undo or a redo.
  // by session: past, future (whole arrangements); local: the one sent and not yet echoed;
  // sent: the ids sent; req: an Aspen layout asked for and not yet answered ({req, tab,
  // session, at}); imp: the last import seen ({at, sig, obj}); frozen: this state's picture of
  // the import it replaced (F.5); srv, seen: the server's arrangement id last seen; model: the
  // flowsheet's model id last seen (the steps are that model's)
  wb.fsl = new Map();
  // what Ctrl+Z / Ctrl+Y undo: "fs" right after a flowsheet step the user took, "blocks" after a
  // hand edit in the blocks, a press there, or a switch of tabs
  wb.undoScope = "blocks";
  function fslOf(s) {
    let f = wb.fsl.get(s);
    if (!f) wb.fsl.set(s, (f = { past: [], future: [], local: null, sent: new Set(), req: null, imp: null, frozen: null, srv: null, seen: false, timer: 0, model: null }));
    return f;
  }
  const B36 = "0123456789abcdefghijklmnopqrstuvwxyz";
  const newId = (p) => p + Array.from({ length: 8 }, () => B36[Math.floor(Math.random() * 36)]).join("");
  const sessNamed = (s) => (wb.state && wb.state.sessions && wb.state.sessions[s]) || {};
  const modelOf = (s) => (sessNamed(s).flowsheet || {}).model || null;
  const sameModel = (a, b) => !a || !b || a === b;
  /** The session's arrangement: this window's copy until the server echoes it, else the
   *  server's; automatic when there is none or it belongs to another model. */
  function current(s) {
    const lay = fslOf(s).local || sessNamed(s).fs_layout;
    if (!lay || typeof lay !== "object" || !["auto", "aspen", "custom"].includes(lay.mode) || !sameModel(lay.model, modelOf(s))) return { v: 1, mode: "auto" };
    return lay;
  }
  /** The last layout read from Aspen, where it fits the model and places a block; else null. */
  function usableImport(s) {
    const imp = sessNamed(s).aspen_layout;
    if (!imp || typeof imp !== "object" || !imp.blocks || typeof imp.blocks !== "object" || !Object.keys(imp.blocks).length) return null;
    return sameModel(imp.model, modelOf(s)) ? imp : null;
  }
  /** Where the arrangement drawn comes from: Aspen's (moved or not), else the automatic one. */
  const famOf = (lay, imp) => ((lay.mode === "aspen" && imp) || (lay.mode === "custom" && lay.base === "aspen") ? "aspen" : "auto");
  /** What is drawn: "custom", "aspen" (with a usable import), else "auto". */
  const drawnMode = (lay, imp) => (lay.mode === "custom" ? "custom" : lay.mode === "aspen" && imp ? "aspen" : "auto");
  const canRead = (tab) => wb.connected && isOpen(tab);
  const r1 = (v) => Math.round(v * 10) / 10;
  const okNum = (v) => typeof v === "number" && Number.isFinite(v);
  /** An arrangement as it is kept and sent: numbers at 0.1, only its own fields. */
  function cleanLayout(lay) {
    const o = { v: 1, id: null, mode: lay.mode, model: null };
    if (lay.mode !== "custom") return o;
    o.base = lay.base === "aspen" ? "aspen" : "auto";
    o.nodes = {};
    Object.entries(lay.nodes || {}).forEach(([k, p]) => { if (Array.isArray(p) && okNum(p[0]) && okNum(p[1])) o.nodes[k] = [r1(p[0]), r1(p[1])]; });
    o.streams = {};
    Object.entries(lay.streams || {}).forEach(([k, g]) => {
      if (!g || !Array.isArray(g.n) || !Array.isArray(g.c)) return;
      const end = (e) => (Array.isArray(e) ? [e[0], r1(e[1])] : null);
      o.streams[k] = { n: g.n.slice(0, 2), a: end(g.a), b: end(g.b), h: g.h ? 1 : 0, c: g.c.map(r1) };
    });
    return o;
  }
  /** The tab an arrangement is posted with: the one asked for while it is on the session, else
   *  the shown tab when it is, else any tab on it; null when none is. */
  function tabFor(s, preferred) {
    const tabs = (wb.state && wb.state.tabs) || [], p = tabs.find((x) => x.id === preferred), shown = shownTab();
    if (p && p.session === s) return p.id;
    if (shown && shown.session === s) return shown.id;
    const any = tabs.find((x) => x.session === s);
    return any ? any.id : null;
  }
  /** Draw the session's panes again (a step, an answer, the toggle's state). */
  function renderFsl(s) {
    const tab = shownTab();
    if (wb.pane && tab && tab.session === s) renderPane(wb.pane);
  }
  /** Make lay the session's arrangement: kept here at once, and posted to the server. quiet: a
   *  state is being applied, and draws everything next. */
  function sendLayout(s, lay, tabId, quiet) {
    const f = fslOf(s), o = cleanLayout(lay), tab = tabFor(s, tabId);
    o.id = newId("L");
    o.model = modelOf(s);
    f.local = o;
    f.sent.add(o.id);
    if (tab) wb.post({ type: "fs_layout", tab, layout: o });
    if (!quiet) renderFsl(s);
  }
  /** A step the user took: what showed goes on the undo stack (pushed: another picture of it,
   *  F.5), redo is cleared, and an Aspen layout still asked for is let go (its answer ignored). */
  function commitLayout(s, next, tabId, pushed, quiet) {
    const f = fslOf(s);
    f.past.push(cleanLayout(pushed || current(s)));
    if (f.past.length > 50) f.past.splice(0, f.past.length - 50);
    f.future = [];
    f.req = null;
    sendLayout(s, next, tabId, quiet);
  }
  /** Undo (back) or redo on the session's arrangement; false when there is no step that way. */
  function fslStep(s, back) {
    const f = fslOf(s), from = back ? f.past : f.future, to = back ? f.future : f.past;
    if (!from.length) return false;
    to.push(cleanLayout(current(s)));
    const next = from.pop();
    f.req = null;
    sendLayout(s, next, (shownTab() || {}).id);
    return true;
  }
  /** When a layout was read from Aspen, as the tooltips and toasts say it: the time, and the
   *  date too when it was not today. */
  function readTime(at) {
    if (!okNum(at)) return "?";
    const d = new Date(at * 1000), lang = wb.lang === "zh" ? "zh-TW" : "en";
    const time = d.toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit" });
    return d.toDateString() === new Date().toDateString() ? time : `${d.toLocaleDateString(lang)} ${time}`;
  }
  /** A toast about a session, while the shown tab is on it. */
  function sayFor(s, text, ms) {
    const tab = shownTab();
    if (tab && tab.session === s) toast(text, ms || (text.length > 80 ? 7000 : 3500));
  }
  /** Ask the server to read the tab's layout from Aspen now (the toggle, the model menu). The
   *  toggle reads "Reading…" on every tab of the session until the answer, or 20 s. */
  function fslRequest(tab) {
    const s = tab.session, f = fslOf(s), req = newId("r");
    f.req = { req, tab: tab.id, session: s, at: Date.now() };
    wb.post({ type: "aspen_layout", tab: tab.id, req });
    clearTimeout(f.timer);
    f.timer = setTimeout(() => {
      if (!f.req || f.req.req !== req) return;
      const r = f.req;
      f.req = null;
      if (!fslStale(s, r, "fsl_stale", "")) sayFor(s, t("fsl_timeout"));
      renderFsl(s);
    }, 20000);
    renderFsl(s);
  }
  /** Aspen could not be read: the last layout read from it, if there is one for this model
   *  (switched to, no step when it shows already), and a toast that says so; false if none. */
  function fslStale(s, r, key, err, quiet) {
    const imp = usableImport(s);
    if (!imp) return false;
    if (current(s).mode !== "aspen") commitLayout(s, { v: 1, mode: "aspen" }, r.tab, null, quiet);
    sayFor(s, key === "fsl_failed_stale" ? t(key, err, readTime(imp.at)) : t(key, readTime(imp.at)));
    return true;
  }
  /** FNV-1a over an import's drawing: whether a new import brings a new picture. */
  function sigOf(imp) {
    const str = JSON.stringify([imp.blocks, imp.streams]);
    let h = 0x811c9dc5;
    for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
    return h;
  }
  /** A new state: per session, the echo of what this window sent (F.3); a new import freezes
   *  the steps that showed the old one into that picture (F.5); then the answer to a layout
   *  asked for (F.4). Before anything is drawn. */
  function fslSync(st) {
    Object.entries(st.sessions || {}).forEach(([s, sess]) => {
      const f = fslOf(s), srv = (sess.fs_layout && sess.fs_layout.id) || null, model = (sess.flowsheet && sess.flowsheet.model) || null;
      // another model on the session (opened from another copy of the file): the steps kept,
      // and a layout asked of the old one, no longer apply (a step would bring the old model's
      // arrangement back under the new id)
      if (f.model && model && model !== f.model) {
        f.past = [];
        f.future = [];
        f.req = null;
        clearTimeout(f.timer);
      }
      if (model) f.model = model;
      if (f.local && srv === f.local.id) f.local = null;
      // another hand changed it (the server let a session's arrangement go on its start): the
      // steps kept here no longer lead to it
      if (f.seen && srv !== f.srv && !(f.local && srv === f.local.id) && !f.sent.has(srv)) { f.past = []; f.future = []; }
      f.srv = srv;
      f.seen = true;
      const imp = usableImport(s), had = !!f.imp;   // (had: an import was drawn before this state)
      f.frozen = null;
      if (imp && f.imp && imp.at !== f.imp.at) {
        const sig = sigOf(imp);
        if (sig !== f.imp.sig && sess.flowsheet && sess.flowsheet.blocks) {
          const lay = FS.explicitFromAspen(f.imp.obj, sess.flowsheet, prefGet("wb.fs.view") === "boxes" ? "boxes" : "icons");
          f.frozen = cleanLayout({ v: 1, mode: "custom", base: "aspen", nodes: lay.nodes, streams: lay.streams });
          const freeze = (list) => list.forEach((x, i) => { if (x.mode === "aspen") list[i] = cleanLayout(f.frozen); });
          freeze(f.past);
          freeze(f.future);
        }
        f.imp = { at: imp.at, sig, obj: imp };
      } else if (imp && !f.imp) f.imp = { at: imp.at, sig: sigOf(imp), obj: imp };
      else if (!imp) f.imp = null;
      const r = f.req, ans = sess.aspen_layout_req;
      if (!r || !ans || ans.req !== r.req) return;
      f.req = null;
      clearTimeout(f.timer);
      const cur = current(s);
      if (ans.status === "ok") {
        // (an aspen arrangement with no import to draw showed the automatic layout: that is the step)
        if (cur.mode !== "aspen" || !had) commitLayout(s, { v: 1, mode: "aspen" }, r.tab, cur.mode === "aspen" ? { v: 1, mode: "auto" } : null, true);
        else if (f.frozen) commitLayout(s, { v: 1, mode: "aspen" }, r.tab, f.frozen, true);   // the picture before the re-read
        const miss = (sess.aspen_layout && Array.isArray(sess.aspen_layout.missing) && sess.aspen_layout.missing) || [];
        if (miss.length) sayFor(s, miss.length === 1 ? t("fsl_missing_1") : t("fsl_missing", miss.length), 6000);
      } else if (ans.status === "closed" || ans.status === "failed") {
        const failed = ans.status === "failed", err = String(ans.error || "").slice(0, 160);
        if (!fslStale(s, r, failed ? "fsl_failed_stale" : "fsl_stale", err, true)) sayFor(s, failed ? t("fsl_failed", err) : t("why_closed", s));
      } else if (ans.status === "no_graphics") sayFor(s, t("fsl_no_graphics"), 9000);
      else if (ans.status === "stacked") sayFor(s, t("fsl_stacked"), 9000);
    });
  }
  /** The capsule's Aspen layout toggle: on, back to the automatic layout; off, read Aspen's
   *  drawing now, or (Aspen out of reach) the last one read from it. */
  function fslToggle(tab) {
    const s = tab.session, cur = current(s), imp = usableImport(s);
    if (fslOf(s).req) return;
    wb.undoScope = "fs";
    if (famOf(cur, imp) === "aspen") {
      commitLayout(s, { v: 1, mode: "auto" }, tab.id);
      if (cur.mode === "custom") sayFor(s, t("fsl_left"));
      return;
    }
    if (canRead(tab)) fslRequest(tab);
    else if (imp) { commitLayout(s, { v: 1, mode: "aspen" }, tab.id); sayFor(s, t("fsl_stale", readTime(imp.at))); }
  }
  /** A drop on the flowsheet: the arrangement with the move in it becomes the session's. ctx:
   *  the view context it was made in; a drop from another tab's is refused (a tab that changed
   *  under a drag lets it go first: FS.use, release). */
  function fslDrop(pane, obj, ctx) {
    const tab = tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id);
    if (!tab || !rec || (ctx && ctx !== rec.fs)) return;
    wb.undoScope = "fs";
    if (prefGet("wb.fs.moved") !== "1") prefSet("wb.fs.moved", "1");   // the move hint has done its work
    commitLayout(tab.session, obj, tab.id);
  }
  /** The capsule's ⋯ while Aspen's drawing is read: busy (the accent, a faint fill), its tooltip
   *  saying so; the flowsheet's menu holds the arrangement (fslItems). */
  function renderFslTools(pane, tab) {
    const b = pane.q('.fs-tools [data-a="fs_menu"]'), reading = !!fslOf(tab.session).req;
    if (!b) return;
    b.classList.toggle("busy", reading);
    const tip = reading ? `${t("tip_fsl_reading")}\n${t("tip_fs_menu")}` : t("tip_fs_menu");
    if (b.title !== tip) b.title = tip;
  }
  /** The flowsheet menu's arrangement ("Layout"): the automatic layout or Aspen's, the one drawn
   *  ticked (moved by hand or not); Aspen's when it is drawn already reads it again (what was
   *  moved in Aspen), and where Aspen is out of reach takes the last one read; then this window's
   *  undo and redo of the arrangement (Ctrl+Z / Ctrl+Y right after a step on the flowsheet). */
  function fslItems(pane, tab) {
    const s = tab.session, f = fslOf(s), cur = current(s), imp = usableImport(s), fam = famOf(cur, imp), moving = FS.dragging(pane.svg);
    const reading = !!f.req, read = canRead(tab);
    let tip, off = false;
    if (reading) { tip = t("tip_fsl_reading"); off = true; }
    else if (fam === "aspen") {
      tip = t(cur.mode === "custom" ? "tip_fsl_aspen_moved" : "tip_fsl_aspen_on", readTime(imp ? imp.at : cur.at));
      if (read) tip += `\n${t("tip_fsl_reread")}`;
      else off = true;
    } else if (read) tip = t("tip_fsl_aspen_off");
    else if (imp) tip = `${t("tip_fsl_aspen_off")}\n${t("fsl_stale", readTime(imp.at))}`;
    else { tip = wb.connected ? t("why_closed", s) : t("why_off"); off = true; }
    const step = (back) => () => { wb.undoScope = "fs"; fslStep(s, back); };
    return [
      { title: t("lbl_fsl") },
      // (the one drawn is ticked, not greyed: pressed again it does nothing; moved by hand, it lays the drawing out anew)
      { label: t("m_fsl_auto"), icon: "layout", check: fam === "auto", tip: t("tip_fsl_auto"),
        run: () => {
          if (drawnMode(current(s), usableImport(s)) === "auto") return;
          wb.undoScope = "fs";
          commitLayout(s, { v: 1, mode: "auto" }, tab.id);
          if (cur.mode === "custom") sayFor(s, t("fsl_left"));
        } },
      { label: reading ? t("reading") : t("m_fsl_aspen"), icon: "aspen", check: fam === "aspen", disabled: off, tip,
        run: () => { if (fam === "aspen") { wb.undoScope = "fs"; fslRequest(tab); } else fslToggle(tab); } },
      { label: t("m_fsl_undo"), icon: "undo", keys: "Ctrl+Z", disabled: moving || !f.past.length, tip: t(f.past.length ? "tip_fsl_undo" : "tip_fsl_undo_none"), run: step(true) },
      { label: t("m_fsl_redo"), icon: "redo", keys: "Ctrl+Y", disabled: moving || !f.future.length, tip: t(f.future.length ? "tip_fsl_redo" : "tip_fsl_redo_none"), run: step(false) },
    ];
  }

  Object.assign(WBA, { commitLayout, current, fslDrop, fslItems, fslStep,
    fslSync, renderFslTools, usableImport });
})();
