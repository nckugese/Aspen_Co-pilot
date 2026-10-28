/* The flowsheet around the drawing: what FS.render is given (fsView), the AI's marks,
 * stale results (staleAt), the stream hover card (peek), the toolbar and the selection chip
 * (renderTools, fitChip, fsMenuItems), and the edge hints (renderEdges). The annotations layer
 * ("Annotations") is app-pins.js's: fsView and renderTools only ask it.
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { changesMarks, current, esc, fslItems, icon,
    keyOf, modelSum, prefGet, prefs, prefSet, renderFslTools, sessOf, t, tabOf, usableImport,
    wb } = WBA;
  const { aspenRedraw, fitPlan, gcPlace, heatOf, heatPlan, heatPlans, heatPref, markRefs, openLegend, redrawWhy, renderPane, renderPlan } = WBA.later;

  /** How this viewer has blocks drawn: as boxes with name and type (pref wb.fs.view "boxes"),
   *  else as their equipment symbols (fs-icons.js). setView(pane, boxes) switches, for every
   *  tab: the drawing is laid out again and fitted (flowsheet.js: a new way of drawing). */
  const boxesOn = () => prefGet("wb.fs.view") === "boxes";
  function setView(pane, boxes) {
    prefSet("wb.fs.view", boxes ? "boxes" : null);
    pane.sigs = {};
    renderPane(pane);
  }

  /** What FS.render draws for the tab: its flowsheet and the layers over it; changes: the
   *  others' changes not seen yet on each block and stream (a dot, changes.js WBC.marks); pins:
   *  the annotations layer's markers (app-pins.js WBP.marks), null while it is off;
   *  view: how blocks are drawn, this viewer's pref wb.fs.view ("boxes", else their symbols);
   *  preview: a proposal's preview (app-preview.js), null when none shows;
   *  effects: a run's result tags (app-effects.js), null when none show;
   *  flows: the flow width layer's bands (app-flows.js), null while it is off;
   *  values: the stream values, with the Values layer's component line where one is chosen (app-comp.js
   *  cpVals). */
  function fsView(pane, tab) {
    const sess = sessOf(tab);
    const heat = heatOf(tab), hp = heatPref(tab);
    return { flowsheet: sess.flowsheet, notes: sess.notes, highlight: marks(tab), selection: shownSel(tab, wb.recs.get(tab.id)),
             status: sess.status, values: WBA.cpVals ? WBA.cpVals(tab, sess.values) : sess.values, showValues: prefs().values, stale: !!staleAt(tab.session), delta: runDelta(tab),
             heat: heat && hp.on ? heatPlan(heat, Math.min(hp.plan, heatPlans(heat) - 1)) : null,
             layout: current(tab.session), aspen: usableImport(tab.session), canMove: true,
             changes: changesMarks(pane, tab), pins: window.WBP ? WBP.marks(pane, tab) : null,
             view: boxesOn() ? "boxes" : "icons", preview: WBA.pvView ? WBA.pvView(pane, tab) : null,
             effects: WBA.fxView ? WBA.fxView(pane, tab) : null, flows: WBA.fwView ? WBA.fwView(pane, tab) : null };
  }

  /** What the last run moved of the values the Values layer shows (the session's run_delta, {stream: {t | p | f: [before, after]}} and its
   *  units): {stream: {t: {b, a, u}}}, or null. Only while it is still the last run's -- no
   *  newer run in the journal, the same model -- and only the values that still read what that
   *  run left (another run, or values read again, since: gone), not a tiny change (runlog's
   *  "small"). Input changed since does not drop it: it shows faded with the values. */
  function runDelta(tab) {
    const sess = sessOf(tab), d = sess.run_delta;
    if (!d || typeof d !== "object" || !d.s || typeof d.s !== "object") return null;
    const run = sess.journal && typeof sess.journal === "object" && sess.journal.run;
    if (run && typeof run.seq === "number" && typeof d.seq === "number" && run.seq > d.seq) return null;
    if (d.model && sess.model && sess.model.id && d.model !== sess.model.id) return null;
    const vals = sess.values || {}, units = d.u && typeof d.u === "object" ? d.u : {};
    let out = null;
    Object.entries(d.s).forEach(([name, ks]) => {
      const cur = vals[name];
      if (!cur || !ks || typeof ks !== "object") return;
      ["t", "p", "f"].forEach((k) => {
        const pr = ks[k], v = cur[k];
        if (!Array.isArray(pr) || pr.length < 2 || !Array.isArray(v)) return;
        const b = Number(pr[0]), a = Number(pr[1]), now = Number(v[0]);
        if (!isFinite(b) || !isFinite(a) || !isFinite(now) || a === b) return;
        if (Math.abs(a - b) < 1e-4 * Math.max(Math.abs(a), Math.abs(b))) return;   // within Aspen's tolerances: no arrow
        if (Math.abs(now - a) > 1e-9 + 1e-6 * Math.abs(a)) return;     // read again since: not that run's
        const u = (units[name] || {})[k];
        if (u && v[1] && u !== v[1]) return;
        out = out || {};
        (out[name] = out[name] || {})[k] = { b, a, u: u || v[1] || "" };
      });
    });
    return out;
  }
  /** The mole fractions the last run moved in a stream (run_delta's x: a reflux change moves a product's purity, not its T / P / F), while it is still the last
   *  run's: [[component, before, after]], or []. */
  function runFracs(tab, name) {
    const sess = sessOf(tab), d = sess.run_delta, x = d && d.x && typeof d.x === "object" ? d.x[name] : null;
    if (!x || typeof x !== "object") return [];
    const run = sess.journal && typeof sess.journal === "object" && sess.journal.run;
    if (run && typeof run.seq === "number" && typeof d.seq === "number" && run.seq > d.seq) return [];
    if (d.model && sess.model && sess.model.id && d.model !== sess.model.id) return [];
    return Object.entries(x).filter(([, p]) => Array.isArray(p) && isFinite(Number(p[0])) && isFinite(Number(p[1])) && Number(p[0]) !== Number(p[1]))
      .map(([c, p]) => [c, Number(p[0]), Number(p[1])]);
  }

  /** What the AI marked on the flowsheet (tab.highlight), until the user lets go of it with
   *  Escape, or the AI sets its next marks. A run does not clear them: the AI marks what it
   *  wants looked at, and a run started to check on it is when one looks. A server that stamps
   *  each write of the marks (tab.highlight_at) lets the same marks set again show again; an
   *  older one is followed by what the marks say (rec.hlGone: the marks let go of, by their
   *  stamp or their words). */
  const hlSig = (tab) => (typeof tab.highlight_at === "number" ? tab.highlight_at : JSON.stringify(tab.highlight || []));
  function marks(tab) {
    const rec = wb.recs.get(tab.id), hl = tab.highlight || [];
    return !hl.length || (rec && rec.hlGone === hlSig(tab)) ? [] : hl;
  }
  function dropMarks(pane, tab) {
    const rec = wb.recs.get(tab.id);
    if (!rec || !marks(tab).length) return false;
    rec.hlGone = hlSig(tab);
    if (pane && pane.tabId === tab.id) FS.render(pane.svg, fsView(pane, tab));
    return true;
  }

  /** When a session's results went stale: an input changed after the last real run on that
   *  session ended: a program's (a check runs no simulation), the window's Run simulation (the
   *  session's sim.finished, kept only by a run Aspen made), an applied point's re-run. Where
   *  the session has its journal summary the journal alone says when an input last changed and a run last ran,
   *  whoever made them: the AI's set_value too, and never the line an applied point writes
   *  after its re-run. Else the inputs set by hand in the inspector (the server notes each in
   *  the tab's messages, from "user"; an applied point's own line, written within a second of
   *  its re-run, is not one). 0 while they are not. Read from the state, so every window on the
   *  session agrees and a reload keeps it. Where the journal measures the model's state (
   *  modelSum) its net count alone decides: an input set back to its value since the last run
   *  leaves the results current (then: the last input's time, or the count's start). */
  function staleAt(session) {
    const sess = (wb.state && wb.state.sessions && wb.state.sessions[session]) || {}, sim = sess.sim;
    const js = modelSum(sess);
    if (js) {
      const st = js.stale, n = Number(st && st.n) || 0;
      return n ? Number(js.last_input_t) || Number(st.since) || 1 : 0;
    }
    const j = sess.journal && typeof sess.journal === "object" ? sess.journal : null;
    let ran = 0, set = 0;
    ((wb.state && wb.state.tabs) || []).forEach((x) => {
      if (x.session !== session) return;
      const run = x.run || {}, st = (x.results || {}).state;
      if (run.finished && !run.dry_run) ran = Math.max(ran, run.finished);
      // where results.state says the model was re-run (an applied point, a program's end): its
      // writes, then that run, then (an applied point) its line from "user" a moment after
      if (st && /^(ok|warn|error)$/.test(st.run || "") && typeof st.t === "number") ran = Math.max(ran, st.t + 1);
      if (!j) (x.messages || []).forEach((m) => { if (m.from === "user") set = Math.max(set, m.t || 0); });
    });
    if (sim && sim.finished) ran = Math.max(ran, sim.finished);
    if (j) {
      set = Math.max(set, Number(j.last_input_t) || 0);
      ran = Math.max(ran, Number(j.last_run_t) || 0);
    }
    return set > ran ? set : 0;
  }

  /** A stream's hover card, where the pointer rests on it: its latest temperature, pressure and
   *  flow (the Values layer's numbers), marked old while they are stale; none without values.
   *  Those the last run moved have their ▲ ▼, and a line more says what they were before it.
   *  Frost, one fixed size (a line taller with that line), placed beside the pointer inside
   *  the drawing's box. Its largest components' shares where the server has read them (app-comp.js
   *  cpPeek; asked for else, and the card drawn again when they come: renderTools). */
  function peek(pane, tg, x, y) {
    const el = pane.q(".fs-peek"), tab = tabOf(pane.tabId);
    const ls = tg && tab ? FS.valueLines((sessOf(tab).values || {})[tg.name], (runDelta(tab) || {})[tg.name]) : [];
    pane.peekAt = null;
    if (!ls.length) { el.classList.add("hidden"); return; }
    const cp = WBA.cpPeek ? WBA.cpPeek(tab, tg.name) : null;     // (its composition: the largest shares)
    pane.peekAt = { tg, x, y, sig: cp ? cp.sig : null };
    const fr = runFracs(tab, tg.name), fx = (b, a) => {           // as few digits as tell them apart (4 at least)
      let p = 4;
      while (p < 10 && Number(b.toPrecision(p)) === Number(a.toPrecision(p))) p++;
      return `${Number(b.toPrecision(p))} → ${Number(a.toPrecision(p))}`;
    };
    const fw = WBA.fwPeek ? WBA.fwPeek(tab, tg.name) : null;     // (the flow width layer's component: its flow here)
    const moved = ls.filter((l) => l.d), old = !!staleAt(tab.session), W = fr.length || cp ? 260 : 220;
    const H = (moved.length ? 94 : 76) + (fr.length ? 18 : 0) + (fw ? 18 : 0) + (cp ? 18 : 0);
    const ai = marks(tab).some((h) => h.kind === "stream" && h.name === tg.name);   // the AI marked it
    el.innerHTML = `<div class="pk-h"><b>${esc(tg.name)}</b><small>${esc(t("stream_word"))}</small>`
      + (ai ? `<span class="hltag">${esc(t("hl_tag"))}</span>` : "")
      + (old ? `<span class="oldtag">${esc(t("stale_tag"))}</span>` : "") + `</div>`
      + ls.map((l) => `<div class="pk-r"><span>${esc(t(`pk_${l.k}`))}</span><b>${esc(l.s)}${l.d ? `<i class="pk-d">${l.d}</i>` : ""}</b></div>`).join("")
      + (fw ? `<div class="pk-r pk-fw"><span>${esc(fw[0])}</span><b>${esc(fw[1])}</b></div>` : "")
      + (cp ? cp.html : "")
      + (moved.length ? `<div class="pk-was">${esc(t("pk_was", moved.map((l) => l.was).join(" · ")))}</div>` : "")
      // the mole fraction the last run moved most (run_delta's x; the line above says "last run")
      + (fr.length ? `<div class="pk-was pk-x">${esc(t("pk_frac", fr.sort((p, q) => Math.abs(q[2] - q[1]) - Math.abs(p[2] - p[1]))
        .slice(0, 1).map(([c, b, a]) => `${c} ${fx(b, a)}${a > b ? "▲" : "▼"}`).join("")))}</div>` : "");
    el.classList.toggle("old", old);
    el.classList.toggle("dl", !!moved.length);
    el.classList.toggle("dx", !!fr.length);
    el.style.height = fw || cp ? `${H}px` : "";     // (a line more: the flow width layer's, the composition's)
    el.style.width = cp ? `${W}px` : "";
    const a = pane.q(".fs-area").getBoundingClientRect();
    let left = x - a.left + 14, top = y - a.top + 18;
    if (left + W > a.width - 8) left = x - a.left - W - 14;          // no room at its right: at its left
    if (top + H > a.height - 8) top = y - a.top - H - 12;            // or above it
    el.style.left = `${Math.round(Math.max(8, Math.min(left, a.width - W - 8)))}px`;
    el.style.top = `${Math.round(Math.max(8, top))}px`;
    el.classList.remove("hidden");
  }

  /** What the flowsheet has picked: the inspector's target here, else the tab's selection. */
  const selOf = (tab, rec) => (rec && rec.insp ? rec.insp.target : shownSel(tab, rec)) || null;
  /** The server's selection, unless it is what the user closed and the server has yet to clear. */
  const shownSel = (tab, rec) => (tab.selection && !(rec && rec.closed && keyOf(tab.selection) === rec.closed) ? tab.selection : null);
  const blockType = (tab, name) => (((sessOf(tab).flowsheet || {}).blocks || []).find((b) => b.name === name) || {}).type || "";
  /** Whether this viewer has ever picked something on a flowsheet (a pref, see prefGet; the
   *  chip's first-use hint read it, which is gone: the tour says how to pick). */
  wb.everPicked = prefGet("wb.fs.picked") === "1";
  function notePicked() {
    if (wb.everPicked) return;
    wb.everPicked = true;
    prefSet("wb.fs.picked", "1");
  }

  /** The pane's own buttons: the program's versions (its run bar), the flowsheet's toolbar
   *  (the layers, the zoom, ⋯), and the selection chip: what is picked, "REACTOR › RCSTR" (a
   *  click finds it), only while something on the flowsheet is (a model object is not; how
   *  to pick and move things is the tour's first steps). Which model this is, is the header's
   *  (app-model.js). */
  function renderTools(pane, tab) {
    const q = pane.q, h = tab.history || { undo: 0, redo: 0 }, rec = wb.recs.get(tab.id);
    const sel = selOf(tab, rec), tg = sel && sel.kind !== "object" ? sel : null;
    const type = tg && tg.kind === "block" ? blockType(tab, tg.name) : "";
    const sig = JSON.stringify([I18N.lang, keyOf(tg), type]);
    if (q(".fs-chip").dataset.sig !== sig) {
      q(".fs-chip").dataset.sig = sig;
      q(".fs-chip").classList.toggle("hidden", !tg);
      q(".fs-chip").classList.toggle("picked", !!tg);
      if (tg) {
        q(".fc-tg b").textContent = tg.name;
        q(".fc-tg small").textContent = tg.kind === "block" ? type : t("stream_word");
      }
    }
    // (one that cannot act says why)
    const undo = q('[data-a="undo"]'), redo = q('[data-a="redo"]');
    undo.disabled = !wb.connected || !h.undo;
    redo.disabled = !wb.connected || !h.redo;
    undo.title = t(!wb.connected ? "why_off" : h.undo ? "tip_undo" : "tip_undo_none");
    redo.title = t(!wb.connected ? "why_off" : h.redo ? "tip_redo" : "tip_redo_none");
    q('[data-a="values"]').classList.toggle("on", prefs().values);
    // ⋯ busy while Aspen's drawing is read (the arrangement is its menu's)
    renderFslTools(pane, tab);
    // the heat plans layer is always there: off, saying how to get plans, until a pinch run
    // left some; its plan card
    const heat = heatOf(tab), shown = !!(heat && heatPref(tab).on), hb = q('[data-a="heat"]');
    hb.disabled = !heat;
    hb.classList.toggle("on", shown);
    const htip = t(heat ? "tip_heat" : "tip_heat_none");
    if (hb.title !== htip) hb.title = htip;
    renderPlan(pane, tab);
    if (window.WBP) WBP.tools(pane, tab);        // the annotations layer's toggle, its card (app-pins.js)
    if (WBA.pvTools) WBA.pvTools(pane, tab);     // a proposal's preview: its pill (app-preview.js)
    if (WBA.fwTools) WBA.fwTools(pane, tab);     // the flow width layer's button (app-flows.js)
    if (WBA.cpTools) WBA.cpTools(pane, tab);     // the Values layer's component line, its ▾ (app-comp.js)
    // the hover card shown, its composition read since (or read again): drawn again where it is
    const pa = pane.peekAt;
    if (pa && WBA.cpPeekSig && !pane.q(".fs-peek").classList.contains("hidden") && WBA.cpPeekSig(tab, pa.tg.name) !== pa.sig) peek(pane, pa.tg, pa.x, pa.y);
    if (rec && keyOf(tg) !== rec.refKey) markRefs(rec);   // the steps that name what is picked
    fitChip(pane);
  }

  /** Where the capsule leaves the chip too little room for what is picked, in steps, so the
   *  chip never shrinks to a stub: first the type goes whole (.notype: the capsule stays where it
   *  is); where the name is still cut, the capsule's Heat plans and Annotations keep only their
   *  icons (.fs-tools.slim: their names stay in their tooltips); where it still shows less than
   *  NAME_MIN px (or all of a shorter name), every layer keeps only its icon (.fs-tools.tight, as
   *  a narrow flowsheet has them). After a step, the type comes back where that made room for it
   *  too. Measured from the full chip and capsule each time, so it never flips back and forth;
   *  again when the chip's content, the room or the capsule changes (the capsule as this left
   *  it: fitSig). */
  const NAME_MIN = 64;
  const fitSig = (chip, pane) => [chip.dataset.sig, pane.q(".right-bar").clientWidth, pane.q(".fs-tools").offsetWidth].join("|");
  function fitChip(pane) {
    const chip = pane.q(".fs-chip"), tools = pane.q(".fs-tools");
    if (chip.dataset.fit === fitSig(chip, pane)) return;
    chip.classList.remove("notype");
    tools.classList.remove("slim", "tight");
    const b = chip.querySelector(".fc-tg b"), cut = (el) => el.scrollWidth > el.clientWidth + 1;   // 0 and 0 while it is not shown
    if (chip.classList.contains("picked")) {
      const typeCut = () => cut(b) || cut(chip.querySelector(".fc-tg small"));
      const give = (step) => {                   // the capsule gives way; the type back where that made room
        tools.classList.add(step);
        chip.classList.remove("notype");
        if (typeCut()) chip.classList.add("notype");
      };
      if (typeCut()) chip.classList.add("notype");
      if (cut(b)) give("slim");
      if (b.clientWidth < Math.min(b.scrollWidth, NAME_MIN)) give("tight");
    }
    chip.dataset.fit = fitSig(chip, pane);
  }

  /** The edge hints: at each edge of the free part of the drawing where blocks, open
   *  requests, annotations (the layer on), the AI's marks or changes not seen yet lie beyond it,
   *  a pill that counts them (the changes first, a dot in the colour of who made most of them;
   *  failed blocks in red, AI marks in violet: "3 changes · 12 blocks · 2 annotations · 1 AI
   *  highlight"; the names in its tooltip; a click goes to the nearest change first, then the
   *  nearest annotation: FS.edgePan), and a static fade. With the Values layer on but zoomed out past reading, a line at the bottom says to
   *  zoom in (static, above the pill there). Counted when the view comes to rest (FS.moved). The left
   *  and right pills sit low in their corners, where a drawing fitted to the top leaves room;
   *  one below sits between them (above them when they would meet). Where the left and right
   *  pills would meet, they keep only the numbers, each after an icon of what it counts (the
   *  words are in their tooltips); where even those meet, the left one rises over the right.
   *  The one below moves aside along its row, the least it takes, off a block, request or
   *  feed drawn under it. What a block selected in the program names, where it lies beyond
   *  an edge, is named first on that edge's pill ("ESTCOL · 12 blocks"), and a click on the
   *  pill shows it (the click handler reads data-link). */
  function renderEdges(pane) {
    const tab = tabOf(pane.tabId), area = pane.q(".fs-area");
    fitPlan(pane);                               // the plan card beside the inspector: the free area's left
    gcPlace(pane);                               // a run by group's card: beside the inspector, or under it
    const off = tab && !pane.q(".pright").classList.contains("fs-off") ? FS.offscreen(pane.svg) : null;
    const ins = FS.insets(pane.svg), W = area.clientWidth;
    const far = !!tab && prefs().values && pane.svg.classList.contains("far") && Object.keys(sessOf(tab).values || {}).length > 0;
    const sig = JSON.stringify([I18N.lang, off, ins, W, area.clientHeight, pane.svg.getAttribute("viewBox"),   // the view: what the pill below sits on
      pane.q(".fs-plan").className, far]);                                                                    // (a folded plan: the row it keeps above)
    if (pane.sigs.edges === sig) return;
    pane.sigs.edges = sig;
    const count = (n, one, many, cls) => { const s = esc(n === 1 ? t(one) : t(many, n)); return cls ? `<b class="${cls}">${s}</b>` : s; };
    const shown = {}, midX = Math.round(ins.left + (W - ins.left - ins.right) / 2);
    ["l", "r", "t", "b"].forEach((side) => {
      const o = off && off[side], el = pane.q(`.fs-hint[data-side="${side}"]`), links = o ? o.links : [];
      const n = o ? o.units + o.notes + o.marks + o.chg + o.pins + o.pv + links.length : 0;
      area.classList.toggle(`e${side}`, !!n || !!(o && o.more));   // the fade: wherever the drawing goes on
      el.classList.toggle("hidden", !n);
      el.classList.remove("compact");
      el.dataset.link = links.length ? keyOf(links[0]) : "";
      if (!n) return;
      shown[side] = el;
      const words = [], nums = [], named = links.map((x) => x.name).join(", ");
      if (links.length) { words.push(`<b class="lk">${esc(named)}</b>`); nums.push(`<b class="lk">${esc(links[0].name)}</b>`); }
      // numbers only, each after the icon of what it counts: changes, blocks, requests, annotations, AI marks,
      // errors, warnings
      const ca = Object.entries(o.chgBy || {}).sort((p, q) => q[1] - p[1])[0], cd = ca ? `<i class="ehd a-${esc(ca[0])}"></i>` : "";
      if (o.chg) { words.push(`<b class="chg">${cd}${esc(o.chg === 1 ? t("eh_chg") : t("eh_chgs", o.chg))}</b>`); nums.push(`<b class="chg">${cd}${o.chg}</b>`); }
      if (o.units) { words.push(count(o.units, "eh_unit", "eh_units")); nums.push(`<span>${icon("block")}${o.units}</span>`); }
      if (o.notes) { words.push(count(o.notes, "eh_note", "eh_notes", "ai")); nums.push(`<b class="ai">${icon("chat")}${o.notes}</b>`); }
      if (o.pins) { words.push(count(o.pins, "eh_pin", "eh_pins", "pn")); nums.push(`<b class="pn">${FS.pinIcon}${o.pins}</b>`); }
      if (o.pv) { words.push(`<b class="ai">${esc(t("pv_off", o.pv))}</b>`); nums.push(`<b class="ai">${icon("eye")}${o.pv}</b>`); }   // a proposal's new objects (preview)
      if (o.marks) { words.push(count(o.marks, "eh_mark", "eh_marks", "ai")); nums.push(`<b class="ai">${icon("sparkle")}${o.marks}</b>`); }
      if (o.errs) { words.push(count(o.errs, "eh_err", "eh_errs", "err")); nums.push(`<b class="err">${icon("warn")}${o.errs}</b>`); }
      if (o.warns) { words.push(count(o.warns, "eh_warn", "eh_warns", "warn")); nums.push(`<b class="warn">${icon("warn")}${o.warns}</b>`); }
      el.querySelector(".eh").innerHTML = `<span class="ew">${words.join(" · ")}</span><span class="en">${nums.join("")}</span>`;
      const plain = [o.chg && (o.chg === 1 ? t("eh_chg") : t("eh_chgs", o.chg)),
        o.units && (o.units === 1 ? t("eh_unit") : t("eh_units", o.units)), o.notes && (o.notes === 1 ? t("eh_note") : t("eh_notes", o.notes)),
        o.pins && (o.pins === 1 ? t("eh_pin") : t("eh_pins", o.pins)),
        o.pv && t("pv_off", o.pv),
        o.marks && (o.marks === 1 ? t("eh_mark") : t("eh_marks", o.marks)),
        o.errs && (o.errs === 1 ? t("eh_err") : t("eh_errs", o.errs)),
        o.warns && (o.warns === 1 ? t("eh_warn") : t("eh_warns", o.warns))].filter(Boolean).join(" · ");
      const names = o.names.slice(0, 8).join(", ") + (o.names.length > 8 ? ", …" : "");
      const colon = I18N.lang === "zh" ? "：" : ": ";
      const marked = o.markNames.length ? `${t("hl_tag")}${colon}${o.markNames.join(", ")}` : "";
      const pinned = o.pinNames.length ? `${t("btn_explain")}${colon}${o.pinNames.join(", ")}` : "";
      const changed = o.chg ? t("tip_eh_chg", o.chgNames.slice(0, 8).join(", ") + (o.chgNames.length > 8 ? ", …" : "")) : "";
      const pvn = o.pvNames.length ? `${t("pv_pill")}${colon}${o.pvNames.slice(0, 8).join(", ")}${o.pvNames.length > 8 ? ", …" : ""}` : "";
      el.title = [links.length && t("tip_eh_link", named), plain && t(`tip_eh_${side}`, plain), changed, names, pinned, marked, pvn].filter(Boolean).join("\n");
      el.style.cssText = side === "l" ? `left:${ins.left + 8}px;bottom:${ins.bottom + 10}px`
        : side === "r" ? `right:${ins.right + 8}px;bottom:${ins.bottom + 10}px`
        : side === "t" ? `left:${midX}px;top:${ins.top + 4}px` : `left:${midX}px;bottom:${ins.bottom + 10}px`;
    });
    // pills that would meet: the numbers only; where even those meet, the left one rises over
    // the right; one below them rises over both
    const room = W - ins.left - ins.right - 24, lw = shown.l ? shown.l.offsetWidth : 0, rw = shown.r ? shown.r.offsetWidth : 0;
    if (lw + rw + (shown.l && shown.r ? 8 : 0) > room) [shown.l, shown.r].forEach((el) => el && el.classList.add("compact"));
    const lift = !!(shown.l && shown.r) && shown.l.offsetWidth + shown.r.offsetWidth + 8 > room;
    if (lift) shown.l.style.bottom = `${ins.bottom + 42}px`;
    // zoomed out past reading the Values: a line at the bottom, over the pill there
    const fl = pane.q(".fs-far");
    fl.classList.toggle("hidden", !far);
    if (far) fl.style.cssText = `left:${midX}px;bottom:${ins.bottom + (shown.b ? 44 : 12)}px`;
    if (shown.b) {
      const bx = shown.b.getBoundingClientRect();
      const meets = (el) => { if (!el) return false; const r = el.getBoundingClientRect(); return r.left < bx.right + 8 && bx.left < r.right + 8; };
      if (lift && meets(shown.l)) shown.b.style.bottom = `${ins.bottom + 74}px`;
      else if (meets(shown.l) || meets(shown.r)) shown.b.style.bottom = `${ins.bottom + 42}px`;
      // off what is drawn under it: the nearest spot along its row, in steps, within the free
      // area and clear of a corner pill on the same row
      const b = shown.b.getBoundingClientRect(), a = area.getBoundingClientRect(), row = (r) => r.bottom > b.top - 4 && r.top < b.bottom + 4;
      const under = [...pane.svg.querySelectorAll(".fs-node > rect, .fs-note, .fs-term")].map((el) => el.getBoundingClientRect()).filter(row);
      const block = under.concat([shown.l, shown.r].filter(Boolean).map((el) => el.getBoundingClientRect()).filter(row));
      const hits = (dx) => block.some((r) => r.left < b.right + dx + 4 && b.left + dx < r.right + 4);
      if (under.length && hits(0)) {
        const lo = a.left + ins.left + 8 - b.left, hi = a.right - ins.right - 8 - b.right;   // how far it may go either way
        for (let s = 16; s <= Math.max(-lo, hi); s += 16) {
          const dx = [s, -s].find((d) => d >= lo && d <= hi && !hits(d));
          if (dx !== undefined) { shown.b.style.left = `${midX + dx}px`; break; }
        }
      }
    }
  }

  /** The flowsheet's menu (the capsule's ⋯): its arrangement (app-fsl.js fslItems: automatic or
   *  Aspen's, undo and redo), and Redraw Aspen's diagram (Aspen's own window laid out
   *  again, app-replay.js) and "Apply arrangement to Aspen" (the arrangement drawn here into Aspen's drawing); Show as boxes (how
   *  blocks are drawn, ticked or not); the legend; Result tags (feature effects, ticked or not, and Show closed tags while a run has some:
   *  app-effects.js); and Export SVG (the drawing as a figure,
   *  FS.figure, through the window's save dialog). Fit is the capsule's zoom, pressed; the
   *  model's own name and state are the model panel's (app-model.js). */
  function fsMenuItems(pane, tab) {
    const rdWhy = redrawWhy(tab), at = pane.q('.fs-tools [data-a="fs_menu"]'), plWhy = WBA.placeWhy(pane, tab);
    const arr = fslItems(pane, tab).concat(
      { label: t("aspen_redraw"), icon: "aspen", disabled: !!rdWhy, tip: rdWhy || t("tip_aspen_redraw"), run: () => aspenRedraw(tab) },
      // (the arrangement drawn here into Aspen's own drawing: it asks first, Aspen reopens the model)
      { label: t("aspen_place"), icon: "layout", disabled: !!plWhy, tip: plWhy || t("tip_aspen_place"), run: () => WBA.aspenPlace(pane, tab) });
    const boxes = boxesOn(), fx = WBA.fxMenuItem ? WBA.fxMenuItem(pane) : null;   // (the result tags)
    return arr.concat(arr.length ? [{ sep: true }] : [], [
      { label: t("m_fs_boxes"), icon: "block", check: boxes, tip: t(boxes ? "tip_fs_icons" : "tip_fs_boxes"), run: () => setView(pane, !boxes) },
      { label: t("m_fs_legend"), icon: "info", tip: t("tip_legend"), run: () => openLegend(at) },
      ...(fx ? [].concat(fx) : []),
      { sep: true },
      { label: t("m_fs_export"), icon: "download", tip: t("tip_fs_export"), run: () => exportFigure(pane, tab) },
    ]);
  }
  /** The drawing as a figure for a paper (FS.figure), saved where the user says. */
  function exportFigure(pane, tab) {
    const svg = FS.figure(pane.svg);
    if (svg) WBA.saveFile(`${String(tab.session || "flowsheet").replace(/[\/:*?"<>|]+/g, "_")}.svg`, svg, "svg");
  }

  Object.assign(WBA, { blockType, dropMarks, fitChip, fsMenuItems, fsView, notePicked, peek,
    renderEdges, renderTools, selOf, setView, shownSel, staleAt, viewBoxes: boxesOn });
})();
