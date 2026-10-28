/* AI review, the feature called "brake" inside: in the header (the review mode, pausing the
 * AI) and the approval requests ("cards" inside). #ai-brake
 * sits just before #ai-bar (what the AI is doing: app-conn.js, which leaves out a call the pause
 * holds, and one waiting on a request while the badge counts it: this group says those).
 *
 *   [🛡▾]                                            the default mode (Approve risky): the shield alone
 *   [👁 Review: Read-only ▾] / [⚡ Review: Auto ▾]    a mode that is not the default names itself
 *   [🛡▾] [✦ AI: set_value · … ⏸]                    the AI working: ⏸ at #ai-bar's end pauses it
 *   [🛡▾] [▶ Resume] AI paused · 1 held · 28 s       paused (a warm group, still)
 *   [🛡▾] [1 pending]                                a request waits: the one place that says so
 *   [⛨ Review off ▾]                                 not in effect here
 *
 * The shield opens the review menu, in two sections: "Review mode" -- the three modes, each with its
 * line (posts brake_mode {mode}), then "Pause AI" (brake_pause), or while paused "Resume AI" (its
 * popover) -- and "Tracking and learning", the switches other parts add (brakeMenuAdd(fn, section):
 * "Follow AI edits", "Learning mode";
 * the ... menu always has the same ones: brakeSwitches); last, the changes refused in read-only.
 * The shield's tooltip names that second section's switches too. Its
 * title's tooltip says what holds with the window closed; its ⚙ opens the auto-pause rules. While
 * paused the group counts down to when the held call gives up (paused.deadline, one timer, a
 * second at a time, only while a call is held), and "Resume" opens a small popover: what waits, the
 * countdown, a note for the AI (optional), then brake_resume {note?}. What was asked shows at once
 * and holds until the server's state says so (WANT_MS at most).
 *
 * The requests (brake.cards: tools/brake.py's view, what each will do from tools/brake_effects.py)
 * live in the dock, over the Changes tab's timeline (.bk-dock, a part of its own: the timeline
 * scrolls under it; where the server keeps no timeline, over the AI chat), never in a dialog:
 * nothing waits on them but the AI. A request's head says what the AI asks and, on its right,
 * "Pending · 38 s · 14:02" (the seconds the AI still waits, card.until); then the request it came
 * in, the AI's reason, "Effects" (the effects' own words), which restore point is created first and
 * about how long, "auto-approve … for the rest of this request" (allow_group), and "Approve" /
 * "Decline…" (the note typed in the card itself), "Create restore point (about 2 min), then
 * approve" (bkc_cp_slow_btn) where the restore point would be
 * skipped as slow (slow_cp). Past the wait, or once the window closed or the client gave up, it
 * stays, one line beside its buttons saying so: an approval then is "approved after timeout".
 * Posted: brake_card {card, decision, comment?, allow_group?, slow_cp?, req}. A decided request
 * leaves the dock (the timeline has its decision line); where there is no timeline, or it failed,
 * it folds to one line (brake_dismiss removes it; the server drops it after 30 minutes). The
 * header's badge is the one announcement of a waiting request (a click shows it); a toast only
 * while the dock is folded; its block or stream is framed on the flowsheet (FS.mark "bkpend").
 * Nothing switches the dock's tab by itself.
 *
 * Paused by the stuck rule (paused.by "stuck"), the "Resume" popover says why in the server's
 * words (paused.detail.why; else the rule's own), offers "Show these 3 records in Changes" (the
 * evidence, detail.ids: the card that holds the last one opened; without them, the Changes tab),
 * "Resume AI" and "Resume; disable this rule for this request" (brake_resume {mute: rule, note?}),
 * and "Auto-pause rules…".
 * Those rules (brake.stuck: runs 2-10, field 3-20, revert 1-10, each on or off) are edited behind a
 * small ⚙ in the review menu (and in the model panel's part): brake_stuck {runs, field, revert, on},
 * each number held in its range. Only where the server has them (catalog.features stuck).
 *
 * The model panel (app-model.js) has a small part on the brakes (brakeItems): the mode (a click
 * opens the chip's menu), paused or not ("Resume…" / "Pause AI"), the cards to decide, the changes refused
 * in Observe, or why the brakes are off.
 *
 * The brakes act only where the server that writes this state serves the window (brake.live)
 * and answers (wb.connected); otherwise the chip says they are off, and why, and no pause is
 * offered. Only where the server has them (catalog.features brake; state.json brake:
 * tools/brake.py's view()): without them the header has none of it.
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { $, base, callWords, changesCtx, closeMenus, esc, feature, hhmm, icon, isObj, now, num, openMenu, prefs, setDock, showPanel,
    shownTab, t, tn, toast, toggleMenu, wb } = WBA;
  const { gotoChange } = WBA.later;

  const MODES = ["observe", "risk", "auto"];
  const DEFAULT_MODE = "risk";  // (tools/brake.py: the chip is the shield alone in it)
  const MODE_ICON = { observe: "eye", risk: "shield", auto: "bolt" };
  const WANT_MS = 5000;         // what was asked shows this long at most while the server has not said
  const NOTE_MAX = 300;         // (tools/brake.py TEXT_MAX)
  const PENDING = ["waiting", "timeout", "cancelled"];   // (tools/brake.py PENDING: the user can still decide)
  const DONE_SHOWN = 3;         // decided cards kept as a line each where no timeline has them (or failed)
  const CLASSES = ["remove", "reinit", "close", "file", "program"];
  const RULES = ["runs", "field", "revert"];
  const RANGE = { runs: [2, 10], field: [3, 20], revert: [1, 10] };   // (tools/stuck.py RANGES)
  const DEFAULTS = { runs: 3, field: 4, revert: 2 };                  // (tools/stuck.py DEFAULTS)
  const est = (s) => WBC.est(s);

  const want = { mode: null, mAt: 0, paused: null, pAt: 0, stuck: null, sAt: 0 };   // asked here, not in the state yet
  // the review menu's other items (brakeMenuAdd), per section: () => menu items. "review": after
  // "Pause AI", only in the review menu; "view": "Tracking and learning", in the review menu and the ... menu alike
  const SECTIONS = ["review", "view"];
  const extras = { review: [], view: [] };
  let timer = 0;

  /** The server's brakes (state.json brake), or null: none. */
  function view() {
    const b = wb.state && wb.state.brake;
    return feature("brake") && b && typeof b === "object" && MODES.includes(b.mode) ? b : null;
  }
  /** What the group shows: the view, with what was just asked laid over it. {mode, paused, p (the
   *  pause), auto (by the stuck rule), held, n (held, counted), left (s until the held call gives
   *  up), live, hold (s a call is held), refused (in Observe), cards (still to decide)} */
  function shown(b) {
    const ms = Date.now();
    if (want.mode && (b.mode === want.mode || ms - want.mAt > WANT_MS)) want.mode = null;
    if (want.paused !== null && (!!b.paused === want.paused || ms - want.pAt > WANT_MS)) want.paused = null;
    const p = b.paused && typeof b.paused === "object" ? b.paused : null;
    const paused = want.paused !== null ? want.paused : !!p;
    const held = paused && p && Array.isArray(p.held) ? p.held.filter((h) => h && typeof h === "object") : [];
    const n = held.length + (paused && p && Number(p.more) > 0 ? Number(p.more) : 0);
    const r = b.refused && typeof b.refused === "object" ? Number(b.refused.n) || 0 : 0;
    return { mode: want.mode || b.mode, paused, p: paused ? p : null, auto: !!(paused && p && p.by === "stuck"), held, n,
             left: n && p && num(p.deadline) ? Math.max(0, Math.ceil(p.deadline - now())) : null,
             live: b.live !== false, hold: num(b.hold_s) ? Math.round(b.hold_s) : 40, refused: r, cards: toDecide(b) };
  }

  // ------------------------------------------------------------------ words
  const modeFull = (m) => t(`aim_${m}_full`);
  const detailOf = (p) => (p && isObj(p.detail) ? p.detail : {});
  const ruleOf = (p) => (p && RULES.includes(p.rule) ? p.rule : null);
  /** Why the stuck rule paused the AI: the server's plain words (detail.why), else the rule's
   *  (its count the rule's threshold where the detail was cut short). */
  function whyWords(p) {
    const d = detailOf(p), why = d.why;
    if (isObj(why) && (why[I18N.lang] || why.en)) { const w = String(why[I18N.lang] || why.en); return w.charAt(0).toUpperCase() + w.slice(1); }
    const rule = ruleOf(p), cfg = stuckCfg(view());
    return rule ? t(`rule_${rule}`, num(d.n) ? d.n : cfg[rule], typeof d.field === "string" && d.field ? d.field : t("rule_field0"))
      : t("autopaused0");
  }
  /** The held calls in words: "set_value · ESTCOL › Reflux ratio", the second, then "…". */
  function heldWords(s) {
    const w = s.held.slice(0, 2).map((h) => callWords(h)).filter(Boolean);
    return w.join(t("ch_s_sep")) + (s.n > w.length ? "…" : "");
  }
  /** The group's words while paused, "AI paused · 1 held", and apart its seconds, "28 s" (they
   *  never give way: the words do; style.css puts the · before them). */
  function stText(s) {
    const head = t(s.auto ? "paused_auto_st" : "paused_st");
    return [s.n ? tn("paused_n", s.n, head) : head, s.n && s.left ? t("dur_s", s.left) : ""];
  }
  const leftWords = (s) => (s.left ? t("resume_left", s.left) : t("resume_left0"));
  function stTip(s) {
    return [s.auto && whyWords(s.p), s.n ? tn("resume_held", s.n, heldWords(s)) : t("resume_none", s.hold),
      s.n && leftWords(s), t("resume_foot")].filter(Boolean).join("\n");
  }

  // ------------------------------------------------------------------ the group
  function renderBrake() {
    const el = $("ai-brake");
    if (!el) return;
    clearTimeout(timer);
    timer = 0;
    const b = view();
    if (!b) {                                     // no brakes: nothing
      if (el.dataset.sig !== "") { el.dataset.sig = ""; el.className = "ai-brake hidden"; el.innerHTML = ""; el.style.minWidth = ""; }
      renderCards();
      pauseSync(null);
      return;
    }
    if (!el.dataset.wired) { el.dataset.wired = "1"; el.addEventListener("click", onClick); }
    const s = shown(b), on = !!wb.connected, off = !s.live || !on, nc = s.cards.length;
    const bare = !off && s.mode === DEFAULT_MODE;   // the default mode: the shield alone (its tooltip names it)
    const sw = switchNames();                     // (the "Tracking and learning" switches: its tooltip names them)
    const sig = JSON.stringify([I18N.lang, s.mode, s.paused, s.auto, off, on, s.hold, s.mode === "observe" ? s.refused : 0, nc,
      nc ? s.cards.slice(0, 2).map((c) => [c.id, c.status]) : 0, sw]);
    if (el.dataset.sig !== sig) {
      el.dataset.sig = sig;
      el.className = `ai-brake${s.paused ? " paused" : ""}${off ? " off" : ""}`;
      const chip = off
        ? `<button class="abk-mode off" data-b="mode" aria-haspopup="menu">${icon("shield-off")}<span class="bt"></span>${icon("chevron-down")}</button>`
        : `<button class="abk-mode m-${s.mode}${bare ? " bare" : ""}" data-b="mode" aria-haspopup="menu">${icon(MODE_ICON[s.mode])}`
          + `${bare ? "" : `<span class="bt"></span>`}${icon("chevron-down")}</button>`;
      const go = s.paused
        ? `<button class="abk-go primary" data-b="resume" aria-haspopup="menu"${on ? "" : " disabled"}>${icon("play")}<span class="bt"></span></button>`
          + `<span class="abk-st"><span class="abk-w"></span><span class="abk-s"></span></span>`
        : "";
      // the cards still to decide: how many, a click shows them
      const cards = nc ? `<button class="abk-cards" data-b="cards"><b class="abk-n"></b><span class="bt"></span></button>` : "";
      el.innerHTML = chip + go + cards;
      const c = el.querySelector(".abk-mode"), ct = c.querySelector(".bt");
      if (ct) ct.textContent = off ? t("aim_off") : t("aim_chip", t(`aim_${s.mode}`));
      const swTip = sw.length ? t("aim_tip_view", sw.join(t("ch_s_sep"))) : "";
      c.title = off ? [t(on ? "aim_not_live" : "aim_off_conn"), swTip].filter(Boolean).join("\n")
        : [t("aim_tip", modeFull(s.mode), t(`aim_${s.mode}_d`)), s.mode === "observe" && s.refused ? tn("aim_refused_n", s.refused) : "", swTip]
          .filter(Boolean).join("\n");
      c.setAttribute("aria-label", off ? t("aim_off") : t("aim_toast", modeFull(s.mode)));
      const g = el.querySelector(".abk-go");
      if (g) { g.querySelector(".bt").textContent = t("resume_short"); g.title = on ? t("tip_resume") : t("why_off"); }
      const k = el.querySelector(".abk-cards");
      if (k) {
        k.querySelector(".abk-n").textContent = String(nc);
        k.querySelector(".bt").textContent = t("bk_pending");
        k.title = tn("tip_bk_pending", nc, s.cards.slice(0, 2).map(doWords).join(t("ch_s_sep")) + (nc > 2 ? "…" : ""));
      }
      holdMin(el);
    }
    const st = el.querySelector(".abk-st");
    if (st) {
      const [words, secs] = stText(s), tip = stTip(s), w = st.firstChild, sec = st.lastChild;
      if (w.textContent !== words) w.textContent = words;
      if (sec.textContent !== secs) sec.textContent = secs;
      if (st.title !== tip) st.title = tip;
    }
    popSync(s);
    renderCards();
    pauseSync(!off && !s.paused ? s : null);
    // the countdown's next whole second, while a call is held; what was asked, when it lapses
    let wait = s.n && s.left ? (s.p.deadline - now()) * 1000 % 1000 + 15 : Infinity;
    [[want.mode, want.mAt], [want.paused, want.pAt]].forEach(([w, at]) => { if (w !== null) wait = Math.min(wait, at + WANT_MS - Date.now() + 15); });
    if (wait < Infinity) timer = setTimeout(renderBrake, Math.max(50, wait));
  }

  /** The narrowest the group may get in the header: its buttons whole, 3em of the paused words
   *  and room for their seconds (the bar's nowrap would make its own narrowest all of the words,
   *  so it would never give way; with none, 0, it would crush its buttons). Measured once each
   *  time it is drawn anew. */
  function holdMin(el) {
    el.style.minWidth = "";
    const st = el.querySelector(".abk-st"), cs = getComputedStyle(el), kids = [...el.children], px = (v) => parseFloat(v) || 0;
    const stMin = () => { const c = getComputedStyle(st); return px(getComputedStyle(st.firstChild).minWidth) + px(c.columnGap) + px(c.fontSize) * 3.2; };
    const w = kids.reduce((a, c) => a + (c === st ? stMin() : c.offsetWidth), 0)
      + px(cs.columnGap) * Math.max(0, kids.length - 1) + px(cs.paddingLeft) + px(cs.paddingRight);
    el.style.minWidth = `${Math.ceil(w)}px`;
  }

  /** ⏸ at #ai-bar's end while the AI works (a call in flight, or waiting), where it can be paused
   *  (`s`: the group's view; null: it cannot). app-conn.js draws the bar's words, and draws them
   *  anew when they change; renderConn calls renderBrake right after, so the button comes back. */
  function pauseSync(s) {
    const bar = $("ai-bar");
    if (!bar) return;
    if (!bar.dataset.bkWired) {
      bar.dataset.bkWired = "1";
      bar.addEventListener("click", (ev) => { const x = ev.target.closest("[data-b=pause]"); if (x && !x.disabled) pause(); });
    }
    const cl = bar.classList, on = !!s && !cl.contains("hidden") && (cl.contains("now") || cl.contains("wait"));
    let p = bar.querySelector(".ab-pause");
    if (!on) { if (p) p.remove(); return; }
    if (!p) {
      bar.insertAdjacentHTML("beforeend", `<button class="ab-pause flat icon" data-b="pause">${icon("pause")}</button>`);
      p = bar.querySelector(".ab-pause");
    }
    const tip = t("tip_pause", s.hold), lab = t("pause_btn");
    if (p.title !== tip) p.title = tip;
    if (p.getAttribute("aria-label") !== lab) p.setAttribute("aria-label", lab);
  }

  /** The popover open from "Resume" (popAt: its button, maybe drawn anew since): its countdown as
   *  the group's; closed once the pause ended. */
  let popAt = null;
  function popSync(s) {
    const m = $("menu");
    if (!popAt || wb.menuAt !== popAt || m.classList.contains("hidden")) { popAt = null; return; }
    if (!s.paused) { popAt = null; closeMenus(); return; }
    const box = m.querySelector(".abk-pop");
    if (box && box.dataset.n !== String(s.n)) {      // a call came to wait, or its wait ended: its lines anew (the box kept)
      box.dataset.n = String(s.n);
      box.querySelectorAll("p").forEach((x) => x.remove());
      box.insertAdjacentHTML("afterbegin", popLines(s));
      const tt = m.querySelector(".mt");
      if (tt) tt.title = popTip(s);
    }
    const cd = m.querySelector(".abk-cd");
    if (cd) { const w = leftWords(s); if (cd.textContent !== w) cd.textContent = w; }
  }

  function onClick(ev) {
    const btn = ev.target.closest("[data-b]");
    if (!btn || btn.disabled) return;
    const a = btn.dataset.b;
    if (a === "mode") toggleMenu(btn, modeItems, ev);
    else if (a === "cards") openCards(null);
    else if (a === "resume") {
      toggleMenu(btn, resumeItems, ev);
      const open = wb.menuAt === btn && !$("menu").classList.contains("hidden"), inp = open && $("menu").querySelector(".abk-in");
      popAt = open ? btn : null;
      if (inp && !inp.disabled) inp.focus({ preventScroll: true });
    }
  }

  // ------------------------------------------------------------------ the popovers (#menu)
  /** The review menu, two sections: why review is off, first; "Review mode" (its tooltip: what
   *  holds with the window closed; its ⚙: the auto-pause rules) -- the modes, each with its line,
   *  the one in force checked, then "Pause AI", or while paused "Resume AI" (its popover), and what
   *  other parts add to it (brakeMenuAdd "review"); "Tracking and learning", the switches other parts add
   *  (brakeMenuAdd "view"); the changes refused in read-only, only then. */
  function modeItems() {
    const b = view();
    if (!b) return [];
    const s = shown(b), on = !!wb.connected, off = !on || !s.live, items = [];
    if (off) items.push({ html: `<div class="abk-offl">${icon("shield-off")}<span>${esc(t(on ? "aim_not_live" : "aim_off_conn"))}</span></div>` });
    items.push(titleItem(t("aim_title"), b, () => chipBtn(), t("aim_foot")));
    const row = (m) => {
      const cur = m === s.mode;
      return `<button class="mi abk-mi${cur ? " cur" : ""}" role="menuitemradio" aria-checked="${cur}" data-mode="${m}"${on ? "" : " disabled"}>`
        + `${icon(MODE_ICON[m])}<span class="abk-mt"><b>${esc(t(`aim_${m}`))}${m === DEFAULT_MODE ? `<i>${esc(t("aim_default"))}</i>` : ""}</b>`
        + `<small>${esc(t(`aim_${m}_d`))}</small></span><svg class="ic ck" aria-hidden="true"><use href="#i-check"/></svg></button>`;
    };
    items.push({ html: `<div class="abk-modes">${MODES.map(row).join("")}</div>`,
                 wire: (box) => box.querySelectorAll("[data-mode]").forEach((x) => x.addEventListener("click", () => { closeMenus(); setMode(x.dataset.mode); })) });
    const act = [];
    if (s.paused) {
      const since = s.p && num(s.p.since) ? hhmm(s.p.since) : null;
      act.push({ label: `${t("resume_btn")}…`, icon: "play", cls: "abk-gomi", keys: since ? t(s.auto ? "aim_autopaused_at" : "aim_paused_at", since) : "",
                 disabled: !on, tip: on ? stTip(s) : t("why_off"), run: openResume });
    } else if (!off) {
      act.push({ label: t("pause_btn"), icon: "pause", cls: "abk-pmi", tip: t("tip_pause", s.hold), run: pause });
    }
    act.push(...switchItems("review"));
    if (act.length) items.push({ sep: true }, ...act);
    const sw = switchItems("view");
    if (sw.length) items.push({ sep: true }, { title: t("aim_sec_view") }, ...sw);
    if (s.mode === "observe" && s.refused) {
      const since = isObj(b.refused) && num(b.refused.since) ? hhmm(b.refused.since) : null;
      items.push({ sep: true }, { html: `<div class="abk-refl">${esc(since ? tn("mp_bk_refused", s.refused, since) : tn("aim_refused_n", s.refused))}</div>` });
    }
    return items;
  }
  /** Another part's items in the review menu: `fn` returns its menu items (openMenu's), drawn
   *  each time the menu opens, in `section` -- "view" (the default: "Tracking and learning", a switch
   *  such as "Follow AI edits" or "Learning mode", which the ... menu has too) or "review" (after
   *  "Pause AI", the review
   *  menu's own). */
  const brakeMenuAdd = (fn, section) => {
    if (typeof fn === "function") extras[SECTIONS.includes(section) ? section : "view"].push(fn);
  };
  /** A section's items, in the order their parts added them. */
  function switchItems(section) {
    const out = [];
    extras[section].forEach((f) => { try { out.push(...(f() || [])); } catch (e) { console.error(e); } });
    return out;
  }
  /** The "Tracking and learning" switches, for the ... menu (app-main.js moreItems): the same as the review
   *  menu's, whether or not there is one (a server without it, or ASPEN_MCP_BRAKE=0). */
  const brakeSwitches = () => switchItems("view");
  /** The switches' names, for the shield's tooltip: each item's label, or its html's words. */
  const named = new Map();
  function switchNames() {
    return switchItems("view").map((it) => {
      if (it.label) return String(it.label);
      if (!it.html) return "";
      let s = named.get(it.html);
      if (s === undefined) {
        const tp = document.createElement("template");
        tp.innerHTML = it.html;
        s = tp.content.textContent.replace(/\s+/g, " ").trim();
        if (named.size > 40) named.clear();
        named.set(it.html, s);
      }
      return s;
    }).filter(Boolean);
  }

  /** The popover's lines: why the stuck rule paused the AI (and the records that made it), what
   *  waits and until when; nothing more while nothing waits (the title's tooltip says what a
   *  pause does). */
  function popLines(s) {
    const lines = [];
    if (s.auto) {
      // why, in the server's words; the records that made it pause (in Changes)
      lines.push(`<p class="abk-why">${esc(whyWords(s.p))}</p>`);
      const ev = evidence(s.p);
      if (ev.can) {
        const n = ev.ids.length, w = n ? tn("stk_ev", n) : t("stk_ev0");
        lines.push(`<p class="abk-evl"><button class="flat abk-ev" data-e="1" title="${esc(t(n ? "tip_stk_ev" : "tip_stk_ev0"))}">`
          + `${icon("eye")}<span>${esc(w)}</span></button></p>`);
      }
    }
    if (s.n) lines.push(`<p>${esc(tn("resume_held", s.n, heldWords(s)))}</p>`, `<p class="abk-cd">${esc(leftWords(s))}</p>`);
    return lines.join("");
  }
  /** The popover title's tooltip: what the pause holds while nothing waits, what it never stops. */
  const popTip = (s) => [!s.n && t("resume_none", s.hold), t("resume_foot")].filter(Boolean).join("\n");
  /** "Resume": popLines, a note for the AI (optional; Enter goes too), and "Resume AI". Paused by
   *  the stuck rule: "Resume; disable this rule for this request" too (its mute), and the rules
   *  ("Auto-pause rules…"). */
  function resumeItems() {
    const b = view();
    if (!b) return [];
    const s = shown(b), on = !!wb.connected, ph = esc(t("resume_note")), rule = s.auto ? ruleOf(s.p) : null;
    const note = () => { const inp = $("menu").querySelector(".abk-in"); return inp ? inp.value : ""; };
    const items = [titleItem(t(s.auto ? "paused_auto_st" : "paused_st"), null, null, popTip(s)),
      { html: `<div class="abk-pop${s.auto ? " auto" : ""}" data-n="${s.n}">${popLines(s)}<input class="abk-in" type="text" maxlength="${NOTE_MAX}" placeholder="${ph}" aria-label="${ph}"${on ? "" : " disabled"}></div>`,
        wire: (box) => {
          const inp = box.querySelector("input");
          inp.addEventListener("keydown", (e) => {
            if (e.key !== "Enter" || e.isComposing || e.keyCode === 229) return;   // (Enter picks a character in an IME)
            e.preventDefault();
            closeMenus();
            resume(inp.value);
          });
          // (its lines are drawn anew while it shows: popSync)
          box.addEventListener("click", (e) => {
            if (!e.target.closest(".abk-ev")) return;
            const bb = view();
            closeMenus();
            if (bb && bb.paused) showEvidence(bb.paused);
          });
        } },
      { label: t("resume_btn"), icon: "play", cls: "abk-gomi", disabled: !on, tip: on ? "" : t("why_off"), run: () => resume(note()) }];
    if (rule) {
      items.push({ label: t("stk_mute"), cls: "abk-mute", disabled: !on, tip: on ? t("tip_stk_mute", t(`stk_rule_${rule}`)) : t("why_off"),
                   run: () => resume(note(), rule) });
    }
    if (s.auto && stuckOn(b)) {
      items.push({ sep: true }, { label: t("stk_open"), icon: "gear", cls: "abk-stkmi", tip: t("tip_stk_open"), run: () => openStuck(chipBtn()) });
    }
    return items;
  }

  /** A popover's title (`tip`: its tooltip), and where the server has the stuck rules (`b`) a
   *  small ⚙ at its end that opens them (anchor(): where they open). */
  function titleItem(title, b, anchor, tip) {
    const tt = tip ? ` title="${esc(tip)}"` : "";
    if (!stuckOn(b)) return tip ? { html: `<div class="mt"${tt}>${esc(title)}</div>` } : { title };
    const gt = esc(t("tip_stk_open"));
    return { html: `<div class="mt abk-mth"${tt}><span>${esc(title)}</span><button class="flat icon abk-gear" data-g="stuck" title="${gt}" aria-label="${gt}">${icon("gear")}</button></div>`,
             wire: (box) => box.querySelector(".abk-gear").addEventListener("click", () => openStuck(anchor())) };
  }
  const chipBtn = () => document.querySelector("#ai-brake .abk-mode");

  // ------------------------------------------------------------------ the evidence
  /** The records that made the stuck rule pause the AI: {ids (record ids, the evidence), gid (its
   *  group, where known), model, can: the Changes tab can show them (the model shown's)}. */
  function evidence(p) {
    const d = detailOf(p), ids = Array.isArray(d.ids) ? d.ids.filter((x) => typeof x === "string" && x) : [];
    const g = (p && p.group) || d.group, gid = typeof g === "string" && g ? g : null, model = typeof d.model === "string" && d.model ? d.model : null;
    const pane = wb.pane, tab = shownTab();
    let can = !!pane && !!tab && WBC.on();
    if (can && model) { const m = changesCtx(pane, tab).model; can = !m || m === model; }
    return { ids, gid, model, can };
  }
  /** The Changes tab shown (the dock opened where it is folded), the card holding the last
   *  record of the evidence (or its group) opened, in view and flashed. */
  function showEvidence(p) {
    const ev = evidence(p), pane = wb.pane, tab = shownTab();
    if (!ev.can) return;
    if (prefs().dockMode === "min") setDock(pane, "split");
    showPanel(pane, "changes");
    if (ev.ids.length || ev.gid) WBC.showGroup(pane.q(".tab-changes"), changesCtx(pane, tab), ev.gid, ev.ids[ev.ids.length - 1] || null);
  }

  // ------------------------------------------------------------------ the stuck rules
  const stuckOn = (b) => !!b && feature("stuck") && isObj(b.stuck);
  const clamp = (k, v, dflt) => { const n = Math.round(Number(v)); return isFinite(n) && String(v).trim() !== "" ? Math.max(RANGE[k][0], Math.min(RANGE[k][1], n)) : dflt; };
  /** The rules in force: the server's (brake.stuck), what was just saved here laid over them. */
  function stuckCfg(b) {
    const s = b && isObj(b.stuck) ? b.stuck : {}, on = isObj(s.on) ? s.on : {}, out = { on: {} };
    RULES.forEach((k) => { out[k] = num(s[k]) ? clamp(k, s[k], DEFAULTS[k]) : DEFAULTS[k]; out.on[k] = on[k] !== false; });
    if (want.stuck) {
      if (Date.now() - want.sAt > WANT_MS || JSON.stringify(out) === JSON.stringify(want.stuck)) want.stuck = null;
      else return JSON.parse(JSON.stringify(want.stuck));
    }
    return out;
  }
  /** The rules' popover: each rule a line with its number in the sentence and a box to turn it
   *  off; "Save" posts brake_stuck (each number held in its range), "Defaults" fills the defaults in.
   *  What counts is its title's tooltip. */
  function stuckItems() {
    const b = view();
    if (!stuckOn(b)) return [];
    const cfg = stuckCfg(b), on = !!wb.connected, dis = on ? "" : " disabled";
    const row = (k) => {
      const [a, z] = t(`stk_${k}`).split("{0}"), [lo, hi] = RANGE[k], rt = esc(t("tip_stk_range", lo, hi));
      return `<label class="abk-sr" data-k="${k}"><input type="checkbox" data-s="on"${cfg.on[k] ? " checked" : ""}${dis}>`
        + `<span class="abk-sx">${esc(a || "")}<input type="number" data-s="n" min="${lo}" max="${hi}" step="1" value="${cfg[k]}" title="${rt}" aria-label="${esc(t(`stk_rule_${k}`))} (${rt})"${dis}>`
        + `${esc(z || "")}</span></label>`;
    };
    const html = `<div class="abk-stk keys-own">${RULES.map(row).join("")}`
      + `<div class="abk-sf"><button class="flat" data-s="dflt" title="${esc(t("tip_stk_dflt"))}"${dis}>${esc(t("stk_dflt"))}</button>`
      + `<button class="primary" data-s="save" title="${esc(on ? t("tip_stk_save") : t("why_off"))}"${dis}>${esc(t("stk_save"))}</button></div></div>`;
    return [titleItem(t("stk_title"), null, null, t("stk_foot")), { html, wire: wireStuck }];
  }
  function wireStuck(box) {
    const el = box.querySelector(".abk-stk");
    const fix = (x) => { const k = x.closest("[data-k]").dataset.k; x.value = String(clamp(k, x.value, stuckCfg(view())[k])); };
    el.addEventListener("change", (e) => { if (e.target.type === "number") fix(e.target); });
    el.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-s]");
      if (!btn || btn.disabled) return;
      if (btn.dataset.s === "dflt") {
        el.querySelectorAll("[data-k]").forEach((r) => {
          r.querySelector("input[type=number]").value = String(DEFAULTS[r.dataset.k]);
          r.querySelector("input[type=checkbox]").checked = true;
        });
      } else saveStuck(el);
    });
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && e.target.type === "number") { e.preventDefault(); saveStuck(el); return; }
      if (e.key !== "Tab") return;                   // (the keys stay in the popover: app-widgets.js menuKey, keys-own)
      const all = [...el.querySelectorAll("input:not(:disabled), button:not(:disabled)")], i = all.indexOf(e.target);
      if (!all.length || (i !== all.length - 1 && !e.shiftKey) || (i !== 0 && e.shiftKey)) return;
      e.preventDefault();
      all[e.shiftKey ? all.length - 1 : 0].focus();
    });
  }
  function saveStuck(el) {
    const b = view();
    if (!stuckOn(b) || !wb.connected) return;
    const cur = stuckCfg(b), ev = { type: "brake_stuck", on: {} };
    el.querySelectorAll("[data-k]").forEach((r) => {
      const k = r.dataset.k;
      ev[k] = clamp(k, r.querySelector("input[type=number]").value, cur[k]);
      ev.on[k] = r.querySelector("input[type=checkbox]").checked;
    });
    closeMenus();
    const cfg = { on: ev.on };
    RULES.forEach((k) => { cfg[k] = ev[k]; });
    if (JSON.stringify(cur) === JSON.stringify(cfg)) { toast(t("stk_same"), 3000); return; }
    want.stuck = cfg;
    want.sAt = Date.now();
    wb.post({ type: "brake_stuck", runs: ev.runs, field: ev.field, revert: ev.revert, on: ev.on });
    toast(t("stk_saved", RULES.filter((k) => ev.on[k]).map((k) => t(`stk_short_${k}`, ev[k])).join(t("ch_s_sep")) || t("stk_none")), 5000);
  }
  /** The rules' popover, from `at` (the chip, or the model panel's capsule). */
  function openStuck(at) {
    if (!at || !stuckOn(view())) return;
    popAt = null;
    openMenu(at, stuckItems());
    wb.menuBack = at;
  }

  // ------------------------------------------------------------------ what the buttons post
  function setMode(m) {
    const b = view();
    if (!b || !MODES.includes(m) || !wb.connected) return;
    if (m !== shown(b).mode) {
      want.mode = m;
      want.mAt = Date.now();
      wb.post({ type: "brake_mode", mode: m });
      toast(t("aim_toast", modeFull(m), t(`aim_${m}_d`)), 4000);
    }
    renderBrake();
  }
  function pause() {
    if (!view() || !wb.connected) return;
    want.paused = true;
    want.pAt = Date.now();
    wb.post({ type: "brake_pause" });
    toast(t("ai_paused"), 4000);
    renderBrake();
  }
  /** "Resume AI", with a line for it (optional); `mute`: a stuck rule not to pause it again in its group. */
  function resume(note, mute) {
    if (!view() || !wb.connected) return;
    const n = String(note || "").replace(/\s+/g, " ").trim().slice(0, NOTE_MAX), ev = { type: "brake_resume" };
    if (n) ev.note = n;
    if (RULES.includes(mute)) ev.mute = mute;
    want.paused = false;
    want.pAt = Date.now();
    wb.post(ev);
    toast(ev.mute ? t(n ? "stk_mute_toast_note" : "stk_mute_toast", t(`stk_rule_${mute}`)) : t(n ? "resume_toast_note" : "ai_resumed"), 4000);
    renderBrake();
  }

  // ================================================================== the cards
  const asked = new Map();      // card id -> {decision | dismiss, at, req, from: its status then}: posted, not answered yet
  const allow = new Map();      // card id -> its "without asking" box ticked
  let form = null;              // {id, value}: a decline's note being written (kept while the card is drawn anew)
  let known = null;             // the card ids seen: a new one waiting toasts once
  let drawn = new Set();        // the card ids on screen: a new one rises in once
  let cdTimer = 0;

  const cardsOf = (b) => (b && Array.isArray(b.cards) ? b.cards.filter((c) => isObj(c) && num(c.id)) : []);
  /** Answered, or given up on: what was asked here no longer overlays the card. */
  function askedSync(all) {
    const ms = Date.now();
    asked.forEach((a, id) => {
      const c = all.find((x) => x.id === id);
      if (!c || c.status !== a.from || (a.req && isObj(c.decided) && c.decided.req === a.req) || ms - a.at > WANT_MS) asked.delete(id);
    });
  }
  const sending = (c) => { const a = asked.get(c.id); return a && a.decision ? a.decision : null; };
  const gone = (c) => { const a = asked.get(c.id); return !!(a && a.dismiss); };
  /** The cards still to decide, the ones the AI waits on first (then oldest first); none asked. */
  function toDecide(b) {
    const all = cardsOf(b);
    askedSync(all);
    return all.filter((c) => PENDING.includes(c.status) && !sending(c))
      .sort((x, y) => (waits(y) - waits(x)) || ((x.t || 0) - (y.t || 0)));
  }
  const waits = (c) => (c.status === "waiting" && c.live !== false ? 1 : 0);
  /** Seconds the AI still waits on a card, or null (it does not, or no time is known: none
   *  given, or one past any hold -- a clock not this machine's). */
  function leftOf(c) {
    if (!waits(c) || !num(c.until)) return null;
    const left = Math.max(0, Math.ceil(c.until - now())), b = view();
    return left > (b && num(b.hold_s) ? b.hold_s : 40) + 20 ? null : left;
  }

  /** What the AI wants to do, as a verb phrase: "delete block B4 (HEATER)", in the window's language. */
  function doWords(c) {
    const r = Array.isArray(c.risky) && isObj(c.risky[0]) ? c.risky[0] : {}, tg = isObj(c.target) ? c.target : {};
    const a = isObj(c.args) ? c.args : {}, code = r.code || c.tool;
    const fx = (k) => ((c.effects || []).find((e) => isObj(e) && e.code === k) || {});
    switch (code) {
      case "remove_block": return t("bkc_t_remove_block", r.block || tg.block || "?") + (r.type ? t("bkc_type", r.type) : "");
      case "remove_stream": return t("bkc_t_remove_stream", r.stream || tg.stream || "?");
      case "remove_component": return t("bkc_t_remove_component", r.component || tg.component || "?");
      case "remove_reaction_set": return t("bkc_t_remove_reaction_set", r.rxnset || tg.rxnset || "?");
      case "remove_reaction": return t("bkc_t_remove_reaction", r.rxnset || tg.rxnset || "?", r.reaction ?? a.reaction_no ?? "?");
      case "remove_item": case "remove_side_duty": case "remove_element": case "remove_row": return t("bkc_t_remove_item");
      case "reinit_simulation": return t("bkc_t_reinit_simulation");
      case "close_aspen_plus": return a.session_name ? t("bkc_t_close_aspen_plus", r.file || base(a.session_name)) : t("bkc_t_close_all");
      case "create_new_simulation": return t("bkc_t_create_new_simulation", base(r.path) || a.project_name || "?");
      case "save_other": case "save_simulation": return t("bkc_t_save_simulation", r.file || tg.file || "?");
      case "program_save": case "workbench_run": return t("bkc_t_workbench_run", fx("program_runs").tab || tg.tab || "?");
      default: return t("bkc_t_other", c.tool || "?");
    }
  }
  /** Where it acts on the flowsheet: "block:B4" / "stream:S5", or null. */
  function objOf(c) {
    const r = Array.isArray(c.risky) && isObj(c.risky[0]) ? c.risky[0] : {}, tg = isObj(c.target) ? c.target : {};
    if (r.code === "remove_block" || (!r.code && c.tool === "remove_block")) return (r.block || tg.block) ? `block:${r.block || tg.block}` : null;
    if (r.code === "remove_stream" || (!r.code && c.tool === "remove_stream")) return (r.stream || tg.stream) ? `stream:${r.stream || tg.stream}` : null;
    return null;
  }
  const hereOf = (c) => { const tab = shownTab(); return !!tab && !!c.session && tab.session === c.session; };
  /** An effect in words: the server's own, else the window's for its code (or nothing). */
  function fxWords(e) {
    if (!isObj(e)) return "";
    if (isObj(e.text) && (e.text[I18N.lang] || e.text.en)) return String(e.text[I18N.lang] || e.text.en);
    const k = `bkc_fx_${e.code}`;
    return I18N.t(k) !== k ? t(k) : "";
  }
  /** The restore point saved first, in words: {text, slow (s it would take: the button), cls}; null for none to say. */
  function cpLine(c) {
    const cp = isObj(c.cp) ? c.cp : null;
    if (!cp || !cp.tier) return null;
    const s = num(cp.est_s) && cp.est_s > 0 ? cp.est_s : null;
    switch (cp.tier) {
      case "copy": return { text: t("bkc_cp_copy", est(s || 1)) };
      case "export": return { text: s ? t("bkc_cp_export", est(s)) : t("bkc_cp_export0") };
      case "reuse": return { text: num(cp.t) ? t("bkc_cp_reuse", hhmm(cp.t)) : t("bkc_cp_dedup") };
      case "dedup": return { text: t("bkc_cp_dedup") };
      case "skip": return { text: t("bkc_cp_skip", est(cp.slow_s || 120)), slow: Number(cp.slow_s) || 120, cls: "warn" };
      case "backup": return { text: cp.why === "program_saves" ? t("bkc_cp_program") : s ? t("bkc_cp_backup", est(s)) : t("bkc_cp_backup0") };
      case "none": {
        const k = { saved: "bkc_cp_none_saved", results_only: "bkc_cp_none_results", new_file: "bkc_cp_none_new" }[cp.why];
        return k ? { text: t(k), cls: "none" } : null;
      }
      default: return null;
    }
  }
  /** Why a card can no longer be applied, in words. */
  const expWords = (why) => { const k = `bkc_x_${why}`; return I18N.t(k) !== k ? t(k) : t("bkc_x_other"); };
  /** Who holds the model while a late apply waits: "the program on tab “Reflux sweep”" / the AI's optimize. */
  function holderWords(bz) {
    if (!isObj(bz)) return "";
    if (bz.title) return t("bkc_busy_tab", bz.title);
    if (bz.tool) return t("bkc_busy_tool", bz.tool);
    return t("bkc_busy");
  }
  /** The line beside a card's buttons once the AI no longer waits: what an approval now is (or
   *  who holds the model); null while it waits (the head counts its seconds). */
  function waitLine(c) {
    const left = leftOf(c);
    if (c.status === "waiting" && waits(c)) return left === 0 ? { text: t("bkc_wait0"), tip: t("tip_bkc_late", c.id) } : null;
    if (isObj(c.busy)) return { text: holderWords(c.busy), cls: "warn", tip: c.busy.text || "" };
    const k = c.status === "cancelled" ? "bkc_cancelled" : c.closed ? "bkc_closed" : "bkc_late";
    return { text: t(k), tip: t("tip_bkc_late", c.id) };
  }
  /** Where a card's wait stands, for its signature: counting, over, or no time known. */
  const waitPhase = (c) => { const l = leftOf(c); return l === null ? "n" : l > 0 ? "c" : "0"; };

  const btn = (k, label, cls, tip, off) => `<button class="${cls || ""}" data-k="${k}"${tip ? ` title="${esc(tip)}"` : ""}${off ? " disabled" : ""}>${esc(label)}</button>`;

  /** A card still to decide (or being applied): the whole of it. Its head: what the AI asks,
   *  and on its right "Pending · 38 s · 14:02" (its number in the tooltip); the request it came in,
   *  the AI's reason, "Effects", the restore point, the allow box, the buttons. */
  function cardHtml(c, on) {
    const doing = sending(c), st = doing ? `sending ${doing}` : c.status, obj = objOf(c), here = obj && hereOf(c);
    const head = esc(t("bkc_head", doWords(c)));
    const title = here
      ? `<button class="bkc-t flat" data-k="go" title="${esc(t("tip_bkc_go", obj.slice(obj.indexOf(":") + 1)))}">${icon("warn")}<span>${head}</span></button>`
      : `<span class="bkc-t">${icon("warn")}<span>${head}</span></span>`;
    const sub = [c.group_title && t("bkc_req", c.group_title), c.session && !hereOf(c) && t("model_is", c.session)].filter(Boolean).join(" · ");
    const fx = (Array.isArray(c.effects) ? c.effects : []).map(fxWords).filter(Boolean);
    const more = [num(c.more) && c.more > 0 && tn("bkc_more", c.more), num(c.since_changes) && c.since_changes > 0 && tn("bkc_since", c.since_changes),
      isObj(c.declined_before) && (c.declined_before.comment ? t("bkc_again_note", num(c.declined_before.t) ? hhmm(c.declined_before.t) : "?", c.declined_before.comment)
        : t("bkc_again", num(c.declined_before.t) ? hhmm(c.declined_before.t) : "?"))].filter(Boolean);
    const cp = cpLine(c), open = PENDING.includes(c.status) && !doing;
    // the head's right: "Pending" and the AI's seconds while it counts them; the time alone once decided
    const left = open ? leftOf(c) : null, counting = !!left && c.status === "waiting";
    const meta = (open ? [`<span>${esc(t("bkc_st_wait"))}</span>`] : [])
      .concat(counting ? [`<span class="bkc-cd" data-id="${c.id}" data-s="1">${esc(t("dur_s", left))}</span>`] : [], [`<span>${esc(hhmm(c.t || now()))}</span>`]);
    const mtip = [`#${c.id}`, counting && t("tip_bkc_wait")].filter(Boolean).join("\n");
    let h = `<article class="bkc s-${st.split(" ").join(" s-")}" data-id="${c.id}">`
      + `<div class="bkc-h">${title}<span class="bkc-m" title="${esc(mtip)}">${meta.join(" · ")}</span></div>`
      + (sub ? `<div class="bkc-sub">${esc(sub)}</div>` : "");
    if (c.reason) h += `<p class="bkc-why" title="${esc(t("tip_reason"))}">${esc(t("reason", c.reason))}</p>`;
    if (fx.length) h += `<p class="bkc-fxh">${esc(t("bkc_fx"))}</p><ul class="bkc-fx">${fx.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
    if (more.length) h += more.map((x) => `<p class="bkc-note">${esc(x)}</p>`).join("");
    if (cp) h += `<p class="bkc-cp${cp.cls ? ` ${cp.cls}` : ""}"><span class="bkc-ms" aria-hidden="true">◆</span>${esc(cp.text)}</p>`;
    if (open && c.group) {
      const cls = CLASSES.includes(c.class) ? c.class : "other";
      h += `<label class="bkc-allow" title="${esc(t("tip_bkc_allow"))}"><input type="checkbox" data-k="allow"${allow.get(c.id) ? " checked" : ""}${on ? "" : " disabled"}>`
        + `<span>${esc(t("bkc_allow", t(`bkc_cls_${cls}`)))}</span></label>`;
    }
    // the buttons, and beside them (under them where the dock is narrow) what an approval is once the
    // AI stopped waiting; they stay in sight at the foot of a dock too short for the whole card
    // (style.css: sticky)
    const w = open ? waitLine(c) : null;
    const wait = w ? `<span class="bkc-wait${w.cls ? ` ${w.cls}` : ""}" data-id="${c.id}"${w.tip ? ` title="${esc(w.tip)}"` : ""}>${esc(w.text)}</span>` : "";
    if (open && form && form.id === c.id) {
      const ph = esc(t("bkc_ph"));
      h += `<div class="bkc-form"><input class="bkc-in" type="text" maxlength="${NOTE_MAX}" placeholder="${ph}" aria-label="${ph}"${on ? "" : " disabled"}>`
        + btn("send", t("bkc_send"), "danger", t("tip_bkc_send"), !on) + btn("cancel", t("bkc_cancel"), "flat") + wait + `</div>`;
    } else if (open) {
      const off = on ? "" : t("why_off"), late = c.status !== "waiting" || !waits(c);
      h += `<div class="bkc-act">${btn("apply", t("bkc_apply"), "primary", off || t(late ? "tip_bkc_apply_late" : "tip_bkc_apply"), !on)}`
        + (cp && cp.slow ? btn("slow", t("bkc_cp_slow_btn", est(cp.slow)), "", off || t("tip_bkc_slow"), !on) : "")
        + btn("decline", t("bkc_decline"), "", off || t("tip_bkc_decline"), !on) + wait + `</div>`;
    } else {
      const late = isObj(c.decided) && c.decided.how === "late";
      const words = doing === "decline" ? t("bkc_declining") : doing === "apply" ? t("bkc_applying") : t(late ? "bkc_applying_late" : "bkc_applying");
      h += `<div class="bkc-act"><span class="bkc-wait busy">${esc(words)}</span></div>`;
    }
    return h + `</article>`;
  }
  /** A decided card: one line, and × to take it off (the timeline keeps it). */
  function oneHtml(c, on) {
    const d = isObj(c.decided) ? c.decided : {}, what = doWords(c);
    let text, ic = "check", cls = c.status;
    if (c.status === "applied") text = t(d.how === "late" ? "bkc_done_late" : "bkc_done_live", what);
    else if (c.status === "failed") { text = t("bkc_failed", what); ic = "warn"; }
    else if (c.status === "declined") { text = d.comment ? t("bkc_declined_note", what, d.comment) : t("bkc_declined", what); ic = "close"; }
    else { text = t("bkc_expired", what, expWords(c.why)); ic = "info"; cls = "expired"; }
    const res = isObj(c.result) && c.result.text ? `\n${c.result.text}` : "";
    return `<div class="bkc-one s-${cls}" data-id="${c.id}" title="${esc(text + res)}">${icon(ic)}<span class="bkc-ot">${esc(text)}</span>`
      + `<span class="bkc-m">#${c.id} · ${hhmm((isObj(c.decided) && num(c.decided.t) ? c.decided.t : c.t) || now())}</span>`
      + `<button class="flat icon bkc-x" data-k="dismiss" title="${esc(t("tip_bkc_dismiss"))}"${on ? "" : " disabled"}>${icon("close")}</button></div>`;
  }
  /** The dock's part over the Changes tab (or the AI chat where the server keeps no timeline):
   *  the cards to decide; where no timeline has them, or they failed, the decided ones as a line
   *  each; the flowsheet's frames; a new card's toast while the dock is folded. */
  function renderCards() {
    clearTimeout(cdTimer);
    cdTimer = 0;
    const b = view(), all = cardsOf(b), pane = wb.pane, el = pane && pane.q(".bk-dock");
    if (b) askedSync(all);
    const pend = b ? toDecide(b) : [], on = !!wb.connected;
    const nj = !WBC.on();                         // no timeline: the cards show over the AI chat
    const busy = all.filter((c) => c.status === "applying" || (sending(c) && PENDING.includes(c.status)));
    const done = all.filter((c) => !PENDING.includes(c.status) && c.status !== "applying" && !gone(c) && (nj || c.status === "failed"))
      .sort((x, y) => ((isObj(y.decided) && y.decided.t) || y.t || 0) - ((isObj(x.decided) && x.decided.t) || x.t || 0)).slice(0, DONE_SHOWN);
    markFs(pend);
    toastNew(all);
    if (!el) return;
    if (!el.dataset.wired) { el.dataset.wired = "1"; wireCards(el); }
    const items = [...pend.map((c) => ["c", c]), ...busy.map((c) => ["c", c]), ...done.map((c) => ["o", c])];
    const sig = JSON.stringify([I18N.lang, on, nj, pend.length, items.map(([k, c]) => [k, c.id, c.status, c.live, c.decided, c.result, c.since_changes,
      c.declined_before, c.busy, c.closed, c.cp, c.effects, c.reason, c.group_title, c.more, sending(c), allow.get(c.id) || false,
      form && form.id === c.id, hereOf(c), c.why, k === "c" && PENDING.includes(c.status) ? waitPhase(c) : null])]);
    const hadFocus = form && document.activeElement && document.activeElement.classList.contains("bkc-in");
    if (el.dataset.sig !== sig) {
      el.dataset.sig = sig;
      el.className = `bk-dock${items.length ? " has" : ""}${pend.length ? " pend" : ""}${nj ? " nj" : ""}`;
      const head = pend.length > 1 ? `<div class="bk-h">${icon("warn")}<b>${esc(t("bkc_title", pend.length))}</b></div>` : "";
      const html = items.map(([k, c]) => (k === "c" ? cardHtml(c, on) : oneHtml(c, on))).join("");
      el.innerHTML = `<div class="bk-full">${head}${html}</div>`;
      const seen = new Set();
      el.querySelectorAll(".bk-full [data-id]").forEach((x) => {
        const id = Number(x.dataset.id);
        seen.add(id);
        if (!drawn.has(id)) x.classList.add("in");        // (a card new here rises in, once)
      });
      drawn = seen;
      const inp = form && el.querySelector(`.bkc[data-id="${form.id}"] .bkc-in`);
      if (inp) {
        inp.value = form.value || "";
        if (hadFocus || form.focus) { form.focus = false; inp.focus({ preventScroll: true }); inp.setSelectionRange(inp.value.length, inp.value.length); }
      } else if (form && !pend.some((c) => c.id === form.id)) form = null;
    }
    countdown(pend, true);
  }
  /** The seconds the AI still waits, each second, only while a card counts; its wait over, the
   *  card drawn anew (the line beside its buttons says so). `drawn`: just drawn (never again). */
  function countdown(pend, drawn) {
    const el = wb.pane && wb.pane.q(".bk-dock"), live = pend.filter((c) => leftOf(c));
    let over = false;
    if (el) {
      el.querySelectorAll(".bkc-cd").forEach((x) => {
        const c = pend.find((p) => String(p.id) === x.dataset.id);
        if (!c) return;
        const left = leftOf(c);
        if (!left) { over = true; return; }
        const w = t("dur_s", left);
        if (x.textContent !== w) x.textContent = w;
      });
    }
    if (over && !drawn) { renderCards(); return; }
    if (!live.length) return;
    const next = Math.min(...live.map((c) => ((c.until - now()) * 1000) % 1000)) + 15;
    cdTimer = setTimeout(() => { const b = view(); countdown(b ? toDecide(b) : []); }, Math.max(50, next));
  }
  /** The flowsheet frames the blocks and streams cards would remove, in the model shown. */
  let fsSig = null;
  function markFs(pend) {
    const pane = wb.pane;
    if (!pane || !pane.svg || typeof FS === "undefined") return;
    const keys = pend.filter(hereOf).map(objOf).filter(Boolean), sig = `${pane.tabId}|${keys.join(",")}`;
    if (sig === fsSig) return;
    fsSig = sig;
    FS.mark(pane.svg, keys, "bkpend");
  }
  /** A card new since the last state, waiting: a toast, once, only while the dock is folded (else
   *  the header's badge is its one announcement). */
  function toastNew(all) {
    const ids = new Set(all.map((c) => c.id));
    if (known) {
      const fresh = all.filter((c) => !known.has(c.id) && c.status === "waiting"), c = fresh[fresh.length - 1];
      if (c && prefs().dockMode === "min") toast(t("bkc_toast", doWords(c)), 6000, { label: t("show"), run: () => openCards(c.id) });
    }
    known = view() ? ids : null;
  }

  /** Show the cards (the Changes tab, or the AI chat without one; the dock opened if folded),
   *  the card `id` (else the first to decide) in view, flashed once. */
  function openCards(id) {
    const pane = wb.pane;
    if (!pane) return;
    if (prefs().dockMode === "min") setDock(pane, "split");
    showPanel(pane, WBC.on() ? "changes" : "msgs");
    renderCards();
    const full = pane.q(".bk-dock .bk-full");
    const card = full && ((id != null && full.querySelector(`[data-id="${id}"]`)) || full.querySelector(".bkc"));
    if (!card) return;
    card.scrollIntoView({ block: "nearest" });
    card.classList.remove("flash");
    void card.offsetWidth;
    card.classList.add("flash");
    setTimeout(() => card.classList.remove("flash"), 1300);
  }

  const reqId = () => `r${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  const cardOf = (id) => cardsOf(view()).find((c) => c.id === id) || null;
  function apply(c, slow) {
    if (!wb.connected || !PENDING.includes(c.status)) return;
    const req = reqId(), ev = { type: "brake_card", card: c.id, decision: "apply", req };
    if (allow.get(c.id) && c.group) ev.allow_group = true;
    if (slow) ev.slow_cp = true;
    asked.set(c.id, { decision: "apply", at: Date.now(), req, from: c.status });
    if (form && form.id === c.id) form = null;
    wb.post(ev);
    renderBrake();
  }
  function decline(c, note) {
    if (!wb.connected || !PENDING.includes(c.status)) return;
    const n = String(note || "").replace(/\s+/g, " ").trim().slice(0, NOTE_MAX), req = reqId();
    const ev = { type: "brake_card", card: c.id, decision: "decline", req };
    if (n) ev.comment = n;
    asked.set(c.id, { decision: "decline", at: Date.now(), req, from: c.status });
    form = null;
    wb.post(ev);
    toast(t(n ? "bkc_toast_declined_note" : "bkc_toast_declined", c.id), 4000);
    renderBrake();
  }
  function dismiss(c) {
    if (!wb.connected || PENDING.includes(c.status) || c.status === "applying") return;
    asked.set(c.id, { dismiss: true, at: Date.now(), from: c.status });
    wb.post({ type: "brake_dismiss", card: c.id });
    renderCards();
  }

  function wireCards(el) {
    el.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-k]");
      if (!b || b.disabled || b.tagName === "INPUT") return;
      const k = b.dataset.k, box = b.closest("[data-id]"), c = box ? cardOf(Number(box.dataset.id)) : null;
      if (!c) return;
      if (k === "go") {
        const o = objOf(c), pane = wb.pane;
        if (o && pane && hereOf(c)) gotoChange(pane, { kind: o.slice(0, o.indexOf(":")), name: o.slice(o.indexOf(":") + 1) });
      } else if (k === "apply" || k === "slow") apply(c, k === "slow");
      else if (k === "decline") { form = { id: c.id, value: "", focus: true }; renderCards(); }
      else if (k === "cancel") { form = null; renderCards(); }
      else if (k === "send") { const inp = box.querySelector(".bkc-in"); decline(c, inp ? inp.value : form && form.value); }
      else if (k === "dismiss") dismiss(c);
    });
    el.addEventListener("change", (ev) => {
      const x = ev.target;
      if (x.dataset.k !== "allow") return;
      const box = x.closest("[data-id]");
      if (box) allow.set(Number(box.dataset.id), x.checked);
      el.dataset.sig = "";                         // (its box drawn as it is now)
    });
    el.addEventListener("input", (ev) => { if (form && ev.target.classList.contains("bkc-in")) form.value = ev.target.value; });
    el.addEventListener("keydown", (ev) => {
      if (!ev.target.classList.contains("bkc-in")) return;
      if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); form = null; renderCards(); return; }
      if (ev.key !== "Enter" || ev.isComposing || ev.keyCode === 229) return;   // (Enter picks a character in an IME)
      ev.preventDefault();
      const c = cardOf(Number(ev.target.closest("[data-id]").dataset.id));
      if (c) decline(c, ev.target.value);
    });
  }

  // ------------------------------------------------------------------ the model panel's part
  /** The chip's menu, or the "Resume AI" popover, opened from elsewhere (the model panel). */
  function openModes() {
    const c = chipBtn();
    if (!c || !view()) return;
    popAt = null;
    openMenu(c, modeItems());
    wb.menuBack = c;
  }
  function openResume() {
    const g = document.querySelector("#ai-brake .abk-go");
    if (!g || g.disabled || !view()) return;
    openMenu(g, resumeItems());
    wb.menuBack = g;
    popAt = g;
    const inp = $("menu").querySelector(".abk-in");
    if (inp && !inp.disabled) inp.focus({ preventScroll: true });
  }
  /** The model panel's part on the brakes (they are the whole workbench's, not the model's): the
   *  mode and its line (a click: the chip's menu), or that they are off and why; paused (since
   *  when, why, what waits; "Resume…") or "Pause AI"; the cards to decide; the changes refused in
   *  Observe. A ⚙ opens the stuck rules. Nothing without the brakes. */
  function brakeItems() {
    const b = view();
    if (!b) return [];
    const s = shown(b), on = !!wb.connected, off = !s.live || !on;
    const line = (text, cls) => ({ html: `<div class="mp-line mp-bkl${cls ? ` ${cls}` : ""}">${esc(text)}</div>` });
    const items = [{ sep: true }, titleItem(t("mp_bk"), b, () => $("modelstat"))];
    if (off) {
      items.push({ label: t("aim_off"), icon: "shield-off", cls: "mp-bk off", keys: t("mp_bk_change"), tip: t("tip_mp_bk_mode"), run: openModes },
        line(t(on ? "aim_not_live" : "aim_off_conn"), "warn"));
    } else {
      items.push({ label: t("mp_bk_mode", modeFull(s.mode)), icon: MODE_ICON[s.mode], cls: `mp-bk m-${s.mode}`, keys: t("mp_bk_change"),
                   tip: t("tip_mp_bk_mode"), run: openModes }, line(t(`aim_${s.mode}_d`)));
    }
    if (s.paused) {
      const since = s.p && num(s.p.since) ? hhmm(s.p.since) : null;
      items.push({ label: since ? t(s.auto ? "mp_bk_auto" : "mp_bk_paused", since) : t(s.auto ? "paused_auto_st" : "paused_st"), icon: "pause",
                   cls: "mp-bk paused", keys: t("mp_bk_resume"), disabled: !on, tip: on ? stTip(s) : t("why_off"), run: openResume });
      if (s.auto) items.push(line(whyWords(s.p), "why"));
      if (s.n) items.push(line(tn("resume_held", s.n, heldWords(s))));
    } else if (!off) {
      items.push({ label: t("mp_bk_running"), icon: "pause", cls: "mp-bk", keys: t("pause_btn"), tip: t("tip_pause", s.hold), run: pause });
    }
    if (s.cards.length) {
      items.push({ label: tn("mp_bk_cards", s.cards.length), icon: "warn", cls: "mp-bk cards", keys: t("show"),
                   tip: tn("tip_bk_pending", s.cards.length, s.cards.slice(0, 2).map(doWords).join(t("ch_s_sep")) + (s.cards.length > 2 ? "…" : "")),
                   run: () => openCards(null) });
    }
    if (s.refused) {
      const since = isObj(b.refused) && num(b.refused.since) ? hhmm(b.refused.since) : null;
      items.push(line(since ? tn("mp_bk_refused", s.refused, since) : tn("aim_refused_n", s.refused)));
    }
    return items;
  }

  /** Review as the page knows it, for app-conn.js (why the AI's last call was refused; a call
   *  waiting on a request the badge counts): null without the brakes, else {mode, paused, cards:
   *  how many to decide}. */
  function brakeNow() {
    const b = view();
    return b ? { mode: b.mode, paused: !!b.paused, cards: toDecide(b).length } : null;
  }

  Object.assign(WBA, { brakeItems, brakeMenuAdd, brakeNow, brakeSwitches, renderBrake, renderCards });
})();
