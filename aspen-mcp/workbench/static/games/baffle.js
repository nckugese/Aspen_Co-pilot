/* Baffles: a shell-side parcel of fluid through a heat exchanger's segmental baffles, cut at the
 * top and the bottom in turn. It sinks; Space, ↑ or a click lifts it. A baffle passed +1; touching
 * one, or the shell, ends the run. (The frame: games/frame.js.) */
WBG.add({
  id: "baffle", name: "cw_baffle", help: ["cw_b_keys", "cw_b_rules"], over: "cw_b_over",
  R: 6, WALL: 10, SHELL: 6,
  reset(S) { Object.assign(S, { y: S.h / 2, vy: 0, walls: [], next: 0.6, flip: Math.random() < 0.5 }); },
  tap(S) { S.vy = -175; },
  step(S, dt, I) {
    if (I.U) { this.tap(S); I.U = 0; }                  // (a press, not held)
    const x = S.w * 0.28, v = Math.min(150, 82 + S.score * 2), gap = Math.max(44, 70 - S.score);
    S.vy = Math.min(260, S.vy + 520 * dt);
    S.y += S.vy * dt;
    if (S.t >= S.next) {                                 // the next baffle: its cut where the last one's was not
      S.flip = !S.flip;
      const room = S.h - 2 * this.SHELL;
      S.walls.push({ x: S.w + this.WALL, top: S.flip, len: room - gap - Math.random() * room * 0.12, done: false });
      S.next = S.t + Math.max(0.95, 1.5 - S.score * 0.02);
    }
    S.walls = S.walls.filter((b) => {
      b.x -= v * dt;
      const y0 = b.top ? this.SHELL : S.h - this.SHELL - b.len, y1 = y0 + b.len;
      if (Math.abs(b.x - x) < this.WALL / 2 + this.R && S.y + this.R > y0 && S.y - this.R < y1) S.over = true;
      if (!b.done && b.x < x - this.R) { b.done = true; S.score++; }
      return b.x > -this.WALL;
    });
    if (S.y - this.R < this.SHELL || S.y + this.R > S.h - this.SHELL) S.over = true;
  },
  draw(S, cx, C) {
    const { w, h } = S, x = w * 0.28;
    cx.fillStyle = C.mid;                                // the shell
    cx.fillRect(0, 0, w, this.SHELL - 2);
    cx.fillRect(0, h - this.SHELL + 2, w, this.SHELL - 2);
    cx.fillStyle = C.dim;                                // the tubes, faint
    for (let y = h * 0.3; y < h - 10; y += h * 0.2) cx.fillRect(0, y, w, 1);
    cx.fillStyle = C.soft;
    S.walls.forEach((b) => cx.fillRect(b.x - this.WALL / 2, b.top ? this.SHELL - 2 : h - this.SHELL + 2 - b.len, this.WALL, b.len));
    cx.fillStyle = S.over ? C.bad : C.warn;
    cx.beginPath();
    cx.arc(x, S.y, this.R, 0, 7);
    cx.fill();
  },
});
