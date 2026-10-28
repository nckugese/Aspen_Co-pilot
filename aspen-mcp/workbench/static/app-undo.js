/* Taking changes back, and restore points: the page's side of the server's undo
 * (event revert: mode dry, the preview, answered in the session's undo_req; then mode apply,
 * seen: the preview's sig, so exactly what was shown is done), restore (event restore, answered
 * in restore_req), a named restore point (checkpoint) and keeping an automatic one
 * (keep_checkpoint), both answered in the session's cp.req; and the model's restore points on
 * disk, read by the window itself (window.py's Api.checkpoints) while the model shows.
 *
 * Every undo, redo and restore shows what it will do first, in one box under the button pressed
 * (.uv-pop: a dialog that blocks nothing -- a press elsewhere or Escape closes it): what changes
 * (field, value now → value it goes back to; a block or stream removed; a connection undone),
 * what was changed since and by whom (skip those, or overwrite them too), what cannot be taken
 * back and why, what stays (results: run again), and whether a restore point is saved first.
 * Nothing is written before its button. A restore says what goes back and what stays, that the
 * model file is backed up first, and how long it takes; "save the current state first" is on
 * by default, and saying no is said to be for good. Once applied, a toast says what was done,
 * with Redo; a box closed meanwhile still gets its toast.
 *
 *   undoOpen(tab, o)       o {ids | group, anchor, label, redo, restore, field}: the preview
 *   restoreOpen(tab, o)    o {checkpoint, anchor, point, then_revert, later}: the confirmation
 *   cpMap(tab)             the model's restore points on disk (Map id -> point, with ver), or null
 *   cpItems(pane, tab)     the model panel's small restore-point section (menu items)
 *   undoSync()             a new state: the answers waited for, the list read again where it moved
 *   undoClose(back)        close the box; whether it was open (Escape)
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { $, base, dialog, drop: dropAt, esc, feature, fmtVal, hhmm, icon, isOpen, menuOpen, openMenu, popover, sessOf, shownTab, t, tabOf,
    th, tn, toast, wb } = WBA;
  const { modelPanel, renderChanges } = WBA.later;

  const WAIT_MS = 8000;        // no answer this long: the box says the server is busy (Aspen holds it)
  const KEEP_MS = 30 * 60e3;   // an applied undo, a restore or a save waited for at most this long
  const BIG_S = 15;            // saving a restore point this slow is said so (restore_points AUTO_MAX_S)
  const SHOW = 5;              // restore points the model panel lists before "N more"
  const STEPS = 12;            // preview lines before "and N more"
  const LATER = 500;           // records read to count the groups a restore takes back
  const uid = () => `u${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  const api = () => window.pywebview && window.pywebview.api;
  const modelOf = (tab) => { const s = sessOf(tab); return (s.model && s.model.id) || (s.journal && s.journal.model) || null; };
  const fileOf = (tab) => { const m = sessOf(tab).model; return m && m.file ? String(m.file) : ""; };
  /** A time as the timeline says it: 14:02 today, yesterday 17:10, 9/24 13:40. */
  function tlWhen(s) {
    const d = new Date((Number(s) || 0) * 1000), y = new Date();
    if (d.toDateString() === y.toDateString()) return hhmm(s);
    y.setDate(y.getDate() - 1);
    return d.toDateString() === y.toDateString() ? t("uv_yday", hhmm(s)) : `${d.getMonth() + 1}/${d.getDate()} ${hhmm(s)}`;
  }
  const est = (s) => WBC.est(s);
  const cpWords = (reason) => WBC.cpWords(reason);
  function bytes(n) {
    const x = Number(n) || 0;
    return x >= 1 << 30 ? `${(x / (1 << 30)).toFixed(1)} GB` : x >= 1 << 20 ? `${(x / (1 << 20)).toFixed(1)} MB` : x >= 1024 ? `${Math.round(x / 1024)} KB` : `${x} B`;
  }
  /** Who changed something, as a conflict says it (null: the Aspen window or a calculation). */
  const whoW = (a) => t(`uv_who_${["ai", "user", "program", "optimizer", "external"].includes(a) ? a : "none"}`);
  /** Why the window cannot send it now, or "". */
  const whyNot = (tab) => (!wb.connected ? t("why_off") : !isOpen(tab) ? t("why_closed", tab.session) : "");

  // ------------------------------------------------------------------ the model's restore points (Api.checkpoints)
  const CP = new Map();        // model id -> {got, err, sig, busy, map}
  let cpVer = 0;
  /** What moves the list: the session's cp summary (how many, the newest, an answer). */
  const cpSig = (sess) => { const c = sess.cp || {}, l = c.last || {}, r = c.req || {}; return JSON.stringify([c.n, c.bytes, l.id, l.class, l.name, r.req, r.status]); };
  function cpEntry(tab) { const m = modelOf(tab); return m ? CP.get(m) || null : null; }
  /** Read the list again where the session's cp moved (or never read). */
  function cpLoad(tab) {
    const a = api(), model = modelOf(tab);
    if (!model || !a || typeof a.checkpoints !== "function") return;
    let e = CP.get(model);
    if (!e) CP.set(model, (e = { got: null, err: "", sig: null, busy: false, map: null }));
    const sig = cpSig(sessOf(tab));
    if (e.busy || e.sig === sig) return;
    e.busy = true;
    e.sig = sig;
    const file = fileOf(tab);
    let p;
    try { p = Promise.resolve(a.checkpoints(file ? { model, path: file } : { model })); } catch (x) { p = Promise.reject(x); }
    p.then((got) => {
      e.busy = false;
      if (!got || typeof got !== "object" || got.error || !Array.isArray(got.points)) { e.err = String((got && got.error) || "?"); return; }
      e.got = got;
      e.err = "";
      e.map = null;
      cpVer++;
      cpArrived(model);
    }, (x) => { e.busy = false; e.err = String((x && x.message) || x || "?"); });
  }
  function cpMap(tab) {
    const e = tab && cpEntry(tab);
    if (!e || !e.got) return null;
    if (!e.map) { e.map = new Map(e.got.points.map((p) => [p.id, p])); e.map.ver = cpVer; }
    return e.map;
  }
  /** The list came: the timeline's milestones, an open model panel and a restore box follow. */
  function cpArrived(model) {
    const pane = wb.pane, tab = shownTab();
    if (!pane || !tab || modelOf(tab) !== model) return;
    renderChanges(pane);
    const ms = $("modelstat");
    if (menuOpen() && wb.menuAt === ms && !$("menu").contains(document.activeElement)) openMenu(ms, modelPanel(pane, tab));
    if (P && P.w.kind === "restore" && !P.w.p) { P.w.p = (cpMap(tab) || new Map()).get(P.w.cp) || null; draw(); }
  }

  // ------------------------------------------------------------------ what is waited for
  // Each request the window sent and still waits for: {kind: undo | restore | cp | keep, req,
  // session, tab, mode (undo: dry | apply), state (wait | plan | run | ask | msg), sent, q (the
  // answer shown), ...}. The box shows one of them (P.w); a dry preview closed is let go.
  const W = [];
  function post(w, ev) {
    w.sent = Date.now();
    w.slow = false;
    wb.post(Object.assign({ tab: w.tab, req: w.req }, ev));
    const req = w.req;
    setTimeout(() => { if (w.req === req && (w.state === "wait" || w.state === "run") && !w.got) { w.slow = true; if (P && P.w === w) draw(); } }, WAIT_MS);
  }
  function drop(w) { const i = W.indexOf(w); if (i >= 0) W.splice(i, 1); }
  function sessQ(w, key) {
    const sess = ((wb.state && wb.state.sessions) || {})[w.session] || {};
    const q = key === "cp" ? (sess.cp || {}).req : sess[key];
    return q && typeof q === "object" && q.req === w.req ? q : null;
  }
  /** A new state: what came for each request waited for. */
  function undoSync() {
    if (!wb.state) return;
    const tab = shownTab();
    if (tab) cpLoad(tab);
    W.slice().forEach((w) => {
      if (Date.now() - w.sent > KEEP_MS) { drop(w); return; }
      const q = sessQ(w, w.kind === "undo" ? "undo_req" : w.kind === "restore" ? "restore_req" : "cp");
      if (!q) return;
      const sig = `${q.status}|${q.at}|${q.sig || ""}`;
      if (sig === w.qsig) return;
      w.qsig = sig;
      w.got = true;
      w.slow = false;
      if (w.kind === "undo") gotUndo(w, q);
      else if (w.kind === "restore") gotRestore(w, q);
      else gotCp(w, q);
    });
  }

  // ------------------------------------------------------------------ the box
  let P = null;                // {el, anchor, rect, w, h, up}
  function popOpen(anchor, w) {
    popClose();
    if (window.WBC) { WBC.coverageClose(); if (WBC.reportClose) WBC.reportClose(); }   // (one box over the page at a time)
    const { el, off } = popover(document.body, "cov-pop uv-pop", "uv-title", { close: popClose, place: popPlace,
      keep: (x) => !!(anchor && anchor.contains && anchor.contains(x)) });
    const r = anchor && anchor.getBoundingClientRect ? anchor.getBoundingClientRect() : null;
    P = { el, off, anchor: anchor || null, rect: r && r.width ? { left: r.left, right: r.right, top: r.top, bottom: r.bottom } : null, w, h: null, up: null };
    el.addEventListener("click", popClick);
    el.addEventListener("change", popChange);
    draw();
    el.focus({ preventScroll: true });
  }
  /** Under the button pressed (its right edges lined up), over it where there is more room there;
   *  a button gone meanwhile (the timeline drawn again): where it was; none: under the header. */
  function popPlace() {
    if (!P) return;
    const W0 = window.innerWidth, w = Math.min(400, W0 - 16);
    const a = P.anchor && P.anchor.isConnected && P.anchor.offsetParent ? P.anchor.getBoundingClientRect() : null;
    const r = a && a.width ? a : P.rect || { left: (W0 - w) / 2, right: (W0 + w) / 2, top: 44, bottom: 52 };
    // the side with room; the preview that came taller than its side moves to the other once
    const was = P.up;
    P.up = dropAt(P.el, r, w, 140, (h, above, below) => (was === null ? h > below && above > below
      : (was ? h > above && below > above : h > below && above > below) ? !was : was));
  }
  function popClose(back) {
    if (!P) return false;
    const { off, anchor, w } = P;
    P = null;
    off(back, anchor);
    if (w && (w.kind === "undo" ? w.mode === "dry" : w.state !== "run")) drop(w);   // (a preview nobody looks at: let go)
    return true;
  }
  /** The box drawn again from its request; the keyboard stays in it (on its first button). */
  function draw() {
    if (!P) return;
    const w = P.w, html = (w.kind === "restore" ? rsHtml(w) : uvHtml(w)) + (w.slow ? `<p class="uv-q">${esc(t("uv_slow"))}</p>` : "");
    if (P.h === html) return;
    const inside = P.el.contains(document.activeElement);
    P.h = html;
    P.el.innerHTML = html;
    popPlace();
    if (inside) { const b = P.el.querySelector("button.primary:not(:disabled), .uv-f button:not(:disabled)"); (b || P.el).focus({ preventScroll: true }); }
  }
  const head = (title) => `<div class="cov-h"><b id="uv-title">${esc(title)}</b>`
    + `<button class="cov-x flat icon" data-u="close" title="${esc(t("close"))}">${icon("close")}</button></div>`;
  const foot = (btns) => `<div class="uv-f">${btns.join("")}</div>`;
  const btn = (u, label, cls, off, tip) => `<button class="${cls || ""}" data-u="${u}"${off ? " disabled" : ""}${tip ? ` title="${esc(tip)}"` : ""}>${esc(label)}</button>`;

  function popClick(ev) {
    const b = ev.target.closest("button[data-u]");
    if (!b || b.disabled || !P) return;
    const w = P.w, u = b.dataset.u, tab = tabOf(w.tab);
    if (u === "close") { popClose(true); return; }
    if (!tab) { popClose(); return; }
    if (u === "apply") applyUndo(w);
    else if (u === "rs_before") {                  // "Restore to before this group": the restore's own confirmation
      const rb = (w.q.preview || {}).restore_before || {};
      restoreOpen(tab, { checkpoint: rb.id, anchor: P.anchor, then_revert: rb.then || [], later: rb.later_groups || null, t: rb.t });
    } else if (u === "restore" || u === "restore_ai") applyRestore(w, u === "restore_ai");
  }
  function popChange(ev) {
    if (!P) return;
    const el = ev.target, w = P.w;
    if (el.name === "uvc") w.choice = el.value === "force" ? "force" : "skip";
    else if (el.dataset.u === "save") w.save = el.checked;
    else return;
    draw();
  }

  // ------------------------------------------------------------------ undo, redo: the preview
  /** Open the preview of taking records `ids` or change group `group` back (o.redo: they are
   *  an undo's: a redo). The server plans it against the model as it is now (mode dry). */
  function undoOpen(tab, o) {
    if (!tab || !feature("undo") || !o || (!o.group && !(o.ids && o.ids.length))) return;
    const title = o.field ? t("uv_t_field", o.label || "") : o.group ? t(o.redo ? "uv_t_group_redo" : "uv_t_group", o.label || "")
      : o.restore ? t("uv_t_rs") : t(o.redo ? "uv_t_redo" : "uv_t_one", o.label || "");
    W.filter((x) => x.kind === "undo" && x.mode === "dry").forEach(drop);
    const w = { kind: "undo", req: uid(), tab: tab.id, session: tab.session, model: modelOf(tab), ids: o.group ? null : o.ids.slice(0, 20),
                group: o.group || null, title, label: o.label || "", redo: !!o.redo, mode: "dry", state: "wait", q: null, choice: "skip", note: "" };
    const why = whyNot(tab);
    if (why) { w.state = "msg"; w.text = why; popOpen(o.anchor, w); return; }
    W.push(w);
    popOpen(o.anchor, w);
    post(w, reqOf(w, "dry"));
  }
  function reqOf(w, mode, on, seen) {
    const ev = { type: "revert", model: w.model, mode, on_conflict: on || "abort" };
    if (w.group) ev.group = w.group; else ev.ids = w.ids;
    if (seen) ev.seen = seen;
    return ev;
  }
  function gotUndo(w, q) {
    if (w.mode === "dry") {
      if (q.status === "planned") { w.q = q; w.state = "plan"; }
      else { w.state = "msg"; w.text = q.text || t("uv_failed0"); drop(w); }
    } else if (q.status === "running") w.state = "run";
    else if (q.status === "conflict") {            // changed meanwhile: the fresh preview, confirmed again
      w.q = Object.assign({}, q, { preview: q.preview || (w.q || {}).preview, sig: q.sig || (w.q || {}).sig });
      w.mode = "dry";
      w.state = "plan";
      w.note = q.code === "plan_changed" ? t("uv_changed") : t("uv_conflict_now");
    } else if (["done", "partial", "nothing"].includes(q.status)) {
      drop(w);
      if (P && P.w === w) popClose(true);
      const g = q.result && q.result.group, tab = tabOf(w.tab);
      toast(q.text || t("uv_done0"), 7000, g && tab && q.status !== "nothing" && feature("undo")
        ? { label: t(w.redo ? "undo" : "redo"), run: () => undoOpen(tabOf(w.tab), { group: g, label: w.label, redo: !w.redo }) } : undefined);
      return;
    } else { w.state = "msg"; w.text = q.text || t("uv_failed0"); drop(w); }
    if (P && P.w === w) draw();
  }
  function applyUndo(w) {
    if (!w.q || w.state !== "plan") return;
    const tab = tabOf(w.tab), why = tab ? whyNot(tab) : t("why_off");
    if (why) { toast(why); return; }
    const conf = conflictsOf(w.q).length > 0, one = ((w.q.preview || {}).steps || []).length === 1;
    w.req = uid();
    w.mode = "apply";
    w.state = "run";
    w.got = false;
    w.note = "";
    if (!W.includes(w)) W.push(w);
    post(w, reqOf(w, "apply", conf ? (one ? "force" : w.choice) : "abort", w.q.sig));
    draw();
  }
  const conflictsOf = (q) => (Array.isArray(q.conflicts) ? q.conflicts : []);

  // what the preview says, line by line
  const fld = (path) => (window.WBC && WBC.field ? WBC.field(path, null, null) : esc(base(path)));
  const valH = (d) => (window.WBC && WBC.valHtml ? WBC.valHtml(d, true) : esc(d && typeof d === "object" ? fmtVal(d.value) : fmtVal(d)));
  /** now → target, the unit on the target only (on both where it differs), as the timeline says a change. */
  function chg(a, b) {
    const unit = (d) => (d && typeof d === "object" ? d.unit || "" : ""), moved = !!a && unit(a) !== unit(b);
    const v = (d, u) => (window.WBC && WBC.valHtml ? WBC.valHtml(d, u) : valH(d));
    return `<span class="ch-v">${a ? `${v(a, moved)} → ` : "→ "}${v(b || {}, true)}</span>`;
  }
  /** A step in words (html): the field, its value now → the one it goes back to; a block or
   *  stream removed; a connection undone or put back; a restore undone. */
  function stepHtml(s) {
    const k = s.kind, now = s.now && typeof s.now === "object" && !("port" in s.now) && !("exists" in s.now) ? s.now : s.expect;
    if (k === "value") return `${fld(s.path)} ${chg(now, s.to)}`;
    if (k === "attr") return `${fld(s.path)} <small class="ch-q">${esc(t("ch_r_attr", s.attr))}</small> ${chg(now, s.to)}`;
    if (k === "remove_block") return esc(t("uv_st_rm_block", `${s.name}${s.type ? ` (${s.type})` : ""}`));
    if (k === "remove_stream") return esc(t("uv_st_rm_stream", s.name));
    if (k === "remove_row") return `${fld(String(s.path).replace(/\\[^\\]*$/, ""))} ${esc(t("uv_st_rm_row", s.name))}`;
    if (k === "remove_element") { const p = String(s.path).split("\\"); return esc(t("uv_st_rm_sub", `${p[3] || ""} › ${p.slice(-2).join(" ")}`)); }
    if (k === "disconnect") return esc(t("uv_st_disc", s.name, `${s.block} ${s.port}`));
    if (k === "reconnect") return esc(t("uv_st_reconn", s.name, `${s.block} ${s.port}`));
    if (k === "restore") return esc(t("uv_st_restore"));
    return esc(String(s.name || s.key || "?"));
  }
  /** What an entry is about, in words: its field, or its block / stream, or its record's kind. */
  function whatOf(e) {
    if (e.path && /\\(Input|Output)\\/i.test(e.path)) return fld(e.path);
    const name = e.name || base(e.path);
    if (e.op === "remove") return esc(t("uv_rm_what", name));
    return esc(name || "?");
  }
  function conflictHtml(c, steps) {
    const who = whoW(c.by), at = c.t ? tlWhen(c.t) : "?", what = c.path && (c.kind === "value" || c.kind === "attr") ? fld(c.path) : esc(c.name || base(c.path) || c.key);
    const s = steps.find((x) => x.key === c.key) || {};
    const x = c.by ? "" : "_x";                    // (not in the journal: Aspen's window or a calculation)
    if ((c.kind === "value" || c.kind === "attr") && c.now && typeof c.now === "object" && "value" in c.now) {
      return th(`uv_conf_value${x}`, what, esc(who), valH(c.now), esc(at), valH(s.to || {}));
    }
    const key = { used_since: "uv_conf_used", foreign_connection: "uv_conf_foreign", restored_since: "uv_conf_restored",
                  displaced_taken: "uv_conf_taken", port_taken: "uv_conf_taken", later_lost: "uv_conf_lost" }[c.code] || `uv_conf_other${x}`;
    const conn = Array.isArray(c.connected) ? c.connected.map((x) => (typeof x === "object" ? x.name || x.stream || "" : String(x))).filter(Boolean).join(t("ch_s_sep")) : "";
    return th(key, what, esc(who), esc(at), esc(conn || "—"));
  }
  function uvHtml(w) {
    let out = head(w.title);
    if (w.state === "wait") return out + `<p class="uv-st">${esc(t("uv_checking"))}</p>` + foot([btn("close", t("cancel"))]);
    if (w.state === "msg") return out + `<p class="uv-msg">${esc(w.text || "")}</p>` + foot([btn("close", t("close"), "primary")]);
    const q = w.q || {}, pv = q.preview || {}, steps = Array.isArray(pv.steps) ? pv.steps : [], n = pv.n || {};
    const moot = pv.moot || [], blocked = pv.blocked || [], info = pv.info || [], rb = pv.restore_before || null;
    const conf = conflictsOf(q), run = w.state === "run", redo = !!pv.redo || w.redo;
    if (w.note) out += `<p class="uv-note">${esc(w.note)}</p>`;
    const nSteps = Number(n.steps) || steps.length;
    out += nSteps ? `<p class="uv-h">${esc(tn(redo ? "uv_head_redo" : "uv_head", nSteps))}</p>` : `<p class="uv-h">${esc(t("uv_nothing"))}</p>`;
    const li = [];
    steps.slice(0, STEPS).forEach((s) => {
      const st = s.state, mark = st === "conflict" ? "⚠" : st === "already" ? "·" : st === "blocked" ? "✕" : redo ? "↷" : "↶";
      const tail = st === "already" ? ` <small class="ch-q">${esc(t("uv_already"))}</small>`
        : st === "blocked" ? ` <small class="ch-q">${esc(t(`uv_bl_${s.state_code}`) === `uv_bl_${s.state_code}` ? t("uv_bl_unsupported0") : t(`uv_bl_${s.state_code}`))}</small>`
        : /^remove_/.test(s.kind) && pv.needs_checkpoint ? ` <small class="ch-q">${esc(t("uv_cp_first_s"))}</small>` : "";
      li.push(`<li class="uv-s ${st || "ok"}"><i aria-hidden="true">${mark}</i><span>${stepHtml(s)}${tail}</span></li>`);
    });
    if (nSteps > Math.min(steps.length, STEPS)) li.push(`<li class="uv-s q"><i></i><span>${esc(t("uv_more", nSteps - Math.min(steps.length, STEPS)))}</span></li>`);
    moot.slice(0, 6).forEach((e) => {
      const k = `uv_moot_${e.code}`, words = t(k) === k ? t("uv_moot_other") : t(k);
      li.push(`<li class="uv-s q"><i aria-hidden="true">·</i><span>${th("uv_line", whatOf(e), esc(words.replace("{0}", String(e.with || "").replace(/^\w+:/, ""))))}</span></li>`);
    });
    blocked.slice(0, 6).forEach((e) => {
      const k = `uv_bl_${e.code}`, words = t(k) === k ? t("uv_bl_unsupported0") : t(k);
      li.push(`<li class="uv-s x"><i aria-hidden="true">✕</i><span>${th("uv_line", whatOf(e), esc(words))}</span></li>`);
    });
    if (li.length) out += `<ul class="uv-l">${li.join("")}</ul>`;
    // what it cannot do or will not change
    const approx = steps.filter((s) => Array.isArray(s.approx) && s.approx.length);
    if (approx.length) out += `<p class="uv-q">${esc(t("uv_approx_h", approx.length, WBC.apWords(approx[0].approx)))}</p>`;
    info.forEach((e) => {
      const k = `uv_info_${e.code}`;
      out += `<p class="uv-q">${esc(t(k) === k ? tn("uv_info_nothing", e.n || 1) : t(k))}</p>`;
    });
    if (pv.needs_checkpoint && nSteps) out += `<p class="uv-q">${esc(t("uv_cp_first"))}</p>`;
    // changed since: who and when; skip them or overwrite them (one step alone: overwrite it or not)
    const one = steps.length === 1;
    if (conf.length) {
      out += `<div class="uv-conf"><p>${esc(one ? t("uv_conf_one") : tn("uv_conf_h", conf.length + (Number(q.conflicts_more) || 0)))}</p>`
        + `<ul>${conf.slice(0, 6).map((c) => `<li>${conflictHtml(c, steps)}</li>`).join("")}</ul>`
        + (one ? "" : `<div class="uv-ch" role="radiogroup" aria-label="${esc(t("uv_conf_ask"))}">`
          + `<label><input type="radio" name="uvc" value="skip"${w.choice !== "force" ? " checked" : ""}${run ? " disabled" : ""}> ${esc(t("uv_skip"))}</label>`
          + `<label><input type="radio" name="uvc" value="force"${w.choice === "force" ? " checked" : ""}${run ? " disabled" : ""}> ${esc(t("uv_force"))}</label></div>`)
        + `</div>`;
    }
    // what only a restore point takes back: "Restore to before this group" (the restore, then the values before it)
    const rsOk = pv.suggest === "restore" && rb && rb.id && rb.on_disk !== false;
    if (rsOk) {
      const later = Array.isArray(rb.later_groups) ? rb.later_groups.length : 0;
      out += `<p class="uv-rs">${esc(t("uv_rs_note", tlWhen(rb.t)) + (later ? tn("uv_rs_later", later) : ""))}</p>`;
    } else if (blocked.some((e) => e.code === "checkpoint_only")) {
      out += `<p class="uv-q">${esc(t(rb && rb.id ? "uv_rs_gone" : "uv_rs_none"))}</p>`;
    }
    if (run) out += `<p class="uv-st">${esc(t(redo ? "uv_running_redo" : "uv_running"))}</p>`;
    const btns = [];
    if (rsOk) btns.push(btn("rs_before", t("uv_group_rs"), "primary", run));
    if (nSteps) {
      const live = steps.filter((s) => s.state !== "already" && s.state !== "blocked").length;
      const label = rsOk ? t("uv_partial_btn") : one && conf.length ? t("uv_go_force") : blocked.length ? t("uv_go_part") : t(redo ? "redo" : "undo");
      btns.push(btn("apply", label, rsOk ? "" : "primary", run || !live, !live ? t("uv_all_already") : ""));
    }
    btns.push(btn("close", nSteps || rsOk ? t("cancel") : t("close"), nSteps || rsOk ? "" : "primary"));
    return out + foot(btns);
  }

  // ------------------------------------------------------------------ restore: the confirmation
  /** Open the confirmation of restoring the model to restore point o.checkpoint (then_revert:
   *  "restore to before this group" -- the values older than the point are undone after it). */
  function restoreOpen(tab, o) {
    if (!tab || !o || !o.checkpoint) return;
    const map = cpMap(tab), p = (map && map.get(o.checkpoint)) || o.point || null;
    if (!map) cpLoad(tab);
    W.filter((x) => x.kind === "restore" && x.state !== "run").forEach(drop);
    const w = { kind: "restore", req: null, tab: tab.id, session: tab.session, model: modelOf(tab), cp: o.checkpoint, p, t: o.t,
                then: Array.isArray(o.then_revert) && o.then_revert.length ? o.then_revert.slice(0, 500) : null,
                later: Array.isArray(o.later) ? o.later : null, laterN: null, laterT: [], save: true, state: "ask", file: fileOf(tab) };
    popOpen(o.anchor, w);
    countLater(w);
  }
  /** How many change groups after the point a restore takes back, and their titles (the
   *  journal read once: its changes after the point's time; a restore point's own milestone and
   *  what changed nothing do not count). */
  function countLater(w) {
    const a = api(), at = (w.p && w.p.t) || w.t;
    if (!a || typeof a.journal !== "function" || !w.model || typeof at !== "number") return;
    const INPUT = ["value", "attr", "add", "remove", "connect", "patch", "restore", "summary"];
    Promise.resolve().then(() => a.journal({ model: w.model, after: at, limit: LATER, types: {} })).then((got) => {
      if (!got || !Array.isArray(got.records)) return;
      const gs = [];
      got.records.forEach((r) => {
        if (r && r.kind === "change" && r.group && INPUT.includes(r.op) && (r.status === "changed" || r.status === "unknown") && !gs.includes(r.group)) gs.push(r.group);
      });
      const heads = got.groups || {};
      gs.reverse();                                  // (the oldest first: the group the point was kept for leads)
      w.laterN = gs.length + (got.more ? "+" : "");
      w.laterT = gs.slice(0, 3).map((g) => (window.WBC && WBC.headTitle ? WBC.headTitle(heads[g], heads) : String((heads[g] || {}).title || g)));
      if (P && P.w === w) draw();
    }).catch(() => {});
  }
  function rsHtml(w) {
    const p = w.p || {}, tab = tabOf(w.tab), e = tab && cpEntry(tab), got = e && e.got;
    const name = p.name || cpWords(p.reason), at = typeof p.t === "number" ? tlWhen(p.t) : typeof w.t === "number" ? tlWhen(w.t) : "";
    let out = head(p.id || w.t ? t("rs_title", at, name) : t("rs_title0"));
    if (w.state === "msg") return out + `<p class="uv-msg">${esc(w.text || "")}</p>` + foot([btn("close", t("close"), "primary")]);
    const bkp = /\.bkp$/i.test(w.file || "") || !w.file, run = w.state === "run";
    // (restoring: the point's own estimate, from what it holds; a window before that, the model's)
    const saveS = got && got.estimate && typeof got.estimate.s === "number" ? got.estimate.s : null;
    const rsS = typeof p.restore_s === "number" ? p.restore_s : got && typeof got.restore_s === "number" ? got.restore_s : null;
    const li = [];
    const n = w.laterN != null ? w.laterN : w.later ? w.later.length : null;
    li.push(n === null ? t("rs_b_back") : n === 0 || n === "0" ? t("rs_b_back0") : tn("rs_b_back_n", String(n) === "1" ? 1 : n, w.laterT.length ? w.laterT.join(t("ch_s_sep")) + (Number(n) > w.laterT.length || String(n).endsWith("+") ? "…" : "") : "…"));
    li.push(t("rs_b_file", base(w.file) || tab && tab.session || "?"));
    li.push(t("rs_b_keep"));
    li.push(t(p.state === "input" ? "rs_b_res_input" : p.fresh === true ? "rs_b_res_fresh" : "rs_b_res_stale"));
    if (w.then) li.push(tn("rs_b_then", w.then.length));
    if (rsS != null) li.push(t("rs_b_time", est(rsS)));
    out += `<ul class="uv-b">${li.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
    if (!bkp) out += `<p class="uv-warn">${esc(t("rs_not_bkp"))}</p>`;
    else if (!w.p && !cpMap(tab)) out += `<p class="uv-q">${esc(t("mp_cp_loading"))}</p>`;
    else if (!w.p) out += `<p class="uv-warn">${esc(t("rs_gone"))}</p>`;
    const big = saveS != null && saveS >= BIG_S;
    out += `<label class="uv-cb"><input type="checkbox" data-u="save"${w.save ? " checked" : ""}${run || !bkp ? " disabled" : ""}> `
      + `${esc(saveS == null ? t("rs_save0") : t(big ? "rs_save_big" : "rs_save", est(saveS)))}</label>`;
    if (!w.save) out += `<p class="uv-warn">${esc(t("rs_save_warn"))}</p>`;
    if (run) out += `<p class="uv-st">${esc(t("rs_running"))}</p>`;
    const why = tab ? whyNot(tab) : t("why_off"), off = run || !bkp || !w.p || !!why;
    return out + foot([btn("restore", t("rs_go"), "primary", off, why), btn("restore_ai", t("rs_go_ai"), "", off, why || t("tip_rs_go_ai")), btn("close", t("cancel"))]);
  }
  function applyRestore(w, ai) {
    const tab = tabOf(w.tab);
    if (!tab || w.state === "run") return;
    w.req = uid();
    w.state = "run";
    w.got = false;
    if (!W.includes(w)) W.push(w);
    const ev = { type: "restore", checkpoint: w.cp, save_first: !!w.save, tell_ai: !!ai };
    if (w.then) ev.then_revert = w.then;
    post(w, ev);
    draw();
  }
  function gotRestore(w, q) {
    if (q.status === "running") w.state = "run";
    else if (q.status === "done") {
      drop(w);
      if (P && P.w === w) popClose(true);
      toast(q.text || t("rs_done0"), 8000);
      return;
    } else { w.state = "msg"; w.text = q.text || t("uv_failed0"); drop(w); }
    if (P && P.w === w) draw();
  }

  // ------------------------------------------------------------------ a named restore point, keeping one
  /** "Save restore point…": its name (a default with the time), how long it takes, then the
   *  server saves it (a copy of the file where the model is its file, else an export). */
  function cpSave(tab) {
    if (!tab) return;
    const e = cpEntry(tab), s = e && e.got && e.got.estimate ? e.got.estimate.s : null;
    const def = t("cp_default", hhmm(Date.now() / 1000));
    dialog({ title: t("cp_dlg_title"), text: def, single: true, ok: t("cp_dlg_go"),
             help: typeof s !== "number" ? t("cp_dlg_help0") : t(s >= BIG_S ? "cp_dlg_help_big" : "cp_dlg_help", est(s)),
             onOk: (v) => {
               const name = String(v || "").replace(/\s+/g, " ").trim().slice(0, 80) || def, why = whyNot(tab);
               if (why) { toast(why); return; }
               const w = { kind: "cp", req: uid(), tab: tab.id, session: tab.session, name, state: "run" };
               W.push(w);
               post(w, { type: "checkpoint", name });
               toast(t("cp_sending", name), 4000);
             } });
  }
  function cpKeep(tab, p) {
    const name = p.name || cpWords(p.reason), w = { kind: "keep", req: uid(), tab: tab.id, session: tab.session, name, state: "run" };
    W.push(w);
    post(w, { type: "keep_checkpoint", checkpoint: p.id, name });
  }
  function gotCp(w, q) {
    if (q.status === "running") return;
    drop(w);
    if (q.status === "done") toast(w.kind === "keep" ? t("cp_kept", q.name || w.name) : q.text || t("cp_saved0", w.name), 6000);
    else toast(q.text || t("uv_failed0"), 6000);
  }

  // ------------------------------------------------------------------ the model panel's section
  /** The model panel's restore points, only where there are some: the
   *  title (how many are kept, in its tooltip), the newest SHOW points (each: what it holds,
   *  "Restore to here", "Keep" for an automatic one), the rest under one item; the list not read yet or
   *  empty: nothing (a list that could not be read: a line). The list is the window's own read
   *  (Api.checkpoints), so it shows while Aspen calculates; the panel is drawn again when it
   *  comes. part "save": the action "Create restore point…" alone (the panel's "Actions"). */
  function cpItems(pane, tab, part) {
    if (!tab) return [];
    const e = cpEntry(tab), got = e && e.got, why = whyNot(tab);
    if (part === "save") {
      const s = got && got.estimate && typeof got.estimate.s === "number" ? got.estimate.s : null;
      return [{ label: t("mp_cp_save"), icon: "add", disabled: !!why, tip: why || (s === null ? t("tip_mp_cp_save0") : t("tip_mp_cp_save", est(s))), run: () => cpSave(tab) }];
    }
    if (!got) {
      if (!e) cpLoad(tab);
      return e && e.err ? [{ sep: true }, { title: t("mp_cp") }, { html: `<div class="mp-line mp-cpl">${esc(t("mp_cp_err"))}</div>` }] : [];
    }
    const pts = got.points || [], ms = $("modelstat");
    if (!pts.length) return [];
    const items = [{ sep: true },
      { html: `<div class="mt mp-cpt" title="${esc(t("mp_cp_foot", got.auto_keep || 20, bytes(got.bytes)))}">${esc(t("mp_cp"))}</div>` }];
    const mark = (p) => (p.class === "named" ? "★" : "◆");
    const tip = (p) => [cpWords(p.reason), t(`mp_cp_st_${["saved", "live", "input"].includes(p.state) ? p.state : "live"}`),
      p.size ? bytes(p.size) : "", p.kept ? t("mp_cp_kept") : ""].filter(Boolean).join(" · ");
    const back = (p) => ({ label: t("cp_here"), icon: "undo", disabled: !!why, tip: why || t("tip_cp_here"),
                          run: () => restoreOpen(tab, { checkpoint: p.id, anchor: ms, point: p }) });
    const item = (p) => ({ label: `${mark(p)} ${p.name || cpWords(p.reason)}`, keys: tlWhen(p.t), cls: "mp-cp", tip: tip(p),
      sub: [{ html: `<div class="mp-note">${esc(tip(p))}</div>` }, back(p),
            ...(p.kept ? [] : [{ label: t("mp_cp_keep"), icon: "check", disabled: !wb.connected, tip: wb.connected ? t("tip_mp_cp_keep") : t("why_off"), run: () => cpKeep(tab, p) }])] });
    pts.slice(0, SHOW).forEach((p) => items.push(item(p)));
    if (pts.length > SHOW) {
      items.push({ label: t("mp_cp_more", pts.length - SHOW), cls: "mp-cp", sub: pts.slice(SHOW).map((p) => Object.assign(back(p),
        { label: `${mark(p)} ${p.name || cpWords(p.reason)}`, keys: tlWhen(p.t), tip: tip(p) })) });
    }
    return items;
  }

  // ------------------------------------------------------------------ the header's words (app-model.js, app-conn.js)
  /** What Aspen is doing for a restore point, counting: "Creating a restore point 42 s / about 2 min", "Restoring 12 s". */
  function busyWords(a, since) {
    if (a.tool === "restore") return t("ms_rs_busy", since);
    const s = a.target && typeof a.target.est_s === "number" ? a.target.est_s : null;
    return s !== null ? t("ms_cp_busy_est", since, est(s)) : t("ms_cp_busy", since);
  }

  Object.assign(WBA, { busyWords, cpItems, cpMap, restoreOpen, undoClose: popClose, undoOpen, undoSync });
})();
