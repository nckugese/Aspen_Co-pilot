/* Why a run failed. After a run that failed, ended with warnings or was refused for
 * incomplete inputs -- whoever ran it -- the server puts its diagnosis card in the session's
 * `diag` (tools/diagnose.py, built from what the run read: {v, level error | warn | refused, run,
 * blocks [{name, type, level, msg, lines, mech, upstream, first}], explain [{mech, title, text,
 * checks, blocks, run}], general, lore [{src, keyword, title, cause, fix, fix_path, block}],
 * suspects {state, since, run, items [{rec, path, op, before, after, actor, t, on_block,
 * upstream}], struct [...], more}, missing {n, objects, more?}, model, session, lang, t, pop,
 * fixed?}). window.py's Api.diagnosis({session | model, run?, lang}) builds one on request: another
 * language, or a run other than the latest (an Ask AI note about a run).
 *
 * The one-line bar (.diag-bar, the flowsheet's top left, once): only for the user's own Run or a
 * program they started (`pop`), not for a warning, and never for a card built before the page
 * came up. The card (.diag-card, a dialog that blocks nothing, in the same place): where it failed
 * (the most upstream block first, Aspen's own lines), the cause in plain words with what to check,
 * past cases from the error history (folded), what changed since the last good run (folded; each
 * row goes to its record in Changes, "Undo" takes it back through the undo preview), a refused
 * run's missing inputs (the missing-inputs panel), one small Ask AI (a note about the run: target {kind "run",
 * id, model, label}). A later good run marks it "Fixed".
 *
 * Where to look in Aspen: each block's line says so (Blocks › B › Results › Status), a cause of the
 * run as a whole is marked as the run's and gets a row of its own (Control Panel). A warning card
 * says the run converged; an error card names its first suspect under the failing block's cause
 * (above other blocks' warnings) and opens the changes since the last good run. A run refused for
 * Aspen's internal fault (fault: true) says that, never "inputs incomplete". Going to a block or
 * field from the card folds it to its head row and keeps the target clear of it; the bar sits
 * where it covers no block.
 *
 *   WBD.of(sess)                the session's card while it says something, else null
 *   WBD.open(tab, o)            the card (o.run: another run's, asked of the window), unfolded
 *   WBD.close(back)             close it; whether it was open
 *   WBD.fold()                  fold an open card to its head row; whether it did
 *   WBD.isOpen()
 *   WBD.sync()                  a new state: the bar, the card redrawn
 *   WBD.names(sess, block)      the card names this block (the inspector's link)
 *   WBD.panelItem(pane, tab)    the model panel's item, or null
 *   WBD.refusal(text)           a refusal the server worded, known: {kind (busy | paused | readonly |
 *                               incomplete | fault), words (the UI's own)}, else null
 *   WBD.clear(pane, target, el) after a pick: the target moved out from under el (a folded card)
 */
