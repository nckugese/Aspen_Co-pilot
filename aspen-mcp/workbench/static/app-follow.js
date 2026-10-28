/* Following the AI's edits , off by default: "Follow AI edits", a switch in the review menu
 * (app-brake.js, brakeMenuAdd), remembered per viewer (pref wb.follow). While it is on, each edit the AI makes to a
 * block or stream of the model shown -- the heartbeat's calls (app-conn.js, wb.setServer): one in
 * flight, or the last one to end, ended ok -- brings the flowsheet to it: a zoom where names do
 * not read at this scale (FS.readable), the least pan clear of what floats over the drawing
 * (app-inspector.js, reveal), and a ring in the AI's violet (FS.ping). Nothing else shows, on or off.
 *
 * It never takes the view from the user: not while a press, a drag or a pan is on, the pointer
 * is over the flowsheet or its inspector, the flowsheet was touched (a press, the wheel, a key)
 * or left in the last REST_S, a value is being typed in the inspector, a menu, a dialog or a card
 * is open, a manual step waits or "Step through" plays, or the flowsheet does not show. What
 * was held back is done once, the latest only, when that ends. Moves are MIN_GAP_S apart; edits
 * between merge into the latest, so a batch of 200 moves a few times. Another model's edits,
 * and components, property methods and other paths not drawn, move nothing. Idle: no timer, no
 * frame (a held-back edit looks again every POLL_MS while what holds it sends no event).
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { $, brakeMenuAdd, closeMenus, esc, icon, now, num, prefGet, prefSet, reveal, sessOf, shownTab, t, wb } = WBA;

  const PREF = "wb.follow";
  const MIN_GAP_S = 1.5;       // two moves at least this far apart
  const REST_S = 4;            // the flowsheet touched or left this recently: not yet
  const KEEP_S = 60;           // a held-back edit older than this is dropped
  const DRAW_S = 5;            // how long an edit waits for its object to be drawn (a block just placed)
  const SAME_S = 5;            // the same object, still in view, flashed this recently: not again
  const POLL_MS = 500;
  const EDIT = /^(set|place|connect|disconnect|insert|add|remove)_/;   // the tools that change the model
  const GONE = /^remove_(block|stream)$/;                                // ... and leave nothing to show
  const isOn = () => prefGet(PREF) === "1";

  // since: edits that began or ended before this are not followed (the page's start, the switch
  // turned on); seen: the last ended call taken; calls: the calls in flight taken (their ids);
  // want: the edit to go to {session, tool, target, t}; at / key: the last flash, its object;
  // touchAt: the flowsheet last touched or left; pane: the pane whose flowsheet is watched
  const F = { since: now(), seen: 0, calls: [], want: null, timer: 0, at: 0, key: "", touchAt: 0, pane: null };

  /** A call of the AI's that changes a block or stream, not waiting (for a holder, an approval):
   *  its target names one (tools/intercept.target_of), or a name alone for a block's or stream's
   *  tool (add_component's is a component). */
  const has = (o, k) => o[k] != null && o[k] !== "";
  const isEdit = (a) => !!a && typeof a === "object" && a.actor === "ai" && typeof a.tool === "string"
    && EDIT.test(a.tool) && !GONE.test(a.tool) && a.phase !== "wait" && !!a.target && typeof a.target === "object"
    && (has(a.target, "block") || has(a.target, "stream") || (has(a.target, "name") && /block|stream/.test(a.tool)));

  /** The heartbeat changed: the newest edit not taken yet, on the model shown, becomes the one
   *  to go to. The calls in flight after the last one ended (act is oldest first). */
  function heard() {
    watch();
    const hb = wb.server, tab = shownTab();
    if (!hb || !tab || !isOn() || !wb.connected) return;
    let got = null;
    const l = hb.last;
    if (isEdit(l) && l.status === "ok" && num(l.end) && l.end > F.seen && l.end >= F.since) got = l;
    if (l && num(l.end)) F.seen = Math.max(F.seen, l.end);
    (Array.isArray(hb.act) ? hb.act : []).forEach((a) => {
      if (!isEdit(a) || !num(a.since) || a.since < F.since || !a.call || F.calls.includes(a.call)) return;
      F.calls = F.calls.concat([a.call]).slice(-40);
      got = a;
    });
    if (!got || got.session !== tab.session) return;          // another model's: #ai-bar names it
    F.want = { session: got.session, tool: got.tool, target: got.target, t: now() };
    tick();
  }

  /** The block or stream an edit names, as the flowsheet shown draws it ({kind, name}), or null:
   *  a stream first for a stream's tool (connect_stream names both), a name alone looked up. */
  function objOf(w, tab) {
    const fs = sessOf(tab).flowsheet || {}, tg = w.target, streamy = /stream/.test(w.tool);
    const find = (kind, name) => {
      const up = String(name).toUpperCase();
      const hit = ((kind === "block" ? fs.blocks : fs.streams) || []).find((x) => x && String(x.name).toUpperCase() === up);
      return hit ? { kind, name: String(hit.name) } : null;
    };
    const kinds = streamy ? ["stream", "block"] : ["block", "stream"];
    for (const k of kinds) if (has(tg, k)) { const o = find(k, tg[k]); if (o) return o; }
    if (has(tg, "name")) for (const k of kinds) { const o = find(k, tg.name); if (o) return o; }
    return null;
  }

  /** How long the user holds the view: 0 not; Infinity until the pointer leaves the flowsheet;
   *  else seconds to look again in. */
  function holdFor(pane, tab) {
    const svg = pane.svg, wrap = pane.q(".fs-wrap"), poll = POLL_MS / 1000;
    if (wrap.matches(":hover")) return Infinity;
    if (svg._fsHeld || FS.dragging(svg)) return poll;
    const rest = F.touchAt + REST_S - now();
    if (rest > 0) return rest;
    const gap = F.at + MIN_GAP_S - now();
    if (gap > 0) return gap;
    const shows = (el) => !!el && !el.classList.contains("hidden");
    const r = svg.getBoundingClientRect();
    if (document.hidden || !r.width || !r.height || pane.q(".pright").classList.contains("fs-off")) return poll;
    if (pane.editing || shows($("menu")) || shows($("menu2")) || shows($("modal")) || shows($("tour"))) return poll;
    // a card or popover (help, diagnosis, what is missing, a change's history, ...)
    if ([...document.querySelectorAll('[role="dialog"]')].some((el) => !el.closest(".ghost") && el.getClientRects().length)) return poll;
    if (window.WBW && typeof WBW.active === "function" && WBW.active()) return poll;   // "Step through" shows (walk.js)
    if (((wb.state && wb.state.tabs) || []).some((x) => x.session === tab.session && x.run && x.run.wait)) return poll;   // a manual step waits
    return 0;
  }

  /** Go to the edit wanted, now or when the user lets go of the view (the latest only). */
  function tick() {
    clearTimeout(F.timer);
    F.timer = 0;
    const w = F.want, pane = wb.pane, tab = shownTab();
    if (!w) return;
    if (!isOn() || !pane || !tab || tab.session !== w.session || now() - w.t > KEEP_S) { F.want = null; return; }
    const wait = holdFor(pane, tab);
    if (wait === Infinity) return;                           // (the pointer leaving calls again)
    if (wait > 0) { F.timer = setTimeout(tick, Math.ceil(wait * 1000) + 15); return; }
    const tg = objOf(w, tab);
    if (!tg || !drawn(pane, tg)) {                             // not drawn (yet: a block just placed)
      if (now() - w.t > DRAW_S) F.want = null;
      else F.timer = setTimeout(tick, POLL_MS);
      return;
    }
    F.want = null;
    go(pane, tg);
  }
  const drawn = (pane, tg) => [...pane.svg.querySelectorAll("[data-kind]")]
    .some((el) => el.getAttribute("data-kind") === tg.kind && el.getAttribute("data-name") === tg.name);

  /** Readable, in view, and a flash -- no second flash for the same object still in view. */
  function go(pane, tg) {
    const zoomed = FS.readable(pane.svg, tg), r = reveal(pane, tg, FS.RING_ROOM), key = `${tg.kind}:${tg.name}`;   // (room for the whole ring)
    if (!r) return;
    if (!zoomed && !r.moved && key === F.key && now() - F.at < SAME_S) return;
    FS.ping(pane.svg, tg, "ai");
    F.at = now();
    F.key = key;
  }

  /** The flowsheet's own hand: a press, the wheel or a key there, and the pointer leaving it
   *  (which lets a held-back edit through REST_S later). Wired once to the page's pane. */
  function watch() {
    const pane = wb.pane;
    if (!pane || F.pane === pane) return;
    F.pane = pane;
    const wrap = pane.q(".fs-wrap"), touch = () => { F.touchAt = now(); };
    ["pointerdown", "wheel", "keydown"].forEach((k) => wrap.addEventListener(k, touch, { capture: true, passive: true }));
    wrap.addEventListener("pointerleave", () => { touch(); if (F.want) tick(); });
  }

  /** The switch: on from now (what the AI did before is not gone to). */
  function toggle() {
    const on = !isOn();
    prefSet(PREF, on ? "1" : null);
    clearTimeout(F.timer);
    F.timer = 0;
    F.want = null;
    F.since = now();
    const l = wb.server && wb.server.last;
    if (l && num(l.end)) F.seen = Math.max(F.seen, l.end);
    F.calls = ((wb.server && wb.server.act) || []).map((a) => a && a.call).filter(Boolean);
  }

  brakeMenuAdd(() => {
    const on = isOn();
    return [{ html: `<button class="mi flw-mi" role="menuitemcheckbox" aria-checked="${on}" title="${esc(t("tip_follow_ai"))}">`
      + `<span class="flw-box" aria-hidden="true">${icon("check")}</span><span class="bt">${esc(t("follow_ai"))}</span></button>`,
      wire: (box) => box.querySelector(".flw-mi").addEventListener("click", () => { closeMenus(); toggle(); }) }];
  });

  const setServer = wb.setServer;
  wb.setServer = function (hb) {
    setServer.call(this, hb);
    WBA.guard("follow", heard);
  };

  Object.assign(WBA, { followOn: isOn });
})();
