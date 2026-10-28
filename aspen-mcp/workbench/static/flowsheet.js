/* Read-only flowsheet view: layered layout of the Aspen topology, drawn as SVG.
 *
 * The process runs left to right, as on an Aspen flowsheet: blocks sit in columns along
 * the stream direction (longest path over the graph with recycle edges reversed). A
 * stream that skips columns passes through a slot in each column it crosses, so it goes
 * around blocks, and keeps one level through them. Blocks line up with their neighbours
 * so a main line runs straight, and a stream leaves or enters a block level with its
 * other end wherever the block's side reaches. So a stream turns once at most (twice when
 * it must pass a row of blocks), at a right angle, in a track of its own between columns.
 * Recycle streams run back along lanes under the diagram. Feeds and products are small
 * terminals. Blocks whose last run ended in errors or warnings are marked; a bar at a block's
 * left says its family (mixing, heat exchange, reaction, separation, pressure), and a name too
 * long for its box is cut (the whole name in its tooltip). Clicking a block or stream calls the
 * pick handler given to FS.attach; resting the pointer on a stream asks for its hover card.
 * The Values layer puts each stream's latest temperature, pressure and flow by its label (under
 * it, or over it where a line runs below), a line each, where they fit clear of blocks, labels
 * and the other streams' lines (the columns spread apart for them); names and values are drawn
 * over every line, and value lines not at all when zoomed out past reading. A value the last
 * run moved has a small ▲ or ▼ after it and says in its tooltip what it was. The heat plans
 * layer draws a pinch plan's exchanger matches and remaining utilities over the flowsheet. A
 * dot grid lies under it all and moves with the view.
 *
 * The arrangement can also be given (FS.render's layout): Aspen's own drawing, read from Aspen
 * and mapped onto the workbench's boxes (each block where Aspen has it, streams along Aspen's
 * routes, their ends snapped onto the boxes; a route that does not fit is drawn afresh at right
 * angles), or one moved by hand. Blocks, feeds and products can be dragged, and a stream's
 * inner segments moved sideways; lines stay at right angles. A drop hands the arrangement to
 * the page, which keeps it; the drawing is never written back to Aspen.
 *
 * Two ways to draw a block (FS.render's view): its equipment symbol (fs-icons.js), the default,
 * in the line style of a journal figure (white ground, black lines, the name outside the symbol),
 * or a box with its name, type and family ("boxes"). In the icon view each block takes its
 * symbol's frame instead of the box, and a stream meets the nozzle its Aspen port says (FSI.assign):
 * that end is pinned, the router never moves it; its line runs on from the frame's edge to the
 * nozzle's tip (a lead), so what is routed and stored is the same in both views. A block whose
 * streams run right to left in a given arrangement (Aspen's drawing of it so) is drawn mirrored,
 * its feeds meeting it on the right (mirror; a custom arrangement keeps no flag: flipsOf reads it
 * back from its ends). FS.figure gives the drawing as a standalone SVG for a paper, with no state
 * of the window in it. The box view's numbers are the same as before there were icons.
 *
 * Layout and zoom live in a context object, one per tab, attached to the SVG that shows
 * the tab (FS.use), so switching tabs keeps each tab's view and two panes each keep theirs.
 * The view only ever changes at once (a pan, a zoom, a fit): nothing inside the SVG moves
 * over time. What helps the eye (a ring round a target that was brought into view, the
 * hints at an edge where more of the drawing lies) is HTML over the drawing.
 */
(function () {
  "use strict";

  const FS = (window.FS = { topInset: 48 });          // px the floating toolbar covers; fit keeps clear
  const BW = 124, BH = 56, PAD = 70;                  // block size, margin
  const GAP = 96, TRACK = 12, STUB = 22, LANE = 20;   // between columns: width, track spacing, ends; recycle lanes
  const VGAP = 40, LINE = 13;                         // while values show: the gaps widen; a value line's height
  const MAX_SHRINK = 1.3;                             // drawing units per pixel beyond which text is unreadable
  const FIT_SHRINK = 2;                               // ... and beyond which a change's dot is hard to see (FS.fitTo)
  const MIN_K = 0.2;                                  // the closest zoom: 500 %
  const { apart, esc, num } = WBA;
  const fmt = (x) => Number(Number(x).toPrecision(4)).toString();
  /** The box round two boxes ({x0, y0, x1, y1}); either may be null. */
  const join = (a, b) => (!a ? b : !b ? a : { x0: Math.min(a.x0, b.x0), y0: Math.min(a.y0, b.y0), x1: Math.max(a.x1, b.x1), y1: Math.max(a.y1, b.y1) });
  const VAL_FAR = 4;                                  // drawing units per pixel beyond which value lines are not drawn
  const STUB_V = 18;                                  // icon view: a stream off a nozzle at the top or bottom turns this far out
  const NAME_H = 21;                                  // ... and the room a block's name takes under (or over) its symbol
  /** The icon view's geometry of what is laid out, routed or drawn now (geoOf: each block's
   *  frame, body wall and nozzles; each stream's ends), set around that work as VAL is around
   *  place(); null in the box view, where everything keeps the box's numbers. */
  let GEO = null;

  // view: the viewBox; px: the SVG's size in pixels when the view was set, so a resize can
  // keep the view's centre and its drawing units per pixel; box: what is drawn (blocks,
  // terminals with their names, recycle lanes, request bubbles), in drawing units; tops:
  // [x0, y0, x1] of each of those, for how high the drawing reaches in part of its width;
  // items: the blocks and requests the edge hints count; vkey: the value lines the layout
  // made room for; marks: the keys each mark class is on (FS.mark); heatBox: what a heat
  // plan shown takes, for FS.frame, and heatParts each exchanger's and utility's (frameHeat);
  // fitted: the view is a fit nobody has moved since. key: what the layout was made from (the
  // snapshot, arrangement, import and value lines); taken: the snapshot's time; mode, fam: the
  // arrangement drawn (auto, aspen or custom) and where it came from (auto or aspen);
  // drewImport: the Aspen layout last drawn here, moved or not (a new one is fitted); asp: fromAspen's
  // layout of it, kept; canMove: things can be dragged
  // geo: the icon view's geometry of the layout drawn (null in the box view); names: each block's
  // name as drawn in the icon view, by node id ("B:NAME": placeNames's, its box joined to the
  // block's by FS.reveal and FS.fitTo)
  FS.newContext = () => ({ key: null, abs: null, lay: null, view: null, px: null, box: null, tops: [], items: [],
                           vkey: "", marks: {}, heatBox: null, heatParts: null, fitted: false,
                           taken: null, mode: null, fam: null, drewImport: null, asp: null, canMove: false,
                           geo: null, names: null });
  /** Show a tab's view context in this SVG (a view kept from another size is adapted). A
   *  press, pan or drag on the context it showed is let go first: nothing is stored, and what
   *  was held back for the press (the old tab's) is dropped. */
  FS.use = function (svg, ctx) {
    if (svg._fs !== ctx) FS.letGo(svg);
    svg._fs = ctx;
    FS.resize(svg);
    fxLayer(svg);                                    // (the context's result tags, or none; its words come with its drawing)
    if (svg._fxL) svg._fxL.ws.innerHTML = "";
  };
  const C = (svg) => svg._fs || (svg._fs = FS.newContext());

  /** A stream's latest values as lines, [{k: "t", s: "187.6 C"}, …], from {t, p, f: [value, unit]}.
   *  dl: what the last run moved of them ({t: {b, a, u}}): such a line also has d, "▲" or "▼",
   *  and was, "180.2 C" (as many digits as tell it from the value now). */
  function valueLines(vals, dl) {
    // (c: the Values layer's component line, app-comp.js cpVals -- its words written there, [_, _, text])
    return ["t", "p", "f", "c"].filter((k) => vals && vals[k]).map((k) => {
      const l = { k, s: k === "c" ? String(vals.c[2] || "") : `${fmt(vals[k][0])} ${vals[k][1] || ""}`.trim() }, m = k !== "c" && dl && dl[k];
      if (m && m.a !== m.b) {
        l.d = m.a > m.b ? "▲" : "▼";
        l.was = `${apart(Number(m.b), Number(m.a))[0]} ${m.u || vals[k][1] || ""}`.trim();
      }
      return l;
    });
  }
  FS.valueLines = valueLines;
  const lineW = (l) => valWidth(l.d ? `${l.s} ▲` : l.s);    // (the arrow drawn smaller: a little room spare)

  // the drawing's fonts (style.css sets the same): block names, labels (stream names, the
  // feeds' and products'), value lines, utility pills and request bubbles
  const FAMILY_CSS = '"Segoe UI Variable Text", "Segoe UI", "Microsoft JhengHei UI", sans-serif';
  // (the icon view's figure font: block names, and stream, feed and product names)
  const FIG_CSS = 'Arial, "Helvetica Neue", Helvetica, "Microsoft JhengHei UI", sans-serif';
  const F = { name: `600 15px ${FAMILY_CSS}`, lbl: `12.5px ${FAMILY_CSS}`, val: `11px ${FAMILY_CSS}`,
              util: `10.5px ${FAMILY_CSS}`, note: `12px ${FAMILY_CSS}`, fig: `13px ${FIG_CSS}`, figLbl: `12px ${FIG_CSS}`, figVal: `11px ${FIG_CSS}`,
              tag: `11.5px ${FAMILY_CSS}`, tagB: `600 11.5px ${FAMILY_CSS}` };   // (the preview's tags, fs-tag2)
  const TAG2_MAX = 12;                                // the preview's tags on a drawing at most
  /** The width of a text in drawing units at one of those fonts: measured by the browser's own
   *  text engine (a canvas, so nothing needs to be on screen), each text once; an estimate
   *  where there is no canvas. A label's font is the icon view's figure font there. */
  const widths = new Map();
  let pen = null;
  function textWidth(s, font = GEO ? F.figLbl : F.lbl) {
    const key = `${font}|${s}`;
    let w = widths.get(key);
    if (w !== undefined) return w;
    if (pen === null) { try { pen = document.createElement("canvas").getContext("2d") || false; } catch (e) { pen = false; } }
    if (pen) { pen.font = font; w = pen.measureText(String(s)).width; }
    else {
      const size = parseFloat(/([\d.]+)px/.exec(font)[1]);
      w = [...String(s)].reduce((a, ch) => a + (ch.codePointAt(0) > 0x2e80 ? size : size * 0.55), 0);
    }
    if (widths.size > 4000) widths.clear();
    widths.set(key, w);
    return w;
  }
  /** A value line's width: its figures are tabular (style.css), each as wide as a 0, which a
   *  canvas does not know of. */
  const valWidth = (s) => textWidth(String(s).replace(/[0-9]/g, "0"), GEO ? F.figVal : F.val);
  /** A block's name as it fits its box (BW − 16 at the name's font; BW − 22 beside a family's
   *  bar, clear of it), cut with an ellipsis. */
  function fitName(s, bar) {
    const all = [...String(s)], max = BW - (bar ? 22 : 16);
    if (textWidth(s, F.name) <= max) return String(s);
    let n = all.length - 1;
    while (n > 1 && textWidth(all.slice(0, n).join("") + "…", F.name) > max) n--;
    return all.slice(0, n).join("").trimEnd() + "…";
  }
  /** A block's family, by its Aspen type, for the colour bar at its left: mixers and splitters,
   *  heat exchangers, reactors (R and a capital: RStoic, RCSTR, …), separators, pressure
   *  changers; none for any other type. */
  const FAMILY = [["mix", /^(Mixer|FSplit|SSplit)$/i], ["heat", /^(Heater|HeatX|MHeatX)$/i], ["rx", /^R[A-Z]/],
    ["sep", /^(RadFrac|RateFrac|MultiFrac|PetroFrac|SCFrac|DSTWU|Distl|ConSep|Flash2|Flash3|Sep2?|Extract|Decanter)$/i],
    ["press", /^(Pump|Compr|MCompr|Valve|Pipe|Pipeline)$/i]];
  const family = (type) => (FAMILY.find(([, re]) => re.test(String(type || ""))) || [null])[0];
  /** A four-pointed star (the AI's ✦) centred at x, y, r to its tips: a path, so it draws the
   *  same whatever fonts the window has. */
  const star = (FS.star = (x, y, r) => { const k = r * 0.3; return `M${x},${y - r}L${x + k},${y - k}L${x + r},${y}L${x + k},${y + k}L${x},${y + r}L${x - k},${y + k}L${x - r},${y}L${x - k},${y - k}Z`; });
  /** A dot for changes not seen yet (FS.render's v.changes: {actor, n, tip}) centred at x, y:
   *  the actor's colour in a white ring (style.css .chdot); on a block, how many (9+ past
   *  nine), 15 px across; beside a stream's name a small one. Its tooltip says who and when. */
  const DOT_ACTORS = new Set(["ai", "program", "optimizer", "external", "user"]);
  function chDot(x, y, c, count) {
    const a = DOT_ACTORS.has(c.actor) ? c.actor : "external", n = Number(c.n) || 0;
    return `<g class="chdot a-${a}${count ? "" : " sm"}"><circle cx="${x}" cy="${y}" r="${count ? 7.5 : 4.5}"/>`
      + (count ? `<text x="${x}" y="${y + 3.2}">${n > 9 ? "9+" : n}</text>` : "") + `<title>${esc(c.tip || "")}</title></g>`;
  }
  /** The annotations marker (FS.render's v.pins: {n, fresh, tip}) centred at x, y: an outlined
   *  speech bubble 16 x 12 with two lines of text in it and no number -- unlike the numbered,
   *  filled dot of changes not seen yet and the AI's ✦ -- its tail towards what it is about
   *  (ang: -45 up right, from its top edge; 0 right; 180 left). Its outline is the AI's violet
   *  while one is not seen yet, grey once seen (style.css .pinmark); how many, in its tooltip
   *  (data-n: the count). A click: FS.onPin. The same drawing, as an icon: FS.pinIcon. */
  const PIN_W = 16, PIN_H = 12;
  function pinPath(x, y, ang) {
    const r = 3, x0 = x - PIN_W / 2, y0 = y - PIN_H / 2, x1 = x + PIN_W / 2, y1 = y + PIN_H / 2;
    const top = ang === -45 ? `H${x1 - r - 4}L${x1 + 1},${y0 - 4}L${x1 - r},${y0}` : "";
    const right = ang === 0 ? `V${y1 - r - 4}L${x1 + 4},${y1 - r}L${x1},${y1 - r}` : "";
    const left = ang === 180 ? `L${x0 - 4},${y1 - r}L${x0},${y1 - r - 4}` : "";
    return `M${x0 + r},${y0}${top}H${x1 - r}A${r},${r} 0 0 1 ${x1},${y0 + r}${right}V${y1 - r}A${r},${r} 0 0 1 ${x1 - r},${y1}`
      + `H${x0 + r}A${r},${r} 0 0 1 ${x0},${y1 - r}${left}V${y0 + r}A${r},${r} 0 0 1 ${x0 + r},${y0}Z`;
  }
  const pinLines = (x, y) => `M${x - 4},${y - 2}H${x + 4}M${x - 4},${y + 2}H${x + 1.5}`;
  function pinMark(x, y, p, ang) {
    const n = Number(p.n) || 0;
    return `<g class="pinmark${p.fresh ? " fresh" : ""}" data-n="${n}"><path d="${pinPath(x, y, ang)}"/><path class="pl" d="${pinLines(x, y)}"/>`
      + `<title>${esc(p.tip || "")}</title></g>`;
  }
  FS.pinMark = pinMark;                              // (the legend draws it too: app-tour.js)
  /** The marker as an icon (the edge hints' count, the layer's toggle): the sprite's chat bubble
   *  with the marker's two lines in it, .ic, 16 x 16. */
  FS.pinIcon = `<svg class="ic pin-ic" viewBox="0 0 16 16" aria-hidden="true"><path d="M2.75 4.25c0-.83.67-1.5 1.5-1.5h7.5c.83 0 1.5.67 1.5 1.5v5c0 .83-.67 1.5-1.5 1.5H7.5l-3 2.5v-2.5h-.25c-.83 0-1.5-.67-1.5-1.5z"/>`
    + `<path d="M5.5 5.5h5M5.5 8h3"/></svg>`;

  /** A block's name in the icon view: whole up to 160 units at the figure font, then cut. */
  function figName(s) {
    const all = [...String(s)], max = 160;
    if (textWidth(s, F.fig) <= max) return String(s);
    let n = all.length - 1;
    while (n > 1 && textWidth(all.slice(0, n).join("") + "…", F.fig) > max) n--;
    return all.slice(0, n).join("").trimEnd() + "…";
  }

  // ------------------------------------------------------------------ the icon view's geometry
  /* geoOf(fs): {node: {"B:NAME": dims}, ends: null | Map}. A block's dims, drawing units about
   * its centre: key (its symbol, FSI.shape), hw, hh (half its frame), body ({x0, y0, x1, y1}: the
   * body's box, where a lead to the wall stops), wall ({l: [lo, hi], ...}: the offsets a free end
   * may take on each side, the middle 70 % of the body's wall), range (the same with the nozzles'
   * offsets on that side: what a port is clamped to), text and nameW (its name as drawn), flip
   * (drawn mirrored, left for right: mirror). ends (assignEnds): each stream's {a, b, energy}, a
   * and b null at a feed or product, else {side, pin ([side, off]: on a nozzle, or null: on the
   * wall), tip ([dx, dy]: the nozzle's free end)}. */
  const ICONS = () => !!(window.FSI && FSI.types);
  /** A symbol's ink as boxes, [x0, y0, x1, y1] in icon units: each circle's and ellipse's, each
   *  stretch of a path from one move to the next (an arc taken as wide as its radius each way);
   *  read from its markup once per type. What a stream's label keeps off (the frame's empty
   *  corners are free for it). */
  const INK = new Map();
  function inkOf(key) {
    if (INK.has(key)) return INK.get(key);
    const out = [];
    (FSI.types[key].g || "").replace(/<(path|circle|ellipse)\b([^>]*)>/g, (m, tag, attrs) => {
      const at = (n) => { const r = new RegExp(` ${n}="([^"]*)"`).exec(attrs); return r ? r[1] : null; };
      if (tag !== "path") {
        const cx = +at("cx"), cy = +at("cy"), rx = +(at("r") || at("rx")), ry = +(at("r") || at("ry"));
        out.push([cx - rx, cy - ry, cx + rx, cy + ry]);
        return m;
      }
      const t = (at("d") || "").match(/[A-Za-z]|-?[\d.]+/g) || [];
      let b = null, x = 0, y = 0, x0 = 0, y0 = 0, cmd = "", i = 0;
      const add = (px, py, r = 0) => { b = b ? [Math.min(b[0], px - r), Math.min(b[1], py - r), Math.max(b[2], px + r), Math.max(b[3], py + r)] : [px - r, py - r, px + r, py + r]; };
      const n = () => +t[i++];
      while (i < t.length) {
        if (/[A-Za-z]/.test(t[i])) cmd = t[i++];
        if (cmd === "M") { if (b) out.push(b); b = null; x = x0 = n(); y = y0 = n(); add(x, y); cmd = "L"; }
        else if (cmd === "L") { x = n(); y = n(); add(x, y); }
        else if (cmd === "H") { x = n(); add(x, y); }
        else if (cmd === "V") { y = n(); add(x, y); }
        else if (cmd === "A") { const r = Math.min(n(), n()); i += 3; add(x, y, r); x = n(); y = n(); add(x, y, r); }
        else if (cmd === "C" || cmd === "Q") { for (let k = cmd === "C" ? 3 : 2; k > 0; k--) { x = n(); y = n(); add(x, y); } }
        else if (cmd === "Z" || cmd === "z") { x = x0; y = y0; }
        else i++;
      }
      if (b) out.push(b);
      return m;
    });
    INK.set(key, out);
    return out;
  }
  function geoOf(fs) {
    const K = FSI.K, node = {};
    const add = (name, type) => {
      const id = "B:" + name;
      if (node[id]) return;
      const sh = FSI.shape(type), cx = sh.w / 2, cy = sh.h / 2;
      const body = { x0: (sh.body[0] - cx) * K, y0: (sh.body[1] - cy) * K, x1: (sh.body[2] - cx) * K, y1: (sh.body[3] - cy) * K };
      const mid = (a, b) => { const m = (a + b) / 2, h = (b - a) * 0.35; return [m - h, m + h]; };
      const wall = { l: mid(body.y0, body.y1), r: mid(body.y0, body.y1), u: mid(body.x0, body.x1), d: mid(body.x0, body.x1) };
      const range = { l: wall.l.slice(), r: wall.r.slice(), u: wall.u.slice(), d: wall.d.slice() };
      Object.values(sh.ports).forEach(([x, y, side]) => {
        const off = side === "l" || side === "r" ? (y - cy) * K : (x - cx) * K;
        range[side] = [Math.min(range[side][0], off), Math.max(range[side][1], off)];
      });
      const text = figName(name), ink = inkOf(sh.key).map(([a, b, c, e]) => ({ x0: (a - cx) * K - 1.5, y0: (b - cy) * K - 1.5, x1: (c - cx) * K + 1.5, y1: (e - cy) * K + 1.5 }));
      // (box: the ink's own extent, what the state outline, the marks and the name go round, so
      // a name lies as far from every symbol's lines)
      const box = ink.reduce((u, r) => join(u, r), null) || { x0: -(sh.w * K) / 2, y0: -(sh.h * K) / 2, x1: (sh.w * K) / 2, y1: (sh.h * K) / 2 };
      node[id] = { key: sh.key, w: sh.w, h: sh.h, hw: (sh.w * K) / 2, hh: (sh.h * K) / 2, body, wall, range, text, nameW: textWidth(text, F.fig), flip: false, ink, box };
    };
    (fs.blocks || []).forEach((b) => add(b.name, b.type));
    (fs.streams || []).forEach((s) => [s.from, s.to].forEach((n) => { if (n) add(n, ""); }));
    return { node, ends: null };
  }
  /** A block's dims drawn mirrored, left for right (or back): a block whose streams mostly run
   *  right to left (Aspen's drawing of it so, or its feeds coming from the right) meets them
   *  on the side they come from, its inlets right and its outlets left. */
  const MIRROR = { l: "r", r: "l", u: "u", d: "d" };
  function mirror(d) {
    const neg = (r) => [-r[1], -r[0]];
    d.flip = !d.flip;
    d.body = { x0: -d.body.x1, y0: d.body.y0, x1: -d.body.x0, y1: d.body.y1 };
    d.ink = d.ink.map((r) => ({ x0: -r.x1, y0: r.y0, x1: -r.x0, y1: r.y1 }));
    d.box = { x0: -d.box.x1, y0: d.box.y0, x1: -d.box.x0, y1: d.box.y1 };
    [d.wall, d.range].forEach((w) => { const l = w.l; w.l = w.r; w.r = l; w.u = neg(w.u); w.d = neg(w.d); });
  }
  /** The blocks of G drawn mirrored: those in ids (a Set of node ids), the rest not. */
  function setFlips(G, ids) {
    Object.keys(G.node).forEach((k) => { if (G.node[k].flip !== ids.has(k)) mirror(G.node[k]); });
  }
  /** Each stream's ends on its blocks (FSI.assign) into G.ends, in drawing units. key(stream,
   *  end, axis): where its other end lies (the order streams on one port take its nozzles); a
   *  mirrored block's nozzles mirrored, their order along x too. */
  function assignEnds(G, fs, key) {
    const K = FSI.K, of = new Map((fs.streams || []).map((s) => [s.name, s]));
    const flipped = (sn, k) => { const s = of.get(sn), b = s && (k === "a" ? s.from : s.to), d = b && G.node["B:" + b]; return !!(d && d.flip); };
    const got = FSI.assign(fs, (sn, k, axis) => (axis === "x" && flipped(sn, k) ? -1 : 1) * key(sn, k, axis)), ends = new Map();
    got.forEach((r, s) => {
      const conv = (e) => {
        if (!e) return null;
        const d = G.node["B:" + e.block], side = d.flip ? MIRROR[e.side] : e.side;
        const tip = e.tip ? [(d.flip ? -1 : 1) * (e.tip[0] - d.w / 2) * K, (e.tip[1] - d.h / 2) * K] : null;
        const bias = (d.flip && (side === "u" || side === "d") ? -1 : 1) * (e.bias || 0);
        return { side, tip, pin: tip ? [side, side === "l" || side === "r" ? tip[1] : tip[0]] : null, bias };
      };
      ends.set(s, { a: conv(r.a), b: conv(r.b), energy: r.energy, aId: r.a ? "B:" + r.a.block : null, bId: r.b ? "B:" + r.b.block : null });
    });
    G.ends = ends;
    Object.values(G.node).forEach((d) => { delete d.room; });
    return G;
  }
  const dimOf = (id) => (GEO && id && GEO.node[id]) || null;
  /** A stream's end k ("a" | "b") in the icon view: {side, pin, tip}, or null. */
  const endGeo = (s, k) => { const e = GEO && GEO.ends && GEO.ends.get(s); return (e && e[k]) || null; };
  const pinOfEnd = (s, k) => { const e = endGeo(s, k); return e && e.pin ? e.pin : null; };
  /** The offsets of the nozzles in use on a side of a block (icon view): a free end keeps clear. */
  function pinsOn(id, side) {
    const ends = GEO && GEO.ends;
    if (!ends) return [];
    if (!ends.ix) {
      ends.ix = {};
      ends.forEach((r) => ["a", "b"].forEach((k) => { const e = r[k]; if (e && e.pin) (ends.ix[r[k + "Id"] + "|" + e.side] = ends.ix[r[k + "Id"] + "|" + e.side] || []).push(e.pin[1]); }));
    }
    return ends.ix[id + "|" + side] || [];
  }
  /** Where a stream's end starts when it has no route yet: its nozzle, else the middle of its
   *  wall (icon view); else the box's middle on the side given. */
  function startEnd(s, k, id, dflt) {
    const e = endGeo(s, k), d = dimOf(id);
    if (!e || !d) return dflt;
    if (e.pin) return e.pin.slice();
    // (one passed on beside a port's nozzles starts beside them: before them up or left)
    const w = d.wall[e.side], m = (w[0] + w[1]) / 2 + (e.bias || 0) * PORT;
    return [e.side, Math.round(Math.max(w[0], Math.min(w[1], m)) * 10) / 10];
  }
  /** The icon view's room under a block (its name, and the turns of streams off its bottom) and
   *  over it (the turns of streams off its top), for the automatic layout. */
  function roomOf(n) {
    const g = GEO && n.kind === "block" && GEO.node[n.id];
    if (!g) return { up: 0, down: 0 };
    if (!g.room) {
      let u = 0, d = 0;
      GEO.ends.forEach((r) => ["a", "b"].forEach((k) => { const e = r[k]; if (e && r[k + "Id"] === n.id) { if (e.side === "u") u++; if (e.side === "d") d++; } }));
      g.room = { up: u ? STUB_V + (u - 1) * PORT + 4 : 0, down: Math.max(NAME_H, d ? STUB_V + (d - 1) * PORT + 4 : 0) };
    }
    return g.room;
  }

  const halfW = (n) => (n.kind === "block" ? (dimOf(n.id) ? GEO.node[n.id].hw : BW / 2) : n.kind === "dummy" ? 0 : 7);
  const halfH = (n) => (n.kind === "block" ? (dimOf(n.id) ? GEO.node[n.id].hh : BH / 2) : n.kind === "dummy" ? 0 : 7);
  /** Centre-to-centre distance between neighbours in a column; streams need room for a label,
   *  and a feed or product its value lines under its name (VAL: while place() lays out for
   *  the Values layer, each stream's value lines by name). */
  const ROOM = [[20, 26, 30], [26, 20, 30], [30, 30, 46]];   // by kind: slot, terminal, block
  let VAL = null;
  const kindIx = (n) => (n.kind === "block" ? 2 : n.kind === "dummy" ? 0 : 1);
  const under = (n) => (VAL && (n.kind === "feed" || n.kind === "prod") && VAL.has(n.name) ? LINE * VAL.get(n.name).length : 0);
  const sep = (a, b) => halfH(a) + halfH(b) + ROOM[kindIx(a)][kindIx(b)] + under(a) + (GEO ? roomOf(a).down + roomOf(b).up : 0);
  const PORT = 10;                                    // least distance between streams on a block's side

  /** The graph in columns: nodes (blocks, terminals, and a slot for every column a stream
   *  skips), edges with the chain of nodes each passes through, ordered to cross little. */
  function layout(fs) {
    const nodes = new Map();
    fs.blocks.forEach((b) => nodes.set("B:" + b.name, { id: "B:" + b.name, kind: "block", name: b.name, type: b.type }));
    const edges = [];
    fs.streams.forEach((s) => {
      const a = s.from ? "B:" + s.from : "F:" + s.name;
      const b = s.to ? "B:" + s.to : "P:" + s.name;
      if (!s.from) nodes.set(a, { id: a, kind: "feed", name: s.name });
      if (!s.to) nodes.set(b, { id: b, kind: "prod", name: s.name });
      [[a, s.from], [b, s.to]].forEach(([id, name]) => {
        if (name && !nodes.has(id)) nodes.set(id, { id, kind: "block", name, type: "" });
      });
      edges.push({ name: s.name, a, b, back: false });
    });
    const out = new Map([...nodes.keys()].map((k) => [k, []]));
    edges.forEach((e) => out.get(e.a).push(e));

    // depth-first search from the feeds marks recycle (back) edges
    const mark = new Map(), post = [];
    const dfs = (u) => {
      mark.set(u, 1);
      out.get(u).forEach((e) => {
        if (mark.get(e.b) === 1) e.back = true;
        else if (!mark.get(e.b)) dfs(e.b);
      });
      mark.set(u, 2);
      post.push(u);
    };
    [...nodes.values()].filter((n) => n.kind === "feed").forEach((n) => { if (!mark.get(n.id)) dfs(n.id); });
    nodes.forEach((n, k) => { if (!mark.get(k)) dfs(k); });

    // longest-path layers over forward edges
    const topo = post.slice().reverse();
    const layer = new Map(topo.map((k) => [k, 0]));
    topo.forEach((u) => out.get(u).forEach((e) => {
      if (!e.back) layer.set(e.b, Math.max(layer.get(e.b), layer.get(u) + 1));
    }));
    edges.forEach((e) => { // a feed sits right before the block it feeds
      if (nodes.get(e.a).kind === "feed") layer.set(e.a, Math.max(0, layer.get(e.b) - 1));
    });

    // a stream that skips columns gets a slot in each one, so it is routed around blocks
    const order = topo.slice();
    edges.forEach((e, i) => {
      e.chain = [e.a];
      if (!e.back) {
        for (let l = layer.get(e.a) + 1; l < layer.get(e.b); l++) {
          const id = `D:${i}:${l}`;
          nodes.set(id, { id, kind: "dummy" });
          layer.set(id, l);
          order.push(id);
          e.chain.push(id);
        }
      }
      e.chain.push(e.b);
    });
    const cols = [];
    order.forEach((k) => { const l = layer.get(k); (cols[l] = cols[l] || []).push(k); });
    for (let i = 0; i < cols.length; i++) cols[i] = cols[i] || [];

    // barycenter sweeps reduce crossings
    const preds = new Map([...nodes.keys()].map((k) => [k, []]));
    const succs = new Map([...nodes.keys()].map((k) => [k, []]));
    edges.forEach((e) => {
      if (e.back) return;
      for (let i = 1; i < e.chain.length; i++) { preds.get(e.chain[i]).push(e.chain[i - 1]); succs.get(e.chain[i - 1]).push(e.chain[i]); }
    });
    const idx = new Map();
    const reindex = () => cols.forEach((c) => c.forEach((k, i) => idx.set(k, i)));
    const bary = (list, k) => (list.length ? list.reduce((s, p) => s + idx.get(p), 0) / list.length : idx.get(k));
    reindex();
    for (let pass = 0; pass < 6; pass++) {
      for (let l = 1; l < cols.length; l++) { cols[l].sort((x, y) => bary(preds.get(x), x) - bary(preds.get(y), y)); reindex(); }
      for (let l = cols.length - 2; l >= 0; l--) { cols[l].sort((x, y) => bary(succs.get(x), x) - bary(succs.get(y), y)); reindex(); }
    }
    return { nodes, edges, cols, layer, preds, succs, fs };
  }

  /** Positions closest to ``want`` (weighted least squares) that keep the order and at least
   *  ``gaps`` apart: pool-adjacent-violators on the positions less their offsets. */
  function isotonic(want, gaps, weights) {
    let off = 0;
    const offs = gaps.map((g) => (off += g)), pools = [];
    want.forEach((d, i) => {
      const w = weights ? weights[i] : 1;
      pools.push({ sum: w * (d - offs[i]), w, n: 1 });
      while (pools.length > 1) {
        const b = pools[pools.length - 1], a = pools[pools.length - 2];
        if (a.sum / a.w <= b.sum / b.w) break;
        a.sum += b.sum; a.w += b.w; a.n += b.n; pools.pop();
      }
    });
    const z = [];
    pools.forEach((p) => { for (let j = 0; j < p.n; j++) z.push(p.sum / p.w); });
    return z.map((v, i) => v + offs[i]);
  }

  /** The icon view: ends on one side of a block, some on nozzles (fix: they stay), the rest on
   *  its wall between lo and hi: v as given where they keep PORT apart (the usual case); else
   *  each free one, in order, the nearest spot on the wall PORT clear of the nozzles and of those
   *  placed before it (the most room where none is), so no two lines leave as one. */
  function spaced(v, fix, lo, hi) {
    if (v.every((x, i) => v.every((y, j) => j <= i || Math.abs(x - y) >= PORT - 0.05))) return v;
    const out = v.slice(), placed = v.filter((_, i) => fix[i]);
    v.forEach((x, i) => {
      if (fix[i]) return;
      let best = x, bs = -Infinity;
      for (let j = 0, n = Math.max(1, Math.ceil((hi - lo) / 0.5)); j <= n; j++) {
        const o = lo + ((hi - lo) * j) / n, sc = 1000 * Math.min(PORT, ...placed.map((u) => Math.abs(u - o))) - Math.abs(o - x);
        if (sc > bs) { bs = sc; best = Math.round(o * 10) / 10; }
      }
      out[i] = best;
      placed.push(best);
    });
    return out;
  }

  /** Whether node k may sit at height Y without crowding its neighbours in the column. */
  const fits = (abs, y, k, Y) => {
    const c = abs.cols[abs.layer.get(k)], i = c.indexOf(k), N = (x) => abs.nodes.get(x);
    const p = c[i - 1], n = c[i + 1];
    return (!p || Y >= y.get(p) + sep(N(p), N(k)) - 0.5) && (!n || Y <= y.get(n) - sep(N(k), N(n)) + 0.5);
  };

  /** Each node's neighbours along the streams (slots included), with the offset that brings the
   *  two ports level (icon view: a nozzle on the left or right has one; one on the top or bottom
   *  the level its stream turns at, STUB_V beyond the frame; else 0). */
  function portNeighbours(abs) {
    const nb = new Map([...abs.nodes.keys()].map((k) => [k, []]));
    const offOf = (e, k) => {
      const g = endGeo(e.name, k), d = g && g.pin && dimOf(k === "a" ? e.a : e.b);
      if (!d) return 0;
      return g.side === "u" ? -(d.hh + STUB_V) : g.side === "d" ? d.hh + STUB_V : g.pin[1];
    };
    abs.edges.forEach((e) => {
      if (e.back) return;
      const L = e.chain.length - 1;
      for (let i = 1; i <= L; i++) {
        const u = e.chain[i - 1], v = e.chain[i], ou = i === 1 ? offOf(e, "a") : 0, ov = i === L ? offOf(e, "b") : 0;
        nb.get(v).push([u, ou - ov]);
        nb.get(u).push([v, ov - ou]);
      }
    });
    return nb;
  }

  /** Heights. Each node is drawn toward its neighbours and then spread within its column;
   *  a stream that skips columns keeps one level through all of them, at the height of one
   *  of its ends, so it turns once at most. */
  function placeY(abs) {
    const { nodes, cols, preds, succs, edges } = abs;
    const N = (k) => nodes.get(k), y = new Map();
    // the icon view aims ports level, not centres: a neighbour reached through a nozzle on the
    // left or right counts at y(m) + its port's offset - this one's (nb: k -> [[m, offset]])
    const nb = GEO ? portNeighbours(abs) : null;
    const around = (k) => (nb ? nb.get(k) : preds.get(k).concat(succs.get(k)).map((m) => [m, 0]));
    const gaps = (c) => c.map((k, i) => (i ? sep(N(c[i - 1]), N(k)) : 0));
    const height = (c) => gaps(c).reduce((s, g) => s + g, 0);
    const tall = Math.max(0, ...cols.map(height));
    cols.forEach((c) => { let t = (tall - height(c)) / 2; gaps(c).forEach((g, i) => { t += g; y.set(c[i], t); }); });
    const long = edges.filter((e) => !e.back && e.chain.length > 2);
    const slots = (e) => e.chain.slice(1, -1);
    const mean = (list) => list.reduce((s, v) => s + v, 0) / list.length;
    const level = new Map();                      // slot -> the level its stream keeps
    for (let it = 0; it < 24; it++) {
      long.forEach((e) => {
        const m = mean(slots(e).map((d) => y.get(d))), a = y.get(e.a), b = y.get(e.b);
        const Y = Math.abs(a - m) <= Math.abs(b - m) ? a : b;
        slots(e).forEach((d) => level.set(d, Y));
      });
      const seq = cols.map((_, i) => (it % 2 ? cols.length - 1 - i : i));
      seq.forEach((l) => {
        const c = cols[l];
        const want = c.map((k) => {
          if (level.has(k)) return level.get(k);
          let s = 0, n = 0;
          if (!nb) preds.get(k).concat(succs.get(k)).forEach((m) => { const w = N(m).kind === "dummy" ? 2 : 1; s += w * y.get(m); n += w; });
          else around(k).forEach(([m, o]) => { const w = N(m).kind === "dummy" ? 2 : 1; s += w * (y.get(m) + o); n += w; });
          return n ? s / n : y.get(k);
        });
        isotonic(want, gaps(c), c.map((k) => (level.has(k) ? 8 : 1))).forEach((v, i) => y.set(c[i], v));
      });
    }
    // then pin each long stream level, the longest first, at a height the streams pinned
    // before leave room for (an end's height if possible, so it turns once); the rest of
    // each column makes way
    const pinned = new Set(), offs = new Map();
    cols.forEach((c) => { let o = 0; gaps(c).forEach((g, i) => { o += g; offs.set(c[i], o); }); });
    const clampTo = (v, [lo, hi]) => Math.max(lo, Math.min(hi, v));
    long.slice().sort((p, q) => q.chain.length - p.chain.length).forEach((e) => {
      // each slot's room between the pinned slots above and below it in its column
      const ds = slots(e), room = ds.map((d) => {
        const c = cols[abs.layer.get(d)], i = c.indexOf(d);
        let lo = -Infinity, hi = Infinity;
        for (let j = i - 1; j >= 0; j--) if (pinned.has(c[j])) { lo = level.get(c[j]) + offs.get(d) - offs.get(c[j]); break; }
        for (let j = i + 1; j < c.length; j++) if (pinned.has(c[j])) { hi = level.get(c[j]) - offs.get(c[j]) + offs.get(d); break; }
        return [lo, hi];
      });
      // as few level runs as the room allows: one, unless a column is too crowded
      const runs = [];
      let cur = null;
      ds.forEach((d, i) => {
        const r = room[i];
        if (r[0] > r[1]) { cur = null; return; }          // no room at all: this slot stays free
        const both = cur && [Math.max(cur.r[0], r[0]), Math.min(cur.r[1], r[1])];
        if (both && both[0] <= both[1]) { cur.r = both; cur.ds.push(d); } else { cur = { r, ds: [d] }; runs.push(cur); }
      });
      let prev = y.get(e.a);
      runs.forEach((run, i) => {
        const ends = i === runs.length - 1 ? [y.get(e.b), prev] : [prev, y.get(e.b)];
        const Y = ends.find((v) => v >= run.r[0] && v <= run.r[1]) ?? clampTo(ends[0], run.r);
        run.ds.forEach((d) => { level.set(d, Y); pinned.add(d); });
        prev = Y;
      });
    });
    for (let it = 0; it < 16; it++) {
      const seq = cols.map((_, i) => (it % 2 ? cols.length - 1 - i : i));
      seq.forEach((l) => {
        const c = cols[l];
        const want = c.map((k) => {
          if (pinned.has(k)) return level.get(k);
          let s = 0, n = 0;
          if (!nb) preds.get(k).concat(succs.get(k)).forEach((m) => { const w = pinned.has(m) ? 4 : 1; s += w * y.get(m); n += w; });
          else around(k).forEach(([m, o]) => { const w = pinned.has(m) ? 4 : 1; s += w * (y.get(m) + o); n += w; });
          return n ? s / n : y.get(k);
        });
        isotonic(want, gaps(c), c.map((k) => (pinned.has(k) ? 1e6 : 1))).forEach((v, i) => y.set(c[i], v));
      });
    }
    pinned.forEach((d) => y.set(d, level.get(d)));
    // a stream level with neither end (its ends moved since) moves level with one if it can
    long.forEach((e) => {
      const ds = slots(e), Y = y.get(ds[0]), reach = BH / 2 - 8;
      if (ds.some((d) => y.get(d) !== Y)) return;
      if (Math.abs(Y - y.get(e.a)) <= reach || Math.abs(Y - y.get(e.b)) <= reach) return;
      const to = [y.get(e.a), y.get(e.b)].find((v) => ds.every((d) => fits(abs, y, d, v)));
      if (to !== undefined) ds.forEach((d) => y.set(d, to));
    });
    const top = Math.min(...[...y].map(([k, v]) => v - halfH(N(k)) - (GEO ? roomOf(N(k)).up : 0)));
    y.forEach((v, k) => y.set(k, v - top + PAD));
    return y;
  }

  /** "M…" path through right-angle points, the corners rounded (square in the icon view, as a
   *  figure draws them: rad 0). */
  function roundPath(pts, rad = GEO ? 0 : 8) {
    const p = [];
    const same = (a, b) => Math.abs(a - b) < 0.5;
    pts.forEach((q) => {
      const last = p[p.length - 1];
      if (last && same(last.x, q.x) && same(last.y, q.y)) return;
      if (p.length >= 2) {
        const a = p[p.length - 2];
        if ((same(a.x, last.x) && same(last.x, q.x)) || (same(a.y, last.y) && same(last.y, q.y))) p.pop();
      }
      p.push(q);
    });
    const r1 = (v) => Math.round(v * 10) / 10;
    const len = (a, b) => Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
    const toward = (a, b, d) => { const L = len(a, b) || 1; return { x: a.x + ((b.x - a.x) * d) / L, y: a.y + ((b.y - a.y) * d) / L }; };
    let d = `M${r1(p[0].x)},${r1(p[0].y)}`;
    for (let i = 1; i < p.length - 1; i++) {
      const r = Math.min(8, len(p[i - 1], p[i]) / 2, len(p[i], p[i + 1]) / 2);
      if (!rad) { d += ` L${r1(p[i].x)},${r1(p[i].y)}`; continue; }
      const u = toward(p[i], p[i - 1], r), w = toward(p[i], p[i + 1], r);
      d += ` L${r1(u.x)},${r1(u.y)} Q${r1(p[i].x)},${r1(p[i].y)} ${r1(w.x)},${r1(w.y)}`;
    }
    const z = p[p.length - 1];
    return { d: d + ` L${r1(z.x)},${r1(z.y)}`, pts: p };
  }

  // ------------------------------------------------------------------ explicit arrangements
  /* An arrangement given explicitly rather than laid out: Aspen's own drawing (read from Aspen,
   * mapped onto the workbench's boxes: fromAspen), or one moved by hand. Each node's centre
   * ("B:block", "F:feed", "P:product", drawing units, y down) and each stream's geometry
   * {a, b, h, c}:
   *   a, b  its ends: [side, off] on a block's box ("l" | "r" | "u" | "d"; off along that side
   *         from its middle, + down for l/r, + right for u/d), or null at a terminal (its centre)
   *   h     1 when the first segment is horizontal, 0 when vertical
   *   c     each inner segment's fixed coordinate in order (x of an upright one, y of a level
   *         one). The path has c.length + 2 segments, alternating; the first runs through A, the
   *         last through B. So a path stays at right angles whatever is moved.
   * A path that no longer reads after a move (it would leave a port inward, or run back through
   * its own block) is routed again at right angles (route), close to the bends it had. */
  const EX = (function () {
    const PORT_IN = 8;          // a port stays this far inside its side's ends
    const R_STUB = 18;          // the router leaves and enters a port straight for this long at least
    const MIN_STUB = 10;        // a kept path leaves (and enters) a port outward for this long
    const FIT_TOL = 0.1;        // ... less this (numbers are stored at 0.1)
    const JOG = 6;              // inner segments shorter than this are removed
    const SNAP = 16;            // an Aspen port this close outside a box counts as on it
    const EPS = 0.01;
    const AXIS_TOL = 1;         // reading a drawn path back: a step under this is part of a straight segment
    const TERM_R = 7;           // a terminal's circle: lines are drawn to its rim
    const TERM_MIN = 26;        // a terminal's end segment, centre to first bend (circle, arrowhead, corner)
    const FAR = 1.2;            // an Aspen route end farther than FAR x its icon's scale from its block is stale
    const NEAR = 8;             // two parallel lines closer than this read as one
    const OVL_BASE = 400, OVL_PER = 6;   // what running along another stream costs a route: at all, and per unit
    const MIXED = 120;          // ... and taking anew a side where others' streams run the other way (in beside out)
    const OUT = { l: [-1, 0], r: [1, 0], u: [0, -1], d: [0, 1] };
    const AXIS_H = { l: true, r: true, u: false, d: false };
    const r1 = (v) => Math.round(v * 10) / 10;
    // (id: the block's node id, whose frame the icon view takes; none, or the box view: the box)
    const boxAt = (p, id) => {
      const d = dimOf(id);
      return d ? { x0: p[0] - d.hw, y0: p[1] - d.hh, x1: p[0] + d.hw, y1: p[1] + d.hh }
        : { x0: p[0] - BW / 2, y0: p[1] - BH / 2, x1: p[0] + BW / 2, y1: p[1] + BH / 2 };
    };
    /** The offsets a port may take on a side: the box's less PORT_IN at each end; the icon view's
     *  wall with the nozzles on that side. */
    const offRange = (side, id) => { const d = dimOf(id), lim = (AXIS_H[side] ? BH : BW) / 2 - PORT_IN; return d ? d.range[side] : [-lim, lim]; };

    /** The point of a block end [side, off] on the box about centre p. */
    function portPoint(p, end, id) {
      const [side, off] = end, b = boxAt(p, id);
      if (dimOf(id)) {
        const [lo, hi] = offRange(side, id), o = Math.max(lo, Math.min(hi, off));
        return AXIS_H[side] ? [side === "l" ? b.x0 : b.x1, p[1] + o] : [p[0] + o, side === "u" ? b.y0 : b.y1];
      }
      if (AXIS_H[side]) return [side === "l" ? b.x0 : b.x1, Math.max(b.y0 + PORT_IN, Math.min(b.y1 - PORT_IN, p[1] + off))];
      return [Math.max(b.x0 + PORT_IN, Math.min(b.x1 - PORT_IN, p[0] + off)), side === "u" ? b.y0 : b.y1];
    }
    /** An end's point: its port on the block (centre p), or p itself at a terminal. */
    const endPoint = (p, end, id) => (end ? portPoint(p, end, id) : p);
    /** The end spec of a point on a box's edge (the side it lies on). */
    function endOf(p, q, id) {
      const b = boxAt(p, id), d = { l: Math.abs(q[0] - b.x0), r: Math.abs(q[0] - b.x1), u: Math.abs(q[1] - b.y0), d: Math.abs(q[1] - b.y1) };
      const side = Object.keys(d).sort((s, t) => d[s] - d[t])[0];
      const off = AXIS_H[side] ? q[1] - p[1] : q[0] - p[0];
      if (dimOf(id)) { const [lo, hi] = offRange(side, id); return [side, r1(Math.max(lo, Math.min(hi, off)))]; }
      const lim = (AXIS_H[side] ? BH : BW) / 2 - PORT_IN;
      return [side, r1(Math.max(-lim, Math.min(lim, off)))];
    }
    /** The c.length + 2 segments of {h, c} between points a and b, unmerged: segment j (1..k)
     *  is the one at c[j - 1]. Some may have zero length. */
    function rawSegments(a, b, h, c) {
      const pts = [a.slice()];
      let cur = a.slice(), horiz = !!h;
      for (let i = 0; i <= c.length; i++) {
        const k = i < c.length ? c[i] : horiz ? b[0] : b[1];
        cur = horiz ? [k, cur[1]] : [cur[0], k];
        pts.push(cur);
        horiz = !horiz;
      }
      pts.push(b.slice());
      return pts.slice(1).map((q, j) => [pts[j], q]);
    }
    /** The points of {h, c} between a and b, repeats and straight middles dropped. */
    function pathPoints(a, b, h, c) {
      const segs = rawSegments(a, b, h, c);
      return dedupe([segs[0][0], ...segs.map((s) => s[1])]);
    }
    function dedupe(pts) {
      const out = [];
      pts.forEach((p) => {
        const l = out[out.length - 1];
        if (l && Math.abs(l[0] - p[0]) < EPS && Math.abs(l[1] - p[1]) < EPS) return;
        if (out.length >= 2) {
          const a = out[out.length - 2];
          if ((Math.abs(a[0] - l[0]) < EPS && Math.abs(l[0] - p[0]) < EPS) || (Math.abs(a[1] - l[1]) < EPS && Math.abs(l[1] - p[1]) < EPS)) out.pop();
        }
        out.push(p.slice());
      });
      return out;
    }
    /** Points -> {h, c, a, b}: an orthogonal path's segments, inner jogs shorter than jog
     *  removed (the ends stay, but for the step a nearly straight end segment makes). tol: a
     *  segment whose smaller extent is under tol counts as straight along its larger one, at its
     *  first point's coordinate. null when a segment is diagonal. */
    function normPath(points, jog = JOG, tol = EPS) {
      const pts = dedupe(points);
      if (pts.length < 2) return null;
      const a = pts[0].slice(), b = pts[pts.length - 1].slice();
      const segs = [];
      for (let i = 1; i < pts.length; i++) {
        const p = pts[i - 1], q = pts[i], dx = Math.abs(p[0] - q[0]), dy = Math.abs(p[1] - q[1]);
        if (dx < tol && dy < tol) continue;
        if (dy < tol) segs.push({ o: "h", k: p[1] });
        else if (dx < tol) segs.push({ o: "v", k: p[0] });
        else return null;
      }
      if (!segs.length) return null;
      const lenOf = (i) => {
        const s = segs[i], from = i === 0 ? (s.o === "h" ? a[0] : a[1]) : segs[i - 1].k;
        const to = i === segs.length - 1 ? (s.o === "h" ? b[0] : b[1]) : segs[i + 1].k;
        return Math.abs(to - from);
      };
      const merge = () => {
        for (let i = 1; i < segs.length; i++) {
          if (segs[i].o !== segs[i - 1].o) continue;
          const end = i === segs.length - 1 ? segs[i] : i - 1 === 0 ? segs[0] : null;
          const k = end ? end.k : lenOf(i - 1) >= lenOf(i) ? segs[i - 1].k : segs[i].k;
          segs.splice(i - 1, 2, { o: segs[i].o, k });
          return true;
        }
        return false;
      };
      for (let guard = 0; guard < 200; guard++) {
        if (merge()) continue;
        let cut = -1;
        for (let i = 1; i < segs.length - 1; i++) if (lenOf(i) < jog) { cut = i; break; }
        if (cut < 0) break;
        segs.splice(cut, 1);
      }
      if (segs[0].o === "h") a[1] = segs[0].k; else a[0] = segs[0].k;
      const L = segs[segs.length - 1];
      if (L.o === "h") b[1] = L.k; else b[0] = L.k;
      if (segs.length === 1) return { h: segs[0].o === "h" ? 1 : 0, c: [segs[0].o === "h" ? (a[0] + b[0]) / 2 : (a[1] + b[1]) / 2], a, b };
      return { h: segs[0].o === "h" ? 1 : 0, c: segs.slice(1, -1).map((s) => s.k), a, b };
    }
    /** Whether an axis-aligned segment p-q runs through the inside of box r (shrunk by e). */
    function hits(p, q, r, e = 2) {
      const x0 = r.x0 + e, y0 = r.y0 + e, x1 = r.x1 - e, y1 = r.y1 - e;
      if (Math.abs(p[1] - q[1]) < EPS) return p[1] > y0 && p[1] < y1 && Math.min(p[0], q[0]) < x1 && Math.max(p[0], q[0]) > x0;
      return p[0] > x0 && p[0] < x1 && Math.min(p[1], q[1]) < y1 && Math.max(p[1], q[1]) > y0;
    }
    const wider = (r, d = 6) => ({ x0: r.x0 - d, y0: r.y0 - d, x1: r.x1 + d, y1: r.y1 + d });   // (hits takes 2 off again)
    const inBox = (p, r) => p[0] > r.x0 + EPS && p[0] < r.x1 - EPS && p[1] > r.y0 + EPS && p[1] < r.y1 - EPS;
    const segLen = (p, q) => Math.abs(p[0] - q[0]) + Math.abs(p[1] - q[1]);
    /** Whether the path leaves port a outward (and enters b inward) for MIN_STUB at least, and
     *  a terminal end (a or b null) has an end segment of TERM_MIN at least. */
    function stubsOk(pts, ea, eb, tol = FIT_TOL) {
      if (pts.length < 2) return false;
      const lo = (v) => v - tol - 1e-9;
      const ok = (p, q, side) => { const [dx, dy] = OUT[side]; return (q[0] - p[0]) * dx + (q[1] - p[1]) * dy >= lo(MIN_STUB); };
      const n = pts.length;
      if (ea ? !ok(pts[0], pts[1], ea[0]) : segLen(pts[0], pts[1]) < lo(TERM_MIN)) return false;
      if (eb ? !ok(pts[n - 1], pts[n - 2], eb[0]) : segLen(pts[n - 1], pts[n - 2]) < lo(TERM_MIN)) return false;
      return true;
    }
    /** How many times the path runs through the boxes (its own ends' boxes count too). */
    function crossings(pts, boxes) {
      let n = 0;
      for (let i = 1; i < pts.length; i++) for (const r of boxes) if (hits(pts[i - 1], pts[i], r)) n++;
      return n;
    }
    /** How far the path runs along the segments segs ([[p, q], ...], other streams' lines): the
     *  length of every stretch of it that lies on one of them, parallel and closer than NEAR. */
    function overlap(pts, segs) {
      let tot = 0;
      if (!segs || !segs.length) return 0;
      for (let i = 1; i < pts.length; i++) {
        const p = pts[i - 1], q = pts[i], h = Math.abs(p[1] - q[1]) < EPS;
        if (!h && Math.abs(p[0] - q[0]) >= EPS) continue;
        const k = h ? 1 : 0, m = 1 - k, lo = Math.min(p[m], q[m]), hi = Math.max(p[m], q[m]);
        for (const [a, b] of segs) {
          if (Math.abs(a[k] - b[k]) >= EPS || Math.abs(a[k] - p[k]) >= NEAR) continue;
          const o = Math.min(hi, Math.max(a[m], b[m])) - Math.max(lo, Math.min(a[m], b[m]));
          if (o > 2) tot += o;
        }
      }
      return tot;
    }
    const ovlCost = (len) => (len > 0 ? OVL_BASE + OVL_PER * len : 0);
    /** The offset on a side of the box about centre p for a stream that comes to that side anew:
     *  PORT clear of the ports others have there (used), nearest the side's middle, toward the
     *  stream's other end q; the middle when the side is free. */
    function clearOff(p, used, side, q, id) {
      const d = dimOf(id);
      if (d) {                                    // (the icon view: on the wall's middle 70 %)
        const [lo, hi] = d.wall[side], i = AXIS_H[side] ? 1 : 0, mid = (lo + hi) / 2;
        used = (used || []).concat(pinsOn(id, side));
        if (!used.length) return r1(mid);
        const want = q ? Math.max(lo, Math.min(hi, q[i] - p[i])) : mid;
        let best = mid, bs = -Infinity;
        for (let o = Math.ceil(lo); o <= hi; o++) {
          const gap = Math.min(...used.map((u) => Math.abs(u - o)));
          const sc = Math.min(gap, PORT) * 100 - Math.abs(o - mid) - 0.01 * Math.abs(o - want);
          if (sc > bs) { bs = sc; best = o; }
        }
        return best;
      }
      if (!used || !used.length) return 0;
      const lim = (AXIS_H[side] ? BH : BW) / 2 - PORT_IN, i = AXIS_H[side] ? 1 : 0;
      const want = q ? Math.max(-lim, Math.min(lim, q[i] - p[i])) : 0;
      let best = 0, bs = -Infinity;
      for (let o = -Math.floor(lim); o <= lim; o++) {
        const gap = Math.min(...used.map((u) => Math.abs(u - o)));
        const sc = Math.min(gap, PORT) * 100 - Math.abs(o) - 0.01 * Math.abs(o - want);
        if (sc > bs) { bs = sc; best = o; }
      }
      return best;
    }
    const lastHoriz = (g) => (g.h && g.c.length % 2 === 1) || (!g.h && g.c.length % 2 === 0);
    /** What is drawn for a path: a terminal end stops at the circle's rim (TERM_R along its end
     *  segment), so a product's arrowhead shows; the model keeps the centre. In the icon view a
     *  block's end runs on from its frame's edge to its nozzle's tip, or to the body's wall
     *  (leads: [la, lb], each [axis, value] or null). */
    function drawPoints(pts, termA, termB, leads) {
      const p = pts.map((q) => q.slice()), n = p.length;
      const cut = (i, j) => { const L = segLen(p[i], p[j]); if (L <= 0) return; const d = Math.min(TERM_R, L / 2); p[i][0] += ((p[j][0] - p[i][0]) * d) / L; p[i][1] += ((p[j][1] - p[i][1]) * d) / L; };
      if (termA && n >= 2) cut(0, 1);
      if (termB && n >= 2) cut(n - 1, n - 2);
      if (leads && n >= 2) {
        if (leads[0]) p[0][leads[0][0]] = leads[0][1];
        if (leads[1]) p[n - 1][leads[1][0]] = leads[1][1];
      }
      return p;
    }
    /** The icon view's lead of a block end (centre p, node id, its end [side, off], whether it
     *  is on its nozzle): [axis, the tip's or the body wall's coordinate], or null. */
    function leadOf(p, id, end, tip) {
      const d = dimOf(id);
      if (!d || !end) return null;
      const side = end[0], h = AXIS_H[side];
      if (tip) return h ? [0, p[0] + tip[0]] : [1, p[1] + tip[1]];
      return h ? [0, p[0] + (side === "l" ? d.body.x0 : d.body.x1)] : [1, p[1] + (side === "u" ? d.body.y0 : d.body.y1)];
    }
    /** Both leads of stream s between centres pa, pb (n: its node ids) as its ends are now. */
    function leadsOf(s, n, pa, pb, ea, eb) {
      if (!GEO) return null;
      const ga = endGeo(s, "a"), gb = endGeo(s, "b");
      const on = (g, e) => (g && g.pin && e && e[0] === g.pin[0] && Math.abs(e[1] - g.pin[1]) < 0.06 ? g.tip : null);
      return [ea ? leadOf(pa, n[0], ea, on(ga, ea)) : null, eb ? leadOf(pb, n[1], eb, on(gb, eb)) : null];
    }
    /** A stream's geometry with its pinned ends on their nozzles (the icon view). */
    function withPins(g, s) {
      const a = s && pinOfEnd(s, "a"), b = s && pinOfEnd(s, "b");
      return a || b ? Object.assign({}, g, a && g.a ? { a: a.slice() } : {}, b && g.b ? { b: b.slice() } : {}) : g;
    }

    /** An orthogonal path from A to B, {h, c, a, b, pts}: their end sides as given, or free
     *  sides when the given ones only give a detour (allowSides). A, B: {p, end, used}: end
     *  [side, off] at a block (p its centre), null at a terminal (p its point); used: the
     *  offsets other streams' ports take on each side of that block ({l: [...], ...}), which a
     *  side taken anew keeps clear of, and opp: how many of them run the other way there (a
     *  side taken anew among those costs MIXED). boxes: every block's box. prefer: {h, c} to stay close to
     *  (the bends a path had). segs: other streams' lines, which running along costs (OVL_*);
     *  with them a block end may change sides even when the other end is a terminal, and to
     *  spare a U-turn. A.id, B.id: the blocks' node ids (their frames in the icon view); A.pin,
     *  B.pin: that end is on its nozzle, and keeps its side and offset.
     *  Deterministic. */
    function route(A, B, boxes, prefer, allowSides, segs) {
      const sidesA = A.end ? [A.end[0]] : ["r", "l", "d", "u"], sidesB = B.end ? [B.end[0]] : ["l", "r", "u", "d"];
      let best = tryRoutes(A, B, sidesA, sidesB, boxes, prefer, 0, segs);
      const all = ["l", "r", "u", "d"];
      const poor = (b) => b.cross || b.bends >= 4 || (segs && (b.ovl || b.bends >= 3));   // (with segs: a drop; a U-turn too)
      const fa = A.end && !A.pin, fb = B.end && !B.pin, free = segs ? fa || fb : fa && fb;
      if ((allowSides || !best) && (!best || (free && poor(best)))) {
        const alt = tryRoutes(A, B, fa ? all : sidesA, fb ? all : sidesB, boxes, null, 150, segs);
        if (alt && (!best || alt.score < best.score)) best = alt;
      }
      if (!best) {                   // nothing qualifies (a stream from a port to itself): straight
        const a = endPoint(A.p, A.end, A.id), b = endPoint(B.p, B.end, B.id), c = [r1((a[0] + b[0]) / 2)];
        best = { score: Infinity, cross: 0, bends: 0, h: 1, c, a: A.end, b: B.end, pts: pathPoints(a, b, 1, c) };
      }
      return best;
    }
    function tryRoutes(A, B, sidesA, sidesB, boxes, prefer, sidePenalty, segs) {
      // a side the end keeps is where its port is; one taken anew (or any, for a fresh route that
      // knows the others' ports) gets an offset clear of the other streams' ports there
      const memo = { a: {}, b: {} };
      const endAt = (E, side, q, m) => {
        if (side === E.end[0] && (E.pin || !(E.fresh && E.used))) return E.end;
        if (!(side in m)) m[side] = clearOff(E.p, E.used && E.used[side], side, q, E.id);
        return [side, m[side]];
      };
      // the end a route found, read back from its point (the icon view: as chosen, so a nozzle
      // near a corner keeps its side)
      const endIs = (E, q, side, o, m) => {
        if (!dimOf(E.id)) return endOf(E.p, q, E.id);
        const e = endAt(E, side, o, m), [lo, hi] = offRange(side, E.id);
        return [side, r1(Math.max(lo, Math.min(hi, e[1])))];
      };
      const mixed = (E, side) => (E.end && side !== E.end[0] && E.used && E.used.opp && E.used.opp[side] ? MIXED : 0);
      const pa = (side) => (A.end ? portPoint(A.p, endAt(A, side, B.p, memo.a), A.id) : A.p);
      const pb = (side) => (B.end ? portPoint(B.p, endAt(B, side, A.p, memo.b), B.id) : B.p);
      let best = null;
      const ax0 = pa(sidesA[0]), bx0 = pb(sidesB[0]);
      const near = (r, p, q) => r.x1 > Math.min(p[0], q[0]) - 200 && r.x0 < Math.max(p[0], q[0]) + 200 && r.y1 > Math.min(p[1], q[1]) - 200 && r.y0 < Math.max(p[1], q[1]) + 200;
      let local = boxes.filter((r) => near(r, ax0, bx0));
      if (segs) {                                  // (as fit's avoid: other blocks 4 units wider)
        const own = [A.end && boxAt(A.p, A.id), B.end && boxAt(B.p, B.id)].filter(Boolean);
        local = local.map((r) => (own.some((o) => Math.abs(o.x0 - r.x0) < EPS && Math.abs(o.y0 - r.y0) < EPS) ? r : wider(r)));
      }
      // the other streams' lines near enough to matter (a lane may reach a little further)
      const lsegs = segs && segs.length
        ? segs.filter(([p, q]) => near({ x0: Math.min(p[0], q[0]) - 60, y0: Math.min(p[1], q[1]) - 60, x1: Math.max(p[0], q[0]) + 60, y1: Math.max(p[1], q[1]) + 60 }, ax0, bx0))
        : null;
      sidesA.forEach((sa) => sidesB.forEach((sb) => {
        const a = pa(sa), b = pb(sb);
        // a terminal's line leaves it straight for TERM_MIN (its circle, the arrowhead, a corner)
        const a1 = A.end ? [a[0] + OUT[sa][0] * R_STUB, a[1] + OUT[sa][1] * R_STUB] : [a[0] + OUT[sa][0] * TERM_MIN, a[1] + OUT[sa][1] * TERM_MIN];
        const b1 = B.end ? [b[0] + OUT[sb][0] * R_STUB, b[1] + OUT[sb][1] * R_STUB] : [b[0] + OUT[sb][0] * TERM_MIN, b[1] + OUT[sb][1] * TERM_MIN];
        const xs = new Set([r1((a1[0] + b1[0]) / 2), a1[0], b1[0]]), ys = new Set([r1((a1[1] + b1[1]) / 2), a1[1], b1[1]]);
        local.forEach((r) => { xs.add(r.x0 - R_STUB); xs.add(r.x1 + R_STUB); ys.add(r.y0 - R_STUB - 6); ys.add(r.y1 + R_STUB + 6); });
        if (lsegs && lsegs.length) {             // beside the lanes others may take: PORT on, and twice
          [[a1, A.end ? sa : null], [b1, B.end ? sb : null]].forEach(([p, s]) => {
            if (!s) return;
            const o = OUT[s];
            [1, 2].forEach((k) => { if (o[0]) xs.add(r1(p[0] + o[0] * PORT * k)); else ys.add(r1(p[1] + o[1] * PORT * k)); });
          });
          [-1, 1].forEach((d) => { xs.add(r1((a1[0] + b1[0]) / 2 + d * PORT)); ys.add(r1((a1[1] + b1[1]) / 2 + d * PORT)); });
        }
        const lane = local.length ? [Math.min(...local.map((r) => r.y0)) - 30, Math.max(...local.map((r) => r.y1)) + 30, Math.min(...local.map((r) => r.x0)) - 30, Math.max(...local.map((r) => r.x1)) + 30] : null;
        if (prefer) prefer.c.forEach((k) => { xs.add(k); ys.add(k); });
        const mids = [[[b1[0], a1[1]]], [[a1[0], b1[1]]]];
        xs.forEach((x) => mids.push([[x, a1[1]], [x, b1[1]]]));
        ys.forEach((y) => mids.push([[a1[0], y], [b1[0], y]]));
        if (lane) {
          [lane[0], lane[1]].forEach((y) => xs.forEach((x) => { mids.push([[a1[0], y], [x, y], [x, b1[1]]]); mids.push([[x, a1[1]], [x, y], [b1[0], y]]); }));
          [lane[2], lane[3]].forEach((x) => ys.forEach((y) => { mids.push([[x, a1[1]], [x, y], [b1[0], y]]); mids.push([[a1[0], y], [x, y], [x, b1[1]]]); }));
        }
        const seen = new Set();                    // (many candidates come to the same path: each is scored once)
        mids.forEach((m) => {
          const g = normPath(dedupe([a, a1, ...m, b1, b]), 0.5);
          if (!g) return;
          if (A.end && AXIS_H[sa] !== !!g.h) return;               // first segment along the port's axis
          if (B.end && AXIS_H[sb] !== lastHoriz(g)) return;
          const key = g.h + ":" + g.c.join(",");
          if (seen.has(key)) return;
          seen.add(key);
          const pp = pathPoints(a, b, g.h, g.c);
          if (!stubsOk(pp, A.end ? [sa] : null, B.end ? [sb] : null, 0)) return;   // strict when made; kept ones get FIT_TOL
          let len = 0;
          for (let i = 1; i < pp.length; i++) len += segLen(pp[i - 1], pp[i]);
          const bends = pp.length - 2, like = prefer && prefer.h === g.h && prefer.c.length === g.c.length;
          let score = len + 28 * bends + (A.end && sa !== A.end[0] ? sidePenalty : 0) + (B.end && sb !== B.end[0] ? sidePenalty : 0) + mixed(A, sa) + mixed(B, sb);
          // (crossings and the distance from the preference only add: a path that cannot win is
          // not measured further, which is most of them; the result is the same)
          if (best && score - (like ? 60 : 0) >= best.score) return;
          if (like) score += 0.3 * g.c.reduce((s, k, i) => s + Math.abs(k - prefer.c[i]), 0) - 60;
          if (best && score >= best.score) return;
          const cross = crossings(pp, local);
          score += 5000 * cross;
          if (best && score >= best.score) return;
          const ovl = lsegs ? overlap(pp, lsegs) : 0;
          score += ovlCost(ovl);
          if (!best || score < best.score) best = { score, cross, ovl, bends, h: g.h, c: g.c.map(r1), a: A.end ? endIs(A, a, sa, B.p, memo.a) : null, b: B.end ? endIs(B, b, sb, A.p, memo.b) : null, pts: pp };
        });
      }));
      return best;
    }

    /** Whether {a, b, h, c} still reads between node centres pa, pb: first and last segments
     *  along their ports' axes, leaving and entering outward (MIN_STUB, TERM_MIN at a
     *  terminal), through neither end's own box. Its points, or null. n: the node ids at its
     *  ends (the icon view's frames). */
    function keeps(g, pa, pb, n) {
      if (!g || !g.c || !pa || !pb) return null;
      const ia = n && n[0], ib = n && n[1];
      const a = endPoint(pa, g.a, ia), b = endPoint(pb, g.b, ib);
      const pts = pathPoints(a, b, g.h, g.c);
      const own = [g.a && boxAt(pa, ia), g.b && boxAt(pb, ib)].filter(Boolean);
      const axesOk = (!g.a || AXIS_H[g.a[0]] === !!g.h) && (!g.b || AXIS_H[g.b[0]] === lastHoriz(g));
      return axesOk && stubsOk(pts, g.a, g.b) && !crossings(pts, own) ? pts : null;
    }
    /** A stream's geometry between node centres pa, pb: kept when it still reads, else the last
     *  drag frame's route while that reads (steady, and no routing), else routed again with the
     *  old bends as the preference. fresh: route it anyway. avoid ({segs, ua, ub}: the other
     *  streams' lines, and their ports on A's and B's blocks, as route takes them; given for
     *  the streams a drop moves): a path is kept only when it also keeps out of every other
     *  block and off the other lines, else it is routed clear of them where that does better.
     *  Numbers at 0.1, and the points those numbers give. who: {n: its node ids, s: its name},
     *  for the icon view's frames and nozzles (an end on a nozzle is put there and stays).
     */
    function fit(g, pa, pb, boxes, fresh, allowSides = true, last = null, avoid = null, who = null) {
      const n = who && who.n, ia = n && n[0], ib = n && n[1];
      const pa0 = !!(who && GEO && pinOfEnd(who.s, "a") && g.a), pb0 = !!(who && GEO && pinOfEnd(who.s, "b") && g.b);
      if (pa0 || pb0) g = withPins(g, who.s);
      // (against avoid, the other blocks count 4 units wider: a line along an edge reads as the box's)
      const own = avoid ? [g.a && boxAt(pa, ia), g.b && boxAt(pb, ib)].filter(Boolean) : [];
      const others = avoid ? boxes.filter((r) => !own.some((o) => Math.abs(o.x0 - r.x0) < EPS && Math.abs(o.y0 - r.y0) < EPS)).map((r) => wider(r)) : null;
      const bad = (pts) => (avoid ? 5000 * crossings(pts, others) + ovlCost(overlap(pts, avoid.segs)) : 0);
      let held = null;
      if (!fresh) {
        const pts = keeps(g, pa, pb, n);
        if (pts) {
          held = { a: g.a, b: g.b, h: g.h, c: g.c, pts, kept: true };
          if (!bad(pts)) return held;
        }
        const lp = !held && last && keeps(last, pa, pb, n);
        if (lp) return { a: last.a, b: last.b, h: last.h, c: last.c, pts: lp, kept: false };
      }
      const A = { p: pa, end: g.a, used: avoid && avoid.ua, fresh, id: ia, pin: pa0 }, B = { p: pb, end: g.b, used: avoid && avoid.ub, fresh, id: ib, pin: pb0 };
      const r = route(A, B, boxes, fresh ? null : { h: g.h, c: g.c }, allowSides, avoid && avoid.segs);
      const c = r.c.map(r1);
      const out = { a: r.a, b: r.b, h: r.h, c, pts: pathPoints(endPoint(pa, r.a, ia), endPoint(pb, r.b, ib), r.h, c), kept: false };
      return held && bad(out.pts) >= bad(held.pts) ? held : out;
    }
    /** What an explicit layout takes, streams included: {x0, y0, x1, y1}. */
    function extent(nodes, paths) {
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      const g = (a, b, c, d) => { x0 = Math.min(x0, a); y0 = Math.min(y0, b); x1 = Math.max(x1, c); y1 = Math.max(y1, d); };
      Object.entries(nodes).forEach(([k, p]) => { const d = dimOf(k), hw = d ? d.hw : k[0] === "B" ? BW / 2 : TERM_R, hh = d ? d.hh : k[0] === "B" ? BH / 2 : TERM_R; g(p[0] - hw, p[1] - hh, p[0] + hw, p[1] + hh); });
      paths.forEach((pts) => pts.forEach((p) => g(p[0], p[1], p[0], p[1])));
      return { x0, y0, x1, y1 };
    }

    // ---------------------------------------------------------------- Aspen's drawing
    const MX = 56, MY = 40;          // scale: room wanted between a block and its nearest neighbour
    const GX = 24, GY = 20;          // stretch: least room between two boxes
    const S_MIN = 40, S_MAX = 200, S_ONE = 70, S_Q = 0.75, S_RATIO = 1.6;
    const quantile = (arr, q) => { const s = arr.slice().sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.floor(q * (s.length - 1) + 0.5))]; };
    /** Per-axis scales from each block's nearest neighbour: a pair set apart mostly along x
     *  asks x for (BW + MX) / dx, one along y asks y for (BH + MY) / dy; each axis takes the
     *  S_Q quantile of what it is asked; the two stay within S_RATIO of each other. */
    function scales(B, ids) {
      const ax = [], ay = [];
      // (the room a pair wants: two boxes, or in the icon view their two frames)
      const wx = (i, j) => { const p = dimOf(ids && ids[i]), q = dimOf(ids && ids[j]); return p && q ? p.hw + q.hw + MX : BW + MX; };
      const wy = (i, j) => { const p = dimOf(ids && ids[i]), q = dimOf(ids && ids[j]); return p && q ? p.hh + q.hh + MY + NAME_H : BH + MY; };
      B.forEach((a, i) => {
        let best = null;
        B.forEach((b, j) => {
          if (i === j) return;
          const dx = Math.abs(a.x - b.x), dy = Math.abs(a.y - b.y), d = Math.max(dx / wx(i, j), dy / wy(i, j));
          if (d > 0 && (!best || d < best.d)) best = { d, dx, dy, nx: wx(i, j), ny: wy(i, j) };
        });
        if (!best) return;
        if (best.dx / best.nx >= best.dy / best.ny) ax.push(best.nx / best.dx); else ay.push(best.ny / best.dy);
      });
      const clamp = (v) => Math.max(S_MIN, Math.min(S_MAX, v));
      let sx = ax.length ? clamp(quantile(ax, S_Q)) : null, sy = ay.length ? clamp(quantile(ay, S_Q)) : null;
      if (sx === null && sy === null) sx = sy = S_ONE;
      else if (sx === null) sx = sy;
      else if (sy === null) sy = sx;
      sy = Math.max(sx / S_RATIO, Math.min(sx * S_RATIO, sy));
      return { sx, sy };
    }
    /** Boxes closer than GX x GY move apart by room inserted along one axis: every coordinate
     *  beyond an insertion moves on by the same amount, so each axis stays in order and
     *  orthogonal routes stay orthogonal. P (centres) moves in place; the insertions per axis,
     *  in order, [[at, by], ...]. */
    function stretch(P, gap = (i, j) => [BW + GX, BH + GY]) {
      // (gap(i, j): the least distance between the centres of two, [x, y]: two boxes and GX, GY;
      // placeExplicit's spread() gives its own)
      const ins = { x: [], y: [] };
      const push = (ax, at, by) => { ins[ax].push([at, by]); const i = ax === "x" ? 0 : 1; P.forEach((p) => { if (p[i] > at) p[i] += by; }); };
      for (let round = 0; round < 20; round++) {
        const conf = [];
        for (let i = 0; i < P.length; i++) for (let j = i + 1; j < P.length; j++) {
          const dX = Math.abs(P[i][0] - P[j][0]), dY = Math.abs(P[i][1] - P[j][1]), [nx, ny] = gap(i, j);
          const ox = nx - dX, oy = ny - dY;
          if (ox <= 0 || oy <= 0) continue;
          const ax = dX < EPS ? "y" : dY < EPS ? "x" : ox / nx <= oy / ny ? "x" : "y";
          conf.push({ i, j, ax });
        }
        if (!conf.length) break;
        ["x", "y"].forEach((ax) => {
          const k = ax === "x" ? 0 : 1;
          conf.filter((c) => c.ax === ax)
            .map((c) => (P[c.i][k] <= P[c.j][k] ? { lo: c.i, hi: c.j } : { lo: c.j, hi: c.i }))
            .sort((p, q) => P[p.hi][k] - P[q.hi][k] || P[p.lo][k] - P[q.lo][k])
            .forEach(({ lo, hi }) => {
              const dX = Math.abs(P[lo][0] - P[hi][0]), dY = Math.abs(P[lo][1] - P[hi][1]), [nx, ny] = gap(lo, hi), need = ax === "x" ? nx : ny;
              if (dX >= nx || dY >= ny) return;        // solved on the way
              const s = P[hi][k] - P[lo][k];
              const prev = Math.max(...P.map((p) => p[k]).filter((v) => v < P[hi][k] - EPS), P[lo][k]);
              push(ax, (prev + P[hi][k]) / 2, need - s);
            });
        });
      }
      return ins;
    }
    const through = (v, list) => list.reduce((w, [at, by]) => (w > at ? w + by : w), v);

    /** The explicit layout for Aspen's drawing imp (a session's aspen_layout) of flowsheet fs
     *  ({blocks: [{name}], streams: [{name, from, to}]}): {nodes, streams, info}. info: the
     *  scales, and each stream drawn afresh with why (fallback). In the icon view (GEO: fs's
     *  blocks with their types, its streams with their ports) the blocks are spaced on their
     *  frames and names, and each stream meets its nozzles (assigned here, in the order of where
     *  Aspen has the other ends). */
    function fromAspen(imp, fs) {
      const ib = imp.blocks || {}, is = imp.streams || {};
      const all = fs.blocks.map((b) => b.name).filter((n) => ib[n] && isFinite(ib[n].x) && isFinite(ib[n].y));
      const at = {};
      all.forEach((n) => { const k = ib[n].x + "," + ib[n].y; (at[k] = at[k] || []).push(n); });
      // a block at (0, 0), or on another's exact place, is Aspen's "not placed"
      const names = all.filter((n) => at[ib[n].x + "," + ib[n].y].length === 1 && !(ib[n].x === 0 && ib[n].y === 0));
      const ids = names.map((n) => "B:" + n);
      const { sx, sy } = scales(names.map((n) => ib[n]), ids);
      const P = names.map((n) => [ib[n].x * sx, -ib[n].y * sy]);
      const ins = GEO ? stretch(P, (i, j) => { const p = dimOf(ids[i]), q = dimOf(ids[j]); return [p.hw + q.hw + GX, p.hh + q.hh + GY + NAME_H]; }) : stretch(P);
      const map = (x, y) => [through(x * sx, ins.x), through(-y * sy, ins.y)];
      const pos = {};
      names.forEach((n, i) => { pos["B:" + n] = P[i]; });
      const boxes = Object.keys(pos).map((k) => boxAt(pos[k], k));
      let flip = null;
      if (GEO) {
        // (each stream's nozzles, in the order of where Aspen's route comes to the block from:
        // its last bend before it, else its other end; a block drawn mirrored where Aspen meets
        // its streams on the sides a mirrored symbol has them, its feeds coming from the right)
        const route = {}, of = new Map(fs.streams.map((s) => [s.name, s]));
        fs.streams.forEach((s) => {
          const rec = is[s.name], raw = rec && Array.isArray(rec.pts) && rec.pts.length >= 2 ? rec.pts : null;
          if (raw) route[s.name] = raw.map((q) => map(q[0], q[1]));
        });
        const otherEnd = (s, k) => {
          const other = k === "a" ? s.to : s.from, r = route[s.name];
          return other && pos["B:" + other] ? pos["B:" + other] : r ? r[k === "a" ? r.length - 1 : 0] : null;
        };
        const toward = (s, k) => { const r = route[s.name], n = r ? r.length : 0; return n ? r[k === "a" ? Math.min(n - 1, 2) : Math.max(0, n - 3)] : otherEnd(s, k); };
        const key = (sn, k, axis) => { const q = toward(of.get(sn), k); return q ? q[axis === "x" ? 0 : 1] : 0; };
        const votes = {};                         // node id -> [as drawn, mirrored]
        fs.streams.forEach((s) => {
          if (FSI.isEnergy(s.from_port) || FSI.isEnergy(s.to_port)) return;
          [["a", s.from, false], ["b", s.to, true]].forEach(([k, blk, inlet]) => {
            const id = blk && "B:" + blk, p = id && pos[id], d = p && dimOf(id);
            if (!d) return;
            const v = (votes[id] = votes[id] || [0, 0]), r = route[s.name], q = r && r[k === "a" ? 0 : r.length - 1], o = otherEnd(s, k);
            // (the side Aspen's route meets it on counts twice, where its other end lies once:
            // an inlet on the right or an outlet on the left asks for it mirrored)
            if (q && Math.abs(q[0] - p[0]) > Math.abs(q[1] - p[1])) v[(q[0] > p[0]) === inlet ? 1 : 0] += 2;
            if (o && Math.abs(o[0] - p[0]) > d.hw) v[(o[0] > p[0]) === inlet ? 1 : 0] += 1;
          });
        });
        flip = Object.keys(votes).filter((id) => votes[id][1] > votes[id][0]);
        setFlips(GEO, new Set(flip));
        assignEnds(GEO, fs, key);
      }
      const info = { sx, sy, insertions: ins.x.length + ins.y.length, fallback: {}, unplaced: fs.blocks.map((b) => b.name).filter((n) => !names.includes(n)) };
      const streams = {}, later = [];
      const stale = (bname, q) => { const B = ib[bname]; return B && Math.max(Math.abs(q[0] - B.x), Math.abs(q[1] - B.y)) > FAR * Math.max(1, B.scale || 1); };
      fs.streams.forEach((s) => {
        const rec = is[s.name];
        const ia = s.from ? "B:" + s.from : "F:" + s.name, ibn = s.to ? "B:" + s.to : "P:" + s.name;
        const raw = rec && Array.isArray(rec.pts) && rec.pts.length >= 2 ? rec.pts : null;
        const pts = raw ? raw.map((q) => map(q[0], q[1])) : null;
        const atp = rec && Array.isArray(rec.at) ? map(rec.at[0], rec.at[1]) : null;
        if (!s.from) pos[ia] = pts ? pts[0].slice() : atp;
        if (!s.to) pos[ibn] = pts ? pts[pts.length - 1].slice() : atp && atp.slice();
        const why = !rec ? "not in Aspen's drawing" : !pts ? "no route" : (s.from && !pos[ia]) || (s.to && !pos[ibn]) ? "end not placed"
          : (s.from && stale(s.from, raw[0])) || (s.to && stale(s.to, raw[raw.length - 1])) ? "route ends away from its block" : null;
        if (why) { later.push([s, why]); return; }
        const g = snapAspen(pts, s.from ? pos[ia] : null, s.to ? pos[ibn] : null, boxes, ia, ibn);
        if (g.why) { later.push([s, g.why, g]); return; }
        if (!s.from) pos[ia] = g.ta.slice();
        if (!s.to) pos[ibn] = g.tb.slice();
        // (the icon view: each end where its port says, a nozzle or its wall's middle: Aspen's
        // symbols are not these, and its route is only the preference from here on)
        streams[s.name] = { a: g.a && startEnd(s.name, "a", ia, g.a), b: g.b && startEnd(s.name, "b", ibn, g.b), h: g.h, c: g.c };
      });
      Object.keys(pos).forEach((k) => { if (!pos[k]) delete pos[k]; });
      const lay = { nodes: pos, streams };
      placeMissing(lay, fs);
      const allBoxes = () => Object.keys(pos).filter((k) => k[0] === "B").map((k) => boxAt(pos[k], k));
      // a terminal on a box moves out of it, beyond its port; the streams moved, by name
      const offBlocks = () => {
        const bx = allBoxes(), moved = new Set();
        fs.streams.forEach((s) => {
          [[!s.from, "F:" + s.name], [!s.to, "P:" + s.name]].forEach(([term, id]) => {
            if (!term || !pos[id]) return;
            const r = bx.find((b) => pos[id][0] > b.x0 - 10 && pos[id][0] < b.x1 + 10 && pos[id][1] > b.y0 - 10 && pos[id][1] < b.y1 + 10);
            if (!r) return;
            pos[id] = id[0] === "F" ? [r.x0 - 48, pos[id][1]] : [r.x1 + 48, pos[id][1]];
            info.fallback[s.name] = info.fallback[s.name] || "terminal on a block";
            moved.add(s.name);
          });
        });
        return moved;
      };
      offBlocks();
      later.forEach(([s, why, g]) => {
        info.fallback[s.name] = why;
        const ia = s.from ? "B:" + s.from : "F:" + s.name, ibn = s.to ? "B:" + s.to : "P:" + s.name;
        const pa = pinOfEnd(s.name, "a"), pb = pinOfEnd(s.name, "b");
        const ea = s.from ? pa || (g && g.a) || startEnd(s.name, "a", ia, ["r", 0]) : null, eb = s.to ? pb || (g && g.b) || startEnd(s.name, "b", ibn, ["l", 0]) : null;
        const r = route({ p: pos[ia], end: ea, id: ia, pin: !!pa }, { p: pos[ibn], end: eb, id: ibn, pin: !!pb }, allBoxes(), null, true);
        streams[s.name] = { a: r.a, b: r.b, h: r.h, c: r.c };
      });
      spreadPorts(lay, fs);
      spreadTerminals(lay);
      straightenTerminals(lay, fs);
      lengthenTerminals(lay, fs);
      // the spreading can push a terminal onto a box again: off it once more, its stream drawn
      // afresh; what else the spreading moved: a path that no longer reads is routed again, so
      // the layout handed on is one the next render keeps as it is
      const again = offBlocks(), ab = allBoxes(), cache = new Map();
      fs.streams.forEach((s) => {
        const g = streams[s.name];
        if (!g) return;
        const ia = s.from ? "B:" + s.from : "F:" + s.name, ibn = s.to ? "B:" + s.to : "P:" + s.name;
        // (the icon view: most routes are drawn afresh on the nozzles; each keeps off the lines
        // and ports of the others, as a drop does)
        const r = fit(g, pos[ia], pos[ibn], ab, again.has(s.name), true, null, GEO ? avoidIn(lay, fs, s.name, cache) : null, { n: [ia, ibn], s: s.name });
        if (!r.kept) { streams[s.name] = { a: r.a, b: r.b, h: r.h, c: r.c }; info.fallback[s.name] = info.fallback[s.name] || "ports spread"; }
      });
      if (GEO) untangle(lay, fs, ab, cache);
      shift(lay, fs);
      straightenStreams(lay, fs);
      // (flip: the blocks drawn mirrored, which placeExplicit draws so; a custom arrangement
      // kept from this has none, and placeExplicit finds them again from its ends: flipsOf)
      return Object.assign(lay, { info }, flip ? { flip } : {});
    }
    /** What stream name keeps clear of in an explicit layout as it is (fit's avoid): every other
     *  stream's line, and their ports on its own blocks. */
    function avoidIn(lay, fs, name, cache) {
      const segs = [], ports = {}, me = fs.streams.find((s) => s.name === name);
      const mine = [me.from && "B:" + me.from, me.to && "B:" + me.to];
      fs.streams.forEach((s) => {
        const g = lay.streams[s.name];
        if (s.name === name || !g) return;
        const pts = ptsIn(lay, s, cache);
        for (let i = 1; i < pts.length; i++) segs.push([pts[i - 1], pts[i]]);
        [[s.from, g.a, true], [s.to, g.b, false]].forEach(([blk, e, leaves]) => {
          const id = blk && "B:" + blk;
          if (!e || !mine.includes(id)) return;
          const p = (ports[id] = ports[id] || { l: [], r: [], u: [], d: [], opp: { l: 0, r: 0, u: 0, d: 0 } });
          p[e[0]].push(e[1]);
          if (me.from !== me.to && leaves !== (id === mine[0])) p.opp[e[0]]++;
        });
      });
      return { segs, ua: (mine[0] && ports[mine[0]]) || null, ub: (mine[1] && ports[mine[1]]) || null };
    }
    /** A stream's points in an explicit layout, kept while its geometry object stays the same
     *  (cache: a Map for one pass, while no node moves). */
    function ptsIn(lay, s, cache) {
      const g = lay.streams[s.name], got = cache && cache.get(s.name);
      if (got && got.g === g) return got.pts;
      const pts = pointsOf(lay, s);
      if (cache) cache.set(s.name, { g, pts });
      return pts;
    }
    /** The icon view: a stream whose line runs along another's (most routes there are drawn
     *  afresh, onto nozzles) is fitted once more, keeping off the others' lines and ports.
     *  lay.streams changed in place; the names changed. */
    function untangle(lay, fs, boxes, cache = new Map()) {
      const changed = [];
      fs.streams.forEach((s) => {
        const g = lay.streams[s.name], ia = s.from ? "B:" + s.from : "F:" + s.name, ib = s.to ? "B:" + s.to : "P:" + s.name;
        if (!g || !lay.nodes[ia] || !lay.nodes[ib]) return;
        const av = avoidIn(lay, fs, s.name, cache);
        if (!overlap(ptsIn(lay, s, cache), av.segs)) return;
        const r = fit(g, lay.nodes[ia], lay.nodes[ib], boxes, false, true, null, av, { n: [ia, ib], s: s.name });
        if (r.kept) return;
        lay.streams[s.name] = Object.assign({}, g, { a: r.a, b: r.b, h: r.h, c: r.c });
        changed.push(s.name);
      });
      return changed;
    }
    /** A stream between two blocks that steps aside by less than 8 units on its way (a Z with
     *  that short a middle: Aspen's icons are larger than the boxes, so its ports were pulled in)
     *  runs straight: the port it enters, else the one it leaves, moves level with the other,
     *  within its side's port range and PORT from the other ports there, where the line still
     *  reads and crosses no box. After shift(): the numbers stay at 0.1. */
    function straightenStreams(lay, fs) {
      const boxes = Object.keys(lay.nodes).filter((k) => k[0] === "B").map((k) => boxAt(lay.nodes[k], k));
      const others = (blk, side, name, key) => fs.streams.flatMap((s) => [[s.from, "a"], [s.to, "b"]]
        .filter(([b, k]) => b === blk && !(s.name === name && k === key) && lay.streams[s.name] && lay.streams[s.name][k] && lay.streams[s.name][k][0] === side)
        .map(([, k]) => lay.streams[s.name][k][1]));
      fs.streams.forEach((s) => {
        const g = lay.streams[s.name], pa = s.from && lay.nodes["B:" + s.from], pb = s.to && lay.nodes["B:" + s.to];
        if (!g || !pa || !pb || s.from === s.to || !g.a || !g.b || g.c.length !== 1) return;
        if (AXIS_H[g.a[0]] !== !!g.h || AXIS_H[g.b[0]] !== !!g.h) return;        // a Z: both ends along its first and last legs
        const n = ["B:" + s.from, "B:" + s.to], i = g.h ? 1 : 0, A = portPoint(pa, g.a, n[0]), B = portPoint(pb, g.b, n[1]);
        if (Math.abs(B[i] - A[i]) < EPS || Math.abs(B[i] - A[i]) >= 8) return;
        for (const [k, p, want, blk] of [["b", pb, A[i], s.to], ["a", pa, B[i], s.from]]) {
          if (pinOfEnd(s.name, k)) continue;      // (an end on its nozzle stays)
          const side = g[k][0], [lo, hi] = offRange(side, "B:" + blk), off = r1(want - p[i]);
          if (off < lo - EPS || off > hi + EPS || others(blk, side, s.name, k).some((o) => Math.abs(o - off) < PORT - EPS)) continue;
          const t = Object.assign({}, g, { [k]: [side, off] }), pts = keeps(t, pa, pb, n);
          if (!pts || crossings(pts, boxes)) continue;
          g[k] = t[k];
          break;
        }
      });
    }
    /** An Aspen path, in drawing units, cut or extended onto the workbench boxes of its ends. */
    function snapAspen(pts, pa, pb, boxes, ia, ib) {
      let g = normPath(pts, JOG);
      if (!g) return { why: "diagonal segment" };
      let p = pathPoints(g.a, g.b, g.h, g.c);
      const ends = {};
      for (const [end, centre] of [["a", pa], ["b", pb]]) {
        if (!centre) continue;
        let seq = end === "a" ? p : p.slice().reverse();
        const id = end === "a" ? ia : ib, r = boxAt(centre, id);
        let got;
        const q = seq[0], out = Math.max(r.x0 - q[0], q[0] - r.x1, r.y0 - q[1], q[1] - r.y1);
        if (out > -EPS && out <= SNAP && seq.length >= 2) {
          seq = seq.map((x) => x.slice());
          const horiz = Math.abs(seq[0][1] - seq[1][1]) < EPS;
          if (horiz) {
            const y = Math.max(r.y0 + PORT_IN, Math.min(r.y1 - PORT_IN, q[1]));
            seq[0][1] = seq[1][1] = y;
            seq[0][0] = Math.max(r.x0 + 1, Math.min(r.x1 - 1, seq[0][0]));
          } else {
            const x = Math.max(r.x0 + PORT_IN, Math.min(r.x1 - PORT_IN, q[0]));
            seq[0][0] = seq[1][0] = x;
            seq[0][1] = Math.max(r.y0 + 1, Math.min(r.y1 - 1, seq[0][1]));
          }
        }
        if (inBox(seq[0], r)) {
          const i = seq.findIndex((x) => !inBox(x, r));
          if (i < 0) return { why: "path inside its block" };
          const q0 = seq[i - 1], q1 = seq[i];
          const e = Math.abs(q0[1] - q1[1]) < EPS ? [q1[0] > q0[0] ? r.x1 : r.x0, q0[1]] : [q0[0], q1[1] > q0[1] ? r.y1 : r.y0];
          got = [e, ...seq.slice(i)];
        } else {
          const q2 = seq[0], dx = Math.max(r.x0 - q2[0], q2[0] - r.x1, 0), dy = Math.max(r.y0 - q2[1], q2[1] - r.y1, 0);
          const side = dy > dx ? (q2[1] < r.y0 ? "u" : "d") : q2[0] < r.x0 ? "l" : "r";
          const e = portPoint(centre, [side, AXIS_H[side] ? q2[1] - centre[1] : q2[0] - centre[0]], id);
          got = [e, AXIS_H[side] ? [q2[0], e[1]] : [e[0], q2[1]], ...seq];
        }
        if (got.length >= 3) {
          const [e, f] = got, len = segLen(e, f);
          const inner = got.length >= 4 || !(end === "a" ? pb : pa);
          if (len < MIN_STUB && inner && MIN_STUB + 2 - len <= 24) {
            const side = endOf(centre, e, id)[0], [ox, oy] = OUT[side], d = MIN_STUB + 2 - len;
            got = got.map((x) => x.slice());
            if (ox) { got[1][0] += ox * d; got[2][0] += ox * d; } else { got[1][1] += oy * d; got[2][1] += oy * d; }
          }
        }
        const g2 = normPath(end === "a" ? got : got.slice().reverse(), JOG);
        if (!g2) return { why: "diagonal segment" };
        g = g2;
        p = pathPoints(g.a, g.b, g.h, g.c);
        ends[end] = endOf(centre, end === "a" ? p[0] : p[p.length - 1], id);
      }
      const ta = p[0], tb = p[p.length - 1];
      const stubOnly = (pp) => { const n = pp.length; const ok = (a, b, s) => (b[0] - a[0]) * OUT[s][0] + (b[1] - a[1]) * OUT[s][1] >= MIN_STUB - FIT_TOL; return (!ends.a || ok(pp[0], pp[1], ends.a[0])) && (!ends.b || ok(pp[n - 1], pp[n - 2], ends.b[0])); };
      if (!stubOnly(p)) return { why: "port stub too short", a: ends.a, b: ends.b };
      if (crossings(p, boxes)) return { why: "crosses a block", a: ends.a, b: ends.b };
      if ((ends.a && AXIS_H[ends.a[0]] !== !!g.h) || (ends.b && AXIS_H[ends.b[0]] !== lastHoriz(g))) return { why: "port axis", a: ends.a, b: ends.b };
      return { a: ends.a || null, b: ends.b || null, h: g.h, c: g.c, ta, tb };
    }
    /** Ends on one side of a block keep PORT apart, in their order, about where they wanted to be. */
    function spreadPorts(lay, fs) {
      const by = {}, fixed = {};
      fs.streams.forEach((s) => {
        const g = lay.streams[s.name];
        if (!g) return;
        // (an end on its nozzle stays where it is: the others keep PORT from it)
        [[s.from, "a"], [s.to, "b"]].forEach(([blk, k]) => {
          if (!blk || !g[k]) return;
          const m = pinOfEnd(s.name, k) ? fixed : by;
          (m[blk + "|" + g[k][0]] = m[blk + "|" + g[k][0]] || []).push({ g, k });
        });
      });
      Object.entries(by).forEach(([key, list]) => {
        const side = key.split("|").pop(), blk = key.slice(0, key.length - 2), d = dimOf("B:" + blk);
        const lim = (AXIS_H[side] ? BH : BW) / 2 - PORT_IN, [lo, hi] = d ? d.wall[side] : [-lim, lim];
        if (fixed[key]) {                         // (the icon view: about the nozzles in use there)
          const all = list.map((o) => ({ o, v: o.g[o.k][1], fix: false })).concat(fixed[key].map((o) => ({ o, v: o.g[o.k][1], fix: true })));
          all.sort((p, q) => p.v - q.v);
          const got = isotonic(all.map((x) => x.v), all.map((_, i) => (i ? PORT : 0)), all.map((x) => (x.fix ? 1e6 : 1)));
          const fin = spaced(all.map((x, i) => (x.fix ? x.v : r1(Math.max(lo, Math.min(hi, got[i]))))), all.map((x) => x.fix), lo, hi);
          all.forEach((x, i) => { if (!x.fix) x.o.g[x.o.k] = [side, fin[i]]; });
          return;
        }
        if (list.length < 2) return;
        list.sort((p, q) => p.g[p.k][1] - q.g[q.k][1]);
        const want = list.map((o) => o.g[o.k][1]);
        const got = want.slice();
        for (let i = 1; i < got.length; i++) got[i] = Math.max(got[i], got[i - 1] + PORT);
        const shiftBy = (want.reduce((a, b) => a + b, 0) - got.reduce((a, b) => a + b, 0)) / got.length;
        let fin = got.map((v) => v + shiftBy);
        if (fin[fin.length - 1] - fin[0] > hi - lo) fin = fin.map((_, i) => lo + ((hi - lo) * i) / (fin.length - 1));
        else { const m = Math.max(0, lo - fin[0]) - Math.max(0, fin[fin.length - 1] - hi); fin = fin.map((v) => v + m); }
        list.forEach((o, i) => { o.g[o.k] = [side, r1(fin[i])]; });
      });
    }
    /** Feeds and products keep 22 units apart up and down where their names would meet. */
    function spreadTerminals(lay) {
      const ids = Object.keys(lay.nodes).filter((k) => k[0] !== "B").sort((a, b) => lay.nodes[a][1] - lay.nodes[b][1]);
      for (let i = 1; i < ids.length; i++) for (let j = 0; j < i; j++) {
        const p = lay.nodes[ids[j]], q = lay.nodes[ids[i]];
        if (Math.abs(p[0] - q[0]) < 90 && q[1] - p[1] < 22) q[1] = p[1] + 22;
      }
    }
    const termEnds = (s) => [[!s.from, "F:" + s.name, true], [!s.to, "P:" + s.name, false]];
    function pointsOf(lay, s) {
      const g = lay.streams[s.name];
      const pa = s.from ? portPoint(lay.nodes["B:" + s.from], g.a, "B:" + s.from) : lay.nodes["F:" + s.name];
      const pb = s.to ? portPoint(lay.nodes["B:" + s.to], g.b, "B:" + s.to) : lay.nodes["P:" + s.name];
      return pathPoints(pa, pb, g.h, g.c);
    }
    /** A feed or product whose path steps aside just after it (under 8 units) moves by that
     *  step, so its line runs straight. */
    function straightenTerminals(lay, fs) {
      fs.streams.forEach((s) => {
        const g = lay.streams[s.name];
        if (!g) return;
        termEnds(s).forEach(([term, id, first]) => {
          if (!term || !lay.nodes[id]) return;
          let pts = pointsOf(lay, s);
          if (!first) pts = pts.reverse();
          if (pts.length < 4) return;
          const j = pts[2], i = pts[1], dx = j[0] - i[0], dy = j[1] - i[1];
          if (Math.abs(dx) + Math.abs(dy) >= 8) return;
          const t = lay.nodes[id];
          // (the icon view: not where its name would meet another feed's or product's, as on a
          // mixer's two nozzles close together: the line keeps its step there)
          if (GEO && Object.keys(lay.nodes).some((k) => k !== id && k[0] !== "B" && Math.abs(lay.nodes[k][0] - t[0] - dx) < 90 && Math.abs(lay.nodes[k][1] - t[1] - dy) < 16)) return;
          t[0] += dx; t[1] += dy;
          pts[0] = t.slice(); pts[1] = [pts[1][0] + dx, pts[1][1] + dy];
          const n = normPath(first ? pts : pts.reverse(), 0.5);
          if (n) { g.h = n.h; g.c = n.c; }
        });
      });
    }
    /** A feed or product closer than TERM_MIN to its line's first bend moves out along it. */
    function lengthenTerminals(lay, fs) {
      fs.streams.forEach((s) => {
        const g = lay.streams[s.name];
        if (!g) return;
        termEnds(s).forEach(([term, id, first]) => {
          if (!term || !lay.nodes[id]) return;
          let pts = pointsOf(lay, s);
          if (!first) pts = pts.reverse();
          const L = segLen(pts[0], pts[1]);
          if (L >= TERM_MIN || L <= 0) return;
          const t = lay.nodes[id], d = TERM_MIN - L;
          t[0] += ((pts[0][0] - pts[1][0]) * d) / L;
          t[1] += ((pts[0][1] - pts[1][1]) * d) / L;
        });
      });
    }
    /** Blocks and terminals with no place (new since the arrangement was made, or with no place
     *  of their own in Aspen): between a placed source and a placed target where there is room
     *  (a block put into a line), else beside a placed neighbour (right of its source, else left
     *  of its target) at the first free height; with none, in a row under the drawing. Terminals
     *  beside their block, clear of the others. */
    function placeMissing(lay, fs) {
      // (a block's half sizes: its box, or its frame in the icon view)
      const hw = (id) => (dimOf(id) ? GEO.node[id].hw : BW / 2), hh = (id) => (dimOf(id) ? GEO.node[id].hh : BH / 2);
      const pos = lay.nodes, taken = () => Object.keys(pos).filter((k) => k[0] === "B" && pos[k]).map((k) => boxAt(pos[k], k));
      const terms = () => Object.keys(pos).filter((k) => k[0] !== "B" && pos[k]).map((k) => pos[k]);
      const free = (p, id) => taken().every((r) => p[0] + hw(id) + 20 <= r.x0 || p[0] - hw(id) - 20 >= r.x1 || p[1] + hh(id) + 16 <= r.y0 || p[1] - hh(id) - 16 >= r.y1)
        && terms().every((t) => Math.abs(t[0] - p[0]) > hw(id) + 30 || Math.abs(t[1] - p[1]) > hh(id) + 20);
      const spot = (p, id) => { for (let i = 0; i < 40; i++) { const q = [p[0], p[1] + (i % 2 ? -1 : 1) * Math.ceil(i / 2) * 80]; if (free(q, id)) return q; } return p; };
      // (a terminal: clear of the other terminals and of the blocks, up or down from where it goes)
      const tfree = (p) => terms().every((t) => Math.abs(t[0] - p[0]) > 60 || Math.abs(t[1] - p[1]) > 30)
        && taken().every((r) => p[0] + 30 <= r.x0 || p[0] - 30 >= r.x1 || p[1] + 20 <= r.y0 || p[1] - 20 >= r.y1);
      const tspot = (p) => { for (let i = 0; i < 20; i++) { const q = [p[0], p[1] + (i % 2 ? -1 : 1) * Math.ceil(i / 2) * 40]; if (tfree(q)) return q; } return p; };
      let row = null;
      fs.blocks.forEach((b) => {
        const id = "B:" + b.name;
        if (pos[id]) return;
        const src = fs.streams.find((s) => s.to === b.name && s.from && pos["B:" + s.from]);
        const dst = fs.streams.find((s) => s.from === b.name && s.to && pos["B:" + s.to]);
        // (put into a line between two placed blocks: between them, on the target's height or the source's)
        const a = src && pos["B:" + src.from], z = dst && pos["B:" + dst.to];
        const mid = a && z && z[0] - a[0] > 0 ? (a[0] + hw("B:" + src.from) + z[0] - hw("B:" + dst.to)) / 2 : null;
        const among = mid != null ? [[mid, z[1]], [mid, a[1]]].find((q) => free(q, id)) : null;
        if (among) pos[id] = among;
        else if (src) pos[id] = spot([pos["B:" + src.from][0] + hw("B:" + src.from) + hw(id) + 90, pos["B:" + src.from][1]], id);
        else if (dst) pos[id] = spot([pos["B:" + dst.to][0] - hw("B:" + dst.to) - hw(id) - 90, pos["B:" + dst.to][1]], id);
        else {
          const all = taken();
          if (!row) row = [all.length ? Math.min(...all.map((r) => r.x0)) + hw(id) : PAD + hw(id), all.length ? Math.max(...all.map((r) => r.y1)) + 120 : PAD + hh(id)];
          pos[id] = spot(row.slice(), id);
          row[0] += 2 * hw(id) + 70;
        }
      });
      fs.streams.forEach((s) => {
        if (!s.from && !pos["F:" + s.name] && s.to && pos["B:" + s.to]) pos["F:" + s.name] = tspot([pos["B:" + s.to][0] - hw("B:" + s.to) - 90, pos["B:" + s.to][1]]);
        if (!s.to && !pos["P:" + s.name] && s.from && pos["B:" + s.from]) pos["P:" + s.name] = tspot([pos["B:" + s.from][0] + hw("B:" + s.from) + 90, pos["B:" + s.from][1]]);
        if (!s.from && !pos["F:" + s.name]) pos["F:" + s.name] = [PAD, PAD];
        if (!s.to && !pos["P:" + s.name]) pos["P:" + s.name] = [PAD + 200, PAD];
      });
    }
    /** Move everything so the drawing (boxes, circles and every path point) starts PAD from
     *  the origin; numbers at 0.1 (what is stored). */
    function shift(lay, fs) {
      const paths = [];
      fs.streams.forEach((s) => { if (lay.streams[s.name]) paths.push(pointsOf(lay, s)); });
      const e = extent(lay.nodes, paths);
      const dx = PAD - e.x0, dy = PAD - e.y0;
      Object.values(lay.nodes).forEach((p) => { p[0] = r1(p[0] + dx); p[1] = r1(p[1] + dy); });
      Object.values(lay.streams).forEach((g) => {
        let horiz = !!g.h;
        g.c = g.c.map((k) => { horiz = !horiz; return r1(k + (horiz ? dy : dx)); });
      });
    }

    /** An automatic drawing (place(): its nodes, pos, edges and each edge's raw points before
     *  roundPath merged them) as an explicit layout {nodes, streams}. A path that does not
     *  read back is routed afresh (redo lists them). */
    function explicitOfAuto(lay) {
      const nodes = {}, streams = {}, redo = [];
      lay.nodes.forEach((n, k) => { if (n.kind !== "dummy" && lay.pos[k]) nodes[k] = [r1(lay.pos[k].x), r1(lay.pos[k].y)]; });
      const boxes = Object.keys(nodes).filter((k) => k[0] === "B").map((k) => boxAt(nodes[k], k));
      lay.edges.forEach((e, i) => {
        const pts = ((lay.geo[i] && lay.geo[i].raw) || []).map((q) => [q.x, q.y]);
        const ta = lay.nodes.get(e.a).kind !== "block", tb = lay.nodes.get(e.b).kind !== "block";
        let ex = null;
        if (pts.length >= 2) {
          if (ta) pts[0] = nodes[e.a].slice();           // the line starts at the circle's rim: its centre
          if (tb) pts[pts.length - 1] = nodes[e.b].slice();
          const g = normPath(pts, 0.5, AXIS_TOL);
          if (g) {
            ex = { n: [e.a, e.b], a: ta ? null : endOf(nodes[e.a], g.a, e.a), b: tb ? null : endOf(nodes[e.b], g.b, e.b), h: g.h, c: g.c.map(r1) };
            if (GEO) ex = Object.assign(withPins(ex, e.name), { n: ex.n });
            if (!keeps(ex, nodes[e.a], nodes[e.b], ex.n)) ex = null;
          }
        }
        if (!ex) {
          redo.push(e.name);
          const g0 = { a: ta ? null : startEnd(e.name, "a", e.a, ["r", 0]), b: tb ? null : startEnd(e.name, "b", e.b, ["l", 0]), h: 1, c: [] };
          const r = fit(g0, nodes[e.a], nodes[e.b], boxes, true, true, null, null, { n: [e.a, e.b], s: e.name });
          ex = { n: [e.a, e.b], a: r.a, b: r.b, h: r.h, c: r.c };
        }
        streams[e.name] = ex;
      });
      return { nodes, streams, redo };
    }

    return { PORT_IN, MIN_STUB, TERM_R, TERM_MIN, OUT, AXIS_H, r1, boxAt, portPoint, endPoint, endOf, rawSegments, pathPoints,
             drawPoints, leadsOf, withPins, keeps, fit, extent, lastHoriz, crossings, wider, fromAspen, placeMissing, explicitOfAuto,
             stretch, through, untangle };
  })();

  /** The flowsheet as fromAspen and placeMissing read it: its blocks (a stream's end names one
   *  not listed too, as layout() does) and its streams' ends. */
  function fsOf(fs) {
    const seen = new Set((fs.blocks || []).map((b) => b.name)), blocks = (fs.blocks || []).map((b) => ({ name: b.name, type: b.type }));
    const streams = (fs.streams || []).map((s) => ({ name: s.name, from: s.from || null, to: s.to || null, from_port: s.from_port, to_port: s.to_port }));
    streams.forEach((s) => [s.from, s.to].forEach((n) => { if (n && !seen.has(n)) { seen.add(n); blocks.push({ name: n }); } }));
    return { blocks, streams };
  }
  /** Aspen's drawing of a flowsheet as an explicit layout: fromAspen, each stream carrying the
   *  node ids at its ends (n). view: "boxes" for the box view, else the icon view's frames and
   *  nozzles. */
  function explicitFromAspen(imp, fs, view) {
    const f = fsOf(fs), prev = GEO;
    GEO = view !== "boxes" && ICONS() ? geoOf(f) : null;
    let lay;
    try { lay = EX.fromAspen(imp, f); } finally { GEO = prev; }
    f.streams.forEach((s) => {
      const g = lay.streams[s.name];
      if (g) g.n = [s.from ? "B:" + s.from : "F:" + s.name, s.to ? "B:" + s.to : "P:" + s.name];
    });
    return lay;
  }
  FS.explicitFromAspen = explicitFromAspen;
  const endOk = (e, term) => (term ? e === null : Array.isArray(e) && e.length === 2 && "lrud".includes(e[0]) && e[0].length === 1 && num(e[1]));
  /** Which side of a terminal its name goes: away from its line ("l": left, "r": right). The
   *  line leaves t toward q; up or down, a feed's name goes left, a product's right. */
  function termSide(t, q, feed) {
    const dx = q[0] - t[0], dy = q[1] - t[1];
    if (Math.abs(dx) >= Math.abs(dy) && Math.abs(dx) > 0.01) return dx > 0 ? "l" : "r";
    return feed ? "l" : "r";
  }

  /** Blocks of an explicit arrangement (nodes, centres by id: moved in place) that lie over
   *  each other move apart (EX.stretch: room inserted along an axis, everything beyond it moving
   *  on), feeds and products with them: 10 units between frames in the icon view; in the box
   *  view only boxes that overlap. The insertions, or null when none was needed (the usual
   *  case: an arrangement drawn in the view it was made in). */
  function spread(nodes) {
    const ids = Object.keys(nodes).filter((k) => k[0] === "B"), P = ids.map((k) => nodes[k].slice());
    const room = GEO ? 10 : 0, half = (k) => (dimOf(k) ? [GEO.node[k].hw, GEO.node[k].hh] : [BW / 2, BH / 2]);
    const ins = EX.stretch(P, (i, j) => { const a = half(ids[i]), b = half(ids[j]); return [a[0] + b[0] + room, a[1] + b[1] + room]; });
    if (!ins.x.length && !ins.y.length) return null;
    Object.keys(nodes).forEach((k) => { nodes[k] = [EX.r1(EX.through(nodes[k][0], ins.x)), EX.r1(EX.through(nodes[k][1], ins.y))]; });
    return ins;
  }
  /** Each block's frame in the icon view, {id: {hw, hh, key, box, flip}} (box: its symbol's ink
   *  about its centre; the regression checks read it), else null. */
  function shapeOf(abs) {
    if (!GEO) return null;
    const out = {};
    abs.nodes.forEach((n, k) => { const d = n.kind === "block" && GEO.node[k]; if (d) out[k] = { hw: d.hw, hh: d.hh, key: d.key, box: Object.assign({}, d.box), flip: d.flip }; });
    return out;
  }
  /** The icon view's block names, outside their symbols: under the frame, centred; else beside
   *  the lines that leave its bottom; else right of it, left of it, over it; the first that lies
   *  clear of other blocks, every stream's line and the names placed before; under it when none
   *  is. {id: {x, y (the baseline), anchor, text, side, box}}. */
  function placeNames(nodes, pos, geo) {
    const out = {}, taken = [], blocks = [], segs = [];
    const ov = (a, b) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
    nodes.forEach((n, k) => {
      const p = pos[k], d = n.kind === "block" && dimOf(k);
      if (d && p) blocks.push({ k, x0: p.x - d.hw, y0: p.y - d.hh, x1: p.x + d.hw, y1: p.y + d.hh });
    });
    geo.forEach((g) => {
      for (let j = 1; j < g.pts.length; j++) {
        const a = g.pts[j - 1], b = g.pts[j];
        segs.push({ x0: Math.min(a.x, b.x) - 1.5, y0: Math.min(a.y, b.y) - 1.5, x1: Math.max(a.x, b.x) + 1.5, y1: Math.max(a.y, b.y) + 1.5 });
      }
    });
    const clear = (b, k) => !blocks.some((r) => r.k !== k && ov(b, r)) && !segs.some((s) => ov(b, s)) && !taken.some((t) => ov(b, t));
    blocks.forEach(({ k }) => {
      const d = GEO.node[k], p = pos[k], w = d.nameW, ib = d.box;
      // (each clear of the state outline, 5 beyond the symbol's ink: a picked or failed block's
      // outline never runs through its name; as far from every symbol)
      const under = (cx) => ({ side: "d", x: cx, y: p.y + ib.y1 + 17, anchor: "middle", box: { x0: cx - w / 2 - 2, y0: p.y + ib.y1 + 5, x1: cx + w / 2 + 2, y1: p.y + ib.y1 + 21 } });
      const cands = [under(p.x)];
      // beside each upright line under the frame, nearest the middle first
      const band = cands[0].box, xs = [];
      segs.forEach((sg) => { if (sg.y0 < band.y1 && sg.y1 > band.y0 && sg.x1 - sg.x0 < 4 && Math.abs((sg.x0 + sg.x1) / 2 - p.x) < d.hw + w) xs.push(sg.x1 + 4 + w / 2, sg.x0 - 4 - w / 2); });
      xs.sort((a, b) => Math.abs(a - p.x) - Math.abs(b - p.x)).forEach((x) => cands.push(under(x)));
      cands.push({ side: "r", x: p.x + ib.x1 + 9, y: p.y + 4.5, anchor: "start", box: { x0: p.x + ib.x1 + 7, y0: p.y - 8, x1: p.x + ib.x1 + 11 + w, y1: p.y + 8 } });
      cands.push({ side: "l", x: p.x + ib.x0 - 9, y: p.y + 4.5, anchor: "end", box: { x0: p.x + ib.x0 - 11 - w, y0: p.y - 8, x1: p.x + ib.x0 - 7, y1: p.y + 8 } });
      cands.push({ side: "u", x: p.x, y: p.y + ib.y0 - 9, anchor: "middle", box: { x0: p.x - w / 2 - 2, y0: p.y + ib.y0 - 21, x1: p.x + w / 2 + 2, y1: p.y + ib.y0 - 5 } });
      const got = cands.find((c) => clear(c.box, k)) || cands[0];
      taken.push(got.box);
      out[k] = Object.assign(got, { text: d.text });
    });
    return out;
  }

  /** The blocks an explicit arrangement's streams (by name, as stored: {a, b} each) have drawn
   *  mirrored (a Set of node ids), for one kept without saying (a custom arrangement keeps only
   *  nodes and streams): each block the way more of its ends lie on the nozzles that way puts
   *  them, else on the sides its inlets and outlets take that way (left in, right out; mirrored
   *  right in, left out). An arrangement made in the icon view comes back as it was drawn. */
  function flipsOf(fs, streams, key) {
    const score = {}, all = new Set(Object.keys(GEO.node));
    [false, true].forEach((f, w) => {
      setFlips(GEO, f ? all : new Set());
      assignEnds(GEO, fs, key);
      (fs.streams || []).forEach((s) => {
        const g = streams[s.name];
        if (!g) return;
        [["a", s.from, false], ["b", s.to, true]].forEach(([k, blk, inlet]) => {
          const e = g[k], at = endGeo(s.name, k);
          if (!blk || !Array.isArray(e)) return;
          const v = (score["B:" + blk] = score["B:" + blk] || [0, 0]);
          if (at && at.pin && at.pin[0] === e[0] && Math.abs(at.pin[1] - e[1]) < 0.15) v[w] += 10;
          else if (e[0] === (inlet !== f ? "l" : "r")) v[w] += 1;
        });
      });
    });
    return new Set(Object.keys(score).filter((id) => score[id][1] > score[id][0]));
  }
  /** Coordinates and stream routes for an explicit arrangement src ({nodes, streams}: a
   *  custom one as stored, or fromAspen's): each node where src has it (placeMissing places
   *  those it has not), each stream as src has it where it still reads between its ends (else
   *  routed again); the labels placed (B.5). Returns what place() returns, plus ex: the
   *  geometry drawn, as an explicit layout (a drag starts from it), x0, y0 (where the drawing
   *  begins; it may lie left of or above the origin once things were moved) and rerouted; in
   *  the icon view also names (placeNames), shape (each block's frame) and ends (each stream's,
   *  assignEnds). */
  function placeExplicit(abs, src, vals) {
    const N = (k) => abs.nodes.get(k);
    const edges = abs.edges.map(({ name, a, b, back }) => ({ name, a, b, back }));
    const nodes = {};
    abs.nodes.forEach((n, k) => {
      const p = src.nodes && src.nodes[k];
      if (n.kind !== "dummy" && Array.isArray(p) && num(p[0]) && num(p[1])) nodes[k] = [p[0], p[1]];
    });
    const f = { blocks: [...abs.nodes.values()].filter((n) => n.kind === "block").map((n) => ({ name: n.name })),
                streams: edges.map((e) => ({ name: e.name, from: N(e.a).kind === "block" ? N(e.a).name : null, to: N(e.b).kind === "block" ? N(e.b).name : null })) };
    const before = new Set(Object.keys(nodes));
    EX.placeMissing({ nodes, streams: {} }, f);
    Object.keys(nodes).forEach((k) => { if (!before.has(k)) nodes[k] = [EX.r1(nodes[k][0]), EX.r1(nodes[k][1])]; });
    // blocks that would lie over each other (an arrangement made in the other view: the boxes are
    // larger than the symbols) move apart, the rest of the drawing with them; none do otherwise
    const ins = spread(nodes);
    const moved = (own) => {
      if (!ins) return own;
      let horiz = !!own.h;
      return Object.assign({}, own, { c: own.c.map((k) => { horiz = !horiz; return EX.r1(EX.through(k, horiz ? ins.y : ins.x)); }) });
    };
    // the icon view: each stream's nozzles, in the order of where its route comes to the block
    // from (its last bend before it; its other end where it has no route kept); the blocks
    // drawn mirrored as src says, else as its ends say (flipsOf)
    const valid = (e, own) => !!own && Array.isArray(own.n) && own.n[0] === e.a && own.n[1] === e.b && endOk(own.a, N(e.a).kind !== "block")
      && endOk(own.b, N(e.b).kind !== "block") && (own.h === 0 || own.h === 1) && Array.isArray(own.c) && own.c.length <= 32 && own.c.every(num);
    if (GEO) {
      const by = new Map(edges.map((e) => [e.name, e]));
      const key = (sn, k, axis) => {
        const e = by.get(sn), own = e && src.streams && src.streams[sn], i = axis === "x" ? 0 : 1;
        if (!e) return 0;
        if (valid(e, own) && nodes[e.a] && nodes[e.b]) {
          const g = moved(own), P = EX.pathPoints(EX.endPoint(nodes[e.a], g.a, e.a), EX.endPoint(nodes[e.b], g.b, e.b), g.h, g.c), n = P.length;
          return P[k === "a" ? Math.min(n - 1, 2) : Math.max(0, n - 3)][i];
        }
        const o = nodes[k === "a" ? e.b : e.a];
        return o ? o[i] : 0;
      };
      setFlips(GEO, Array.isArray(src.flip) ? new Set(src.flip) : flipsOf(abs.fs, src.streams || {}, key));
      assignEnds(GEO, abs.fs, key);
    }
    const boxes = Object.keys(nodes).filter((k) => k[0] === "B").map((k) => EX.boxAt(nodes[k], k));
    const streams = {}, geo = [], tside = {}, rerouted = [], drawn = {};
    edges.forEach((e) => {
      const ta = N(e.a).kind !== "block", tb = N(e.b).kind !== "block";
      const own = src.streams && src.streams[e.name], ok = valid(e, own);
      const g = ok ? moved(own) : { a: ta ? null : startEnd(e.name, "a", e.a, ["r", 0]), b: tb ? null : startEnd(e.name, "b", e.b, ["l", 0]), h: 1, c: [] };
      const r = EX.fit(g, nodes[e.a], nodes[e.b], boxes, !ok, true, null, null, { n: [e.a, e.b], s: e.name });
      if (!r.kept) rerouted.push(e.name);
      streams[e.name] = { n: [e.a, e.b], a: r.a ? [r.a[0], r.a[1]] : null, b: r.b ? [r.b[0], r.b[1]] : null, h: r.h, c: r.c.slice() };
      drawn[e.name] = r.pts;
    });
    // (the icon view: a line along another's is fitted again, clear of the others)
    if (GEO) EX.untangle({ nodes, streams }, f, boxes).forEach((n) => { drawn[n] = null; if (!rerouted.includes(n)) rerouted.push(n); });
    // two ends at one spot of a block's side (an arrangement made in the other view: its ports
    // clamped onto the smaller sides, or one side the router took anew for both) move PORT
    // apart, an end on its nozzle staying, and their lines are fitted again; none move otherwise
    const at = {}, redo = new Set();
    edges.forEach((e) => [["a", e.a], ["b", e.b]].forEach(([k, id]) => {
      const s = streams[e.name];
      if (id[0] === "B" && s[k]) (at[`${id}|${s[k][0]}`] = at[`${id}|${s[k][0]}`] || []).push({ e, k });
    }));
    Object.entries(at).forEach(([key, list]) => {
      if (list.length < 2) return;
      const id = key.slice(0, -2), side = key.slice(-1), d = dimOf(id), half = (EX.AXIS_H[side] ? BH : BW) / 2 - EX.PORT_IN;
      list.sort((p, q) => streams[p.e.name][p.k][1] - streams[q.e.name][q.k][1]);
      const v = list.map((o) => streams[o.e.name][o.k][1]);
      const got = spaced(v, list.map((o) => !!pinOfEnd(o.e.name, o.k)), d ? d.wall[side][0] : -half, d ? d.wall[side][1] : half);
      list.forEach((o, i) => { if (got[i] !== v[i]) { streams[o.e.name][o.k] = [side, EX.r1(got[i])]; redo.add(o.e); } });
    });
    redo.forEach((e) => {
      const s = streams[e.name], r = EX.fit(s, nodes[e.a], nodes[e.b], boxes, false, false, null, null, { n: [e.a, e.b], s: e.name });
      streams[e.name] = { n: s.n, a: r.a ? [r.a[0], r.a[1]] : null, b: r.b ? [r.b[0], r.b[1]] : null, h: r.h, c: r.c.slice() };
      drawn[e.name] = r.pts;
      if (!rerouted.includes(e.name)) rerouted.push(e.name);
    });
    edges.forEach((e) => {
      const ta = N(e.a).kind !== "block", tb = N(e.b).kind !== "block", s = streams[e.name];
      const pts = drawn[e.name] || EX.pathPoints(EX.endPoint(nodes[e.a], s.a, e.a), EX.endPoint(nodes[e.b], s.b, e.b), s.h, s.c);
      const n = pts.length, leads = EX.leadsOf(e.name, [e.a, e.b], nodes[e.a], nodes[e.b], s.a, s.b);
      geo.push(Object.assign(roundPath(EX.drawPoints(pts, ta, tb, leads).map(([x, y]) => ({ x, y }))), { raw: pts }));
      if (ta) tside[e.a] = termSide(pts[0], pts[1], true);
      if (tb) tside[e.b] = termSide(pts[n - 1], pts[n - 2], false);
    });
    // a recycle is dashed where this drawing runs it back: a stream in a loop of blocks whose
    // end lies left of its start, by more than half a box (the automatic layout's choice of
    // recycles says nothing here)
    const loops = inLoops(edges.filter((e) => N(e.a).kind === "block" && N(e.b).kind === "block"));
    edges.forEach((e) => { e.back = loops.has(e.name) && nodes[e.b][0] < nodes[e.a][0] - (dimOf(e.a) ? GEO.node[e.a].hw : BW / 2); });
    const pos = {};
    Object.keys(nodes).forEach((k) => { pos[k] = { x: nodes[k][0], y: nodes[k][1] }; });
    const e = EX.extent(nodes, geo.map((g) => g.raw));
    const names = GEO ? placeNames(abs.nodes, pos, geo) : null;
    const tval = {}, labels = placeLabels(abs.nodes, edges, pos, geo, vals, tside, true, tval, names);
    return Object.assign({}, abs, { edges, pos, geo: labels, width: e.x1 + PAD, height: e.y1 + PAD, x0: e.x0 - PAD, y0: e.y0 - PAD,
                                    tside, tval, explicit: true, ex: { nodes, streams }, rerouted, names, shape: shapeOf(abs), ends: GEO ? GEO.ends : null });
  }

  /** Coordinates and stream routes for a layering, left to right. vals: each stream's value
   *  lines by name while the Values layer shows (the gaps widen and they are placed with the
   *  labels), else null. */
  /** The names of the edges ({name, a, b}) that lie on a loop: their start is reached from their end. */
  function inLoops(edges) {
    const adj = new Map(), reach = new Map();
    edges.forEach((e) => { if (!adj.has(e.a)) adj.set(e.a, []); adj.get(e.a).push(e.b); });
    const from = (k) => {
      if (!reach.has(k)) {
        const seen = new Set([k]), todo = [k];
        while (todo.length) (adj.get(todo.pop()) || []).forEach((n) => { if (!seen.has(n)) { seen.add(n); todo.push(n); } });
        reach.set(k, seen);
      }
      return reach.get(k);
    };
    return new Set(edges.filter((e) => from(e.b).has(e.a)).map((e) => e.name));
  }
  function place(abs, vals) {
    VAL = vals || null;
    try { return placeAll(abs, VAL); } finally { VAL = null; }
  }
  /** The icon view's columns: nodes that meet one block on the same side through its nozzles
   *  (a column's products, a mixer's feeds) take their places in the column in the order of
   *  those nozzles, so their lines do not cross (the layering knows no ports). A node that meets
   *  several blocks goes by the one it comes from, where that is a single one (a drum's vapour
   *  product and the heater its liquid goes on to: the vapour's above). A copy of abs. */
  function byPorts(abs) {
    const key = new Map();                       // node -> [[block, where its end meets it, from it]]
    const at = (e, k) => {
      const g = endGeo(e.name, k), d = g && dimOf(k === "a" ? e.a : e.b);
      if (!d) return null;
      if (g.side === "u") return -1e3 + (g.pin ? g.pin[1] : 0);
      if (g.side === "d") return 1e3 + (g.pin ? g.pin[1] : 0);
      return g.pin ? g.pin[1] : (d.wall[g.side][0] + d.wall[g.side][1]) / 2;
    };
    abs.edges.forEach((e) => {
      if (e.back) return;
      [["a", e.a, e.chain[1]], ["b", e.b, e.chain[e.chain.length - 2]]].forEach(([k, blk, nb]) => {
        const v = at(e, k);
        if (v !== null) (key.get(nb) || key.set(nb, []).get(nb)).push([blk, v, k === "a"]);
      });
    });
    const cols = abs.cols.map((col) => {
      const out = col.slice(), groups = new Map();
      col.forEach((k, i) => {
        const ks = key.get(k), from = ks ? ks.filter((x) => x[2]) : [];
        const one = ks && ks.length === 1 ? ks[0] : from.length === 1 ? from[0] : null;
        if (one) (groups.get(one[0]) || groups.set(one[0], []).get(one[0])).push([i, k, one[1]]);
      });
      groups.forEach((list) => {
        if (list.length < 2) return;
        const slots = list.map(([i]) => i), sorted = list.slice().sort((p, q) => p[2] - q[2] || p[0] - q[0]);
        slots.forEach((i, j) => { out[i] = sorted[j][1]; });
      });
      return out;
    });
    return Object.assign({}, abs, { cols });
  }
  function placeAll(abs0, vals) {
    const abs = GEO ? byPorts(abs0) : abs0;
    const { nodes, edges, cols, layer } = abs, N = (k) => nodes.get(k);
    const y = placeY(abs);
    // the icon view: two blocks joined nozzle to nozzle (right to left) whose nozzles came out a
    // little apart (under 8 units) move level, the one downstream where its column lets it; a
    // nozzle at the top or bottom counts at the level its stream turns at (STUB_V beyond the frame)
    if (GEO) {
      const at = (e, k, g) => {
        const id = k === "a" ? e.a : e.b, d = dimOf(id);
        return g.side === "u" ? y.get(id) - d.hh - STUB_V : g.side === "d" ? y.get(id) + d.hh + STUB_V : y.get(id) + g.pin[1];
      };
      edges.forEach((e) => {
        if (e.back || e.chain.length !== 2) return;
        const ga = endGeo(e.name, "a"), gb = endGeo(e.name, "b");
        if (!ga || !gb || !ga.pin || !gb.pin || !"rud".includes(ga.side) || !"lud".includes(gb.side) || (ga.side !== "r" && gb.side !== "l")) return;
        const d = at(e, "a", ga) - at(e, "b", gb);
        if (!d || Math.abs(d) >= 8) return;
        if (Math.abs(d) < 1 || fits(abs, y, e.b, y.get(e.b) + d)) y.set(e.b, y.get(e.b) + d);
        else if (fits(abs, y, e.a, y.get(e.a) - d)) y.set(e.a, y.get(e.a) - d);
      });
    }

    // where each stream leaves and enters a block: level with its other end wherever the
    // block's side reaches, in order and PORT apart; a recycle at the bottom, toward its lane.
    // The icon view: a free end within the body's wall (s: the side, "l" or "r"); an end on a
    // nozzle at the left or right where the nozzle is (pin: its offset); one at the top or
    // bottom (ud) turns off it, below
    const IC = !!GEO;
    const side = (k, s) => {
      if (N(k).kind !== "block") return [y.get(k), y.get(k)];
      const d = IC && dimOf(k);
      if (d) { const w = d.wall[s || "r"]; return [y.get(k) + w[0], y.get(k) + w[1]]; }
      return [y.get(k) - BH / 2 + 8, y.get(k) + BH / 2 - 8];
    };
    const clamp = (v, [lo, hi]) => Math.max(lo, Math.min(hi, v));
    const meet = (u, v) => {                     // the height a hop from u to v can run level at
      const a = side(u, "r"), b = side(v, "l"), lo = Math.max(a[0], b[0]), hi = Math.min(a[1], b[1]);
      return lo <= hi ? clamp((y.get(u) + y.get(v)) / 2, [lo, hi]) : y.get(v);
    };
    const outs = new Map(), ins = new Map();
    const add = (m, k, o) => (m.get(k) || m.set(k, []).get(k)).push(o);
    const geoAt = (e, k) => (IC && N(k === "a" ? e.a : e.b).kind === "block" ? endGeo(e.name, k) : null);
    const pinAt = (g, s) => (g && g.pin && g.side === s ? g.pin[1] : null);
    const udAt = (g) => (g && (g.side === "u" || g.side === "d") ? g : null);
    edges.forEach((e) => {
      const next = e.chain[1], prev = e.chain[e.chain.length - 2];
      // a stream whose other end cannot move (a slot or a terminal) gets its place first
      const firm = (k) => N(k).kind !== "block";
      const ga = geoAt(e, "a"), gb = geoAt(e, "b");
      e.udA = null;
      e.udB = null;
      add(outs, e.a, { e, key: "y1", other: "y2", mate: e.chain.length === 2 && !firm(next),
                       firm: firm(next), want: e.back ? Infinity : meet(e.a, next), pin: pinAt(ga, "r"), ud: udAt(ga), out: true });
      add(ins, e.b, { e, key: "y2", other: "y1", mate: e.chain.length === 2 && !firm(prev),
                      firm: firm(prev), want: e.back ? Infinity : meet(e.b, prev), pin: pinAt(gb, "l"), ud: udAt(gb), out: false });
    });
    const settle = (all, k, s) => {
      const list = IC ? all.filter((o) => !o.ud) : all;
      if (!list.length) return;
      const [lo, hi] = side(k, s);
      if (IC && list.some((o) => o.pin !== null)) {
        // the ends on nozzles stay; the free ones settle PORT apart about them, on the wall
        const at = (o) => (o.pin !== null ? y.get(k) + o.pin : clamp(o.want, [lo, hi]));
        list.sort((a, b) => at(a) - at(b));
        const got = isotonic(list.map(at), list.map((_, i) => (i ? PORT : 0)), list.map((o) => (o.pin !== null ? 1e6 : o.firm ? 8 : 1)));
        const fin = spaced(list.map((o, i) => (o.pin !== null ? y.get(k) + o.pin : clamp(got[i], [lo, hi]))), list.map((o) => o.pin !== null), lo, hi);
        list.forEach((o, i) => { o.e[o.key] = fin[i]; });
        return;
      }
      list.sort((a, b) => a.want - b.want);
      let got = isotonic(list.map((o) => clamp(o.want, [lo, hi])), list.map((_, i) => (i ? PORT : 0)),
        list.map((o) => (o.firm ? 8 : 1)));
      if (got[got.length - 1] - got[0] > hi - lo) {
        got = list.map((_, i) => (list.length > 1 ? lo + ((hi - lo) * i) / (list.length - 1) : (lo + hi) / 2));
      } else {
        const shift = Math.max(0, lo - got[0]) - Math.max(0, got[got.length - 1] - hi);
        got = got.map((v) => v + shift);
      }
      list.forEach((o, i) => { o.e[o.key] = got[i]; });
    };
    // block to block, each end then aims at where the other end landed, until they agree
    // the icon view, first: a stream off a nozzle (or the wall) at the top or bottom runs out from it
    // to a level STUB_V beyond the frame, then on to the right edge, and leaves from there as
    // any other (an inlet the same the other way); several on one side each have their level,
    // PORT apart, the one nearest the edge it heads to innermost, so none crosses another
    if (IC) {
      [outs, ins].forEach((m) => m.forEach((list, k) => {
        const d = dimOf(k);
        if (!d) return;
        ["u", "d"].forEach((s) => {
          const mine = list.filter((o) => o.ud && o.ud.side === s);
          if (!mine.length) return;
          // the free ones about the wall's middle, inlets left of outlets; each set so that the one
          // whose other end lies farther out takes the outer level and does not cross the rest
          // (a top inlet farther right, a top outlet farther left; the bottom the same, mirrored)
          const w = d.wall[s], mid = (w[0] + w[1]) / 2, far = (o) => (s === "u" ? o.want : -o.want);
          const fin = mine.filter((o) => !o.ud.pin && !o.out).sort((a, b) => far(b) - far(a));
          const fout = mine.filter((o) => !o.ud.pin && o.out).sort((a, b) => far(a) - far(b));
          const free = fin.concat(fout);
          free.forEach((o, i) => { o.x = clamp(mid + (i - (free.length - 1) / 2) * PORT, w); });
          mine.forEach((o) => { if (o.ud.pin) o.x = o.ud.pin[1]; });
        });
      }));
      nodes.forEach((n, k) => {
        const d = n.kind === "block" && dimOf(k);
        if (!d) return;
        const mine = [...(outs.get(k) || []), ...(ins.get(k) || [])].filter((o) => o.ud);
        ["u", "d"].forEach((s) => {
          mine.filter((o) => o.ud.side === s).sort((a, b) => (a.out ? d.hw - a.x : a.x + d.hw) - (b.out ? d.hw - b.x : b.x + d.hw))
            .forEach((o, i) => {
              const yv = s === "u" ? y.get(k) - d.hh - STUB_V - i * PORT : y.get(k) + d.hh + STUB_V + i * PORT;
              o.e[o.key] = yv;
              o.e[o.out ? "udA" : "udB"] = { x: o.x, yv, s };
            });
        });
      });
    }
    for (let pass = 0; pass < 4; pass++) {
      if (pass) [...outs.values(), ...ins.values()].flat().forEach((o) => { if (o.mate && !o.e.back) o.want = o.e[o.other]; });
      outs.forEach((l, k) => settle(l, k, "r"));
      ins.forEach((l, k) => settle(l, k, "l"));
    }
    // a feed or product moves level with the side it meets, where its column has room
    edges.forEach((e) => {
      [[e.a, "y1", "y2"], [e.b, "y2", "y1"]].forEach(([t, own, other]) => {
        const kind = N(t).kind;
        // (the icon view: a hair's breadth always, so a line into a nozzle runs straight)
        if ((kind === "feed" || kind === "prod") && e.chain.length === 2 && (fits(abs, y, t, e[other]) || (GEO && Math.abs(y.get(t) - e[other]) < 1))) {
          y.set(t, e[other]);
          e[own] = e[other];
        }
      });
    });

    // a long stream level with neither of its ports moves level with one, where it fits
    edges.forEach((e) => {
      const ds = e.chain.slice(1, -1);
      if (e.back || !ds.length) return;
      const L = y.get(ds[0]);
      if (ds.some((d) => Math.abs(y.get(d) - L) > 0.5) || Math.abs(L - e.y1) < 0.5 || Math.abs(L - e.y2) < 0.5) return;
      const to = [e.y2, e.y1].find((v) => ds.every((d) => fits(abs, y, d, v)));
      if (to !== undefined) ds.forEach((d) => y.set(d, to));
    });

    // the turns: each in a track of its own in the gap it crosses (gap g lies right of
    // column g; -1 is the left margin)
    const L = cols.length, gapTurns = new Map();
    const turn = (g, t) => (gapTurns.get(g) || gapTurns.set(g, []).get(g)).push(t);
    edges.forEach((e) => {
      if (e.back) {
        e.exit = { from: e.y1, to: Infinity };
        e.entry = { from: Infinity, to: e.y2 };
        turn(layer.get(e.a), e.exit);
        turn(layer.get(e.b) - 1, e.entry);
        return;
      }
      e.hops = [];
      for (let i = 1; i < e.chain.length; i++) {
        const u = e.chain[i - 1], v = e.chain[i];
        const h = { u, v, from: i === 1 ? e.y1 : y.get(u), to: i === e.chain.length - 1 ? e.y2 : y.get(v) };
        e.hops.push(h);
        if (Math.abs(h.to - h.from) >= 1) turn(layer.get(u), h);
      }
    });
    // a turn going down from higher up sits further right, one going up from lower down too:
    // then two turns in the same gap do not cross
    gapTurns.forEach((list) => {
      const down = list.filter((t) => t.to > t.from).sort((a, b) => b.from - a.from);
      const up = list.filter((t) => t.to < t.from).sort((a, b) => a.from - b.from);
      const order = down.concat(up);
      // (the icon view: a turn up that starts about where one going down ends, the two lines
      // would run along each other there, reading as one: the turn up goes left of it)
      if (GEO) up.forEach((u) => {
        const i = order.indexOf(u), j = order.findIndex((d) => d.to > d.from && Math.abs(d.to - u.from) < 8);
        if (j >= 0 && j < i) { order.splice(i, 1); order.splice(j, 0, u); }
      });
      order.forEach((t, i) => { t.track = i; });
    });
    const width = (g) => Math.max(g < 0 || g >= L - 1 ? 0 : vals ? GAP + VGAP : GAP, (gapTurns.get(g) || []).length
      ? 2 * STUB + ((gapTurns.get(g).length - 1) * TRACK) : 0);
    // (the icon view: a column as wide as its frames and the names under them)
    const colOf = (n) => (IC && n.kind === "block" && dimOf(n.id) ? Math.max(2 * halfW(n), GEO.node[n.id].nameW + 8) : 2 * halfW(n));
    const colW = cols.map((c) => Math.max(14, ...c.map((k) => colOf(N(k)))));
    const cx = [], gapX = new Map();
    let cursor = PAD + width(-1);
    gapX.set(-1, PAD);
    cols.forEach((c, l) => {
      cx[l] = cursor + colW[l] / 2;
      cursor += colW[l];
      gapX.set(l, cursor);
      cursor += width(l);
    });
    const trackX = (g, t) => {
      const n = gapTurns.get(g).length;
      return gapX.get(g) + width(g) / 2 + (t.track - (n - 1) / 2) * TRACK;
    };
    const pos = {};
    nodes.forEach((n, k) => { pos[k] = { x: cx[layer.get(k)], y: y.get(k) }; });
    const right = (k) => pos[k].x + halfW(N(k)), left = (k) => pos[k].x - halfW(N(k));

    // recycle lanes under the drawing, the shortest nearest
    const bottom = nodes.size ? Math.max(...[...nodes.keys()].map((k) => pos[k].y + halfH(N(k)) + (IC ? roomOf(N(k)).down : 0))) : 0;   // (nothing: no height, not -Infinity)
    const backs = edges.filter((e) => e.back);
    backs.forEach((e) => { e.span = Math.abs(pos[e.a].x - pos[e.b].x); });
    backs.slice().sort((a, b) => a.span - b.span).forEach((e, i) => { e.lane = bottom + 40 + i * LANE; });

    const geo = edges.map((e) => {
      let pts;
      if (e.back) {
        const xo = trackX(layer.get(e.a), e.exit), xi = trackX(layer.get(e.b) - 1, e.entry);
        pts = [{ x: right(e.a), y: e.y1 }, { x: xo, y: e.y1 }, { x: xo, y: e.lane }, { x: xi, y: e.lane },
          { x: xi, y: e.y2 }, { x: left(e.b), y: e.y2 }];
      } else {
        pts = [{ x: right(e.a), y: e.y1 }];
        e.hops.forEach((h) => {
          if (h.track != null) {
            const x = trackX(layer.get(h.u), h);
            pts.push({ x, y: h.from }, { x, y: h.to });
          }
          pts.push({ x: left(h.v), y: h.to });
        });
      }
      if (!IC) return Object.assign(roundPath(pts), { raw: pts });
      // the icon view: the turns off a top or bottom nozzle; then each block end's lead (the
      // line on from the frame's edge to the nozzle's tip, or to the body's wall)
      const A = e.udA, B = e.udB;
      if (A) { const x = pos[e.a].x + A.x, y0 = pos[e.a].y + (A.s === "u" ? -1 : 1) * halfH(N(e.a)); pts.unshift({ x, y: y0 }, { x, y: A.yv }); }
      if (B) { const x = pos[e.b].x + B.x, y0 = pos[e.b].y + (B.s === "u" ? -1 : 1) * halfH(N(e.b)); pts.push({ x, y: B.yv }, { x, y: y0 }); }
      const blkA = N(e.a).kind === "block", blkB = N(e.b).kind === "block", pa = [pos[e.a].x, pos[e.a].y], pb = [pos[e.b].x, pos[e.b].y];
      const ea = blkA ? (A ? [A.s, A.x] : ["r", pts[0].y - pa[1]]) : null, eb = blkB ? (B ? [B.s, B.x] : ["l", pts[pts.length - 1].y - pb[1]]) : null;
      const leads = EX.leadsOf(e.name, [e.a, e.b], pa, pb, ea, eb);
      const drawn = EX.drawPoints(pts.map((q) => [q.x, q.y]), false, false, leads).map(([x, q]) => ({ x, y: q }));
      return Object.assign(roundPath(drawn), { raw: pts });
    });
    const tside = {};                              // a feed's name left of it, a product's right
    nodes.forEach((n, k) => { if (n.kind === "feed" || n.kind === "prod") tside[k] = n.kind === "feed" ? "l" : "r"; });
    const names = IC ? placeNames(nodes, pos, geo) : null;
    const labels = placeLabels(nodes, edges, pos, geo, vals, tside, false, undefined, names);
    const lanes = backs.length ? Math.max(...backs.map((e) => e.lane)) : bottom;
    return Object.assign({}, abs, { pos, geo: labels, width: cursor + PAD, height: lanes + PAD, x0: 0, y0: 0, tside,
                                    names, shape: shapeOf(abs), ends: GEO ? GEO.ends : null });
  }

  /** Stream labels: {d, lx, ly, vy, vk, anchor, pts, raw} each (lx, ly: the name's anchor
   *  point and baseline; vy: its first value line's baseline; vk: the value lines kept;
   *  anchor: the text-anchor of both). Labels go on level stretches, the first place that
   *  covers no other label, block or stream line (its own but for the stretch it sits on); a
   *  label's value lines go with it: all of them where they fit, else the flow alone, else
   *  none (the stream's hover card has them all). A feed's or product's name and values sit
   *  beside it, on the side tside says (sep made room for them under it). explicit: an
   *  arrangement given explicitly, whose streams may run up and down without a level stretch
   *  that has room: then beside an upright stretch; then the name alone at the middle of any
   *  stretch, clear of blocks and labels; then the nearest free spot about the path's middle
   *  (off its arrowhead); last, over the longest stretch. (Automatic layouts keep the first
   *  rule and its fallback.) An explicit arrangement's feeds and products get their value
   *  lines placed too, before the labels: tval, by node, {vy, vk}. names: the icon view's block
   *  names (placeNames), which the labels keep clear of as of the blocks. */
  function placeLabels(nodes, edges, pos, geo, vals, tside, explicit, tval, names) {
    const N = (k) => nodes.get(k);
    const taken = [];
    const apart = (r, t) => r.x + r.w <= t.x || t.x + t.w <= r.x || r.y + r.h <= t.y || t.y + t.h <= r.y;
    const free = (r) => taken.every((t) => apart(r, t));
    const valW = (ls) => Math.max(0, ...ls.map((l) => lineW(l)));
    // every stretch of every stream, 3 units spare each side, with whose it is (i) and which (j)
    const segs = [];
    geo.forEach((g, i) => {
      for (let j = 1; j < g.pts.length; j++) {
        const a = g.pts[j - 1], b = g.pts[j];
        segs.push({ i, j, x: Math.min(a.x, b.x) - 3, y: Math.min(a.y, b.y) - 3, w: Math.abs(a.x - b.x) + 6, h: Math.abs(a.y - b.y) + 6 });
      }
    });
    const terms = [], blocks = [];
    nodes.forEach((n, k) => {
      const p = pos[k];
      if (n.kind === "block") {
        const d = dimOf(k), hw = d ? d.hw : BW / 2, hh = d ? d.hh : BH / 2;
        blocks.push(d ? { x: p.x - hw, y: p.y - hh, w: 2 * hw, h: 2 * hh } : { x: p.x - BW / 2, y: p.y - BH / 2, w: BW, h: BH });
        // (the icon view: its symbol's ink, so a label may sit in an empty corner of the frame)
        if (d) d.ink.forEach((r) => taken.push({ x: p.x + r.x0, y: p.y + r.y0, w: r.x1 - r.x0, h: r.y1 - r.y0 }));
        else taken.push(blocks[blocks.length - 1]);
        const nm = names && names[k];
        if (nm) taken.push({ x: nm.box.x0, y: nm.box.y0, w: nm.box.x1 - nm.box.x0, h: nm.box.y1 - nm.box.y0 });
      }
      else if (n.kind !== "dummy") {
        const ls = (vals && vals.get(n.name)) || [], w = Math.max(textWidth(n.name), explicit ? 0 : valW(ls)) + 16;
        const own = { x: tside[k] === "l" ? p.x - 7 - w : p.x - 7, y: p.y - 9, w: w + 14, h: 18 + (explicit ? 0 : LINE * ls.length) };
        taken.push(own);
        if (explicit && ls.length) terms.push({ k, p, ls, own });
      }
    });
    // a feed's or product's value lines in an explicit arrangement, where terminals may sit
    // close together (automatic layouts made room under each: sep): under its name, else over
    // it, where they cover no other terminal, block or value lines placed before, with 8 units
    // up and down to spare (so they never read as the lines of the terminal above or below);
    // all of them, else the flow alone, else none (the stream's hover card has them all). Top
    // to bottom, so a stack of terminals reads the same way each time. vy: the first line's
    // baseline, vk: the lines kept (the render draws them: draw)
    terms.sort((a, b) => a.p.y - b.p.y || a.p.x - b.p.x).forEach(({ k, p, ls, own }) => {
      const left = tside[k] === "l", tries = [ls];
      if (ls.length > 1 && ls.some((l) => l.k === "f")) tries.push(ls.filter((l) => l.k === "f"));
      let got = null;
      for (const t of tries) {
        const vw = valW(t), n = t.length, x = left ? p.x - 16 - vw : p.x + 8;
        for (const vy of [p.y + 18, p.y - 10 - LINE * (n - 1)]) {
          const b = { x, y: vy - 9, w: vw + 8, h: LINE * (n - 1) + 12 }, room = { x: b.x - 4, y: b.y - 8, w: b.w + 8, h: b.h + 16 };
          if (taken.every((r) => r === own || apart(room, r))) { got = { vy, vk: t.map((l) => l.k), b }; break; }
        }
        if (got) break;
      }
      if (got) taken.push(got.b);
      tval[k] = got ? { vy: got.vy, vk: got.vk } : { vy: p.y + 18, vk: [] };
    });
    return edges.map((e, i) => {
      const pts = geo[i].pts, nw = textWidth(e.name);
      const terminal = N(e.a).kind === "feed" || N(e.b).kind === "prod";
      const runs = [], ups = [];
      for (let j = 1; j < pts.length; j++) {
        const a = pts[j - 1], b = pts[j];
        if (Math.abs(a.y - b.y) < 0.5) runs.push({ lo: Math.min(a.x, b.x), hi: Math.max(a.x, b.x), y: a.y, j });
        else if ((explicit || GEO) && Math.abs(a.x - b.x) < 0.5) ups.push({ lo: Math.min(a.y, b.y), hi: Math.max(a.y, b.y), x: a.x, j });
      }
      runs.sort((a, b) => (b.hi - b.lo) - (a.hi - a.lo));
      ups.sort((a, b) => (b.hi - b.lo) - (a.hi - a.lo));
      // about a spot q on the line: the name over the line and the value lines under it; else
      // the values over the name; else both under the line. ly: the name's baseline, vy: the
      // first value line's; boxes: what they take (4 units spare each side: text at a small
      // scale is laid out a little wider)
      const nameAt = (q, y) => ({ x: q.x - nw / 2 - 4, y, w: nw + 8, h: 18 });
      const valsAt = (q, vw, y, n) => ({ x: q.x - vw / 2 - 4, y, w: vw + 8, h: 3 + n * LINE });
      const ways = [
        (q, vw, n) => ({ ly: q.y - 6, vy: q.y + 14, boxes: [nameAt(q, q.y - 20)].concat(n ? [valsAt(q, vw, q.y + 2, n)] : []) }),
        (q, vw, n) => (n ? { ly: q.y - 6, vy: q.y - 24 - (n - 1) * LINE, boxes: [nameAt(q, q.y - 20), valsAt(q, vw, q.y - 23 - n * LINE, n)] } : null),
        (q, vw, n) => ({ ly: q.y + 16, vy: q.y + 30, boxes: [nameAt(q, q.y + 2)].concat(n ? [valsAt(q, vw, q.y + 20, n)] : []) }),
      ];
      // a level stretch between blocks close together (explicit arrangements) has no room at its
      // side for value lines as wide as the gap: the name on the line, its value lines over the
      // top edge of the blocks at its height (up), or under their bottom edge; null where no
      // block is at its height there (the ways above cover that)
      const edgeOf = (q, vw, up) => {
        const x0 = q.x - vw / 2 - 4, x1 = q.x + vw / 2 + 4;
        const at = blocks.filter((b) => b.x < x1 && b.x + b.w > x0 && b.y < q.y + 2 && b.y + b.h > q.y - 2);
        return at.length ? (up ? Math.min(...at.map((b) => b.y)) : Math.max(...at.map((b) => b.y + b.h))) : null;
      };
      const past = [true, false].map((up) => (q, vw, n) => {
        const k = n ? edgeOf(q, vw, up) : null;
        if (k === null) return null;
        const y = up ? k - 6 - n * LINE : k + 3;
        return { ly: q.y - 6, vy: y + LINE - 1, boxes: [nameAt(q, q.y - 20), valsAt(q, vw, y, n)] };
      });
      // beside an upright line (explicit arrangements): the name level with spot q, right of
      // the line (dir 1, text-anchor start) or left of it (-1, end), its value lines under it
      const beside = (q, vw, n, dir) => {
        const x = q.x + 8 * dir, ly = q.y + 4, vy = ly + 14, at = (w) => (dir > 0 ? x - 4 : x - w - 4);
        return { x, ly, vy, anchor: dir > 0 ? "start" : "end",
                 boxes: [{ x: at(nw), y: ly - 14, w: nw + 8, h: 18 }].concat(n ? [{ x: at(vw), y: vy - 12, w: vw + 8, h: 3 + n * LINE }] : []) };
      };
      const all = (!terminal && vals && vals.get(e.name)) || [];
      const tries = [all];
      if (all.length > 1 && all.some((l) => l.k === "f")) tries.push(all.filter((l) => l.k === "f"));
      if (all.length) tries.push([]);
      let got = null, kept = [];
      for (const ls of terminal ? [] : tries) {
        // the middle of each stretch, its ends, then its quarters and eighths: the name on the
        // stretch, its values may reach past its ends (clear of blocks, labels and lines all
        // the same); each way of setting them out along every stretch before the next way
        const vw = valW(ls), w = Math.max(nw, vw), spots = [];
        runs.forEach((r) => {
          if (r.hi - r.lo < nw + 16) return;
          const at = (x) => Math.max(r.lo + nw / 2 + 8, Math.min(r.hi - nw / 2 - 8, x));
          const lines = segs.filter((s) => s.i !== i || s.j !== r.j);
          [(r.lo + r.hi) / 2, r.lo + w / 2 + 8, r.hi - w / 2 - 8].concat([0.25, 0.75, 0.125, 0.375, 0.625, 0.875].map((f) => r.lo + f * (r.hi - r.lo)))
            .forEach((x) => spots.push({ x: at(x), y: r.y, lines }));
        });
        for (const way of ways) {
          for (const q of spots) {
            const o = way(q, vw, ls.length);
            if (o && o.boxes.every((b) => free(b) && q.lines.every((s) => apart(b, s)))) { got = Object.assign(o, { x: q.x }); break; }
          }
          if (got) break;
        }
        // beside an upright stretch long enough for the name and its values: at its middle,
        // quarters and eighths (kept clear of its ends), right of the line, then left of it
        if (!got && explicit) {
          const n = ls.length, up = [];
          ups.forEach((r) => {
            if (r.hi - r.lo < 18 + n * LINE + 24) return;
            const at = (y) => Math.max(r.lo + 25, Math.min(r.hi - 17 - n * LINE, y));
            const lines = segs.filter((s) => s.i !== i || s.j !== r.j);
            [0.5, 0.25, 0.75, 0.125, 0.375, 0.625, 0.875].forEach((f) => up.push({ x: r.x, y: at(r.lo + f * (r.hi - r.lo)), lines }));
          });
          for (const dir of [1, -1]) {
            for (const q of up) {
              const o = beside(q, vw, n, dir);
              if (o.boxes.every((b) => free(b) && q.lines.every((s) => apart(b, s)))) { got = o; break; }
            }
            if (got) break;
          }
        }
        if (!got && explicit && ls.length) {
          for (const way of past) {
            for (const q of spots) {
              const o = way(q, vw, ls.length);
              if (o && o.boxes.every((b) => free(b) && q.lines.every((s) => apart(b, s)))) { got = Object.assign(o, { x: q.x }); break; }
            }
            if (got) break;
          }
        }
        if (got) { kept = ls; taken.push(...got.boxes); break; }
      }
      if (!got && GEO && !terminal) {
        // the icon view (a figure): the name alone, by any stretch of its own line however short,
        // over or under a level one, beside an upright one, where it covers no other line, none
        // of its own but that stretch, no block and no label; else as below
        const ok = (b, j) => free(b) && segs.every((s) => (s.i === i && s.j === j) || apart(b, s));
        const fr = [0.5, 0.25, 0.75, 0.125, 0.375, 0.625, 0.875];
        for (const r of runs) {
          for (const f of fr) {
            const q = { x: r.lo + f * (r.hi - r.lo), y: r.y };
            got = [ways[0], ways[2]].map((w) => Object.assign(w(q, 0, 0), { x: q.x })).find((o) => o.boxes.every((b) => ok(b, r.j))) || null;
            if (got) break;
          }
          if (got) break;
        }
        for (const r of got ? [] : ups) {
          for (const f of fr) {
            const q = { x: r.x, y: r.lo + f * (r.hi - r.lo) };
            got = [1, -1].map((dir) => beside(q, 0, 0, dir)).find((o) => o.boxes.every((b) => ok(b, r.j))) || null;
            if (got) break;
          }
          if (got) break;
        }
        if (got) taken.push(...got.boxes);
      }
      if (!got && explicit && !terminal) {
        // the name alone at the middle of any stretch, however short (over or under a level one,
        // beside an upright one), clear of blocks and labels: the halo covers other lines
        const cand = [];
        runs.forEach((r) => { const q = { x: (r.lo + r.hi) / 2, y: r.y }; cand.push(Object.assign(ways[0](q, 0, 0), { x: q.x }), Object.assign(ways[2](q, 0, 0), { x: q.x })); });
        ups.forEach((r) => { const q = { x: r.x, y: (r.lo + r.hi) / 2 }; cand.push(beside(q, 0, 0, 1), beside(q, 0, 0, -1)); });
        got = cand.find((o) => o.boxes.every(free)) || null;
        if (!got) {
          // the nearest free spot about the path's middle (by length), 10 units apart, off its
          // arrowhead (a short stream's middle lies next to it: its last 12 units, 5 either side)
          const mid = middle(pts), offs = [], n = pts.length, e1 = pts[n - 1], e0 = pts[n - 2];
          const f = Math.min(1, 12 / (Math.abs(e1.x - e0.x) + Math.abs(e1.y - e0.y) || 1)), q = { x: e1.x + (e0.x - e1.x) * f, y: e1.y + (e0.y - e1.y) * f };
          const tip = { x: Math.min(e1.x, q.x) - 5, y: Math.min(e1.y, q.y) - 5, w: Math.abs(e1.x - q.x) + 10, h: Math.abs(e1.y - q.y) + 10 };
          for (let dx = -60; dx <= 60; dx += 10) for (let dy = -40; dy <= 40; dy += 10) offs.push([dx, dy]);
          offs.sort((a, b) => Math.abs(a[0]) + Math.abs(a[1]) - Math.abs(b[0]) - Math.abs(b[1]) || a[1] - b[1] || a[0] - b[0]);
          for (const [dx, dy] of offs) {
            const x = mid.x + dx, ly = mid.y + dy + 1, b = { x: x - nw / 2 - 4, y: ly - 14, w: nw + 8, h: 18 };
            if (free(b) && apart(b, tip)) { got = { x, ly, vy: ly + 14, boxes: [b] }; break; }
          }
        }
        if (!got) {                                // last: over the longest stretch
          const lr = runs[0], ur = ups[0];
          if (ur && (!lr || ur.hi - ur.lo > lr.hi - lr.lo)) got = beside({ x: ur.x, y: (ur.lo + ur.hi) / 2 }, 0, 0, 1);
          else { const q = lr ? { x: (lr.lo + lr.hi) / 2, y: lr.y } : middle(pts); got = Object.assign(ways[0](q, 0, 0), { x: q.x }); }
        }
        taken.push(...got.boxes);
      }
      if (!got) {
        const q = runs[0] ? { x: (runs[0].lo + runs[0].hi) / 2, y: runs[0].y } : pts[0];
        got = Object.assign(ways[0](q, 0, 0), { x: q.x });
        if (!terminal) taken.push(...got.boxes);
      }
      return { d: geo[i].d, lx: got.x, ly: got.ly, vy: got.vy, vk: kept.map((l) => l.k), anchor: got.anchor || "middle", pts, raw: geo[i].raw };
    });
  }
  /** The point halfway along a path ({x, y} points), by length. */
  function middle(pts) {
    let L = 0;
    for (let j = 1; j < pts.length; j++) L += Math.abs(pts[j].x - pts[j - 1].x) + Math.abs(pts[j].y - pts[j - 1].y);
    let acc = 0;
    for (let j = 1; j < pts.length; j++) {
      const d = Math.abs(pts[j].x - pts[j - 1].x) + Math.abs(pts[j].y - pts[j - 1].y);
      if (acc + d >= L / 2) { const f = d ? (L / 2 - acc) / d : 0; return { x: pts[j - 1].x + f * (pts[j].x - pts[j - 1].x), y: pts[j - 1].y + f * (pts[j].y - pts[j - 1].y) }; }
      acc += d;
    }
    return { x: pts[0].x, y: pts[0].y };
  }

  /** v: {flowsheet, notes, highlight, selection, status, values, showValues, stale, delta, heat,
   *  layout, aspen, canMove, changes} for the tab shown. delta: {stream: {t | p | f: {b, a, u}}},
   *  the values the last run moved (a small ▲ ▼ after each, what it was in the tooltip; the
   *  page drops it once another run came or the values moved since). changes: {"block:NAME" |
   *  "stream:NAME": {actor, n, tip}}, changes by others not seen yet: a dot in the actor's
   *  colour at a block's top left (with how many) or beside a stream's name (a click:
   *  FS.attach's on.changes). pins: the same keys: {n, fresh, tip}, the annotations layer
   *  (app-pins.js): a speech-bubble marker outside a block's bottom left, after a stream's
   *  name (a click: FS.onPin); counted beyond an edge (FS.offscreen). stale: the values are from the last run, and
   *  an input changed by hand since (they show faded, and their tooltip says so). layout: the
   *  session's arrangement ({mode: "auto" | "aspen" | "custom", id, base, nodes, streams}) or
   *  null (automatic); aspen: the last layout read from Aspen that fits this model, or null
   *  (an "aspen" arrangement without it is drawn automatically); canMove: blocks, feeds,
   *  products and the inner parts of streams can be dragged (FS.attach's on.layout hears of
   *  each drop). While a press is held on the drawing, what comes is drawn once it is let go:
   *  a rebuild under the press would lose its click, and a drag starts from what it pressed. */
  FS.render = function (svg, v) {
    if (svg._fsHeld) { svg._fsPending = v; return; }
    svg._fsPending = null;
    draw(svg, v);
  };
  /** The explicit layout of Aspen's drawing imp for this context, kept while the import, the
   *  flowsheet and the view stay the same. */
  function aspenOf(c, imp, fs, view) {
    const k = `${imp.at}|${imp.req}|${fs.taken_at}|${view}`;
    if (!c.asp || c.asp.k !== k) c.asp = { k, lay: explicitFromAspen(imp, fs, view) };
    return c.asp.lay;
  }
  /** The icon view's geometry for the automatic layout: each stream's nozzles in the order of
   *  its other end's row in the columns (the layering's own order); a recycle comes from its lane
   *  under the drawing (from the left of the block it enters, to the right of the one it leaves). */
  function autoGeo(abs) {
    const G = geoOf(abs.fs), row = new Map(), by = new Map(abs.edges.map((e) => [e.name, e]));
    abs.cols.forEach((col) => col.forEach((k, i) => row.set(k, i - (col.length - 1) / 2)));
    return assignEnds(G, abs.fs, (s, k, axis) => {
      const e = by.get(s);
      if (e && e.back) return axis === "x" ? (k === "a" ? 1e6 : -1e6) : 1e6;
      return e ? row.get(k === "a" ? e.chain[1] : e.chain[e.chain.length - 2]) || 0 : 0;
    });
  }
  // the symbols a drawing uses, as <symbol> markup, each set of types made once
  const SYMS = new Map();
  function symbols(keys) {
    const k = [...keys].sort().join(",");
    if (!SYMS.has(k)) {
      if (SYMS.size > 40) SYMS.clear();
      SYMS.set(k, [...keys].sort().map((t) => { const s = FSI.types[t]; return `<symbol id="fsi-${t}" viewBox="0 0 ${s.w} ${s.h}" overflow="visible">${s.g}</symbol>`; }).join(""));
    }
    return SYMS.get(k);
  }
  function draw(svg, v) {
    const prev = GEO;
    try { drawIn(svg, v); } finally { GEO = prev; }
  }

  // ------------------------------------------------------------------ a proposal's preview
  /* What a proposal would leave drawn (FS.render's v.preview.shadow: the server's tab.check.shadow),
   * over the drawing as it is: nothing drawn moves. A new block goes beside the block it connects
   * to (placeMissing, the way an explicit arrangement places one it lacks), else in a row under the
   * drawing, new ones by name; a new stream's feed or product beside its block; each new stream,
   * and each moved one's new route, routed fresh among the blocks. Kept in the context while the
   * drawing and the shadow stay the same (one placing per check). Its parts: nodes (each new
   * block's and terminal's centre), blocks [{id, name, type, g, d (its frame, icon view)}], lines
   * [{name, g, d, mid, moved, ex ({n, a, b, h, c}: the route as an arrangement keeps it)}], terms
   * [{id, name, feed}], gone (the removed blocks' and streams' keys), was (the moved streams':
   * their old line and end), geo (the icon view's geometry of it), ms (what placing took).
   * keep (a run by group): the arrangement drawn, whose places for what is still
   * new win (the places the preview gave, kept once an earlier group was applied: nothing jumps).
   * only (that run's group now): a new stream an earlier group made and this one connects on is a
   * moved one of this group (late); a stream of this group whose end is a block of a later group
   * ends loose (a feed or product beside its block) until that group puts the block there. */
  function pvLayout(c, fs, sh, keep, only) {
    const t0 = performance.now(), lay = c.lay, nodes = {}, add = (sh && sh.add) || {};
    lay.nodes.forEach((n, k) => { if (n.kind !== "dummy" && lay.pos[k]) nodes[k] = [lay.pos[k].x, lay.pos[k].y]; });
    const have = new Set((fs.blocks || []).map((b) => b.name));
    const fresh = (add.blocks || []).filter((b) => b && b.name && !have.has(b.name)).sort((p, q) => (p.name < q.name ? -1 : p.name > q.name ? 1 : 0));
    const streams = (fs.streams || []).map((s) => ({ name: s.name, from: s.from || null, to: s.to || null, from_port: s.from_port, to_port: s.to_port, type: s.type }));
    const by = new Map(streams.map((s) => [s.name, s])), moved = new Set(), made = new Set();
    (sh.move || []).forEach((m) => {
      const s = m && by.get(m.stream);
      if (!s || (m.end !== "from" && m.end !== "to")) return;
      s[m.end] = m.now && m.now.block ? m.now.block : null;
      s[m.end + "_port"] = m.now && m.now.block ? m.now.port || null : null;
      moved.add(s.name);
    });
    const late = new Map();                        // (stream -> the new block its end now reaches)
    (add.streams || []).forEach((a) => {
      if (!a || !a.name) return;
      if (by.has(a.name)) {                        // (made already: an earlier group of a run by group)
        const s = by.get(a.name);
        ["from", "to"].forEach((e) => {
          if (!a[e] || s[e] === a[e]) return;
          s[e] = a[e];
          s[e + "_port"] = a[e + "_port"] || null;
          moved.add(s.name);
          late.set(s.name, a[e]);
        });
        return;
      }
      const s = { name: a.name, from: a.from || null, to: a.to || null, from_port: a.from_port, to_port: a.to_port, type: a.type };
      streams.push(s);
      by.set(s.name, s);
      made.add(s.name);
    });
    const blocks = (fs.blocks || []).map((b) => ({ name: b.name, type: b.type })).concat(fresh.map((b) => ({ name: b.name, type: b.type || "" })));
    const f2 = { blocks, streams };
    // (the icon view: the frames of every block, the new ones' too, existing ones mirrored as drawn;
    // each stream's nozzles in the order of where its other end lies)
    let G = null;
    if (c.geo) {
      G = geoOf(f2);
      setFlips(G, new Set(Object.keys(c.geo.node).filter((k) => c.geo.node[k].flip)));
    }
    const prev = GEO;
    GEO = G;
    const out = { nodes: {}, blocks: [], lines: [], terms: [], gone: [], was: [], geo: G, ms: 0 };
    try {
      const before = new Set(Object.keys(nodes)), kept = keep && keep.nodes && typeof keep.nodes === "object" ? keep.nodes : null;
      if (kept) fresh.map((b) => "B:" + b.name).concat([...made].flatMap((n) => ["F:" + n, "P:" + n])).forEach((k) => {
        const p = kept[k];
        if (!nodes[k] && Array.isArray(p) && isFinite(p[0]) && isFinite(p[1])) nodes[k] = [Number(p[0]), Number(p[1])];
      });
      EX.placeMissing({ nodes, streams: {} }, { blocks, streams: streams.filter((s) => made.has(s.name) || moved.has(s.name)) });
      if (only != null) {                          // (an end on a later group's block: loose for now)
        const gNew = new Map(fresh.map((b) => [b.name, b.g])), gS = new Map();
        (add.streams || []).forEach((a) => a && gS.set(a.name, a.g));
        (sh.move || []).forEach((m) => m && gS.set(m.stream, m.g));
        const cut = streams.filter((s) => (made.has(s.name) || moved.has(s.name)) && !late.has(s.name) && gS.get(s.name) === only
          && ["from", "to"].some((e) => s[e] && gNew.get(s[e]) > only));
        cut.forEach((s) => ["from", "to"].forEach((e) => { if (s[e] && gNew.get(s[e]) > only) { s[e] = null; s[e + "_port"] = null; } }));
        if (cut.length) EX.placeMissing({ nodes, streams: {} }, { blocks, streams: cut });
      }
      Object.keys(nodes).forEach((k) => { if (!before.has(k)) { nodes[k] = [EX.r1(nodes[k][0]), EX.r1(nodes[k][1])]; out.nodes[k] = nodes[k].slice(); } });
      if (G) {
        const end = (s, k) => (k === "a" ? (s.to ? "B:" + s.to : "P:" + s.name) : (s.from ? "B:" + s.from : "F:" + s.name));
        assignEnds(G, f2, (sn, k, axis) => { const s = by.get(sn), p = s && nodes[end(s, k)]; return p ? p[axis === "x" ? 0 : 1] : 0; });
      }
      const gOf = new Map();
      (add.blocks || []).forEach((b) => b && gOf.set("block:" + b.name, b.g));
      (add.streams || []).forEach((s) => s && gOf.set("stream:" + s.name, s.g));
      (sh.move || []).forEach((m) => m && gOf.set("stream:" + m.stream, m.g));
      late.forEach((blk, name) => { const b = fresh.find((x) => x.name === blk); if (b && b.g != null) gOf.set("stream:" + name, b.g); });
      fresh.forEach((b) => {
        const id = "B:" + b.name;
        if (nodes[id]) out.blocks.push({ id, name: b.name, type: b.type || "", g: b.g, d: G ? G.node[id] : null });
      });
      const boxes = Object.keys(nodes).filter((k) => k[0] === "B").map((k) => EX.boxAt(nodes[k], k));
      streams.forEach((s) => {
        if (!made.has(s.name) && !moved.has(s.name)) return;
        const a = s.from ? "B:" + s.from : "F:" + s.name, b = s.to ? "B:" + s.to : "P:" + s.name;
        if (!nodes[a] || !nodes[b]) return;
        const ta = a[0] !== "B", tb = b[0] !== "B";
        const g0 = { a: ta ? null : startEnd(s.name, "a", a, ["r", 0]), b: tb ? null : startEnd(s.name, "b", b, ["l", 0]), h: 1, c: [] };
        const r = EX.fit(g0, nodes[a], nodes[b], boxes, true, true, null, null, { n: [a, b], s: s.name });
        const leads = EX.leadsOf(s.name, [a, b], nodes[a], nodes[b], r.a, r.b);
        const pts = EX.drawPoints(r.pts, ta, tb, leads).map(([x, y]) => ({ x, y })), geo = roundPath(pts);
        const box = pts.reduce((u, q) => join(u, { x0: q.x, y0: q.y, x1: q.x, y1: q.y }), null);
        out.lines.push({ name: s.name, g: gOf.get("stream:" + s.name), d: geo.d, mid: middle(pts), box, moved: moved.has(s.name), late: late.has(s.name), ta, tb,
                         energy: !!(G && G.ends && G.ends.get(s.name) && G.ends.get(s.name).energy),
                         ex: { n: [a, b], a: r.a ? [r.a[0], r.a[1]] : null, b: r.b ? [r.b[0], r.b[1]] : null, h: r.h, c: r.c.slice() } });
        [[a, ta, true], [b, tb, false]].forEach(([id, term, feed]) => { if (term && out.nodes[id]) out.terms.push({ id, name: s.name, feed }); });
      });
    } finally { GEO = prev; }
    (sh.remove && sh.remove.blocks || []).forEach((b) => b && out.gone.push("block:" + b.name));
    (sh.remove && sh.remove.streams || []).forEach((s) => s && out.gone.push("stream:" + s.name));
    moved.forEach((n) => out.was.push("stream:" + n));
    out.ms = performance.now() - t0;
    return out;
  }
  /** A symbol's markup as a proposal's line drawing: violet and dashed on its white ground .75;
   *  gone: grey and dashed (what the proposal removes). */
  const PVSYM = new Map();
  function pvSymbol(key, gone, gc) {
    const k = `${key}|${gone ? 1 : 0}|${gc ? 1 : 0}`;
    if (!PVSYM.has(k)) {
      const g = String((FSI.types[key] || FSI.types._Generic).g);
      PVSYM.set(k, g.replace(/stroke="#1a1a1a"/g, `stroke="${gone ? "#9aa3ae" : gc ? "#3b82f6" : "#7c5cff"}"`).replace(/fill="#ffffff"/g, 'fill="#ffffff" fill-opacity=".75"')
        .replace(/^<g /, '<g stroke-dasharray="3.4 2.7" '));
    }
    return PVSYM.get(k);
  }
  function drawIn(svg, v) {
    const fs = v.flowsheet, c = C(svg);
    c.canMove = !!(v.canMove && fs && fs.blocks);
    if (svg.classList.contains("can-move") !== c.canMove) svg.classList.toggle("can-move", c.canMove);
    if (!fs || !fs.blocks) {
      svg.innerHTML = `<text x="40" y="60" class="fs-empty">${esc(I18N.t("fs_empty"))}</text>`;
      svg._fsHtml = null;
      c.items = [];
      c.pins = [];
      c.pvItems = [];
      c.pvShown = false;
      c.tops = [];
      c.heatBox = null;
      moved(svg);
      return;
    }
    // each stream's value lines while the Values layer shows: the layout makes room for them,
    // so a new flowsheet, the layer turned on or off, or new values lay the drawing out again
    // (the view kept on what it showed: keepPlace)
    // (and the last run's arrows beside them: v.delta, which the layout makes room for too)
    // (the icon view, a figure: a temperature's unit with its degree sign, 187.6 °C)
    const vals = v.showValues ? new Map() : null, fig = v.view !== "boxes" && ICONS();
    const deg = (s) => (s ? String(s).replace(/ (C|F)$/, " °$1") : s);
    if (vals) (fs.streams || []).forEach((s) => {
      let ls = valueLines((v.values || {})[s.name], v.delta && v.delta[s.name]);
      if (fig) ls = ls.map((l) => (l.k === "t" ? Object.assign({}, l, { s: deg(l.s) }, l.was ? { was: deg(l.was) } : {}) : l));
      if (ls.length) vals.set(s.name, ls);
    });
    const vkey = vals ? JSON.stringify([...vals].map(([n, ls]) => [n, ls.map((l) => l.s + (l.d || ""))])) : "";
    // the arrangement drawn: custom (moved by hand), Aspen's (with a layout read from it), or
    // automatic; its family is where it came from (custom ones keep their base)
    const L = v.layout || null, imp = v.aspen || null;
    const mode = L && L.mode === "custom" && L.nodes && typeof L.nodes === "object" ? "custom" : L && L.mode === "aspen" && imp ? "aspen" : "auto";
    const fam = mode === "aspen" || (mode === "custom" && L.base === "aspen") ? "aspen" : "auto";
    // how blocks are drawn: their symbols (the default), or boxes
    const view = v.view === "boxes" || !ICONS() ? "boxes" : "icons";
    const key = [fs.taken_at, mode, (L && L.id) || "", mode === "aspen" ? imp.at : "", vkey, view].join("|");
    let edge = null, refit = false, fitNow = false;  // edge: the drawing's start edge the view showed, kept where it was
    if (!c.lay || key !== c.key) {
      // the view: fitted for a new context, another family or way of drawing, or an import not
      // drawn here yet; an automatic drawing as before (a new flowsheet fits, the Values layer
      // keeps the place); otherwise (a drop, an undo within the family, a refresh) it stays
      // exactly as it is
      const first = !c.lay, taken = fs.taken_at !== c.taken, famNew = fam !== c.fam, oldV = c.vkey, viewNew = view !== c.drawn;
      const old = !first && c.lay, ob = c.box, ov = c.view;
      if (taken || !c.abs) c.abs = layout(fs);
      c.geo = view === "icons" ? autoGeo(c.abs) : null;
      GEO = c.geo;
      c.lay = mode === "auto" ? place(c.abs, vals) : placeExplicit(c.abs, mode === "custom" ? L : aspenOf(c, imp, fs, view), vals);
      c.key = key;
      c.taken = fs.taken_at;
      c.vkey = vkey;
      c.mode = mode;
      c.fam = fam;
      c.drawn = view;
      if (first || famNew || viewNew || (mode === "aspen" && c.drewImport !== imp.at)) fitNow = true;
      else if (mode === "auto" && taken) fitNow = true;
      else if (mode === "auto" && vkey !== oldV) {
        if (c.fitted) refit = true;                // a fitted view nobody has moved since is fitted again
        else {
          keepPlace(c, old, ov && c.px && c.px.w ? (ov.w / c.px.w) * FS.insets(svg).top : 0);
          if (ov && ob) edge = { x: ov.x <= ob.x0 + 1 ? ob.x0 - ov.x : null, y: ov.y <= ob.y0 + 1 ? ob.y0 - ov.y : null };
        }
      }
      // (a moved Aspen layout drawn while that import is kept counts as drawing it: undoing
      // back to the unmoved one keeps the view, in a tab that never drew it too)
      if (fam === "aspen" && imp) c.drewImport = imp.at;
    }
    GEO = c.geo;
    const IC = !!GEO, used = new Set();            // (the icon view; the symbols it draws)
    if (svg.classList.contains("icons") !== IC) svg.classList.toggle("icons", IC);
    const lay = c.lay, status = v.status || {};
    // a proposal's preview (v.preview): placed once per drawing and shadow
    // (pvLayout), never with a heat plan (that layer pauses it)
    // (a run by group: the same placing -- the arrangement's places for what is new kept --,
    // only the group applied now drawn: pvIn.only, in the accent: pvIn.gc)
    const pvIn = v.preview && v.preview.shadow && !v.heat ? v.preview : null;
    let PV = null;
    if (pvIn) {
      const keep = pvIn.gc && mode === "custom" ? L : null;
      const pk = `${c.key}|${keep ? "k" : ""}|${pvIn.gc ? pvIn.only : ""}|${JSON.stringify(pvIn.shadow)}`;
      if (!c.pv || c.pv.k !== pk) c.pv = { k: pk, res: pvLayout(c, fs, pvIn.shadow, keep, pvIn.gc ? pvIn.only : null), taken: fs.taken_at };
      PV = c.pv.res;
    }
    const pvG = {}, pvOnly = PV && pvIn.only != null ? pvIn.only : null;   // (each new or changed object's group)
    if (pvOnly != null) {
      const sh = pvIn.shadow, by = (list, kind, name) => (Array.isArray(list) ? list : []).forEach((x) => { if (x && x[name]) pvG[`${kind}:${x[name]}`] = x.g; });
      by(sh.add && sh.add.blocks, "block", "name"); by(sh.add && sh.add.streams, "stream", "name");
      by(sh.remove && sh.remove.blocks, "block", "name"); by(sh.remove && sh.remove.streams, "stream", "name");
      by(sh.move, "stream", "stream");
      PV.lines.forEach((l) => { if (l.late) pvG[`stream:${l.name}`] = l.g; });   // (connected on by a later group)
    }
    const pvIs = (k) => pvOnly == null || pvG[k] === pvOnly;
    // what is drawn, for fitting and for the edge hints
    const box = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
    const tops = [];                               // [x0, y0, x1] of each thing: how high the drawing reaches where
    const grow = (x0, y0, x1, y1) => {
      box.x0 = Math.min(box.x0, x0); box.y0 = Math.min(box.y0, y0); box.x1 = Math.max(box.x1, x1); box.y1 = Math.max(box.y1, y1);
      tops.push([x0, y0, x1]);
    };
    const items = [], chgs = [];                   // chgs: the changes' dots, {kind, name, actor, box} (FS.offscreen)
    const pinned = [];                             // the annotations' markers, {kind, name, n, box} (FS.offscreen)
    const hl = new Set((v.highlight || []).map((h) => `${h.kind}:${h.name}`));
    const sel = v.selection ? `${v.selection.kind}:${v.selection.name}` : null;
    const chOf = (kind, name) => (v.changes && v.changes[`${kind}:${String(name).toUpperCase()}`]) || null;
    const pinOf = (kind, name) => (v.pins && v.pins[`${kind}:${String(name).toUpperCase()}`]) || null;
    // value lines: one text, a line each; faded, with a tooltip, while they are stale. Written
    // once the request bubbles are placed (a function, called then): lines a bubble would
    // cover are left out, as the hover card has them. A value the last run moved has a small
    // ▲ or ▼ after it, and the tooltip says what it was before that run
    const bubbles = [];
    const valText = (x, y, anchor, ls) => () => {
      if (!ls.length) return "";
      const w = Math.max(...ls.map((l) => lineW(l))), x0 = anchor === "middle" ? x - w / 2 : anchor === "end" ? x - w : x;
      const y1 = y + LINE * (ls.length - 1) + 3;
      if (bubbles.some((u) => u.x0 < x0 + w && x0 < u.x1 && u.y0 < y1 && y - 9 < u.y1)) return "";
      const moved = ls.filter((l) => l.d), tip = [v.stale ? I18N.t("tip_stale") : ""]
        .concat(moved.length ? [I18N.t("vd_tip")].concat(moved.map((l) => `${I18N.t(`pk_${l.k}`)} ${l.was} → ${l.s} ${l.d}`)) : [])
        .filter(Boolean).join("\n");
      return `<text x="${x}" y="${y}" class="val" text-anchor="${anchor}">${tip ? `<title>${esc(tip)}</title>` : ""}`
        + ls.map((l, i) => `<tspan x="${x}"${i ? ` dy="${LINE}"` : ""}>${esc(l.s)}${l.d ? `<tspan class="vd" dx="2">${l.d}</tspan>` : ""}</tspan>`).join("") + "</text>";
    };
    // a dot grid under it all, well past the drawing's edges (a pattern: one tile, repeated),
    // so the glass floating over the drawing has something to bend; it moves with the view
    // (the icon view: a white ground with no grid, as a figure; the symbols of the types drawn,
    // and an arrowhead in the lines' ink, its tip on the line's end)
    const G = Math.max(lay.width, lay.height, 1200) * 1.5, gx = Math.min(0, lay.x0 || 0), gy = Math.min(0, lay.y0 || 0);
    const parts = [IC ? () => `<defs>
      <marker id="arr-ink" viewBox="0 0 8 7" refX="8" refY="3.5" markerWidth="8" markerHeight="7" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0,0 L8,3.5 L0,7 z" fill="#1a1a1a"/></marker>
      <marker id="arr-heat" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#f08a24"/></marker>
      <marker id="arr-hl" viewBox="0 0 8 7" refX="8" refY="3.5" markerWidth="8" markerHeight="7" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0,0 L8,3.5 L0,7 z" fill="#7c5cff"/></marker>
      ${PV && pvIn.gc ? `<marker id="arr-gc" viewBox="0 0 8 7" refX="8" refY="3.5" markerWidth="8" markerHeight="7" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0,0 L8,3.5 L0,7 z" fill="#3b82f6"/></marker>` : ""}
      ${symbols(used)}</defs>` : `<defs>
      <pattern id="fs-dots" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="10" cy="10" r="1.2" fill="#d5dbe5"/></pattern>
      <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#6b7785"/></marker>
      <marker id="arr-heat" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#f08a24"/></marker>
      <marker id="arr-hl" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#7c5cff"/></marker>
      ${PV && pvIn.gc ? `<marker id="arr-gc" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#3b82f6"/></marker>` : ""}
    </defs><rect class="fs-grid" x="${gx - G}" y="${gy - G}" width="${lay.width - gx + 2 * G}" height="${lay.height - gy + 2 * G}" fill="url(#fs-dots)"/>`];
    // a stream is its line (.fs-edge); its name and value lines (.fs-tag) are drawn after every
    // line, so their halo keeps the lines that pass under them from crossing the words
    const anchor = {}, tags = [], names = [];      // (names: where streams' names are, which a result tag keeps off)
    // the flow width layer (v.flows): a pale band under each stream's line, as wide
    // as app-flows.js fwView says (drawing units: it zooms as the line does); the lines, their
    // arrowheads and dashes stay as they are, heat and work streams have none. A small flow's value
    // goes by its name (fwVal): under it where the Values layer shows no lines there, else after
    // it. Neither in a figure (FIG_DROP), nor the names' halo over the bands (svg.fw, FIG_STATE)
    const FW = v.flows && typeof v.flows === "object" ? v.flows : null, fwv = [];
    const fwVal = (name, x, y, anchor, ls) => {
      const s = FW && FW.vals && FW.vals[name];
      if (FW.total && ls.some((l) => l.k === "f")) return;   // (the total flow: its value line says it already)
      if (!s) return;
      fwv.push(`<text x="${x}" y="${y}" text-anchor="${anchor}" data-s="${esc(name)}">${esc(s)}</text>`);
      const w = textWidth(s), x0 = anchor === "end" ? x - w : anchor === "middle" ? x - w / 2 : x;
      grow(x0, y - 10, x0 + w, y + 3);             // (inside the drawing's box: a fit shows it whole)
    };
    // (the composition, FW.seg -- a band in segments along its stream, [start, length, colour] as
    // shares of the line: one path each, its dashes on a pathLength of 1000, the palette .c0-.c7 in style.css)
    if (FW && FW.w) {
      let h = "";
      lay.edges.forEach((e, i) => {
        const w = Number(FW.w[e.name]), g = lay.geo[i];
        if (!(w > 0) || !g || !g.d || (IC && GEO.ends && GEO.ends.get(e.name) && GEO.ends.get(e.name).energy)) return;
        const sw = Math.round(w * 100) / 100, sg = FW.seg && FW.seg[e.name], r = (x) => Math.round(x * 10000) / 10;
        if (sg) sg.forEach(([a, l, k]) => {
          h += `<path class="c${k}" d="${g.d}" stroke-width="${sw}" pathLength="1000" stroke-dasharray="0 ${r(a)} ${r(l)} 2000" data-s="${esc(e.name)}"/>`;
        });
        else h += `<path d="${g.d}" stroke-width="${sw}" data-s="${esc(e.name)}"/>`;
      });
      if (h) parts.push(`<g class="fs-band${FW.seg ? " mix" : ""}">${h}</g>`);
    }
    lay.edges.forEach((e, i) => {
      const g = lay.geo[i], key = `stream:${e.name}`, on = hl.has(key), selected = sel === key;
      const cls = `${on ? " hl" : ""}${selected ? " sel" : ""}`, data = `data-kind="stream" data-name="${esc(e.name)}"`;
      if (e.back && e.lane) grow(Infinity, Infinity, -Infinity, e.lane + 4);   // its lane under the drawing
      if (lay.explicit) {                          // an explicit route may run anywhere: each stretch counts
        for (let j = 1; j < g.pts.length; j++) {
          const p = g.pts[j - 1], q = g.pts[j];
          grow(Math.min(p.x, q.x), Math.min(p.y, q.y), Math.max(p.x, q.x), Math.max(p.y, q.y));
        }
      }
      const terminal = lay.nodes.get(e.a).kind === "feed" || lay.nodes.get(e.b).kind === "prod";
      const ls = vals && !terminal ? (g.vk || []).map((k) => (vals.get(e.name) || []).find((l) => l.k === k)).filter(Boolean) : [];
      anchor[key] = { x: g.lx, y: (ls.length && g.vy < g.ly ? g.vy : g.ly) - 18, lbl: e.name };   // over its name (or its values over that)
      const energy = IC && GEO.ends && GEO.ends.get(e.name) && GEO.ends.get(e.name).energy ? " energy" : "";
      parts.push(`<g class="fs-edge${cls}${e.back ? " back" : ""}${energy}" ${data}>
        <path class="hit" d="${g.d}"/><path class="line" d="${g.d}" marker-end="url(#${on ? "arr-hl" : IC ? "arr-ink" : "arr"})"/></g>`);
      if (!terminal) {
        const ta = g.anchor || "middle", vt = valText(g.lx, g.vy, ta, ls), cm = chOf("stream", e.name), pm = pinOf("stream", e.name);
        // changes not seen yet: a small dot left of its name; annotations: their marker after it
        const w = cm || pm ? textWidth(e.name) : 0, x0 = ta === "middle" ? g.lx - w / 2 : ta === "end" ? g.lx - w : g.lx;
        const dot = cm ? chDot(x0 - 7, g.ly - 4, cm, false) : "";
        const pin = pm ? pinMark(x0 + w + 17, g.ly - 4, pm, 180) : "";
        if (pm) pinned.push({ kind: "stream", name: e.name, n: Number(pm.n) || 0, box: { x0: x0 + w + 5, y0: g.ly - 10, x1: x0 + w + 25, y1: g.ly + 2 } });
        if (cm) chgs.push({ kind: "stream", name: e.name, actor: cm.actor, box: { x0: x0 - 12, y0: g.ly - 13, x1: x0 + w, y1: g.ly + 4 } });
        tags.push(() => `<g class="fs-tag${cls}" ${data}><text x="${g.lx}" y="${g.ly}" class="lbl" text-anchor="${ta}">${esc(e.name)}</text>${vt()}${dot}${pin}</g>`);
        if (FW) {                                  // (a small flow's value: under the name, or after it)
          const nw = textWidth(e.name), dx = pm ? 28 : 6;     // (after the name, beyond its annotation marker)
          if (ls.length) fwVal(e.name, (ta === "middle" ? g.lx + nw / 2 : ta === "end" ? g.lx : g.lx + nw) + dx, g.ly, "start", ls);
          else fwVal(e.name, g.lx, g.vy, ta, ls);
        }
        if (v.effects) {
          const nw = textWidth(e.name), nx = ta === "middle" ? g.lx - nw / 2 : ta === "end" ? g.lx - nw : g.lx;
          names.push({ x0: nx, y0: g.ly - 11, x1: nx + nw, y1: g.ly + 3 });
        }
      }
    });
    // the preview's new blocks and streams, and the new routes of moved streams: the proposal's
    // line drawing (violet, dashed, no glow), over the streams and under the blocks; none of it
    // in a figure (FIG_DROP). The anchors of its tags (pvAnchor) and what it takes (pvItems: the
    // edge hints count it)
    const pvAnchor = {}, pvItems = [];
    if (PV) {
      const tips = pvIn.tips || {}, ttl = (k) => (tips[k] ? `<title>${esc(tips[k])}</title>` : "");
      let h = "";
      PV.lines.forEach((l) => {
        const k = `stream:${l.name}`, lb = l.ta || l.tb ? null : l.mid;   // (a feed's or product's name is at its end)
        if (!pvIs(k)) return;
        if (l.box) grow(l.box.x0, l.box.y0, l.box.x1, l.box.y1);
        h += `<g class="pv-line${l.moved ? " moved" : ""}${l.energy ? " energy" : ""}" data-pv="${esc(k)}">${ttl(k)}`
          + `<path class="line" d="${l.d}" marker-end="url(#arr-${pvIn.gc ? "gc" : "hl"})"/>`
          + (lb && !l.moved ? `<text class="pv-name" x="${lb.x}" y="${lb.y - 6}" text-anchor="middle">${esc(l.name)}</text>` : "") + `</g>`;
        if (!pvAnchor[k]) pvAnchor[k] = { x: l.mid.x, y: l.mid.y - (lb && !l.moved ? 24 : 10) };
        if (!l.moved) pvItems.push({ name: l.name, box: l.box || { x0: l.mid.x, y0: l.mid.y, x1: l.mid.x, y1: l.mid.y } });
      });
      PV.terms.forEach((tm) => {
        const p = PV.nodes[tm.id], left = tm.feed;
        if (!p || !pvIs(`stream:${tm.name}`)) return;
        const w = textWidth(tm.name);
        grow(left ? p[0] - 12 - w : p[0] - 7, p[1] - 9, left ? p[0] + 7 : p[0] + 12 + w, p[1] + 9);
        h += `<g class="pv-term" data-pv="stream:${esc(tm.name)}">${ttl(`stream:${tm.name}`)}<circle cx="${p[0]}" cy="${p[1]}" r="7"/>`
          + `<text class="pv-name" x="${p[0] + (left ? -12 : 12)}" y="${p[1] + 4}" text-anchor="${left ? "end" : "start"}">${esc(tm.name)}</text></g>`;
        pvAnchor[`stream:${tm.name}`] = { x: p[0], y: p[1] - 22 };
      });
      PV.blocks.forEach((b) => {
        const p = PV.nodes[b.id], k = `block:${b.name}`;
        if (!p || !pvIs(k)) return;
        let box, inner;
        if (IC && b.d) {
          const d = b.d, x0 = p[0] + d.box.x0, y0 = p[1] + d.box.y0, x1 = p[0] + d.box.x1, y1 = p[1] + d.box.y1, w = textWidth(b.name, F.fig);
          box = { x0: Math.min(x0, p[0] - w / 2), y0, x1: Math.max(x1, p[0] + w / 2), y1: y1 + 21 };
          inner = `<rect class="pvpad" x="${x0 - 5}" y="${y0 - 5}" width="${x1 - x0 + 10}" height="${y1 - y0 + 10}" rx="6"/>`
            + `<g transform="translate(${p[0] - d.hw} ${p[1] - d.hh}) scale(${FSI.K})">${pvSymbol(d.key, false, !!pvIn.gc)}</g>`
            + `<text class="pv-name fig" x="${p[0]}" y="${y1 + 17}" text-anchor="middle">${esc(figName(b.name))}</text>`;
          pvAnchor[k] = { x: p[0], y: y0 - 10 };
        } else {
          box = { x0: p[0] - BW / 2, y0: p[1] - BH / 2, x1: p[0] + BW / 2, y1: p[1] + BH / 2 };
          inner = `<rect class="pvbox" x="${box.x0}" y="${box.y0}" width="${BW}" height="${BH}" rx="10"/>`
            + `<text class="pv-name blk" x="${p[0]}" y="${p[1] - 3}" text-anchor="middle">${esc(fitName(b.name, false))}</text>`
            + `<text class="pv-type" x="${p[0]}" y="${p[1] + 15}" text-anchor="middle">${esc(b.type || "")}</text>`;
          pvAnchor[k] = { x: p[0], y: box.y0 - 10 };
        }
        grow(box.x0, box.y0, box.x1, box.y1);
        pvItems.push({ name: b.name, box });
        h += `<g class="pv-blk" data-pv="${esc(k)}">${ttl(k)}${inner}</g>`;
      });
      // (a block it removes, in the icon view: its symbol grey and dashed over the one drawn, which
      // pv-gone hides; the box view greys the box itself)
      if (!IC) PV.gone.forEach((k) => {             // (the box view: counted where it lies, the box itself greyed)
        const p = pvIs(k) && k.startsWith("block:") && lay.pos["B:" + k.slice(6)];
        if (p) pvItems.push({ name: k.slice(6), box: { x0: p.x - BW / 2, y0: p.y - BH / 2, x1: p.x + BW / 2, y1: p.y + BH / 2 } });
      });
      if (IC) PV.gone.forEach((k) => {
        const id = "B:" + k.slice(6), p = pvIs(k) && k.startsWith("block:") && lay.pos[id], d = p && GEO.node[id], nm = lay.names && lay.names[id];
        if (!d) return;
        pvItems.push({ name: k.slice(6), box: { x0: p.x + d.box.x0, y0: p.y + d.box.y0, x1: p.x + d.box.x1, y1: p.y + d.box.y1 } });
        const flip = d.flip ? `matrix(-1 0 0 1 ${2 * p.x} 0) ` : "";
        h += `<g class="pv-was" data-pv="${esc(k)}">${ttl(k)}<g transform="${flip}translate(${p.x - d.hw} ${p.y - d.hh}) scale(${FSI.K})">${pvSymbol(d.key, true)}</g>`
          + (nm ? `<text class="pv-name fig gone" x="${nm.x}" y="${nm.y}" text-anchor="${nm.anchor}">${esc(nm.text)}</text>` : "") + `</g>`;
      });
      parts.push(`<g class="fs-pv${pvIn.gc ? " gcv" : ""}">${h}</g>`);
    }
    parts.push(() => `<g class="fs-tags">${tags.map((f) => f()).join("")}</g>`);
    lay.nodes.forEach((n) => {
      const p = lay.pos[n.id];
      if (n.kind === "dummy") return;
      if (n.kind === "block" && IC) {
        const key = `block:${n.name}`, on = hl.has(key), selected = sel === key, st = status[n.name];
        const lvl = st ? (st.level === "error" ? " err" : " warn") : "";
        const d = GEO.node[n.id], nm = lay.names && lay.names[n.id];
        // (x0..y1: the symbol's ink, which the state outline and the marks go round)
        const x0 = p.x + d.box.x0, y0 = p.y + d.box.y0, x1 = p.x + d.box.x1, y1 = p.y + d.box.y1, nb = nm ? nm.box : { x0: p.x, y0: y1, x1: p.x, y1 };
        used.add(d.key);
        // a request's bubble hangs over the symbol (over its name where that went over it)
        anchor[key] = { x: p.x, y: (nm && nm.side === "u" ? nb.y0 : y0) - 10, at: n.id };
        if (v.effects && nm) names.push(nb);
        grow(Math.min(x0 - 10, nb.x0), Math.min(y0 - 12, nb.y0), Math.max(x1 + 12, nb.x1), Math.max(y1, nb.y1));
        items.push({ kind: "block", name: n.name, err: !!st && st.level === "error", warn: !!st && st.level === "warn",
                     x0: Math.min(x0, nb.x0), y0: Math.min(y0, nb.y0), x1: Math.max(x1, nb.x1), y1: Math.max(y1, nb.y1) });
        // the marks sit just outside the symbol, off its lines: Aspen's badge at the top right,
        // the AI's ✦ left of it (over it on a narrow symbol), the changes' dot at the top left;
        // the annotations' marker at the start of the name, its tail toward it
        const bx = x1 + 2, by = y0 - 2;
        const badge = st ? `<g class="badge"><circle cx="${bx}" cy="${by}" r="10"/>
            <text x="${bx}" y="${by + 4.5}">${st.level === "error" ? "!" : "⚠"}</text>
            <title>${esc(I18N.t(st.level === "error" ? "lvl_error" : "lvl_warn"))}: ${esc(st.msg || "")}</title></g>` : "";
        const wide = x1 - x0 > 48, ax = wide ? bx - (st ? 23 : 0) : bx, ay = wide ? by : by - (st ? 23 : 0);
        const aimark = on ? `<g class="aimark"><circle cx="${ax}" cy="${ay}" r="9"/><path d="${star(ax, ay, 5.4)}"/></g>` : "";
        if (on && !wide) grow(ax - 9, ay - 9, ax + 9, ay);
        const cm = chOf("block", n.name), chdot = cm ? chDot(x0 - 2, y0 - 2, cm, true) : "";
        if (cm) chgs.push({ kind: "block", name: n.name, actor: cm.actor, box: { x0: x0 - 10, y0: y0 - 10, x1, y1 } });
        const pm = pinOf("block", n.name), px = nb.x0 - 13, py = (nb.y0 + nb.y1) / 2, pin = pm ? pinMark(px, py, pm, 0) : "";
        if (pm) {
          grow(px - 9, py - 7, nb.x0, py + 7);
          pinned.push({ kind: "block", name: n.name, n: Number(pm.n) || 0, box: { x0: px - 8, y0: py - 6, x1: px + 12, y1: py + 6 } });
        }
        const fam = family(n.type), tip = [n.name, n.type, fam && I18N.t(`fam_${fam}`)].filter(Boolean).join(" · ")
          + (on ? `\n${I18N.t("tip_hl")}` : "");
        const anc = nm ? { start: " st", end: " en" }[nm.anchor] || "" : "";
        parts.push(`<g class="fs-node${on ? " hl" : ""}${selected ? " sel" : ""}${lvl}" data-kind="block" data-name="${esc(n.name)}" data-node="${esc(n.id)}"><title>${esc(tip)}</title>
          <rect class="frame" x="${x0 - 5}" y="${y0 - 5}" width="${x1 - x0 + 10}" height="${y1 - y0 + 10}" rx="6"/>
          <use href="#fsi-${d.key}" x="${p.x - d.hw}" y="${p.y - d.hh}" width="${2 * d.hw}" height="${2 * d.hh}"${d.flip ? ` transform="matrix(-1 0 0 1 ${2 * p.x} 0)"` : ""}/>
          ${nm ? `<text x="${nm.x}" y="${nm.y}" class="name${anc}">${esc(nm.text)}</text>` : ""}${aimark}${badge}${chdot}${pin}</g>`);
      } else if (n.kind === "block") {
        const key = `block:${n.name}`, on = hl.has(key), selected = sel === key, st = status[n.name];
        const lvl = st ? (st.level === "error" ? " err" : " warn") : "";
        anchor[key] = { x: p.x, y: p.y - BH / 2 - 10, at: n.id };
        grow(p.x - BW / 2, p.y - BH / 2 - 8, p.x + BW / 2 + 8, p.y + BH / 2);
        items.push({ kind: "block", name: n.name, err: !!st && st.level === "error", warn: !!st && st.level === "warn",
                     x0: p.x - BW / 2, y0: p.y - BH / 2, x1: p.x + BW / 2, y1: p.y + BH / 2 });
        const badge = st ? `<g class="badge"><circle cx="${p.x + BW / 2 - 4}" cy="${p.y - BH / 2 + 4}" r="10"/>
            <text x="${p.x + BW / 2 - 4}" y="${p.y - BH / 2 + 8.5}">${st.level === "error" ? "!" : "⚠"}</text>
            <title>${esc(I18N.t(st.level === "error" ? "lvl_error" : "lvl_warn"))}: ${esc(st.msg || "")}</title></g>` : "";
        // the AI's mark: a violet ✦ at the top right (left of Aspen's badge where there is one),
        // with the dashed violet outline (style.css), unlike Aspen's red and amber
        const ax = p.x + BW / 2 - 4 - (st ? 23 : 0), ay = p.y - BH / 2 + 4;
        const aimark = on ? `<g class="aimark"><circle cx="${ax}" cy="${ay}" r="9"/><path d="${star(ax, ay, 5.4)}"/></g>` : "";
        // changes by others not seen yet: a dot at the top left, in the colour of who made the
        // latest, with how many (the top right is Aspen's badge's and the AI's ✦)
        const cm = chOf("block", n.name), chdot = cm ? chDot(p.x - BW / 2 + 3, p.y - BH / 2 + 3, cm, true) : "";
        if (cm) chgs.push({ kind: "block", name: n.name, actor: cm.actor, box: { x0: p.x - BW / 2 - 5, y0: p.y - BH / 2 - 5, x1: p.x + BW / 2, y1: p.y + BH / 2 } });
        // annotations: a speech bubble just outside the bottom left, its tail on the corner
        // (the other corners: changes, Aspen's badge and the AI's ✦, a heat plan's utility)
        const pm = pinOf("block", n.name), px = p.x - BW / 2 - 6, py = p.y + BH / 2 + 5, pin = pm ? pinMark(px, py, pm, -45) : "";
        if (pm) {
          grow(px - 9, p.y, p.x, py + 7);
          pinned.push({ kind: "block", name: n.name, n: Number(pm.n) || 0, box: { x0: px - 8, y0: py - 10, x1: px + 9, y1: py + 6 } });
        }
        // the family's bar just inside the left edge, the words a little right of it; the whole
        // name, type and family in its tooltip
        const fam = family(n.type), tip = [n.name, n.type, fam && I18N.t(`fam_${fam}`)].filter(Boolean).join(" · ")
          + (on ? `\n${I18N.t("tip_hl")}` : "");      // the AI's mark says whose it is
        const tx = p.x + (fam ? 2 : 0);
        parts.push(`<g class="fs-node${on ? " hl" : ""}${selected ? " sel" : ""}${lvl}" data-kind="block" data-name="${esc(n.name)}" data-node="${esc(n.id)}"><title>${esc(tip)}</title>
          <rect x="${p.x - BW / 2}" y="${p.y - BH / 2}" width="${BW}" height="${BH}" rx="10"/>
          ${fam ? `<rect class="fam ${fam}" x="${p.x - BW / 2 + 4}" y="${p.y - BH / 2 + 11}" width="4" height="${BH - 22}" rx="2"/>` : ""}
          <text x="${tx}" y="${p.y - 3}" class="name">${esc(fitName(n.name, !!fam))}</text>
          <text x="${tx}" y="${p.y + 15}" class="type">${esc(n.type || "")}</text>${aimark}${badge}${chdot}${pin}</g>`);
      } else {
        const key = `stream:${n.name}`, on = hl.has(key), selected = sel === key;
        // its name beside it, away from its line (a feed's left, a product's right, as laid out)
        // and its value lines under the name, or where an explicit arrangement placed them (tval:
        // over the name, fewer, or none where others would meet them)
        const left = lay.tside && lay.tside[n.id] ? lay.tside[n.id] === "l" : n.kind === "feed", tv = lay.tval && lay.tval[n.id];
        const ls = tv ? ((vals && vals.get(n.name)) || []).filter((l) => tv.vk.includes(l.k)) : (vals && vals.get(n.name)) || [];
        const vy = tv ? tv.vy : p.y + 18, over = ls.length > 0 && vy < p.y;
        const reach = 12 + Math.max(textWidth(n.name), ...ls.map((l) => lineW(l)));
        grow(left ? p.x - reach : p.x - 7, over ? vy - 9 : p.y - 9, left ? p.x + 7 : p.x + reach, over ? p.y + 9 : p.y + 9 + LINE * ls.length);
        const vt = valText(p.x + (left ? -12 : 12), vy, left ? "end" : "start", ls);
        // changes not seen yet: a small dot beside its name, on the side away from its end
        const cm = chOf("stream", n.name), pm = pinOf("stream", n.name), tw = cm || pm ? textWidth(n.name) : 0;
        const dot = cm ? chDot(left ? p.x - 12 - tw - 7 : p.x + 12 + tw + 7, p.y, cm, false) : "";
        if (cm) chgs.push({ kind: "stream", name: n.name, actor: cm.actor, box: { x0: left ? p.x - 24 - tw : p.x - 7, y0: p.y - 9, x1: left ? p.x + 7 : p.x + 24 + tw, y1: p.y + 9 } });
        // annotations: their marker beyond the name (and beyond its dot), the tail towards it
        const pdx = 12 + tw + (cm ? 14 : 0) + 17, pin = pm ? pinMark(left ? p.x - pdx : p.x + pdx, p.y, pm, left ? 0 : 180) : "";
        if (pm) {
          grow(left ? p.x - pdx - 9 : p.x, p.y - 9, left ? p.x : p.x + pdx + 9, p.y + 9);
          const mx = left ? p.x - pdx : p.x + pdx;
          pinned.push({ kind: "stream", name: n.name, n: Number(pm.n) || 0, box: { x0: mx - 12, y0: p.y - 6, x1: mx + 12, y1: p.y + 6 } });
        }
        parts.push(() => `<g class="fs-term${on ? " hl" : ""}${selected ? " sel" : ""}" data-kind="stream" data-name="${esc(n.name)}" data-node="${esc(n.id)}">
          <circle cx="${p.x}" cy="${p.y}" r="7"/>
          <text x="${p.x + (left ? -12 : 12)}" y="${p.y + 4}" class="term" text-anchor="${left ? "end" : "start"}">${esc(n.name)}</text>
          ${vt()}${dot}${pin}</g>`);
        anchor[key] = { x: p.x, y: over ? vy - 22 : p.y - 22, at: n.id };   // (a request's bubble over its values too)
        if (FW) {                                  // (a small flow's value: under the name, or beyond it)
          const dx = 18 + textWidth(n.name) + (cm ? 14 : 0) + (pm ? 24 : 0);   // (beyond the name, its dot and marker)
          if (ls.length) fwVal(n.name, left ? p.x - dx : p.x + dx, p.y + 4, left ? "end" : "start", ls);
          else fwVal(n.name, p.x + (left ? -12 : 12), vy, left ? "end" : "start", ls);
        }
        if (v.effects) {
          const nw = textWidth(n.name);
          names.push({ x0: left ? p.x - 12 - nw : p.x + 12, y0: p.y - 7, x1: left ? p.x - 12 : p.x + 12 + nw, y1: p.y + 7 });
        }
      }
    });
    if (fwv.length) parts.push(`<g class="fs-band-v">${fwv.join("")}</g>`);
    // heat integration: a plan's exchanger matches as dashed arcs from the hot stream's block
    // to the cold one's (a condenser at the top edge, a reboiler at the bottom), and the
    // heating or cooling utility each block still needs. Each carries its index in the plan
    // (data-heat, data-util) for the plan card; heatBox is what they take, with their blocks,
    // and heatParts each one's (FS.frameHeat: the most of a plan that reads at once).
    let hb = null;
    const heatParts = { links: [], utils: [] };
    const take = (x0, y0, x1, y1) => { hb = join(hb, { x0, y0, x1, y1 }); };
    // (a block's half sizes: its box, or its symbol's frame in the icon view)
    const half = (id) => (IC && dimOf(id) ? [GEO.node[id].hw, GEO.node[id].hh] : [BW / 2, BH / 2]);
    const blockBox = (p, id) => { const [hw, hh] = half(id), b = { x0: p.x - hw, y0: p.y - hh, x1: p.x + hw, y1: p.y + hh }; take(b.x0, b.y0, b.x1, b.y1); return b; };
    if (v.heat) {
      // under the blocks when a reboiler is involved and no condenser, so the arc does not
      // cross a block; a heater's end follows the arc
      const at = (w, down) => {
        const id = w && "B:" + w.block, p = w && lay.pos[id];
        const low = w && (w.part === "reb" || (w.part !== "cond" && down));
        return p ? { x: p.x, y: low ? p.y + half(id)[1] : p.y - half(id)[1], p, id } : null;
      };
      v.heat.links.forEach((l, i) => {
        const parts2 = [l.a && l.a.part, l.b && l.b.part];
        const down = parts2.includes("reb") && !parts2.includes("cond");
        const a = at(l.a, down), b = at(l.b, down);
        if (!a || !b) return;
        const lift = 46 + Math.abs(a.x - b.x) * 0.12;
        const cx = (a.x + b.x) / 2, cy = down ? Math.max(a.y, b.y) + lift : Math.min(a.y, b.y) - lift;
        const lx = (a.x + 2 * cx + b.x) / 4, ly = (a.y + 2 * cy + b.y) / 4, text = `${fmt(l.duty)} kW`;
        const arc = { x0: Math.min(a.x, b.x), y0: Math.min(a.y, b.y, ly - 20), x1: Math.max(a.x, b.x), y1: Math.max(a.y, b.y, ly + 20) };
        grow(arc.x0, arc.y0, arc.x1, arc.y1);
        take(arc.x0, arc.y0, arc.x1, arc.y1);
        const ends = join(blockBox(a.p, a.id), blockBox(b.p, b.id));
        heatParts.links.push({ i, box: join(arc, ends), ends });
        parts.push(`<g class="fs-heat${l.split ? " split" : ""}" data-heat="${i}" data-on="${esc(`B:${l.a.block}|B:${l.b.block}`)}"><title>${esc(`${l.hot} → ${l.cold}: ${text}`)}</title>
          <path d="M${a.x},${a.y} Q${cx},${cy} ${b.x},${b.y}" marker-end="url(#arr-heat)"/><circle cx="${a.x}" cy="${a.y}" r="3.5"/>
          <text x="${lx}" y="${ly + (down ? 16 : -7)}">${esc(text)}</text></g>`);
      });
      v.heat.utils.forEach((u, i) => {
        const id = u.block && "B:" + u.block, p = id && lay.pos[id];
        if (!p) return;
        const text = `${u.heating ? "+" : "−"}${fmt(u.duty)} kW`, w = textWidth(text, F.util) + 14;
        let x = p.x + BW / 2 - w + 8, y = u.part === "reb" ? p.y + BH / 2 + 4 : p.y - BH / 2 - 20;
        if (IC && dimOf(id)) {
          // the icon view: over the symbol, clear of the badge row when one shows; a reboiler's
          // under the block's name
          // (about the symbol's ink, as the marks are; clear of the changes' dot at its top left:
          // a narrow symbol's pill would reach over it, so it starts right of it)
          const ib = GEO.node[id].box, nm = lay.names && lay.names[id], marked = !!status[u.block] || hl.has(`block:${u.block}`);
          x = p.x + ib.x1 - w + 8;
          if (chOf("block", u.block) && u.part !== "reb") x = Math.max(x, p.x + ib.x0 + 8);
          y = u.part === "reb" ? Math.max(p.y + ib.y1, nm && nm.side === "d" ? nm.box.y1 : -Infinity) + 4 : p.y + ib.y0 - (marked ? 32 : 20);
        }
        grow(x, y, x + w, y + 16);
        take(x, y, x + w, y + 16);
        heatParts.utils.push({ i, box: join({ x0: x, y0: y, x1: x + w, y1: y + 16 }, blockBox(p, id)) });
        parts.push(`<g class="fs-util ${u.heating ? "heat" : "cool"}" data-util="${i}" data-on="${esc(`B:${u.block}`)}"><title>${esc(`${u.name}: ${I18N.t(u.heating ? "hi_heat" : "hi_cool", fmt(u.duty))}`)}</title>
          <rect x="${x}" y="${y}" width="${w}" height="16" rx="8"/><text x="${x + w / 2}" y="${y + 12}">${esc(text)}</text></g>`);
      });
    }
    // requests to the AI: speech bubbles over their target, the nearest one pointing at it;
    // the dot says where each stands (waiting for the AI, answered). A done request is not
    // drawn: it stays in the AI chat. A bubble shows the request's first 40 characters on
    // one line, the whole of it in its tooltip; a click finds it in the AI chat. It stays
    // inside the drawing (a feed at its left edge gets a bubble reaching right), its tail on
    // the target.
    const stack = {}, xMax = Math.max(lay.width, 400), xMin = lay.x0 || 0;
    // (a request about a change or a field hangs on its block or stream; one about a change
    // group or a program step has no place here)
    (v.notes || []).forEach((note) => {
      if (note.status === "done") return;
      const t = note.target || {}, kind = t.kind === "change" || t.kind === "field" ? t.obj : t.kind;
      const key = `${kind}:${t.name}`, a = anchor[key];
      if (!a) return;
      const k = (stack[key] = (stack[key] || 0) + 1);
      const line = [...String(note.text).replace(/\s+/g, " ").trim()];
      const text = line.length > 40 ? line.slice(0, 39).join("").trimEnd() + "…" : line.join("");
      const h = 24, r = 12, w = Math.max(64, 34 + textWidth(text, F.note));
      const tip = k === 1 ? 6 : 0, y0 = a.y - 10 - (h + 6) * k;
      const x0 = Math.min(a.x - r - tip, Math.max(a.x - w + r + tip, Math.min(xMax - w - 4, Math.max(xMin + 4, a.x - w / 2))));
      const cls = note.reply ? "replied" : "open";
      grow(x0, y0, x0 + w, y0 + h + tip);
      bubbles.push({ x0, y0, x1: x0 + w, y1: y0 + h + tip, ax: a.x, ay: a.y });
      items.push({ kind: "note", name: note.id, x0, y0, x1: x0 + w, y1: y0 + h });
      const shape = `M${x0 + r},${y0} H${x0 + w - r} A${r},${r} 0 0 1 ${x0 + w - r},${y0 + h}`
        + (tip ? ` H${a.x + tip} L${a.x},${y0 + h + tip} L${a.x - tip},${y0 + h}` : "")
        + ` H${x0 + r} A${r},${r} 0 0 1 ${x0 + r},${y0} Z`;
      // (what it hangs on: a node, which a drag moves it with, or a stream's label, which a drag hides)
      const on = a.at ? ` data-at="${esc(a.at)}"` : a.lbl ? ` data-lbl="${esc(a.lbl)}"` : "";
      parts.push(`<g class="fs-note ${cls}" data-note="${esc(note.id)}"${on}><title>${esc(String(note.text).slice(0, 600))}</title>
        <path class="bubble" d="${shape}"/><circle class="state" cx="${x0 + 13}" cy="${y0 + h / 2}" r="4"/>
        <text x="${x0 + 23}" y="${y0 + h / 2 + 4}">${esc(text)}</text></g>`);
    });
    // the preview's tags (fs-tag2): what the steps set, one paper slip an object, over
    // it (its anchor, as a request's bubble hangs), at most TAG2_MAX; one that would meet a bubble
    // or another tag goes up past it. Each line is parts {t, c}: c "g" the group's number, "o" a
    // value now, "n" the value proposed, "m" the goal's mark, "" plain. A run's result tags
    // (v.effects) are drawn the same way when no preview shows: no group, no mark
    // but the goal's, a tooltip on each line (tg.tips)
    const T2 = PV && Array.isArray(pvIn.tags) ? { cls: pvIn.gc ? "gcv" : "pv", tags: pvIn.tags }
      : !PV && v.effects && Array.isArray(v.effects.tags) && v.effects.tags.length ? { cls: "fx", tags: v.effects.tags } : null;
    // (a run's result tags are placed here but drawn as glass over the SVG: fxLayer)
    const fxOut = T2 && T2.cls === "fx" ? [] : null, fxMoved = fxOut && v.effects.moved ? v.effects.moved : {};
    if (T2) {
      // (a result tag keeps off the streams' names too: the tag must not hide which line is which)
      const taken = bubbles.map((u) => ({ x0: u.x0, y0: u.y0, x1: u.x1, y1: u.y1 })).concat(T2.cls === "fx" ? names : []);
      const meets = (b) => taken.find((u) => u.x0 < b.x1 + 3 && b.x0 < u.x1 + 3 && u.y0 < b.y1 + 3 && b.y0 < u.y1 + 3);
      let h = "";
      T2.tags.slice(0, TAG2_MAX).forEach((tg) => {
        const a = tg && Array.isArray(tg.lines) && tg.lines.length ? anchor[tg.key] || pvAnchor[tg.key] : null;
        if (!a) return;
        const wOf = (seg) => textWidth(seg.t, seg.c === "n" || seg.c === "g" ? F.tagB : F.tag);
        const MK = 3;                                  // (air after the goal's mark)
        const isMk = (ln) => !!ln[0] && ln[0].c === "m";
        const w = Math.max(...tg.lines.map((ln) => ln.reduce((s, seg) => s + wOf(seg), 0) + (isMk(ln) ? MK : 0))) + 16, hh = 8 + 15 * tg.lines.length;
        let b = { x0: a.x - w / 2, y0: a.y + 4 - hh, x1: a.x + w / 2, y1: a.y + 4 };
        // (a result tag first slides aside, past what it meets, as long as it still spans its
        // anchor: gone up past another stream's name it would read as that stream's)
        const hit = T2.cls === "fx" && meets(b);
        if (hit) {
          for (const dx of [hit.x1 + 4 - b.x0, hit.x0 - 4 - b.x1]) {
            const c = { x0: b.x0 + dx, y0: b.y0, x1: b.x1 + dx, y1: b.y1 };
            if (c.x0 + 8 <= a.x && a.x <= c.x1 - 8 && !meets(c)) { b = c; break; }
          }
        }
        for (let i = 0, u; i < 8 && (u = meets(b)); i++) { b.y1 = u.y0 - 4; b.y0 = b.y1 - hh; }
        taken.push(b);
        grow(b.x0, b.y0, b.x1, b.y1);
        const rx = tg.lines.length === 1 ? hh / 2 : 9;
        if (fxOut) {
          const o = Array.isArray(fxMoved[tg.key]) ? fxMoved[tg.key] : null;   // (moved by the user: FS.onTag's "move")
          if (o) grow(b.x0 + o[0], b.y0 + o[1], b.x1 + o[0], b.y1 + o[1]);
          fxOut.push({ key: tg.key, b, w, hh, rx, a: { x: a.x, y: a.y }, lines: tg.lines, tips: tg.tips, tip: tg.tip,
                       mkw: textWidth("◎ ", F.tag) + MK, mc: textWidth("◎", F.tag) / 2 });
          return;
        }
        const lt = (i) => (Array.isArray(tg.tips) && tg.tips[i] ? `<title>${esc(tg.tips[i])}</title>` : "");
        // (the goal's ◎: its glyph keeps the room and the text, two circles draw it -- a font's ◎ reads as a dot)
        const mark = (ln, y) => {
          if (!isMk(ln)) return "";
          const cx = b.x0 + 8 + textWidth(ln[0].t.trimEnd(), F.tag) / 2, cy = y - 4;
          return `<circle class="t2mk" cx="${cx}" cy="${cy}" r="4.3"/><circle class="t2mk d" cx="${cx}" cy="${cy}" r="1.6"/>`;
        };
        h += `<g class="fs-tag2 ${T2.cls}" data-tag="${esc(tg.key)}"${tg.g != null ? ` data-g="${esc(tg.g)}"` : ""}>`
          + (tg.tip ? `<title>${esc(tg.tip)}</title>` : "")
          + `<rect x="${b.x0}" y="${b.y0}" width="${w}" height="${hh}" rx="${rx}"/>`
          + tg.lines.map((ln, i) => `<text x="${b.x0 + 8}" y="${b.y0 + 15 + 15 * i}"${lt(i) ? ` data-i="${i}"` : ""}>${lt(i)}`
            + ln.map((seg, j) => `<tspan${seg.c ? ` class="t2${seg.c}"` : ""}${j === 1 && isMk(ln) ? ` dx="${MK}"` : ""}>${esc(seg.t)}</tspan>`).join("") + `</text>`
            + mark(ln, b.y0 + 15 + 15 * i)).join("") + `</g>`;
      });
      if (h) parts.push(`<g class="fs-tags2">${h}</g>`);
    }
    // (the same drawing as before -- a state push that changed nothing drawn -- keeps its elements: no
    // flicker, nothing under the pointer replaced; the marks below are put on again either way)
    const html = parts.map((p) => (typeof p === "function" ? p() : p)).join("");
    if (svg._fsHtml !== html || !svg.firstChild) { svg.innerHTML = html; svg._fsHtml = html; }
    else svg.querySelectorAll(".pv-gone, .pv-tagged").forEach((el) => el.classList.remove("pv-gone", "pv-tagged"));
    // (the preview's states on what is drawn: removed, moved away (the old line and end), tagged
    // (a tagged stream's value lines give way), out of date; FIG_STATE takes them off a figure)
    if (PV) {
      PV.gone.forEach((k) => { if (pvIs(k)) markEls(svg, k).forEach((el) => el.classList.add("pv-gone")); });
      PV.was.forEach((k) => { if (pvIs(k)) markEls(svg, k).forEach((el) => { if (el.classList.contains("fs-edge") || el.classList.contains("fs-term")) el.classList.add("pv-gone"); }); });
    }
    // (a tagged stream's value lines give way to its tag: the preview's and the result tags alike;
    // its small flow's value too, the flow width layer's -- the tag says the stream's story)
    if (T2) T2.tags.slice(0, TAG2_MAX).forEach((tg) => {
      if (!tg || !String(tg.key).startsWith("stream:")) return;
      markEls(svg, tg.key).forEach((el) => { if (!el.classList.contains("fs-edge")) el.classList.add("pv-tagged"); });
      if (fwv.length) svg.querySelectorAll(`g.fs-band-v text[data-s="${CSS.escape(String(tg.key).slice(7))}"]`).forEach((el) => el.classList.add("pv-tagged"));
    });
    svg.classList.toggle("pv-stale", !!(PV && pvIn.stale));
    c.pvItems = PV && pvIn.gc ? [] : pvItems;      // (a run by group's: not a preview; its pause brings it in view)
    c.pvShown = !!PV;
    pvHotOn(svg);
    svg.classList.toggle("stale", !!(v.stale && vals));
    svg.classList.toggle("fw", !!FW);
    Object.keys(c.marks || {}).forEach((cls) => markOn(svg, cls));   // marks stay across a redraw
    hotOn(svg, svg._fsHot);                        // and so does the stream under the pointer
    c.box = isFinite(box.x0) ? box : { x0: 0, y0: 0, x1: lay.width, y1: lay.height };
    c.tops = tops;
    c.items = items;
    c.chgs = chgs;
    c.pins = pinned;
    c.heatBox = hb;
    c.heatParts = hb ? heatParts : null;
    c.bubbles = bubbles;
    c.names = lay.names || null;
    c.hl = [...hl];                                // the AI's marks: counted beyond an edge (FS.offscreen)
    c.fx = fxOut && fxOut.length ? { tags: fxOut, moved: Object.assign({}, fxMoved), xtip: v.effects.xtip || "" } : null;
    fxLayer(svg);                                  // the result tags, glass over the drawing (kept, not made anew)
    causeWords(svg);                               // a result's causal path's words stay too (FS.cause)
    if (edge && c.view) {                          // a view that began at the drawing's left or top still does
      if (edge.x !== null) c.view.x = c.box.x0 - edge.x;
      if (edge.y !== null) c.view.y = c.box.y0 - edge.y;
    }
    // a fitted view of a drawing that held nothing (a new model's empty flowsheet) is fitted again once it
    // holds something -- a proposal's preview counts as the drawing, as its blocks do
    const empty = !items.length && !c.pvItems.length;
    if (!fitNow && c.fitted && c.empty && !empty) refit = true;
    c.empty = empty;
    if (fitNow) FS.fit(svg, false);
    else if (refit) FS.fit(svg);
    else if (c.view) apply(svg);
    moved(svg);                                   // what lies off screen may have changed
  }

  /** The same flowsheet laid out again (the Values layer spreads it): the view moves with the
   *  block or terminal that was nearest its middle, at the same scale, so what the user was
   *  looking at stays in place (a view that showed the drawing's left or top edge keeps
   *  showing it there: FS.render); less far down where a block or terminal that showed clear
   *  of the toolbar (bar: its height, drawing units) would slide under it. */
  function keepPlace(c, old, bar) {
    const v = c.view;
    if (!v) return;
    const cx = v.x + v.w / 2, cy = v.y + v.h / 2, both = (k) => old.nodes.get(k).kind !== "dummy" && old.pos[k] && c.lay.pos[k];
    let best = null, bd = Infinity;
    old.nodes.forEach((n, k) => {
      if (!both(k)) return;
      const d = Math.hypot(old.pos[k].x - cx, old.pos[k].y - cy);
      if (d < bd) { bd = d; best = k; }
    });
    if (!best) return;
    const nv = Object.assign({}, v, { x: v.x + c.lay.pos[best].x - old.pos[best].x, y: v.y + c.lay.pos[best].y - old.pos[best].y });
    const top = (lay, k) => lay.pos[k].y - halfH(lay.nodes.get(k)) - (lay.nodes.get(k).kind === "block" ? 8 : 2);
    const inX = (p, w) => p.x >= w.x && p.x <= w.x + w.w;
    let lift = 0;
    old.nodes.forEach((n, k) => {
      if (!both(k) || !inX(old.pos[k], v) || !inX(c.lay.pos[k], nv)) return;
      const was = top(old, k) - v.y, now = top(c.lay, k) - nv.y;
      if (was >= bar && was < v.h && now < bar) lift = Math.max(lift, bar - now);
    });
    nv.y -= lift;
    c.view = nv;
  }

  /** Mark things on the drawing with a class, at once (nothing inside the SVG fades or moves):
   *  keys are "block:NAME", "stream:NAME" (its line, label and end), or "heat:i" / "util:i" (a
   *  heat plan's exchanger or utility); none clears. Kept in the view's context, so a redraw
   *  keeps them. */
  FS.mark = function (svg, keys, cls) {
    const c = C(svg);
    c.marks = Object.assign({}, c.marks, { [cls]: (keys || []).slice() });
    markOn(svg, cls);
  };
  function markEls(svg, key) {
    const i = key.indexOf(":"), kind = key.slice(0, i), name = key.slice(i + 1);
    if (kind === "heat" || kind === "util") return [...svg.querySelectorAll(`[data-${kind}="${CSS.escape(name)}"]`)];
    return [...svg.querySelectorAll("[data-kind]")].filter((el) => el.getAttribute("data-kind") === kind && el.getAttribute("data-name") === name);
  }
  function markOn(svg, cls) {
    svg.querySelectorAll(`.${cls}`).forEach((el) => el.classList.remove(cls));
    ((C(svg).marks || {})[cls] || []).forEach((k) => markEls(svg, k).forEach((el) => el.classList.add(cls)));
  }

  /** A result's causal path (app-effects.js): ``spec`` {keys: what is marked
   *  "cause" -- the streams on the path (their line in the accent), or with no path the objects at
   *  its ends --, words: [{key, t, c: "m" (measured) | "ai"}], each a small glass chip by its object
   *  (causeWords, in the result tags' layer), pin: {tag (a result tag's key, "stream:NAME"), tip (the
   *  ×'s tooltip)}: that tag shown pinned (.pinned), its × showing (fxLayer)}; null clears. Kept in
   *  the view's context: a redraw, a pan or a zoom keeps it; a figure drops it (outside the SVG, and
   *  FIG_STATE). No ``spec`` (undefined): the one the shown view has, or null. */
  FS.cause = function (svg, spec) {
    if (spec === undefined) return C(svg).cause || null;
    const c = C(svg), on = !!spec && ((spec.keys || []).length || (spec.words || []).length);
    c.cause = on ? spec : null;
    FS.mark(svg, on ? spec.keys || [] : [], "cause");
    causeWords(svg);
    fxPin(svg);
  };

  // ------------------------------------------------------------------ the result tags, in glass
  // A run's result tags (FS.render's v.effects, placed by draw as the preview's are: c.fx) are HTML
  // glass over the SVG -- div.fs-fx right after it, since backdrop-filter does nothing inside an SVG
  // -- with the causal path's words (causeWords). One plane holds them all in drawing units: a pan
  // or a zoom sets its transform and nothing else (fxPlace, from apply). Each tag is kept across
  // redraws by its key: its lines rewritten only when they change, its × one element throughout, so
  // a press never lands on something a state push replaced. On a tag: a press that moves FX_DRAG px
  // drags it -- a thin leader line back to its object while it is away -- and its drop calls FS.onTag's
  // fn(key, el, ev, "move", [dx, dy]) (drawing units from where it was placed; FS.render's
  // v.effects.moved puts it back there); one that does not move is a click: fn(key, el, ev, "line").
  // Its × (on hover, and while its path is pinned) calls fn(key, el, ev, "x") when the press is let
  // go over it (the press is captured: nothing under it, the drawing's pan or the background's
  // click, hears it), or on Enter. The wheel over a tag zooms the drawing. Never in a figure.
  const FX_DRAG = 4;
  const fxOff = (c, key) => { const o = c.fx && c.fx.moved[key]; return Array.isArray(o) ? o : [0, 0]; };
  function fxHost(svg) {
    if (svg._fxL) return svg._fxL;
    const root = document.createElement("div");
    root.className = "fs-fx";
    root.hidden = true;
    root.innerHTML = '<div class="fx-plane"><svg class="fx-lead" aria-hidden="true"></svg><div class="fx-ws"></div></div>';
    root.style.font = F.tag;
    svg.after(root);
    const L = svg._fxL = { root, plane: root.firstChild, lead: root.querySelector(".fx-lead"), ws: root.querySelector(".fx-ws"),
                           els: new Map(), press: null, k: 0 };
    wireFx(svg, L);
    return L;
  }
  function fxLayer(svg) {
    const c = C(svg), X = c.fx;
    let L = svg._fxL;
    if (!X) {
      if (L) {
        if (L.press && L.press.frame) cancelAnimationFrame(L.press.frame);
        L.press = null;
        L.els.forEach((el) => el.remove());
        L.els.clear();
        L.lead.innerHTML = "";
        L.ws.innerHTML = "";
        L.root.hidden = true;
      }
      return;
    }
    L = fxHost(svg);
    L.root.hidden = false;
    const keep = new Set();
    X.tags.forEach((tg) => {
      keep.add(tg.key);
      let el = L.els.get(tg.key);
      if (!el) {
        el = document.createElement("div");
        el.className = "fs-tag2 fx plate";
        el.dataset.tag = tg.key;
        el.innerHTML = '<div class="t2ls"></div><button type="button" class="t2x"><i><svg viewBox="-6 -6 12 12" aria-hidden="true">'
          + '<path d="M-2.6,-2.6L2.6,2.6M2.6,-2.6L-2.6,2.6"/></svg></i></button>';
        L.plane.insertBefore(el, L.ws);
        L.els.set(tg.key, el);
      }
      const sig = JSON.stringify([tg.lines, tg.tips, tg.tip, tg.w, tg.hh, tg.rx]);
      if (el._sig !== sig) {                       // (rewritten only when it reads otherwise)
        el._sig = sig;
        el.querySelector(".t2ls").innerHTML = tg.lines.map((ln, i) => `<div class="t2l" data-i="${i}"`
          + `${Array.isArray(tg.tips) && tg.tips[i] ? ` title="${esc(tg.tips[i])}"` : ""}>`
          + ln.map((seg, j) => (j === 0 && seg.c === "m" ? `<span class="t2mk" style="width:${tg.mkw}px;--c:${tg.mc}px"></span>`
            : `<span${seg.c ? ` class="t2${seg.c}"` : ""}>${esc(seg.t)}</span>`)).join("") + "</div>").join("");
        Object.assign(el.style, { width: `${tg.w}px`, height: `${tg.hh}px`, borderRadius: `${tg.rx}px` });
        if (tg.tip) el.title = tg.tip;
        else el.removeAttribute("title");
      }
      el._fx = tg;
      if (!(L.press && L.press.el === el && L.press.drag)) fxAt(L, tg, fxOff(c, tg.key));   // (one being dragged stays under the pointer)
    });
    L.els.forEach((el, k) => {
      if (keep.has(k)) return;
      if (L.press && L.press.el === el) L.press = null;
      el.remove();
      L.els.delete(k);
    });
    let prev = L.lead;                             // (in the run's order: the goal's first)
    X.tags.forEach((tg) => {
      const el = L.els.get(tg.key);
      if (el.previousElementSibling !== prev) L.plane.insertBefore(el, prev.nextSibling);
      prev = el;
    });
    fxLeads(svg, L.press && L.press.drag ? L.press : null);
    fxPin(svg);
    fxPlace(svg);
  }
  function fxAt(L, tg, o) {
    const el = L.els.get(tg.key);
    if (!el) return;
    el.style.transform = `translate(${tg.b.x0 + o[0]}px, ${tg.b.y0 + o[1]}px)`;
    el.classList.toggle("moved", !!(o[0] || o[1]));
  }
  /** A moved tag's leader: from its nearest edge to a dot over its object (where it hung), unless
   *  it still lies by it. ``drag``: the press under way ({el, o}), drawn where it is now. */
  function fxLeads(svg, drag) {
    const c = C(svg), L = svg._fxL;
    if (!L) return;
    let h = "";
    (c.fx ? c.fx.tags : []).forEach((tg) => {
      const o = drag && drag.el && drag.el.dataset.tag === tg.key && drag.o ? drag.o : fxOff(c, tg.key);
      if (!o[0] && !o[1]) return;
      const x0 = tg.b.x0 + o[0], y0 = tg.b.y0 + o[1], x1 = x0 + tg.w, y1 = y0 + tg.hh, px = tg.a.x, py = tg.a.y + 4;
      const qx = Math.min(Math.max(px, x0 + 4), x1 - 4), qy = Math.min(Math.max(py, y0), y1);
      if (Math.hypot(px - qx, py - qy) < 8) return;
      h += `<line data-tag="${esc(tg.key)}" x1="${qx}" y1="${qy}" x2="${px}" y2="${py}"/><circle cx="${px}" cy="${py}" r="2.2"/>`;
    });
    L.lead.innerHTML = h;
  }
  /** The pinned path's tag (FS.cause's spec.pin): .pinned, its × showing and saying it closes the
   *  path; the others' × close the tag itself (c.fx.xtip). */
  function fxPin(svg) {
    const L = svg._fxL, c = C(svg);
    if (!L) return;
    const p = c.cause && c.cause.pin, key = p ? p.tag : null;
    L.els.forEach((el, k) => {
      const on = k === key, x = el.querySelector(".t2x"), tip = on ? p.tip || "" : (c.fx && c.fx.xtip) || "";
      el.classList.toggle("pinned", on);
      if (x.title !== tip) { x.title = tip; x.setAttribute("aria-label", tip); }
    });
  }
  /** The plane where the view puts the drawing: a transform only (every pan and zoom: apply). */
  function fxPlace(svg) {
    const L = svg._fxL, c = C(svg), v = c.view, px = c.px;
    if (!L || L.root.hidden || !v || !px || !px.w || !v.w || !v.h) return;
    const k = Math.min(px.w / v.w, px.h / v.h), ox = (px.w - v.w * k) / 2, oy = (px.h - v.h * k) / 2;
    L.plane.style.transform = `translate(${ox - v.x * k}px, ${oy - v.y * k}px) scale(${k})`;
    if (L.k !== k) { L.k = k; L.plane.style.setProperty("--k", String(k)); }
  }
  /** Whether result tags show over this SVG (walk.js: Esc is theirs first). */
  FS.fxShown = (svg) => !!(svg && svg._fxL && svg._fxL.els.size);
  function wireFx(svg, L) {
    const R = L.root;
    const fire = (el, ev, part, o) => {
      const fn = svg._fsTags && svg._fsTags.fx;
      if (fn && el && el.isConnected) fn(el.dataset.tag, el, ev, part, o);
    };
    R.addEventListener("pointerdown", (ev) => {
      const el = ev.target.closest && ev.target.closest(".fs-tag2");
      if (!el || ev.button !== 0) return;
      ev.stopPropagation();
      const x = ev.target.closest(".t2x");
      try { (x || el).setPointerCapture(ev.pointerId); } catch (e) { /* (a synthetic pointer) */ }
      L.press = { el, x: !!x, id: ev.pointerId, cx: ev.clientX, cy: ev.clientY, o0: fxOff(C(svg), el.dataset.tag).slice(), o: null, drag: false, frame: 0 };
    });
    R.addEventListener("pointermove", (ev) => {
      const p = L.press;
      if (!p || p.id !== ev.pointerId || p.x) return;
      const dx = ev.clientX - p.cx, dy = ev.clientY - p.cy;
      if (!p.drag) {
        if (Math.hypot(dx, dy) <= FX_DRAG) return;
        p.drag = true;
        p.el.classList.add("drag");
      }
      const k = L.k || 1;
      p.o = [p.o0[0] + dx / k, p.o0[1] + dy / k];
      if (!p.frame) p.frame = requestAnimationFrame(() => {
        p.frame = 0;
        if (L.press !== p || !p.el._fx) return;
        fxAt(L, p.el._fx, p.o);
        fxLeads(svg, p);
      });
    });
    const end = (ev, cancel) => {
      const p = L.press;
      if (!p || p.id !== ev.pointerId) return;
      L.press = null;
      if (p.frame) cancelAnimationFrame(p.frame);
      p.el.classList.remove("drag");
      ev.stopPropagation();
      const c = C(svg), tg = p.el._fx;
      if (p.x) {                                   // (let go over the ×: it closes; dragged off it: nothing)
        const r = p.el.querySelector(".t2x").getBoundingClientRect();
        if (!cancel && ev.clientX >= r.left - 1 && ev.clientX <= r.right + 1 && ev.clientY >= r.top - 1 && ev.clientY <= r.bottom + 1) fire(p.el, ev, "x");
        return;
      }
      if (p.drag && tg) {
        const o = cancel || !p.o ? p.o0 : p.o.map((n) => Math.round(n * 10) / 10);
        if (c.fx) c.fx.moved[tg.key] = o;
        fxAt(L, tg, o);
        fxLeads(svg);
        if (c.cause && (c.cause.words || []).length) causeWords(svg);   // (the words keep clear of it where it is now)
        if (!cancel) fire(p.el, ev, "move", o);
        return;
      }
      if (!cancel) fire(p.el, ev, "line");
    };
    R.addEventListener("pointerup", (ev) => end(ev, false));
    R.addEventListener("pointercancel", (ev) => end(ev, true));
    // the click that follows a press was handled at its release; Enter or Space on the × has none
    R.addEventListener("click", (ev) => {
      if (!ev.target.closest || !ev.target.closest(".fs-tag2")) return;
      ev.stopPropagation();
      const x = ev.target.closest(".t2x");
      if (x && ev.detail === 0) fire(x.closest(".fs-tag2"), ev, "x");
    });
    R.addEventListener("dblclick", (ev) => ev.stopPropagation());
    R.addEventListener("wheel", (ev) => {          // (over a tag the wheel zooms the drawing, as anywhere on it)
      ev.preventDefault();
      svg.dispatchEvent(new WheelEvent("wheel", { deltaX: ev.deltaX, deltaY: ev.deltaY, deltaMode: ev.deltaMode,
        clientX: ev.clientX, clientY: ev.clientY, ctrlKey: ev.ctrlKey, bubbles: true, cancelable: true }));
    }, { passive: false });
  }
  /** Where a word may go by its object, the first choice first ({x, y, ta, dy}: dy the way a
   *  second word on it steps): a stream over its name -- over its values where they are drawn over
   *  it --, else by its longest stretch (a feed's or product's only there); a block under, over,
   *  beside its symbol. */
  function causeSpots(svg, c, key) {
    const i = key.indexOf(":"), kind = key.slice(0, i), name = key.slice(i + 1), lay = c.lay;
    if (kind === "block") {
      const it = (c.items || []).find((x) => x.kind === "block" && x.name === name);
      if (!it) return [];
      const cx = (it.x0 + it.x1) / 2, cy = (it.y0 + it.y1) / 2;
      return [{ x: cx, y: it.y1 + 14, ta: "middle", dy: 17 }, { x: cx, y: it.y0 - 6, ta: "middle", dy: -17 },
              { x: it.x1 + 6, y: cy + 4, ta: "start", dy: 17 }, { x: it.x0 - 6, y: cy + 4, ta: "end", dy: 17 }];
    }
    const j = lay ? lay.edges.findIndex((e) => e.name === name) : -1, g = j >= 0 ? lay.geo[j] : null;
    if (!g) return [];
    const e = lay.edges[j], na = lay.nodes.get(e.a), nb = lay.nodes.get(e.b), out = [];
    if (!(na && na.kind === "feed") && !(nb && nb.kind === "prod") && isFinite(g.lx)) {
      let top = g.ly;
      const tg = [...svg.querySelectorAll('.fs-tag[data-kind="stream"]')].find((el) => el.getAttribute("data-name") === name);
      if (tg) tg.querySelectorAll(":scope > text").forEach((el) => { const y = Number(el.getAttribute("y")); if (isFinite(y)) top = Math.min(top, y); });
      out.push({ x: g.lx, y: top - 15, ta: g.anchor || "middle", dy: -17 });
    }
    const pts = g.pts || [];
    let best = null, bl = -1;
    for (let k = 1; k < pts.length; k++) {
      const l = Math.hypot(pts[k].x - pts[k - 1].x, pts[k].y - pts[k - 1].y);
      if (l > bl) { bl = l; best = [pts[k - 1], pts[k]]; }
    }
    if (best) {
      const mx = (best[0].x + best[1].x) / 2, my = (best[0].y + best[1].y) / 2;
      if (Math.abs(best[1].x - best[0].x) >= Math.abs(best[1].y - best[0].y)) out.push({ x: mx, y: my + 15, ta: "middle", dy: 17 }, { x: mx, y: my - 6, ta: "middle", dy: -17 });
      else out.push({ x: mx + 7, y: my + 4, ta: "start", dy: 17 }, { x: mx - 7, y: my + 4, ta: "end", dy: 17 });
    }
    return out;
  }
  /** The words of a lit path, each a small glass chip (in the result tags' layer: fxHost) at its
   *  object's first spot clear of the drawing's names, symbols, tags and the words before it (none
   *  clear: the first). */
  const CW_PAD = 5;
  function causeWords(svg) {
    const c = C(svg), L0 = svg._fxL;
    if (L0) L0.ws.innerHTML = "";
    if (!c.cause || !(c.cause.words || []).length || !c.lay) return;
    const taken = [];
    svg.querySelectorAll(".fs-node, .fs-tag > text, .fs-term text, .fs-tags2 rect").forEach((el) => {
      try { const b = el.getBBox(); if (b.width) taken.push({ x0: b.x, y0: b.y, x1: b.x + b.width, y1: b.y + b.height }); } catch (e) { /* (not drawn) */ }
    });
    (c.fx ? c.fx.tags : []).forEach((tg) => {        // (the result tags, where they are now)
      const o = fxOff(c, tg.key);
      taken.push({ x0: tg.b.x0 + o[0], y0: tg.b.y0 + o[1], x1: tg.b.x0 + o[0] + tg.w, y1: tg.b.y0 + o[1] + tg.hh });
    });
    const meets = (b) => taken.some((u) => u.x0 < b.x1 + 2 && b.x0 < u.x1 + 2 && u.y0 < b.y1 + 2 && b.y0 < u.y1 + 2);
    const h = c.cause.words.map((w) => {
      const tw = textWidth(w.t, F.tag) + 2 * CW_PAD, box = (s) => {
        const x0 = s.ta === "middle" ? s.x - tw / 2 : s.ta === "end" ? s.x - tw + CW_PAD : s.x - CW_PAD;
        return { x0, y0: s.y - 12, x1: x0 + tw, y1: s.y + 4 };
      };
      const spots = causeSpots(svg, c, w.key).flatMap((s) => [s, Object.assign({}, s, { y: s.y + s.dy })]);
      const at = spots.find((s) => !meets(box(s))) || spots[0];
      if (!at) return "";
      const b = box(at);
      taken.push(b);
      return `<span class="fx-w plate ${w.c === "ai" ? "ai" : "m"}" data-x="${at.x}" data-y="${at.y}" style="width:${tw}px;transform:translate(${b.x0}px, ${b.y0}px)">${esc(w.t)}</span>`;
    }).join("");
    if (!h) return;
    const L = fxHost(svg);
    L.root.hidden = false;
    L.ws.innerHTML = h;
    fxPlace(svg);
  }

  /** What floats over the drawing, in px from each edge of the SVG: the toolbar on top, the
   *  inspector on the right while it shows (all the way down: its height follows its rows,
   *  which may still be on their way), and a heat plan's card at the bottom left: its width on
   *  the left, while the drawing keeps 240 px beside it; folded to its row (a short card, or
   *  little room beside the inspector), that row's height at the bottom (opened upward, it is
   *  a popover for the moment, and the row still counts); a run by group's card at the bottom
   *  (its height and the 12 px under it, unless ``bare`` -- where the card itself goes). Fit, frame, reveal, zoom and the edge hints keep clear of them. */
  FS.insets = function (svg, bare) {
    const r = svg.getBoundingClientRect(), wrap = svg.closest(".fs-wrap");
    const insp = wrap && wrap.querySelector(".insp:not(.hidden):not(.ghost)"), plan = wrap && wrap.querySelector(".fs-plan:not(.hidden)");
    const fold = plan && plan.classList.contains("fold"), head = fold && plan.querySelector(".pl-head");
    const right = insp ? Math.max(0, Math.min(insp.offsetWidth + 18, r.width - 100)) : 0;
    const left = plan && !fold ? Math.max(0, Math.min(plan.offsetWidth + 18, r.width - right - 240)) : 0;
    const top = Math.min(FS.topInset, r.height / 3);
    let bottom = head ? Math.max(0, Math.min(head.offsetHeight + 16, r.height - top - 80)) : 0;   // the row sits 10 px up
    const gc = !bare && wrap && wrap.querySelector(".gc-card:not(.hidden)");
    if (gc) bottom = Math.max(bottom, Math.min(bottom + gc.offsetHeight + 12, r.height - top - 80));
    return { top, right, bottom, left };
  };
  /** The free part of the view (the view less the insets), in drawing units. */
  function free(svg, c, r) {
    const v = c.view, k = v.w / r.width, ins = FS.insets(svg);
    return { k, x0: v.x + ins.left * k, x1: v.x + v.w - ins.right * k, y0: v.y + ins.top * k, y1: v.y + v.h - ins.bottom * k, ins };
  }

  /** Frame the drawing. whole=true (Fit, or a double-click on empty space) shows all of it,
   *  centred beside what floats over it; otherwise a drawing too large to read at once opens
   *  at a readable size from its start: the feeds, the top of what shows of it just under
   *  the toolbar (a row farther right may reach higher). The choice holds for a refit
   *  after a size change from nothing, until the next layout; a fitted view nobody has
   *  moved since (c.fitted) is fitted again when the drawing is laid out again. */
  FS.fit = function (svg, whole) {
    const c = C(svg);
    if (!c.lay) return;
    if (whole !== undefined) c.whole = whole;
    const r = svg.getBoundingClientRect(), ins = FS.insets(svg), M = 16;
    const b = c.box || { x0: 0, y0: 0, x1: c.lay.width, y1: c.lay.height };
    const w = b.x1 - b.x0 + 2 * M, h = b.y1 - b.y0 + 2 * M;
    const freeW = Math.max(r.width - ins.left - ins.right, 1), freeH = Math.max(r.height - ins.top - ins.bottom, 1);
    let k = Math.max(w / freeW, h / freeH, 1);        // drawing units per px; never larger than life
    const capped = !c.whole && k > MAX_SHRINK;
    if (capped) k = MAX_SHRINK;
    const start = capped && w > freeW * k, fx = start ? b.x0 - M : (b.x0 + b.x1 - freeW * k) / 2;
    const top = start ? (c.tops || []).reduce((m, t) => (t[0] < fx + freeW * k ? Math.min(m, t[1]) : m), Infinity) : b.y0;
    const fy = capped ? (isFinite(top) ? top : b.y0) - M : (b.y0 + b.y1 - freeH * k) / 2;
    c.view = { x: fx - ins.left * k, y: fy - ins.top * k, w: r.width * k, h: r.height * k };
    c.px = { w: r.width, h: r.height };
    c.fitted = true;                                 // until the view is moved (a relayout fits it again)
    apply(svg);
  };

  /** Frame part of the drawing (b: {x0, y0, x1, y1}, drawing units) in the free area: all of
   *  it at the scale that shows it, never larger than life nor smaller than text reads
   *  (MAX_SHRINK); one too large for that shows from its top left. At once, as every view
   *  change. keep: more room to keep clear at the top and bottom, px (the app's edge hints).
   *  FS.heatBox: what the heat plan shown takes (its arcs, utilities and blocks). */
  FS.frame = function (svg, b, keep) {
    const c = C(svg), r = svg.getBoundingClientRect();
    if (!c.lay || !b || !r.width || !r.height) return;
    const ins = kept(FS.insets(svg), keep, r), M = 24;
    const freeW = Math.max(r.width - ins.left - ins.right, 1), freeH = Math.max(r.height - ins.top - ins.bottom, 1);
    const w = b.x1 - b.x0 + 2 * M, h = b.y1 - b.y0 + 2 * M;
    const k = Math.min(MAX_SHRINK, Math.max(w / freeW, h / freeH, 1));
    const fx = w > freeW * k ? b.x0 - M : (b.x0 + b.x1 - freeW * k) / 2;
    const fy = h > freeH * k ? b.y0 - M : (b.y0 + b.y1 - freeH * k) / 2;
    c.view = { x: fx - ins.left * k, y: fy - ins.top * k, w: r.width * k, h: r.height * k };
    c.px = { w: r.width, h: r.height };
    c.fitted = false;
    apply(svg);
  };
  FS.heatBox = (svg) => C(svg).heatBox || null;

  /** Frame the heat plan shown: all of it where it reads at once (MAX_SHRINK); else the most
   *  exchangers that do, together (the one each begins from tried in turn, the card's first
   *  row first on a tie), with the utilities on their blocks where they fit too; else the
   *  first exchanger's two blocks, from its left. The request bubbles over the blocks framed
   *  come too where they fit, so none reaches under what floats over the drawing. The rest
   *  are the edge hints' and the card's rows' (a click finds an arc). */
  FS.frameHeat = function (svg, keep) {
    const c = C(svg), r = svg.getBoundingClientRect(), hp = c.heatParts;
    if (!c.lay || !hp || !r.width || !r.height) return;
    const ins = kept(FS.insets(svg), keep, r), M = 24;
    const freeW = Math.max(r.width - ins.left - ins.right, 1), freeH = Math.max(r.height - ins.top - ins.bottom, 1);
    const fits = (b) => Math.max((b.x1 - b.x0 + 2 * M) / freeW, (b.y1 - b.y0 + 2 * M) / freeH) <= MAX_SHRINK;
    const notes = (b) => {                           // a bubble's tail sits 10 units over its block
      (c.bubbles || []).forEach((u) => {
        if (u.ax < b.x0 || u.ax > b.x1 || u.ay < b.y0 - 12 || u.ay > b.y1) return;
        const x = join(b, u);
        if (fits(x)) b = x;
      });
      return b;
    };
    if (fits(c.heatBox)) { FS.frame(svg, notes(c.heatBox), keep); return; }
    const mid = (b) => [(b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2];
    let best = null;
    hp.links.forEach((l) => {
      if (!fits(l.box)) return;
      const [x, y] = mid(l.box);
      let b = l.box, n = 1;
      hp.links.filter((m) => m !== l).map((m) => ({ m, d: Math.hypot(mid(m.box)[0] - x, mid(m.box)[1] - y) })).sort((p, q) => p.d - q.d)
        .forEach(({ m }) => { const u = join(b, m.box); if (fits(u)) { b = u; n++; } });
      if (!best || n > best.n) best = { b, n };
    });
    if (best) {
      hp.utils.forEach((u) => { const x = join(best.b, u.box); if (fits(x)) best.b = x; });
      FS.frame(svg, notes(best.b), keep);
      return;
    }
    const first = hp.links[0] || hp.utils[0];
    FS.frame(svg, first ? first.ends || first.box : c.heatBox, keep);
  };
  /** Show one exchanger or utility of the heat plan shown (a plan card's row: target {kind:
   *  "heat" | "util", name: its index}) with both its blocks: nothing moves where it all shows
   *  in the free area; else the least pan where it fits there at this scale; else it is framed
   *  where it reads at once (MAX_SHRINK); else, at that scale, as much of it as fits about its
   *  duty label (a long arc's middle, its ends beyond the sides). keep: as FS.frame's.
   *  Returns null when it is not drawn, else {moved}. */
  FS.showHeat = function (svg, target, keep) {
    const c = C(svg), v = c.view, r = svg.getBoundingClientRect(), hp = c.heatParts;
    if (!v || !hp || !r.width || !r.height) return null;
    const part = (target.kind === "util" ? hp.utils : hp.links).find((p) => String(p.i) === String(target.name));
    const el = part && targetEl(svg, target);
    if (!el) return null;
    const ins = kept(FS.insets(svg), keep, r), k = v.w / r.width, M = 24, b = part.box;
    const freeW = Math.max(r.width - ins.left - ins.right, 1), freeH = Math.max(r.height - ins.top - ins.bottom, 1);
    const a = { x0: v.x + ins.left * k, x1: v.x + v.w - ins.right * k, y0: v.y + ins.top * k, y1: v.y + v.h - ins.bottom * k };
    if (b.x0 >= a.x0 && b.x1 <= a.x1 && b.y0 >= a.y0 && b.y1 <= a.y1) return { moved: false };
    const w = b.x1 - b.x0 + 2 * M, h = b.y1 - b.y0 + 2 * M;
    if (w <= freeW * k && h <= freeH * k) {
      const need = (lo, hi, p, z) => (p - M < lo ? p - M - lo : z + M > hi ? z + M - hi : 0);
      c.view = Object.assign({}, v, { x: v.x + need(a.x0, a.x1, b.x0, b.x1), y: v.y + need(a.y0, a.y1, b.y0, b.y1) });
      c.fitted = false;
      apply(svg);
    } else if (Math.max(w / freeW, h / freeH) <= MAX_SHRINK) FS.frame(svg, b, keep);
    else {
      // the most that reads at once on each axis, about the label, inside what the part takes
      const t = el.getBBox();
      const cut = (lo, hi, m, room) => {
        const half = Math.max(room / 2 - M, 0), s = Math.max(lo, Math.min(m - half, hi - 2 * half));
        return hi - lo <= 2 * half ? [lo, hi] : [s, s + 2 * half];
      };
      const [x0, x1] = cut(b.x0, b.x1, t.x + t.width / 2, freeW * MAX_SHRINK), [y0, y1] = cut(b.y0, b.y1, t.y + t.height / 2, freeH * MAX_SHRINK);
      FS.frame(svg, { x0, y0, x1, y1 }, keep);
    }
    return { moved: true };
  };
  /** Insets with more room kept at the top and bottom (px), the free area never under 80 px tall. */
  function kept(ins, keep, r) {
    if (!keep) return ins;
    const room = Math.max(0, r.height - ins.top - ins.bottom - 80);
    const top = Math.min(keep.top || 0, room), bottom = Math.min(keep.bottom || 0, room - top);
    return Object.assign({}, ins, { top: ins.top + top, bottom: ins.bottom + bottom });
  }

  /** The zoom as a percentage: 100 is one drawing unit a pixel. */
  FS.scalePct = function (svg) {
    const c = C(svg), v = c.view, w = (c.px && c.px.w) || svg.getBoundingClientRect().width;
    return v && w ? Math.round((100 * w) / v.w) : 100;
  };
  /** The farthest a zoom may go out: twice what shows the whole drawing. */
  function maxK(c, r) {
    const b = c.box || { x0: 0, y0: 0, x1: 800, y1: 600 };
    return Math.max(3, 2 * Math.max((b.x1 - b.x0) / r.width, (b.y1 - b.y0) / r.height));
  }
  /** Zoom to k units a px about the drawing point (x, y), which stays where it is. */
  function zoomTo(svg, x, y, k) {
    const c = C(svg), v = c.view, r = svg.getBoundingClientRect();
    const nk = Math.max(MIN_K, Math.min(maxK(c, r), k)), f = nk / (v.w / r.width);
    c.view = { x: x - (x - v.x) * f, y: y - (y - v.y) * f, w: v.w * f, h: v.h * f };
    c.fitted = false;
    apply(svg);
  }
  /** The toolbar's − and +: zoom by f (above 1 closer) about the middle of the free area. */
  FS.zoomBy = function (svg, f) {
    const c = C(svg), r = svg.getBoundingClientRect();
    if (!c.view || !r.width) return;
    const a = free(svg, c, r);
    zoomTo(svg, (a.x0 + a.x1) / 2, (a.y0 + a.y1) / 2, a.k / f);
  };

  /** The SVG changed size (a window resize, a splitter, the dock): keep the view's centre
   *  and scale rather than refit, so zoom and pan do not drift; a view from the drawing's
   *  start (FS.fit's open of a large drawing, or one panned there) keeps that edge where it
   *  was instead (starts). A view set while the SVG had no size yet is fitted afresh. */
  FS.resize = function (svg) {
    const c = C(svg);
    if (!c.view) return;
    const r = svg.getBoundingClientRect();
    if (!r.width || !r.height) return;
    const px = c.px;
    if (!px || !px.w || !px.h) { FS.fit(svg); return; }
    if (Math.abs(px.w - r.width) < 0.5 && Math.abs(px.h - r.height) < 0.5) return;
    const v = c.view, k = v.w / px.w, cx = v.x + v.w / 2, cy = v.y + v.h / 2, at = starts(c, k, FS.insets(svg));
    c.view = { x: at.x ? v.x : cx - (r.width * k) / 2, y: at.y ? v.y : cy - (r.height * k) / 2, w: r.width * k, h: r.height * k };
    c.px = { w: r.width, h: r.height };
    apply(svg);
  };
  /** Which axes of the view (at its size c.px, k units a px) begin at the drawing's start:
   *  its left edge, or the top of what shows of it, just inside the free area (40 px at most)
   *  while its far edge is not (a view that fits the drawing on that axis stays centred). */
  function starts(c, k, ins) {
    const v = c.view, b = c.box;
    if (!b) return { x: false, y: false };
    const x0 = v.x + ins.left * k, x1 = v.x + (c.px.w - ins.right) * k, y0 = v.y + ins.top * k, y1 = v.y + (c.px.h - ins.bottom) * k;
    const top = (c.tops || []).reduce((m, t) => (t[0] < x1 && t[2] > x0 ? Math.min(m, t[1]) : m), Infinity);
    const near = (d) => d >= -k && d <= 40 * k;
    return { x: near(b.x0 - x0) && !near(x1 - b.x1), y: isFinite(top) && near(top - y0) && !near(y1 - b.y1) };
  }
  /** The part of a target that shows where it is: a block's box, a stream's label, else its
   *  feed or product end (circle and name), else its line; a heat plan's exchanger (kind
   *  "heat": its duty label) or utility ("util": its pill) by its index in the plan. */
  function targetEl(svg, target) {
    if (target.kind === "heat" || target.kind === "util") {
      const g = svg.querySelector(`[data-${target.kind}="${CSS.escape(String(target.name))}"]`);
      return g && target.kind === "heat" ? g.querySelector("text") : g;
    }
    const all = [...svg.querySelectorAll("[data-kind]")].filter((el) => el.getAttribute("data-kind") === target.kind
      && el.getAttribute("data-name") === target.name);
    for (const g of all) { const el = g.querySelector("rect, .lbl"); if (el) return el; }
    return all.find((g) => g.classList.contains("fs-term")) || (all[0] && (all[0].querySelector(".hit") || all[0])) || null;
  }

  /** A target's box (an SVGRect, {x, y, width, height}) with a block's name in the icon view. */
  function withName(c, target, b) {
    const nm = target.kind === "block" && c.names && c.names["B:" + target.name];
    if (!nm) return b;
    const x0 = Math.min(b.x, nm.box.x0), y0 = Math.min(b.y, nm.box.y0);
    return { x: x0, y: y0, width: Math.max(b.x + b.width, nm.box.x1) - x0, height: Math.max(b.y + b.height, nm.box.y1) - y0 };
  }
  /** Bring a stream or block into the part of the card nothing floats over (FS.insets): the
   *  least pan at the same scale, at once, or none when it shows already. keep: more room to
   *  keep clear at the top and bottom, px from the SVG's edges (the app's edge hints there),
   *  and pad, the room kept round the target, px (16; FS.RING_ROOM where a ring follows); tag:
   *  its tag (.fs-tag2, a preview's or a run by group's) in view too, as far as both fit.
   *  Returns null when the target is not drawn, else {moved, rect}: rect is where it now
   *  shows, in client px. */
  FS.reveal = function (svg, target, keep) {
    const c = C(svg), v = c.view, r = svg.getBoundingClientRect();
    if (!v || !r.width || !target) return null;
    const el = targetEl(svg, target);
    if (!el) return null;
    let b = withName(c, target, el.getBBox());
    const a = free(svg, c, r), pad = Math.max(16, (keep && keep.pad) || 0) * a.k;
    if (keep) {
      a.y0 = Math.max(a.y0, v.y + (keep.top || 0) * a.k);
      a.y1 = Math.min(a.y1, v.y + v.h - (keep.bottom || 0) * a.k);
    }
    const tk = `${target.kind}:${target.name}`, fxt = keep && keep.tag && c.fx ? c.fx.tags.find((x) => x.key === tk) : null;
    const tag = keep && keep.tag && !fxt ? svg.querySelector(`.fs-tag2[data-tag="${CSS.escape(tk)}"] rect`) : null;
    const fo = fxt ? fxOff(c, tk) : null;            // (a result tag: where it is now, glass over the SVG)
    if (tag || fxt) {                                // (with the tag: as long as both fit, else the target alone)
      const t = fxt ? { x: fxt.b.x0 + fo[0], y: fxt.b.y0 + fo[1], width: fxt.w, height: fxt.hh } : tag.getBBox(), x0 = Math.min(b.x, t.x), y0 = Math.min(b.y, t.y);
      const u = { x: x0, y: y0, width: Math.max(b.x + b.width, t.x + t.width) - x0, height: Math.max(b.y + b.height, t.y + t.height) - y0 };
      if (u.width + 2 * pad <= a.x1 - a.x0 && u.height + 2 * pad <= a.y1 - a.y0) b = u;
    }
    const need = (lo, hi, p, z) => (z - p + 2 * pad > hi - lo || p - pad < lo ? p - pad - lo : z + pad > hi ? z + pad - hi : 0);
    const dx = need(a.x0, a.x1, b.x, b.x + b.width), dy = need(a.y0, a.y1, b.y, b.y + b.height);
    if (dx || dy) {
      c.view = Object.assign({}, v, { x: v.x + dx, y: v.y + dy });
      c.fitted = false;
      apply(svg);
    }
    return { moved: !!(dx || dy), rect: el.getBoundingClientRect() };
  };

  /** Zoomed out past reading (MAX_SHRINK), zoom in about a target until names read again, the
   *  target staying where it shows (then FS.reveal brings it in); nothing otherwise. Following
   *  the AI's edits (app-follow.js). Returns whether the view changed. */
  FS.readable = function (svg, target) {
    const c = C(svg), v = c.view, r = svg.getBoundingClientRect();
    const el = v && r.width && target ? targetEl(svg, target) : null;
    if (!el || v.w / r.width <= MAX_SHRINK) return false;
    const b = el.getBBox();
    zoomTo(svg, b.x + b.width / 2, b.y + b.height / 2, MAX_SHRINK);
    return true;
  };

  const RING = 26;                                   // the ring's room round its target, px
  FS.RING_ROOM = RING + 8;                           // ... with its glow and a little air: FS.reveal's pad before a ring
  /** A ring round a target that grows and fades once (HTML over the drawing, so nothing in
   *  the SVG animates): where the eye should look after a pan or a jump from elsewhere. cls: a
   *  class more on the ring ("ai": the AI's edit, in its violet). A target revealed with pad
   *  FS.RING_ROOM keeps the whole ring in the card. */
  FS.ping = function (svg, target, cls) {
    const el = targetEl(svg, target), host = svg.parentNode;
    if (!el || !host) return;
    const a = el.getBoundingClientRect(), h = host.getBoundingClientRect(), pad = RING;
    if (!a.width && !a.height) return;
    host.querySelectorAll(":scope > .fs-ring").forEach((x) => x.remove());
    const ring = document.createElement("div");
    ring.className = `fs-ring${target.kind === "block" ? "" : " round"}${cls ? ` ${cls}` : ""}`;
    Object.assign(ring.style, { left: `${a.left - h.left - pad}px`, top: `${a.top - h.top - pad}px`,
      width: `${a.width + 2 * pad}px`, height: `${a.height + 2 * pad}px` });
    host.appendChild(ring);
    const done = () => ring.remove();
    ring.addEventListener("animationend", done);
    setTimeout(done, 700);
  };

  /** What of the drawing lies beyond each edge of the free area: {l, r, t, b}, each with
   *  the blocks there (units, names), how many of them failed (errs) or warn (warns), the requests not
   *  done (notes), and how far the farthest reaches (far, drawing units). A thing counts by
   *  its middle: beside the view first, then above or below it. more: whether anything
   *  drawn (a feed's name too) reaches past that edge of the card; past the top, only what
   *  lies within the card's width counts (a view fitted to the drawing's start leaves rows
   *  farther right higher up, and those are the right edge's). links: what a block selected
   *  in the program names (the "link" mark) that lies beyond that edge; marks, markNames: the
   *  AI's marks there (a marked block is counted in units too); chg, chgNames, chgBy ({actor:
   *  n}): the changes not seen yet there (FS.render's v.changes: a block's counted in units too);
   *  pins, pinNames: the annotations there (FS.render's v.pins: each marker's count, by where
   *  the marker lies); pv, pvNames: a proposal's new blocks and streams there (the preview). */
  FS.offscreen = function (svg) {
    const c = C(svg), r = svg.getBoundingClientRect(), out = {};
    ["l", "r", "t", "b"].forEach((s) => { out[s] = { units: 0, errs: 0, warns: 0, notes: 0, names: [], far: null, more: false, links: [], marks: 0, markNames: [], chg: 0, chgNames: [], chgBy: {}, pins: 0, pinNames: [], pv: 0, pvNames: [] }; });
    if (!c.view || !r.width || !r.height) return out;
    const a = free(svg, c, r), v = c.view, b = c.box, e = 2 * a.k;
    if (b) {
      out.l.more = b.x0 < v.x - e; out.r.more = b.x1 > v.x + v.w + e;
      out.t.more = (c.tops || []).some((t) => t[1] < v.y - e && t[0] < v.x + v.w && t[2] > v.x); out.b.more = b.y1 > v.y + v.h + e;
    }
    (c.items || []).forEach((it) => {
      const cx = (it.x0 + it.x1) / 2, cy = (it.y0 + it.y1) / 2;
      const s = cx < a.x0 ? "l" : cx > a.x1 ? "r" : cy < a.y0 ? "t" : cy > a.y1 ? "b" : null;
      if (!s) return;
      const o = out[s], edge = { l: it.x0, r: it.x1, t: it.y0, b: it.y1 }[s];
      if (it.kind === "note") o.notes++;
      else { o.units++; o.names.push(it.name); if (it.err) o.errs++; if (it.warn) o.warns++; }
      o.far = o.far === null ? edge : s === "l" || s === "t" ? Math.min(o.far, edge) : Math.max(o.far, edge);
    });
    ((c.marks || {}).link || []).forEach((key) => {
      const i = key.indexOf(":"), tg = { kind: key.slice(0, i), name: key.slice(i + 1) }, el = targetEl(svg, tg);
      if (!el) return;
      const bb = el.getBBox(), cx = bb.x + bb.width / 2, cy = bb.y + bb.height / 2;
      const s = cx < a.x0 ? "l" : cx > a.x1 ? "r" : cy < a.y0 ? "t" : cy > a.y1 ? "b" : null;
      if (s) out[s].links.push(tg);
    });
    (c.hl || []).forEach((key) => {
      const i = key.indexOf(":"), tg = { kind: key.slice(0, i), name: key.slice(i + 1) }, el = targetEl(svg, tg);
      if (!el) return;
      const bb = el.getBBox(), cx = bb.x + bb.width / 2, cy = bb.y + bb.height / 2;
      const s = cx < a.x0 ? "l" : cx > a.x1 ? "r" : cy < a.y0 ? "t" : cy > a.y1 ? "b" : null;
      if (s) { out[s].marks++; out[s].markNames.push(tg.name); }
    });
    (c.chgs || []).forEach((d) => {
      const s = sideOf(a, d.box);
      if (!s) return;
      out[s].chg++;
      out[s].chgNames.push(d.name);
      out[s].chgBy[d.actor] = (out[s].chgBy[d.actor] || 0) + 1;
    });
    (c.pins || []).forEach((d) => {              // annotations: how many (each marker's count), by its marker
      const s = sideOf(a, d.box);
      if (!s) return;
      out[s].pins += d.n || 1;
      out[s].pinNames.push(d.name);
    });
    (c.pvShown ? c.pvItems || [] : []).forEach((d) => {   // a proposal's new blocks and streams (the preview)
      const s = sideOf(a, d.box);
      if (!s) return;
      out[s].pv++;
      out[s].pvNames.push(d.name);
    });
    return out;
  };
  /** Which edge of the free area a box lies beyond, by its middle (beside the view first, then
   *  above or below it), or null inside. */
  function sideOf(a, b) {
    const cx = (b.x0 + b.x1) / 2, cy = (b.y0 + b.y1) / 2;
    return cx < a.x0 ? "l" : cx > a.x1 ? "r" : cy < a.y0 ? "t" : cy > a.y1 ? "b" : null;
  }
  /** An edge hint's click: at once, the least pan on both axes that brings the nearest of what
   *  lies beyond that edge into the free area -- the nearest change not seen yet first, where
   *  there is one there, else the nearest annotations' marker, else the nearest block or
   *  request -- with as many of the others there near it as fit beside it. Returns the change it went to ({kind, name}: the caller rings it),
   *  true for anything else, or null. */
  FS.edgePan = function (svg, side) {
    const c = C(svg), r = svg.getBoundingClientRect(), o = FS.offscreen(svg)[side];
    if (!c.view || !r.width || !o || (o.far === null && !o.chg && !o.pins)) return null;
    const a = free(svg, c, r), pad = 24 * a.k, v = c.view, b = c.box || {};
    const box = (it) => it.box || it, there = (it) => sideOf(a, box(it)) === side;
    const chg = (c.chgs || []).filter(there), pins = chg.length ? [] : (c.pins || []).filter(there);
    const pool = chg.length ? chg : pins.length ? pins : (c.items || []).filter(there);
    if (pool.length) {
      const mx = (a.x0 + a.x1) / 2, my = (a.y0 + a.y1) / 2, d = (q) => Math.hypot((q.x0 + q.x1) / 2 - mx, (q.y0 + q.y1) / 2 - my);
      pool.sort((p, q) => d(box(p)) - d(box(q)));
      const W = a.x1 - a.x0 - 2 * pad, H = a.y1 - a.y0 - 2 * pad, first = box(pool[0]);
      let u = first;
      pool.slice(1).map(box).sort((p, q) => Math.hypot(p.x0 - first.x0, p.y0 - first.y0) - Math.hypot(q.x0 - first.x0, q.y0 - first.y0))
        .forEach((q) => { const j = join(u, q); if (j.x1 - j.x0 <= W && j.y1 - j.y0 <= H) u = j; });
      // the least move that shows it (its middle, where it is wider than the free area)
      const need = (lo, hi, p, z) => (z - p > hi - lo - 2 * pad ? (p + z - lo - hi) / 2 : p - pad < lo ? p - pad - lo : z + pad > hi ? z + pad - hi : 0);
      c.view = Object.assign({}, v, { x: v.x + need(a.x0, a.x1, u.x0, u.x1), y: v.y + need(a.y0, a.y1, u.y0, u.y1) });
      c.fitted = false;
      apply(svg);
      return chg.length ? { kind: pool[0].kind, name: pool[0].name } : true;
    }
    const step = (side === "l" || side === "r" ? a.x1 - a.x0 : a.y1 - a.y0) * 0.9;
    // as far as the drawing reaches that way (its feeds' and products' names too)
    const far = side === "r" ? Math.max(o.far, b.x1 ?? -Infinity) : side === "l" ? Math.min(o.far, b.x0 ?? Infinity)
      : side === "b" ? Math.max(o.far, b.y1 ?? -Infinity) : Math.min(o.far, b.y0 ?? Infinity);
    const d = side === "r" ? far + pad - a.x1 : side === "l" ? a.x0 - (far - pad)
      : side === "b" ? far + pad - a.y1 : a.y0 - (far - pad);
    const m = Math.max(0, Math.min(step, d)) * (side === "l" || side === "t" ? -1 : 1);
    c.view = Object.assign({}, v, side === "l" || side === "r" ? { x: v.x + m } : { y: v.y + m });
    c.fitted = false;
    apply(svg);
    return true;
  };
  /** Frame these blocks and streams (targets {kind, name, n?}) in the free area: all of them where
   *  that takes no more than FIT_SHRINK (their dots and annotation markers still show where names
   *  no longer read), else about their middle at that scale (the edge hints count the rest); never
   *  larger than life. most: where they do not all fit, the most of them that do instead (by
   *  their n, 1 each without: from each one, its nearest others while they still fit), so the view
   *  shows a group rather than the empty middle of a spread. Returns whether any is drawn. */
  FS.fitTo = function (svg, targets, most) {
    const c = C(svg), r = svg.getBoundingClientRect();
    if (!c.lay || !r.width || !r.height) return false;
    const own = (list, tg) => (list || []).find((d) => d.kind === tg.kind && d.name === tg.name);
    const boxes = [];
    (targets || []).forEach((tg) => {
      const el = tg && targetEl(svg, tg);
      if (!el) return;
      const bb = withName(c, tg, el.getBBox()), dot = own(c.chgs, tg), pin = own(c.pins, tg);
      const b = join(join({ x0: bb.x, y0: bb.y, x1: bb.x + bb.width, y1: bb.y + bb.height }, dot ? dot.box : null), pin ? pin.box : null);
      boxes.push({ b, w: Number(tg.n) || 1 });
    });
    if (!boxes.length) return false;
    const ins = FS.insets(svg), M = 36;
    const freeW = Math.max(r.width - ins.left - ins.right, 1), freeH = Math.max(r.height - ins.top - ins.bottom, 1);
    const fits = (b) => (b.x1 - b.x0 + 2 * M) / freeW <= FIT_SHRINK && (b.y1 - b.y0 + 2 * M) / freeH <= FIT_SHRINK;
    let u = boxes.reduce((acc, x) => join(acc, x.b), null);
    if (most && !fits(u)) {
      const mid = (b) => [(b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2];
      let best = -1;
      boxes.forEach((s) => {
        const [sx, sy] = mid(s.b), d = (o) => Math.hypot(mid(o.b)[0] - sx, mid(o.b)[1] - sy);
        let g = s.b, w = s.w;
        boxes.filter((o) => o !== s).sort((p, q) => d(p) - d(q)).forEach((o) => { const j = join(g, o.b); if (fits(j)) { g = j; w += o.w; } });
        if (w > best) { best = w; u = g; }
      });
    }
    const k = Math.min(FIT_SHRINK, Math.max((u.x1 - u.x0 + 2 * M) / freeW, (u.y1 - u.y0 + 2 * M) / freeH, 1));
    const fx = (u.x0 + u.x1 - freeW * k) / 2, fy = (u.y0 + u.y1 - freeH * k) / 2;
    c.view = { x: fx - ins.left * k, y: fy - ins.top * k, w: r.width * k, h: r.height * k };
    c.px = { w: r.width, h: r.height };
    c.fitted = false;
    apply(svg);
    return true;
  };

  function apply(svg) {
    const c = C(svg), v = c.view;
    if (!v) return;
    svg.setAttribute("viewBox", `${v.x} ${v.y} ${v.w} ${v.h}`);
    // zoomed out past reading (VAL_FAR), the value lines are not drawn: a class on the SVG
    const far = !!(c.px && c.px.w) && v.w / c.px.w > VAL_FAR;
    if (svg._fsFar !== far) { svg._fsFar = far; svg.classList.toggle("far", far); }
    if (svg._fxL) fxPlace(svg);                    // (the result tags' glass: their plane follows the view)
    moved(svg);
  }
  /** The view (or what is drawn, or what floats over it) changed: the zoom readout hears of
   *  a new scale at once; the edge hints are counted again once the view rests (140 ms after
   *  the last change: the end of a pan or of a turn of the wheel). */
  function moved(svg) {
    const on = svg._fsOn;
    if (!on) return;
    const pct = FS.scalePct(svg);
    if (on.zoom && pct !== svg._fsPct) { svg._fsPct = pct; on.zoom(pct); }
    clearTimeout(svg._fsRest);
    svg._fsRest = setTimeout(() => on.view && on.view(), 140);
  }
  FS.moved = moved;

  /** The stream under the pointer (its name or null): its line lights up (.hot) wherever the
   *  pointer is on it, its label or its end too; kept across a redraw (FS.render). */
  function hotOn(svg, name) {
    svg._fsHot = name || null;
    svg.querySelectorAll(".fs-edge.hot").forEach((el) => el.classList.remove("hot"));
    if (name) markEls(svg, `stream:${name}`).forEach((el) => { if (el.classList.contains("fs-edge")) el.classList.add("hot"); });
  }

  // ------------------------------------------------------------------ moving things
  // Blocks, feeds and products can be dragged, and so can a stream's inner segments (across
  // their own direction: where the stream bends). A drag moves only what it touches, straight
  // in the drawing: the node's group (and the requests over it) by a transform, the paths of
  // its streams by their d; nothing is laid out again and no label is placed until the drop,
  // which hands the whole arrangement to on.layout (the page stores it, and draws it again).
  // Their labels, and heat arcs on a moved block, are hidden meanwhile. Escape cancels.

  const FRAME_MS = 2;                                 // the routing a drag frame may spend (ms)
  let routeMs = 1;                                    // the most a stream's routing took in the last drag (ms)
  let warmed = false;
  /** The router's first runs are slow (the engine has yet to compile it): once per page, a
   *  press on a block, feed or product routes its streams afresh where they are and drops the
   *  result, so the drag that may follow does not pay for that inside a frame. */
  function warm(ex, id) {
    if (warmed || !ex) return;
    const own = Object.entries(ex.streams).filter(([, g]) => g.n.includes(id) && ex.nodes[g.n[0]] && ex.nodes[g.n[1]]);
    if (!own.length) return;
    warmed = true;
    const boxes = Object.keys(ex.nodes).filter((k) => k[0] === "B").map((k) => EX.boxAt(ex.nodes[k], k));
    own.forEach(([s, g]) => EX.fit(g, ex.nodes[g.n[0]], ex.nodes[g.n[1]], boxes, true, false, null, null, { n: g.n, s }));
  }
  /** fn() with the icon view's geometry of context c in force (a drag's routing, read back,
   *  happens outside a render). */
  function inGeo(c, fn) {
    const prev = GEO;
    GEO = (c && c.geo) || null;
    try { return fn(); } finally { GEO = prev; }
  }
  /** A pointer position (client px) in drawing units, through the SVG's transform as it is now
   *  (a resize or a zoom meanwhile cannot skew a drag). */
  function units(svg, x, y) {
    const m = svg.getScreenCTM();
    if (!m) return null;
    const p = new DOMPoint(x, y).matrixTransform(m.inverse());
    return [p.x, p.y];
  }
  /** The explicit layout of what this context draws: the geometry an explicit arrangement drew,
   *  or the automatic drawing read back (once per layout). */
  function exOf(c) {
    if (!c.lay) return null;
    if (!c.lay.ex) c.lay.ex = inGeo(c, () => EX.explicitOfAuto(c.lay));
    return c.lay.ex;
  }
  const copyEx = (ex) => ({
    nodes: Object.fromEntries(Object.entries(ex.nodes).map(([k, p]) => [k, p.slice()])),
    streams: Object.fromEntries(Object.entries(ex.streams).map(([k, g]) => [k, { n: g.n.slice(), a: g.a && g.a.slice(), b: g.b && g.b.slice(), h: g.h, c: g.c.slice() }])),
  });
  /** What is drawn, as an explicit layout {nodes, streams} (a copy): where a drag starts from. */
  FS.explicitOf = (svg) => { const x = exOf(C(svg)); return x ? copyEx(x) : null; };

  /** The drawing shown in svg as a figure: a standalone SVG document (markup), the blocks,
   *  streams, their names and the value lines as they are drawn, their look written into each
   *  element, on a white ground cropped to the drawing (12 units round it), 1 unit to 1 px. No
   *  state of the window goes with it: what is picked or marked, Aspen's badges and outlines,
   *  changes, annotations, requests, the heat plan, tooltips and the dot grid are left out.
   *  null when nothing is drawn. */
  const FIG_PROPS = ["fill", "fill-opacity", "stroke", "stroke-width", "stroke-dasharray", "stroke-linecap", "stroke-linejoin",
    "stroke-opacity", "opacity", "paint-order", "font-family", "font-size", "font-weight", "font-style", "text-anchor", "font-variant-numeric"];
  const FIG_DROP = ".fs-note, .fs-heat, .fs-util, .badge, .chdot, .aimark, .pinmark, rect.frame, .hit, .fs-grid, .fs-empty, title, .fs-pv, .fs-tags2, .fs-band, .fs-band-v";
  const FIG_STATE = ["sel", "hl", "link", "walk", "err", "warn", "bkpend", "clash", "drag-hide", "moving", "pv-gone", "pv-on", "pv-tagged", "pv-stale", "gc", "cause", "fw"];
  FS.figure = function (svg) {
    const c = C(svg);
    if (!c.lay || !svg.querySelector(".fs-node, .fs-edge")) return null;
    // the look of each element with no state on (classes taken off a moment, then put back)
    const off = [];
    [svg, ...svg.querySelectorAll(FIG_STATE.map((k) => "." + k).join(","))].forEach((el) => {
      const had = FIG_STATE.filter((k) => el.classList.contains(k));
      if (had.length) { off.push([el, had]); el.classList.remove(...had); }
    });
    const src = [...svg.querySelectorAll("*")], looks = new Map();
    let box = null;
    try {
      src.forEach((el) => {
        if (el.closest("defs") || el.closest(FIG_DROP)) return;
        const cs = getComputedStyle(el);
        if (cs.display === "none" || cs.visibility === "hidden") { looks.set(el, null); return; }
        looks.set(el, FIG_PROPS.map((p) => [p, cs.getPropertyValue(p)]).filter(([, v]) => v && v !== "normal" && v !== "auto"));
        if (/^(path|use|text|circle)$/.test(el.tagName)) {
          const b = el.getBBox(), pad = el.tagName === "text" ? 2 : 1;
          if (b.width || b.height) box = join(box, { x0: b.x - pad, y0: b.y - pad, x1: b.x + b.width + pad, y1: b.y + b.height + pad });
        }
      });
    } finally {
      off.forEach(([el, had]) => el.classList.add(...had));
    }
    if (!box) return null;
    const NS = "http://www.w3.org/2000/svg", XL = "http://www.w3.org/1999/xlink";
    const doc = svg.cloneNode(true), dst = [...doc.querySelectorAll("*")];
    src.forEach((el, i) => {
      const d = dst[i];
      if (!d.parentNode) return;
      if (el.closest("defs")) return;
      const look = looks.get(el);
      if (look === undefined || look === null) { d.remove(); return; }
      d.setAttribute("style", look.map(([p, v]) => `${p}:${v}`).join(";"));
    });
    doc.querySelectorAll("*").forEach((d) => {
      [...d.attributes].forEach((a) => { if (a.name === "class" || a.name.startsWith("data-")) d.removeAttribute(a.name); });
      if (d.tagName === "use") d.setAttributeNS(XL, "xlink:href", d.getAttribute("href"));
      if (d.getAttribute("marker-end")) d.setAttribute("marker-end", `url(#${svg.classList.contains("icons") ? "arr-ink" : "arr"})`);
    });
    doc.querySelectorAll("defs pattern, defs #arr-gc").forEach((d) => d.remove());   // (#arr-gc: a run by group's)
    const M = 12, x = box.x0 - M, y = box.y0 - M, w = box.x1 - box.x0 + 2 * M, h = box.y1 - box.y0 + 2 * M;
    const r = (v) => Math.round(v * 10) / 10;
    ["class", "style", "width", "height", "preserveAspectRatio", "aria-label", "role", "tabindex"].forEach((a) => doc.removeAttribute(a));
    doc.setAttribute("xmlns", NS);
    doc.setAttribute("xmlns:xlink", XL);
    doc.setAttribute("viewBox", `${r(x)} ${r(y)} ${r(w)} ${r(h)}`);
    doc.setAttribute("width", r(w));
    doc.setAttribute("height", r(h));
    const ground = document.createElementNS(NS, "rect");
    [["x", r(x)], ["y", r(y)], ["width", r(w)], ["height", r(h)], ["fill", "#ffffff"]].forEach(([k, v]) => ground.setAttribute(k, v));
    const defs = doc.querySelector("defs");
    doc.insertBefore(ground, defs ? defs.nextSibling : doc.firstChild);
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(doc);
  };
  const isTerm = (id) => id[0] !== "B";
  /** The d of stream s's path pts as drawn (ea, eb: its ends now, pa, pb: their centres; the
   *  icon view's leads). */
  const drawnPath = (pts, g, s, ea, eb, pa, pb) =>
    roundPath(EX.drawPoints(pts, isTerm(g.n[0]), isTerm(g.n[1]), EX.leadsOf(s, g.n, pa, pb, ea, eb)).map(([x, y]) => ({ x, y }))).d;

  /** The inner segment of a stream nearest the pointer (client px), within max(8 px, 7 units):
   *  {j, up} (j: 1..k, as in its c; up: it runs up and down, so it moves sideways), or null
   *  (an end segment is nearest, or nothing is near). */
  function segAt(svg, name, cx, cy) {
    const c = C(svg);
    return inGeo(c, () => segAtIn(svg, c, name, cx, cy));
  }
  function segAtIn(svg, c, name, cx, cy) {
    const ex = exOf(c), g = ex && ex.streams[name];
    const pa = g && ex.nodes[g.n[0]], pb = g && ex.nodes[g.n[1]];
    const p = pa && pb && units(svg, cx, cy), r = svg.getBoundingClientRect();
    if (!p || !c.view || !r.width) return null;
    const tol = Math.max((8 * c.view.w) / r.width, 7);
    const segs = EX.rawSegments(EX.endPoint(pa, g.a, g.n[0]), EX.endPoint(pb, g.b, g.n[1]), g.h, g.c);
    let best = -1, bd = Infinity;
    segs.forEach(([a, b], j) => {
      if (Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]) < 0.01) return;      // no length: not there
      const dx = Math.max(0, Math.min(a[0], b[0]) - p[0], p[0] - Math.max(a[0], b[0]));
      const dy = Math.max(0, Math.min(a[1], b[1]) - p[1], p[1] - Math.max(a[1], b[1]));
      const d = Math.hypot(dx, dy);
      if (d < bd) { bd = d; best = j; }
    });
    if (best < 1 || best > segs.length - 2 || bd > tol) return null;
    const [a, b] = segs[best];
    return { j: best, up: Math.abs(a[0] - b[0]) < 0.01 };
  }
  function segClass(svg, s) {
    const v = !!(s && s.up), h = !!(s && !s.up);
    if (svg.classList.contains("seg-v") !== v) svg.classList.toggle("seg-v", v);
    if (svg.classList.contains("seg-h") !== h) svg.classList.toggle("seg-h", h);
  }

  /** A drag begins (the press moved 4 px): what it moves, from what is drawn. */
  function startMove(svg, press) {
    const c = C(svg);
    return inGeo(c, () => startMoveIn(svg, c, press));
  }
  function startMoveIn(svg, c, press) {
    const src = exOf(c), start = units(svg, press.x, press.y);
    if (!src || !start) return null;
    const ex = copyEx(src), all = (sel) => [...svg.querySelectorAll(sel)];
    const mv = { kind: press.kind, ex, start, fam: c.fam || "auto", hidden: [], moved: [], paths: {}, last: {}, rest: null,
                 restT: 0, frame: 0, at: null, alt: false, pend: [], est: routeMs, own: 0, ctx: c, svg, extra: {}, xhid: [] };
    if (press.kind === "node") {
      const id = press.id;
      if (!ex.nodes[id]) return null;
      mv.id = id;
      mv.c0 = ex.nodes[id].slice();
      mv.cur = mv.c0.slice();
      mv.touch = [...new Set(Object.keys(ex.streams).filter((s) => ex.streams[s].n.includes(id)))];
      mv.boxes = Object.keys(ex.nodes).filter((k) => k[0] === "B" && k !== id).map((k) => EX.boxAt(ex.nodes[k], k));
      mv.moved = all("[data-node], [data-at]").filter((el) => el.getAttribute("data-node") === id || el.getAttribute("data-at") === id);
      mv.el = mv.moved.find((el) => el.getAttribute("data-node") === id) || null;
      mv.obst = obstaclesOf(c, ex, id);
      mv.hidden = all("[data-on]").filter((el) => el.getAttribute("data-on").split("|").includes(id));
    } else {
      const g = ex.streams[press.name];
      const pa = g && ex.nodes[g.n[0]], pb = g && ex.nodes[g.n[1]];
      if (!pa || !pb || !(press.j >= 1 && press.j <= g.c.length)) return null;
      Object.assign(mv, { name: press.name, g, j: press.j, up: press.up, v0: g.c[press.j - 1], touch: [press.name],
                          A: EX.endPoint(pa, g.a, g.n[0]), B: EX.endPoint(pb, g.b, g.n[1]) });
      mv.val = mv.v0;
    }
    mv.hidden = mv.hidden.concat(all(".fs-tag, [data-lbl]").filter((el) => mv.touch.includes(el.getAttribute("data-lbl") || el.getAttribute("data-name"))));
    all(".fs-edge").forEach((el) => {
      const n = el.getAttribute("data-name");
      if (mv.touch.includes(n)) mv.paths[n] = [...el.querySelectorAll("path")].map((p) => [p, p.getAttribute("d")]);
    });
    mv.hidden.forEach((el) => el.classList.add("drag-hide"));
    svg.classList.add("moving");
    svg._fsHtml = null;                            // (its elements moved by hand: the next drawing is made anew)
    c.fitted = false;
    return mv;
  }
  /** Where a moved node snaps: level with the other end of one of its streams that would then
   *  run straight, within 8 units, on each axis; else to the 10-unit grid. */
  function snapNode(mv, x, y) {
    const ex = mv.ex, id = mv.id;
    let sx = null, sy = null, bx = 8.0001, by = 8.0001;
    mv.touch.forEach((s) => {
      const g = ex.streams[s];
      [["a", 0], ["b", 1]].forEach(([k, i]) => {
        if (g.n[i] !== id || g.n[1 - i] === id) return;
        const mine = g[k], oth = g[k === "a" ? "b" : "a"], other = ex.nodes[g.n[1 - i]];
        if (!other) return;
        // the end segments' directions: both level (or both upright) for a straight line
        const hm = mine ? EX.AXIS_H[mine[0]] : k === "a" ? !!g.h : EX.lastHoriz(g);
        const ho = oth ? EX.AXIS_H[oth[0]] : k === "a" ? EX.lastHoriz(g) : !!g.h;
        if (hm !== ho) return;
        const op = EX.endPoint(other, oth, g.n[1 - i]), me = EX.endPoint([x, y], mine, id);
        if (hm) { const d = op[1] - me[1]; if (Math.abs(d) < by) { by = Math.abs(d); sy = y + d; } }
        else { const d = op[0] - me[0]; if (Math.abs(d) < bx) { bx = Math.abs(d); sx = x + d; } }
      });
    });
    return [sx !== null ? sx : Math.round(x / 10) * 10, sy !== null ? sy : Math.round(y / 10) * 10];
  }
  /** What a node takes about its centre: a block its box (the icon view: its frame, and its
   *  name where it is drawn), a feed or product its circle and its name on the side it is drawn
   *  (lay.tside), as [kind, x0, y0, x1, y1]. */
  function partsOf(lay, id) {
    if (id[0] === "B") {
      const d = dimOf(id), nm = d && lay && lay.names && lay.names[id], p = lay && lay.pos && lay.pos[id];
      if (!d) return [["box", -BW / 2, -BH / 2, BW / 2, BH / 2]];
      const out = [["box", -d.hw, -d.hh, d.hw, d.hh]];
      if (nm && p) out.push(["name", nm.box.x0 - p.x, nm.box.y0 - p.y, nm.box.x1 - p.x, nm.box.y1 - p.y]);
      return out;
    }
    const R = EX.TERM_R, n = lay && lay.nodes && lay.nodes.get(id), w = textWidth(n ? n.name : id.slice(2)) + 2;
    const left = lay && lay.tside && lay.tside[id] ? lay.tside[id] === "l" : id[0] === "F";
    return [["dot", -R, -R, R, R], ["name", left ? -12 - w : 10, -9, left ? -10 : 12 + w, 9]];
  }
  // room kept between the parts of two nodes: blocks 10 apart, a feed's or product's circle 20
  // from a block and 40 from its own (its line leaves straight, and has room to turn once),
  // names clear of blocks and circles (names of two terminals may meet: their lines tell them
  // apart)
  const ROOM_OWN = 40;
  const ROOM_BY = { "box|box": 10, "box|dot": 20, "dot|box": 20, "box|name": 4, "name|box": 4, "dot|dot": 4, "dot|name": 2, "name|dot": 2 };
  /** What a moved node must not land on: the other blocks, feeds and products, each part as
   *  the box its own parts' corners must keep out of ({k: its parts' kinds, x0, y0, x1, y1},
   *  room included). A drop never moves a node for what it did not do: where it kept less
   *  room from one when the drag began, it keeps that much (10, else none), and what it
   *  already sat on is left out. */
  function obstaclesOf(c, ex, id) {
    const mine = partsOf(c.lay, id), c0 = ex.nodes[id], out = [];
    const linked = new Set(Object.values(ex.streams).filter((g) => g.n.includes(id)).map((g) => (g.n[0] === id ? g.n[1] : g.n[0])));
    Object.entries(ex.nodes).forEach(([k, p]) => {
      if (k === id) return;
      const theirs = partsOf(c.lay, k), own = linked.has(k);
      // the room it kept from this one when the drag began, where that was less (none at all:
      // the two already met, and this one is left out)
      for (const most of [Infinity, 10, 0]) {
        const list = [];
        mine.forEach((m) => theirs.forEach((t) => {
          const pair = m[0] + "|" + t[0], want = own && (pair === "box|dot" || pair === "dot|box") ? ROOM_OWN : ROOM_BY[pair];
          if (want === undefined) return;
          const gap = Math.min(want, most);
          list.push({ x0: p[0] + t[1] - m[3] - gap, y0: p[1] + t[2] - m[4] - gap, x1: p[0] + t[3] - m[1] + gap, y1: p[1] + t[4] - m[2] + gap });
        }));
        if (!list.some((o) => inRect(c0, o))) { out.push(...list); break; }
      }
    });
    return out;
  }
  const inRect = (p, o) => p[0] > o.x0 && p[0] < o.x1 && p[1] > o.y0 && p[1] < o.y1;
  const clashAt = (mv, p) => mv.obst.some((o) => inRect(p, o));
  let NUDGE = null;                                   // the steps a drop looks for room in, nearest first
  /** Where a node let go at p lands: p, or the nearest spot clear of the others (10-unit steps
   *  from p, so what it snapped to on one axis stays when it only has to move along the other). */
  function freeSpot(mv, p) {
    if (!clashAt(mv, p)) return p;
    if (!NUDGE) {
      NUDGE = [];
      for (let i = -30; i <= 30; i++) for (let j = -30; j <= 30; j++) if (i || j) NUDGE.push([i * 10, j * 10]);
      NUDGE.sort((a, b) => a[0] * a[0] + a[1] * a[1] - b[0] * b[0] - b[1] * b[1] || Math.abs(a[1]) - Math.abs(b[1]) || a[1] - b[1] || a[0] - b[0]);
    }
    for (const [dx, dy] of NUDGE) {
      const q = [EX.r1(p[0] + dx), EX.r1(p[1] + dy)];
      if (!clashAt(mv, q)) return q;
    }
    return p;
  }
  /** Every stream's points as drawn when the drag began (once per drag). */
  function drawnOf(mv) {
    if (!mv.drawn) {
      mv.drawn = {};
      Object.entries(mv.ex.streams).forEach(([s, g]) => {
        const pa = mv.ex.nodes[g.n[0]], pb = mv.ex.nodes[g.n[1]];
        if (pa && pb) mv.drawn[s] = { pts: EX.pathPoints(EX.endPoint(pa, g.a, g.n[0]), EX.endPoint(pb, g.b, g.n[1]), g.h, g.c) };
      });
    }
    return mv.drawn;
  }
  /** The streams the drag does not touch whose lines run through the moved block where it is, or
   *  along its edge. */
  function hitsAt(mv) {
    if (mv.id[0] !== "B") return [];
    const box = [EX.wider(EX.boxAt(mv.cur, mv.id))], d = drawnOf(mv);         // (a line along its edge too)
    return Object.keys(d).filter((s) => !mv.touch.includes(s) && EX.crossings(d[s].pts, box));
  }
  /** What stream s, routed at the rest or the drop, keeps clear of: every other stream's line,
   *  and their ports on its own blocks (fit's avoid). Those routed already in this pass count
   *  as routed, the moved node's other streams as the last frame drew them, the rest as drawn. */
  function avoidFor(mv, s, out) {
    const d = drawnOf(mv), g = mv.ex.streams[s], segs = [], ports = {};
    // (out: that stream leaves the block there; opp counts those running the other way from s)
    const port = (id, e, leaves) => {
      if (!e || id[0] !== "B" || (id !== g.n[0] && id !== g.n[1])) return;
      const p = (ports[id] = ports[id] || { l: [], r: [], u: [], d: [], opp: { l: 0, r: 0, u: 0, d: 0 } });
      p[e[0]].push(e[1]);
      if (g.n[0] !== g.n[1] && leaves !== (id === g.n[0])) p.opp[e[0]]++;
    };
    Object.keys(mv.ex.streams).forEach((t) => {
      if (t === s) return;
      const gt = mv.ex.streams[t], r = out[t] || (mv.touch.includes(t) ? mv.last[t] : d[t]);
      if (r && r.pts) for (let i = 1; i < r.pts.length; i++) segs.push([r.pts[i - 1], r.pts[i]]);
      const e = out[t] || gt;
      port(gt.n[0], e.a, true);
      port(gt.n[1], e.b, false);
    });
    return { segs, ua: ports[g.n[0]] || null, ub: ports[g.n[1]] || null };
  }
  /** The paths of a stream the drag does not touch, its old d kept (the first time), and its
   *  name and values hidden while its line is drawn anew. */
  function extraPaths(mv, s) {
    if (!mv.extra[s]) {
      const el = [...mv.svg.querySelectorAll(".fs-edge")].find((e) => e.getAttribute("data-name") === s);
      mv.extra[s] = el ? [...el.querySelectorAll("path")].map((p) => [p, p.getAttribute("d")]) : [];
      [...mv.svg.querySelectorAll(".fs-tag")].filter((e) => e.getAttribute("data-name") === s).forEach((e) => { e.classList.add("drag-hide"); mv.xhid.push(e); });
    }
    return mv.extra[s];
  }
  /** Those streams drawn as they were again (the block moved on). */
  function unhit(mv) {
    Object.values(mv.extra).forEach((list) => list.forEach(([el, d]) => el.setAttribute("d", d)));
    mv.xhid.forEach((e) => e.classList.remove("drag-hide"));
    mv.extra = {};
    mv.xhid = [];
  }
  /** Route the streams a node drag touches between their ends as they are now, and draw them:
   *  each kept as it was while it reads, else the last frame's route while that reads, else
   *  routed again (sides free with allowSides). The rest and the drop (allowSides) take more
   *  care: each path keeps out of every other block and off the other streams' lines and ports
   *  (avoidFor), and the lines of others the moved block now sits on are routed again too
   *  (hitsAt). Returns the geometry by stream. */
  function routeTouching(mv, allowSides, useLast, budget) {
    const nodes = mv.ex.nodes, pos = (k) => (k === mv.id ? mv.cur : nodes[k]);
    const boxes = mv.id[0] === "B" ? mv.boxes.concat([EX.boxAt(mv.cur, mv.id)]) : mv.boxes, out = {};
    const hits = allowSides ? hitsAt(mv) : [], list = hits.length ? mv.touch.concat(hits) : mv.touch;
    // a frame routes what it can in its budget (ms): the streams left keep the path they show
    // for a frame more and go first in the next one (mv.pend), so a hub's frame stays short. A
    // stream whose path (or the last frame's) still reads costs next to nothing and always
    // goes; one to be routed again waits when the most a routing took (in this drag, or in the
    // last one: mv.est) would run past the budget, but the first of a frame always goes
    const t0 = performance.now(), order = budget ? mv.pend.concat(mv.touch.filter((s) => !mv.pend.includes(s))) : list;
    let routed = 0;
    mv.pend = [];
    order.forEach((s) => {
      const g = mv.ex.streams[s], pa = pos(g.n[0]), pb = pos(g.n[1]), last = useLast ? mv.last[s] : null;
      const cheap = !budget || EX.keeps(EX.withPins(g, s), pa, pb, g.n) || (last && EX.keeps(last, pa, pb, g.n));
      if (!cheap && routed && performance.now() - t0 + mv.est > budget) { mv.pend.push(s); return; }
      const t1 = performance.now(), r = EX.fit(g, pa, pb, boxes, false, allowSides, last, allowSides ? avoidFor(mv, s, out) : null, { n: g.n, s });
      if (!cheap) {
        const ms = performance.now() - t1;
        routed++;
        mv.est = Math.max(mv.est, ms);
        routeMs = mv.own = Math.max(mv.own, ms);
      }
      if (!hits.includes(s)) mv.last[s] = r;
      out[s] = r;
      const d = drawnPath(r.pts, g, s, r.a, r.b, pa, pb);
      (mv.paths[s] || (hits.includes(s) ? extraPaths(mv, s) : [])).forEach(([el]) => el.setAttribute("d", d));
    });
    return out;
  }
  /** One frame of a drag: the pointer's last position (a frame at most per display frame). */
  function moveFrame(svg, mv) {
    inGeo(mv.ctx, () => moveFrameIn(svg, mv));
  }
  function moveFrameIn(svg, mv) {
    mv.frame = 0;
    const p = mv.at && units(svg, mv.at[0], mv.at[1]);
    if (!p) return;
    const t0 = performance.now(), r1 = EX.r1;
    if (mv.kind === "node") {
      let x = mv.c0[0] + p[0] - mv.start[0], y = mv.c0[1] + p[1] - mv.start[1];
      if (!mv.alt) [x, y] = snapNode(mv, x, y);
      x = r1(x);
      y = r1(y);
      const same = x === mv.cur[0] && y === mv.cur[1];
      if (same && !mv.pend.length) return;
      if (!same) {
        mv.cur = [x, y];
        const t = `translate(${r1(x - mv.c0[0])} ${r1(y - mv.c0[1])})`;
        mv.moved.forEach((el) => el.setAttribute("transform", t));
        unhit(mv);                                 // (lines the rest drew round it go back)
        // over another block, feed or product the node shows it (the drop finds it room)
        const cl = clashAt(mv, mv.cur);
        if (mv.el && mv.el.classList.contains("clash") !== cl) mv.el.classList.toggle("clash", cl);
      }
      routeTouching(mv, false, true, FRAME_MS);
      if (mv.pend.length && !mv.frame) mv.frame = requestAnimationFrame(() => moveFrame(svg, mv));   // the rest, next frame
      // at rest (150 ms after the last move, the button still held) the routes the drop would store show
      if (!same) {
        clearTimeout(mv.restT);
        mv.restT = setTimeout(() => {
          if (svg._fsMove !== mv || clashAt(mv, mv.cur)) return;
          mv.rest = { at: mv.cur.slice(), res: inGeo(mv.ctx, () => routeTouching(mv, true, false)) };
        }, 150);
      }
    } else {
      const i = mv.up ? 0 : 1, g = mv.g, k = g.c.length;
      let v = mv.v0 + p[i] - mv.start[i];
      if (!mv.alt) {                               // to the grid, or level with a port (a Z made straight)
        const near = [mv.A[i], mv.B[i]].map((q) => [Math.abs(q - v), q]).filter(([d]) => d <= 6).sort((a, b) => a[0] - b[0])[0];
        v = near ? near[1] : Math.round(v / 10) * 10;
      }
      // the end segments keep their length out of their ports (a terminal's its own)
      let lo = -Infinity, hi = Infinity;
      const keep = (P, end) => {
        if (end) {
          const o = EX.OUT[end[0]][i];
          if (o > 0) lo = Math.max(lo, P[i] + EX.MIN_STUB + 1); else if (o < 0) hi = Math.min(hi, P[i] - EX.MIN_STUB - 1);
        } else if (mv.v0 >= P[i]) lo = Math.max(lo, P[i] + EX.TERM_MIN + 1);
        else hi = Math.min(hi, P[i] - EX.TERM_MIN - 1);
      };
      if (mv.j === 1) keep(mv.A, g.a);
      if (mv.j === k) keep(mv.B, g.b);
      v = r1(lo > hi ? mv.v0 : Math.max(lo, Math.min(hi, v)));
      if (v === mv.val) return;
      mv.val = v;
      g.c[mv.j - 1] = v;
      const d = drawnPath(EX.pathPoints(mv.A, mv.B, g.h, g.c), g, mv.name, g.a, g.b, mv.ex.nodes[g.n[0]], mv.ex.nodes[g.n[1]]);
      (mv.paths[mv.name] || []).forEach(([el]) => el.setAttribute("d", d));
    }
    if (FS.onFrame) FS.onFrame(performance.now() - t0);    // a frame-cost hook (ms) for performance checks; unset in normal use
  }
  /** The drop: the arrangement with the move in it, or null when nothing moved. */
  function dropMove(svg, mv) {
    return inGeo(mv.ctx, () => dropMoveIn(svg, mv));
  }
  function dropMoveIn(svg, mv) {
    if (mv.frame) { cancelAnimationFrame(mv.frame); moveFrameIn(svg, mv); }   // where the pointer let go
    clearTimeout(mv.restT);
    const r1 = EX.r1;
    if (mv.kind === "node") {
      const spot = freeSpot(mv, mv.cur);         // let go on another node: the nearest free spot
      if (spot !== mv.cur) { mv.cur = spot; unhit(mv); }
      if (mv.cur[0] === mv.c0[0] && mv.cur[1] === mv.c0[1]) return null;
      const res = mv.rest && mv.rest.at[0] === mv.cur[0] && mv.rest.at[1] === mv.cur[1] ? mv.rest.res : routeTouching(mv, true, false);
      mv.ex.nodes[mv.id] = mv.cur.slice();
      Object.keys(res).forEach((s) => {
        const r = res[s];
        mv.ex.streams[s] = { n: mv.ex.streams[s].n, a: r.a && [r.a[0], r1(r.a[1])], b: r.b && [r.b[0], r1(r.b[1])], h: r.h, c: r.c.map(r1) };
      });
    } else if (mv.val === mv.v0) return null;
    return { v: 1, mode: "custom", base: mv.fam, nodes: mv.ex.nodes, streams: mv.ex.streams };
  }
  /** After a drag: hidden things show again; put back as they were when nothing is stored. */
  function endMove(svg, mv, restore) {
    mv.hidden.forEach((el) => el.classList.remove("drag-hide"));
    svg.classList.remove("moving");
    if (mv.el) mv.el.classList.remove("clash");
    mv.xhid.forEach((el) => el.classList.remove("drag-hide"));
    if (!restore) return;
    unhit(mv);
    mv.moved.forEach((el) => el.removeAttribute("transform"));
    Object.values(mv.paths).forEach((list) => list.forEach(([el, d]) => el.setAttribute("d", d)));
  }
  /** Whether a block, terminal or segment is being dragged in this SVG. */
  FS.dragging = (svg) => !!(svg && svg._fsMove);
  /** The SVG stops showing its tab: a press, pan or drag on it ends, storing nothing. */
  FS.letGo = (svg) => { if (svg && svg._fsLetGo) svg._fsLetGo(); };
  /** Cancel the drag (Escape): everything back where it was, nothing stored; what came
   *  meanwhile is drawn now. */
  FS.cancelDrag = function (svg) {
    const mv = svg._fsMove;
    if (!mv) return;
    svg._fsMove = null;
    cancelAnimationFrame(mv.frame);
    clearTimeout(mv.restT);
    endMove(svg, mv, true);
    const p = svg._fsPending;
    if (p) { svg._fsPending = null; draw(svg, p); }
    if (svg._fsOn && svg._fsOn.moving) svg._fsOn.moving(false);
  };

  /** A click on an annotations marker (FS.render's v.pins) calls fn({kind, name}, the marker's
   *  element) instead of picking its block or stream (app-pins.js); null: none. */
  FS.onPin = function (svg, fn) {
    svg._fsPin = typeof fn === "function" ? fn : null;
  };

  /** A click on a preview's tag (FS.render's v.preview.tags) calls fn(its key, its element, the
   *  event) instead of picking anything; null: none. ``cls`` "fx": a run's result tag's instead
   *  (app-effects.js), glass over the drawing (fxLayer): fn(key, element, event,
   *  part, offset), part "line" (a click), "x" (its ×) or "move" (a drop; offset [dx, dy]) --
   *  each kind of tag its own. */
  FS.onTag = function (svg, fn, cls) {
    svg._fsTags = Object.assign({}, svg._fsTags, { [cls || ""]: typeof fn === "function" ? fn : null });
  };
  /** Light up a preview's objects ("block:NAME", "stream:NAME": drawn or new) with the pad of
   *  pv-on, at once; none clears. Kept in the view's context across a redraw. */
  FS.pvHot = function (svg, keys) {
    C(svg).pvHot = (keys || []).slice();
    pvHotOn(svg);
  };
  function pvHotOn(svg) {
    svg.querySelectorAll(".pv-on").forEach((el) => el.classList.remove("pv-on"));
    (C(svg).pvHot || []).forEach((k) => {
      markEls(svg, k).forEach((el) => el.classList.add("pv-on"));
      svg.querySelectorAll(`[data-pv="${CSS.escape(k)}"]`).forEach((el) => el.classList.add("pv-on"));
    });
  }
  /** Where the last preview drawn in this view context placed what a proposal adds, for the
   *  arrangement to keep once it is applied: {names (the new
   *  blocks), base (what is drawn now, as an explicit arrangement: FS.explicitOf), nodes (the
   *  new blocks' and terminals' centres), streams (the new streams' routes, {n, a, b, h, c}),
   *  ms (what placing took)}; null when no preview was drawn in it. ctx: a context (a tab's). */
  FS.pvKeep = function (ctx) {
    const pv = ctx && ctx.pv && ctx.pv.res, ex = pv && exOf(ctx);
    if (!pv || !ex) return null;
    const streams = {};
    pv.lines.forEach((l) => { if (!l.moved) streams[l.name] = { n: l.ex.n.slice(), a: l.ex.a, b: l.ex.b, h: l.ex.h, c: l.ex.c.slice() }; });
    return { names: pv.blocks.map((b) => b.name), base: copyEx(ex), nodes: Object.fromEntries(Object.entries(pv.nodes).map(([k, p]) => [k, p.slice()])),
             streams, ms: pv.ms, taken: ctx.pv.taken };
  };
  /** Whether a view context draws block NAME now (its last drawing). */
  FS.draws = (ctx, name) => !!(ctx && ctx.lay && ctx.lay.pos && ctx.lay.pos["B:" + name]);

  /** Wheel zoom, drag pan, a double-click on empty space to show it all, and clicks:
   *  on.pick(target | null), on.note(noteId), on.changes(target) (a dot of changes not seen
   *  yet: FS.render's v.changes); on.zoom(percent) when the scale changes and
   *  on.view() when the view comes to rest; on.peek(target, x, y) once the pointer has rested
   *  on a stream for 350 ms (client px: each move on it starts the wait again), on.peek(null)
   *  when it leaves it, presses or turns the wheel. Where things can be moved (FS.render's
   *  canMove), a press on a block, feed, product or a stream's inner segment that moves 4 px
   *  drags it (Alt: no snapping); the drop calls on.layout(arrangement), on.moving(bool) says
   *  when a drag starts and ends, and the click that ends a drag picks nothing. */
  FS.attach = function (svg, on) {
    let drag = null, panned = false;           // a pan must not count as a click on empty space
    let press = null, dragged = false;         // a press that may become a drag; a drag ended the press
    let hover = null, shown = null, held = false, peekTimer = 0, px = 0, py = 0;
    svg._fsOn = on;
    // (after a press the stream under the pointer gets no card until the pointer leaves it)
    const unpeek = (stay) => {
      clearTimeout(peekTimer);
      held = stay === true;
      if (!held) hover = null;
      if (shown !== null) { shown = null; if (on.peek) on.peek(null); }
    };
    // the press is let go: what came meanwhile is drawn, in a task after the click that follows
    const letGo = () => {
      svg._fsHeld = false;
      setTimeout(() => {
        const p = svg._fsPending;
        if (p && !svg._fsHeld) { svg._fsPending = null; draw(svg, p); }
      }, 0);
    };
    // size changes: a ResizeObserver reports at most once a frame, after layout and before
    // paint, so the view is adapted in the same frame (a further rAF would show one frame
    // of the old viewBox at the new size on every step of a splitter drag)
    new ResizeObserver(() => FS.resize(svg)).observe(svg);
    svg.addEventListener("mousemove", (ev) => {
      px = ev.clientX;
      py = ev.clientY;
      if (drag || svg._fsMove) return;
      // (an annotations marker is not its stream: no hover card over it)
      const g = ev.target.closest && !ev.target.closest(".pinmark") && ev.target.closest('[data-kind="stream"]'), name = g ? g.getAttribute("data-name") : null;
      // over a stream's inner segment where things move: the cursor says which way it goes
      if (C(svg).canMove && !press) {
        const hit = ev.target.classList && ev.target.classList.contains("hit") ? name : null;
        segClass(svg, hit ? segAt(svg, hit, ev.clientX, ev.clientY) : null);
      }
      if (name !== hover) {
        hover = name;
        held = false;
        if (name !== svg._fsHot) hotOn(svg, name);
        if (shown !== null && shown !== name) { shown = null; if (on.peek) on.peek(null); }
      }
      // the card once the pointer rests: every move on the stream starts the wait again (a
      // timer only, nothing is measured)
      clearTimeout(peekTimer);
      if (name !== null && !held && shown !== name && on.peek) peekTimer = setTimeout(() => { shown = name; on.peek({ kind: "stream", name }, px, py); }, 350);
    });
    svg.addEventListener("mouseleave", () => { unpeek(); hotOn(svg, null); if (!svg._fsMove) segClass(svg, null); });
    svg.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      if (svg._fsMove) return;                   // no zoom under a drag
      unpeek();
      const c = C(svg), r = svg.getBoundingClientRect(), v = c.view;
      if (!v) return;
      const f = ev.deltaY > 0 ? 1.12 : 1 / 1.12;
      zoomTo(svg, v.x + ((ev.clientX - r.left) / r.width) * v.w, v.y + ((ev.clientY - r.top) / r.height) * v.h, (v.w / r.width) * f);
    }, { passive: false });
    svg.addEventListener("dblclick", (ev) => {
      // (two quick clicks on a tag -- a result's path pinned and closed -- are not a double-click on space)
      if (ev.target.closest("[data-kind],[data-note],.fs-tag2") || !C(svg).lay) return;
      FS.fit(svg, true);
    });
    // a press: on a block, feed, product or a stream's inner segment it may become a drag (the
    // elements are found again when it starts); on empty space a pan: the SVG's box is read
    // when it starts, the view moved once a frame at most (pointer events can come faster than
    // frames), from the offset since the press
    svg.addEventListener("mousedown", (ev) => {
      unpeek(true);
      dragged = false;
      press = null;
      svg._fsHeld = true;
      const c = C(svg), t = ev.target;
      if (t.closest("[data-kind],[data-note]")) {
        if (!c.canMove || !c.lay || ev.button !== 0 || ev.ctrlKey || ev.metaKey) return;
        const node = t.closest(".fs-node, .fs-term");
        if (node) press = { kind: "node", id: node.getAttribute("data-node"), x: ev.clientX, y: ev.clientY };
        else if (t.classList.contains("hit")) {
          const name = t.parentNode.getAttribute("data-name"), s = segAt(svg, name, ev.clientX, ev.clientY);
          if (s) press = { kind: "seg", name, j: s.j, up: s.up, x: ev.clientX, y: ev.clientY };
        }
        // what a drag starts from, made now rather than as it starts (and the router warmed)
        if (press) { const ex = exOf(c); if (press.kind === "node") inGeo(c, () => warm(ex, press.id)); }
        return;
      }
      if (!c.view) return;
      const r = svg.getBoundingClientRect();
      drag = { x: ev.clientX, y: ev.clientY, v: Object.assign({}, c.view), w: r.width, h: r.height, at: null, frame: 0 };
      panned = false;
    });
    const pan = () => {
      const d = drag;
      if (!d) return;
      d.frame = 0;
      const view = C(svg).view;
      view.x = d.v.x - ((d.at.x - d.x) / d.w) * d.v.w;
      view.y = d.v.y - ((d.at.y - d.y) / d.h) * d.v.h;
      apply(svg);
    };
    const release = () => {
      if (drag && drag.frame) { cancelAnimationFrame(drag.frame); pan(); }   // where the pointer let go
      drag = null;
      press = null;
      const mv = svg._fsMove;
      if (mv && mv.ctx !== C(svg)) { FS.cancelDrag(svg); letGo(); }   // (another tab's: FS.use lets go first)
      else if (mv) {
        svg._fsMove = null;
        const obj = dropMove(svg, mv);
        endMove(svg, mv, !obj);
        letGo();                                 // (the drop's own drawing is not held back)
        if (obj && on.layout) on.layout(obj, mv.ctx);
        if (on.moving) on.moving(false);
      } else if (svg._fsHeld) letGo();
    };
    // the SVG shows another context (FS.use): a drag is put back and stores nothing, a press or
    // pan ends, what was held back for it is dropped (the next render draws the new context),
    // and the click that ends the press picks nothing
    svg._fsLetGo = () => {
      svg._fsPending = null;
      if (svg._fsMove) FS.cancelDrag(svg);
      if (drag && drag.frame) cancelAnimationFrame(drag.frame);
      if (svg._fsHeld) dragged = true;
      drag = null;
      press = null;
      svg._fsHeld = false;
      segClass(svg, null);
      unpeek();
    };
    window.addEventListener("mousemove", (ev) => {
      if (svg._fsHeld && ev.buttons === 0) { release(); return; }   // a release nobody heard (outside the window)
      if (press && !svg._fsMove && Math.abs(ev.clientX - press.x) + Math.abs(ev.clientY - press.y) > 4) {
        const mv = startMove(svg, press);
        press = null;
        if (mv) {
          svg._fsMove = mv;
          dragged = true;
          unpeek(true);
          if (mv.kind === "node") segClass(svg, null);
          if (on.moving) on.moving(true);
        }
      }
      const mv = svg._fsMove;
      if (mv) {
        mv.at = [ev.clientX, ev.clientY];
        mv.alt = ev.altKey;
        if (!mv.frame) mv.frame = requestAnimationFrame(() => moveFrame(svg, mv));
        return;
      }
      if (!drag) return;
      if (Math.abs(ev.clientX - drag.x) + Math.abs(ev.clientY - drag.y) > 4) { panned = true; C(svg).fitted = false; }
      drag.at = { x: ev.clientX, y: ev.clientY };
      if (!drag.frame) drag.frame = requestAnimationFrame(pan);
    });
    window.addEventListener("mouseup", release);
    window.addEventListener("blur", () => {      // the window lost the pointer mid-press
      if (svg._fsMove) FS.cancelDrag(svg);
      if (svg._fsHeld) { drag = null; press = null; letGo(); }
    });
    svg.addEventListener("click", (ev) => {
      if (dragged) { dragged = false; panned = false; return; }   // the end of a drag picks nothing
      const dot = on.changes && ev.target.closest(".chdot"), owner = dot && dot.closest("[data-kind]");
      if (owner) return on.changes({ kind: owner.getAttribute("data-kind"), name: owner.getAttribute("data-name") });
      const tag = svg._fsTags && ev.target.closest(".fs-tag2");     // a preview's or a result tag (FS.onTag)
      const tagFn = tag && svg._fsTags[tag.classList.contains("fx") ? "fx" : ""];
      if (tagFn) { panned = false; return tagFn(tag.getAttribute("data-tag"), tag, ev); }
      const pin = svg._fsPin && ev.target.closest(".pinmark"), pinned = pin && pin.closest("[data-kind]");
      if (pinned) return svg._fsPin({ kind: pinned.getAttribute("data-kind"), name: pinned.getAttribute("data-name") }, pin);
      const note = ev.target.closest("[data-note]");
      if (note) return on.note(note.getAttribute("data-note"));
      const g = ev.target.closest("[data-kind]");
      if (g) on.pick({ kind: g.getAttribute("data-kind"), name: g.getAttribute("data-name") });
      else if (!panned) on.pick(null);
      panned = false;
    });
  };
})();
