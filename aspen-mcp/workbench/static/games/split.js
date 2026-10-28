/* Cut point: components come along the feed line to a column (right), each with its normal boiling
 * point. ↑ (or a click in the upper half) sends the one nearest the column to the distillate,
 * ↓ (the lower half) to the bottoms: below the cut point goes up. Right +1; wrong, or one reaching
 * the column unsorted, costs one of three lives. The cut moves every 8. (The frame: games/frame.js.) */
WBG.add({
  id: "split", name: "cw_cut", help: ["cw_c_keys", "cw_c_rules"], over: "cw_c_over",
  // [formula, normal boiling point, °C]
  COMPS: [["H₂", -253], ["CH₄", -161], ["C₂H₆", -89], ["C₃H₈", -42], ["C₄H₁₀", -1], ["C₅H₁₂", 36], ["(CH₃)₂CO", 56],
    ["CH₃OH", 65], ["C₆H₁₄", 69], ["C₂H₅OH", 78], ["C₆H₆", 80], ["H₂O", 100], ["C₇H₈", 111], ["CH₃COOH", 118], ["C₈H₁₀", 138]],
  CUTS: [-60, -20, 20, 50, 74, 90, 105],
  reset(S) { Object.assign(S, { cut: 50, items: [], next: 0.4, lives: 3, sorted: 0, hurt: 0 }); },   // (then a new cut every 8)
  newCut(was) { let c = was; while (c === was) c = this.CUTS[Math.floor(Math.random() * this.CUTS.length)]; return c; },
  send(S, up) {
    const it = S.items.filter((x) => !x.dir).sort((a, b) => b.x - a.x)[0];
    if (!it) return;
    it.dir = up ? -1 : 1;
    if ((it.bp < S.cut) === up) {
      S.score++;
      if (++S.sorted % 8 === 0) S.cut = this.newCut(S.cut);
    } else this.miss(S, it);
  },
  miss(S, it) { it.bad = true; S.lives--; S.hurt = 0.35; if (S.lives <= 0) S.over = true; },
  tap(S, I, click) { if (!click) return false; this.send(S, I.py < S.h / 2); },
  step(S, dt, I) {
    if (I.U || I.D) { this.send(S, !!I.U); I.U = I.D = 0; }   // (a press, not held)
    const end = S.w - 46, v = Math.min(120, 46 + S.score * 1.6);
    if (S.t >= S.next) {
      const [f, bp] = this.COMPS[Math.floor(Math.random() * this.COMPS.length)];
      S.items.push({ f, bp, x: -30, y: S.h / 2, dir: 0 });
      S.next = S.t + Math.max(0.9, 2.1 - S.score * 0.03) * (0.8 + Math.random() * 0.4);
    }
    S.items = S.items.filter((it) => {
      if (it.dir) { it.y += it.dir * 220 * dt; it.x += v * 0.5 * dt; return it.y > -20 && it.y < S.h + 20; }
      it.x += v * dt;
      if (it.x >= end) { this.miss(S, it); return false; }
      return true;
    });
    if (S.hurt > 0) S.hurt -= dt;
  },
  draw(S, cx, C) {
    const { w, h } = S, end = w - 46;
    cx.fillStyle = C.dim;                                // the feed line, the column
    cx.fillRect(0, h / 2 + 12, end, 1.5);
    cx.fillStyle = S.hurt > 0 ? C.bad : C.mid;
    cx.fillRect(end + 8, 8, 24, h - 16);
    cx.fillStyle = C.bg;
    for (let y = 20; y < h - 20; y += 16) cx.fillRect(end + 11, y, 18, 1.5);
    cx.font = C.font(11, 600);
    cx.textBaseline = "middle";
    cx.textAlign = "left";
    cx.fillStyle = C.ink;
    cx.fillText(I18N.t("cw_c_cut", S.cut), 8, 11);
    for (let i = 0; i < 3; i++) {
      cx.fillStyle = i < S.lives ? C.accent : C.dim;
      cx.beginPath();
      cx.arc(end - 6 - i * 12, 11, 3.5, 0, 7);
      cx.fill();
    }
    cx.textAlign = "center";
    S.items.forEach((it) => {
      cx.font = C.font(12, 600);
      cx.fillStyle = it.bad ? C.bad : it.dir ? C.soft : C.ink;
      cx.fillText(it.f, it.x, it.y - 7);
      cx.font = C.font(10);
      cx.fillStyle = it.bad ? C.bad : C.mid;
      cx.fillText(`${it.bp} °C`, it.x, it.y + 6);
    });
  },
});
