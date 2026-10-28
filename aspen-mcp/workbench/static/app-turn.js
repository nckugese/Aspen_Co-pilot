/* The manual step (feature yourturn). A program's yourturn
 * statement (blocks.js wb_yourturn) stops the run until the user sets the input it names -- in
 * the inspector or in Aspen's own window -- and presses Done. While the server holds a run
 * waiting (tab.run.wait {sid, n, path, label, hint, before {value, unit}, t, tries, msg null |
 * unchanged | expect, now?, expect? {op, value}, has_answer, can_answer, loc, where, enterable};
 * run.status stays "running"), app-step.js takes it as a pause (pausedOf: why "turn") and:
 *
 *   - the run bar says "Waiting for input · <field>" and holds Stop and Done (F10 too); a press waits for
 *     the server's answer (or TURN_MS) before Done acts again;
 *   - the card beside the waiting step (app-step.js placeStepCard, its content here; never over
 *     the step's own rows, whose hint it does not repeat) says what to set: the field, where it
 *     sits in Aspen, a check not met ("Not met: …") or a value
 *     left as it was (Continue anyway?); after the misses the step allows, Show answer (the
 *     program writes it and goes on);
 *   - once a wait, on the tab shown: a folded program column opens, the field's stream or block
 *     is picked on the flowsheet (a ring) and the inspector goes to the field, whose row stays
 *     marked while the run waits; nothing is picked while the user is typing;
 *   - the inspector writes meanwhile, as while paused (app-step.js pausedOn);
 *   - while the run goes, the program's manual steps keep their answers hidden ("(hidden)":
 *     blocks.js WB.ytHide), each until Show answer is pressed for it; as ever once the run ends.
 *
 *   waitOf(tab)            the run's wait, where the server has the feature, else null
 *   renderTurn(pane)       the run bar's words and Done; the focus once a wait; the marked row
 *   turnCardHtml(tab, w)   the card's content (html); turnOff(tab): why its buttons wait ("" none)
 *   turnPress(kind, force) Done ("done"; force: the value as it is) or Show answer ("answer")
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { canon, esc, fmtVal, icon, isObj, progEmpty, setProg, shownTab, t, tabOf, toast, wb } = WBA;
  const { commitEdit, gotoChange, renderRunbar, rowTarget } = WBA.later;

  const TURN_MS = 4000;                                // a press not answered in this long: Done acts again
  const OPS = { ">": ">", ">=": "≥", "<": "<", "<=": "≤", "==": "=", "!=": "≠" };
  const PH = "\u0001";                                 // (a place for html in words escaped)

  /** The run's wait for the user (a running run's). */
  function waitOf(tab) {
    const r = tab && tab.run, w = r && r.status === "running" ? r.wait : null;
    return isObj(w) && typeof w.sid === "string" ? w : null;
  }
  const keyOf = (w) => canon([w.sid, w.t, w.tries, w.msg, w.now || null, !!w.can_answer]);
  /** Why Done and Show answer wait now ("" for acting): no connection, a press unanswered, a Stop. */
  function turnOff(tab) {
    const rec = tab && wb.recs.get(tab.id), w = waitOf(tab);
    if (!rec || !w) return "";
    if (!wb.connected) return t("why_off");
    if (rec.pending && rec.pending.kind === "stop") return t("st_stopping");
    return rec.ytSent && rec.ytSent.key === keyOf(w) && Date.now() - rec.ytSent.at < TURN_MS ? t("st_sending") : "";
  }

  /** The field in words: labels.js's short form. */
  const fieldName = (tab, w) => WBL.say(w.path, tab.session);
  const fieldHtml = (tab, w) => WBL.html(WBL.of(w.path, null, tab.session), "short");
  const valText = (x) => (isObj(x) ? `${fmtVal(x.value)}${x.unit && x.value != null ? ` ${x.unit}` : ""}` : "—");

  // ------------------------------------------------------------------ the card
  /** What the card beside the waiting step says (html): the field (not the hint: the step shows
   *  it), where in Aspen; a field not enabled now; a check not met, or a value unchanged
   *  (Continue as it is); Edit value (the field in the inspector) and, once the step allows it,
   *  Show answer. */
  function turnCardHtml(tab, w) {
    const off = turnOff(tab), dis = off ? " disabled" : "";
    const btn = (kind, cls, words, tip, ic) => `<button class="yt-btn ${cls}" data-yt="${kind}"${dis} data-tip="${esc(tip)}" title="${esc(off || tip)}">`
      + `${ic ? icon(ic) : ""}<span class="bt">${esc(words)}</span></button>`;
    let msg = "";
    if (w.msg === "expect" && isObj(w.expect)) {
      const need = t("yt_need", OPS[w.expect.op] || w.expect.op || "", fmtVal(w.expect.value), valText(w.now));
      msg = `<div class="yt-msg">${icon("warn")}<span>${esc(t("yt_retry", need))}</span></div>`;
    } else if (w.msg === "unchanged") {
      msg = `<div class="yt-msg ask"><span>${esc(t("yt_unchanged", valText(w.now || w.before)))}</span>`
        + `${btn("force", "", t("go_on"), t("tip_yt_force"))}</div>`;
    }
    const hit = rowTarget(tab, { path: w.path });    // (its object on the flowsheet: Edit value)
    const acts = (hit ? `<button class="sc-go" data-kind="${esc(hit.target.kind)}" data-name="${esc(hit.target.name)}" data-path="${esc(hit.path)}"`
      + ` title="${esc(t("tip_step_edit"))}">${icon("pen")}<span class="bt">${esc(t("step_edit"))}</span></button>` : "")
      + (w.can_answer ? btn("answer", "yt-ans", t("yt_answer"), t("tip_yt_answer_btn")) : "");
    // (no hint: the step shows it, and the card keeps clear of it; the run log has it whole)
    return `<div class="sc-h">${icon("pen")}<b>${esc(t("yt_bar", PH)).replace(PH, fieldHtml(tab, w))}</b></div>`
      + (w.where ? `<div class="sc-at">${esc(t("in_aspen", w.where))}</div>` : "")
      + (w.enterable === false ? `<div class="sc-x yt-off">${esc(t("yt_off"))}</div>` : "")
      + msg + (acts ? `<div class="sc-act">${acts}</div>` : "");
  }

  // ------------------------------------------------------------------ presses
  /** Done (force: the value as it is) or Show answer on the shown tab: an edit being typed in the
   *  inspector goes first (the server waits for it). False when the tab does not wait. */
  function turnPress(kind, force) {
    const tab = shownTab(), rec = tab && wb.recs.get(tab.id), w = waitOf(tab);
    if (!w || !rec) return false;
    if (!wb.connected) { toast(t("why_off")); return true; }
    if (turnOff(tab)) return true;
    if (wb.pane && wb.pane.tabId === tab.id) commitEdit(wb.pane);
    rec.ytSent = { key: keyOf(w), at: Date.now() };
    if (kind === "answer") (rec.ytShown || (rec.ytShown = new Set())).add(w.sid);   // (its answer shows now: answersSync)
    wb.post(Object.assign({ type: kind === "answer" ? "yourturn_answer" : "yourturn_done", tab: tab.id, sid: w.sid },
      kind !== "answer" && force ? { force: true } : {}));
    setTimeout(() => { if (wb.pane && wb.pane.tabId === tab.id) renderRunbar(); }, TURN_MS + 50);
    renderRunbar();
    return true;
  }

  // ------------------------------------------------------------------ the run bar
  /** Done, beside Stop: made once a pane, in the run bar after the stepping buttons. */
  function doneGroup(pane) {
    const bar = pane.q(".prog-bar");
    let g = bar.querySelector(".turnbtns");
    if (g) return g;
    g = document.createElement("span");
    g.className = "turnbtns hidden";
    g.setAttribute("role", "group");
    g.innerHTML = `<button class="primary" data-yt="done">${icon("check")}<span class="bt"></span></button>`;
    (bar.querySelector(".stepbtns") || bar.querySelector(".runstop")).after(g);
    g.addEventListener("click", (ev) => { const b = ev.target.closest("[data-yt]"); if (b && !b.disabled && wb.pane === pane) turnPress("done"); });
    return g;
  }
  /** The status capsule's words while the run waits: app-status.js drew the pause (statusOf: the
   *  pause is app-step.js pausedOf's); here its words become "Waiting for input · <field>", and the folded
   *  column's strip and the log tab say the same. Its signature is cleared, so the next drawing
   *  starts from statusOf again (the class stays: no animation). */
  function turnStat(pane, tab, w) {
    const el = pane.q(".prog-stat");
    if (!el || !el.classList.contains("paused")) return;   // (a Stop being sent, a lost connection: theirs)
    const long = t("yt_wait", fieldName(tab, w)), set = (e, s) => { if (e && e.textContent !== s) e.textContent = s; };
    set(el.querySelector(".st-long"), long);
    set(el.querySelector(".st-short"), t("yt_wait_s"));
    const tip = [long, t("tip_yt_wait"), t("tip_stat_go_log")].join("\n");
    if (el.title !== tip) el.title = tip;
    el.dataset.sig = "";
    const strip = pane.q(".prog-strip"), stip = `${t("prog_title")}\n${long}`;
    if (strip && strip.title !== stip) strip.title = stip;
    const log = pane.q('.panel nav [data-tab="log"]'), ltip = `${t("tip_tab_log")}\n${long}`;
    if (log && log.title !== ltip) log.title = ltip;
  }
  /** Once a wait, on the tab shown: the program column open, the field's object picked (a ring)
   *  and the inspector at the field -- not while the user is typing somewhere. */
  function turnFocus(pane, tab, rec, w) {
    const key = `${w.sid}|${w.t}`;
    if (rec.ytSeen === key) return;
    rec.ytSeen = key;
    if (pane.progShut && !progEmpty(rec)) setProg(pane, true);
    const el = document.activeElement;
    const typing = !!pane.editing || (el && el !== document.body && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)))
      || (window.Blockly && (Blockly.WidgetDiv.isVisible() || Blockly.DropDownDiv.isVisible()));
    const hit = rowTarget(tab, { path: w.path });
    if (!hit || typing) return;
    setTimeout(() => {
      const now = tabOf(tab.id), cur = now && waitOf(now);
      if (wb.pane === pane && pane.tabId === tab.id && cur && cur.sid === w.sid) gotoChange(pane, hit.target, hit.path);
    }, 0);
  }
  /** The inspector's row of the field the run waits for: marked (.yt-row) while it waits. Its
   *  rows are drawn anew often (values, names, history): marked again each time (an observer). */
  function turnMark(pane) {
    const box = pane.q(".insp .irows");
    if (!box) return;
    if (!pane.ytObs) {
      pane.ytObs = new MutationObserver(() => turnMark(pane));
      pane.ytObs.observe(box, { childList: true });
    }
    const tab = tabOf(pane.tabId), w = tab && waitOf(tab), want = w ? String(w.path).toLowerCase() : null;
    const i = want ? (pane.rows || []).findIndex((r) => String(r.path || "").toLowerCase() === want) : -1;
    const row = i >= 0 ? box.querySelector(`.irow[data-i="${i}"]`) : null;
    box.querySelectorAll(".irow.yt-row").forEach((r) => { if (r !== row) r.classList.remove("yt-row"); });
    if (row && !row.classList.contains("yt-row")) row.classList.add("yt-row");
  }
  /** The program's manual steps' answers: hidden while its run goes, but for a step whose
   *  Show answer was pressed in it (rec.ytShown: step ids); shown once it ends (edit mode as ever). */
  function answersSync(tab, rec) {
    const going = (tab.run || {}).status === "running";
    if (!going) rec.ytShown = null;
    if (rec.ws && window.WB && WB.ytHide) WB.ytHide(rec.ws, (b) => going && !(rec.ytShown && rec.ytShown.has(b.id)));
  }
  /** From app-step.js renderStepBar (the run bar drawn): Done beside Stop while the run waits,
   *  the capsule's words, the focus once a wait, the inspector's marked row, the answers hidden. */
  function renderTurn(pane) {
    const tab = pane && tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id);
    if (!tab || !rec) return;
    answersSync(tab, rec);
    const w = waitOf(tab), run = tab.run || {}, on = !!w && !isObj(run.paused);
    const g = on || pane.q(".prog-bar .turnbtns") ? doneGroup(pane) : null;
    if (g) {
      g.classList.toggle("hidden", !on);
      const b = g.querySelector("[data-yt=done]"), off = on ? turnOff(tab) : "";
      b.disabled = !!off;
      b.title = off || t("tip_yt_done");
      b.querySelector(".bt").textContent = t("yt_done");
    }
    turnMark(pane);
    if (!on) return;
    turnStat(pane, tab, w);
    const off = turnOff(tab);                          // (the card's buttons: as Done)
    pane.q(".step-card").querySelectorAll(".yt-btn").forEach((x) => { x.disabled = !!off; x.title = off || x.dataset.tip || ""; });
    turnFocus(pane, tab, rec, w);
  }

  Object.assign(WBA, { renderTurn, turnCardHtml, turnOff, turnPress, waitOf });
})();
