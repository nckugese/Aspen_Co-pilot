/* Visual effects with no app state: the sliding glass highlight (glide), liquid glass lenses
 * (lens: an SVG displacement filter per element, maps cached), and the glint that follows
 * the pointer (followLight).
 *
 * One of the page's app-*.js files (their order and how they share WBA: app-core.js). */
(function () {
  "use strict";
  const { $ } = WBA;

  /** Move a glass highlight onto the chosen item, like a drop of liquid: it first stretches
   *  over the old place and the new one (90 ms), then settles on the new one (320 ms, the
   *  spring). node is a .glide (style.css): .gx slides along a row, .gy down a list. It is
   *  three slices moved by transform only, so nothing is laid out while it moves: two caps
   *  (translate) and a square middle (translate, and scale along the axis) that tucks under
   *  each cap. Each slice plays both legs as one animation (the legs are its keyframes), and
   *  the three start in one frame with one start time, so their edges stay joined, a click
   *  mid-move and a busy page included (a slice left standing and started a frame after the
   *  others came loose). The slices' cross size is written only when it changes (a language
   *  switch, the list's narrow mode), and a change of size in place is not animated. No
   *  target: it fades out. */
  const GLIDE_MID = 100, GLIDE_TUCK = 1;           // the middle's own length (at most), and its tuck under a cap (px)
  const GLIDE_GO = 90, GLIDE_SETTLE = 320;         // the stretch and the settle (ms; style.css --d3)
  const EASE_OUT = "cubic-bezier(.2, .8, .2, 1)", SPRING = "cubic-bezier(.3, 1.35, .5, 1)";   // (style.css)
  function glide(node, target) {
    if (!node) return;
    if (!node.firstElementChild) node.innerHTML = "<b></b><b></b><b></b>";
    if (!target) { cancelAnimationFrame(node.wbRaf); node.classList.remove("on"); node.wbAt = null; return; }
    const to = { x: target.offsetLeft, y: target.offsetTop, w: target.offsetWidth, h: target.offsetHeight };
    const from = node.wbAt, same = (a, b) => a.x === b.x && a.y === b.y && a.w === b.w && a.h === b.h;
    if (from && same(from, to) && node.classList.contains("on")) return;   // (asked again mid-move: let it go on)
    cancelAnimationFrame(node.wbRaf);
    node.wbAt = to;
    const along = node.classList.contains("gy") ? "y" : "x", cross = along === "x" ? "h" : "w", len = along === "x" ? "w" : "h";
    // the cap's length is the item's corner radius (a pill's: half its height)
    const R = Math.max(1, Math.min(parseFloat(getComputedStyle(target).borderTopLeftRadius) || 0, to.w / 2, to.h / 2));
    const [c0, mid, c1] = node.children;
    node.classList.toggle("short", to[len] < 3 * R);   // its shadow is the whole drop's (style.css)
    const resized = node.wbSize !== `${to[cross]}|${R}`;
    if (resized) {                                // the slices' size: only when it changes
      node.wbSize = `${to[cross]}|${R}`;
      // the middle's own length is no more than the item's, so a stretch scales it up: the
      // compositor then draws it from a picture at least its size (drawn from a smaller one,
      // its edges blur and the shadow under a short pill shows through them)
      node.wbMid = Math.max(1, Math.min(GLIDE_MID, to[len]));
      const S = along === "x" ? ["width", "height"] : ["height", "width"], rad = `${R}px`;
      [c0, mid, c1].forEach((b, i) => { b.style[S[0]] = `${i === 1 ? node.wbMid : R}px`; b.style[S[1]] = `${to[cross]}px`; });
      c0.style.borderRadius = along === "x" ? `${rad} 0 0 ${rad}` : `${rad} ${rad} 0 0`;
      c1.style.borderRadius = along === "x" ? `0 ${rad} ${rad} 0` : `0 0 ${rad} ${rad}`;
    }
    // the three slices' transforms for the box r, along the axis; every one is a translate
    // (and the middle's a scale), so a keyframe from where a slice shows now matches it
    const at = (p, o) => (along === "x" ? `translate(${p}px, ${o}px)` : `translate(${o}px, ${p}px)`);
    const sc = (s) => `scale${along.toUpperCase()}(${s})`;
    const put = (r) => {
      const a = r[along], l = Math.max(2 * R, r[len]), o = along === "x" ? r.y : r.x;
      return [at(a, o), `${at(a + R - GLIDE_TUCK, o)} ${sc((l - 2 * R + 2 * GLIDE_TUCK) / node.wbMid)}`, at(a + l - R, o)];
    };
    const slices = [c0, mid, c1];
    const stop = () => { (node.wbAnims || []).forEach((an) => an.cancel()); node.wbAnims = null; };
    if (!from || resized || !node.classList.contains("on") || from[along === "x" ? "y" : "x"] !== to[along === "x" ? "y" : "x"]
        || (from[along] === to[along] && from[len] !== to[len])) {
      stop();                                     // shown anew, or a size changed: at once
      put(to).forEach((tf, i) => { slices[i].style.transform = tf; });
      node.classList.add("on");
      return;
    }
    // stretch over both, then settle; a long way back to a small item settles without the
    // spring's overshoot, which would fold the middle past zero
    const lo = Math.min(from[along], to[along]), hi = Math.max(from[along] + from[len], to[along] + to[len]);
    const union = put(Object.assign({}, to, { [along]: lo, [len]: hi - lo })), end = put(to);
    const back = Math.max(to[along] - lo, hi - to[along] - to[len]);
    const settle = back * 0.05 > to[len] - 2 * R ? EASE_OUT : SPRING;
    // started at the next frame (after whatever else this task draws), all three at its time
    node.wbRaf = requestAnimationFrame(() => {
      // where each slice shows now: read all three before any changes (mid-move, off its rest)
      const now = node.wbAnims && node.wbAnims.some((an) => an.playState === "running") ? slices.map((b) => {
        try {
          const m = new DOMMatrix(getComputedStyle(b).transform);
          return b === mid ? `${at(along === "x" ? m.e : m.f, along === "x" ? m.f : m.e)} ${sc(along === "x" ? m.a : m.d)}`
            : at(along === "x" ? m.e : m.f, along === "x" ? m.f : m.e);
        } catch (e) { return b.style.transform; }
      }) : slices.map((b) => b.style.transform);
      stop();
      const t0 = document.timeline.currentTime, cut = GLIDE_GO / (GLIDE_GO + GLIDE_SETTLE);
      node.wbAnims = slices.map((b, i) => {
        b.style.transform = end[i];                // where it rests once the animation ends
        const an = b.animate([{ transform: now[i], easing: EASE_OUT }, { transform: union[i], offset: cut, easing: settle },
          { transform: end[i] }], GLIDE_GO + GLIDE_SETTLE);
        an.startTime = t0;
        return an;
      });
    });
  }

  // ------------------------------------------------------------------ liquid glass
  /** The displacement map of a rounded rectangle's rim: red and green say where each pixel
   *  of the backdrop is taken from. Near the rim it comes from further in, so what lies
   *  behind the edge bends, as through the thick edge of a lens; past the bezel, nothing. */
  function lensMap(w, h, R, bezel) {
    const cv = Object.assign(document.createElement("canvas"), { width: w, height: h });
    const g = cv.getContext("2d"), d = g.createImageData(w, h);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const px = x + 0.5, py = y + 0.5;
        let nx = px - Math.min(Math.max(px, R), w - R), ny = py - Math.min(Math.max(py, R), h - R);
        const len = Math.hypot(nx, ny);
        let depth;
        if (len > 0) { depth = R - len; nx /= len; ny /= len; } else {  // along a straight side
          const m = Math.min(px, w - px, py, h - py);
          depth = m;
          nx = m === px ? -1 : m === w - px ? 1 : 0;
          ny = nx ? 0 : m === py ? -1 : 1;
        }
        const t = Math.max(0, Math.min(1, depth / bezel)), mag = (1 - t) * (1 - t);
        const i = (y * w + x) * 4;
        d.data[i] = 128 - nx * mag * 127; d.data[i + 1] = 128 - ny * mag * 127; d.data[i + 2] = 128; d.data[i + 3] = 255;
      }
    }
    g.putImageData(d, 0, 0);
    return cv.toDataURL();
  }

  /** Maps drawn lately, by size (a long side rounded up to 8 px), radius and bezel: the
   *  eight used last are kept, so an inspector that hugs its rows or a chip that follows the
   *  selection does not compute a map pixel by pixel each time it takes a size it had before. */
  const lensMaps = new Map();
  function cachedMap(w, h, R, bezel) {
    const key = `${w}x${h}|${Math.round(R)}|${Math.round(bezel)}`;
    let url = lensMaps.get(key);
    if (url) lensMaps.delete(key);
    else url = lensMap(w, h, R, bezel);
    lensMaps.set(key, url);                        // the newest last
    if (lensMaps.size > 8) lensMaps.delete(lensMaps.keys().next().value);
    return url;
  }

  /** Make el a lens of liquid glass: frost plus refraction at its rim. Each element gets its
   *  own SVG filter; its map is drawn when its size settles on a new value (at once when it
   *  first shows), from the cache when that size came before. The rim follows the element's
   *  own corner radius (a pill's is half its height) unless radius says. Returns {dispose},
   *  which takes the filter and the observer away again; nothing when glass is unsupported. */
  let lensN = 0;
  function lens(el, { radius = null, bezel = 14, scale = 36, blur = 2, tint = "saturate(185%) brightness(1.06)" } = {}) {
    const defs = $("wb-lenses"), none = { dispose() {} };
    if (!el || !defs || !(window.CSS && CSS.supports("backdrop-filter", "url(#x)"))) return none;
    const ns = "http://www.w3.org/2000/svg", id = `wb-lens-${++lensN}`;
    const mk = (tag, attrs) => { const n = document.createElementNS(ns, tag); Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v)); return n; };
    const img = mk("feImage", { x: 0, y: 0, width: 1, height: 1, preserveAspectRatio: "none", result: "map" });
    const filter = mk("filter", { id, x: 0, y: 0, width: "100%", height: "100%", "color-interpolation-filters": "sRGB" });
    filter.append(img, mk("feDisplacementMap", { in: "SourceGraphic", in2: "map", scale, xChannelSelector: "R", yChannelSelector: "G" }));
    defs.appendChild(filter);
    let size = "", timer = null;
    const draw = () => {
      const w = Math.round(el.offsetWidth), h = Math.round(el.offsetHeight);
      if (!w || !h || size === `${w}x${h}`) return;
      size = `${w}x${h}`;
      // a side longer than 64 px is drawn rounded up to 8 px and stretched onto the element, so
      // the rim stays on its edges; a short one (a pill's height, which sets its radius) at
      // its own length, and the radius is the element's own, so its ends stay round
      const qs = (n) => (n > 64 ? Math.ceil(n / 8) * 8 : n), qw = qs(w), qh = qs(h);
      const R = Math.min(radius === null ? parseFloat(getComputedStyle(el).borderTopLeftRadius) || 0 : radius, w / 2, h / 2);
      img.setAttribute("href", cachedMap(qw, qh, R, Math.min(bezel, w / 2, h / 2)));
      img.setAttribute("width", w);
      img.setAttribute("height", h);
      el.style.backdropFilter = `url(#${id}) blur(${blur}px) ${tint}`;
    };
    const ro = new ResizeObserver(() => {
      clearTimeout(timer);
      if (!size && el.offsetWidth) draw();         // showing again: no frame without its rim
      else timer = setTimeout(draw, 120);
      if (!el.offsetWidth) size = "";
    });
    ro.observe(el);
    draw();
    return {
      dispose() {
        ro.disconnect();
        clearTimeout(timer);
        filter.remove();
        el.style.backdropFilter = "";
      },
    };
  }

  /** Glass catches the light where the pointer is. One element for the page (#glint) goes
   *  into the glass or button under the pointer (for the block categories, their capsule, so
   *  pointing along the rows moves nothing but the spot), and a spot in it follows the
   *  pointer by transform, once a frame at most. Nothing else is written: no custom
   *  property, no size; the host's box is read when the host changes (and after a scroll or
   *  a resize), not on every move. It fades in with a new host and out off the glass. */
  const GLINT_HOSTS = ".glass, button:not(:disabled), .blocklyToolboxCategoryGroup";
  function followLight() {
    const glint = Object.assign(document.createElement("i"), { id: "glint" });
    glint.setAttribute("aria-hidden", "true");
    const spot = glint.appendChild(document.createElement("b"));
    let host = null, box = null, over = null, x = 0, y = 0, frame = 0;
    const flush = () => {
      frame = 0;
      const el = over && over.isConnected && over.closest ? over.closest(GLINT_HOSTS) : null;
      if (el !== host || (el && glint.parentNode !== el)) {
        host = el;
        box = null;
        if (el) { el.appendChild(glint); glint.classList.add("on"); } else glint.classList.remove("on");
      }
      if (!host) return;
      if (!box) {                                  // where the glint's own box starts, in the window
        const r = host.getBoundingClientRect();
        box = { x: r.left + host.clientLeft, y: r.top + host.clientTop, sx: host.scrollLeft, sy: host.scrollTop };
        glint.style.transform = box.sx || box.sy ? `translate(${box.sx}px, ${box.sy}px)` : "";   // a scrolled capsule
      }
      spot.style.transform = `translate3d(${Math.round(x - box.x)}px, ${Math.round(y - box.y)}px, 0)`;
    };
    const move = (ev) => {
      x = ev.clientX;
      y = ev.clientY;
      over = ev.target;
      if (!frame) frame = requestAnimationFrame(flush);
    };
    document.addEventListener("pointermove", move, { passive: true });
    document.addEventListener("pointerover", move, { passive: true });
    document.documentElement.addEventListener("pointerleave", () => { over = null; if (!frame) frame = requestAnimationFrame(flush); });
    const stale = () => { box = null; };
    document.addEventListener("scroll", stale, { capture: true, passive: true });
    window.addEventListener("resize", stale);
  }

  Object.assign(WBA, { followLight, glide, lens });
})();
