/* Where a field sits in Aspen, in words: the page's side of tools/aspen_labels.py.
 *
 * The server names a tree path with a "loc" ({sec, obj, type, io, field, code, q, gl, hint,
 * src}): every inspector row carries one, and pywebview.api.labels gives the rest in batches
 * (window.py, Api.labels). Until one comes, the catalog's words where it names the path, else
 * the path's own parts: never a backslash. The glossary itself lives only in Python.
 *
 * One style everywhere: Aspen's English name, and in the Chinese interface our own
 * explanation beside it, quieter: "Reflux ratio（迴流比）", with its object "ESTCOL › Reflux
 * ratio（迴流比）", a result "…（再沸器熱負荷，結果）" / "… (result)". A field the glossary does
 * not know is named by the prompt the user's own Aspen gives for it (learned by the server);
 * one with no name yet shows its Aspen variable, and the window asks the server to learn it
 * (a labels_learn event, at most 30 paths, debounced). The path itself goes only into a
 * tooltip.
 *
 *   WBL.of(path, type?, session?)     a loc, at once (cached, else a stand-in and a batch asked)
 *   WBL.best(path, type, loc, sess)   the better of a row's own loc and the one cached
 *   WBL.text(loc, form, zh1)          "full" breadcrumb, "short" object › field, "name" the field
 *                                     with its result note, "field" the field alone (zh1: WBL.html's)
 *   WBL.html(loc, form, o)            the same words as markup (gloss quieter, a code in mono),
 *                                     with the tooltip (o.tip: a line more, e.g. the path); o.zh1:
 *                                     in Chinese our words first, Aspen's after them, quieter
 *                                     ("壓力 Pressure": the inspector's rows)
 *   WBL.say(path, session?)           short text of a path; WBL.full(path, session?) the breadcrumb
 *   WBL.name(label)                   a catalog label {en, zh} in this style (block menus)
 *   WBL.title(en, zh1), WBL.titleText(en)  a title (form, sheet, model object, palette tab) in this
 *                                     style, our Chinese from catalog.terms (markup / text; zh1 as
 *                                     WBL.html's); WBL.zhOf(en) it alone
 *   WBL.rich(text, session?)          plain text as markup, every \Data\ path in it named
 *   WBL.learn(session, paths)         ask the server to learn names for these paths
 *   WBL.ver, WBL.onChange             bumped / called when better names came
 */
