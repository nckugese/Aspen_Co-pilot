/* A stream's composition (feature composition): what each stream carries, component by
 * component, read by the server off the run path on demand (tools/flows.py) -- nothing shows until asked.
 *
 *   the inspector    a stream picked: its "Composition" section, first under the inspector's head -- one row a component
 *                    with a small bar (its share of the stream), its flow or fraction ("Flow" / "Fraction") by mass or
 *                    mole ("Mass" / "Mole"; mole where the model has no mass flows), the largest N_ROWS - 1 and "other"
 *                    where there are more, those with none counted in one line. One grid for the rows: every
 *                    bar starts and ends at one x, the values right-aligned in one column, the unit in its own.
 *                    Compact so the stream's inputs stay near: N_FOLD rows, the rest behind "N more components" (this
 *                    page's choice, every stream's). The choice is this viewer's (prefs wb.cp.q, wb.cp.b).
 *                    The server reads the stream's both bases (event stream_comp {tab, stream}; the session's
 *                    stream_comp), again once a run made them stale.
 *   the hover card   the largest components' shares in one line (cpPeek), from what is read already --
 *                    the stream's composition, or the flow layer's every component --, else asked for.
 *   the Values layer its ▾ (values_pick, while the layer shows) adds a line to each stream: a component's
 *                    flow or share (cpVals; pref wb.vc.<model id> "flow:NAME" / "frac:NAME"), from the flow
 *                    layer's read of every component (app-flows.js fwAll: comp "*", cpWantsAll).
 *
 *   cpSection(tab, tg, old)  the inspector's section: {sig, html}, or null (not a stream, no feature)
 *   cpAsk(tab, name)         the stream's composition asked for where it is not read, or stale
 *   cpPeek(tab, name)        the hover card's line {sig, html}, or null; cpPeekSig(tab, name) its sig alone
 *   cpWantsAll(tab)          whether the Values layer's line needs every component read
 *   cpVals(tab, values)      the stream values with that line (c: [value, unit, text]) where it shows
 *   cpTools(pane, tab)       the Values layer's ▾ (renderTools)
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { compsOf, esc, finite, icon, modelKey, prefGet, prefs, prefSet, sessOf, t, tabOf, wb } = WBA;
  const { fwAll, fwAsk, fwFmt, fwMixKey, renderInspector, renderPane, toggleMenu } = WBA.later;

  const N_ROWS = 8, N_FOLD = 4, N_PEEK = 3, PEEK_CH = 32, N_COMP = 8, REPOST_MS = 3000;
  let more = false;                                // (the inspector's rows past N_FOLD shown: this page's choice)

  // ------------------------------------------------------------------ reading
  const entryOf = (tab, name) => {
    const sc = sessOf(tab).stream_comp, e = sc && sc.s && typeof sc.s === "object" ? sc.s[name] : null;
    return e && typeof e === "object" && Array.isArray(e.comps) ? e : null;
  };
  /** Whether a stream has results to split: its total flow is read (a heat or work stream, a stream
   *  before the first run: none -- nothing asked, no section). */
  const hasFlow = (tab, name) => { const v = (sessOf(tab).values || {})[name]; return !!(v && Array.isArray(v.f)); };
  const asked = new Map();                         // "tab|stream" -> when asked (a server that lost it: asked again)
  /** Ask the server for a stream's composition: not kept, or stale and not being read again. */
  function cpAsk(tab, name) {
    if (!tab || !name || !wb.connected || !hasFlow(tab, name)) return;
    const e = entryOf(tab, name), k = `${tab.id}|${name}`;
    if (e && (e.reading || !e.stale)) return;
    if (Date.now() - (asked.get(k) || 0) < REPOST_MS) return;
    asked.set(k, Date.now());
    if (asked.size > 64) asked.delete(asked.keys().next().value);
    wb.post({ type: "stream_comp", tab: tab.id, stream: name });
  }

  /** A stream's flows by component in one basis: {comps, x: [number], unit, basis, src} -- the stream's
   *  own read (basis b where it has it, else the other), else the flow layer's every component. */
  function flowsOf(tab, name, b) {
    const e = entryOf(tab, name);
    if (e && (e.mass || e.mole)) {
      const basis = (b === "mole" && e.mole) || !e.mass ? "mole" : "mass";
      return { comps: e.comps, x: e[basis].map((v) => Math.max(0, finite(v) || 0)), unit: (basis === "mass" ? e.mu : e.nu) || "",
        basis, both: !!(e.mass && e.mole), src: e };
    }
    const all = fwAll(tab), a = all && all.v ? all.v[name] : null;
    if (Array.isArray(a)) return { comps: all.comps, x: a.map((v) => Math.max(0, finite(v) || 0)), unit: all.unit || "",
      basis: all.basis === "mole" ? "mole" : "mass", both: false, src: all };
    return null;
  }

  // ------------------------------------------------------------------ words
  /** A fraction as Aspen shows one: 0.8925; under 1e-4 as 2.3e-5. */
  const fracTxt = (x) => (x === 0 ? "0" : x >= 1e-4 ? x.toFixed(4) : x.toExponential(1));
  /** A share in percent, three digits: 89.3 · 10.7 · 0.42; under 0.1, <0.1. */
  const pctTxt = (x) => { const p = x * 100; return p >= 0.1 ? String(Number(p.toPrecision(3))) : "<0.1"; };
  const pctUnit = (basis) => t(basis === "mole" ? "cp_molpct" : "cp_wtpct");

  /** The rows: the components with some, the largest first (N_ROWS at most: the rest as one, "other"), and
   *  those with none. */
  function rowsOf(f) {
    const tot = f.x.reduce((s, v) => s + v, 0), tiny = tot * 1e-12;
    const some = f.x.map((v, i) => [v, i]).filter(([v]) => v > tiny).sort((a, b) => b[0] - a[0] || a[1] - b[1]);
    const zero = f.x.map((v, i) => [v, i]).filter(([v]) => !(v > tiny)).map(([, i]) => f.comps[i]);
    const top = some.length > N_ROWS ? some.slice(0, N_ROWS - 1) : some, rest = some.slice(top.length);
    return { tot, top: top.map(([v, i]) => ({ name: f.comps[i], v })),
      rest: rest.length ? { names: rest.map(([, i]) => f.comps[i]), v: rest.reduce((s, [v]) => s + v, 0) } : null, zero };
  }

  // ------------------------------------------------------------------ the inspector
  const qPref = () => (prefGet("wb.cp.q") === "frac" ? "frac" : "flow");
  const bPref = () => (prefGet("wb.cp.b") === "mole" ? "mole" : "mass");

  function cpSection(tab, tg, old) {
    if (!tg || tg.kind !== "stream" || !hasFlow(tab, tg.name)) return null;
    const e = entryOf(tab, tg.name), sc = sessOf(tab).stream_comp, busy = !!(sc && sc.busy);
    const q = qPref(), f = flowsOf(tab, tg.name, bPref());
    // (rows read before a run, until read again; the flow layer's while it reads again)
    const fresh = !!f && (f.src === e ? !e.stale : !f.src.reading);
    if (e && !e.reading && !(e.mass || e.mole) && !f) return { sig: "none", html: "" };   // (no results: no section)
    const sig = JSON.stringify([I18N.lang, tg.name, q, f && f.basis, f && f.x, f && f.unit, e && [e.reading, e.stale, e.partial], busy, old, more]);
    const seg = (key, val, label, on, dis) => `<button class="lp-g${on ? " on" : ""}" data-cp="${key}:${val}"${dis ? ` disabled title="${esc(dis)}"` : ""}>${esc(label)}</button>`;
    const tag = old ? ` <span class="oldtag" title="${esc(t("tip_stale"))}">${esc(t("stale_tag"))}</span>` : "";
    const sw = f ? `<span class="cp-sw"><span class="lp-seg" role="group">${seg("q", "flow", t("cp_flow"), q === "flow")}${seg("q", "frac", t("cp_frac"), q === "frac")}</span>`
      + `<span class="lp-seg" role="group">${seg("b", "mass", t("cp_mass"), f.basis === "mass", f.basis === "mole" && !f.both ? t("fw_mole_note") : "")}`
      + `${seg("b", "mole", t("cp_mole"), f.basis === "mole", f.basis === "mass" && !f.both ? t("cp_no_mole") : "")}</span></span>` : "";
    const head = `<div class="sec cp-h" title="${esc([t("tip_cp"), e && e.partial ? t("cp_partial") : ""].filter(Boolean).join("\n"))}">`
      + `<span class="cp-t">${esc(t("cp_head"))}${tag}</span>${sw}</div>`;
    if (!f) {
      const w = busy ? t("fw_busy") : t("cp_reading");
      return { sig, html: `${head}<div class="hint cp-wait">${esc(w)}</div>` };
    }
    // one grid for every row (style.css .cp-rows): the name, the bar's track, the value, its unit
    const R = rowsOf(f), unit = q === "flow" ? f.unit : "";
    const val = (v) => (q === "flow" ? fwFmt(v) : fracTxt(R.tot > 0 ? v / R.tot : 0));
    const tip = (name, v) => `${name}\n${fwFmt(v)}${f.unit ? ` ${f.unit}` : ""} · ${fracTxt(R.tot > 0 ? v / R.tot : 0)}`;
    const row = (name, v, cls, title) => `<div class="cp-r${cls ? ` ${cls}` : ""}" title="${esc(title || tip(name, v))}">`
      + `<span class="cp-n">${esc(name)}</span><span class="cp-bar"><i style="width:${R.tot > 0 ? Math.max(0.5, Math.round((v / R.tot) * 1000) / 10) : 0}%"></i></span>`
      + `<span class="cp-v">${esc(val(v))}</span>${unit ? `<span class="cp-u">${esc(unit)}</span>` : ""}</div>`;
    const all = R.top.map((r) => row(r.name, r.v));
    if (R.rest) all.push(row(t("cp_other_n", R.rest.names.length), R.rest.v, "cp-o", `${R.rest.names.join(", ")}\n${tip(t("cp_other"), R.rest.v).split("\n")[1]}`));
    // folded: the first N_FOLD rows (one more is shown rather than a line to fold it), the rest counted
    const fold = all.length > N_FOLD + 1, shut = fold && !more;
    const hid = shut ? R.top.slice(N_FOLD).map((r) => r.name).concat(R.rest ? R.rest.names : []) : [];
    let body = (shut ? all.slice(0, N_FOLD) : all).join("");
    const foot = [];
    if (fold) foot.push(`<button class="flat cp-more" data-cp="more:${shut ? 1 : 0}" aria-expanded="${!shut}"${shut ? ` title="${esc(hid.join(", "))}"` : ""}>`
      + `${esc(shut ? t("cp_more_n", hid.length) : t("cp_less"))}${icon(shut ? "chevron-down" : "chevron-up")}</button>`);
    if (R.zero.length) foot.push(`<span class="cp-z" title="${esc(R.zero.join(", "))}">${esc(t(R.zero.length === 1 ? "cp_zero1" : "cp_zero", R.zero.length))}</span>`);
    if (foot.length) body += `<div class="cp-f">${foot.join("")}</div>`;
    if (!R.top.length) body = `<div class="hint cp-wait">${esc(t("cp_empty"))}</div>`;
    return { sig, html: `${head}<div class="cp-rows${unit ? "" : " nou"}${fresh ? "" : " old"}">${body}</div>` };
  }

  /** A switch in the section pressed ("q:frac", "b:mole"; app-inspector.js wireInspector): this viewer's
   *  choice kept, the rows drawn again; "more:1" / "more:0" unfolds or folds the rows (this page's). */
  function cpSwitch(pane, tab, spec) {
    const [k, v] = String(spec).split(":");
    if (k === "more") more = v === "1";
    else prefSet(k === "q" ? "wb.cp.q" : "wb.cp.b", v);
    pane.sigs.irows = null;
    renderInspector(pane, tab, sessOf(tab));
  }

  // ------------------------------------------------------------------ the hover card
  /** The hover card's line: the largest shares (N_PEEK at most, as many as one line of the card holds:
   *  PEEK_CH characters), each with its segment's colour while the flow layer shows the composition;
   *  faded while read before a run (and asked again). {sig, html}, or null; ask: whether a missing or
   *  stale read is asked for. */
  function peekLine(tab, name, ask) {
    if (!hasFlow(tab, name)) return null;
    if (ask) cpAsk(tab, name);
    const f = flowsOf(tab, name, "mass");
    if (!f) return null;
    const R = rowsOf(f);
    if (!(R.tot > 0)) return null;
    const key = fwMixKey ? fwMixKey(tab) : null, old = f.src === entryOf(tab, name) ? !!f.src.stale : !!f.src.reading;
    const sig = JSON.stringify([I18N.lang, name, f.basis, f.x, old, key && R.top.slice(0, N_PEEK).map((r) => key[r.name])]);
    const list = [], room = PEEK_CH - (key ? 4 : 0);
    let used = 0;
    for (const r of R.top.slice(0, N_PEEK)) {
      const w = `${r.name} ${pctTxt(r.v / R.tot)}`;
      if (list.length && used + w.length + 3 > room) break;
      used += w.length + (list.length ? 3 : 0);
      const k = key ? key[r.name] : undefined;
      list.push(`${k === undefined ? "" : `<i class="pk-sw c${k}"></i>`}${esc(w)}`);
    }
    if (R.top.length > list.length || R.rest) list.push("…");
    return { sig, html: `<div class="pk-was pk-cp${old ? " old" : ""}"><span class="pk-cpu">${esc(pctUnit(f.basis))}</span>${list.join(" · ")}</div>` };
  }
  const cpPeek = (tab, name) => peekLine(tab, name, true);
  const cpPeekSig = (tab, name) => { const l = peekLine(tab, name, false); return l ? l.sig : null; };

  // ------------------------------------------------------------------ the Values layer's line
  const vcKey = (tab) => `wb.vc.${modelKey(tab)}`;
  /** This model's line: {q: "flow" | "frac", c: component}, or null (none). */
  function vcOf(tab) {
    const m = /^(flow|frac):(.+)$/.exec(prefGet(vcKey(tab)) || "");
    return m && compsOf(tab).includes(m[2]) ? { q: m[1], c: m[2] } : null;
  }
  const cpWantsAll = (tab) => !!prefs().values && !!vcOf(tab);

  function cpVals(tab, values) {
    const vc = cpWantsAll(tab) ? vcOf(tab) : null, all = vc ? fwAll(tab) : null;
    if (!all || !all.v) return values;
    const i = all.comps.indexOf(vc.c);
    if (i < 0) return values;
    const out = Object.assign({}, values || {});
    Object.entries(all.v).forEach(([n, a]) => {
      if (!Array.isArray(a) || !(out[n] && Object.keys(out[n]).length)) return;   // (streams the layer shows values of)
      const x = Math.max(0, finite(a[i]) || 0), tot = a.reduce((s, v) => s + Math.max(0, finite(v) || 0), 0);
      if (!(x > tot * 1e-12)) return;                                               // (none of it here: no line)
      const text = vc.q === "flow" ? `${vc.c} ${fwFmt(x)}${all.unit ? ` ${all.unit}` : ""}`
        : `${vc.c} ${tot > 0 ? pctTxt(x / tot) : "0"} ${pctUnit(all.basis)}`;
      out[n] = Object.assign({}, out[n], { c: [x, all.unit || "", text] });
    });
    return out;
  }

  function choose(pane, tab, v) {
    prefSet(vcKey(tab), v);
    const rec = wb.recs.get(tab.id);
    if (rec) fwAsk(tab);
    pane.sigs = {};
    renderPane(pane);
  }
  function menuItems(pane, tab) {
    const vc = vcOf(tab), cs = compsOf(tab), q = vc ? vc.q : "flow";
    const it = (label, c) => ({ label, check: c === (vc ? vc.c : null), run: () => choose(pane, tab, c ? `${q}:${c}` : null) });
    const out = [{ html: `<div class="fw-w">${esc(t("vc_by"))}</div>` }, it(t("vc_none"), null)];
    if (cs.length) out.push({ sep: true }, ...cs.slice(0, N_COMP).map((x) => it(x, x)));
    if (cs.length > N_COMP) out.push({ label: t("fw_more"), icon: "more", sub: cs.slice(N_COMP).map((x) => it(x, x)) });
    if (vc) out.push({ sep: true },
      { label: t("cp_flow"), check: q === "flow", run: () => choose(pane, tab, `flow:${vc.c}`) },
      { label: t("cp_frac"), check: q === "frac", run: () => choose(pane, tab, `frac:${vc.c}`) });
    const all = vc ? fwAll(tab) : null;
    if (vc && (!all || all.reading)) out.push({ sep: true }, { html: `<div class="fw-note">${esc(t(all && all.busy ? "fw_busy" : "fw_reading"))}</div>` });
    return out;
  }
  function cpTools(pane, tab) {
    const vb = pane.q('.fs-tools [data-a="values"]');
    if (!vb) return;
    let pk = pane.q('.fs-tools [data-a="values_pick"]');
    if (!pk) {
      vb.insertAdjacentHTML("afterend", `<button data-a="values_pick" class="hidden" aria-haspopup="menu">${icon("chevron-down")}</button>`);
      pk = pane.q('.fs-tools [data-a="values_pick"]');
      pk.addEventListener("click", (ev) => { const t2 = tabOf(pane.tabId); if (t2) toggleMenu(vb, () => menuItems(pane, t2), ev); });
    }
    const on = !!prefs().values, vc = on ? vcOf(tab) : null;
    const tip = vc ? t("tip_vc_on", vc.c, t(vc.q === "flow" ? "cp_flow" : "cp_frac")) : t("tip_vc");
    const sig = JSON.stringify([on, tip]);
    if (pk.dataset.sig === sig) return;
    pk.dataset.sig = sig;
    pk.classList.toggle("hidden", !on);
    pk.classList.toggle("on", on);
    vb.classList.toggle("has-pick", on);
    pk.title = tip;
  }

  Object.assign(WBA, { cpAsk, cpPeek, cpPeekSig, cpSection, cpSwitch, cpTools, cpVals, cpWantsAll });
})();
