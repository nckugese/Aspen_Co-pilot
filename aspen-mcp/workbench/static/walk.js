/* Step through a change group . A card in the Changes tab (changes.js: opened, a labelled
 * "Step through" over its rows) hands over the group's records that went in, oldest first; a glass capsule at
 * the bottom of the flowsheet (.walk-bar, a group that blocks nothing) shows one at a time:
 *
 *   [◀] 3 / 12 [▶] │ 14:02  ESTCOL › Reflux ratio 1.5 → 2           [✕]
 *                  │ Reason: a higher reflux ratio, for a top purity over 99%
 *
 * Each stop frames what the record is about on the flowsheet (FS.mark "walk": solid, as a pick is),
 * brings the first of it into view clear of the capsule (FS.reveal) and rings it once (FS.ping); a
 * connection's stream first, a run's blocks with messages, a loop's fields' blocks. Something no
 * longer drawn (removed, renamed) says so under the line. The row it is on is marked in the card.
 * Nothing is read from Aspen: the inspector does not open (it would read Aspen, which may be busy
 * calculating), and the flowsheet is today's -- the counter's tooltip says so, once (walk_now).
 * Where the card may not hold the whole group (earlier pages, a filter on), the window's journal is
 * read for it (Api.journal group: a file read, never COM); the count follows ("3 / 500").
 *
 * ◀ ▶ or ← → move a record (not while typing, a menu or dialog open, or the tour showing; an arrow
 * inside a game or a block program is theirs); Esc or ✕ closes it (what lies over it first, as the
 * page's Escape does: a help card, the missing list, an undo's preview ...). Another tab shown, the
 * pane gone: it closes by itself. No autoplay, no timer but a light check (WATCH_MS) while it shows:
 * the tab, the language, where the edge hints left room.
 *
 *   WBW.on()        the walk can be offered: the timeline is there, and a flowsheet
 *   WBW.open(o)     o {model, session, tab, group, title, types, recs (walkable, oldest first), full
 *                   (the card holds the whole group), anchor (focus back there on close), step(r)
 *                   (WBC.walkStep: its words and objects), onStep(rid | null) (the card's row)}
 *   WBW.close(back) close it (back: the focus returns to the anchor); whether it was open
 *   WBW.active()    a walk shows (following the AI's edits holds still meanwhile)
 *   WBW.current()   {model, id} of the record shown, or null
 */
