/* The page's shell: the ... menu (moreItems, resetLayout, showKeys), the keyboard (onKey,
 * escape), and startup (start, on DOMContentLoaded). Loaded last. The tour and the legend,
 * and what shows at a first launch: app-tour.js.
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { $, act, autoFold, awayBack, awayLeft, brakeSwitches, busy, closeInspector, closeMenus, commitEdit, cycleTab, dialog, dressIcons, dropMarks,
    esc, feature, flushPrefs, focusComposer, followLight, fslStep, helpItems, hideProv, layout,
    loadPrefs, makePane, menuKey, menuOpen, normLayout, openAsNewTab, openNewItem, prefSet, prefs,
    renderConn, revealTab, runSim, saveFile, saveModel, savePrefs, saveTab, setDock, settled,
    shownTab, shutPlan, startRun, stepPress, stopRun, t, tabItems, tabOf, toast, tourKey, undoClose, wb, wireTabs } = WBA;
  const { pausedOf } = WBA.later;

  /** The ... menu, in parts: block program files, the view (the layout, the language: the LLM
   *  sets it from what the user writes, so it is seldom needed), "Tracking and learning" (the review menu's
   *  switches, the same ones whether or not the header has that menu: "Follow AI edits", "Learning mode"),
   *  help (the beginner tour, the flowsheet legend, the keys; the logo opens the same). */
  function moreItems() {
    const tab = shownTab(), rep = !!tab && !!wb.pane && !!window.WBC && WBC.repOn(), sw = brakeSwitches();
    return [
      // the model's change report (a file-level action, found where files are)
      ...(rep ? [{ title: t("m_sec_model") }, { label: t("m_report"), icon: "download", tip: t("tip_m_report"),
        run: () => WBC.report($("btn-more"), WBA.changesCtx(wb.pane, tab)) }, { sep: true }] : []),
      { title: t("m_sec_prog") },
      openNewItem(),
      { label: t("m_this_tab"), icon: "tab", sub: tab ? tabItems(tab) : [], disabled: !tab },
      { sep: true },
      { title: t("m_sec_layout") },
      { label: t("m_reset"), icon: "layout", run: resetLayout },
      { label: t("lang_btn"), cls: "m-lang", tip: t("tip_lang"), run: switchLang },
      { sep: true },
      ...(sw.length ? [{ title: t("aim_sec_view") }, ...sw, { sep: true }] : []),
      { title: t("m_help") },
      ...helpItems($("btn-more")),
    ];
  }

  /** The workbench in the other language (the server keeps it: state.lang). */
  const switchLang = () => wb.post({ type: "lang", lang: wb.lang === "zh" ? "en" : "zh" });

  function resetLayout() {
    wb.layout2 = normLayout({});
    savePrefs();
    ((wb.state && wb.state.tabs) || []).forEach((x) => prefSet(`wb.prog.${x.id}`, null));   // each tab's own fold too
    if (wb.pane && wb.pane.tabId) wb.pane.progShut = autoFold(wb.pane);   // the program column: auto again
    layout();
    if (wb.pane && wb.pane.tabId) settled(wb.pane);
  }

  /** The keys: F5 is Run simulation (the program is F6); Ctrl+S saves the model, Ctrl+Shift+S
   *  the block program. */
  function showKeys() {
    const rows = [["F5", "run_sim"], ["F6", "run_prog"],
      ["Ctrl+F5 · Ctrl+Shift+Enter", "check_prog"], ["Ctrl+.", "stop"], ["F10", "k_step"],
      ["Ctrl+Tab · Ctrl+Shift+Tab", "k_tabs"], ["Ctrl+PgDn · Ctrl+PgUp", "k_subtabs"], ["Ctrl+Shift+H", "prop_hist"],
      ["Ctrl+K · /", "ask_ai"],
      ["Ctrl+S", "k_save"], ["Ctrl+Shift+S", "k_save_awb"], ["Ctrl+O", "k_open"],
      ["Esc", "k_esc"], ["Ctrl+Z · Ctrl+Y", "k_undo"], ["Ctrl+0", "k_bfit"]];
    dialog({ title: t("m_keys"), html: `<table class="keys">${rows.map(([k, what]) =>
      `<tr><td>${k.split(" · ").map((x) => `<kbd>${esc(x)}</kbd>`).join(" ")}</td><td>${esc(t(what))}</td></tr>`).join("")}</table>`,
      ok: t("ok"), onOk: () => {}, noCancel: true, focus: "ok" });
  }

  // ------------------------------------------------------------------ keyboard
  // One handler for the page, ahead of Blockly's. Nothing fires while the user types (a text
  // box, a Blockly field editor) or a menu or dialog is open, except that F5 never reloads
  // the page, and that F5 (Run simulation) and Ctrl+S, which mean nothing in a text box, still
  // run and save: a value being typed in the inspector is written first, the way a click
  // elsewhere writes it (typeKey). F5 is Aspen's Run (Run simulation), F6 the block program;
  // Ctrl+S saves the model, never the .awb in its place, Ctrl+Shift+S the block program. An
  // open menu or dialog
  // takes the keys first, then the beginner tour (its arrows, and Escape skips it; not while
  // typing, so the page stays usable under it). Escape closes the topmost thing,
  // one a press: menu, dialog, a category's blocks, the folded heat plan's rows, the
  // maximized dock, a row's history card, the inspector (a text box's own Escape comes first; the composer's goes
  // through the same steps before it lets go of the caret).
  function onKey(ev) {
    const k = ev.key, ctrl = ev.ctrlKey || ev.metaKey;
    if (k === "F5" || k === "F6" || (k === "F10" && pausedOf(shownTab()))) ev.preventDefault();
    if (menuOpen()) {
      if (menuKey(ev)) { ev.preventDefault(); ev.stopPropagation(); }
      return;
    }
    if (!$("modal").classList.contains("hidden")) {
      if (k === "Escape") { ev.preventDefault(); ev.stopPropagation(); if (wb.modalClose) wb.modalClose(); }
      return;
    }
    const el = document.activeElement;
    const typing = (el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)))
      || (window.Blockly && ((Blockly.WidgetDiv && Blockly.WidgetDiv.isVisible()) || (Blockly.DropDownDiv && Blockly.DropDownDiv.isVisible())));
    // the model's sub-tabs and its History (app-subtabs.js): the popover's keys while it is open (its
    // filter too), Ctrl+PgDn / Ctrl+PgUp and Ctrl+Shift+H
    if (WBA.subKey && WBA.subKey(ev)) { ev.preventDefault(); ev.stopPropagation(); return; }
    if (typing) { typeKey(ev); return; }
    if (tourKey(ev)) { ev.preventDefault(); ev.stopPropagation(); return; }
    const tab = shownTab();
    let did = true;
    if ((k === "F5" && ctrl) || (k === "Enter" && ctrl && ev.shiftKey)) runKey(true);
    else if (k === "F5" && !ev.shiftKey && !ev.altKey) { if (tab) runSim(tab); }
    else if (k === "F6" && !ctrl && !ev.shiftKey && !ev.altKey) runKey(false);
    else if (k === "F10" && !ctrl && !ev.shiftKey && !ev.altKey) did = stepPress("next");   // paused: the next step
    else if (k === "." && ctrl) { if (busy(tab) && !wb.connected) toast(t("why_stop_off")); else stopRun(); }
    else if (k === "Tab" && ctrl) cycleTab(ev.shiftKey ? -1 : 1);
    else if ((k.toLowerCase() === "k" && ctrl) || (k === "/" && !ctrl && !ev.altKey)) focusComposer(wb.pane);
    else if (k.toLowerCase() === "s" && ctrl && !ev.altKey) { if (tab) { if (ev.shiftKey) saveTab(tab.id); else saveModel(tab); } }
    else if (k.toLowerCase() === "o" && ctrl && !ev.altKey && !ev.shiftKey) { if (wb.connected) openAsNewTab(); else toast(t("why_off")); }
    else if (k === "0" && ctrl && !ev.altKey && !ev.shiftKey) { const rec = tab && wb.recs.get(tab.id); if (rec) WBA.fitProgram(rec); }   // the program's Fit (its ⋯)
    else if (ctrl && !ev.altKey && /^[zy]$/i.test(k) && wb.undoScope === "fs" && tab) {
      // right after a step on the flowsheet, its undo and redo; with nothing that way there,
      // the blocks' (Blockly hears the key)
      if (wb.pane && FS.dragging(wb.pane.svg)) ev.stopImmediatePropagation();   // nothing under a drag
      else if (fslStep(tab.session, !(k.toLowerCase() === "y" || ev.shiftKey))) ev.stopImmediatePropagation();
      else { wb.undoScope = "blocks"; did = false; }
    }
    else if (ctrl && !ev.altKey && /^[zy]$/i.test(k) && wb.undoScope === "model") {
      // in the Changes tab or the inspector: the model's changes are taken back row by row there
      // (Ctrl+Z is the block program's), so a line says how rather than nothing happening
      ev.stopImmediatePropagation();               // (the blocks' own undo does not hear it either)
      toast(t(feature("undo") && WBC.on() ? "undo_key_hint" : "undo_key_hint_off"), 5000, undefined, "hint");
    }
    else if (k === "Escape") did = escape();
    else did = false;
    if (did) ev.preventDefault();
  }
  /** F5 or Ctrl+S while the user types: the value being typed in the inspector goes to Aspen
   *  first (commitEdit, as a click elsewhere or Enter sends it; the server takes it before
   *  the run or the save that follows), then Run simulation or Save model, as outside a text
   *  box. In the Ask AI box, a Blockly field or any other text box they go at once, the text
   *  left as it is. */
  function typeKey(ev) {
    const k = ev.key, ctrl = ev.ctrlKey || ev.metaKey, tab = shownTab();
    const f5 = k === "F5" && !ctrl && !ev.shiftKey && !ev.altKey;
    const save = k.toLowerCase() === "s" && ctrl && !ev.shiftKey && !ev.altKey;
    const f10 = k === "F10" && !ctrl && !ev.shiftKey && !ev.altKey && !!pausedOf(tab);   // paused: the value typed, then the next step
    if (!tab || !(f5 || save || f10)) return;
    ev.preventDefault();
    ev.stopPropagation();
    if (wb.pane) commitEdit(wb.pane);
    if (f10) stepPress("next");
    else if (f5) runSim(tab);
    else saveModel(tab);
  }
  /** Run program (F6) while the tab runs says how to stop instead:
   *  the key never stops a run. */
  function runKey(dry) {
    const tab = shownTab();
    if (!tab) return;
    if (busy(tab)) { toast(t("f5_busy")); return; }
    startRun(dry);
  }
  function escape() {
    const pane = wb.pane, rec = pane && wb.recs.get(pane.tabId);
    if (pane && FS.dragging(pane.svg)) { FS.cancelDrag(pane.svg); return true; }   // a drag on the flowsheet, first
    if (window.WBC && WBC.coverageClose(true)) return true;   // what the change record covers, over the rest
    if (window.WBC && WBC.reportClose && WBC.reportClose(true)) return true;   // the change report's box, the same
    if (undoClose && undoClose(true)) return true;   // an undo's preview, a restore's confirmation (app-undo.js)
    if (window.WBH && WBH.close(true)) return true;   // a field's help card (help.js)
    if (window.WBM && WBM.close(true)) return true;   // the list of missing inputs (missing.js)
    if (window.WBD && WBD.close(true)) return true;   // a run's diagnosis card (diag.js)
    if (window.WBPN && WBPN.close(true)) return true;   // a principle card (principle.js), before a path and the result tags
    if (!rec) return false;
    // what lies over the rest first, as a menu does: a category's blocks (Blockly's own Escape,
    // when the list has the focus, closes them too), the folded heat plan's rows
    const box = rec.ws.getToolbox(), fly = box && box.getFlyout();
    if (fly && fly.isVisible()) { box.clearSelection(); return true; }
    if (shutPlan(pane)) return true;
    if (prefs().dockMode === "max") { setDock(pane, "split"); return true; }
    if (hideProv(pane)) return true;              // a row's history card, before the inspector under it
    if (rec.insp) { closeInspector(pane); return true; }
    const tab = tabOf(pane.tabId);
    if (WBA.fxEsc && WBA.fxEsc(pane)) return true;   // this run's result tags (app-effects.js)
    if (tab && dropMarks(pane, tab)) return true;   // then what the AI marked on the flowsheet
    return false;
  }

  // ------------------------------------------------------------------ startup
  function start() {
    I18N.setLang("en");
    dressIcons($("bar"));
    dressIcons($("no-tabs"));
    I18N.apply(document);
    makePane();
    wireTabs();
    WBR.onExport = saveFile;
    $("bar").addEventListener("click", (ev) => { if (wb.pane) act(wb.pane, ev.target.closest("[data-a]"), ev); });
    // (a press on a button that opens a menu is its own toggle: toggleMenu)
    document.addEventListener("mousedown", (ev) => {
      if (!ev.target.closest('.menu, #tab-add, #btn-more, #logo, #empty-new, [data-a="fs_menu"], [data-a="model"], [data-a="run_sim_menu"], [data-a="prog_menu"], [data-a="legend"], .iadd, .ch-more, #ai-brake [aria-haspopup]')) closeMenus();
    });
    $("modal").addEventListener("mousedown", (ev) => { if (ev.target === $("modal") && wb.modalClose) wb.modalClose(); });
    window.addEventListener("blur", closeMenus);
    // away from the window and back: what the others changed meanwhile (app-layout.js)
    window.addEventListener("blur", awayLeft);
    window.addEventListener("focus", awayBack);
    let frame = 0, rest = 0;                       // a window resize: sizes once a frame, charts when it stops
    window.addEventListener("resize", () => {
      if (!frame) frame = requestAnimationFrame(() => { frame = 0; layout(); revealTab(); });
      closeMenus();
      clearTimeout(rest);
      rest = setTimeout(() => wb.pane && settled(wb.pane), 150);
    });
    layout();
    renderConn();
    followLight();
    document.addEventListener("keydown", onKey, true);
    // a block the connection check refused while held over a slot (blocks.js): a result over a
    // slot that writes, a flowsheet change over a loop; each said at most every 4 s
    const refused = {};
    WB.onRefuse = (why = "result") => {
      if (Date.now() - (refused[why] || 0) < 4000) return;
      refused[why] = Date.now();
      toast(why === "struct" ? Blockly.Msg.WB_STRUCT_IN_LOOP : t("refuse_result"));
    };

    const boot = () => {
      const api = window.pywebview.api;
      (api.prefs ? loadPrefs(api) : Promise.resolve()).then(() => api.state()).then((s) => s && wb.applyState(s));
    };
    window.addEventListener("pagehide", flushPrefs);
    if (window.pywebview && window.pywebview.api) boot();
    else window.addEventListener("pywebviewready", boot);
    if (window.DEV_STATE) {                        // preview outside pywebview
      wb.applyState(window.DEV_STATE);
      wb.setConnected(true);
    }
  }
  document.addEventListener("DOMContentLoaded", start);

  Object.assign(WBA, { escape, moreItems, showKeys });
})();
