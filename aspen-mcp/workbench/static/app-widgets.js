/* Generic controls: the menus (#menu, #menu2: open, place, keys), the one dialog (dialog,
 * modal), toast, ghost (an exit animation on a copy), copyText, saveFile.
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { $, esc, icon, t, wb } = WBA;
  const { endsHtml } = WBA.later;

  // ------------------------------------------------------------------ menus
  // One menu at a time (#menu), and a submenu beside it (#menu2). An item is {label, icon,
  // keys, run, danger, disabled, tip, cls (a class of its own), others (names the label is
  // told apart from: endsHtml), sub: [items]}, {sep: true}, {title} or {html, wire(el)}.
  const menuOpen = () => !$("menu").classList.contains("hidden");

  function closeMenus() {
    const m1 = $("menu"), m2 = $("menu2"), at = wb.menuBack || wb.menuAt;
    const inside = m1.contains(document.activeElement) || m2.contains(document.activeElement);
    m1.classList.add("hidden");
    m2.classList.add("hidden");
    wb.menuAt = wb.menuBack = null;
    if (inside && at && at.focus) at.focus({ preventScroll: true });   // the keyboard goes back where it was
  }

  /** The + menu, the ... menu: a second click on the button closes its menu. A menu opened
   *  from the keyboard puts the focus on its first item, and gives it back to the button
   *  pressed (the model chip's menu hangs from the chip, which two buttons open). */
  function toggleMenu(anchor, items, ev) {
    if (menuOpen() && wb.menuAt === anchor) { closeMenus(); return; }
    openMenu(anchor, items(), false, ev && ev.detail === 0);
    wb.menuBack = (ev && ev.target && ev.target.closest && ev.target.closest("button")) || null;
  }

  function openMenu(at, items, sub, keyboard) {
    const menu = $(sub ? "menu2" : "menu");
    if (!sub) { closeMenus(); wb.menuAt = at; }
    menu.innerHTML = "";
    items.forEach((it) => {
      if (it.sep) { menu.insertAdjacentHTML("beforeend", `<div class="msep"></div>`); return; }
      if (it.title) { menu.insertAdjacentHTML("beforeend", `<div class="mt">${esc(it.title)}</div>`); return; }
      if (it.html) {
        const box = Object.assign(document.createElement("div"), { className: "mhtml", innerHTML: it.html });
        menu.appendChild(box);
        if (it.wire) it.wire(box);
        return;
      }
      // (check: an item that is on or off -- ticked, in the accent, where on; aside: a quiet word at
      // its end, such as where a proposal stands)
      const b = document.createElement("button"), ck = typeof it.check === "boolean";
      b.className = `mi${it.danger ? " danger" : ""}${it.sub ? " has-sub" : ""}${it.cls ? ` ${it.cls}` : ""}`;
      b.disabled = !!it.disabled;
      b.setAttribute("role", ck ? "menuitemcheckbox" : "menuitem");
      if (ck) b.setAttribute("aria-checked", String(it.check));
      b.innerHTML = (ck && it.check ? icon("check") : it.icon ? icon(it.icon) : `<span class="ic"></span>`)
        + (it.others ? endsHtml("bt", it.label, it.others) : `<span class="bt">${esc(it.label)}</span>`)
        + (it.aside ? `<small class="mside">${esc(it.aside)}</small>` : "")
        + (it.keys ? `<kbd>${esc(it.keys)}</kbd>` : "") + (it.sub ? icon("chevron-right") : "");
      if (it.tip) b.title = it.tip;
      b.addEventListener("click", (e) => {
        if (it.sub) { openMenu(b, it.sub, true, e.detail === 0); return; }
        closeMenus();
        it.run();
      });
      // pointing at an item opens its submenu, or closes the one open
      b.addEventListener("pointerenter", () => {
        if (it.sub && !it.disabled) openMenu(b, it.sub, true);
        else if (!sub) $("menu2").classList.add("hidden");
      });
      menu.appendChild(b);
    });
    menu.classList.remove("hidden");
    placeMenu(menu, at, sub);
    if (sub) wb.subFrom = at;
    const first = menu.querySelector("button.mi:not(:disabled)");
    if (keyboard && first) first.focus();
    else menu.focus({ preventScroll: true });
    return menu;
  }

  /** Under an anchor (or beside it, for a submenu) or at a point, held inside the window.
   *  One that does not fit below opens above instead when there is more room there; a menu
   *  taller than either side scrolls. */
  function placeMenu(menu, at, sub) {
    menu.style.left = "0px";
    menu.style.top = "0px";
    menu.style.maxHeight = "";
    const r = at.getBoundingClientRect ? at.getBoundingClientRect() : { left: at.x, right: at.x, top: at.y, bottom: at.y };
    const w = menu.offsetWidth, h = menu.offsetHeight, vw = window.innerWidth, vh = window.innerHeight;
    const top = sub ? r.top - 6 : r.bottom + 4, bottom = sub ? r.bottom + 6 : r.top - 4;   // opening down / up
    const up = top + h > vh - 8 && bottom - 8 > vh - 8 - top;
    let x = sub ? r.right + 4 : r.left;
    if (sub && x + w > vw - 8) x = r.left - w - 4;
    x = Math.max(8, Math.min(x, vw - w - 8));
    const y = up ? Math.max(8, bottom - h) : Math.max(8, Math.min(top, vh - 120));
    menu.style.left = `${Math.round(x)}px`;
    menu.style.top = `${Math.round(y)}px`;
    menu.style.maxHeight = `${Math.round(up ? bottom - y : vh - y - 12)}px`;
    menu.style.transformOrigin = `${sub && x < r.left ? "right" : "left"} ${up ? "bottom" : "top"}`;
  }

  /** Arrow keys walk a menu, right opens a submenu and left closes it, Escape closes the
   *  submenu and then the menu. Enter is the focused item's own click. */
  function menuKey(ev) {
    const m1 = $("menu"), m2 = $("menu2"), inSub = !m2.classList.contains("hidden") && m2.contains(document.activeElement);
    const menu = inSub ? m2 : m1, items = [...menu.querySelectorAll("button.mi:not(:disabled)")];
    const i = items.indexOf(document.activeElement), k = ev.key;
    // a small form in a menu (.keys-own: the AI's auto-pause rules) keeps Tab and the arrows for its fields
    const own = document.activeElement && document.activeElement.closest && document.activeElement.closest(".menu .keys-own");
    if (own && (k === "Tab" || k === "ArrowDown" || k === "ArrowUp")) return false;
    if (k === "Escape") {
      if (inSub) { m2.classList.add("hidden"); if (wb.subFrom) wb.subFrom.focus(); } else closeMenus();
      return true;
    }
    if (k === "ArrowDown" || k === "ArrowUp") {
      if (items.length) items[(i + (k === "ArrowDown" ? 1 : i < 0 ? 0 : -1) + items.length) % items.length].focus();
      return true;
    }
    if (k === "ArrowRight" && document.activeElement && document.activeElement.classList.contains("has-sub")) {
      document.activeElement.click();
      return true;
    }
    if (k === "ArrowLeft" && inSub) { m2.classList.add("hidden"); if (wb.subFrom) wb.subFrom.focus(); return true; }
    if (k === "Tab") closeMenus();
    return false;
  }

  /** Put text on the clipboard: the async API, else the old way through a hidden box. */
  function copyText(text) {
    const old = () => {
      const ta = Object.assign(document.createElement("textarea"), { value: text });
      ta.style.cssText = "position:fixed;left:-9999px;opacity:0";
      document.body.appendChild(ta);
      ta.select();
      let ok = false;
      try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
      ta.remove();
      return ok;
    };
    const done = (ok) => toast(ok ? t("copied") : t("copy_fail"));
    try { navigator.clipboard.writeText(text).then(() => done(true), () => done(old())); } catch (e) { done(old()); }
  }
  /** A text dialog. opts: {help: a line under the text box, ok: the confirm button's label} */
  function modal(title, text, placeholder, onOk, onDelete, single, opts) {
    const o = opts || {};
    dialog({ title, text, placeholder, onOk, onDelete, single, help: o.help, ok: o.ok });
  }

  /** The one dialog. o: {title, body (plain text) or html, text (a text box, with its
   *  value), placeholder, single (one line: Enter confirms), help, ok (its label), okClass,
   *  onOk(text), onDelete, alt: {label, run} (a second way out, on the left), noCancel,
   *  focus: "cancel" or "ok" (else the text box, else ok)}. Escape and a click on the
   *  backdrop cancel; Enter presses the focused button. */
  function dialog(o) {
    closeMenus();
    document.querySelectorAll(".modal.ghost").forEach((g) => g.remove());   // one closing just now
    const back = document.activeElement;
    $("modal-title").textContent = o.title || "";
    const body = $("modal-body");
    body.classList.toggle("hidden", !(o.body || o.html));
    if (o.html) body.innerHTML = o.html;
    else body.textContent = o.body || "";
    const ta = $("modal-text"), hasText = typeof o.text === "string";
    ta.style.display = hasText ? "" : "none";
    ta.value = hasText ? o.text : "";
    ta.placeholder = o.placeholder || "";
    ta.rows = o.single ? 1 : 4;
    $("modal-help").textContent = o.help || "";
    $("modal-help").classList.toggle("hidden", !o.help);
    const ok = $("modal-ok"), cancel = $("modal-cancel"), del = $("modal-del"), alt = $("modal-alt");
    ok.textContent = o.ok || t("ok");
    ok.className = o.okClass || "primary";
    cancel.textContent = t("cancel");
    cancel.style.display = o.noCancel ? "none" : "";
    del.textContent = t("del");
    del.style.display = o.onDelete ? "" : "none";
    alt.style.display = o.alt ? "" : "none";
    alt.textContent = o.alt ? o.alt.label : "";
    $("modal").classList.remove("hidden");
    const close = () => {
      if (!$("modal").classList.contains("hidden")) ghost($("modal"), 160);   // a copy fades out
      $("modal").classList.add("hidden");
      wb.modalClose = null;
      if (back && back.isConnected && back !== document.body) back.focus({ preventScroll: true });
    };
    wb.modalClose = close;
    ok.onclick = () => { close(); if (o.onOk) o.onOk(ta.value); };
    cancel.onclick = close;
    del.onclick = () => { close(); if (o.onDelete) o.onDelete(); };
    alt.onclick = () => { close(); if (o.alt) o.alt.run(); };
    ta.onkeydown = (ev) => {
      if (ev.key !== "Enter" || ev.isComposing || ev.keyCode === 229) return;   // Enter picks a character in an IME
      if (o.single || ev.ctrlKey || ev.metaKey) { ev.preventDefault(); ok.click(); }
    };
    (o.focus === "cancel" ? cancel : o.focus === "ok" || !hasText ? ok : ta).focus();
  }

  /** An exit that keeps no state waiting: a copy of el, laid in its place, plays its exit
   *  (the class ghost: an animation, style.css) and is removed after ms, while the caller
   *  hides el itself at once, so whatever asks what shows sees it gone. The copy takes no
   *  pointer, is hidden from assistive tech and has no ids (nor the glint's). */
  function ghost(el, ms) {
    const g = el.cloneNode(true);
    g.removeAttribute("id");
    g.querySelectorAll("[id]").forEach((n) => n.removeAttribute("id"));
    g.classList.add("ghost");
    g.setAttribute("aria-hidden", "true");
    g.inert = true;
    el.after(g);
    setTimeout(() => g.remove(), ms + 40);
    return g;
  }

  /** A short line; ms: how long it stays; action: a button after the words ({label, run}; the
   *  one part of the line that takes the pointer); kind: what it is about, so what makes it moot
   *  can take it away (toastClose). It sits at the top of the flowsheet's column, centred over
   *  it -- over the dock's list, above the Ask AI box, while the dock takes the whole column --,
   *  so neither the program's run bar nor the dock's tabs are under it; a menu or a panel
   *  opened over the page lies over it (style.css). at: where else it goes, a function that
   *  places the line (its words already in) low, rising in, and says whether it did (the
   *  annotations' line: the flowsheet's bottom, clear of its toolbar, app-pins.js). */
  function toast(text, ms, action, kind, at) {
    const el = $("toast");
    el.textContent = text;
    el.classList.toggle("act", !!action);
    if (action) {
      el.innerHTML = `<span class="tt">${esc(text)}</span>`;
      const b = Object.assign(document.createElement("button"), { className: "tact", textContent: action.label });
      b.addEventListener("click", () => { el.classList.remove("show"); action.run(); });
      el.appendChild(b);
    }
    wb.toastKind = kind || "";
    el.classList.remove("low");
    if (!(at && at(el))) toastPlace(el);
    else el.classList.add("low");
    el.classList.add("show");
    clearTimeout(wb.toastTimer);
    wb.toastTimer = setTimeout(() => el.classList.remove("show"), ms || 2800);
  }
  function toastPlace(el) {
    const pane = wb.pane, pr = pane && pane.q(".pright"), r = pr && pr.getBoundingClientRect();
    if (!r || r.width < 200) { el.style.left = el.style.top = el.style.maxWidth = ""; return; }   // (no pane: under the header)
    const cb = pr.classList.contains("dock-max") && pane.q(".composer").getBoundingClientRect();
    el.style.left = `${Math.round(r.left + r.width / 2)}px`;
    el.style.top = `${Math.round(cb && cb.height ? cb.top - 46 : r.top + 10)}px`;
    el.style.maxWidth = `${Math.round(r.width - 32)}px`;
  }
  /** Take a toast of this kind away (the Changes tab now shows what it says). */
  function toastClose(kind) {
    if (!kind || wb.toastKind !== kind) return;
    $("toast").classList.remove("show");
    wb.toastKind = "";
  }

  /** Save text through the window's file dialog; a plain download outside pywebview.
   *  Resolves to the path saved to, or null. */
  function saveFile(name, text, kind) {
    const api = window.pywebview && window.pywebview.api;
    if (api && api.save_file) {
      return api.save_file(name, text, kind || "csv").then((path) => {
        if (path) toast(t("saved", path));
        return path || null;
      }, () => null);
    }
    const a = document.createElement("a");                // outside the window (a browser preview)
    a.href = URL.createObjectURL(new Blob([kind === "awb" ? text : "﻿" + text], { type: "text/plain" }));
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    return Promise.resolve(null);
  }

  Object.assign(WBA, { closeMenus, copyText, dialog, ghost, menuKey, menuOpen, modal, openMenu,
    saveFile, toast, toastClose, toggleMenu });
})();