(function () {
  "use strict";
  const ARROW = " › ", DOT = " · ";
  const UNNAMED = new Set(["Components", "Methods", "Setup"]);   // a short label names the section there
  const RANK = { glossary: 3, prompt: 2, aspen: 1, docs: 0.5, code: 0 };   // (docs: an inspector row the server named by its docs row)
  const FETCH_MS = 50, LEARN_MS = 1500, LEARN_MAX = 30, BATCH = 200;

  const WBL = (window.WBL = { ver: 0, onChange: null, strings: null });
  const cache = new Map();          // "path|TYPE" -> {lc, gen}: the server's loc
  const asked = new Set();          // keys asked for in this generation
  const want = new Map();           // key -> {path, type, session}: to ask in the next batch
  const learnQ = new Map();         // session -> Set of paths to learn
  const sent = new Set();           // "session|path" asked to be learned (once a page)
  let gen = 0, fetchT = 0, learnT = 0, bumpT = 0, started = false, seenSig = null, polls = 0;

  const { catalog, esc, t, zh } = WBA;
  const state = () => (window.wb && wb.state) || null;
  const api = (name) => { const a = window.pywebview && window.pywebview.api; return a && typeof a[name] === "function" ? a : null; };
  const rank = (lc) => RANK[(lc && lc.src) || "code"] ?? 0;

  // ------------------------------------------------------------------ what a path names
  const blockOf = (p) => { const m = /^\\Data\\Blocks\\([^\\]+)/i.exec(p); return m ? m[1] : null; };
  /** A block's type (RadFrac): from the session's flowsheet, the one the blocks work on, any. */
  function typeOf(p, session) {
    const b = blockOf(p), s = state();
    if (!b) return null;
    const lists = [];
    if (s && session && s.sessions && s.sessions[session]) lists.push((s.sessions[session].flowsheet || {}).blocks);
    if (window.WB && WB.data && WB.data.flowsheet) lists.push(WB.data.flowsheet.blocks);
    if (s && s.sessions) Object.values(s.sessions).forEach((x) => lists.push((x.flowsheet || {}).blocks));
    for (const l of lists) { const hit = (l || []).find((x) => x.name === b); if (hit && hit.type) return hit.type; }
    return null;
  }
  const keyOf = (p, type) => `${p}|${String(type || "").toUpperCase()}`;
  const reEsc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const enWord = (s) => String(s || "").replace(/\s*\(result\)$/i, "");
  const zhWord = (s) => String(s || "").replace(/（結果）$/, "");
  /** The catalog's words for a path it names ({en, zh, q}), else null. */
  function catWords(p, type) {
    const cat = catalog();
    let m = /^\\Data\\Streams\\([^\\]+)\\(.+)$/.exec(p);
    if (m) {
      for (const sp of cat.stream_props || []) {
        const mm = new RegExp("^" + reEsc(sp.path).replace(reEsc("{C}"), "([^\\\\]+)") + "$").exec(m[2]);
        if (mm && sp.label) return { en: enWord(sp.label.en), zh: zhWord(sp.label.zh), q: mm[1] ? [mm[1]] : [] };
      }
    }
    m = /^\\Data\\Blocks\\([^\\]+)\\(.+)$/.exec(p);
    if (m) {
      const params = cat.block_params || {}, own = params[String(type || "").toUpperCase()];
      for (const list of [own].concat(Object.values(params))) {
        const hit = (list || []).find((x) => x.path === m[2]);
        if (hit && hit.label) return { en: enWord(hit.label.en), zh: zhWord(hit.label.zh), q: [] };
      }
    }
    return null;
  }
  /** A stand-in loc until the server's comes: the path's parts (Data and Input dropped, Output
   *  a Results step), the catalog's words where it names the field. */
  function rough(p, type) {
    const segs = p.split("\\").filter(Boolean);
    if (segs.length > 1 && /^data$/i.test(segs[0])) segs.shift();
    const io = segs.findIndex((s) => s === "Input" || s === "Output");
    let head = io >= 0 ? segs.slice(0, io) : segs, tail = io >= 0 ? segs.slice(io + 1) : [];
    const out = io >= 0 && segs[io] === "Output";
    if (io < 0 && head.length > 2) { tail = head.slice(-1); head = head.slice(0, -1); }
    if (head[0] === "Streams" && out && tail[0] === "STR_MAIN" && tail.length > 1) tail = tail.slice(1);
    const sec = head[0] === "Properties" ? "Methods" : head[0] || null;
    const code = tail[0] || null;
    const lc = { sec, obj: head.slice(1).join(ARROW) || null, type: type || null, io: out ? "out" : "in", field: code, code,
      q: tail.slice(1).filter((s) => s !== "MIXED"), gl: null, hint: null, src: "code" };
    const w = catWords(p, type);
    if (w && w.en) Object.assign(lc, { field: w.en, gl: w.zh && w.zh !== w.en ? w.zh : null, q: w.q, src: "glossary" });
    return lc;
  }

  // ------------------------------------------------------------------ the server's names
  function start() {
    if (started) return;
    started = true;
    checkStrings();
  }
  function ask(p, type, k, session) {
    if (!api("labels") || asked.has(k)) return;
    asked.add(k);
    want.set(k, { path: p, type, session });
    if (!fetchT) fetchT = setTimeout(fetchNow, FETCH_MS);
  }
  /** One api.labels call for what is waiting (a block named twice with two types: the next). */
  function fetchNow() {
    fetchT = 0;
    const a = api("labels");
    if (!a || !want.size) return;
    const batch = [], types = {};
    for (const [k, w] of want) {
      const b = blockOf(w.path);
      if (b && w.type && types[b] && types[b] !== w.type) continue;
      if (b && w.type) types[b] = w.type;
      batch.push([k, w]);
      if (batch.length >= BATCH) break;
    }
    batch.forEach(([k]) => want.delete(k));
    const g = gen;
    Promise.resolve(a.labels({ paths: batch.map(([, w]) => w.path), types })).then((got) => {
      if (!got || typeof got !== "object" || got.error || g !== gen) return;
      let news = false;
      batch.forEach(([k, w]) => {
        const lc = got[w.path];
        if (!lc || typeof lc !== "object") return;
        const old = cache.get(k);
        if (!old || JSON.stringify(old.lc) !== JSON.stringify(lc)) news = true;
        cache.set(k, { lc, gen });
        if (lc.src === "code" && lc.code && w.session) WBL.learn(w.session, [w.path]);
      });
      if (news) bump();
    }).catch(() => {}).then(() => { if (want.size && !fetchT) fetchT = setTimeout(fetchNow, FETCH_MS); });
  }
  function bump() {
    WBL.ver++;
    if (!bumpT) bumpT = setTimeout(() => { bumpT = 0; if (typeof WBL.onChange === "function") WBL.onChange(); }, 0);
  }
  /** The server's extraction and learned names (Api.strings): once it tells of newer files,
   *  the names are asked for again. While the extraction runs, asked every 3 s (a minute or so,
   *  once per Aspen version). */
  function checkStrings() {
    const a = api("strings");
    if (!a) return;
    Promise.resolve(a.strings()).then((s) => {
      if (!s || typeof s !== "object") return;
      WBL.strings = s;
      const sig = JSON.stringify([s.state || null, s.labels_mtime ?? null, s.learned_mtime ?? null]);
      if (seenSig !== null && sig !== seenSig) { gen++; asked.clear(); bump(); }
      seenSig = sig;
      if (s.state === "running" && polls++ < 60) setTimeout(checkStrings, 3000);
    }).catch(() => {});
  }

  /** A loc for a path, at once: the server's when it came (asked again once newer names may
   *  be there), else a stand-in and the path asked for in the next batch. */
  WBL.of = function (path, type, session) {
    const p = String(path || "");
    if (!p) return null;
    start();
    const ty = type || typeOf(p, session), k = keyOf(p, ty), hit = cache.get(k);
    if (hit) {
      if (hit.gen !== gen || (hit.lc.src === "code" && hit.lc.code)) ask(p, ty, k, session);
      return hit.lc;
    }
    ask(p, ty, k, session);
    return rough(p, ty);
  };
  /** An inspector row's loc against the one cached: the better named wins (a name learned
   *  since the row was read); one still named by its code is asked to be learned. */
  WBL.best = function (path, type, given, session) {
    const p = String(path || "");
    if (!given || typeof given !== "object") return WBL.of(p, type, session);
    start();
    const ty = type || typeOf(p, session), k = keyOf(p, ty), hit = cache.get(k);
    if (!hit || rank(given) >= rank(hit.lc)) cache.set(k, { lc: given, gen: hit ? hit.gen : gen });
    const lc = cache.get(k).lc;
    if (lc.src === "code" && lc.code) {
      if (session) WBL.learn(session, [p]);
      ask(p, ty, k, session);
    }
    return lc;
  };

  /** Ask the server to learn names (the GUI prompt its Aspen gives) for fields known only by
   *  their code: one labels_learn event per session, at most 30 paths, a moment after the last
   *  request; each path once. Nothing is sent while the server is not there. */
  WBL.learn = function (session, paths) {
    if (!session || !window.wb || typeof wb.post !== "function") return;
    (paths || []).forEach((p) => {
      p = String(p || "");
      const k = `${session}|${p}`;
      if (!p.startsWith("\\Data\\") || sent.has(k)) return;
      sent.add(k);
      if (!learnQ.has(session)) learnQ.set(session, new Set());
      learnQ.get(session).add(p);
    });
    if (learnQ.size) { clearTimeout(learnT); learnT = setTimeout(flushLearn, LEARN_MS); }
  };
  function flushLearn() {
    learnT = 0;
    let more = false;
    learnQ.forEach((set, session) => {
      const paths = [...set].slice(0, LEARN_MAX);
      paths.forEach((p) => set.delete(p));
      if (!wb.connected) paths.forEach((p) => sent.delete(`${session}|${p}`));   // (asked again when it shows again)
      else if (paths.length) wb.post({ type: "labels_learn", session, paths });
      if (set.size) more = true; else learnQ.delete(session);
    });
    if (more) learnT = setTimeout(flushLearn, LEARN_MS);
    else if (wb.connected) [2500, 8000].forEach((ms) => setTimeout(checkStrings, ms));   // the names learned show
  }

  // ------------------------------------------------------------------ words
  /** The words as parts: {t, c} with c "" plain, "gl" our explanation or a result note, "code"
   *  an Aspen variable, "en" Aspen's word after ours (zh1). form: "full", "short", "name" (the
   *  field with its result note), "field". */
  function parts(lc, form, zh1) {
    lc = lc || {};
    const out = lc.io === "out", note = out && (form === "short" || form === "name");
    const leaf = [];
    if (lc.field && zh1 && zh() && lc.gl && lc.src !== "code") leaf.push({ t: String(lc.gl), c: "" }, { t: " ", c: "" }, { t: String(lc.field), c: "en" });
    else if (lc.field) {
      leaf.push({ t: String(lc.field), c: lc.src === "code" ? "code" : "" });
      const notes = zh() ? [lc.gl, note && "結果"].filter(Boolean) : [];
      if (notes.length) leaf.push({ t: `（${notes.join("，")}）`, c: "gl" });
      else if (note && !zh()) leaf.push({ t: " (result)", c: "gl" });
    }
    (lc.q || []).forEach((x) => { if (leaf.length) leaf.push({ t: DOT, c: "" }); leaf.push({ t: String(x), c: "" }); });
    let head = [];
    if (form === "short") head = [UNNAMED.has(lc.sec) || !lc.obj || String(lc.obj).includes(ARROW) ? lc.sec : lc.obj];
    else if (form === "full") head = [lc.sec, lc.obj ? (lc.type ? `${lc.obj} (${lc.type})` : lc.obj) : null, out && leaf.length ? "Results" : null];
    const all = [];
    head.filter(Boolean).forEach((h) => all.push({ t: String(h), c: "" }, { t: ARROW, c: "" }));
    if (leaf.length) all.push(...leaf); else all.pop();
    return all.map((x) => ({ t: x.t.replace(/\\/g, "/"), c: x.c }));
  }
  WBL.text = (lc, form = "short", zh1) => parts(lc, form, zh1).map((x) => x.t).join("");
  /** Its tooltip: where it is in Aspen's navigation tree, our note on it (Chinese), and a word
   *  on a field named only by its variable. */
  WBL.tip = function (lc) {
    lc = lc || {};
    const where = [lc.sec, lc.obj ? (lc.type ? `${lc.obj} (${lc.type})` : lc.obj) : null, lc.io === "out" ? "Results" : null]
      .filter(Boolean).join(ARROW).replace(/\\/g, "/");
    const lines = [t("loc_where", where || "—", [lc.field, ...(lc.q || [])].filter(Boolean).join(DOT))];
    if (zh() && lc.gl && lc.hint) lines.push(`${lc.gl}：${lc.hint}`);
    if (lc.src === "code") lines.push(t("loc_code"));
    return lines.join("\n");
  };
  WBL.html = function (lc, form = "short", o = {}) {
    const inner = parts(lc, form, o.zh1).map((x) => (x.c === "gl" ? `<small class="gl">${esc(x.t)}</small>`
      : x.c === "en" ? `<small class="en">${esc(x.t)}</small>` : x.c === "code" ? `<code class="code">${esc(x.t)}</code>` : esc(x.t))).join("");
    const tip = o.title === false ? "" : [WBL.tip(lc), o.tip].filter(Boolean).join("\n");
    return `<span class="loc"${tip ? ` title="${esc(tip)}"` : ""}>${inner}</span>`;
  };
  /** Our Chinese for a title the window shows -- a form, a sheet, a subobject collection, a model
   *  object, a palette tab -- in the Chinese interface (catalog.terms: the English, lower case), else "". */
  WBL.zhOf = (en) => (zh() && (catalog().terms || {})[String(en || "").trim().replace(/\s+/g, " ").toLowerCase()]) || "";
  /** A title in the field rows' style: Aspen's English, our Chinese beside it, quieter (markup / text);
   *  zh1: ours first, Aspen's after it, quieter. */
  WBL.title = (en, zh1) => {
    const g = WBL.zhOf(en);
    return !g ? `<span class="ttl">${esc(en)}</span>` : zh1 ? `<span class="ttl">${esc(g)} <small class="en">${esc(en)}</small></span>`
      : `<span class="ttl">${esc(en)}<small class="gl">（${esc(g)}）</small></span>`;
  };
  WBL.titleText = (en) => { const g = WBL.zhOf(en); return g ? `${en}（${g}）` : String(en ?? ""); };
  WBL.say = (path, session) => WBL.text(WBL.of(path, null, session), "short");
  WBL.full = (path, session) => WBL.text(WBL.of(path, null, session), "full");
  /** A catalog label {en, zh} (the block menus' words) in this style: "Reflux ratio（迴流比）",
   *  "Reboiler duty（再沸器熱負荷，結果）"; English "Reboiler duty (result)". */
  WBL.name = function (label) {
    if (!label || typeof label !== "object") return String(label || "");
    const out = /\(result\)\s*$/i.test(label.en || "") || /（結果）$/.test(label.zh || "");
    const en = enWord(label.en), zw = zhWord(label.zh);
    return WBL.text({ field: en || zw, gl: zw && zw !== en ? zw : null, io: out ? "out" : "in", q: [], src: "glossary" }, "name");
  };
  /** A block's field by its path under the block (Input\BASIS_RR), for a menu that lists one
   *  the program named on another block: the catalog's words for it on any block type, else
   *  its code and qualifiers ("XYZ_Q · 2"); never a backslash. */
  WBL.param = function (rel) {
    const r = String(rel || ""), cat = catalog().block_params || {};
    for (const list of Object.values(cat)) {
      const hit = (list || []).find((x) => x.path === r);
      if (hit && hit.label) return WBL.name(hit.label);
    }
    const segs = r.split("\\").filter(Boolean), out = segs[0] === "Output";
    if (segs[0] === "Input" || out) segs.shift();
    return WBL.text({ field: segs[0] || r, io: out ? "out" : "in", q: segs.slice(1).filter((s) => s !== "MIXED"), src: "code" }, "name");
  };

  // a path in running text: \Data\ and its parts (two sections have spaces in their names), up to
  // a space, a quote or a closing bracket; a sentence's full stop is not part of it
  const PATH_RE = /\\Data\\(?:Flowsheeting Options|Model Analysis Tools|[^\\\s"'<>()（）]+)(?:\\[^\\\s,;，；。、"'<>()（）[\]「」]+)*/g;
  /** Plain text as markup, each \Data\ path in it named (the path in the name's tooltip). */
  WBL.rich = function (text, session) {
    const s = String(text ?? "");
    if (!s.includes("\\Data\\")) return esc(s);
    let html = "", at = 0;
    for (const m of s.matchAll(PATH_RE)) {
      const p = m[0].replace(/[.:：]+$/, "");
      html += esc(s.slice(at, m.index)) + WBL.html(WBL.of(p, null, session), "short", { tip: p });
      at = m.index + p.length;
    }
    return html + esc(s.slice(at));
  };
})();
