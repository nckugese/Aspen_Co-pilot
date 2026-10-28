/* Result tags: after an approved proposal's run -- or, in learning mode,
 * after the user's own Run simulation -- the flowsheet tags what the run moved, from what the server
 * measured before and after it (tab.run.effects, sess.effects; feature effects):
 *
 *   PRODUCT  ◎ ETHANOL 11.19 → 11.42 t/h        (the proposal's goal first: its watch[0])
 *            ETHANOL 90.1 → 89.3 wt%
 *
 * At most 3 objects, at most 2 lines each ("+N" for the rest), the goal's object first; every line's
 * tooltip says what it is and where the numbers come from (the goal's starts with fx_goal "Goal"; a run that
 * took inputs from outside the proposal says the result is not the proposal's alone), and a tag's
 * the results left out (fx_more "N more results moved"). New tags bring the first one's object into view with
 * its tag (zoomed in where names do not read) and ring it once. A result of an object the proposal
 * made has no value before: its value after alone. A fraction shows as a percentage: wt% on a mass basis,
 * mol% on a mole one (a model without mass fractions: the server read the mole twin). Learning mode
 * off: the proposal's goal alone, and nothing without one; the user's own runs are tagged only in
 * learning mode. A goal that moved within the server's tolerance (fxSame) reads as unchanged:
 * "◎ Ethanol in the vent 3.64 kg/hr · unchanged", its two numbers in the tooltip. Gone once the model's inputs
 * change or it runs again (the session's journal), with Esc (this run's tags, remembered by run id in
 * this viewer's localStorage), or for good with ⋯ › "Result tags" (pref wb.fx); one tag alone with its ×
 * (shown on hover) until the next run -- ⋯ › "Show closed tags" brings this run's back (wb.fx.hide). A
 * tag dragged away stays where it was put, a thin line back to its object, for this model and that
 * result while the window lasts (sessionStorage wb.fx.moved); a drag is not a click. Tags are glass
 * over the drawing (flowsheet.js fxLayer): never in a figure.
 *
 * A line clicked pins its causal path: the streams from what was changed to the
 * result in the accent, by them at most 2 measured words ("new 4.6 kg/hr", "total flow +4.6 kg/hr") and
 * the AI's one ("✦ ethanol dissolves in the wash", proposal.explain). It stays, its tag tinted with its × showing,
 * until the ×, the same line again, Esc or a click on the flowsheet's empty background closes it;
 * another line clicked takes its place. Pointing at a line lights nothing. The line's tooltip: the
 * AI's sentence, else how the path was found.
 *
 *   fxView(pane, tab)      FS.render's v.effects for the tab, or null
 *   fxEsc(pane)            Esc: a pinned path closed, else this run's tags put away (true when either)
 *   fxMenuItem(pane)       ⋯'s "Result tags" item (null without the feature)
 *   fxSame(path, u, b, a)  the server's thresholds (catalog.notable): b -> a too small to tell
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { feature, isObj, learning, objOfPath, prefGet, prefSet, sessOf, t, tabOf, wb } = WBA;
  const { pvWord, renderEdges, renderPane } = WBA.later;

  const OBJ_MAX = 3, LINE_MAX = 2, ESC_KEY = "wb.fx.esc", ESC_MAX = 20, HIDE_KEY = "wb.fx.hide", HIDE_MAX = 60, MOVE_KEY = "wb.fx.moved";
  const COMP = /\\(MASS|MOLE)(FRAC|FLOW)\\MIXED\\([^\\]+)$/i;
  const prefOff = () => prefGet("wb.fx") === "off";

  // ------------------------------------------------------------------ the thresholds (tools/notable.py)
  const NOTABLE = { temp_abs_K: 0.5, rel: 0.005, frac_abs: 0.001 };
  const limits = () => Object.assign({}, NOTABLE, isObj(wb.state && wb.state.catalog && wb.state.catalog.notable) ? wb.state.catalog.notable : {});
  const GAUGE = { psig: 14.6959, barg: 1.01325, kpag: 101.325, mpag: 0.101325, atmg: 1, "kg/sqcmg": 1.03323, mbarg: 1013.25 };
  const TEMP_U = /^(DEG)?[KCFR]$/i, F_U = /^(DEG)?[FR]$/i;
  /** frac | temp | pres | other, by the field's name, else its unit (notable.kind's order). */
  function kindOf(path, u) {
    const p = String(path || "").toUpperCase(), seg = p.split("\\").filter(Boolean), i = seg.indexOf("OUTPUT"), f = i >= 0 && seg[i + 1] ? seg[i + 1] : seg[seg.length - 1] || "";
    if (/FRAC/.test(f)) return "frac";
    if (/TEMP/.test(f)) return "temp";
    if (/PRES/.test(f)) return "pres";
    if (/DUTY|FLOW|FLMX/.test(f) || /^(QCALC|QNET|NET_DUTY|HDUTY)$/.test(f)) return "other";
    const uu = String(u || "").trim();
    if (TEMP_U.test(uu)) return "temp";
    if (Object.prototype.hasOwnProperty.call(GAUGE, uu.toLowerCase())) return "pres";
    return "other";
  }
  /** b -> a too small to tell (both numbers): a temperature by 0.5 K, a pressure's absolute value and
   *  anything else by 0.5 %, a fraction by 0.001 -- the server's catalog.notable. */
  function fxSame(path, u, b, a) {
    const L = limits(), k = kindOf(path, u), d = Math.abs(a - b);
    if (k === "frac") return d < L.frac_abs - 1e-12;
    if (k === "temp") return d / (F_U.test(String(u || "").trim()) ? 1.8 : 1) < L.temp_abs_K - 1e-12;
    const g = k === "pres" ? GAUGE[String(u || "").trim().toLowerCase()] || 0 : 0;
    const big = Math.max(Math.abs(a + g), Math.abs(b + g));
    return !(big > 0) || d / big < L.rel - 1e-12;
  }

  // ------------------------------------------------------------------ which effects show
  function escaped() {
    try { const v = JSON.parse(localStorage.getItem(ESC_KEY) || "[]"); return Array.isArray(v) ? v : []; } catch (e) { return []; }
  }
  function putAway(run) {
    try {
      const v = escaped().filter((x) => x !== run);
      v.push(run);
      localStorage.setItem(ESC_KEY, JSON.stringify(v.slice(-ESC_MAX)));
    } catch (e) { /* (no storage: the tags stay until the next input or run) */ }
  }
  /** Tags closed with their × ("run|key"), this viewer's: until the next run (a new run id). */
  function hidden() {
    try { const v = JSON.parse(localStorage.getItem(HIDE_KEY) || "[]"); return Array.isArray(v) ? v : []; } catch (e) { return []; }
  }
  function setHidden(v) {
    try { localStorage.setItem(HIDE_KEY, JSON.stringify(v.slice(-HIDE_MAX))); } catch (e) { /* (no storage: shown again on the next draw) */ }
  }
  const hiddenOf = (run) => hidden().filter((x) => x.startsWith(`${run}|`)).map((x) => x.slice(String(run).length + 1));
  /** Where tags were dragged: {"model|key": [dx, dy]} (drawing units), for this window's session. */
  function movedAll() {
    try { const v = JSON.parse(sessionStorage.getItem(MOVE_KEY) || "{}"); return isObj(v) ? v : {}; } catch (e) { return {}; }
  }
  const modelOf = (tab) => { const m = sessOf(tab).model; return String((isObj(m) && (m.id || m.file)) || tab.session || ""); };

  /** The effects the tab shows now: {fx, own (the user's own run)}, or null -- none, put away, or no
   *  longer the model's (an input changed since, or a later run). */
  function subject(tab) {
    if (!tab || !feature("effects") || prefOff()) return null;
    const sess = sessOf(tab);
    let fx = null, own = false;
    if (tab.kind === "proposal") {
      const run = tab.run || {}, p = isObj(tab.proposal) ? tab.proposal : {};
      if (run.status === "running" || !["applied", "partial"].includes(p.status)) return null;
      fx = run.effects;
    } else {
      if (!learning()) return null;
      fx = sess.effects;
      own = true;
    }
    if (!isObj(fx) || !Array.isArray(fx.items) || !fx.items.length) return null;
    if (fx.run && escaped().includes(fx.run)) return null;
    const j = isObj(sess.journal) ? sess.journal : null;
    if (j) {
      const r = isObj(j.run) ? j.run : null;
      if (r && typeof r.seq === "number" && typeof fx.seq === "number" && r.seq > fx.seq) return null;
      if (Number(j.last_input_t) > Number(fx.at) + 0.001) return null;
    }
    return { fx, own };
  }

  // ------------------------------------------------------------------ the words
  /** A result's word: the AI's label, a component's name for its flow or fraction, else the field. */
  function word(it, tab) {
    if (it.label) return String(it.label);
    const m = COMP.exec(String(it.path || ""));
    if (m) return m[3];
    const key = String(it.key || ""), fs = sessOf(tab).flowsheet || {};
    const b = key.startsWith("block:") ? (fs.blocks || []).find((x) => x && String(x.name).toUpperCase() === key.slice(6)) : null;
    const w = String(pvWord(it.path, b ? b.type : null, tab.session) || it.path || ""), parts = w.split(" › ");
    // (the tag hangs on its object: "B1 › Duty" reads "Duty")
    return parts.length > 1 && parts[0].toUpperCase() === key.slice(key.indexOf(":") + 1) ? parts.slice(1).join(" › ") : w;
  }
  const toNum = (x) => (typeof x === "number" ? x : x === null || x === undefined || x === "" ? NaN : Number(x));
  /** [before, after, unit] as text, with the same decimals: 4 significant digits of the larger (every
   *  whole digit), more where they would read the same, the trailing zeros both have left off;
   *  a fraction as a percentage, wt% on a mass basis, mol% on a mole one. */
  function values(it) {
    let b = toNum(it.b), a = toNum(it.a), u = it.u ? String(it.u) : "";
    if (!isFinite(a)) return [String(it.b ?? "—"), String(it.a ?? "—"), u];
    const none = it.b === null || it.b === undefined || it.b === "";   // (an object the proposal made: no value before)
    if (!none && !isFinite(b)) return [String(it.b), String(it.a), u];
    if (none) b = a;
    if (it.kind === "frac") {
      b *= 100; a *= 100;
      u = pctUnit(it);
    }
    const big = Math.max(Math.abs(a), Math.abs(b)) || 1;
    let dec = Math.max(0, 3 - Math.floor(Math.log10(big)));    // (4 significant digits of the larger, both alike)
    while (dec < 10 && b !== a && b.toFixed(dec) === a.toFixed(dec)) dec++;
    while (dec > 0 && /0$/.test(b.toFixed(dec)) && /0$/.test(a.toFixed(dec))) dec--;   // (90.10 → 89.30 reads 90.1 → 89.3)
    const show = (x) => x.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
    return [none ? null : show(b), show(a), u];
  }
  const pctUnit = (it) => (/\\MASSFRAC\\/i.test(it.path || "") ? "wt%" : /\\MOLEFRAC\\/i.test(it.path || "") ? "mol%" : "%");
  /** A result that did not move past the tolerance: its value after, 3 significant digits (every
   *  whole digit), and its unit -- [text, unit]. */
  function settled(it) {
    let a = toNum(it.a), u = it.u ? String(it.u) : "";
    if (it.kind === "frac") { a *= 100; u = pctUnit(it); }
    const dec = Math.max(0, 2 - Math.floor(Math.log10(Math.abs(a) || 1)));
    return [a.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: dec }), u];
  }
  /** A goal's b -> a within the server's tolerance (both numbers there): it reads as unchanged. (The
   *  other results come only when they moved past it: notable.py; a goal comes whatever it did.) */
  function unmoved(it) {
    const b = toNum(it.b), a = toNum(it.a);
    return !!it.goal && it.b !== null && it.b !== undefined && it.b !== "" && isFinite(a) && isFinite(b) && fxSame(it.path, it.u, b, a);
  }

  // ------------------------------------------------------------------ the causal path
  // Each line's path from what was changed to its result: the AI's ``via`` when every step of it is
  // a stream of the flowsheet now; else the flowsheet's own connections -- the shortest way along
  // the streams from the earliest changed object that reaches the result, and the way a second one
  // joins it (at most 2 starts, SEG_MAX streams) --; no way at all: the change and the result padded.
  // Its words: at most 2 measured (the streams on it that moved most: tab.run.effects.seg, the result's
  // own left out, one that repeats the last one's change left out) and the AI's one (``words``).
  const SEG_MAX = 12, SAME = 0.02;
  const twin = (p) => String(p || "").toUpperCase().replace(/\\MOLE(FRAC|FLOW)\\/g, "\\MASS$1\\");
  /** The flowsheet as a directed graph: a block to the streams leaving it, a stream to the block it
   *  enters; ``key`` the key as drawn ("block:B1") for any spelling of it. */
  function graphOf(fs) {
    const out = new Map(), canon = new Map();
    const up = (k) => { const i = k.indexOf(":"); return `${k.slice(0, i)}:${k.slice(i + 1).toUpperCase()}`; };
    const key = (k) => canon.get(up(String(k || ""))) || null;
    (fs.blocks || []).forEach((b) => { if (b && b.name != null) canon.set(up(`block:${b.name}`), `block:${b.name}`); });
    (fs.streams || []).forEach((s) => { if (s && s.name != null) canon.set(up(`stream:${s.name}`), `stream:${s.name}`); });
    const add = (a, b) => { if (!out.has(a)) out.set(a, []); out.get(a).push(b); };
    (fs.streams || []).forEach((s) => {
      if (!s || s.name == null) return;
      const k = `stream:${s.name}`, f = s.from ? key(`block:${s.from}`) : null, t = s.to ? key(`block:${s.to}`) : null;
      if (f) add(f, k);
      if (t) add(k, t);
    });
    return { out, key };
  }
  /** The shortest way from ``a`` to ``b`` along the streams' direction (each object once: a recycle
   *  ends it), or null. */
  function bfs(G, a, b) {
    if (a === b) return [a];
    const prev = new Map([[a, null]]), q = [a];
    for (let h = 0; h < q.length; h++) {
      for (const n of G.out.get(q[h]) || []) {
        if (prev.has(n)) continue;
        prev.set(n, q[h]);
        if (n === b) {
          const p = [];
          for (let x = n; x != null; x = prev.get(x)) p.unshift(x);
          return p;
        }
        q.push(n);
      }
    }
    return null;
  }
  /** The AI's ``via`` as the flowsheet's objects, when each step of it follows a stream (a block to a
   *  block: the stream between; a stream to a stream: the block between); else null. */
  function viaPath(G, via) {
    const nodes = (Array.isArray(via) ? via : []).map((n) => G.key(`block:${n}`) || G.key(`stream:${n}`));
    if (nodes.length < 2 || nodes.some((k) => !k)) return null;
    const p = [nodes[0]];
    for (let i = 1; i < nodes.length; i++) {
      const a = nodes[i - 1], b = nodes[i], next = G.out.get(a) || [];
      if (!next.includes(b)) {
        const mid = next.find((m) => (G.out.get(m) || []).includes(b));
        if (!mid) return null;
        p.push(mid);
      }
      p.push(b);
    }
    return p;
  }
  const UNIT_T = { C: "°C", F: "°F", K: "K", R: "°R" };
  /** A measured change as words: "+4.6 kg/hr" (3 significant digits). */
  function qty(x, u, signed) {
    const a = Number(Math.abs(x).toPrecision(3)).toLocaleString("en-US", { maximumFractionDigits: 6 });
    return (signed ? (x < 0 ? "−" : "+") : "") + a + (u ? ` ${u}` : "");
  }
  /** The measured words of a path: the streams on it that moved most (a new one: "new 4.6 kg/hr"; its
   *  total flow: "total flow +4.6 kg/hr"; no flow change, its temperature: "+3.2 °C"), at most 2, the
   *  result's own and a repeat of the last one's change (within SAME) left out. */
  function measured(fx, streams, dst) {
    const seg = isObj(fx.seg) ? fx.seg : {}, cand = [];
    streams.forEach((k, at) => {
      if (k === dst) return;
      const name = k.slice(7), row = seg[name] || seg[name.toUpperCase()];
      if (!isObj(row)) return;
      const u = isObj(row.u) ? row.u : {};
      if (Array.isArray(row.f)) {
        const b = toNum(row.f[0]), a = toNum(row.f[1]);
        if (!isFinite(a)) return;
        if (row.new || !isFinite(b)) cand.push({ key: k, at, r: 1, d: Math.abs(a), t: t("fx_new", qty(a, u.f)) });
        else cand.push({ key: k, at, r: 1, d: Math.abs(a - b), t: t("fx_total", qty(a - b, u.f, true)) });
      } else if (Array.isArray(row.t)) {
        const b = toNum(row.t[0]), a = toNum(row.t[1]);
        if (isFinite(a) && isFinite(b)) cand.push({ key: k, at, r: 0, d: Math.abs(a - b), t: qty(a - b, UNIT_T[String(u.t || "").toUpperCase()] || u.t, true) });
      }
    });
    cand.sort((x, y) => y.r - x.r || y.d - x.d || x.at - y.at);
    const out = [];
    for (const c of cand) {
      const last = out[out.length - 1];
      if (last && last.r === c.r && Math.abs(last.d - c.d) <= SAME * Math.max(last.d, c.d)) continue;
      out.push(c);
      if (out.length === 2) break;
    }
    return out.map((c) => ({ key: c.key, t: c.t, c: "m" }));
  }
  /** Where a run's paths start: the objects it changed (effects.changed, the earliest first); a server
   *  that does not say: what the proposal's groups act on (its check). */
  function starts(G, fx, tab) {
    let src = Array.isArray(fx.changed) ? fx.changed : null;
    if (!src && tab.kind === "proposal" && tab.check && Array.isArray(tab.check.groups)) src = tab.check.groups.flatMap((g) => (g && Array.isArray(g.objs) ? g.objs : []));
    return [...new Set((src || []).map((k) => G.key(k)).filter(Boolean))];
  }
  /** A line's path: {spec: FS.cause's, how: "ai" | "flow" | "none"}, or null (nothing to show: no
   *  start known, or the result is the changed object itself). */
  function pathOf(G, fx, it, ex, srcs) {
    const dst = G.key(it.key || objOfPath(it.path) || "");
    if (!dst) return null;
    let nodes = ex ? viaPath(G, ex.via) : null, how = "ai";
    if (!nodes) {
      how = "flow";
      let main = null, more = null;
      for (const s of srcs) {
        const p = bfs(G, s, dst);
        if (!p) continue;
        if (!main) { main = p; continue; }
        const on = new Set(main), cut = p.findIndex((k) => on.has(k));
        if (cut > 0) { more = p.slice(0, cut + 1); break; }   // (a second start, up to where it joins)
      }
      if (!main) return srcs.length ? { how: "none", spec: { keys: [...new Set([...srcs.slice(0, 2), dst])], words: [] } } : null;
      nodes = main.concat(more || []);
    }
    const streams = [...new Set(nodes.filter((k) => k.startsWith("stream:")))].slice(0, SEG_MAX);
    const words = measured(fx, streams, dst);
    const w = ex && isObj(ex.words) ? Object.entries(ex.words)[0] : null, wk = w ? G.key(`block:${w[0]}`) || G.key(`stream:${w[0]}`) : null;
    if (wk && w[1]) words.push({ key: wk, t: `✦ ${w[1]}`, c: "ai" });
    return streams.length || words.length ? { how, spec: { keys: streams, words } } : null;
  }
  /** The AI's explanation of this run's result (proposal.explain, for this run only), or null. */
  function explainOf(tab, fx, it) {
    const ex = tab.kind === "proposal" && isObj(tab.proposal) ? tab.proposal.explain : null;
    if (!isObj(ex) || !fx.run || ex.run !== fx.run || !Array.isArray(ex.items)) return null;
    return ex.items.find((x) => isObj(x) && twin(x.result) === twin(it.path)) || null;
  }

  /** The run's paths on the pane: {of(item, its explanation)}, worked out once per run, flowsheet
   *  and explanation (kept on the pane); pane.fxPaths, the drawn lines' paths by "key|line", anew. */
  function paths(pane, tab, fx) {
    const fs = sessOf(tab).flowsheet || {}, ex = tab.kind === "proposal" && isObj(tab.proposal) ? tab.proposal.explain : null;
    const sig = [tab.id, fx.run, (fs.streams || []).length, (fs.blocks || []).length, JSON.stringify(ex || null),
      JSON.stringify(fx.changed || null), tab.check ? tab.check.rev : ""].join("|");
    let c = pane.fxPC;
    if (!c || c.sig !== sig) {
      const G = graphOf(fs), srcs = starts(G, fx, tab), memo = new Map();
      c = pane.fxPC = { sig, of: (it, e) => {
        const k = `${it.path}|${it.key}|${e ? 1 : 0}`;
        if (!memo.has(k)) memo.set(k, pathOf(G, fx, it, e, srcs));
        return memo.get(k);
      } };
    }
    pane.fxPaths = {};
    return c;
  }

  /** A line's path on the drawing (FS.cause), pinned: "key|line", or null for none. The path stays
   *  until it is closed -- the × on its tag, the same line again, Esc, empty flowsheet background --
   *  or another line is clicked; pointing at a line shows nothing. */
  function pin(pane, id) {
    const P = id && pane.fxPaths ? pane.fxPaths[id] : null;
    id = P ? id : null;
    if (pane.fxPin === id) return;
    pane.fxPin = id;
    pane.fxBase = P ? P.spec : null;
    pane.fxSpec = P ? pinSpec(id, P.spec) : null;
    if (pane.svg) FS.cause(pane.svg, pane.fxSpec);
  }
  /** FS.cause's spec for a pinned line: its path, its tag drawn pinned with the × that closes it. */
  const pinSpec = (id, spec) => Object.assign({}, spec, { pin: { tag: id.slice(0, id.lastIndexOf("|")), tip: t("fx_close") } });
  function release(pane) { pin(pane, null); }
  /** Drawn again: the pinned line's path follows what it is now (gone: closed). */
  function relight(pane) {
    const id = pane.fxPin, P = id ? pane.fxPaths[id] : null;
    if (id && !P) return release(pane);
    if (P && pane.fxBase !== P.spec) { pane.fxBase = P.spec; pane.fxSpec = pinSpec(id, P.spec); FS.cause(pane.svg, pane.fxSpec); }
  }
  /** The line of a result tag a click is on: the line's own text, else (the tag's padding, between
   *  its lines) the line nearest the pointer. */
  function lineAt(tag, ev) {
    const own = ev && ev.target && ev.target.closest ? ev.target.closest("[data-i]") : null;
    let tx = own && tag.contains(own) ? own : null;
    if (!tx) {
      let best = Infinity;
      tag.querySelectorAll("[data-i]").forEach((el) => {
        const r = el.getBoundingClientRect(), d = Math.abs((r.top + r.bottom) / 2 - ev.clientY);
        if (d < best) { best = d; tx = el; }
      });
    }
    return tx ? `${tag.getAttribute("data-tag")}|${tx.getAttribute("data-i")}` : null;
  }
  function wire(pane) {
    if (pane.fxWired || !pane.svg) return;
    pane.fxWired = true;
    const svg = pane.svg;
    // a press that moved (a pan) is not a click on a tag or on the background
    const still = (ev) => { const d = pane.fxDown; return !d || Math.hypot(ev.clientX - d[0], ev.clientY - d[1]) <= 5; };
    // a line clicked: its path pinned, again: closed; the ×: the pinned path closed, else the tag put
    // away until the next run; a drop: where the tag stays (the layer tells a drag from a click)
    FS.onTag(svg, (key, el, ev, part, o) => {
      if (part === "move") return keepMoved(pane, key, o);
      if (part === "x") return pinnedTag(pane) === key ? release(pane) : hideTag(pane, key);
      if (!ev) return;
      const id = lineAt(el, ev);
      if (!id) return;
      if (pane.fxPin === id) release(pane);
      else pin(pane, id);
    }, "fx");
    // a click on the flowsheet's empty background closes it (not one on a block, a stream, a tag)
    document.addEventListener("pointerdown", (ev) => { pane.fxDown = [ev.clientX, ev.clientY]; }, true);
    document.addEventListener("click", (ev) => {
      if (!pane.fxPin || !still(ev)) return;
      const el = ev.target;
      if (el === pane.svg || (el && el.classList && el.classList.contains("fs-grid") && pane.svg.contains(el))) release(pane);
    }, true);
  }

  const pinnedTag = (pane) => (pane.fxPin ? pane.fxPin.slice(0, pane.fxPin.lastIndexOf("|")) : null);
  /** A tag's × (its path not pinned): this run's tag of that object put away, until the next run. */
  function hideTag(pane, key) {
    const tab = tabOf(pane.tabId), s = tab ? subject(tab) : null;
    if (!s || !s.fx.run) return;
    setHidden(hidden().filter((x) => x !== `${s.fx.run}|${key}`).concat(`${s.fx.run}|${key}`));
    if (pinnedTag(pane) === key) release(pane);
    pane.sigs = {};
    renderPane(pane);
  }
  /** A tag dropped where the user put it: kept for this model and that result (sessionStorage). */
  function keepMoved(pane, key, o) {
    const tab = tabOf(pane.tabId);
    if (!tab || !Array.isArray(o)) return;
    const all = movedAll(), k = `${modelOf(tab)}|${key}`;
    if (!o[0] && !o[1]) delete all[k];
    else all[k] = o;
    try { sessionStorage.setItem(MOVE_KEY, JSON.stringify(all)); } catch (e) { /* (kept in the drawing until the next draw) */ }
  }

  /** FS.render's v.effects: {tags: [{key, lines, tips (a line's tooltip each), tip}], moved ({key:
   *  [dx, dy]}: where the user dragged them), xtip (a tag's ×)}, or null; a
   *  lit path whose tags are gone goes with them. */
  function fxView(pane, tab) {
    const v = view(pane, tab);
    if (!v && pane && pane.fxPin) release(pane);
    // (each tab keeps its own view: one left pinned there while another tab was shown goes now)
    if (pane && pane.svg && !pane.fxPin && FS.cause(pane.svg)) FS.cause(pane.svg, null);
    return v;
  }
  function view(pane, tab) {
    const s = subject(tab);
    if (!s) return null;
    const full = s.own || learning();
    const items = s.fx.items.filter((it) => isObj(it) && (full || it.goal));
    if (!items.length) return null;
    const by = new Map();
    items.forEach((it) => {
      const k = it.key || objOfPath(it.path);
      if (!k) return;
      if (!by.has(k)) by.set(k, []);
      by.get(k).push(it);
    });
    const off = new Set(s.fx.run ? hiddenOf(s.fx.run) : []);   // (closed with their ×, this run)
    const objs = [...by].filter(([k]) => !off.has(k)).slice(0, OBJ_MAX);
    const shown = objs.reduce((n, [, list]) => n + Math.min(list.length, LINE_MAX), 0);
    const rest = full ? items.length - shown + (Number(s.fx.more) || 0) : 0;
    const joint = !s.own && !!s.fx.joint_outside;
    // (every tooltip ends alike: the joint run's caveat, then the results left out)
    const tail = (joint ? [t("fx_tip_joint")] : []).concat(rest > 0 ? [t("fx_more", rest)] : []);
    if (!objs.length) { if (pane && pane.fxPin) release(pane); return null; }
    const host = pane || {}, P = paths(host, tab, s.fx), owner = `${tab.id}|${s.fx.run}`;
    if (host.fxOwner !== owner) {                      // (another tab's or run's tags: a lit path goes)
      if (pane && pane.fxPin) release(pane);
      host.fxOwner = owner;
    }
    const tags = objs.map(([key, list]) => {
      const lines = [], tips = [], obj = key.slice(key.indexOf(":") + 1);   // (the tooltip names the object: a tag sits by it, not on it)
      const lit = [];                                  // (each line's path)
      list.forEach((it, i) => {
        const w = word(it, tab), [b, a, u] = values(it), unit = u ? ` ${u}` : "", ow = `${obj} · ${w}`, same = unmoved(it);
        const ex = s.own ? null : explainOf(tab, s.fx, it), path = i < LINE_MAX ? P.of(it, ex) : null;
        // one sentence and where it comes from: the AI's (its own words, no number), else the template
        // -- the path from the flowsheet's connections, or none between the change and the result;
        // within the tolerance: unchanged, its two numbers said
        const say = ex && ex.text ? `✦ ${ex.text}\n${t("fx_src_ai")}`
          : same ? t(s.own ? "fx_tip_same_run" : "fx_tip_same", ow, `${b}${unit}`, `${a}${unit}`)
          : b === null ? t("fx_tip_new", ow, `${a}${unit}`)
            : path && path.how === "flow" ? t(s.own ? "fx_tip_derived_run" : "fx_tip_derived", ow, `${b}${unit}`, `${a}${unit}`)
              : t(s.own ? "fx_tip_run" : "fx_tip_meas", ow, `${b}${unit}`, `${a}${unit}`);
        tips.push((it.goal ? `${t("fx_goal")} · ` : "") + say + (path && path.how === "none" ? `\n${t("fx_no_path")}` : ""));
        if (i >= LINE_MAX) return;
        lit.push(path);
        const one = same ? settled(it) : null;     // ("Ethanol in the vent 3.64 kg/hr · unchanged", not two numbers that read alike)
        lines.push([...(it.goal ? [{ t: "◎ ", c: "m" }] : []), { t: `${w} `, c: "" },
          ...(one ? [{ t: `${one[0]}${one[1] ? ` ${one[1]}` : ""}`, c: "n" }, { t: ` · ${t("fx_same")}`, c: "s" }]
            : [...(b === null ? [] : [{ t: b, c: "o" }, { t: " → ", c: "" }]), { t: `${a}${unit}`, c: "n" }])]);
      });
      if (list.length > LINE_MAX) lines[LINE_MAX - 1].push({ t: `  ${t("pv_more", list.length - LINE_MAX)}`, c: "" });
      lit.forEach((p, i) => { if (p) host.fxPaths[`${key}|${i}`] = p; });
      // a line's own tooltip; the last one's also lists the results its "+N" stands for
      const lineTips = lines.map((_, i) => (i === lines.length - 1 ? tips.slice(i) : [tips[i]])
        .concat(lit[i] ? [t("fx_tip_path")] : [], tail).join("\n"));
      return { key, lines, tips: lineTips, tip: tips.concat(tail).join("\n") };
    });
    if (pane && pane.svg) { wire(pane); relight(pane); }
    const at = `${tab.id}|${s.fx.run}|${full}`;
    if (pane && wb.pane === pane && pane.fxAt !== at) {   // (new tags: the first brought into view, once)
      pane.fxAt = at;
      requestAnimationFrame(() => look(pane, tab, tags[0].key, at));
    }
    const mv = movedAll(), mk = modelOf(tab), moved = {};
    tags.forEach((tg) => { const o = mv[`${mk}|${tg.key}`]; if (Array.isArray(o) && o.length === 2 && o.every(isFinite)) moved[tg.key] = o; });
    return { tags, run: s.fx.run, moved, xtip: t("fx_hide") };
  }
  /** The first tag's object (the goal's, where there is one): zoomed in where names do not read,
   *  brought into the free area with its tag, ringed once -- as a group's pause does (app-group.js). */
  function look(pane, tab, key, at) {
    if (wb.pane !== pane || pane.tabId !== tab.id) return;
    const fs = sessOf(tab).flowsheet || {}, i = key.indexOf(":"), kind = key.slice(0, i), name = key.slice(i + 1).toUpperCase();
    const list = kind === "block" ? fs.blocks : kind === "stream" ? fs.streams : null;
    const hit = (Array.isArray(list) ? list : []).find((b) => b && String(b.name).toUpperCase() === name);
    if (!hit) return;
    const tg = { kind, name: String(hit.name) };
    FS.readable(pane.svg, tg);
    const r = FS.reveal(pane.svg, tg, { pad: FS.RING_ROOM, tag: true });
    if (!r) { if (pane.fxAt === at) pane.fxAt = null; return; }   // (no view yet: the next draw tries again)
    renderEdges(pane);
    FS.ping(pane.svg, tg);
  }

  /** Esc: the tab's result tags put away for this run (true when some were drawn). */
  function fxEsc(pane) {
    if (pane && pane.fxPin) { release(pane); return true; }   // (a pinned path first)
    const tab = pane && tabOf(pane.tabId), v = tab ? fxView(pane, tab) : null;
    if (!v || !v.run) return false;
    putAway(v.run);
    pane.sigs = {};
    renderPane(pane);
    return true;
  }

  /** ⋯'s "Result tags": the result tags on or off for good (this viewer); after it, while this run has
   *  tags closed with their ×, "Show closed tags (N)" brings them back. A list of items, or null. */
  function fxMenuItem(pane) {
    if (!feature("effects")) return null;
    const on = !prefOff(), redraw = () => { pane.sigs = {}; renderPane(pane); };
    const items = [{ label: t("pref_fx"), icon: "eye", check: on, tip: t("tip_pref_fx"),
                     run: () => { prefSet("wb.fx", on ? "off" : null); redraw(); } }];
    const tab = on && pane ? tabOf(pane.tabId) : null, s = tab ? subject(tab) : null, run = s && s.fx.run;
    const n = run ? hiddenOf(run).length : 0;
    if (n) items.push({ label: t("fx_show_hidden", n), icon: "eye", tip: t("tip_fx_show_hidden"),
                        run: () => { setHidden(hidden().filter((x) => !x.startsWith(`${run}|`))); redraw(); } });
    return items;
  }

  Object.assign(WBA, { fxEsc, fxMenuItem, fxSame, fxView });
})();
