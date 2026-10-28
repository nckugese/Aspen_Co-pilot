/* What Aspen still needs before it can run, like Aspen's own Next: the server reads
 * Aspen's completeness flags after every run, open and edit burst into the session's `missing`
 * ({state complete | incomplete | unknown | off, n, objects: [{path, sec, name, type, kind, what?,
 * open_ports?, and once looked at in depth: deep, n_required, n_values, n_lists, more_fields?,
 * first: [items], n_cands, cands, hints}], more, stale?, partial, pending, deep {status, n, done}}).
 * Only what the server can decide counts as missing (certainty required: an empty field a GUI rule
 * names, a port Aspen flags open); other empty fields are counted apart, and the rules matched by
 * keyword stay folded, in Aspen's own words.
 *
 * The panel (.miss-pop, a dialog that blocks nothing, at the flowsheet's top left): the objects in
 * the server's order (components and the property method first), each with its required items (a
 * click opens the inspector at the field; ⊕ makes a set block), its empty-field counts, its related
 * rules folded and its open ports; one status line with the one action it needs ("Details": the event
 * missing {tab, paths?}, the deep look at up to ten objects; "Continue" after a writer stopped it;
 * "Check again" after edits).
 *
 * The components and the property method have no field the inspector shows: without required
 * items, each says what is missing and where in Aspen it is set (Components › Specifications,
 * Methods › Specifications); the panel's one Ask AI can have the AI add them. The count in the
 * head is the server's n (the objects listed plus the ones counted past them). Going to an object
 * from the panel folds it to its head row and keeps the target clear of it.
 *
 *   WBM.of(sess)                 the session's `missing` while it says incomplete, else null
 *   WBM.open(tab, o)             the panel on tab's session (o.focus: an object's path, scrolled to), unfolded
 *   WBM.close(back)              close it; whether it was open
 *   WBM.fold()                   fold an open panel to its head row; whether it did
 *   WBM.isOpen()
 *   WBM.sync()                   a new state: redrawn, closed when its tab no longer shows
 *   WBM.check(tab, paths)        the deep look asked for (event missing)
 *   WBM.panelItems(pane, tab)    the model panel's section (menu items), [] when complete
 *   WBM.objName(o)               an object's name in words
 *   WBM.itemName(it)             an item's name in words (Aspen's English, our gloss beside it)
 *   WBM.rule(it)                 the rule under an item: {text, en, own}, or null
 */
