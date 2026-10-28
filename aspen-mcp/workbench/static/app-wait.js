/* The wait for the AI, in the chat: one quiet line under the newest request still waiting, or at the
 * chat's end while the AI thinks with no request waiting here.
 *
 * "AI is thinking…" (ai_think) has two places, and only two: the header's pill (app-conn.js) and this line. Both
 * come from one state, WBA.think (app-conn.js renderThink: the AI's turn running), drawn at the same
 * moment with the same seconds: renderThink calls waitThink right after the pill. While it holds,
 * the line says it whatever else is true of the request (a request not yet delivered is told under
 * the chat box as well, app-chat.js). Otherwise, under a request waiting: sent (the seconds since);
 * queued, or said delivered but untouched (what to say to the AI in the client; tooltip: how to
 * connect the channel); not connected. What the AI is calling is #ai-bar's, in the header.
 *
 * It never says the AI works when it cannot know. The server pushes each request to the AI
 * (state.channel) and marks the note delivered (the client is known to take it: state.listening,
 * a hook handed it, the AI read it), pushed (the client may drop it) or undelivered. A request not
 * known delivered is waited on CFG.pickup s, then the line says it is queued, unless the heartbeat
 * shows the AI at work after it. Delivered by the channel is only probable (state.listening is the
 * user's ASPEN_MCP_CHANNELS): unless the AI read it, a hook handed it, or the AI was seen at work
 * after it, it is waited on CFG.grace s, then the line says the AI has not answered. A request open
 * longer than CFG.maxAge is not waited on, nor one an AI message came after.
 *
 * After CFG.gameAfter s of thinking or waiting, "Play while waiting" opens a small canvas game
 * (games/*.js, one file each, on games/frame.js) in a card of its own under the chat list: one at
 * random, the card's ↻ the next. A reply that comes meanwhile leaves the game where it is: its
 * header says so, and closing the game (or that line) goes to the reply. Each game keeps its best
 * score (prefs wb.wait.best.<id>).
 *
 * Nothing runs unseen: the line's own 1 s timer (while it counts a sent request) only while it is
 * on screen (IntersectionObserver) and the window shows; the game draws only while played, on
 * screen, in a shown window, and pauses when it loses the focus. app-chat.js calls waitRender right
 * after it redraws the list, so the line is back under its request before the list is scrolled.
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { atEnd, esc, familyOf, icon, isObj, listFades, now, num, prefGet, prefSet, sessOf, t, tabOf, wb } = WBA;
  const { gotoNote, since } = WBA.later;

  // gameAfter: s before the game is offered; maxAge: s after which an open request is no longer
  // waited on; pickup: s a request not known delivered is waited on before the user is told to
  // prompt the AI; grace: the same for one said delivered (unchecked) that the AI has not touched
  const CFG = (WBA.waitCfg = { gameAfter: 8, maxAge: 1800, pickup: 12, grace: 20 });
  // how to have requests arrive at once (INSTALL.md, docs/mcp/workbench/requests.md: "How requests reach the AI")
  const CHANNEL_CMD = {
    claude: '$env:ASPEN_MCP_CHANNELS = "1"; claude --dangerously-load-development-channels plugin:aspen-plus@aspen-mcp',
    codex: "%USERPROFILE%\\.aspen-mcp\\codex-aspen.cmd" };
  const isCodex = () => /codex/i.test(String((((wb.state || {}).brake) || {}).client || ""));
  /** The client the AI runs in, by name ("Claude Code" / "Codex"). */
  WBA.aiClient = () => (isCodex() ? "Codex" : "Claude Code");
  /** The tooltip line on connecting the channel, so a request reaches the AI at once. */
  WBA.channelTip = () => (isCodex() ? t("cw_chan_codex", CHANNEL_CMD.codex)
    : t("cw_chan", ((wb.state || {}).channel_cmd) || CHANNEL_CMD.claude));   // the server names itself
  const W = { key: "", at: 0, line: null, seen: false, timer: 0, sig: "", told: false, heard: new Set(), game: null, last: "", frames: 0 };
  W.io = new IntersectionObserver((es) => es.forEach((e) => {
    if (e.target === W.line) { W.seen = e.isIntersecting; if (W.seen && !W.timer) tick(); }
    else if (W.game && e.target === W.game.el) { W.game.seen = e.isIntersecting; if (!e.isIntersecting) W.game.run.pause(); }
  }));

  // ------------------------------------------------------------------ what is waited on
  /** The heartbeat's AI calls (in flight, and the last one), or null: not connected. */
  function beatNow() {
    const hb = wb.server;
    if (!isObj(hb) || !wb.connected) return null;
    return { act: (Array.isArray(hb.act) ? hb.act : []).filter((a) => isObj(a) && a.actor === "ai"),
      last: isObj(hb.last) && hb.last.actor === "ai" ? hb.last : null };
  }
  /** The AI seen at work after the request was sent: a call begun since. */
  const workedSince = (b, at) => !!b && (b.act.some((a) => num(a.since) && a.since >= at - 1)
    || (!!b.last && num(b.last.end) && b.last.end >= at && (!num(b.last.since) || b.last.since >= at - 1)));
  /** An answer of the AI's in the tab's chat after a time. */
  const aiAfter = (tab, at) => (tab.messages || []).some((m) => (m.from === "llm" || !m.from) && num(m.t) && m.t > at);

  /** The request waited on in the tab shown: the newest sent from here not yet in state
   *  (rec.outbox), else the session's newest still open with no reply. {key, id, at, out}. */
  function pendingOf(tab, rec, sess, b) {
    const o = rec.outbox[rec.outbox.length - 1];
    if (o) return { key: o.k, id: null, at: o.at / 1000, out: true };
    let n = null;
    (sess.notes || []).forEach((x) => { if (isObj(x) && !x.event && x.status !== "done" && !x.reply && num(x.t) && (!n || x.t >= n.t)) n = x; });
    if (!n || aiAfter(tab, n.t) || (now() - n.t > CFG.maxAge && !(b && b.act.length))) return null;
    return { key: n.id, id: n.id, at: n.t, out: false, delivered: num(n.delivered) ? n.delivered : 0,
      known: num(n.read) || num(n.handed), pushed: num(n.pushed) ? n.pushed : 0,
      failed: num(n.undelivered) && !num(n.delivered) && !(num(n.pushed) && n.pushed > n.undelivered) };
  }
  /** When the AI last answered in the tab's chat (a reply, an AI message), 0 when never. */
  function newestAI(tab, sess) {
    let a = 0;
    familyOf(tab).forEach((x) => (x.messages || []).forEach((m) => { if (isObj(m) && (m.from === "llm" || !m.from) && num(m.t) && m.t > a) a = m.t; }));
    (sess.notes || []).forEach((n) => { const r = isObj(n) && n.reply ? (num(n.replied) ? n.replied : n.t) : 0; if (num(r) && r > a) a = r; });
    return a;
  }
  /** wait (sent), say (the AI does not hear it by itself), unheard (said delivered, the AI not
   *  seen on it CFG.grace s on), off (not connected), or "". */
  function stateOf(p, b) {
    if (!wb.connected) return p.out ? "" : "off";
    const s = wb.state || {};
    if (p.known || W.heard.has(p.key)) return "wait";
    if (workedSince(b, p.at)) { W.heard.add(p.key); return "wait"; }
    // said delivered (unchecked): waited on a while, then the user is told
    if (s.listening === true || p.delivered) return p.out || now() - Math.max(p.at, p.delivered) < CFG.grace ? "wait" : "unheard";
    // pushed to a client that may drop it, or about to be: waited on a moment, then the user is told
    if (s.channel === true && !p.failed && (p.out || now() - Math.max(p.at, p.pushed) < CFG.pickup)) return "wait";
    return "say";
  }
  /** The AI was seen at work on this request soon after it was sent (the channel took it). */
  WBA.waitHeard = (id) => W.heard.has(id);
  /** A request said delivered that nothing shows the AI took (read, handed, seen at work on it)
   *  CFG.grace s after it was sent or delivered: the user is told to prompt the AI. */
  WBA.waitUnheard = (n) => !!n && n.status !== "done" && !n.reply && !num(n.read) && !num(n.handed) && !W.heard.has(n.id)
    && now() - Math.max(num(n.t) ? n.t : 0, num(n.delivered) ? n.delivered : 0) >= CFG.grace;

  // ------------------------------------------------------------------ the line
  function lineEl() {
    if (W.line) return W.line;
    const el = (W.line = document.createElement("div"));
    el.className = "chat notice cw-line";
    el.innerHTML = `<i class="cw-spin" aria-hidden="true"><b></b><b></b><b></b></i><span class="cw-w"></span>`
      + `<span class="cw-el"></span><button class="na cw-play hidden"></button>`;
    el.querySelector(".cw-play").addEventListener("click", () => openGame());
    W.io.observe(el);
    return el;
  }
  /** Right under the request (after its answer's and its effect's lines, if it has them); the
   *  AI thinking with no request waiting: at the chat's end. */
  function place(box, p) {
    let at = p.end ? null : box.querySelector(p.out ? `:scope > [data-id="${CSS.escape(p.key)}"]` : `:scope > [data-note="${CSS.escape(p.key)}"]`);
    const el = lineEl();
    if (p.end) { if (box.lastElementChild !== el) box.appendChild(el); return true; }
    if (!at) return false;
    while (at.nextElementSibling && [`r${p.key}`, `x${p.key}`].includes(at.nextElementSibling.dataset.id)) at = at.nextElementSibling;
    if (at.nextElementSibling !== el) at.after(el);
    return true;
  }
  /** st: think (WBA.think, th), wait, say, unheard, off. */
  function paint(p, st, th) {
    const el = W.line, tell = st === "say" || st === "unheard";
    const text = st === "think" ? t("ai_think") : st === "wait" ? t("cw_sent") : tell ? t(`cw_${st}`, WBA.aiClient(), t("say_look")) : t("cw_off");
    const count = st === "think" ? th.el : st === "wait" ? since(p.at) : "";
    const play = !!count && !W.game && now() - (st === "think" ? th.since : p.at) >= CFG.gameAfter;
    const sig = JSON.stringify([st, text, count, play, I18N.lang]);
    if (sig === W.sig && el.isConnected) return;
    W.sig = sig;
    el.className = `chat notice cw-line s-${st === "unheard" ? "say s-unheard" : st}`;
    el.title = tell ? `${t(`tip_cw_${st}`, WBA.aiClient())}\n${WBA.channelTip()}`
      : st === "think" ? t("tip_ai_think", WBA.aiClient()) : st === "wait" ? t("tip_cw_sent") : text;
    el.querySelector(".cw-w").textContent = text;
    el.querySelector(".cw-el").textContent = count && `· ${count}`;
    const pb = el.querySelector(".cw-play");
    pb.classList.toggle("hidden", !play);
    if (pb.textContent !== t("cw_play")) { pb.textContent = t("cw_play"); pb.title = t("tip_cw_play"); }
  }
  function dropLine(box) {
    clearTimeout(W.timer);
    W.timer = 0;
    W.key = "";
    W.sig = "";
    if (W.line && W.line.isConnected) {
      W.line.remove();
      W.seen = false;
      if (box) listFades(box);
    }
  }
  /** The line for the tab shown: placed (fromRender: the list was just redrawn, and scrolls
   *  after), painted, the timer set; gone when nothing waits and the AI does not think. */
  function update(pane, tab, sess, fromRender) {
    const rec = tab && wb.recs.get(tab.id), box = pane && pane.q(".chat-list");
    const b = beatNow(), ss = rec ? sess || sessOf(tab) : null, th = rec && wb.connected ? WBA.think || null : null;
    let p = rec ? pendingOf(tab, rec, ss, b) : null, st = p ? stateOf(p, b) : "";
    const tell = st === "say" || st === "unheard";
    // the line under the chat box follows the request's own state (app-chat.js's heard): redrawn when it turns
    if (W.told !== tell && wb.pane) { W.told = tell; WBA.later.renderComposer(wb.pane); }
    if (th) { st = "think"; p = p || { key: `w${th.since}`, at: th.since, end: true }; }
    if (!st) { dropLine(fromRender ? null : box); noteGame(); return; }
    W.key = p.key;
    W.at = p.at;
    const stick = !fromRender && !(W.line && W.line.isConnected) && atEnd(box);
    if (!place(box, p)) { dropLine(null); noteGame(); return; }
    paint(p, st, th);
    if (stick) box.scrollTop = box.scrollHeight;
    noteGame();
    arm(st);
  }
  /** The next second of a sent request's count, while the line can be seen and the window shows
   *  (thinking: the header's count drives both, waitThink). */
  function arm(st) {
    clearTimeout(W.timer);
    W.timer = 0;
    if (st !== "wait" || !W.line || !W.line.isConnected || !W.seen || document.visibilityState !== "visible") return;
    W.timer = setTimeout(tick, 1000 - ((Date.now() - W.at * 1000) % 1000 + 1000) % 1000 + 30);
  }
  function tick() {
    W.timer = 0;
    const pane = wb.pane, tab = pane && tabOf(pane.tabId);
    if (tab && document.visibilityState === "visible") update(pane, tab, null, false);
  }
  /** Something the line follows moved (the heartbeat, WBA.think, a state the chat did not redraw
   *  for): the line as it should be, in the chat shown. */
  function poke() {
    const pane = wb.pane, tab = pane && tabOf(pane.tabId);
    if (tab && pane.chatTab === tab.id && document.visibilityState === "visible") update(pane, tab, null, false);
  }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") { if (W.seen) tick(); }
    else { clearTimeout(W.timer); W.timer = 0; if (W.game) W.game.run.pause(); }
  });
  window.addEventListener("blur", () => { if (W.game) W.game.run.pause(); });

  // ------------------------------------------------------------------ the game card
  const bestOf = (id) => { const v = Number(prefGet(`wb.wait.best.${id}`)); return v > 0 ? v : 0; };
  /** The card under the chat list, made once per pane (before the composer). */
  function cardOf(pane) {
    if (pane.cwCard) return pane.cwCard;
    const el = (pane.cwCard = document.createElement("div"));
    el.className = "cw-game";
    el.tabIndex = -1;
    el.innerHTML = `<div class="cw-hd"><span class="cw-tt"></span><span class="cw-sc"></span><span class="grow"></span>`
      + `<button class="cw-rp hidden" data-w="reply"></button><button class="icon flat cw-sw" data-w="next">${icon("refresh")}</button>`
      + `<button class="icon flat cw-x" data-w="close">${icon("close")}</button></div><div class="cw-bd"></div>`;
    // ↻ the next game; × and the reply's line close it (closing once the reply came goes to the reply)
    el.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-w]");
      if (b) { if (b.dataset.w === "next") openGame(nextId(W.game && W.game.kind, 1)); else closeGame(); }
    });
    pane.q(".composer").before(el);
    return el;
  }
  /** A game's id: ``step`` 1 the one after ``id`` in WBG.list, 0 one at random other than ``id``. */
  function nextId(id, step) {
    const ids = WBG.list.map((g) => g.id), i = ids.indexOf(id);
    if (step) return ids[(i + 1) % ids.length];
    const rest = ids.length > 1 ? ids.filter((x) => x !== id) : ids;
    return rest[Math.floor(Math.random() * rest.length)];
  }
  /** Open a game (an id of WBG.list; none: one at random, not the last one played) in the card,
   *  the focus on it. */
  function openGame(kind) {
    const pane = wb.pane, tab = pane && tabOf(pane.tabId);
    const id = WBG.list.some((g) => g.id === kind) ? kind : nextId(W.last, 0), def = WBG.list.find((g) => g.id === id);
    if (!tab || !def) return;
    closeGame(true);
    W.last = def.id;
    const box = pane.q(".chat-list"), stick = atEnd(box), el = cardOf(pane), rec = wb.recs.get(tab.id);
    const p = rec && pendingOf(tab, rec, sessOf(tab), beatNow());
    const g = (W.game = { kind: def.id, el, note: p && !p.out ? p.id : null, work: p ? 0 : now(), session: tab.session, seen: false });
    el.dataset.kind = def.id;
    el.classList.add("open");
    el.querySelector(".cw-x").title = t("cw_close");
    el.querySelector(".cw-sw").title = t("cw_switch");
    const head = () => {
      const sc = [t("cw_t_score", g.run.score()), g.run.best() && t("cw_best", g.run.best())].filter(Boolean).join(" · ");
      el.querySelector(".cw-tt").textContent = t(def.name);
      el.querySelector(".cw-sc").textContent = sc;
    };
    g.run = WBG.run(el.querySelector(".cw-bd"), def, { best: bestOf(def.id), head, frame: () => W.frames++,
      keep: (v) => prefSet(`wb.wait.best.${def.id}`, String(v)),
      live: () => g.seen && document.visibilityState === "visible" && W.game === g });
    g.out = (ev) => { if (!el.contains(ev.relatedTarget)) g.run.pause(); };
    el.addEventListener("focusout", g.out);
    head();
    W.io.observe(el);
    if (stick) box.scrollTop = box.scrollHeight;
    listFades(box);
    el.focus({ preventScroll: true });
    W.sig = "";
    poke();                                         // (the line drops its link)
  }
  /** Close the game; after the reply came, go to it (quiet: another game opens in its place). */
  function closeGame(quiet) {
    const g = W.game;
    if (!g) return;
    W.game = null;
    g.run.stop();
    g.el.removeEventListener("focusout", g.out);
    W.io.unobserve(g.el);
    const had = g.el.contains(document.activeElement);
    g.el.classList.remove("open");
    g.el.querySelector(".cw-bd").innerHTML = "";
    if (had) g.el.blur();
    const pane = wb.pane;
    if (!pane || quiet) return;
    listFades(pane.q(".chat-list"));
    if (g.note && answered(g)) gotoNote(pane, g.note);
    else if (g.work && answered(g)) { const box = pane.q(".chat-list"); box.scrollTop = box.scrollHeight; listFades(box); }
    W.sig = "";
    poke();
  }
  /** Whether the request the game waited on has its answer (a reply, done, an AI message); played
   *  with no request waiting: whether the AI said something since it opened. */
  function answered(g) {
    if (g.work) {
      const pane = wb.pane, tab = pane && tabOf(pane.tabId);
      return !!tab && tab.session === g.session && newestAI(tab, sessOf(tab)) > g.work;
    }
    let n = null;
    Object.values((wb.state && wb.state.sessions) || {}).forEach((s) => (s.notes || []).forEach((x) => { if (x && x.id === g.note) n = x; }));
    if (!n) return false;
    return !!n.reply || n.status === "done" || ((wb.state && wb.state.tabs) || []).some((x) => x.session === g.session && aiAfter(x, n.t || 0));
  }
  /** The card's header: the reply's line, where it came. */
  function noteGame() {
    const g = W.game;
    if (!g) return;
    const rp = g.el.querySelector(".cw-rp"), on = answered(g);
    rp.classList.toggle("hidden", !on);
    if (on && rp.textContent !== t("cw_reply")) rp.textContent = t("cw_reply");
  }
  // The game's keys, ahead of the page's (app-main.js listens on the document, capturing):
  // only while the focus is in the card. Escape closes it.
  const gameKey = (down) => (ev) => {
    const g = W.game;
    if (!g || !g.el.contains(document.activeElement) || ev.ctrlKey || ev.metaKey || ev.altKey) return;
    if (ev.key === "Escape") { if (down) closeGame(); }
    else if (!g.run.key(ev, down)) return;
    ev.preventDefault();
    ev.stopPropagation();
  };
  window.addEventListener("keydown", gameKey(true), true);
  window.addEventListener("keyup", gameKey(false), true);

  /** For the regression suite: what the line and the game show, and the frames drawn. */
  function waitDebug() {
    const l = W.line && W.line.isConnected ? W.line : null, g = W.game;
    return { line: l ? { cls: l.className, text: l.querySelector(".cw-w").textContent, el: l.querySelector(".cw-el").textContent,
      last: !l.nextElementSibling, title: l.title, play: !l.querySelector(".cw-play").classList.contains("hidden"),
      after: Object.assign({}, (l.previousElementSibling || {}).dataset) } : null,
      timer: !!W.timer, seen: W.seen, frames: W.frames, games: WBG.list.map((x) => x.id),
      game: g ? { kind: g.kind, state: g.run.state(), raf: g.run.raf(), score: g.run.score(),
        notice: !g.el.querySelector(".cw-rp").classList.contains("hidden") } : null };
  }

  Object.assign(WBA, { waitDebug, waitGame: openGame, waitThink: poke,
    waitRender: (pane, tab, sess) => update(pane, tab, sess, true),
    waitUpdate: (pane, tab, sess) => { if (pane.chatTab === tab.id) update(pane, tab, sess, false); } });
})();