(function () {
  "use strict";
  const WBD = (window.WBD = {});
  const { esc, feature, fmtVal: fmt, hhmm, icon, list, popover, sessOf, t, who, words, zh } = WBA;
  const st = () => (window.wb && wb.state) || null;
  const LEVELS = ["error", "warn", "refused"];
  const LOADED = Date.now() / 1000;          // a card built before the page came up never pops

  WBD.of = (sess) => {
    const d = sess && sess.diag;
    return d && typeof d === "object" && LEVELS.includes(d.level) ? d : null;
  };
  // a card is its run's (a card built again -- another language, a newer scan of what is missing -- is the same one)
  const keyOf = (d) => (d ? String((d.run && d.run.id) || d.t || "") : "");
  WBD.names = (sess, block) => { const d = WBD.of(sess); return !!d && (d.blocks || []).some((b) => String(b.name).toUpperCase() === String(block).toUpperCase()); };

  /** The known refusals, by the server's words (main_tools, activity.py, brake.py, the workbench's
   *  own messages); the first that matches. A program paused at a step holds the model: busy. */
  const REFUSALS = [
    ["fault", /internal fault|SERVERFAULT|內部錯誤/i],
    ["incomplete", /inputs? (?:are )?incomplete|輸入不完整/],
    ["readonly", /read-only|\(Observe\)|Observe mode|唯讀/],
    ["busy", /is being changed by|holds the model|held by a workbench program|is running a program|'your turn' step|正在執行程式|正由.+修改|被程式占用/],
    ["paused", /paused (?:the AI|you)|still paused|已暫停 AI/],
  ];
  WBD.refusal = function (text) {
    const s = String(text || ""), hit = s && REFUSALS.find(([, rx]) => rx.test(s));
    return hit ? { kind: hit[0], words: t(`refuse_${hit[0]}`) } : null;
  };

  // ------------------------------------------------------------------ words
  /** The run in a few words: "Run #2 · 13:30" (who ran it only when it was not the user: · AI). */
  function runWords(r) {
    if (!r) return "";
    return [typeof r.seq === "number" ? t("mp_run_n", r.seq) : "", r.t ? hhmm(r.t) : "", r.actor && r.actor !== "user" ? who(r.actor) : ""]
      .filter(Boolean).join(" · ");
  }
  /** A refused run's card for Aspen's internal fault: nothing is incomplete then. */
  const faulted = (d) => !!d && d.level === "refused" && !!d.fault;
  const title = (d) => t(faulted(d) ? "diag_t_fault" : d.level === "refused" ? "diag_t_refused" : d.level === "warn" ? "diag_t_warn" : "diag_t_error");
  /** A cause of the run as a whole (the run's own messages named it, no block's did). */
  const runLevel = (x) => !!x && !!x.run && !(x.blocks || []).length;
  /** A field's path in words (labels.js), never a backslash. */
  const fieldWords = (path, tab) => WBL.say(String(path || ""), tab && tab.session);
  /** The first failing block and its cause, for the bar and an Ask AI note's label: only a cause
   *  that block's words named -- a cause of the run as a whole is never said of a block (none
   *  then); without a block, the first cause. */
  function lead(d) {
    const b = (d.blocks || []).find((x) => x.first) || (d.blocks || [])[0] || null;
    const m = b ? (d.explain || []).find((x) => (x.blocks || []).includes(b.name)) : (d.explain || [])[0];
    return { block: b ? b.name : "", why: (m && m.title) || "" };
  }

  // ------------------------------------------------------------------ the bar (once)
  const seen = new Map();        // session -> the key of the last card seen here
  const bars = new Map();        // session -> the key of the card whose bar shows
  function watch() {
    const s = st();
    if (!s) return;
    Object.entries(s.sessions || {}).forEach(([session, sess]) => {
      const d = WBD.of(sess), k = keyOf(d);
      if (!d) { bars.delete(session); return; }
      if (seen.get(session) === k) return;
      seen.set(session, k);
      const fresh = Number(d.t) >= LOADED - 2;
      if (d.pop && fresh && d.level !== "warn" && !d.fixed) bars.set(session, k);
      else bars.delete(session);
    });
  }
  function barEl(pane) {
    let el = pane.diagBar;
    if (el && el.isConnected) return el;
    el = pane.diagBar = document.createElement("div");
    el.className = "diag-bar plate hidden";
    el.setAttribute("role", "status");
    pane.q(".fs-wrap").appendChild(el);
    el.addEventListener("click", (ev) => {
      const b = ev.target.closest && ev.target.closest("[data-f]"), tab = WBA.shownTab();
      if (!b || !tab) return;
      bars.delete(tab.session);
      if (b.dataset.f === "see") WBD.open(tab, { from: "bar" });
      renderBar();
    });
    return el;
  }
  function renderBar() {
    const pane = window.wb && wb.pane, tab = WBA.shownTab();
    if (!pane || !pane.q) return;
    const d = tab ? WBD.of(sessOf(tab)) : null, k = keyOf(d);
    const show = !!d && !d.fixed && bars.get(tab.session) === k && !(C && C.session === tab.session);
    if (!show) { if (pane.diagBar) { pane.diagBar.classList.add("hidden"); pane.diagBar.dataset.sig = ""; } return; }
    const el = barEl(pane), L = lead(d);
    const text = faulted(d) ? t("diag_bar_fault") : d.level === "refused" ? t("diag_bar_refused")
      : L.block ? (L.why ? t("diag_bar", L.block, L.why) : t("diag_bar_blk", L.block)) : t("diag_bar_run");
    const tip = faulted(d) ? `${text}\n${t("tip_diag_fault")}` : d.level === "refused" ? `${text}\n${t("tip_diag_refused")}` : text;
    const sig = JSON.stringify([I18N.lang, k, text]);
    if (el.dataset.sig === sig) return;
    el.dataset.sig = sig;
    el.className = `diag-bar plate ${d.level}`;
    el.innerHTML = `${icon("warn")}<span class="db-t" title="${esc(tip)}">${esc(text)}</span>`
      + `<button class="db-see" data-f="see">${esc(t("diag_see"))}</button>`
      + `<button class="db-x flat icon" data-f="x" title="${esc(t("close"))}" aria-label="${esc(t("close"))}">${icon("close")}</button>`;
    el.classList.add("in");
    placeBar(pane, el, L.block);
  }
  /** The bar where it covers no block: along the flowsheet's top (under its tools, left of the
   *  inspector) or its bottom, the free spot nearest the top left; else the one covering least
   *  (the failing block counts thrice, and nothing floating over the drawing may be covered). */
  function placeBar(pane, el, failing) {
    const wrap = pane.q(".fs-wrap"), svg = pane.svg;
    el.style.left = el.style.top = "";
    if (!wrap || !svg || !svg.querySelectorAll) return;
    const W = wrap.getBoundingClientRect(), w = el.offsetWidth, h = el.offsetHeight, cs = getComputedStyle(el);
    if (!W.width || !w) return;
    const ins = window.FS && FS.insets ? FS.insets(svg) : { right: 0, bottom: 0 };
    const m = 10, x0 = parseFloat(cs.left) || m, y0 = parseFloat(cs.top) || 52;     // (the CSS spot: its rise does not count)
    const xMax = W.width - ins.right - m - w, yLow = W.height - (ins.bottom || 0) - m - h;
    const rel = (r) => ({ l: r.left - W.left, t: r.top - W.top, r: r.right - W.left, b: r.bottom - W.top });
    const up = String(failing || "").toUpperCase();
    const blocks = [...svg.querySelectorAll('g.fs-node[data-kind="block"]')].map((g) => {
      const r = (g.querySelector("rect") || g).getBoundingClientRect();
      return r.width ? Object.assign(rel(r), { k: String(g.getAttribute("data-name")).toUpperCase() === up ? 3 : 1 }) : null;
    }).filter(Boolean);
    const floats = [...wrap.querySelectorAll(".fs-hint:not(.hidden), .fs-plan:not(.hidden), .insp:not(.hidden), .fs-far:not(.hidden), .fs-peek:not(.hidden)")]
      .map((x) => x.getBoundingClientRect()).filter((r) => r.width).map((r) => Object.assign(rel(r), { k: 50 }));
    const over = (x, y) => [...blocks, ...floats].reduce((s, o) => s + o.k
      * Math.max(0, Math.min(x + w, o.r) - Math.max(x, o.l)) * Math.max(0, Math.min(y + h, o.b) - Math.max(y, o.t)), 0);
    const xs = [];
    for (let x = x0; x < xMax; x += 16) xs.push(x);
    xs.push(Math.max(x0, xMax));
    let best = null;
    for (const y of yLow > y0 + h ? [y0, yLow] : [y0]) {
      for (const x of xs) {
        const s = over(x, y);
        if (!best || s < best.s) best = { x, y, s };
        if (!s) break;
      }
      if (best && !best.s) break;
    }
    if (best && (best.x !== x0 || best.y !== y0)) { el.style.left = `${Math.round(best.x)}px`; el.style.top = `${Math.round(best.y)}px`; }
  }

  // ------------------------------------------------------------------ the card
  let C = null;                  // the card open: {el, tab, session, run, card, err, open, sig, back, min (folded)}
  const cache = new Map();       // session|run|lang|t -> a card from the window
  WBD.isOpen = () => !!C;
  function apiFn() {
    const a = window.pywebview && window.pywebview.api;
    return a && typeof a.diagnosis === "function" ? (req) => Promise.resolve().then(() => a.diagnosis.call(a, req)) : null;
  }
  WBD.open = function (tab, o = {}) {
    const pane = window.wb && wb.pane;
    if (!tab || !pane || pane.tabId !== tab.id) return false;
    WBM.close();                                                 // one card over the flowsheet at a time
    if (WBA.prefs().dockMode === "max") WBA.setDock(pane, "split");
    const fresh = !C;
    if (!C) {
      const { el, off } = popover(pane.q(".fs-wrap"), "diag-card", "diag-title", { close: (back) => WBD.close(back),
        keep: ".diag-bar, #modelstat, .insp, #menu, #menu2, #modal, #toast, .uv-pop, .fh-card, .ierr, .miss-pop" });
      C = { el, off, open: new Set(), back: document.activeElement };
      el.addEventListener("click", onClick);
      el.addEventListener("toggle", onToggle, true);
    }
    Object.assign(C, { tab: tab.id, session: tab.session, pane, run: o.run || null, card: null, err: null, sig: null, want: null, min: false });
    bars.delete(tab.session);
    renderBar();
    load();
    if (fresh) { C.el.classList.add("in"); C.el.focus({ preventScroll: true }); }
    return true;
  };
  /** The card folded to its head row (the inspector opened from it: the flowsheet shows again). */
  WBD.fold = function () {
    if (!C || C.min) return false;
    C.min = true;
    C.sig = null;
    draw();
    return true;
  };
  function unfold() {
    if (!C || !C.min) return;
    C.min = false;
    C.sig = null;
    draw();
    C.el.focus({ preventScroll: true });
  }
  /** After a pick from a folded card or panel (el): a target under it moved clear of it (below
   *  it, FS.reveal), ringed again. Whether the view moved. */
  WBD.clear = function (pane, target, el) {
    if (!pane || !pane.svg || !target || !el || !el.isConnected || !window.FS || !FS.reveal) return false;
    const now = FS.reveal(pane.svg, target, null);          // (picked just now: in view, so this only measures)
    if (!now || !now.rect) return false;
    const a = now.rect, c = el.getBoundingClientRect(), g = 6;
    if (!(a.left < c.right + g && c.left < a.right + g && a.top < c.bottom + g && c.top < a.bottom + g)) return false;
    const s = pane.svg.getBoundingClientRect();
    const r = FS.reveal(pane.svg, target, { top: Math.max(0, c.bottom - s.top + g), bottom: 0, pad: FS.RING_ROOM || 0 });
    WBA.renderEdges(pane);
    if (r && r.moved && FS.ping) FS.ping(pane.svg, target);
    return !!(r && r.moved);
  };
  WBD.close = function (back) {
    const c = C;
    if (!c) return false;
    C = null;
    c.off(back, c.back);
    return true;
  };
  /** A fold opened or closed: drawn again (a fold's contents are drawn only while it is open, so
   *  nothing folded takes the pointer), the focus kept on its summary. The first block's lines
   *  are open until closed by hand (!key). */
  function onToggle(ev) {
    const d = ev.target, k = d && d.dataset ? d.dataset.d : "";
    if (!C || !k) return;
    const had = d.contains(document.activeElement), was = C.open.has(k) || (d.dataset.first === "1" && !C.open.has(`!${k}`));
    if (d.open === was) return;
    if (d.open) { C.open.add(k); C.open.delete(`!${k}`); } else { C.open.delete(k); C.open.add(`!${k}`); }
    C.sig = null;
    draw();
    const s = had && [...C.el.querySelectorAll("details[data-d]")].find((x) => x.dataset.d === k);
    if (s) s.querySelector("summary").focus({ preventScroll: true });
  }
  /** The card to show: the session's own where it is about that run and in the page's language,
   *  else the window's (Api.diagnosis), asked once per run, language and card. */
  function load() {
    const c = C;
    if (!c) return;
    const s = st(), tab = s && (s.tabs || []).find((x) => x.id === c.tab), sess = sessOf(tab), d = WBD.of(sess);
    const lang = zh() ? "zh" : "en", rid = c.run || (d && d.run && d.run.id) || null;
    const own = d && (!c.run || (d.run && d.run.id === c.run));
    if (own && (d.lang || lang) === lang) { c.card = d; c.err = null; draw(); return; }
    const fn = apiFn();
    if (!fn) { c.card = own ? d : null; c.err = own ? null : "Api.diagnosis"; draw(); return; }
    const key = [c.session, rid, lang, d ? d.t : 0, d && d.fixed ? 1 : 0].join("|");
    if (cache.has(key)) { c.card = cache.get(key); draw(); return; }
    if (c.want === key) return;
    c.want = key;
    c.card = own ? d : null;                     // (the session's, in its language, meanwhile)
    draw();
    const model = (sess.model && sess.model.id) || (d && d.model) || null;
    fn(Object.assign({ session: c.session, lang }, model ? { model } : {}, rid ? { run: rid } : {})).then((card) => {
      if (C !== c || c.want !== key) return;
      if (!card || typeof card !== "object" || card.error) { c.err = (card && card.error) || "?"; c.sig = null; draw(); return; }
      if (own && d.fixed && !card.fixed) card.fixed = d.fixed;
      cache.set(key, card);
      c.card = card;
      c.sig = null;
      draw();
    }, (e) => { if (C === c) { c.err = String((e && e.message) || e || "?"); c.sig = null; draw(); } });
  }
  WBD.sync = function () {
    watch();
    renderBar();
    if (!C) return;
    const pane = window.wb && wb.pane, s = st(), tab = s && (s.tabs || []).find((x) => x.id === C.tab);
    if (!tab || !pane || pane.tabId !== tab.id) { WBD.close(); return; }
    load();
  };

  // ------------------------------------------------------------------ drawing the card
  /** The head row: the state's dot, the title, the run, "Fixed", and ✕; folded, a chevron that
   *  unfolds it (a click on the row does too). */
  function headHtml(d, min) {
    const fx = d.fixed;
    const tip = d.level === "warn" ? ` title="${esc(t("tip_diag_t_warn"))}"` : faulted(d) ? ` title="${esc(t("tip_diag_fault"))}"`
      : d.level === "refused" ? ` title="${esc(t("tip_diag_refused"))}"` : "";
    const un = min ? `<button class="dc-un flat icon" data-f="unfold" aria-expanded="false" title="${esc(t("diag_unfold"))}" aria-label="${esc(t("diag_unfold"))}">${icon("chevron-down")}</button>` : "";
    return `<div class="dc-h"><i class="dc-dot ${esc(d.level)}${fx ? " fixed" : ""}" aria-hidden="true"></i>`
      + `<div class="dc-t"><b id="diag-title"${tip}>${esc(title(d))}</b><small>${esc(runWords(d.run))}</small></div>`
      + (fx ? `<span class="dc-fixed" title="${esc(t("tip_diag_fixed", runWords(fx)))}">${icon("check")}${esc(t("diag_fixed"))}</span>` : "")
      + un + `<button class="dc-x flat icon" data-f="close" title="${esc(t("close"))}" aria-label="${esc(t("close"))}">${icon("close")}</button></div>`;
  }
  /** One short line under the head where the state says something the title does not: a warning
   *  run converged (Aspen's Results with warnings; the server's words where the card has them,
   *  its ``state``); a fault asks for the model to be reopened. */
  function stateHtml(d) {
    if (faulted(d)) return `<p class="dc-state fault" title="${esc(t("tip_diag_fault"))}">${icon("info")}<span>${esc(t("diag_fault_do"))}</span></p>`;
    if (d.level !== "warn") return "";
    const said = typeof d.state === "string" && d.state.trim() ? d.state : t("diag_state_warn");
    return `<p class="dc-state ok" title="${esc(t("tip_diag_state_warn"))}">${icon("check")}<span>${esc(said)}</span></p>`;
  }
  /** Where in Aspen to look, as a chip: a block's Results form, Status sheet; the run's Control Panel. */
  const atHtml = (where, tip) => `<p class="dc-at" title="${esc(tip)}">${esc(t("in_aspen", where))}</p>`;
  /** The run's own messages: the session's while the card is about its latest run. */
  function runMsgs(sess) {
    const own = WBD.of(sess), latest = !C.run || (own && own.run && own.run.id === C.run);
    return latest ? (sess.run_msgs || []).filter((x) => String(x).trim()) : [];
  }
  /** The run as a whole: its row (Control Panel) and its messages folded (open by default where
   *  it is the only place named: no block). */
  function runRowHtml(sess, alone) {
    const msgs = runMsgs(sess), key = "run", open = C.open.has(key) || (alone && !C.open.has(`!${key}`));
    return `<div class="dc-b dc-rb"><div class="dc-bh"><b class="dc-rn" title="${esc(t("tip_diag_run_row"))}">${esc(t("diag_run_row"))}</b></div>`
      + atHtml("Control Panel", t("tip_diag_at_run"))
      + (msgs.length ? `<details class="dc-d dc-ln" data-d="${key}"${alone ? ' data-first="1"' : ""}${open ? " open" : ""}><summary>${esc(t("diag_run_lines"))}</summary>`
        + (open ? `<pre lang="en">${esc(msgs.join("\n"))}</pre>` : "") + "</details>" : "")
      + "</div>";
  }
  /** Where it failed: each block, the most upstream first (marked), Aspen's line, where in Aspen;
   *  its lines folded (the first one's open). The run as a whole where no block has any, or where
   *  a cause is the run's own (its lines folded). */
  function whereHtml(d, sess) {
    const blocks = d.blocks || [];
    if (d.level === "refused") return "";
    let h = "";
    if (blocks.length) {
      h = blocks.map((b, i) => {
        const key = `b:${b.name}`, open = C.open.has(key) || (i === 0 && !C.open.has(`!${key}`));
        const lvl = b.level === "warn" ? `<em class="dc-lv warn">${esc(t("lvl_warn"))}</em>` : "";
        const first = b.first && blocks.length > 1 ? `<em class="dc-first" title="${esc(t("tip_diag_first"))}">${esc(t("diag_first"))}</em>` : "";
        const lines = (b.lines || []).filter((x) => String(x).trim());
        return `<div class="dc-b"><div class="dc-bh"><button class="dc-bn flat" data-f="block" data-name="${esc(b.name)}" title="${esc(t("tip_log_show", b.name))}">`
          + `${icon("block")}<b>${esc(b.name)}</b></button>${b.type ? `<small>${esc(b.type)}</small>` : ""}${lvl}${first}</div>`
          + (b.msg ? `<p class="dc-msg" lang="en">${esc(b.msg)}</p>` : "")
          + (String(b.name).startsWith("$") ? "" : atHtml(`Blocks › ${b.name} › Results › Status`, t("tip_diag_at")))   // ($: Aspen's own convergence block)
          + (lines.length ? `<details class="dc-d dc-ln" data-d="${esc(key)}"${i === 0 ? ' data-first="1"' : ""}${open ? " open" : ""}><summary>${esc(t("diag_lines"))}</summary>`
            + (open ? `<pre lang="en">${esc(lines.join("\n"))}</pre>` : "") + "</details>" : "")
          + "</div>";
      }).join("");
      if ((d.explain || []).some(runLevel)) h += runRowHtml(sess, false);
    } else if (runMsgs(sess).length || (d.explain || []).some(runLevel)) {
      h = runRowHtml(sess, true);
    }
    return h ? `<section class="dc-s"><h4>${esc(t("diag_where"))}</h4>${h}</section>` : "";
  }
  /** The change since the last good run most likely behind a failure: on the failing block, else
   *  upstream of it, else the first. */
  function firstSuspect(d) {
    const S = d.suspects;
    if (!S || !["ok", "never_ok"].includes(S.state)) return null;
    const rows = [...(S.items || []), ...(S.struct || [])];
    return rows.find((x) => x.on_block) || rows.find((x) => x.upstream) || rows[0] || null;
  }
  const susTag = (x) => (x.on_block ? `<em class="dc-tag on">${esc(t("diag_on_block"))}</em>` : x.upstream ? `<em class="dc-tag">${esc(t("diag_upstream"))}</em>` : "");
  /** The cause: the blocks' first, then the run's own (marked as the run's: they are no block's);
   *  on a failure, the first suspect right under the failing blocks' causes (above the
   *  warnings of other blocks, not after them); the general checks folded. */
  function causeHtml(d, tab) {
    const ex = (d.explain || []).filter((x) => x && (x.title || x.text));
    const sus = d.level === "error" ? firstSuspect(d) : null;
    if (!ex.length && !sus) return "";
    const many = (d.blocks || []).length > 1;
    const one = (x) => `<div class="dc-m"><b>${esc(x.title)}</b>`
      + (runLevel(x) ? `<small class="dc-rl" title="${esc(t("tip_diag_run_row"))}">${esc(t("diag_run_row"))}</small>`
        : many && (x.blocks || []).length ? `<small>${esc(x.blocks.join(", "))}</small>` : "")
      + (x.text ? `<p>${esc(x.text)}</p>` : "")
      + ((x.checks || []).length ? `<p class="dc-ck">${esc(t("diag_checks"))}</p><ul class="dc-cl">${x.checks.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>` : "") + "</div>";
    // a failure's: the causes on a failing block (not a warning's), then the first suspect, then the rest
    const failing = new Set((d.blocks || []).filter((b) => b.level !== "warn").map((b) => b.name));
    const onFail = (x) => !runLevel(x) && (x.blocks || []).some((n) => failing.has(n));
    const head = sus ? ex.filter(onFail) : [], rest = [...ex.filter((x) => !runLevel(x) && !head.includes(x)), ...ex.filter(runLevel)];
    let h = `<section class="dc-s"><h4>${esc(t("diag_mech"))}</h4>${head.map(one).join("")}`;
    if (sus) {
      h += `<div class="dc-lead"><span class="dc-k" title="${esc(t("tip_diag_sus_first"))}">${esc(t("diag_sus_first"))}</span>`
        + `<button class="dc-sl flat" data-f="record" data-rec="${esc(sus.rec || "")}" data-path="${esc(sus.path || "")}" title="${esc(t("tip_diag_sus_row"))}">`
        + `<span class="dc-sw">${esc(susWords(sus, tab))}</span></button>${susTag(sus)}</div>`;
    }
    h += rest.map(one).join("");
    if ((d.general || []).length) {
      const on = C.open.has("general");
      h += `<details class="dc-d" data-d="general"${on ? " open" : ""}><summary>${esc(t("diag_general"))}</summary>`
        + (on ? `<ul class="dc-cl">${d.general.map((g) => `<li>${esc(g)}</li>`).join("")}</ul>` : "") + "</details>";
    }
    return h + "</section>";
  }
  function missHtml(d) {
    const m = d.missing;
    if (d.level !== "refused" || !m) return "";
    const objs = (m.objects || []).map(WBM.objName).filter(Boolean);
    const n = Number(m.n) || objs.length;
    const see = `<button class="dc-go" data-f="missing">${esc(t("show"))}</button>`;
    return `<section class="dc-s"><div class="dc-sh"><h4>${esc(t("diag_missing", n))}</h4>${see}</div>`
      + (objs.length ? `<p class="dc-objs">${esc(list(objs))}${Number(m.more) > 0 ? ` …` : ""}</p>` : "") + "</section>";
  }
  /** Aspen's dotted paths in an error-history text, named: `Data.Blocks.{name}.Input.BASIS_D` ->
   *  ESTCOL › BASIS_D (the block the entry matched), a stream's {name} left as … */
  function loreText(s, block) {
    return String(s || "").replace(/`?Data\.((?:Blocks|Streams)\.)?([^`\s]+?)`?(?=[\s,;:)]|$)/g, (m, sec, rest) => {
      const parts = rest.split(".");
      if (sec === "Blocks.") parts[0] = parts[0] === "{name}" ? (block || "…") : parts[0];
      else if (sec === "Streams.") parts[0] = parts[0] === "{name}" ? "…" : parts[0];
      return parts.filter((p) => p !== "Input" && p !== "Output").join(" › ");
    }).replace(/\\/g, " › ");
  }
  function loreHtml(d, tab) {
    const lo = (d.lore || []).filter((x) => x && (x.title || x.fix || x.cause));
    if (!lo.length) return "";
    const one = (x) => {
      const src = x.src === "user" ? "user" : "docs";
      const fix = x.fix_path ? `<button class="dc-fp flat" data-f="field" data-path="${esc(x.fix_path)}" title="${esc(t("tip_diag_fix_path"))}">${icon("eye")}<span>${esc(fieldWords(x.fix_path, tab))}</span></button>` : "";
      return `<div class="dc-lo"><div class="dc-loh"><span class="dc-src ${src}" title="${esc(t(`tip_diag_lore_${src}`))}">${esc(t(`diag_lore_${src}`))}</span>`
        + `<span lang="en">${esc(loreText(x.title, x.block))}</span></div>`
        + (x.cause ? `<p><span class="dc-k">${esc(t("diag_lo_cause"))}</span><span lang="en">${esc(loreText(x.cause, x.block))}</span></p>` : "")
        + (x.fix ? `<p><span class="dc-k">${esc(t("diag_lo_fix"))}</span><span lang="en">${esc(loreText(x.fix, x.block))}</span></p>` : "")
        + fix + "</div>";
    };
    const on = C.open.has("lore");
    return `<details class="dc-d dc-s" data-d="lore"${on ? " open" : ""}><summary title="${esc(t("tip_diag_lore"))}">${esc(t("diag_lore", lo.length))}</summary>${on ? lo.map(one).join("") : ""}</details>`;
  }
  /** One change since the last good run, in words: ESTCOL › Distillate rate 40 → 120 kmol/hr. */
  function susWords(x, tab) {
    if (x.op === "value" || x.op === "attr" || x.path && !x.kind) {
      const b = x.before || {}, a = x.after || {}, unit = a.unit || b.unit || "";
      return `${fieldWords(x.path, tab)}  ${fmt(b.value)} → ${fmt(a.value)}${unit ? ` ${unit}` : ""}`;
    }
    const name = x.name || x.block || (String(x.path || "").split("\\").pop());
    if (x.op === "add") return t("mp_st_add", name);
    if (x.op === "remove") return t("mp_st_remove", name);
    if (x.op === "connect") return t("mp_st_connect", name);
    return `${x.op || ""} ${name}`.trim();
  }
  function susHtml(d, tab) {
    const S = d.suspects;
    if (!S || !["ok", "never_ok"].includes(S.state)) return "";
    const rows = [...(S.items || []), ...(S.struct || [])];
    if (!rows.length) return "";
    const undo = feature("undo") && !!(window.wb && wb.connected);
    const one = (x) => {
      const tags = susTag(x);
      const meta = [who(x.actor), x.t ? hhmm(x.t) : ""].filter(Boolean).join(" · ");
      const back = undo && x.rec && ["value", "attr", "add", "remove", "connect"].includes(x.op)
        ? `<button class="dc-rv flat" data-f="revert" data-rec="${esc(x.rec)}" title="${esc(t("tip_diag_revert"))}">${icon("undo")}<span>${esc(t("undo"))}</span></button>` : "";
      return `<li class="dc-su"><button class="dc-sl flat" data-f="record" data-rec="${esc(x.rec || "")}" data-path="${esc(x.path || "")}" title="${esc(t("tip_diag_sus_row"))}">`
        + `<span class="dc-sw">${esc(susWords(x, tab))}</span></button>${tags}<small class="dc-sm">${esc(meta)}</small>${back}</li>`;
    };
    const n = rows.length + (Number(S.more) || 0);
    const head = S.state === "never_ok" ? `<summary title="${esc(t("tip_diag_sus_never"))}">${esc(t("diag_sus_never", n))}</summary>` : `<summary>${esc(t("diag_sus", n))}</summary>`;
    // a failure's: open until closed by hand (its first answer); a warning's folded
    const first = d.level === "error", on = C.open.has("sus") || (first && !C.open.has("!sus"));
    return `<details class="dc-d dc-s" data-d="sus"${first ? ' data-first="1"' : ""}${on ? " open" : ""}>${head}`
      + (on ? `<ul class="dc-sus">${rows.map(one).join("")}</ul>` + (Number(S.more) > 0 ? `<p class="dc-q">${esc(t("diag_sus_more", S.more))}</p>` : "") : "")
      + "</details>";
  }
  function html(tab, sess) {
    const c = C, d = c.card;
    if (!d) {
      const close = `<button class="dc-x flat icon" data-f="close" title="${esc(t("close"))}" aria-label="${esc(t("close"))}">${icon("close")}</button>`;
      const known = c.err ? WBD.refusal(c.err) : null;          // (a known refusal: the UI's words, the server's in the tooltip)
      return `<div class="dc-h"><div class="dc-t"><b id="diag-title">${esc(t("diag_t_error"))}</b></div>${close}</div>`
        + (c.min ? "" : `<p class="dc-q"${known ? ` title="${esc(c.err)}"` : ""}>${esc(c.err ? t("diag_err", known ? known.words : words(c.err)) : t("diag_loading"))}</p>`);
    }
    if (c.min) return headHtml(d, true);
    let h = headHtml(d) + stateHtml(d) + whereHtml(d, sess) + causeHtml(d, tab) + missHtml(d) + loreHtml(d, tab) + susHtml(d, tab);
    const run = d.run && d.run.id;
    if (run) h += `<div class="dc-f"><button class="dc-ask" data-f="ask" title="${esc(t("tip_diag_ask"))}">${icon("sparkle")}<span class="bt">${esc(t("ask_ai"))}</span></button></div>`;
    return h;
  }
  function draw() {
    const c = C, s = st();
    if (!c || !s) return;
    const tab = (s.tabs || []).find((x) => x.id === c.tab), sess = sessOf(tab);
    const sig = JSON.stringify([I18N.lang, c.card, c.err, [...c.open], wb.connected, feature("undo"), sess.run_msgs || null, WBL.ver, !!c.min]);
    if (c.sig === sig) return;
    const top = c.el.scrollTop;
    c.sig = sig;
    c.el.classList.toggle("min", !!c.min);
    c.el.innerHTML = html(tab, sess);
    c.el.scrollTop = c.min ? 0 : top;
  }

  // ------------------------------------------------------------------ what is done in it
  function onClick(ev) {
    const b = ev.target.closest && ev.target.closest("[data-f]"), c = C, s = st();
    const tab = c && s ? (s.tabs || []).find((x) => x.id === c.tab) : null;
    if (c && c.min && !b && ev.target.closest && ev.target.closest(".dc-h")) { unfold(); return; }   // (the folded head row)
    if (!b || !tab || b.disabled) return;
    const f = b.dataset.f, pane = c.pane, d = c.card || {};
    if (f === "close") WBD.close(true);
    else if (f === "unfold") unfold();
    else if (f === "block") goTo(pane, tab, { kind: "block", name: b.dataset.name }, null);
    else if (f === "field") fieldGo(pane, tab, b.dataset.path);
    else if (f === "missing") { if (window.WBM) WBM.open(tab); }
    else if (f === "record") recordGo(pane, tab, b.dataset.rec, b.dataset.path);
    else if (f === "revert") revert(tab, d, b);
    else if (f === "ask") ask(pane, tab, d);
  }
  /** A block or stream from the card: the card folds to its head row, the target is picked (the
   *  inspector at path) and kept clear of it. One no longer drawn: gotoChange says so. */
  function goTo(pane, tab, target, path) {
    const fs = sessOf(tab).flowsheet || {}, up = String(target.name).toUpperCase();
    const hit = ((target.kind === "stream" ? fs.streams : fs.blocks) || []).find((x) => x && String(x.name).toUpperCase() === up);
    if (hit) WBD.fold();
    WBA.gotoChange(pane, target, path);
    if (hit && C) WBD.clear(pane, { kind: target.kind, name: hit.name }, C.el);
  }
  /** A field (an error-history entry's fix): its block or stream picked, the inspector at it. */
  function fieldGo(pane, tab, path) {
    const m = /^\\Data\\(Blocks|Streams)\\([^\\]+)/i.exec(String(path || ""));
    if (m) goTo(pane, tab, { kind: /^b/i.test(m[1]) ? "block" : "stream", name: m[2] }, path);
  }
  /** A suspect's record in the Changes tab (its card opened at the row); without the timeline, its
   *  field in the inspector. */
  function recordGo(pane, tab, rec, path) {
    if (rec && WBC.on()) {
      if (WBA.prefs().dockMode === "min") WBA.setDock(pane, "split");
      WBA.showPanel(pane, "changes");
      WBC.showGroup(pane.q(".tab-changes"), WBA.changesCtx(pane, tab), null, rec);
      return;
    }
    if (path) fieldGo(pane, tab, path);
  }
  /** Take a suspect back: the undo preview under the button (app-undo.js). */
  function revert(tab, d, btn) {
    const S = d.suspects || {}, rec = btn.dataset.rec;
    const x = [...(S.items || []), ...(S.struct || [])].find((y) => y.rec === rec);
    if (!x) return;
    const field = x.op === "value" || x.op === "attr";
    WBA.undoOpen(tab, { ids: [rec], anchor: btn, label: field ? fieldWords(x.path, tab) : susWords(x, tab), field });
  }
  /** Ask AI about this run: the composer's chip on it (target {kind "run", id, model, label}) and a
   *  line to start from; nothing is sent until Send (without the run's id: the failing block). */
  function ask(pane, tab, d) {
    const L = lead(d), run = d.run || {};
    const label = faulted(d) ? t("diag_lbl_fault") : d.level === "refused" ? t("diag_lbl_refused")
      : L.block ? t(d.level === "warn" ? "diag_lbl_warn" : "diag_lbl_error", L.block)
      : typeof run.seq === "number" ? t("diag_lbl_run", run.seq) : t("diag_t_error");
    const model = d.model || ((sessOf(tab).model || {}).id) || null;
    WBD.close();
    const pin = run.id && model ? { pin: { target: { kind: "run", id: run.id, model, label } } }
      : L.block ? { pin: { target: { kind: "block", name: L.block } } } : {};
    WBA.focusComposer(pane, Object.assign(pin, { text: t("diag_ask_text") }));
  }

  // ------------------------------------------------------------------ the model panel
  WBD.panelItem = function (pane, tab) {
    const d = WBD.of(sessOf(tab));
    if (!d) return null;
    const label = d.fixed ? `${t("mp_diag")} · ${t("diag_fixed")}` : t("mp_diag");
    return { label, icon: d.fixed ? "check" : "warn", cls: `mp-diag ${d.fixed ? "fixed" : d.level}`, tip: t("tip_mp_diag"), run: () => WBD.open(tab) };
  };
})();
