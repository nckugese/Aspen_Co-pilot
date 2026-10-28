/* The Changes tab: who changed what in the model -- the AI, you, a block program, an
 * optimization -- as the server measured it, newest first, one card per change group.
 *
 * The window reads the model's change journal itself (window.py, Api.journal: a page of
 * records, each field named with its "loc"), so the tab scrolls and opens while Aspen holds
 * the server. It asks only when there is something new: when the tab shows the first time,
 * when the session's journal summary in state.json (sessions[s].journal: n, last_t) moved,
 * and for an earlier page on request. One request at a time per model; what came meanwhile
 * is asked for once it answers.
 *
 * A card is a change group (the AI's request, your hand edits, one program run): who (a
 * badge), its title (the request, the AI's first reason, the program tab), when, and one line
 * that counts what it did ("3 values, 1 block added, 1 run: converged, 2 warnings"). Opened, a
 * card lists its records oldest first: "ESTCOL › Reflux ratio 1.5 → 2", the AI's
 * stated reason under the call it gave it for (its own words, beside what was measured), a
 * run's outcome and Aspen's lines. The newest card opens by itself.
 *
 * Who: small chips over the cards show only the AI's, your, a program's, an optimization's
 * or outside changes (the journal is asked for that actor's records: Api.journal actors), each
 * with its count from the summary (sessions[s].journal.by); a chip only for who changed the
 * model. Each workbench tab keeps its own choice. A short record (under SHORT records) folds
 * them into one "Filter" chip.
 *
 * Last seen: per model, the window's prefs keep where you last looked (wb.seen.<model>: the
 * newest record's {t, id} and how many changes others had made then). The tab opened, a line
 * "last seen here" sits over the first card you had seen -- while the away line shows, over
 * the first card before it counts from --, and the cards above it open (at most OPEN_MAX).
 * Once the tab has shown SEEN_MS with the window in front, or the list was scrolled by hand,
 * or when it stops showing, the mark moves to the newest record. The dock's tab counts the
 * changes by the AI, programs, optimizations and outside since then (WBC.unread; never your
 * own). The mark moves only that count: the flowsheet's dots and the away line stay.
 *
 * A page of records draws only the cards that are new or changed (the others keep their
 * elements); a card's rows come ROWS at a time, then ROWS_STEP more a click; cards off screen
 * skip their layout (content-visibility). WBC.perf keeps the last draws' and opens' times.
 *
 * The flowsheet: a row that names a block or stream (or a block in a run's line) is a
 * link: a click picks it on the flowsheet and opens the inspector at that field (ctx.goto). A
 * block or stream you pick while the tab shows keeps only its changes (a chip "Only ESTCOL ✕";
 * letting go of it, or the ✕, shows all again; nothing changes while the tab is hidden).
 * WBC.marks gives the flowsheet a dot per block or stream the AI, a program, an optimization
 * or someone outside changed since the dots' own mark (wb.dots.<model>: the last-seen mark as
 * it was when the dots first showed, moved only by "mark all seen"), coloured by who changed it
 * last; one you looked at since drops it -- picked on the flowsheet, a row of it clicked, a card
 * holding it opened by hand (wb.seenobj.<model>: object -> the newest change seen, MARKS_KEEP at
 * most). While the tab shows only one object, looking marks that object seen too.
 *
 * The inspector: each row names its field's last change under its value, "AI · 14:02 ·
 * was 1.5" (who, when, the value before; a loop's or an optimization's writes: "Optimizer ·
 * 14:24 · 9 evaluations"), and a card of its last PROV_PER changes with their reasons where
 * the pointer rests on it. One read per object inspected (Api.journal per_path: the journal's
 * latest_by_path), PROV_WAIT after the pick (a quick run of picks reads only the last one),
 * kept until the journal's last_t moves; an older window.py that answers with a page instead
 * is asked no more.
 *
 *   WBC.on()                 the server offers the timeline and the window can read it
 *   WBC.render(box, ctx)     draw ctx's model into box (.tab-changes), asking what is new;
 *                            ctx {model, session, tab, types, summary, journalOn, shown, show,
 *                            gotoNote(id), goto(target, path), onMarks(), prefGet(k),
 *                            prefSet(k, v), connected, newTab(title, program), toast,
 *                            menu(at, items, ev), ask(target)}; cheap when nothing changed
 *   WBC.unread(ctx)          the unread count for the dock's tab
 *   WBC.pick(box, ctx, tg)   the user picked tg (null: let go) on the flowsheet: the shown
 *                            tab keeps only its changes (or all again)
 *   WBC.only(box, ctx, tg)   keep only tg's changes (a dot clicked), shown or not
 *   WBC.marks(ctx)           {"block:ESTCOL": {actor, n, t, tip}} for the flowsheet, or null
 *   WBC.seeObj(ctx, tg)      the user looked at tg: its dot goes (true: it had one)
 *   WBC.forObject(ctx, tg)   tg's rows' history {paths: {lower-cased path: [records, newest
 *                            first]}, ver}, or null; ctx.onProv() once a read answers
 *   WBC.provLine(r, unit)    a row's last change in words; WBC.provWas(r, unit): its value before
 *   WBC.provCard(recs, unit) the card of a row's last changes (html)
 *
 * What the record covers: an ⓘ beside the dock's buttons, while the tab shows, opens a
 * small note over the page (catalog.coverage, the server's classification of its tools): what
 * is recorded, edits made in Aspen's own window, what can be taken back later and how, and the
 * tools behind each. It blocks nothing: a press anywhere else closes it and still does what it
 * does; Escape closes it too.
 *
 *   WBC.covOn()              the server says what its record covers
 *   WBC.coverage(btn)        open the note under (or over) btn; open already: close it
 *   WBC.coverageClose(back)  close it (back: the focus returns to the ⓘ); whether it was open
 *   WBC.coverageSync(on)     the ⓘ shows (on) or not: closed when not; words redrawn after a
 *                            language switch
 *
 * What a run changed: the server measures its runs: a run's record carries seq, inputs (changed since the run before, net) and delta (results
 * read just before and after it). Its line says "Run #7: converged with 2 warnings", and one
 * more under it opens onto them (the newest run open by itself): the inputs and who changed
 * them, then the results that moved most, ▲ ▼ for which way; a first run, a failed one, a
 * Reinitialize before it each say why there is nothing (or something else) to compare.
 * Inputs changed together cannot be told apart: the card says so, and "Try one at a time"
 * opens a program tab that sweeps each numeric input alone between its value before and now
 * (ctx.newTab(title, program), where the page offers it; ctx.connected; nothing runs until
 * Run program).
 *
 * While you were away, the report: where the window makes change reports (window.py's
 * Api.report; there is no catalog flag), coming back to the window after a while, or opening
 * it on a model changed since you last looked, puts one row over the cards: "12 new changes since
 * 14:02" -- the AI's, programs', the optimizer's and Aspen's own window's changes, never your own
 * edits in the workbench; who did what ("the AI changed 12 values in 3 blocks, added B4, ...")
 * and the results before -> now are its tooltip, a click opens the cards it counts -- with Show on
 * the flowsheet, Mark all read and × (put away for those records: wb.away.dismiss.<model>).
 * Every card's count line and that line
 * count with one function, WBC.tally (tools/report.py's tally answers the same fixture). The
 * tab's download button and each card's ⋯ open a small box to export a report of today, since
 * you last looked, everything or that group, as Markdown or one HTML page, which the window's
 * own save dialog writes. A run that ended in errors, or did not run, says so on its line and
 * never "not applied".
 *
 * Edits made in Aspen's own window: where the server compares that window with what it
 * knows (catalog.features external), what the compare found is recorded as actor external: a
 * row says so and when it was found ("Changed in the Aspen window (found at 14:05): B17 ›
 * Temperature 595 → 606.9 C"), a block or stream added or removed there, a run started or a
 * save made there; the tooltip says between which times the edit was made (the compare only
 * sees it, never when it happened) and what asked for the compare. Their card is titled
 * "Changes in the Aspen window"; the External chip keeps only them.
 *
 *   WBC.tally(recs, skip, opt) the counts {values, objs, added, removed, connects, runs {n,
 *                            last}, studies, saves, failed, refused, external, by: {actor: …}}
 *   WBC.repOn()              the window makes reports (and the tab reads the journal)
 *   WBC.back(ctx, left)      you are back (left: when you left, s) or the window opened (null):
 *                            a promise of the away line's state {n, tally, since, …} or null;
 *                            the caller draws the tab again and toasts where it is not shown
 *   WBC.awayOf(model)        the away line's state, or null
 *   WBC.report(btn, ctx, g)  the report box under btn (g: {id, title}, a card's group); again: closed
 *   WBC.reportClose(back)    close it; WBC.reportSync(on): the button shows or not
 *
 * Ask AI about anything: where the page can ask (ctx.ask(target)), a row shows Ask AI at
 * its end under the pointer (target {kind "change", id, model, label: its line in words, obj,
 * name, path}) and a card's ⋯ offers Ask AI about this group ({kind "group", id, model, label:
 * its title}). A request's See changes comes back here:
 *
 *   WBC.showGroup(box, ctx, gid)  the group's card opened, in view and flashed once (a filter
 *                            hiding it let go; earlier pages read to find it)
 *
 * A field's help card: where the page makes them (ctx.help(anchor, record), help.js),
 * a record that changed a field shows “?” beside Ask AI under the pointer; the card says what the
 * field is (Aspen's own description, units, options, rules, docs).
 *
 * Step through a group: where the window has walk.js (WBW) and a flowsheet, a card of
 * two or more changes that went in, opened, shows a button Step through over its rows (words, not an
 * icon under the pointer): walk.js shows them one at a time on the flowsheet, oldest first, in
 * the rows' own words (WBC.walkStep), and the row it is on is marked here (.wk-on).
 * WBC.walkable(r): whether the walk stops at a record.
 *
 * A connect record that took its stream off the port (the stream in before, not after: disconnect_stream,
 * a program's, an undo's) reads "Took OIL3 off REACTOR F(IN)" (tools/journal.py is_disconnect).
 *
 * The timeline as blocks: where the server makes a program of records (feature
 * to_blocks) and the page can ask (ctx.toBlocks({group | ids, label})), a card's ⋯ offers Convert to
 * program (new tab) for its group, and select mode (the dock's ☑, WBC.select) puts a tick box before each
 * change a card lists, with a bar at the tab's foot: "3 selected [Convert] [Cancel]". Nothing here
 * writes: the page posts the request, then shows what came of it and the new tab (app-replay.js).
 *
 *   WBC.tbOn(ctx)            the timeline can be turned into blocks
 *   WBC.select(box, ctx, on) select mode on or off (what was picked let go); WBC.selOn(tab)
 *
 * Undo, redo and restore points: where the server takes changes back (catalog.features
 * undo, and the page can ask: ctx.undo(o)), a row that can be taken back shows ↶ Undo at its end
 * under the pointer (↷ Redo on an undo's own row); a row that cannot says why there instead
 * (results stay; only a restore point; its value before was not measured). A row an undo in the
 * loaded records took back carries “undone 14:12” (“undone approx.” where it came back approximately). A card's ⋯
 * offers Undo this group / Redo this group / Restore to before this group first. ctx.undo({ids | group, anchor, label, redo})
 * opens the preview (app-undo.js); nothing is written from here. A restore-point record is a
 * milestone line (◆ automatic, ★ named, ◇ none made and why); with ctx.restore, Restore to here at its end under the
 * pointer, or why not (cleared by the rotation). ctx.cps: the model's restore points on disk
 * (app-undo.js's Api.checkpoints cache: a Map id -> point, with ver), or null.
 *
 * The brakes: a call they kept out says what the AI wanted and why (Observe, a pause,
 * a confirmation card and what became of it since); a change let through says how (you
 * confirmed #12, let through for the request, done while the window was closed); one applied
 * after its call had ended carries "AI proposed, you did it #12" (a click: the AI's request).
 * Their own records -- the mode, a pause, a resume, an automatic pause -- and a proposal declined
 * later are milestone lines of their own, at their time.
 *
 *   WBC.field(path, loc, type)   a field's name in words (html), as the rows name it
 *   WBC.valHtml(d, unit)         a measured {value, unit} (html)
 *   WBC.cpWords(reason)          what a restore point was kept before, in words
 *   WBC.est(s)                   a duration to expect, in words (about 3 s, about 2 min)
 *   WBC.apWords(codes)           why an undo came back only approximately, in words
 *   WBC.headTitle(h, groups)     a change group's title from its header, as its card says it
 */
