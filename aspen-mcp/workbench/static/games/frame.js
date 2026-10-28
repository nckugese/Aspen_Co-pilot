/* The waiting row's games (app-wait.js opens one in the card under the chat). This file is the
 * frame they share: the canvas sized to the card, one requestAnimationFrame loop that runs only
 * while the game is played and seen (the card on screen, the window shown, the focus in it), the
 * keys and the pointer, the start / paused / over overlay, and the best score (app-wait.js keeps
 * it in prefs). Each game is one small file, games/<id>.js, loaded after this one:
 *
 *   WBG.add({ id, name, help: [i18n keys under the start line], over: i18n key ({0}: the score),
 *     reset(S)        a new game: its own fields on S (S.w, S.h: the canvas in CSS px; S.score 0)
 *     step(S, dt, I)  dt s on; I: the keys held {L, R, U, D} (arrows, WASD) and the pointer
 *                     {px, py} (null until it moves; a key forgets it); S.over = true ends the game
 *     draw(S, cx, C)  the picture; C: the page's colours, C.font(px, weight)
 *     tap(S, I, click)?  Space / Enter / a click while played; false (or no tap): Space and Enter pause })
 */
(function () {
  "use strict";
  const LIST = [];
  const KEYS = { arrowleft: "L", a: "L", arrowright: "R", d: "R", arrowup: "U", w: "U", arrowdown: "D", s: "D" };
  const t = (...a) => I18N.t(...a);

  function colours() {
    const css = getComputedStyle(document.documentElement), v = (k, d) => css.getPropertyValue(k).trim() || d;
    return { accent: v("--accent-500", "#3b82f6"), ai: v("--ai-500", "#7c5cff"), warn: v("--warn", "#c98500"),
      ok: v("--ok", "#2f9e55"), bad: v("--danger", "#d03b3b"), ink: v("--ink-700", "#3b4757"), mid: v("--ink-500", "#5b6778"),
      soft: v("--ink-300", "#aab3c0"), bg: v("--canvas", "#f5f7fb"), dim: "rgba(30, 50, 90, .14)",
      font: (px, w) => `${w || 400} ${px}px ${v("--font", "sans-serif")}` };
  }

  /** Play ``def`` in ``host`` (emptied). o: {best, keep(score), live() -- the card seen, the window
   *  shown, still this game --, head() (the score changed), frame() (one drawn)}. */
  function run(host, def, o) {
    host.innerHTML = `<canvas class="cwt"></canvas>`;
    const cv = host.firstChild, cx = cv.getContext("2d"), C = colours();
    const S = { w: 0, h: 0, st: "idle", score: 0, best: o.best, over: false, t: 0 };
    const I = { L: 0, R: 0, U: 0, D: 0, px: null, py: null };
    let raf = 0, last = 0, shown = 0;
    const playing = () => S.st === "play" && o.live();
    const ro = new ResizeObserver((es) => {
      const r = es[es.length - 1].contentRect, d = window.devicePixelRatio || 1;
      if (!r.width || !r.height) return;
      S.w = r.width;
      S.h = r.height;
      cv.width = Math.round(r.width * d);
      cv.height = Math.round(r.height * d);
      cx.setTransform(d, 0, 0, d, 0, 0);
      if (S.st === "idle") def.reset(S);
      draw();
    });
    ro.observe(cv);

    function go() { if (!raf && playing()) { last = 0; raf = requestAnimationFrame(frame); } }
    function halt() { if (raf) cancelAnimationFrame(raf); raf = 0; }
    function frame(ts) {
      raf = 0;
      if (!playing()) return;
      const dt = Math.min(0.05, last ? (ts - last) / 1000 : 0.016);
      last = ts;
      S.t += dt;
      def.step(S, dt, I);
      if (S.over) end();
      if (S.score !== shown) { shown = S.score; o.head(); }
      draw();
      o.frame();
      if (S.st === "play") raf = requestAnimationFrame(frame);
    }
    function start() {
      if (S.st !== "paused") { Object.assign(S, { score: 0, over: false, t: 0 }); def.reset(S); }
      S.st = "play";
      o.head();
      go();
    }
    function pause() { if (S.st === "play") { S.st = "paused"; I.L = I.R = I.U = I.D = 0; halt(); draw(); } }
    function end() {
      S.st = "over";
      halt();
      if (S.score > S.best) { S.best = S.score; o.keep(S.best); }
      o.head();
    }
    function draw() {
      const { w, h } = S;
      if (!w) return;
      cx.clearRect(0, 0, w, h);
      def.draw(S, cx, C);
      if (S.st === "play") return;
      const lines = S.st === "idle" ? [t("cw_t_start"), ...def.help.map((k) => t(k))]
        : S.st === "paused" ? [t("cw_t_paused")] : [t(def.over, S.score), t("cw_t_again")];
      cx.globalAlpha = 0.86;
      cx.fillStyle = C.bg;
      cx.fillRect(0, 0, w, h);
      cx.globalAlpha = 1;
      cx.textAlign = "center";
      cx.textBaseline = "middle";
      lines.forEach((s, i) => {
        let px = i ? 12 : 14;
        cx.font = C.font(px, i ? 400 : 600);
        while (px > 9 && cx.measureText(s).width > w - 20) cx.font = C.font(--px, i ? 400 : 600);
        cx.fillStyle = i ? C.mid : C.ink;
        cx.fillText(s, w / 2, h / 2 + (i - (lines.length - 1) / 2) * 22);
      });
    }
    function act(click) {
      if (S.st !== "play") start();
      else if (!(def.tap && def.tap(S, I, click) !== false) && !click) pause();
    }
    const onMove = (ev) => { I.px = ev.offsetX; I.py = ev.offsetY; };
    const onDown = (ev) => { host.closest("[tabindex]").focus({ preventScroll: true }); onMove(ev); act(true); };
    cv.addEventListener("pointermove", onMove);
    cv.addEventListener("pointerdown", onDown);

    /** A key while the focus is in the card (app-wait.js routes them): whether it was the game's. */
    function key(ev, down) {
      const k = String(ev.key).toLowerCase(), dir = KEYS[k];
      if (dir) { I[dir] = down && S.st === "play" ? 1 : 0; if (down) I.px = I.py = null; return true; }
      if (k === " " || k === "enter") { if (down && !ev.repeat) act(); return true; }
      if (k === "p") { if (down && !ev.repeat) { if (S.st === "play") pause(); else if (S.st === "paused") start(); } return true; }
      return false;
    }
    function stop() { halt(); ro.disconnect(); S.st = "closed"; }
    draw();
    return { key, pause, stop, state: () => S.st, raf: () => !!raf, score: () => S.score, best: () => S.best };
  }

  window.WBG = { list: LIST, add: (g) => LIST.push(g), run };
})();
