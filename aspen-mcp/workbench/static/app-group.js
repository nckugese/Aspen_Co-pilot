/* A proposal applied by group (learning mode): approved "by group", the run pauses
 * before each group of steps (tab.run.paused.why "group", paused.group: the group with the values
 * the server read at the pause, and what was set by hand since the approval that the group sets
 * again) and shows which one it applies meanwhile (tab.run.gcur). A card at the bottom of the
 * flowsheet -- a lens, centred over the free area -- holds it:
 *
 *   1 / 2 │ Add a water scrubber SCRUB              Stop  Apply the rest  [Apply group]
 *         │ Absorb the ethanol in VENT with water
 *
 * "1 / 2" is where it is (its tooltip: the technical steps the group runs as well); the title (its
 * tooltip: the whole why), the why in two lines at most (a longer one opens in place on a click, and
 * folds back on another) -- or, where a field the group sets was set by hand
 * since, that (warn), or while it applies "Applying… 3 s"; Stop (it can continue from this group),
 * Apply the rest (no more pauses; not on the last group) and the main action: Apply group, Apply and
 * run (the group runs the simulation), Apply and start (a sweep, a seek, an optimization) -- F10, or
 * Enter while the card itself has the focus; Esc does nothing to it. The flowsheet shows this group
 * only: what it changes padded (FS.mark "gc"), what it adds in the accent where the preview placed
 * it, a tag on each object it sets; at a group's pause the object tagged brought into view with its
 * tag (zoomed in where names do not read) and ringed once.
 * The run bar keeps its title, a thin line of the groups done and ⋯ (Stop is the card's). A
 * breakpoint's or a manual step's pause shows their own cards and run bar instead; the card comes
 * back as the run goes on. Another tab shown: that tab's (none). Feature-detected: groups.
 *
 *   gcNow(tab)           the card's subject {g, paused} -- the run by group's group -- or null
 *   gcRows(tab, s)       the rows its tags show (the pause's; while it applies, the last read)
 *   renderGroup(pane)    the card, the run bar's line, the marks (from renderProgBar)
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { canon, feature, fmtVal, isObj, t, tabOf, tn, wb } = WBA;
  const { gTitle, pausedOf, pvWord, renderEdges, stepPress, stopRun } = WBA.later;

  const GAP = 12, MAX_W = 640, PRESS_MS = 8000;
  const GO = { run: "gc_apply_run", start: "gc_apply_start" };

  /** The group a run by group applies now, or pauses before: {g, paused, pa}; null for any other
   *  run, or while a breakpoint, a step or a manual step pauses it (their cards show then). */
  function gcNow(tab) {
    const run = tab && tab.run;
    if (!run || !feature("groups") || run.status !== "running" || run.dry_run || run.mode !== "group") return null;
    const pa = pausedOf(tab);
    if (pa) return pa.why === "group" && isObj(pa.group) && Number.isFinite(pa.group.n) ? { g: pa.group, paused: true, pa } : null;
    return isObj(run.gcur) && Number.isFinite(run.gcur.n) ? { g: run.gcur, paused: false, pa: null } : null;
  }
  /** The rows its tags show: the pause's live rows (kept with the tab); while the group applies, the
   *  last ones read for it. */
  function gcRows(tab, s) {
    const rec = wb.recs.get(tab.id), key = `${(tab.run || {}).started}|${s.g.n}`;
    if (s.paused && Array.isArray(s.g.rows)) {
      if (rec) rec.gcRows = { key, rows: s.g.rows };
      return s.g.rows;
    }
    return rec && rec.gcRows && rec.gcRows.key === key ? rec.gcRows.rows : [];
  }

  // ------------------------------------------------------------------ the words
  const kindWord = (k) => { const w = I18N.t(`stp_${k}`) !== `stp_${k}` ? t(`stp_${k}`) : t("stp_other"); return I18N.lang === "zh" ? w : w.toLowerCase(); };
  const valUnit = (d) => (isObj(d) ? `${fmtVal(d.value)}${d.unit ? ` ${d.unit}` : ""}` : "");
  /** A field set by hand that the group sets again: "SCRUB stages: set by hand to 12; applying sets 10". */
  function conflictText(tab, c) {
    const m = /^\\Data\\(Blocks|Streams)\\([^\\]+)/i.exec(String(c.path || ""));
    const fs = ((wb.state && wb.state.sessions) || {})[tab.session] || {}, name = m ? m[2].toUpperCase() : "";
    const blk = m && /^blocks$/i.test(m[1]) ? ((fs.flowsheet || {}).blocks || []).find((b) => b && String(b.name).toUpperCase() === name) : null;
    const field = `${m ? `${m[2]} ` : ""}${pvWord(c.path, blk ? blk.type : null, tab.session)}`;
    return t("gc_conflict", field, valUnit(c.user), valUnit(c.new));
  }
  /** The press the card waits for an answer to (the server's next pause, PRESS_MS at most). */
  const sentKey = (p) => `${p.at}|${p.since}|${p.n}`;
  const waiting = (rec, s) => !!(s.paused && rec && rec.stepSent && rec.stepSent.key === sentKey(s.pa) && Date.now() - rec.stepSent.at < PRESS_MS);

  // ------------------------------------------------------------------ the card
  function wire(pane, card) {
    if (card.dataset.wired) return;
    card.dataset.wired = "1";
    card.addEventListener("click", (ev) => {
      const l2 = ev.target.closest(".gc-l2.long");
      if (l2) {                                         // (a drag that selected words is not a click on them)
        if (!String(window.getSelection ? window.getSelection() : "")) openLine(pane, card, l2);
        return;
      }
      const b = ev.target.closest("[data-gc]");
      if (!b || b.disabled || wb.pane !== pane) return;
      press(pane, b.dataset.gc);
    });
    card.addEventListener("keydown", (ev) => {           // Enter: only the card's own focus (not a field's elsewhere)
      if ((ev.key === "Enter" || ev.key === " ") && ev.target.matches(".gc-l2.long") && !ev.isComposing) {
        ev.preventDefault();
        openLine(pane, card, ev.target);
        return;
      }
      if (ev.key !== "Enter" || ev.target !== card || ev.isComposing || ev.ctrlKey || ev.altKey || ev.metaKey || ev.shiftKey) return;
      ev.preventDefault();
      const go = card.querySelector('[data-gc="go"]');
      if (go && !go.disabled) press(pane, "go");
    });
  }
  function press(pane, what) {
    if (what === "stop") stopRun();
    else stepPress(what === "rest" ? "cont" : "next");
    renderGroup(pane);
  }
  const setTip = (el, s) => { if (el.title !== s) el.title = s; };
  /** The why (or the conflict) in two lines at most: a longer one, cut with "…", reads as one to
   *  click (.long: the pointer, a faint fill under it); open, it shows whole, scrolling inside past
   *  a few lines. Its tooltip: the whole why -- for a long one what a click does (the conflicts'
   *  list kept above it). Measured after the card is placed (its width is the free area's). */
  function longLine(card) {
    const l2 = card.querySelector(".gc-l2"), open = l2.classList.contains("open");
    const long = !l2.classList.contains("hidden") && (open || l2.scrollHeight > l2.clientHeight + 1);
    if (!long && open) l2.classList.remove("open");
    if (l2.classList.contains("long") !== long) l2.classList.toggle("long", long);
    if (card.classList.contains("open") !== (long && open)) card.classList.toggle("open", long && open);
    const tip = l2._tip || "", hint = long ? t(open ? "tip_gc_less" : "tip_gc_more") : "";
    setTip(l2, !long ? tip : tip && tip !== l2.textContent ? `${tip}\n${hint}` : hint);
    if (long) {
      if (l2.getAttribute("role") !== "button") { l2.setAttribute("role", "button"); l2.tabIndex = 0; }
      l2.setAttribute("aria-expanded", String(open));
    } else if (l2.hasAttribute("role")) {
      l2.removeAttribute("role");
      l2.removeAttribute("tabindex");
      l2.removeAttribute("aria-expanded");
    }
  }
  /** A click (Enter, Space) on a long why: open in place, or folded back to two lines. */
  function openLine(pane, card, l2) {
    l2.classList.toggle("open");
    l2.scrollTop = 0;
    l2.animate([{ opacity: 0.55 }, { opacity: 1 }], { duration: 160, easing: "ease-out" });
    renderGroup(pane);                                  // (its tooltip, and the free area's bottom: the card's height moved)
  }

  /** The card, the run bar's line and the marks for the tab the pane shows. */
  function renderGroup(pane) {
    const card = pane && pane.q && pane.q(".gc-card");
    if (!card) return;
    wire(pane, card);
    const tab = tabOf(pane.tabId), s = tab ? gcNow(tab) : null, bar = pane.q(".prog-bar"), rec = tab && wb.recs.get(tab.id);
    if (bar.classList.contains("gc") !== !!s) bar.classList.toggle("gc", !!s);
    if (!s) {
      if (!card.classList.contains("hidden")) {
        card.classList.add("hidden");
        card._sig = null;
        if (card.contains(document.activeElement)) card.blur();
        gcRoom(pane, 0);
        renderEdges(pane);                              // (the free area's bottom back)
      }
      // (the marks live in the tab's own view context: a run that ended while the tab was away too)
      if (pane.gcMark || pane.svg.querySelector(".gc")) FS.mark(pane.svg, [], "gc");
      pane.gcMark = null;
      pane.gcAt = null;
      return;
    }
    const g = s.g, of = Math.max(Number(g.of) || 1, g.n), last = g.n >= of, run = tab.run;
    // the run bar's line: the groups done (half of the one it applies)
    const line = bar.querySelector(".gc-line > b");
    if (line) line.style.transform = `scaleX(${Math.min(1, (g.n - 1 + (s.paused ? 0 : 0.5)) / of)})`;
    const conflict = s.paused && Array.isArray(g.conflict) ? g.conflict.filter(isObj) : [];
    const secs = !s.paused && Number.isFinite(g.t) ? Math.max(0, Math.round(Date.now() / 1000 - g.t)) : null;
    const stopping = !!(rec && rec.pending && rec.pending.kind === "stop");
    const off = !wb.connected ? t("why_off") : stopping ? t("st_stopping") : "";
    const busy = off || !s.paused ? off || t("gc_applying_s") : waiting(rec, s) ? t("st_sending") : "";
    const prnOn = !!(window.WBPN && WBPN.on());
    const sig = canon([I18N.lang, window.WBL ? WBL.ver : 0, tab.id, run.started, g, s.paused, secs, off, busy, wb.connected, prnOn]);
    const fresh = card.classList.contains("hidden");
    if (card._sig !== sig) {
      card._sig = sig;
      const q = (sel) => card.querySelector(sel), title = gTitle(g);
      const pos = q(".gc-pos");
      pos.textContent = t("gc_pos", g.n, of);
      const tech = Number(g.tech) || 0, kinds = Array.isArray(g.tech_kinds) ? g.tech_kinds.map(kindWord) : [];
      setTip(pos, [t("tip_gc_pos", g.n, of), tech ? tn("gc_tech", tech, kinds.join(t("ps_and"))) : ""].filter(Boolean).join("\n"));
      card.setAttribute("aria-label", t("gc_label", g.n, of, title));
      const tt = q(".gc-t");
      tt.textContent = title;
      setTip(tt, typeof g.why === "string" ? g.why : "");
      // learning mode: the group's principle chip (E, principle.js) -- the fields it sets: the pause's rows, the check's
      const rows = prnOn ? [...gcRows(tab, s), ...WBPN.rows(tab, g.n)] : [];
      q(".gc-prn").innerHTML = prnOn ? WBPN.chip(`gc|${tab.id}|${run.started}|${g.n}`, WBPN.of(g, rows, tab)) : "";
      const l2 = q(".gc-l2"), why = typeof g.why === "string" ? g.why.trim() : "";
      const say = secs !== null ? t("gc_applying", secs) : conflict.length ? conflictText(tab, conflict[0]) : why;
      if (l2.textContent !== say) { l2.textContent = say; l2.classList.remove("open"); }   // (other words: two lines again)
      l2.classList.toggle("warn", secs === null && conflict.length > 0);
      l2.classList.toggle("hidden", !say);
      l2._tip = secs === null && conflict.length ? conflict.map((c) => conflictText(tab, c)).join("\n") : why;
      const go = q('[data-gc="go"]'), rest = q('[data-gc="rest"]'), stop = q('[data-gc="stop"]');
      go.textContent = t(GO[g.does] || "gc_apply");
      go.disabled = !!busy;
      setTip(go, busy || t(last ? "tip_gc_apply_last" : "tip_gc_apply"));
      rest.textContent = t("gc_rest");
      rest.classList.toggle("hidden", last);
      rest.disabled = !!busy;
      setTip(rest, busy || t("tip_gc_rest"));
      stop.textContent = t("stop");
      stop.disabled = !!off;
      setTip(stop, off || t("tip_gc_stop"));
    }
    if (fresh) {
      card.classList.remove("hidden");
      if (window.WBW && WBW.active()) WBW.close();      // (the same place as a change's walk)
      card.animate([{ opacity: 0, transform: "translateX(-50%) translateY(8px) scale(.98)" }, { opacity: 1, transform: "translateX(-50%)" }],
        { duration: 260, easing: "cubic-bezier(.3, 1.35, .5, 1)" });
    }
    place(pane, card);
    longLine(card);
    // the group's objects padded; brought into view and ringed once when its pause comes
    const objs = Array.isArray(g.objs) ? g.objs.filter((k) => typeof k === "string" && k.includes(":")) : [];
    const msig = canon([tab.id, objs]);                // (marked again only when they change: kept across redraws)
    if (pane.gcMark !== msig) { FS.mark(pane.svg, objs, "gc"); pane.gcMark = msig; }
    if (fresh || card._h !== card.offsetHeight) { card._h = card.offsetHeight; renderEdges(pane); }
    const at = `${tab.id}|${run.started}|${g.n}`, ver = window.WBL ? WBL.ver : 0;
    if (s.paused && pane.gcAt !== at) {
      pane.gcAt = at;
      pane.gcVer = ver;
      requestAnimationFrame(() => look(pane, tab, objs, true, at));
    } else if (s.paused && pane.gcVer !== ver) {       // (field names came: its tag grew -- kept in view, no ring)
      pane.gcVer = ver;
      requestAnimationFrame(() => look(pane, tab, objs, false));
    }
  }
  /** Centred over the free area (FS.insets, the card itself left out), 12 px over its bottom.
   *  Where the inspector leaves too little room beside it for the card's words (ROOM): across
   *  the inspector's foot too, the inspector stopping above it (--gc-h, style.css .insp). */
  const ROOM = 420;
  function place(pane, card) {
    const area = pane.q(".fs-area"), ins = FS.insets(pane.svg, true), width = area.clientWidth;
    const under = ins.right > 0 && width - ins.left - ins.right < ROOM;
    const free = Math.max(width - ins.left - (under ? 0 : ins.right), 160);
    const set = (k, v) => { if (card.style[k] !== v) card.style[k] = v; };   // (one by one: the lens's backdrop stays)
    set("left", `${Math.round(ins.left + free / 2)}px`);
    set("bottom", `${Math.round(ins.bottom + GAP)}px`);
    set("maxWidth", `${Math.round(Math.min(MAX_W, free - 24))}px`);
    gcRoom(pane, under ? card.offsetHeight + ins.bottom + GAP : 0);
  }
  /** The card placed again where it shows (the free area changed: the inspector opened, closed or resized). */
  function gcPlace(pane) {
    const card = pane.q(".gc-card");
    if (card && !card.classList.contains("hidden")) place(pane, card);
  }
  /** The room the inspector leaves at its foot for the card (px; 0: none). */
  function gcRoom(pane, h) {
    const wrap = pane.q(".fs-wrap"), v = h ? `${Math.round(h)}px` : "";
    if (wrap.style.getPropertyValue("--gc-h") === v) return;
    if (v) wrap.style.setProperty("--gc-h", v); else wrap.style.removeProperty("--gc-h");
  }
  /** The group's object with a tag (else its first drawn): zoomed in where names do not read
   *  (as following the AI's edits), into view clear of the card with its tag, then ringed once;
   *  ring false (field names came since, its tag wider): only kept in view, no zoom, no ring. */
  function look(pane, tab, objs, ring, at) {
    if (wb.pane !== pane || pane.tabId !== tab.id) return;
    const fs = ((wb.state.sessions || {})[tab.session] || {}).flowsheet || {};
    const drawn = (k) => {
      const i = k.indexOf(":"), kind = k.slice(0, i), name = k.slice(i + 1).toUpperCase();
      const x = kind === "block" ? fs.blocks : kind === "stream" ? fs.streams : null;
      const hit = (Array.isArray(x) ? x : []).find((b) => b && String(b.name).toUpperCase() === name);
      return hit ? { kind, name: String(hit.name) } : null;
    };
    const tagged = new Set([...pane.svg.querySelectorAll(".fs-tag2.gcv")].map((e) => String(e.dataset.tag || "").toUpperCase()));
    const list = objs.map(drawn).filter(Boolean), tg = list.find((x) => tagged.has(`${x.kind}:${x.name}`.toUpperCase())) || list[0];
    if (!tg) return;
    if (ring) FS.readable(pane.svg, tg);
    const r = FS.reveal(pane.svg, tg, { pad: FS.RING_ROOM, tag: true });
    if (!r) {                                          // (no view yet -- the window just opened: the next draw tries again)
      if (ring && pane.gcAt === at) pane.gcAt = null;
      return;
    }
    if (!ring && !r.moved) return;
    renderEdges(pane);
    if (ring) FS.ping(pane.svg, tg);
  }

  Object.assign(WBA, { gcNow, gcPlace, gcRows, renderGroup });
})();
