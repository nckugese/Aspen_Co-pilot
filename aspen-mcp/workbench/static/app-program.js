/* The block program and its canvas: versions loaded, sent (sendProgram) and held while the
 * user edits (loadHeld, renderHeld and the pill), the capsule's zoom and fit, loose stacks,
 * room for the main program, the empty-program line, the category list (dressToolbox, its
 * lens and fades), flashBlock.
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { canon, glide, lens, setProg, shownTab, soon, t, tabOf, toast, useSession, wb } = WBA;
  const { markRefs } = WBA.later;

  /** What a version is, as text: the program plus the loose stacks beside it. */
  const versionText = (program, loose) => canon({ program: program || [], loose: loose || [] });

  /** Show the tab's version in its workspace. live: it came while the window was open (not the
   *  first sync of a window just opened), so what the AI changed in it flashes, once a version. */
  function loadProgram(rec, tab, live) {
    if (rec.ws.isDragging()) {                // never pull the workspace from under a drag or a pan
      clearTimeout(rec.reload);
      rec.reload = setTimeout(() => {
        const now = tabOf(rec.id);
        if (!now) return;
        // a block drag that began just before the version came: the user's drop is an edit
        if (now.program_origin === "llm" && now.program_rev === rec.programRev && editing(rec)) {
          rec.held = now.program_rev;
          rec.heldBack = 0;
          renderHeld(rec);
          return;
        }
        if (rec.held) { rec.held = null; renderHeld(rec); }   // the newest version loads
        loadProgram(rec, now, live);
      }, 250);
      return;
    }
    const cur = shownTab();
    useSession(tab);
    Blockly.Events.disable();
    let view;
    try {
      view = WB.loadProgram(rec.ws, tab.program || [], tab.loose);
    } finally {
      Blockly.Events.enable();
      if (cur && cur.id !== tab.id) useSession(cur);
    }
    keepView(rec, view);
    rec.ws.clearUndo();                       // Ctrl+Z is for hand edits; the ↶ button walks versions
    noteMain(rec);
    rec.lastSent = versionText(WB.workspaceToProgram(rec.ws), WB.looseStacks(rec.ws));
    if (rec.markSaved && tab.program_rev > 0) { rec.savedVer = rec.lastSent; rec.markSaved = false; }
    markLoose(rec);
    markRefs(rec);                            // the blocks were made again
    const flash = tab.flash || [];
    if (live && tab.program_origin === "llm" && flash.length && rec.flashRev !== tab.program_rev) {
      rec.flashRev = tab.program_rev;
      // the AI wrote the program shown: a folded column opens, so its blocks can be seen flashing
      if (wb.pane && wb.pane.tabId === tab.id && wb.pane.progShut && !progEmpty(rec)) setProg(wb.pane, true);
      flash.forEach((id) => flashBlock(rec.ws.getBlockById(id)));
      if (wb.pane && wb.pane.tabId === tab.id) toast(t("ai_updated"));
    }
    // a tab the page made with a program (a run's "try one at a time"): its column opens on it,
    // and a dock that took the whole column gives the flowsheet back, so Run program shows
    if (wb.progWant === tab.id && wb.pane && wb.pane.tabId === tab.id && !progEmpty(rec)) {
      wb.progWant = null;
      setProg(wb.pane, true);
      if (WBA.prefs().dockMode === "max") WBA.setDock(wb.pane, "split");
    }
    if (wb.pane && wb.pane.tabId === tab.id) soon("blkEmpty", () => renderBlkEmpty(wb.pane));
  }

  /** Put a workspace's view back after its blocks were made anew (a version loaded, a language
   *  switch). Only the shown one scrolls now: Blockly's scroll closes the open field editor and
   *  menu whichever workspace they are on, so an AI version loading on a tab off screen would
   *  close the one being typed in here (and the next Backspace would delete its block). One
   *  off screen keeps the view it had when last shown (rec.view) for showIn. */
  function keepView(rec, v) {
    if (!v) return;
    if (wb.pane && wb.pane.tabId === rec.id) rec.ws.scroll(v.x, v.y);
    else if (!rec.view) rec.view = v;
  }

  /** The user is in the middle of an edit on the shown workspace: a block is being dragged, a
   *  field's editor or a menu is open, or an edit waits its 450 ms to go out. A version from
   *  the AI then waits too. Panning the canvas is no edit (loadProgram waits for it to end). */
  function editing(rec) {
    if (!wb.pane || wb.pane.tabId !== rec.id) return false;   // a workspace off screen has no editor open
    return !!rec.timer || rec.el.classList.contains("blk-drag") || Blockly.WidgetDiv.isVisible() || Blockly.DropDownDiv.isVisible();
  }

  /** Show the AI's version held off screen (the pill's Load): editors close, and an edit not
   *  sent yet is dropped (the pill's tooltip says so). live: it flashes and says so (not for
   *  a tab being left, where nobody would see it). */
  function loadHeld(rec, live = true) {
    const tab = tabOf(rec.id);
    if (!rec.held || !tab) return;
    Blockly.WidgetDiv.hide();
    Blockly.DropDownDiv.hideWithoutAnimation();
    clearTimeout(rec.timer);
    rec.timer = 0;
    rec.held = null;
    loadProgram(rec, tab, live);
    renderHeld(rec);
  }
  /** Before the program is shown elsewhere or run: an edit of the user's goes out (then theirs
   *  is the newest and the AI's one step back), else the AI's version held is loaded. */
  function settleHeld(rec, live = true) {
    if (!rec.held) return;
    sendProgram(rec);                            // an edit that goes out lets go of the held version
    if (rec.held) loadHeld(rec, live);
  }

  /** The pill beside the block capsule: the AI's version held (Load), or for six seconds after
   *  the user's edit went out over it, where it is now. */
  function renderHeld(rec) {
    const pane = wb.pane;
    if (!pane || pane.tabId !== rec.id) return;
    const el = pane.q(".blk-held"), back = !rec.held && rec.heldBack && Date.now() - rec.heldBack < 6000;
    el.classList.toggle("hidden", !rec.held && !back);
    el.classList.toggle("back", !!back);
    if (rec.held || back) {
      el.querySelector(".hi use").setAttribute("href", `#i-${back ? "undo" : "sparkle"}`);
      el.querySelector(".ht").textContent = t(back ? "held_back" : "held_new");
      el.title = back ? t("tip_held_back") : t("tip_held");
    }
    if (back) {
      clearTimeout(rec.heldTimer);
      rec.heldTimer = setTimeout(() => renderHeld(rec), 6000 - (Date.now() - rec.heldBack) + 20);
    }
    fitHeld(pane);
  }
  /** Where the pill goes: beside the capsule, words and all, while the canvas has the room
   *  (right of the category list); a held version's with a short label where only that fits
   *  (.compact: the sparkle, "AI version" and Load, in the AI's colour; the full words are
   *  its tooltip), so it keeps off the start block at the top left; else under the capsule.
   *  There a long label (English, a narrow canvas) could reach over the start block's cap:
   *  its words then wrap in the room right of the cap, two lines at most, or go (.bare; the
   *  tooltip keeps them). Measured, as the room goes by the list's width and the language.
   *  The view does not move out of the pill's way: that would close the field editor a held
   *  version waits on. */
  function fitHeld(pane) {
    const el = pane.q(".blk-held"), bar = pane.q(".blk-bar"), rec = wb.recs.get(pane.tabId);
    el.classList.remove("compact", "bare", "wrap");
    el.style.maxWidth = "";
    bar.classList.remove("stack");
    if (el.classList.contains("hidden") || !rec) return;
    const back = el.classList.contains("back"), ht = el.querySelector(".ht"), words = t(back ? "held_back" : "held_new");
    ht.textContent = words;
    const tb = rec.el.querySelector(".blocklyToolbox");
    const left = (tb ? tb.getBoundingClientRect().right : pane.q(".blockly").getBoundingClientRect().left) + 4;
    const fits = () => el.getBoundingClientRect().left >= left;
    if (fits()) return;
    if (!back) {
      el.classList.add("compact");
      ht.textContent = t("held_short");
      if (fits()) return;
      el.classList.remove("compact");
      ht.textContent = words;
    }
    bar.classList.add("stack");
    const start = rec.ws.getTopBlocks(false).find((x) => x.type === "wb_start");
    const cap = start && start.pathObject.svgPath.getBoundingClientRect(), r = el.getBoundingClientRect();
    if (!cap || cap.right <= r.left || cap.left >= r.right || cap.bottom <= r.top || cap.top >= r.bottom) return;
    el.classList.add("wrap");
    el.style.maxWidth = `${Math.floor(r.right - cap.right - 6)}px`;
    if (el.getBoundingClientRect().height <= 46 && el.scrollWidth <= el.clientWidth + 1) return;
    el.classList.remove("wrap");
    el.style.maxWidth = "";
    el.classList.add("compact", "bare");
  }

  // ------------------------------------------------------------------ the block canvas
  /** Fit the whole program in view, never larger than 100% (a short program is not blown up)
   *  nor smaller than FIT_LEAST, below which its words stop reading. One too long to fit at
   *  that shows as much of itself as reads, from its start, not from its middle. */
  const FIT_LEAST = 0.5;
  function fitProgram(rec) {
    const ws = rec.ws;
    if (!ws.getTopBlocks(false).length) return;
    ws.zoomToFit();
    if (ws.scale > 1) ws.setScale(1);
    else if (ws.scale < FIT_LEAST) ws.setScale(FIT_LEAST);
    const m = ws.getMetrics(), b = ws.getBlocksBoundingBox(), s = ws.scale;
    if ((b.bottom - b.top) * s > m.viewHeight || (b.right - b.left) * s > m.viewWidth) toStart(rec);
    else ws.scrollCenter();
  }

  /** Scroll the start block to the top left of the view, where a program is read from: near
   *  the top, or under the block capsule (and a held version's pill) where they would sit on
   *  its cap or its first steps. (Beside them, as in most windows, the room under the capsule
   *  is a row more of the program.) */
  function toStart(rec) {
    const ws = rec.ws, start = ws.getTopBlocks(false).find((x) => x.type === "wb_start");
    if (!start) return;
    const r = start.getBoundingRectangle(), s = ws.scale, go = (top) => ws.scroll(20 - r.left * s, top - r.top * s);
    const bar = wb.pane && wb.pane.tabId === rec.id && wb.pane.q(".blk-bar").getBoundingClientRect();
    if (!bar || !bar.height) { go(52); return; }
    go(16);
    const over = [...wb.pane.q(".blk-bar").children].filter((el) => !el.classList.contains("hidden"))
      .map((el) => el.getBoundingClientRect()).filter((b) => b.width);
    const low = Math.max(...over.map((b) => b.bottom)) + 8;
    const hit = [start].concat(start.getDescendants(false).slice(1, 8)).some((b) => {
      const c = b.pathObject.svgPath.getBoundingClientRect();
      return c.top < low && over.some((o) => c.left < o.right + 8 && o.left - 8 < c.right);
    });
    if (hit) go(Math.round(bar.bottom - ws.getParentSvg().getBoundingClientRect().top) + 8);
  }

  /** A stack beside the program (not under the start block, not a procedure) does not run: it
   *  shows faded (.wb-loose; not while it is dragged). Counted once a frame at most. */
  function looseTops(rec) {
    return rec.ws.getTopBlocks(false).filter((x) => x.type !== "wb_start" && x.type !== "wb_proc" && !x.isInsertionMarker());
  }
  function markLoose(rec) {
    const now = new Set(looseTops(rec).map((x) => x.getSvgRoot()).filter(Boolean));
    rec.ws.getParentSvg().querySelectorAll(".wb-loose").forEach((el) => { if (!now.has(el)) el.classList.remove("wb-loose"); });
    now.forEach((el) => el.classList.add("wb-loose"));
  }
  /** An edit made the main program longer (a step dropped in): a procedure it now reaches
   *  moves down out of its way (WB.clearOfMain), as when a longer version loads. Blockly has
   *  nudged such a procedure aside already (its bump, for blocks whose connections line up):
   *  it goes back first, so it moves straight down in its column; one not pushed keeps the
   *  nudge. These moves are no edit (Ctrl+Z undoes the drop, which puts the nudged one back).
   *  Checked once a frame, not mid-drag. */
  function roomForMain(rec) {
    if (rec.ws.isDragging()) return;
    Blockly.renderManagement.triggerQueuedRenders(rec.ws);   // measured at their final sizes
    if (WB.mainEnd(rec.ws) > rec.mainEnd) {
      Blockly.Events.disable();
      try {
        const nudged = rec.ws.getTopBlocks(false).filter((b) => b.type === "wb_proc" && rec.procAt.has(b.id))
          .map((b) => ({ b, at: b.getRelativeToSurfaceXY(), was: rec.procAt.get(b.id) }))
          .filter((p) => p.at.x !== p.was.x || p.at.y !== p.was.y);
        nudged.forEach((p) => p.b.moveBy(p.was.x - p.at.x, p.was.y - p.at.y));
        const pushed = WB.clearOfMain(rec.ws);
        nudged.filter((p) => !pushed.has(p.b)).forEach((p) => p.b.moveBy(p.at.x - p.was.x, p.at.y - p.was.y));
      } finally { Blockly.Events.enable(); }
    }
    noteMain(rec);
  }
  /** What roomForMain compares an edit with: the main program's bottom, and each procedure's place. */
  function noteMain(rec) {
    rec.mainEnd = WB.mainEnd(rec.ws);
    rec.procAt = new Map(rec.ws.getTopBlocks(false).filter((b) => b.type === "wb_proc").map((b) => [b.id, b.getRelativeToSurfaceXY()]));
  }

  /** An empty program: a quiet line under the start block says where the first block goes. An
   *  HTML overlay at the start block's place, moved with the view, gone once a step is attached. */
  function renderBlkEmpty(pane) {
    const rec = pane && wb.recs.get(pane.tabId), el = pane && pane.q(".blk-empty");
    if (!el) return;
    const start = rec && steps(rec).main === 0 && rec.ws.getTopBlocks(false).find((x) => x.type === "wb_start");
    const root = start && start.getSvgRoot();
    if (!root) { el.classList.add("hidden"); return; }
    const box = pane.q(".blockly").getBoundingClientRect(), r = root.getBoundingClientRect();
    const view = rec.ws.getParentSvg().getBoundingClientRect(), left = r.left - box.left, top = r.bottom - box.top + 6;
    // the category named as the list shows it: its short label in a narrow list
    const text = t("empty_prog", rec.el.classList.contains("narrow") ? t("cs_run") : Blockly.Msg.WB_CAT_RUN || "");
    if (el.textContent !== text) el.textContent = text;
    // only while its place is in view (right of the category list, inside the card)
    const tb = rec.ws.getToolbox(), minX = view.left - box.left + (tb ? tb.getWidth() : 0);
    el.classList.toggle("hidden", left < minX - 4 || top < 0 || top > box.height - 30 || left > box.width - 80);
    el.style.transform = `translate(${Math.round(left)}px, ${Math.round(top)}px)`;
    el.style.maxWidth = `${Math.max(60, Math.round(box.width - left - 16))}px`;
  }

  // ------------------------------------------------------------------ run, check, stop
  // A press shows at once: the buttons go quiet and the capsule says "Sending…" until the
  // server's state answers (the run's status or start time changes). Five seconds without an
  // answer: "The server did not answer", and the buttons come back.

  /** The program's steps: those under the start block (main), and those that run -- the steps
   *  under it not turned off (a proposal's unticked rows, a block turned off) and the procedures (all,
   *  the count the run bar says); any: every one, turned off or not. */
  function steps(rec) {
    const tops = rec.ws.getTopBlocks(false), start = tops.find((x) => x.type === "wb_start");
    let main = 0, on = 0;
    for (let b = start && start.getNextBlock(); b; b = b.getNextBlock()) { main++; if (b.isEnabled()) on++; }
    const procs = tops.filter((x) => x.type === "wb_proc").length;
    return { main, all: on + procs, any: main + procs };
  }
  /** No program at all: no step, no procedure, no loose stack (the program column folds). */
  const progEmpty = (rec) => steps(rec).any === 0 && !looseTops(rec).length;

  // ------------------------------------------------------------------ program edits -> server
  /** Send the tab's version (program and loose stacks) if it changed. Never mid-drag: a
   *  block being dragged is out of the program for a moment, and that is no version. */
  function sendProgram(rec) {
    if (!rec) return;
    clearTimeout(rec.timer);
    rec.timer = 0;
    if (rec.ws.isDragging()) {
      rec.timer = setTimeout(() => { rec.timer = 0; sendProgram(rec); }, 300);
      return;
    }
    const program = WB.workspaceToProgram(rec.ws), loose = WB.looseStacks(rec.ws);
    const text = versionText(program, loose);
    if (text === rec.lastSent) return;
    rec.lastSent = text;
    wb.post({ type: "program", tab: rec.id, program, loose });
    if (rec.held) { rec.held = null; rec.heldBack = Date.now(); renderHeld(rec); }   // the user's edit is the newest now
  }

  /** The block capsule (and a held version's pill) step aside while the block flyout is open
   *  over them, and so do the empty program's line and the run cursor. */
  function shadeTools(rec) {
    const box = rec.ws.getToolbox(), fly = box && box.getFlyout(), open = !!(fly && fly.isVisible());
    rec.el.classList.toggle("fly-open", open);   // the canvas's scrollbars would cross the flyout
    if (!wb.pane || wb.pane.tabId !== rec.id) return;
    wb.pane.q(".blk-bar").classList.toggle("shade", open);
    wb.pane.q(".blk-empty").classList.toggle("shade", open);
    wb.pane.q(".run-cur").classList.toggle("shade", open);
    wb.pane.q(".step-card").classList.toggle("shade", open);   // (paused: the card beside the step)
  }

  /** The category list's lens, on the capsule that hugs the categories (not on Blockly's
   *  full-height strip, whose size Blockly writes): only the shown workspace has one (at most
   *  six lenses a pane), made again when Blockly rebuilds the list (a language switch). */
  function railLens(pane) {
    if (pane.rail) { pane.rail.dispose(); pane.rail = null; }
    const rec = pane.tabId && wb.recs.get(pane.tabId);
    const group = rec && rec.ws.getInjectionDiv().querySelector(".blocklyToolbox .blocklyToolboxCategoryGroup");
    if (group) pane.rail = lens(group, { bezel: 16, scale: 42, blur: 14 });
  }
  /** A category list taller than its room scrolls, and fades at the edge where more lies. */
  function railFade(rec) {
    const g = rec.ws.getInjectionDiv().querySelector(".blocklyToolboxCategoryGroup");
    if (!g) return;
    if (!g.wbFade) { g.wbFade = true; g.addEventListener("scroll", () => railFade(rec), { passive: true }); }
    g.classList.toggle("fb", g.scrollTop + g.clientHeight < g.scrollHeight - 1);
    g.classList.toggle("ft", g.scrollTop > 1);
  }

  /** Blockly's category list, dressed: each category's colour (Blockly keeps it in its row's
   *  border, which the stylesheet hides) tints its icon chip (the icon is a CSS mask, by the
   *  category's key: WB.toolbox), its short label for a narrow list, and its tooltip: what the
   *  category is for (i18n.js cd_<key>), after its name in a narrow list, which shows only the
   *  short label; and a glass drop that slides to the open category. Blockly rebuilds the list
   *  on a language switch. Its lens is the shown pane's (railLens). */
  function dressToolbox(ws) {
    const box = ws.getInjectionDiv().querySelector(".blocklyToolbox");
    const group = box && box.querySelector(".blocklyToolboxCategoryGroup");
    if (!group) return;
    const narrow = !!box.closest(".ws.narrow");
    group.querySelectorAll(".blocklyToolboxCategory").forEach((row) => {
      row.style.setProperty("--cat", row.style.borderLeftColor || row.style.borderRightColor || "#9aa3b1");
      const ico = row.querySelector(".wbi"), key = ico && [...ico.classList].find((c) => c.startsWith("wbi-"));
      const content = row.querySelector(".blocklyTreeRowContentContainer"), label = row.querySelector(".blocklyToolboxCategoryLabel");
      if (!key || !content) return;
      const short = t(`cs_${key.slice(4)}`), about = t(`cd_${key.slice(4)}`);
      if (content.dataset.short !== short) content.dataset.short = short;
      const tip = narrow && label ? `${label.textContent}\n${about}` : about;   // (a description may hold a colon)
      if (row.title !== tip) row.title = tip;
    });
    let drop = group.querySelector(".tb-glide");
    if (!drop) { drop = Object.assign(document.createElement("i"), { className: "tb-glide glide gy" }); group.prepend(drop); }
    const sel = group.querySelector(".blocklyToolboxSelected");
    if (sel) drop.style.setProperty("--cat", sel.style.getPropertyValue("--cat"));
    glide(drop, sel);
  }
  /** A block just changed (by the AI while the window is open, or dropped from the inspector)
   *  flashes: a copy of its outline over it, stroked in the run colour, whose opacity goes
   *  0 → 1 → 0 twice in 900 ms, then is removed. The block's own paint is never touched; this
   *  is the one animation inside an SVG (style.css, rule 3). */
  function flashBlock(blk) {
    const root = blk && blk.getSvgRoot && blk.getSvgRoot();
    const path = root && root.querySelector(":scope > .blocklyPath");
    if (!path) return;
    const ring = document.createElementNS("http://www.w3.org/2000/svg", "path");
    ring.setAttribute("d", path.getAttribute("d") || "");
    ring.setAttribute("class", "wb-flash");
    path.after(ring);
    const done = () => ring.remove();
    ring.addEventListener("animationend", done, { once: true });
    setTimeout(done, 1200);
  }

  Object.assign(WBA, { dressToolbox, editing, fitHeld, fitProgram, flashBlock, keepView, loadHeld,
    loadProgram, looseTops, markLoose, noteMain, progEmpty, railFade, railLens, renderBlkEmpty, renderHeld,
    roomForMain, sendProgram, settleHeld, shadeTools, steps, toStart, versionText });
})();
