/* Catch the reflux: a column's tray at the foot of the canvas, moved by ← → or the pointer. Reflux
 * drops fall from the distributor: blue +1 (one missed weeps through: a life), gold +3, grey foam
 * costs a life when caught. Three lives. (The frame: games/frame.js.) */
WBG.add({
  id: "tray", name: "cw_tray", help: ["cw_t_keys", "cw_t_rules"], over: "cw_t_over",
  TW: 58,
  reset(S) { Object.assign(S, { items: [], lives: 3, next: 0.3, hurt: 0, x: S.w / 2 }); },
  step(S, dt, I) {
    const half = this.TW / 2 + 4;
    if (I.L || I.R) S.x += (I.R - I.L) * 360 * dt;
    else if (I.px != null) S.x += (I.px - S.x) * Math.min(1, dt * 14);
    S.x = Math.min(Math.max(S.x, half), S.w - half);
    if (S.t >= S.next) {
      const r = Math.random(), kind = r < 0.08 ? "gold" : S.score > 3 && r < 0.3 ? "foam" : "drop", rad = { foam: 8, gold: 6, drop: 5 }[kind];
      S.items.push({ kind, r: rad, x: rad + 6 + Math.random() * Math.max(1, S.w - 2 * rad - 12), y: -rad, k: { foam: 0.8, gold: 1.15, drop: 1 }[kind] });
      S.next = S.t + Math.max(0.36, 0.95 - S.score * 0.012) * (0.7 + Math.random() * 0.6);
    }
    const ty = S.h - 14, v = Math.min(250, 70 + S.score * 2.4);
    const hurt = () => { S.lives--; S.hurt = 0.35; if (S.lives <= 0) S.over = true; };
    S.items = S.items.filter((it) => {
      it.y += v * it.k * dt;
      if (it.y + it.r >= ty - 5 && it.y - it.r <= ty + 4 && Math.abs(it.x - S.x) <= this.TW / 2 + it.r * 0.6) {
        if (it.kind === "foam") hurt(); else S.score += it.kind === "gold" ? 3 : 1;
        return false;
      }
      if (it.y - it.r > S.h) { if (it.kind === "drop") hurt(); return false; }
      return true;
    });
    if (S.hurt > 0) S.hurt -= dt;
  },
  drop(cx, x, y, r, c) {
    cx.fillStyle = c;
    cx.beginPath();
    cx.moveTo(x, y - r * 2);
    cx.bezierCurveTo(x + r * 0.9, y - r * 0.9, x + r, y - r * 0.3, x + r, y);
    cx.arc(x, y, r, 0, Math.PI);
    cx.bezierCurveTo(x - r, y - r * 0.3, x - r * 0.9, y - r * 0.9, x, y - r * 2);
    cx.fill();
  },
  draw(S, cx, C) {
    const { w, h } = S, TW = this.TW, ty = h - 14;
    cx.fillStyle = C.dim;                               // the column's shell
    cx.fillRect(1, 0, 2, h);
    cx.fillRect(w - 3, 0, 2, h);
    S.items.forEach((it) => {
      if (it.kind !== "foam") { this.drop(cx, it.x, it.y, it.r, it.kind === "gold" ? C.warn : C.accent); return; }
      cx.fillStyle = C.soft;
      [[-0.5, 0.2, 0.6], [0.45, 0.25, 0.55], [0, -0.35, 0.62]].forEach(([dx, dy, rr]) => {
        cx.beginPath(); cx.arc(it.x + dx * it.r, it.y + dy * it.r, rr * it.r, 0, 7); cx.fill();
      });
    });
    cx.fillStyle = S.hurt > 0 ? C.bad : C.mid;          // the tray, its three bubble caps and weirs
    cx.fillRect(S.x - TW / 2, ty, TW, 4);
    cx.fillRect(S.x - TW / 2, ty - 5, 2, 5);
    cx.fillRect(S.x + TW / 2 - 2, ty - 5, 2, 5);
    for (let i = -1; i <= 1; i++) { cx.beginPath(); cx.arc(S.x + i * 17, ty, 4.5, Math.PI, 0); cx.fill(); }
    for (let i = 0; i < 3; i++) this.drop(cx, w - 14 - i * 12, 16, 3.5, i < S.lives ? C.accent : C.dim);
  },
});
