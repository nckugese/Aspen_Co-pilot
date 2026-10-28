/* Two requests the server answers in the session's state: the timeline made into
 * blocks and Aspen's own drawing laid out again.
 *
 *   toBlocks(tab, o)     o {model, group | ids}: event to_blocks {tab, model, group, ids, req};
 *                        answered in sessions[s].to_blocks_req {req, status done | none | failed,
 *                        tab, n, steps, skipped [{code, n}], missing, text}. Done: the new tab is
 *                        shown and a toast says how many steps came of how many changes and what
 *                        was skipped and why, and for a group offers Restore to before this group
 *                        (its undo preview: the same result needs the model as it was before it);
 *                        none: why nothing came of them.
 *   aspenRedraw(tab)     event aspen_redraw {tab, req}: answered in sessions[s].redraw_req {req,
 *                        status running, then done | failed | busy | closed, text}.
 *   aspenPlace(pane, tab) the flowsheet's arrangement as drawn here into Aspen's own drawing: a
 *                        confirmation first (Aspen saves the model -- what is unsaved said --,
 *                        closes and reopens it), then event aspen_place {tab, req, blocks: {name:
 *                        [x, y]}} (the drawn block centres), answered as aspen_redraw.
 *   redrawWhy(tab)       why Redraw cannot start now (the flowsheet's ⋯ says so), or ""
 *   replaySync()         a new state: what came for each request waited for (app-state.js)
 *
 * Nothing here writes the model: the server does, as the user's.
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { base, busy, dialog, esc, feature, isOpen, sessOf, t, tabOf, toast, wb } = WBA;
  const { activate, showIn, undoOpen } = WBA.later;

  const KEEP_MS = 120000;                              // a request not answered in this long is let go
  const W = [];                                        // {kind: tb | rd, req, session, tab, sent; tb: group, label}
  const uid = () => `r${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  const drop = (w) => { const i = W.indexOf(w); if (i >= 0) W.splice(i, 1); };
  const has = (key) => I18N.t(key) !== key;

  /** Records into blocks: a change group (o.group) or the records picked (o.ids). */
  function toBlocks(tab, o) {
    if (!tab || !feature("to_blocks")) return;
    if (!wb.connected) { toast(t("why_off")); return; }
    const ids = Array.isArray(o.ids) && o.ids.length ? o.ids.slice(0, 200) : null;
    const w = { kind: "tb", req: uid(), session: tab.session, tab: tab.id, sent: Date.now(), group: ids ? null : o.group || null, label: o.label || "" };
    W.push(w);
    wb.post({ type: "to_blocks", tab: tab.id, model: o.model || null, group: w.group, ids, req: w.req });
    toast(t("to_blocks_wait"), 2500);
  }
  /** What was skipped, in words: "save, attribute settings" (tb_skip_*: the server's codes; one it has no words for: other changes). */
  function skipWords(list) {
    const words = [];
    (Array.isArray(list) ? list : []).forEach((s) => {
      const w = s && has(`tb_skip_${s.code}`) ? t(`tb_skip_${s.code}`) : t("tb_skip_other");
      if (!words.includes(w)) words.push(w);
    });
    return words.join(t("tb_sep"));
  }
  function gotBlocks(w, q) {
    const skipped = Array.isArray(q.skipped) ? q.skipped : [], m = skipped.reduce((a, s) => a + (Number(s && s.n) || 0), 0);
    if (q.status === "none") { toast(m ? t("to_blocks_none_why", skipWords(skipped)) : t("to_blocks_none"), 6000); return; }
    if (q.status !== "done") { toast(t("to_blocks_failed", q.text || "?"), 6000); return; }
    let text = m ? t("to_blocks_done", q.n ?? "?", q.steps ?? "?", m, skipWords(skipped)) : t("to_blocks_done0", q.n ?? "?", q.steps ?? "?");
    if (Number(q.missing) > 0) text += t("to_blocks_missing", q.missing);
    const go = () => { if (wb.pane && tabOf(q.tab)) { showIn(wb.pane, q.tab); activate(q.tab); } };
    go();                                            // (the server made it the active tab too)
    const shown = !!wb.pane && wb.pane.tabId === q.tab;
    // the same result again takes the model back to before the group first: its preview
    const back = w.group && feature("undo") ? tabOf(w.tab) || tabOf(q.tab) : null;
    toast(text, back ? 9000 : 7000, !shown && q.tab ? { label: t("to_blocks_open"), run: go }
      : back ? { label: t("uv_group_rs"), run: () => undoOpen(back, { group: w.group, label: w.label }) } : undefined);
  }

  /** Aspen's own drawing laid out again, as the user's (it reopens the model in Aspen). */
  function redrawWhy(tab) {
    if (!wb.connected) return t("why_off");
    if (!isOpen(tab)) return t("why_closed", tab.session);
    if (((wb.state && wb.state.tabs) || []).some((x) => x.session === tab.session && busy(x))) return t("why_redraw_busy");
    const q = ((wb.state.sessions || {})[tab.session] || {}).redraw_req;
    if (W.some((w) => w.kind === "rd" && w.session === tab.session) || (q && q.status === "running")) return t("redraw_wait");
    return "";
  }
  function aspenRedraw(tab) {
    if (!tab) return;
    const why = redrawWhy(tab);
    if (why) { toast(why); return; }
    const w = { kind: "rd", req: uid(), session: tab.session, tab: tab.id, sent: Date.now() };
    W.push(w);
    wb.post({ type: "aspen_redraw", tab: tab.id, req: w.req });
    toast(t("redraw_wait"), 4000);
  }
  /** The blocks as drawn in the pane (FS.explicitOf: their centres), by name; null when none. */
  function drawnBlocks(pane) {
    const ex = pane && pane.svg && FS.explicitOf(pane.svg), out = {};
    Object.entries((ex && ex.nodes) || {}).forEach(([k, p]) => { if (k.startsWith("B:") && Array.isArray(p)) out[k.slice(2)] = [p[0], p[1]]; });
    return Object.keys(out).length ? out : null;
  }
  /** Why the arrangement cannot go to Aspen now, or "" (the flowsheet's ⋯ says so). */
  function placeWhy(pane, tab) {
    return redrawWhy(tab) || (drawnBlocks(pane) ? "" : t("why_place_empty"));
  }
  /** The arrangement as drawn here into Aspen's own drawing, once the user confirms: it saves
   *  the model in Aspen (what is unsaved said first) and reopens it. */
  function aspenPlace(pane, tab) {
    if (!tab) return;
    const why = placeWhy(pane, tab);
    if (why) { toast(why); return; }
    const j = sessOf(tab).journal, u = j && typeof j === "object" && j.unsaved && typeof j.unsaved === "object" ? j.unsaved : null;
    const n = u ? Number(u.n) || 0 : 0, file = base(((sessOf(tab).model || {}).file) || tab.session);
    const li = [t("place_b_save", file), n ? t("place_b_unsaved", `${n}${u.more ? "+" : ""}`) : "", t("place_b_reopen"), t("place_b_streams")].filter(Boolean);
    dialog({ title: t("place_title"), html: `<ul class="uv-b">${li.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`,
      ok: t("place_go"), focus: "ok", onOk: () => {
        const blocks = drawnBlocks(pane), again = placeWhy(pane, tab);
        if (again || !blocks) { toast(again || t("why_place_empty")); return; }
        const w = { kind: "rd", place: true, req: uid(), session: tab.session, tab: tab.id, sent: Date.now() };
        W.push(w);
        wb.post({ type: "aspen_place", tab: tab.id, req: w.req, blocks });
        toast(t("place_wait"), 4000);
      } });
  }
  function gotRedraw(w, q) {
    if (w.place) toast(q.text ? String(q.text) : t(q.status === "done" ? "place_done" : "redraw_failed", q.status || "?"), q.status === "done" ? 5000 : 7000);
    else if (q.status === "done") toast(t("redraw_done"), 4000);
    else toast(q.text ? String(q.text) : t("redraw_failed", q.status || "?"), 6000);
  }

  function replaySync() {
    if (!wb.state) return;
    W.slice().forEach((w) => {
      if (Date.now() - w.sent > KEEP_MS) { drop(w); return; }
      const sess = (wb.state.sessions || {})[w.session] || {}, q = sess[w.kind === "tb" ? "to_blocks_req" : "redraw_req"];
      if (!q || typeof q !== "object" || q.req !== w.req || q.status === "running") return;
      drop(w);
      if (w.kind === "tb") gotBlocks(w, q);
      else gotRedraw(w, q);
    });
  }

  Object.assign(WBA, { aspenPlace, aspenRedraw, placeWhy, redrawWhy, replaySync, toBlocks });
})();
