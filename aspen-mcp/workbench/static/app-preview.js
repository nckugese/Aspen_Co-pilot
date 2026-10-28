/* A proposal's preview on the flowsheet: before it is approved,
 * the flowsheet shows what the proposal would leave -- its new blocks and streams as the
 * proposal's line drawing (violet, dashed), what it removes grey and dashed, a moved stream's
 * new route -- and over each object it sets a tag with the values ("Number of stages 10 → 12").
 * Nothing drawn moves: flowsheet.js places what is new beside what it connects to (pvLayout).
 * The server says what changes (tab.check.shadow, feature preview); the values are the check's
 * rows (current → proposed). A pill at the flowsheet's top left says it is a preview, not the
 * model ("Preview · not applied"); pressed, the preview hides and the pill keeps its eye (this
 * viewer's pref wb.pv). Shown on a proposal's tab while it waits for the decision (draft, open)
 * or can continue where it stopped (the steps left); out of date (the blocks changed since the
 * check) at .45; paused while a heat plan shows. A tag pointed at lights its group's line in the
 * proposal's card and its objects on the drawing, and the other way round; a click on a tag
 * opens its group's steps in the card.
 *
 * Once the proposal is applied, its new blocks stay where the preview put them:
 * the first state whose flowsheet has a block the last preview drew as new makes the drawing
 * as it was, plus those places, the session's arrangement (a custom one, a step on the
 * flowsheet's undo, so ⋯ › "Undo layout" goes back to the arrangement before).
 *
 *   pvView(pane, tab)      FS.render's v.preview for the tab, or null
 *   pvTools(pane, tab)     the pill (from renderTools)
 *   pvToggle(pane)         the pill pressed
 *   pvSync(state)          a new state: the arrangement kept once a previewed proposal is applied
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { commitLayout, current, feature, fmtVal, isObj, objOfPath, prefGet, prefSet, sessOf, t, tabOf, usableImport, wb } = WBA;
  const { gcNow, gcRows, heatOf, heatPref, openGroup, propOf, renderPane, resumeOf, typeWords } = WBA.later;

  const WAITING = ["draft", "open"];
  const APPLYING = ["running", "applied", "partial", "stopped", "failed"];

  /** The tab's proposal while a preview of it may show: {p, chk, stale}; null otherwise (no
   *  proposal or no check, approved and under way, applied, sent back, withdrawn). */
  function subject(tab) {
    if (!tab || !feature("preview")) return null;
    const p = propOf(tab), chk = tab.check, run = tab.run || {};
    if (!p || !isObj(chk) || !Array.isArray(chk.steps)) return null;
    if (run.status === "running" && !run.dry_run) return null;
    const rec = wb.recs.get(tab.id);
    if (!WAITING.includes(p.status) && !(["stopped", "partial"].includes(p.status) && resumeOf(tab, rec, p))) return null;
    return { p, chk, stale: chk.rev !== tab.program_rev || !!(rec && rec.timer) };
  }
  const hidden = () => prefGet("wb.pv") === "off";

  // ------------------------------------------------------------------ what is drawn
  /** A field's word on a tag: the field alone (Chinese: our gloss where there is one), its
   *  qualifiers after it; never a path. */
  function word(path, type, session) {
    const lc = WBL.of(path, type || null, session) || {}, f = I18N.lang === "zh" && lc.gl ? lc.gl : lc.field;
    return ([f, ...(lc.q || [])].filter(Boolean).join(" · ") || WBL.say(path)).replace(/\\/g, "/");
  }
  const unitOf = (d) => (isObj(d) && d.unit ? String(d.unit) : "");
  /** One row's item on its object's tag: {segs (the line's parts), text (its tooltip line)}, or
   *  null (no value to show, or the same value). */
  function itemOf(r, lbl) {
    const nw = isObj(r.new) ? r.new : null, segs = [{ t: `${lbl} `, c: "" }];
    if (r.kind === "sweep" && nw) {
      const u = unitOf(nw);
      segs.push({ t: t("pv_sweep", fmtVal(nw.from), fmtVal(nw.to), nw.steps ?? "?") + (u ? ` ${u}` : ""), c: "n" });
    } else if (r.when === "runtime" || (nw && nw.expr != null && nw.expr !== "")) segs.push({ t: t("pv_runtime"), c: "n" });
    else if (nw && r.kind === "set") {
      const u = unitOf(nw) || unitOf(r.cur), to = `${fmtVal(nw.value)}${u ? ` ${u}` : ""}`;
      if (isObj(r.cur) && !r.created) {
        const ou = unitOf(r.cur) && unitOf(nw) && unitOf(r.cur) !== unitOf(nw) ? ` ${unitOf(r.cur)}` : "";
        if (String(r.cur.value) === String(nw.value) && !ou) return null;
        segs.push({ t: `${fmtVal(r.cur.value)}${ou}`, c: "o" }, { t: " → ", c: "" });
      }
      segs.push({ t: to, c: "n" });
    } else return null;
    return { segs, text: segs.map((s) => s.t).join("").trim() };
  }
  /** A type in words: "Heat exchanger (HeatX)" where the language has a name for it, else the type. */
  function typeName(type) {
    const w = String(typeWords(type) || type || "?"), i = w.indexOf(" ");
    return i > 0 ? `${w.slice(i + 1)}（${w.slice(0, i)}）` : w;
  }
  /** FS.render's v.preview: the shadow, a tag per object the steps set (by group, at most two
   *  values on it, "+N" for the rest, all of them in its tooltip), the new and removed objects'
   *  tooltips, out of date or not. */
  function build(tab, s) {
    const chk = s.chk, sh = isObj(chk.shadow) ? chk.shadow : {}, session = tab.session, fs = sessOf(tab).flowsheet || {};
    const types = {};
    (fs.blocks || []).forEach((b) => { if (b && b.name) types[String(b.name).toUpperCase()] = b.type; });
    ((sh.add && sh.add.blocks) || []).forEach((b) => { if (b && b.name) types[String(b.name).toUpperCase()] = b.type; });
    const typeOf = (key) => (key && key.startsWith("block:") ? types[key.slice(6)] : null);
    const tips = {}, isNew = {};
    ((sh.add && sh.add.blocks) || []).forEach((b) => { if (b && b.name) { tips[`block:${b.name}`] = t("tip_pv_new", typeName(b.type)); isNew[`block:${b.name}`] = 1; } });
    ((sh.add && sh.add.streams) || []).forEach((x) => { if (x && x.name) { tips[`stream:${x.name}`] = t("tip_pv_new", t("stream_word")); isNew[`stream:${x.name}`] = 1; } });
    (sh.move || []).forEach((m) => {                // (each end that moves, a line: from one block to another, onto one, off one)
      if (!m || !m.stream) return;
      const was = isObj(m.was) && m.was.block ? m.was.block : null, now = isObj(m.now) && m.now.block ? m.now.block : null;
      const line = was && now ? t("tip_pv_moved", m.stream, was, now) : now ? t("tip_pv_moved_on", m.stream, now) : was ? t("tip_pv_moved_off", m.stream, was) : "";
      const k = `stream:${m.stream}`;
      if (line) tips[k] = tips[k] ? `${tips[k]}\n${line}` : line;
    });
    ((sh.remove && sh.remove.blocks) || []).forEach((b) => { if (b && b.name) tips[`block:${b.name}`] = b.g != null ? t("tip_pv_gone", b.g) : t("tip_pv_gone_0"); });
    const by = new Map();
    chk.steps.forEach((r) => {
      if (!isObj(r) || r.off || r.applied || r.when === "branch" || !["set", "sweep"].includes(r.kind) || !r.path) return;
      const key = typeof r.obj === "string" && r.obj.includes(":") ? r.obj : objOfPath(r.path);
      const it = key && itemOf(r, word(r.path, typeOf(key), session));
      if (!it) return;
      if (!by.has(key)) by.set(key, { key, g: r.g ?? null, items: [] });
      by.get(key).items.push(it);
    });
    const tags = [...by.values()].map((x) => {
      const lines = x.items.slice(0, 2).map((it) => it.segs.slice());
      if (x.g != null) lines[0].unshift({ t: String(x.g), c: "g" }, { t: " ", c: "" });
      if (x.items.length > 2) lines[1].push({ t: `  ${t("pv_more", x.items.length - 2)}`, c: "" });
      const tip = [tips[x.key], ...x.items.map((it) => it.text), t("tip_pv_tag")].filter(Boolean).join("\n");
      return { key: x.key, g: x.g, lines, tip };
    });
    return { shadow: sh, tags, tips, stale: s.stale };
  }
  /** Whether a preview draws anything: a change to what is drawn, or a value on a tag. A proposal
   *  that changes neither (it only runs, or changes the components) has no preview and no pill. */
  const drawsAny = (v) => !!v && (v.tags.length > 0 || ["add", "remove"].some((k) => isObj(v.shadow[k])
    && ["blocks", "streams"].some((x) => Array.isArray(v.shadow[k][x]) && v.shadow[k][x].length)) || (Array.isArray(v.shadow.move) && v.shadow.move.length > 0));
  /** A run by group (app-group.js): the group it applies now -- its new objects in the
   *  accent, placed as the preview placed them (only: its number; the others' hidden) -- and a tag
   *  per object it sets, the values the server read at the pause (an accent dot ahead: "● Number of stages 10 → 12").
   *  The check's shadow only while it is the program's (the same groups). */
  function gcView(tab, s) {
    const chk = isObj(tab.check) && tab.check.rev === tab.program_rev ? tab.check : null;
    const sh = chk && isObj(chk.shadow) ? chk.shadow : {}, v = build(tab, { chk: { shadow: sh, steps: [] }, stale: false });
    const by = new Map(), types = {};
    ((sessOf(tab).flowsheet || {}).blocks || []).forEach((b) => { if (b && b.name) types[String(b.name).toUpperCase()] = b.type; });
    gcRows(tab, s).forEach((r) => {
      if (!isObj(r) || !["set", "sweep"].includes(r.kind) || !r.path) return;
      const key = typeof r.obj === "string" && r.obj.includes(":") ? r.obj : objOfPath(r.path);
      const it = key && itemOf(Object.assign({}, r, { created: !isObj(r.cur) }), word(r.path, key.startsWith("block:") ? types[key.slice(6)] : null, tab.session));
      if (!it) return;
      if (!by.has(key)) by.set(key, []);
      by.get(key).push(it);
    });
    const tags = [...by].map(([key, items]) => {
      const lines = items.slice(0, 2).map((it) => it.segs.slice());
      lines[0].unshift({ t: "● ", c: "d" });
      if (items.length > 2) lines[1].push({ t: `  ${t("pv_more", items.length - 2)}`, c: "" });
      return { key, g: null, lines, tip: [v.tips[key], ...items.map((it) => it.text)].filter(Boolean).join("\n") };
    });
    return { shadow: sh, tags, tips: v.tips, stale: false, gc: true, only: s.g.n };
  }
  /** FS.render's v.preview for the tab shown: null when none shows (none due, the pill pressed); a
   *  run by group's group (gcView) whatever the pill says -- it is no preview but what is applied. */
  function pvView(pane, tab) {
    const g = gcNow(tab);
    if (g) return gcView(tab, g);
    const s = subject(tab);
    if (!s || hidden()) return null;
    const v = build(tab, s);
    if (!drawsAny(v)) return null;
    wire(pane);
    return v;
  }

  // ------------------------------------------------------------------ the pill
  function pvTools(pane, tab) {
    const el = pane.q(".fs-pvp");
    if (!el) return;
    const s0 = subject(tab), s = s0 && drawsAny(build(tab, s0)) ? s0 : null;   // (nothing to draw: no pill)
    const off = hidden(), heat = !!(heatOf(tab) && heatPref(tab).on);           // (a heat plan shown pauses it)
    const tip = !s ? "" : off ? t("tip_pv_show") : [t("tip_pv_pill"), s.stale ? t("pv_stale") : "", heat ? t("pv_heat_off") : ""].filter(Boolean).join("\n");
    const sig = JSON.stringify([I18N.lang, !!s, off, s && s.stale, heat]);
    if (el.dataset.sig === sig) return;
    el.dataset.sig = sig;
    el.classList.toggle("hidden", !s);
    el.classList.toggle("off", off);
    el.classList.toggle("stale", !!(s && s.stale) || heat);
    el.setAttribute("aria-pressed", String(!!s && !off));
    el.title = tip;
    el.setAttribute("aria-label", off ? t("tip_pv_show") : t("pv_pill"));
    el.querySelector(".pvp-w").textContent = t("pv_pill");
  }
  function pvToggle(pane) {
    prefSet("wb.pv", hidden() ? null : "off");
    pane.sigs = {};
    renderPane(pane);
  }

  // ------------------------------------------------------------------ pointing: tag <-> card
  /** The keys of what a group (its n) changes on the drawing: its objects, and the preview's. */
  function keysOf(tab, n) {
    const chk = tab.check, g = isObj(chk) && Array.isArray(chk.groups) ? chk.groups.find((x) => isObj(x) && x.n === n) : null;
    const out = new Set(g && Array.isArray(g.objs) ? g.objs.map(String) : []), sh = isObj(chk) && isObj(chk.shadow) ? chk.shadow : {};
    ((sh.add && sh.add.blocks) || []).forEach((b) => b && b.g === n && out.add(`block:${b.name}`));
    ((sh.add && sh.add.streams) || []).forEach((x) => x && x.g === n && out.add(`stream:${x.name}`));
    (sh.move || []).forEach((m) => m && m.g === n && out.add(`stream:${m.stream}`));
    ((sh.remove && sh.remove.blocks) || []).forEach((b) => b && b.g === n && out.add(`block:${b.name}`));
    return [...out];
  }
  /** A group's key in the card (its line's data-g) by its number, and back. */
  const groupOf = (tab, by) => {
    const gs = isObj(tab.check) && Array.isArray(tab.check.groups) ? tab.check.groups.filter(isObj) : [];
    return gs.find(by) || null;
  };
  const gKey = (g) => String(g.key || g.n);
  /** Light up group n (null: none): its line in the card, its tags and its objects. */
  function hot(pane, n) {
    const tab = tabOf(pane.tabId), g = tab && n != null ? groupOf(tab, (x) => x.n === n) : null;
    pane.q(".prop-card").querySelectorAll(".pg.pv-hot").forEach((el) => el.classList.remove("pv-hot"));
    pane.svg.querySelectorAll(".fs-tag2.on").forEach((el) => el.classList.remove("on"));
    if (!g || !subject(tab) || hidden()) { FS.pvHot(pane.svg, []); return; }
    const li = pane.q(`.prop-card .pg[data-g="${CSS.escape(gKey(g))}"]`);
    if (li) li.classList.add("pv-hot");
    pane.svg.querySelectorAll(`.fs-tag2[data-g="${CSS.escape(String(n))}"]`).forEach((el) => el.classList.add("on"));
    FS.pvHot(pane.svg, keysOf(tab, n));
  }
  function wire(pane) {
    if (pane.pvWired) return;
    pane.pvWired = true;
    const num = (el) => { const v = el && el.getAttribute("data-g"); return v == null || v === "" ? null : Number(v); };
    FS.onTag(pane.svg, (key, el) => {
      const tab = tabOf(pane.tabId), n = num(el), g = tab && n != null ? groupOf(tab, (x) => x.n === n) : null;
      if (g) { openGroup(pane, gKey(g)); hot(pane, n); }   // (the card drawn again: its line lit again)
    });
    pane.svg.addEventListener("mouseover", (ev) => {
      const tg = ev.target.closest && ev.target.closest(".fs-tag2");
      if (tg && pane.pvAt !== tg) { pane.pvAt = tg; hot(pane, num(tg)); }
    });
    pane.svg.addEventListener("mouseout", (ev) => {
      const tg = ev.target.closest && ev.target.closest(".fs-tag2");
      if (tg && !(ev.relatedTarget && tg.contains(ev.relatedTarget))) { pane.pvAt = null; hot(pane, null); }
    });
    const card = pane.q(".prop-card");
    card.addEventListener("mouseover", (ev) => {
      const li = ev.target.closest && ev.target.closest(".pg"), tab = tabOf(pane.tabId);
      const g = li && tab ? groupOf(tab, (x) => gKey(x) === li.dataset.g) : null, n = g ? g.n : null;
      if (pane.pvCard !== n) { pane.pvCard = n; hot(pane, n); }
    });
    card.addEventListener("mouseleave", () => { if (pane.pvCard != null) { pane.pvCard = null; hot(pane, null); } });
  }

  // ------------------------------------------------------------------ once applied
  /** A new state: where a tab's last preview placed new blocks and the proposal is now applied
   *  (the flowsheet has one of them, the drawing does not yet), the drawing as it was plus those
   *  places becomes the session's arrangement: a step the user can take back (⋯ › "Undo layout"). */
  function pvSync(st) {
    if (!st || !Array.isArray(st.tabs)) return;
    wb.recs.forEach((rec, id) => {
      const c = rec.fs, pv = c && c.pv && !c.pv.used ? c.pv : null;
      if (!pv || !pv.res || !pv.res.blocks.length) return;
      const tab = st.tabs.find((x) => x.id === id), p = tab && isObj(tab.proposal) ? tab.proposal : null;
      const fs = tab && st.sessions && st.sessions[tab.session] && st.sessions[tab.session].flowsheet;
      if (!p || !fs || !Array.isArray(fs.blocks) || fs.taken_at === pv.taken) return;
      const run = tab.run || {};
      if (!APPLYING.includes(p.status) && !(run.status === "running" && !run.dry_run)) return;
      const now = new Set(fs.blocks.map((b) => b && b.name));
      if (!pv.res.blocks.some((b) => now.has(b.name) && !FS.draws(c, b.name))) return;
      const k = FS.pvKeep(c);
      pv.used = true;
      if (!k) return;
      const cur = current(tab.session), imp = usableImport(tab.session);
      const base = (cur.mode === "aspen" && imp) || (cur.mode === "custom" && cur.base === "aspen") ? "aspen" : "auto";
      commitLayout(tab.session, { v: 1, mode: "custom", base, nodes: Object.assign({}, k.base.nodes, k.nodes),
                                  streams: Object.assign({}, k.base.streams, k.streams) }, tab.id, null, true);
    });
  }

  Object.assign(WBA, { pvSync, pvToggle, pvTools, pvView, pvWord: word });
})();