(function () {
  "use strict";
  const WBW = (window.WBW = {});
  const { esc, icon, t } = WBA;
  const LIMIT = 1000;          // records a group's own read asks for
  const WATCH_MS = 600;        // while it shows: the tab, the language, the room at the bottom checked this often
  const GAP = 12, OVER_HINTS = 44;   // px over the free area's bottom; over the edge hints' row where one shows there
  const MAX_W = 640;
  // what lies over the walk: the page's Escape closes it first
  const OVER = ".cov-pop:not(.hidden), .fh-card:not(.hidden), .miss-pop:not(.hidden), .diag-card:not(.hidden)";
  let W = null;                // the walk: {o, steps, i, moved, pane, tab, lang, el, loading, timer}

  const pane = () => (window.wb && wb.pane) || null;
  WBW.on = () => !!window.WBC && WBC.on() && !!(pane() && pane().svg);
  WBW.active = () => !!W;
  WBW.current = () => (W && W.steps[W.i] ? { model: W.o.model, id: String(W.steps[W.i].id || "") } : null);

  WBW.open = function (o) {
    if (!o || !Array.isArray(o.recs) || !o.recs.length || typeof o.step !== "function" || !WBW.on()) return;
    WBW.close();
    const p = pane();
    if (WBA.prefs().dockMode === "max") WBA.setDock(p, "split");   // the flowsheet shows again
    W = { o, steps: o.recs.slice(), i: 0, moved: false, pane: p, tab: p.tabId, lang: I18N.lang, el: make(p), loading: false, timer: 0 };
    W.timer = setInterval(watch, WATCH_MS);
    show(true);
    W.el.classList.add("in");
    const nx = W.el.querySelector('[data-w="next"]');
    (nx && !nx.disabled ? nx : W.el.querySelector('[data-w="close"]')).focus({ preventScroll: true });
    if (!o.full && o.group) whole(W);
  };

  WBW.close = function (back) {
    if (!W) return false;
    const w = W;
    W = null;
    clearInterval(w.timer);
    unmark(w);
    w.el.remove();
    try { w.o.onStep && w.o.onStep(null); } catch (e) { console.error(e); }
    if (back && w.o.anchor && w.o.anchor.isConnected) w.o.anchor.focus({ preventScroll: true });
    return true;
  };

  /** The capsule, in the flowsheet's area: its buttons made once (the focus stays on one pressed),
   *  their words and the record's filled in by show(). */
  function make(p) {
    const el = document.createElement("div");
    el.className = "walk-bar plate";
    el.setAttribute("role", "group");
    el.innerHTML = `<span class="wk-nav"><button class="flat icon" data-w="prev">${icon("chevron-left")}</button>`
      + `<span class="wk-pos" aria-live="polite"></span><button class="flat icon" data-w="next">${icon("chevron-right")}</button></span>`
      + `<span class="wk-body"></span><button class="flat icon wk-close" data-w="close">${icon("close")}</button>`;
    el.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-w]");
      if (b && !b.disabled) {
        if (b.dataset.w === "close") WBW.close(true);
        else go(b.dataset.w === "prev" ? -1 : 1);
        return;
      }
      // a block named in a run's line: into view and ringed (nothing opens: no read of Aspen)
      const g = ev.target.closest(".go[data-obj]"), tg = g && drawn(g.dataset.obj);
      if (tg && W) look(tg);
    });
    p.q(".fs-area").appendChild(el);
    return el;
  }

  /** A move of d records (at the ends: nothing). */
  function go(d) {
    if (!W) return;
    const i = Math.max(0, Math.min(W.steps.length - 1, W.i + d));
    if (i === W.i) return;
    W.i = i;
    W.moved = true;
    show(true);
  }

  /** The session's flowsheet as last read (null: none read yet). */
  const fsOf = () => { const s = W && window.wb && wb.state && wb.state.sessions && wb.state.sessions[W.o.session]; return (s && s.flowsheet) || null; };
  /** The drawn block or stream of a key ("block:ESTCOL", any case), as the flowsheet names it, or null. */
  function drawn(key) {
    const k = String(key || ""), i = k.indexOf(":"), kind = k.slice(0, i), up = k.slice(i + 1).toUpperCase();
    if (!W || i < 1 || !up) return null;
    const fs = fsOf() || {};
    const list = kind === "block" ? fs.blocks : kind === "stream" ? fs.streams : null;
    const x = (Array.isArray(list) ? list : []).find((b) => b && String(b.name).toUpperCase() === up);
    return x ? { kind, name: String(x.name) } : null;
  }
  const nameOf = (key) => { const k = String(key || ""); return k.slice(k.indexOf(":") + 1); };
  const setTip = (el, s) => { if (el.title !== s) { el.title = s; el.setAttribute("aria-label", s); } };

  /** The record at W.i: its words, its objects framed; move: into view and ringed (a language
   *  switch, the whole group read, draw the words again without moving the view). */
  function show(move) {
    const w = W, r = w.steps[w.i], el = w.el;
    let s;
    try { s = w.o.step(r) || {}; } catch (e) { console.error(e); s = {}; }
    const tgs = (s.keys || []).map(drawn).filter(Boolean);
    // not drawn: removed by this record (and not added again), or since; a flowsheet not read yet says nothing
    const lost = !fsOf() ? "" : s.gone ? (drawn(s.gone) ? "" : nameOf(s.gone)) : !tgs.length && (s.keys || []).length ? nameOf(s.keys[0]) : "";
    const n = w.steps.length, q = (sel) => el.querySelector(sel);
    const prev = q('[data-w="prev"]'), next = q('[data-w="next"]'), pos = q(".wk-pos");
    el.setAttribute("aria-label", t("walk_label", w.o.title || ""));
    setTip(prev, t("walk_prev"));
    setTip(next, t("walk_next"));
    setTip(q('[data-w="close"]'), t("close_esc"));
    // the one note that the drawing is today's: the counter's tooltip
    pos.title = `${t("walk_now")}\n${t("tip_walk_now")}`;
    pos.textContent = t("walk_pos", w.i + 1, w.loading ? `${n}…` : n);
    const back = document.activeElement === prev && !w.i, fwd = document.activeElement === next && w.i >= n - 1;
    prev.disabled = !w.i;
    next.disabled = w.i >= n - 1;
    if (back || fwd) (back ? next : prev).focus({ preventScroll: true });   // (at an end: the other way keeps the focus)
    const l2 = lost ? `<span class="wk-l2 gone">${esc(t("walk_gone", lost))}</span>`
      : s.reason ? `<span class="wk-l2" title="${esc(s.reasonTip || "")}">${s.reason}</span>` : "";
    q(".wk-body").innerHTML = `<span class="wk-l1" title="${esc(s.tip || "")}"><span class="wk-t">${esc(s.time || "")}</span>`
      + `${s.who || ""}<span class="wk-x">${s.html || ""}</span></span>${l2}`;
    FS.mark(w.pane.svg, tgs.map((x) => `${x.kind}:${x.name}`), "walk");
    place();
    if (move && tgs.length) look(tgs[0]);
    try { if (w.o.onStep) w.o.onStep(r && r.id ? String(r.id) : null); } catch (e) { console.error(e); }
  }

  /** A target into view clear of the capsule, then ringed once. */
  function look(tg) {
    const w = W, svg = w.pane.svg, area = w.pane.q(".fs-area");
    const bottom = area.getBoundingClientRect().bottom - w.el.getBoundingClientRect().top + 8;
    const r = FS.reveal(svg, tg, { top: 0, bottom: Math.max(0, bottom), pad: FS.RING_ROOM });   // (room for the whole ring)
    if (!r) return;
    WBA.renderEdges(w.pane);                     // the edge hints at once, where the view moved
    place();
    FS.ping(svg, tg);
  }

  /** The capsule centred over the free area (FS.insets: clear of the inspector, a heat plan), over the
   *  edge hints' row where one shows at the bottom. */
  function place() {
    const w = W;
    if (!w) return;
    const area = w.pane.q(".fs-area"), ins = FS.insets(w.pane.svg), width = area.clientWidth;
    const free = Math.max(width - ins.left - ins.right, 120);
    const hints = [...area.querySelectorAll(".fs-hint:not(.hidden)")].some((h) => h.dataset.side !== "t");
    const css = `left:${Math.round(ins.left + free / 2)}px;bottom:${Math.round(ins.bottom + (hints ? OVER_HINTS : GAP))}px;max-width:${Math.round(Math.min(MAX_W, free - 24))}px`;
    if (w.el.style.cssText !== css) w.el.style.cssText = css;
  }

  /** The whole group from the window's journal (the card had part of it): from its first where the
   *  walk has not moved yet, else the stop shown stays. */
  function whole(w) {
    const api = window.pywebview && window.pywebview.api;
    if (!api || typeof api.journal !== "function") return;
    w.loading = true;
    show(false);
    Promise.resolve(api.journal({ model: w.o.model, group: w.o.group, limit: LIMIT, types: w.o.types || {} })).then((page) => {
      if (W !== w) return;
      w.loading = false;
      const recs = page && Array.isArray(page.records) ? page.records.filter((r) => WBC.walkable(r)).reverse() : [];
      let move = false;
      if (recs.length > w.steps.length) {
        // not moved yet: from the group's first; else the stop shown stays
        const id = w.steps[w.i] && w.steps[w.i].id, at = w.moved ? recs.findIndex((r) => r.id === id) : -1;
        w.steps = recs;
        w.i = at < 0 ? 0 : at;
        move = at < 0;
      }
      show(move);
    }, () => { if (W === w) { w.loading = false; show(false); } });
  }

  /** While it shows: another tab shown (or the pane gone) closes it; a language switch draws it again. */
  function watch() {
    const w = W, p = pane();
    if (!w) return;
    if (!p || p !== w.pane || p.tabId !== w.tab || !w.el.isConnected) { WBW.close(); return; }
    if (w.lang !== I18N.lang) { w.lang = I18N.lang; show(false); return; }
    place();
  }

  /** The frames off the drawing: the tab's own view context where another tab shows now (its marks
   *  would come back with it). */
  function unmark(w) {
    const p = pane();
    if (p && p.svg && p === w.pane && p.tabId === w.tab) { FS.mark(p.svg, [], "walk"); return; }
    const rec = window.wb && wb.recs && wb.recs.get(w.tab), c = rec && rec.fs;
    if (c && c.marks && c.marks.walk) c.marks = Object.assign({}, c.marks, { walk: [] });
  }

  // ------------------------------------------------------------------ keys (ahead of the page's, which listens on the document)
  function onKey(ev) {
    if (!W || ev.isComposing || ev.ctrlKey || ev.metaKey || ev.altKey) return;
    const k = ev.key;
    if (k !== "ArrowLeft" && k !== "ArrowRight" && k !== "Escape") return;
    const modal = document.getElementById("modal"), tour = document.getElementById("tour");
    if (WBA.menuOpen() || (modal && !modal.classList.contains("hidden")) || (tour && !tour.classList.contains("hidden"))) return;
    const el = document.activeElement, mine = !!el && W.el.contains(el);
    if (!mine && el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName))) return;
    // the walk's keys where the focus is on it, nowhere in particular, in the Changes tab or on the
    // flowsheet (elsewhere -- a game, the block program -- they are theirs)
    if (!mine && el && el !== document.body && !el.closest(".tab-changes, .fs-wrap, .dnav")) return;
    if (k === "Escape") {
      if (!mine && document.querySelector(OVER)) return;   // what lies over it closes first (the page's Escape)
      const p = pane();                                     // ... and a run's result tags (they close before the walk)
      if (!mine && p && p.svg && FS.fxShown(p.svg)) return;
      WBW.close(mine);
    } else go(k === "ArrowLeft" ? -1 : 1);
    ev.preventDefault();
    ev.stopPropagation();
  }
  window.addEventListener("keydown", onKey, true);
})();
