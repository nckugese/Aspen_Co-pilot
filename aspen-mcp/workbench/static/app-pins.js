/* The annotations layer on the flowsheet (btn_explain:
 * "Annotations"). What the AI said about a block or stream, from three sources:
 *
 *   Reason   its reasons: the journal's AI changes with a reason (window.py Api.journal, actors ai),
 *            of the model's last REASON_GROUPS AI change groups, REASON_PER an object (the same words
 *            on several fields of one object: one, naming the fields)
 *   Reply    its replies: the session's notes about the object that have a reply, REPLY_PER an object
 *   Note     its notes: workbench_edit highlight[].note, kept per model by the server (the session's
 *            pins {v, model, pins [{id, kind, name, text, t, tab, group?}]})
 *
 * The layer is off by default (pref wb.layer.explain "1": on); while learning mode is on
 * (learn.js WBLP.learnOn) it is on unless turned off then (wb.layer.explain.learn "0"). Its toggle
 * "Annotations" sits with the other layers in the flowsheet's capsule, only where the server keeps pins and
 * the model has something to show (or the layer is on). Off, nothing is drawn. On, each object
 * with something shows one small outlined speech bubble, no number (flowsheet.js pinMark; how
 * many: its tooltip): outside a block's bottom left, after a stream's name; violet while one is
 * not seen yet, grey once seen (wb.pins.seen.<model>). Counted beyond the edges (the edge hints,
 * app-flowsheet.js renderEdges). Turned on with none of them in view, a toast says how many
 * there are, with "Show all": the view fitted to the objects they are on (FS.fitTo: 50 % at the
 * least; spread wider, the most of them that fit; the rest counted at the edges). It sits low in
 * the flowsheet, over the edge hints, for 5 s: never over the flowsheet's toolbar.
 *
 * A click on one opens a compact frosted card beside it (.pin-card, role dialog, blocks nothing):
 * the newest CARD_MAX, each with its source (the tooltip says what it is), the field for a reason,
 * its time and one action: "Show less" for a reason or a reply (wb.pins.hide.<model>: gone until there is
 * something newer), "Remove" for a note (the event pin_hide {tab, id, model}); the foot "Show in Changes"
 * (the Changes tab, this object only). A click outside, the wheel over the drawing or Escape
 * closes it; so does the layer turned off or the object gone.
 *
 *   WBP.marks(pane, tab)   FS.render's v.pins, or null while the layer is off (app-flowsheet.js fsView)
 *   WBP.tools(pane, tab)   the toggle and the card, with each render (app-flowsheet.js renderTools)
 *   WBP.on()               the layer shows
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { changesCtx, cut, esc, fsView, icon, learning, list, prefGet, prefs, prefSet, renderTools, sessOf, setDock,
    showPanel, soon, t, tabOf, tn, toast, toastClose, wb, when } = WBA;
  const WBP = (window.WBP = {});

  const KEY = "wb.layer.explain";               // "1": the layer shows (off by default)
  const KEY_LEARN = "wb.layer.explain.learn";   // "0": not while learning mode is on (on by default then)
  const SEEN = (m) => `wb.pins.seen.${m}`;
  const HIDE = (m) => `wb.pins.hide.${m}`;
  const CARD_MAX = 5;          // items a card lists, the newest first
  const REASON_GROUPS = 3;     // the AI's latest change groups whose reasons show
  const REASON_PER = 3;        // reasons an object shows
  const REPLY_PER = 2;         // replies an object shows
  const LIMIT = 250;           // the AI's records one journal read asks for
  const KEEP = 300;            // keys the seen and hidden lists remember a model
  const TEXT = 300;            // characters an item shows (the whole in its tooltip)
  const OPS = new Set(["value", "attr", "add", "connect"]);
  const PATH_OBJ = /^\\Data\\(Blocks|Streams)\\([^\\#]+)/i;

  const isOn = () => (learning() ? prefGet(KEY_LEARN) !== "0" : prefGet(KEY) === "1");
  WBP.on = isOn;
  const okey = (kind, name) => `${kind}:${String(name).toUpperCase()}`;
  /** The model the tab's session holds (the pins', the journal's), else its session. */
  function mkey(tab) {
    const sess = sessOf(tab), j = sess.journal && typeof sess.journal === "object" ? sess.journal : null;
    return (sess.model && sess.model.id) || (j && j.model) || (sess.pins && sess.pins.model) || (sess.flowsheet || {}).model || `s:${tab.session}`;
  }
  const modelOf = (tab) => { const m = mkey(tab); return m.startsWith("s:") ? null : m; };
  /** A pref's list of keys (seen, hidden); add: the newest last, KEEP at most. */
  function keys(k) {
    try { const a = JSON.parse(prefGet(k) || "[]"); return new Set(Array.isArray(a) ? a.map(String) : []); } catch (e) { return new Set(); }
  }
  function addKeys(k, more) {
    const s = keys(k), n = s.size;
    more.forEach((x) => { s.delete(x); s.add(x); });
    if (s.size !== n || more.length) prefSet(k, JSON.stringify([...s].slice(-KEEP)));
  }
  const hash = (s) => { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0; return h.toString(36); };

  // ------------------------------------------------------------------ what there is to show
  /** The blocks and streams drawn, by key: {kind, name (as drawn), type}. */
  function drawn(tab) {
    const fs = sessOf(tab).flowsheet || {}, out = new Map();
    (fs.blocks || []).forEach((b) => { if (b && b.name) out.set(okey("block", b.name), { kind: "block", name: String(b.name), type: b.type || "" }); });
    (fs.streams || []).forEach((s) => { if (s && s.name) out.set(okey("stream", s.name), { kind: "stream", name: String(s.name), type: "" }); });
    return out;
  }
  /** The block or stream a journal record changed: [kind, name], or null. */
  function recObj(r) {
    const tg = r.target && typeof r.target === "object" ? r.target : {};
    if (r.op === "add") return tg.kind === "block" || tg.kind === "stream" ? [tg.kind, tg.name] : null;
    if (tg.block) return ["block", tg.block];
    if (tg.stream) return ["stream", tg.stream];
    const m = PATH_OBJ.exec(String(tg.path || ""));
    return m ? [/^b/i.test(m[1]) ? "block" : "stream", m[2]] : null;
  }
  /** The AI's reasons (its records, newest first, as Api.journal read them). */
  function reasons(E, names, add) {
    const recs = (E && Array.isArray(E.recs) && E.recs) || [], gids = [];
    recs.forEach((r) => {
      if (r && r.kind === "change" && r.actor === "ai" && r.group && !gids.includes(r.group) && gids.length < REASON_GROUPS) gids.push(r.group);
    });
    const per = new Map();
    recs.forEach((r) => {
      if (!r || r.kind !== "change" || r.actor !== "ai" || r.status !== "changed" || !gids.includes(r.group) || !OPS.has(r.op)) return;
      const why = typeof r.reason === "string" ? r.reason.trim() : "", o = why ? recObj(r) : null;
      const k = o && o[1] ? okey(o[0], o[1]) : "";
      if (!k || !names.has(k)) return;
      const mine = per.get(k) || per.set(k, []).get(k), tg = r.target || {};
      const path = r.op !== "add" && typeof tg.path === "string" ? tg.path : "";
      const same = mine.find((x) => x.text === why);
      if (same) {                                // the same words on another field: named with the first
        if (path && !same.paths.some((p) => p.path === path)) same.paths.push({ path, loc: r.loc || null });
        return;
      }
      if (mine.length < REASON_PER) {
        mine.push({ src: "reason", key: `r:${r.id}`, text: why, t: Number(r.t) || 0, paths: path ? [{ path, loc: r.loc || null }] : [] });
      }
    });
    per.forEach((mine, k) => mine.forEach((it) => add(k, it)));
  }
  /** The AI's replies to notes about an object (a field or a change of it counts). */
  function replies(sess, names, add) {
    const per = new Map(), notes = Array.isArray(sess.notes) ? sess.notes.slice() : [];
    notes.sort((a, b) => (Number(b && b.t) || 0) - (Number(a && a.t) || 0)).forEach((n) => {
      const reply = n && typeof n.reply === "string" ? n.reply.trim() : "", tg = (n && n.target) || {};
      const kind = tg.kind === "change" || tg.kind === "field" ? tg.obj : tg.kind;
      if (!reply || (kind !== "block" && kind !== "stream") || !tg.name) return;
      const k = okey(kind, tg.name), c = per.get(k) || 0;
      if (!names.has(k) || c >= REPLY_PER) return;
      per.set(k, c + 1);
      add(k, { src: "reply", key: `n:${n.id}:${hash(reply)}`, text: reply, q: String(n.text || ""), t: Number(n.t) || 0 });
    });
  }
  const gone = new Map();                        // pin id -> model: removed here, until the server's state drops it
  /** The AI's notes pinned on objects (the session's pins, for the model it holds). */
  function notes(sess, names, add) {
    const P = sess.pins;
    if (!P || typeof P !== "object" || !Array.isArray(P.pins)) return;
    const live = new Set();
    P.pins.forEach((p) => {
      if (!p || !p.id) return;
      const id = String(p.id);
      live.add(id);
      if (gone.has(id) || (p.kind !== "block" && p.kind !== "stream") || !p.name || !p.text) return;
      const k = okey(p.kind, p.name);
      if (names.has(k)) add(k, { src: "note", key: `p:${id}`, id, model: P.model || null, text: String(p.text), t: Number(p.t) || 0 });
    });
    gone.forEach((m, id) => { if (m === P.model && !live.has(id)) gone.delete(id); });
  }
  /** Everything to show on the tab's model, by object: {obj, items (newest first)}. all: the
   *  items put away ("Show less") too. */
  function collect(tab, all) {
    const sess = sessOf(tab), names = drawn(tab), out = new Map(), model = modelOf(tab);
    const hide = all ? null : keys(HIDE(mkey(tab)));
    const add = (k, it) => {
      if (hide && hide.has(it.key)) return;
      (out.get(k) || out.set(k, { obj: names.get(k), items: [] }).get(k)).items.push(it);
    };
    notes(sess, names, add);
    replies(sess, names, add);
    if (model) reasons(J.get(model), names, add);
    out.forEach((o) => o.items.sort((a, b) => b.t - a.t));
    return out;
  }

  // ------------------------------------------------------------------ the AI's reasons (the journal)
  const J = new Map();                           // model -> {sig, busy, recs}: its AI records, newest first
  /** Read the model's AI records again when its journal moved (the summary's n and last time):
   *  one read at a time, only where the window reads journals. */
  function journal(tab) {
    const model = modelOf(tab), api = window.pywebview && window.pywebview.api;
    if (!model || !WBC.on() || !api || typeof api.journal !== "function") return;
    const s = sessOf(tab).journal, sig = s && typeof s === "object" ? `${s.n}|${s.last_t}` : "-";
    let E = J.get(model);
    if (!E) J.set(model, (E = { sig: null, busy: false, recs: null }));
    if (E.busy || E.sig === sig) return;
    E.busy = true;
    const types = {};
    ((sessOf(tab).flowsheet || {}).blocks || []).forEach((b) => { if (b && b.name && b.type) types[b.name] = b.type; });
    let p;
    try { p = Promise.resolve(api.journal({ model, limit: LIMIT, actors: ["ai"], types })); } catch (e) { p = Promise.reject(e); }
    p.then((got) => { if (got && !got.error && Array.isArray(got.records)) E.recs = got.records; }, () => {})
      .then(() => { E.busy = false; E.sig = sig; redraw(); });
  }
  /** The drawing and the capsule again (once a frame at most). */
  function redraw() {
    soon("pins", () => {
      const pane = wb.pane, tab = pane && tabOf(pane.tabId);
      if (!tab) return;
      FS.render(pane.svg, fsView(pane, tab));
      renderTools(pane, tab);
    });
  }

  // ------------------------------------------------------------------ the markers
  WBP.marks = function (pane, tab) {
    if (!tab || !isOn()) return null;
    journal(tab);
    const seen = keys(SEEN(mkey(tab))), out = {};
    collect(tab).forEach((o, k) => {
      const n = o.items.length;
      if (!n) return;
      out[k] = { n, fresh: o.items.some((it) => !seen.has(it.key)), tip: `${tn("pin_n", n)}\n${cut(o.items[0].text, 90)}` };
    });
    return out;
  };

  // ------------------------------------------------------------------ the toggle
  /** The layer's toggle, made once beside the heat plans'; its icon is the markers' (FS.pinIcon),
   *  shown where the capsule keeps icons only. */
  function button(pane) {
    let b = pane.q('.fs-tools [data-a="explain"]');
    if (b) return b;
    const heat = pane.q('.fs-tools [data-a="heat"]');
    if (!heat) return null;
    heat.insertAdjacentHTML("afterend", `<button data-a="explain" class="tgl hidden" data-i18n="btn_explain" data-i18n-title="tip_explain" aria-pressed="false">`
      + `<i class="tdot"></i>${FS.pinIcon}<span class="bt"></span></button>`);
    b = pane.q('.fs-tools [data-a="explain"]');
    I18N.apply(heat.parentNode);
    b.addEventListener("click", () => {
      const tab = tabOf(pane.tabId);
      if (!tab) return;
      const on = !isOn();
      if (learning()) prefSet(KEY_LEARN, on ? null : "0");
      else prefSet(KEY, on ? "1" : null);
      if (!on) { closeCard(); toastClose("pins"); }
      FS.render(pane.svg, fsView(pane, tab));
      renderTools(pane, tab);
      if (on) offerAll(pane, tab);
    });
    return b;
  }
  /** Where the layer's toast goes (app-widgets.js toast's at): centred low in the free part of
   *  the flowsheet (FS.insets), above the row of edge hints and whatever else lies there under it
   *  (a lifted hint, the line of far values, the diagnosis bar), so it covers none of the toolbar;
   *  placed again once the hints are drawn for the layer just turned on. False (the usual place)
   *  where the flowsheet is too small for it. */
  const lowIn = (pane) => {
    const put = (el) => {
      const area = pane.q(".fs-area"), a = area && area.getBoundingClientRect();
      if (!a || a.width < 200 || a.height < 120) return false;
      const ins = FS.insets(pane.svg), l = a.left + ins.left, r = a.right - ins.right, x = (l + r) / 2;
      el.style.maxWidth = `${Math.round(Math.max(120, r - l - 32))}px`;
      const w = el.offsetWidth, h = el.offsetHeight;
      let bottom = a.bottom - ins.bottom - 44;     // (the hints' row: 10 px up, 26 high, 8 apart)
      [...pane.q(".pright").querySelectorAll(".fs-hint:not(.hidden), .fs-far:not(.hidden), .diag-bar:not(.hidden)")]
        .map((e) => e.getBoundingClientRect())
        .filter((b) => b.width && b.height && b.left < x + w / 2 + 8 && b.right > x - w / 2 - 8)
        .sort((p, q) => q.bottom - p.bottom)
        .forEach((b) => { if (b.bottom > bottom - h - 6 && b.top < bottom + 6) bottom = b.top - 8; });
      if (bottom - h < a.top + ins.top + 8) return false;
      el.style.left = `${Math.round(x)}px`;
      el.style.top = `${Math.round(bottom - h)}px`;
      return true;
    };
    return (el) => {
      if (!put(el)) return false;
      requestAnimationFrame(() => requestAnimationFrame(() => {
        if (wb.toastKind === "pins" && el.classList.contains("show") && el.classList.contains("low")) put(el);
      }));
      return true;
    };
  };
  /** Turned on with none of the markers wholly in the free part of the drawing (FS.insets): a
   *  toast with how many annotations there are and "Show all", the view fitted to the objects they
   *  are on (FS.fitTo: never below 50 %; spread too far for that, the most of them that fit
   *  there; what still lies beyond, the edge hints count). */
  function offerAll(pane, tab) {
    const svg = pane.svg, ms = [...svg.querySelectorAll("[data-kind] > .pinmark")];
    if (!ms.length || pane.q(".pright").classList.contains("fs-off")) return;
    const a = svg.getBoundingClientRect(), ins = FS.insets(svg);
    const inView = (r) => r.width > 0 && r.left >= a.left + ins.left && r.right <= a.right - ins.right
      && r.top >= a.top + ins.top && r.bottom <= a.bottom - ins.bottom;
    if (ms.some((m) => inView(m.getBoundingClientRect()))) return;
    const all = [...collect(tab).values()].filter((o) => o.items.length), n = all.reduce((s, o) => s + o.items.length, 0);
    const targets = all.map((o) => ({ kind: o.obj.kind, name: o.obj.name, n: o.items.length }));
    toast(t(n === 1 ? "eh_pin" : "eh_pins", n), 5000, { label: t("pin_fit"), run: () => {
      if (isOn() && pane.tabId === tab.id) FS.fitTo(svg, targets, true);
    } }, "pins", lowIn(pane));
  }
  WBP.tools = function (pane, tab) {
    wire(pane);
    const b = button(pane);
    if (!b || !tab) return;
    const on = isOn();
    journal(tab);                                // (the toggle shows only where there is something)
    const show = on || collect(tab).size > 0;
    b.classList.toggle("hidden", !show);
    b.classList.toggle("on", show && on);
    b.setAttribute("aria-pressed", String(show && on));
    sync(pane, tab);
  };

  // ------------------------------------------------------------------ the card
  let card = null;                               // {el, pane, tab, key, sig}
  /** A reason's fields, by name only (labels.js: the card's head names the object), two at most. */
  function fields(it, obj) {
    const f = (p) => WBL.html(WBL.best(p.path, obj.type || null, p.loc, null), "name", { tip: p.path });
    return list(it.paths.slice(0, 2).map(f)) + (it.paths.length > 2 ? "…" : "");
  }
  function srcTip(it) {
    if (it.src === "reply") return t("tip_pin_reply", cut(it.q, 200));
    return t(it.src === "reason" ? "tip_pin_reason" : "tip_pin_note");
  }
  const changesOn = () => WBC.on();
  /** The card's content for its object now; closed when nothing is left. */
  function fill(tab) {
    const o = collect(tab).get(card.key);
    if (!o || !o.items.length) { closeCard(); return false; }
    const items = o.items.slice(0, CARD_MAX), more = o.items.length - items.length;
    const sig = JSON.stringify([I18N.lang, items.map((it) => [it.key, it.text, it.t, it.paths ? it.paths.length : 0]), more, !!wb.connected, changesOn()]);
    if (sig === card.sig) return true;
    card.sig = sig;
    const x = t("pin_close");
    const rows = items.map((it) => {
      const n = [...it.text].length, long = n > TEXT;   // (five lines at most show: the whole in the tooltip)
      const act = it.src === "note"
        ? `<button class="flat pin-a" data-p="remove" data-id="${esc(it.id)}" title="${esc(t(wb.connected ? "tip_pin_remove" : "why_off"))}"${wb.connected ? "" : " disabled"}>${esc(t("pin_remove"))}</button>`
        : `<button class="flat pin-a" data-p="hide" data-k="${esc(it.key)}" title="${esc(t("tip_pin_hide"))}">${esc(t("pin_hide"))}</button>`;
      return `<li class="pin-it s-${it.src}"><div class="pin-m"><span class="pin-src" title="${esc(srcTip(it))}">${esc(t(`pin_${it.src}`))}</span>`
        + (it.src === "reason" && it.paths.length ? `<span class="pin-f">${fields(it, o.obj)}</span>` : "")
        + `<span class="pin-t">${esc(when(it.t))}</span>${act}</div>`
        + `<p class="pin-txt"${n > 80 ? ` title="${esc(it.text)}"` : ""}>${WBL.rich(long ? cut(it.text, TEXT) : it.text)}</p></li>`;
    }).join("");
    const foot = (more ? `<span class="pin-more">${esc(t("pin_more", more))}</span>` : "")
      + (changesOn() ? `<button class="flat pin-all" data-p="all" title="${esc(t("tip_pin_all"))}">${esc(t("pin_all"))}${icon("chevron-right")}</button>` : "");
    card.el.setAttribute("aria-label", `${o.obj.name} · ${t("btn_explain")}`);
    card.el.innerHTML = `<div class="pin-h"><b>${esc(o.obj.name)}</b><small>${esc(o.obj.kind === "block" ? o.obj.type : t("stream_word"))}</small>`
      + `<button class="flat pin-x" data-p="close" title="${esc(x)}" aria-label="${esc(x)}">${icon("close")}</button></div>`
      + `<ul class="pin-list">${rows}</ul>` + (foot ? `<div class="pin-foot">${foot}</div>` : "");
    return true;
  }
  /** The marker drawn now for the card's object (a redraw makes it again). */
  function marker(pane, key) {
    return [...pane.svg.querySelectorAll("[data-kind] > .pinmark")].find((m) => {
      const g = m.parentNode;
      return okey(g.getAttribute("data-kind"), g.getAttribute("data-name")) === key;
    }) || null;
  }
  /** Hung from its marker, clear of what it is about: under the marker, else over the object,
   *  else beside both; inside the free part of the drawing (FS.insets). */
  function place() {
    const C = card, m = C && marker(C.pane, C.key);
    if (!m) return;
    const area = C.pane.q(".fs-area").getBoundingClientRect(), ins = FS.insets(C.pane.svg), r = m.getBoundingClientRect();
    const g = m.parentNode, own = (g.querySelector(":scope > rect:not(.fam)") || g).getBoundingClientRect();
    const W = C.el.offsetWidth, H = C.el.offsetHeight, x = (v) => v - area.left, y = (v) => v - area.top;
    const minL = ins.left + 8, maxL = area.width - ins.right - W - 8, minT = ins.top + 6, maxT = area.height - ins.bottom - H - 8;
    const clampL = (v) => Math.max(minL, Math.min(v, maxL));
    let left = clampL(x(r.left) - 4), top = y(Math.max(r.bottom, own.bottom)) + 6;
    if (top > maxT) {
      top = y(Math.min(r.top, own.top)) - H - 6;
      if (top < minT) {                          // neither: beside the two, the room there
        const right = x(Math.max(r.right, own.right)) + 8, before = x(Math.min(r.left, own.left)) - W - 8;
        left = right <= maxL ? right : clampL(before);
        top = Math.max(minT, Math.min(y(r.top) - 12, maxT));
      }
    }
    C.el.style.left = `${Math.round(left)}px`;
    C.el.style.top = `${Math.round(top)}px`;
  }
  function openCard(pane, tg) {
    const tab = tabOf(pane.tabId);
    if (!tab || !isOn()) return;
    const key = okey(tg.kind, tg.name), again = card && card.key === key && card.tab === tab.id;
    closeCard();
    if (again) return;                           // (its marker again: a toggle)
    const el = document.createElement("div");
    el.className = "pin-card plate";
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-modal", "false");
    el.tabIndex = -1;
    pane.q(".fs-area").appendChild(el);
    card = { el, pane, tab: tab.id, key, sig: "" };
    el.addEventListener("click", (ev) => act(ev.target.closest("[data-p]")));
    if (!fill(tab)) return;
    place();
    const seen = collect(tab).get(key);           // what it lists is seen now: the marker goes hollow
    if (seen) addKeys(SEEN(mkey(tab)), seen.items.map((it) => it.key));
    FS.render(pane.svg, fsView(pane, tab));
    el.focus({ preventScroll: true });
  }
  function closeCard() {
    if (!card) return false;
    card.el.remove();
    card = null;
    return true;
  }
  WBP.close = closeCard;
  /** The card follows the state: another tab, the layer off, the object gone -- closed; new
   *  or fewer items -- filled again, in place. */
  function sync(pane, tab) {
    if (!card || card.pane !== pane) return;
    if (!tab || card.tab !== tab.id || !isOn() || pane.q(".pright").classList.contains("fs-off")) { closeCard(); return; }
    const h = card.el.offsetHeight;
    if (fill(tab) && card.el.offsetHeight !== h) place();
  }
  function act(btn) {
    const C = card, tab = C && tabOf(C.tab);
    if (!btn || btn.disabled || !tab) return;
    const p = btn.dataset.p, pane = C.pane;
    if (p === "close") { closeCard(); return; }
    if (p === "hide") addKeys(HIDE(mkey(tab)), [btn.dataset.k]);
    else if (p === "remove") {
      const it = ((collect(tab).get(C.key) || {}).items || []).find((x) => x.src === "note" && x.id === btn.dataset.id);
      if (!it || !wb.connected) return;
      gone.set(it.id, it.model);
      wb.post({ type: "pin_hide", tab: tab.id, id: it.id, ...(it.model ? { model: it.model } : {}) });
    } else if (p === "all") {                    // the Changes tab, this object only
      const o = collect(tab, true).get(C.key);
      closeCard();
      if (!o || !changesOn()) return;
      WBC.only(pane.q(".tab-changes"), changesCtx(pane, tab), { kind: o.obj.kind, name: o.obj.name });
      if (prefs().dockMode === "min") setDock(pane, "split");
      showPanel(pane, "changes");
      return;
    }
    FS.render(pane.svg, fsView(pane, tab));
    renderTools(pane, tab);                       // (sync fills the card again, or closes it)
  }

  /** Once a pane: the markers' clicks; a click outside the card, the wheel over the drawing and
   *  Escape close it (Escape before the page's own keys: the window's capture comes first). */
  function wire(pane) {
    if (pane._pins) return;
    pane._pins = true;
    FS.onPin(pane.svg, (tg) => openCard(pane, tg));
    pane.svg.addEventListener("wheel", () => closeCard(), { passive: true });
    document.addEventListener("pointerdown", (ev) => {
      if (card && !card.el.contains(ev.target) && !(ev.target.closest && ev.target.closest(".pinmark"))) closeCard();
    }, true);
    window.addEventListener("keydown", (ev) => {
      if (ev.key !== "Escape" || !card) return;
      const shows = (id) => { const el = document.getElementById(id); return !!el && !el.classList.contains("hidden"); };
      if (shows("menu") || shows("modal")) return;
      ev.preventDefault();
      ev.stopPropagation();
      closeCard();
    }, true);
    window.addEventListener("resize", () => { if (card) place(); });
  }
})();