(function () {
  "use strict";
  const PAGE = 100;                   // records a page
  const ROWS = 20;                    // rows an opened card draws before "show N more"
  const ROWS_STEP = 100;              // ... and how many more each click
  const SUB = 5;                      // fields a loop's or optimization's line lists
  const OPEN_MAX = 3;                 // cards opened by themselves: the newest, and unseen ones
  const SHORT = 30;                   // a record this short folds its filter chips
  const SEEN_MS = 5000;               // shown this long, in front (or scrolled by hand): seen -- the unread count only
  const MARKS = 300;                  // records a flowsheet-dot request reads at most
  const MARKS_KEEP = 200;             // objects wb.seenobj.<model> remembers
  const PROV_PER = 5;                 // changes the inspector's card lists per field
  const PROV_WAIT = 150;              // ms after a pick before its object's history is read
  const PROV_KEEP = 40;               // objects whose history is kept
  const JUMP_PAGES = 5;               // earlier pages read to find a group gone to (WBC.showGroup)
  const FLASH_MS = 1600;              // a card gone to flashes this long (style.css .ch-card.flash)
  const ACT = { ai: "sparkle", user: "pen", program: "gear", optimizer: "target", external: "aspen" };
  const WHO = ["ai", "user", "program", "optimizer", "external"];
  const OTHERS = ["ai", "program", "optimizer", "external"];   // what the unread count counts
  const BAD = new Set(["failed", "refused", "error"]);

  const WBC = (window.WBC = {});
  const store = new Map();            // model id + actor filter -> its timeline (see model())
  const tabs = new Map();             // workbench tab id -> {actors, bar}: its filter
  WBC.perf = { draws: [], opens: [] };
  const perf = (list, v) => { list.push(v); if (list.length > 200) list.shift(); };
  const { apart, base, drop, esc, feature, hhmm, icon, isObj, pad, popover, setHtml, t, th, tn, when, who, zh } = WBA;
  const api = () => { const a = window.pywebview && window.pywebview.api; return a && typeof a.journal === "function" ? a : null; };
  WBC.on = () => !!api();

  // ------------------------------------------------------------------ seen, unread
  const seenKey = (id) => `wb.seen.${id}`;
  /** Where you last looked at a model's changes: {t, id, others} (id "": every record at t),
   *  or null (never). */
  function seenOf(ctx, id) {
    const s = typeof ctx.prefGet === "function" ? ctx.prefGet(seenKey(id)) : null;
    if (!s) return null;
    try {
      const o = JSON.parse(s);
      return o && typeof o === "object" && isFinite(Number(o.t)) ? { t: Number(o.t), id: String(o.id || ""), others: Number(o.others) || 0 } : null;
    } catch (e) { return null; }
  }
  /** Changes the journal counts by the AI, programs, optimizations and outside; null: it
   *  does not count them. */
  function othersOf(s) {
    const by = s && typeof s === "object" && s.by && typeof s.by === "object" ? s.by : null;
    return by ? OTHERS.reduce((n, k) => n + (Number(by[k]) || 0), 0) : null;
  }
  /** Whether a record is at or before a seen mark. */
  const seenBy = (m) => (r) => { const t = Number(r.t) || 0; return t < m.t || (t === m.t && (!m.id || String(r.id || "") <= m.id)); };
  WBC.unread = (ctx) => {
    if (!ctx || !ctx.model || ctx.journalOn === false || !WBC.on()) return 0;
    const n = othersOf(ctx.summary);
    if (n == null) return 0;
    const m = seenOf(ctx, ctx.model);
    return Math.max(0, n - (m ? m.others : 0));
  };
  const focused = () => document.visibilityState !== "hidden" && (typeof document.hasFocus !== "function" || document.hasFocus());

  /** The tab looked at a model: v {model, divider (the mark when the tab opened), ctx (the
   *  newest shown), timer, marked (the summary last marked)}. It starts when the tab shows a
   *  model, marks the model seen after SEEN_MS in front (again whenever the journal moves
   *  while it shows), and marks it once more when it ends (another panel, tab or model). */
  function look(box, ctx) {
    const w = box._wbc, v = w.view, on = !!(ctx.on && ctx.shown && ctx.model);
    if (v && (!on || v.model !== ctx.model)) {
      clearTimeout(v.timer);
      w.view = null;
      mark(v);                                     // (the away line stays: × or the next return puts it away)
    }
    if (!on) return;
    if (!w.view) w.view = { model: ctx.model, divider: seenOf(ctx, ctx.model), ctx, timer: 0, marked: null, wait: false };
    const cur = w.view;
    cur.ctx = ctx;
    if (!cur.timer && cur.marked !== sigOf(ctx.summary)) cur.timer = setTimeout(() => due(box, cur), SEEN_MS);
  }
  function due(box, v) {
    v.timer = 0;
    if (box._wbc.view !== v) return;
    if (focused()) { mark(v); return; }
    if (v.wait) return;                          // the window behind: once it comes to the front
    v.wait = true;
    window.addEventListener("focus", () => {
      v.wait = false;
      if (box._wbc.view === v && !v.timer) v.timer = setTimeout(() => due(box, v), SEEN_MS);
    }, { once: true });
  }
  /** Move the model's mark to its newest record (the summary's, or a newer one loaded) and
   *  the count of others' changes now; never back. While the tab shows one object only, that
   *  object's changes are what was seen (the newest of them loaded): the model's mark stays. */
  function mark(v) {
    const ctx = v.ctx, s = ctx.summary;
    v.marked = sigOf(s);
    if (typeof ctx.prefSet !== "function" || !s || typeof s !== "object") return;
    const only = okey(tabState(ctx.tab).obj);
    if (only) {
      let tt = 0;
      store.forEach((M) => { const r = M.id === v.model && M.obj === only && M.recs[0]; if (r && Number(r.t) > tt) tt = Number(r.t); });
      if (seeKey(ctx, v.model, only, tt)) notify(ctx);
      return;
    }
    let m = { t: Number(s.last_t) || 0, id: "" };
    store.forEach((M) => { const r = M.id === v.model && M.recs[0]; if (r && Number(r.t) > m.t) m = { t: Number(r.t), id: String(r.id || "") }; });
    const old = seenOf(ctx, v.model);
    if (old && (old.t > m.t || (old.t === m.t && m.id && (!old.id || old.id > m.id)))) m = { t: old.t, id: old.id };
    if (!m.t) return;
    const val = JSON.stringify({ t: m.t, id: m.id, others: othersOf(s) || 0 });
    if (ctx.prefGet(seenKey(v.model)) !== val) {
      dotsBase(ctx, v.model, true);              // (the dots keep counting from before this look)
      ctx.prefSet(seenKey(v.model), val);
      notify(ctx);
    }
  }
  /** The flowsheet's dots may have moved: its owner draws them again. */
  const notify = (ctx) => { if (ctx && typeof ctx.onMarks === "function") ctx.onMarks(); };

  // ------------------------------------------------------------------ the flowsheet's dots
  /** "block:ESTCOL" / "stream:FEED" of a target ({kind, name}); "" for none or another kind. */
  const okey = (o) => (o && (o.kind === "block" || o.kind === "stream") && o.name ? `${o.kind}:${String(o.name).toUpperCase()}` : "");
  const PATH_OBJ = /^\\Data\\(Blocks|Streams)\\([^\\#]+)/i;
  const objOfPath = (p) => { const m = PATH_OBJ.exec(String(p || "")); return m ? `${/^b/i.test(m[1]) ? "block" : "stream"}:${m[2].toUpperCase()}` : ""; };
  /** The blocks and streams a record changed: a value of one, one added, a connection (its
   *  block and stream), the fields a loop or an optimization left changed. What failed, was
   *  refused or left the value as it was, a run, a save: none. */
  function objsOf(r) {
    const out = new Set(), tg = r.target || {}, op = r.op;
    if (r.kind !== "change") return out;
    if (op === "summary" || op === "restore") {
      const ws = r.writes && typeof r.writes === "object" && !Array.isArray(r.writes) ? r.writes : {};
      Object.entries(ws).forEach(([p, w]) => { const k = w && w.status === "changed" && objOfPath(p.split("#")[0]); if (k) out.add(k); });
      return out;
    }
    if (r.status !== "changed") return out;
    const add = (kind, name) => { const k = okey({ kind, name }); if (k) out.add(k); };
    if (op === "value" || op === "attr") { if (tg.block) add("block", tg.block); else if (tg.stream) add("stream", tg.stream); else { const k = objOfPath(tg.path); if (k) out.add(k); } }
    else if (op === "add") add(tg.kind, tg.name);
    else if (op === "connect") {
      add("block", tg.block);
      [tg.stream].concat(Array.isArray(r.after) ? r.after : []).forEach((x) => add("stream", x));
    }
    return out;
  }
  const seenObjKey = (id) => `wb.seenobj.${id}`;
  /** Objects looked at since their changes: {"block:ESTCOL": the newest change's time seen}. */
  function seenObjs(ctx, id) {
    const s = typeof ctx.prefGet === "function" ? ctx.prefGet(seenObjKey(id)) : null;
    try { const o = s ? JSON.parse(s) : null; return o && typeof o === "object" && !Array.isArray(o) ? o : {}; } catch (e) { return {}; }
  }
  /** Keep that the object's changes up to t were seen (never back; MARKS_KEEP objects at
   *  most, the longest seen going first). Returns whether anything was written. */
  function seeKey(ctx, id, key, t) {
    if (!key || !(t > 0) || typeof ctx.prefSet !== "function") return false;
    const o = seenObjs(ctx, id);
    if ((Number(o[key]) || 0) >= t) return false;
    o[key] = t;
    const keys = Object.keys(o);
    if (keys.length > MARKS_KEEP) keys.sort((a, b) => o[a] - o[b]).slice(0, keys.length - MARKS_KEEP).forEach((k) => delete o[k]);
    ctx.prefSet(seenObjKey(id), JSON.stringify(o));
    return true;
  }
  const dotsKey = (id) => `wb.dots.${id}`;
  /** The dots' own mark {t, id, others}: the last-seen mark as it was when the model's dots
   *  first showed, or before a look first moved it (keep: written then, t 0 where there was
   *  none), so a look at the list leaves them; moved only by "mark all as seen". null: never
   *  looked (every change counts). */
  function dotsBase(ctx, id, keep) {
    const s = typeof ctx.prefGet === "function" ? ctx.prefGet(dotsKey(id)) : null;
    try {
      const o = s ? JSON.parse(s) : null;
      if (o && typeof o === "object" && isFinite(Number(o.t))) return { t: Number(o.t), id: String(o.id || ""), others: Number(o.others) || 0 };
    } catch (e) { /* (made again from the last-seen mark) */ }
    const m = seenOf(ctx, id);
    if ((m || keep) && typeof ctx.prefSet === "function") ctx.prefSet(dotsKey(id), JSON.stringify(m || { t: 0, id: "", others: 0 }));
    return m;
  }
  const dots = new Map();             // model id -> {sig, want, busy, recs}: the unseen changes by others
  /** The others' changes to the model's blocks and streams not seen yet, for the flowsheet:
   *  {"block:ESTCOL": {actor (the latest), n, t (the latest), tip}}; {} for none, null where
   *  there is no timeline. Newer than the dots' mark (read again when the journal summary or
   *  the mark moves, MARKS records at most) and than when you last looked at that object. */
  WBC.marks = function (ctx) {
    if (!ctx || !ctx.model || ctx.journalOn === false || !WBC.on()) return null;
    const s = ctx.summary, others = othersOf(s);
    if (others == null) return null;
    const m0 = dotsBase(ctx, ctx.model), m = m0 && m0.t ? m0 : null;
    if (others - (m ? m.others : 0) <= 0) return {};     // nothing by others since the mark
    let D = dots.get(ctx.model);
    if (!D) dots.set(ctx.model, (D = { sig: null, want: null, busy: false, recs: [] }));
    D.want = `${sigOf(s)}|${m ? `${m.t}:${m.id}` : ""}`;
    if (D.sig !== D.want && !D.busy) loadMarks(D, ctx, m);
    const so = seenObjs(ctx, ctx.model), fresh = m ? (r) => !seenBy(m)(r) : () => true, out = {};
    D.recs.forEach((r) => {                      // (newest first)
      if (!fresh(r)) return;
      const tt = Number(r.t) || 0, a = ACT[r.actor] ? r.actor : "external";
      objsOf(r).forEach((k) => {
        if (tt <= (Number(so[k]) || 0)) return;
        const o = out[k] || (out[k] = { actor: a, n: 0, t: tt, by: {} });
        o.n++;
        o.by[a] = (o.by[a] || 0) + 1;
      });
    });
    Object.values(out).forEach((o) => { o.tip = dotTip(o); });
    return out;
  };
  function loadMarks(D, ctx, m) {
    const a = api(), want = D.want, req = { model: ctx.model, limit: MARKS, actors: OTHERS.slice() };
    if (!a) return;
    if (m) req.after = m.id ? [m.t, m.id] : m.t;
    D.busy = true;
    let p;
    try { p = Promise.resolve(a.journal(req)); } catch (e) { p = Promise.reject(e); }
    p.then((got) => {
      D.recs = got && Array.isArray(got.records) ? got.records.filter((r) => r && r.kind === "change") : [];
    }).catch(() => { D.recs = []; }).then(() => {
      D.busy = false;
      D.sig = want;
      notify(ctx);                               // (drawn again; asked again if it moved meanwhile)
    });
  }
  /** A dot's tooltip: who changed it, when last, how many times; you have not seen it. */
  function dotTip(o) {
    const who = Object.keys(o.by);
    if (who.length > 1) {
      const parts = who.map((a) => t("bd_part", t(`ch_who_${a}`), o.by[a])).join(t("ch_s_sep"));
      return t("bd_tip_mix", o.n, parts, hhmm(o.t));
    }
    return t(`bd_tip_${o.actor === "user" ? "external" : o.actor}`, hhmm(o.t), o.n);
  }
  /** The user looked at tg (picked it): its dot goes. Returns whether it had one (the caller
   *  draws the flowsheet again, at once: the pick's own feedback). */
  WBC.seeObj = function (ctx, tg) {
    const k = okey(tg), D = ctx && ctx.model ? dots.get(ctx.model) : null;
    if (!k || !D || !D.recs.length) return false;
    let tt = 0;
    D.recs.forEach((r) => { if (Number(r.t) > tt && objsOf(r).has(k)) tt = Number(r.t); });
    return seeKey(ctx, ctx.model, k, tt);
  };
  /** A card opened by hand: the blocks and streams its records changed are seen up to its
   *  newest change of each (a newer change elsewhere keeps its dot); the dots drawn again. */
  function seeCard(ctx, c) {
    const D = ctx && ctx.model ? dots.get(ctx.model) : null;
    if (!D || !D.recs.length || !c) return;
    const upto = new Map();
    c.recs.forEach((r) => objsOf(r).forEach((k) => upto.set(k, Math.max(upto.get(k) || 0, Number(r.t) || 0))));
    let any = false;
    upto.forEach((tt, k) => { if (seeKey(ctx, ctx.model, k, tt)) any = true; });
    if (any) notify(ctx);
  }

  // ------------------------------------------------------------------ the inspector's rows
  const provs = new Map();            // model id + object -> {sig, paths, busy, ver}: its rows' history
  let provWant = null, provTimer = 0, provOld = false;
  WBC.forObject = function (ctx, tg) {
    const k = okey(tg);
    if (provOld || !ctx || !ctx.model || !k || ctx.journalOn === false || !WBC.on()) return null;
    const key = `${ctx.model}\n${k}`, sig = String((ctx.summary && ctx.summary.last_t) || "");
    let P = provs.get(key);
    if (P) provs.delete(key);                    // (the newest looked at last: the oldest go first)
    else P = { model: ctx.model, obj: k, sig: null, paths: {}, busy: false, ver: 0 };
    provs.set(key, P);
    if (provs.size > PROV_KEEP) provs.delete(provs.keys().next().value);
    const due = P.sig !== sig && !P.busy;
    if (provTimer && provWant && provWant.P !== P) { clearTimeout(provTimer); provTimer = 0; provWant = null; }   // picked past it
    if (due && !provTimer) { provWant = { P, ctx, sig }; provTimer = setTimeout(provLoad, PROV_WAIT); }
    return P;
  };
  function provLoad() {
    const w = provWant, a = api();
    provTimer = 0;
    provWant = null;
    if (!w || !a || w.P.busy) return;
    const { P, ctx, sig } = w;
    P.busy = true;
    let p;
    try { p = Promise.resolve(a.journal({ model: P.model, obj: P.obj, per_path: PROV_PER, types: ctx.types || {} })); } catch (e) { p = Promise.reject(e); }
    p.then((got) => {
      const paths = got && typeof got === "object" ? got.paths : null;
      if (paths && typeof paths === "object" && !Array.isArray(paths)) P.paths = paths;
      else if (got && typeof got === "object" && !got.error && Array.isArray(got.records)) provOld = true;   // a page: an older window.py
      else P.paths = {};                         // it failed: nothing shown, read again when the journal moves
    }).catch(() => { P.paths = {}; }).then(() => {
      P.busy = false;
      P.sig = sig;
      P.ver++;
      if (typeof ctx.onProv === "function") ctx.onProv(P);
    });
  }
  /** A loop's or an optimization's writes to the field, in short ("9 evaluations"). */
  function provSum(r) {
    const n = Number((r.report || {}).evaluations) || Number((r.runs || {}).n) || Number(r.n) || 0, d = r.do || "loop";
    if (r.op === "restore") return t("prov_restore");
    return tn(d === "optimize" ? "ch_r_evals" : ["sweep", "seek"].includes(d) ? `ch_s_${d}` : "ch_s_loop", n);
  }
  const provLoop = (r) => r.op === "summary" || r.op === "restore";
  /** A record's value before, cut short, with its unit where it is not the row's. */
  WBC.provWas = function (r, unit) {
    const b = r && r.before;
    if (b == null) return "";
    let s = val(b);
    if (s.length > 24) s = s.slice(0, 23).trimEnd() + "…";
    const u = typeof b === "object" && b.unit;
    return u && u !== unit ? `${s} ${u}` : s;
  };
  WBC.provLine = function (r, unit) {
    const head = `${who(r.actor)} · ${when(r.t)}`;
    if (provLoop(r)) return `${head} · ${provSum(r)}`;
    const was = WBC.provWas(r, unit);
    return was ? t("prov_line", who(r.actor), when(r.t), was) : head;
  };
  WBC.provCard = function (recs, unit) {
    const rows = (recs || []).slice(0, PROV_PER).map((r) => {
      const d = "before" in r || "after" in r ? change(r.before, r.after) : "";
      const sum = provLoop(r) ? ` <span class="ch-q">· ${esc(provSum(r))}</span>` : "";
      const why = r.reason != null && String(r.reason).trim(), own = r.reason_src === "why";
      return `<div class="pvc-r"><span class="pvc-t">${esc(when(r.t))}</span>${whoHtml(r.actor, true)}<span class="pvc-x">${d}${sum}</span></div>`
        + (why ? `<div class="ch-reason${own ? " why" : ""}" title="${esc(t(own ? "tip_why" : "tip_reason"))}">${rich(t(own ? "ch_why" : "reason", why), 200)}</div>` : "");
    });
    return `<div class="pvc-h">${esc(t("prov_head"))}</div>${rows.join("")}`
      + `<button class="pvc-all flat" data-act="prov_all">${icon("chevron-right")}<span>${esc(t("prov_all"))}</span></button>`;
  };

  // ------------------------------------------------------------------ what the record covers
  const covOf = () => { const c = window.wb && wb.state && wb.state.catalog, v = c && c.coverage; return v && typeof v === "object" && !Array.isArray(v) ? v : null; };
  /** The coverage bucket a tool's change falls in (value, inverse, checkpoint, none, program), or "". */
  const covClass = (tool) => { const c = covOf(); return (c && tool && COV_UNDO.find((k) => toolsOf(c[k]).includes(String(tool)))) || ""; };
  WBC.covOn = () => !!covOf();
  const COV_UNDO = ["value", "inverse", "checkpoint", "none", "program"];   // how a change could be taken back
  const toolsOf = (v) => (Array.isArray(v) ? v.map(String) : []);
  let cov = null;                     // the open note: {el, btn, sig}
  const covSig = (c) => `${I18N.lang}|${JSON.stringify(c)}|${((window.WBL && WBL.strings) || {}).state || ""}`;
  /** The note's words: what is recorded (and by which tools), Aspen's own window, taking back
   *  (not live yet: how it will be), and a line when Aspen's field names could not be read. */
  function covHtml(c) {
    const f = c.flags || {}, quiet = new Set(toolsOf(c.unrec)), all = [];
    Object.entries(c).forEach(([k, v]) => { if (k !== "unrec") toolsOf(v).forEach((n) => { if (!all.includes(n)) all.push(n); }); });
    const rec = all.filter((n) => !quiet.has(n)), undo = COV_UNDO.filter((k) => toolsOf(c[k]).length);
    const code = (list) => list.map((n) => `<code>${esc(n)}</code>`).join(" ");
    const more = (label, body) => `<details class="cov-d"><summary>${esc(label)}</summary>${body}</details>`;
    const part = (head, body) => `<section class="cov-s"><h4>${esc(head)}</h4>${body}</section>`;
    const cat = (window.wb && wb.state && wb.state.catalog) || {}, strings = (window.WBL && WBL.strings) || cat.strings || {};
    return `<div class="cov-h"><b id="cov-title">${esc(t("cov_btn"))}</b>`
      + `<button class="cov-x flat icon" data-c="close" title="${esc(t("close"))}">${icon("close")}</button></div>`
      + part(t("cov_rec_h"), `<p>${esc(t("cov_rec"))}</p>${more(t("cov_tools_n", rec.length), `<div class="cov-t">${code(rec)}</div>`)}`)
      + part(t("cov_ext_h"), `<p>${esc(t(f.external ? "cov_ext_on" : "cov_ext_off"))}</p>`)
      // taking back: live -- how, where the restore points are, the three words apart
      + part(t("cov_undo_h"), (f.undo ? `<p>${esc(t("cov_undo_on"))}</p><p>${esc(t("cov_undo_words"))}</p><p class="cov-q">${esc(t("cov_cp_limit"))}</p>`
        : `<p>${esc(t("cov_undo_off"))}</p><ul>${undo.map((k) => `<li>${esc(t(`cov_u_${k}`))}</li>`).join("")}</ul>`)
        + more(t("cov_tools"), undo.map((k) => `<div class="cov-t"><span>${esc(t(`cov_b_${k}`))}</span> ${code(toolsOf(c[k]))}</div>`).join("")))
      + (strings.state === "failed" ? `<p class="cov-str">${esc(t("cov_str_failed"))}</p>` : "");
  }
  /** Under the ⓘ, its right edges lined up; over it when there is more room there than under
   *  it and the note does not fit under (chosen when it opens; a part opened later scrolls).
   *  P: the box placed (the note, else the report box, which sits the same way). */
  function covPlace(first, P = cov) {
    if (P) P.up = drop(P.el, P.btn.getBoundingClientRect(), Math.min(380, window.innerWidth - 16), 120, first ? null : P.up);
  }
  /** The box btn opens (covPlace puts it under or over btn), btn marked open; Escape and a press
   *  outside the two close it (close(back)). boxOff takes it away. */
  function boxAt(btn, cls, title, close, place) {
    const box = popover(document.body, cls, title, { close, place, keep: (x) => btn.contains(x) });
    btn.setAttribute("aria-expanded", "true");
    btn.classList.add("on");
    return box;
  }
  function boxOff(P, back) {
    P.btn.setAttribute("aria-expanded", "false");
    P.btn.classList.remove("on");
    P.off(back, P.btn);
  }
  WBC.coverage = function (btn) {
    if (cov) {
      const same = cov.btn === btn;
      WBC.coverageClose(same);
      if (same) return;
    }
    const c = covOf();
    if (!c || !btn) return;
    WBC.reportClose();                           // (one box over the page at a time)
    const { el, off } = boxAt(btn, "cov-pop", "cov-title", (back) => WBC.coverageClose(back), () => covPlace(false));
    el.innerHTML = covHtml(c);
    cov = { el, off, btn, sig: covSig(c), up: false };
    covPlace(true);
    el.addEventListener("click", (ev) => { if (ev.target.closest('[data-c="close"]')) WBC.coverageClose(true); });
    el.addEventListener("toggle", () => covPlace(false), true);     // a list of tools opened or shut
    el.focus({ preventScroll: true });
  };
  WBC.coverageClose = function (back) {
    if (!cov) return false;
    const c = cov;
    cov = null;
    boxOff(c, back);
    return true;
  };
  WBC.coverageSync = function (on) {
    if (!cov) return;
    const c = covOf();
    if (!on || !c) { WBC.coverageClose(); return; }
    const sig = covSig(c);
    if (sig === cov.sig) return;
    const open = [...cov.el.querySelectorAll("details")].map((d) => d.open);
    cov.el.innerHTML = covHtml(c);
    cov.el.querySelectorAll("details").forEach((d, i) => { d.open = !!open[i]; });
    cov.sig = sig;
    covPlace(false);
  };

  // ------------------------------------------------------------------ while you were away, the report
  // Where the window makes change reports (window.py's Api.report: detected, no catalog flag).
  // Back in the window after being away (the page's caller decides when: WBC.back), or opening
  // it on a model changed since you last looked, one line over the Changes tab's cards counts
  // what the AI, programs, the optimizer and Aspen's own window changed meanwhile -- WBC.tally
  // over those records, never your own workbench edits, so the cards below add up to it. ×
  // puts it away for those records (wb.away.dismiss.<model>: the newest one counted); leaving
  // the tab after it showed does too. A newer journal while it shows counts again from the
  // same moment. The report: the tab's download button, or a card's ⋯ for its group.
  const AWAY_MAX = 2000;              // records the line reads at most (past it: "at least")
  const AWAY_SKIP = ["user"];         // your own edits in the workbench: never "while you were away"
  const AWAY_ORDER = ["ai", "program", "optimizer", "external"];
  const AWAY_PARTS = 3;               // parts an actor's clause shows (all of them in the tooltip)
  const AWAY_OPEN = 8;                // cards "See changes" opens at most
  WBC.repOn = () => WBC.on() && typeof api().report === "function";
  /** A card's ⋯ (its group's report), where the page can open a menu. */
  const moreOn = (ctx) => WBC.repOn() && !!ctx && typeof ctx.menu === "function";
  /** Ask AI about a record (its row, under the pointer) or a group (the card's ⋯), where the
   *  page can ask. */
  const askOn = (ctx) => !!ctx && typeof ctx.ask === "function";
  const askMenu = (ctx) => askOn(ctx) && typeof ctx.menu === "function";
  /** A group or picked records made into a block program, where the server does it (feature
   *  to_blocks) and the page can ask. */
  const tbOn = (ctx) => feature("to_blocks") && !!ctx && typeof ctx.toBlocks === "function";
  WBC.tbOn = tbOn;
  const aways = new Map();            // model id -> {model, since, upto, tally, n, more, sig, busy, shown, objs, over, net}
  const dismissKey = (id) => `wb.away.dismiss.${id}`;
  /** A {t, id} mark as Api.journal's `after`: id "" means every record at t (a bare time). */
  const cursorOf = (m) => (m.id ? [m.t, m.id] : m.t);
  const markOf = (s) => {
    try { const o = s ? JSON.parse(s) : null; return isObj(o) && isFinite(Number(o.t)) ? { t: Number(o.t), id: String(o.id || "") } : null; } catch (e) { return null; }
  };
  const later = (a, b) => (!b ? a : !a ? b : a.t !== b.t ? (a.t > b.t ? a : b) : (!a.id || (b.id && a.id > b.id)) ? a : b);
  /** You are back (left: when you left, epoch seconds), or the window opened (left null): the
   *  others' changes since then -- or since you last looked, when that is later; at opening,
   *  only when you had looked before. Resolves to the line's state (the caller shows the Changes
   *  tab's line, or a toast where the tab is not on screen), or null when there is nothing. */
  WBC.back = function (ctx, left) {
    if (!ctx || !ctx.model || ctx.journalOn === false || !WBC.repOn() || typeof ctx.prefGet !== "function") return Promise.resolve(null);
    if (left != null) aways.delete(ctx.model);   // back again: the last line gives way to this one (or to none)
    const s = ctx.summary, last = s && typeof s === "object" ? Number(s.last_t) || 0 : 0;
    let since = seenOf(ctx, ctx.model);
    if (left != null) since = later(since, { t: Number(left) || 0, id: "" });
    since = since && later(since, markOf(ctx.prefGet(dismissKey(ctx.model))));
    if (!since || !last || last < since.t || (!since.id && last <= since.t)) return Promise.resolve(null);
    return awayLoad(ctx, since);
  };
  function awayLoad(ctx, since) {
    const model = ctx.model, want = sigOf(ctx.summary), A0 = aways.get(model);
    if (A0) A0.busy = true;
    let p, q;
    try { p = Promise.resolve(api().journal({ model, after: cursorOf(since), limit: AWAY_MAX, types: ctx.types || {} })); } catch (e) { p = Promise.reject(e); }
    // before -> now of the results (journal.net: the runs' deltas chained); none: no line of it
    try { q = Promise.resolve(api().journal({ model, net: true, after: cursorOf(since), types: ctx.types || {} })).catch(() => null); } catch (e) { q = Promise.resolve(null); }
    return Promise.all([p, q]).then(([got, net]) => {
      if (A0) Object.assign(A0, { busy: false, sig: want });     // (a failed read: tried again when the journal moves)
      if (!isObj(got) || !Array.isArray(got.records) || (got.error && !got.records.length)) return null;
      const recs = got.records.filter((r) => isObj(r) && r.kind === "change");
      const mine = recs.filter((r) => !AWAY_SKIP.includes(String(r.actor || "")));
      const top = mine.reduce((m, r) => (!m || newer(r, m) ? r : m), null);
      const gone = markOf(ctx.prefGet(dismissKey(model)));
      const tally = WBC.tally(recs, AWAY_SKIP, { kinds: true });
      if (!top || (gone && !newer(top, gone)) || !awayClauses(tally, false).length) { if (aways.get(model) === A0) aways.delete(model); return null; }
      const objs = new Set();
      mine.forEach((r) => objsOf(r).forEach((k) => objs.add(k)));
      const A = { model, since, upto: { t: Number(top.t) || 0, id: String(top.id || "") }, tally, n: mine.length,
                  more: !!got.more, sig: want, busy: false, shown: !!(A0 && A0.shown), objs: [...objs].map(tgOf),
                  over: overOf(recs), net: isObj(net) && Array.isArray(net.results) ? net : null };
      aways.set(model, A);
      return A;
    }).catch(() => { if (A0) A0.busy = false; return null; });
  }
  /** One actor's part of the tally in words, most telling first: values (in how many blocks and
   *  streams), what was added, runs and how the last ended, loops and optimizations, what was
   *  removed, connections, saves, what did not go through. */
  function awayParts(c) {
    const out = [], one = (key, n, ...more) => tn(key, n, ...more);
    if (c.values) {
      const k = c.kinds || {}, where = [k.block ? one("aw_nb", k.block) : "", k.stream ? one("aw_ns", k.stream) : ""].filter(Boolean);
      out.push(where.length ? t("aw_vals_in", one("aw_nv", c.values), where.join(t("aw_and"))) : t("aw_vals", one("aw_nv", c.values)));
    }
    const named = (box, key) => {
      let n = 0;
      const ns = [];
      Object.values(box || {}).forEach((e) => { n += Number(e.n) || 0; (e.names || []).forEach((x) => { if (ns.length < NAMES_MAX) ns.push(x); }); });
      if (!n) return;
      const list = ns.join(t(ns.length === 2 ? "aw_and" : "aw_nsep"));
      out.push(!ns.length ? one(`${key}_k`, n) : n > ns.length ? t(`${key}_n`, list, n, n - ns.length) : t(key, list));
    };
    named(c.added, "aw_add");
    const runs = c.runs || {};
    if (runs.n) {
      const l = runs.last || {}, w = Number(l.warnings) || 0;
      const how = l.status === "ok" ? t("aw_o_ok") : l.status === "warn" ? (w ? one("aw_o_warn", w) : t("aw_o_warn_n"))
        : l.status === "error" ? t("aw_o_error") : t("aw_o_other");
      out.push(runs.n === 1 ? t("aw_run1", how) : t("aw_runs", runs.n, how));
    }
    Object.entries(c.studies || {}).forEach(([d, n]) => out.push(one(`aw_${["sweep", "seek", "optimize"].includes(d) ? d : "loop"}`, n)));
    named(c.removed, "aw_rm");
    if (c.connects) out.push(one("aw_conn", c.connects));
    if (c.saves) out.push(one("aw_saves", c.saves));
    if ((c.failed || 0) + (c.refused || 0)) out.push(one("aw_bad", (c.failed || 0) + (c.refused || 0)));
    return out;
  }
  /** Each actor's clause ("the AI changed 12 values in 3 blocks, added B4, ran it twice"), in
   *  order; all: every part (else AWAY_PARTS, then "and more"). */
  function awayClauses(T, all) {
    const by = T.by || {}, order = AWAY_ORDER.filter((a) => by[a]).concat(Object.keys(by).filter((a) => !AWAY_ORDER.includes(a)));
    return order.map((a) => {
      const ps = awayParts(by[a]);
      if (!ps.length) return "";
      const shown = all || ps.length <= AWAY_PARTS ? ps.join(t("aw_psep")) : ps.slice(0, AWAY_PARTS).join(t("aw_psep")) + t("aw_etc");
      return t(`aw_${AWAY_ORDER.includes(a) ? a : "other"}`, shown);
    }).filter(Boolean);
  }
  const awaySig = (id) => { const A = id && aways.get(id); return A ? `${A.upto.t}|${A.upto.id}|${A.n}|${A.more}|${A.net ? 1 : 0}` : ""; };
  /** "block:ESTCOL" as a target {kind, name}. */
  const tgOf = (k) => { const i = k.indexOf(":"); return { kind: k.slice(0, i), name: k.slice(i + 1) }; };
  const YOURS = ["external", "user"];         // your own edits: in Aspen's window, in the workbench
  /** Your own edits someone else set again afterwards (WBC.overrides), for the away line:
   *  [{own (whose edit), by (who changed it), n, paths}], one per pair. */
  function overOf(recs) {
    const ov = WBC.overrides(recs), byId = new Map(recs.map((r) => [r.id, r])), out = new Map();
    ov.forEach((x, id) => {
      const r = byId.get(id), own = r && String(r.actor || ""), by = String(x.actor || "");
      if (!r || !YOURS.includes(own) || YOURS.includes(by)) return;
      const k = `${own}|${by}`, e = out.get(k) || { own, by, n: 0, paths: [] };
      e.n++;
      if (e.paths.length < NAMES_MAX) e.paths.push(String((r.target || {}).path || ""));
      out.set(k, e);
    });
    return [...out.values()];
  }
  /** "the AI later changed 1 of your edits in the Aspen window (HX1 › Temperature)". */
  function overClauses(A) {
    return (A.over || []).map((e) => {
      const who = t(`aw_by_${["ai", "program", "optimizer"].includes(e.by) ? e.by : "other"}`);
      const names = e.paths.map((p) => (window.WBL ? WBL.say(p) : base(p))).join(t("aw_nsep")) + (e.n > e.paths.length ? t("aw_etc") : "");
      return tn(`aw_over_${e.own}`, e.n, who, names);
    });
  }
  /** The results before -> now (journal.net): the NET_SHOW that moved most and did not come back,
   *  as markup, and all of them in words for its tooltip; null where none moved. */
  const NET_SHOW = 2;
  function netParts(net, types) {
    const rs = (net && Array.isArray(net.results) ? net.results : []).filter((x) => x && x.path && !x.back && !x.small);
    if (!rs.length) return null;
    const seqs = Array.isArray(net.seqs) ? net.seqs : [], runs = Number(net.runs) || 0;
    const tail = seqs.length === 2 && seqs[0] !== seqs[1] ? t("net_runs", seqs[0], seqs[1]) : seqs.length ? t("net_run", seqs[1]) : runs > 1 ? tn("net_runs_n", runs) : "";
    const one = (x) => { const [b, a] = pair(x.b, x.a), ar = arrow(x.b, x.a); return { b, a, ar, u: x.u ? ` ${x.u}` : "" }; };
    const html = rs.slice(0, NET_SHOW).map((x) => {
      const v = one(x), p = String(x.path);
      return `<span class="nr${goAt(p, true)}>${field(p, null, typeAt(p, types))} <span class="ch-v"><b>${esc(v.b)}</b> → <b>${esc(v.a)}</b>`
        + `${v.u ? `<small>${esc(v.u)}</small>` : ""}${v.ar ? `<i class="rc-ar">${v.ar}</i>` : ""}</span></span>`;
    }).join(`<span class="ch-q"> · </span>`);
    const text = rs.map((x) => { const v = one(x); return `${window.WBL ? WBL.say(String(x.path)) : base(x.path)} ${v.b} → ${v.a}${v.u}${v.ar}${x.cut ? ` ${t("net_cut")}` : ""}`; });
    const cut = !!net.partial;
    return { html: `${html}${tail ? ` <small class="ch-q">${esc(tail)}</small>` : ""}${cut ? ` <small class="ch-q">${esc(t("net_part"))}</small>` : ""}`,
             plain: text.slice(0, NET_SHOW).join(" · ") + (tail ? ` ${tail}` : "") + (cut ? ` ${t("net_part")}` : ""),
             tip: [t("net_head"), ...text, tail, cut ? t("tip_net_part") : ""].filter(Boolean).join("\n") };
  }
  /** A change group's results before -> now, where it ran the simulation twice or more (one run:
   *  its own card says it): journal.net of the group, read once for what the card holds (the
   *  card drawn again when it comes); null till then, or where there is nothing to say. */
  const nets = new Map();             // model + group -> {sig, busy, net}
  function cardNet(c, M, ctx) {
    if (!c.gid || c.recs.filter(measured).length < 2) return null;
    const key = `${M.id}\n${c.gid}`, sig = `${c.recs.length}|${(c.recs[c.recs.length - 1] || {}).id}`, a = api();
    let N = nets.get(key);
    if (!N) nets.set(key, (N = { sig: null, busy: false, net: null }));
    if (N.sig !== sig && !N.busy && a) {
      N.busy = true;
      let p;
      try { p = Promise.resolve(a.journal({ model: M.id, net: true, group: c.gid, types: (ctx && ctx.types) || {} })); } catch (e) { p = Promise.reject(e); }
      p.then((got) => { N.net = isObj(got) && Array.isArray(got.results) ? got : null; }).catch(() => {}).then(() => {
        N.busy = false;
        N.sig = sig;
        M.ver++;
        const w = M.box && M.box._wbc;
        if (w && w.ctx.model === M.id) WBC.render(M.box, w.ctx);
      });
    }
    return N.net;
  }
  /** The line, one row: "12 new changes since 13:50" (a click opens the cards it counts), Show on the flowsheet,
   *  Mark all read, ×. Who did what, whose edits were set again and the results before -> now are its
   *  tooltip; the report is the tab's download button. */
  function awayHtml(A, ctx) {
    const at = when(A.since.t), key = A.more ? "aw_line_more" : "aw_line", ov = overClauses(A);
    const n = `${A.n}${A.more ? "+" : ""}`, one = A.n === 1 && !A.more && !zh() && I18N.t("aw_short_1") !== "aw_short_1";
    const res = netParts(A.net, (ctx && ctx.types) || {});
    const tip = [t(key, at, awayClauses(A.tally, true).concat(ov).join(t("aw_sep"))), res ? res.tip : "", t("tip_away"), t("tip_aw_see")].filter(Boolean).join("\n");
    const fs = A.objs && A.objs.length && ctx && typeof ctx.showObjs === "function";
    const btn = (c, label, tip2) => `<button class="aw-b flat" data-c="${c}" title="${esc(tip2)}">${esc(label)}</button>`;
    return `${icon("eye")}<button class="aw-t flat" data-c="away_go" title="${esc(tip)}">${esc(t(one ? "aw_short_1" : "aw_short", at, n))}</button>`
      + (fs ? btn("away_fs", t("aw_fs"), t("tip_aw_fs")) : "")
      + btn("away_all", t("aw_all"), t("tip_aw_all"))
      + `<button class="aw-x flat icon" data-c="away_x" title="${esc(t("tip_aw_x"))}">${icon("close")}</button>`;
  }
  /** The line's state for a model (the regression suite reads it), or null. */
  WBC.awayOf = (id) => aways.get(id) || null;
  /** "Mark all as seen": the last-seen mark and the dots' move to the newest record (the unread
   *  count, the line "last seen here" and every dot go), and the away line is put away. */
  function markAll(box, ctx) {
    const s = ctx.summary, A = aways.get(ctx.model);
    if (typeof ctx.prefSet !== "function" || !s || typeof s !== "object") return;
    let m = { t: Number(s.last_t) || 0, id: "" };
    store.forEach((M) => { const r = M.id === ctx.model && M.recs[0]; if (r && Number(r.t) >= m.t) m = later(m, { t: Number(r.t), id: String(r.id || "") }); });
    if (A) m = later(m, A.upto);
    if (!m.t) return;
    const val = JSON.stringify({ t: m.t, id: m.id, others: othersOf(s) || 0 });
    ctx.prefSet(seenKey(ctx.model), val);
    ctx.prefSet(dotsKey(ctx.model), val);
    if (A) ctx.prefSet(dismissKey(ctx.model), JSON.stringify(A.upto));
    aways.delete(ctx.model);
    const w = box._wbc;
    if (w && w.view && w.view.model === ctx.model) { w.view.divider = { t: m.t, id: m.id, others: othersOf(s) || 0 }; w.view.marked = sigOf(s); }
    notify(ctx);
    WBC.render(box, ctx);
    if (typeof ctx.toast === "function") ctx.toast(t("aw_all_done"), 2400);
  }
  /** "See changes" in the tab: the cards holding what the line counts, opened (AWAY_OPEN at
   *  most), the first brought into view. */
  function awayOpen(box, ctx) {
    const A = aways.get(ctx.model), st = tabState(ctx.tab), M = ctx.model ? model(ctx.model, st.actors, okey(st.obj)) : null;
    if (!A || !M) return;
    const after = (r) => r.kind === "change" && !AWAY_SKIP.includes(String(r.actor || "")) && newer(r, A.since);
    const hit = cards(M).filter((c) => c.recs.some(after)).slice(0, AWAY_OPEN);
    hit.forEach((c) => M.open.set(c.key, true));
    M.ver++;
    WBC.render(box, ctx);
    const el = hit.length && box.querySelector(`.ch-card[data-key="${CSS.escape(hit[0].key)}"]`);
    if (el) box.scrollTop = Math.max(0, el.offsetTop - 4);
  }

  let rep = null;                     // the report box open: {el, btn, ctx, since, group, title, span, fmt, busy, err}
  const REP_SPANS = ["today", "since", "all", "group"];
  function repPref(ctx) {
    try { const o = JSON.parse((typeof ctx.prefGet === "function" && ctx.prefGet("wb.rep")) || "{}"); return isObj(o) ? o : {}; } catch (e) { return {}; }
  }
  /** The report box's words: the range (today, since you last looked -- the line the tab shows
   *  --, all, this group from a card), the format, what the format is good for, the button. */
  function repHtml() {
    const R = rep, radio = (attr, k, label, on, tip, off) => `<button class="rep-c${on ? " on" : ""}" data-${attr}="${k}" role="radio"`
      + ` aria-checked="${on}"${off ? " disabled" : ""}${tip ? ` title="${esc(tip)}"` : ""}>${esc(label)}</button>`;
    const spans = [radio("span", "today", t("today"), R.span === "today"),
      radio("span", "since", R.since ? t("rep_span_since", when(R.since.t)) : t("rep_span_since0"), R.span === "since", R.since ? "" : t("tip_rep_since0"), !R.since),
      radio("span", "all", t("rep_span_all"), R.span === "all")];
    if (R.group) spans.push(radio("span", "group", t("rep_span_group"), R.span === "group", R.title));
    const fmts = [radio("fmt", "md", "Markdown", R.fmt === "md"), radio("fmt", "html", "HTML", R.fmt === "html")];
    return `<div class="cov-h"><b id="rep-title">${esc(t("rep_title"))}</b>`
      + `<button class="cov-x flat icon" data-c="close" title="${esc(t("close"))}">${icon("close")}</button></div>`
      + `<div class="rep-g"><span class="rep-l">${esc(t("rep_span"))}</span><div class="rep-o" role="radiogroup" aria-label="${esc(t("rep_span"))}">${spans.join("")}</div>`
      + `<span class="rep-l">${esc(t("rep_fmt"))}</span><div class="rep-o" role="radiogroup" aria-label="${esc(t("rep_fmt"))}">${fmts.join("")}</div></div>`
      + `<p class="rep-n">${esc(t(R.fmt === "html" ? "rep_hint_html" : "rep_hint_md"))}</p>`
      + (R.err ? `<p class="rep-e">${esc(R.err)}</p>` : "")
      + `<div class="rep-f"><button class="primary rep-go" data-c="go"${R.busy ? " disabled" : ""}>${esc(t(R.busy ? "rep_busy" : "rep_go"))}</button></div>`;
  }
  function repDraw() {
    if (!rep) return;
    const inside = rep.el.contains(document.activeElement), go = inside && document.activeElement.closest("[data-c=go]");
    rep.el.innerHTML = repHtml();
    covPlace(false, rep);
    const b = go && rep.el.querySelector("[data-c=go]");
    if (b && !b.disabled) b.focus({ preventScroll: true });
    else if (inside) rep.el.focus({ preventScroll: true });   // (the button waits: the keyboard stays in the box)
  }
  /** Open the report box under (or over) btn for ctx's model; group: {id, title} from a card
   *  (the range "this group" offered and chosen). Open already from btn: close it. */
  WBC.report = function (btn, ctx, group) {
    if (rep) {
      const same = rep.btn === btn;
      WBC.reportClose(same);
      if (same) return;
    }
    if (!btn || !ctx || !ctx.model || !WBC.repOn()) return;
    WBC.coverageClose();
    const pane = btn.closest(".pane") || (window.wb && wb.pane && wb.pane.el);   // (from a menu outside the pane too)
    const box = pane && pane.querySelector(".tab-changes"), w = box && box._wbc, A = aways.get(ctx.model);
    const since = A ? A.since : w && w.view && w.view.model === ctx.model ? w.view.divider : null;
    const p = repPref(ctx);
    const span = group ? "group" : p.span === "since" && !since ? "today" : REP_SPANS.includes(p.span) && p.span !== "group" ? p.span : "today";
    const { el, off } = boxAt(btn, "cov-pop rep-pop", "rep-title", (back) => WBC.reportClose(back), () => covPlace(false, rep));
    rep = { el, off, btn, ctx, since, group: group ? group.id : null, title: group ? group.title : "", span, fmt: p.fmt === "html" ? "html" : "md",
            busy: false, err: "", up: false, lang: I18N.lang };
    el.innerHTML = repHtml();
    covPlace(true, rep);
    el.addEventListener("click", (ev) => {
      const b = ev.target.closest("button");
      if (!b || b.disabled || !rep) return;
      if (b.dataset.c === "close") { WBC.reportClose(true); return; }
      if (b.dataset.c === "go") { repGo(); return; }
      if (b.dataset.span) rep.span = b.dataset.span;
      else if (b.dataset.fmt) rep.fmt = b.dataset.fmt;
      else return;
      rep.err = "";
      if (typeof rep.ctx.prefSet === "function") rep.ctx.prefSet("wb.rep", JSON.stringify({ span: rep.span === "group" ? (repPref(rep.ctx).span || "today") : rep.span, fmt: rep.fmt }));
      repDraw();
      const again = rep.el.querySelector(`[data-${b.dataset.span ? "span" : "fmt"}="${b.dataset.span || b.dataset.fmt}"]`);
      if (again) again.focus({ preventScroll: true });
    });
    const go = el.querySelector("[data-c=go]");
    (go || el).focus({ preventScroll: true });
  };
  /** Make the report (Api.report) and hand it to the window's save dialog (Api.save_file). */
  function repGo() {
    const R = rep, a = api();
    if (!R || R.busy || !a || typeof a.report !== "function") return;
    const ctx = R.ctx, cat = (window.wb && wb.state && wb.state.catalog) || {};
    const req = { model: ctx.model, span: R.span, fmt: R.fmt, lang: I18N.lang, types: ctx.types || {} };
    if (isObj(cat.coverage)) req.coverage = cat.coverage;
    if (R.span === "since" && R.since) req.after = cursorOf(R.since);
    if (R.span === "group" && R.group) req.group = R.group;
    R.busy = true;
    R.err = "";
    repDraw();
    let p;
    try { p = Promise.resolve(a.report(req)); } catch (e) { p = Promise.reject(e); }
    p.then((got) => {
      if (!isObj(got) || got.error || typeof got.text !== "string") throw new Error(String((got && got.error) || "no answer"));
      if (!got.n) { if (rep === R) { R.busy = false; R.err = t("rep_none"); repDraw(); } return; }
      if (rep === R) WBC.reportClose(true);
      return Promise.resolve(typeof a.save_file === "function" ? a.save_file(String(got.name || `changes.${R.fmt}`), got.text, R.fmt) : null)
        .then((path) => { if (path && typeof ctx.toast === "function") ctx.toast(t("rep_done", path), 5000); });
    }).catch((e) => {
      if (rep !== R) return;
      R.busy = false;
      R.err = t("rep_err", String((e && e.message) || e || "?"));
      repDraw();
    });
  }
  WBC.reportClose = function (back) {
    if (!rep) return false;
    const r = rep;
    rep = null;
    boxOff(r, back);
    return true;
  };
  /** The tab's download button shows (on) or not: the box closed when not; words again after
   *  a language switch. */
  WBC.reportSync = function (on) {
    if (!rep) return;
    if (!on || !rep.btn.isConnected || !rep.btn.offsetParent) { WBC.reportClose(); return; }
    if (rep.lang !== I18N.lang) { rep.lang = I18N.lang; repDraw(); }
  };

  // ------------------------------------------------------------------ one model's timeline
  // One per model and actor filter. recs: newest first, as loaded; groups: {gid: newest
  // header}; more / cursor: an earlier page (capped: the search stopped at its limit, scanned
  // records); sig: the journal summary it was loaded for; busy: a request out (seq tells its
  // answer from a newer one's); open: card key -> opened (the user's, or by itself: auto);
  // rows: card key -> rows drawn; ver: bumped on every change drawn; rc: a measured run's
  // record id -> its effects opened (the newest by itself); rcAll: runs showing every result;
  // same: cards whose writes that left a value as it was are drawn one by one (sameOf).
  function model(id, actors, obj) {
    const key = `${id}\n${actors || ""}\n${obj || ""}`;
    let M = store.get(key);
    if (!M) {
      M = { id, key, actors: actors || null, obj: obj || "", recs: [], ids: new Set(), groups: {}, more: false, cursor: null, capped: false, scanned: 0,
            loaded: false, error: null, sig: null, busy: false, seq: 0, older: false,
            open: new Map(), auto: new Set(), rows: new Map(), ver: 0, rc: new Map(), rcAll: new Set(), same: new Set() };
      store.set(key, M);
    }
    return M;
  }
  /** A workbench tab's filter: actors (one actor, or null: all), obj (only one block's or
   *  stream's changes: {kind, name}, or null), bar (the chips unfolded by hand: true / false;
   *  null: as the record's length has it). */
  function tabState(id) {
    let st = tabs.get(id || "");
    if (!st) { st = { actors: null, obj: null, bar: null, sel: null }; tabs.set(id || "", st); }
    return st;
  }
  /** The tab's select mode: on, and the records picked, of its model (another model: off). */
  function selOf(ctx) {
    const st = tabState(ctx.tab);
    if (!st.sel || st.sel.model !== ctx.model) st.sel = { on: false, model: ctx.model, ids: new Set() };
    return st.sel;
  }
  const selSig = (ctx) => { const st = tabs.get((ctx && ctx.tab) || ""); return st && st.sel && st.sel.on && tbOn(ctx) ? `sel:${st.sel.model}` : ""; };
  WBC.selOn = (tab) => { const st = tabs.get(tab || ""); return !!(st && st.sel && st.sel.on); };
  WBC.select = function (box, ctx, on) {
    if (!ctx || !ctx.model) return;
    const S = selOf(ctx);
    S.on = !!on && tbOn(ctx);
    S.ids.clear();
    if (box) WBC.render(box, ctx);
  };
  /** The foot of the tab in select mode: how many are picked, Turn into blocks, Cancel. */
  function selBar(box, ctx) {
    const P = box._wbc && box._wbc.parts;
    if (!P || !P.selbar) return;
    const S = ctx.model && tbOn(ctx) ? selOf(ctx) : null, on = !!(S && S.on) && !!ctx.shown;
    P.selbar.classList.toggle("hidden", !on);
    if (!on) { setHtml(P.selbar, ""); return; }
    const n = S.ids.size, off = !ctx.connected ? t("why_off") : "";
    setHtml(P.selbar, `<span class="ch-sn">${esc(n ? tn("to_blocks_sel", n) : t("to_blocks_sel0"))}</span>`
      + `<button class="primary" data-c="sel_go"${!n || off ? " disabled" : ""} title="${esc(off || t("tip_to_blocks"))}">${icon("blocks")}<span>${esc(t("to_blocks_go"))}</span></button>`
      + `<button data-c="sel_x">${esc(t("cancel"))}</button>`);
  }
  /** Keep only tg's changes on the tab's timeline (null: all again); the look at the model
   *  starts again (what is seen follows what shows). Returns whether it moved. */
  function setObj(box, ctx, tg) {
    const st = tabState(ctx.tab), o = okey(tg) ? { kind: tg.kind, name: String(tg.name) } : null;
    if (okey(st.obj) === okey(o)) return false;
    const w = box && box._wbc;
    if (w && w.view) { clearTimeout(w.view.timer); w.view.timer = 0; w.view.marked = null; }
    st.obj = o;
    return true;
  }
  /** Go to a change group's card (an Ask AI request's See changes): a filter that hides it
   *  lets go, earlier pages are read until it is found (JUMP_PAGES at most), then it opens,
   *  comes into view and flashes once (draw: jumped). Not found: a toast says so. */
  WBC.showGroup = function (box, ctx, gid, rid) {
    if (!box || !ctx || !ctx.on || !ctx.model || !(gid || rid)) return;
    const w = boxOf(box, ctx), st = tabState(ctx.tab), M = model(ctx.model, st.actors, okey(st.obj));
    const has = (c) => (rid ? c.recs.some((r) => r.id === rid) : c.gid === gid);
    if (!(M.loaded && cards(M).some(has)) && (st.actors || st.obj)) {
      st.actors = null;
      setObj(box, ctx, null);
    }
    w.jump = { gid: String(gid || ""), rid: rid ? String(rid) : "", model: ctx.model, pages: 0 };
    w.sig = null;                                // (drawn again, even with a jump on its way)
    WBC.render(box, ctx);
  };
  /** The card a jump is for, in the list drawn: opened (its element made again), or earlier
   *  pages asked for; null while it is not here. */
  function jumpFind(box, ctx, M, list) {
    const w = box._wbc, J = w.jump;
    if (!J || J.model !== ctx.model) { w.jump = null; return null; }
    const c = list.find((x) => (J.rid ? x.recs.some((r) => r.id === J.rid) : x.gid === J.gid));
    if (c) {
      M.open.set(c.key, true);
      const i = J.rid ? c.recs.findIndex((r) => r.id === J.rid) : -1;   // (its row drawn)
      if (i >= 0 && isSame(c.recs[i])) M.same.add(c.key);                // (a folded one: unfolded)
      if (i >= (M.rows.get(c.key) || ROWS)) M.rows.set(c.key, i + 1);
      return c;
    }
    if (M.more && J.pages < JUMP_PAGES) {
      if (!M.busy) { J.pages++; load(M, ctx, "older", box); M.ver++; }   // (its answer draws again)
      return null;
    }
    w.jump = null;
    if (typeof ctx.toast === "function") ctx.toast(t("ch_group_gone"), 4000);
    return null;
  }
  /** The card found: in view near the list's top, a tint that fades out once (a record gone
   *  to: its row, in view at a third of the list's height). */
  function jumped(box, L, c) {
    const J = box._wbc.jump;
    box._wbc.jump = null;
    const card = L.querySelector(`.ch-card[data-key="${CSS.escape(c.key)}"]`);
    const row = card && J && J.rid ? card.querySelector(`.ch-row[data-rid="${CSS.escape(J.rid)}"]`) : null, el = row || card;
    if (!el) return;
    if (row) box.scrollTop = Math.max(0, box.scrollTop + row.getBoundingClientRect().top - box.getBoundingClientRect().top - box.clientHeight / 3);
    else box.scrollTop = Math.max(0, el.offsetTop - 4);
    // a card made just now takes its size only once in view (content-visibility), and the
    // browser's scroll anchoring may then carry the view past it: brought back, the next frames
    let n = 0;
    const back = () => {
      if (!el.isConnected) return;
      const a = box.getBoundingClientRect(), b = el.getBoundingClientRect();
      if (b.top < a.top - 1 || b.top > a.bottom - 24) box.scrollTop = Math.max(0, box.scrollTop + b.top - a.top - (row ? box.clientHeight / 3 : 4));
      if (++n < 3) requestAnimationFrame(back);
    };
    requestAnimationFrame(back);
    el.classList.remove("flash");
    void el.offsetWidth;
    el.classList.add("flash");
    setTimeout(() => el.classList.remove("flash"), FLASH_MS);
  }
  WBC.pick = function (box, ctx, tg) {
    if (!box || !ctx || !ctx.on || !ctx.shown || !ctx.model) return;   // hidden: its filter stays as it is
    if (setObj(box, ctx, tg)) WBC.render(box, ctx);
  };
  WBC.only = function (box, ctx, tg) {
    if (!box || !ctx || !ctx.on || !okey(tg)) return;
    if (setObj(box, ctx, tg) && ctx.shown) WBC.render(box, ctx);
  };
  const sigOf = (s) => (s && typeof s === "object" ? `${s.n}|${s.last_t}` : "");
  const keyT = (r) => [Number(r.t) || 0, String(r.id || "")];
  const newer = (a, b) => { const x = keyT(a), y = keyT(b); return x[0] !== y[0] ? x[0] > y[0] : x[1] > y[1]; };

  function mergeGroups(M, groups) {
    Object.entries(groups || {}).forEach(([gid, h]) => {
      if (h && typeof h === "object" && (!M.groups[gid] || newer(h, M.groups[gid]))) M.groups[gid] = h;
    });
  }
  function take(M, recs, where) {
    const fresh = (recs || []).filter((r) => r && typeof r === "object" && r.id && !M.ids.has(r.id));
    fresh.forEach((r) => M.ids.add(r.id));
    M.recs = where === "top" ? fresh.concat(M.recs) : M.recs.concat(fresh);
  }

  /** Ask the window for a page: "first" (the newest), "new" (since the newest shown; more
   *  than a page new: the first page again), "older" (the page before the oldest shown). */
  function load(M, ctx, how, box) {
    const a = api();
    if (!a) return;
    if (M.busy) return;                        // (its answer draws, and asks again if the journal moved)
    if (how === "new" && !M.recs.length) how = "first";
    const want = sigOf(ctx.summary);
    const req = { model: M.id, limit: PAGE, types: ctx.types || {} };
    if (M.actors) req.actors = [M.actors];
    if (M.obj) req.obj = M.obj;
    if (how === "new") req.after = keyT(M.recs[0]);
    if (how === "older") req.before = M.cursor;
    M.busy = true;
    M.older = how === "older";
    const my = ++M.seq;
    let p;
    try { p = Promise.resolve(a.journal(req)); } catch (e) { p = Promise.reject(e); }
    p.then((got) => {
      if (my !== M.seq) return;
      if (!got || typeof got !== "object") throw new Error("no answer");
      if (got.error && !(got.records || []).length) throw new Error(String(got.error));
      if (how === "new" && got.more) {         // more came than a page: start again from the newest
        Object.assign(M, { recs: [], ids: new Set(), groups: {} });
        M.busy = false;
        return load(M, ctx, "first", box);
      }
      mergeGroups(M, got.groups);
      if (how === "first") { M.recs = []; M.ids = new Set(); }
      take(M, got.records, how === "new" ? "top" : "end");
      if (how !== "new") {
        M.more = !!got.more;
        M.cursor = got.cursor || null;
        M.capped = !!got.more && (got.records || []).length < PAGE;
        M.scanned = Number(got.scanned) || 0;
      }
      M.error = null;
      M.loaded = true;
      if (how !== "older") M.sig = want;
    }).catch((e) => {
      if (my !== M.seq) return;
      M.error = String((e && e.message) || e || "?");
      M.loaded = true;
      if (how !== "older") M.sig = want;       // asked again when the journal moves or the tab shows
    }).then(() => {
      if (my !== M.seq) return;                // a newer request took over (a first page again)
      M.busy = false;
      M.older = false;
      M.ver++;
      const w = box && box._wbc;
      if (w && w.ctx.model === M.id) WBC.render(box, w.ctx);
    });
  }

  // ------------------------------------------------------------------ cards
  /** The loaded records as cards, newest card first: one per change group (a record without
   *  one: its call's, else its own), its records oldest first. A begin whose call ended (the
   *  journal says open false; an older one: a record of its call is here) is no line, only
   *  its card's start time: it says a long call started. */
  function cards(M) {
    const byKey = new Map(), list = [], ended = new Set();
    M.recs.forEach((r) => { if (r.kind === "change" && r.call) ended.add(r.call); });
    M.recs.forEach((r) => {
      // a brake's milestone (its mode, a pause, a resume) or a proposal you declined later: a line
      // of its own at its time, whatever group it came in
      const mile = r.kind === "change" && (r.op === "brake" || r.op === "proposal");
      const key = mile ? `m:${r.id}` : r.group ? `g:${r.group}` : r.call ? `c:${r.call}` : `r:${r.id}`;
      let c = byKey.get(key);
      if (r.kind === "begin" && (r.open === false || (r.open !== true && r.call && ended.has(r.call)))) {
        if (c) c.t0 = Math.min(c.t0, Number(r.t) || c.t0);
        return;
      }
      if (!c) {
        c = { key, gid: mile ? null : r.group || null, head: (!mile && r.group && M.groups[r.group]) || null, recs: [], t0: Infinity, t1: -Infinity, mile };
        byKey.set(key, c);
        list.push(c);
      }
      c.recs.push(r);
      const tt = Number(r.t) || 0;
      c.t0 = Math.min(c.t0, tt);
      c.t1 = Math.max(c.t1, tt);
    });
    list.forEach((c) => {
      c.recs.reverse();
      c.actor = (c.head && c.head.actor) || (c.recs[0] && c.recs[0].actor) || "external";
      if (c.head && !c.head.title && (c.head.source === "revert" || c.head.source === "restore")) c.alt = altTitle(c, M);
    });
    return list;
  }
  /** A group's title from its header alone (a restore's confirmation lists the groups it takes
   *  back): its own, an undo's or a restore's as the cards say it, else who made it. */
  WBC.headTitle = function (h, groups) {
    if (!h || typeof h !== "object") return t("ch_title_external");
    if (h.title) return ownTitle(h);
    if (h.source === "revert" || h.source === "restore") return altTitle({ head: h, recs: [] }, { groups: groups || {} });
    return t(`ch_title_${ACT[h.actor] ? h.actor : "external"}`);
  };
  /** An undo's card (a group of its own, source revert, of the group it took back) is titled
   *  by what it took back: Undo of “Raise the top purity”, Redo of “…” for the undo of an undo; a
   *  restore's, Model restored. `of` is a group id, or the ids when it took back records of several
   *  (the first one known names it); its header not at hand, the undo's `label` does. */
  function altTitle(c, M) {
    const h = c.head;
    if (h.source === "restore") return t("uv_title_restore");
    const headOf = (of) => (Array.isArray(of) ? of : of ? [of] : []).map((g) => M.groups[g]).find(Boolean) || null;
    const base = headOf(h.of), redo = c.recs.some((r) => r.redo) || (!!base && base.source === "revert");
    const orig = redo ? base && headOf(base.of) : base;
    const name = orig ? String(orig.title || t(`ch_title_${ACT[orig.actor] ? orig.actor : "external"}`))
      : String(h.label || (base && base.label) || "");
    return name ? t(redo ? "uv_title_redo" : "uv_title_undo", name.length > 40 ? `${name.slice(0, 39)}…` : name)
      : t(redo ? "redo" : "undo");
  }

  // ------------------------------------------------------------------ words
  const dt = (s) => new Date((Number(s) || 0) * 1000);
  const md = (s) => { const d = dt(s); return `${d.getMonth() + 1}/${d.getDate()}`; };
  const sameDay = (a, b) => dt(a).toDateString() === dt(b).toDateString();
  const stamp = (s) => { const d = dt(s); return `${d.getFullYear()}/${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${hhmm(s)}:${pad(d.getSeconds())}`; };
  /** A card's time: 14:02, 14:02–14:05; with its date when not today (9/25 14:02). */
  function span(t0, t1) {
    const now = Date.now() / 1000, day = (s) => (sameDay(s, now) ? "" : `${md(s)} `);
    if (hhmm(t0) === hhmm(t1) && sameDay(t0, t1)) return day(t1) + hhmm(t1);
    return sameDay(t0, t1) ? `${day(t0)}${hhmm(t0)}–${hhmm(t1)}` : `${day(t0)}${hhmm(t0)} – ${md(t1)} ${hhmm(t1)}`;
  }
  const numText = (v) => (typeof v === "number" && isFinite(v) ? Number(v.toPrecision(6)).toString() : String(v));
  /** A measured {value, unit, show}: its words (an option's name, a cut value with …). */
  function val(d) {
    if (!d || typeof d !== "object") return d == null ? "—" : numText(d);
    if (d.show != null) return String(d.show);
    return d.value == null || d.value === "" ? t("ch_empty_v") : numText(d.value);
  }
  function valHtml(d, unit) {
    const tip = d && typeof d === "object" && d.tip ? ` title="${esc(d.tip)}"` : "";
    const u = unit && d && d.unit ? ` <small>${esc(d.unit)}</small>` : "";
    return `<b${tip}>${esc(val(d))}</b>${u}`;
  }
  /** before → after unit, the unit (or basis) on each side when it changed. */
  function change(b, a) {
    const ub = b && b.unit, ua = a && a.unit, unitMoved = (ub || ua) && ub !== ua;
    const basisMoved = b && a && (b.basis || a.basis) && b.basis !== a.basis;
    let s = `${valHtml(b, unitMoved)} → ${valHtml(a, true)}`;
    if (unitMoved) s += `<small class="ch-q">${esc(t("ch_r_unit"))}</small>`;
    else if (basisMoved) s += `<small class="ch-q">${esc(t("ch_r_basis", b.basis || "—", a.basis || "—"))}</small>`;
    return `<span class="ch-v">${s}</span>`;
  }
  /** A field's name where it sits in Aspen (labels.js): the record's own loc, or the better
   *  one the window has since. The path itself only in the tooltip. */
  function field(path, lc, type) {
    const p = String(path || "");
    const l = window.WBL ? WBL.best(p, type || null, lc || null, null) : null;
    return l ? WBL.html(l, "short", { tip: p }) : `<span title="${esc(p)}">${esc(base(p))}</span>`;
  }
  const op0 = (r) => r.op === "call" || r.op == null;      // a tool's own record: nothing measured
  /** A write that set a field to the value it already had (its line ends “(no change)”, ch_r_same): a card
   *  folds these into one quiet line (sameOf). A field made by the write is a change. */
  const isSame = (r) => r.kind === "change" && (r.op === "value" || r.op === "attr") && r.status === "unchanged" && !r.created;
  const kindWord = (k) => { const w = t(`ch_k_${k}`); return w === `ch_k_${k}` ? t("ch_k_element") : w; };
  /** Plain text naming any \Data\ path in it (labels.js), cut to n characters. */
  function rich(s, n) {
    s = String(s || "").replace(/\s+/g, " ").trim();
    if (s.length > n) s = s.slice(0, n - 1).trimEnd() + "…";
    return window.WBL ? WBL.rich(s) : esc(s);
  }

  // ------------------------------------------------------------------ edits made in Aspen's own window
  // Where the server compares Aspen's own window with what it knows (catalog.features external),
  // a record by actor external is what a compare found: t when it was found, since when the old
  // state was last known (the edit came in between; when exactly, no one can tell), why what
  // asked for the compare, detect how (deep: the inspector's check). Without the feature such
  // records read as before.
  const extOn = () => feature("external");
  const isExt = (r) => !!r && r.actor === "external" && r.kind === "change" && extOn();
  /** "Changed in the Aspen window (found at 14:05): " before a value's row. */
  const extPre = (r) => (isExt(r) ? `<span class="ch-ext">${esc(t("ext_pre", when(r.t)))}</span>` : "");
  /** What asked for the compare, in words (the row's tooltip). */
  function extWhy(r) {
    const w = String(r.why || "");
    if (r.detect === "deep" || w === "deep") return t("tip_ext_deep");
    if (w.startsWith("ai_call:")) return t("tip_ext_why_ai", w.slice(8));
    if (w === "idle") return t("tip_ext_why_idle");
    if (w === "program") return t("tip_ext_why_prog");
    return w ? t("tip_ext_why_win") : "";
  }
  /** The tooltip's lines of a record found in Aspen's window: between which times, and why. */
  function extTip(r) {
    if (!isExt(r)) return [];
    const s = Number(r.since);
    return [s > 0 ? t("tip_ext_when", when(s), when(r.t)) : t("tip_ext_found", when(r.t)), extWhy(r)].filter(Boolean);
  }

  /** How a run ended, in words ("converged, 2 warnings"). */
  function outcome(st, warns, errs) {
    if (st === "ok") return t("ch_o_ok");
    if (st === "warn") return warns ? tn("ch_o_warn", warns) : t("ch_o_warn_n");
    if (st === "error") return errs > 1 ? t("ch_o_errors_n", errs) : t("ch_o_error");
    if (st === "failed" || st === "refused") return t("ch_o_failed");
    return t("ch_o_unknown");
  }

  // ------------------------------------------------------------------ counts (WBC.tally)
  // One way to count change records, shared by every card's count line and the "while you
  // were away" line, so their numbers always agree; tools/report.py's tally counts the same
  // way (both answer fixtures/journal2b/expected_tally.json). Only records whose status is
  // "changed" count as values / additions / removals / connections / saves; runs are run
  // records that ran (ok, warn, error), "last" the latest by time -- a Reinitialize runs
  // nothing, so "Reinitialize, then Run" is one run; studies are loops and optimizations by
  // what they did; failed (or an error on anything but a run or a loop: it did not apply) and
  // refused apart; external, anything made in Aspen's own window.
  const NAMES_MAX = 3;                // names tally keeps per kind added or removed
  const RAN = new Set(["ok", "warn", "error"]);
  const RUN_OPS = new Set(["run", "reinit"]);
  function counter() {
    return { values: 0, connects: 0, saves: 0, failed: 0, refused: 0, external: 0, objs: new Set(),
             added: {}, removed: {}, studies: {}, runs: 0, last: null, over: 0 };
  }
  function count(c, r, over) {
    const op = r.op, st = r.status, tg = isObj(r.target) ? r.target : {};
    if (over) c.over++;
    if (r.actor === "external") c.external++;
    if (st === "refused") c.refused++;
    else if (st === "failed" || (st === "error" && !RUN_OPS.has(op) && op !== "summary")) c.failed++;
    else if (op === "run") {
      if (RAN.has(st)) {
        c.runs++;
        c.last = { status: st };
        ["errors", "warnings"].forEach((k) => { if (k in r) c.last[k] = r[k]; });
      }
    } else if (op === "reinit") return;           // (not a run of its own: the run after it is)
    else if (op === "summary") {
      const d = String(r.do || "loop");
      c.studies[d] = (c.studies[d] || 0) + 1;
    } else if (st !== "changed") return;
    else if (op === "value" || op === "attr") {
      c.values++;
      const kind = ["block", "stream"].find((k) => tg[k]);
      if (kind) c.objs.add(`${kind}:${String(tg[kind]).toUpperCase()}`);
    } else if (op === "add" || op === "remove") {
      const box = op === "add" ? c.added : c.removed, k = String(tg.kind || "item");
      const e = box[k] || (box[k] = { n: 0, names: [] });
      e.n++;
      if (tg.name && !e.names.includes(String(tg.name)) && e.names.length < NAMES_MAX) e.names.push(String(tg.name));
    } else if (op === "connect") c.connects++;
    else if (op === "save") c.saves++;
  }
  function counted(c, full, kinds) {
    const d = { values: c.values, objs: c.objs.size, added: c.added, removed: c.removed, connects: c.connects,
                runs: Object.assign({ n: c.runs }, c.last ? { last: c.last } : {}), studies: c.studies, saves: c.saves,
                failed: c.failed, refused: c.refused, external: c.external };
    if (c.over) d.overridden = c.over;             // (only when there are some: report.py's tally the same)
    if (kinds) {                                  // (the away line's words: blocks and streams apart)
      const ks = [...c.objs].map((k) => k.slice(0, k.indexOf(":")));
      Object.defineProperty(d, "kinds", { value: { block: ks.filter((k) => k === "block").length, stream: ks.filter((k) => k === "stream").length } });
    }
    if (full) return d;
    const out = {};
    Object.entries(d).forEach(([k, v]) => {
      if (!v || (isObj(v) && (!Object.keys(v).length || (k === "runs" && !v.n)))) return;
      out[k] = v;
    });
    if (kinds && Object.keys(out).length) Object.defineProperty(out, "kinds", { value: d.kinds });
    return out;
  }
  /** Oldest first, by (t, id). */
  const byKey = (a, b) => { const x = keyT(a), y = keyT(b); return x[0] - y[0] || (x[1] < y[1] ? -1 : x[1] > y[1] ? 1 : 0); };
  /** A value record's field, lower-cased (Aspen paths are case-insensitive), or "". */
  const vpath = (r) => (isObj(r) && r.op === "value" && r.status === "changed" && r.id && isObj(r.target) && r.target.path ? String(r.target.path).toLowerCase() : "");
  /** Map id -> the first later record that set the same field again, by someone else: a value one
   *  actor set that another changed afterwards (the AI putting back your edit made in Aspen's
   *  window). An undo of the record itself (its revert_of) is not one. Any order in;
   *  tools/report.py's overrides answers the same. */
  WBC.overrides = function (records) {
    const by = new Map(), out = new Map();
    (records || []).filter(vpath).sort(byKey).forEach((r) => {
      const p = vpath(r), rev = new Set(revIds(r));
      (by.get(p) || []).forEach((e) => { if (!out.has(e.id) && e.actor !== r.actor && !rev.has(String(e.id))) out.set(e.id, r); });
      if (!by.has(p)) by.set(p, []);
      by.get(p).push(r);
    });
    return out;
  };
  /** Counts of change records, whole and `by` actor (an actor with nothing
   *  to count left out; skip: actors left out entirely, default your own, "user"). Any order in.
   *  overridden (only when there are some): values another counted actor set again later.
   *  opt.kinds: each part also says (not enumerable) how many blocks and streams its values touched. */
  WBC.tally = function (records, skip, opt) {
    const sk = new Set(skip === undefined ? ["user"] : skip || []), kinds = !!(opt && opt.kinds);
    const recs = (records || []).filter((r) => isObj(r) && (r.kind === undefined || r.kind === "change") && !sk.has(String(r.actor || "unknown")));
    recs.sort(byKey);
    const top = counter(), by = new Map(), ov = WBC.overrides(recs);
    recs.forEach((r) => {
      const actor = String(r.actor || "unknown"), o = ov.has(r.id);
      count(top, r, o);
      if (!by.has(actor)) by.set(actor, counter());
      count(by.get(actor), r, o);
    });
    const out = counted(top, true, kinds);
    out.by = {};
    by.forEach((c, a) => { const o = counted(c, false, kinds); if (Object.keys(o).length) out.by[a] = o; });
    return out;
  };

  /** What a card did, counted (WBC.tally): values, blocks and streams added or removed,
   *  connections, runs and how the last ended, loops and optimizations (with their points or
   *  evaluations), saves...; what did not apply, apart. At most four parts, then "and more"
   *  (all: every part, for the card's tooltip). */
  function sumLine(c, all) {
    const T = WBC.tally(c.recs, []), n = {}, add = (k, x = 1) => { n[k] = (n[k] || 0) + x; };
    // what the count leaves to a card: a loop's points, an optimization's evaluations, a put
    // back, a layout, a file edited, a model opened or closed, an analysis
    c.recs.forEach((r) => {
      if (r.kind !== "change") return;
      const op = r.op, st = r.status;
      if (op === "summary") {
        if (st === "failed" || st === "refused") return;          // (counted as not applied)
        const d = r.do || "loop";
        if (d === "optimize") add("opt", Number((r.report || {}).evaluations) || Number((r.runs || {}).n) || 0);
        else if (d === "sweep") add("sweep", Number((r.runs || {}).n) || Number(r.n) || 0);
        else if (d === "seek") add("seek", Number((r.runs || {}).n) || Number(r.n) || 0);
        else add("loop", Number((r.runs || {}).n) || Number(r.n) || 0);
      } else if (op === "restore" && cpRestore(r)) { if (st === "changed") add("rs_cp"); }   // (a restore point put back)
      else if (op === "restore" && !BAD.has(st)) add("restore", Number(r.n) || Object.keys(r.writes || {}).length);
      else if (op === "checkpoint" && st === "changed" && !r.reuse) add("cp");
      else if (op === "reinit" && st === "ok") add("reinit");
      else if (st !== "changed") return;
      else if (op === "patch") add(r.tool === "layout_flowsheet" ? "layout" : "patch");
      else if (op === "open" || op === "close" || op === "analysis") add(op);
    });
    const parts = [], kinds = (box, pre) => {
      const other = Object.entries(box).reduce((s, [k, e]) => s + (k === "block" || k === "stream" ? 0 : e.n), 0);
      [["block", (box.block || {}).n], ["stream", (box.stream || {}).n], ["other", other]].forEach(([k, x]) => { if (x) parts.push(tn(`ch_s_${pre}_${k}`, x)); });
    };
    if (T.values) parts.push(tn("ch_s_values", T.values));
    kinds(T.added, "add");
    kinds(T.removed, "rm");
    if (T.connects) parts.push(tn("ch_s_connect", T.connects));
    if (T.runs.n) {
      const last = T.runs.last || {}, how = outcome(last.status, Number(last.warnings) || 0, Number(last.errors) || 0);
      parts.push(t(T.runs.n > 1 ? "ch_s_run_last" : "ch_s_run_out", tn("ch_s_runs", T.runs.n), how));
    } else if (n.reinit) parts.push(t("ch_s_reinit"));   // (with a run after it: part of that run)
    ["sweep", "seek", "loop", "opt", "restore"].forEach((k) => { if (k in n) parts.push(tn(`ch_s_${k}`, n[k])); });
    if (n.rs_cp) parts.push(t("ch_s_rs_cp"));
    if (n.cp) parts.push(tn("ch_s_cp", n.cp));
    if (T.saves) parts.push(t("ch_s_save"));
    ["layout", "patch", "open", "close", "analysis"].forEach((k) => { if (n[k]) parts.push(t(`ch_s_${k}`)); });
    if (T.failed + T.refused) parts.push(tn("ch_s_bad", T.failed + T.refused));
    if (!parts.length) return c.recs.some((r) => r.kind === "begin") ? t("ch_s_begun") : t("ch_s_none");
    return parts.length > 4 && !all ? parts.slice(0, 4).join(t("ch_s_sep")) + t("ch_s_etc") : parts.join(t("ch_s_sep"));
  }

  /** A header's own title, as the cards show it. A diagnosis group's (source "diagnose") is
   *  stored as the server's fixed prefix, then the failing blocks: the prefix is shown in the
   *  window's language. Older journals stored the Chinese prefix, newer ones the English. */
  const DIAG_PREFIX = /^(?:診斷與修正|Diagnose and fix)\s*(?:[：:]\s*)?/;
  function ownTitle(h) {
    const s = String(h.title);
    if (h.source !== "diagnose" || !DIAG_PREFIX.test(s)) return s;
    const rest = s.replace(DIAG_PREFIX, "");
    return rest ? t("diag_group_title_of", rest) : t("diag_group_title");
  }

  function titleOf(c) {
    const h = c.head || {};
    if (h.title) return ownTitle(h);
    if (c.alt) return c.alt;
    if (c.actor === "external" && c.recs.length && c.recs.every(isExt)) return t("ch_title_aspen");
    return t(`ch_title_${ACT[c.actor] ? c.actor : "external"}`);
  }
  function whoHtml(actor, small) {
    const a = ACT[actor] ? actor : "external";
    return `<span class="ch-who a-${a}${small ? " sm" : ""}" title="${esc(t(`tip_who_${a}`))}">${icon(ACT[a])}<span>${esc(t(`ch_who_${a}`))}</span></span>`;
  }

  // ------------------------------------------------------------------ rows
  /** One record's line: what it did, in the page's words. */
  function what(r, types, badge) {
    const op = r.op, st = r.status, tg = r.target || {};
    const type = (tg.block && types[tg.block]) || tg.type || null;
    if (r.kind === "begin") return esc(t("ch_r_begin", r.tool || r.do || "?"));
    if (op === "brake") return brakeLine(r);           // (the brakes' records)
    if (op === "proposal") return proposalLine(r, types);
    if (isGate(r)) return gateLine(r, types);
    if (op === "value" || op === "attr") {
      const name = field(tg.path, r.loc, type) + (op === "attr" ? ` <small class="ch-q">${esc(t("ch_r_attr", tg.attr))}</small>` : "");
      if (BAD.has(st)) return `${name} → ${valHtml(r.req)}`;
      if (st === "changed" && "before" in r) return `${extPre(r)}${name} ${change(r.before, r.after)}`;
      return `${name} = ${valHtml(r.after || r.req, true)}<small class="ch-q">${esc(t(r.created ? "ch_r_created" : "ch_r_same"))}</small>`;
    }
    if (op === "add" || op === "remove") {
      const name = `${tg.name || base(tg.path)}${tg.type ? ` (${tg.type})` : ""}`;
      if (isExt(r)) return esc(t(op === "add" ? "ext_add" : "ext_rm", kindWord(tg.kind), name, when(r.t)));
      const p = String(tg.path || "").split("\\");   // a list's row: under its field; a subobject: its collection
      if (tg.kind === "row" && p.length > 2) return `${field(p.slice(0, -1).join("\\"), null, type)} ${esc(t(op === "add" ? "ch_r_add" : "ch_r_remove", kindWord("row"), tg.name))}`;
      return esc(t(op === "add" ? "ch_r_add" : "ch_r_remove", kindWord(tg.kind), tg.kind === "element" ? p.slice(-2).join(" ") : name));
    }
    if (op === "connect") {
      const where = [tg.block, tg.port || tg.field].filter(Boolean).join(" ");
      const s = tg.stream || (Array.isArray(r.after) ? r.after.join(t("ch_s_sep")) : "");
      if (r.detached) {                             // a refused connect that still took the stream off its port
        const a = isObj(r.asked) ? r.asked : {};
        return esc(t("ch_r_detached", s, where, [a.block, a.port].filter(Boolean).join(" ") || "?"));
      }
      // a disconnect (disconnect_stream, a program's, an undo's): the stream on the port before, not after
      const up = (x) => String(x == null ? "" : x).toUpperCase();
      const had = (k) => Array.isArray(r[k]) && r[k].some((x) => up(x) === up(tg.stream));
      if (tg.stream && had("before") && !had("after")) return esc(t("ch_r_disconnect", tg.stream, where));
      const gone = Array.isArray(r.displaced) && r.displaced.length ? t("ch_r_displaced", r.displaced.join(t("ch_s_sep"))) : "";
      return esc(t("ch_r_connect", s, where) + gone);
    }
    if (op === "run" || op === "reinit") {
      const blocks = r.blocks && typeof r.blocks === "object" ? Object.keys(r.blocks) : [];
      const how = op === "reinit" ? (st === "ok" ? t("ch_o_done") : t("ch_o_failed")) : outcome(st, Number(r.warnings) || 0, Number(r.errors) || 0);
      const ext = isExt(r) && op === "run";      // (a run started in Aspen's own window)
      let s = esc(measured(r) ? t(ext ? "ext_run_seq" : "rc_run", r.seq, how) : t(ext ? "ext_run" : op === "run" ? "ch_r_run" : "ch_r_reinit", how));
      if (blocks.length) s += ` <span class="ch-blk">· ${blocks.slice(0, 6).map((b) => `<span class="go" data-obj="block:${esc(b)}" title="${esc(t("tip_ch_go"))}">${esc(b)}</span>`).join(esc(t("ch_s_sep")))}${blocks.length > 6 ? "…" : ""}</span>`;
      if (r.secs) s += ` <small class="ch-q">${esc(t("ch_r_secs", Math.round(r.secs)))}</small>`;
      return s;
    }
    if (op === "restore" && cpRestore(r)) {         // the model put back to a restore point
      const n = tg.name || cpWords(tg.reason);
      return esc(t(st === "changed" ? "ch_r_restore_cp" : "ch_r_restore_cp_not", n, typeof tg.t === "number" ? when(tg.t) : "?"));
    }
    if (op === "summary" || op === "restore") return loop(r, types, badge);
    if (op === "save") {
      const w = Array.isArray(r.writes) ? r.writes[0] || {} : {};
      if (st === "failed") return esc(t("ch_r_save_fail", base(w.path || tg.path || r.file)));
      if (isExt(r)) return esc(t("ext_save", base(w.path || tg.path || r.file)));
      return esc(t("ch_r_save", base(w.path || tg.path || r.file)) + (w.backup ? t("ch_r_backup") : ""));
    }
    if (op === "checkpoint") return milestone(r);
    if (op === "patch") return esc(t(r.tool === "layout_flowsheet" ? "ch_r_layout" : "ch_r_patch") + (r.reopened ? t("ch_r_reopen") : ""));
    if (op === "open" || op === "close") return esc(t(`ch_r_${op}`, base(r.file || r.session)));
    if (op === "analysis") return esc(t("ch_r_pinch"));
    return esc(t("ch_r_call", r.tool || op || "?"));
  }
  /** A loop's or an optimization's one record: what it varied and how many times, how the
   *  runs went, where it left the model. badge: the row already says who (an optimizer's
   *  badge: its algorithm, not the word again). */
  function loop(r, types, badge) {
    const tg = r.target || {}, rep = r.report || {}, runs = r.runs || {}, d = r.do || "loop";
    const type = (tg.block && types[tg.block]) || tg.type || null;
    const ws = r.writes && typeof r.writes === "object" && !Array.isArray(r.writes) ? r.writes : {};
    const own = tg.path && ws[tg.path];
    const name = tg.path ? field(tg.path, r.loc, type) : "";
    let s;
    if (r.op === "restore") s = esc(tn("ch_r_restore", Number(r.n) || Object.keys(ws).length));
    else if (d === "optimize") s = esc(t(badge ? "ch_r_alg" : "ch_r_opt", rep.algorithm || "—"));
    else if (!name) s = esc(t("ch_r_loop_n"));
    else s = th(`ch_r_${["sweep", "seek"].includes(d) ? d : "loop"}`, name);
    const bits = [];
    const unit = own && own.after && own.after.unit ? ` ${own.after.unit}` : "";
    if (d === "sweep" && Array.isArray(r.range) && r.range.length === 2) bits.push(`${numText(r.range[0])}–${numText(r.range[1])}${unit}`);
    if (d === "optimize" && rep.evaluations != null) bits.push(tn("ch_r_evals", rep.evaluations));
    if (d === "optimize" && rep.feasible != null) bits.push(t("ch_r_feasible", rep.feasible));
    if (d !== "optimize" && r.op !== "restore" && runs.n) bits.push(tn(d === "sweep" ? "ch_r_points" : "ch_r_runs", runs.n));
    if (runs.n) bits.push(t("ch_r_conv", (runs.ok || 0) + (runs.warn || 0)));
    if (d === "optimize" && rep.finish) bits.push(t(`ch_fin_${["restore", "best", "last"].includes(rep.finish) ? rep.finish : "last"}`));
    else if (own && own.after && r.op !== "restore") bits.push(t("ch_r_end", val(own.after) + (own.after.unit ? ` ${own.after.unit}` : "")));
    if (bits.length) s += ` <span class="ch-q">· ${esc(bits.join(" · "))}</span>`;
    return s;
  }
  /** The fields a loop or an optimization left changed, under its line: at most SUB. */
  function subLines(r, types) {
    const ws = r.writes && typeof r.writes === "object" && !Array.isArray(r.writes) ? r.writes : null;
    if (!ws || (r.op !== "summary" && r.op !== "restore")) return "";
    const tg = r.target || {}, skipOwn = r.op === "summary" && r.do !== "optimize";   // (its own line says it)
    const list = Object.entries(ws).filter(([p, w]) => w && typeof w === "object" && !(skipOwn && p === tg.path));
    if (!list.length) return "";
    const shown = list.slice(0, SUB).map(([p, w]) => {
      const path = p.split("#")[0], blk = /^\\Data\\Blocks\\([^\\]+)/.exec(path);
      const type = blk ? types[blk[1]] : null, obj = PATH_OBJ.exec(path);
      const go = obj ? ` go" data-obj="${esc(`${/^b/i.test(obj[1]) ? "block" : "stream"}:${obj[2]}`)}" data-path="${esc(path)}" title="${esc(t("tip_ch_go_field"))}` : "";
      return `<div class="ch-sub${go}">${field(path, null, type)} ${w.status === "changed" ? change(w.before, w.after) : `= ${valHtml(w.after, true)}`}</div>`;
    });
    if (list.length > SUB) shown.push(`<div class="ch-sub ch-q">${esc(t("ch_r_wmore", list.length - SUB))}</div>`);
    return shown.join("");
  }
  /** Aspen's own lines of a run that did not end cleanly, and a failure's answer. */
  function errLines(r) {
    const out = [];
    const lines = Array.isArray(r.msgs) ? r.msgs : typeof r.msgs === "string" ? r.msgs.split("\n") : [];
    const keep = lines.map((x) => String(x).trimEnd()).filter((x) => x.trim());
    if (keep.length && (r.op === "run" || r.op === "reinit") && r.status !== "ok") {
      out.push(`<pre class="ch-msgs${r.status === "warn" ? " warn" : ""}">${esc(keep.slice(0, 4).join("\n"))}${keep.length > 4 ? "\n…" : ""}</pre>`);
    }
    if (r.result && !isGate(r) && (BAD.has(r.status) || (r.op === "run" && r.status !== "ok" && !keep.length))) {   // (the brakes' refusal: its line says it)
      // a known refusal in the window's own words, the server's sentence in the tooltip (diag.js)
      const ref = window.WBD && WBD.refusal ? WBD.refusal(r.result) : null;
      out.push(ref ? `<div class="ch-err" title="${esc(String(r.result))}">${esc(t("ch_r_why", ref.words))}</div>`
        : `<div class="ch-err" title="${esc(String(r.result))}">${esc(t("ch_r_said"))}${rich(r.result, 160)}</div>`);
    }
    return out.join("");
  }
  // ------------------------------------------------------------------ the brakes
  // A call the brakes did not let in (op call, refused, gate.why): what the AI wanted and why it
  // did not go in -- refused in Observe (the eye), held by a pause, a confirmation card and what
  // became of it since (declined with your note, approved, still waiting, applied later by you).
  // A change that went through them says how (you confirmed #12, let through for the request,
  // done while the window was closed); one you applied later carries "AI proposed, you did it
  // #12", a click going to the AI's request. The brakes' own records (op brake: the mode, a
  // pause, a resume, an automatic pause) and a proposal declined later are milestone lines.
  const CARD_WHY = new Set(["declined", "timeout", "window_closed", "expired", "late", "dup", "joined"]);
  const isGate = (r) => r.op === "call" && isObj(r.gate) && !!r.gate.why;
  const isCardGate = (r) => isGate(r) && r.gate.card != null && CARD_WHY.has(r.gate.why);
  const gIcon = (n, cls) => `<svg class="ic ch-gi${cls ? ` ${cls}` : ""}" aria-hidden="true"><use href="#i-${n}"/></svg>`;
  let gateM = null;                   // the timeline the rows are drawn from: a card's later fate is looked up in it
  /** What the AI wanted, as a verb phrase (html): set ESTCOL › Reflux ratio → 2.5, delete block B4. */
  function actWords(r, types) {
    const tool = String(r.tool || ""), tg = isObj(r.target) ? r.target : {}, a = isObj(r.args) ? r.args : {};
    if (tg.path && /^set_(value|node_attribute)$/.test(tool)) {
      const type = (tg.block && types[tg.block]) || null, v = a.value;
      const to = v === undefined || v === null || typeof v === "object" ? "" : ` → <b>${esc(numText(v))}</b>`;
      return th("gt_set", field(tg.path, r.loc, type) + to) + (Number(tg.n) > 1 ? esc(t("gt_more", Number(tg.n) - 1)) : "");
    }
    const k = `bkc_t_${tool}`, name = tg.block || tg.stream || tg.component || tg.rxnset || tg.file || tg.tab || tg.name || "";
    if (tool === "close_aspen_plus") return esc(a.session_name ? t(k, base(a.session_name)) : t("bkc_t_close_all"));
    if (tool === "remove_reaction") return esc(t(k, tg.rxnset || "?", a.reaction_no ?? "?"));
    if (/^remove_(side_duty|element|row)$/.test(tool)) return esc(t("bkc_t_remove_item"));
    if (tool === "create_new_simulation") return esc(t(k, a.project_name || name || "?"));
    if (I18N.t(k) !== k) return esc(t(k, name || "?"));
    return esc(t("bkc_t_other", [tool || "?", name].filter(Boolean).join(" · ")));
  }
  /** What became of card `id` later: a record of the timeline (applied by you, declined), else
   *  the brakes' state (still waiting...); [key, comment] or null. */
  function laterFate(id) {
    const M = gateM, all = M && (M.actors || M.obj) ? store.get(`${M.id}\n\n`) : null;
    for (const recs of [M && M.recs, all && all.loaded ? all.recs : null]) {
      for (const x of recs || []) {
        if (x.kind !== "change") continue;
        if (x.op === "proposal" && Number(x.card) === id) return ["gt_f_declined_l", x.comment];
        if (isObj(x.proposed) && Number(x.proposed.card) === id && x.status === "changed") return ["gt_f_applied"];
      }
    }
    const b = feature("brake") && window.wb && wb.state && isObj(wb.state.brake) ? wb.state.brake : null;
    const c = b && Array.isArray(b.cards) ? b.cards.find((x) => isObj(x) && Number(x.id) === id) : null;
    if (!c) return null;
    if (["waiting", "timeout", "cancelled"].includes(c.status)) return ["gt_f_waiting"];
    if (c.status === "declined") return ["gt_f_declined_l", isObj(c.decided) ? c.decided.comment : null];
    return { applying: ["gt_f_applying"], applied: ["gt_f_applied"], expired: ["gt_f_expired"] }[c.status] || null;
  }
  /** " → declined: …", " → pending"...: what became of a card row's proposal. */
  function fateWords(r) {
    const g = r.gate, why = g.why;
    if (why === "declined") return g.comment ? t("gt_f_declined", g.comment) : t("gt_f_declined0");
    if (why === "late") return t("gt_f_approved");
    const f = laterFate(Number(g.card));
    if (f) return f[0] === "gt_f_declined_l" ? (f[1] ? t("gt_f_declined_l", f[1]) : t("gt_f_declined_l0")) : t(f[0]);
    return t({ window_closed: "gt_f_closed", expired: "gt_f_expired", dup: "gt_f_dup", joined: "gt_f_joined" }[why] || "gt_f_timeout");
  }
  function gateLine(r, types) {
    const g = r.gate, why = g.why;
    if (isCardGate(r)) return `${gIcon("warn", "card")}${th("gt_card", actWords(r, types), esc(String(g.card)))}<span class="ch-fate">${esc(fateWords(r))}</span>`;
    const k = { observe: "gt_observe", paused: "gt_paused", stuck: "gt_stuck", changed: "gt_changed", window_closed: "gt_closed", late: "gt_late" }[why] || "gt_not";
    return `${gIcon(why === "observe" ? "eye" : "pause", why === "observe" ? "obs" : "pause")}${th("gt_want", actWords(r, types))}<small class="ch-q">${esc(t(k))}</small>`;
  }
  let deadNow = null;                 // the drawn timeline's deleted proposal records (deadOf), for propTab
  /** The proposals whose record the user deleted, as the timeline M (and its unfiltered whole)
   *  records it (op proposal, status deleted): their ids and tab ids. */
  function deadOf(M) {
    if (!M) return null;
    const all = M.actors || M.obj ? store.get(`${M.id}\n\n`) : null, n = M.recs.length + (all && all.loaded ? all.recs.length : 0);
    if (M._dead && M._deadN === n) return M._dead;
    const out = new Set();
    for (const recs of [M.recs, all && all.loaded ? all.recs : null]) {
      for (const x of recs || []) {
        if (x.kind === "change" && x.op === "proposal" && x.status === "deleted") { if (x.proposal) out.add(x.proposal); if (x.tab) out.add(x.tab); }
      }
    }
    M._dead = out; M._deadN = n;
    return out;
  }
  /** Where the AI's proposal pid is now (tid: the tab it was on): its tab while one
   *  holds it, kept in History, or its record deleted (app-core.js propWhere); null where
   *  the window has no way to it. */
  function propTab(pid, tid) {
    if (window.WBA && typeof WBA.propWhere === "function") return WBA.propWhere(pid, tid, deadNow);
    const tabs = window.wb && wb.state && Array.isArray(wb.state.tabs) ? wb.state.tabs : [];
    const isProp = (x) => isObj(x) && x.kind === "proposal" && isObj(x.proposal);
    const x = (pid && tabs.find((y) => isProp(y) && y.proposal.id === pid)) || (tid && tabs.find((y) => isProp(y) && y.id === tid));
    return x ? { state: "loaded", tab: x.id } : null;
  }
  const ptabKey = (w) => (w ? `${w.state}:${w.tab || ""}` : "-");
  /** The way to a proposal (where: propTab's): its tab while loaded, from History while kept
   *  there, greyed out once its record is deleted -- ✦, or "Open the proposal" where label. */
  function ptabBtn(where, cls, label) {
    if (!where) return "";
    const face = label ? esc(t("gt_ptab")) : icon("sparkle");
    if (where.state === "gone") return ` <button class="${cls} flat off" data-c="ptab" aria-disabled="true" title="${esc(t("ch_ptab_gone"))}">${face}</button>`;
    const hist = where.state === "hist";
    return ` <button class="${cls} flat" data-c="ptab" data-tab="${esc(where.tab)}"${hist ? ' data-hist="1"' : ""}`
      + ` title="${esc(t(hist ? "tip_ch_ptab_hist" : label ? "tip_gt_ptab" : "tip_ch_ptab"))}">${face}</button>`;
  }
  /** A proposal you declined after its call had ended (op proposal): a milestone. A proposal tab
   *  you sent back (op proposal with its proposal id, status rejected) is one too,
   *  with your comment and a way to its tab while it is open. */
  function proposalLine(r, types) {
    if (r.proposal && r.status === "deleted") return `${gIcon("sparkle", "prop")}${esc(t("gt_prop_deleted", r.title || "?"))}`;
    if (r.proposal) {
      return `${gIcon("sparkle", "prop")}${esc(t("gt_prop_sent", r.title || "?"))}`
        + `${r.comment ? `<span class="ch-fate">${esc(t("gt_prop_said", r.comment))}</span>` : ""}${ptabBtn(propTab(r.proposal, r.tab), "ch-link", true)}`;
    }
    const go = isObj(r.proposed) && r.proposed.group
      ? ` <button class="ch-link flat" data-c="prop" data-g="${esc(r.proposed.group)}" title="${esc(t("tip_gt_prop"))}">${esc(t("gt_prop_go"))}</button>` : "";
    return `${gIcon("warn", "card")}${th("gt_card_ai", actWords(r, types), esc(String(r.card ?? "?")))}`
      + `<span class="ch-fate">${esc(r.comment ? t("gt_f_declined", r.comment) : t("gt_f_declined0"))}</span>${go}`;
  }
  /** The brakes' own records (op brake), in words. */
  function brakeLine(r) {
    const w = r.what, d = isObj(r.detail) ? r.detail : {};
    if (w === "mode") return gIcon("shield", "mode") + esc(t("gm_mode", t(`aim_${["observe", "risk", "auto"].includes(r.mode) ? r.mode : "risk"}_full`)));
    if (w === "pause") return gIcon("pause", "pause") + esc(t("ai_paused"));
    if (w === "resume") {
      if (r.by === "window_closed") return gIcon("play", "go") + esc(t("gm_resume_closed"));
      const n = Number(r.changes) || 0;
      return gIcon("play", "go") + esc((n ? tn("gm_resume_n", n) : t("ai_resumed")) + (r.note ? t("gm_note", r.note) : ""));
    }
    if (w === "stuck") {
      const why = isObj(d.why) && (d.why[I18N.lang] || d.why.en) ? String(d.why[I18N.lang] || d.why.en)
        : ["runs", "field", "revert"].includes(r.rule) ? t(`rule_${r.rule}`, d.n ?? "", d.field || d.path || "") : t("autopaused0");
      return gIcon("pause", "stuck") + esc(t(r.fallback ? "gm_stuck_nowin" : "gm_stuck", why));
    }
    return esc(t("ch_r_call", "brake"));
  }
  /** How a change went through the brakes, after its line: “Approved #12”, allowed, done while closed. */
  function gateTag(r) {
    const g = isObj(r.gate) && !isGate(r) ? r.gate : null;
    const words = !g ? "" : g.confirmed ? t("gt_confirmed", g.card) : g.allowed ? t("gt_allowed") : g.fallback ? t("gt_fallback") : g.resumed ? t("gt_resumed") : "";
    return words ? ` <small class="ch-gtag${g.fallback ? " off" : ""}">${esc(words)}</small>` : "";
  }
  /** "Approved after timeout #12" on a change you applied after the AI's call had ended: a click goes to its request. */
  function propTag(r) {
    const p = isObj(r.proposed) ? r.proposed : null;
    if (!p || p.card == null || r.op === "proposal" || r.op === "checkpoint") return "";
    return ` <button class="ch-prop flat" data-c="prop" data-g="${esc(p.group || "")}" title="${esc(t("tip_gt_prop"))}">${esc(t("gt_prop", p.card))}</button>`;
  }
  /** “While paused” on a value set by hand while a program was paused before a step (the
   *  record's paused_at, the step it waited before); its tooltip says when. */
  function pausedTag(r) {
    return r.paused_at ? ` <small class="ch-gtag ch-ptag" title="${esc(t("tip_ch_paused", stamp(r.t)))}">${esc(t("ch_paused"))}</small>` : "";
  }
  /** A milestone of the brakes: one line at its time, no card around it. */
  function mileHtml(c) {
    const r = c.recs[0] || {}, tip = [stamp(r.t), who(r.actor === "ai" || r.actor === "user" ? r.actor : "user"), r.gate && r.gate.held_s ? t("gt_held", Math.round(r.gate.held_s)) : ""].filter(Boolean).join("\n");
    return `<div class="ch-mile${r.op === "proposal" ? " prop" : ""}" data-key="${esc(c.key)}" title="${esc(tip)}"><span class="ch-rt">${hhmm(r.t)}</span> `
      + `<span class="ch-rx">${what(r, {}, false)}</span></div>`;
  }

  // ------------------------------------------------------------------ what a run changed
  // A run the server measured (the record's seq, inputs, delta):
  // under its line, one more that opens onto the inputs changed since the run before and the
  // results that moved, the newest run open by itself. Arrows say only which way (never red or
  // green: larger is not worse). Inputs changed together cannot be told apart: a button opens a
  // program tab that sweeps each one alone (the window's own tab_new and program events).
  const RC_SHOW = 5;                  // results listed before "show N more"
  const RC_READS = 5;                 // results the one-at-a-time program reads after each run
  const rcSig = (ctx) => `${ctx.connected ? 1 : 0}${typeof ctx.newTab === "function" ? 1 : 0}`;   // what the button depends on
  const measured = (r) => !!r && r.op === "run" && typeof r.seq === "number";
  const numOf = (v) => (typeof v === "number" && isFinite(v) ? v
    : typeof v === "string" && v.trim() !== "" && isFinite(Number(v)) ? Number(v) : null);
  /** Two results in as few digits as tell them apart (at least 4, the whole integer part). */
  function pair(b, a) {
    const x = numOf(b), y = numOf(a), word = (v) => (v == null || v === "" ? t("ch_empty_v") : String(v));
    if (x === null || y === null) return [word(b), word(a)];
    const big = Math.max(Math.abs(x), Math.abs(y));
    return apart(x, y, Math.min(12, Math.max(4, big >= 1 ? Math.floor(Math.log10(big)) + 1 : 4)), 12).map(String);
  }
  const arrow = (b, a) => { const x = numOf(b), y = numOf(a); return x === null || y === null || x === y ? "" : y > x ? "▲" : "▼"; };
  const typeAt = (p, types) => { const m = /^\\Data\\Blocks\\([^\\]+)/i.exec(p); return m ? types[m[1]] || null : null; };
  const goAt = (p, field) => {
    const m = PATH_OBJ.exec(p);
    return m ? ` go" data-obj="${esc(`${/^b/i.test(m[1]) ? "block" : "stream"}:${m[2]}`)}"${field ? ` data-path="${esc(p)}"` : ""}` : `"`;
  };
  /** A result that moved: "PRODUCT › Temperature 180.2 → 183.9 C ▲" (a tiny one quieter). */
  function movedHtml(it, types) {
    const p = String(it.path || ""), [b, a] = pair(it.b, it.a), ar = arrow(it.b, it.a);
    return `${field(p, null, typeAt(p, types))} <span class="ch-v"><b>${esc(b)}</b> → <b>${esc(a)}</b>`
      + `${it.u ? ` <small>${esc(it.u)}</small>` : ""}${ar ? `<i class="rc-ar">${ar}</i>` : ""}</span>`;
  }
  /** An input changed since the run before: its value then and now, and who changed it. */
  function inputHtml(it, types) {
    const p = String(it.path || "");
    return `<div class="rc-r${goAt(p, true)} title="${esc(PATH_OBJ.test(p) ? `${p}\n${t("tip_ch_go_field")}` : p)}">${field(p, null, typeAt(p, types))} `
      + `${change(it.before, it.after)} <small class="ch-q">· ${esc(who(it.actor))}</small></div>`;
  }
  /** A block, stream or connection added or removed since the run before. */
  function objHtml(o) {
    const name = o.name || base(o.path), port = /\\Blocks\\([^\\]+)\\Ports\\([^\\]+)/i.exec(String(o.path || ""));
    const s = o.op === "connect" ? t("ch_r_connect", o.stream || "—", port ? `${port[1]} ${port[2]}` : base(o.path))
      : t(o.op === "remove" ? "ch_r_remove" : "ch_r_add", kindWord(o.kind), name);
    const go = o.op === "add" && (o.kind === "block" || o.kind === "stream") && o.name;
    return `<div class="rc-r${go ? ` go" data-obj="${esc(`${o.kind}:${o.name}`)}" title="${esc(t("tip_ch_go"))}` : ""}">${esc(s)}</div>`;
  }
  /** What the one-at-a-time program can sweep (numeric inputs) and what it says it skips. */
  function ofatOf(r) {
    const inp = r.inputs && typeof r.inputs === "object" ? r.inputs : {}, objs = Array.isArray(inp.objs) ? inp.objs : [];
    const sweeps = [], skips = [];
    (Array.isArray(inp.items) ? inp.items : []).forEach((it) => {
      const b = it.before || {}, a = it.after || {}, x = numOf(b.value), y = numOf(a.value), p = String(it.path || "");
      const label = window.WBL ? WBL.say(p) : base(p);
      if (it.op === "attr" || x === null || y === null) skips.push(t("rc_ofat_skip_text", label));
      else if (b.unit && a.unit && b.unit !== a.unit) skips.push(t("rc_ofat_skip_unit", label, b.unit, a.unit));
      else if (x === y) skips.push(t("rc_ofat_skip_same", label));
      else sweeps.push({ path: p, x, y, unit: a.unit || b.unit || null, label });
    });
    objs.forEach((o) => skips.push(t("rc_ofat_skip_obj", o.name || o.stream || base(o.path) || "?")));
    const hidden = (Number(inp.more) || 0) + Math.max(0, (Number(inp.struct) || 0) - objs.length);
    if (hidden > 0) skips.push(t("rc_ofat_skip_more", hidden));
    return { sweeps, skips };
  }
  /** A variable name out of a path (ESTCOL_BASIS_RR), not one used yet. */
  function varName(p, used) {
    let s = String(p || "").split("\\").filter((x) => x && !/^(Data|Blocks|Streams|Input|Output)$/i.test(x)).join("_")
      .replace(/[^A-Za-z0-9_]+/g, "_").replace(/_+/g, "_").replace(/^_|_$/g, "").slice(0, 40) || "v";
    if (/^[0-9]/.test(s)) s = `s_${s}`;
    let n = s, k = 2;
    while (used.has(n.toLowerCase())) n = `${s}_${k++}`;
    used.add(n.toLowerCase());
    return n;
  }
  /** The program: a note on how it works, what it skips, then per numeric input a sweep from
   *  its value before the run to its value now (2 points), each point run and the results that
   *  moved most read. Each sweep ends at the value now; the program puts every input back. */
  function ofatProgram(r) {
    const { sweeps, skips } = ofatOf(r), used = new Set(["sweep_value", "last_run_ok"]);
    const d = r.delta && typeof r.delta === "object" ? r.delta : {};
    const reads = (Array.isArray(d.items) ? d.items : []).filter((it) => it && it.path && !it.small).slice(0, RC_READS)
      .map((it) => ({ do: "read", path: String(it.path), as: varName(it.path, used) }));
    const prog = [{ do: "log", text: t("rc_ofat_log", r.seq) }].concat(skips.map((s) => ({ do: "log", text: s })));
    sweeps.forEach((s) => {
      const st = { do: "sweep", path: s.path, from: s.x, to: s.y, steps: 2, as: varName(s.path, used),
                   why: t("rc_ofat_why", s.label, numText(s.x), numText(s.y)).slice(0, 300),
                   body: [{ do: "run" }].concat(reads.map((q) => Object.assign({}, q))) };
      if (s.unit) st.unit = s.unit;
      prog.push(st);
    });
    return prog;
  }
  /** A measured run's parts: its inputs, its delta, the results listed, whether it failed. */
  function runParts(r) {
    const inp = r.inputs && typeof r.inputs === "object" ? r.inputs : {}, d = r.delta && typeof r.delta === "object" ? r.delta : null;
    return { inp, d, n: Number(inp.n) || 0, items: Array.isArray(inp.items) ? inp.items : [], objs: Array.isArray(inp.objs) ? inp.objs : [],
             ds: d && Array.isArray(d.items) ? d.items.filter((it) => it && it.path) : [], failed: r.status === "error" && !d };   // (an error run keeps its delta: Aspen kept its results)
  }
  /** The line under a measured run ("3 inputs changed since the last run · PRODUCT › Temperature
   *  180.2 → 183.9 C ▲"), and, opened, what it opens onto (rcBody). */
  function runCard(r, M, types, ctx) {
    const { inp, d, n, ds, failed } = runParts(r), open = !!M.rc.get(r.id), id = esc(r.id);
    const inWord = !n ? t("rc_in0") : inp.full ? t("rc_inN_more", n) : n === 1 ? t("rc_in1") : t("rc_inN", n);
    const res = failed ? esc(t("rc_s_failed")) : !d ? "" : d.first ? esc(t("rc_s_first")) : ds.length ? movedHtml(ds[0], types) : esc(t("rc_s_same"));
    return `<div class="rc${open ? " open" : ""}" data-id="${id}"><button class="rc-tog flat" data-c="rc" data-id="${id}" aria-expanded="${open}"`
      + ` title="${esc(t("tip_rc_tog"))}">${icon("chevron-right").replace('class="ic"', 'class="ic chev"')}`
      + `<span class="rc-sum">${esc(inWord)}${res ? ` · ${res}` : ""}</span></button><div class="rc-body">${open ? rcBody(r, M, types, ctx) : ""}</div></div>`;
  }
  /** An opened run: the inputs changed since the run before (who changed each), whether they
   *  can be told apart, then the results that moved (RC_SHOW, then all) or why none are. */
  function rcBody(r, M, types, ctx) {
    const { inp, d, n, items, objs, ds, failed } = runParts(r), id = esc(r.id);
    let body = "";
    // what changed since the run before
    const noise = !n && d && !d.first && (Number(d.n) || 0) > 0 ? ` ${t("rc_noise")}` : "";
    body += `<div class="rc-h">${esc(!n ? t("rc_h_in0") + noise : n === 1 ? t("rc_h_in1") : t("rc_h_inN", inp.full ? `${n}+` : n))}</div>`;
    body += items.map((it) => inputHtml(it, types)).join("") + objs.map(objHtml).join("");
    const more = Number(inp.more) || 0, struct = Math.max(0, (Number(inp.struct) || 0) - objs.length);
    if (more > 0) body += `<div class="rc-note">${esc(tn("rc_i_more", more))}</div>`;
    if (struct > 0) body += `<div class="rc-note">${esc(tn("rc_i_struct", struct))}</div>`;
    if (typeof inp.joint === "boolean" ? inp.joint : n > 1) {
      const k = ofatOf(r).sweeps.length, can = k > 0 && typeof ctx.newTab === "function" && !!ctx.model;
      const btn = can ? `<button class="rc-ofat" data-c="ofat" data-id="${id}"${ctx.connected ? "" : " disabled"}`
        + ` title="${esc(ctx.connected ? t("tip_rc_ofat", 2 * k) : t("why_off"))}">${esc(t("rc_ofat"))}</button>` : "";
      body += `<div class="rc-joint"><span>${esc(t("rc_joint"))}</span>${btn}</div>`;
    }
    // what moved in the results
    if (failed) body += `<div class="rc-note">${esc(t("rc_failed"))}</div>`;
    else if (d && d.first) body += `<div class="rc-note">${esc(t("rc_first"))}</div>`;
    else if (d && !ds.length) body += `<div class="rc-note">${esc(t("rc_res_none", Number(d.read) || 0))}</div>`;
    else if (d) {
      const all = M.rcAll.has(r.id), shown = all ? ds : ds.slice(0, RC_SHOW), total = Math.max(Number(d.n) || 0, ds.length);
      body += `<div class="rc-h">${esc(t("rc_res", total, Number(d.read) || total))}</div>`;
      body += shown.map((it) => {
        const p = String(it.path || "");
        return `<div class="rc-r${it.small ? " small" : ""}${goAt(p, false)} title="${esc([p, it.small ? t("rc_small") : "", PATH_OBJ.test(p) ? t("tip_ch_go") : ""].filter(Boolean).join("\n"))}">`
          + `${movedHtml(it, types)}</div>`;
      }).join("");
      if (shown.length < ds.length) body += `<button class="rc-more flat" data-c="rcmore" data-id="${id}">${esc(tn("rc_res_show", ds.length - shown.length))}</button>`;
      else if (total > ds.length) body += `<div class="rc-note">${esc(tn("rc_res_more", total - ds.length))}</div>`;
      if (d.reinit) body += `<div class="rc-note">${esc(t("rc_reinit"))}</div>`;
      if (d.partial) body += `<div class="rc-note">${esc(t("rc_partial"))}</div>`;
    }
    return body;
  }

  // ------------------------------------------------------------------ undo, redo, restore points
  // Where the server takes changes back (feature undo) and the page can preview it (ctx.undo):
  // a row's own action at its end under the pointer -- ↶ Undo, ↷ Redo on an undo's row, Undo this restore
  // on a restore -- or, where there is none, why (quietly, in the same place). What the loaded
  // records say was undone is marked on the row. Nothing is written from here: ctx.undo and
  // ctx.restore open the preview (app-undo.js), which the user confirms.
  const undoOn = (ctx) => feature("undo") && !!ctx && typeof ctx.undo === "function" && ctx.journalOn !== false;
  const rsOn = (ctx) => !!ctx && typeof ctx.restore === "function";
  /** A restore record that put the model back to a restore point, not a program's values. */
  const cpRestore = (r) => r.op === "restore" && isObj(r.target) && !!r.target.checkpoint;
  /** What a restore point was kept before, in words (its reason). */
  const cpWords = (reason) => { const k = `cpr_${reason || "manual"}`, w = t(k); return w === k ? t("cpr_manual") : w; };
  WBC.cpWords = cpWords;
  /** A duration to expect, in words: about 3 s, about 2 min. */
  const estWords = (s) => { const x = Number(s) || 0; return x < 60 ? t("est_s", Math.max(1, Math.round(x))) : t("n_min", Math.round(x / 60)); };
  WBC.est = estWords;
  /** Why an undo came back only approximately, in words (its first reason code). */
  WBC.apWords = (codes) => { const c = (Array.isArray(codes) ? codes : [codes]).find(Boolean) || "other", k = `uv_ap_${c}`, w = t(k); return w === k ? t("uv_ap_other") : w; };
  /** What the rows' undo parts depend on, for the cards' and the tab's signatures. */
  const uvSig = (ctx) => `${undoOn(ctx) ? 1 : 0}${rsOn(ctx) ? 1 : 0}:${ctx && ctx.cps ? ctx.cps.ver : ""}`;
  WBC.field = (path, loc, type) => field(path, loc, type);
  WBC.valHtml = (d, unit) => valHtml(d, unit);
  let cpNow = null;                   // the restore points on disk the rows are drawn with (ctx.cps)
  /** A restore-point record as a milestone line: ◆ an automatic one (what it was kept before),
   *  ★ a named one (by you, or kept since: the store knows its name), ◇ none made and why,
   *  ◆ quieter where the last one was reused (nothing changed since). */
  function milestone(r) {
    const c0 = (Array.isArray(r.checkpoints) && r.checkpoints[0]) || {}, mark = (cls, ch) => `<span class="ch-ms${cls}" aria-hidden="true">${ch}</span> `;
    if (r.status === "skipped" || (r.why && !c0.id)) {
      const why = r.why === "slow" && r.est_s ? t("cp_ms_skipped", estWords(r.est_s)) : t(r.why === "no_session" ? "cp_ms_nosess" : "cp_ms_failed");
      return mark(" none", "◇") + esc(why);
    }
    if (r.reuse) { const p = cpNow && cpNow.get(r.reuse); return mark("", "◆") + esc(t("cp_ms_reuse", p ? when(p.t) : cpWords(r.cp_reason))); }
    const p = (cpNow && c0.id && cpNow.get(c0.id)) || null, name = (p && p.name) || c0.name;
    if (((p && p.class === "named") || c0.class === "named") && name) {
      return mark(" named", "★") + esc(t("cp_ms_named", name)) + (c0.reason === "manual" && r.actor === "user" ? esc(t("cp_ms_yours")) : "");
    }
    return mark("", "◆") + esc(t("cp_ms_auto", cpWords(c0.reason || r.cp_reason)));
  }
  /** A milestone's tooltip lines: what it holds (the file as saved, the model then, inputs
   *  only), why none was made. */
  function msTip(r) {
    const c0 = (Array.isArray(r.checkpoints) && r.checkpoints[0]) || {};
    if (r.status === "skipped") return r.why === "slow" ? t("tip_cp_ms_skipped") : "";
    const st = c0.state || (cpNow && cpNow.get(r.reuse || c0.id) || {}).state;
    return st ? t(`tip_cp_state_${["saved", "live", "input"].includes(st) ? st : "live"}`, when(r.t)) : "";
  }
  /** How a record could be taken back: undo | redo (an undo's own) | rs (a restore, back to the
   *  point kept before it) | cp (only a restore point) | results (a run: never) | nobefore (its
   *  value before was not measured) | rs_nocp (a restore not saved before) | ms (a milestone) |
   *  "" (nothing to take back). By the coverage of its tool and its op, no tool names here. */
  function undoKind(r) {
    if (!r || r.kind !== "change" || !r.id) return "";
    const op = r.op, st = r.status, tg = isObj(r.target) ? r.target : {};
    if (op === "run" || op === "reinit") return RAN.has(st) ? "results" : "";
    if (op === "checkpoint") return "ms";
    if (!(st === "changed" || st === "unknown") || ["save", "open", "close", "analysis"].includes(op)) return "";
    if (op === "restore") return cpRestore(r) ? (r.before_cp ? "rs" : "rs_nocp") : "";
    if (r.revert_of) return "redo";
    const cls = covClass(r.tool);
    if (cls === "none") return "";
    if (cls === "checkpoint" || op === "remove" || op === "patch" || (op === "add" && !["block", "stream", "row", "element"].includes(tg.kind))) return "cp";
    if (op === "value" || op === "attr") return "before" in r ? "undo" : "nobefore";
    if (op === "summary") return isObj(r.writes) && Object.values(r.writes).some((w) => w && w.status === "changed") ? "undo" : "";
    return op === "add" || op === "connect" ? "undo" : "";
  }
  const revIds = (r) => (Array.isArray(r.revert_of) ? r.revert_of.map(String) : r.revert_of ? [String(r.revert_of)] : []);
  /** The loaded undo records by the record each took back (the newest): what was undone. */
  function revOf(M) {
    if (M.revV === M.ver && M.rev) return M.rev;
    const m = new Map();
    M.recs.forEach((r) => { if (r.kind === "change" && r.status === "changed") revIds(r).forEach((id) => { const was = m.get(id); if (!was || newer(r, was)) m.set(id, r); }); });
    M.rev = m;
    M.revV = M.ver;
    return m;
  }
  /** A row's undo parts: its action or why there is none (act, at its end under the pointer),
   *  “undone 14:12” (tag), and on an undo's own row which record it took back (of). */
  function rowUndo(r, M, ctx, c) {
    const out = { act: "", tag: "", of: "" }, k = undoKind(r);
    if (!k) return out;
    const on = undoOn(ctx), rev = revOf(M), by = rev.get(r.id), undone = !!by && !rev.has(by.id);
    if (undone && on) {
      const approx = by.exact === false || (Array.isArray(by.approx) && by.approx.length);
      const key = r.revert_of ? "uv_redone_tag" : approx ? "uv_done_tag_approx" : "uv_done_tag";
      out.tag = ` <small class="ch-q ch-undone" title="${esc(approx && !r.revert_of ? WBC.apWords(by.approx) : "")}">${esc(t(key, when(by.t)))}</small>`;
    }
    if (r.revert_of && on) {
      const o = M.recs.find((x) => x.id === revIds(r)[0]);
      out.of = ` <small class="ch-q">${esc(o ? t(r.redo ? "uv_of_redo" : "uv_of", when(o.t)) : t(r.redo ? "uv_of_redo0" : "uv_of0"))}</small>`;
    }
    const id = esc(r.id), btn = (label, icn, tip) => `<button class="ch-undo flat" data-c="undo" data-id="${id}" title="${esc(tip)}">${icon(icn)}<span>${esc(label)}</span></button>`;
    const note = (text, tip, go) => (go ? `<button class="ch-nu flat" data-c="${go}" data-id="${id}" title="${esc(tip)}">${esc(text)}</button>`
      : `<span class="ch-nu" title="${esc(tip)}">${esc(text)}</span>`);
    if (k === "ms") {                              // a milestone: back to it, or why not
      const c0 = (Array.isArray(r.checkpoints) && r.checkpoints[0]) || {}, cid = c0.id || r.reuse;
      if (!cid || r.status === "skipped" || !cpNow) return out;
      if (!cpNow.has(cid)) out.act = note(t("cp_pruned"), t("tip_cp_pruned"));
      else if (rsOn(ctx)) out.act = `<button class="ch-undo flat" data-c="cp_here" data-cp="${esc(cid)}" title="${esc(t("tip_cp_here"))}">${icon("undo")}<span>${esc(t("cp_here"))}</span></button>`;
      return out;
    }
    if (!on) return out;
    if (k === "results") out.act = note(t("uv_nu_results"), t("tip_uv_nu_results"));
    else if (undone) return out;
    else if (k === "undo") out.act = btn(t("undo"), "undo", t("tip_uv_undo"));
    else if (k === "redo") out.act = btn(t("redo"), "redo", t("tip_uv_redo"));
    else if (k === "rs") out.act = btn(t("uv_rs_undo"), "undo", t("tip_uv_rs_undo"));
    else if (k === "cp") out.act = note(t("uv_nu_cp"), t("tip_uv_nu_cp"), c && c.gid ? "nu_cp" : "");
    else if (k === "nobefore") out.act = note(t("uv_nu_nobefore"), t("tip_uv_nu_nobefore"));
    else if (k === "rs_nocp") out.act = note(t("uv_nu_nocp"), t("tip_uv_nu_nocp"));
    return out;
  }
  /** A card's own way back, for its ⋯ (first): {label, icon, redo}, or null. Restore to before this group where
   *  it holds a change only a restore point takes back and its restore point is on disk; the
   *  preview says what exactly (the server plans it). */
  function groupUndo(c, M, ctx) {
    if (!c.gid || !undoOn(ctx)) return null;
    const ks = c.recs.map(undoKind), rev = revOf(M);
    const live = c.recs.filter((r, i) => ["undo", "redo", "rs", "cp"].includes(ks[i]) && !(rev.has(r.id) && !rev.has(rev.get(r.id).id)));
    if (!live.length) return null;
    const kinds = live.map(undoKind), redo = kinds.every((k) => k === "redo");
    const cp = kinds.includes("cp") && c.recs.some((r) => r.op === "checkpoint" && cpNow && cpNow.has(((r.checkpoints || [])[0] || {}).id || r.reuse));
    return redo ? { label: t("uv_group_redo"), icon: "redo", redo: true } : { label: t(cp ? "uv_group_rs" : "uv_group"), icon: "undo", redo: false };
  }
  // ------------------------------------------------------------------ step through a group (walk.js)
  // An open card's Step through (a labelled button over its rows) hands walk.js the
  // group's records that went in, oldest first; walk.js shows one at a time on the flowsheet, in the
  // row's own words, and the row it is on is marked in the card (.wk-on). Where the loaded page may
  // not hold the whole group (earlier pages, a filter), walk.js reads the group itself (Api.journal group).
  const walkOn = (ctx) => !!window.WBW && WBW.on() && !!ctx && !!ctx.model;
  /** A record the walk stops at: a change that went in (a run however it ended; a loop, even one
   *  that left the model as it was or ended in an error: it ran its points) -- not a write that
   *  failed, was refused or left the value as it was, a call with nothing measured, a gate. */
  const walkable = (r) => !!r && r.kind === "change" && !isGate(r) && !op0(r) && r.op !== "brake" && r.op !== "proposal"
    && (r.status !== "unchanged" || r.op === "summary") && !(BAD.has(r.status) && !RUN_OPS.has(r.op) && !(r.op === "summary" && r.status === "error"));
  WBC.walkable = walkable;
  /** The group may hold more records than the card has: earlier pages, or a filter on. */
  const walkPart = (M) => !!(M.more || M.actors || M.obj);
  /** How many stops the card's walk has (0: none offered; one alone is its row's click). */
  function walkN(c, M) {
    if (c.mile) return 0;
    const n = c.recs.filter(walkable).length;
    return n >= 2 || (n === 1 && c.gid && walkPart(M)) ? n : 0;
  }
  /** One stop in words: its time, who (when not the card's), its line (html, the row's), the
   *  reason or note under it, the blocks and streams it is about ("block:NAME", the one to look at
   *  first: a connection's stream), and one it removed (gone). */
  WBC.walkStep = function (r, types, actor) {
    const tg = r.target || {}, keys = [], add = (k) => { if (k && !keys.includes(k)) keys.push(k); };
    if (r.op === "connect") add(okey({ kind: "stream", name: tg.stream }));
    if (r.op === "summary" && tg.path) add(objOfPath(tg.path));
    objsOf(r).forEach(add);
    if (RUN_OPS.has(r.op) && isObj(r.blocks)) Object.keys(r.blocks).forEach((b) => add(okey({ kind: "block", name: b })));
    const why = r.reason != null && String(r.reason).trim(), own = r.reason_src === "why";
    return { id: r.id, time: hhmm(r.t), tip: rowTip(r), who: r.actor && r.actor !== actor ? whoHtml(r.actor, true) : "",
             html: what(r, types || {}, !!r.actor && r.actor !== actor), keys,
             gone: r.op === "remove" && r.status === "changed" ? okey({ kind: tg.kind, name: tg.name }) : "",
             reason: why ? rich(t(own ? "ch_why" : "reason", why), 320) : "", reasonTip: why ? t(own ? "tip_why" : "tip_reason") : "" };
  };
  let walkRid = null;                            // the row the walk shows (its card drawn again keeps the mark)
  function walkMark(box, rid) {
    walkRid = rid || null;
    box.querySelectorAll(".ch-row.wk-on").forEach((el) => el.classList.remove("wk-on"));
    const el = rid ? box.querySelector(`.ch-row[data-rid="${CSS.escape(rid)}"]`) : null;
    if (!el) return;
    el.classList.add("wk-on");
    if (!box.clientHeight) return;               // (the tab hidden: nothing to scroll)
    const a = el.getBoundingClientRect(), b = box.getBoundingClientRect();
    if (a.top < b.top + 4) box.scrollTop -= b.top + 4 - a.top;
    else if (a.bottom > b.bottom - 4) box.scrollTop += Math.min(a.bottom - b.bottom + 4, a.top - b.top - 4);
  }
  /** The card's walk starts: the card opens (its dots go, as opened by hand), walk.js takes it. */
  function walkStart(box, ctx, M, c, anchor) {
    const recs = c.recs.filter(walkable);
    if (!recs.length || !walkOn(ctx)) return;
    if (!M.open.get(c.key)) {
      M.open.set(c.key, true); M.ver++; seeCard(ctx, c); WBC.render(box, ctx);
      anchor = box.querySelector(`.ch-card[data-key="${CSS.escape(c.key)}"] .ch-walk`) || anchor;   // (the card made again)
    }
    const types = ctx.types || {};
    WBW.open({ model: ctx.model, session: ctx.session, tab: ctx.tab, group: c.gid || null, title: titleOf(c), types, recs,
               full: !(c.gid && walkPart(M)), anchor, step: (r) => WBC.walkStep(r, types, c.actor), onStep: (rid) => walkMark(box, rid) });
  }

  /** A record's line in plain words (the preview's title, a chip's label). */
  function rowWords(r, ctx) {
    const el = document.createElement("div");
    el.innerHTML = what(r, (ctx && ctx.types) || {}, false);
    return el.textContent.replace(/\s+/g, " ").trim().slice(0, 200);
  }

  /** An Ask AI request's target for a record: its id and model, its line in words (the
   *  label the chip and the chat show), its block or stream and its field. */
  function changeTarget(r, ctx) {
    const tg = r.target || {}, obj = tg.block ? ["block", tg.block] : tg.stream ? ["stream", tg.stream]
      : (tg.kind === "block" || tg.kind === "stream") && tg.name ? [tg.kind, tg.name] : null;
    const el = document.createElement("div");
    el.innerHTML = what(r, ctx.types || {}, false);
    const out = { kind: "change", id: String(r.id), model: ctx.model, label: el.textContent.replace(/\s+/g, " ").trim().slice(0, 200) };
    if (obj) Object.assign(out, { obj: obj[0], name: String(obj[1]) });
    if (tg.path && String(tg.path).startsWith("\\Data\\")) out.path = String(tg.path);
    return out;
  }
  function rowTip(r) {
    const tg = r.target || {};
    const more = r.op === "checkpoint" ? [msTip(r)]           // (what a restore point holds; an undo's accuracy)
      : r.revert_of && r.exact === false && feature("undo") ? [t("uv_approx_row", WBC.apWords(r.approx))]
      : isObj(r.gate) && Number(r.gate.held_s) >= 1 ? [t("gt_held", Math.round(r.gate.held_s))] : [];   // (how long the brakes held it)
    return [stamp(r.t), [who(r.actor), r.tool].filter(Boolean).join(" · "), ...extTip(r), ...more,
            tg.path && String(tg.path).startsWith("\\Data\\") ? tg.path : ""].filter(Boolean).join("\n");
  }
  /** The loaded records' overrides (WBC.overrides): with the whole timeline's records where a
   *  filter hides who set a field again. */
  function ovOf(M) {
    const all = M.actors || M.obj ? store.get(`${M.id}\n\n`) : null, sig = `${M.ver}|${all && all.loaded ? all.ver : ""}`;
    if (M.ovSig === sig && M.ov) return M.ov;
    const recs = all && all.loaded ? all.recs.concat(M.recs.filter((r) => !all.ids.has(r.id))) : M.recs;
    M.ov = WBC.overrides(recs.filter((r) => r.kind === "change"));
    M.ovSig = sig;
    return M.ov;
  }
  /** "↳ 12:16 AI changed it back to 60 C" under a value someone else set again later; a click
   *  goes to that record. */
  function overLine(r, ov) {
    const x = ov && ov.get(r.id);
    if (!x) return "";
    const v = (d) => (isObj(d) ? d.value : d), a = x.after, u = isObj(a) && a.unit ? ` ${a.unit}` : "";
    const back = numOf(v(r.before)) !== null ? numOf(v(r.before)) === numOf(v(a)) : String(v(r.before)) === String(v(a));
    return `<button class="ch-over flat" data-c="over" data-id="${esc(x.id)}" data-g="${esc(x.group || "")}" title="${esc(t("tip_ch_over"))}">`
      + `${esc(t(back ? "ch_over_back" : "ch_over", when(x.t), who(x.actor), val(a) + u))}</button>`;
  }
  /** An opened card's rows, oldest first: at most its row count (ROWS, or all once asked); from:
   *  only the rows after the first `from` (those already drawn), with the button for more. */
  function rowsHtml(c, M, types, ctx, from = 0) {
    const Z = sameOf(c, M), limit = M.rows.get(c.key) || ROWS, list = Z.recs.slice(0, limit), title = titleOf(c).trim();
    const newest = M.recs.find(measured);          // the newest measured run opens by itself, once
    if (newest && !M.rc.has(newest.id)) M.rc.set(newest.id, true);
    const asks = askOn(ctx), undos = undoOn(ctx) || !!(ctx && ctx.cps), ov = ovOf(M);
    const helps = !!ctx && typeof ctx.help === "function";   // a field's help card (help.js)
    const S = ctx && ctx.model && tbOn(ctx) && selOf(ctx).on ? selOf(ctx) : null;
    cpNow = (ctx && ctx.cps) || null;
    gateM = M;
    deadNow = deadOf(M);
    // step through it on the flowsheet (walk.js): a labelled button over the rows
    const walk = !from && walkOn(ctx) && walkN(c, M)
      ? `<div class="ch-wkl"><button class="ch-walk flat" data-c="walk" title="${esc(t("tip_walk"))}">${icon("step")}<span>${esc(t("walk_btn"))}</span></button></div>` : "";
    const html = walk + list.slice(from).map((r, k) => {
      const i = k + from;
      // (a call the brakes kept out says why in its own words, quietly: the brakes worked)
      const gate = isGate(r), st = r.status, bad = BAD.has(st) && !gate, badge = !!r.actor && r.actor !== c.actor;
      const dim = r.kind === "change" && !gate && (st === "unchanged" || op0(r));
      // "not applied": a write that did not go in; a run says how it ended (it ran, or did not
      // run) and a loop that ended in an error still wrote its points (WBC.tally's rule)
      const not = bad && !RUN_OPS.has(r.op) && !(r.op === "summary" && st === "error");
      const tg = r.target || {}, obj = tg.block ? `block:${tg.block}` : tg.stream ? `stream:${tg.stream}` : tg.kind && tg.name ? `${tg.kind}:${tg.name}` : "";
      // a block or stream still to be found: a click picks it (at the field, for a value)
      const go = /^(block|stream):/.test(obj) && r.op !== "remove", fld = go && /^(value|attr|summary)$/.test(r.op) && tg.path;
      const tip = rowTip(r) + (go ? `\n${t(fld ? "tip_ch_go_field" : "tip_ch_go")}` : "");
      // Ask AI about this record: at the row's end under the pointer, its own hit area
      const ask = asks && r.kind === "change" && r.id
        ? `<button class="ch-ask flat icon" data-c="ask" data-id="${esc(r.id)}" title="${esc(t("ask_row"))}">${icon("chat")}</button>` : "";
      // what the field is: its help card, from a “?” beside Ask AI under the pointer
      const help = helps && fld && r.id
        ? `<button class="ch-help flat icon" data-c="help" data-id="${esc(r.id)}" title="${esc(t("tip_fh"))}" aria-label="${esc(t("fh_what"))}" aria-haspopup="dialog">${icon("help")}</button>` : "";
      // its way back (or why there is none) beside it, what an undo took back
      const U = undos ? rowUndo(r, M, ctx, c) : null, uv = !!(U && U.act);
      // select mode: a change that went in can be picked to turn into blocks
      const pick = S && r.kind === "change" && r.id && !gate && !bad
        ? `<input type="checkbox" class="ch-pick" data-c="pick" data-id="${esc(r.id)}"${S.ids.has(r.id) ? " checked" : ""} title="${esc(t("tip_ch_pick"))}" aria-label="${esc(t("tip_ch_pick"))}">` : "";
      let s = `<div class="ch-row${bad ? " bad" : ""}${gate ? " gate" : ""}${dim ? " dim" : ""}${go ? " go" : ""}${ask ? " ask" : ""}${help ? " hp" : ""}${uv ? " uv" : ""}${walkRid && r.id === walkRid ? " wk-on" : ""}" data-rid="${esc(r.id || "")}"${obj ? ` data-obj="${esc(obj)}"` : ""}${fld ? ` data-path="${esc(tg.path)}"` : ""} title="${esc(tip)}">`
        + `${pick}<span class="ch-rt">${hhmm(r.t)}</span> <span class="ch-rx">${badge ? `${whoHtml(r.actor, true)} ` : ""}${what(r, types, badge)}`
        + `${not ? `<small class="ch-q">${esc(t("ch_r_not"))}</small>` : ""}${gateTag(r)}${propTag(r)}${pausedTag(r)}${U ? U.of + U.tag : ""}</span>${uv ? U.act : ""}${help}${ask}</div>`;
      s += overLine(r, ov) + subLines(r, types) + errLines(r) + (measured(r) ? runCard(r, M, types, ctx || {}) : "");
      const why = r.reason != null && String(r.reason).trim();
      if (why && !(c.head && c.head.source === "reason" && why.startsWith(title.replace(/…$/, "")))) {
        const own = r.reason_src === "why";
        s += `<div class="ch-reason${own ? " why" : ""}" title="${esc(t(own ? "tip_why" : "tip_reason"))}">${rich(t(own ? "ch_why" : "reason", why), 320)}</div>`;
      }
      return (i === Z.at ? Z.line : "") + s;
    }).join("") + (Z.at >= list.length ? Z.line : "");
    const left = Z.recs.length - list.length, next = Math.min(left, ROWS_STEP);
    const label = left > next ? t("ch_rows_more_of", next, left) : tn("ch_rows_more", left);
    return html + (left > 0 ? `<button class="ch-rmore flat" data-c="rows">${esc(label)}</button>` : "");
  }
  /** A card's writes that left a value as it was (isSame), folded: the rows drawn (recs), and one
   *  quiet line in their place ("16 more writes left the value unchanged") at the row index `at` -- where the first
   *  of them is, or the end of the rows drawn -- that shows them in place on a click, and folds
   *  them again (M.same). No such writes: the rows as they are, no line. */
  function sameOf(c, M) {
    const n = c.recs.filter(isSame).length;
    if (!n) return { recs: c.recs, at: -1, line: "" };
    const shown = M.same.has(c.key), recs = shown ? c.recs : c.recs.filter((r) => !isSame(r));
    const first = c.recs.findIndex(isSame), at = shown ? first : c.recs.slice(0, first).filter((r) => !isSame(r)).length;
    const words = tn(n === c.recs.length ? "ch_same_all" : "ch_same_more", n);
    const line = `<button class="ch-same flat" data-c="same" aria-expanded="${shown}" title="${esc(t("tip_ch_same"))}">`
      + `${icon("chevron-right").replace('class="ic"', 'class="ic chev"')}<span>${esc(words)}</span></button>`;
    return { recs, at, line };
  }
  /** What a card's element shows, in short: redrawn only when this (or the page's words) moved. */
  function cardSig(c, M) {
    const h = c.head || {}, a = c.recs[0] || {}, z = c.recs[c.recs.length - 1] || {}, ov = ovOf(M);
    // (a card's proposals: what became of them since, as their rows say it)
    const fates = M.open.get(c.key) && c.recs.some(isCardGate) ? (gateM = M, c.recs.filter(isCardGate).map(fateWords).join("|")) : "";
    return [c.key, c.actor, c.recs.length, a.id, z.id, c.t0, c.t1, M.open.get(c.key) ? 1 : 0, M.rows.get(c.key) || 0, M.same.has(c.key) ? 1 : 0,
            h.title, h.source, h.note, h.ai_group, c.recs.filter((r) => ov.has(r.id)).length, (nets.get(`${M.id}\n${c.gid}`) || {}).sig, fates,
            h.proposal ? ptabKey(propTab(h.proposal)) : "",
            c.mile && (c.recs[0] || {}).proposal ? ptabKey(propTab(c.recs[0].proposal, c.recs[0].tab)) : ""].join("\u0001");
  }
  /** Your own edits in a card someone else set again later: "1 later changed by the AI" (the
   *  card of your edits in Aspen's window, or in the workbench), or "". */
  function overSum(c, M) {
    if (!YOURS.includes(c.actor)) return "";
    const ov = ovOf(M), by = new Map();
    c.recs.forEach((r) => { const x = ov.get(r.id); if (x && YOURS.includes(String(r.actor)) && !YOURS.includes(String(x.actor))) by.set(x.actor, (by.get(x.actor) || 0) + 1); });
    return [...by].map(([a, n]) => tn("ch_s_over", n, who(a))).join(t("ch_s_sep"));
  }
  function cardHtml(c, M, types, ctx) {
    if (c.mile) return mileHtml(c);
    const open = !!M.open.get(c.key), a = ACT[c.actor] ? c.actor : "external", h = c.head || {};
    const title = titleOf(c), over = overSum(c, M), sum = sumLine(c) + (over ? `${t("ch_s_sep")}${over}` : "");
    const res = netParts(cardNet(c, M, ctx), types);   // (twice run or more: before -> now of the results)
    // (a run of the AI's proposal you approved: ✦ and a way to its tab while it is open)
    const tag = h.proposal ? `<span class="ch-tag prop">${esc(t("ch_tag_prop"))}</span>`
      : a === "program" && h.ai_group ? `<span class="ch-tag">${esc(t("ch_by_ai_prog"))}</span>` : "";
    const ptab = h.proposal ? ptabBtn(propTab(h.proposal), "ch-note icon ch-ptab", false) : "";
    const tip = [h.source === "reason" ? t("tip_title_reason") : h.source === "note" ? t("tip_title_note") : "", sumLine(c, true) + (over ? `${t("ch_s_sep")}${over}` : "")].filter(Boolean).join("\n");
    const note = h.note
      ? `<button class="ch-note flat icon" data-c="note" data-note="${esc(h.note)}" title="${esc(t("tip_ch_note"))}">${icon("chat")}</button>` : "";
    // ⋯: this group's own actions: take it back, ask the AI about it, its report
    const more = c.gid && (moreOn(ctx) || askMenu(ctx) || (typeof ctx.menu === "function" && (tbOn(ctx) || !!groupUndo(c, M, ctx))))
      ? `<button class="ch-more flat icon" data-c="more" aria-haspopup="menu" title="${esc(t("tip_ch_more"))}">${icon("more")}</button>` : "";
    return `<article class="ch-card a-${a}${open ? " open" : ""}" data-key="${esc(c.key)}">`
      + `<div class="ch-head"><button class="ch-tog" data-c="tog" aria-expanded="${open}" title="${esc(tip)}">`
      + `${icon("chevron-right").replace('class="ic"', 'class="ic chev"')}<span class="ch-l1">${whoHtml(c.actor)}<b class="ch-title">${esc(title)}</b>${tag}`
      + `<span class="ch-time">${esc(span(c.t0, c.t1))}</span></span><span class="ch-l2">${esc(sum)}</span>`
      + `${res ? `<span class="ch-l3" title="${esc(res.tip)}"><span class="aw-rl">${esc(t("net_label"))}</span>${esc(res.plain)}</span>` : ""}</button>${note}${ptab}${more}</div>`
      + `<div class="ch-rows">${open ? rowsHtml(c, M, types, ctx) : ""}</div></article>`;
  }

  // ------------------------------------------------------------------ drawing
  /** One line instead of cards: none recorded yet ("none"), or the words of `kind`. */
  function empty(kind, arg) {
    return `<div class="ch-empty"><div class="ch-eb">${esc(t(kind === "none" ? "ch_empty_t" : kind, arg))}</div></div>`;
  }
  /** The tab's parts, made once: lines on top, the filter chips, the list (the cards and the
   *  "last seen here" line, or what shows instead of cards), its foot. */
  function parts(box) {
    const w = box._wbc;
    if (w.parts && w.parts.list.parentNode === box) return w.parts;
    box.innerHTML = '<div class="ch-tops"></div><div class="ch-bar hidden"></div><div class="ch-away hidden"></div>'
      + '<div class="ch-list"></div><div class="ch-end"></div><div class="ch-selbar hidden" role="group"></div>';
    const q = (s) => box.querySelector(s), seen = document.createElement("div");
    seen.className = "ch-seen";
    w.parts = { tops: q(".ch-tops"), bar: q(".ch-bar"), away: q(".ch-away"), list: q(".ch-list"), end: q(".ch-end"), selbar: q(".ch-selbar"), seen };
    return w.parts;
  }

  /** The filter chips: All, then who changed the model, each with its count (the journal's
   *  summary; All's in its tooltip); folded into one chip while the record is short and no filter is on. Nothing
   *  when one kind of change is all there is. */
  function barHtml(ctx, st) {
    // one block's or stream's changes only: first, its ✕ shows all again
    const only = st.obj ? `<button class="ch-chip ch-obj on" data-c="obj" title="${esc(t("tip_ch_only_obj", st.obj.name))}">`
      + `${icon(st.obj.kind === "stream" ? "stream" : "block")}<span>${esc(t("ch_only", st.obj.name))}</span>${icon("close")}</button>` : "";
    const s = ctx.summary, by = s && typeof s === "object" && s.by && typeof s.by === "object" ? s.by : null;
    if (!by) return only;
    const have = WHO.filter((a) => (Number(by[a]) || 0) > 0 || st.actors === a);
    if (have.length < 2 && !st.actors) return only;
    const short = (Number(s.n) || 0) < SHORT;
    if (!st.actors && !(st.bar != null ? st.bar : !short)) {
      return `${only}<button class="ch-chip ch-fold" data-c="bar" aria-expanded="false" title="${esc(t("tip_ch_filter"))}">`
        + `${icon("filter")}<span>${esc(t("ch_filter"))}</span></button>`;
    }
    // (the model's counts: not one object's; All's is the others' sum, said in its tooltip)
    const chip = (a, n) => {
      const on = (st.actors || null) === a, tip = a ? t(`tip_ch_only_${a}`) : st.obj ? t("tip_ch_all") : `${t("tip_ch_all")}
${t("tip_ch_all_n", n)}`;
      return `<button class="ch-chip${a ? ` a-${a}` : ""}${on ? " on" : ""}" data-c="actor" data-a="${a || ""}" aria-pressed="${on}"`
        + ` title="${esc(tip)}">${a ? icon(ACT[a]) : ""}<span>${esc(t(a ? `ch_who_${a}` : "ch_all"))}</span>${st.obj || !a ? "" : `<small>${n}</small>`}</button>`;
    };
    let html = only + chip(null, Number(s.n) || 0) + have.map((a) => chip(a, Number(by[a]) || 0)).join("");
    if (short && !st.actors) html += `<button class="ch-chip ch-unfold flat icon" data-c="bar" aria-expanded="true" title="${esc(t("tip_ch_fold"))}">${icon("chevron-up")}</button>`;
    return html;
  }

  function draw(box, ctx, M) {
    const t0 = performance.now(), P = parts(box), w = box._wbc, L = P.list;
    if (M) M.box = box;                          // (a card's results read later draw it again: cardNet)
    const strings = (window.WBL && WBL.strings) || ctx.strings || {}, top = [];
    if (strings.state === "running") top.push(`<div class="ch-top">${esc(t("str_running"))}</div>`);
    if (ctx.journalOn === false) top.push(`<div class="ch-top off">${esc(t("ch_off"))}</div>`);
    if (M && M.loaded && M.error) top.push(`<div class="ch-top bad">${esc(t("ch_err", M.error))}</div>`);
    setHtml(P.tops, top.join(""));
    const dotsN = ctx.model && !(WBC.repOn() && aways.get(ctx.model)) ? Object.keys(WBC.marks(ctx) || {}).length : 0;   // (the away line has its own)
    const bar = ctx.model ? barHtml(ctx, tabState(ctx.tab)) + (dotsN
      ? `<button class="ch-chip ch-allseen flat" data-c="away_all" title="${esc(t("tip_aw_all"))}">${icon("eye")}<span>${esc(t("aw_all"))}</span></button>` : "") : "";
    setHtml(P.bar, bar);
    P.bar.classList.toggle("hidden", !bar);
    // while you were away: one line over the cards
    const A = ctx.model && WBC.repOn() ? aways.get(ctx.model) : null;
    setHtml(P.away, A ? awayHtml(A, ctx) : "");
    P.away.classList.toggle("hidden", !A);
    if (A) A.shown = true;
    /** Words instead of cards. */
    const say = (html) => {
      if (L._h !== html) { L._h = html; L._key = null; L.innerHTML = html; }
      L.classList.remove("wait");
      setHtml(P.end, "");
      w.cards = null;
    };
    if (!ctx.model) return say(empty("ch_no_model"));
    if (!M.loaded) {
      if (L._key && L._h == null && L.firstChild) { L.classList.add("wait"); return; }   // another filter's cards, faded, till these come
      return say(`<div class="ch-empty ch-loading"><div class="ch-eb">${esc(t("ch_loading"))}</div></div>`);
    }
    const list = cards(M);
    deadNow = deadOf(M);
    if (!list.length) {
      const only = tabState(ctx.tab).obj;
      if (M.actors || only) {
        const a = ACT[M.actors] ? M.actors : "external";
        const words = only ? t(M.actors ? `ch_none_obj_${a}` : "ch_none_obj", only.name) : t(`ch_none_${a}`);
        say(`<div class="ch-empty"><div class="ch-eb">${esc(words)}`
          + ` <button class="ch-link flat" data-c="${only ? "obj" : "actor"}" data-a="">${esc(t("ch_show_all"))}</button></div></div>`);
        // the search stopped at its limit: it can go on further back
        if (M.more) setHtml(P.end, `<div class="ch-foot"><button class="ch-older" data-c="older"${M.older ? " disabled" : ""}>${esc(M.older ? t("ch_more_busy") : t("ch_scanned", M.scanned))}</button></div>`);
        return;
      }
      return say(M.error || ctx.journalOn === false ? "" : empty("none"));
    }
    // the line over the first card seen when the tab opened (while the away line shows: over the
    // first card before it counts from); the cards above it open (and the newest)
    const mk = A ? A.since : w.view && w.view.model === ctx.model ? w.view.divider : null;
    const at = mk ? list.findIndex((c) => c.recs.every(seenBy(mk))) : -1;
    const unseen = !mk ? 0 : at < 0 ? list.length : at;
    list.slice(0, Math.max(1, Math.min(unseen, OPEN_MAX))).forEach((c) => {
      if (!M.open.has(c.key) && !M.auto.has(c.key)) { M.open.set(c.key, true); M.auto.add(c.key); }
    });
    // a group gone to (WBC.showGroup): its card opens before the cards are made
    const jc = w.jump ? jumpFind(box, ctx, M, list) : null;
    // scrolled down, the card at the top of the view stays where it is (new cards come in above it)
    const fresh = L._key !== M.key || L._h != null;
    let anchor = null;
    if (!fresh && box.scrollTop > 4) {
      for (const el of L.children) {
        if (el.dataset.key && el.offsetTop + el.offsetHeight > box.scrollTop) { anchor = { key: el.dataset.key, el, off: el.offsetTop - box.scrollTop }; break; }
      }
    }
    if (fresh) { L.innerHTML = ""; L._h = null; L._key = M.key; }
    L.classList.remove("wait");
    // only the cards that are new or changed are made again; the rest keep their elements
    const gen = (w.gen = [I18N.lang, window.WBL ? WBL.ver : 0, JSON.stringify(ctx.types || {}), rcSig(ctx),
      moreOn(ctx) ? "more" : "", extOn() ? "ext" : "", askOn(ctx) ? "ask" : "", uvSig(ctx), tbOn(ctx) ? "tb" : "", selSig(ctx), walkOn(ctx) ? "walk" : ""].join("\u0002"));
    const have = new Map(), nodes = [], build = [];
    for (const el of L.children) if (el.dataset.key) have.set(el.dataset.key, el);
    list.forEach((c, i) => {
      const sig = `${gen}\u0002${cardSig(c, M)}`, el = have.get(c.key);
      if (el && el._sig === sig) nodes.push(el);
      else { nodes.push(null); build.push([i, c, sig]); }
    });
    if (build.length) {
      const tpl = document.createElement("template"), types = ctx.types || {};
      tpl.innerHTML = build.map(([, c]) => cardHtml(c, M, types, ctx)).join("");
      const made = [...tpl.content.children];
      build.forEach(([i, , sig], k) => { made[k]._sig = sig; nodes[i] = made[k]; });
    }
    if (at > 0) {
      setHtml(P.seen, `<span>${esc(t("ch_seen"))}</span>`);
      P.seen.title = t("tip_ch_seen");
      nodes.splice(at, 0, P.seen);
    }
    let cur = L.firstChild;
    for (const n of nodes) {
      if (n === cur) { cur = cur.nextSibling; continue; }
      L.insertBefore(n, cur);
    }
    while (cur) { const nx = cur.nextSibling; cur.remove(); cur = nx; }
    w.cards = new Map(list.map((c) => [c.key, c]));
    let foot;
    if (M.more) {
      const label = M.older ? t("ch_more_busy") : M.capped ? t("ch_scanned", M.scanned) : t("ch_more");
      foot = `<div class="ch-foot"><button class="ch-older" data-c="older"${M.older ? " disabled" : ""}>${esc(label)}</button></div>`;
    } else foot = `<div class="ch-foot ch-q">${esc(t("ch_end"))}</div>`;
    setHtml(P.end, foot);
    if (fresh) box.scrollTop = 0;
    else if (anchor) {
      const el = anchor.el.parentNode === L ? anchor.el : L.querySelector(`.ch-card[data-key="${CSS.escape(anchor.key)}"]`);
      if (el) box.scrollTop = el.offsetTop - anchor.off;
    }
    if (jc) jumped(box, L, jc);
    void L.offsetHeight;                         // (its layout, in the time kept)
    perf(WBC.perf.draws, { ms: Math.round((performance.now() - t0) * 100) / 100, recs: M.recs.length, cards: list.length, built: build.length });
  }

  /** The tab's clicks: a filter chip, the chips folded or not; a card opens or closes, shows
   *  more of its rows; a request's icon goes to it in the AI chat; an earlier page. */
  function wire(box) {
    // the list scrolled by hand: what it shows is seen (the unread count), as SEEN_MS in front is
    const byHand = () => { const w = box._wbc, v = w && w.view; if (v && v.marked !== sigOf(v.ctx.summary) && focused()) mark(v); };
    box.addEventListener("wheel", byHand, { passive: true });
    // a card's rows rise in once, when opened: not again where a redraw moves the card among the others
    box.addEventListener("animationend", (ev) => { if (ev.target.matches && ev.target.matches(".ch-rows.in, .rc-body.in")) ev.target.classList.remove("in"); });
    box.addEventListener("keydown", (ev) => { if (/^(PageDown|PageUp|ArrowDown|ArrowUp|End|Home)$/.test(ev.key)) byHand(); });
    box.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-c]"), w = box._wbc;
      if (!w) return;
      // a record's block or stream: picked on the flowsheet, the inspector at its field
      const go = !b && ev.target.closest(".go[data-obj]");
      if (go) {
        const k = go.dataset.obj, i = k.indexOf(":");
        if (typeof w.ctx.goto === "function" && i > 0) w.ctx.goto({ kind: k.slice(0, i), name: k.slice(i + 1) }, go.dataset.path || null);
        return;
      }
      if (!b || b.disabled) return;
      const st = tabState(w.ctx.tab);
      if (b.dataset.c === "pick") {                // select mode: picked or let go
        const S = selOf(w.ctx);
        if (b.checked) S.ids.add(b.dataset.id); else S.ids.delete(b.dataset.id);
        selBar(box, w.ctx);
        return;
      }
      if (b.dataset.c === "sel_go" || b.dataset.c === "sel_x") {   // turn the picked into blocks, or leave select mode
        const S = selOf(w.ctx), ids = [...S.ids];
        if (b.dataset.c === "sel_go" && ids.length && tbOn(w.ctx)) w.ctx.toBlocks({ ids, label: tn("to_blocks_sel", ids.length) });
        WBC.select(box, w.ctx, false);
        if (typeof w.ctx.onSel === "function") w.ctx.onSel();
        return;
      }
      if (b.dataset.c === "obj") { if (setObj(box, w.ctx, null)) WBC.render(box, w.ctx); return; }
      if (b.dataset.c === "actor") {
        const a = b.dataset.a || null;
        st.actors = st.actors === a ? null : a;    // (the one on, again: all)
        st.bar = true;                             // the chips stay where the pointer is
        WBC.render(box, w.ctx);
        return;
      }
      if (b.dataset.c === "bar") { st.bar = b.getAttribute("aria-expanded") !== "true"; WBC.render(box, w.ctx); return; }
      const M = model(w.ctx.model, st.actors, okey(st.obj)), card = b.closest(".ch-card"), c = card && w.cards && w.cards.get(card.dataset.key);
      if (b.dataset.c === "older") { load(M, w.ctx, "older", box); M.ver++; WBC.render(box, w.ctx); return; }
      if (b.dataset.c === "note") { if (typeof w.ctx.gotoNote === "function") w.ctx.gotoNote(b.dataset.note); return; }
      if (b.dataset.c === "over") { WBC.showGroup(box, w.ctx, b.dataset.g, b.dataset.id); return; }
      if (b.dataset.c === "prop") { if (b.dataset.g) WBC.showGroup(box, w.ctx, b.dataset.g); return; }   // (the AI's request that proposed it)
      if (b.dataset.c === "ptab") {                // (the proposal's tab, also from History; none once deleted)
        if (b.getAttribute("aria-disabled") === "true" || !b.dataset.tab) return;
        if (b.dataset.hist && typeof w.ctx.openProposal === "function") w.ctx.openProposal({ tab: b.dataset.tab });
        else if (typeof w.ctx.openTab === "function") w.ctx.openTab(b.dataset.tab);
        return;
      }
      if (b.dataset.c === "away_go") { awayOpen(box, w.ctx); return; }
      if (b.dataset.c === "away_fs") {              // what the line counts, framed on the flowsheet
        const A = aways.get(w.ctx.model);
        if (A && typeof w.ctx.showObjs === "function") w.ctx.showObjs(A.objs);
        return;
      }
      if (b.dataset.c === "away_all") { markAll(box, w.ctx); return; }
      if (b.dataset.c === "away_x") {              // put away for these records, here and after a reload
        const A = aways.get(w.ctx.model);
        if (A && typeof w.ctx.prefSet === "function") w.ctx.prefSet(dismissKey(A.model), JSON.stringify(A.upto));
        aways.delete(w.ctx.model);
        WBC.render(box, w.ctx);
        return;
      }
      if (!c) return;
      const gu = b.dataset.c === "more" && typeof w.ctx.menu === "function" ? (cpNow = w.ctx.cps || null, groupUndo(c, M, w.ctx)) : null;
      const tb = b.dataset.c === "more" && tbOn(w.ctx) && typeof w.ctx.menu === "function";
      if (b.dataset.c === "more" && (moreOn(w.ctx) || askMenu(w.ctx) || gu || tb)) {   // the group's ⋯: take it back, blocks, ask the AI, its report
        const group = { id: c.gid, title: titleOf(c) }, ctx = w.ctx, items = [];
        if (gu) items.push({ label: gu.label, icon: gu.icon, tip: t(gu.redo ? "tip_uv_group_redo" : "tip_uv_group"),
                             run: () => ctx.undo({ group: c.gid, anchor: b, label: group.title, redo: gu.redo }) }, { sep: true });
        if (tb) items.push({ label: t("to_blocks"), icon: "blocks", tip: ctx.connected ? t("tip_to_blocks") : t("why_off"), disabled: !ctx.connected,
                             run: () => ctx.toBlocks({ group: c.gid, label: group.title }) });
        if (askMenu(ctx)) items.push({ label: t("ask_group"), icon: "chat", run: () => ctx.ask({ kind: "group", id: c.gid, model: ctx.model, label: group.title }) });
        if (moreOn(ctx)) items.push({ label: t("rep_group"), icon: "download", run: () => WBC.report(b, ctx, group) });
        if (items.length && items[items.length - 1].sep) items.pop();
        ctx.menu(b, items, ev);
        return;
      }
      if (b.dataset.c === "walk") { walkStart(box, w.ctx, M, c, b); return; }   // step through it
      if (b.dataset.c === "help") {                // a record's “?”: its field's help card
        const r = c.recs.find((x) => x.id === b.dataset.id);
        if (r && typeof w.ctx.help === "function") w.ctx.help(b, r);
        return;
      }
      if (b.dataset.c === "ask") {                 // a record's Ask AI: the composer held on it
        const r = c.recs.find((x) => x.id === b.dataset.id);
        if (r && askOn(w.ctx)) w.ctx.ask(changeTarget(r, w.ctx));
        return;
      }
      // a record's ↶ Undo / ↷ Redo / Undo this restore, its group's options, a milestone's point
      if (b.dataset.c === "undo" || b.dataset.c === "nu_cp") {
        const r = c.recs.find((x) => x.id === b.dataset.id);
        if (!r || !undoOn(w.ctx)) return;
        if (b.dataset.c === "nu_cp") w.ctx.undo({ group: c.gid, anchor: b, label: titleOf(c) });
        else w.ctx.undo({ ids: [r.id], anchor: b, label: rowWords(r, w.ctx), redo: !!r.revert_of, restore: cpRestore(r) });
        return;
      }
      if (b.dataset.c === "cp_here") { if (rsOn(w.ctx)) w.ctx.restore({ checkpoint: b.dataset.cp, anchor: b }); return; }
      // a measured run: its effects opened or closed, every result shown, one input at a time
      const run = b.dataset.id ? c.recs.find((r) => r.id === b.dataset.id) : null;
      if (run && /^(rc|rcmore)$/.test(b.dataset.c)) {
        const el = b.closest(".rc");
        if (b.dataset.c === "rc") M.rc.set(run.id, !M.rc.get(run.id));
        else M.rcAll.add(run.id);
        const tpl = document.createElement("template");
        tpl.innerHTML = runCard(run, M, w.ctx.types || {}, w.ctx);
        const made = tpl.content.firstElementChild;
        el.replaceWith(made);
        if (b.dataset.c === "rc") {
          if (M.rc.get(run.id)) made.querySelector(".rc-body").classList.add("in");
          made.querySelector(".rc-tog").focus({ preventScroll: true });     // (the one pressed was replaced)
        }
        return;
      }
      if (run && b.dataset.c === "ofat") {
        if (typeof w.ctx.newTab === "function") w.ctx.newTab(t("rc_ofat_tab", run.seq), ofatProgram(run));
        return;
      }
      const t0 = performance.now();
      const same = b.dataset.c === "same";         // the writes that left a value as it was: shown or folded (sameOf)
      const drawn = M.rows.get(c.key) || ROWS;
      if (b.dataset.c === "rows") M.rows.set(c.key, Math.min(c.recs.length, drawn + ROWS_STEP));
      else if (same) { if (!M.same.delete(c.key)) M.same.add(c.key); }
      else M.open.set(c.key, !card.classList.contains("open"));
      const open = !!M.open.get(c.key), rows = card.querySelector(".ch-rows");
      if (open && b.dataset.c === "tog") seeCard(w.ctx, c);   // (its blocks' and streams' dots go)
      card.classList.toggle("open", open);
      card.querySelector(".ch-tog").setAttribute("aria-expanded", String(open));
      // 100 rows more: only those drawn after the ones there (where no folded line sits among them)
      if (b.dataset.c === "rows" && open && !sameOf(c, M).line) {
        b.remove();
        rows.insertAdjacentHTML("beforeend", rowsHtml(c, M, w.ctx.types || {}, w.ctx, drawn));
      } else rows.innerHTML = open ? rowsHtml(c, M, w.ctx.types || {}, w.ctx) : "";
      card._sig = `${w.gen}\u0002${cardSig(c, M)}`;
      if (same) { const sb = rows.querySelector(".ch-same"); if (sb) sb.focus({ preventScroll: true }); }   // (the one pressed was replaced)
      if (open && b.dataset.c !== "rows" && !same) {
        rows.classList.remove("in"); void rows.offsetWidth; rows.classList.add("in");
        // what opened below the fold comes into view, its head kept in sight
        const below = card.offsetTop + card.offsetHeight + 6 - (box.scrollTop + box.clientHeight);
        if (below > 0) box.scrollTop += Math.min(below, card.offsetTop - box.scrollTop - 4);
      }
      void card.offsetHeight;
      perf(WBC.perf.opens, { ms: Math.round((performance.now() - t0) * 100) / 100, rows: rows.querySelectorAll(".ch-row").length });
    });
  }

  function boxOf(box, ctx) {
    if (!box._wbc) { box._wbc = { ctx, sig: null, cards: null, view: null, parts: null, gen: "", jump: null }; wire(box); }
    return box._wbc;
  }
  WBC.render = function (box, ctx) {
    if (!box) return;
    const w = boxOf(box, ctx), show = !!ctx.show;
    w.ctx = Object.assign({}, ctx, { show: false });   // (an answer draws again with it: once only)
    look(box, w.ctx);                            // seen: a look at the model starts, goes on or ends
    if (!ctx.on) { if (w.sig !== "off") { box.innerHTML = ""; w.parts = null; w.sig = "off"; } return; }
    if (!ctx.shown) return;                      // hidden: nothing asked, nothing drawn
    const st = tabState(ctx.tab), M = ctx.model ? model(ctx.model, st.actors, okey(st.obj)) : null;
    if (M && !M.busy) {
      const want = sigOf(ctx.summary);
      if (!M.loaded) load(M, ctx, "first", box);
      else if (want !== M.sig || (show && (M.error || !ctx.summary))) load(M, ctx, "new", box);
    }
    // the away line counts again from the same moment when the journal moved while it shows
    const A = ctx.model ? aways.get(ctx.model) : null;
    if (A && !A.busy && A.sig !== sigOf(ctx.summary) && WBC.repOn()) {
      awayLoad(ctx, A.since).then(() => { const w2 = box._wbc; if (w2 && w2.ctx.model === ctx.model) WBC.render(box, w2.ctx); });
    }
    const strings = (window.WBL && WBL.strings) || ctx.strings || {}, s = ctx.summary && typeof ctx.summary === "object" ? ctx.summary : {};
    const D = ctx.model ? dots.get(ctx.model) : null;
    const sig = JSON.stringify([ctx.model, M && M.key, M && M.ver, M && M.loaded, I18N.lang, window.WBL ? WBL.ver : 0, D && D.sig, ctx.prefGet ? ctx.prefGet(`wb.seenobj.${ctx.model}`) : "",
      ctx.journalOn, strings.state === "running", ctx.types || {}, st.actors, okey(st.obj), st.bar, s.n, s.by, w.view && w.view.divider,
      rcSig(ctx), awaySig(ctx.model), WBC.repOn() && typeof ctx.menu === "function", extOn(), askOn(ctx), !!w.jump, uvSig(ctx),
      tbOn(ctx), selSig(ctx)]);
    if (sig !== w.sig) {
      w.sig = sig;
      if (w.model !== ctx.model) { w.model = ctx.model; box.scrollTop = 0; }
      draw(box, ctx, M);
    }
    selBar(box, w.ctx);                          // (select mode's foot: the connection moves it too)
  };
})();
