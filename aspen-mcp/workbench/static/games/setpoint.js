/* Hold the setpoint: a level loop on manual. The controller output (OP, the valve, right) moves
 * with ↑ ↓ or follows the pointer's height; the process value (PV) follows it with a lag and a
 * drifting load, and the setpoint (SP) steps every few seconds. Each second inside the band +1;
 * 2.5 s outside it costs one of three lives. (The frame: games/frame.js.) */
WBG.add({
  id: "setpoint", name: "cw_sp", help: ["cw_sp_keys", "cw_sp_rules"], over: "cw_sp_over",
  BAND: 6, TAU: 1.6, SPAN: 8,                            // band: ± % of span; tau: s; the trend: s shown
  reset(S) {
    Object.assign(S, { pv: 50, op: 50, sp: 50, load: 0, drift: 0, nextSp: 3, out: 0, lives: 3, inside: 0, trend: [] });
  },
  step(S, dt, I) {
    if (I.U || I.D) S.op += (I.U - I.D) * 45 * dt;
    else if (I.py != null) S.op += ((1 - I.py / S.h) * 100 - S.op) * Math.min(1, dt * 10);
    S.op = Math.min(100, Math.max(0, S.op));
    if (S.t >= S.nextSp) {                               // a new setpoint, never next to the last
      let sp = S.sp;
      while (Math.abs(sp - S.sp) < 15) sp = 20 + Math.random() * 60;
      S.sp = sp;
      S.nextSp = S.t + Math.max(2.5, 5 - S.score * 0.04);
    }
    S.drift += (Math.random() - 0.5) * 40 * dt;          // the load wanders, harder as it goes
    S.drift = Math.max(-1, Math.min(1, S.drift));
    S.load += (S.drift * Math.min(30, 10 + S.score * 0.3) - S.load) * dt;
    S.pv += (S.op + S.load - S.pv) * dt / this.TAU;
    const ok = Math.abs(S.pv - S.sp) <= this.BAND;
    S.out = ok ? 0 : S.out + dt;
    if (ok) { S.inside += dt; if (S.inside >= 1) { S.inside -= 1; S.score++; } }
    if (S.out >= 2.5) { S.out = 0; S.lives--; if (S.lives <= 0) S.over = true; }
    S.trend.push([S.t, S.pv, S.sp]);
    while (S.trend.length && S.trend[0][0] < S.t - this.SPAN) S.trend.shift();
  },
  draw(S, cx, C) {
    const { w, h } = S, bw = 14, gw = w - bw - 18, top = 22, ht = h - top - 10;
    const y = (v) => top + ht * (1 - v / 100), x = (tm) => 6 + gw * (1 - (S.t - tm) / this.SPAN);
    cx.fillStyle = C.dim;                                // the band round SP
    cx.fillRect(6, y(S.sp + this.BAND), gw, y(S.sp - this.BAND) - y(S.sp + this.BAND));
    cx.lineWidth = 1.5;
    cx.lineJoin = "round";
    [[2, C.soft], [1, S.out > 0 ? C.bad : C.accent]].forEach(([i, col]) => {
      cx.strokeStyle = col;
      cx.beginPath();
      S.trend.forEach((p, k) => (k ? cx.lineTo(x(p[0]), y(p[i])) : cx.moveTo(x(p[0]), y(p[i]))));
      cx.stroke();
    });
    cx.fillStyle = C.dim;                                // OP, the valve
    cx.fillRect(w - bw - 6, top, bw, ht);
    cx.fillStyle = C.mid;
    cx.fillRect(w - bw - 6, y(S.op), bw, top + ht - y(S.op));
    cx.font = C.font(11, 600);
    cx.textBaseline = "middle";
    cx.textAlign = "left";
    cx.fillStyle = C.ink;
    cx.fillText(`SP ${S.sp.toFixed(0)}  PV ${S.pv.toFixed(0)}  OP ${S.op.toFixed(0)}`, 8, 11);
    for (let i = 0; i < 3; i++) {
      cx.fillStyle = i < S.lives ? C.accent : C.dim;
      cx.beginPath();
      cx.arc(w - 12 - i * 12, 11, 3.5, 0, 7);
      cx.fill();
    }
  },
});
