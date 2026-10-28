/* Stepping through a program. Step (the run bar, a plain tab's; a
 * proposal's is its card's "Step through") runs the program so that it pauses before every step outside a
 * loop; a breakpoint pauses any run there. While the server holds a run paused (tab.run.paused
 * {at, n, depth, why step|break, next, loc, where}):
 *
 *   - the run bar says "Paused before step 3" and offers Stop, Continue and Run next step (F10);
 *     a press waits for the server's next pause (or 8 s) before the buttons act again;
 *   - a card beside the paused step (in the block canvas, where the run cursor was) says what the
 *     next step does -- its current → new value, a condition as it stands (its variable named),
 *     the last run -- where it acts in Aspen and its problems. A step on a field drawn on the
 *     flowsheet has Edit value: the field picked in the inspector (an edit while paused is the
 *     user's, and kept: its tooltip). Otherwise it only informs (the run buttons are the bar's),
 *     lets the pointer through, is placed clear of the block capsule, moves with the view at
 *     once and never animates on its own;
 *   - the paused step keeps the run outline (a little heavier, no animation).
 *
 * Breakpoints (tab.breaks, event breaks {ids}): a click on a step's left edge, or its menu's
 * "Add breakpoint", sets one (a red dot left of the step, its tooltip saying a click removes it);
 * again, it goes. A step inside a loop cannot have one (a loop runs whole): its menu item says
 * so, greyed. A faint ring shows where the dot would go while the pointer rests on a step's left
 * edge. Feature-detected: stepping.
 *
 * A run waiting at a manual step (tab.run.wait; app-turn.js) is a pause here too
 * (why "turn", at the step it waits in): the run bar holds Stop and Done instead, the card beside
 * the step is the manual step's, F10 presses Done, and the inspector writes.
 *
 *   pausedOf(tab)             the run's pause, where the server steps, or its wait for the user, else null
 *   pausedOn(session)         a tab on the session is paused (the inspector may write then)
 *   stepPress(action)         the shown tab's next | cont (waiting: Done); false when it is not paused
 *   renderStepBar(pane)       the run bar's Step, Continue, Run next step; the breakpoints
 *   placeStepCard(pane, o)    the cursor card beside the paused step (renderCursor), o null: hidden
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { busy, canon, esc, fmtVal, icon, isObj, shownTab, t, tabOf, toast, wb } = WBA;
  const { blocker, findStmt, gcNow, gotoChange, probHtml, propOf, renderRunbar, renderTurn, rowTarget, stepWords, turnCardHtml, turnOff,
    turnPress, waitOf } = WBA.later;

  const PRESS_MS = 8000;                               // a press not answered in this long: the buttons act again
  const BRK_MS = 8000;                                 // a breakpoint set here, not yet in the state: kept this long
  const LOOP_T = ["wb_sweep", "wb_seek", "wb_repeat", "wb_until", "wb_optimize"];
  const DOT = { cx: -9, cy: 14, r: 5.5 };              // the red dot, in the step's own units (left of it)

  // ------------------------------------------------------------------ the pause
  const pausedOf = (tab) => {
    const r = tab && tab.run, p = r && r.status === "running" ? r.paused : null;
    if (isObj(p)) return p;
    const w = waitOf(tab);                               // waiting for the user at a manual step
    return w ? { at: w.sid, n: w.n, why: "turn", since: w.t, loc: w.loc, where: w.where, wait: w } : null;
  };
  const pausedOn = (session) => ((wb.state && wb.state.tabs) || []).some((x) => x.session === session && !!pausedOf(x));
  const keyOf = (p) => `${p.at}|${p.since}|${p.n}`;
  /** A press sent and not yet answered by a new pause (PRESS_MS at most). */
  const waiting = (rec, p) => !!rec.stepSent && rec.stepSent.key === keyOf(p) && Date.now() - rec.stepSent.at < PRESS_MS;

  /** Run next step (next) or Continue (cont) on the shown tab: false when it is not paused. */
  function stepPress(action) {
    const tab = shownTab(), rec = tab && wb.recs.get(tab.id), p = pausedOf(tab);
    if (!p || !rec) return false;
    if (p.why === "turn") return turnPress("done");    // (F10 at a manual step: the value typed, then Done)
    if (!wb.connected) { toast(t("why_off")); return true; }
    if (waiting(rec, p) || (rec.pending && rec.pending.kind === "stop")) return true;
    rec.stepSent = { key: keyOf(p), at: Date.now() };
    wb.post({ type: "step", tab: tab.id, action: action === "cont" ? "cont" : "next" });
    setTimeout(() => { if (wb.pane && wb.pane.tabId === tab.id) renderRunbar(); }, PRESS_MS + 50);
    renderRunbar();
    return true;
  }

  // ------------------------------------------------------------------ the run bar
  /** Step on a plain tab while nothing runs; while paused, Continue and Run next step
   *  after Stop (Check gives way). Also marks the breakpoints of the shown tab. */
  function renderStepBar(pane) {
    const tab = pane && tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id);
    if (!tab || !rec) return;
    const bar = pane.q(".prog-bar"), p = pausedOf(tab), turn = !!p && p.why === "turn";
    const step = bar.querySelector('[data-a="step"]'), btns = bar.querySelector(".stepbtns");
    if (!step || !btns) return;
    const show = !propOf(tab) && !busy(tab);
    step.classList.toggle("hidden", !show);
    if (show) {
      const why = rec.pending && rec.pending.kind !== "stop" ? { long: t("st_sending") } : blocker(tab, rec);
      step.disabled = !!why;
      step.title = why ? why.long : t("tip_step");
      step.setAttribute("aria-label", t("btn_step"));   // (a narrow column shows its icon only)
    }
    // Once a run has paused, its buttons keep their places until it ends: while a step runs
    // (not paused) Continue and Run next step stay, greyed -- so Stop never slides into the place
    // of the button just pressed (a quick second click).
    const run = tab.run || {}, key = run.status === "running" && !run.dry_run ? `${run.started}` : "";
    if (p && !turn && key) rec.stepRun = key;
    const between = !p && !!key && rec.stepRun === key && busy(tab);
    if (!key) rec.stepRun = null;
    bar.classList.toggle("paused", !!p);
    bar.classList.toggle("stepping", (!!p && !turn) || between);
    btns.classList.toggle("hidden", !(p || between) || turn);   // (a manual step: Done instead, app-turn.js)
    if ((p && !turn) || between) {
      const off = !wb.connected ? t("why_off") : between ? t("st_step_running") : waiting(rec, p) ? t("st_sending")
        : rec.pending && rec.pending.kind === "stop" ? t("st_stopping") : "";
      btns.querySelectorAll("button").forEach((b) => {
        const nx = b.dataset.a === "step_next";
        b.disabled = !!off;
        b.title = off || t(nx ? "tip_step_next_k" : "tip_step_cont");
        b.setAttribute("aria-label", t(nx ? "btn_step_next" : "go_on"));
      });
    }
    syncBreaks(tab, rec);
    markBreaks(tab, rec);
    renderTurn(pane);
  }

  // ------------------------------------------------------------------ the cursor card
  const OUTCOME = { ok: "step_last_ok", warn: "step_last_warn", error: "step_last_error" };
  /** An if's left side by name (html): a variable, a field in short words, an expression. */
  function leftName(tab, left) {
    if (!isObj(left)) return "";
    if (typeof left.var === "string" && left.var) return esc(left.var);
    if (typeof left.path === "string" && left.path) {
      return WBL.html(WBL.of(left.path, null, tab.session), "short");
    }
    const x = String(left.expr ?? "").trim();
    return x ? `<code class="pr-x">${esc(x.length > 40 ? `${x.slice(0, 39)}…` : x)}</code>` : "";
  }
  const PH = "\u0001";                                 // (a place for html in words escaped)
  /** What the card says of the next step (html): its words, its values, where, its problems;
   *  on a field drawn on the flowsheet, Edit value. */
  function cardHtml(tab, p) {
    let nx = isObj(p.next) ? Object.assign({}, p.next) : null;
    if (!nx || !nx.kind) {                              // (no preview read: the statement itself)
      const st = findStmt(tab.program, p.at) || {};
      nx = { id: p.at, kind: st.do || "", path: typeof st.path === "string" ? st.path : undefined };
    }
    const extra = [], nw = isObj(nx.new) ? nx.new : null;
    if (nw && nw.expr != null) {                         // an expression: its value now, and the expression
      if (nw.value != null) { nx.new = { value: nw.value, unit: nw.unit || null }; extra.push(esc(t("step_expr", nw.expr))); }
      else { delete nx.new; extra.push(esc(t("step_nocalc", nw.why || nw.expr))); }
    }
    if (nx.kind === "if" && isObj(nx.cond)) {
      const c = nx.cond, hit = c.hit === true ? t("step_cond_yes") : c.hit === false ? t("step_cond_no") : t("step_cond_unk");
      const name = leftName(tab, (findStmt(tab.program, p.at) || {}).left), now = c.left == null ? "—" : fmtVal(c.left);
      const left = name ? esc(t("step_cond_v", PH, now)).replace(PH, name) : esc(now);
      extra.push(esc(t("step_cond", PH, c.op || ">", fmtVal(c.right), hit)).replace(PH, left));
    }
    if (nx.kind === "run") {
      if (nx.reinit) extra.push(esc(t("step_reinit")));
      if (OUTCOME[nx.last]) extra.push(esc(t("step_last", t(OUTCOME[nx.last]))));
    }
    if (nx.kind === "call" && isObj(nx.what) && Array.isArray(nx.what.args) && nx.what.args.length) {
      extra.push(esc(t("step_args", nx.what.args.map((a) => fmtVal(a)).join(", "))));
    }
    if (["sweep", "repeat", "until", "seek", "optimize"].includes(nx.kind)) extra.push(esc(t("step_loop")));
    const where = p.where ? String(p.where) : nx.path ? WBL.full(nx.path) : "";
    const probs = (Array.isArray(nx.problems) ? nx.problems : []).filter(isObj).slice(0, 3).map((q) => probHtml(q, tab.session)).join("");
    const hit = nx.path ? rowTarget(tab, { path: nx.path }) : null;   // (a field on the flowsheet: Edit value)
    const go = hit ? `<div class="sc-act"><button class="sc-go" data-kind="${esc(hit.target.kind)}" data-name="${esc(hit.target.name)}"`
      + ` data-path="${esc(hit.path)}" title="${esc(t("tip_step_edit"))}">${icon("pen")}<span class="bt">${esc(t("step_edit"))}</span></button></div>` : "";
    return `<div class="sc-h">${icon("step")}<b>${esc(t("step_card_next", p.n ?? "?"))}</b>`
      + (p.why === "break" ? `<span class="sc-brk"><i></i>${esc(t("step_card_brk"))}</span>` : "") + `</div>`
      + `<div class="sc-w">${stepWords(tab, nx)}</div>`
      + extra.map((h) => `<div class="sc-x">${h}</div>`).join("")
      + (where ? `<div class="sc-at">${esc(t("in_aspen", where))}</div>` : "")
      + probs + go;
  }
  /** The card beside the paused step: o {blk, path, box, bar, minX, scale} from renderCursor (the
   *  step's box, the canvas's, the block capsule's), null for none. Right of the step's own shape,
   *  level with its top; where the canvas has no room there, over the step (on the steps already
   *  done), else under its first row (a manual step's: under the whole step, its rows are read);
   *  clear of the capsule; hidden while the step is out of view. Returns whether it shows. */
  function placeStepCard(pane, o) {
    const card = pane && pane.q(".step-card"), tab = pane && tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id);
    if (!card) return false;
    const p = o && tab ? pausedOf(tab) : null;
    if (rec) rec.el.classList.toggle("paused", !!p && wb.connected);
    if (!p || (p.why === "group" && gcNow(tab))) {      // (a group's pause: the group card says it, app-group.js)
      if (!card.classList.contains("hidden")) card.classList.add("hidden");
      card._sig = null;
      return false;
    }
    if (!card.dataset.wired) {                         // Edit value: the field picked in the inspector, the flowsheet at it
      card.dataset.wired = "1";
      card.addEventListener("click", (ev) => {
        const b = ev.target.closest(".sc-go"), y = ev.target.closest(".yt-btn");
        if (b && wb.pane === pane) gotoChange(pane, { kind: b.dataset.kind, name: b.dataset.name }, b.dataset.path || null);
        if (y && !y.disabled && wb.pane === pane) turnPress(y.dataset.yt === "answer" ? "answer" : "done", y.dataset.yt === "force");
      });
    }
    const turn = p.why === "turn";                     // (a manual step's card: app-turn.js)
    const sig = canon([I18N.lang, tab.id, p, window.WBL ? WBL.ver : 0, turn ? turnOff(tab) : ""]);
    const fresh = card.classList.contains("hidden");
    card.classList.remove("hidden");
    card.classList.toggle("turn", turn);
    if (card._sig !== sig) { card._sig = sig; card.innerHTML = turn ? turnCardHtml(tab, p.wait) : cardHtml(tab, p); }
    // (t0: the canvas's own top in the block card, under the proposal's window where it sits over the blocks)
    const { path, box, bar, minX, scale } = o, r = path.getBoundingClientRect(), t0 = o.top || 0;
    const W = card.offsetWidth, H = card.offsetHeight, rowH = Math.min(r.height, 48 * scale);
    const hits = (x0, y0) => !!bar.height && box.left + x0 + W > bar.left - 6 && box.left + x0 < bar.right + 6
      && box.top + y0 < bar.bottom + 6 && box.top + y0 + H > bar.top - 6;
    let x = r.right - box.left + 12, y = r.top - box.top - 2;
    if (x + W > box.width - 10) {                      // no room at its right: over it, else under its first row
      x = Math.max(minX + 8, Math.min(box.width - W - 10, r.left - box.left + 24));
      y = r.top - box.top - H - 6;
      if (turn) {
        // a manual step's rows (its hint, check and answer) stay in sight: over it, left of the
        // capsule where that is in the way, else under the whole step
        const x2 = Math.max(minX + 8, bar.left - box.left - 7 - W);
        if (y >= t0 + 6 && hits(x, y) && !hits(x2, y)) x = x2;
        if (y < t0 + 6 || hits(x, y)) y = r.bottom - box.top + 6;
      } else if (y < t0 + 6 || hits(x, y)) y = r.top - box.top + rowH + 6;
    }
    if (hits(x, y)) y = bar.bottom - box.top + 8;
    y = Math.max(t0 + 6, Math.min(y, box.height - H - 6));
    const off = r.bottom < box.top + t0 + 4 || r.top > box.bottom - 12 || r.right < box.left + minX || r.left > box.right - 8;
    card.classList.toggle("off", off);
    card.style.transform = `translate3d(${Math.round(x)}px, ${Math.round(y)}px, 0)`;
    if (fresh && !off) card.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 160, easing: "cubic-bezier(.2, .8, .2, 1)" });
    return true;
  }

  // ------------------------------------------------------------------ breakpoints
  /** A block's worth as a breakpoint: null (not a step of the program: a value, a definition, a
   *  stack beside the program, the flyout), "loop" (inside a loop: it runs whole) or "ok". */
  function brkKind(blk) {
    if (!blk || !blk.wbStep || blk.isInFlyout || blk.isInsertionMarker() || blk.type === "wb_def" || blk.type === "wb_proc") return null;
    const root = blk.getRootBlock();
    if (!root || (root.type !== "wb_start" && root.type !== "wb_proc")) return null;
    for (let s = blk.getSurroundParent(); s; s = s.getSurroundParent()) if (LOOP_T.includes(s.type)) return "loop";
    return "ok";
  }
  function ofWs(ws) {
    for (const rec of wb.recs.values()) if (rec.ws === ws) { const tab = tabOf(rec.id); return tab ? { tab, rec } : null; }
    return null;
  }
  /** The tab's breakpoints: those set here and not yet in the state, else the state's. */
  const breaksOf = (tab, rec) => (rec.brkWant ? rec.brkWant.ids : Array.isArray(tab.breaks) ? tab.breaks.filter((x) => typeof x === "string") : []);
  function syncBreaks(tab, rec) {
    const w = rec.brkWant;
    if (w && (canon(tab.breaks || []) === canon(w.ids) || Date.now() - w.at > BRK_MS)) rec.brkWant = null;
  }
  function toggleBreak(tab, rec, id) {
    if (!wb.connected) { toast(t("why_off")); return; }
    const cur = breaksOf(tab, rec), on = !cur.includes(id);
    const ids = on ? cur.concat(id).slice(-50) : cur.filter((x) => x !== id);
    rec.brkWant = { ids, at: Date.now() };
    wb.post({ type: "breaks", tab: tab.id, ids });
    markBreaks(tab, rec);
    hint(wb.pane, null);
  }
  /** The red dots: a circle inside each breakpoint's step (it moves and scales with it; its
   *  tooltip: a click removes it), the step's root marked wb-brk; made again where a version
   *  loaded made the blocks anew. */
  function markBreaks(tab, rec) {
    const want = new Set(breaksOf(tab, rec)), had = rec.brkDots || (rec.brkDots = new Map());
    const tip = t("brk_set");
    had.forEach((dot, id) => {
      const blk = rec.ws.getBlockById(id), root = blk && blk.getSvgRoot();
      if (want.has(id) && root && dot.parentNode === root) {
        if (dot.firstChild && dot.firstChild.textContent !== tip) dot.firstChild.textContent = tip;   // (the language switched)
        return;
      }
      dot.remove();
      if (root) root.classList.remove("wb-brk");
      had.delete(id);
    });
    want.forEach((id) => {
      if (had.has(id)) return;
      const blk = rec.ws.getBlockById(id), root = blk && !blk.isInFlyout && blk.getSvgRoot();
      if (!root) return;
      const NS = "http://www.w3.org/2000/svg", dot = document.createElementNS(NS, "circle"), title = document.createElementNS(NS, "title");
      dot.setAttribute("class", "wb-brk-dot");
      Object.entries(DOT).forEach(([k, v]) => dot.setAttribute(k, String(v)));
      title.textContent = tip;
      dot.appendChild(title);
      root.insertBefore(dot, root.firstChild);
      root.classList.add("wb-brk");
      had.set(id, dot);
    });
  }
  /** A step's left edge under a point (client px): the step's block, or null. */
  function edgeOf(rec, blk, x, y) {
    if (brkKind(blk) !== "ok") return null;
    const path = blk.pathObject && blk.pathObject.svgPath, r = path && path.getBoundingClientRect();
    if (!r || !r.width) return null;
    const s = rec.ws.scale, dx = x - r.left, dy = y - r.top;
    return dx >= (DOT.cx - DOT.r - 2) * s && dx <= 9 && dy >= 0 && dy <= Math.min(r.height, 44 * s) ? r : null;
  }
  /** The faint ring where a step's dot would go (r: its box), or none. */
  function hint(pane, r, rec) {
    const el = pane && pane.q(".brk-hint");
    if (!el) return;
    if (!r) { if (!el.classList.contains("hidden")) el.classList.add("hidden"); return; }
    const box = pane.q(".blockly").getBoundingClientRect(), s = rec.ws.scale;
    el.style.transform = `translate3d(${Math.round(r.left - box.left + DOT.cx * s - 5)}px, ${Math.round(r.top - box.top + DOT.cy * s - 5)}px, 0)`;
    el.classList.remove("hidden");
  }
  /** The canvas's pointer: where a press started (a click on a step's edge sets its breakpoint:
   *  Blockly's own click event, so a drag is none), and the ring while it rests on an edge. */
  function wireCanvas(pane) {
    if (pane.stepWired) return;
    pane.stepWired = true;
    const area = pane.q(".blockly");
    area.addEventListener("pointerdown", (ev) => { pane.brkPt = { x: ev.clientX, y: ev.clientY, t: Date.now() }; }, { capture: true, passive: true });
    let pend = null;
    area.addEventListener("pointermove", (ev) => {
      if (pend) { pend.ev = ev; return; }
      pend = { ev };
      requestAnimationFrame(() => {
        const e = pend.ev, tab = tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id);
        pend = null;
        const g = e.target && e.target.closest ? e.target.closest("g[data-id]") : null;
        const blk = g && rec && !rec.ws.isDragging() ? rec.ws.getBlockById(g.getAttribute("data-id")) : null;
        const r = blk ? edgeOf(rec, blk, e.clientX, e.clientY) : null;
        hint(pane, r && !breaksOf(tab, rec).includes(blk.id) ? r : null, rec);
      });
    }, { passive: true });
    area.addEventListener("pointerleave", () => hint(pane, null), { passive: true });
  }
  function wireRec(rec) {
    if (rec.stepWired) return;
    rec.stepWired = true;
    rec.ws.addChangeListener((ev) => {
      if (ev.type !== Blockly.Events.CLICK || ev.targetType !== "block" || !ev.blockId) return;
      const pane = wb.pane, pt = pane && pane.brkPt, tab = tabOf(rec.id);
      if (!pane || pane.tabId !== rec.id || !pt || Date.now() - pt.t > 1500 || !tab) return;
      const blk = rec.ws.getBlockById(ev.blockId);
      if (blk && edgeOf(rec, blk, pt.x, pt.y)) toggleBreak(tab, rec, blk.id);
    });
  }

  /** The block menu's "Add breakpoint" / "Remove breakpoint" (greyed inside a loop, saying why). */
  function registerMenu() {
    const R = window.Blockly && Blockly.ContextMenuRegistry, reg = R && R.registry;
    if (!reg || reg.getItem("wb_brk")) return;
    const at = (b) => { const o = b && b.workspace ? ofWs(b.workspace) : null; return o && { ...o, on: breaksOf(o.tab, o.rec).includes(b.id) }; };
    reg.register({ id: "wb_brk", scopeType: R.ScopeType.BLOCK, weight: 5,
      displayText: (scope) => { const o = at(scope.block); return t(o && o.on ? "brk_remove" : brkKind(scope.block) === "loop" ? "brk_in_loop_menu" : "brk_add"); },
      preconditionFn: (scope) => {
        const k = brkKind(scope.block), o = k && at(scope.block);
        return !o ? "hidden" : k === "loop" && !o.on ? "disabled" : "enabled";
      },
      callback: (scope) => { const o = at(scope.block); if (o) toggleBreak(o.tab, o.rec, scope.block.id); } });
  }
  registerMenu();

  /** Wire the shown pane's canvas and tab (once each): from renderProgBar. */
  function stepWire(pane) {
    const rec = pane && wb.recs.get(pane.tabId);
    if (!pane || !rec) return;
    wireCanvas(pane);
    wireRec(rec);
  }

  Object.assign(WBA, { pausedOf, pausedOn, placeStepCard, renderStepBar: (pane) => { stepWire(pane); renderStepBar(pane); }, stepPress });
})();
