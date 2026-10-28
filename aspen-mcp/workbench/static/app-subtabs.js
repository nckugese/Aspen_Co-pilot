/* A model's sub-tabs and its History.
 *
 * The row (.subtabs, at the top of the program's column, over its card): a segmented control --
 * "My program" (the model tab's own program), the model's other programs, "+" ("New program"), then the
 * AI's proposals in progress in the order they were written (never reordered), and last those
 * opened from History (a clock, × puts one back) -- and at its right end "History n". A proposal
 * that finishes while shown stays until the user shows another sub-tab, then slides toward
 * History. The row is hidden while the model has only "My program", no proposal and no History; folded,
 * the column's strip counts the proposals in progress (a dot: one awaits review).
 *
 * The History popover (plate glass, from "History n"): the model's finished proposals (applied,
 * sent back, withdrawn, closed; state.history[mkey]) by day, newest first, a filter past eight;
 * a row opens its proposal (prop_open: loaded from the archive and shown), ⋯ shows its change
 * group or deletes its record (prop_delete, after a dialog). Keys: ↑ ↓ Enter Delete Esc.
 *
 * Keys anywhere: Ctrl+PgDn / Ctrl+PgUp the next or previous sub-tab, Ctrl+Shift+H History. In
 * the row: ← → Home End move, Enter / Space shows, Delete puts a pinned one back, Shift+F10 its
 * menu.
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { activate, addProgram, busy, closeMenus, closeTab, cycleTab, dialog, duplicateTab, esc, finished, glide, hhmm, icon, inRow,
    kidsOf, layout, num, openMenu, propHidden, propOf, propPill, propWord, renameTab, replaceTab, rootOf, saveTab, seeGroup, showCard,
    showIn, sideways, soon, stripView, t, tabOf, toast, toggleMenu, underline, wb } = WBA;

  const t0Of = (x) => { const p = x.proposal || {}; return num(p.t0) ? p.t0 : num(p.t) ? p.t : 0; };
  /** The model's History: its finished proposals, the newest first (state.history). */
  const histOf = (root) => (root && root.mkey ? (((wb.state && wb.state.history) || {})[root.mkey] || []) : [])
    .filter((e) => e && e.lane === "history" && e.tab);
  /** A program sub-tab's name: its own, or "Program N" where it still bears the session's name. */
  function progName(x, i) {
    const s = String(x.session || ""), ti = String(x.title || "");
    return !ti || ti === s || ti.startsWith(`${s} (`) ? t("sub_prog_n", i + 2) : ti;
  }

  // ------------------------------------------------------------------ the row
  /** What the row shows for the tab the pane shows: {root, progs, props, pins, hist}, or null. */
  function rowOf(pane) {
    const cur = tabOf(pane.tabId), root = rootOf(cur);
    if (!root) return null;
    const kids = kidsOf(root), shown = cur.id;
    const progs = kids.filter((x) => x.kind !== "proposal");
    const live = kids.filter((x) => x.kind === "proposal" && inRow(x, shown));
    const pinned = (x) => finished(x) && !!x.pinned;
    const byT0 = (a, b) => t0Of(a) - t0Of(b);
    return { cur, root, progs, props: live.filter((x) => !pinned(x)).sort(byT0), pins: live.filter(pinned).sort(byT0), hist: histOf(root) };
  }
  /** A segment's small dot (not on the one shown): to review, running or stepping, failed, part done. */
  function dotOf(x) {
    if (propOf(x)) {
      const k = (propPill(x) || {}).key;
      return k === "open" ? "review" : k === "running" || k === "paused" ? "run" : k === "failed" ? "fail" : k === "partial" ? "warn" : "";
    }
    const st = (x.run || {}).status;
    return busy(x) ? "run" : st === "error" ? "fail" : "";
  }
  function segHtml(x, kind, name, on) {
    const p = propOf(x), d = on ? "" : dotOf(x), keys = t("tip_sub_keys");
    let tip;
    if (p) {
      const rev = Number(p.rev) || 1;
      tip = [p.title || x.title, propWord(x) + (rev > 1 ? ` · ${t("prop_meta", rev)}` : ""), t("tip_sub_ai"), keys];
    } else tip = [name, keys];
    const lead = kind === "pin" ? icon("clock") : kind === "prop" ? icon("sparkle") : "";
    const end = kind === "pin" ? `<span class="sx" data-shelve="${esc(x.id)}" role="button" title="${esc(t("tip_sub_shelve"))}">${icon("close")}</span>` : "";
    return `<button class="sub ${kind}${on ? " on" : ""}${busy(x) ? " busy" : ""}" role="tab" aria-selected="${on}" tabindex="${on ? 0 : -1}"`
      + ` data-tab="${esc(x.id)}" title="${esc(tip.filter(Boolean).join("\n"))}">${lead}<span class="sn">${esc(name)}</span>`
      + `${d ? `<i class="sdot ${d}"></i>` : ""}${end}<i class="uline"><b></b></i></button>`;
  }

  /** The row of the shown tab's model, and the folded column's count. Drawn again only when what
   *  it shows moved; a proposal that left it (finished, shown no more) slides toward History. */
  function renderSubtabs() {
    const pane = wb.pane, row = pane && pane.q(".subtabs");
    if (!row) return;
    const m = rowOf(pane);
    renderStrip(pane, m);
    const on = !!m && (m.progs.length + m.props.length + m.pins.length + m.hist.length > 0);
    if (!on) {
      if (!row.classList.contains("hidden")) { row.classList.add("hidden"); layout(); }
      row.dataset.sig = "";
      [...row.querySelectorAll(".sub-track > .sub")].forEach((el) => el.remove());   // (nothing of another model's left behind)
      return;
    }
    const segs = [[m.root, "mine", t("prog_mine")], ...m.progs.map((x, i) => [x, "prog", progName(x, i)]),
      ...m.props.map((x) => [x, "prop", (propOf(x) || {}).title || x.title]), ...m.pins.map((x) => [x, "pin", (propOf(x) || {}).title || x.title])];
    const sig = JSON.stringify([I18N.lang, m.cur.id, wb.connected, m.hist.length, segs.map(([x, k, n]) => [x.id, k, n, dotOf(x), busy(x), propWord(x),
      (x.proposal || {}).rev]), m.props.length > 0 || m.pins.length > 0]);
    const wasHidden = row.classList.contains("hidden");
    row.classList.remove("hidden");
    if (wasHidden) layout();
    if (row.dataset.sig === sig) return;
    row.dataset.sig = sig;
    const track = row.querySelector(".sub-track"), hb = row.querySelector(".sub-hist");
    // what was there, to see what left (a ghost of each finished proposal slides to History)
    const before = new Map([...track.querySelectorAll(".sub.prop, .sub.pin")].map((el) => [el.dataset.tab, el]));
    pane.subGlide = pane.subGlide || Object.assign(document.createElement("i"), { className: "glide gx" });
    const keep = pane.subGlide;
    const same = pane.subRoot === m.root.id, inHist = new Set(m.hist.map((e) => e.tab));
    pane.subRoot = m.root.id;
    const ghosts = !same ? [] : [...before].filter(([id]) => !segs.some(([x]) => x.id === id)).map(([id, el]) => {
      const tab = tabOf(id), r = el.getBoundingClientRect();
      return (tab ? finished(tab) : inHist.has(id)) && r.width ? { el: el.cloneNode(true), r } : null;
    }).filter(Boolean);
    const div = m.props.length || m.pins.length ? `<i class="sub-div" aria-hidden="true"></i>` : "";
    const add = `<button class="sub-add flat icon" data-sub="add" tabindex="-1" title="${esc(wb.connected ? t("tip_sub_add") : t("why_off"))}"`
      + `${wb.connected ? "" : " disabled"} aria-label="${esc(t("sub_add"))}">${icon("plus")}</button>`;
    // (drawn anew around the glide, which stays in place: taken out and put back, it would jump instead of
    // sliding; the keyboard's focus, where it was in the row, goes to the one shown)
    const hadFocus = track.contains(document.activeElement);
    [...track.children].forEach((el) => { if (el !== keep) el.remove(); });
    if (keep.parentNode !== track) track.prepend(keep);
    track.insertAdjacentHTML("beforeend", segs.slice(0, 1 + m.progs.length).map(([x, k, n]) => segHtml(x, k, n, x.id === m.cur.id)).join("") + add + div
      + segs.slice(1 + m.progs.length).map(([x, k, n]) => segHtml(x, k, n, x.id === m.cur.id)).join(""));
    track.setAttribute("aria-label", t("sub_tablist"));
    // "History n": hidden at none; the count springs when it grows
    const n0 = Number(hb.dataset.n || 0);
    hb.classList.toggle("hidden", !m.hist.length);
    hb.querySelector(".sh-t").textContent = t("sub_hist");
    hb.querySelector(".sh-n").textContent = String(m.hist.length);
    hb.title = t("tip_sub_hist");
    hb.dataset.n = String(m.hist.length);
    if (m.hist.length > n0 && n0 && ghosts.length === 0) hb.querySelector(".sh-n").animate([{ transform: "scale(1.25)" }, { transform: "none" }], { duration: 320, easing: "cubic-bezier(.3, 1.35, .5, 1)" });
    segs.forEach(([x]) => { if (busy(x)) underline(x.id); });
    stripView(track, track.querySelector(".sub.on"));
    glide(keep, track.querySelector(".sub.on"));
    if (hadFocus && track.querySelector(".sub.on")) track.querySelector(".sub.on").focus({ preventScroll: true });
    ghosts.forEach((g) => leave(row, hb, g));
  }
  /** A finished proposal leaving the row: its copy slides toward History and fades (transform and
   *  opacity only), then the count springs. */
  function leave(row, hb, g) {
    const R = row.getBoundingClientRect(), el = g.el;
    el.classList.add("ghost");
    el.classList.remove("on");
    el.removeAttribute("data-tab");
    el.setAttribute("aria-hidden", "true");
    el.tabIndex = -1;
    el.style.left = `${g.r.left - R.left}px`;
    el.style.top = `${g.r.top - R.top}px`;
    row.appendChild(el);
    const to = hb.classList.contains("hidden") ? null : hb.getBoundingClientRect();
    const dx = to ? to.left + to.width / 2 - (g.r.left + g.r.width / 2) : 24;
    el.animate([{ transform: "none", opacity: 1 }, { transform: `translateX(${Math.round(dx)}px) scale(.6)`, opacity: 0 }],
      { duration: 340, easing: "cubic-bezier(.4, 0, 1, 1)", fill: "forwards" }).onfinish = () => {
      el.remove();
      if (!hb.classList.contains("hidden")) hb.querySelector(".sh-n").animate([{ transform: "scale(1.25)" }, { transform: "none" }], { duration: 320, easing: "cubic-bezier(.3, 1.35, .5, 1)" });
    };
  }
  /** The folded column's strip: ✦ and the count of the proposals in progress, a dot where one
   *  awaits review. */
  function renderStrip(pane, m) {
    const box = pane.q(".prog-strip .ps-prop");
    if (!box) return;
    const live = m ? [...m.props, ...m.pins].filter((x) => propOf(x) && !finished(x) && !["withdrawn", "dismissed"].includes(propOf(x).status)) : [];
    const review = live.some((x) => (propPill(x) || {}).key === "open");
    box.classList.toggle("hidden", !live.length);
    box.querySelector(".ps-n").textContent = live.length ? String(live.length) : "";
    box.querySelector(".ps-rv").classList.toggle("hidden", !review);
    box.title = live.length ? t("tip_strip_props", live.length) : "";
  }

  /** Show a sub-tab (the one shown: a proposal's window hidden by its × comes back). */
  function go(pane, id) {
    const x = tabOf(id);
    if (!x) return;
    if (id === pane.tabId) { if (propOf(x) && propHidden(id)) showCard(pane); return; }
    showIn(pane, id);
    activate(id);
  }

  /** A sub-tab's menu: a proposal's (open, close it, put it back, its changes, delete its record) or a
   *  program's (rename, duplicate, its .awb, close; "My program": duplicate and its .awb). */
  function subItems(pane, x) {
    const p = propOf(x), off = wb.connected ? "" : t("why_off"), shown = pane.tabId === x.id;
    if (p) {
      const hist = finished(x), run = busy(x) || p.status === "running", gid = (p.run || {}).group;
      return [
        { label: t("open"), icon: "sparkle", disabled: shown && !propHidden(x.id), run: () => go(pane, x.id) },
        ...(!hist ? [{ label: t("btn_dismiss_prop"), icon: "close", disabled: run || !wb.connected, tip: run ? t("del_running") : off,
          run: () => wb.post({ type: "proposal_reply", tab: x.id, action: "dismiss" }) }] : []),
        ...(hist ? [{ label: t("sub_shelve"), icon: "clock", tip: t("tip_sub_shelve"), disabled: !wb.connected, run: () => closeTab(x.id) }] : []),
        ...(gid && WBC.on() ? [{ label: t("hist_changes"), icon: "list", run: () => seeGroup(pane, x, gid) }] : []),
        ...(hist ? [{ sep: true }, { label: t("hist_delete"), icon: "trash", danger: true, disabled: run || !wb.connected,
          tip: run ? t("del_running") : off, run: () => askDelete({ tab: x.id, title: p.title || x.title }) }] : []),
      ];
    }
    if (x === rootOf(x)) {
      return [
        { label: t("m_duplicate"), icon: "copy", disabled: !wb.connected, tip: off, run: () => duplicateTab(x.id) },
        { label: t("m_save_awb"), icon: "save", keys: shown ? "Ctrl+Shift+S" : "", run: () => saveTab(x.id) },
        { label: t("m_replace"), icon: "folder", run: () => replaceTab(x.id) },
      ];
    }
    return [
      { label: t("m_rename"), icon: "pen", run: () => renameTab(x.id) },
      { label: t("m_duplicate"), icon: "copy", disabled: !wb.connected, tip: off, run: () => duplicateTab(x.id) },
      { label: t("m_save_awb"), icon: "save", keys: shown ? "Ctrl+Shift+S" : "", run: () => saveTab(x.id) },
      { sep: true },
      { label: t("close"), icon: "close", danger: true, run: () => closeTab(x.id) },
    ];
  }

  function wireSubtabs(pane) {
    const row = pane.q(".subtabs"), track = row.querySelector(".sub-track");
    row.addEventListener("click", (ev) => {
      const sx = ev.target.closest("[data-shelve]");
      if (sx) { ev.stopPropagation(); closeTab(sx.dataset.shelve); return; }
      const b = ev.target.closest("[data-sub]");
      if (b && b.dataset.sub === "add") { addProgram(rootOf(tabOf(pane.tabId))); return; }
      if (b && b.dataset.sub === "hist") { toggleHist(b); return; }
      const seg = ev.target.closest(".sub[data-tab]");
      if (seg) go(pane, seg.dataset.tab);
    });
    row.addEventListener("dblclick", (ev) => {
      const seg = ev.target.closest(".sub.prog[data-tab]");
      if (seg && !ev.target.closest("[data-shelve]")) renameTab(seg.dataset.tab);
    });
    row.addEventListener("contextmenu", (ev) => {
      const seg = ev.target.closest(".sub[data-tab]"), x = seg && tabOf(seg.dataset.tab);
      if (!x) return;
      ev.preventDefault();
      openMenu({ x: ev.clientX, y: ev.clientY }, subItems(pane, x));
    });
    // the keyboard inside the row: a roving focus (one segment in the tab order)
    track.addEventListener("keydown", (ev) => {
      const seg = ev.target.closest(".sub[data-tab]");
      if (!seg) return;
      const segs = [...track.querySelectorAll(".sub[data-tab]")], i = segs.indexOf(seg), k = ev.key;
      let to = null;
      if (k === "ArrowRight") to = segs[(i + 1) % segs.length];
      else if (k === "ArrowLeft") to = segs[(i - 1 + segs.length) % segs.length];
      else if (k === "Home") to = segs[0];
      else if (k === "End") to = segs[segs.length - 1];
      else if (k === "Delete" && seg.classList.contains("pin")) { closeTab(seg.dataset.tab); }
      else if ((k === "F10" && ev.shiftKey) || k === "ContextMenu") {
        const x = tabOf(seg.dataset.tab);
        if (x) openMenu(seg, subItems(pane, x), false, true);
      } else return;
      ev.preventDefault();
      ev.stopPropagation();
      if (to) { segs.forEach((b) => { b.tabIndex = b === to ? 0 : -1; }); to.focus(); }
    });
    sideways(track);
    new ResizeObserver(() => soon("subFit", () => { stripView(track); glide(pane.subGlide, track.querySelector(".sub.on")); })).observe(track);
  }

  // ------------------------------------------------------------------ History
  const HP = { el: null, at: null, rows: [], q: "" };
  const dayKey = (s) => { const d = new Date(s * 1000); return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`; };
  function dayName(s) {
    const d = new Date(s * 1000), now = new Date(), y = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
    if (d.toDateString() === now.toDateString()) return t("today");
    if (d.toDateString() === y.toDateString()) return t("hist_yesterday");
    return I18N.lang === "zh" ? `${d.getMonth() + 1} 月 ${d.getDate()} 日` : d.toLocaleDateString("en", { month: "short", day: "numeric" });
  }
  /** An entry's state in a word: applied, sent back, withdrawn, closed. */
  const stWord = (e) => t(`prop_st_${["applied", "rejected", "withdrawn", "dismissed"].includes(e.status) ? e.status : "dismissed"}`);
  /** Whether an entry's record may be deleted: not while its proposal runs or awaits a decision. */
  const deletable = (e) => { const x = tabOf(e.tab); return !x || (!busy(x) && finished(x)); };

  function histHtml(root) {
    const all = histOf(root), q = HP.q.trim().toLowerCase();
    const rows = q ? all.filter((e) => String(e.title || "").toLowerCase().includes(q)) : all;
    HP.rows = rows;
    let html = `<div class="hp-head"><b>${esc(t("prop_hist"))}</b><span class="hp-n">(${all.length})</span></div>`;
    if (all.length > 8) html += `<input class="hp-filter" type="text" spellcheck="false" placeholder="${esc(t("hist_filter"))}" aria-label="${esc(t("hist_filter"))}">`;
    html += `<div class="hp-list" role="listbox" aria-label="${esc(t("prop_hist"))}">`;
    if (!rows.length) html += `<div class="hp-empty">${esc(all.length ? t("hist_none_match") : t("hist_empty"))}</div>`;
    let day = null;
    rows.forEach((e, i) => {
      const at = num(e.t) ? e.t : num(e.t0) ? e.t0 : 0;
      if (dayKey(at) !== day) { day = dayKey(at); html += `<div class="hp-g" role="presentation">${esc(dayName(at))}</div>`; }
      const meta = t("hist_row", stWord(e), hhmm(at), Number(e.rev) || 1) + (e.undone ? ` · ${t("hist_undone")}` : "");
      html += `<div class="hp-row" role="option" tabindex="${i ? -1 : 0}" data-i="${i}" title="${esc(e.title || "")}">${icon("sparkle")}`
        + `<div class="hp-tx"><div class="hp-t">${esc(e.title || e.tab)}</div><div class="hp-m"><i class="hp-dot s-${esc(e.status || "")}"></i>`
        + `<span>${esc(meta)}</span></div></div>`
        + `<button class="hp-more flat icon" data-hm="${i}" tabindex="-1" title="${esc(t("tip_hist_more"))}" aria-haspopup="menu">${icon("more")}</button></div>`;
    });
    return `${html}</div>`;
  }
  /** Open (or close) the History popover from its button: under it, its right edge on the
   *  button's, inside the window; it springs from the button. */
  function toggleHist(btn) {
    if (HP.el && !HP.el.classList.contains("hidden")) { closeHist(); return; }
    const pane = wb.pane, root = pane && rootOf(tabOf(pane.tabId));
    if (!root) return;
    if (!histOf(root).length) { toast(t("hist_empty"), 2500); return; }
    btn = btn || pane.q(".subtabs .sub-hist");
    if (!btn || !btn.offsetWidth) return;
    closeMenus();
    if (!HP.el) {
      HP.el = Object.assign(document.createElement("div"), { className: "hist-pop plate hidden", id: "hist-pop", tabIndex: -1 });
      HP.el.setAttribute("role", "dialog");
      document.body.appendChild(HP.el);
      HP.el.addEventListener("click", histClick);
      HP.el.addEventListener("input", (ev) => {
        if (!ev.target.classList.contains("hp-filter")) return;
        HP.q = ev.target.value;
        fillHist(true);
      });
    }
    HP.at = btn;
    HP.q = "";
    HP.el.setAttribute("aria-label", t("prop_hist"));
    btn.setAttribute("aria-expanded", "true");
    fillHist(false);
    HP.el.classList.remove("hidden");
    placeHist();
    const f = HP.el.querySelector(".hp-filter") || HP.el.querySelector(".hp-row");
    if (f) f.focus({ preventScroll: true });
  }
  /** The popover's contents drawn (keepFilter: the filter typed into keeps its focus and caret). */
  function fillHist(keepFilter) {
    const pane = wb.pane, root = pane && rootOf(tabOf(pane.tabId));
    if (!root || !HP.el) return;
    if (keepFilter && HP.el.querySelector(".hp-filter")) {
      const tmp = document.createElement("div");
      tmp.innerHTML = histHtml(root);
      HP.el.querySelector(".hp-list").replaceWith(tmp.querySelector(".hp-list"));
      HP.el.querySelector(".hp-n").textContent = tmp.querySelector(".hp-n").textContent;
      return;
    }
    HP.el.innerHTML = histHtml(root);
    const inp = HP.el.querySelector(".hp-filter");
    if (inp) inp.value = HP.q;
  }
  function placeHist() {
    const el = HP.el, r = HP.at.getBoundingClientRect(), w = el.offsetWidth, h = el.offsetHeight, vw = window.innerWidth, vh = window.innerHeight;
    const x = Math.max(8, Math.min(r.right - w, vw - w - 8)), y = Math.min(r.bottom + 6, Math.max(8, vh - h - 8));
    el.style.left = `${Math.round(x)}px`;
    el.style.top = `${Math.round(y)}px`;
    el.style.transformOrigin = `${Math.round(r.left + r.width / 2 - x)}px 0`;
  }
  function closeHist(back) {
    if (!HP.el || HP.el.classList.contains("hidden")) return false;
    HP.el.classList.add("hidden");
    if (HP.at) HP.at.setAttribute("aria-expanded", "false");
    if (back && HP.at && HP.at.isConnected) HP.at.focus({ preventScroll: true });
    return true;
  }
  const histOpen = () => !!HP.el && !HP.el.classList.contains("hidden");
  function histClick(ev) {
    const more = ev.target.closest("[data-hm]");
    if (more) { ev.stopPropagation(); entryMenu(more, HP.rows[Number(more.dataset.hm)], ev); return; }
    const row = ev.target.closest(".hp-row");
    if (row) openEntry(HP.rows[Number(row.dataset.i)]);
  }
  function entryMenu(anchor, e, ev) {
    if (!e) return;
    const pane = wb.pane, cur = pane && tabOf(pane.tabId), ok = deletable(e);
    toggleMenu(anchor, () => [
      { label: t("open"), icon: "sparkle", disabled: !wb.connected, tip: wb.connected ? "" : t("why_off"), run: () => openEntry(e) },
      ...(e.group && cur && WBC.on() ? [{ label: t("hist_changes"), icon: "list", run: () => { closeHist(); seeGroup(pane, cur, e.group); } }] : []),
      { sep: true },
      { label: t("hist_delete"), icon: "trash", danger: true, disabled: !ok || !wb.connected, tip: !ok ? t("del_running") : wb.connected ? "" : t("why_off"),
        run: () => askDelete(e) },
    ], ev);
  }
  /** A History entry opened: shown at once where it is still loaded, else when the server has
   *  brought it back from the archive (prop_open; subSync). It stays in the row (pinned). */
  function openEntry(e) {
    if (!e || !wb.connected) return;
    closeHist();
    const pane = wb.pane, x = tabOf(e.tab);
    wb.post({ type: "prop_open", tab: e.tab });
    if (x && pane) {
      if (pane.tabId !== x.id) showIn(pane, x.id);
      wb.lastActive = x.id;
      wb.pendingActive = { id: x.id, until: Date.now() + 3000 };
      (wb.fronts = wb.fronts || new Map()).set(rootOf(x).id, x.id);
      return;
    }
    wb.histWait = { id: e.tab, until: Date.now() + 60000 };
  }
  /** "Delete proposal record…": asked first (the red button apart from Cancel, which has the focus). */
  function askDelete(e) {
    if (!e || !deletable(e)) { toast(t("del_running")); return; }
    closeHist();
    dialog({ title: t("del_title"), body: t("del_body", e.title || e.tab), ok: t("del_go"), okClass: "danger-solid", focus: "cancel",
             onOk: () => { wb.post({ type: "prop_delete", tab: e.tab }); toast(t("del_done", e.title || e.tab), 3000); } });
  }

  /** A new state: an entry opened from History shown once it is loaded; the popover follows the
   *  model's History (closed when the model is not shown any more). */
  function subSync(s) {
    const w = wb.histWait;
    if (w && (Date.now() > w.until)) wb.histWait = null;
    else if (w && s.tabs.some((x) => x.id === w.id) && wb.pane) {
      wb.histWait = null;
      const x = tabOf(w.id);
      (wb.fronts = wb.fronts || new Map()).set(rootOf(x).id, x.id);
      showIn(wb.pane, w.id);
      wb.lastActive = w.id;
    }
    if (histOpen()) {
      const root = wb.pane && rootOf(tabOf(wb.pane.tabId));
      if (!root || !histOf(root).length || !HP.at || !HP.at.isConnected || !HP.at.offsetWidth) closeHist();
      else fillHist(true);
    }
  }

  /** The keys (app-main.js onKey, ahead of the rest): the History popover's while it is open,
   *  Ctrl+PgDn / Ctrl+PgUp and Ctrl+Shift+H anywhere. True when taken. */
  function subKey(ev) {
    const k = ev.key, ctrl = ev.ctrlKey || ev.metaKey;
    if (histOpen()) {
      const el = HP.el, rows = [...el.querySelectorAll(".hp-row")], at = rows.indexOf(document.activeElement);
      const inFilter = document.activeElement && document.activeElement.classList.contains("hp-filter");
      const focusRow = (i) => { const r = rows[Math.max(0, Math.min(rows.length - 1, i))]; if (!r) return; rows.forEach((x) => { x.tabIndex = x === r ? 0 : -1; }); r.focus(); r.scrollIntoView({ block: "nearest" }); };
      if (k === "Escape") { closeHist(true); return true; }
      if (k === "ArrowDown") { focusRow(at < 0 ? 0 : at + 1); return true; }
      if (k === "ArrowUp") { if (at <= 0 && el.querySelector(".hp-filter")) el.querySelector(".hp-filter").focus(); else focusRow(at - 1); return true; }
      if (k === "Enter" && (at >= 0 || inFilter)) { openEntry(HP.rows[at >= 0 ? Number(rows[at].dataset.i) : 0]); return true; }
      if (k === "Delete" && at >= 0) { askDelete(HP.rows[Number(rows[at].dataset.i)]); return true; }
      if ((k === "F10" && ev.shiftKey) || k === "ContextMenu") {
        if (at >= 0) entryMenu(rows[at].querySelector(".hp-more"), HP.rows[Number(rows[at].dataset.i)], { detail: 0 });
        return true;
      }
      if (!el.contains(document.activeElement) && k !== "Tab") closeHist();
    }
    const el = document.activeElement;
    if (el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName))) return false;   // (typing: the text box's)
    if (ctrl && !ev.altKey && (k === "PageDown" || k === "PageUp")) return cycleTab(k === "PageDown" ? 1 : -1, true);
    if (ctrl && ev.shiftKey && !ev.altKey && k.toLowerCase() === "h") {
      if (histOpen()) closeHist(true);
      else toggleHist(null);
      return true;
    }
    return false;
  }
  // a press outside the popover (not on a menu it opened or the dialog it asks) closes it
  document.addEventListener("pointerdown", (ev) => {
    if (histOpen() && !ev.target.closest("#hist-pop, .menu, #modal, .sub-hist")) closeHist();
  }, true);
  window.addEventListener("resize", () => { if (histOpen()) closeHist(); });

  Object.assign(WBA, { openEntry, renderSubtabs, subKey, subSync, wireSubtabs });
})();
