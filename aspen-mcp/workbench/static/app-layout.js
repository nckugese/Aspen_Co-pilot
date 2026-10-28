/* The pane's geometry: the program column (folded to a strip or open: setProg, autoFold) and
 * the flowsheet column, the dock's height and mode (split, max, min) with its animation, the
 * splitters (dragBar), which dock panel shows (showPanel), the results panel
 * (renderResults, csvButton) and the Changes panel (renderChanges: changes.js; what it is told,
 * changesCtx, and its ties to the flowsheet: changesMarks, changesPicked, changesFor; coming
 * back to the window, what the others changed meanwhile: awayLeft, awayBack, changesBack).
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { atEnd, busy, contentBottom, feature, glide, isOpen, listFades, prefGet, prefs, prefSet, savePrefs, sessOf, setIcon,
    shownTab, soon, t, tabOf, toast, toastClose, toggleMenu, wb } = WBA;
  const { activate, askAI, clampCheck, cpMap, dressToolbox, fitHeld, fitText, fsView, gotoChange, gotoNote, grow, heatOf, heatPlans, heatPref, markRead,
    newTab, openEntry, pick, progEmpty, railFade, renderBlkEmpty, renderCursor, renderPlan, restoreOpen, reveal, selOf, shadeTools, showIn,
    toBlocks, toFirstError, undoOpen } = WBA.later;

  // ------------------------------------------------------------------ layout
  // The least each part may get, in px: the program (plus its category list), the
  // flowsheet column, the flowsheet card, the dock; and the collapsed dock's row.
  const FLOOR = { prog: 360, model: 440, fs: 200, dock: 150, row: 48 };
  /** The folded program column's width: the strip. */
  const STRIP = 40;

  // ------------------------------------------------------------------ the program column
  // wb.layout2.prog: "auto" (the default), "open" or "closed". Auto folds a tab with no
  // program (no step, procedure or loose stack) as it shows, and opens one with blocks; the
  // column never folds under the user's hands (a last block deleted leaves it open). A block
  // added from the inspector, a program the AI writes and a run started here open it again
  // (setProg without "user"; a column the user folded goes back to auto). The user's own
  // fold and open (the run bar's chevron, the strip, the splitter's double-click or drag) are
  // kept for that tab (keepProg, below).
  // pane.progShut: whether it is folded now. Folded, the program's card keeps its open size
  // out of sight (the canvas is neither resized nor scrolled), and the strip takes the column.
  // The user's own fold or open is kept per tab (the prefs key wb.prog.<tab id>: "open" or
  // "closed"; forgotten with the tab, app-core.js loadPrefs), so a tab shown again, or the
  // window opened again, has its column as it was left; a tab with no choice of its own goes
  // by wb.layout2.prog.
  const progKey = (id) => `wb.prog.${id}`;
  function autoFold(p) {
    const pr = prefs(), rec = p && wb.recs.get(p.tabId);
    const own = p && p.tabId ? prefGet(progKey(p.tabId)) : null;
    if (own === "open" || own === "closed") return own === "closed";
    return pr.prog === "closed" || (pr.prog === "auto" && !!rec && progEmpty(rec));
  }
  /** Keep the user's own fold (open false) or open of the program column for tab p's tab. */
  function keepProg(p, open) {
    if (p && p.tabId) prefSet(progKey(p.tabId), open ? "open" : "closed");
  }
  /** Open (open true) or fold the program column. how: "user" (the user's own choice, kept for
   *  the tab), else something opened it for the user. Returns whether it moved. */
  function setProg(p, open, how) {
    if (!p) return false;
    const pr = prefs();
    if (how === "user") keepProg(p, open);
    else if (open && p.tabId && prefGet(progKey(p.tabId)) === "closed") prefSet(progKey(p.tabId), null);
    if (open && pr.prog === "closed") pr.prog = "auto";   // (a fold kept for every tab, before)
    savePrefs();
    if (!p.progShut === open) return false;
    p.progShut = !open;
    const rec = wb.recs.get(p.tabId);
    if (!open && rec) {                          // nothing of the canvas stays open over the flowsheet
      const box = rec.ws.getToolbox();
      if (box) box.clearSelection();
      Blockly.WidgetDiv.hide();
      Blockly.DropDownDiv.hideWithoutAnimation();
      if (p.el.contains(document.activeElement)) document.activeElement.blur();
      shadeTools(rec);
    }
    layout();
    settled(p);
    const tab = tabOf(p.tabId), tg = tab && selOf(tab, rec);
    if (tg) reveal(p, tg);                       // what is picked stays in view as the flowsheet's width changes
    return true;
  }

  /** The widths and heights layout() works with, read from the pane as it stands. */
  function measure(p) {
    const body = p.q(".pbody"), cs = getComputedStyle(body);
    const tb = p.q(".blockly .blocklyToolbox");
    return {
      W: body.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - p.q(".vsplit").offsetWidth,
      H: p.q(".pright").clientHeight, gap: p.q(".hsplit").offsetHeight,
      progMin: (tb && tb.offsetWidth ? tb.offsetWidth : 150) + FLOOR.prog,
    };
  }
  /** The program column's width for the measures m: the saved share held to the floors (lw),
   *  and the width asked for before the program's own floor (want); split when the two
   *  floors do not both fit. */
  function colWidth(m, pr) {
    const lo = m.progMin, hi = m.W - FLOOR.model, split = lo > hi;
    const lw = split ? (m.W * lo) / (lo + FLOOR.model) : Math.min(hi, Math.max(lo, pr.left * m.W));
    return { lo, hi, lw, split, want: Math.min(Math.max(0, hi), pr.left * m.W) };
  }

  /** The category list goes narrow in a narrow program column, as in Scratch: each category's
   *  icon over a short label, about 64 px wide, and back when the column widens. It goes by
   *  the width asked for (a drag, the saved share, a small window), not the width the full
   *  list's floor allows, so a column dragged narrower than that floor gets the narrow list
   *  and follows the drag; and a full list with no room beside the flowsheet's floor goes
   *  narrow too, however the window got that small. Under 540 px it goes narrow, and wide
   *  again from 580, so a width near the line does not flip it back and forth (from 580 the
   *  full list has its room, while it is under 220 px). Blockly keeps the list's width for
   *  the blocks' left edge and places the flyout by it: both are told (position(), and
   *  svgResize in layout()). */
  function railMode(p, narrow) {
    const rec = wb.recs.get(p.tabId);
    p.narrow = narrow;
    if (!rec || rec.el.classList.contains("narrow") === narrow) return false;
    rec.el.classList.toggle("narrow", narrow);
    const box = rec.ws.getToolbox();
    if (box) box.position();
    railFade(rec);
    dressToolbox(rec.ws);                        // the open category's drop takes the rows' new size
    return true;
  }

  /** Size the pane from wb.layout2: fractions held to pixel floors. When the window is too
   *  small for two floors, they share what there is in proportion. */
  function layout() {
    const p = wb.pane;
    if (!p) return;
    if (p.dockAnim) p.dockAnim.finish();
    railMode(p, !!p.narrow);                     // a workspace just shown takes the pane's list mode
    const pr = prefs();
    let m = measure(p);
    if (m.W <= 0 || m.H <= 0) return;            // nothing shown
    // the reads before the first write, so they take the layout the last frame left (the first
    // read after the writes lays out: Blockly's measure of its canvas, when the canvas changed
    // size, and the placing of its list once more); a chat or log read to its end stays at
    // its end when the dock changes size
    const list = p.q(".panel .tab.on");
    const stick = list && atEnd(list);
    let { lw, want, split } = colWidth(m, pr);
    if (railMode(p, p.narrow ? want < 580 : split || want < 540)) {   // the list's width moved the floor
      m = measure(p);
      ({ lw } = colWidth(m, pr));
    }
    // folded: the strip takes the column, and the card keeps the width it has open, hidden
    const shut = !!(p.progShut && p.tabId), left = p.q(".pleft");
    left.classList.toggle("closed", shut);
    left.style.width = `${shut ? STRIP : Math.round(lw)}px`;
    p.q(".pl-card").style.width = shut ? `${Math.round(lw)}px` : "";
    const room = m.H - m.gap;
    let dock;
    if (pr.dockMode === "min") dock = FLOOR.row;
    else if (FLOOR.dock + FLOOR.fs > room) dock = (room * FLOOR.dock) / (FLOOR.dock + FLOOR.fs);
    else dock = Math.min(room - FLOOR.fs, Math.max(FLOOR.dock, pr.dock * m.H));
    dock = Math.round(dock);
    const dockKey = pr.dockMode === "max" ? -1 : dock, resized = dockKey !== p.dockKey;
    p.dockKey = dockKey;
    // the flowsheet card keeps its split size under a maximized dock: hidden, not refitted
    p.q(".fs-wrap").style.height = `${room - dock}px`;
    if (p.q(".fs-wrap").classList.toggle("short", room - dock < 380) !== p.planShort) {   // a heat plan card folds or unfolds
      p.planShort = room - dock < 380;
      soon("plan", () => { const tab = tabOf(p.tabId); if (tab) renderPlan(p, tab); });
    }
    p.q(".panel").style.height = pr.dockMode === "max" ? "" : `${dock}px`;
    if (pr.dockMode !== "min") fitText(p, pr.dockMode === "max" ? m.H : dock);   // a short dock keeps Send
    const right = p.q(".pright");
    right.classList.toggle("dock-max", pr.dockMode === "max");
    right.classList.toggle("fs-off", pr.dockMode === "max");
    right.classList.toggle("dock-min", pr.dockMode === "min");
    dockButtons(p);
    const rec = wb.recs.get(p.tabId);
    if (rec) {
      // the canvas's box follows the column's width, the pane's height and the list's width
      // only: a drag of the dock's edge leaves it be (Blockly's measure and the placing of its
      // list would cost two layouts a frame for nothing)
      const box = String([rec.id, Math.round(lw), m.H, m.progMin]);
      if (p.canvasBox !== box) { p.canvasBox = box; Blockly.svgResize(rec.ws); }
      soon("railFade", () => { const r = wb.recs.get(p.tabId); if (r) railFade(r); });   // read in the next frame
      soon("blkEmpty", () => renderBlkEmpty(p));
      soon("runCur", () => renderCursor(p, "view"));
      if (!p.q(".blk-held").classList.contains("hidden")) soon("fitHeld", () => fitHeld(p));
    }
    // the chat or log kept at its end, after Blockly's measure (the layout is fresh then): at
    // once when the dock's height changed; a drag across the columns (only its width changes,
    // its lines rewrap) keeps it for the drop (settled), not every frame
    if (stick && (resized || !document.body.classList.contains("dragging"))) list.scrollTop = list.scrollHeight;
    else if (stick) p.stick = list;
    FS.moved(p.svg);                             // the edge hints, once things rest
  }

  /** Redraw what is drawn at its box's size (the results chart) once sizes settle, and see
   *  again which requests run past five lines at the chat's new width, and how many lines
   *  the draft takes at the text box's. */
  function settled(pane) {
    const tab = tabOf(pane.tabId);
    if (pane.stick) { pane.stick.scrollTop = pane.stick.scrollHeight; pane.stick = null; }
    if (tab) renderResults(pane, tab);
    clampCheck(pane);
    listFades(pane.q(".chat-list"));
    logShown(pane);                              // a collapsed dock that opened on the log
    renderChanges(pane);                         // ... or on the changes
    if (pane.q(".cta").clientWidth !== pane.taW) grow(pane);
  }

  /** A splitter drag (axis "x" or "y"; "ew": an edge, the inspector's). move(dx, dy) gets the
   *  offset from where the drag began and is applied once an animation frame at most; done(moved)
   *  runs on mouseup. A press that stays within 2 px is a click (or half a double-click): move
   *  never runs and nothing is kept. */
  function dragBar(bar, axis, begin, move, done) {
    bar.addEventListener("mousedown", (ev) => {
      if (ev.button !== 0) return;
      ev.preventDefault();
      const x0 = ev.clientX, y0 = ev.clientY;
      let x = x0, y = y0, frame = 0, moved = false;
      begin();
      document.body.classList.add("dragging");
      document.body.classList.toggle("ns", axis === "y");
      document.body.classList.toggle("ew", axis === "ew");
      const flush = () => {
        frame = 0;
        moved = moved || Math.abs(x - x0) > 2 || Math.abs(y - y0) > 2;
        if (moved) move(x - x0, y - y0);
      };
      const mm = (e) => { x = e.clientX; y = e.clientY; if (!frame) frame = requestAnimationFrame(flush); };
      const up = () => {
        if (frame) { cancelAnimationFrame(frame); flush(); }
        document.body.classList.remove("dragging", "ns", "ew");
        window.removeEventListener("mousemove", mm);
        window.removeEventListener("mouseup", up);
        done(moved);
      };
      window.addEventListener("mousemove", mm);
      window.addEventListener("mouseup", up);
    });
  }

  /** The dock's two buttons say what they would do now: maximize or restore, collapse or
   *  expand. */
  function dockButtons(pane) {
    const mode = prefs().dockMode;
    const set = (btn, name, tip) => {
      setIcon(btn, name);
      btn.dataset.i18nTitle = tip;
      btn.title = t(tip);
    };
    set(pane.q('[data-dock="max"]'), mode === "max" ? "restore" : "maximize", mode === "max" ? "tip_dock_restore" : "tip_dock_max");
    set(pane.q('[data-dock="min"]'), mode === "min" ? "chevron-up" : "chevron-down", mode === "min" ? "tip_dock_expand" : "tip_dock_min");
  }

  /** Switch the dock between split, max and min. The layout changes at once; then only the
   *  dock's own box moves (FLIP, transform only). Maximizing slides it up over the flowsheet,
   *  whose box keeps its size and is hidden once covered; restoring slides it back down
   *  with the flowsheet showing again, and it takes its split size when it lands. */
  function setDock(pane, mode) {
    const pr = prefs(), prev = pr.dockMode;
    if (prev === mode) return;
    if (pane.dockAnim) pane.dockAnim.finish();
    const right = pane.q(".pright"), dock = pane.q(".panel");
    const top0 = dock.offsetTop;
    pr.dockMode = mode;
    savePrefs();
    if (mode === "max") {
      layout();
      right.classList.remove("fs-off");        // still showing while the dock rises over it
      slide(pane, top0 - dock.offsetTop, 0, () => right.classList.add("fs-off"));
      settled(pane);
    } else if (prev === "max") {
      if (mode === "min") { layout(); settled(pane); return; }
      right.classList.remove("fs-off");
      const land = pane.q(".fs-wrap").offsetHeight + pane.q(".hsplit").offsetHeight;
      dockButtons(pane);
      // a list read to its end moves to its newest lines when it lands (layout() keeps it at
      // its end): it fades out over the landing and back in there, rather than jumping
      const list = pane.q(".panel .tab.on");
      right.classList.toggle("dock-land", !!list && !list.classList.contains("tab-results")
        && atEnd(list) && contentBottom(list) > list.clientHeight - land);
      slide(pane, 0, land, () => { layout(); right.classList.remove("dock-land"); settled(pane); });
    } else {
      layout();                                // min <-> split: the row fades in, the content rises
      settled(pane);
    }
    markRead(pane);                              // the chat shows again: its answers are read
  }

  /** Move the dock from translateY(from) to translateY(to), then call end once. */
  function slide(pane, from, to, end) {
    const right = pane.q(".pright"), dock = pane.q(".panel");
    let timer = 0;
    const anim = {
      finish() {
        if (pane.dockAnim !== anim) return;
        pane.dockAnim = null;
        clearTimeout(timer);
        dock.removeEventListener("transitionend", onEnd);
        right.classList.remove("dock-anim");
        dock.style.transform = "";
        end();
      },
    };
    const onEnd = (ev) => { if (ev.target === dock && ev.propertyName === "transform") anim.finish(); };
    dock.style.transform = from ? `translateY(${from}px)` : "";
    void dock.offsetHeight;                      // start from there, without a transition
    right.classList.add("dock-anim");
    dock.style.transform = to ? `translateY(${to}px)` : "";
    pane.dockAnim = anim;
    dock.addEventListener("transitionend", onEnd);
    timer = setTimeout(() => anim.finish(), 420);  // in case no transition ran
  }

  function showPanel(pane, name) {
    pane.q(".panel nav").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
    pane.el.querySelectorAll(".panel .tab").forEach((x) => x.classList.toggle("on", x.classList.contains("tab-" + name)));
    glide(pane.q(".panel nav .seg"), pane.q(".panel nav button.on"));
    const tab = tabOf(pane.tabId);
    if (name === "results" && tab) renderResults(pane, tab);    // a chart is drawn at its box's size
    else csvButton(pane);
    if (name === "msgs") { clampCheck(pane); listFades(pane.q(".chat-list")); markRead(pane); }
    if (name === "log") logShown(pane);
    if (name === "changes") toastClose("away");  // (its line says what the toast said)
    renderChanges(pane, name === "changes");     // (leaving it: what it showed is seen)
  }

  // ------------------------------------------------------------------ the Changes panel
  /** The Changes panel's segment shows where the window can read the timeline (changes.js,
   *  WBC.on; else hidden, and a dock left on it goes back to the AI chat); the panel is drawn
   *  from the shown tab's model. show: the user opened
   *  it now (a model with no journal summary, or one that failed, is asked again). While the
   *  panel does not show, its segment counts the others' changes not seen yet. */
  function renderChanges(pane, show) {
    const on = WBC.on(), btn = pane.q(".panel nav [data-tab=changes]");
    if (btn.classList.contains("hidden") === on) {
      btn.classList.toggle("hidden", !on);
      if (!on && btn.classList.contains("on")) { showPanel(pane, "msgs"); return; }
      glide(pane.q(".panel nav .seg"), pane.q(".panel nav button.on"));
    }
    const tab = tabOf(pane.tabId), ctx = Object.assign(changesCtx(pane, tab), { on, show: !!show });
    WBC.render(pane.q(".tab-changes"), ctx);
    // the dock's ⋯ while the tab shows (dockItems): what the record covers, where the window
    // makes reports the report of the changes, where the server makes blocks of them the
    // changes to turn into blocks
    const av = pane.dockAv || (pane.dockAv = {});
    av.cov = on && ctx.shown && WBC.covOn();
    av.rep = on && ctx.shown && !!ctx.model && WBC.repOn();
    av.sel = on && ctx.shown && !!ctx.model && WBC.tbOn(ctx);
    WBC.coverageSync(av.cov);
    WBC.reportSync(av.rep);
    dockMore(pane);
    // the window just opened on a model changed since you last looked: the away line, once
    if (on && tab && !pane.awayOpened && ctx.model && ctx.summary) {
      pane.awayOpened = true;
      changesBack(pane, null);
    }
    if (on && ctx.shown && ctx.model && WBC.awayOf(ctx.model)) toastClose("away");   // the away line on screen says it
    const n = on && !ctx.shown ? WBC.unread(ctx) : 0, word = n > 99 ? "99+" : n ? String(n) : "";
    if (btn._unread !== `${word}|${I18N.lang}`) {
      btn._unread = `${word}|${I18N.lang}`;
      const c = btn.querySelector(".ch-count");
      c.textContent = word;
      c.classList.toggle("hidden", !n);
      btn.title = n ? `${t("tip_tab_changes")}\n${t(n === 1 && I18N.lang !== "zh" ? "tip_ch_unread_1" : "tip_ch_unread", n)}` : t("tip_tab_changes");
      glide(pane.q(".panel nav .seg"), pane.q(".panel nav button.on"));   // (the segments after it moved)
    }
  }
  /** What changes.js is told of the pane's tab: its model, the journal summary, whether the
   *  panel shows, the prefs, and what it can ask of the page: a request shown in the AI chat,
   *  a record's block or stream found (gotoChange), the flowsheet's dots drawn again, the AI
   *  asked about a record or a group (ask). */
  function changesCtx(pane, tab) {
    const btn = pane.q(".panel nav [data-tab=changes]"), sess = tab ? sessOf(tab) : {}, cat = (wb.state && wb.state.catalog) || {};
    const fs = sess.flowsheet || {}, types = {};
    (fs.blocks || []).forEach((b) => { if (b && b.name && b.type) types[b.name] = b.type; });
    const j = sess.journal && typeof sess.journal === "object" ? sess.journal : null;
    const model = (sess.model && sess.model.id) || (j && j.model) || fs.model || null;
    return {
      on: WBC.on(), show: false, session: tab ? tab.session : null, tab: tab ? tab.id : null, types, summary: j,
      model,
      journalOn: cat.journal_on !== false, strings: cat.strings || null,
      shown: !!tab && btn.classList.contains("on") && prefs().dockMode !== "min",
      gotoNote: (id) => gotoNote(pane, id), goto: (tg, path) => gotoChange(pane, tg, path),
      onMarks: () => soon("chMarks", () => { const t2 = tabOf(pane.tabId); if (t2) { FS.render(pane.svg, fsView(pane, t2)); renderChanges(pane); } }),
      prefGet, prefSet, connected: !!wb.connected,
      newTab: tab ? (title, program) => programTab(tab.session, title, program) : null,
      showObjs: (tgs) => showObjs(pane, tgs),
      toast, menu: (at, items, ev) => toggleMenu(at, () => items, ev),
      // Ask AI about a record or a group
      ask: tab ? (target) => askAI(tab, target) : null,
      // a record's field: its help card (help.js), where the server and the window make one
      help: tab && WBH.on() ? (anchor, r) => WBH.fromRecord(anchor, r, tab, types) : null,
      // take a record or a group back, restore a restore point (app-undo.js previews
      // first); the model's restore points on disk (Api.checkpoints, read while the tab shows)
      undo: tab && feature("undo") ? (o) => undoOpen(tab, o) : null,
      restore: tab ? (o) => restoreOpen(tab, o) : null,
      cps: tab ? cpMap(tab) : null,
      // the AI's proposal a record names: its tab shown
      openTab: (id) => { if (tabOf(id)) { showIn(pane, id); activate(id); } },
      // ... and one kept in History: brought back (prop_open) and shown once it is loaded
      openProposal: (o) => {
        const id = (o && o.tab) || "";
        if (tabOf(id)) { showIn(pane, id); activate(id); } else if (id) openEntry({ tab: id });
      },
      // a group or picked records made into blocks in a new tab (app-replay.js)
      toBlocks: tab && model && feature("to_blocks") ? (o) => toBlocks(tab, Object.assign({ model }, o)) : null,
      onSel: () => soon("chSel", () => renderChanges(pane)),
    };
  }
  // ------------------------------------------------------------------ while you were away
  // Away: the window lost the focus (another program in front, the window minimized) and got it
  // back AWAY_MS or more later. Then, and once when the window opens, changes.js counts what the
  // others changed in the shown tab's model meanwhile (WBC.back): its line over the Changes
  // tab's cards, and a toast with See changes where that tab is not on screen.
  const AWAY_MS = 2 * 60 * 1000;
  let leftAt = 0;
  function awayLeft() { if (!leftAt) leftAt = Date.now(); }
  function awayBack() {
    const left = leftAt;
    leftAt = 0;
    if (left && Date.now() - left >= AWAY_MS && wb.pane) changesBack(wb.pane, left / 1000);
  }
  function changesBack(pane, left) {
    const tab = tabOf(pane.tabId);
    if (!window.WBC || !tab) return;
    WBC.back(changesCtx(pane, tab), left).then((A) => {
      renderChanges(pane);                       // (back again: the last line goes, or this one comes)
      if (!A) return;
      const now = tabOf(pane.tabId), ctx = now ? changesCtx(pane, now) : null;
      if (ctx && !ctx.shown && ctx.model === A.model) {
        const n = A.more ? `${A.n}+` : A.n;
        toast(t(A.n === 1 && I18N.lang !== "zh" ? "away_toast_1" : "away_toast", n), 5000, { label: t("away_see"), run: () => {
          if (prefs().dockMode === "min") setDock(pane, "split");
          showPanel(pane, "changes");
        } }, "away");
      }
    });
  }
  /** A new tab on a session holding a program the page made (a measured run's one input at a
   *  time): the tab asked of the server, then the program sent as its first version, yours;
   *  its column opens once that version loads (app-program.js, wb.progWant). */
  function programTab(session, title, program) {
    newTab(session, title, (id) => {
      wb.progWant = id;
      wb.post({ type: "program", tab: id, program });
      toast(t("rc_ofat_done", title), 5000);
    });
  }
  /** The flowsheet frames these blocks and streams (the away line's "show on the flowsheet"):
   *  the dock gives the flowsheet back where it took the whole column. */
  function showObjs(pane, tgs) {
    if (!tgs || !tgs.length) return;
    if (prefs().dockMode === "max") setDock(pane, "split");
    if (!FS.fitTo(pane.svg, tgs)) toast(t("aw_fs_none"), 3000);
  }
  /** The flowsheet's dots: the unseen changes by others on each block and stream (WBC.marks). */
  const changesMarks = (pane, tab) => (window.WBC && tab ? WBC.marks(changesCtx(pane, tab)) : null);
  /** The user picked a target on the flowsheet (null: let go): its dot goes, and a Changes
   *  panel that shows keeps only its changes (or all again). quiet: picked from the panel
   *  itself, which keeps its filter. */
  function changesPicked(pane, target, quiet) {
    const tab = tabOf(pane.tabId);
    if (!window.WBC || !tab) return;
    const ctx = changesCtx(pane, tab);
    if (target && WBC.seeObj(ctx, target)) FS.render(pane.svg, fsView(pane, tab));   // its dot goes at once
    if (!quiet) WBC.pick(pane.q(".tab-changes"), ctx, target);
  }
  /** A dot clicked: the target is picked, and the Changes panel shows its changes only. */
  function changesFor(pane, target) {
    const tab = tabOf(pane.tabId);
    if (!window.WBC || !tab) return;
    pick(pane, target);
    WBC.only(pane.q(".tab-changes"), changesCtx(pane, tab), target);
    if (prefs().dockMode === "min") setDock(pane, "split");
    showPanel(pane, "changes");
  }
  /** A log drawn while hidden (another panel on, the dock collapsed) goes to its newest lines,
   *  or a failed run's first error, once it shows. */
  function logShown(pane) {
    const list = pane.q(".tab-log");
    if (!pane.logTo || !list.clientHeight) return;
    list.scrollTop = list.scrollHeight;
    if (pane.logTo === "error") toFirstError(pane);
    pane.logTo = null;
  }

  function renderResults(pane, tab) {
    const run = tab.run || {};
    const live = run.status === "running" && !run.dry_run && ((run.tables || []).length || (run.opts || []).length);
    const res = live ? { tables: run.tables, opts: run.opts } : (tab.results || { tables: [], opts: [] });
    const n = (res.tables || []).length + (res.opts || []).length;
    // the segment: a dot while results came that the panel has not shown (the run bar says how
    // many; the count is the tooltip's); the results there when the window opened count as seen
    const btn = pane.q(".panel nav [data-tab=results]"), rec = wb.recs.get(tab.id);
    const ver = n ? String(live ? `${run.started}:${n}` : res.finished) : "";
    if (rec && (rec.resSeen === undefined || (btn.classList.contains("on") && prefs().dockMode !== "min"))) rec.resSeen = ver;
    const fresh = !!rec && !!ver && rec.resSeen !== ver;
    btn.querySelector(".res-dot").classList.toggle("on", fresh);
    const tip = [t("tip_tab_results"), n && t(n === 1 ? "tip_res_n_1" : "tip_res_n", n), fresh && t("tip_res_new")].filter(Boolean).join("\n");
    if (btn.title !== tip) btn.title = tip;
    glide(pane.q(".panel nav .seg"), pane.q(".panel nav button.on"));
    const heat = heatOf(tab), hp = heatPref(tab);
    // ver: which run's results these are (a rerun makes the same tables with new numbers)
    WBR.render(pane.q(".tab-results"), tab, res, { plan: heat && hp.on ? Math.min(hp.plan, heatPlans(heat) - 1) : null,
                                                   ver: live ? run.started : res.finished, apply: applyOf(tab) });
    csvButton(pane);
  }
  /** What the results panel needs to apply a point (results.js, opt.apply): why not now (as the
   *  inspector's Run simulation says it: not connected, the model not open, a program running on
   *  it, Aspen calculating it), what changes when the server answers (the tab's messages), and the
   *  send. */
  function applyOf(tab) {
    const why = !wb.connected ? t("why_off") : !isOpen(tab) ? t("why_closed", tab.session)
      : wb.state.tabs.some((x) => x.session === tab.session && busy(x)) ? t("why_ap_busy")
      : (sessOf(tab).sim || {}).status === "running" ? t("why_sim_running") : "";
    const msgs = tab.messages || [], last = msgs[msgs.length - 1];
    return { why, stamp: `${msgs.length}:${last ? last.t : ""}`,
      send: (source, row) => wb.post(Object.assign({ type: "apply_point", tab: tab.id, source },
        row && typeof row === "object" ? { eval: row.eval } : { row })) };
  }
  // an Apply sent and never answered lets its buttons go after a while (results.js)
  WBR.onRefresh = () => { const tab = shownTab(); if (tab) renderResults(wb.pane, tab); };
  /** The dock bar's CSV item: while the results show one. */
  function csvButton(pane) {
    const on = pane.q(".panel nav [data-tab=results]").classList.contains("on");
    (pane.dockAv || (pane.dockAv = {})).csv = on && WBR.canExport(pane.q(".tab-results"));
    dockMore(pane);
  }
  /** The dock's ⋯: the shown tab's own items -- Changes: what the record covers, the changes to
   *  turn into blocks (ticked while picking), the report; Tables & charts: the result as CSV --
   *  hidden where it has none (the AI chat, the run log). A popover it opens hangs from it. */
  function dockMore(pane) {
    const b = pane.q(".dnav .dock-more");
    if (!b) return;
    const items = dockItems(pane, b).length > 0;
    if (b.classList.contains("hidden") === items) b.classList.toggle("hidden", !items);
  }
  function dockItems(pane, b) {
    const av = pane.dockAv || {}, on = (k) => pane.q(`.panel nav [data-tab=${k}]`).classList.contains("on"), tab = tabOf(pane.tabId);
    if (on("results")) {
      return av.csv ? [{ label: t("m_csv"), icon: "download", tip: t("tip_export"), run: () => WBR.exportShown(pane.q(".tab-results")) }] : [];
    }
    if (!on("changes") || !window.WBC || !tab) return [];
    const ctx = () => changesCtx(pane, tabOf(pane.tabId));
    return [
      av.cov && { label: t("cov_btn"), icon: "info", run: () => WBC.coverage(b) },
      av.sel && { label: t("to_blocks_sel_btn"), icon: "select", check: !!WBC.selOn(tab.id),
        run: () => { const c = ctx(); WBC.select(pane.q(".tab-changes"), c, !WBC.selOn(c.tab)); renderChanges(pane); } },
      av.rep && { label: t("rep_btn"), icon: "download", run: () => WBC.report(b, ctx()) },
    ].filter(Boolean);
  }

  Object.assign(WBA, { autoFold, awayBack, awayLeft, changesCtx, changesFor, changesMarks, changesPicked, dockItems, dragBar, layout, measure, renderChanges,
    renderResults, keepProg, setDock, setProg, settled, showPanel });
})();