(function () {
  "use strict";
  const WBM = (window.WBM = {});
  const { esc, icon, list, popover, sessOf, t, words, zh } = WBA;
  const st = () => (window.wb && wb.state) || null;
  const SEND_MS = 15000;          // the deep look asked: "checking…" until the server's word moves, at most this long
  const DEEP_MAX = 10;            // objects one check looks at (the server's _MISS_DEEP_MAX)

  WBM.of = (sess) => {
    const m = sess && sess.missing;
    return m && typeof m === "object" && m.state === "incomplete" && (Number(m.n) || 0) > 0 ? m : null;
  };

  // ------------------------------------------------------------------ words
  WBM.objName = function (o) {
    if (!o) return "";
    if (o.what === "components") return t("miss_comps");
    if (o.what === "method") return t("miss_method");
    if (o.what === "flowsheet") return t("miss_flowsheet");
    if (o.kind === "stream") return t("stream_n", o.name);
    if (o.kind === "block" || o.sec === "Blocks") return String(o.name || "");
    return words([o.sec, o.name].filter(Boolean).join("\\"));
  };
  WBM.itemName = function (it) {
    const base = words(it && (it.label || it.field || it.port || ""));
    return zh() && it && it.gl ? `${base}（${it.gl}）` : base;
  };
  /** The rule that makes an item required: Aspen's own text (English), or a sentence of the
   *  server's in the window's language (rule_zh: ports, the components, the method, a column's
   *  specs); `own` when it is this project's rule, not Aspen's (rule_by "server": the operating
   *  spec count), which the window marks as the workbench's. An older server: `rule` as it came. */
  WBM.rule = function (it) {
    if (!it || !it.rule) return null;
    const zhText = zh() && it.rule_zh;
    return { text: words(zhText || it.rule), en: !zhText, own: it.rule_by === "server" };
  };
  /** The words a required item's name takes where a list names a few: the field's own name. */
  const req = (o) => ((o && o.first) || []).filter((x) => x && x.certainty === "required");
  const unset = (o) => ((o && o.first) || []).filter((x) => x && x.certainty !== "required");
  const deepDone = (o) => o && (o.deep === "ok" || o.deep === "error");
  /** A count, with + where the walk stopped early (a lower bound). */
  const cnt = (n, o) => `${Number(n) || 0}${o && o.more_fields ? "+" : ""}`;
  /** How many objects are incomplete: the server's n counts every one, those listed and those
   *  past the list (more); an older state without n, the two added. */
  const total = (m) => Number(m.n) || ((m.objects || []).length + (Number(m.more) || 0));
  /** What an object without fields of its own needs, and where Aspen sets it. */
  const TODO = { components: ["miss_comps_do", "Components › Specifications", "tip_miss_comps_do", "miss_comps_part"],
                 method: ["miss_method_do", "Methods › Specifications", "tip_miss_method_do", "miss_method_part"] };
  /** The server's item for such an object itself (inputs_check: kind components | method, source
   *  empty -- none defined -- or object -- defined, still incomplete): said as that line, not as a field. */
  const ownItem = (o, it) => !!TODO[o && o.what] && !!it && it.kind === o.what && !it.field;

  // ------------------------------------------------------------------ the model panel's row
  /** One row under the model panel's state, only while inputs are missing: "Missing inputs: ESTCOL, Components …"
   *  (the first three objects), which opens the list. */
  WBM.panelItems = function (pane, tab) {
    const m = WBM.of(sessOf(tab));
    if (!m) return [];
    const objs = m.objects || [], n = total(m);
    const names = list(objs.slice(0, 3).map(WBM.objName)) + (n > 3 ? " …" : "");
    return [{ label: t("mp_missing", names), icon: "warn", cls: "mp-miss", tip: `${t("mp_miss_all", n)}\n${t("tip_mp_miss_all")}`,
      run: () => WBM.open(tab) }];
  };

  // ------------------------------------------------------------------ open, close
  let P = null;                  // the panel open: {el, tab, pane, focus, sent (a check asked), sig, open (folds), back, min (folded)}
  WBM.isOpen = () => !!P;
  WBM.open = function (tab, o = {}) {
    const pane = window.wb && wb.pane;
    if (!tab || !pane || pane.tabId !== tab.id) return false;
    WBD.close();                                                 // one card over the flowsheet at a time
    if (WBA.prefs().dockMode === "max") WBA.setDock(pane, "split");   // the flowsheet shows again
    const fresh = !P;
    if (!P) {
      // what opens it, the inspector (an item goes there), menus and dialogs over it keep it open
      const { el, off } = popover(pane.q(".fs-wrap"), "miss-pop", "miss-title", { close: (back) => WBM.close(back),
        keep: "#modelstat, .insp, #menu, #menu2, #modal, #toast, .fh-card, .uv-pop, .diag-card" });
      P = { el, off, tab: tab.id, pane, focus: null, sent: null, sig: null, open: new Set(), back: document.activeElement };
      el.addEventListener("click", onClick);
      el.addEventListener("toggle", onToggle, true);
    }
    if (P.tab !== tab.id) { P.tab = tab.id; P.sig = null; }
    if (P.min) { P.min = false; P.sig = null; }
    P.focus = o.focus || null;
    // opened before the scan says incomplete (a refused run's toast can come first): a check asked,
    // the panel says so until the answer
    const m0 = sessOf(tab).missing;
    if (!(m0 && m0.state === "incomplete") && !P.sent) WBM.check(tab);
    draw();
    if (fresh) { P.el.classList.add("in"); P.el.focus({ preventScroll: true }); }
    if (P.focus) toFocus();
    return true;
  };
  /** The panel folded to its head row (the inspector opened from it: the flowsheet shows again). */
  WBM.fold = function () {
    if (!P || P.min) return false;
    P.min = true;
    P.sig = null;
    draw();
    return true;
  };
  function unfold() {
    if (!P || !P.min) return;
    P.min = false;
    P.sig = null;
    draw();
    P.el.focus({ preventScroll: true });
  }
  WBM.close = function (back) {
    const p = P;
    if (!p) return false;
    P = null;
    p.off(back, p.back);
    return true;
  };
  /** A fold opened or closed: drawn again (a fold's contents are drawn only while it is open,
   *  so nothing folded takes the pointer), the focus kept on its summary. */
  function onToggle(ev) {
    const d = ev.target, k = d && d.dataset ? d.dataset.d : "";
    if (!P || !k || d.open === P.open.has(k)) return;
    const had = d.contains(document.activeElement);
    if (d.open) P.open.add(k); else P.open.delete(k);
    P.sig = null;
    draw();
    const s = had && [...P.el.querySelectorAll("details[data-d]")].find((x) => x.dataset.d === k);
    if (s) s.querySelector("summary").focus({ preventScroll: true });
  }
  WBM.sync = function () {
    if (!P) return;
    const pane = window.wb && wb.pane, s = st(), tab = s && (s.tabs || []).find((x) => x.id === P.tab);
    if (!tab || !pane || pane.tabId !== tab.id) { WBM.close(); return; }
    draw();
  };
  /** The object gone to: scrolled into the panel's view and flashed once. */
  function toFocus() {
    const f = P && P.focus, el = f && [...P.el.querySelectorAll(".mp-obj")].find((x) => x.dataset.path === f);
    P.focus = null;
    if (!el) return;
    P.el.scrollTop += el.getBoundingClientRect().top - P.el.getBoundingClientRect().top - 56;
    el.classList.remove("flash");
    void el.offsetWidth;
    el.classList.add("flash");
  }

  // ------------------------------------------------------------------ the check (event missing)
  WBM.check = function (tab, paths) {
    if (!tab || !(window.wb && wb.connected)) return;
    const m = sessOf(tab).missing || {};
    if (P && P.tab === tab.id && P.sent && Date.now() - P.sent.at < 1000) return;   // (a double press)
    const ev = { type: "missing", tab: tab.id };
    if (paths && paths.length) ev.paths = paths.slice(0, DEEP_MAX);
    wb.post(ev);
    if (P && P.tab === tab.id) {
      P.sent = { at: Date.now(), sig: JSON.stringify([m.deep || null, m.t || 0]) };
      clearTimeout(P.sentT);
      P.sentT = setTimeout(() => { if (P) { P.sent = null; P.sig = null; draw(); } }, SEND_MS);
      P.sig = null;
      draw();
    }
  };
  /** A check sent and not answered yet: the server's word on the session's missing has not moved. */
  function sending(m) {
    if (!P || !P.sent) return false;
    if (JSON.stringify([m.deep || null, m.t || 0]) !== P.sent.sig) { P.sent = null; clearTimeout(P.sentT); return false; }
    return Date.now() - P.sent.at < SEND_MS;
  }

  // ------------------------------------------------------------------ drawing
  /** The one status line and its action: checking (n of m, a bar that fills), waiting for Aspen,
   *  stopped midway (Continue), changed since (Check again), or Details while objects wait for
   *  their deep look. Nothing when there is nothing to say or do. */
  function statusHtml(tab, m) {
    const d = m.deep || {}, objs = m.objects || [];
    const todo = objs.filter((o) => !deepDone(o) && (o.kind || o.what)).map((o) => o.path);
    const off = !(window.wb && wb.connected), why = off ? t("why_off") : "";
    const btn = (f, label, tip, primary) => `<button class="${primary ? "mp-go" : "mp-go flat"}" data-f="${f}"${off ? " disabled" : ""} title="${esc(why || tip)}">${esc(label)}</button>`;
    if (sending(m)) return `<div class="mp-st run" role="status"><span>${esc(t("miss_sending"))}</span></div>`;
    if (d.status === "running") {
      const n = Number(d.n) || 0, k = Number(d.done) || 0;
      return `<div class="mp-st run" role="status"><span>${esc(t("miss_running", k, n))}</span>`
        + `<i class="mp-bar" aria-hidden="true"><i style="transform:scaleX(${n ? Math.min(1, k / n).toFixed(3) : 0})"></i></i></div>`;
    }
    if (d.status === "waiting") return `<div class="mp-st" role="status" title="${esc(t("tip_miss_waiting"))}"><span>${esc(t("miss_waiting"))}</span></div>`;
    if (m.partial && (m.pending || []).length) {
      return `<div class="mp-st" role="status"><span>${esc(t("miss_partial", m.pending.length))}</span>${btn("go_on", t("go_on"), t("tip_miss_check"), true)}</div>`;
    }
    if (m.stale) return `<div class="mp-st" role="status"><span title="${esc(t("tip_miss_stale"))}">${esc(t("miss_stale"))}</span>${btn("check", t("miss_recheck"), t("tip_miss_check"), false)}</div>`;
    if (todo.length) return `<div class="mp-st"><span></span>${btn("check", t("miss_check"), t("tip_miss_check"), true)}</div>`;
    return "";
  }
  /** An item: its name (a click: the inspector at the field), its rule under it (Aspen's, or the
   *  workbench's own marked so), ⊕ a set block. */
  function itemHtml(o, it) {
    const name = WBM.itemName(it), port = it.source === "port";
    const go = o.kind && (it.set || port);
    const label = port ? t("miss_port", name) : name;
    const tip = port ? [t("tip_miss_open", o.name), (it.ports || []).length > 1 ? t("tip_miss_port_any", list(it.ports)) : ""].filter(Boolean).join("\n")
      : [t("tip_miss_field"), it.where ? words(it.where) : ""].filter(Boolean).join("\n");
    const head = go ? `<button class="mp-it flat" data-f="field" data-path="${esc(it.path)}" title="${esc(tip)}"><i class="mp-dot" aria-hidden="true"></i><span class="mp-in">${esc(label)}</span></button>`
      : `<span class="mp-it"><i class="mp-dot" aria-hidden="true"></i><span class="mp-in">${esc(label)}</span></span>`;
    const blk = it.set && window.WB && WB.rowBlock ? `<button class="mp-blk flat icon" data-f="block" data-path="${esc(it.path)}" title="${esc(t("miss_block"))}" aria-label="${esc(t("miss_block"))}">${icon("add")}</button>` : "";
    const rl = WBM.rule(it), rtip = rl && [rl.text, rl.own ? t("tip_miss_rule_own") : ""].filter(Boolean).join("\n");
    const rule = rl ? `<p class="mp-rule${rl.own ? " own" : ""}"${rl.en ? ' lang="en"' : ""} title="${esc(rtip)}">`
      + `${rl.own ? `<b class="mp-by">${esc(t("miss_rule_own"))}</b>` : ""}${esc(rl.text)}</p>` : "";
    return `<li class="mp-i${it.certainty === "required" ? " req" : ""}" data-path="${esc(it.path)}">${head}${blk}${rule}</li>`;
  }
  function objHtml(o, open) {
    const all = req(o), own = all.find((it) => ownItem(o, it)), items = all.filter((it) => !ownItem(o, it)), rest = unset(o);
    const name = WBM.objName(o);
    const type = o.type && o.kind === "block" ? `<small class="mp-ty">${esc(o.type)}</small>` : "";
    const goObj = o.kind ? `<button class="mp-open flat" data-f="obj" data-path="${esc(o.path)}" title="${esc(t("tip_miss_open", name))}">${esc(t("open"))}</button>` : "";
    let h = `<section class="mp-obj" data-path="${esc(o.path)}"><div class="mp-oh"><b>${esc(name)}</b>${type}${goObj}</div>`;
    // the components, the property method: what is missing and where Aspen sets it (its empty
    // field is that same fact: not counted again)
    const todo = (own || !items.length) && TODO[o.what];
    if (todo) {
      const said = own && own.source === "object" ? todo[3] : todo[0];
      h += `<p class="mp-do" title="${esc(t(todo[2]))}"><i class="mp-dot" aria-hidden="true"></i>`
        + `<span>${esc(t(said))} · <span class="mp-at" lang="en">${esc(todo[1])}</span></span></p>`;
    }
    // the ports Aspen flags open, before the deep look names them as items
    const openPorts = !deepDone(o) ? (o.open_ports || []) : [];
    if (items.length || openPorts.length) {
      h += `<ul class="mp-l">${items.map((it) => itemHtml(o, it)).join("")}`
        + openPorts.map((p) => itemHtml(o, { path: `${o.path}\\Ports\\${p}`, label: p, port: p, source: "port", certainty: "required" })).join("") + "</ul>";
      const more = (Number(o.n_required) || 0) - items.length - (own ? 1 : 0);
      if (more > 0 && o.kind) h += `<button class="mp-more flat" data-f="obj" data-path="${esc(o.path)}" title="${esc(t("tip_miss_open", name))}">${esc(t("miss_more_req", more))}</button>`;
    }
    if (o.deep === "error") h += `<p class="mp-q">${esc(t("miss_deep_err"))}</p>`;
    // empty fields: counted apart (Aspen does not mark which are required), the first ones folded
    const nv = Number(o.n_values) || 0, nl = Number(o.n_lists) || 0;
    if (deepDone(o) && (nv || nl) && !todo) {
      const sum = [nv ? t("miss_empty", cnt(nv, o)) : "", nl ? t("miss_lists", cnt(nl, o)) : ""].filter(Boolean).join(" · ");
      const key = `e:${o.path}`, shown = rest.filter((x) => x.source !== "port");
      h += shown.length ? `<details class="mp-d" data-d="${esc(key)}"${open.has(key) ? " open" : ""}><summary title="${esc(t("tip_miss_empty"))}">${esc(sum)}</summary>`
        + (open.has(key) ? `<ul class="mp-l">${shown.map((it) => itemHtml(o, it)).join("")}</ul>` : "") + "</details>"
        : `<p class="mp-q" title="${esc(t("tip_miss_empty"))}">${esc(sum)}</p>`;
    }
    const cands = (o.cands || []).filter((c) => c && c.rule);
    if (cands.length) {
      const key = `r:${o.path}`;
      h += `<details class="mp-d" data-d="${esc(key)}"${open.has(key) ? " open" : ""}><summary title="${esc(t("tip_miss_rules"))}">${esc(t("miss_rules", Math.max(cands.length, Number(o.n_cands) || 0)))}</summary>`
        + (open.has(key) ? `<ul class="mp-rl">${cands.map((c) => `<li lang="en">${esc(words(c.rule))}</li>`).join("")}</ul>` : "") + "</details>";
    }
    if ((o.hints || []).length) h += `<p class="mp-q" title="${esc(t("tip_miss_ports"))}">${esc(t("miss_ports", list(o.hints)))}</p>`;
    if (o.rules === "loading" || o.rules === "unavailable") h += `<p class="mp-q" title="${esc(t("tip_miss_rules_off"))}">${esc(t("miss_rules_off"))}</p>`;
    return h + "</section>";
  }
  function html(tab, m) {
    const objs = m.objects || [], n = total(m);
    const un = P.min ? `<button class="mp-un flat icon" data-f="unfold" aria-expanded="false" title="${esc(t("diag_unfold"))}" aria-label="${esc(t("diag_unfold"))}">${icon("chevron-down")}</button>` : "";
    let h = `<div class="mp-h"><b id="miss-title">${esc(t("miss_title"))}</b><span class="mp-n">${esc(String(n))}</span>${un}`
      + `<button class="mp-x flat icon" data-f="close" title="${esc(t("close"))}" aria-label="${esc(t("close"))}">${icon("close")}</button></div>`;
    if (P.min) return h;
    h += statusHtml(tab, m);
    h += objs.map((o) => objHtml(o, P.open)).join("");
    if (Number(m.more) > 0) h += `<p class="mp-q mp-rest">${esc(t("miss_more_objs", m.more))}</p>`;
    // one Ask AI, small, at the foot (the structure the panel cannot fill: components, ports)
    return `${h}<div class="mp-f"><button class="mp-ask" data-f="ask" title="${esc(t("tip_miss_ask"))}">${icon("sparkle")}<span class="bt">${esc(t("ask_ai"))}</span></button></div>`;
  }
  function draw() {
    const p = P, s = st();
    if (!p || !s) return;
    const tab = (s.tabs || []).find((x) => x.id === p.tab), sess = sessOf(tab), m = sess.missing || {};
    const busy = sending(m);
    // complete now (or no longer measured): the panel has nothing to show -- unless a check it asked
    // for is still on its way (then its head and "Checking…")
    if (!tab || m.state !== "incomplete") {
      if (!tab || !busy) { WBM.close(); return; }
      const sig0 = JSON.stringify([I18N.lang, "sending"]);
      if (p.sig !== sig0) {
        p.sig = sig0;
        p.el.innerHTML = `<div class="mp-h"><b id="miss-title">${esc(t("miss_title"))}</b>`
          + `<button class="mp-x flat icon" data-f="close" title="${esc(t("close"))}" aria-label="${esc(t("close"))}">${icon("close")}</button></div>`
          + `<div class="mp-st run" role="status"><span>${esc(t("miss_sending"))}</span></div>`;
      }
      return;
    }
    const sig = JSON.stringify([I18N.lang, wb.connected, busy, m, [...p.open], !!p.min]);
    if (p.sig === sig) return;
    const top = p.el.scrollTop;
    p.sig = sig;
    p.el.classList.toggle("min", !!p.min);
    p.el.innerHTML = html(tab, m);
    p.el.scrollTop = p.min ? 0 : top;
  }

  // ------------------------------------------------------------------ what is done in it
  const objOf = (path) => { const tab = tabNow(); const m = tab && sessOf(tab).missing; return ((m && m.objects) || []).find((o) => o.path === path) || null; };
  const tabNow = () => { const s = st(); return P && s ? (s.tabs || []).find((x) => x.id === P.tab) : null; };
  function onClick(ev) {
    const b = ev.target.closest && ev.target.closest("[data-f]"), tab = tabNow();
    if (P && P.min && !b && ev.target.closest && ev.target.closest(".mp-h")) { unfold(); return; }   // (the folded head row)
    if (!P || !b || !tab || b.disabled) return;
    const f = b.dataset.f, m = sessOf(tab).missing || {};
    if (f === "close") WBM.close(true);
    else if (f === "unfold") unfold();
    else if (f === "check") WBM.check(tab, (m.objects || []).filter((o) => !deepDone(o) && (o.kind || o.what)).map((o) => o.path));
    else if (f === "go_on") WBM.check(tab, m.pending || []);
    else if (f === "obj") { const o = objOf(b.dataset.path); if (o) openObj(P.pane, tab, o); }
    else if (f === "field") openField(P.pane, tab, b.dataset.path);
    else if (f === "block") setBlock(P.pane, tab, b.dataset.path);
    else if (f === "ask") ask(P.pane, tab, m);
  }
  /** An object's inspector (its block or stream picked on the flowsheet); one no longer flagged
   *  or no longer drawn says so. The panel folds to its head row, the object kept clear of it. */
  function openObj(pane, tab, o, focus, sheet) {
    const fs = sessOf(tab).flowsheet || {};
    if (!o || !o.kind) return;
    const up = String(o.name).toUpperCase(), obj = o.kind === "object";   // (a model object: by its path)
    const hit = obj ? o : ((o.kind === "stream" ? fs.streams : fs.blocks) || []).find((x) => x && String(x.name).toUpperCase() === up);
    if (!hit) { WBA.toast(t("ch_gone", o.name), 4000); return; }
    if (WBA.prefs().dockMode === "max") WBA.setDock(pane, "split");
    const target = obj ? { kind: "object", path: o.path, name: o.name, type: o.type || o.sec } : { kind: o.kind, name: hit.name };
    WBM.fold();
    WBA.pick(pane, target, Object.assign({ ring: true }, focus ? { focus } : {}, sheet ? { sheet } : {}));
    if (P) WBD.clear(pane, target, P.el);
  }
  /** An item's field: its object's inspector, at that field -- on the item's form sheet (`at`,
   *  Aspen V15), else among the rows (the server adds the missing ones). */
  function openField(pane, tab, path) {
    const m = sessOf(tab).missing || {}, o = (m.objects || []).find((x) => path === x.path || String(path).startsWith(x.path + "\\"));
    if (!o) { WBA.toast(t("miss_gone"), 4000); return; }
    const it = (o.first || []).find((x) => x.path === path);
    openObj(pane, tab, o, /\\Ports\\/i.test(path) ? null : path, it && it.at);
  }
  /** A set block of the field, its value left empty (Check program asks for one). */
  function setBlock(pane, tab, path) {
    const m = sessOf(tab).missing || {};
    let it = null;
    (m.objects || []).forEach((o) => (o.first || []).forEach((x) => { if (x.path === path) it = x; }));
    WBA.addRow(pane, { path, value: null, unit: null, input: true, label: it ? { en: it.label, zh: it.gl || it.label } : path }, "set");
  }
  /** Ask AI about what is missing: the composer, the list in its words (nothing sent until Send). */
  function ask(pane, tab, m) {
    const names = (m.objects || []).slice(0, 6).map(WBM.objName);
    WBM.close();
    WBA.focusComposer(pane, { text: t("miss_ask_text", list(names)) });
  }
})();
