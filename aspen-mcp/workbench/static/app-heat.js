/* The heat integration view: the plans from a pinch run (heatOf, heatPlan), the heat plan
 * card on the flowsheet (renderPlan, fitPlan, wirePlan, shutPlan), and Ask AI to apply.
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { esc, ghost, glide, HINT_ROOM, listFades, renderEdges, renderPane, t, tabOf, wb } = WBA;
  const { focusComposer } = WBA.later;

  // ------------------------------------------------------------------ heat integration view
  /** The latest pinch match suggestions in the tab's results, with where each stream sits. */
  function heatOf(tab) {
    const items = ((tab && tab.results) || {}).tables || [];
    for (let i = items.length - 1; i >= 0; i--) if (items[i].heat) return items[i].heat;
    return null;
  }
  const heatPref = (tab) => (wb.heat[tab.id] = wb.heat[tab.id] || { on: false, plan: 0 });
  const heatPlans = (heat) => Math.max(1, ...(heat.regions || []).map((r) => (r.alts || []).length));
  /** Plan k: each pinch region's k-th alternative (its last when it has fewer): the
   *  exchanger matches, and the utility each block still needs. */
  function heatPlan(heat, k) {
    const links = [], utils = new Map();
    (heat.regions || []).forEach((reg) => {
      const alts = reg.alts || [];
      (alts[Math.min(k, alts.length - 1)] || []).forEach((m) => {
        if (!m.utility) {
          links.push({ hot: m.hot, cold: m.cold, duty: m.duty, split: m.check === "needs_split",
            a: heat.where[m.hot], b: heat.where[m.cold] });
          return;
        }
        const heating = m.hot === "HOT-UTILITY", name = heating ? m.cold : m.hot, s = heat.where[name];
        const key = `${name}|${heating}`;
        const u = utils.get(key) || { name, block: s && s.block, part: s && s.part, heating, duty: 0 };
        u.duty += m.duty || 0;
        utils.set(key, u);
      });
    });
    return { links, utils: [...utils.values()] };
  }
  const kw = (v) => Number(Number(v || 0).toPrecision(4)).toString();
  /** Put the plan shown in the composer, as a request to the whole tab: the user reads it
   *  and sends it; the AI changes the model with its own tools, saving a snapshot first so
   *  the change can be undone. */
  function askApply(tab) {
    const heat = heatOf(tab), p = heatPref(tab);
    if (!heat) return;
    const plan = heatPlan(heat, p.plan);
    const links = plan.links.map((l) => `• ${l.hot} → ${l.cold}  ${kw(l.duty)} kW${l.split ? `（${t("hi_split")}）` : ""}`);
    const utils = plan.utils.map((u) => `• ${u.name}  ${t(u.heating ? "hi_heat" : "hi_cool", kw(u.duty))}`);
    const text = t("hi_apply_text", p.plan + 1, links.join("\n") || "—", utils.join("\n") || "—");
    focusComposer(wb.pane, { pin: { target: null }, text });
  }

  /** A pinch stream's name as the card says it: its block and the part ("GLYCRCOL reboiler"),
   *  where the pinch run placed it on one; else its own name. */
  function heatName(heat, name) {
    const w = (heat.where || {})[name];
    return w && w.block && (w.part === "reb" || w.part === "cond") ? `${w.block} ${t(w.part === "reb" ? "hi_reb" : "hi_cond")}` : name;
  }
  /** The heat plan card, at the flowsheet's bottom left while the heat plans layer shows:
   *  the plans to switch between (each one alternative per pinch region), the plan's
   *  exchangers (hot to cold, duty, a stream split where one is needed) and the utilities
   *  still needed, the heat the plan recovers, and Ask AI to apply. A card under 380 px, or
   *  one with too little room beside the inspector for the plan and a readable drawing (600
   *  px), folds it to its head row (the plans and the heat recovered), which opens upward
   *  over the drawing. Its rows are drawn again only when the plan or the language changes;
   *  a new plan's rows fade in. Showing, hiding or folding it changes the free area
   *  (FS.insets). */
  function renderPlan(pane, tab) {
    const card = pane.q(".fs-plan"), heat = heatOf(tab), hp = heatPref(tab), shown = !!(heat && hp.on);
    const fold = shown && planFolds(pane);
    const was = [card.classList.contains("hidden"), card.classList.contains("fold")];
    card.classList.toggle("hidden", !shown);
    card.classList.toggle("fold", fold);
    if (!fold) card.classList.remove("open");
    if (was[0] !== !shown || was[1] !== fold) FS.moved(pane.svg);
    if (!shown) {
      if (!was[0]) { FS.mark(pane.svg, [], "hov"); pane.svg.classList.remove("heat-hover"); }   // a row was pointed at
      pane.planSig = null;
      glide(card.querySelector(".pl-seg .glide"), null);   // shown again, it starts where it is
      return;
    }
    const n = heatPlans(heat);
    hp.plan = Math.min(hp.plan, n - 1);
    const plan = heatPlan(heat, hp.plan), rec = plan.links.reduce((s, l) => s + (l.duty || 0), 0);
    const sig = JSON.stringify([tab.id, I18N.lang, hp.plan, n, plan.links, plan.utils]);
    if (pane.planSig !== sig) {
      const swap = !!pane.planSig && pane.planAt === `${tab.id}|${n}` && pane.planK !== hp.plan;
      pane.planSig = sig;
      pane.planAt = `${tab.id}|${n}`;
      pane.planK = hp.plan;
      const q = (s) => card.querySelector(s), seg = q(".pl-seg");
      // the plan switch: its pills made again only for another count or language; the glide
      // stays and slides to the plan shown
      const segKey = `${n}|${I18N.lang}`;
      if (seg.dataset.key !== segKey) {
        seg.dataset.key = segKey;
        const gl = seg.querySelector(".glide") || Object.assign(document.createElement("i"), { className: "glide gx" });
        [...seg.children].forEach((el) => { if (el !== gl) el.remove(); });
        if (gl.parentNode !== seg) seg.prepend(gl);
        seg.insertAdjacentHTML("beforeend", n > 1 ? Array.from({ length: n }, (_, i) => `<button data-plan="${i}"`
          + ` title="${esc(`${t("hi_plan", i + 1)}\n${t("tip_heat_plan")}`)}">${esc(t("hi_plan", i + 1))}</button>`).join("") : "");
      }
      seg.classList.toggle("hidden", n < 2);
      seg.querySelectorAll("button").forEach((b) => b.classList.toggle("on", Number(b.dataset.plan) === hp.plan));
      q(".pl-sum").innerHTML = `<span>${esc(t("hi_rec", kw(rec)))}</span>`;   // (whole or not at all: style.css)
      q(".pl-head").title = t("hi_rec", kw(rec));
      // a row: what it names (each end cut on its own where the card is narrow), its duty; the
      // pinch's own names and the duty in its tooltip
      // (a utility's row also says what its sign means: note)
      const row = (attr, i, names, duty, cls, extra, tip, note) => `<button class="pl-row${cls}" ${attr}="${i}" title="${esc([`${tip} · ${duty}`, note, t("tip_pl_row")].filter(Boolean).join("\n"))}">`
        + `<span class="pl-hc">${names.map((n) => `<span>${esc(n)}</span>`).join(`<svg class="ic ar" aria-hidden="true"><use href="#i-stream"/></svg>`)}</span>`
        + `${extra || ""}<span class="kw">${esc(duty)}</span></button>`;
      // another plan while the rows show: a copy of the old rows fades out over the new ones
      const list = q(".pl-list");
      list.parentNode.querySelectorAll(".pl-list.ghost").forEach((g) => g.remove());
      if (swap && list.offsetHeight) {
        const g = ghost(list, 150), top = list.scrollTop;
        g.style.top = `${list.offsetTop}px`;
        g.style.height = `${list.offsetHeight}px`;
        if (top) g.scrollTop = top;                // the rows it showed, not the list's top
        list.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 150, easing: "cubic-bezier(.2, .8, .2, 1)" });
      }
      list.innerHTML = (plan.links.length ? plan.links.map((l, i) => row("data-heat", i,
        [heatName(heat, l.hot), heatName(heat, l.cold)], `${kw(l.duty)} kW`, "",
        l.split ? `<small class="pl-split">${esc(t("hi_split"))}</small>` : "", `${l.hot} → ${l.cold}`)).join("")
        : `<div class="pl-none">${esc(t("hi_none"))}</div>`)
        + (plan.utils.length ? `<div class="pl-sub" title="${esc(t("tip_hi_util"))}">${esc(t("hi_utils"))}</div>` + plan.utils.map((u, i) => row("data-util", i,
          [heatName(heat, u.name)], `${u.heating ? "+" : "−"}${kw(u.duty)} kW`, ` u ${u.heating ? "heat" : "cool"}`, "", u.name, t("tip_hi_util"))).join("") : "");
      q(".pl-rec").innerHTML = `${esc(t("hi_rec_l"))} <b>${esc(kw(rec))} kW</b>`;
      q(".pl-rec").title = t("tip_hi_rec", kw(heat.recovery));
    }
    const fb = card.querySelector(".pl-fold"), open = card.classList.contains("open");
    const tip = t(open ? "tip_pl_close" : "tip_pl_open");
    if (fb.title !== tip) fb.title = tip;
    fitPlan(pane);
    glide(card.querySelector(".pl-seg .glide"), card.querySelector(".pl-seg:not(.hidden) button.on"));
    listFades(card.querySelector(".pl-list"));  // a list taller than the card scrolls: a fade where more lies
  }
  /** Whether the heat plan card folds to its row: a short flowsheet card, or too little room
   *  beside the inspector for the plan and a readable drawing (600 px). */
  function planFolds(pane) {
    const insp = pane.q(".insp:not(.hidden):not(.ghost)"), room = pane.q(".fs-area").clientWidth - (insp ? insp.offsetWidth + 18 : 0);
    return pane.q(".fs-wrap").classList.contains("short") || room < 600;
  }
  /** The card keeps left of the inspector: no wider than the room there, its rows' words cut
   *  where it is narrower than they need. A folded row's total shows whole or not at all
   *  (.nosum; the head's tooltip has it), so the row is only as wide as what it shows.
   *  Unfolded, it is at least 320 px (or 60 % of the flowsheet card), and grows with its rows'
   *  words up to 380 px where the drawing keeps 240 px beside it. Run on every size change
   *  (the edge hints' count), so it also folds or unfolds the card when the room beside the
   *  inspector crosses the line. */
  function fitPlan(pane) {
    const card = pane.q(".fs-plan");
    if (card.classList.contains("hidden")) return;
    if (card.classList.contains("fold") !== planFolds(pane)) {
      const tab = tabOf(pane.tabId);
      if (tab) { renderPlan(pane, tab); return; }     // (which fits it again)
    }
    const aw = pane.q(".fs-area").clientWidth, room = Math.max(160, Math.round(aw - FS.insets(pane.svg).right - 20));
    const fold = card.classList.contains("fold"), lo = fold ? 0 : Math.round(Math.min(320, 0.6 * aw, room));
    const hi = fold ? room : Math.max(lo, Math.round(Math.min(380, 0.6 * aw, room - 240)));
    if (card.style.minWidth !== `${lo}px`) card.style.minWidth = `${lo}px`;
    if (card.style.maxWidth !== `${hi}px`) card.style.maxWidth = `${hi}px`;
    if (!fold) return;
    // the row's parts before the total and after it (▴ and the padding), the total between,
    // 6 px apart (the head's gap): whether all of it fits the card's widest
    card.classList.remove("nosum");
    const head = card.querySelector(".pl-head").getBoundingClientRect(), fb = card.querySelector(".pl-fold").getBoundingClientRect();
    const last = (card.querySelector(".pl-seg:not(.hidden)") || card.querySelector(".pl-title")).getBoundingClientRect();
    const sum = card.querySelector(".pl-sum > span"), sw = sum ? sum.offsetWidth : 0;
    const need = (last.right - head.left) + 6 + sw + 6 + (head.right - fb.left) + (card.offsetWidth - head.width);
    card.classList.toggle("nosum", !sw || need > hi + 0.5);
  }
  /** The card's parts: a plan's number shows that plan (framed on the flowsheet); pointing at
   *  a row dims every other arc and utility (at once: a class on the drawing, FS.mark), a
   *  click shows its arc with both its blocks (FS.showHeat) and rings its duty label, shutting
   *  a folded card's rows first; ▴ opens a folded card, Ask AI to apply puts the plan in the
   *  composer. */
  function wirePlan(pane) {
    const card = pane.q(".fs-plan"), svg = pane.svg;
    let cur = null;
    const hot = (row) => {
      FS.mark(svg, row ? [row.dataset.heat !== undefined ? `heat:${row.dataset.heat}` : `util:${row.dataset.util}`] : [], "hov");
      svg.classList.toggle("heat-hover", !!row);
    };
    card.addEventListener("click", (ev) => {
      const tab = tabOf(pane.tabId), b = ev.target.closest("button");
      if (!tab || !b) return;
      if (b.dataset.plan !== undefined) {
        const hp = heatPref(tab), k = Number(b.dataset.plan);
        if (hp.plan === k) return;
        hp.plan = k;
        pane.sigs = {};
        renderPane(pane);
        FS.frameHeat(svg, HINT_ROOM);
      } else if (b.dataset.p === "fold") {
        card.classList.toggle("open");
        renderPlan(pane, tab);
        renderEdges(pane);                         // the pills it stepped over, or no longer
      } else if (b.dataset.p === "ask") askApply(tab);
      else if (b.classList.contains("pl-row")) {
        const tg = b.dataset.heat !== undefined ? { kind: "heat", name: b.dataset.heat } : { kind: "util", name: b.dataset.util };
        if (card.classList.contains("open")) {     // a folded card's rows shut first: they lie over the drawing
          card.classList.remove("open");
          hot((cur = null));
          renderPlan(pane, tab);
        }
        const shown = FS.showHeat(svg, tg, HINT_ROOM);
        renderEdges(pane);                         // the hints, for the view and the card as they are now
        if (shown) FS.ping(svg, tg);
      }
    });
    card.querySelector(".pl-list").addEventListener("scroll", (ev) => listFades(ev.target), { passive: true });
    // the folded card's rows lie over the drawing, as a menu does: a press elsewhere shuts them
    document.addEventListener("mousedown", (ev) => { if (!card.contains(ev.target)) shutPlan(pane); }, true);
    card.addEventListener("mouseover", (ev) => { const row = ev.target.closest(".pl-row"); if (row !== cur) hot((cur = row)); });
    card.addEventListener("mouseleave", () => { if (cur) hot((cur = null)); });
  }

  /** Shut the folded heat plan's rows (Escape, a press elsewhere). Returns whether they were open. */
  function shutPlan(pane) {
    const card = pane.q(".fs-plan"), tab = tabOf(pane.tabId);
    if (!card.classList.contains("open")) return false;
    card.classList.remove("open");
    if (tab) renderPlan(pane, tab);
    renderEdges(pane);                           // the pills it lay over
    return true;
  }

  Object.assign(WBA, { fitPlan, heatOf, heatPlan, heatPlans, heatPref, renderPlan, shutPlan,
    wirePlan });
})();
