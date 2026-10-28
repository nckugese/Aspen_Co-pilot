/* A field's help card: what a field is, from the window's own files -- never Aspen,
 * never the AI -- so it opens while Aspen calculates. window.py's Api.fieldhelp (short name
 * Api.help; tools/fieldhelp.py) answers a request {path, type, row, info, lang} with the card:
 * Aspen's own prompt for the field (the inspector row's, one learned, or read now), its value,
 * unit and basis, the options with this Aspen's names, up to three completeness rules that may
 * concern it, the docs rows and passages about it, and a target for Ask AI. Where no source had
 * a prompt (need_prompt) the page posts field_info {tab, path} and asks again with the tab's
 * field_info once the server has read that one field (when Aspen is free).
 *
 * Entry points, where the user already is: a "?" on an inspector row (under the pointer or the
 * keyboard's focus, always on the row whose card is open) and the row's ⊕ menu's first item; a
 * change record's row in the Changes tab; a step's path in the block program (a "?" on the path
 * of the step under the pointer or selected, and the block's right-click menu). One card at a
 * time: a dialog that blocks nothing (a press elsewhere or Escape closes it; another "?" swaps
 * it), beside what it is about. Cards are kept per field and language, so a second open is only
 * drawing. Aspen's texts stay in Aspen's English; our words follow the page's language; a tree
 * path never shows (the title's tooltip has it). A card opened over the flowsheet folds the
 * diagnosis card and the missing-inputs panel to their head rows. While a card shows its "Ask AI", the
 * inspector's own "Ask AI" hides (body.fh-asks, style.css): one Ask AI on screen. Feature-detected:
 * catalog.features field_help and the window's Api.fieldhelp.
 *
 *   WBH.on()                          the server and the window make help cards
 *   WBH.open(anchor, req, o)          the card of req {path, type, row?} beside anchor; o {tab,
 *                                     beside (an element the card keeps clear of), title (shown
 *                                     while it loads), mark (marked .fh-on while open), onClose}
 *   WBH.fromRecord(anchor, r, tab, types)   a change record's field (its target.path)
 *   WBH.fromBlock(blk, anchor)        a program step's field (WB.fieldPathOf)
 *   WBH.close(back)                   close it (back: the focus to what opened it); whether one was open
 *   WBH.sync()                        a new state: a field_info answered, the language, the canvas's 「?」
 *   WBH.isOpen(path?)                 a card is open (on that field)
 *   WBH.lastMs                        how long the last open took until its card was drawn
 */
