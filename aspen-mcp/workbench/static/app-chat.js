/* The AI chat (renderChat: requests, answers, notices, the line each AI edit of the program
 * leaves, what a request led to; unread; its buttons), the composer
 * under the dock (drafts, the chip, Send: sendNote), editing a request (editNote), and asking
 * the AI about a stream or block -- or a change, a change group, a field, a step (askAI).
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { act, atEnd, changed, changesCtx, copyText, esc, familyOf, feature, flashBlock, icon, keyOf, listFades, modal, prefGet, prefs,
    prefSet, propWhere, sessOf, setDock, setProg, settled, showStep, shownSel, showPanel, soon, t, tabOf, tn, toast, wb } = WBA;
  const { activate, escape, gotoChange, openEntry, pick, showIn, undoOpen } = WBA.later;

  // What a request can be about: a stream or block, a change record, a change group, an inspector
  // field, a program step -- each sent with the keys the server keeps of its kind.
  const TG_KEYS = { block: ["name"], stream: ["name"], change: ["id", "model", "label", "obj", "name", "path"],
    group: ["id", "model", "label"], field: ["path", "label", "obj", "name"], stmt: ["tab", "sid", "label"],
    run: ["id", "model", "label"],          // (a run the diagnosis card asks about)
    proposal: ["tab", "name"],              // (the note sending a proposal back; its tab and title)
    object: ["path", "name", "type"] };     // (a model object the inspector shows)
  const TG_ICON = { block: "block", stream: "stream", change: "pen", group: "values", field: "eye", stmt: "braces", run: "warn",
    proposal: "sparkle", object: "gear" };  // (the proposal's own mark, as on its tab)
  function targetLabel(tg) {
    if (!tg) return "";
    if (tg.kind === "stream") return t("stream_n", tg.name);
    if (tg.kind === "change") return t("tg_change", tg.label || tg.name || tg.id);
    if (tg.kind === "group") return t("tg_group", tg.label || tg.id);
    if (tg.kind === "field") return t("tg_field", tg.label || tg.name || "?");
    if (tg.kind === "stmt") return t("tg_stmt", tg.label || tg.sid);
    if (tg.kind === "run") return t("tg_run", tg.label || tg.id);
    if (tg.kind === "object") return tg.type && tg.type !== tg.name ? `${tg.name} · ${tg.type}` : String(tg.name || tg.path || "");
    if (tg.kind === "proposal") return t("tg_proposal", tg.name || (tabOf(tg.tab) || {}).title || (propWhere(null, tg.tab) || {}).title || "?");
    return t("block_n", tg.name);
  }
  /** A target as sent in a request: its kind's keys, strings only. */
  function sendable(tg) {
    const keys = tg && TG_KEYS[tg.kind];
    if (!keys) return null;
    const out = { kind: tg.kind };
    keys.forEach((k) => { if (tg[k] != null && String(tg[k]).trim()) out[k] = String(tg[k]); });
    return out;
  }
  const GOTO_TIP = { change: "tip_goto_field", field: "tip_goto_field", group: "tip_goto_group", stmt: "tip_goto_stmt", run: "tip_goto_run",
    proposal: "tip_goto_prop" };
  /** Where a proposal a request is about is now (app-core.js propWhere): "loaded", "hist" (kept in
   *  History), "gone" (its record deleted), or "" (no way to it). */
  const propAt = (tg) => (tg && tg.kind === "proposal" && tg.tab ? (propWhere(null, tg.tab) || {}).state || "" : "");
  /** Whether a request's target can be gone to from the chat (tab: the one shown). A proposal kept
   *  in History can: it opens from there first. */
  const goable = (tg, tab) => (tg.kind === "block" || tg.kind === "stream" ? !!tg.name
    : tg.kind === "change" || tg.kind === "field" ? (tg.obj === "block" || tg.obj === "stream") && !!tg.name
      : tg.kind === "group" ? !!tg.id && WBC.on() : tg.kind === "run" ? !!tg.id
        : tg.kind === "proposal" ? propAt(tg) === "loaded" || propAt(tg) === "hist"
          : tg.kind === "stmt" && !!tg.sid && (!tg.tab || tg.tab === tab.id));

  // ------------------------------------------------------------------ what a request led to
  // Once the AI's changes for a request are recorded, the server puts on the request the newest
  // change group it led to (group, group_model). Under the request (and its answer) the chat
  // counts what it led to -- the records of that group and of the groups whose header names it,
  // and of the programs those started, as journal.page(note=, note_group=) keeps them -- with WBC.tally, the Changes
  // tab's own count, and See changes goes to the group there. Read again when the session's
  // journal moves while the request is open; a request done, once.
  const FX_MAX = 2000;                 // records one count reads at most (past it: "at least")
  const FX_SLACK = 5;                  // s before the request was sent that it reads from
  const fx = new Map();                // note id -> {sig, busy, done, v, tally, more}
  let fxV = 0;
  const fxOn = () => WBC.on() && ((wb.state && wb.state.catalog) || {}).journal_on !== false;
  /** The model the tab's Changes shows (a group is gone to only there). */
  const fxModel = (tab) => { const s = sessOf(tab); return (s.model && s.model.id) || (s.journal && s.journal.model) || (s.flowsheet || {}).model || null; };
  function fxOf(n, sess) {
    if (!n || !n.group || !n.group_model) return null;
    const j = sess.journal && typeof sess.journal === "object" ? sess.journal : null;
    const sig = `${n.group}|${n.group_model}|${n.status === "done" ? "done" : j ? `${j.n}|${j.last_t}` : ""}`;
    let e = fx.get(n.id);
    if (!e) fx.set(n.id, (e = { sig: null, busy: false, done: false, v: 0, key: "" }));
    if (e.sig !== sig && !e.busy) fxLoad(e, n, sig);
    return e;
  }
  function fxLoad(e, n, sig) {
    const a = window.pywebview && window.pywebview.api;
    if (!a || typeof a.journal !== "function") return;
    e.busy = true;
    const req = { model: n.group_model, note: n.id, note_group: n.group, limit: FX_MAX };   // (the server's group too, even where no header names the note)
    if (typeof n.t === "number" && n.t > 0) req.after = n.t - FX_SLACK;   // (nothing before the request is its)
    let p;
    try { p = Promise.resolve(a.journal(req)); } catch (err) { p = Promise.reject(err); }
    p.then((got) => {
      if (!got || typeof got !== "object" || !Array.isArray(got.records)) throw new Error("no answer");
      const T = WBC.tally(noteRecs(got, n), []), more = !!got.more, key = JSON.stringify([T, more]);
      if (key !== e.key) Object.assign(e, { key, tally: T, more, v: ++fxV });
      e.done = true;
    }).catch(() => {}).then(() => {
      e.busy = false;
      e.sig = sig;                                  // (a failed read: again once the journal moves)
      const pane = wb.pane, tab = pane && tabOf(pane.tabId);
      if (tab && e.done) renderChat(pane, tab, sessOf(tab));
    });
  }
  /** The records a request led to in a journal page: the server's group, the groups whose header
   *  names the request and the programs those started (ai_group). (A window that does not pass
   *  `note` on answers every record since the request: the same records are kept.) */
  function noteRecs(got, n) {
    const heads = got.groups && typeof got.groups === "object" ? got.groups : {}, ids = new Set([n.group]);
    Object.entries(heads).forEach(([g, h]) => { if (h && String(h.note || "") === n.id) ids.add(g); });
    for (let more = true; more;) {
      more = false;
      Object.entries(heads).forEach(([g, h]) => { if (h && !ids.has(g) && ids.has(h.ai_group)) { ids.add(g); more = true; } });
    }
    return got.records.filter((r) => r && r.kind === "change" && ids.has(r.group));
  }
  /** "Led to 7 changes · 1 run": values, blocks and streams added or removed and connections as
   *  changes; runs; loops and optimizations; what did not apply. */
  function fxWords(e) {
    const T = e.tally || {}, parts = [], sum = (box) => Object.values(box || {}).reduce((s, x) => s + (Number(x && x.n) || 0), 0);
    const changes = (T.values || 0) + sum(T.added) + sum(T.removed) + (T.connects || 0);
    if (changes) parts.push(tn("nfx_changes", changes));
    if (T.runs && T.runs.n) parts.push(tn("nfx_runs", T.runs.n));
    Object.entries(T.studies || {}).forEach(([d, k]) => parts.push(tn(`nfx_${["sweep", "seek", "optimize"].includes(d) ? d : "loop"}`, k)));
    if ((T.failed || 0) + (T.refused || 0)) parts.push(tn("nfx_bad", (T.failed || 0) + (T.refused || 0)));
    return parts.length ? t(e.more ? "note_effect_more" : "note_effect", parts.join(t("nfx_sep"))) : t("note_none");
  }
  /** The line under a request: what it led to, and See changes where the tab's Changes has it. */
  function fxLine(n, e, model) {
    const go = n.group_model === model ? `<button class="na" data-c="note_goto" title="${esc(t("tip_note_goto"))}">${esc(t("note_goto"))}</button>` : "";
    return `<div class="chat notice nfx" data-id="x${esc(n.id)}" data-fx="${esc(n.id)}">${icon("pen")}`
      + `<span class="nt" title="${esc(t("tip_note_effect"))}">${esc(fxWords(e))}</span>${go}</div>`;
  }
  /** A change group in the Changes tab: the tab shown, the group's card opened, brought into view
   *  and flashed (changes.js WBC.showGroup). */
  function gotoGroup(pane, gid) {
    const tab = tabOf(pane.tabId);
    if (!tab || !gid || !window.WBC || !WBC.on()) return;
    if (prefs().dockMode === "min") setDock(pane, "split");
    showPanel(pane, "changes");
    WBC.showGroup(pane.q(".tab-changes"), changesCtx(pane, tab), gid);
  }
  /** A program step a request is about: shown in the blocks (the column opened) and flashed. */
  function goStep(pane, tg) {
    const rec = wb.recs.get(pane.tabId), blk = rec && rec.ws && rec.ws.getBlockById(tg.sid);
    if (!blk) { toast(t("tg_stmt_gone"), 4000); return; }
    setProg(pane, true);
    Blockly.common.setSelected(blk);
    showStep(rec, blk.id);
    flashBlock(blk);
  }
  /** A proposal a request is about (the note sending it back): its tab shown, the program
   *  column open on the proposal's card; one kept in History opened from there first (
   *  app-subtabs.js openEntry: shown once the server has loaded it). */
  function goProposal(pane, tg) {
    if (!tabOf(tg.tab)) {
      if (propAt(tg) === "hist") { openEntry({ tab: tg.tab }); setProg(pane, true); }
      return;
    }
    if (pane.tabId !== tg.tab) { showIn(pane, tg.tab); activate(tg.tab); }
    setProg(pane, true);
  }
  // ------------------------------------------------------------------ the AI chat
  // A conversation: the user's requests on the right (the session's, so every tab on it
  // shows them; one sent from another tab says so), the AI's answers on the left, and the
  // window's own notices (a value set by hand, an error) as quiet lines between, and a line for
  // each change the AI made to the block program (from "ai_edit": what it added, changed and
  // removed, with Show in program and, while that version is the newest, Undo). Only this
  // list is redrawn from state; the composer under the dock is not (see below).

  /** The server's lines that are news, not errors: their kind and its mark. */
  const NEWS = { proposal: "sparkle", to_blocks: "blocks" };
  const PROP_BAD = new Set(["refused", "failed", "partial"]);   // (a proposal's line that is an error all the same)

  /** Each item's id, so only what is new rises in; a request sent here shows at once, until
   *  the server's state has it (rec.outbox). */
  function renderChat(pane, tab, sess) {
    // (an event -- the server telling the AI a proposal ended -- is not the user's: the
    // proposal's own line says it)
    // (an event the AI answered -- a question with choices after a proposal ran -- shows: its
    // answer and buttons, without the event's own words)
    const rec = wb.recs.get(tab.id), notes = (sess.notes || []).filter((n) => !n.event || n.reply);
    // one chat for a model: the lines of its model tab and every sub-tab of it (its programs and
    // proposals, app-core.js familyOf) show together, a proposal's with its title. An AI edit's line
    // stays with its own tab (its Undo is that tab's program).
    const isProp = (x) => x && x.kind === "proposal";
    const family = familyOf(tab);
    const msgs = family.flatMap((x) => (x.messages || []).filter((m) => x.id === tab.id || m.from !== "ai_edit")
      .map((m) => (x.id === tab.id || !isProp(x) ? m : { ...m, prop: m.prop || (x.proposal || {}).title || x.title })))
      .sort((a, b) => (a.t || 0) - (b.t || 0)).slice(-30);
    // sent from here and now in state: that one takes its place. A note stands for one sent
    // request only (rec.claimed), so the same words sent twice wait for their second note.
    rec.outbox = rec.outbox.filter((o) => {
      const hit = notes.find((n) => !rec.claimed.has(n.id) && String(n.text).trim() === o.text
        && keyOf(n.target) === keyOf(o.target) && (n.t || 0) * 1000 >= o.at - 10000 && (!n.tab || n.tab === tab.id));
      if (!hit) return true;
      rec.claimed.add(hit.id);
      if (rec.seen) rec.seen.add(`n${hit.id}`);
      return false;
    });
    // an answer the user has not seen: the chat's segment carries a dot until it is shown
    const aiKeys = msgs.filter((m) => m.from === "llm" || m.from === "ai_edit" || !m.from).map((m) => `m${m.t}`)
      .concat(notes.filter((n) => n.reply).map((n) => `r${n.id}:${n.reply.length}`));
    if (rec.aiSeen && !chatShown(pane) && aiKeys.some((k) => !rec.aiSeen.has(k))) rec.unread = true;
    rec.aiSeen = new Set(aiKeys);
    renderUnread(pane, rec);
    const titles = notes.some((n) => n.tab && n.tab !== tab.id) ? wb.state.tabs.map((x) => [x.id, x.title]) : 0;
    // where the proposals the requests are about (or were sent from) are now: loaded, in History, deleted
    const pats = notes.map((n) => [propAt(n.target), n.tab && n.tab !== tab.id && !tabOf(n.tab) ? (propWhere(null, n.tab) || {}).title || "" : ""]);
    // an AI edit's Undo: only while the version it made is the newest (and there is one before it)
    const undoable = (m) => wb.connected && tab.program_rev === m.rev && !!(tab.history || {}).undo;
    const edits = msgs.filter((m) => m.from === "ai_edit");
    // an Aspen path in the AI's answers and the window's notices is shown by its name (labels.js;
    // the path in its tooltip), never as a backslash path
    const words = (s) => WBL.rich(s, tab.session);
    // what each request led to, counted from the change record: read now where it moved
    const fxs = fxOn() ? notes.map((n) => fxOf(n, sess)) : [];
    // a hand edit's line carries its record: "Undo" after it, where the server takes it back
    const undoOn = feature("undo") && wb.connected;
    // (the connection too: the options under an answer are offline-greyed until it is back)
    if (!changed(pane, "panel", [tab.id, I18N.lang, notes, msgs.length, msgs.length && msgs[msgs.length - 1].t, undoOn, !!wb.connected,
      rec.outbox.map((o) => o.k), rec.outbox.length && wb.connected, [...wb.expanded], titles,
      edits.length && [wb.connected, edits.map(undoable)], WBL.ver, fxs.map((e) => (e && e.done ? e.v : 0)), fxs.length && fxModel(tab),
      rec.choV || 0, pats])) {
      if (WBA.waitUpdate) WBA.waitUpdate(pane, tab, sess);   // (the AI still working: app-wait.js, on the turn's news)
      return;
    }
    const items = [];
    const ai = (id, text, reply) => `<div class="chat ai" data-id="${id}"><span class="avatar">AI</span>`
      + `<div class="bubble">${words(text)}</div><button class="rep" data-c="reply" data-reply="${esc(reply)}" title="${esc(t("tip_c_reply"))}">`
      + `${icon("reply")}<span class="bt">${esc(t("c_reply"))}</span></button></div>`;
    const mine = (id, cls, target, extra, text, note) => {
      const tip = !target ? "" : propAt(target) === "hist" ? "tip_goto_prop_hist" : GOTO_TIP[target.kind] || "tip_goto";
      const tg = target ? (note && goable(target, tab) ? `<button class="tg" data-c="goto" data-kind="${esc(target.kind)}" data-name="${esc(target.name || "")}" title="${esc(t(tip))}">${esc(targetLabel(target))}</button>`
        : `<span>${esc(targetLabel(target))}</span>`) : "";
      const open = note && wb.expanded.has(note);
      return `<div class="chat you ${cls}${open ? " full long" : ""}" data-id="${id}"${note ? ` data-note="${esc(note)}"` : ""}>`
        + `<div class="bubble"><div class="meta">${tg}${extra}`
        + (note ? `<button class="edit" data-c="edit" title="${esc(t("c_edit"))}">${icon("pen")}</button>` : "")
        + `</div><div class="txt">${esc(text)}</div>`
        + (note ? `<button class="more" data-c="more">${esc(t(open ? "c_less" : "c_more"))}</button>` : "") + `</div></div>`;
    };
    const aiEdit = (m) => {
      const why = undoable(m) ? "" : !wb.connected ? t("why_off") : t("why_aiedit_old");
      const link = (c, label, tip, off) => `<button class="na" data-c="${c}"${off ? " disabled" : ""} title="${esc(tip)}">${esc(t(label))}</button>`;
      return `<div class="chat notice ai_edit" data-id="m${m.t}">${icon("sparkle")}<span class="nt">${esc(m.text)}</span>`
        + ((m.added || []).length + (m.changed || []).length ? link("aiedit_show", "aiedit_show", t("tip_aiedit_show")) : "")
        + link("aiedit_undo", "aiedit_undo", why || t("tip_aiedit_undo"), !!why) + `</div>`;
    };
    // the server's own lines are "system": an error or a refusal (red, ⚠), except where it says
    // what kind of news a line is -- where a proposal stands, a program made from the change log:
    // a quiet line with that kind's mark (a proposal refused or failing is still an error)
    const news = (m) => (m.from === "system" && NEWS[m.kind] && !(m.kind === "proposal" && PROP_BAD.has(m.what)) ? NEWS[m.kind] : "");
    // a line of a proposal (living in this tab, or closed): its title before it
    const pfx = (m) => (m.prop ? `<span class="from prop">${icon("sparkle")}${esc(m.prop)}</span>` : "");
    msgs.forEach((m) => items.push({ t: m.t || 0, html: m.from === "llm" || !m.from ? ai(`m${m.t}`, (m.prop ? `✦ ${m.prop}
` : "") + m.text, "")
      : m.from === "ai_edit" ? aiEdit(m)
      : news(m) ? `<div class="chat notice news" data-id="m${m.t}">${icon(news(m))}${pfx(m)}${words(m.text)}</div>`
      : `<div class="chat notice ${esc(m.from)}" data-id="m${m.t}">${icon(m.from === "system" ? "warn" : "pen")}${pfx(m)}${words(m.text)}`
        + (undoOn && m.from === "user" && m.record ? `<button class="na" data-c="undo_rec" data-rec="${esc(m.record)}" title="${esc(t("tip_c_undo"))}">${esc(t("undo"))}</button>` : "")
        + `</div>` }));
    notes.forEach((n, i) => {
      if (n.event) {                            // the AI's question on an event: its answer and choices only
        items.push({ t: n.t || 0, html: ai(`r${n.id}`, n.reply, n.id) + choicesHtml(rec, n) });
        return;
      }
      const st = n.status === "done" ? "done" : n.reply ? "replied" : "open";
      // (sent from a proposal now kept in History: its title from there)
      const other = n.tab && n.tab !== tab.id ? tabOf(n.tab) : null, was = other ? other.title : pats[i][1];
      const from = !n.tab || n.tab === tab.id ? "" : `<span class="from">${esc(was ? t("c_from", was) : t("c_from_gone"))}</span>`;
      items.push({ t: n.t || 0, html: mine(`n${n.id}`, st, n.target, from + `<span class="state"><i></i>${esc(t("note_" + st))}</span>`, n.text, n.id)
        + (n.reply ? ai(`r${n.id}`, n.reply, n.id) + choicesHtml(rec, n) : "") + (fxs[i] && fxs[i].done ? fxLine(n, fxs[i], fxModel(tab)) : "") });
    });
    rec.outbox.forEach((o) => items.push({ t: o.at / 1000, html: mine(o.k, "sending", o.target,
      `<span class="state"><i></i>${esc(t(wb.connected ? "c_sending" : "c_queued"))}</span>`, o.text, null) }));
    items.sort((a, b) => a.t - b.t);
    const box = pane.q(".chat-list"), first = pane.chatTab !== tab.id;
    const stick = first || rec.stick || atEnd(box), top = box.scrollTop;
    box.innerHTML = items.length ? items.map((x) => x.html).join("") : `<div class="hint">${t("msgs_hint")}</div>`;
    if (WBA.waitRender) WBA.waitRender(pane, tab, sess);   // the waiting line back under its request (app-wait.js)
    const ids = [...box.querySelectorAll(":scope > [data-id]")].map((el) => el.dataset.id);
    if (rec.seen && !first) box.querySelectorAll(":scope > [data-id]").forEach((el) => { if (!rec.seen.has(el.dataset.id)) el.classList.add("new"); });
    rec.seen = new Set(ids);
    const ais = box.querySelectorAll(":scope > .chat.ai");
    if (ais.length) ais[ais.length - 1].classList.add("last");
    pane.chatTab = tab.id;
    rec.stick = false;
    clampCheck(pane);
    box.scrollTop = stick ? box.scrollHeight : top;
    listFades(box);
  }

  // ------------------------------------------------------------------ choices under an answer
  // An answer may offer options (note.choices [{label, detail?}], note.multi): buttons under
  // it, so the user answers by a click. One: the click sends it. Several (multi): clicks tick
  // them (rec.choosing, per request) and Send sends the ticked. A pick goes to the server as
  // note_choose {id, picks: [index]}, which closes the request (note.picked) and sends the AI
  // the labels as a request of its own; until the state says so the pick shows as sent
  // (rec.chose), so it is not sent twice. Picked or offline: the options are greyed, the
  // picked ones marked. A request the AI closed (done) after asking keeps its options until
  // the user picks or the AI answers again: closing an event it asked on is the AI's routine,
  // not a withdrawal. Typing an answer in the box instead works as ever.

  /** The question an answer asks, as the window keeps its ticks and pick (a new answer on the
   *  same request asks afresh). */
  const choKey = (n) => `${n.id}|${String(n.reply || "").length}|${(n.choices || []).map((c) => c.label).join("\u0001")}`;
  /** The options under the answer to request n ("" when it offers none). */
  function choicesHtml(rec, n) {
    const cs = Array.isArray(n.choices) ? n.choices : [];
    if (!cs.length) return "";
    const k = choKey(n), picked = Array.isArray(n.picked) ? n.picked : null, sent = rec.chose && rec.chose.get(k);
    const on = new Set(picked ? cs.map((c, i) => (picked.includes(c.label) ? i : -1)).filter((i) => i >= 0)
      : sent || (rec.choosing && rec.choosing.get(k)) || []);
    const closed = !!picked || !!sent, off = closed || !wb.connected;
    const why = closed ? "" : !wb.connected ? t("why_off") : t(n.multi ? "tip_cho_multi" : "tip_cho");
    const btn = (c, i) => `<button class="cho${on.has(i) ? " on" : ""}" data-c="choose" data-i="${i}"${off ? " disabled" : ""}`
      + ` aria-pressed="${on.has(i)}"${why ? ` title="${esc(why)}"` : ""}>`
      + (n.multi ? `<i class="box"></i>` : "") + `<span class="cl">${esc(c.label)}</span>`
      + (c.detail ? `<span class="cd">${esc(c.detail)}</span>` : "") + `</button>`;
    const foot = closed ? `<span class="chn">${esc(t(picked ? "cho_picked" : "c_sending"))}</span>`
      : (n.multi ? `<button class="cho-send" data-c="choose_send"${off || !on.size ? " disabled" : ""}>${esc(t("cho_send"))}</button>` : "")
        + `<span class="chn">${esc(t("cho_hint"))}</span>`;
    return `<div class="chat choices${closed ? " closed" : ""}" data-id="c${esc(n.id)}" data-cho="${esc(n.id)}">`
      + `<div class="cho-list">${cs.map(btn).join("")}</div><div class="cho-foot">${foot}</div></div>`;
  }
  /** A click on an option (choose) or on Send under several (choose_send). */
  function choose(pane, tab, rec, b) {
    const n = noteById(b.closest("[data-cho]").dataset.cho), k = n && choKey(n);
    if (!n || !Array.isArray(n.choices) || n.picked || (rec.chose && rec.chose.has(k))) return;
    rec.choosing = rec.choosing || new Map();
    let picks;
    if (b.dataset.c === "choose") {
      const i = Number(b.dataset.i);
      if (!n.multi) picks = [i];
      else {
        const set = new Set(rec.choosing.get(k) || []);
        if (set.has(i)) set.delete(i); else set.add(i);
        rec.choosing.set(k, set);
      }
    } else picks = [...(rec.choosing.get(k) || [])].sort((x, y) => x - y);
    if (picks && picks.length) {
      wb.post({ type: "note_choose", tab: tab.id, id: n.id, picks });
      (rec.chose = rec.chose || new Map()).set(k, new Set(picks));
      rec.choosing.delete(k);
      rec.stick = true;
    }
    rec.choV = (rec.choV || 0) + 1;
    renderChat(pane, tab, sessOf(tab));
  }

  /** A request longer than five lines gets "Show more" (measured: only a shown list can be). */
  function clampCheck(pane) {
    const box = pane.q(".chat-list");
    if (!box.clientHeight) return;
    box.querySelectorAll(":scope > .chat.you:not(.full) .txt").forEach((el) => {
      el.closest(".chat").classList.toggle("long", el.scrollHeight > el.clientHeight + 1);
    });
  }

  const chatShown = (pane) => pane.q(".panel nav [data-tab=msgs]").classList.contains("on") && prefs().dockMode !== "min";
  function renderUnread(pane, rec) {
    if (!pane || pane.tabId !== rec.id) return;
    const b = pane.q(".panel nav [data-tab=msgs]"), tip = [t("tip_tab_msgs"), rec.unread && t("tip_unread")].filter(Boolean).join("\n");
    b.querySelector(".ai-dot").classList.toggle("on", rec.unread);
    if (b.title !== tip) b.title = tip;
  }
  /** The chat shows: its answers count as read. */
  function markRead(pane) {
    const rec = pane && wb.recs.get(pane.tabId);
    if (!rec || !rec.unread || !chatShown(pane)) return;
    rec.unread = false;
    renderUnread(pane, rec);
  }

  function noteById(id) {
    let n = null;
    Object.values((wb.state && wb.state.sessions) || {}).forEach((s) => (s.notes || []).forEach((x) => { if (x.id === id) n = x; }));
    return n;
  }

  /** The chat's buttons: a target (select it on the flowsheet), Show more / less, edit a
   *  request, Reply to an answer, an AI edit's Show in program and Undo. */
  function chatAct(pane, b) {
    const tab = tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id);
    if (!b || !rec || b.disabled) return;
    const a = b.dataset.c;
    if (a === "choose" || a === "choose_send") { choose(pane, tab, rec, b); return; }
    if (a === "aiedit_show" || a === "aiedit_undo") {
      const id = b.closest("[data-id]").dataset.id, m = (tab.messages || []).find((x) => x.from === "ai_edit" && `m${x.t}` === id);
      if (m && a === "aiedit_undo") act(pane, { dataset: { a: "undo" } });   // the program capsule's Undo
      else if (m) showAiEdit(rec, m);
      return;
    }
    if (a === "undo_rec") {                       // a hand edit's "Undo": its record undone, previewed first
      const m = (tab.messages || []).find((x) => x.record === b.dataset.rec);
      undoOpen(tab, { ids: b.dataset.rec.split(","), anchor: b, label: m ? String(m.text).replace(/\s+/g, " ").trim().slice(0, 120) : "" });
      return;
    }
    if (a === "note_goto") {                      // what a request led to: its group in Changes
      const n = noteById(b.closest("[data-fx]").dataset.fx);
      if (n && n.group) gotoGroup(pane, n.group);
      return;
    }
    if (a === "goto") {
      const el = b.closest("[data-note]"), n = el && noteById(el.dataset.note);
      goAny(pane, n && n.target ? n.target : { kind: b.dataset.kind, name: b.dataset.name });
    } else if (a === "edit") editNote(b.closest("[data-note]").dataset.note);
    else if (a === "more") {
      const id = b.closest("[data-note]").dataset.note;
      if (wb.expanded.has(id)) wb.expanded.delete(id); else wb.expanded.add(id);
      renderChat(pane, tab, sessOf(tab));
    } else if (a === "reply") {
      // continue that conversation: the chip holds the request's target (none: the whole tab)
      const n = b.dataset.reply ? noteById(b.dataset.reply) : null;
      focusComposer(pane, { pin: { target: n ? n.target || null : null, reply: true } });
    }
  }

  /** The steps an AI edit added or changed: each flashes, the first is picked and centred.
   *  One since removed (or held behind the Load pill) is not there to show: said when none is. */
  function showAiEdit(rec, m) {
    const blks = (m.added || []).concat(m.changed || []).map((id) => rec.ws.getBlockById(id)).filter(Boolean);
    if (!blks.length) { toast(t("aiedit_gone")); return; }
    Blockly.common.setSelected(blks[0]);
    showStep(rec, blks[0].id);
    blks.forEach(flashBlock);
  }

  /** A request's target named in the chat: a stream or block (goTarget); a change or a field:
   *  its block or stream, the inspector at the field; a group: its card in Changes; a step: in
   *  the blocks; a proposal: its tab. */
  function goAny(pane, tg) {
    if (!tg) return;
    if (tg.kind === "change" || tg.kind === "field") gotoChange(pane, { kind: tg.obj, name: tg.name }, tg.path || null);
    else if (tg.kind === "group") gotoGroup(pane, tg.id);
    else if (tg.kind === "stmt") goStep(pane, tg);
    else if (tg.kind === "run") { const tab = tabOf(pane.tabId); if (tab && window.WBD) WBD.open(tab, { run: tg.id }); }
    else if (tg.kind === "proposal") goProposal(pane, tg);
    else goTarget(pane, tg);
  }
  /** A target named in the chat: select it, as a click on the flowsheet would, bring it into
   *  view beside the inspector (same scale, the least pan) and ring it. */
  function goTarget(pane, target) {
    if (!target.kind || !target.name) return;
    if (prefs().dockMode === "max") setDock(pane, "split");      // the flowsheet shows again, to show it
    pick(pane, target, { ring: true });
  }

  /** A request's bubble on the flowsheet: find it in the chat, with its answer, and flash it. */
  function gotoNote(pane, id) {
    if (!pane.tabId) return;
    if (prefs().dockMode === "min") setDock(pane, "split");
    showPanel(pane, "msgs");
    const box = pane.q(".chat-list"), el = box.querySelector(`:scope > [data-note="${CSS.escape(id)}"]`);
    if (!el) return;
    const next = el.nextElementSibling, end = next && next.dataset.id === `r${id}` ? next : el;
    const top = el.offsetTop - 8, h = end.offsetTop + end.offsetHeight + 8 - top;
    box.scrollTop = h <= box.clientHeight ? top - (box.clientHeight - h) / 2 : top;   // centred when it fits
    listFades(box);
    el.classList.remove("ping");
    void el.offsetWidth;
    el.classList.add("ping");
    setTimeout(() => el.classList.remove("ping"), 1000);
  }

  // ------------------------------------------------------------------ the composer
  // Under the dock's three panels, so the user can ask or answer while the log or results
  // show. The node is built once (index.html) and never redrawn: applyState cannot eat a
  // draft, a caret or an IME composition. Each tab keeps its own draft (in memory, and as
  // a pref: see prefGet) and its chip, the target the request is about.

  const draftKey = (id) => `wb.draft.${id}`;
  const loadDraft = (id) => prefGet(draftKey(id)) || "";
  const saveDraft = (rec) => prefSet(draftKey(rec.id), rec.draft || null);

  /** The request the composer may continue: the session's newest, when the AI has answered
   *  it, it is not done, and it names a stream or block (one sent from another tab is that
   *  tab's thread). */
  function latestThread(tab) {
    let n = null;
    (sessOf(tab).notes || []).forEach((x) => { if (!n || (x.t || 0) >= (n.t || 0)) n = x; });
    return n && n.reply && n.status !== "done" && n.target && (!n.tab || n.tab === tab.id) ? n : null;
  }
  function threadKey(n) { return n ? `${n.id}|${n.reply.length}` : ""; }

  /** What the composer asks about: {target (null: the whole tab), reply, pinned}. A pin
   *  (the inspector's Ask AI, the chip's ×, Reply, a heat plan) holds until the request is
   *  sent. Otherwise the chip follows the newer of the user's last pick on the flowsheet
   *  and the AI's latest answer to a request on a stream or block (shown with the reply
   *  icon, to answer it; only an answer that came while the window was open, since one
   *  that was there already is an old conversation), then the inspector's target, the
   *  tab's selection, the whole tab.
   *  While a draft is being written only the user's own picks move it (rec.frozen). */
  function chipOf(tab, rec) {
    if (rec.pin) return Object.assign({ pinned: true }, rec.pin);
    const typing = !!rec.draft.trim();
    if (typing && rec.frozen) return rec.frozen;
    const n = latestThread(tab), key = threadKey(n);
    if (rec.thread.key !== key) {                       // an answer that came while typing does not take the chip
      rec.thread = { key, at: key && !typing && !rec.outbox.length ? Date.now() : -1 };
    }
    let c;                                              // (a request on its way is the newest: no thread)
    if (n && !rec.outbox.length && rec.thread.at > rec.pickAt) c = { target: n.target, reply: true };
    else if (rec.insp) c = { target: rec.insp.target };
    else if (shownSel(tab, rec)) c = { target: tab.selection };
    else c = { target: null };
    if (typing) rec.frozen = c;
    return c;
  }

  /** The composer for the shown tab: its draft (only when the tab changed: never over what
   *  is being typed), the chip, Send, and the line under it. */
  /** Whether a request reaches the AI by itself: the server says its client listens (channels
   *  on), or it pushes requests (state.channel) and the session's latest pushed one reached the
   *  AI at once (_announce marks a note delivered / pushed / undelivered; a hook's hand-over is
   *  handed; the AI seen at work on it soon after: app-wait.js's waitHeard). Said delivered is a
   *  claim (state.listening is the user's ASPEN_MCP_CHANNELS): as the waiting line, not heard
   *  once the AI has left the latest request untouched for waitCfg.grace s (waitUnheard). No
   *  request yet: assumed heard. */
  function heard(tab) {
    const s = wb.state || {}, on = s.listening === true;
    if (!on && s.channel !== true) return false;
    const n0 = (x) => Number(x) || 0;
    let last = null;
    (((s.sessions || {})[tab && tab.session] || {}).notes || []).forEach((n) => {
      const at = n && Math.max(n0(n.delivered), n0(n.undelivered), n0(n.pushed), on ? n0(n.t) : 0);
      if (at && (!last || at >= last.at)) last = { at, n };
    });
    if (!last) return true;
    const n = last.n;
    if (WBA.later.waitHeard(n.id)) return true;
    if (!on && n0(n.undelivered) >= Math.max(n0(n.delivered), n0(n.pushed))) return false;
    if (n0(n.pushed) && !n0(n.delivered)) return Date.now() / 1000 - n0(n.pushed) < WBA.waitCfg.pickup;
    if (n.handed || n0(n.pushed)) return false;          // (a hook, or the user, had to hand it over)
    return Date.now() / 1000 - n0(n.t) > WBA.waitCfg.maxAge || !WBA.later.waitUnheard(n);
  }
  function renderComposer(pane) {
    const tab = tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id);
    if (!rec) return;
    const q = pane.q, ta = q(".cta");
    if (pane.cTab !== tab.id) {
      pane.cTab = tab.id;
      ta.value = rec.draft;
      grow(pane);
    }
    const c = chipOf(tab, rec), chip = q(".cchip");
    const label = c.target ? targetLabel(c.target) : t("c_whole");
    const name = c.reply ? "reply" : !c.target ? "tab" : TG_ICON[c.target.kind] || "block";
    const tip = c.reply ? t("tip_c_reply_chip", label) : c.pinned ? t("tip_c_pinned") : t("tip_c_auto");
    const sig = JSON.stringify([I18N.lang, label, name, !!c.pinned, !c.target && !c.reply]);
    if (chip.dataset.sig !== sig) {
      chip.dataset.sig = sig;
      chip.querySelector(":scope > .ic use").setAttribute("href", `#i-${name}`);
      chip.querySelector(".cl").textContent = label;
      chip.className = `cchip${c.pinned ? " pinned" : ""}${!c.target && !c.reply ? " whole" : ""}`;
      chip.title = `${label}\n${tip}`;
    }
    q(".csend").disabled = !ta.value.trim();
    // the line under the box, only when a request would not reach the AI at once from a server
    // that does not hear it (Claude Code channels off, or an older server that does not say):
    // then what to say in Claude. The AI hearing at once is the default and says nothing (the
    // keys are in Send's tooltip); so is no connection: the header's indicator says it, and a
    // request sent meanwhile says it itself (c_queued).
    const live = wb.connected && heard(tab), quiet = live || !wb.connected;
    const hint = q(".chint"), text = quiet ? "" : t("c_say", WBA.later.aiClient(), t("say_look"));
    hint.classList.toggle("live", live);
    const ht = hint.querySelector(".ch-text");
    const may = text && (wb.state || {}).listening === true ? `\n${t("tip_c_unheard")}` : "";
    if (ht.textContent !== text || ht.dataset.may !== may) {
      ht.textContent = text;
      ht.dataset.may = may;
      ht.title = text && `${text}${may}\n${WBA.later.channelTip()}`;
    }
    hint.querySelector(".ch-copy").classList.toggle("hidden", quiet);
    if (hint.classList.contains("hidden") !== quiet) {
      const list = pane.q(".panel .tab.on"), end = !!list && atEnd(list);   // (before the line moves the list's foot)
      hint.classList.toggle("hidden", quiet);
      grow(pane);                                  // the composer's height changed: the box measured again
      if (end && !atEnd(list)) list.scrollTop = list.scrollHeight;   // a chat read to its end stays there
    }
  }

  /** The text box grows with its text from one line to five (three in a short dock), then
   *  scrolls; a chat read to its end stays there as the box grows. */
  function grow(pane) {
    const ta = pane.q(".cta"), list = pane.q(".panel .tab.on"), stick = list && atEnd(list);
    const before = ta.offsetHeight;
    ta.style.height = "";
    pane.taText = ta.scrollHeight;
    pane.taW = ta.clientWidth;                     // 0 while the dock is collapsed: measured again when it opens
    const box = pane.q(".composer");
    if (box.offsetHeight) pane.taChrome = pane.q(".dnav").offsetHeight + box.offsetHeight - ta.offsetHeight;
    const h = fitText(pane, pane.q(".panel").clientHeight);
    if (stick) list.scrollTop = list.scrollHeight;
    if (before && h !== before) soon("regrow", () => settled(pane));   // the results chart takes the new height
  }
  /** Size the text box to its text (pane.taText) in a dock dockH tall: five lines at most,
   *  three in a dock under 260 px (the list keeps some room), fewer when it is shorter still,
   *  so Send and the line under it always stay in the dock with a line of the list above
   *  them. Writes only (layout() calls it while dragging). */
  function fitText(pane, dockH) {
    const ta = pane.q(".cta");
    if (!pane.taText) return ta.offsetHeight;
    // whole lines (20 px each, 6 px of padding), so no line shows cut in half
    const cap = dockH < 260 ? 3 : 5;
    const lines = Math.max(1, Math.min(cap, Math.floor((dockH - (pane.taChrome || 0) - 28 - 6) / 20)));
    const max = lines === 5 ? 108 : 6 + 20 * lines, h = Math.min(pane.taText, max);
    ta.style.height = `${h}px`;
    ta.style.overflowY = pane.taText > max ? "auto" : "hidden";
    return h;
  }

  /** The composer, idle: not focused and nothing typed. Only then may the dock move by itself. */
  function composerIdle(pane) {
    const ta = pane.q(".cta");
    return document.activeElement !== ta && !ta.value.trim();
  }

  /** Put the caret in the composer: the dock back from its collapsed row (on the chat), with
   *  o.pin as the chip and o.text added to the draft, after what is there. */
  function focusComposer(pane, o) {
    if (!pane || !pane.tabId) return;
    const rec = wb.recs.get(pane.tabId), ta = pane.q(".cta"), opt = o || {};
    if (prefs().dockMode === "min") { setDock(pane, "split"); showPanel(pane, "msgs"); }
    if (opt.pin !== undefined) rec.pin = opt.pin;
    let at = null;
    if (opt.text) {
      const had = ta.value.replace(/\s+$/, "");
      ta.value = had ? `${had}\n\n${opt.text}` : opt.text;
      at = had ? had.length + 2 : 0;               // the caret where the new text begins
      rec.draft = ta.value;
      saveDraft(rec);
      grow(pane);
    }
    renderComposer(pane);
    ta.focus({ preventScroll: true });
    if (at === null) at = ta.value.length;
    ta.setSelectionRange(at, at);
    if (opt.text) ta.scrollTop = 0;
  }

  /** Send the draft as a request on the chip's target (none: the whole tab). The chip lets
   *  go of its pin, the draft clears, and the chat shows the request at once. */
  function sendNote(pane) {
    const tab = tabOf(pane.tabId), rec = tab && wb.recs.get(tab.id), ta = pane.q(".cta");
    const text = ta.value.trim();
    if (!rec || !text) return;
    const c = chipOf(tab, rec), target = c.target ? sendable(c.target) : null;
    wb.post({ type: "note_add", tab: tab.id, target, text });
    rec.outbox.push({ k: `o${++wb.outN}`, text, target, at: Date.now() });
    rec.draft = "";
    rec.pin = rec.frozen = null;
    saveDraft(rec);
    ta.value = "";
    grow(pane);
    if (prefs().dockMode === "min") setDock(pane, "split");
    showPanel(pane, "msgs");
    rec.stick = true;
    renderChat(pane, tab, sessOf(tab));
    renderComposer(pane);
  }

  function wireComposer(pane) {
    const ta = pane.q(".cta");
    ta.addEventListener("input", () => {
      const rec = wb.recs.get(pane.tabId);
      if (!rec) return;
      const was = !!rec.draft.trim();
      rec.draft = ta.value;
      if (!ta.value.trim()) rec.frozen = null;
      saveDraft(rec);
      grow(pane);
      if (was !== !!ta.value.trim()) renderComposer(pane);   // the chip holds still while typing; Send wakes
    });
    ta.addEventListener("keydown", (ev) => {
      if (ev.isComposing || ev.keyCode === 229) return;              // an IME's keys: Enter picks a character
      // Escape restores a maximized dock, then closes the inspector, and only then leaves the box
      if (ev.key === "Escape") { ev.preventDefault(); if (!escape()) ta.blur(); return; }
      if (ev.key !== "Enter" || ev.shiftKey || ev.altKey) return;   // Shift+Enter: a new line
      ev.preventDefault();
      sendNote(pane);
    });
    pane.q(".composer").addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-c]"), rec = wb.recs.get(pane.tabId);
      if (!b) { if (ev.target.closest(".cbox") && !ev.target.closest(".cta")) ta.focus(); return; }
      if (!rec || b.disabled) return;
      if (b.dataset.c === "send") sendNote(pane);
      else if (b.dataset.c === "clear") { rec.pin = { target: null }; renderComposer(pane); ta.focus(); }
      else if (b.dataset.c === "copy") copyText(t("say_look"));
    });
  }

  // ------------------------------------------------------------------ notes, dialogs
  /** Ask the AI about a stream or block -- or, where the server takes them, a change
   *  record, a change group, an inspector field or a program step: the composer, its chip held
   *  on that target (its × lets go: the whole tab). The request shows in the chat, and over its
   *  block or stream on the flowsheet where it has one. */
  function askAI(tab, target) {
    if (!target || !TG_KEYS[target.kind]) return;
    focusComposer(wb.pane, { pin: { target: sendable(target) } });
  }
  /** The blocks' "Ask AI about this step" (blocks.js): the step, by its place in the program
   *  ("step 3 · Sweep ESTCOL › Reflux ratio"), in its tab. */
  WB.onAsk = (blk) => {
    const rec = [...wb.recs.values()].find((r) => r.ws === blk.workspace), at = WB.stepOf(blk);
    if (!rec || !at || !wb.pane || wb.pane.tabId !== rec.id) return;
    const kind = t(`stp_${at.kind}`), what = at.path ? `${kind} ${WBL.say(at.path)}` : kind;
    askAI(tabOf(rec.id), { kind: "stmt", sid: blk.id, tab: rec.id, label: t("tg_step_n", at.n, what.startsWith("stp_") ? at.kind : what) });
  };
  /** Edit or delete one of the user's requests (its pencil in the chat). */
  function editNote(id) {
    const n = noteById(id);
    if (!n) return;
    const live = wb.connected && heard(tabOf(wb.pane && wb.pane.tabId));
    modal(n.target ? `${t("c_edit_title")} · ${targetLabel(n.target)}` : t("c_edit_title"), n.text, "", (text) => {
      if (text.trim() && text.trim() !== n.text) wb.post({ type: "note_edit", id, text: text.trim() });
    }, () => wb.post({ type: "note_delete", id }), false,
    { help: n.reply ? t("ask_reply", n.reply) : t(live ? "ask_help_live" : "ask_help"), ok: t("save") });
  }

  Object.assign(WBA, { askAI, chatAct, clampCheck, composerIdle, fitText, focusComposer, gotoNote,
    grow, latestThread, loadDraft, markRead, renderChat, renderComposer, saveDraft, threadKey,
    wireComposer });
})();
