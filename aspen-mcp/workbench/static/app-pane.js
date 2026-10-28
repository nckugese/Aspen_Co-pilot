/* The pane: made once (makePane: its lenses, FS.attach and its callbacks), a tab shown in
 * it and let go (showIn, release, activate), its listeners (wirePane), every data-a button
 * (act: the header's, the program's run bar, the flowsheet's, the canvas's), and renderPane,
 * which draws the shown tab's parts.
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { $, autoFold, changed, changesFor, dragBar, dressIcons, guard, keepProg, layout, lens, listFades, measure, prefs,
    renderChanges, renderResults, rootOf, savePrefs, sessOf, setDock, setProg, settled, showPanel, soon, t, tabOf, toast, toggleMenu,
    useSession, wb } = WBA;
  const { chatAct, dockItems, fitChip, flashBlock, focusComposer, fsMenuItems, fslDrop,
    fsView, gotoNote, heatOf, heatPref, loadHeld, logAct, modelPanel, openStatus,
    peek, pick, progItems, railLens, renderChat, renderComposer, renderConn, renderEdges,
    renderFslTools, renderHeld, renderInspector, renderRun, renderRunbar, renderTabs, renderTools,
    reveal, runSim, saveModel, sayFailure, selOf, sendProgram, settleHeld, shadeTools, simItems,
    startRun, stepPress, stopRun, toStart, wireComposer, wireInspector, wirePlan, wireSubtabs } = WBA.later;

  // ------------------------------------------------------------------ the pane
  function makePane() {
    const el = $("pane-tpl").content.firstElementChild.cloneNode(true);
    const q = (sel) => el.querySelector(sel);
    const pane = { el, q, tabId: null, sigs: {}, svg: q(".fs"), editing: null, rail: null };
    dressIcons(el);
    // a layer toggle carries a dot that says whether its layer shows
    el.querySelectorAll(".fs-tools .tgl").forEach((b) => b.insertAdjacentHTML("afterbegin", `<i class="tdot"></i>`));
    I18N.apply(el);
    $("panes").appendChild(el);
    wb.pane = pane;
    FS.attach(pane.svg, { pick: (tg) => pick(pane, tg), note: (id) => gotoNote(pane, id), changes: (tg) => changesFor(pane, tg),
                          zoom: (pct) => { q(".zpct").textContent = `${pct}%`; }, view: () => renderEdges(pane),
                          peek: (tg, x, y) => peek(pane, tg, x, y), layout: (obj, ctx) => fslDrop(pane, obj, ctx),
                          moving: () => { const tab = tabOf(pane.tabId); if (tab) renderFslTools(pane, tab); } });
    wirePane(pane);
    wireSubtabs(pane);                           // the model's sub-tabs over the program (app-subtabs.js)
    wireComposer(pane);
    wirePlan(pane);
    // the pane's lenses, with the shown workspace's category list (railLens): seven (the heat plan
    // card's shows only with the card, the proposal's only on a proposal, the group card's only
    // while a proposal is applied by group). Glass with words over the drawing blurs 10 px or more, so the
    // lines under the words go soft
    pane.lenses = [lens(q(".fs-tools"), { bezel: 12, scale: 30, blur: 10 }), lens(q(".fs-chip"), { bezel: 10, scale: 24, blur: 10 }),
                   lens(q(".insp"), { bezel: 18, scale: 48, blur: 12 }),
                   lens(q(".fs-plan"), { bezel: 16, scale: 36, blur: 10 }), lens(q(".prop-card"), { bezel: 20, scale: 44, blur: 16, tint: "saturate(150%) brightness(1.05)" }),
                   lens(q(".gc-card"), { bezel: 16, scale: 36, blur: 12 })];
    return pane;
  }

  function release(pane) {
    FS.letGo(pane.svg);                          // a press or drag on the flowsheet was the tab's
    const rec = wb.recs.get(pane.tabId);
    if (rec) {
      settleHeld(rec, false);                    // off screen no editor is open: nothing to hold for
      rec.el.classList.remove("on", "narrow");
      $("ws-store").appendChild(rec.el);
    }
    if (pane.rail) { pane.rail.dispose(); pane.rail = null; }
    pane.tabId = null;
    pane.sigs = {};
    pane.canvasBox = null;                       // the next workspace shown is measured
  }

  function showIn(pane, id) {
    if (!pane || pane.tabId === id) return;
    if (pane.editing && pane.editing.done) pane.editing.done(true);   // a value being typed in the inspector is written (startEdit)
    release(pane);
    const rec = wb.recs.get(id), tab = tabOf(id);
    if (!rec || !tab) return;
    pane.tabId = id;
    pane.editing = null;
    wb.undoScope = "blocks";                   // another tab: Ctrl+Z is the blocks' until a flowsheet step
    pane.q(".blockly").appendChild(rec.el);
    rec.el.classList.add("on");
    pane.q(".pbody").classList.remove("hidden");
    railLens(pane);
    pane.progShut = autoFold(pane);            // a tab with no program shows folded (app-layout.js)
    layout();                                  // sizes first, so the flowsheet fits its real box
    renderHeld(rec);                           // (the pill toStart keeps the start block clear of)
    if (!rec.shown) { rec.shown = true; toStart(rec); }   // first shown: the program's start at the top left
    else if (rec.view) rec.ws.scroll(rec.view.x, rec.view.y);   // made anew off screen: the view it had
    rec.view = null;
    FS.use(pane.svg, rec.fs);
    pane.linkSig = null;                       // the workspace moved: Blockly let go of its selection
    FS.mark(pane.svg, [], "link");
    peek(pane, null);
    useSession(tab);
    shadeTools(rec);
    renderPane(pane);
    renderTabs();
    renderRunbar();
    renderConn();
    sayFailure(rec, tab);                      // a failure while the tab was not shown
    if (window.WBPN) WBPN.sync();              // (a principle card of the tab left: closed)
  }

  /** The tab shown is the server's active one too; the sub-tab its model tab shows next time
   *  (wb.fronts, this window's: the server keeps its own, the model tab's front). */
  function activate(id) {
    const root = rootOf(tabOf(id));
    if (root) (wb.fronts = wb.fronts || new Map()).set(root.id, id);
    wb.lastActive = id;
    wb.pendingActive = { id, until: Date.now() + 3000 };
    wb.post({ type: "tab_active", tab: id });
  }

  function wirePane(pane) {
    const q = pane.q;
    let start = null;
    // a drag on the splitter of a folded column opens it (at its floor, then as dragged)
    dragBar(q(".vsplit"), "x", () => { start = { w: q(".pleft").offsetWidth, m: measure(pane) }; }, (dx) => {
      const pr = prefs();
      if (pane.progShut) {
        if (dx < 12) return;
        pane.progShut = false;
        keepProg(pane, true);
        start.w = start.m.progMin - dx;          // from its floor, its edge then follows the pointer
      }
      pr.left = Math.max(0, Math.min(1, (start.w + dx) / start.m.W));
      layout();
    }, (moved) => {
      if (!moved || pane.progShut) return;       // a click keeps the saved share, even one a floor holds
      prefs().left = q(".pleft").offsetWidth / measure(pane).W;   // keep what the floors allowed
      savePrefs();
      settled(pane);
    });
    dragBar(q(".hsplit"), "y", () => {
      if (pane.dockAnim) pane.dockAnim.finish();
      start = { h: q(".panel").offsetHeight, m: measure(pane) };
    }, (dx, dy) => {
      const pr = prefs();
      pr.dockMode = "split";
      pr.dock = Math.max(0, Math.min(1, (start.h - dy) / start.m.H));
      layout();
    }, (moved) => {
      if (!moved) return;
      prefs().dock = q(".panel").offsetHeight / measure(pane).H;
      savePrefs();
      settled(pane);
    });
    // double-click: the program column folds to its strip (the flowsheet gets the width) and
    // opens again, the user's choice for every tab from then on; the dock grows over the
    // flowsheet and back
    q(".vsplit").addEventListener("dblclick", () => { if (pane.tabId) setProg(pane, !!pane.progShut, "user"); });
    q(".hsplit").addEventListener("dblclick", () => setDock(pane, prefs().dockMode === "split" ? "max" : "split"));
    // under a maximized dock the hsplit is covered: a double-click on the dock's bar, off its
    // buttons, does the same
    q(".dnav").addEventListener("dblclick", (ev) => {
      if (ev.target.closest("nav, button")) return;
      setDock(pane, prefs().dockMode === "split" ? "max" : "split");
    });
    q(".dnav").addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-dock]");
      if (!b) return;
      const mode = prefs().dockMode, d = b.dataset.dock;
      if (d === "max") setDock(pane, mode === "max" ? "split" : "max");
      else if (d === "min") setDock(pane, mode === "min" ? "split" : "min");
      else if (d === "ask") focusComposer(pane);
      else if (d === "more") {                     // the shown tab's own menu (app-layout.js); a note it opened: pressed again, it closes
        if (window.WBC && (WBC.coverageClose() || (WBC.reportClose && WBC.reportClose()))) return;
        toggleMenu(b, () => dockItems(pane, b), ev);
      }
    });
    q(".right-bar").addEventListener("click", (ev) => act(pane, ev.target.closest("[data-a]"), ev));
    // the model chip gives way in order as the room beside the capsule changes (fitChip)
    const fit = new ResizeObserver(() => fitChip(pane));
    fit.observe(q(".right-bar"));
    fit.observe(q(".fs-tools"));
    // an edge hint pans that way; one naming what a selected block names shows that
    q(".fs-area").addEventListener("click", (ev) => {
      const h = ev.target.closest(".fs-hint");
      if (!h) return;
      const k = h.dataset.link, i = k ? k.indexOf(":") : -1;
      if (i > 0) {
        const tg = { kind: k.slice(0, i), name: k.slice(i + 1) };
        if (reveal(pane, tg, FS.RING_ROOM)) FS.ping(pane.svg, tg);
      } else {
        const got = FS.edgePan(pane.svg, h.dataset.side);      // the nearest change there first: a ring on it
        if (got && got.kind) FS.ping(pane.svg, got);
      }
    });
    q(".blk-bar").addEventListener("click", (ev) => act(pane, ev.target.closest("[data-a]")));
    q(".prog-bar").addEventListener("click", (ev) => act(pane, ev.target.closest("[data-a]"), ev));
    q(".prog-strip").addEventListener("click", (ev) => act(pane, ev.target.closest("[data-a]"), ev));
    q(".panel nav").addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-tab]");
      if (!b) return;
      if (prefs().dockMode === "min") setDock(pane, "split");      // a collapsed dock opens on it
      pane.navAt = Date.now();                   // (picked by hand: a run ending now leaves the dock here, app-run.js)
      showPanel(pane, b.dataset.tab);
    });
    q(".chat-list").addEventListener("click", (ev) => chatAct(pane, ev.target.closest("[data-c]")));
    q(".chat-list").addEventListener("scroll", () => soon("chatFades", () => listFades(q(".chat-list"))), { passive: true });
    q(".tab-log").addEventListener("click", (ev) => logAct(pane, ev));
    // a press on the program's side: Ctrl+Z is the blocks' again; in the Changes tab or the
    // inspector it says how the model's changes are taken back (app-main.js)
    q(".pleft").addEventListener("pointerdown", () => { wb.undoScope = "blocks"; }, { capture: true, passive: true });
    [q(".tab-changes"), q(".insp")].forEach((el) => el.addEventListener("pointerdown", () => { wb.undoScope = "model"; }, { capture: true, passive: true }));
    const area = q(".blockly");
    // the user's hand on the canvas: for ten seconds a run does not scroll it (renderCursor)
    const touch = () => { pane.touchAt = Date.now(); };
    area.addEventListener("pointerdown", touch, { capture: true, passive: true });
    area.addEventListener("wheel", touch, { capture: true, passive: true });
    area.addEventListener("dragover", (ev) => {
      if (!wb.dragRow || !pane.tabId) return;
      ev.preventDefault();
      ev.dataTransfer.dropEffect = "copy";
    });
    area.addEventListener("drop", (ev) => {
      const rec = wb.recs.get(pane.tabId);
      if (!wb.dragRow || !rec) return;
      ev.preventDefault();
      useSession(tabOf(pane.tabId));
      flashBlock(WB.dropRow(rec.ws, wb.dragRow, ev.clientX, ev.clientY));
      wb.dragRow = null;
    });
    wireInspector(pane);
  }

  /** What a plan framed on the flowsheet keeps clear of at the bottom: the edge hints' row
   *  (their height and 10 px under them), px. */
  const HINT_ROOM = { bottom: 44 };

  /** A button with data-a: in the header (the model group), the program's run bar or its
   *  strip, on the flowsheet or on the block canvas. ev: the click (a menu opened from the
   *  keyboard focuses its first item). */
  function act(pane, btn, ev) {
    if (!btn || btn.disabled) return;
    const tab = tabOf(pane.tabId), rec = wb.recs.get(pane.tabId), a = btn.dataset.a;
    if (a === "values") { const pr = prefs(); pr.values = !pr.values; savePrefs(); pane.sigs = {}; renderPane(pane); return; }
    if (a === "fit") { FS.fit(pane.svg, true); return; }  // (the capsule's zoom: a click shows the whole drawing)
    if (!tab) return;
    if (a === "fs_menu") { toggleMenu(btn, () => fsMenuItems(pane, tab), ev); return; }
    if (a === "pv_pill") { WBA.pvToggle(pane); return; }   // a proposal's preview shown or hidden (app-preview.js)
    if (a === "model") { toggleMenu(btn, () => modelPanel(pane, tab), ev); return; }
    if (a === "run_sim") { runSim(tab); return; }
    if (a === "run_sim_menu") { toggleMenu(btn, () => simItems(tab), ev); return; }
    if (a === "save_model") { saveModel(tab); return; }
    if (a === "prog_menu") { toggleMenu(btn, () => progItems(tab), ev); return; }
    if (a === "prog_open") { setProg(pane, true, "user"); return; }
    if (a === "prog_fold") { setProg(pane, false, "user"); return; }
    if (a === "find_sel") { const tg = selOf(tab, rec); if (tg && reveal(pane, tg, FS.RING_ROOM)) FS.ping(pane.svg, tg); return; }
    if (a === "status") { openStatus(pane, tab, rec); return; }
    if (a === "heat") {                          // the layer, and the plan framed as it shows
      if (!heatOf(tab)) return;
      const h = heatPref(tab);
      h.on = !h.on;
      pane.sigs = {};
      renderPane(pane);
      if (h.on) FS.frameHeat(pane.svg, HINT_ROOM);
      return;
    }
    if (a === "run" || a === "check") { startRun(a === "check"); return; }
    if (a === "step") { startRun(false, false, { approve: true, mode: "step" }); return; }   // (app-step.js)
    if (a === "step_next" || a === "step_cont") { stepPress(a === "step_cont" ? "cont" : "next"); return; }
    if (a === "stop") { stopRun(); return; }
    if (a === "held_load") { loadHeld(rec); return; }
    if (a === "undo" || a === "redo") {
      sendProgram(rec);
      // the version the server moves to comes back and loads: a held one is not offered any more
      rec.held = null;
      rec.heldBack = 0;
      renderHeld(rec);
      wb.post({ type: a, tab: tab.id });
      toast(t(a === "undo" ? "prog_undo_done" : "prog_redo_done", tab.title), 4000);   // (the blocks only: the model is as it was)
    }
  }

  function renderPane(pane) {
    const tab = tabOf(pane.tabId);
    pane.q(".pempty").classList.toggle("hidden", !!tab);
    pane.q(".pbody").classList.toggle("hidden", !tab);
    if (!tab) return;
    const sess = sessOf(tab), rec = wb.recs.get(tab.id);
    if (changed(pane, "units", [tab.id, sess.units])) {   // unit menus follow data that came late
      useSession(tab);
      wb.tidyQuiet = Date.now() + 250;           // (its change events are no hand edit)
      WB.tidy(rec.ws);
    }
    if (rec) guard("whyShow", () => WB.whyShow(rec.ws));   // the steps' notes drawn while learning mode is on
    // each panel on its own (guard): one that throws leaves the others drawn
    guard("flowsheet", () => FS.render(pane.svg, fsView(pane, tab)));
    guard("renderTools", () => renderTools(pane, tab));
    guard("renderRun", () => renderRun(pane, tab, rec));
    guard("renderChat", () => renderChat(pane, tab, sess));
    guard("renderComposer", () => renderComposer(pane));
    guard("renderInspector", () => renderInspector(pane, tab, sess));
    guard("renderResults", () => renderResults(pane, tab));
    guard("renderChanges", () => renderChanges(pane));
    // over the flowsheet: what Aspen still needs (missing.js), why a run failed (diag.js)
    if (window.WBM) guard("missing", () => WBM.sync());
    if (window.WBD) guard("diagnosis", () => WBD.sync());
  }

  Object.assign(WBA, { act, activate, HINT_ROOM, makePane, release, renderPane, showIn });
})();
