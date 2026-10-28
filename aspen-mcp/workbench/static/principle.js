/* A principle card (learning mode): the idea behind a group of steps, from the
 * package's own small library (docs/principles/<key>.md, read by window.py's Api.principle) --
 * never Aspen, never the AI's words (the group's why is on its own line already).
 *
 * Only in learning mode, a "Principle" chip on two places: a group's line on the proposal card and
 * the group card's first line. A group has a chip when it, or a step of it that changes the
 * model, carries a principle key the library lists (catalog.principles), or else when the rules
 * table (catalog.principle_rules, docs/principles/rules.md) finds one from the type of a block
 * and the field a step sets -- nothing else; such a chip says so in its tooltip.
 *
 *   Absorption factor                                            ✕
 *   How well the solvent takes up the solute ... designs often take 1.2 to 2.
 *              A = L / (K·V)
 *   L solvent molar flow · V gas molar flow · K = y/x the solute's vapour-liquid ratio
 *   Related  Henry's law  Stages and separation
 *   Source  Seader, Henley & Roper, Separation Process Principles, 3rd ed., Ch. 6
 *
 * One card at a time, a plate beside its chip, clear of the card the chip is on. A related key
 * shows its card in the same place (‹ Back returns). Closed by Esc, ✕, a press outside, another
 * tab, the group card moving to the next group, or learning mode turned off (the chip gone).
 * Feature-detected: catalog.features principles and the window's Api.principle.
 *
 *   WBPN.on()                     learning mode, the server's library and the window's Api
 *   WBPN.of(g, rows, tab)         {keys, rule} the chip of a group: its keys, else the rules' for
 *                                 the fields its rows set (a check's set / sweep rows, a pause's rows)
 *   WBPN.rows(tab, n)             a check's rows of group n
 *   WBPN.chip(at, of)             the chip's HTML ("" none); at: where it is, unique on the page
 *   WBPN.close(back)              close the card; whether one was open
 *   WBPN.sync()                   a new state or another tab: the card follows its chip, or closes
 */
