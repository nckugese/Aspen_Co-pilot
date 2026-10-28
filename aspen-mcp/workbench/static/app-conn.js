/* The server, as the header shows it: the connection capsule (renderConn; shown only when not
 * connected as normal), #ai-bar (what the AI is calling: renderAiBar; the review group beside it is
 * app-brake.js's, drawn from here too), #ai-think (the AI's turn running: renderThink, the one state
 * the chat's waiting line shares) and what the model capsule says while Aspen calculates (aspenBusy,
 * for app-model.js). window.py calls wb.setConnected with whether the heartbeat is fresh, and
 * wb.setServer with the heartbeat's content whenever more than its times changed
 * (tools/activity.py): the calls in flight (act: actor ai | program | user, tool, session, phase
 * call | aspen | compute | wait, since, target), the last one to end (last), who holds each
 * session (holders), and when the server's loop last came round (loop, against t).
 *
 * Used only while it is fresh. The seconds count by one timer that runs only while something
 * counts and the window shows.
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { $, busy, esc, feature, guard, icon, isObj, now, num, renderPane, renderRunbar, shownTab, t, tabOf, wb } = WBA;
  const { brakeNow, renderBrake, renderModelBar } = WBA.later;

  const LAG_S = 2.5;          // the loop this far behind the heartbeat: the server is held up (window.py LAG_S)
  const JUST_S = 4;           // "AI just did" shows this long after the AI's call ended

  /** The heartbeat as the page uses it, or null: not connected, or none. {act, last, holders,
   *  lag (the loop held up), loop}. */
  function beat() {
    const hb = wb.server;
    if (!hb || !wb.connected) return null;
    return { act: Array.isArray(hb.act) ? hb.act.filter(isObj) : [], last: isObj(hb.last) ? hb.last : null,
             holders: isObj(hb.holders) ? hb.holders : {}, lag: num(hb.t) && num(hb.loop) && hb.t - hb.loop > LAG_S,
             loop: num(hb.loop) ? hb.loop : null };
  }
  /** How long since a server time, counting: "42 s", "3 min 5 s". */
  function since(at) {
    const s = Math.max(0, Math.floor(now() - (num(at) ? at : now())));
    return s < 60 ? t("dur_s", s) : t("dur_min_s", Math.floor(s / 60), s % 60);
  }

  /** The call keeping Aspen busy on a session, for the model capsule: the oldest in phase aspen
   *  there, the AI's or the window's own (Run simulation, Save model); a program's only while
   *  it holds the server's loop up (its steps come and go, and its own run bar tells). */
  function aspenBusy(session) {
    const b = beat();
    return (b && b.act.find((a) => a.phase === "aspen" && a.session === session && (a.actor !== "program" || b.lag))) || null;
  }
  /** Who holds a session (a program run, the AI's optimize), or null. */
  function holderOf(session) {
    const b = beat(), h = b && b.holders[session];
    return h && typeof h === "object" ? h : null;
  }

  /** Who made a call or a change, in a word. */
  const whoWord = (actor) => (["ai", "user", "program", "optimizer"].includes(actor) ? t(`who_${actor}`) : String(actor || ""));
  /** What a call works on, in plain words (tools/intercept.target_of): a path by the catalog's
   *  label, a batch of values as their count, else the name it gives (a tab by its title). */
  function targetWords(tg) {
    if (!tg || typeof tg !== "object") return "";
    const n = Number(tg.n) > 1 ? Number(tg.n) : 0;
    if (tg.path) return n ? t("ai_n_values", n) : WBL.say(tg.path);
    if (tg.algorithm) return String(tg.algorithm);
    if (tg.tab) { const x = tabOf(String(tg.tab)); return x ? x.title || x.session : String(tg.tab); }
    const name = ["name", "block", "stream", "component", "rxnset", "chemistry", "file"].map((k) => tg[k]).find((v) => v != null && v !== "");
    return name == null ? "" : n ? t("ai_n_more", String(name), n - 1, n) : String(name);
  }
  /** A call in words: the tool (the window's own by its button's name), then its target. */
  function callWords(a) {
    const own = { run_sim: "run_sim", save_model: "m_save_model" }[a.tool];
    // a restore point being saved, a restore: in words, whoever asked; their target is no name
    const cp = { checkpoint: "act_checkpoint", restore: "act_restore" }[a.tool];
    if (cp) return [t(cp), a.target && a.target.name].filter(Boolean).join(" · ");
    return [a.actor === "user" && own ? t(own) : a.tool, targetWords(a.target)].filter(Boolean).join(" · ");
  }
  /** The AI's call waiting for a session's holder: for whom, in words. */
  const waitKey = (actor) => (actor === "program" ? "ai_wait_prog" : actor === "optimizer" ? "ai_wait_opt" : "ai_wait");

  // ------------------------------------------------------------------ #ai-bar
  /** The AI's call in flight (the newest, "+N" for more at once), or waiting for a session's
   *  holder or for an approval (a card), or the one that ended a moment ago (fainter);
   *  hidden otherwise. Only the AI's: the window's own Run and a program's steps show in the
   *  model capsule, and a call the pause holds, or one waiting on a request the header's badge
   *  counts, in the review group (app-brake.js: it adds ⏸ here while the AI works). */
  function renderAiBar(b) {
    const brk = feature("brake"), bk = brk ? brakeNow() : null, badge = !!bk && bk.cards > 0;
    const el = $("ai-bar"), ai = b ? b.act.filter((a) => a.actor === "ai" && !(brk && a.phase === "wait" && (a.why === "pause" || (badge && a.why === "card")))) : [];
    const a = ai[ai.length - 1];
    let cls = "", text = "", tip = [];
    if (a) {
      cls = a.phase === "wait" ? "wait" : "now";
      text = t(cls === "wait" ? (a.why === "card" ? "ai_wait_card" : waitKey(a.holder)) : "ai_now", callWords(a));
      if (ai.length > 1) text += ` +${ai.length - 1}`;
      const h = cls === "wait" && b.holders[a.session];
      // (the field where it sits in Aspen: the whole breadcrumb)
      const where = a.target && a.target.path && WBL.full(a.target.path, a.session);
      tip = [text, where, a.session && t("model_is", a.session),
        h && (h.actor === "program" ? t("ai_tip_wait_prog", h.title || h.tab || "") : t("ai_tip_wait", whoWord(h.actor))),
        num(a.since) && t("ai_tip_since", since(a.since))];
    } else if (b && b.last && b.last.actor === "ai" && num(b.last.end) && now() - b.last.end < JUST_S) {
      cls = "just";
      text = t("ai_just", callWords(b.last));
      // (refused where the brakes are: by the pause or Observe as they stand now, else a holder)
      const bk = b.last.status === "refused" && brk ? brakeNow() : null;
      const st = bk && bk.paused ? "refused_pause" : bk && bk.mode === "observe" ? "refused_observe" : b.last.status;
      tip = [text, b.last.session && t("model_is", b.last.session),
        ["error", "refused"].includes(b.last.status) && t(`ai_st_${st}`)];
    }
    const title = tip.filter(Boolean).concat(text ? [t("tip_ai_bar")] : []).join("\n");
    const sig = JSON.stringify([cls, text, title]);
    if (el.dataset.sig === sig) return;
    el.dataset.sig = sig;
    el.className = text ? `ai-bar ${cls}` : "ai-bar hidden";
    el.title = title;
    el.innerHTML = text ? `${icon("sparkle")}<span class="ab-t"></span>` : "";
    if (text) el.querySelector(".ab-t").textContent = text;
  }

  // ------------------------------------------------------------------ #ai-think
  // "AI is thinking…" (ai_think) and its seconds, here and on the chat's waiting line (app-wait.js), both from
  // WBA.think and drawn together (renderThink calls waitThink). The AI's turn, not its replies: from
  // the turn's start until it ends, whatever it said meanwhile. A start is the latest of the hooks'
  // prompt (state.ai_turn.start: UserPromptSubmit, or a Stop that hands it requests;
  // plugin/scripts/workbench-asks.ps1), a request delivered to it (note.delivered: the channel, a
  // hook; not once app-wait.js takes it as unheard), an answer saying more is coming (note.working) or an AI call (the heartbeat: in flight, or
  // the last one's start); the end is the hooks' Stop (ai_turn.stop) after it. No Stop comes when the
  // turn is interrupted or the client dies, so with no sign of life for THINK.quiet s it is taken as
  // over; without the hooks (no ai_turn: another client) only those signs count, for THINK.bare s
  // after the last. Not while every AI call waits (review, a holder: #ai-bar says).
  const THINK = (WBA.thinkCfg = { quiet: 300, bare: 30 });
  /** {since: when the turn started, until: when it is taken as over} while it runs, else null. */
  function thinkOf(b) {
    const s = wb.state;
    if (!wb.connected || !isObj(s)) return null;
    const tn = isObj(s.ai_turn) ? s.ai_turn : null, stop = tn && num(tn.stop) ? tn.stop : 0;
    const ai = b ? b.act.filter((a) => a.actor === "ai") : [], last = b && b.last && b.last.actor === "ai" ? b.last : null;
    let start = tn && num(tn.start) ? tn.start : 0;
    const later = (x) => { if (num(x) && x > start) start = x; };
    // without the hooks a request's times count only while recent: one delivered days ago and never
    // closed is no sign of this turn (it made the clock count from then)
    const fresh = (x) => (tn || (num(x) && x > now() - THINK.quiet) ? x : 0);
    Object.values(isObj(s.sessions) ? s.sessions : {}).forEach((ss) => ((isObj(ss) && ss.notes) || []).forEach((n) => {
      if (isObj(n)) { if (!WBA.waitUnheard(n)) later(fresh(n.delivered)); later(fresh(n.working)); }   // (not one the AI left untouched)
    }));
    ai.forEach((a) => later(a.since));
    if (last) later(last.since);
    if (!(start > stop) || (ai.length && ai.every((a) => a.phase === "wait"))) return null;
    const t0 = now(), life = ai.length ? t0 : Math.max(start, last && num(last.end) ? last.end : 0);
    const until = life + (tn ? THINK.quiet : THINK.bare);
    if (t0 >= until) return null;
    // (since: the turn's first start, the hooks' begin -- a Stop that handed it requests goes on with it)
    const first = tn ? [tn.begin, tn.start].find((x) => num(x) && x > stop) : null;
    return { since: first || start, until };
  }
  /** #ai-think as the turn stands, WBA.think set (el: its seconds in words) and the chat's line
   *  drawn from it at once; returns it (the timer: count). */
  function renderThink(b) {
    const el = $("ai-think"), th = (WBA.think = thinkOf(b));
    if (th) th.el = since(th.since);
    const sig = JSON.stringify([!!th, I18N.lang]);
    if (el.dataset.sig !== sig) {
      el.dataset.sig = sig;
      el.className = th ? "ai-think" : "ai-think hidden";
      el.innerHTML = th ? `<span class="atk-t">${esc(t("ai_think"))}</span><span class="atk-s"></span>` : "";
      el.title = th ? t("tip_ai_think", WBA.aiClient()) : "";
    }
    if (th) el.querySelector(".atk-s").textContent = th.el;
    if (WBA.waitThink) WBA.waitThink();
    return th;
  }

  // ------------------------------------------------------------------ the connection
  /** The connection, and only the connection (the capsule tells about runs), shown only when it
   *  is not the normal state (connected: nothing): not connected; lost while a run was going,
   *  when the server stopped answering in the middle of one. Its heartbeat fresh but its loop
   *  held up (a long Aspen call): busy, counting, not gone; where the model capsule already says
   *  Aspen calculates on the model shown, just connected. */
  function renderConn() {
    const el = $("conn"), tabs = (wb.state && wb.state.tabs) || [], b = beat(), tab = shownTab();
    let st = wb.connected ? "on" : tabs.some(busy) ? "lost" : "off", text = t(`conn_${st}`), tip = t(`tip_conn_${st}`);
    if (b && b.lag && !(tab && aspenBusy(tab.session))) {
      const a = b.act.find((x) => x.phase === "aspen");
      st = "busy";
      text = a ? t("conn_busy_aspen", since(a.since)) : t("conn_busy", since(b.loop));
      tip = t("tip_conn_busy");
    }
    el.className = `conn ${st}${st === "on" ? " hidden" : ""}`;
    const ct = el.querySelector(".ct");
    if (ct.textContent !== text) ct.textContent = text;
    if (el.title !== tip) el.title = tip;
    renderAiBar(b);
    renderBrake();
    count(b, renderThink(b));
  }

  /** One timer while something counts (the AI's turn, Aspen's seconds, a held-up loop's) or "AI
   *  just did" is to go, and the window shows (hidden: only the turn's end); none otherwise. */
  let timer = 0;
  const nextSec = (from) => 1000 - (((Date.now() - from * 1000) % 1000) + 1000) % 1000 + 15;
  function count(b, th) {
    clearTimeout(timer);
    timer = 0;
    const shown = document.visibilityState === "visible";
    let wait = th ? (shown ? nextSec(th.since) : (th.until - now()) * 1000 + 15) : Infinity, model = false;
    if (b && shown) {
      const from = b.act.filter((a) => a.phase === "aspen" && num(a.since)).map((a) => a.since).concat(b.lag ? [b.loop] : [])[0];
      if (num(from)) { wait = Math.min(wait, nextSec(from)); model = true; }
      const l = b.last;
      if (l && l.actor === "ai" && num(l.end) && !b.act.some((a) => a.actor === "ai")) {
        const left = (l.end + JUST_S - now()) * 1000;
        if (left > 0) wait = Math.min(wait, left + 15);
      }
    }
    if (wait < Infinity) timer = setTimeout(() => { renderConn(); if (model) renderModelBar(); }, Math.max(50, wait));
  }
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") renderConn(); });

  // (each part on its own, as an update's: guard, app-state.js)
  wb.setConnected = function (alive) {
    wb.connected = alive;
    const tab = shownTab();
    if (tab) { wb.pane.sigs.irows = null; guard("renderPane", () => renderPane(wb.pane)); }
    guard("renderRunbar", () => renderRunbar());
    guard("renderConn", () => renderConn());
  };
  /** The heartbeat's content (window.py). */
  wb.setServer = function (hb) {
    wb.server = hb && typeof hb === "object" && !Array.isArray(hb) ? hb : null;
    guard("renderConn", () => renderConn());
    guard("renderModelBar", () => renderModelBar());
  };

  Object.assign(WBA, { aspenBusy, callWords, holderOf, renderConn, since, whoWord });
})();
