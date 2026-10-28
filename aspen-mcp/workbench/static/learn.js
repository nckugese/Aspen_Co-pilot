/* Learning mode and predictions.
 *
 * Learning mode (state.json learn {on, since, by, enforced, weak}):
 * "Learning mode", a checkbox in the review menu's "Tracking and learning" (app-brake.js brakeMenuAdd, after "Follow AI edits";
 * the ... menu has the same: brakeSwitches), posts
 * learn_mode {on}; what was asked shows until the server's state says so (WANT_MS at most). While
 * it is on, "Learning" beside the review shield (#learn-tag: its tooltip the rule, a click the review
 * menu, or the ... menu without one). The first time this viewer switches it on (pref wb.learn.intro), one tour step on Run
 * simulation's ▾ says what changes (#lp-tour, the tour's look); there is no intro card.
 *
 * Predictions (catalog.features predict, only while learning mode is on): "Predict, then run…"
 * heads Run simulation's ▾ (app-model.js simItems, wrapped here through WBA: app-pane.js looks it up
 * at call time) and opens the card under Run simulation (.lp-card, a popover that blocks nothing):
 * up to MAX results of a block or stream, picked in the card (the object follows the inspector's
 * while the card is open), each Up / Same / Down. The guesses stay in this window (prefs
 * wb.pred.<model>: {open: {id, t, items [{path, label, guess}], result?}, past [at most PAST]}):
 * the server gets only the paths (predict_watch {tab, id, paths}), reads them now (the session's
 * predict.b) and again after the session's next run, whoever made it (predict.a, state done; a run
 * that went wrong: state failed, and the watch waits for the next). Then the card compares each
 * result: its actual change, always with the amount; Matches / Differs (unchanged by the result tags'
 * thresholds, catalog.notable: 0.5 K for a temperature, 0.001 for a fraction, else 0.5 % of the larger
 * value -- a pressure's absolute; units that changed: no verdict); one "Ask AI" (a note about the
 * run, the rows that differ in words, read before it is sent). A toast says so when the card is
 * not open; a dot on the ▾ while a prediction waits. "Clear": predict_clear. No score, no rate.
 *
 *   WBLP.learnOn()   learning mode is on (as asked here, until the server says)
 *   WBLP.predOn()    predictions are offered
 *   WBLP.open(tab)   the prediction card; WBLP.close(back); WBLP.isOpen()
 *   WBLP.sync()      a new state: the tag, the dot, the card (wb.applyState, wrapped here)
 *
 * Loaded after app-brake.js (index.html): it takes what it uses from WBA by value. */