(function () {
  "use strict";
  const WBPN = (window.WBPN = {});
  const { esc, feature, icon, isObj, learning, popover, t, zh } = WBA;
  const cat = () => (window.wb && wb.state && isObj(wb.state.catalog) ? wb.state.catalog : {});
  const W = 340, M = 8, GAP = 8;
  const KEY_RE = /^[a-z0-9_]+$/;

  function apiFn() {
    const a = window.pywebview && window.pywebview.api;
    return a && typeof a.principle === "function" ? (k) => Promise.resolve().then(() => a.principle(k)) : null;
  }
  WBPN.on = () => learning() && feature("principles") && !!apiFn();

  /** The library's index: key -> title {en, zh}. */
  function lib() {
    const out = new Map();
    for (const e of Array.isArray(cat().principles) ? cat().principles : []) {
      if (isObj(e) && typeof e.key === "string" && KEY_RE.test(e.key)) out.set(e.key, isObj(e.title) ? e.title : {});
    }
    return out;
  }
  const titleOf = (key, L) => { const tt = (L || lib()).get(key) || {}; return (zh() ? tt.zh : tt.en) || tt.en || key; };

  // ------------------------------------------------------------------ which keys a group has
  /** Block name (upper case) -> type: the tab's session's flowsheet, then the blocks its program places. */
  function types(tab) {
    const out = new Map(), s = window.wb && wb.state;
    const fs = (s && s.sessions && tab && s.sessions[tab.session] && s.sessions[tab.session].flowsheet) || {};
    for (const b of Array.isArray(fs.blocks) ? fs.blocks : []) if (b && b.name && b.type) out.set(String(b.name).toUpperCase(), String(b.type));
    const walk = (list) => (Array.isArray(list) ? list : []).forEach((st) => {
      if (!isObj(st)) return;
      if (st.do === "place" && st.block && st.type) out.set(String(st.block).toUpperCase(), String(st.type));
      Object.values(st).forEach((v) => { if (Array.isArray(v) && v.some(isObj)) walk(v); });
    });
    walk(tab && tab.program);
    return out;
  }
  /** The rules table's key for a field (its block's type and its path under the block), else null. */
  function rule(path, ty) {
    const m = /^\\Data\\Blocks\\([^\\]+)\\(.+)$/i.exec(String(path || ""));
    const bt = m && ty.get(m[1].toUpperCase());
    if (!bt) return null;
    const field = m[2].toUpperCase(), btu = bt.toUpperCase();
    for (const r of Array.isArray(cat().principle_rules) ? cat().principle_rules : []) {
      if (!isObj(r) || !Array.isArray(r.types) || !Array.isArray(r.fields)) continue;
      if (!r.types.some((x) => String(x).toUpperCase() === btu)) continue;
      if (r.fields.some((f) => { const u = String(f).toUpperCase(); return field === u || field.startsWith(u + "\\"); })) return r.key;
    }
    return null;
  }
  /** {keys, rule}: the group's own keys the library lists (at most 2); none, the rules table's for
   *  the fields its steps set (rule true) -- a check's set and sweep rows (a read or a step turned
   *  off sets nothing; the caller leaves the latter out), a pause's rows with a path; none either:
   *  no keys. */
  const SETS = new Set(["set", "sweep"]);
  WBPN.of = function (g, rows, tab) {
    const L = lib();
    const own = [...new Set((g && Array.isArray(g.principle) ? g.principle : []).filter((k) => typeof k === "string" && L.has(k)))].slice(0, 2);
    if (own.length) return { keys: own, rule: false };
    const paths = (Array.isArray(rows) ? rows : []).filter((r) => isObj(r) && typeof r.path === "string" && r.path && (r.kind == null || SETS.has(r.kind)))
      .map((r) => r.path);
    if (!paths.length) return { keys: [], rule: false };
    const ty = types(tab), got = [];
    for (const p of paths) { const k = rule(p, ty); if (k && L.has(k) && !got.includes(k)) got.push(k); }
    return { keys: got.slice(0, 2), rule: got.length > 0 };
  };
  /** A check's rows of group n. */
  WBPN.rows = function (tab, n) {
    const rows = tab && isObj(tab.check) && Array.isArray(tab.check.steps) ? tab.check.steps : [];
    return rows.filter((r) => isObj(r) && r.g === n);
  };
  /** The chip ("" when the card cannot show: learning mode off, no library, no key). */
  WBPN.chip = function (at, of) {
    if (!of || !of.keys.length || !WBPN.on()) return "";
    const L = lib(), tip = of.keys.map((k) => titleOf(k, L)).join(" · ") + (of.rule ? `\n${t("tip_prn_rule")}` : "");
    const on = !!C && C.at === at;
    return `<button class="prn-chip${on ? " on" : ""}" data-prn-at="${esc(at)}" data-prn-keys="${esc(of.keys.join(","))}"`
      + ` aria-haspopup="dialog" aria-expanded="${on}" title="${esc(tip)}">${esc(t("prn_chip"))}</button>`;
  };

  // ------------------------------------------------------------------ the card
  const cards = new Map();    // key -> the card, or {error}
  let C = null;               // the card open: {el, at, chip, keys, key, back [keys], err}

  function chipAt(at) {
    for (const b of document.querySelectorAll(".prn-chip")) if (b.dataset.prnAt === at && b.offsetParent !== null) return b;
    return null;
  }
  function setOn(chip, on) {
    if (!chip) return;
    chip.classList.toggle("on", on);
    chip.setAttribute("aria-expanded", String(on));
  }
  function open(chip) {
    const at = chip.dataset.prnAt, keys = String(chip.dataset.prnKeys || "").split(",").filter((k) => KEY_RE.test(k));
    if (!keys.length) return;
    if (C && C.at === at) { WBPN.close(true); return; }
    const swap = !!C;
    drop();
    // (a press on a chip: its click decides)
    const { el, off } = popover(document.body, "prn-card", "prn-title", { close: (back) => WBPN.close(back), place, keep: ".prn-chip" });
    C = { el, off, at, chip, keys, key: keys[0], back: [], err: null };
    setOn(chip, true);
    el.addEventListener("click", onClick);
    document.addEventListener("scroll", onScroll, true);
    if (!swap) el.classList.add("in");
    show(keys[0]);
    el.focus({ preventScroll: true });
  }
  function drop(back) {
    const c = C;
    if (!c) return null;
    C = null;
    document.removeEventListener("scroll", onScroll, true);
    c.off(back, c.chip);
    setOn(c.chip, false);
    return c;
  }
  WBPN.close = (back) => !!drop(back);
  WBPN.isOpen = () => !!C;
  /** A list scrolled under its chip: the card follows it, or closes once the chip is out of its list's view. */
  function onScroll(ev) {
    const c = C;
    if (!c || c.el.contains(ev.target) || !(ev.target instanceof Element) || !ev.target.contains(c.chip)) return;
    const a = c.chip.getBoundingClientRect(), r = ev.target.getBoundingClientRect();
    if (a.bottom <= r.top || a.top >= r.bottom) WBPN.close();
    else place();
  }
  /** A new state, another tab shown: the card stays with its chip (drawn anew), or closes when the
   *  chip is gone -- its tab not shown, the group card on another group, learning mode off. */
  WBPN.sync = function () {
    const c = C;
    if (!c) return;
    const chip = c.chip && c.chip.isConnected && c.chip.offsetParent !== null ? c.chip : chipAt(c.at);
    if (!chip || !WBPN.on()) { WBPN.close(); return; }
    if (chip !== c.chip) { c.chip = chip; setOn(chip, true); }
    if (c.lang !== I18N.lang) draw();
    else place();
  };

  function show(key) {
    const c = C;
    c.key = key;
    c.err = null;
    if (cards.has(key)) { draw(); return; }
    draw();
    const fn = apiFn();
    if (!fn) { c.err = "Api.principle"; draw(); return; }
    fn(key).then((card) => {
      if (!isObj(card) || card.error) { if (C === c && c.key === key) { c.err = (card && card.error) || "?"; draw(); } return; }
      cards.set(key, card);
      if (C === c && c.key === key) draw();
    }, (e) => { if (C === c && c.key === key) { c.err = String((e && e.message) || e || "?"); draw(); } });
  }

  // ------------------------------------------------------------------ drawing
  const LETTER = /[\p{Script=Latin}\p{Script=Greek}]/u;
  const OPS = new Set(["Σ", "Δ", "Π", "∂", "∇"]);       // (Greek capitals used as operators: upright)
  /** An equation or a symbol line in its plain marks: _x a subscript and ^x a superscript (the run
   *  of letters and digits after it), a single letter in italics (in a symbol line only the
   *  letters the equation uses: its words stay upright). Only <i>, <sub>, <sup>; the rest escaped. */
  function math(s, only) {
    const out = [], str = String(s || "");
    let i = 0;
    const run = (j) => { let k = j; while (k < str.length && /[\p{L}\p{N}]/u.test(str[k]) && !OPS.has(str[k])) k++; return k; };
    while (i < str.length) {
      const ch = str[i];
      if ((ch === "_" || ch === "^") && i + 1 < str.length && /[\p{L}\p{N}]/u.test(str[i + 1])) {
        const k = run(i + 1), tag = ch === "_" ? "sub" : "sup";
        out.push(`<${tag}>${esc(str.slice(i + 1, k))}</${tag}>`);
        i = k;
        continue;
      }
      if (/[\p{L}\p{N}]/u.test(ch) && !OPS.has(ch)) {
        const k = run(i), word = str.slice(i, k);
        const single = [...word].length === 1 && LETTER.test(word) && (!only || only.has(word));
        out.push(single ? `<i>${esc(word)}</i>` : esc(word));
        i = k;
        continue;
      }
      out.push(esc(ch));
      i++;
    }
    return out.join("");
  }
  /** The single letters an equation uses (a symbol line sets only those in italics). */
  function letters(eq) {
    const out = new Set(), str = String(eq || "").replace(/[_^][\p{L}\p{N}]+/gu, " ");
    for (const m of str.matchAll(/[\p{L}\p{N}]+/gu)) if ([...m[0]].length === 1 && LETTER.test(m[0]) && !OPS.has(m[0])) out.add(m[0]);
    return out;
  }
  /** The source line: each book "Authors, Title, Nth ed.[, Ch. N]", its title (the field before the
   *  edition) in italics; the rest as written. */
  function refHtml(ref) {
    return String(ref || "").split(" · ").map((book) => {
      const parts = book.split(", "), e = parts.findIndex((p) => /^\d+(st|nd|rd|th) ed\.$/.test(p));
      return e > 0 ? parts.map((p, i) => (i === e - 1 ? `<i>${esc(p)}</i>` : esc(p))).join(", ") : esc(book);
    }).join(" · ");
  }
  function html(c) {
    const L = lib(), card = cards.get(c.key), lg = zh() ? "zh" : "en";
    const tt = card && isObj(card.title) ? card.title : (L.get(c.key) || {});
    const name = (zh() ? tt.zh : tt.en) || tt.en || c.key, term = zh() && tt.en && tt.en !== name ? tt.en : "";
    let h = `<div class="prn-h">`
      + (c.back.length ? `<button class="prn-back flat" data-n="back">${icon("chevron-left")}<span>${esc(t("prn_back"))}</span></button>` : "")
      + `<div class="prn-t"><b id="prn-title">${esc(name)}</b>${term ? `<span class="prn-en" lang="en">${esc(term)}</span>` : ""}</div>`
      + `<button class="prn-x flat icon" data-n="close" title="${esc(t("close"))}" aria-label="${esc(t("close"))}">${icon("close")}</button></div>`;
    if (!card) return h + (c.err ? `<p class="prn-q err" title="${esc(c.err)}">${esc(t("prn_error"))}</p>` : `<p class="prn-q">${esc(t("reading"))}</p>`);
    const pick = (f) => (isObj(card[f]) ? card[f][lg] || card[f].en || "" : "");
    const idea = pick("idea"), eq = pick("eq"), sym = pick("sym");
    if (idea) h += `<p class="prn-idea">${esc(idea)}</p>`;
    if (eq) h += `<div class="prn-eq">${math(eq)}</div>`;
    if (sym) h += `<p class="prn-sym">${math(sym, letters(eq))}</p>`;
    // related: the group's other key first, then the card's own; not the cards ‹ Back goes through
    const rel = [...new Set([...c.keys, ...(Array.isArray(card.related) ? card.related : [])])]
      .filter((k) => k !== c.key && !c.back.includes(k) && L.has(k)).slice(0, 3);
    if (rel.length) {
      h += `<p class="prn-rel"><span class="prn-lb">${esc(t("prn_related"))}</span><span class="prn-rl">`
        + rel.map((k) => `<button class="prn-go flat" data-n="go" data-k="${esc(k)}">${esc(titleOf(k, L))}</button>`).join("") + `</span></p>`;
    }
    if (typeof card.ref === "string" && card.ref.trim()) h += `<p class="prn-ref"><span class="prn-lb">${esc(t("prn_ref"))}</span><span>${refHtml(card.ref.trim())}</span></p>`;
    return h;
  }
  function draw() {
    const c = C;
    if (!c) return;
    const h = html(c);
    c.lang = I18N.lang;
    if (c.h !== h) { c.h = h; c.el.innerHTML = h; }
    place();
  }

  // ------------------------------------------------------------------ where it goes
  /** What the card keeps clear of on the flowsheet: the objects a run by group has framed (their
   *  blocks drawn ahead and their tags, .gcv) in the pane shown. */
  function framed() {
    const svg = window.wb && wb.pane && wb.pane.svg;
    if (!svg) return [];
    return [...svg.querySelectorAll(".fs-pv.gcv .pv-blk, .fs-tag2.gcv")].map((e) => e.getBoundingClientRect()).filter((r) => r.width > 0 && r.height > 0);
  }
  const hits = (x, y, w, h, rs) => rs.filter((r) => x < r.right + GAP && r.left - GAP < x + w && y < r.bottom + GAP && r.top - GAP < y + h);
  /** Beside its chip, clear of the card the chip is on: right of that card where there is room
   *  (level with the chip), else over the chip (the group card: at the flowsheet's bottom), else
   *  under it; where neither fits, on the side with more room. Then slid sideways off the objects
   *  a run by group framed, where a place clear of them is in the window. Held inside the window. */
  function place() {
    const c = C;
    if (!c || !c.chip || !c.chip.isConnected) return;
    const el = c.el, vw = window.innerWidth, vh = window.innerHeight, w = Math.min(W, vw - 2 * M);
    el.style.width = `${w}px`;
    el.style.maxHeight = `${vh - 2 * M}px`;
    const a = c.chip.getBoundingClientRect(), host = c.chip.closest(".prop-card, .gc-card"), b = host ? host.getBoundingClientRect() : a;
    const h = el.offsetHeight, up = !!(host && host.classList.contains("gc-card"));
    let x, y;
    if (!up && b.right + GAP + w <= vw - M) { x = b.right + GAP; y = a.top - 12; }
    else {
      const above = a.top - GAP - M, below = vh - a.bottom - GAP - M, over = up ? h <= above || above >= below : h > below && above > below;
      x = Math.min(Math.max(M, a.left + a.width / 2 - w / 2), vw - w - M);
      if (up) x = Math.min(Math.max(M, a.left - 16), vw - w - M);
      y = over ? Math.max(M, (up ? Math.min(a.top, b.top) : a.top) - GAP - h) : a.bottom + GAP;
    }
    y = Math.max(M, Math.min(y, vh - M - h));
    const rs = framed(), on = hits(x, y, w, h, rs);
    if (on.length) {                             // (left of what it covers, else right of it; never over its own card)
      const lo = Math.min(...on.map((r) => r.left)) - GAP - w, hi = Math.max(...on.map((r) => r.right)) + GAP;
      const ok = (nx) => nx >= M && nx + w <= vw - M && !hits(nx, y, w, h, rs).length && !(host && hits(nx, y, w, h, [b]).length);
      const nx = [lo, hi].filter(ok).sort((p, q) => Math.abs(p - x) - Math.abs(q - x))[0];
      if (nx !== undefined) x = nx;
    }
    el.style.left = `${Math.round(x)}px`;
    el.style.top = `${Math.round(y)}px`;
  }

  // ------------------------------------------------------------------ what is done in it
  function onClick(ev) {
    const c = C, b = ev.target.closest && ev.target.closest("[data-n]");
    if (!c || !b) return;
    const n = b.dataset.n;
    if (n === "close") WBPN.close(true);
    else if (n === "go" && KEY_RE.test(b.dataset.k || "")) { c.back.push(c.key); show(b.dataset.k); c.el.focus({ preventScroll: true }); }
    else if (n === "back" && c.back.length) { show(c.back.pop()); c.el.focus({ preventScroll: true }); }
  }
  document.addEventListener("click", (ev) => {
    const chip = ev.target.closest && ev.target.closest(".prn-chip");
    if (!chip || chip.disabled) return;
    ev.preventDefault();
    ev.stopPropagation();
    open(chip);
  }, true);                                    // (before the card it sits on hears the press)
})();
