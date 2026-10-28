/* The flow width layer (with the composition view): a pale band under every stream's
 * line, as wide as the stream's flow on a log scale -- the largest BAND_MAX drawing units, a thousandth of
 * it BAND_MIN, less than that no band -- so where a component goes reads at a glance while the drawing
 * stays its black line art. Streams under VAL_SHARE of the largest show their value by their name (they
 * are the ones a band cannot tell apart: a vent's loss, a purge).
 *
 *   Flow  ->  Width · ETHANOL ▾       the capsule's button (feature flows), on per tab; pressed on, its menu
 *                                     opens at once where it was pressed (the last choice already drawn, kept
 *                                     per model: pref wb.fw.<model id>); its ▾ opens it again. What the width
 *                                     shows: "Total flow" (the stream values' F, nothing read), "Composition" (feature
 *                                     composition: each band split along the stream into its components'
 *                                     shares, PALETTE, the largest N_MIX - 1 and "other") or one of the model's
 *                                     components (the first N_COMP, the rest under "More components…"). Its tooltip is
 *                                     the legend: three ticks in one unit (composition: the components in
 *                                     their order, darkest first), and whether Aspen is still to be read.
 *
 * A component's flows are the server's (the event flows {tab, on, comp}; the session's flows, read off the
 * run path: tools/flows.py); comp "*" reads every component (composition, and the Values layer's component
 * line: app-comp.js), which one component's width is then taken from too. The bands read before stay while
 * new ones are read. Bands and values are the drawing's annotations (flowsheet.js: g.fs-band, g.fs-band-v,
 * FIG_DROP): never in a figure.
 *
 *   fwView(pane, tab)    FS.render's v.flows ({w: {stream: units}, vals: {stream: text}, total, seg}), or null
 *   fwTools(pane, tab)   the capsule's button and its ▾: label, state, legend (renderTools)
 *   fwPeek(tab, name)    the stream hover card's line [label, value], or null
 *   fwAll(tab)           every component's flows (comp "*"), {comps, unit, basis, v, at, ...}, or null
 *   fwRank(all)          the components by their flow over every stream, the largest first
 *   fwMixKey(tab)        while the composition shows: {component: its segment colour}, else null
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { esc, finite, icon, prefGet, prefSet, sessOf, t, tabOf, wb } = WBA;
  const { fsView, renderTools, toggleMenu } = WBA.later;

  const N_COMP = 8, BAND_MAX = 8, BAND_MIN = 2, DECADES = 3, VAL_SHARE = 0.05, REPOST_MS = 3000;
  const TOTAL = "*", MIX = "+", ALL = "*";        // (the pref's total flow; its composition; the server's every component)
  const N_MIX = 8;                                 // composition segments a band at most (the last: "other")

  // ------------------------------------------------------------------ what the width shows
  const comps = (tab) => {
    const c = (sessOf(tab).flowsheet || {}).components;
    return Array.isArray(c) ? c.filter((x) => typeof x === "string" && x) : [];
  };
  const modelKey = (tab) => {
    const s = sessOf(tab);
    return (s.model && s.model.id) || (s.flowsheet && s.flowsheet.model) || tab.session;
  };
  const prefKey = (tab) => `wb.fw.${modelKey(tab)}`;
  /** This model's choice: TOTAL, MIX (its composition), a component it has, or null. */
  function chosen(tab) {
    const v = prefGet(prefKey(tab));
    return v === TOTAL || v === MIX || comps(tab).includes(v) ? v : null;
  }
  /** What the width shows now: MIX or a component, else TOTAL. */
  const what = (tab) => chosen(tab) || TOTAL;
  const recOf = (tab) => (tab ? wb.recs.get(tab.id) : null);
  const isOn = (tab) => { const r = recOf(tab); return !!(r && r.fwOn); };

  /** Every component's flows in every stream (the server's comp "*"), or null. */
  function fwAll(tab) {
    const f = sessOf(tab).flows;
    if (!f || typeof f !== "object" || f.comp !== ALL || !Array.isArray(f.comps)) return null;
    return f;
  }
  /** The components of fwAll's answer by their flow over every stream, the largest first, those with
   *  none left out: [index]. Kept per answer. */
  const ranked = new WeakMap();
  function fwRank(all) {
    if (ranked.has(all)) return ranked.get(all);
    const sum = all.comps.map(() => 0);
    Object.values(all.v || {}).forEach((a) => { if (Array.isArray(a)) a.forEach((x, i) => { if (finite(x) > 0) sum[i] += x; }); });
    const out = sum.map((s, i) => [s, i]).filter(([s]) => s > 0).sort((a, b) => b[0] - a[0] || a[1] - b[1]).map(([, i]) => i);
    ranked.set(all, out);
    return out;
  }

  /** The flows the layer goes by: {comp, unit, v: {stream: number}, basis, reading, busy, partial}, and for
   *  MIX mix: {stream: [flow per component]}, comps. */
  function data(tab) {
    const sess = sessOf(tab), c = what(tab), v = {};
    if (c === TOTAL) {
      let unit = "";
      Object.entries(sess.values || {}).forEach(([n, x]) => {
        const f = x && x.f;
        if (Array.isArray(f) && typeof f[0] === "number" && isFinite(f[0])) { v[n] = f[0]; unit = unit || f[1] || ""; }
      });
      return { comp: TOTAL, unit, v };
    }
    const all = fwAll(tab), f = sess.flows && typeof sess.flows === "object" ? sess.flows : null;
    const state = (x) => ({ basis: x.basis, reading: !!x.reading, busy: !!x.busy, partial: !!x.partial });
    if (c === MIX) {
      if (!all) return { comp: c, unit: "", v, reading: true };
      const mix = {};
      Object.entries(all.v || {}).forEach(([n, a]) => {
        if (!Array.isArray(a)) return;
        mix[n] = a.map((x) => (finite(x) > 0 ? x : 0));
        v[n] = mix[n].reduce((s, x) => s + x, 0);
      });
      return Object.assign({ comp: c, unit: all.unit || "", v, mix, comps: all.comps, all }, state(all));
    }
    if (all && all.comps.includes(c)) {             // (one component out of every one)
      const i = all.comps.indexOf(c);
      Object.entries(all.v || {}).forEach(([n, a]) => { const x = Array.isArray(a) ? finite(a[i]) : null; if (x !== null) v[n] = x; });
      return Object.assign({ comp: c, unit: all.unit || "", v }, state(all));
    }
    if (!f || f.comp !== c) return { comp: c, unit: "", v, reading: true };
    Object.entries(f.v && typeof f.v === "object" ? f.v : {}).forEach(([n, x]) => { if (typeof x === "number" && isFinite(x)) v[n] = x; });
    return Object.assign({ comp: c, unit: f.unit || "", v }, state(f));
  }

  /** A flow as few digits as read well: 11,461 · 258 · 3.6 · 0.0123. */
  function fmtFlow(x) {
    if (Math.abs(x) >= 1000) return Math.round(x).toLocaleString("en-US");
    return String(Number(x.toPrecision(3)));
  }
  const withUnit = (x, u) => `${fmtFlow(x)}${u ? ` ${u}` : ""}`;
  const maxOf = (d) => Math.max(0, ...Object.values(d.v));
  /** A band's width for a flow x of the largest m (drawing units), or 0: none. */
  function width(x, m) {
    const r = m > 0 ? x / m : 0;
    return r >= Math.pow(10, -DECADES) ? BAND_MIN + (BAND_MAX - BAND_MIN) * (Math.log10(r) + DECADES) / DECADES : 0;
  }
  /** The composition's legend order: the largest components (by fwRank), at most N_MIX - 1 of them where
   *  there are more than N_MIX (the rest: "other"), as [index]; and whether there is a rest. */
  function mixOrder(d) {
    const r = fwRank(d.all);
    return r.length > N_MIX ? { top: r.slice(0, N_MIX - 1), rest: r.slice(N_MIX - 1) } : { top: r, rest: [] };
  }

  // ------------------------------------------------------------------ the drawing
  function fwView(pane, tab) {
    ask(tab);                                      // (what the server reads: this layer and the Values layer's line)
    if (!isOn(tab)) return null;
    const d = data(tab), m = maxOf(d), w = {}, vals = {};
    Object.entries(d.v).forEach(([n, x]) => {
      const k = width(x, m);
      if (k > 0) w[n] = k;
      if (x > 0 && x < VAL_SHARE * m) vals[n] = withUnit(x, d.unit);
    });
    let seg = null;
    if (d.mix) {                                   // each band's segments: [start, length, colour], shares of 1
      const o = mixOrder(d);
      seg = {};
      Object.entries(d.mix).forEach(([n, a]) => {
        const tot = d.v[n];
        if (!(w[n] > 0) || !(tot > 0)) return;
        let at = 0;
        const out = [];
        o.top.forEach((i, k) => { const s = a[i] / tot; if (s > 0) { out.push([at, s, k]); at += s; } });
        const rest = o.rest.reduce((s, i) => s + a[i], 0) / tot;
        if (rest > 0) out.push([at, rest, N_MIX - 1]);
        seg[n] = out;
      });
    }
    return { w, vals, total: d.comp === TOTAL, seg };   // (total: a stream's F value line says its value already)
  }

  /** The stream hover card's line: the chosen component's flow in the stream (not for the total or the
   *  composition: the card has those). */
  function fwPeek(tab, name) {
    if (!isOn(tab)) return null;
    const d = data(tab);
    return d.comp !== TOTAL && d.comp !== MIX && typeof d.v[name] === "number" ? [d.comp, withUnit(d.v[name], d.unit)] : null;
  }
  /** While the composition shows: each component's segment colour (0 .. N_MIX - 1, the last "other") by
   *  name, so the hover card can key its shares to the segments; else null. */
  function fwMixKey(tab) {
    if (!isOn(tab) || what(tab) !== MIX) return null;
    const all = fwAll(tab);
    if (!all) return null;
    const o = mixOrder({ all }), key = {};
    o.top.forEach((i, k) => { key[all.comps[i]] = k; });
    o.rest.forEach((i) => { key[all.comps[i]] = N_MIX - 1; });
    return key;
  }

  // ------------------------------------------------------------------ asking the server
  /** What this tab has the server read: every component (the composition, or the Values layer's
   *  component line: app-comp.js cpWantsAll), one component, or nothing. */
  function want(tab) {
    const c = isOn(tab) ? what(tab) : null;
    if (c === MIX || (WBA.cpWantsAll && WBA.cpWantsAll(tab))) return ALL;
    return c && c !== TOTAL ? c : null;
  }
  /** Tell the server what this tab's layers read. A change is sent (also one this tab did not make: the
   *  component gone from the model); the same request again only to a server whose session has another
   *  component, or none (a restart), after REPOST_MS. */
  function ask(tab) {
    const r = recOf(tab);
    if (!r) return;
    const c = want(tab), on = c !== null, key = on ? c : "";
    if (key === (r.fwSent || "")) {
      const f = sessOf(tab).flows;
      if (!on || (f && f.comp === c) || Date.now() - (r.fwAt || 0) < REPOST_MS) return;
    }
    r.fwSent = key;
    r.fwAt = Date.now();
    wb.post({ type: "flows", tab: tab.id, on, comp: on ? c : null });
  }

  function redraw(pane, tab) {
    FS.render(pane.svg, fsView(pane, tab));
    renderTools(pane, tab);
  }

  /** Pressed: on with this model's last choice, and its menu open where it was pressed (a second look
   *  at what else it can show is one click); pressed again: off. */
  function toggle(pane, btn, ev) {
    const tab = tabOf(pane.tabId), r = recOf(tab);
    if (!tab || !r) return;
    r.fwOn = !r.fwOn;
    ask(tab);
    redraw(pane, tab);
    if (r.fwOn) toggleMenu(btn, () => items(pane, tab), ev);
  }

  function choose(pane, tab, c) {
    prefSet(prefKey(tab), c);
    const r = recOf(tab);
    if (r) r.fwOn = true;
    ask(tab);
    redraw(pane, tab);
  }

  // ------------------------------------------------------------------ the menu
  function items(pane, tab) {
    const c = what(tab), cs = comps(tab), d = data(tab);
    const it = (label, val, tip) => Object.assign({ label, check: c === val, run: () => choose(pane, tab, val) }, tip ? { tip } : {});
    const out = [{ html: `<div class="fw-w">${esc(t("fw_by"))}</div>` }, it(t("fw_total"), TOTAL)];
    if (cs.length > 1) out.push(it(t("fw_mix"), MIX, t("tip_fw_mix_item")));
    if (cs.length) out.push({ sep: true }, ...cs.slice(0, N_COMP).map((x) => it(x, x)));
    if (cs.length > N_COMP) out.push({ label: t("fw_more"), icon: "more", sub: cs.slice(N_COMP).map((x) => it(x, x)) });
    const notes = [c !== TOTAL && d.partial ? t("fw_partial") : "", c !== TOTAL && d.basis === "mole" ? t("fw_mole_note") : ""].filter(Boolean);
    if (notes.length) out.push({ sep: true }, { html: notes.map((s) => `<div class="fw-note">${esc(s)}</div>`).join("") });
    return out;
  }

  // ------------------------------------------------------------------ the button
  function buttons(pane) {
    let b = pane.q('.fs-tools [data-a="flows"]');
    if (b) return b;
    const vb = pane.q('.fs-tools [data-a="values_pick"]') || pane.q('.fs-tools [data-a="values"]');
    if (!vb) return null;
    vb.insertAdjacentHTML("afterend", `<button data-a="flows" class="tgl hidden" aria-pressed="false">${icon("flow")}<span class="bt"></span></button>`
      + `<button data-a="flows_pick" class="hidden" aria-haspopup="menu">${icon("chevron-down")}</button>`);
    b = pane.q('.fs-tools [data-a="flows"]');
    b.addEventListener("click", (ev) => toggle(pane, b, ev));
    pane.q('.fs-tools [data-a="flows_pick"]').addEventListener("click", (ev) => {
      const tab = tabOf(pane.tabId);
      if (tab && isOn(tab)) toggleMenu(b, () => items(pane, tab), ev);
    });
    return b;
  }

  /** The legend: what the width is, three ticks in one unit (the largest and the decades under it),
   *  the composition's components in their order (darkest first: the palette's grey order), what the
   *  small values mean, and whether Aspen is still to be read. */
  function legend(tab) {
    const d = data(tab), m = maxOf(d);
    const word = d.comp === TOTAL ? t("fw_w_total") : d.comp === MIX ? "" : t(d.basis === "mole" ? "fw_w_mole" : "fw_w_mass", d.comp);
    const ticks = m > 0 ? [...new Set([Math.pow(10, Math.round(Math.log10(m / 100))), Math.pow(10, Math.round(Math.log10(m / 10))), m])]
      .filter((x) => x <= m).sort((a, b) => a - b).map(fmtFlow).join(" · ") + (d.unit ? ` ${d.unit}` : "") : "";
    let head = t("tip_flows", word), order = "";
    if (d.comp === MIX) {
      head = t("tip_fw_mix", t(d.basis === "mole" ? "fw_b_mole" : "fw_b_mass"));
      if (d.all) {
        const o = mixOrder(d);
        order = o.top.map((i, k) => `${k + 1} ${d.comps[i]}`).concat(o.rest.length ? [`${N_MIX} ${t("cp_other")}`] : []).join(" · ");
      }
    }
    return [head, order, ticks, t("tip_fw_vals"), d.busy ? t("fw_busy") : d.reading ? t("fw_reading") : ""].filter(Boolean).join("\n");
  }

  function fwTools(pane, tab) {
    const b = buttons(pane);
    if (!b) return;
    const pk = pane.q('.fs-tools [data-a="flows_pick"]'), on = isOn(tab);
    const c = what(tab), label = on ? t("btn_flows_on", c === TOTAL ? t("fw_total") : c === MIX ? t("fw_mix") : c) : t("btn_flows");
    const tip = on ? legend(tab) : t("tip_flows_off");
    const sig = JSON.stringify([on, label, tip]);
    if (b.dataset.sig === sig) return;
    b.dataset.sig = sig;
    b.classList.remove("hidden");
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", String(on));
    b.querySelector(".bt").textContent = label;
    b.title = tip;
    pk.classList.toggle("hidden", !on);
    pk.classList.toggle("on", on);
    pk.title = t("tip_fw_pick");
  }

  Object.assign(WBA, { compsOf: comps, fwAll, fwMixKey, fwPeek, modelKey, fwTools, fwView, fwFmt: fmtFlow, fwAsk: ask });
})();
