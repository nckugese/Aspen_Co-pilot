/* What every script of the page shares, loaded first (index.html): WBA, the namespace of the
 * app-*.js files (how they use it: app-core.js), made here with the small helpers below on it.
 * Every other file takes the helpers by value too (const { esc, icon, t } = WBA). */
(function () {
  "use strict";
  const WBA = (window.WBA = {});
  WBA.later = new Proxy({}, { get: (o, name) => (...args) => WBA[name](...args) });

  // ------------------------------------------------------------------ words
  const t = (...a) => I18N.t(...a);
  const zh = () => I18N.lang === "zh";
  /** A count in words: English says "1 value" (key_1) where there is such a key, Chinese has one form. */
  const tn = (key, n, ...more) => t(n === 1 && !zh() && I18N.t(`${key}_1`) !== `${key}_1` ? `${key}_1` : key, n, ...more);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  /** A sentence around markup: the words escaped, {0}... replaced by the html given. */
  const th = (key, ...html) => esc(t(key)).replace(/\{(\d+)\}/g, (m, i) => html[i] ?? "");
  const list = (a) => a.join(zh() ? "、" : ", ");
  /** A tree path in words: no \Data\, a › for each backslash (the server's texts carry their paths so). */
  const words = (s) => String(s ?? "").replace(/\\?Data\\/g, "").replace(/\\/g, " › ");
  /** Who made a record, in a word (AI, User, Program, Optimizer, Aspen window: ch_who_*). */
  const who = (a) => t(`ch_who_${["ai", "user", "program", "optimizer"].includes(a) ? a : "external"}`);
  const cut = (s, n) => { const a = [...String(s ?? "").replace(/\s+/g, " ").trim()]; return a.length > n ? `${a.slice(0, n - 1).join("").trimEnd()}…` : a.join(""); };
  const base = (p) => String(p || "").split(/[\\/]/).pop();
  /** "block:B1" / "stream:S2" of the object a tree path is under, or null. */
  const objOfPath = (p) => { const m = /^\\Data\\(Blocks|Streams)\\([^\\]+)/i.exec(String(p || "")); return m ? `${m[1].toLowerCase() === "blocks" ? "block" : "stream"}:${m[2].toUpperCase()}` : null; };
  // Icons come from the sprite in index.html.
  const icon = (name) => `<svg class="ic" aria-hidden="true"><use href="#i-${name}"/></svg>`;
  const setHtml = (el, html) => { if (el._h !== html) { el._h = html; el.innerHTML = html; } };

  // ------------------------------------------------------------------ values and times
  const isObj = (x) => !!x && typeof x === "object" && !Array.isArray(x);
  const num = (x) => typeof x === "number" && isFinite(x);
  const finite = (x) => (num(x) ? x : null);
  const fmtVal = (v) => (v === null || v === undefined || v === "" ? "—"
    : typeof v === "number" ? Number(v.toPrecision(6)).toString() : String(v));
  /** Two numbers in as few digits as tell them apart: p at least, max at most. */
  function apart(x, y, p = 4, max = 10) {
    while (p < max && Number(x.toPrecision(p)) === Number(y.toPrecision(p))) p++;
    return [Number(x.toPrecision(p)), Number(y.toPrecision(p))];
  }
  const now = () => Date.now() / 1000;          // the server's times are this machine's clock too
  const pad = (n) => String(n).padStart(2, "0");
  /** 14:02, of a time in seconds. */
  const hhmm = (s) => { const d = new Date((Number(s) || 0) * 1000); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
  /** 14:02 today, 9/24 13:40 another day. */
  function when(s) {
    const d = new Date((Number(s) || 0) * 1000);
    return d.toDateString() === new Date().toDateString() ? hhmm(s) : `${d.getMonth() + 1}/${d.getDate()} ${hhmm(s)}`;
  }

  // ------------------------------------------------------------------ the state
  const catalog = () => (window.wb && wb.state && wb.state.catalog) || (window.WB && WB.data && WB.data.catalog) || {};
  /** Whether this server answers a feature it may leave out (catalog.features): a control for
   *  one it does not is hidden, or says why it cannot act. */
  const feature = (name) => { const f = catalog().features; return Array.isArray(f) && f.includes(name); };
  const sessOf = (tab) => (tab && window.wb && wb.state && wb.state.sessions && wb.state.sessions[tab.session]) || {};
  const learning = () => !!(window.WBLP && WBLP.learnOn());

  // ------------------------------------------------------------------ a card over the page
  /** The focus back on el, where it can take it. */
  const refocus = (el) => { if (el && el.isConnected && el.focus && el.offsetParent !== null) el.focus({ preventScroll: true }); };
  /** A card that does not block the page (a dialog, not modal), put in parent with class cls,
   *  named by the element with id title. o.close(back) shuts it: Escape in it (back true; o.esc(ev)
   *  first, which keeps the key where it returns true), a press outside it and outside o.keep (a
   *  selector, or a test of the element pressed). o.place runs again when the window is resized.
   *  Returns {el, off}: off(back, to) takes the card and its listeners away, the focus to `to`
   *  where back and the focus was in it. */
  function popover(parent, cls, title, o) {
    const el = document.createElement("div");
    el.className = `plate ${cls}`;
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-modal", "false");
    el.setAttribute("aria-labelledby", title);
    el.tabIndex = -1;
    parent.appendChild(el);
    el.addEventListener("keydown", (ev) => {
      if (ev.key !== "Escape" || ev.isComposing) return;
      ev.preventDefault();
      ev.stopPropagation();
      if (!(o.esc && o.esc(ev))) o.close(true);
    });
    const out = (ev) => {
      const x = ev.target;
      if (el.contains(x) || (typeof o.keep === "function" ? o.keep(x) : o.keep && x && x.closest && x.closest(o.keep))) return;
      o.close();
    };
    document.addEventListener("pointerdown", out, true);
    if (o.place) window.addEventListener("resize", o.place);
    const off = (back, to) => {
      const had = el.contains(document.activeElement);
      document.removeEventListener("pointerdown", out, true);
      if (o.place) window.removeEventListener("resize", o.place);
      el.remove();
      if (back && had) refocus(to);
    };
    return { el, off };
  }
  /** A card w px wide under the box r, right edges lined up, or over it (up) where it does not fit
   *  under and there is more room over (up null: chosen now; a function (h, above, below): its
   *  answer; else as given); held inside the window, scrolling where it is taller than its side's
   *  room (min px at least). Returns up. */
  function drop(el, r, w, min, up) {
    const W = window.innerWidth, H = window.innerHeight, m = 8;
    el.style.width = `${w}px`;
    el.style.left = `${Math.round(Math.max(m, Math.min(r.right - w, W - w - m)))}px`;
    el.style.maxHeight = "none";
    const h = el.offsetHeight, below = H - r.bottom - 6 - m, above = r.top - 6 - m;
    up = typeof up === "function" ? up(h, above, below) : up === null ? h > below && above > below : up;
    const room = Math.max(min, up ? above : below);
    el.style.maxHeight = `${room}px`;
    el.style.top = `${Math.round(up ? Math.max(m, r.top - 6 - Math.min(h, room)) : r.bottom + 6)}px`;
    el.classList.toggle("up", up);
    return up;
  }
  /** A strip that scrolls sideways (the tabs, a model's sub-tabs, the results' chips): its shown item
   *  on kept in view, and the edge where more of it lies faded (fl / fr: style.css masks them). */
  function stripView(strip, on) {
    if (on) {
      const l = on.offsetLeft - 6, r = on.offsetLeft + on.offsetWidth + 6;
      if (l < strip.scrollLeft) strip.scrollLeft = l;
      else if (r > strip.scrollLeft + strip.clientWidth) strip.scrollLeft = r - strip.clientWidth;
    }
    strip.classList.toggle("fl", strip.scrollLeft > 1);
    strip.classList.toggle("fr", strip.scrollLeft + strip.clientWidth < strip.scrollWidth - 1);
  }
  /** Such a strip: the wheel scrolls it sideways; a scroll fades its edges again. */
  function sideways(strip) {
    strip.addEventListener("wheel", (ev) => {
      if (strip.scrollWidth <= strip.clientWidth) return;
      ev.preventDefault();
      strip.scrollLeft += Math.abs(ev.deltaX) > Math.abs(ev.deltaY) ? ev.deltaX : ev.deltaY;
    }, { passive: false });
    strip.addEventListener("scroll", () => stripView(strip), { passive: true });
  }
  /** A press on el dragged: move(e) on each move until the pointer lets go, then up(). */
  function track(el, ev, move, up) {
    el.setPointerCapture(ev.pointerId);
    const end = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", end);
      el.removeEventListener("pointercancel", end);
      up();
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", end);
    el.addEventListener("pointercancel", end);
  }

  Object.assign(WBA, { apart, base, catalog, cut, drop, esc, feature, finite, fmtVal, hhmm, icon, isObj, learning, list, now, num, objOfPath, pad,
    popover, sessOf, setHtml, sideways, stripView, t, th, tn, track, when, who, words, zh });
})();