(function () {
  "use strict";
  const { $, brakeMenuAdd, closeMenus, esc, feature, flushPrefs, fmtVal, icon, num, popover, prefGet, prefSet, sessOf,
    shownTab, t, tabOf, toast, wb, who, zh } = WBA;
  const { focusComposer, runSim } = WBA.later;
  const WBLP = (window.WBLP = {});

  const MAX = 3;                 // results one prediction compares (tools/runlog.py WATCH_MAX)
  const PAST = 20;               // predictions kept to look back on
  const WANT_MS = 5000;          // learning mode as asked here, this long at most before the server says
  const INTRO = "wb.learn.intro";
  const GUESSES = ["up", "same", "down"];
  const FRAC = /FRAC(\\|$)/i;    // a fraction: compared to 0.001, not to 0.5 %
  const LOADED = Date.now() / 1000;

  // ------------------------------------------------------------------ learning mode
  const want = { on: null, at: 0 };
  /** The server's learning mode (state.json learn), or null. */
  function view() {
    const l = wb.state && wb.state.learn;
    return l && typeof l === "object" ? l : null;
  }
  function learnOn() {
    const l = view();
    if (!l) return false;
    if (want.on !== null && (!!l.on === want.on || Date.now() - want.at > WANT_MS)) want.on = null;
    return want.on !== null ? want.on : !!l.on;
  }
  const predOn = () => learnOn() && feature("predict");
  WBLP.learnOn = learnOn;
  WBLP.predOn = predOn;

  function setLearn(on) {
    if (!view() || !wb.connected) return;
    want.on = on;
    want.at = Date.now();
    wb.post({ type: "learn_mode", on });
    setTimeout(sync, WANT_MS + 50);
    sync();
    if (on && prefGet(INTRO) === null) {          // (null: unset; undefined: nothing keeps it, so never)
      prefSet(INTRO, "1");
      flushPrefs();
      setTimeout(intro, 60);
    } else toast(t(on ? "learn_on_toast" : "learn_off_toast"));
  }

  // the review menu's checkbox, in "Tracking and learning" after "Follow AI edits", where the server has learning mode
  brakeMenuAdd(() => {
    const l = view();
    if (!l) return [];
    const on = learnOn(), live = !!wb.connected;
    const tip = [t("tip_learn_mode"), l.enforced === false ? t("learn_not_enforced") : "", live ? "" : t("why_off")].filter(Boolean).join("\n");
    return [{ html: `<button class="mi lp-mi" role="menuitemcheckbox" aria-checked="${on}"${live ? "" : " disabled"} title="${esc(tip)}">`
      + `<span class="lp-box" aria-hidden="true">${icon("check")}</span><span class="bt">${esc(t("learn_mode"))}</span></button>`,
      wire: (box) => box.querySelector(".lp-mi").addEventListener("click", () => { closeMenus(); setLearn(!on); }) }];
  }, "view");

  /** "Learning" beside the review shield while learning mode is on (made the first time it shows). */
  function renderTag() {
    const l = view(), on = !!l && learnOn();
    let el = $("learn-tag");
    if (!el) {
      const at = $("ai-brake");
      if (!on || !at) return;
      el = document.createElement("button");
      el.id = "learn-tag";
      el.type = "button";
      el.className = "learn-tag";
      at.insertAdjacentElement("afterend", el);
      el.addEventListener("click", () => {
        const b = document.querySelector("#ai-brake [data-b=mode]"), more = $("btn-more");
        if (b && !b.disabled && b.offsetParent !== null) b.click();
        else if (more && WBA.brakeSwitches().length) more.click();   // no review menu: the switch is in ... too
      });
    }
    const tip = [t("tip_learn_tag"), l && l.enforced === false ? t("learn_not_enforced") : ""].filter(Boolean).join("\n");
    el.classList.toggle("hidden", !on);
    el.classList.toggle("off", !!l && l.enforced === false);
    if (el.textContent !== t("learn_tag")) el.textContent = t("learn_tag");
    if (el.title !== tip) el.title = tip;
  }

  // ------------------------------------------------------------------ the tour step (once)
  let tour = null;               // {el, at, back}
  /** The element's box where it shows, else null. */
  function shows(el) {
    if (!el || !el.isConnected) return null;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1 && r.right > 0 && r.bottom > 0 && r.left < innerWidth && r.top < innerHeight ? r : null;
  }
  /** Run simulation's ▾ (where "Predict, then run…" is), else the header's "Learning". */
  function introAt() {
    const more = $("bar").querySelector('[data-a="run_sim_menu"]'), tag = $("learn-tag");
    return predOn() && shows(more) ? more : shows(tag) ? tag : null;
  }
  function intro() {
    const at = introAt();
    if (!at || wb.tour) return;                   // (the beginner tour open: it says enough)
    introClose();
    const el = document.createElement("div");
    el.id = "lp-tour";
    el.className = "tour-layer lp-tour";
    el.innerHTML = `<div class="tour-ring" aria-hidden="true"></div>`
      + `<div class="tour-card plate cov-pop" role="dialog" aria-modal="false" aria-labelledby="lp-tour-t" aria-describedby="lp-tour-b">`
      + `<div class="tc-title" id="lp-tour-t">${esc(t("tour_learn_t"))}</div>`
      + `<div class="tc-body" id="lp-tour-b">${esc(t(at.dataset.a === "run_sim_menu" ? "tour_learn_b" : "tour_learn_b_nopred"))}</div>`
      + `<div class="tc-row"><span class="grow"></span><button class="primary" data-lt="done">${esc(t("tour_done"))}</button></div></div>`;
    document.body.appendChild(el);
    tour = { el, at, back: document.activeElement };
    el.querySelector("[data-lt=done]").addEventListener("click", () => introClose(true));
    document.addEventListener("keydown", introKey, true);
    window.addEventListener("resize", introPlace);
    introPlace();
    el.querySelector("[data-lt=done]").focus({ preventScroll: true });
  }
  /** The ring around its anchor, the card under it, its right edge at the anchor's (inside the window). */
  function introPlace() {
    if (!tour) return;
    const at = shows(tour.at) ? tour.at : introAt();
    if (!at) { introClose(); return; }
    tour.at = at;
    const r = at.getBoundingClientRect(), vw = innerWidth, vh = innerHeight, m = 12;
    const ring = { l: Math.max(2, r.left - 6), t: Math.max(2, r.top - 6), r: Math.min(vw - 2, r.right + 6), b: Math.min(vh - 2, r.bottom + 6) };
    Object.assign(tour.el.querySelector(".tour-ring").style, { left: `${ring.l}px`, top: `${ring.t}px`,
      width: `${ring.r - ring.l}px`, height: `${ring.b - ring.t}px` });
    const c = tour.el.querySelector(".tour-card"), w = c.offsetWidth, h = c.offsetHeight;
    const x = Math.max(m, Math.min(r.right - w, vw - w - m)), y = Math.max(m, Math.min(ring.b + 14, vh - h - m));
    c.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
  }
  function introKey(ev) {
    if (!tour || ev.key !== "Escape" || ev.isComposing) return;
    ev.preventDefault();
    ev.stopPropagation();
    introClose(true);
  }
  function introClose(back) {
    const c = tour;
    if (!c) return;
    tour = null;
    document.removeEventListener("keydown", introKey, true);
    window.removeEventListener("resize", introPlace);
    const had = c.el.contains(document.activeElement);
    c.el.remove();
    if (back && had && c.back && c.back.isConnected && c.back !== document.body && c.back.focus) c.back.focus({ preventScroll: true });
  }

  // ------------------------------------------------------------------ predictions: this window's
  const mem = {};                // model -> its predictions (the prefs' copy)
  const armed = new Set();       // prediction ids this page has asked the server to watch
  const modelOf = (tab) => { const s = sessOf(tab); return String((s.model && s.model.id) || (s.flowsheet && s.flowsheet.model) || (tab && tab.session) || ""); };
  const newId = () => `p${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  const itemOk = (x) => !!x && typeof x.path === "string" && x.path.startsWith("\\Data\\");
  function store(model) {
    if (mem[model]) return mem[model];
    let o = null;
    try { o = JSON.parse(prefGet(`wb.pred.${model}`) || "null"); } catch (e) { o = null; }
    o = o && typeof o === "object" && !Array.isArray(o) ? o : {};
    const open = o.open && typeof o.open === "object" && Array.isArray(o.open.items) ? o.open : null;
    if (open) {
      open.items = open.items.filter(itemOk).slice(0, MAX).map((x) => ({ path: x.path, label: String(x.label || ""), guess: GUESSES.includes(x.guess) ? x.guess : null }));
      open.id = String(open.id || newId()).slice(0, 40);
    }
    return (mem[model] = { open, past: Array.isArray(o.past) ? o.past.slice(-PAST) : [] });
  }
  const keep = (model) => { const o = mem[model]; if (o) prefSet(`wb.pred.${model}`, JSON.stringify({ open: o.open, past: o.past.slice(-PAST) })); };
  /** Tell the server which results to read now and after the next run (never a guess). */
  function watch(tab, o) {
    if (!wb.connected || !o.open) return;
    armed.add(o.open.id);
    if (o.open.items.length) wb.post({ type: "predict_watch", tab: tab.id, id: o.open.id, paths: o.open.items.map((x) => x.path) });
    else wb.post({ type: "predict_clear", tab: tab.id });
  }
  /** The session's measurement of this prediction, or null. */
  const spOf = (tab, o) => { const sp = sessOf(tab).predict; return o.open && sp && typeof sp === "object" && sp.id === o.open.id ? sp : null; };

  /** A new state for the shown tab: a finished measurement becomes the prediction's result (kept,
   *  and said once in a toast when the card is not open); a prediction the server no longer
   *  watches (restarted, another window cleared it) is asked for again, once a page. */
  function track(tab) {
    const model = modelOf(tab), o = store(model), open = o.open;
    if (!open || open.result || !open.items.length) return;
    const sp = spOf(tab, o);
    if (sp && sp.state === "done" && sp.a && typeof sp.a === "object") {
      const got = (m, p) => (m && Object.prototype.hasOwnProperty.call(m, p) ? m[p] : null);
      open.result = { run: sp.run || null, seq: num(sp.seq) ? sp.seq : null, by: sp.by || null, at: num(sp.at) ? sp.at : null,
        model: sp.model || model, items: open.items.map((x) => ({ path: x.path, b: got(sp.b, x.path), a: got(sp.a, x.path) })) };
      o.past.push(JSON.parse(JSON.stringify(open)));
      o.past = o.past.slice(-PAST);
      keep(model);
      if (!(C && C.tab === tab.id) && (open.result.at || 0) >= LOADED - 5) {
        toast(t("pred_toast"), 6000, { label: t("pred_see"), run: () => WBLP.open(shownTab()) }, "pred");
      }
      return;
    }
    if (!sp && wb.connected && !armed.has(open.id)) watch(tab, o);
    else if (sp) armed.add(open.id);
  }

  // ------------------------------------------------------------------ words
  const plain = (label) => String(I18N.pick(label) || "").replace(/（結果）$/, "").replace(/\s*\(result\)$/i, "");
  const words = (path, fallback) => WBL.say(path) || fallback || path;
  const valText = (v, u) => `${fmtVal(v)}${u ? ` ${u}` : ""}`;
  const delta = (d, u) => `${d > 0 ? "+" : d < 0 ? "−" : "±"}${Number(Math.abs(d).toPrecision(3))}${u ? ` ${u}` : ""}`;
  /** The value now: the server's reading, else the flowsheet's stream values or the inspector's row. */
  function nowOf(tab, path, sp) {
    if (sp && sp.b && Object.prototype.hasOwnProperty.call(sp.b, path)) {
      const v = sp.b[path];
      return Array.isArray(v) ? { text: valText(v[0], v[1]) } : { text: t("pred_gone"), cls: "gone" };
    }
    const m = /^\\Data\\Streams\\([^\\]+)\\Output\\(RES_TEMP|RES_PRES|TOT_FLOW)$/.exec(path);
    const sv = m && (sessOf(tab).values || {})[m[1]], k = m && { RES_TEMP: "t", RES_PRES: "p", TOT_FLOW: "f" }[m[2]];
    if (sv && Array.isArray(sv[k])) return { text: valText(sv[k][0], sv[k][1]) };
    const r = tab.inspect && (tab.inspect.rows || []).find((x) => x && x.path === path);
    if (r && r.value !== undefined && r.value !== null && r.value !== "") return { text: valText(r.value, r.unit) };
    return { text: t("pred_reading"), cls: "wait" };
  }
  /** How a result moved against the guess: {kind "ok", act, d, vb, va, u, match (null: no guess)},
   *  {kind "units", …} (no verdict) or {kind "gone"} (not in the model, or not a number). */
  function verdict(path, guess, b, a) {
    if (!Array.isArray(b) || !Array.isArray(a) || !num(b[0]) || !num(a[0])) return { kind: "gone" };
    const [vb, ub] = b, [va, ua] = a;
    if (ub && ua && ub !== ua) return { kind: "units", vb, va, ub, ua };
    const d = va - vb, tol = FRAC.test(path) ? 0.001 : 0.005 * Math.max(Math.abs(va), Math.abs(vb));
    // (the result tags' thresholds, the server's catalog.notable -- a temperature by 0.5 K)
    const same = WBA.fxSame ? WBA.fxSame(path, ua || ub, vb, va) : Math.abs(d) <= tol;
    const act = same ? "same" : d > 0 ? "up" : "down";
    return { kind: "ok", act, d, vb, va, u: ua || ub || "", match: GUESSES.includes(guess) ? guess === act : null };
  }

  // ------------------------------------------------------------------ the picker
  const split = (v) => { const i = String(v || "").indexOf(":"); return i < 0 ? ["", ""] : [v.slice(0, i), v.slice(i + 1)]; };
  function objects(tab) {
    const fs = sessOf(tab).flowsheet || {};
    return { streams: (fs.streams || []).filter((s) => s && s.name).map((s) => s.name), blocks: (fs.blocks || []).filter((b) => b && b.name) };
  }
  const prefix = (kind, name) => `\\Data\\${kind === "stream" ? "Streams" : "Blocks"}\\${name}\\`;
  /** The results a block or stream offers: [{rel, label, comp}] (rel under its path; comp: a
   *  component goes in {C}): the catalog's, then the inspector's own result rows for it. */
  function fields(tab, obj) {
    const [kind, name] = split(obj), cat = (wb.state && wb.state.catalog) || {}, out = [], seen = new Set();
    const add = (rel, label, comp) => { if (rel && !seen.has(rel)) { seen.add(rel); out.push({ rel, label: label || rel, comp: !!comp }); } };
    if (kind === "stream") (cat.stream_props || []).filter((p) => p && !p.input).forEach((p) => add(p.path, plain(p.label), p.comp));
    else if (kind === "block") {
      const b = objects(tab).blocks.find((x) => x.name === name), type = b ? String(b.type || "").toUpperCase() : "";
      ((cat.block_params || {})[type] || []).filter((p) => p && /^Output\\/.test(p.path)).forEach((p) => add(p.path, plain(p.label)));
    }
    const ins = tab.inspect, pre = prefix(kind, name);
    if (ins && ins.target && ins.target.kind === kind && ins.target.name === name) {
      (ins.rows || []).filter((r) => r && !r.input && typeof r.path === "string" && r.path.startsWith(pre) && r.value != null && r.value !== "" && num(Number(r.value)))
        .slice(0, 40).forEach((r) => add(r.path.slice(pre.length), r.loc ? WBL.text(r.loc, "field") : plain(r.label)));
    }
    return out;
  }
  const fullPath = (obj, rel, comp) => { const [kind, name] = split(obj); return prefix(kind, name) + (rel.includes("{C}") ? rel.replace("{C}", comp || "") : rel); };
  /** The inspector's block or stream on this tab ("stream:PRODUCT"), or null. */
  function inspected(tab) {
    const rec = wb.recs && wb.recs.get(tab.id), tg = (rec && rec.insp && rec.insp.target) || tab.selection;
    return tg && (tg.kind === "stream" || tg.kind === "block") && tg.name ? `${tg.kind}:${tg.name}` : null;
  }
  /** What the picker shows: its object (the inspector's when it changes, else the one chosen, else
   *  a product stream), a result of it and a component where the result needs one. */
  function pick(tab) {
    const pk = C.pick || (C.pick = {}), ob = objects(tab);
    const has = (v) => { const [k, n] = split(v); return k === "stream" ? ob.streams.includes(n) : k === "block" && ob.blocks.some((b) => b.name === n); };
    const ins = inspected(tab);
    if (ins !== C.ins) { C.ins = ins; if (ins && has(ins) && ins !== pk.obj) { pk.obj = ins; pk.rel = null; } }
    if (!pk.obj || !has(pk.obj)) {
      const prod = ((sessOf(tab).flowsheet || {}).streams || []).find((s) => s && s.from && !s.to);
      pk.obj = ins && has(ins) ? ins : prod ? `stream:${prod.name}` : ob.streams.length ? `stream:${ob.streams[0]}` : ob.blocks.length ? `block:${ob.blocks[0].name}` : null;
      pk.rel = null;
    }
    const fl = pk.obj ? fields(tab, pk.obj) : [];
    if (!fl.some((x) => x.rel === pk.rel)) pk.rel = fl.length ? fl[0].rel : null;
    const comps = (sessOf(tab).flowsheet || {}).components || [];
    if (!comps.includes(pk.comp)) pk.comp = comps[0] || null;
    return { pk, fl, f: fl.find((x) => x.rel === pk.rel) || null, comps };
  }

  // ------------------------------------------------------------------ the card
  let C = null;                  // the card open: {el, tab, session, sig, back, pick, ins}
  WBLP.isOpen = () => !!C;
  const running = (tab) => (sessOf(tab).sim || {}).status === "running";
  /** Run simulation in the header: whether it can run now, and why not (app-model.js keeps it). */
  function simBtn() {
    const b = $("bar").querySelector('[data-a="run_sim"]');
    return { off: !b || b.disabled || !wb.connected, why: (b && b.disabled && b.title) || (!wb.connected ? t("why_off") : "") };
  }

  function headHtml(title, tip, sub) {
    return `<div class="cov-h lp-h"><b id="lp-title"${tip ? ` title="${esc(tip)}"` : ""}>${esc(title)}</b>${sub ? `<small>${esc(sub)}</small>` : ""}`
      + `<button class="cov-x flat icon" data-p="close" title="${esc(t("close"))}" aria-label="${esc(t("close"))}">${icon("close")}</button></div>`;
  }
  function editHtml(tab, o, sp) {
    const busy = running(tab), items = o.open.items;
    const rows = items.map((it, i) => {
      const lab = words(it.path, it.label), now = nowOf(tab, it.path, sp);
      const seg = GUESSES.map((g) => `<button class="lp-g${it.guess === g ? " on" : ""}" role="radio" aria-checked="${it.guess === g}" data-g="${g}" data-i="${i}"${busy ? " disabled" : ""}>`
        + `${esc(t(`pred_${g}`))}</button>`).join("");
      return `<li class="lp-r"><span class="lp-l" title="${esc(lab)}">${esc(lab)}</span>`
        + `<span class="lp-v${now.cls ? ` ${now.cls}` : ""}" title="${esc(t("pred_now_tip"))}">${esc(now.text)}</span>`
        + `<span class="lp-seg" role="radiogroup" aria-label="${esc(lab)}">${seg}</span>`
        + `<button class="lp-rm flat icon" data-p="rm" data-i="${i}"${busy ? " disabled" : ""} title="${esc(t("pred_remove"))}" aria-label="${esc(t("pred_remove"))}">${icon("close")}</button></li>`;
    }).join("");
    let add = "";
    const ob = objects(tab);
    if (items.length < MAX && (ob.streams.length || ob.blocks.length)) {
      const { pk, fl, f, comps } = pick(tab);
      const opt = (v, label, sel) => `<option value="${esc(v)}"${sel ? " selected" : ""}>${esc(label)}</option>`;
      const sel = (key, tip, body, dis) => `<select class="lp-s lp-s-${key}" data-s="${key}" title="${esc(tip)}" aria-label="${esc(tip)}"${dis ? " disabled" : ""}>${body}</select>`;
      const objs = (ob.streams.length ? `<optgroup label="${esc(t("pred_streams"))}">${ob.streams.map((n) => opt(`stream:${n}`, n, pk.obj === `stream:${n}`)).join("")}</optgroup>` : "")
        + (ob.blocks.length ? `<optgroup label="${esc(t("pred_blocks"))}">${ob.blocks.map((b) => opt(`block:${b.name}`, b.name, pk.obj === `block:${b.name}`)).join("")}</optgroup>` : "");
      const path = f && (!f.comp || pk.comp) ? fullPath(pk.obj, f.rel, pk.comp) : null, dup = !!path && items.some((x) => x.path === path);
      add = `<div class="lp-add">${sel("obj", t("pred_obj"), objs, busy)}`
        + sel("rel", t("pred_field"), fl.length ? fl.map((x) => opt(x.rel, x.label, x.rel === pk.rel)).join("") : opt("", t("pred_none_out"), true), busy || !fl.length)
        + (f && f.comp ? sel("comp", t("pred_comp"), comps.map((c) => opt(c, c, c === pk.comp)).join(""), busy) : "")
        + `<button class="lp-plus" data-p="add"${!path || dup || busy ? " disabled" : ""} title="${esc(dup ? t("pred_dup") : t("tip_pred_add"))}">${icon("plus")}<span class="bt">${esc(t("pred_add"))}</span></button></div>`;
    }
    const failed = sp && sp.state === "failed" ? `<p class="lp-note">${icon("warn")}<span>${esc(t("pred_failed"))}</span></p>` : "";
    const sim = simBtn(), need = !items.length || items.some((x) => !x.guess);
    const why = sim.off ? sim.why : need ? t(items.length ? "pred_need" : "pred_need0") : "";
    const clear = items.length ? `<button class="flat lp-clear" data-p="clear" title="${esc(t("tip_pred_clear"))}"${busy ? " disabled" : ""}>${esc(t("pred_clear"))}</button>` : "";
    return headHtml(t("pred_title"), t("tip_pred_title"))
      + (rows ? `<ul class="lp-rows">${rows}</ul>` : "") + add + failed
      + `<div class="lp-f">${clear}<span class="grow"></span><button class="primary lp-run" data-p="run"${why ? " disabled" : ""} title="${esc(why || t("tip_run_sim"))}">`
      + `${icon("play")}<span class="bt">${esc(t("run_sim"))}</span></button></div>`;
  }
  function resHtml(tab, o) {
    const r = o.open.result, by = r.by && r.by.actor && r.by.actor !== "user" ? t("pred_by", who(r.by.actor)) : "";
    let differs = false;
    const rows = o.open.items.map((it, i) => {
      const x = r.items[i] || {}, v = verdict(it.path, it.guess, x.b, x.a), lab = words(it.path, it.label);
      const guess = GUESSES.includes(it.guess) ? t(`pred_${it.guess}`) : "—";
      let mid, tip = "", vd = "";
      if (v.kind === "ok") {
        mid = `<span class="lp-gs">${esc(guess)}</span> <span class="lp-ar">→</span> <b>${esc(t(`pred_${v.act}`))}</b> <span class="lp-d">${esc(delta(v.d, v.u))}</span>`;
        tip = `${valText(v.vb, v.u)} → ${valText(v.va, v.u)}`;
        if (v.match !== null) vd = `<span class="lp-vd ${v.match ? "ok" : "bad"}">${esc(t(v.match ? "pred_same_as" : "pred_diff"))}</span>`;
        if (v.match === false) differs = true;
      } else if (v.kind === "units") {
        mid = `<span class="lp-gs">${esc(guess)}</span> <span class="lp-ar">→</span> <span class="lp-q">${esc(t("pred_units", v.ub, v.ua))}</span>`;
        tip = `${valText(v.vb, v.ub)} → ${valText(v.va, v.ua)}`;
        vd = `<span class="lp-vd">${esc(t("pred_cant"))}</span>`;
      } else {
        mid = `<span class="lp-gs">${esc(guess)}</span> <span class="lp-ar">→</span> <span class="lp-q">${esc(t("pred_gone"))}</span>`;
        vd = `<span class="lp-vd">${esc(t("pred_cant"))}</span>`;
      }
      return `<li class="lp-r res"><span class="lp-l" title="${esc(lab)}">${esc(lab)}</span><span class="lp-c"${tip ? ` title="${esc(tip)}"` : ""}>${mid}</span>${vd}</li>`;
    }).join("");
    const ask = differs
      ? `<button class="lp-ask" data-p="ask" title="${esc(t("tip_pred_why"))}">${icon("sparkle")}<span class="bt">${esc(t("pred_why"))}</span></button>` : "";
    const title = [t("pred_title"), num(r.seq) ? t("diag_lbl_run", r.seq) : ""].filter(Boolean).join(" · ");
    return headHtml(title, t("tip_pred_title"), by)
      + `<ul class="lp-rows res">${rows}</ul>`
      + `<div class="lp-f"><button class="flat lp-again" data-p="again" title="${esc(t("tip_pred_again"))}">${esc(t("pred_again"))}</button><span class="grow"></span>${ask}</div>`;
  }

  WBLP.open = function (tab) {
    if (!tab || !predOn() || !wb.pane || wb.pane.tabId !== tab.id) return false;
    closeMenus();
    introClose();
    if (C && C.tab !== tab.id) WBLP.close();
    const model = modelOf(tab), o = store(model);
    if (!o.open) { o.open = { id: newId(), t: Date.now() / 1000, items: [] }; keep(model); }
    if (!C) {
      // a press outside closes it; not one on the flowsheet or its inspector (picking a block or
      // stream there fills the picker), Run simulation, a menu, a dialog or the toast
      const { el, off } = popover(document.body, "cov-pop lp-card", "lp-title", { close: (back) => WBLP.close(back), place,
        keep: ".simrun, .fs-wrap, .insp, #menu, #menu2, #modal, #toast, #lp-tour, #learn-tag" });
      C = { el, off, back: document.activeElement, pick: null, ins: undefined };
      el.addEventListener("click", onClick);
      el.addEventListener("change", onChange);
    }
    Object.assign(C, { tab: tab.id, session: tab.session, sig: null });
    draw();
    renderDot();
    if (C) C.el.focus({ preventScroll: true });
    return true;
  };
  WBLP.close = function (back) {
    const c = C;
    if (!c) return false;
    C = null;
    c.off(back, c.back);
    const tab = tabOf(c.tab);
    if (tab) {                                     // a prediction with nothing in it is not kept
      const model = modelOf(tab), o = store(model);
      if (o.open && !o.open.items.length && !o.open.result) { o.open = null; keep(model); }
    }
    renderDot();
    return true;
  };
  /** Under Run simulation, its right edge at the group's (inside the window); taller than the
   *  room below: it scrolls. */
  function place() {
    if (!C) return;
    const g = $("bar").querySelector(".simrun"), r = shows(g) || $("bar").getBoundingClientRect();
    const el = C.el, w = el.offsetWidth, vw = innerWidth, vh = innerHeight, y = Math.round(r.bottom + 6);
    el.style.left = `${Math.round(Math.max(8, Math.min(r.right - w, vw - w - 8)))}px`;
    el.style.top = `${y}px`;
    el.style.maxHeight = `${Math.max(120, vh - y - 12)}px`;
  }
  /** The control that had the focus, found again after the card is drawn anew. */
  function focusKey() {
    const a = document.activeElement;
    if (!C || !a || !C.el.contains(a)) return null;
    return ["p", "g", "s", "i"].map((k) => (a.dataset && a.dataset[k] ? `[data-${k}="${a.dataset[k]}"]` : "")).join("") || null;
  }
  function draw() {
    if (!C) return;
    const tab = tabOf(C.tab);
    if (!tab || !predOn() || !wb.pane || wb.pane.tabId !== tab.id) { WBLP.close(); return; }
    const o = store(modelOf(tab));
    if (!o.open) o.open = { id: newId(), t: Date.now() / 1000, items: [] };
    const sp = spOf(tab, o), sim = simBtn();
    if (!o.open.result && o.open.items.length < MAX) pick(tab);
    const fs = sessOf(tab).flowsheet || {};
    const sig = JSON.stringify([I18N.lang, o.open, sp && [sp.state, sp.b], C.pick, wb.connected, running(tab), sim, (fs.blocks || []).length,
      (fs.streams || []).length, (fs.components || []).length, tab.inspect && [tab.inspect.target, tab.inspect.t], WBL.ver]);
    if (C.sig === sig) return;
    C.sig = sig;
    const fk = focusKey(), top = C.el.scrollTop;
    C.el.innerHTML = o.open.result ? resHtml(tab, o) : editHtml(tab, o, sp);
    C.el.classList.toggle("res", !!o.open.result);
    C.el.scrollTop = top;
    const back = fk && C.el.querySelector(fk);
    if (back && !back.disabled) back.focus({ preventScroll: true });
    else if (fk) C.el.focus({ preventScroll: true });
    place();
  }

  // ------------------------------------------------------------------ what is done in it
  function current() {
    const tab = C && tabOf(C.tab);
    if (!tab) return null;
    const model = modelOf(tab);
    return { tab, model, o: store(model) };
  }
  function onClick(ev) {
    const b = ev.target.closest && ev.target.closest("button"), cur = current();
    if (!b || b.disabled || !cur) return;
    const { tab, model, o } = cur, open = o.open;
    if (b.dataset.g) {                              // a guess
      const it = open && open.items[Number(b.dataset.i)];
      if (!it || open.result) return;
      it.guess = b.dataset.g;
      keep(model);
      draw();
      return;
    }
    const p = b.dataset.p;
    if (p === "close") WBLP.close(true);
    else if (p === "add") {
      const { pk, f } = pick(tab);
      if (!f || (f.comp && !pk.comp) || !open || open.result || open.items.length >= MAX) return;
      const path = fullPath(pk.obj, f.rel, pk.comp);
      if (open.items.some((x) => x.path === path)) return;
      open.items.push({ path, label: words(path), guess: null });
      const next = pick(tab).fl.find((x) => !x.comp && !open.items.some((y) => y.path === fullPath(pk.obj, x.rel)));
      if (next) pk.rel = next.rel;                 // (the picker moves on to a result not taken yet)
      keep(model);
      watch(tab, o);
      draw();
    } else if (p === "rm") {
      if (!open || open.result) return;
      open.items.splice(Number(b.dataset.i), 1);
      keep(model);
      watch(tab, o);
      draw();
    } else if (p === "clear") {
      o.open = { id: newId(), t: Date.now() / 1000, items: [] };
      keep(model);
      if (wb.connected) wb.post({ type: "predict_clear", tab: tab.id });
      draw();
    } else if (p === "again") {                     // the same results, new guesses, measured anew
      o.open = { id: newId(), t: Date.now() / 1000, items: (open ? open.items : []).map((x) => ({ path: x.path, label: x.label, guess: null })) };
      keep(model);
      watch(tab, o);
      draw();
    } else if (p === "run") runSim(tab);
    else if (p === "ask") ask(tab, o);
  }
  function onChange(ev) {
    const s = ev.target.closest && ev.target.closest("select[data-s]");
    if (!s || !C) return;
    const pk = C.pick || (C.pick = {});
    pk[s.dataset.s] = s.value;
    if (s.dataset.s === "obj") pk.rel = null;
    draw();
  }
  /** "Ask AI" about the rows that differ: a note on the run (a server that takes one), its words
   *  in the box to read before Send; nothing is sent here. */
  function ask(tab, o) {
    const r = o.open.result;
    if (!r) return;
    const rows = [];
    o.open.items.forEach((it, i) => {
      const x = r.items[i] || {}, v = verdict(it.path, it.guess, x.b, x.a);
      if (v.kind === "ok" && v.match === false) {
        rows.push(t("pred_ask_row", words(it.path, it.label), t(`pred_${it.guess}`), `${t(`pred_${v.act}`)} ${delta(v.d, v.u)}`));
      }
    });
    if (!rows.length) return;
    const text = t("pred_ask_text", rows.join(zh() ? "；" : "; "));
    const label = num(r.seq) ? t("diag_lbl_run", r.seq) : t("pred_title");
    const pin = r.run && r.model ? { pin: { target: { kind: "run", id: r.run, model: r.model, label } } } : {};
    const pane = wb.pane;
    WBLP.close();
    focusComposer(pane, Object.assign(pin, { text }));
  }

  // ------------------------------------------------------------------ the header's dot, and sync
  /** A dot on Run simulation's ▾ while a prediction waits for its run (not while the card shows it). */
  function renderDot() {
    const more = $("bar") && $("bar").querySelector('[data-a="run_sim_menu"]');
    if (!more) return;
    const tab = shownTab();
    let n = 0;
    if (tab && wb.state && predOn() && !C) {
      const o = store(modelOf(tab));
      if (o.open && !o.open.result) n = o.open.items.length;
    }
    let d = more.querySelector(".lp-dot");
    if (!n) { if (d) d.remove(); return; }
    if (!d) {
      more.insertAdjacentHTML("beforeend", `<i class="lp-dot"></i>`);
      d = more.querySelector(".lp-dot");
    }
    const tip = t(n === 1 && !zh() ? "pred_dot_1" : "pred_dot", n);
    if (d.title !== tip) { d.title = tip; d.setAttribute("aria-label", tip); d.setAttribute("role", "img"); }
  }
  function sync() {
    if (!wb.state) return;                        // (the first state comes after the prefs file: loadPrefs)
    renderTag();
    const tab = shownTab();
    if (tab && predOn()) track(tab);
    renderDot();
    if (C) draw();
    if (tour) introPlace();
  }
  WBLP.sync = sync;

  // ------------------------------------------------------------------ hooks
  // Run simulation's ▾: "Predict, then run…" first, while predictions are offered (app-pane.js calls
  // simItems through WBA.later, so it finds this one)
  const simItems = WBA.simItems;
  WBA.simItems = function (tab) {
    const items = typeof simItems === "function" ? simItems(tab) : [];
    if (!tab || !predOn()) return items;
    return [{ label: t("pred_menu"), icon: "target", tip: t("tip_pred_menu"), cls: "lp-menu", run: () => WBLP.open(tab) }, ...items];
  };
  // every new state, and the connection coming or going; better field names (labels.js)
  const applyState = wb.applyState;
  // (its own part of the update: a fault is logged once and counted, WBA.guard)
  wb.applyState = function (s) {
    applyState.call(this, s);
    WBA.guard("learn", sync);
  };
  const setConnected = wb.setConnected;
  if (typeof setConnected === "function") {
    wb.setConnected = function (alive) {
      setConnected.call(this, alive);
      WBA.guard("learn", sync);
    };
  }
  if (window.WBL) {
    const onChange = WBL.onChange;
    WBL.onChange = function () {
      if (typeof onChange === "function") onChange();
      if (C) draw();
    };
  }
})();
