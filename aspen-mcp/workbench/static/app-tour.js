/* Help: the beginner tour (#tour: firstRun, startTour, tourKey), the flowsheet legend
 * (legendItems, openLegend) and the help items the ... menu and the logo share (helpItems).
 *
 * The tour is ten steps, each on a real element of the page: its anchor, else a stand-in
 * (with words of its own where the stand-in says something else); a step with neither is
 * left out and the count follows (the review mode's, on the header's shield, only where the
 * server has AI review; field help, diagnosis and missing inputs, on the model capsule, and the
 * Changes tab's "Step through" and "Annotations", only where the server has them). A ring around the anchor dims
 * the rest (a box-shadow; the layer takes no pointer, so the page stays usable under it) and a
 * glass card sits beside it.
 * Nothing traps the focus and a click on the dimmed page does not close it. A step change
 * slides the card (transform only); the window's size, a new state or a click places it
 * again, once each, since what a step points at may have moved.
 *
 * Once it is dismissed (Skip tour, Esc, Done) it never starts by itself again: prefs
 * wb.tour is "2:done" or "2:skip:<step>" (the 2 is the tour's version). It starts by itself only
 * for a new viewer (neither wb.tour nor the older wb.notice.layout2), once a tab shows: the whole
 * tour. A viewer who dismissed an older version sees, once, only the steps added since (a step's
 * v: the version that added it; the count reads "New 1 / 2"). Where nothing keeps prefs, it never
 * starts by itself, rather than at every launch.
 *
 * Shared state on wb: tour (the open tour: {n: the step shown (its n in STEPS), lang, back: the
 * focus before it, since: only the steps newer than this version, 0 for all}), firstRunSeen (this
 * page has decided what to show at startup).
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { $, closeMenus, esc, flushPrefs, ghost, menuOpen, openMenu, prefGet, prefSet,
    shownTab, t, toggleMenu, wb } = WBA;
  const { showKeys } = WBA.later;

  // 2: the steps on field help, diagnosis and missing inputs (hp) and on the Changes tab (ch).
  // 3: the inspector's forms (2) and the model objects (hp), shown again.
  // (The review step, rv, came later in version 1 too, but in place of a bubble every viewer
  // of version 1 had seen: not new to them.)
  const VERSION = "3", KEY = "wb.tour";

  // ------------------------------------------------------------------ what a step points at
  const pq = (sel) => (wb.pane && wb.pane.tabId ? wb.pane.q(sel) : null);
  /** The element's box where it shows: inside the window, drawn, not hidden or faded out. */
  function shows(el) {
    if (!el || !el.isConnected) return null;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2 || r.right <= 0 || r.bottom <= 0 || r.left >= innerWidth || r.top >= innerHeight) return null;
    const cs = getComputedStyle(el);
    return cs.visibility === "visible" && Number(cs.opacity) > 0.05 ? r : null;
  }
  /** The first block on the flowsheet that shows whole in the part nothing floats over. */
  function firstNode() {
    const svg = wb.pane && wb.pane.svg, area = pq(".fs-area");
    if (!svg || !area) return null;
    const a = area.getBoundingClientRect(), ins = FS.insets(svg);
    const box = { l: a.left + ins.left, t: a.top + ins.top, r: a.right - ins.right, b: a.bottom - ins.bottom };
    return [...svg.querySelectorAll(".fs-node > rect:not(.fam)")].find((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.left >= box.l && r.right <= box.r && r.top >= box.t && r.bottom <= box.b;
    }) || null;
  }
  /** The steps, in the order shown. n: the step's name (its words are
   *  tour<n>_t, or tour_<k>_t where it has a key k, or title()'s key); at: the anchor; alt: the stand-in;
   *  body(alt): the key of its words; place: where the card goes; v: the tour's version that
   *  added it (1 where left out). */
  const STEPS = [
    { n: 1, at: () => pq(".pright .fs-area"), place: "inside", body: () => "tour1_b" },
    { n: 2, v: 3, at: firstNode, alt: () => pq(".pright .fs-area"), place: "right", body: () => "tour2_b" },
    // Run simulation (F5); where it does not show, the program's Run program, or its strip while
    // the column is folded
    { n: 3, at: () => $("bar").querySelector('[data-a="run_sim"]'),
      alt: () => (shows(pq('.prog-bar [data-a="run"]')) ? pq('.prog-bar [data-a="run"]') : pq(".prog-strip")),
      place: "below", body: (alt) => (alt ? "tour3_b_nosim" : "tour3_b") },
    { n: 4, at: () => $("modelstat"), place: "below", body: () => "tour4_b" },
    // a field's help (the inspector rows' "?"), the run's diagnosis and the missing inputs (the
    // model menu's rows): on the model capsule, whose menu lists them
    { n: "hp", k: "hp", v: 3, at: () => $("modelstat"), place: "below", body: () => "tour_hp_b" },
    // (where the window reads the model's changes, the words point at the Changes tab as it is)
    { n: 5, at: () => pq(".composer .cbox"), alt: () => pq(".dnav .dock-ask"), place: "above",
      body: () => (WBC.on() ? "tour5_b_ch" : "tour5_b") },
    // the Changes tab: "Step through" in an opened group (walk.js), and the flowsheet's "Annotations"
    { n: "ch", k: "ch", v: 2, at: () => (WBW.on() ? pq('.panel nav [data-tab="changes"]') : null), place: "above",
      title: () => "tour_ch_t", body: () => "tour_ch_b" },
    // AI review (app-brake.js): the header's shield, where the server has it
    { n: "rv", k: "rv", at: () => document.querySelector("#ai-brake .abk-mode"), place: "below-end", body: () => "tour_rv_b" },
    { n: 6, at: () => pq(".prog-bar"), alt: () => pq(".prog-strip"), place: "right", body: () => "tour6_b" },
    { n: 7, at: () => $("btn-more"), place: "below-end", body: () => "tour7_b" },
  ];
  /** A step's anchor and words as the page is now, or null when neither shows. */
  function resolve(s) {
    const el = s.at();
    if (shows(el)) return { el, alt: false };
    const a = s.alt && s.alt();
    return shows(a) ? { el: a, alt: true } : null;
  }

  // ------------------------------------------------------------------ the tour
  const layer = () => $("tour");
  const card = () => layer().querySelector(".tour-card");

  /** The steps that show now, of the open tour's (since: only those added after that version). */
  const listed = () => {
    const since = (wb.tour && wb.tour.since) || 0;
    return STEPS.filter((s) => (s.v || 1) > since && resolve(s));
  };
  /** Start at the first step (from the menus, or by itself for a new viewer); since: a viewer who
   *  dismissed that version, by itself: only the steps added after it. */
  function startTour(since) {
    closeMenus();
    if (!shownTab() || !$("modal").classList.contains("hidden")) return;
    const back = wb.tour ? wb.tour.back : document.activeElement;
    wb.tour = { n: 0, lang: I18N.lang, back, since: typeof since === "number" && since > 0 ? since : 0 };
    const el = layer();
    el.classList.remove("hidden");
    el.classList.add("first");                     // placed where it is at once, then it slides
    if (!go(0, 1)) { stop(null); return; }
    card().animate([{ opacity: 0 }, { opacity: 1 }], { duration: 180, easing: "cubic-bezier(.2, .8, .2, 1)" });
    el.querySelector(".tour-ring").animate([{ opacity: 0 }, { opacity: 1 }], { duration: 180, easing: "cubic-bezier(.2, .8, .2, 1)" });
    requestAnimationFrame(() => requestAnimationFrame(() => el.classList.remove("first")));
  }
  const posOf = (n) => STEPS.findIndex((s) => s.n === n);
  /** Show the step at `pos` in STEPS, or the nearest one that shows that way (dir 1 forward, -1
   *  back). */
  function go(pos, dir) {
    const list = listed();
    if (!list.length) return false;
    let i = dir > 0 ? list.findIndex((s) => posOf(s.n) >= pos) : -1;
    if (dir < 0) for (let j = list.length - 1; j >= 0; j--) if (posOf(list[j].n) <= pos) { i = j; break; }
    if (i < 0) return false;
    const s = list[i], at = resolve(s), c = card();
    wb.tour.n = s.n;
    wb.tour.lang = I18N.lang;
    c.querySelector(".tc-step").textContent = t(wb.tour.since ? "tour_step_new" : "tour_step", i + 1, list.length);
    c.querySelector(".tc-title").textContent = t(s.title ? s.title() : s.k ? `tour_${s.k}_t` : `tour${s.n}_t`);
    c.querySelector(".tc-body").textContent = t(s.body(at.alt));
    const last = i === list.length - 1, b = (k) => c.querySelector(`[data-tour="${k}"]`);
    b("skip").textContent = t("tour_skip");
    b("prev").textContent = t("tour_prev");
    b("next").textContent = t("tour_next");
    b("done").textContent = t("tour_done");
    b("prev").classList.toggle("hidden", i === 0);
    b("next").classList.toggle("hidden", last);
    b("done").classList.toggle("hidden", !last);
    c.dataset.step = String(s.n);
    place();
    (last ? b("done") : b("next")).focus({ preventScroll: true });
    return true;
  }
  const step = (d) => { if (wb.tour) go(posOf(wb.tour.n) + d, d); };

  /** The ring around the step's anchor (its box and 6 px), the card where the step puts it,
   *  held inside the window and off the ring where it can be. A step whose anchor went away
   *  goes on to the next one there is. */
  function place() {
    if (!wb.tour) return;
    const s = STEPS.find((x) => x.n === wb.tour.n), at = s && resolve(s);
    if (!at) { const p = posOf(wb.tour.n); if (!go(p + 1, 1) && !go(p, -1)) stop(null); return; }
    const r = at.el.getBoundingClientRect(), vw = innerWidth, vh = innerHeight, m = 12, gap = 14;
    const ring = { l: Math.max(2, r.left - 6), t: Math.max(2, r.top - 6), r: Math.min(vw - 2, r.right + 6), b: Math.min(vh - 2, r.bottom + 6) };
    Object.assign(layer().querySelector(".tour-ring").style, { left: `${ring.l}px`, top: `${ring.t}px`,
      width: `${ring.r - ring.l}px`, height: `${ring.b - ring.t}px` });
    const c = card(), w = c.offsetWidth, h = c.offsetHeight;
    const clampX = (x) => Math.max(m, Math.min(x, vw - w - m)), clampY = (y) => Math.max(m, Math.min(y, vh - h - m));
    const meets = (x, y) => x < ring.r && ring.l < x + w && y < ring.b && ring.t < y + h;
    const at2 = {
      inside: () => [clampX(r.left + r.width / 2 - w / 2), clampY(r.top + 58)],
      right: () => [ring.r + gap, clampY(r.top + r.height / 2 - h / 2)],
      left: () => [ring.l - gap - w, clampY(r.top + r.height / 2 - h / 2)],
      below: () => [clampX(r.left), ring.b + gap],
      "below-end": () => [clampX(r.right - w), ring.b + gap],
      above: () => [clampX(r.left), ring.t - gap - h],
    };
    const tries = { inside: ["inside"], right: ["right", "left", "below", "above"], below: ["below", "above", "right", "left"],
      "below-end": ["below-end", "below", "left"], above: ["above", "below", "right", "left"] }[s.place];
    let best = null;
    for (const k of tries) {
      const [x, y] = at2[k]();
      const fits = x >= m - 0.5 && y >= m - 0.5 && x + w <= vw - m + 0.5 && y + h <= vh - m + 0.5;
      if (fits && (k === "inside" || !meets(x, y))) { best = [x, y]; break; }
    }
    if (!best) { const [x, y] = at2[tries[0]](); best = [clampX(x), clampY(y)]; }
    c.style.transform = `translate(${Math.round(best[0])}px, ${Math.round(best[1])}px)`;
  }

  /** The tour ends: kind "done" or "skip" writes the pref (at once: the window may close
   *  next); null only closes it. The card fades out (a copy), the focus goes back. */
  function stop(kind) {
    const tour = wb.tour, el = layer();
    if (!tour) return;
    wb.tour = null;
    const had = el.contains(document.activeElement);
    if (had) document.activeElement.blur();
    if (!el.classList.contains("hidden") && kind) ghost(el, 160);
    el.classList.add("hidden");
    if (kind) {
      prefSet(KEY, kind === "done" ? `${VERSION}:done` : `${VERSION}:skip:${tour.n}`);
      flushPrefs();
    }
    const back = tour.back;
    if (had && back && back.isConnected && back !== document.body && !el.contains(back)) back.focus({ preventScroll: true });
  }

  /** The tour's keys, while it is open and nothing is being typed: → (or Enter, the focus on
   *  nothing in particular) the next step, ← the one before, Esc skips it. Enter on one of its
   *  buttons is that button's own. Returns whether the key was the tour's. */
  function tourKey(ev) {
    if (!wb.tour) return false;
    const k = ev.key, el = document.activeElement, inCard = !!(el && card().contains(el));
    const loose = !el || el === document.body || inCard;
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return false;
    if (k === "Escape") { stop("skip"); return true; }
    if (!loose) return false;
    if (k === "ArrowRight" || (k === "Enter" && !inCard)) {
      const list = listed();
      if (!list.length || wb.tour.n === list.slice(-1)[0].n) { if (k === "Enter") stop("done"); }
      else step(1);
      return true;
    }
    if (k === "ArrowLeft") { step(-1); return true; }
    return false;
  }

  /** At every new state (app-state.js): the tour, once a tab shows, for a new viewer; an open
   *  tour placed again (and said again in another language). */
  function firstRun() {
    if (wb.tour) {
      if (wb.tour.lang !== I18N.lang) go(posOf(wb.tour.n), 1);
      else place();
      return;
    }
    if (wb.firstRunSeen || !wb.state || !wb.state.tabs.length || !shownTab()) return;
    if (menuOpen() || !$("modal").classList.contains("hidden")) return;
    wb.firstRunSeen = true;
    const seen = prefGet(KEY), older = prefGet("wb.notice.layout2");
    if (seen === undefined) return;               // nothing keeps it: never, rather than at every launch
    // a new viewer: the whole tour; one who dismissed an older version of it (its number before
    // the colon): the steps added since, once
    const was = seen === null ? 0 : parseInt(String(seen).split(":")[0], 10) || 0;
    if ((seen === null && older === null) || (seen !== null && was < Number(VERSION))) {
      setTimeout(() => {                          // once the layout has settled
        if (wb.tour) return;
        if (!shownTab() || menuOpen() || !$("modal").classList.contains("hidden")) { wb.firstRunSeen = false; return; }
        startTour(was);
      }, 600);
    }
  }

  // ------------------------------------------------------------------ the legend
  const sw = (inner, vb) => `<svg class="lg-sw" viewBox="${vb || "0 0 60 36"}" aria-hidden="true">${inner}</svg>`;
  const box = (cls, extra) => `<g class="fs-node ${cls}"><rect x="6" y="6" width="44" height="26" rx="7"/>${extra || ""}</g>`;
  // in the symbols' view (app-flowsheet.js viewBoxes): a small Heater symbol (beside the node's
  // group, so no box rule reaches its lines) in its frame, the marks just outside the frame as on
  // the flowsheet (flowsheet.js: the dot at the top left, the badge and ✦ at the top right)
  const SYM = "Heater";
  const iconView = () => !!window.FSI && !WBA.viewBoxes();
  const symbol = (cls, extra) => {
    const s = FSI.shape(SYM);
    return `<svg class="lg-sym" x="20" y="8" width="22" height="22" viewBox="0 0 ${s.w} ${s.h}" overflow="visible">${s.g}</svg>`
      + `<g class="fs-node ${cls}"><rect class="frame" x="17" y="5" width="28" height="28" rx="4"/>${extra || ""}</g>`;
  };
  /** What the colours, outlines and marks on the flowsheet mean, each beside a small drawing
   *  of it made with the flowsheet's own classes (so the two cannot drift apart). */
  function legendHtml() {
    const fams = ["mix", "heat", "rx", "sep", "press"].map((f) => `<span class="lg-fam"><i class="${f}"></i>${esc(t(`fam_${f}`))}</span>`).join("");
    // the symbols' view: an outline round a symbol in place of the family bar, heat and work
    // streams dashed in place of recycles (solid there)
    const ic = iconView(), node = ic ? symbol : box, vb = ic ? "-2 -2 64 38" : "";
    const at = ic ? [47, 3] : [48, 8], dot = ic ? [15, 3] : [8, 8];
    const badge = (s) => `<g class="badge"><circle cx="${at[0]}" cy="${at[1]}" r="7"/><text x="${at[0]}" y="${at[1] + 3.5}">${s}</text></g>`;
    const rows = [
      ic ? [sw(node("lg-frame"), vb), t("lg_frame")]
        : [sw(box("", `<rect class="fam heat" x="10" y="12" width="4" height="14" rx="2"/>`)), t("lg_fam"), `<span class="lg-fams">${fams}</span>`],
      [sw(node("err", badge("!")), vb), t("lg_err")],
      [sw(node("warn", badge("⚠")), vb), t("lg_warn")],
      [sw(node("hl", `<g class="aimark"><circle cx="${at[0]}" cy="${at[1]}" r="7"/><path d="${FS.star(at[0], at[1], 4.2)}"/></g>`), vb), t("lg_ai")],
      [sw(node("sel"), vb), t("lg_sel")],
      [sw(node("link"), vb), t("lg_link")],
      ic ? [sw(`<g class="fs-edge energy"><path class="line" d="M6,18H50" marker-end="url(#lg-arr-ink)"/></g>`
        + `<defs><marker id="lg-arr-ink" viewBox="0 0 8 7" refX="8" refY="3.5" markerWidth="8" markerHeight="7" markerUnits="userSpaceOnUse" orient="auto"><path d="M0,0 L8,3.5 L0,7 z" fill="#1a1a1a"/></marker></defs>`, vb), t("lg_energy")]
        : [sw(`<g class="fs-edge back"><path class="line" d="M6,18H50" marker-end="url(#lg-arr)"/></g>`
        + `<defs><marker id="lg-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#6b7785"/></marker></defs>`), t("lg_recycle")],
      [sw(`<text class="lg-val" x="30" y="14" text-anchor="middle">80 C</text><text class="lg-val old" x="30" y="32" text-anchor="middle">1.2 bar</text>`), t("lg_stale")],
      [sw(`<g class="fs-note open"><path class="bubble" d="M12,6H48A8,8 0 0 1 48,22H33L30,27L27,22H12A8,8 0 0 1 12,6Z"/><circle class="state" cx="15" cy="14" r="3"/></g>`), t("lg_note")],
    ];
    // where the window reads the change record: the dots of changes not seen yet (changes.js)
    if (WBC.on()) {
      rows.push([sw(node("", `<g class="chdot a-ai"><circle cx="${dot[0]}" cy="${dot[1]}" r="6.5"/><text x="${dot[0]}" y="${dot[1] + 3.2}">3</text></g>`), vb), t("lg_chg")]);
    }
    // annotations: the layer's outlined bubble at a block's bottom left, placed as the flowsheet
    // places it (flowsheet.js pinMark: 6 left of the corner, 5 below); in the symbols' view just
    // before the block's name, its tail toward it
    rows.push(ic ? [sw(`<text class="lg-nm" x="27" y="23">B1</text>${FS.pinMark(12, 19, { n: 2, fresh: true }, 0)}`, vb), t("lg_pin_ic")]
      : [sw(`<g class="fs-node"><rect x="18" y="2" width="38" height="19" rx="7"/></g>${FS.pinMark(12, 26, { n: 2, fresh: true }, -45)}`), t("lg_pin")],
    // what each run moved: the arrows beside the values
    [sw(`<text class="lg-val" x="28" y="23" text-anchor="middle">362 C<tspan class="vd" dx="2">▲</tspan></text>`), t("lg_delta")]);
    return `<div class="lg${ic ? " icons" : ""}">${rows.map(([pic, words, more]) => `<div class="lg-row">${pic}<span class="lg-t">${esc(words)}${more || ""}</span></div>`).join("")}</div>`;
  }
  const legendItems = () => [{ title: t("m_legend") }, { html: legendHtml() }];
  /** The legend, under the flowsheet capsule's ⋯ (whose menu lists it) where it shows, else under anchor. */
  function openLegend(anchor, ev) {
    const b = pq('.fs-tools [data-a="fs_menu"]'), at = shows(b) ? b : anchor || $("btn-more");
    if (ev) toggleMenu(at, legendItems, ev);
    else openMenu(at, legendItems(), false, false);
  }

  /** Help, in the ... menu and the logo's menu: the tour, the legend, the keys. */
  function helpItems(anchor) {
    const tab = shownTab();
    return [
      { label: t("m_tour"), icon: "sparkle", disabled: !tab, tip: tab ? "" : t("tour_need_tab"), run: () => startTour(0) },
      { label: t("m_legend"), icon: "help", tip: t("tip_legend"), run: () => openLegend(anchor) },
      { label: t("m_keys"), icon: "keyboard", run: showKeys },
    ];
  }

  // the logo: Help; the tour placed again when the window's size changes, or after a click
  // (what a step points at may have moved: the inspector opened, the column folded)
  document.addEventListener("DOMContentLoaded", () => {
    $("logo").addEventListener("click", (ev) => toggleMenu($("logo"), () => [{ title: t("m_help") }, ...helpItems($("logo"))], ev));
    const c = card();
    c.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-tour]");
      if (!b) return;
      const k = b.dataset.tour;
      if (k === "next") step(1);
      else if (k === "prev") step(-1);
      else stop(k === "done" ? "done" : "skip");
    });
    let frame = 0;
    window.addEventListener("resize", () => { if (wb.tour && !frame) frame = requestAnimationFrame(() => { frame = 0; place(); }); });
    document.addEventListener("pointerup", (ev) => { if (wb.tour && !c.contains(ev.target)) setTimeout(place, 280); }, true);
  });

  Object.assign(WBA, { firstRun, helpItems, openLegend, startTour, tourKey });
})();