(function () {
  "use strict";
  const WBH = (window.WBH = { lastMs: null });
  // the server's texts come with their tree paths in words (a backslash left, an option's
  // description, is made one too): the card never shows a path
  const { esc, feature, fmtVal, icon, list, popover, t, words, zh } = WBA;
  const st = () => (window.wb && wb.state) || null;

  /** window.py's Api.fieldhelp (or its short name), as a function returning a promise; null
   *  where the window has neither. */
  function apiFn() {
    const a = window.pywebview && window.pywebview.api;
    const fn = a && (typeof a.fieldhelp === "function" ? a.fieldhelp : typeof a.help === "function" ? a.help : null);
    return fn ? (req) => Promise.resolve().then(() => fn.call(a, req)) : null;
  }
  WBH.on = () => feature("field_help") && !!apiFn();

  const WAIT_MS = 20000;      // field_info not answered in this long: the card says Aspen has not answered
  const cards = new Map();    // the request (JSON) -> its card: a second open only draws
  const passages = new Map(); // a docs entry's ref -> {state: "loading" | "ok" | "error", p}
  const allOpts = new Map();  // the field's path + language -> every option, or "loading"
  let C = null;               // the card open: see open()

  /** A block's type from the path's block name, in the tab's session. */
  function typeOf(path, tab) {
    const m = /^\\Data\\Blocks\\([^\\]+)\\/i.exec(String(path || "")), s = st();
    if (!m || !s) return null;
    const sess = tab && s.sessions ? s.sessions[tab.session] : null, name = m[1].toUpperCase();
    const b = (((sess || {}).flowsheet || {}).blocks || []).find((x) => x && String(x.name).toUpperCase() === name);
    return b && b.type ? b.type : null;
  }
  const rectOf = (el) => {
    if (!el) return null;
    if (el.getBoundingClientRect) { const r = el.getBoundingClientRect(); return r.width || r.height ? { left: r.left, right: r.right, top: r.top, bottom: r.bottom } : null; }
    return el.left !== undefined ? el : null;
  };

  // ------------------------------------------------------------------ open, close
  /** Returns whether a card is open now (false: none could be, or the same 「?」 closed it). */
  WBH.open = function (anchor, req, o = {}) {
    if (!WBH.on() || !req || !req.path) return false;
    const t0 = performance.now();
    const tab = o.tab || null, q = { path: String(req.path), type: req.type || typeOf(req.path, tab) || null, lang: zh() ? "zh" : "en" };
    if (req.row) q.row = req.row;
    // the tab's field_info for this field, read earlier: no need to ask Aspen again
    const fi = tab && tab.field_info;
    if (fi && fi.path === q.path && fi.status === "ok" && !(q.row && typeof q.row.prompt === "string")) q.info = fi;
    const sig = JSON.stringify(q);
    // the same 「?」 again (or its row's, drawn anew since): closed
    const same = C && C.sig === sig && (C.anchor === anchor || (C.anchor && anchor && !C.anchor.isConnected && C.anchor.className === anchor.className));
    if (same) { WBH.close(true); return false; }
    const swap = !!C;
    drop();
    const { el, off } = popover(document.body, "fh-card", "fh-title", { close: (back) => WBH.close(back), esc: clearFilter, place,
      keep: (x) => !!(x && x.closest && x.closest(TRIGGERS)) || !!(C && C.anchor && C.anchor.contains && C.anchor.contains(x)) });
    C = { el, off, sig, q, tab, anchor, rect: rectOf(anchor), beside: o.beside || null, title: o.title || "", mark: o.mark || null,
          onClose: o.onClose || null, step: o.step || null, card: cards.get(sig) || null, err: null, wait: null, filter: "",
          showAll: false, open: new Set(), docs: new Set(), lang: I18N.lang, t0, timed: false };
    if (C.mark) C.mark.classList.add("fh-on");
    // a card over the flowsheet (an inspector row's): the diagnosis card or the missing-inputs
    // panel there folds to its head row, so the three do not stack over the drawing
    if (anchor && anchor.closest && anchor.closest(".fs-wrap")) {
      if (window.WBD && WBD.fold) WBD.fold();
      if (window.WBM && WBM.fold) WBM.fold();
    }
    el.addEventListener("click", onClick);
    el.addEventListener("input", onInput);
    el.addEventListener("toggle", onToggle, true);
    draw();
    if (!swap) el.classList.add("in");
    el.focus({ preventScroll: true });
    if (C.card) { C.timed = true; WBH.lastMs = performance.now() - t0; after(C); } else load(C);
    return true;
  };
  /** Take the card off the page (a swap: another opens in its place; back: the focus to what opened it). */
  function drop(back) {
    const c = C;
    if (!c) return null;
    C = null;
    clearTimeout(c.slowT);
    document.body.classList.remove("fh-asks");
    if (c.mark) c.mark.classList.remove("fh-on");
    if (c.onClose) c.onClose();
    c.off(back, c.anchor);
    return c;
  }
  WBH.close = function (back) {
    const c = drop(back);
    if (!c) return false;
    if (c.step && window.wb && wb.pane) bqSoon();
    return true;
  };
  WBH.place = () => place();
  WBH.isOpen = (path) => !!C && (path === undefined || C.q.path.toLowerCase() === String(path || "").toLowerCase());
  const TRIGGERS = ".ihelp, .ch-help, .fh-bq";      // another 「?」: it swaps the card itself

  // ------------------------------------------------------------------ the card from the window
  const cacheable = (card) => !card.need_prompt && !(card.notes || []).some((n) => n === "strings_loading" || n === "aspen_busy");
  function load(c) {
    const fn = apiFn();
    if (!fn) { c.err = "Api.fieldhelp"; draw(); return; }
    const q = c.q, sig = c.sig;
    fn(q).then((card) => {
      if (C !== c || c.sig !== sig) return;
      if (!card || typeof card !== "object" || card.error) { c.err = (card && card.error) || "?"; draw(); return; }
      c.card = card;
      if (cacheable(card)) cards.set(sig, card);
      draw();
      if (!c.timed) { c.timed = true; WBH.lastMs = performance.now() - c.t0; }
      after(c);
    }, (e) => { if (C === c) { c.err = String((e && e.message) || e || "?"); draw(); } });
  }
  /** No prompt anywhere: the server reads the field (field_info), once it is connected and the
   *  model open; the answer comes in the tab's field_info (sync). */
  function after(c) {
    const card = c.card;
    if (!card || !card.need_prompt || c.q.info || c.wait || !c.tab) return;
    if (!(window.wb && wb.connected)) c.wait = { state: "offline" };
    else if (!WBA.isOpen(c.tab)) c.wait = { state: "closed" };
    else {
      const fi = c.tab.field_info;
      c.wait = { state: "asked", at: Date.now(), base: fi && fi.path === c.q.path ? Number(fi.t) || 0 : 0 };
      wb.post({ type: "field_info", tab: c.tab.id, path: c.q.path });
      c.slowT = setTimeout(() => { if (C === c && c.wait && c.wait.state === "asked") { c.wait.state = "slow"; draw(); } }, WAIT_MS);
    }
    draw();
  }
  WBH.sync = function () {
    bqSoon();
    const c = C, s = st();
    if (!c || !s) return;
    if (c.tab) {
      const tab = (s.tabs || []).find((x) => x.id === c.tab.id);
      if (!tab || (wb.pane && wb.pane.tabId !== tab.id)) { WBH.close(); return; }   // its tab closed, or another shown
      c.tab = tab;
    }
    if (c.lang !== I18N.lang) {                  // the language switched: the card in the new one
      c.lang = I18N.lang;
      c.q = Object.assign({}, c.q, { lang: zh() ? "zh" : "en" });
      c.sig = JSON.stringify(c.q);
      c.card = cards.get(c.sig) || null;
      c.err = null;
      draw();
      if (!c.card) load(c);
      return;
    }
    const w = c.wait, fi = c.tab && c.tab.field_info;
    if (!w || !["asked", "waiting", "slow"].includes(w.state) || !fi || fi.path !== c.q.path || !((Number(fi.t) || 0) > w.base)) return;
    if (fi.status === "waiting") { if (w.state !== "waiting") { w.state = "waiting"; draw(); } return; }
    clearTimeout(c.slowT);
    if (fi.status === "closed") { c.wait = { state: "closed" }; draw(); return; }
    c.wait = { state: "read" };                  // read: the card again, with what Aspen said
    c.q = Object.assign({}, c.q, { info: fi });
    c.sig = JSON.stringify(c.q);
    load(c);
    draw();
  };

  // ------------------------------------------------------------------ drawing
  function titleHtml(c) {
    const lc = c.card && c.card.loc;
    if (!lc || !lc.field) return esc(c.title || words(c.q.path.split("\\").filter(Boolean).slice(-1)[0] || ""));
    const name = lc.src === "code" ? `<code class="code">${esc(words(lc.field))}</code>` : esc(words(lc.field));
    const q = (lc.q || []).map((x) => ` · ${esc(words(x))}`).join("");
    return `${name}${zh() && lc.gl ? `<small class="gl">（${esc(lc.gl)}）</small>` : ""}${q}`;
  }
  function kindText(c) {
    const card = c.card, lc = (card && card.loc) || {}, stream = /^\\Data\\Streams\\/i.test(c.q.path);
    const type = lc.type || c.q.type || (stream ? t("stream_word") : null);
    return [lc.obj, type, card ? t(card.result ? "fh_io_out" : "fh_io_in") : null].filter(Boolean).join(" · ");
  }
  const note = (text, cls) => `<p class="fh-note${cls ? ` ${cls}` : ""}">${icon("info")}<span>${esc(text)}</span></p>`;
  /** Aspen's own words on the field, or where they are: being read, waiting for Aspen, none. */
  function aspenHtml(c) {
    const card = c.card, pr = card.prompt && card.prompt.text, w = c.wait && c.wait.state;
    const notes = card.notes || [];
    let body = "";
    if (pr) body = `<p class="fh-pr" lang="en">${esc(words(pr))}</p>`;
    else if (w === "asked" || w === "read") body = `<p class="fh-q run">${esc(t("fh_reading"))}<i class="fh-bar" aria-hidden="true"><i></i></i></p>`;
    else if (w === "waiting" || notes.includes("aspen_busy")) body = `<p class="fh-q">${esc(t("fh_busy"))}</p>`;
    else if (w === "slow") body = `<p class="fh-q">${esc(t("fh_slow"))}</p>`;
    else if (w === "offline") body = `<p class="fh-q">${esc(t("fh_offline"))}</p>`;
    else if (w === "closed") body = `<p class="fh-q">${esc(t("fh_closed"))}</p>`;
    else if (notes.includes("no_prompt")) body = `<p class="fh-q">${esc(t("fh_no_prompt"))}</p>`;
    return body ? `<section class="fh-s"><h4>${esc(t("fh_aspen"))}</h4>${body}</section>` : "";
  }
  /** What it holds now: value and unit; the units it takes; its basis and the others. */
  function nowHtml(c) {
    const card = c.card, now = card.now, lines = [];
    if (now && ("value" in now) && now.found !== false) {
      const has = now.value !== null && now.value !== undefined && now.value !== "";
      const opt = has && (card.options || []).find((o) => o.now && o.name && o.name !== o.code);   // an option: its name too
      const val = `${fmtVal(now.value)}${now.unit ? ` ${now.unit}` : ""}${opt ? ` · ${words(opt.name)}` : ""}`;
      let s = has ? t("fh_now", val) : t("fh_now_none");
      if (has && !now.unit && typeof now.value === "number" && !(now.units || []).length) s += ` · ${t("fh_no_unit")}`;
      lines.push(`<p class="fh-now">${esc(s)}</p>`);
      const units = (now.units || []).filter(Boolean);
      if (units.length > 1) {
        const more = Number(now.units_more) || 0;
        lines.push(`<p class="fh-u">${esc(t("fh_units", list(units) + (more ? ` ${t("fh_units_more", more)}` : "")))}</p>`);
      }
    }
    const b = card.basis;
    if (b && Array.isArray(b.choices) && b.choices.length) {
      const nm = (x) => `${x.name || x.code}${zh() && x.gl ? `（${x.gl}）` : ""}`;
      const cur = b.choices.find((x) => x.now), others = b.choices.filter((x) => !x.now);
      lines.push(`<p class="fh-u">${esc(t("fh_basis", cur ? nm(cur) : b.now))}${others.length ? esc(t("fh_basis_alt", list(others.map(nm)))) : ""}</p>`);
    }
    if (card.result) lines.push(note(t("fh_result"), "res"));
    else if (now && now.enterable === false) lines.push(note(t("fh_inactive"), "off"));
    return lines.join("");
  }
  const optKey = (c) => `${c.q.path}|${c.q.lang}`;
  /** The options shown: the card's, or every one (asked for once) while filtering or shown all. */
  function optsList(c) {
    const card = c.card, all = allOpts.get(optKey(c)), f = c.filter.trim().toLowerCase();
    const whole = (c.showAll || f) && Array.isArray(all) ? all : card.options;
    if (!f) return { items: whole, loading: (c.showAll && all === "loading") };
    const hit = (o) => [o.code, o.name, o.desc].some((x) => String(x || "").toLowerCase().includes(f));
    return { items: whole.filter(hit), loading: all === "loading" };
  }
  function optsItems(c) {
    const card = c.card, { items, loading } = optsList(c);
    const nameOf = (o) => (o.name && o.name !== o.code ? esc(words(o.name)) : "");   // (a code with no name: the code alone)
    let h = items.map((o) => `<li class="fh-o${o.now ? " now" : ""}"><span class="fh-ot"><code>${esc(o.code)}</code>`
      + `<span class="fh-on">${nameOf(o)}</span>`
      + `${o.now ? `<em class="fh-cur">${esc(t("fh_opt_now"))}</em>` : ""}</span>`
      + `${o.desc ? `<small class="fh-od" lang="en">${esc(words(o.desc))}</small>` : ""}</li>`).join("");
    if (loading) h += `<li class="fh-oq">${esc(t("reading"))}</li>`;
    else if (!items.length) h += `<li class="fh-oq">${esc(t("fh_opts_none"))}</li>`;
    const more = Number(card.options_more) || 0;
    if (more && !c.showAll && !c.filter.trim()) h += `<li class="fh-omore"><button class="fh-more flat" data-f="opts_all">${esc(t("fh_opts_more", more))}</button></li>`;
    return h;
  }
  function optsHtml(c) {
    const card = c.card;
    if (!Array.isArray(card.options) || !card.options.length) return "";
    const n = card.options.length + (Number(card.options_more) || 0);
    const filter = card.options_more > 0 ? `<input class="fh-of" type="search" spellcheck="false" value="${esc(c.filter)}"`
      + ` placeholder="${esc(t("fh_opts_filter"))}" aria-label="${esc(t("fh_opts_filter"))}">` : "";
    return `<section class="fh-s fh-opts"><h4>${esc(t("fh_opts", n))}</h4>${filter}<ul class="fh-ol">${optsItems(c)}</ul></section>`;
  }
  function rulesHtml(c) {
    const rules = (c.card.rules || []).filter((r) => r && r.text);
    if (!rules.length) return "";
    return `<details class="fh-d" data-d="rules"${c.open.has("rules") ? " open" : ""}><summary>${esc(t("fh_rules", rules.length))}</summary>`
      + `<p class="fh-dn">${esc(t("fh_rules_note"))}</p><ul class="fh-rl">${rules.map((r) => `<li lang="en">${esc(words(r.text))}</li>`).join("")}</ul></details>`;
  }
  /** A docs passage (Markdown) as a little markup: headings, a table (the rows naming the
   *  field marked), list items and lines; `code` and **bold**. */
  function mdHtml(text, code) {
    const inline = (s) => esc(s).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
    const hitRx = code ? new RegExp(`(^|[^A-Z0-9_])${code.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}([^A-Z0-9_]|$)`) : null;
    const out = [];
    let rows = null;
    String(text || "").split("\n").forEach((line) => {
      if (/^\s*\|/.test(line)) {
        if (/^\s*\|[\s:|-]+\|?\s*$/.test(line)) return;          // the header's rule
        const cells = line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((x) => x.trim());
        if (!rows) { rows = []; out.push(rows); }
        rows.push(cells);
        return;
      }
      rows = null;
      const h = /^(#{1,6})\s+(.*)$/.exec(line);
      if (h) out.push(`<p class="fh-mh">${inline(h[2].replace(/\s*#+\s*$/, ""))}</p>`);
      else if (/^\s*[-*]\s+/.test(line)) out.push(`<p class="fh-ml">• ${inline(line.replace(/^\s*[-*]\s+/, ""))}</p>`);
      else if (/^\s*>\s?/.test(line)) out.push(`<p class="fh-mq">${inline(line.replace(/^\s*>\s?/, ""))}</p>`);
      else if (line.trim() && !/^\s*(```|~~~)/.test(line)) out.push(`<p>${inline(line)}</p>`);
    });
    return out.map((x) => (Array.isArray(x)
      ? `<table>${x.map((cells, i) => `<tr${i && hitRx && hitRx.test(cells.join(" ")) ? ' class="hit"' : ""}>${cells.map((cell) => (i ? `<td>${inline(cell)}</td>` : `<th>${inline(cell)}</th>`)).join("")}</tr>`).join("")}</table>`
      : x)).join("");
  }
  function docsHtml(c) {
    const docs = (c.card.docs || []).filter((d) => d && d.ref);
    if (!docs.length) return "";
    const code = ((c.card.loc || {}).code || "").toUpperCase();
    const one = (d) => {
      const open = c.docs.has(d.ref), p = passages.get(d.ref);
      const src = t(d.src === "user" ? "fh_docs_user" : "fh_docs_ship");
      const where = [d.file, d.heading && words(d.heading)].filter(Boolean).join(" › ");
      const pass = !open ? "" : !p || p.state === "loading" ? `<div class="fh-pass q">${esc(t("reading"))}</div>`
        : p.state === "error" ? `<div class="fh-pass q">${esc(t("fh_doc_err"))}</div>`
          : `<div class="fh-pass" data-ref="${esc(d.ref)}" lang="en">${mdHtml(words(p.p.section), code)}</div>`;
      return `<div class="fh-doc"><div class="fh-dh"><span class="fh-src${d.src === "user" ? " user" : ""}">${esc(src)}</span> ${esc(where)}</div>`
        + `<p class="fh-dr" lang="en">${esc(words(d.row || d.text || ""))}</p>`
        + `<button class="fh-dx flat" data-f="doc" data-ref="${esc(d.ref)}" aria-expanded="${open}">${esc(t(open ? "fh_doc_hide" : "fh_doc_show"))}</button>${pass}</div>`;
    };
    return `<details class="fh-d" data-d="docs"${c.open.has("docs") ? " open" : ""}><summary>${esc(t("fh_docs", docs.length))}</summary>${docs.map(one).join("")}</details>`;
  }
  const NOTES = { strings_loading: "fh_strings_loading", strings_failed: "fh_nostrings", rules_unavailable: "fh_rules_off", not_found: "fh_not_found" };
  function html(c) {
    const card = c.card;
    const tip = card ? [card.where && t("in_aspen", words(card.where)), c.q.path].filter(Boolean).join("\n") : c.q.path;
    let h = `<div class="fh-h"><div class="fh-t"><b id="fh-title" title="${esc(tip)}">${titleHtml(c)}</b><span class="fh-k">${esc(kindText(c))}</span></div>`
      + `<button class="fh-x flat icon" data-f="close" title="${esc(t("close"))}" aria-label="${esc(t("close"))}">${icon("close")}</button></div>`;
    if (!card) {
      // a known refusal in the UI's own words (diag.js), the server's sentence in the tooltip
      const known = c.err && window.WBD && WBD.refusal ? WBD.refusal(c.err) : null;
      return h + (c.err ? `<p class="fh-q err"${known ? ` title="${esc(c.err)}"` : ""}>${esc(t("fh_error", known ? known.words : words(c.err)))}</p>`
        : `<p class="fh-q run">${esc(t("reading"))}<i class="fh-bar" aria-hidden="true"><i></i></i></p>`);
    }
    const lc = card.loc || {};
    if (zh() && lc.hint) h += `<p class="fh-hint">${esc(lc.hint)}</p>`;
    h += aspenHtml(c) + nowHtml(c);
    if (card.where) h += `<p class="fh-where">${esc(t("in_aspen", words(card.where)))}</p>`;
    h += optsHtml(c) + rulesHtml(c) + docsHtml(c);
    h += (card.notes || []).filter((n) => NOTES[n]).map((n) => note(t(NOTES[n]))).join("");
    if (card.ask && card.ask.path) {
      h += `<div class="fh-f"><button class="fh-ask" data-f="ask" title="${esc(t("tip_fh_ask"))}">${icon("sparkle")}<span class="bt">${esc(t("ask_ai"))}</span></button></div>`;
    }
    return h;
  }
  function draw() {
    const c = C;
    if (!c) return;
    const h = html(c);
    if (c.h !== h) {
      const f = c.el.querySelector(".fh-of"), typing = f && document.activeElement === f, at = typing ? [f.selectionStart, f.selectionEnd] : null;
      const scroll = c.el.scrollTop, tops = {};
      c.el.querySelectorAll(".fh-pass[data-ref]").forEach((p) => { tops[p.dataset.ref] = p.scrollTop; });
      c.h = h;
      c.el.innerHTML = h;
      c.el.scrollTop = scroll;
      if (typing) { const g = c.el.querySelector(".fh-of"); if (g) { g.focus({ preventScroll: true }); g.setSelectionRange(at[0], at[1]); } }
      // a passage keeps where it was scrolled; one just shown opens at the rows that name the field
      c.el.querySelectorAll(".fh-pass[data-ref]").forEach((p) => {
        const hit = p.querySelector("tr.hit");
        if (tops[p.dataset.ref] !== undefined) p.scrollTop = tops[p.dataset.ref];
        else if (hit) p.scrollTop += hit.getBoundingClientRect().top - p.getBoundingClientRect().top - 36;
      });
      // the card's "Ask AI" stands for the inspector's while it shows (one Ask AI on screen)
      document.body.classList.toggle("fh-asks", !!c.el.querySelector(".fh-ask"));
    }
    place();
  }
  /** Only the options' list (the filter keeps its caret). */
  function drawOpts() {
    const c = C, ul = c && c.el.querySelector(".fh-ol");
    if (!ul) return;
    ul.innerHTML = optsItems(c);
    c.h = null;
  }

  // ------------------------------------------------------------------ where it goes
  /** Beside the element it keeps clear of (the inspector, the step), left of it where there is
   *  room, else right, level with what opened it; otherwise under that (its right edges lined
   *  up), over it where there is more room there. Held inside the window; taller: it scrolls. */
  function place() {
    const c = C;
    if (!c) return;
    const el = c.el, vw = window.innerWidth, vh = window.innerHeight, m = 8, w = Math.min(360, vw - 2 * m);
    el.style.width = `${w}px`;
    el.style.maxHeight = `${vh - 2 * m}px`;
    const live = c.anchor && c.anchor.isConnected !== false ? rectOf(c.anchor) : null;
    const a = live || c.rect || { left: vw / 2, right: vw / 2, top: 60, bottom: 60 };
    if (live) c.rect = live;
    const b = c.beside ? rectOf(c.beside) : null, h = el.offsetHeight;
    let x = null, y;
    if (b) x = b.left - m - w >= m ? b.left - m - w : b.right + m + w <= vw - m ? b.right + m : null;
    if (x !== null) y = Math.max(m, Math.min(a.top - 10, vh - m - h));
    else {
      x = Math.max(m, Math.min(a.right - w, vw - w - m));
      const below = vh - a.bottom - 6 - m, above = a.top - 6 - m, up = h > below && above > below;
      const room = Math.max(160, up ? above : below);
      el.style.maxHeight = `${room}px`;
      y = up ? Math.max(m, a.top - 6 - Math.min(h, room)) : a.bottom + 6;
    }
    el.style.left = `${Math.round(x)}px`;
    el.style.top = `${Math.round(y)}px`;
  }

  // ------------------------------------------------------------------ what is done in it
  function onClick(ev) {
    const c = C, b = ev.target.closest && ev.target.closest("[data-f]");
    if (!c || !b) return;
    const f = b.dataset.f;
    if (f === "close") WBH.close(true);
    else if (f === "ask") ask(c);
    else if (f === "opts_all") { c.showAll = true; allOptions(c); drawOpts(); }
    else if (f === "doc") doc(c, b.dataset.ref);
  }
  function onInput(ev) {
    const c = C;
    if (!c || !ev.target.classList.contains("fh-of")) return;
    c.filter = ev.target.value;
    if (c.filter.trim()) allOptions(c);
    drawOpts();
  }
  /** Escape in the options' filter empties it first. */
  function clearFilter(ev) {
    if (!(ev.target.classList && ev.target.classList.contains("fh-of") && ev.target.value)) return false;
    ev.target.value = "";
    onInput(ev);
    return true;
  }
  function onToggle(ev) {
    const c = C, d = ev.target;
    if (!c || !d || !d.dataset || !d.dataset.d) return;
    if (d.open) c.open.add(d.dataset.d); else c.open.delete(d.dataset.d);
    c.h = null;
    place();
  }
  /** Every option of the field (the card lists 12), asked for once. */
  function allOptions(c) {
    const k = optKey(c), fn = apiFn();
    if (allOpts.has(k) || !fn) return;
    allOpts.set(k, "loading");
    const req = { path: c.q.path, type: c.q.type, options: "all", lang: c.q.lang };
    if (c.q.row) req.row = c.q.row;
    if (c.q.info) req.info = c.q.info;
    fn(req).then((got) => {
      allOpts.set(k, got && Array.isArray(got.options) ? got.options : []);
      if (C === c) drawOpts();
    }, () => { allOpts.delete(k); if (C === c) drawOpts(); });
  }
  /** A docs entry's passage shown or hidden (read once). */
  function doc(c, ref) {
    if (!ref) return;
    if (c.docs.has(ref)) { c.docs.delete(ref); draw(); return; }
    c.docs.add(ref);
    const fn = apiFn();
    if (!passages.has(ref) && fn) {
      passages.set(ref, { state: "loading" });
      fn({ ref }).then((p) => {
        passages.set(ref, p && !p.error && p.section ? { state: "ok", p } : { state: "error" });
        if (C === c) draw();
      }, () => { passages.set(ref, { state: "error" }); if (C === c) draw(); });
    }
    draw();
  }
  /** Ask AI about the field: the composer, its chip held on the field. The card closes. */
  function ask(c) {
    const card = c.card, a = card && card.ask, tab = c.tab || WBA.shownTab();
    if (!a || !tab) return;
    WBH.close();
    WBA.askAI(tab, { kind: "field", path: a.path, label: words(card.short || a.label || ""), obj: a.obj, name: a.name });
  }

  // ------------------------------------------------------------------ the other entry points
  WBH.fromRecord = function (anchor, r, tab, types) {
    const tg = (r && r.target) || {};
    if (!tg.path) return;
    const type = tg.type || (tg.block && types ? types[tg.block] : null) || typeOf(tg.path, tab);
    const lc = WBL.of(tg.path, type, tab && tab.session);
    WBH.open(anchor, { path: tg.path, type }, { tab, title: lc ? WBL.text(lc, "field") : "", mark: anchor && anchor.closest ? anchor.closest(".ch-row") : null });
  };
  /** A step's field (or a path block's own): the card beside the step. */
  WBH.fromBlock = function (blk, anchor) {
    const fp = blk && WB.fieldPathOf ? WB.fieldPathOf(blk) : null, pane = window.wb && wb.pane;
    const rec = fp && pane ? wb.recs.get(pane.tabId) : null;
    if (!fp || !rec || rec.ws !== blk.workspace) return;
    const tab = WBA.tabOf(rec.id), type = typeOf(fp.path, tab);
    const shape = (b) => (b.pathObject && b.pathObject.svgPath) || b.getSvgRoot();
    const lc = WBL.of(fp.path, type, tab && tab.session);
    WBH.open(anchor || shape(fp.at), { path: fp.path, type }, { tab, beside: shape(blk), step: blk.id, title: lc ? WBL.text(lc, "field") : "" });
    bqSoon();
  };
  if (window.WB) {                               // the block menu's "What is this field?" (blocks.js)
    WB.onFieldHelp = (blk) => WBH.fromBlock(blk);
    WB.fieldHelpOn = () => WBH.on();
  }

  // ------------------------------------------------------------------ the block program's 「?」
  // A small 「?」 at the corner of the path a step names -- the step under the pointer, else the
  // one selected, else the one whose card is open -- over the canvas (it moves with the view,
  // never animates but its fade); none while a block is dragged, a category's blocks show, or
  // where it would sit under the canvas's own tools.
  let bqFrame = 0;
  function bqSoon() { if (!bqFrame) bqFrame = requestAnimationFrame(() => { bqFrame = 0; bqUpdate(); }); }
  /** The step a block is, or whose path it is. */
  function stepOf(blk) {
    if (!blk || blk.isInFlyout) return null;
    if (/^wb_(stream|block|path)$/.test(blk.type)) {
      const p = blk.getParent();
      return p && p.getInput && p.getInput("PATH") && p.getInputTargetBlock("PATH") === blk ? p : null;
    }
    return blk.getInput && blk.getInput("PATH") ? blk : null;
  }
  function bqEl(pane) {
    if (pane.fhBq && pane.fhBq.isConnected) return pane.fhBq;
    const area = pane.q(".blockly");
    if (!area) return null;
    const b = (pane.fhBq = document.createElement("button"));
    b.type = "button";
    b.className = "fh-bq";
    b.innerHTML = icon("help");
    area.appendChild(b);
    b.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const rec = wb.recs.get(pane.tabId), blk = rec && b.dataset.id ? rec.ws.getBlockById(b.dataset.id) : null;
      if (blk) WBH.fromBlock(blk, b);
    });
    // the pointer: which step it rests on (a frame at a time)
    let pend = null;
    area.addEventListener("pointermove", (ev) => {
      if (!WBH.on()) return;
      if (pend) { pend.ev = ev; return; }
      pend = { ev };
      requestAnimationFrame(() => {
        const e = pend.ev, rec = wb.recs.get(pane.tabId);
        pend = null;
        if (!rec || (e.target && e.target.closest && e.target.closest(".fh-bq"))) return;
        const g = e.target && e.target.closest ? e.target.closest("g[data-id]") : null;
        const step = g && !rec.ws.isDragging() ? stepOf(rec.ws.getBlockById(g.getAttribute("data-id"))) : null;
        const id = step ? step.id : null;
        if (pane.fhHover !== id) { pane.fhHover = id; bqUpdate(); }
      });
    }, { passive: true });
    area.addEventListener("pointerleave", () => { if (pane.fhHover) { pane.fhHover = null; bqUpdate(); } }, { passive: true });
    window.addEventListener("resize", bqSoon);
    return b;
  }
  function bqHide(b) { if (b && b.classList.contains("on")) b.classList.remove("on"); }
  function bqUpdate() {
    const pane = window.wb && wb.pane, rec = pane && pane.tabId ? wb.recs.get(pane.tabId) : null;
    if (!rec) return;
    if (!WBH.on()) { bqHide(pane.fhBq); return; }
    const b = bqEl(pane);
    if (!b) return;
    if (!rec.fhWired) {                           // the view moves, a block is picked or moved
      rec.fhWired = true;
      const E = Blockly.Events, kinds = new Set([E.SELECTED, E.VIEWPORT_CHANGE, E.BLOCK_MOVE, E.BLOCK_DRAG, E.BLOCK_CHANGE,
        E.BLOCK_CREATE, E.BLOCK_DELETE, E.TOOLBOX_ITEM_SELECT].filter(Boolean));
      rec.ws.addChangeListener((ev) => { if (kinds.has(ev.type) && wb.pane && wb.pane.tabId === rec.id) bqSoon(); });
    }
    b.title = t("tip_fh");
    b.setAttribute("aria-label", t("fh_what"));
    const ws = rec.ws, box = ws.getToolbox && ws.getToolbox(), fly = box && box.getFlyout && box.getFlyout();
    if (ws.isDragging() || (fly && fly.isVisible()) || !rec.el.isConnected || !pane.q(".blockly").contains(rec.el)) { bqHide(b); return; }
    const sel = Blockly.common && Blockly.common.getSelected ? Blockly.common.getSelected() : null;
    const cand = [pane.fhHover && ws.getBlockById(pane.fhHover), sel && sel.workspace === ws ? stepOf(sel) : null,
      C && C.step ? ws.getBlockById(C.step) : null];
    let fp = null, step = null;
    for (const s of cand) { fp = s ? WB.fieldPathOf(s) : null; if (fp) { step = s; break; } }
    const shape = fp && fp.at.pathObject && fp.at.pathObject.svgPath;
    const r = shape && shape.getBoundingClientRect(), area = pane.q(".blockly").getBoundingClientRect();
    if (!r || !r.width) { bqHide(b); return; }
    const x = r.right - area.left - 10, y = r.top - area.top - 8;
    const bar = pane.q(".blk-bar"), br = bar ? bar.getBoundingClientRect() : null;
    const under = br && br.width && area.left + x < br.right + 4 && area.left + x + 18 > br.left - 4 && area.top + y < br.bottom + 4 && area.top + y + 18 > br.top - 4;
    if (x < 2 || y < 2 || x > area.width - 20 || y > area.height - 20 || under) { bqHide(b); return; }
    b.dataset.id = step.id;
    b.style.transform = `translate3d(${Math.round(x)}px, ${Math.round(y)}px, 0)`;
    b.classList.add("on");
  }
})();
