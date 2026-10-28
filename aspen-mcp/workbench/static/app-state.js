/* A new state from the server (wb.applyState) and what follows from it: the language,
 * one record per tab (syncTabs: the rec fields are listed there; a program version loaded
 * or held), the tab to show (placeTabs), and renderAll.
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { $, canon, faults, guard, parentOf, shownTab, soon, t, tabOf, useSession, wb } = WBA;
  const { awaitedTab, dressToolbox, frontOf, editing, followInspect, fslSync, keepView, latestThread, layout,
    firstRun, linkFrom, loadDraft, loadProgram, markLoose, markRefs, noteMain, pollProgress, railLens,
    release, renderBlkEmpty, renderConn, renderCursor, renderHeld, renderPane, renderRunbar,
    renderTabs, roomForMain, saveDraft, sendProgram, settle, shadeTools, showIn, threadKey,
    replaySync, subSync, undoSync, versionText } = WBA.later;

  // ------------------------------------------------------------------ state from the server
  wb.applyState = function (s) {
    const wait = wb.prefsWait;                   // the prefs file first (loadPrefs)
    if (wait) { if (s && (!wait.s || s.rev > wait.s.rev)) wait.s = s; return; }
    if (!s || s.rev <= wb.rev) return;
    wb.rev = s.rev;
    wb.state = s;
    // each part on its own (guard): one that throws is logged and the rest still runs, so the page
    // never stays on an old state (a throw here once ended window.py's watcher)
    const n0 = faults();
    if (s.lang !== wb.lang) guard("setLang", () => setLang(s.lang || "en"));
    guard("syncTabs", () => syncTabs(s));
    guard("placeTabs", () => placeTabs(s));
    guard("settle", () => settle());
    guard("awaitedTab", () => awaitedTab(s));
    guard("subSync", () => subSync(s));          // a proposal opened from History, shown once loaded (app-subtabs.js)
    guard("openModel", () => wb.openModelSeen && wb.openModelSeen(s));   // Open Aspen model answered (app-tabs.js)
    guard("fslSync", () => fslSync(s));          // the flowsheet's arrangement: echoes, imports, answers
    if (WBA.pvSync) guard("pvSync", () => WBA.pvSync(s));   // a previewed proposal applied: its new blocks kept where shown
    renderAll();
    guard("pollProgress", () => pollProgress());
    guard("firstRun", () => firstRun());         // the beginner tour, or a line for an older viewer (app-tour.js)
    // (counted once what wraps this has run too: learn.js)
    queueMicrotask(() => { stale.n = faults() > n0 ? stale.n + 1 : 0; renderStale(); });
  };

  /** Updates in a row that failed in some part (stale.n): from STALE_N on, a quiet line in the
   *  header says the page may not show the server's state, its button reloads the page (which
   *  reads the state again); the next update that goes through takes it away. */
  const STALE_N = 3, stale = { n: 0 };
  function renderStale() {
    const el = $("ui-stale");
    if (!el) return;
    const on = stale.n >= STALE_N;
    el.classList.toggle("hidden", !on);
    if (!on) return;
    el.title = t("tip_ui_stale");
    el.querySelector(".us-t").textContent = t("ui_stale");
    el.querySelector("button").textContent = t("ui_reload");
    if (!el.dataset.wired) {
      el.dataset.wired = "1";
      el.querySelector("button").addEventListener("click", () => location.reload());
    }
  }

  function setLang(lang) {
    const first = wb.lang === null;
    wb.lang = lang;
    I18N.setLang(lang);
    if (wb.pane) { I18N.apply(wb.pane.el); wb.pane.sigs = {}; }
    if (first) return;
    wb.recs.forEach((rec) => {
      const tab = tabOf(rec.id);
      if (tab) useSession(tab);
      Blockly.Events.disable();
      let view;
      try { view = WB.relabel(rec.ws); } finally { Blockly.Events.enable(); }
      keepView(rec, view);
      dressToolbox(rec.ws);
      markLoose(rec);                            // the blocks were made again
      markRefs(rec);
      noteMain(rec);
    });
    if (shownTab()) useSession(shownTab());
    if (wb.pane && wb.pane.tabId) {
      railLens(wb.pane);                         // the list was rebuilt
      renderHeld(wb.recs.get(wb.pane.tabId));
    }
    layout();                                    // the category list's width follows its labels
  }

  /** Create workspaces for new tabs, drop closed ones, load programs that changed. */
  function syncTabs(s) {
    const ids = new Set(s.tabs.map((x) => x.id));
    wb.recs.forEach((rec, id) => {
      if (ids.has(id)) return;
      guard("closeTab", () => { rec.ws.dispose(); rec.el.remove(); });
      wb.recs.delete(id);
      rec.draft = "";
      saveDraft(rec);                            // a closed tab's draft goes with it
    });
    s.tabs.forEach((tab) => guard("syncTab", () => {     // (one tab that fails leaves the others in step)
      let rec = wb.recs.get(tab.id);
      const born = !rec;
      if (!rec) {
        WB.data.catalog = s.catalog || WB.data.catalog;   // (its toolbox follows the server's features: WB.toolbox)
        const el = document.createElement("div");
        el.className = "ws";
        $("ws-store").appendChild(el);
        // pending: a Run, Check or Stop this window sent and the server has not answered yet;
        // late: one that went unanswered for 5 s, which the server may still carry out;
        // mine: the run going now (or just ended) was started here; savedVer: the version last
        // saved to or opened from a .awb file (markSaved: take the next one loaded as that).
        // The composer's part (see chipOf): draft, pin, frozen, pickAt, closed, thread; outbox:
        // requests sent and not yet in state, claimed: the notes that took their place; seen:
        // the chat items drawn; aiSeen, unread: the AI's answers seen, and whether one came
        // while the chat was not shown.
        // The blocks' part: timer, an edit waiting to go out (0: none); shown, whether the pane
        // has shown the workspace yet; held, the AI's version (its program_rev) kept off screen
        // while the user was editing; heldBack, when the user's edit went out over it; mainEnd,
        // procAt: the main program's bottom and where each procedure lay, to tell when an edit
        // made the program longer (roomForMain); view, the view a workspace had when its blocks
        // were made anew off screen, put back when it shows (keepView).
        // The inspector's part: insp, what it shows ({target, all}); askAt, asks: when its
        // values were last asked for and how many times since the pick (followInspect).
        // A failed run (see settle, renderRun): errKey, the failure last seen (undefined until
        // the first state: one there already is not announced); warn, the failed block
        // carrying its log line as a warning; toErr, center: show the log's first error line
        // and centre the failed step, once, when the run was started here.
        rec = { id: tab.id, el, ws: WB.init(el), programRev: -1, lastSent: canon([]), timer: 0,
                fs: FS.newContext(), insp: null, filter: "", pending: null, late: null, mine: false, noReply: 0,
                savedVer: null, markSaved: false, shown: false, held: null, heldBack: 0, mainEnd: 0, procAt: new Map(), view: null,
                askAt: 0, asks: 0,
                draft: loadDraft(tab.id), pin: null, frozen: null, pickAt: 0, closed: null,
                thread: { key: threadKey(latestThread(tab)), at: -1 },   // an answer there already is not offered
                outbox: [], claimed: new Set(), seen: null, aiSeen: null, unread: false,
                errKey: undefined, warn: null, toErr: false, center: null };
        dressToolbox(rec.ws);
        rec.ws.addChangeListener((ev) => {
          const front = !!wb.pane && wb.pane.tabId === rec.id;
          if (ev.type === Blockly.Events.TOOLBOX_ITEM_SELECT) { dressToolbox(rec.ws); shadeTools(rec); }
          // the trash shows while a block is dragged (it is faint the rest of the time)
          if (ev.type === Blockly.Events.BLOCK_DRAG) rec.el.classList.toggle("blk-drag", !!ev.isStart);
          if (ev.type === Blockly.Events.VIEWPORT_CHANGE && front) {
            soon("blkEmpty", () => renderBlkEmpty(wb.pane));
            soon("runCur", () => renderCursor(wb.pane, "view"));
          }
          // a block selected marks what it names on the flowsheet (the selection hub)
          if (ev.type === Blockly.Events.SELECTED && front) linkFrom(wb.pane, rec, ev.newElementId);
          if (ev.isUiEvent) return;
          // a hand edit in the blocks (not the unit menus tidied as data comes): Ctrl+Z is theirs
          if (ev.recordUndo && front && Date.now() > (wb.tidyQuiet || 0)) wb.undoScope = "blocks";
          clearTimeout(rec.timer);
          rec.timer = setTimeout(() => { rec.timer = 0; sendProgram(rec); }, 450);
          soon(`loose:${rec.id}`, () => { markLoose(rec); roomForMain(rec); markRefs(rec); });
          if (front) {
            soon("runbar", renderRunbar);          // steps, or an empty program
            soon("blkEmpty", () => renderBlkEmpty(wb.pane));
            soon("runCur", () => renderCursor(wb.pane, "view"));   // the step may have moved
          }
        });
        wb.recs.set(tab.id, rec);
      }
      if (tab.program_rev !== rec.programRev) {
        const first = rec.programRev === -1;
        rec.programRev = tab.program_rev;
        const echo = tab.program_origin === "user" && versionText(tab.program, tab.loose) === rec.lastSent;
        // (an echo of the user's edit sent over a held AI version: sendProgram let go of it, the
        // AI's version is one step back, where the previous-version button finds it)
        if (echo) {
          if (rec.held) { rec.held = null; rec.heldBack = Date.now(); renderHeld(rec); }
        } else if (!first && tab.program_origin === "llm" && editing(rec)) {
          rec.held = tab.program_rev;              // not from under the user's hands: a pill offers it
          rec.heldBack = 0;
          renderHeld(rec);
        } else {
          if (rec.held) { rec.held = null; renderHeld(rec); }   // a newer version shows: the held one with it
          loadProgram(rec, tab, !first);
        }
      }
      // the inspector the tab had when this window opened on it; later, the user's own picks
      // and closes lead (followInspect)
      if (born && tab.inspect) rec.insp = { target: tab.inspect.target, all: !!tab.inspect.all };
      else followInspect(rec, tab);
    }));
  }

  /** Show the server's active tab; when the shown one closed and the server names none, the
   *  first model tab's sub-tab last shown (its front). */
  function placeTabs(s) {
    const ids = new Set(s.tabs.map((x) => x.id)), p = wb.pane;
    // no tab: the header keeps only what can make one, and a card says what to do (the pane
    // shows again before a tab is placed in it, so it lays out at its real size)
    document.body.dataset.tabs = s.tabs.length ? "some" : "none";
    $("no-tabs").classList.toggle("hidden", s.tabs.length > 0);
    p.el.classList.toggle("hidden", !s.tabs.length);
    if (p.tabId && !ids.has(p.tabId)) release(p);
    const pa = wb.pendingActive;
    if (pa && (Date.now() > pa.until || s.active === pa.id)) wb.pendingActive = null;
    if (!wb.pendingActive && s.active && ids.has(s.active) && s.active !== wb.lastActive) {
      wb.lastActive = s.active;                // the LLM (or our own click, echoed) chose a tab
      showIn(p, s.active);
    }
    if (!p.tabId && s.tabs.length) showIn(p, ids.has(s.active) ? s.active : frontOf(s.tabs.find((x) => !parentOf(x)) || s.tabs[0]).id);
  }

  // ------------------------------------------------------------------ rendering
  /** Every panel drawn again, each on its own (guard): one that throws leaves the others drawn. */
  function renderAll() {
    guard("renderTabs", () => renderTabs());
    guard("renderPane", () => renderPane(wb.pane));
    guard("renderRunbar", () => renderRunbar());
    guard("renderConn", () => renderConn());
    guard("undoSync", () => undoSync());         // an undo, a restore or a restore point answered (app-undo.js)
    guard("replaySync", () => replaySync());     // blocks made of the timeline, Aspen's drawing redrawn (app-replay.js)
    if (window.WBH) guard("help", () => WBH.sync());        // a help card's field read by Aspen, the canvas's 「?」 (help.js)
    if (window.WBPN) guard("principle", () => WBPN.sync());   // a principle card follows its chip, or closes (principle.js)
  }
  // better names for fields came from the server (labels.js): what shows them draws again (the
  // inspector's rows, results, chat and log carry WBL.ver in what they compare; a block's field
  // menu the catalog does not name, its words in place)
  if (window.WBL) WBL.onChange = () => {
    wb.recs.forEach((rec) => WB.paramWords(rec.ws));
    if (wb.state && wb.pane && wb.pane.tabId) renderAll();
  };
})();
