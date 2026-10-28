/* A stream or block picked (pick, reveal, closeInspector; from a change record: gotoChange),
 * the selection hub (markRefs, linkFrom), and the inspector: its head, Aspen's own words on the
 * block, the bar saying its results are stale, the check for edits made in Aspen's own window
 * (renderDeep, deepAsk), its rows and filter (a field gone to: focusRow),
 * each row's last change and the card of its history (provOf, the prov card), editing a value
 * (startEdit, commitEdit), the row's + menu and a row added to the program (rowItems, addRow),
 * a row's help card (helpRow: help.js), what Aspen still needs of the object
 * (renderStatus, the line under the head, and the rows' marks: missing.js), its rows under
 * Aspen's sheets (sectionsOf) and its other GUI forms behind one line, a sheet picked read
 * when picked (moreHtml, openSheet: Aspen V15), the way from its error to the run's diagnosis
 * (diag.js).
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { INSP_W, askAI, blockType, busy, changed, changesCtx, changesPicked, dragBar, esc, feature, flashBlock, fmtVal, focusComposer, ghost,
    hhmm, icon, isObj, isOpen, keyOf, notePicked, prefGet, prefSet, prefs, renderComposer, renderEdges, renderTools, runSim,
    selOf, sendProgram, sessOf, setDock, setInspW, setProg, showPanel, showStep, staleAt, t, tabOf, toast, toggleMenu,
    useSession, wb, words, zh } = WBA;
  const { pausedOn, undoOpen } = WBA.later;

  /** A stream or block picked (a click on the flowsheet, a target named in the chat): the
   *  inspector shows it, the chip names it, and the drawing pans the least it takes to show
   *  it beside the inspector and clear of the edge hints (same scale; never a refit). A ring
   *  shows where it went after a pan, or always with o.ring. o.focus: a field's path the
   *  inspector goes to once its rows come (focusRow); o.sheet: the form sheet it opens
   *  ({form, sheet, ids}: a missing item's); o.quiet: picked from the Changes panel, whose
   *  filter stays (changesPicked). */
  function pick(pane, target, o) {
    const tab = tabOf(pane.tabId);
    if (!tab) return;
    const rec = wb.recs.get(tab.id);
    commitEdit(pane);
    if (!target) { closeInspector(pane); return; }
    const same = rec.insp && keyOf(rec.insp.target) === keyOf(target), focus = o && o.focus ? { path: String(o.focus), at: Date.now() } : null;
    if (!same && pane.fhSel && window.WBH) WBH.close();   // a row's help card goes with its object
    const sheet = o && o.sheet && o.sheet.sheet ? o.sheet : same ? rec.insp.sheet : null;
    rec.insp = { target, all: same ? rec.insp.all : false, focus, sheet };
    if (!same || focus) rec.filter = "";         // the filter holds while the same target shows
    pane.editing = pane.adding = null;
    rec.asks = 0;
    askInspect(rec, tab);
    if (sheet) askSheet(rec, tab);
    notePicked();
    renderInspector(pane, tab, sessOf(tab));
    renderTools(pane, tab);
    picked(pane, rec, null);
    const r = reveal(pane, target, o && o.ring ? FS.RING_ROOM : 0);
    if (r && (r.moved || (o && o.ring))) FS.ping(pane.svg, target);
    changesPicked(pane, target, !!(o && o.quiet));
  }
  /** A record's block or stream in the Changes panel clicked: picked, the inspector at the
   *  field it changed (path), the flowsheet in sight; one no longer drawn says so. */
  function gotoChange(pane, target, path) {
    const tab = tabOf(pane.tabId), fs = tab ? sessOf(tab).flowsheet : null;
    if (!tab || !target || !fs || !fs.blocks) return;
    const up = String(target.name).toUpperCase();
    const hit = ((target.kind === "stream" ? fs.streams : fs.blocks) || []).find((x) => x && String(x.name).toUpperCase() === up);
    if (!hit) { toast(t("ch_gone", target.name), 4000); return; }
    if (prefs().dockMode === "max") setDock(pane, "split");   // the flowsheet shows again
    pick(pane, { kind: target.kind, name: hit.name }, { ring: true, focus: path, quiet: true });
  }
  /** Show a target where nothing floats over it: beside the inspector and under the toolbar
   *  (FS.reveal), and clear of the edge hints, which are placed (and counted again) only once
   *  the view has moved: a hint over the target pans it again, keeping clear of that hint's
   *  row. pad: the room kept round it, px (FS.reveal's; FS.RING_ROOM where a ring follows, so
   *  the ring is not cut at the card's edge). Returns null when the target is not drawn, else {moved}. */
  function reveal(pane, target, pad) {
    const keep = { top: 0, bottom: 0, pad: pad || 0 };
    let moved = false;
    for (let i = 0; i < 3; i++) {
      const r = FS.reveal(pane.svg, target, keep);
      renderEdges(pane);                         // the hints move beside the inspector at once
      if (!r) return null;
      moved = moved || r.moved;
      const s = pane.svg.getBoundingClientRect(), a = r.rect, over = [...pane.el.querySelectorAll(".fs-hint:not(.hidden)")]
        .map((h) => h.getBoundingClientRect()).filter((h) => h.left < a.right + 4 && a.left < h.right + 4 && h.top < a.bottom + 4 && a.top < h.bottom + 4);
      if (!over.length) break;
      over.forEach((h) => {
        if (h.top + h.bottom < s.top + s.bottom) keep.top = Math.max(keep.top, h.bottom - s.top + 6);
        else keep.bottom = Math.max(keep.bottom, s.bottom - h.top + 6);
      });
    }
    return { moved };
  }
  /** Ask the server for the inspector's values. */
  function askInspect(rec, tab) {
    rec.askAt = Date.now();
    rec.asks++;
    const f = rec.insp.focus;                    // (the field it goes to: the page's own, the server passes it by)
    wb.post(Object.assign({ type: "inspect", tab: tab.id, target: rec.insp.target, all: rec.insp.all }, f ? { focus: f.path } : {}));
  }
  /** Ask for the fields of the sheet picked (rec.insp.sheet); the tab's isheet brings them. */
  function askSheet(rec, tab) {
    const s = rec.insp.sheet;
    rec.sheetAt = Date.now();
    wb.post({ type: "inspect_sheet", tab: tab.id, target: rec.insp.target, form: s.form, sheet: s.sheet, ids: s.ids || "" });
  }
  /** The tab's isheet when it is the sheet picked, else null. */
  function sheetOf(tab, rec) {
    const s = rec.insp && rec.insp.sheet, d = tab.isheet;
    return s && isObj(d) && keyOf(d.target) === keyOf(rec.insp.target) && d.form === s.form && d.sheet === s.sheet
      && (d.ids || "") === (s.ids || "") ? d : null;
  }
  /** The inspector against the server's record of it, which can run behind the user: a state
   *  saved before the server read a close still names the target (and a close that crossed
   *  the pick's own request can leave it named for good), and a pick's values can fail to
   *  come. A close the server has not taken goes again (once a state that still names it, so
   *  it never reopens nor stays marked); values not come 5 s on are asked for again, twice at
   *  most, while the model is open and no run holds the server up (a run step keeps it from
   *  reading requests); a sheet's fields likewise. */
  function followInspect(rec, tab) {
    if (!rec.insp) {
      const k = rec.closed, named = (tab.inspect && keyOf(tab.inspect.target) === k) || keyOf(tab.selection) === k;
      if (k && named && wb.connected) wb.post({ type: "close_inspect", tab: tab.id });
      return;
    }
    const d = tab.inspect, can = wb.connected && isOpen(tab) && !wb.state.tabs.some(busy);
    const n = rec.sheetAsks || 0;
    if (rec.insp.sheet && sheetOf(tab, rec)) rec.sheetAsks = 0;
    else if (rec.insp.sheet && can && n < 2 && Date.now() - rec.sheetAt > 5000) { rec.sheetAsks = n + 1; askSheet(rec, tab); }
    if (d && keyOf(d.target) === keyOf(rec.insp.target) && (!rec.insp.all || d.all)) { rec.asks = 0; return; }
    if (can && rec.asks < 3 && Date.now() - rec.askAt > 5000) askInspect(rec, tab);
  }
  function closeInspector(pane) {
    const tab = tabOf(pane.tabId);
    if (!tab) return;
    commitEdit(pane);
    const rec = wb.recs.get(tab.id), was = rec.insp;
    if (!was && !tab.selection) return;          // a click on empty space with nothing picked
    if (pane.fhSel && window.WBH) WBH.close();   // a row's help card goes with the inspector
    rec.insp = null;
    pane.editing = pane.adding = null;
    wb.post({ type: "close_inspect", tab: tab.id });
    pane.inspExit = true;                        // (it slides out; a tab switch just hides it)
    renderInspector(pane, tab, sessOf(tab));
    renderTools(pane, tab);
    picked(pane, rec, was ? keyOf(was.target) : null);
    renderEdges(pane);
    changesPicked(pane, null);                   // a Changes panel that shows: all again
  }
  /** A pick or a close by the user: the composer's chip follows it unless pinned (closed:
   *  the target let go, whose selection the server has yet to clear). */
  function picked(pane, rec, closed) {
    rec.pickAt = Date.now();
    rec.frozen = null;
    rec.closed = closed;
    renderComposer(pane);
  }

  /** The selection hub, program side: every step whose path names what the flowsheet has
   *  picked (the inspector's target, else the tab's selection) carries .wb-ref, a bar in the
   *  accent colour at its left (style.css). A class on the step's own SVG group, nothing
   *  drawn into it, so Blockly redrawing the block keeps it; a version loaded or a language
   *  switch makes the blocks anew, and they are marked again (and after every edit). */
  function markRefs(rec) {
    const tab = tabOf(rec.id), tg = tab ? selOf(tab, rec) : null;
    const want = new Set(tg ? WB.refsTo(rec.ws, tg).map((b) => b.getSvgRoot()).filter(Boolean) : []);
    rec.ws.getParentSvg().querySelectorAll(".wb-ref").forEach((el) => { if (!want.has(el)) Blockly.utils.dom.removeClass(el, "wb-ref"); });
    want.forEach((el) => Blockly.utils.dom.addClass(el, "wb-ref"));
    rec.refKey = keyOf(tg);
  }
  /** The selection hub, flowsheet side: a block selected in the program marks what its paths
   *  name (.link, FS.mark: a class, no redraw). Where that lies off screen, the edge hint on
   *  that side names it, and a click on the hint shows it. */
  function linkFrom(pane, rec, id) {
    const blk = id ? rec.ws.getBlockById(id) : null;
    const keys = blk ? WB.targetsIn(blk).map(keyOf) : [], sig = keys.join("\n");
    if (pane.linkSig === sig) return;
    pane.linkSig = sig;
    FS.mark(pane.svg, keys, "link");
    renderEdges(pane);
  }

  /** The first line of one of Aspen's messages ("** ERROR", "*  WARNING", "***SEVERE ERROR"). */
  const MSG_HEAD = /^\s*\*+\s*(SEVERE|TERMINAL|ERROR|WARNING)/i;

  /** The inspector, floating over the flowsheet from its right (out to its left edge unless
   *  the viewer narrowed it: style.css) and as tall as its rows (it scrolls past the card's
   *  height): its target's name, type and last-run status, Ask AI and a path block, the line
   *  saying what it still needs (renderStatus), a filter for a long list, and the rows.
   *  Opening or closing it never refits the drawing: a pick pans the least it takes (pick),
   *  and the edge hints are counted again for the new free area.
   *  Its parts are filled in place (index.html builds them once), the rows on their own. */
  function renderInspector(pane, tab, sess) {
    const rec = wb.recs.get(tab.id), box = pane.q(".insp");
    const exit = pane.inspExit;
    pane.inspExit = false;
    if (!rec.insp) {
      hideProv(pane);
      if (!box.classList.contains("hidden")) {
        if (exit) ghost(box, 160);                 // closed by the user: a copy slides out
        box.classList.add("hidden");
        FS.moved(pane.svg);
      }
      pane.sigs.ihead = pane.sigs.irows = pane.sigs.iext = pane.sigs.ipaused = pane.sigs.istat = null;
      return;
    }
    if (pane.editing && keyOf(pane.editing.target) === keyOf(rec.insp.target)) return;   // keep the open editor
    const tg = rec.insp.target, data = tab.inspect;
    if (tg.kind === "stream" && WBA.cpAsk) WBA.cpAsk(tab, tg.name);   // its composition, where not read yet
    const ready = data && keyOf(data.target) === keyOf(tg) && (!rec.insp.all || data.all);
    const st = tg.kind === "block" ? (sess.status || {})[tg.name] : null;
    // a program paused before a step lets the inspector write: the edit is the
    // user's, in the run's change group, and kept when the program ends -- a note says so
    const paused = pausedOn(tab.session);
    const editable = wb.connected && (!busy(tab) || paused);
    if (box.classList.contains("hidden")) {
      box.classList.remove("hidden");
      FS.moved(pane.svg);                          // the free area narrowed: count the edges again
    }
    const q = (s) => box.querySelector(s);
    const diagOn = !!st && !!window.WBD && WBD.names(sess, tg.name);
    if (changed(pane, "ihead", [tab.id, I18N.lang, tg, blockType(tab, tg.name), st, rec.insp.all, diagOn])) {
      const obj = tg.kind === "object";            // a model object: Setup, a reaction, a design spec
      q(".ik use").setAttribute("href", `#i-${obj ? "gear" : tg.kind === "stream" ? "stream" : "block"}`);
      q(".iname").textContent = tg.name;
      q(".iname").title = obj ? tg.path : tg.name;
      const type = tg.kind === "block" ? blockType(tab, tg.name) : obj ? tg.type || "" : t("stream_word");
      q(".itype").textContent = type;
      q(".itype").classList.toggle("hidden", !type);
      // the last run's word on it: its level and how many messages it left (Aspen writes each
      // over several lines, under a "** ERROR" or "*  WARNING" head), the lines below
      const lvl = q(".lvl"), n = st ? (st.lines || []).filter((l) => MSG_HEAD.test(l)).length || 1 : 0;
      lvl.classList.toggle("hidden", !st);
      if (st) {
        lvl.className = `lvl ${st.level === "error" ? "err" : "warn"}`;
        lvl.innerHTML = `${icon("warn")}${n}`;
        lvl.title = `${t(st.level === "error" ? "lvl_error" : "lvl_warn")}: ${st.msg || ""}`;
      }
      // Aspen's own words on it, as Aspen wrote them. The header's "Ask AI" is the one way to ask the
      // AI (it takes these words along: see the click below), so its tooltip says so
      const open = st && st.level === "error" && !pane.q(".fs-wrap").classList.contains("short");   // a short card keeps the rows
      const err = st && st.level === "error";
      const ask = q(".ia .ask"), askTip = st ? "tip_insp_note_err" : "tip_insp_note";
      ask.dataset.i18nTitle = askTip;                // (I18N.apply sets it again on a language switch)
      ask.title = t(askTip);
      // (the head's actions are icons: their names for a screen reader)
      ask.setAttribute("aria-label", t("ask_ai"));
      q('.ia [data-act="block"]').setAttribute("aria-label", t("insp_block"));
      q('.ia [data-act="block"]').classList.toggle("hidden", obj);   // (a path block is a block's or a stream's)
      // the run's diagnosis names this block (diag.js): "Diagnosis" opens its card
      const acts = diagOn ? `<div class="ierr-acts"><button class="ierr-diag" data-act="ierr_diag" title="${esc(t("tip_ierr_diag"))}">`
        + `${icon("info")}<span class="bt">${esc(t("ierr_diag"))}</span></button></div>` : "";
      q(".ierrs").innerHTML = st && st.lines && st.lines.length
        ? `<details class="ierr ${err ? "err" : "warn"}"${open ? " open" : ""}><summary>${esc(t(err ? "ierr_head_err" : "ierr_head_warn", st.msg || t(err ? "lvl_error" : "lvl_warn")))}</summary><pre>${esc(st.lines.join("\n"))}</pre>`
          + `${acts}</details>` : "";
      q("[data-act=all]").checked = !!rec.insp.all;
      // (no line of help under the filter: ⊕, a double-click and a click on a value are said in
      // each row's tooltip, and the tour shows them)
      q(".itip").classList.add("hidden");
    }
    if (changed(pane, "ipaused", [tab.id, I18N.lang, paused && editable])) {
      const note = q(".ipaused");
      note.classList.toggle("hidden", !(paused && editable));
      // two words on the card; what an edit now does (the user's, kept when the program ends) in the tooltip
      note.title = paused && editable ? t("step_edit_hint") : "";
      note.innerHTML = paused && editable ? `${icon("pause")}<span class="st">${esc(t("insp_paused"))}</span>` : "";
    }
    renderDeep(pane, tab, rec);
    oneBand(pane);
    const inp = q(".ifilter");
    if (inp.value !== rec.filter && document.activeElement !== inp) inp.value = rec.filter;
    renderRows(pane, tab, rec, data, ready, editable);
    staleMarks(pane, tab);
  }

  /** An input set by hand since the last run: the results shown are that run's. Said where they
   *  are -- the "old" tag by their headings (the rows faded) --, nothing above the rows that would
   *  move them; the tag's tooltip says why, and a click on it runs the simulation (or why not now). */
  function staleMarks(pane, tab) {
    const tags = pane.el.querySelectorAll(".insp .irows .oldtag");
    if (!tags.length) return;
    const why = !wb.connected ? t("why_off") : !isOpen(tab) ? t("why_closed", tab.session)
      : wb.state.tabs.some((x) => x.session === tab.session && busy(x)) ? t("why_sim_busy")
      : (sessOf(tab).sim || {}).status === "running" ? t("why_sim_running") : "";
    const tip = `${t("tip_stale")}
${why || t("tip_insp_run_sim")}`;
    tags.forEach((x) => {
      if (x.dataset.act !== "run_sim") { x.dataset.act = "run_sim"; x.setAttribute("role", "button"); }
      if (x.title !== tip) x.title = tip;
      if ((x.getAttribute("aria-disabled") === "true") !== !!why) x.setAttribute("aria-disabled", why ? "true" : "false");
    });
  }

  /** The status lines under the head, as one line: the most important that has something to say
   *  shows -- a check for edits in Aspen reading, or one that found edits (the user just asked);
   *  what Aspen still needs; results out of date; a program paused; what a check came to else --
   *  the others are its "+N"'s tooltip. */
  const BANDS = [".ipaused", ".iext"];
  const rank = (el) => (el.classList.contains("iext") ? (el.querySelector(".ixd.run, .ixd-see") ? -1 : 9) : BANDS.indexOf(`.${el.classList[0]}`));
  function oneBand(pane) {
    const els = BANDS.map((s) => pane.q(`.insp ${s}`)).filter(Boolean);
    const has = els.filter((el) => !el.classList.contains("hidden") && el.textContent.trim()).sort((a, b) => rank(a) - rank(b));
    const words = (el) => [...el.querySelectorAll(".st, .ixd-t")].map((x) => x.textContent.trim()).filter(Boolean).join(" ") || el.textContent.trim();
    els.forEach((el) => {
      el.classList.toggle("band-off", has.indexOf(el) > 0);
      const n = el.querySelector(":scope > .band-n");
      if (n && has[0] !== el) n.remove();
    });
    if (!has.length) return;
    const top = has[0], rest = has.slice(1).map(words);
    let n = top.querySelector(":scope > .band-n");
    if (!rest.length) { if (n) n.remove(); return; }
    if (!n) { n = document.createElement("small"); n.className = "band-n"; top.appendChild(n); }
    n.textContent = `+${rest.length}`;
    n.title = rest.join("\n");
  }

  /** What Aspen still needs of the object shown, one line under the head: "Inputs complete"
   *  where it is known to need nothing -- the completeness scan does not flag it, and the session's
   *  scan or the forms' sheets say so --, else what is missing: the required fields by name, each a
   *  button that goes to its row (goMissing), or the first incomplete sheet, or the empty fields'
   *  count; its lead opens the first incomplete sheet, else the list of missing inputs (missGo).
   *  No words while the values come. All fields sits at its end while the list is too short for a
   *  filter (many). */
  function renderStatus(pane, tab, rec, data, ready, many) {
    const box = pane.q(".insp .istat"), tg = rec.insp.target;
    const m = ready && isObj(data.missing) ? data.missing : null, todo = ready ? firstTodo(data) : null, sm = sessOf(tab).missing;
    const scanned = isObj(sm) && (sm.state === "complete" || (sm.state === "incomplete" && !sm.cut && !sm.stale && !missObj(sm, tg)));
    const known = ready && !data.reading && (!!m || !!todo || scanned || formsOf(data).some((f) => f.sheets.some((x) => x.state)));
    if (ready && data.reading && pane.istatOn === `${tab.id}|${keyOf(tg)}`) return;   // (read again: the words stay till it is read)
    if (!changed(pane, "istat", [tab.id, I18N.lang, keyOf(tg), known, m, todo, many, rec.insp.all])) return;
    pane.istatOn = known ? `${tab.id}|${keyOf(tg)}` : null;
    let html = "";
    if (known && !m && !todo) html = `<span class="is-ok">${icon("check")}<span>${esc(t("insp_ok"))}</span></span>`;
    else if (known) {
      const req = ((m && m.items) || []).filter((x) => x && x.certainty === "required");
      const n = Math.max(req.length, Number(m && m.n_required) || 0);
      const lead = req.length ? t("insp_miss_count", n) : todo ? t("insp_miss_sheet", `${todo.title} › ${todo.sheetTitle}`)
        : m.deep === "waiting" ? t("insp_miss_wait") : t("insp_miss_empty", `${Number(m.n_values) || 0}${m.more_fields ? "+" : ""}`);
      html = `<button class="is-lead flat" data-act="miss_go" title="${esc(t(todo ? "tip_insp_miss_go" : "tip_insp_miss_see"))}">${icon("warn")}<span>${esc(lead)}</span></button>`
        + req.slice(0, 3).map((x) => `<button class="is-go flat" data-go="${esc(x.path)}" title="${esc(t("tip_insp_go"))}">`
          + `${esc(zh() && x.gl ? x.gl : words(x.label || x.field || ""))}</button>`).join(zh() ? "、" : ", ") + (n > 3 ? "…" : "");
    }
    if (!many) {
      html += `<label class="iall" title="${esc(t("tip_insp_all"))}"><input type="checkbox" data-act="all"${rec.insp.all ? " checked" : ""}>`
        + `<span>${esc(t("insp_all"))}</span></label>`;
    }
    box.classList.toggle("hidden", !html);
    box.innerHTML = html;
  }
  /** A missing field's name pressed: its row, its section opened (rec.insp.shown) and its value
   *  focused (focusRow); one no row holds: on its form sheet where the scan names one, else the
   *  list of missing inputs at it. */
  function goMissing(pane, tab, rec, path) {
    const want = low(path), has = (pane.rows || []).some((r) => low(r.path) === want);
    const it = !has && (((missObj(sessOf(tab).missing, rec.insp.target) || {}).first) || []).find((x) => low(x.path) === want);
    if (!has && !(it && it.at)) { WBM.open(tab, { focus: path }); return; }
    rec.insp.focus = { path: String(path), at: Date.now(), key: true };
    if (it) { openSheet(pane, tab, rec, it.at); return; }
    renderInspector(pane, tab, sessOf(tab));
  }
  /** The completeness scan's entry for a target: a model object's by its path, a block's or a stream's by its name. */
  const missObj = (m, tg) => ((m && m.objects) || []).find((x) => (tg.kind === "object" ? x.path === tg.path
    : String(x.name || "").toUpperCase() === String(tg.name).toUpperCase() && (x.kind || "block") === tg.kind)) || null;
  /** The head's dot pressed: the first incomplete sheet opened, else the list of missing inputs. */
  function missGo(pane, tab, rec) {
    const todo = firstTodo(tab.inspect), tg = rec.insp.target;
    if (todo) { openSheet(pane, tab, rec, todo.at); return; }
    const o = missObj(sessOf(tab).missing, tg);
    WBM.open(tab, { focus: o ? o.path : null });
  }

  /** The object's GUI forms (inspect's `forms`), as the inspector lists them: a collection's form
   *  once per member ("Pumparounds P-1"), the sheets Aspen hides left out, a form with none
   *  left out; each {key, form, title, name (the form's), id (the member's), adv, todo, sheets: [{cls, title, state, at}]}. */
  function formsOf(data) {
    const out = [];
    ((data && data.forms) || []).forEach((f) => {
      const ids = f.coll ? [...new Set(f.sheets.flatMap((s) => Object.keys(s.of || {})))] : [""];
      ids.forEach((id) => {
        const sheets = f.sheets.map((s) => ({ cls: s.cls, title: s.title && s.title !== "?" ? s.title : f.title,
          state: id ? (s.of || {})[id] : s.state, at: { form: f.form, sheet: s.cls, ids: id } }))
          .filter((s) => s.state !== "hidden" && (!id || s.state));
        if (sheets.length) {
          out.push({ key: sheetKey({ form: f.form, ids: id }), form: f.form, title: id ? `${f.title} ${id}` : f.title, name: f.title, id,
            adv: !!f.adv, sheets, todo: sheets.some((s) => s.state === "todo") });
        }
      });
    });
    return out;
  }
  const sheetKey = (s) => (s.ids ? `${s.form}/${s.ids}` : s.form);
  /** The first incomplete sheet the forms list (the GUI's Next goes there): {title, sheetTitle, at}, or null. */
  function firstTodo(data) {
    for (const f of formsOf(data)) {
      const s = f.sheets.find((x) => x.state === "todo" && x.cls);
      if (s) return { title: f.title, sheetTitle: s.title, at: s.at };
    }
    return null;
  }
  /** Which forms are open, as the user left them (prefs wb.insp.forms {form class: bool}; "+TYPE":
   *  the more forms of a type); by default a form the docs name or one with an incomplete sheet.
   *  Which sections (sectionsOf) likewise, a type's own (wb.insp.secs {TYPE: {section key: bool}}). */
  const FORMS_KEY = "wb.insp.forms", SECS_KEY = "wb.insp.secs";
  const opensOf = (key) => { try { return JSON.parse(prefGet(key) || "{}") || {}; } catch (e) { return {}; } };
  const formOpens = () => opensOf(FORMS_KEY);
  function setOpen(key, open) {
    const o = formOpens();
    o[key] = open;
    prefSet(FORMS_KEY, JSON.stringify(o));
  }
  function setSec(type, key, open) {
    const o = opensOf(SECS_KEY);
    o[type] = Object.assign(isObj(o[type]) ? o[type] : {}, { [key]: open });
    prefSet(SECS_KEY, JSON.stringify(o));
  }
  /** The object's type as the prefs key it: RADFRAC, a stream's STREAM, a model object's record type. */
  const typeKey = (tab, rec, data) => String((data && data.type) || (rec.insp.target.kind === "block" ? blockType(tab, rec.insp.target.name) : "")
    || rec.insp.target.kind).toUpperCase();
  /** A sheet picked (its capsule, the head's dot, a missing item): its form open, its fields asked for. */
  function openSheet(pane, tab, rec, at) {
    rec.insp.sheet = at;
    rec.sheetAsks = 0;
    if (at.sheet) askSheet(rec, tab);
    pane.sigs.irows = null;
    renderInspector(pane, tab, sessOf(tab));
    const el = pane.q(".insp .irows .isc.on, .insp .irows .isec.pick");
    if (el) el.scrollIntoView({ block: "nearest" });
  }

  /** Check for edits made in Aspen: where the server finds edits made in Aspen's own window
   *  (catalog.features "external"), a quiet button under the inspector's actions reads every
   *  input field of the block or stream shown (event ext_deep; the tab's ext_deep holds its
   *  progress and outcome). The first press only notes the fields as they are; a later one finds
   *  what changed there since and records it. While it reads, a thin bar sweeps (the server says
   *  only that it is reading: a RadFrac takes about a second); then one line says what came of
   *  it, with See in Changes where it found edits. A press waits for the server's word until the
   *  tab's ext_deep moves (DEEP_WAIT at most). */
  const DEEP_WAIT = 15000;
  /** The tab's ext_deep when it is about tg (the server's name may differ in case), else null. */
  function deepOf(tab, tg) {
    const d = tab.ext_deep, o = d && typeof d === "object" ? d.obj : null;
    return o && String(o.kind || "").toLowerCase() === tg.kind && String(o.name || "").toUpperCase() === String(tg.name).toUpperCase() ? d : null;
  }
  /** What a check came to, in the page's words: {cls, text, tip, see}. */
  function deepWords(d, name) {
    const n = Number(d.n) || 0, k = Number(d.found) || 0, st = d.status;
    if (st === "done") {
      if (d.noted === false && !k) return { cls: "bad", text: t("ext_deep_fail", name, "~/.aspen-mcp/journal") };
      let s = d.baseline === "new" ? t("ext_deep_base", name, n) + (/^(reopened|replaced)$/.test(d.reason || "") ? t("ext_deep_afresh", name) : "")
        : k ? t(k === 1 && I18N.lang !== "zh" ? "ext_deep_found_1" : "ext_deep_found", k, name, n) : t("ext_deep_none", name, n);
      if (d.partial) s += t("ext_deep_partial", n);
      return { cls: k ? "found" : "", text: s, see: k > 0 };
    }
    if (st === "busy") return { cls: "warn", text: t("ext_deep_busy"), tip: d.text || "" };
    if (st === "changed") return { cls: "warn", text: t("ext_deep_changed", name) };
    if (st === "missing") return { cls: "warn", text: t("ext_deep_missing", name) };
    return { cls: "bad", text: d.text ? String(d.text) : t("ext_deep_fail", name, d.error || st || "?") };
  }
  function renderDeep(pane, tab, rec) {
    const box = pane.q(".insp .iext"), btn = pane.q('.insp .ia [data-act="ext_deep"]');
    if (!box) return;
    if (!feature("external") || !rec.insp || rec.insp.target.kind === "object") {
      if (!box.classList.contains("hidden")) { box.classList.add("hidden"); box.innerHTML = ""; }
      if (btn) btn.classList.add("hidden");
      pane.sigs.iext = null;
      return;
    }
    const tg = rec.insp.target, d = deepOf(tab, tg), p = pane.deepAsk;
    if (p && (p.tab !== tab.id || p.key !== keyOf(tg) || p.sig !== JSON.stringify(tab.ext_deep || null) || Date.now() - p.at > DEEP_WAIT)) pane.deepAsk = null;
    const asked = !!pane.deepAsk, reading = asked || (!!d && d.status === "running");
    const why = !wb.connected ? t("why_off") : !isOpen(tab) ? t("why_closed", tab.session)
      : wb.state.tabs.some((x) => x.session === tab.session && busy(x)) ? t("ext_deep_why_busy") : "";
    if (!changed(pane, "iext", [tab.id, I18N.lang, keyOf(tg), reading, why, reading ? null : d])) return;
    // the button: an icon in the head (its name and what it does in its tooltip); its line under it
    // while it reads and once it found something to say
    if (btn) {
      btn.classList.remove("hidden");
      btn.disabled = !!(why || reading);
      btn.title = why || `${t("ext_deep_btn")}\n${t("tip_ext_deep_btn", tg.name)}`;
      btn.setAttribute("aria-label", t("ext_deep_btn"));
    }
    box.classList.toggle("hidden", !reading && !d);
    let html = "";
    if (reading) {
      html += `<div class="ixd run" role="status" title="${esc(t("tip_ext_deep_run"))}"><span class="ixd-t">${esc(t("ext_deep_run", tg.name))}</span>`
        + `<i class="ixd-bar" aria-hidden="true"><i></i></i></div>`;
    } else if (d) {
      const w = deepWords(d, tg.name), at = Number(d.t) > 0 ? `<span class="ixd-at">${esc(hhmm(d.t))}</span>` : "";
      html += `<div class="ixd${w.cls ? ` ${w.cls}` : ""}" role="status"${w.tip ? ` title="${esc(w.tip)}"` : ""}>${at}<span class="ixd-t">${esc(w.text)}</span>`
        + (w.see ? `<button class="ixd-see flat" data-act="ext_see" title="${esc(t("tip_ext_deep_see"))}">${esc(t("ext_deep_see"))}</button>` : "") + "</div>";
    }
    box.innerHTML = html;
    const line = box.querySelector(".ixd");
    if (line && !reading && pane.deepShown !== JSON.stringify(d)) {   // a new outcome comes in once
      pane.deepShown = JSON.stringify(d);
      line.classList.add("in");
    }
  }
  /** The button pressed: the check asked for, the button off and the bar sweeping until the
   *  server's word comes (or DEEP_WAIT, then drawn again). */
  function deepAsk(pane, tab, tg) {
    pane.deepAsk = { tab: tab.id, key: keyOf(tg), sig: JSON.stringify(tab.ext_deep || null), at: Date.now() };
    wb.post({ type: "ext_deep", tab: tab.id, target: { kind: tg.kind, name: tg.name } });
    clearTimeout(pane.deepTimer);
    pane.deepTimer = setTimeout(() => { const t2 = tabOf(pane.tabId); if (t2) renderInspector(pane, t2, sessOf(t2)); }, DEEP_WAIT + 50);
    renderInspector(pane, tab, sessOf(tab));
  }

  /** A server and a window that make help cards (help.js). */
  const helpOn = () => WBH.on();
  /** A missing row's rule for its tooltip: Aspen's words, or the workbench's own rule (a column's
   *  operating specs) in the window's language, named as the workbench's (missing.js WBM.rule). */
  const missRule = (r) => {
    const rl = WBM.rule ? WBM.rule(r) : { text: r.rule, own: false };
    return t(rl.own ? "tip_insp_miss_rule_own" : "tip_insp_miss_rule", rl.text);
  };

  /** A row's tooltip: what the field is and what it takes, in the window's language -- its
   *  name (ours first in Chinese), the docs' first sentence on it and our hint, then what to enter
   *  (a number in its unit, the others it takes; one of its menu's values; a component or stream
   *  of the model; a word) or, for a result, that Aspen computes it; why it is greyed (one the
   *  settings turn off, r.off "cc": by the option field above it on its sheet, rows), old or
   *  missing. Never its tree path: the field's help card (?) has that. */
  function fieldTip(tab, rec, r, lc, stale, rows) {
    const sep = zh() ? "、" : ", ", few = (xs) => xs.slice(0, 4).join(sep) + (xs.length > 4 ? "…" : "");
    const doc = r.doc ? (/^.*?[.。;；](?=\s|$)/.exec(String(r.doc)) || [String(r.doc)])[0].slice(0, 160) : "";
    const list = listOf(tab, r), others = (r.units || []).filter((u) => u !== r.unit);
    const miss = r.missing && r.input, req = miss && r.certainty === "required";
    const what = r.input && r.enterable === false ? offWhy(tab, rec, r, rows)
      : !r.input ? t(r.unit ? "tip_out_u" : "tip_out", r.unit)
        : list && r.choices && r.choices.length ? t("tip_in_list", few(list.map((x) => x.label)))
          : list ? t(r.pick === "comp" ? "tip_in_comp" : "tip_in_stream", list[0].label)
            : r.unit ? t("tip_in_num_u", r.unit) + (others.length ? t("tip_in_units", few(others)) : "")
              : typeof r.value === "number" ? t("tip_in_num") : typeof r.value === "string" && r.value.trim() ? t("tip_in_word") : "";
    return [lc ? WBL.text(lc, "field", true) : I18N.pick(r.label), doc, zh() && lc && lc.gl && lc.hint, what, stale && t("tip_stale"),
      miss && t(req ? "tip_insp_miss_row" : "tip_miss_empty"), miss && r.rule && missRule(r), lc && lc.src === "code" && t("loc_code")]
      .filter(Boolean).join("\n");
  }
  /** Why an input is greyed: the option field above it on its sheet (its own rows or the sheet's,
   *  the same docs table) and what it is set to, where the current settings turn it off (r.off "cc":
   *  a CC condition of the sheet, inputs_check.off_fields); else that the settings do not use it. */
  function offWhy(tab, rec, r, rows) {
    const at = rows.indexOf(r), by = r.off === "cc" && at > 0 ? rows.slice(0, at).reverse()
      .find((x) => x.input && x.enterable !== false && x.choices && x.choices.length && !!x.sheet === !!r.sheet && (x.g || "") === (r.g || "")) : null;
    if (!by) return t("tip_inactive");
    const lc = locOf(tab, rec, by), o = by.opt;
    return t("tip_off_by", lc ? (zh() && lc.gl) || WBL.text(lc, "field") : I18N.pick(by.label), (o && ((zh() && o.zh) || o.en)) || String(by.value ?? ""));
  }
  /** The values an input takes from a list, as its menu's items {label, tip, code}: Aspen's options
   *  by what each means (r.choices, the code in its tooltip), the model's components or streams
   *  (r.pick); null for a field typed in. */
  function listOf(tab, r) {
    if (!r.input) return null;
    if (r.choices && r.choices.length) {
      return r.choices.map((c) => ({ label: (zh() && c.zh) || c.en || c.code, code: c.code, tip: [t("insp_opt_code", c.code), c.desc].filter(Boolean).join("\n") }));
    }
    const fs = sessOf(tab).flowsheet || {};
    const xs = r.pick === "comp" ? fs.components || [] : r.pick === "stream" ? (fs.streams || []).map((x) => x.name) : [];
    return xs.length ? xs.map((x) => ({ label: String(x), code: String(x) })) : null;
  }

  /** A row's help card (its "?", or the ⊕ menu's first item), beside the inspector at the row's
   *  height: what the row knows goes along (its prompt and basis, where the server read them),
   *  so the card needs nothing of Aspen. The row stays marked while it is open. */
  function helpRow(pane, i, anchor) {
    const tab = tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id), r = pane.rows && pane.rows[i];
    if (!tab || !rec || !rec.insp || !r || !helpOn()) return;
    const tg = rec.insp.target, lc = locOf(tab, rec, r);
    const row = { value: r.value ?? null, unit: r.unit ?? null, units: r.units || [] };
    if (r.input) row.enterable = r.enterable !== false;
    if (typeof r.prompt === "string") row.prompt = r.prompt;
    if (r.basis) row.basis = r.basis;
    const at = anchor && anchor.isConnected ? anchor : pane.q(`.insp .irows .irow[data-i="${i}"] .ihelp`);
    hideProv(pane);
    const opened = WBH.open(at, { path: r.path, type: tg.kind === "block" ? blockType(tab, tg.name) : null, row },
      { tab, beside: pane.q(".insp"), title: lc ? WBL.text(lc, "field") : I18N.pick(r.label), onClose: () => setSel(pane, null) });
    if (opened) setSel(pane, r.path);
  }
  /** The row selected: a click on it, or the field gone to (focusRow). It keeps its "?"
   *  showing (.pk) until another row is, while the inspector stays on the same object. */
  function pickRow(pane, el) {
    const tab = tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id), r = el && pane.rows && pane.rows[Number(el.dataset.i)];
    if (!rec || !rec.insp || !r) return;
    pane.rowPk = { key: keyOf(rec.insp.target), path: String(r.path || "").toLowerCase() };
    pane.q(".insp .irows").querySelectorAll(".irow.pk").forEach((x) => { if (x !== el) x.classList.remove("pk"); });
    el.classList.add("pk");
  }
  /** The row whose card is open: marked (.sel, its "?" showing) in place, and again when the
   *  rows are drawn anew. */
  function setSel(pane, path) {
    pane.fhSel = path ? String(path).toLowerCase() : null;
    pane.q(".insp .irows").querySelectorAll(".irow").forEach((el) => {
      const r = pane.rows && pane.rows[Number(el.dataset.i)];
      el.classList.toggle("sel", !!pane.fhSel && !!r && String(r.path || "").toLowerCase() === pane.fhSel);
    });
  }
  /** A row's loc: the server's on the row, or a better one learned since (WBL.best: a field
   *  still named by its code is asked to be learned). */
  const locOf = (tab, rec, r) => WBL.best(r.path, rec && rec.insp && rec.insp.target.kind === "block"
    ? blockType(tab, rec.insp.target.name) : null, r.loc, tab.session);

  /** The inspector's rows, filtered: redrawn when the data, the filter or what may be edited
   *  changes. Until the values come it says they are on their way, or that they cannot come
   *  while the window is not connected. Read like Aspen's form: the inputs under Aspen's
   *  sheets (sectionsOf), the first open, the others a line each to open; then the object's other
   *  forms and subobjects behind one line (moreHtml); the results apart -- beside the inputs where
   *  the inspector is wide (style.css), under them else -- one line saying they come with a run
   *  until one has. An input is a box to type in, its unit beside it (an option code shown by
   *  what it means: r.opt), an empty required one outlined; one the current settings do not use
   *  (enterable false: Flash2 with PD has no temperature) greyed in its place, as Aspen greys it;
   *  a result plain text. While an input set by hand waits for a run (staleAt), the results are
   *  the last run's: their heading says "old" and their values are faded, the tooltip saying why.
   *  Each row is labelled by its loc: Aspen's English, in Chinese ours first and Aspen's after it,
   *  quieter (two lines at most, never cut short of it; where it is in Aspen in the tooltip, with
   *  what the docs say it is for); the fields All fields adds are Aspen's own variables (named by
   *  the prompt the user's Aspen gives, else by their code).
   *  Where the model's change journal can be read (changes.js), a field changed shows its last
   *  change by its value, a dot in who made it's colour (provOf; the card of its history where
   *  the pointer rests on it: showProv). */
  const FILTER_MIN = 12;
  const empty = (v) => v === null || v === undefined || v === "";
  function renderRows(pane, tab, rec, data, ready, editable) {
    const old = !!staleAt(tab.session);
    const open = isOpen(tab);
    const P = (pane.prov = provOf(pane, tab, rec));
    const H = helpOn();
    // a stream's composition (app-comp.js): its own section, first among the results
    const cp = ready && WBA.cpSection ? WBA.cpSection(tab, rec.insp.target, old) : null;
    const sh = ready ? sheetOf(tab, rec) : null, opens = formOpens(), secs = opensOf(SECS_KEY)[typeKey(tab, rec, data)] || {};
    const shown = rec.insp.shown || (rec.insp.shown = new Set());
    const inp = pane.q(".ifilter"), many = !!ready && (data.rows.length > FILTER_MIN || !!rec.filter.trim() || document.activeElement === inp);
    if (ready && pane.saving && data.t > pane.saving.t) pane.saving = null;
    // drawn anew only when what they show changes: the rows read again with the same values are not
    // (a value written reads the object and its sheet again, a pass at a time: no time stamps here)
    if (!changed(pane, "irows", [tab.id, I18N.lang, keyOf(rec.insp.target), ready && { ...data, t: 0, reading: 0 }, rec.filter, editable, pane.saving,
      wb.connected, old, open, WBL.ver, P && P.ver, H, cp && cp.sig, rec.insp.sheet, sh && { ...sh, t: 0, req: 0 }, opens, secs, [...shown], pane.adding])) {
      renderStatus(pane, tab, rec, data, ready, many);
      focusRow(pane, tab, rec, data, ready);
      return;
    }
    const fv = document.activeElement && document.activeElement.closest && document.activeElement.closest(".insp .irows .vl");
    const fp = fv && pane.el.contains(fv) && pane.rows && (pane.rows[Number(fv.dataset.i)] || {}).path;   // (the value box the keyboard was on: kept on)
    let body;
    pane.rowSec = new Map();
    if (!ready) body = `<div class="hint">${esc(!wb.connected ? t("insp_offline") : open ? t("insp_loading") : t("why_closed", tab.session))}</div>`;
    else {
      const f = rec.filter.trim().toLowerCase();
      const has = (s) => String(s || "").toLowerCase().includes(f);
      const lcOf = (r) => locOf(tab, rec, r);
      // the sheet picked: its rows after the object's own, marked where the completeness check names them
      const miss = new Map(((isObj(data.missing) && data.missing.items) || []).map((x) => [low(x.path), x]));
      const srows = (sh ? sh.rows : []).map((r) => {
        const x = r.input && miss.get(low(r.path));
        return Object.assign({ sheet: true }, r, x ? { missing: true, certainty: x.certainty, rule: x.rule, rule_zh: x.rule_zh, rule_by: x.rule_by } : {});
      });
      const rows = [...data.rows, ...srows].filter((r) => { const lc = f && lcOf(r);
        return !f || has(I18N.pick(r.label)) || has(r.label && r.label.en) || has(r.path) || has(r.doc) || (lc && (has(lc.field) || has(lc.gl) || has(lc.code))); });
      pane.rows = rows;
      const tag = old ? ` <span class="oldtag" title="${esc(t("tip_stale"))}">${esc(t("stale_tag"))}</span>` : "";
      const raw = ` <small class="aspen">${esc(t("insp_raw"))}</small>`;
      const pk0 = pane.rowPk && pane.rowPk.key === keyOf(rec.insp.target) ? pane.rowPk.path : null;
      const head = (title, o = {}) => `<div class="sec">${esc(title)}${o.out ? tag : ""}${o.raw ? raw : ""}</div>`;
      // a value: an input's box (typed over in place where it may be; empty where the settings do
      // not use it), a result's text; a row's, a table's cell
      const vcell = (r, tip) => {
        const i = rows.indexOf(r), off = r.input && r.enterable === false, canEdit = editable && r.input && !off;
        const req = r.missing && r.input && r.certainty === "required" && empty(r.value);
        const o = r.input && !off && r.opt, said = o && ((zh() && o.zh) || o.en);
        const otip = o ? [said, said !== o.en && o.en, t("insp_opt_code", r.value), o.desc].filter(Boolean).join("\n") : "";
        const v = pane.saving && pane.saving.path === r.path ? esc(t("insp_saving")) : off ? ""
          : r.missing && r.input && empty(r.value) ? `<em class="imtag">${esc(t(req ? "insp_missing_tag" : "insp_empty_tag"))}</em>`
            : said ? esc(said) : r.input && empty(r.value) ? "" : esc(fmtVal(r.value));
        const unit = r.unit ? `<small>${esc(r.unit)}</small>` : "", menu = canEdit && !!listOf(tab, r);
        if (!r.input) return `<span class="vl" data-i="${i}"${tip ? ` title="${esc(tip)}"` : ""}>${v}${unit && ` ${unit}`}</span>`;
        return `<span class="vl in${canEdit ? " editable" : ""}${off ? " off" : ""}${req ? " req" : ""}" data-i="${i}"${canEdit ? ' tabindex="0"' : ""}`
          + `${tip ? ` title="${esc(tip)}"` : ""}><span class="vb${said ? " opt" : typeof r.value === "string" && !isFinite(Number(r.value)) ? " w" : ""}${menu ? " menu" : ""}"${otip ? ` title="${esc(otip)}"` : ""}>${v}</span>${unit && ` ${unit}`}</span>`;
      };
      // o.lab: a table's row, named by its label; o.rm: its remove button
      const row = (r, o = {}) => {
        const i = rows.indexOf(r), off = r.input && r.enterable === false;
        const lc = lcOf(r);
        const stale = old && !r.input;
        // what Aspen still needs: an empty field the completeness check names, marked
        // "missing" where a rule requires it (the rule in the tooltip: Aspen's, or the workbench's own so
        // named), "empty" where Aspen marks only its sheet incomplete (it may need any one of them)
        const miss = r.missing && r.input, req = miss && r.certainty === "required";
        const tip = fieldTip(tab, rec, r, lc, stale, rows);
        // its last change: a dot before the value in the colour of who made it, its words (who, when,
        // the value before) on its card, shown under the pointer or the keyboard's focus (the row's
        // tooltip kept off it: the card is its tooltip)
        const pv = lastOf(pane, r), act = pv && ["ai", "user", "program", "optimizer"].includes(pv.actor) ? pv.actor : "external";
        // the field's help card and ⊕: under the pointer or the keyboard, always on the
        // row selected (.pk: pickRow) and the one whose card is open (.sel)
        const sel = H && pane.fhSel && low(r.path) === pane.fhSel;
        const pk = pk0 && low(r.path) === pk0;
        return `<div class="irow ${r.input ? "in" : "out"}${stale ? " old" : ""}${off ? " inactive" : ""}${pv ? " pv" : ""}${sel ? " sel" : ""}${pk ? " pk" : ""}${miss ? " miss" : ""}${req ? " req" : ""}" draggable="true" data-i="${i}" title="${esc(tip)}">
          <span class="lb${lc && !o.lab ? " l1" : ""}">${o.lab ? esc(o.lab) : lc ? WBL.html(lc, "field", { title: false, zh1: true })
            : esc(I18N.pick(r.label))}</span>`
          + (pv ? `<span class="iprov" title=""><span class="pvt a-${act}" data-pv="${i}" tabindex="0" role="button" aria-label="${esc(WBC.provLine(pv, r.unit))}"><i class="pvd"></i></span></span>` : "")
          + vcell(r)
          + (H ? `<button class="ihelp" data-help="${i}" title="${esc(t("tip_fh"))}" aria-label="${esc(t("fh_what"))}" aria-haspopup="dialog">${icon("help")}</button>` : "")
          + `<button class="iadd" data-add="${i}" title="${esc(t("tip_iadd"))}" aria-haspopup="menu">${icon("add")}</button>`
          + (o.rm || "") + "</div>";
      };
      const sec = (title, list, o) => (list.length ? head(title, o) + list.map(row).join("") : "");
      const own = rows.filter((r) => !r.sheet), outs = own.filter((r) => !r.input);
      const cx = { row, vcell, can: editable && !busy(tab), index: (r) => rows.indexOf(r), adding: pane.adding, tip: (r) => fieldTip(tab, rec, r, lcOf(r), old && !r.input, rows) };
      // the sections: open as the viewer left them (a type's own), else the first with rows and any
      // with a required field missing; one a field was gone to (shown) and the sheet picked open too.
      // A sheet the docs have no rows of opens by being picked (its fields read: openSheet); one they
      // have rows of reads its other fields on a word at its foot. While filtering: the sections
      // with rows that match, open.
      const pk = rec.insp.sheet, S = sectionsOf(data, own.filter((r) => r.input && !r.extra));
      const first = S.find((x) => x.rows.length);
      const inputs = S.map((x) => {
        const here = !!(x.at && pk && pk.sheet && sheetKey(pk) === sheetKey(x.at) && pk.sheet === x.at.sheet);
        if (f && !x.rows.length) return "";
        const on = !!f || here || shown.has(x.key) || (!!x.rows.length && (secs[x.key] ?? (x === first || x.req)));
        // the sheet picked: its own read of a docs row in that row's place (a list's entry in its table
        // instead), its other fields after them
        const sp = new Map(here ? srows.filter((r) => rows.includes(r)).map((r) => [low(r.path), r]) : []);
        const mine = x.rows.flatMap((r) => { const y = sp.get(low(r.path)); return !y ? [r] : ((sh && sh.lists) || []).some((l) => inList(y, l)) ? [] : [y]; });
        const more = [...sp.values()].filter((r) => !mine.includes(r));
        [...x.rows, ...mine].forEach((r) => pane.rowSec.set(rows.indexOf(r), x.key));
        const all = x.rows.length && x.at && !here ? `<button class="isec-all flat" data-sec="${esc(x.key)}" title="${esc(t("tip_sheet_all"))}">${esc(t("insp_sheet_all"))}</button>` : "";
        return `<div class="isec${on ? " open" : ""}${here ? " pick" : ""}"><button class="isec-h flat" data-sec="${esc(x.key)}" aria-expanded="${on}"`
          + `${x.tip ? ` title="${esc(x.tip)}"` : ""}>${icon("chevron-right")}<span>${x.title.split(" › ").map((w) => WBL.title(w, true)).join(" › ")}</span>`
          + `${x.todo || x.req ? '<i class="idot" aria-hidden="true"></i>' : ""}</button>`
          + (on ? `<div class="isec-b">${mine.map((r) => row(r)).join("")}${here ? sheetBody(tab, rec, sh, more, cx) : all}</div>` : "") + "</div>";
      }).join("")
        + sec(t("insp_more_in"), own.filter((r) => r.input && r.extra), { raw: true })
        + (f ? "" : moreHtml(pane, tab, rec, data, sh, rows.filter((r) => r.sheet), cx, opens, S));
      // the results: their values, or before any run one line saying they come with it
      const results = (cp && !f ? cp.html : "") + (!outs.length ? "" : outs.some((r) => !empty(r.value)) ? sec(t("insp_results"), outs, { out: true })
        : `${head(t("insp_results"))}<div class="hint inone">${esc(t("insp_results_after"))}</div>`);
      body = (inputs ? `<div class="icol in">${inputs}</div>` : "") + (results ? `<div class="icol out">${results}</div>` : "");
      if (f && !rows.length) body = `<div class="hint">${esc(t(rec.insp.all ? "insp_nomatch" : "insp_nomatch_all"))}</div>`;
    }
    const was = pane.q(".insp .irows .ilab"), keep = was && { v: was.value, f: document.activeElement === was };
    const L = pane.q(".insp .irows"), top = L.scrollTop;
    L.innerHTML = body;
    L.scrollTop = top;
    const lab = pane.q(".insp .irows .ilab");     // a row or subobject being added keeps what was typed
    if (lab && keep) { lab.value = keep.v; if (keep.f) lab.focus(); } else if (lab) { lab.focus(); lab.select(); }
    const fi = !lab && fp ? pane.rows.findIndex((r) => r.path === fp) : -1, fe = fi >= 0 && L.querySelector(`.vl[data-i="${fi}"]`);
    if (fe && fe.tabIndex >= 0) fe.focus({ preventScroll: true });
    // the filter only where the list is long (more than FILTER_MIN rows), or while it is in use;
    // All fields then sits on the status line
    pane.q(".ifrow").classList.toggle("hidden", !many);
    renderStatus(pane, tab, rec, data, ready, many);
    reflash(pane, true);
    focusRow(pane, tab, rec, data, ready);
    if (pane.pv) showProv(pane, pane.pv.path, true);   // an open card follows its row, or goes with it
  }

  /** The inputs' sections, in Aspen's order: a section a sheet of the object's main forms (the
   *  forms the docs' general file names, not a collection's: formsOf), the docs' rows of its table
   *  (r.g "Setup | Configuration") in it; a table no sheet shown matches (no forms: not Aspen
   *  V15) one of its own after them, and the inputs no table holds last. Each {key, title, tip,
   *  rows, at (its sheet), todo (incomplete), req (a required field missing)}. */
  function sectionsOf(data, ins) {
    const out = formsOf(data).filter((f) => !f.adv && !f.id).flatMap((f) => f.sheets.filter((x) => x.cls)
      .map((x) => ({ key: `${f.form}/${x.cls}`, title: x.title, tip: `${f.title} › ${x.title}`, at: x.at, todo: x.state === "todo", rows: [],
        m: `${f.title}|${x.title}`.toLowerCase() })));
    [...new Set(ins.map((r) => r.g || ""))].forEach((g) => {
      const full = String(g).split(/\s*\|\s*/).join(" › ").replace(/`/g, ""), parts = full.replace(/\s*\(.*$/, "").split(" › ");
      const list = ins.filter((r) => (r.g || "") === g), hit = parts.length === 2 && out.find((x) => x.m === parts.join("|").toLowerCase());
      if (hit) hit.rows.push(...list);
      else out.push({ key: `g:${g}`, title: g ? parts[parts.length - 1] : t("insp_inputs"), tip: g && full !== parts[parts.length - 1] ? full : "", rows: list });
    });
    out.forEach((x) => { x.req = x.rows.some((r) => r.missing && r.certainty === "required"); });
    return out;
  }
  /** A sheet picked: its fields (srows: sheetHtml) and, until they are all here, why not. */
  function sheetBody(tab, rec, sh, srows, cx) {
    const why = !sh ? t("insp_loading") : sh.status === "waiting" ? t("insp_sheet_wait") : sh.status === "done" && !sh.rows.length ? t("insp_sheet_none") : "";
    return `${sheetHtml(tab, rec, sh, srows, cx)}${why || (sh && sh.status === "reading") ? `<div class="hint">${esc(why || t("insp_loading"))}</div>` : ""}`;
  }

  /** The object's other forms (on Aspen V15; formsOf: those no section shows) and its subobjects,
   *  behind one line ("More Aspen forms"), open as the viewer left it for the type (else where one has an
   *  incomplete sheet, its amber dot on the line), or while the sheet picked is among them. A row per form,
   *  open as the user left it (else one with an incomplete sheet); an open form shows its sheets
   *  as capsules, an amber dot on an incomplete one (on the form's row too); the sheet picked
   *  shows its fields (srows, drawn by row) under its form's capsules, read when picked (askSheet). */
  function moreHtml(pane, tab, rec, data, sh, srows, cx, opens, S) {
    const shownF = new Set(S.filter((x) => x.at).map((x) => x.at.form));
    const list = formsOf(data).filter((f) => f.id || !shownF.has(f.form)), subs = subsHtml(pane, tab, rec, data, cx.can);
    if (!list.length && !subs) return "";
    const pk = rec.insp.sheet, pkey = pk ? sheetKey(pk) : null;
    const dot = '<i class="idot" aria-hidden="true"></i>';
    const one = (f) => {
      const here = pkey === f.key && f.sheets.some((x) => x.cls === pk.sheet);
      const isOpen = here || (opens[f.form] ?? (f.todo || !f.adv));
      let h = `<div class="ifm${isOpen ? " open" : ""}"><button class="ifm-h flat" data-form="${esc(f.key)}" aria-expanded="${isOpen}"`
        + `${f.todo ? ` title="${esc(t("tip_form_todo"))}"` : ""}>${icon("chevron-right")}<span>${WBL.title(f.name, true)}${f.id ? ` ${esc(f.id)}` : ""}</span>${f.todo ? dot : ""}</button>`;
      if (!isOpen) return `${h}</div>`;
      h += `<div class="ifs">${f.sheets.map((x, i) => `<button class="isc${here && x.cls === pk.sheet ? " on" : ""}" data-form="${esc(f.key)}" data-si="${i}"`
        + `${x.cls ? "" : " disabled"} title="${esc(`${f.title} › ${x.title}${x.state === "todo" ? `\n${t("tip_sheet_todo")}` : ""}`)}">`
        + `${WBL.title(x.title, true)}${x.state === "todo" ? dot : ""}</button>`).join("")}</div>`;
      if (here) h += `<div class="ifr">${sheetBody(tab, rec, sh, srows, cx)}</div>`;
      return `${h}</div>`;
    };
    const plus = `+${typeKey(tab, rec, data)}`, on = list.some((f) => f.key === pkey) || !!(cx.adding && cx.adding.sub) || (opens[plus] ?? list.some((f) => f.todo));
    return `<div class="imore${on ? " open" : ""}"><button class="ifm-more flat" data-more="${esc(plus)}" aria-expanded="${on}" title="${esc(t("tip_forms_more"))}">`
      + `${icon("chevron-right")}<span>${esc(t("insp_forms_more"))}</span>${list.some((f) => f.todo) ? dot : ""}</button>`
      + (on ? `<div class="imore-b">${list.map(one).join("")}${subs}</div>` : "") + "</div>";
  }

  /** A sheet's fields: its lists of values (the tab's isheet.lists) as small tables, the
   *  lists whose rows share a dimension name one table with a column each (a row inserted in one
   *  is in all: Aspen's table); the other fields as rows. */
  const low = (p) => String(p || "").toLowerCase();
  const tbOf = (sh, key) => { const ls = (sh && sh.lists) || [], k = ls.find((l) => l.path === key); return k ? ls.filter((l) => l.dn === k.dn) : []; };
  const inList = (r, l) => { const p = low(r.path), q = low(l.path); return p === q || (p.startsWith(`${q}\\`) && !p.slice(q.length + 1).includes("\\")); };
  function sheetHtml(tab, rec, sh, srows, cx) {
    const lists = (sh && sh.lists) || [], done = new Set();
    return srows.map((r) => {
      const l = lists.find((x) => inList(r, x));
      if (!l) return cx.row(r);
      if (done.has(l.dn)) return "";
      done.add(l.dn);
      return tableHtml(tab, rec, tbOf(sh, l.path), srows, cx);
    }).join("");
  }
  /** One table: its lists' names and + (a row: its label typed, a stream or component offered),
   *  a row per label with − (one list: a field row of its own, ⊕ and help as any row; several: a
   *  value per column). */
  function tableHtml(tab, rec, cols, srows, cx) {
    const key = cols[0].path, lk = cols[0].lk, multi = cols.length > 1;
    const name = (l) => (l.loc ? WBL.text(l.loc, "field") : String(l.path).split("\\").pop());
    const labs = [...new Set(cols.flatMap((l) => srows.filter((r) => inList(r, l) && low(r.path) !== low(l.path))
      .map((r) => String(r.path).slice(l.path.length + 1))))];
    const cell = (l, lab) => srows.find((r) => low(r.path) === low(`${l.path}\\${lab}`));
    const rm = (lab) => (cx.can ? `<button class="itb-rm" data-tb="${esc(key)}" data-lab="${esc(lab)}" title="${esc(t("tip_row_rm", lab))}" aria-label="${esc(t("tip_row_rm", lab))}">${icon("minus")}</button>` : "");
    // the head: the list's name, or several lists' (Aspen's word each, our Chinese beside it; the whole in the tooltip) over their columns
    const names = multi ? `<span></span>${cols.map((l) => `<span title="${esc(name(l))}">${l.loc ? WBL.html(l.loc, "field", { title: false }) : esc(name(l))}</span>`).join("")}`
      : `<span>${cols[0].loc ? WBL.html(cols[0].loc, "field", { title: false }) : esc(name(cols[0]))}</span>`;
    let h = `<div class="itb${multi ? " multi" : ""}" style="--n:${cols.length}"><div class="itb-h">${names}`
      + (cx.can ? `<button class="itb-add" data-tb="${esc(key)}" title="${esc(t("tip_row_add"))}" aria-label="${esc(t("tip_row_add"))}">${icon("plus")}</button>` : "") + "</div>";
    h += labs.map((lab) => {
      if (!multi) return cx.row(cell(cols[0], lab), { lab, rm: rm(lab) });
      const cs = cols.map((l) => cell(l, lab));
      return `<div class="irow in itr" data-i="${cx.index(cs.find(Boolean))}"><span class="lb">${esc(lab)}</span>`
        + `${cs.map((r) => (r ? cx.vcell(r, cx.tip(r)) : '<span class="vl">—</span>')).join("")}${rm(lab)}</div>`;
    }).join("");
    if (cx.adding && cx.adding.tb === key) {
      const opts = choices(tab, rec, lk, labs);
      h += `<div class="irow itr add"><input class="ilab" data-tb="${esc(key)}"${lk === "stage" ? ' type="number" min="1" step="1"' : ""}`
        + ` placeholder="${esc(t(`row_lk_${lk}`))}" aria-label="${esc(t(`row_lk_${lk}`))}" value="${esc(opts[0] || "")}"${opts.length ? ' list="ilab-dl"' : ""}>`
        + (opts.length ? `<datalist id="ilab-dl">${opts.map((o) => `<option value="${esc(o)}">`).join("")}</datalist>` : "") + "</div>";
    }
    return `${h}</div>`;
  }
  /** What a new row may be labelled (not taken yet): the block's streams, the components; a
   *  numbered list its next number. */
  function choices(tab, rec, lk, taken) {
    const fs = sessOf(tab).flowsheet || {}, nm = rec.insp.target.name, free = (xs) => xs.filter((x) => !taken.some((y) => low(y) === low(x)));
    if (lk === "stream") return free((fs.streams || []).filter((x) => x.from === nm || x.to === nm).map((x) => x.name));
    if (lk === "comp") return free((fs.components || []).map(String));
    if (lk === "text") return [String(Math.max(0, ...taken.map(Number).filter(Number.isInteger)) + 1)];
    return [];
  }

  /** The block's subobjects (inspect's subs): a line a collection with members -- each a capsule
   *  that opens its first sheet, − to remove it, + to add one (its ID typed: the next number) --
   *  a nested one (internals' sections) a line per member it hangs under; the empty ones behind
   *  one + menu. */
  function subsOf(rec, data) {
    const subs = (data && data.subs) || [], ids = Object.fromEntries(subs.map((x) => [x.coll, x.ids]));
    const base = `\\Data\\Blocks\\${rec.insp.target.name}\\Subobjects\\`, out = [];
    subs.filter((x) => Array.isArray(x.ids)).forEach((x) => {
      const [top, sub] = x.coll.split("/");
      (sub ? ids[top] || [] : [""]).forEach((p) => out.push({ title: p ? `${sub} ${p}` : top, name: sub || top, at: p, forms: x.forms || [],
        folder: base + (p ? `${top}\\${p}\\Subobjects\\${sub}` : top), full: (id) => (p ? `${p}/${id}` : id),
        ids: p ? x.ids.filter((v) => v.startsWith(`${p}/`)).map((v) => v.slice(p.length + 1)) : x.ids.filter((v) => !v.includes("/")) }));
    });
    return out;
  }
  /** A new subobject's ID: the next number after the members' (P-1, P-2 -> P-3), else 1. */
  const nextId = (ids) => {
    const m = /^(.*?)(\d+)$/.exec(ids[ids.length - 1] || "");
    return m ? m[1] + (Math.max(...ids.map((v) => Number((/(\d+)$/.exec(v) || [])[1]) || 0)) + 1) : String(ids.length + 1);
  };
  function subsHtml(pane, tab, rec, data, can) {
    const all = rec.insp.target.kind === "block" ? subsOf(rec, data) : [], add = pane.adding && pane.adding.sub;
    const shown = all.filter((c) => c.ids.length || add === c.folder), rest = all.filter((c) => !shown.includes(c));
    if (!shown.length && !(can && rest.length)) return "";
    const line = (c) => `<div class="isub"><span class="isub-t">${WBL.title(c.name, true)}${c.at ? ` ${esc(c.at)}` : ""}</span><div class="ifs">`
      + c.ids.map((id) => `<span class="isg"><button class="isc" data-sub="${esc(c.folder)}" data-id="${esc(id)}">${esc(id)}</button>`
        + (can ? `<button class="isx" data-subrm="${esc(c.folder)}" data-id="${esc(id)}" title="${esc(t("tip_sub_rm", `${c.title} ${id}`))}" aria-label="${esc(t("tip_sub_rm", id))}">${icon("minus")}</button>` : "") + "</span>").join("")
      + (add === c.folder ? `<input class="ilab isub-in" data-sub="${esc(c.folder)}" value="${esc(nextId(c.ids))}" aria-label="${esc(t("tip_sub_add", c.title))}">`
        : can ? `<button class="isc isub-add" data-subadd="${esc(c.folder)}" title="${esc(t("tip_sub_add", c.title))}" aria-label="${esc(t("tip_sub_add", c.title))}">${icon("plus")}</button>` : "")
      + "</div></div>";
    return shown.map(line).join("")
      + (can && rest.length ? `<button class="ifm-more flat isub-more" title="${esc(t("tip_sub_more"))}" aria-haspopup="menu">${icon("plus")}<span>${esc(t("insp_sub_more"))}</span><small>${rest.length}</small></button>` : "");
  }
  /** A capsule pressed: the member's first sheet opened. */
  function openSub(pane, tab, rec, folder, id) {
    const c = subsOf(rec, tab.inspect).find((x) => x.folder === folder), full = c && c.full(id);
    const f = c && formsOf(tab.inspect).find((x) => c.forms.includes(x.form) && x.key === sheetKey({ form: x.form, ids: full }));
    const s = f && f.sheets.find((x) => x.cls);
    if (s) openSheet(pane, tab, rec, s.at);
  }
  /** A row or a subobject added (the line's input: Enter; Escape or leaving it puts it away) or
   *  removed: the event struct. */
  function structPost(pane, tab, ev) {
    pane.adding = null;
    if (ev) wb.post(Object.assign({ type: "struct", tab: tab.id }, ev));
    pane.sigs.irows = null;
    renderInspector(pane, tab, sessOf(tab));
  }
  function addDone(pane, tab, rec, el, ok) {
    const v = el.value.trim();
    if (!ok || (!v && !el.dataset.tb)) structPost(pane, tab, null);
    else if (el.dataset.tb) structPost(pane, tab, { op: "row_add", lists: tbOf(sheetOf(tab, rec), el.dataset.tb).map((l) => l.path), label: v });
    else structPost(pane, tab, { op: "sub_add", path: el.dataset.sub, label: v });
  }

  /** The history of the inspected object's rows (changes.js WBC.forObject: read once, a
   *  moment after the pick, and again when the journal moves; the rows are drawn again when
   *  it comes), or null where the journal cannot be read. */
  function provOf(pane, tab, rec) {
    if (!window.WBC || !WBC.forObject || !rec.insp) return null;
    const ctx = changesCtx(pane, tab);
    ctx.onProv = () => { const t2 = tabOf(pane.tabId), r2 = t2 && wb.recs.get(t2.id); if (r2 && r2.insp) renderInspector(pane, t2, sessOf(t2)); };
    return WBC.forObject(ctx, rec.insp.target);
  }
  /** A row's newest change recorded, or null. */
  function lastOf(pane, r) {
    const P = pane.prov, h = P && r && r.path ? P.paths[String(r.path).toLowerCase()] : null;
    return Array.isArray(h) && h.length && h[0] && typeof h[0] === "object" ? h[0] : null;
  }

  /** The card of a row's last changes, beside the inspector at the row's height: shown once
   *  the pointer rests on the row's last-change line (PROV_MS; at once from one card to the
   *  next, on a click or the keyboard's focus), kept while the pointer is on the line or the
   *  card (following the row as the rows scroll), gone when it leaves (HIDE_MS), on Escape, or
   *  with its row out of view or gone. */
  const PROV_MS = 250, HIDE_MS = 350;
  function provCard(pane) {
    if (pane.pvCard) return pane.pvCard;
    const card = (pane.pvCard = document.createElement("div"));
    card.className = "ipv-card hidden";
    pane.q(".insp").appendChild(card);
    return card;
  }
  function showProv(pane, path, again) {
    clearTimeout(pane.pvTimer);
    pane.pvWant = null;
    const i = (pane.rows || []).findIndex((r) => String(r.path || "").toLowerCase() === path);
    const r = i >= 0 ? pane.rows[i] : null, P = pane.prov, h = r && P ? P.paths[path] : null;
    const line = r && pane.q(`.insp .irows .pvt[data-pv="${i}"]`);
    if (!line || !Array.isArray(h) || !h.length) { hideProv(pane); return; }
    const card = provCard(pane), html = WBC.provCard(h, r.unit) + backHtml(pane, r), fresh = card.classList.contains("hidden");
    if (card._h !== html) { card._h = html; card.innerHTML = html; }
    pane.pv = { path };
    card.classList.remove("hidden");
    placeProv(pane, card, line);
    if (fresh && !again) { card.classList.remove("in"); void card.offsetWidth; card.classList.add("in"); }
  }
  /** The card's way back (where the server takes changes back): ↶ "Back to the previous value (1.5)", the
   *  undo of the field's last change, previewed first. An input only; "" otherwise. */
  function backHtml(pane, r) {
    const pv = feature("undo") && settable(r) ? lastOf(pane, r) : null, was = pv && pv.id && WBC.provWas(pv, r.unit);
    return was ? `<button class="pvc-back flat" data-act="prov_revert" title="${esc(t("tip_prov_revert_on"))}">${icon("undo")}`
      + `<span>${esc(t("prov_revert", was))}</span></button>` : "";
  }
  /** Take a row's last change back: its preview, under the button pressed (undoOpen). */
  function revertRow(pane, r, anchor) {
    const tab = tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id), pv = lastOf(pane, r);
    if (!tab || !pv || !pv.id) return;
    const lc = rec ? locOf(tab, rec, r) : null, tg = rec && rec.insp ? rec.insp.target : null;
    const name = `${tg ? `${tg.name} › ` : ""}${lc ? WBL.text(lc, "field") : I18N.pick(r.label)}`;
    undoOpen(tab, { ids: [pv.id], anchor, label: name, field: true, redo: !!pv.revert_of });
  }
  /** Beside the inspector, level with the row, held inside the flowsheet's area (it scrolls
   *  where taller); an inspector out to the card's left edge (its default) leaves no room
   *  there: beside the row inside it, over the other column, where that has room; else over it,
   *  under the row (over it where there is more room), its right edge the row's. */
  function placeProv(pane, card, line) {
    const b = pane.q(".insp").getBoundingClientRect(), a = pane.q(".fs-wrap").getBoundingClientRect();
    const row = line.closest(".irow").getBoundingClientRect(), out = Math.floor(b.left - a.left - 16);
    const right = Math.floor(b.right - row.right - 16), left = Math.floor(row.left - b.left - 16);
    const at = out >= 240 ? "out" : right >= 240 ? "right" : left >= 240 ? "left" : "over", over = at === "over";
    card.style.left = at === "right" ? `${Math.round(row.right - b.left + 8)}px` : "auto";
    card.style.right = over ? `${Math.round(b.right - row.right)}px` : at === "left" ? `${Math.round(b.right - row.left + 8)}px` : "";
    card.style.maxWidth = `${over ? Math.floor(row.width) : { out, right, left }[at]}px`;
    card.style.maxHeight = `${Math.max(80, Math.floor(over ? Math.max(a.bottom - row.bottom, row.top - a.top) - 12 : a.height - 16))}px`;
    const h = card.offsetHeight, up = over && row.bottom + 4 + h > a.bottom - 8;
    const top = !over ? Math.max(a.top + 8, Math.min(row.top - 4, a.bottom - 8 - h)) : up ? Math.max(a.top + 8, row.top - 4 - h) : row.bottom + 4;
    card.style.top = `${Math.round(top - b.top)}px`;
  }
  /** The rows scrolled (by hand, or to bring a focused line into view): the card follows its
   *  row, and goes once the row is out of the rows' view. */
  function followProv(pane) {
    if (!pane.pv || !pane.pvCard) return;
    const i = (pane.rows || []).findIndex((r) => String(r.path || "").toLowerCase() === pane.pv.path);
    const line = i >= 0 && pane.q(`.insp .irows .pvt[data-pv="${i}"]`);
    const a = line && line.getBoundingClientRect(), b = pane.q(".insp .irows").getBoundingClientRect();
    if (!line || a.bottom < b.top || a.top > b.bottom) hideProv(pane);
    else placeProv(pane, pane.pvCard, line);
  }
  /** Hide the card; true when it was shown. */
  function hideProv(pane) {
    clearTimeout(pane.pvTimer);
    pane.pvWant = null;
    const card = pane.pvCard, shown = !!card && !card.classList.contains("hidden");
    pane.pv = null;
    if (shown) card.classList.add("hidden");
    return shown;
  }
  const pvPath = (pane, el) => { const r = pane.rows && pane.rows[Number(el.dataset.pv)]; return r ? String(r.path || "").toLowerCase() : null; };
  /** The pointer came onto a row's last-change line (or the card: it stays). */
  function provOver(pane, ev) {
    const el = ev.target.closest && ev.target.closest(".pvt, .ipv-card");
    if (!el) return;
    clearTimeout(pane.pvTimer);
    if (el.classList.contains("ipv-card")) return;
    const path = pvPath(pane, el);
    if (!path || (pane.pv && pane.pv.path === path)) return;
    if (pane.pv) { showProv(pane, path); return; }   // from one card to the next: at once
    if (pane.pvWant === path) return;              // (on its way)
    pane.pvWant = path;
    pane.pvTimer = setTimeout(() => showProv(pane, path), PROV_MS);
  }
  /** The pointer left the line or the card, and not for the other one: the card goes. */
  function provOut(pane, ev) {
    const from = ev.target.closest && ev.target.closest(".pvt, .ipv-card"), to = ev.relatedTarget;
    if (!from || (to && to.closest && from.contains(to))) return;
    if (to && to.closest && to.closest(".ipv-card, .pvt")) return;
    clearTimeout(pane.pvTimer);
    pane.pvWant = null;
    if (pane.pv) pane.pvTimer = setTimeout(() => hideProv(pane), HIDE_MS);
  }
  /** The field a record in the Changes panel or a missing item named (pick's o.focus), once the
   *  rows are here -- the sheet's too, where one is picked (its row, where both have it): its
   *  section opened (rec.insp.shown), scrolled into the rows' view and flashed once (a tint that
   *  fades out); one named on the status line (f.key) its value focused, to type in. A field not
   *  among the rows asks for All fields first; not there either, or asked for long ago: let go. */
  function focusRow(pane, tab, rec, data, ready) {
    const f = rec.insp && rec.insp.focus;
    if (!f || !ready) return;
    if (Date.now() - f.at > 20000) { rec.insp.focus = null; return; }
    const sh = rec.insp.sheet && rec.insp.sheet.sheet ? sheetOf(tab, rec) : null;
    if (rec.insp.sheet && rec.insp.sheet.sheet && !(sh && sh.status === "done")) return;   // (its fields on their way)
    const want = f.path.toLowerCase(), is = (r) => String(r.path || "").toLowerCase() === want;
    const i = (pane.rows || []).findLastIndex(is);
    if (i < 0 && data.reading) return;           // (the rows still coming)
    if (i < 0) {
      rec.insp.focus = rec.insp.all || (data.rows || []).some(is) ? null : f;
      if (rec.insp.focus) {                      // not a default row: All fields, then again
        rec.insp.all = true;
        rec.asks = 0;
        askInspect(rec, tab);
        renderInspector(pane, tab, sessOf(tab));
      }
      return;
    }
    const list = pane.q(".insp .irows"), row = list.querySelector(`.irow[data-i="${i}"]`), k = pane.rowSec && pane.rowSec.get(i);
    if (!row && k && !rec.insp.shown.has(k)) {    // (in a section shut: opened, and drawn again)
      rec.insp.shown.add(k);
      renderInspector(pane, tab, sessOf(tab));
      return;
    }
    rec.insp.focus = null;
    if (!row) return;
    pickRow(pane, row);
    const v = f.key && row.querySelector(".vl.editable");
    if (v) v.focus({ preventScroll: true });
    const a = row.getBoundingClientRect(), b = list.getBoundingClientRect();
    if (a.top < b.top || a.bottom > b.bottom) list.scrollTop += a.top - b.top - Math.max(0, (list.clientHeight - row.offsetHeight) / 2);
    row.classList.remove("flash");
    void row.offsetWidth;                        // (again from the start)
    pane.flash = { path: want, at: Date.now() };
    reflash(pane);
  }
  /** The flash on the field gone to, kept where the rows are drawn again meanwhile (the fields'
   *  names learned, new values, the rows' last changes come): the same fade, from where it
   *  was; keep: the row brought back into the rows' view if the new rows moved it out. */
  function reflash(pane, keep) {
    const f = pane.flash, dt = f ? Date.now() - f.at : 0;
    if (!f || dt > FLASH_MS) { pane.flash = null; return; }
    const i = (pane.rows || []).findLastIndex((r) => String(r.path || "").toLowerCase() === f.path);
    const row = i >= 0 && pane.q(`.insp .irows .irow[data-i="${i}"]`);
    if (!row) return;
    row.style.setProperty("--flash-at", `${200 - dt}ms`);
    row.classList.add("flash");
    const list = pane.q(".insp .irows"), a = row.getBoundingClientRect(), b = list.getBoundingClientRect();
    if (keep && (a.top < b.top || a.bottom > b.bottom)) list.scrollTop += a.top - b.top - Math.max(0, (list.clientHeight - row.offsetHeight) / 2);
  }
  const FLASH_MS = 1200;                         // style.css .irow.flash: 0.2 s, then a 1 s fade

  /** Edit an input's value in place: one Aspen takes from a list through its menu (listOf), else
   *  typed in its box, the unit menu and ✓ beside it in the row's room. Enter, ✓ or a click
   *  anywhere else writes it to Aspen (when it changed); only Escape lets it go. The focus moving to the unit menu or ✓ is no click
   *  elsewhere, nor is the window losing the focus (the focus stays in the cell). A pick or a
   *  close of the inspector writes it first (commitEdit), whichever comes first. */
  function startEdit(pane, i, ev) {
    const tab = tabOf(pane.tabId), rec = wb.recs.get(pane.tabId), r = pane.rows && pane.rows[i];
    if (!tab || !r) return;
    const cell = pane.q(`.irows .vl[data-i="${i}"]`);
    if (!cell) return;
    const list = listOf(tab, r);
    if (list) {                                    // a value Aspen takes from a list: its menu, the current one ticked
      const now = String(r.value ?? "").replace(/\.0$/, "").toUpperCase();
      toggleMenu(cell, () => list.map((x) => ({ label: x.label, tip: x.tip, check: x.code.toUpperCase() === now,
        run: () => { if (x.code.toUpperCase() !== now) writeValue(pane, tab, r, x.code, null); } })), ev || { detail: 0 });
      return;
    }
    const ed = (pane.editing = { target: rec.insp.target, path: r.path });
    cell.classList.add("ed");
    cell.closest(".irow").draggable = false;
    const units = r.units && r.units.length ? r.units : r.unit ? [r.unit] : [];
    cell.innerHTML = `<input class="ival" value="${esc(r.value ?? "")}">`
      + (units.length ? `<select class="iunit">${units.map((u) => `<option${u === r.unit ? " selected" : ""}>${esc(u)}</option>`).join("")}</select>` : "")
      + `<button class="iok">${icon("check")}</button>`;
    const inp = cell.querySelector(".ival");
    inp.focus();
    inp.select();
    const done = (commit) => {
      if (pane.editing !== ed) return;
      const unitSel = cell.querySelector(".iunit");
      const unit = unitSel && unitSel.value !== r.unit ? unitSel.value : null;
      pane.editing = null;
      if (commit && (inp.value.trim() !== String(r.value ?? "") || unit)) writeValue(pane, tab, r, inp.value.trim(), unit);
      else { pane.sigs.irows = null; renderInspector(pane, tab, sessOf(tab)); }
    };
    ed.done = done;
    inp.addEventListener("keydown", (ev) => {
      if (ev.isComposing || ev.keyCode === 229) return;   // Enter picks a character in an IME
      if (ev.key === "Enter") done(true);
      if (ev.key === "Escape") done(false);
    });
    cell.querySelector(".iok").addEventListener("click", (ev) => { ev.stopPropagation(); done(true); });
    cell.addEventListener("focusout", (ev) => {
      if (ev.relatedTarget && cell.contains(ev.relatedTarget)) return;
      setTimeout(() => { if (!cell.contains(document.activeElement)) done(true); }, 0);
    });
  }
  /** A value written to Aspen from the inspector (typed, or picked from its menu): "writing…" in
   *  its box until the next read. */
  function writeValue(pane, tab, r, value, unit) {
    pane.saving = { path: r.path, t: tab.inspect ? tab.inspect.t : 0 };
    wb.post({ type: "set_value", tab: tab.id, path: r.path, value, unit });
    pane.sigs.irows = null;
    renderInspector(pane, tab, sessOf(tab));
  }
  /** Write the value being edited in the inspector, if one is (the pick or the close that
   *  follows a click elsewhere can come before the focus has been seen to leave). */
  function commitEdit(pane) {
    if (pane.editing && pane.editing.done) pane.editing.done(true);
  }

  /** An input the program can set (else it is read, as a result is). */
  const settable = (r) => !!r.input && r.enterable !== false;

  /** The loop the next step would go into or after (WB.loopOf): a read offered there is asked
   *  where, each pass or once after it. */
  const loopAt = (pane) => { const rec = wb.recs.get(pane.tabId); return rec ? WB.loopOf(rec.ws) : null; };

  /** A row's ⊕ menu: what it can become in the program. An input: set it (the default, a
   *  double-click's), sweep it, adjust it to reach a target, make it a decision variable, or
   *  read it (an input that holds a word, not a number, is only set or read); a result: read
   *  it (the default), make it an objective or a constraint. Where the step picked last is a
   *  loop or lies in one, a read is two: at every pass, inside the loop (the default), or
   *  once after the loop ends. Last, where the server takes it: ask the AI about the field. First,
   *  where the server and the window make help cards: what this field is (helpRow). */
  function rowItems(pane, i) {
    const r = pane.rows && pane.rows[i];
    if (!r) return [];
    const loop = loopAt(pane);
    const go = (what) => () => addRow(pane, r, what, loop), dbl = t("k_dbl");
    const tab = tabOf(pane.tabId), lc = tab ? locOf(tab, wb.recs.get(tab.id), r) : null;
    const fname = lc ? WBL.text(lc, "field") : I18N.pick(r.label);
    const head = [{ title: `${fname} · ${fmtVal(r.value)}${r.unit ? ` ${r.unit}` : ""}` }];
    // Ask AI about this field, last
    const tg = tab && (wb.recs.get(tab.id) || {}).insp ? wb.recs.get(tab.id).insp.target : null;
    const ask = tg ? [{ sep: true }, { label: t("ask_field"), icon: "chat",
      run: () => askAI(tab, { kind: "field", path: r.path, label: `${tg.name} › ${fname}`, obj: tg.kind, name: tg.name }) }] : [];
    const word = typeof r.value === "string" && r.value.trim() !== "" && !isFinite(Number(r.value));
    const lname = loop ? t(`loop_${loop.type}`) : "";
    const reads = (keys) => (loop ? [
      { label: t("add_read_each", lname), icon: "loop", keys, run: go("read_each") },
      { label: t("add_read_after", lname), icon: "eye", run: go("read_after") },
    ] : [{ label: t("add_read"), icon: "eye", keys, run: go("read") }]);
    // a field changed has a way back to its value before: its last change undone, previewed first
    // (feature undo; without it: shown, off)
    const pv = settable(r) ? lastOf(pane, r) : null, was = pv && WBC.provWas(pv, r.unit), live = feature("undo") && !!(pv && pv.id);
    const at = () => pane.q(`.insp .irows .iadd[data-add="${i}"]`);
    const back = was ? [{ sep: true }, { label: t("prov_revert", was), icon: "undo", disabled: !live, tip: t(live ? "tip_prov_revert_on" : "tip_prov_revert"),
                                         run: () => revertRow(pane, r, at()) }] : [];
    // first, where the server and the window make help cards: what this field is
    if (helpOn()) head.push({ label: t("fh_what"), icon: "help", tip: t("tip_fh"),
      run: () => helpRow(pane, i, pane.q(`.insp .irows .irow[data-i="${i}"] .ihelp`) || at()) }, { sep: true });
    if (settable(r) && word) return [...head,
      { label: t("add_set"), icon: "pen", keys: dbl, run: go("set") },
      { sep: true },
      ...reads(),
      ...back,
      ...ask,
    ];
    return settable(r) ? [...head,
      { label: t("add_set"), icon: "pen", keys: dbl, run: go("set") },
      { label: t("add_sweep"), icon: "loop", run: go("sweep") },
      { label: t("add_seek"), icon: "seek", run: go("seek") },
      { sep: true },
      { label: t("add_optvar"), icon: "slider", run: go("optvar") },
      { sep: true },
      ...reads(),
      ...back,
      ...ask,
    ] : [...head,
      ...reads(dbl),
      { sep: true },
      { label: t("add_optobj"), icon: "target", run: go("optobj") },
      { label: t("add_optcon"), icon: "limit", run: go("optcon") },
      ...ask,
    ];
  }

  /** An inspector row into the program: a step after the step picked last in the blocks (else
   *  at the main program's end: WB.appendStatements), or a decision variable, objective or
   *  constraint in an optimize step (WB.addToOptimize, which says where in a toast). A read in
   *  a loop (loop: WB.loopOf when the menu opened) goes into it after its last run step
   *  (read_each: WB.appendInto), or after it (read_after). */
  function addRow(pane, r, what, loop) {
    const tab = tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id);
    if (!rec) return;
    useSession(tab);
    const each = what === "read_each", after = what === "read_after";
    const json = WB.rowBlock(r, each || after ? "read" : what);
    if (!json) return;
    let blk = null;
    const lp = (each || after) && loop && !loop.isDeadOrDying() && loop.workspace === rec.ws ? loop : null;
    if (lp) {
      blk = (each ? WB.appendInto(rec.ws, lp, [json]) : WB.appendStatements(rec.ws, [json], lp.id))[0] || null;
    } else if (what.startsWith("opt")) {
      const got = WB.addToOptimize(rec.ws, json, { optvar: "VARS", optobj: "OBJS", optcon: "CONS" }[what], WB.focused(rec.ws));
      blk = got.blk;
      if (got.opt) toast(t(got.made ? "add_opt_new" : "add_opt", `${Blockly.Msg.WB_CAT_OPT || ""} ${got.opt.getField("ALG").getText()}`.trim()), 4000);
    } else {
      const at = WB.anchor(rec.ws);
      blk = WB.appendStatements(rec.ws, [json], at && at.id)[0] || null;
    }
    placed(rec, blk);
  }
  /** A block the inspector just added: it goes out at once as a version of its own (one
   *  "previous version" takes it back, as one Ctrl+Z does), a folded program column opens,
   *  the view centres on it, it flashes, and it is the picked block, so the next one added
   *  goes after it. */
  function placed(rec, blk) {
    if (!blk) return;
    if (wb.pane && wb.pane.tabId === rec.id) setProg(wb.pane, true);
    sendProgram(rec);
    Blockly.common.setSelected(blk);             // (Blockly scrolls a block it focuses into view: first)
    showStep(rec, blk.id);
    flashBlock(blk);
  }

  function wireInspector(pane) {
    const box = pane.q(".insp");
    box.addEventListener("click", (ev) => {
      const tab = tabOf(pane.tabId);
      if (!tab) return;
      const cps = ev.target.closest("[data-cp]");   // the composition's Flow / Fraction, Mass / Mole (app-comp.js)
      if (cps) { if (!cps.disabled && WBA.cpSwitch) WBA.cpSwitch(pane, tab, cps.dataset.cp); return; }
      const rowEl = ev.target.closest(".irow");     // (a row clicked is the one selected: its "?" stays)
      if (rowEl) pickRow(pane, rowEl);
      const add = ev.target.closest(".iadd");
      if (add) { toggleMenu(add, () => rowItems(pane, Number(add.dataset.add)), ev); return; }
      const hq = ev.target.closest(".ihelp");        // the field's help card
      if (hq) { helpRow(pane, Number(hq.dataset.help), hq); return; }
      const pvt = ev.target.closest(".pvt");         // a row's last change: its card at once
      if (pvt) { const p = pvPath(pane, pvt); if (p) showProv(pane, p); return; }
      const rc = wb.recs.get(tab.id), sx = ev.target.closest(".itb-add, .itb-rm, .isc[data-sub], .isx, .isub-add, .isub-more");
      if (sx && rc.insp) {                           // a sheet's table, the block's subobjects
        const sh = sheetOf(tab, rc), cols = sx.dataset.tb ? tbOf(sh, sx.dataset.tb) : [], open = (a) => { pane.adding = a; pane.sigs.irows = null; renderInspector(pane, tab, sessOf(tab)); };
        if (sx.classList.contains("itb-add") && cols.length && cols[0].lk === "none") structPost(pane, tab, { op: "row_add", lists: cols.map((l) => l.path), label: "" });
        else if (sx.classList.contains("itb-add")) open({ tb: sx.dataset.tb });
        else if (sx.classList.contains("itb-rm")) structPost(pane, tab, { op: "row_del", lists: cols.map((l) => l.path), label: sx.dataset.lab });
        else if (sx.dataset.subrm) {
          if (rc.insp.sheet && String(rc.insp.sheet.ids || "").split("/").includes(sx.dataset.id)) rc.insp.sheet = null;
          structPost(pane, tab, { op: "sub_del", path: sx.dataset.subrm, label: sx.dataset.id });
        } else if (sx.dataset.subadd) open({ sub: sx.dataset.subadd });
        else if (sx.classList.contains("isub-more")) {
          toggleMenu(sx, () => subsOf(rc, tab.inspect).filter((c) => !c.ids.length).map((c) => ({ label: `${WBL.titleText(c.name)}${c.at ? ` ${c.at}` : ""}`, icon: "plus", run: () => open({ sub: c.folder }) })), ev);
        } else openSub(pane, tab, rc, sx.dataset.sub, sx.dataset.id);
        return;
      }
      const go = ev.target.closest(".is-go");        // a missing field named on the status line: its row
      if (go && rc.insp) { goMissing(pane, tab, rc, go.dataset.go); return; }
      const sc = ev.target.closest(".isec-h, .isec-all");   // a section opened or shut; a sheet the docs have no rows of: picked
      if (sc && rc.insp) {
        const S = sectionsOf(tab.inspect, (tab.inspect.rows || []).filter((r) => r.input && !r.extra)), x = S.find((y) => y.key === sc.dataset.sec);
        if (x && sc.classList.contains("isec-all")) { openSheet(pane, tab, rc, x.at); return; }   // (its other fields read)
        const shut = sc.getAttribute("aria-expanded") === "true", pk = rc.insp.sheet;
        if (!x) return;
        rc.insp.shown.delete(x.key);
        if (x.rows.length) setSec(typeKey(tab, rc, tab.inspect), x.key, !shut);
        if (shut && x.at && pk && sheetKey(pk) === sheetKey(x.at) && pk.sheet === x.at.sheet) rc.insp.sheet = null;
        else if (!shut && x.at && !x.rows.length) { openSheet(pane, tab, rc, x.at); return; }
        renderInspector(pane, tab, sessOf(tab));
        return;
      }
      const fm = ev.target.closest(".ifm-h, .isc, .ifm-more");
      if (fm && rc.insp) {                           // the forms: a form opened or closed, a sheet picked
        const f = formsOf(tab.inspect).find((x) => x.key === fm.dataset.form);
        if (fm.dataset.more) setOpen(fm.dataset.more, fm.getAttribute("aria-expanded") !== "true");
        else if (f && fm.classList.contains("ifm-h")) {
          const shut = fm.getAttribute("aria-expanded") === "true";
          setOpen(f.form, !shut);
          if (shut && rc.insp.sheet && sheetKey(rc.insp.sheet) === f.key) rc.insp.sheet = null;
        } else if (f && !fm.disabled) {
          const s = f.sheets[Number(fm.dataset.si)];
          if (fm.classList.contains("on")) rc.insp.sheet = null;   // (picked again: put away)
          else if (s) { openSheet(pane, tab, rc, s.at); return; }
        }
        renderInspector(pane, tab, sessOf(tab));
        return;
      }
      const vl = ev.target.closest(".vl.editable");
      if (vl && !pane.editing) { startEdit(pane, Number(vl.dataset.i), ev); return; }
      const hit = ev.target.closest && ev.target.closest("[data-act]"), actn = hit && hit.dataset.act;
      if (!actn) return;
      const rec = wb.recs.get(tab.id), tg = rec.insp && rec.insp.target;
      if (actn === "close") closeInspector(pane);
      else if (actn === "note" && tg) {            // "Ask AI": about it, with Aspen's words on it where the last run left some
        const st = tg.kind === "block" ? (sessOf(tab).status || {})[tg.name] : null;
        const text = st ? t("c_ierr_text", tg.name, t(st.level === "error" ? "w_err_a" : "w_warn_a"), (st.lines || []).join("\n").trim() || st.msg || "") : "";
        if (text && !pane.q(".cta").value.includes(text)) focusComposer(pane, { pin: { target: tg }, text });
        else askAI(tab, tg);                       // (words already in the draft are not added twice)
      }
      else if (actn === "ierr_diag" && window.WBD) WBD.open(tab);   // the run's diagnosis card
      else if (actn === "miss_go" && tg) missGo(pane, tab, rec);   // what Aspen still needs of it
      else if (actn === "run_sim" && !hit.disabled && hit.getAttribute("aria-disabled") !== "true") runSim(tab);
      else if (actn === "prov_revert" && pane.pv) {  // the card's way back: the row's last change undone (previewed)
        const r = (pane.rows || []).find((x) => String(x.path || "").toLowerCase() === pane.pv.path);
        if (r) revertRow(pane, r, hit);
      }
      else if (actn === "ext_deep" && tg && !hit.disabled) deepAsk(pane, tab, tg);
      else if ((actn === "prov_all" || actn === "ext_see") && tg) {   // "See all in Changes": the tab, this object only
        hideProv(pane);
        if (window.WBC) WBC.only(pane.q(".tab-changes"), changesCtx(pane, tab), tg);
        if (prefs().dockMode === "min") setDock(pane, "split");
        showPanel(pane, "changes");
      }
      else if (actn === "block" && tg) {           // a path block beside the step picked last
        useSession(tab);
        placed(rec, WB.newReporter(rec.ws, tg, WB.anchor(rec.ws)));
      }
    });
    // All fields: every other field of the object in Aspen too (the filter searches them)
    box.addEventListener("change", (ev) => {
      if (ev.target.dataset.act !== "all") return;
      const tab = tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id), tg = rec && rec.insp && rec.insp.target;
      if (!tg) return;
      rec.insp.all = ev.target.checked;
      rec.asks = 0;
      askInspect(rec, tab);
      renderInspector(pane, tab, sessOf(tab));
    });
    // the filter redraws the rows only: the box keeps its caret and an IME composition
    box.addEventListener("input", (ev) => {
      if (!ev.target.classList.contains("ifilter")) return;
      const tab = tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id);
      if (!rec || !rec.insp) return;
      rec.filter = ev.target.value;
      renderInspector(pane, tab, sessOf(tab));
    });
    // a value box with the keyboard's focus: Enter or Space types in it
    box.addEventListener("keydown", (ev) => {
      const vl = ev.target.classList && ev.target.classList.contains("vl") && ev.target.classList.contains("editable") ? ev.target : null;
      if (!vl || pane.editing || ev.isComposing || !["Enter", " "].includes(ev.key)) return;
      ev.preventDefault();
      startEdit(pane, Number(vl.dataset.i));
    });
    // a row or subobject being added: Enter adds it, Escape or leaving the line puts it away
    box.addEventListener("keydown", (ev) => {
      const el = ev.target, tab = tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id);
      if (!el.classList.contains("ilab") || ev.isComposing || ev.keyCode === 229 || !["Enter", "Escape"].includes(ev.key) || !rec || !rec.insp) return;
      ev.preventDefault();
      ev.stopPropagation();
      addDone(pane, tab, rec, el, ev.key === "Enter");
    });
    box.addEventListener("focusout", (ev) => {
      const el = ev.target;
      if (!el.classList.contains("ilab")) return;     // (after a click elsewhere in the inspector has acted)
      const was = pane.adding;
      setTimeout(() => { const tab = tabOf(pane.tabId); if (el.isConnected && document.activeElement !== el && pane.adding === was && tab) structPost(pane, tab, null); }, 200);
    });
    // Escape in the filter clears it, then lets go of the caret (the next one closes the inspector)
    box.addEventListener("keydown", (ev) => {
      if (!ev.target.classList.contains("ifilter") || ev.key !== "Escape" || ev.isComposing) return;
      ev.preventDefault();
      if (ev.target.value) { ev.target.value = ""; ev.target.dispatchEvent(new Event("input", { bubbles: true })); } else ev.target.blur();
    });
    box.addEventListener("dragstart", (ev) => {
      const row = ev.target.closest && ev.target.closest(".irow");
      if (!row || pane.editing) return;
      wb.dragRow = pane.rows[Number(row.dataset.i)];
      ev.dataTransfer.effectAllowed = "copy";
      ev.dataTransfer.setData("text/plain", wb.dragRow.path);
    });
    box.addEventListener("dragend", () => { wb.dragRow = null; });
    // its left edge: a drag widens it, out to the flowsheet card's left edge (style.css keeps the
    // margin); a double-click, the default again. The viewer's width, for every object and tab
    const grip = box.querySelector(".insp-grip");
    let w0 = 0, max = 0;
    dragBar(grip, "ew", () => {
      w0 = box.offsetWidth;
      max = pane.q(".fs-wrap").clientWidth - 20;
      grip.classList.add("on");
      hideProv(pane);
    }, (dx) => { box.style.width = `${Math.round(Math.max(INSP_MIN, Math.min(max, w0 - dx)))}px`; }, (moved) => {
      grip.classList.remove("on");
      if (moved) resized(pane, box.offsetWidth);
    });
    grip.addEventListener("dblclick", () => resized(pane, null));
    // a row's last change: the pointer or the keyboard's focus on it shows its card
    box.addEventListener("mouseover", (ev) => provOver(pane, ev));
    box.addEventListener("mouseout", (ev) => provOut(pane, ev));
    box.addEventListener("focusin", (ev) => { const el = ev.target.closest && ev.target.closest(".pvt"), p = el && pvPath(pane, el); if (p) showProv(pane, p); });
    box.addEventListener("focusout", (ev) => { if (ev.target.closest && ev.target.closest(".pvt, .ipv-card")) provOut(pane, ev); });
    box.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !ev.isComposing && hideProv(pane)) { ev.preventDefault(); ev.stopPropagation(); } });
    pane.q(".insp .irows").addEventListener("scroll", () => followProv(pane), { passive: true });
    // a double-click does the row's first ⊕ item: an input is set, a result read
    box.addEventListener("dblclick", (ev) => {
      const row = ev.target.closest && ev.target.closest(".irow"), r = row && pane.rows && pane.rows[Number(row.dataset.i)];
      if (!r || ev.target.closest(".vl.editable, .iadd, .ihelp, .iprov") || pane.editing) return;
      const loop = settable(r) ? null : loopAt(pane);
      addRow(pane, r, settable(r) ? "set" : loop ? "read_each" : "read", loop);
    });
  }

  /** The inspector's width set by its edge (px; null: the default): kept, every pane's, the
   *  edge hints counted again (and the cards beside it placed with them) and a field's help card. */
  const INSP_MIN = 260;                          // (style.css --insp-now)
  function resized(pane, w) {
    pane.q(".insp").style.width = "";
    prefSet(INSP_W, w);
    setInspW(w);
    FS.moved(pane.svg);
    if (window.WBH && WBH.place) WBH.place();
  }

  Object.assign(WBA, { addRow, closeInspector, commitEdit, followInspect, gotoChange, hideProv, linkFrom, markRefs, pick, renderInspector,
    reveal, wireInspector });
})();
