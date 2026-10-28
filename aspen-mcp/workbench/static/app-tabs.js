/* The top tab strip (renderTabs: one tab per model, names cut where they differ, progress
 * underlines), what can be done to a tab (new, rename, close -- a model tab by its own dialogs --,
 * duplicate; its menu, the + menu and the program's menu), and .awb files (saveTab, openAsNewTab,
 * replaceTab). The row of a model's sub-tabs (its programs and the AI's proposals) and its History
 * are app-subtabs.js's.
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { $, activate, busy, copyText, dialog, esc, familyOf, glide, icon, isOpen, keepView, kidsOf, modal,
    noteMain, openMenu, openSet, parentOf, propOf, propPill, propWord, rootOf, saveFile, sendProgram, sessOf, showIn, shownTab, sideways, stripView,
    t, tabOf, toast, toggleMenu, useSession, versionText, wb } = WBA;
  const { moreItems } = WBA.later;

  // ------------------------------------------------------------------ tabs
  // A tab shows its title only; the model is in its tooltip ("Program tab · model: …"), and a
  // small colour square tells models apart when the tabs work on more than one (a square, so
  // it is not read as the round status dot; no amber, so not as a warning). Its status dot is
  // hollow while its model is not open in Aspen; a running tab is underlined with its progress.
  const SESS = ["#0891b2", "#64748b", "#2f9e55", "#d0437b", "#6366f1", "#8b5e3c"];

  /** Changed since it was saved to or opened from a .awb file (kept in memory only). */
  function isDirty(tab) {
    const rec = wb.recs.get(tab.id);
    return !!(rec && rec.savedVer) && versionText(WB.workspaceToProgram(rec.ws), WB.looseStacks(rec.ws)) !== rec.savedVer;
  }

  // ------------------------------------------------------------------ one tab per model
  // The strip shows the model tabs only (app-core.js parentOf: a sub-tab's model tab); a model
  // tab carries the sparkle and pill of its most urgent proposal in progress, the underline of
  // whatever of it runs, and a click shows the sub-tab last shown in it (frontOf).
  const allTabs = () => (wb.state && wb.state.tabs) || [];
  /** The proposals' history lane (tools/proposals.py FINISHED): they leave the sub-tab row. */
  const FINISHED = ["applied", "rejected", "withdrawn", "dismissed"];
  const finished = (tab) => { const p = propOf(tab); return !!p && FINISHED.includes(p.status); };
  /** A proposal in its sub-tab row: one in progress, one opened from History (pinned), the one
   *  shown. */
  const inRow = (x, shownId) => !propOf(x) || x.id === shownId || !finished(x) || !!x.pinned;
  /** The sub-tab a model tab shows when it is clicked: the one last shown in it (this window's,
   *  else the server's front), unless that is gone or a finished proposal the user left. */
  function frontOf(root) {
    if (!root) return null;
    const fam = new Set(familyOf(root).map((x) => x.id));
    for (const id of [(wb.fronts || new Map()).get(root.id), root.front]) {
      const f = id && fam.has(id) ? tabOf(id) : null;
      if (f && (f.id === root.id || !propOf(f) || inRow(f, null))) return f;
    }
    return root;
  }
  /** The most urgent proposal in progress of a model (failed, then stepping or running, then to
   *  review, then any other) -- its pill is the model tab's --, or null. */
  const URGENT = { failed: 4, paused: 3, running: 3, open: 2 };
  function leadOf(root) {
    let best = null, rank = -1;
    familyOf(root).forEach((x) => {
      if (!propOf(x) || shut(x) || finished(x)) return;
      const r = URGENT[(propPill(x) || {}).key] || 1;
      if (r > rank) { best = x; rank = r; }
    });
    return best;
  }
  /** A model tab whose session holds another file now (one of the same name opened there):
   *  read-only until closed; the server refuses its runs. */
  function stale(root) {
    const key = String(root.mkey || ""), now = ((sessOf(root).model || {}).id) || "";
    return !!key && !key.startsWith("s:") && !!now && key !== now;
  }

  function renderTabs() {
    WBA.later.renderSubtabs();
    const tabs = allTabs().filter((x) => !parentOf(x));
    const shownTabObj = wb.pane && tabOf(wb.pane.tabId), front = shownTabObj ? rootOf(shownTabObj).id : null, open = openSet();
    const sessions = [...new Set(tabs.map((x) => x.session))].sort(), multi = sessions.length > 1;
    const fams = tabs.map(familyOf), lead = tabs.map(leadOf);
    const run = fams.map((f) => f.find(busy) || null);
    const dirty = fams.map((f) => f.some(isDirty)), words = lead.map((g) => (g ? propWord(g) : ""));
    const old = tabs.map(stale), closing = tabs.map((x) => !!x.closing);
    const sig = JSON.stringify([front, I18N.lang, multi, open && [...open], tabs.map((x, i) => [x.id, x.title, x.session,
      run[i] ? run[i].run.status : x.run.status, dirty[i], words[i], old[i], closing[i], ((sessOf(x).model || {}).file) || ""])]);
    if (wb.tabSig === sig) return;
    wb.tabSig = sig;
    const strip = $("tabs");
    // the tabs are drawn anew around the glide, which stays in place (taken out and put back,
    // it would lose where it was and jump instead of sliding)
    wb.tabGlide = wb.tabGlide || Object.assign(document.createElement("i"), { className: "glide gx" });
    [...strip.children].forEach((el) => { if (el !== wb.tabGlide) el.remove(); });
    if (wb.tabGlide.parentNode !== strip) strip.prepend(wb.tabGlide);
    const titles = tabs.map((x) => x.title);
    strip.insertAdjacentHTML("beforeend", tabs.map((x, i) => {
      // (the pill only where it asks for a look: a tab not shown, waiting for review, running or failed)
      const r = run[i] || x, closed = (!isOpen(x) && !run[i]) || old[i], pw = words[i], p0 = pw && propPill(lead[i]);
      const pill = p0 && x.id !== front && PILLED.includes(p0.key) && !closing[i] ? p0 : null;
      const head = t("model_is", (sessOf(x).model || {}).file || x.session);
      const tip = [head + (old[i] ? ` · ${t("tab_stale")}` : !isOpen(x) && !run[i] ? ` · ${t("tab_closed")}` : ""), x.title,
                   pw ? t("tip_prop_tab_st", pw) : "", dirty[i] ? t("tab_dirty") : "", tabs.length > 1 ? t("tip_tab_keys") : ""].filter(Boolean).join("\n");
      // closing once its run ends (a stop asked): it says so, and "Keep open" takes it back
      const end = closing[i] ? `<span class="tclosing">${esc(t("mclose_wait"))}</span><button class="tkeep flat" data-keep="${esc(x.id)}" tabindex="-1">${esc(t("mclose_keep"))}</button>`
        : `<button class="x" data-close="${esc(x.id)}" title="${esc(t("tab_close"))}" tabindex="-1">${icon("close")}</button>`;
      return `<div class="tabbtn${x.id === front ? " on" : ""}${run[i] ? " busy" : ""}${pw ? " prop" : ""}${closing[i] ? " closing" : ""}" data-tab="${esc(x.id)}" title="${esc(tip)}">`
        + `<span class="dot ${esc(closed ? "closed" : r.run.status || "idle")}"></span>`
        + (pw ? `<svg class="ic tprop" aria-hidden="true"><use href="#i-sparkle"/></svg>` : "") + endsHtml("ttl", x.title, titles)
        + (pill ? `<span class="tpill s-${esc(pill.key)}">${esc(pill.word)}</span>` : "")
        + (dirty[i] ? `<span class="dirty">•</span>` : "")
        + (multi ? `<i class="sess" style="--sc:${SESS[sessions.indexOf(x.session) % SESS.length]}"></i>` : "")
        + end + `<i class="uline"><b></b></i></div>`;
    }).join(""));
    tabs.forEach((x, i) => underline((run[i] || x).id));
    revealTab();
    glide(wb.tabGlide, strip.querySelector(".tabbtn.on"));
  }

  /** The proposal states a tab's pill shows (on a tab not shown): the rest are its tooltip's. */
  const PILLED = ["open", "running", "paused", "failed"];
  /** A long name cut where it tells itself apart from the others. Names that part only near
   *  their end (tabs named after sessions that share a long start: "Plant…- 1 (HI)",
   *  "Plant…(before HI)") keep that end whole, from where they part (the last 8 letters
   *  at least; from a word's start when one is near), and their head gives way to an
   *  ellipsis first; any other keeps its start, cut at its end as usual (tail ""). Returns
   *  [head, tail]. */
  function nameEnds(name, others) {
    const s = String(name || "");
    if (s.length <= 18) return [s, ""];
    let shared = 0;
    others.forEach((o) => {
      o = String(o || "");
      if (o === s) return;
      let i = 0;
      while (i < s.length && i < o.length && s[i] === o[i]) i++;
      shared = Math.max(shared, i);
    });
    if (shared < s.length - 18) return [s, ""];   // they part where the head shows (or it is alone)
    let at = Math.min(shared, s.length - 8);
    const sp = s.lastIndexOf(" ", at);
    if (sp >= 0 && at - sp <= 4) at = sp + 1;
    return [s.slice(0, at), s.slice(at)];
  }
  /** A name in a box of class cls, drawn by nameEnds: a head that shrinks, a tail kept whole. */
  function endsHtml(cls, name, others) {
    const [h, tl] = nameEnds(name, others);
    return `<span class="${cls} ends"><span class="eh">${esc(h)}</span><span class="et">${esc(tl)}</span></span>`;
  }

  /** A running tab's underline (on its model's tab in the strip, and on its sub-tab): its
   *  optimization's progress, or all the way when there is no telling how far it is. */
  function underline(id) {
    const tab = tabOf(id), root = rootOf(tab);
    if (!tab) return;
    const got = wb.prog.get(id), s = got && tab.run.progress && got.file === tab.run.progress.file ? got.s : null;
    const tf = s ? `scaleX(${Math.min(1, (s.eval_count || 0) / Math.max(1, s.total || 1))})` : "";
    const top = $("tabs").querySelector(`.tabbtn[data-tab="${CSS.escape(root.id)}"] .uline b`);
    if (top && (busy(tab) || !familyOf(root).some(busy))) top.style.transform = tf;
    const sub = wb.pane && wb.pane.q(`.subtabs .sub[data-tab="${CSS.escape(id)}"] .uline b`);
    if (sub) sub.style.transform = tf;
  }

  /** Keep the shown tab in view, and fade the edge where more tabs lie. */
  const revealTab = () => stripView($("tabs"), $("tabs").querySelector(".tabbtn.on"));

  // ------------------------------------------------------------------ tabs
  function wireTabs() {
    const strip = $("tabs");
    strip.addEventListener("click", (ev) => {
      const close = ev.target.closest("[data-close]");
      if (close) { closeTab(close.dataset.close); return; }
      const keep = ev.target.closest("[data-keep]");
      if (keep) { wb.post({ type: "tab_close_cancel", tab: keep.dataset.keep }); return; }
      // a model tab: the sub-tab last shown in it
      const btn = ev.target.closest(".tabbtn"), go = btn && frontOf(tabOf(btn.dataset.tab));
      if (!go || rootOf(tabOf(wb.pane.tabId)) === tabOf(btn.dataset.tab)) return;
      showIn(wb.pane, go.id);
      activate(go.id);
    });
    strip.addEventListener("dblclick", (ev) => {
      const btn = ev.target.closest(".tabbtn");
      if (btn && !ev.target.closest("[data-close], [data-keep]")) renameTab(btn.dataset.tab);
    });
    strip.addEventListener("contextmenu", (ev) => {
      const btn = ev.target.closest(".tabbtn"), tab = btn && tabOf(btn.dataset.tab);
      if (!tab) return;
      ev.preventDefault();
      openMenu({ x: ev.clientX, y: ev.clientY }, tabItems(tab));
    });
    sideways(strip);
    $("tab-add").addEventListener("click", (ev) => toggleMenu($("tab-add"), addItems, ev));
    $("btn-more").addEventListener("click", (ev) => toggleMenu($("btn-more"), moreItems, ev));
    $("empty-new").addEventListener("click", (ev) => toggleMenu($("empty-new"), addItems, ev));
    $("empty-copy").addEventListener("click", () => copyText(t("say_open")));
  }

  /** Ctrl+Tab / Ctrl+Shift+Tab: the next or previous model tab (the sub-tab last shown in it); sub:
   *  Ctrl+PgDn / Ctrl+PgUp, the next or previous sub-tab of the row (shown, the column open). False
   *  when there is no other. */
  function cycleTab(step, sub) {
    const pane = wb.pane, row = sub && pane && pane.q(".subtabs");
    if (!pane || (sub && (!row || row.classList.contains("hidden") || pane.q(".pleft").classList.contains("closed")))) return false;
    const ids = sub ? [...row.querySelectorAll(".sub-track .sub[data-tab]")].map((b) => b.dataset.tab)
      : allTabs().filter((x) => !parentOf(x)).map((x) => x.id);
    const at = sub ? (row.querySelector(".sub-track .sub.on") || { dataset: {} }).dataset.tab : (rootOf(tabOf(pane.tabId)) || {}).id;
    if (ids.length < 2) return false;
    const next = ids[(ids.indexOf(at) + step + ids.length) % ids.length], id = sub ? next : frontOf(tabOf(next)).id;
    showIn(pane, id);
    activate(id);
    return true;
  }

  function renameTab(id) {
    const tab = tabOf(id);
    if (!tab) return;
    modal(t("tab_rename"), tab.title, "", (text) => {
      if (text.trim() && text.trim() !== tab.title) wb.post({ type: "tab_rename", tab: tab.id, title: text.trim() });
    }, null, true);
  }

  /** An AI proposal no longer to be run (withdrawn, closed on its card). */
  const shut = (tab) => { const p = propOf(tab); return !!p && ["withdrawn", "dismissed"].includes(p.status); };
  /** Whether a tab holds blocks (as on screen, or as the server keeps them). */
  const hasBlocks = (tab) => { const rec = wb.recs.get(tab.id); return !!((tab.program || []).length || (rec && WB.workspaceToProgram(rec.ws).length)); };
  /** Close a tab, by its kind. A model tab: closeModel. A finished proposal: back to History (one
   *  in progress has no ×: its card closes it -- asked anyway, the server's chat line says so). A
   *  program asks first, with the red button apart from Cancel (which has the focus) and a way to
   *  save it before it goes. */
  function closeTab(id) {
    const tab = tabOf(id);
    if (!tab) return;
    if (!parentOf(tab)) { closeModel(tab); return; }
    if (propOf(tab)) {                          // (one in progress: the server says to close it on its card)
      wb.post(finished(tab) ? { type: "prop_shelve", tab: id } : { type: "tab_close", tab: id });
      return;
    }
    if (busy(tab)) { toast(t("tab_busy_close")); return; }
    const go = () => wb.post({ type: "tab_close", tab: id });
    if (!hasBlocks(tab)) { go(); return; }
    dialog({ title: t("close_title"), body: t("close_body", tab.title), ok: t("close_go"), okClass: "danger-solid",
             onOk: go, focus: "cancel",
             alt: { label: t("close_save"), run: () => saveTab(id).then((path) => { if (path) go(); }) } });
  }
  /** A sub-tab's name as its row shows it: "My program", a program's title, a proposal's title. */
  const subName = (x) => (propOf(x) ? propOf(x).title || x.title : !parentOf(x) ? t("prog_mine") : x.title);
  /** The step a run is at, counted from 1 in its program (paused: the one it waits before; 0: not known). */
  function stepNo(tab) {
    const run = tab.run || {}, want = run.step;
    if (run.paused && typeof run.paused.n === "number") return run.paused.n;
    let n = 0, at = 0;
    const walk = (list) => (list || []).forEach((s) => {
      if (at || !s || typeof s !== "object" || s.do === "def" || s.do === "proc") return;
      n++;
      if (s.id === want) { at = n; return; }
      walk(s.body); walk(s.then); walk(s.else);
    });
    if (want) walk(tab.program);
    return at;
  }
  /** A model tab's ×. Something of it running: stop and close, or cancel -- it then
   *  closes once the step running ends (the tab says so, "Keep open" takes it back). Else, programs
   *  with blocks: they are deleted with it (save them first, or cancel). Its proposals are kept in
   *  History either way, and come back when the file is opened again. */
  function closeModel(root) {
    if (root.closing) return;
    const fam = familyOf(root), runner = fam.find(busy);
    if (runner) {
      const n = stepNo(runner);
      dialog({ title: t(runner.kind === "proposal" ? "mclose_run_title" : "mclose_run_title_prog", root.title), body: t(n ? "mclose_run_body" : "mclose_run_body0", subName(runner), n),
               ok: t("mclose_run_go"), okClass: "danger-solid", focus: "cancel",
               onOk: () => wb.post({ type: "tab_close", tab: root.id, stop: true }) });
      return;
    }
    const progs = fam.filter((x) => x.kind !== "proposal" && hasBlocks(x));
    const kept = fam.filter((x) => x.kind === "proposal").length
      + (((wb.state.history || {})[root.mkey]) || []).filter((e) => !e.loaded).length;
    const go = () => {
      wb.post({ type: "tab_close", tab: root.id });
      toast(kept ? t("mclose_done", root.title, kept) : t("mclose_done0", root.title), 4000);
    };
    if (!progs.length) { go(); return; }
    const saveAll = (i) => (i >= progs.length ? Promise.resolve(true)
      : saveTab(progs[i].id).then((path) => (path ? saveAll(i + 1) : false)));
    dialog({ title: t("mclose_title", root.title), body: t("mclose_body", progs.length), ok: t("mclose_go"), okClass: "danger",
             onOk: go, focus: "cancel", alt: { label: t("mclose_save"), run: () => saveAll(0).then((ok) => { if (ok) go(); }) } });
  }

  /** Ask the server for a new tab on a session (parent: a program sub-tab of that model tab),
   *  then do then(id) once it exists. The server reads the request when it is free, which a run
   *  step or a long tool call can put off for a minute: the request waits as long as it takes (a
   *  note says so after 3 s), in a queue, so a second one made meanwhile does not drop the first. */
  function newTab(session, title, then, parent) {
    const w = { before: new Set(((wb.state && wb.state.tabs) || []).map((x) => x.id)), session,
                title: title || session, then };
    wb.awaitTabs.push(w);
    wb.post(Object.assign({ type: "tab_new", session, title }, parent ? { parent } : {}));
    setTimeout(() => { if (wb.awaitTabs.includes(w)) toast(t("tab_wait")); }, 3000);
  }
  /** "New program": a new program sub-tab in a model tab ("Program 2", ...), shown once it exists. */
  function addProgram(root) {
    if (!root || !wb.connected) return;
    const used = new Set(allTabs().map((x) => x.title));
    let n = kidsOf(root).filter((x) => x.kind !== "proposal").length + 2;
    while (used.has(t("sub_prog_n", n))) n++;
    newTab(root.session, t("sub_prog_n", n), (id) => { if (wb.pane) { showIn(wb.pane, id); activate(id); } }, root.id);
  }
  /** Each new tab that answers a request goes to the oldest request it answers: one on the
   *  request's session and named as asked (the server adds " (2)" to a title in use), made
   *  since the request (not among the tabs there were then), active or not. */
  function awaitedTab(s) {
    const q = wb.awaitTabs;
    [...q].forEach((w) => {
      const tab = s.tabs.find((x) => !w.before.has(x.id) && x.session === w.session
                                      && (x.title === w.title || x.title.startsWith(`${w.title} (`)));
      if (!tab) return;
      q.splice(q.indexOf(w), 1);
      q.forEach((o) => o.before.add(tab.id));    // taken: no other request's
      w.then(tab.id);
    });
  }

  /** A copy of a tab: a program sub-tab of its model tab with its blocks (as on screen) and
   *  results ("My program"'s copy named as a new program). */
  function duplicateTab(id) {
    const tab = tabOf(id), rec = wb.recs.get(id), root = rootOf(tab);
    if (!tab || !rec) return;
    const program = WB.workspaceToProgram(rec.ws), loose = WB.looseStacks(rec.ws), results = tab.results;
    let title = tab.title;
    if (tab === root) {
      const used = new Set(allTabs().map((x) => x.title));
      let n = kidsOf(root).filter((x) => x.kind !== "proposal").length + 2;
      while (used.has(t("sub_prog_n", n))) n++;
      title = t("sub_prog_n", n);
    }
    newTab(tab.session, title, (nid) => {
      wb.post({ type: "program", tab: nid, program, loose });
      if (results) wb.post({ type: "results", tab: nid, results });
      toast(t("dup_done", subName(tab)));
    }, root.id);
  }

  /** What can be done to one tab: its context menu, and "This tab" in the ... menu. A model tab:
   *  rename, "New program", save its program, close. */
  function tabItems(tab) {
    const shown = wb.pane && wb.pane.tabId === tab.id, off = wb.connected ? "" : t("why_off");
    if (!parentOf(tab)) {
      return [
        { label: t("m_rename"), icon: "pen", run: () => renameTab(tab.id) },
        { label: t("sub_add"), icon: "plus", tip: off || t("tip_sub_add"), disabled: !wb.connected, run: () => addProgram(tab) },
        { label: t("m_save_awb"), icon: "save", keys: shown ? "Ctrl+Shift+S" : "", run: () => saveTab(tab.id) },
        { sep: true },
        { label: t("close"), icon: "close", danger: true, run: () => closeTab(tab.id) },
      ];
    }
    return [
      { label: t("m_rename"), icon: "pen", run: () => renameTab(tab.id) },
      { label: t("m_duplicate"), icon: "copy", run: () => duplicateTab(tab.id), disabled: !wb.connected, tip: off },
      { label: t("m_save_awb"), icon: "save", keys: shown ? "Ctrl+Shift+S" : "", run: () => saveTab(tab.id) },
      { label: t("m_replace"), icon: "folder", run: () => replaceTab(tab.id) },
      { sep: true },
      { label: t("close"), icon: "close", danger: true, run: () => closeTab(tab.id) },
    ];
  }

  /** The program's ⋯ menu (its run bar): Fit (the whole program in view; the canvas zooms with
   *  the wheel), its .awb file. (Folding the column away is the run bar's own chevron, at its
   *  left end.) */
  function progItems(tab) {
    const rec = wb.recs.get(tab.id);
    return [
      { label: t("m_bfit"), icon: "fit", keys: "Ctrl+0", tip: t("tip_bfit"), disabled: !rec, run: () => { if (rec) WBA.later.fitProgram(rec); } },
      { sep: true },
      { label: t("m_save_awb"), icon: "save", keys: "Ctrl+Shift+S", run: () => saveTab(tab.id) },
      { label: t("m_replace"), icon: "folder", run: () => replaceTab(tab.id) },
    ];
  }

  /** The + menu: a tab on any session open in Aspen (one already open is ticked, and picking it
   *  shows it), or a .awb file as a new tab (a program sub-tab). With no session open
   *  it says what to tell Claude. */
  function addItems() {
    const names = (wb.state && wb.state.open_sessions) || [];
    const items = [{ title: t("tab_add_on") }];
    const roots = allTabs().filter((x) => !parentOf(x));
    // (sessions that share a long start keep the ends that tell them apart, as the tabs do)
    if (names.length) names.forEach((n) => {
      const there = roots.find((x) => x.session === n);
      items.push({ label: n, others: names, icon: "block", tip: there ? t("tab_focus_exist", there.title) : n,
        ...(there ? { check: true } : {}),
        run: () => {
          if (!there) { wb.post({ type: "tab_new", session: n }); return; }
          const f = frontOf(there);
          if (wb.pane && wb.pane.tabId !== f.id) { showIn(wb.pane, f.id); activate(f.id); }
          toast(t("tab_focus_exist", there.title), 2500);
        } });
    });
    else {
      items.push({ html: `<div class="msay"><span>${esc(t("tab_no_sessions"))}</span><q>${esc(t("say_open"))}</q>`
        + `<button class="mcopy">${icon("copy")}<span class="bt">${esc(t("copy"))}</span></button></div>`,
        wire: (el) => { el.querySelector(".mcopy").onclick = () => copyText(t("say_open")); } });
    }
    items.push({ sep: true }, openModelItem(), openNewItem());
    return items;
  }

  /** Open Aspen model: .bkp files the user picks become sessions of the server that serves the
   *  window (a model a running Aspen has open is taken as it is), each shown in its model's tab.
   *  The server answers in state.open_req; a failure is said in a toast. */
  let openReq = null;
  function openModelItem() {
    const api = window.pywebview && window.pywebview.api;
    const can = !!(wb.connected && api && api.pick_models);
    return { label: t("m_open_model"), icon: "folder", disabled: !can, tip: can ? t("tip_open_model") : t("why_off"),
      run: () => api.pick_models().then((paths) => {
        if (!paths || !paths.length) return;
        openReq = { id: "o" + Date.now().toString(36), n: paths.length, seen: 0 };
        wb.post({ type: "open_model", paths, req: openReq.id });
        toast(t("open_model_wait", paths.length), 6000);
      }) };
  }
  wb.openModelSeen = function (state) {
    const r = state && state.open_req;
    if (!openReq || !r || r.req !== openReq.id) return;
    const done = r.done || [];
    done.slice(openReq.seen).forEach((d) => { if (d.state === "error") toast(t("open_model_failed", d.text || d.path), 9000); });
    openReq.seen = done.length;
    if (openReq.seen >= openReq.n) openReq = null;
  };

  /** Open .awb as a new tab: the new tab is the server's to make, so not while there is none. */
  function openNewItem() {
    return { label: t("m_open_new"), icon: "folder", keys: "Ctrl+O", run: openAsNewTab,
             disabled: !wb.connected, tip: wb.connected ? "" : t("why_off") };
  }

  // ------------------------------------------------------------------ workbench files
  // A .awb file is one tab's work: its program, the loose stacks beside it, and the last
  // results, as JSON. Opening one makes a new tab (on the file's session when it is open,
  // else on the shown tab's); "Replace from .awb" puts it in a tab that exists (one undo
  // step: ↶ brings back what was there).
  const AWB = "aspen-workbench";

  function saveTab(id) {
    const tab = tabOf(id), rec = wb.recs.get(id);
    if (!tab || !rec) return Promise.resolve(null);
    sendProgram(rec);
    const program = WB.workspaceToProgram(rec.ws), loose = WB.looseStacks(rec.ws);
    const doc = { format: AWB, version: 1, saved: new Date().toISOString(), title: tab.title, session: tab.session,
                  program, loose, results: tab.results || null };
    // (a tab made of the timeline, uv_t_redo "Redo: <title>", saves as "<redo>-<title>.awb")
    const base = tab.origin && tab.origin.kind === "journal" ? String(tab.title).replace(/^([^：:]{1,12})[：:]\s*/, "$1-") : tab.title;
    return saveFile(`${base}.awb`.replace(/[\\/:*?"<>|]+/g, "_"), JSON.stringify(doc, null, 1), "awb").then((path) => {
      if (path) { rec.savedVer = versionText(program, loose); wb.tabSig = null; renderTabs(); }
      return path;
    });
  }

  /** Ask for a .awb file and read it: {doc, file}, or null (cancelled, or not a workbench file). */
  function readAwb() {
    const api = window.pywebview && window.pywebview.api;
    if (!(api && api.open_file)) return Promise.resolve(null);
    return api.open_file("awb").then((file) => {
      if (!file) return null;
      let doc = null;
      try { doc = JSON.parse(file.text); } catch (e) { doc = null; }
      if (!doc || doc.format !== AWB || !Array.isArray(doc.program)) { toast(t("open_bad", file.name)); return null; }
      return { doc, file };
    }, () => null);
  }

  function openAsNewTab() {
    readAwb().then((got) => {
      if (!got) return;
      const { doc, file } = got, open = openSet(), cur = shownTab(), want = String(doc.session || "");
      let session = want, note = "";
      if (!want || (open && !open.has(want))) {
        session = cur ? cur.session : open && open.size ? [...open][0] : want;
        if (want && session !== want) note = t("awb_fallback", want, session);
      }
      if (!session) { toast(t("tab_no_sessions")); return; }
      newTab(session, String(doc.title || file.name.replace(/\.awb$/i, "")), (id) => {
        const rec = wb.recs.get(id);
        if (rec) rec.markSaved = true;             // the version the server sends back is the file's
        wb.post({ type: "program", tab: id, program: doc.program, loose: Array.isArray(doc.loose) ? doc.loose : [] });
        if (doc.results) wb.post({ type: "results", tab: id, results: doc.results });
        toast(note || t("awb_new", file.name), note ? 5000 : 0);
      });
    });
  }

  function replaceTab(id) {
    readAwb().then((got) => {
      const tab = tabOf(id), rec = wb.recs.get(id);
      if (!got || !tab || !rec) return;
      const { doc, file } = got, cur = shownTab();
      sendProgram(rec);                                    // an edit not sent yet becomes a version of its own
      useSession(tab);
      Blockly.Events.disable();
      let view;
      try { view = WB.loadProgram(rec.ws, doc.program, Array.isArray(doc.loose) ? doc.loose : []); } finally {
        Blockly.Events.enable();
        if (cur && cur.id !== tab.id) useSession(cur);
      }
      keepView(rec, view);
      noteMain(rec);
      sendProgram(rec);                                    // the server keeps it as one version
      rec.savedVer = rec.lastSent;
      if (doc.results) wb.post({ type: "results", tab: tab.id, results: doc.results });
      toast(t("opened", file.name));
    });
  }

  Object.assign(WBA, { addProgram, awaitedTab, closeTab, cycleTab, duplicateTab, endsHtml, finished, frontOf, inRow, newTab, openAsNewTab,
    openNewItem, progItems, renameTab, renderTabs, replaceTab, revealTab, saveTab, tabItems, underline, wireTabs });
})();
