/* Block icons for the flowsheet's icon view (flowsheet.js): each Aspen block type drawn as its
 * equipment symbol, in the monochrome line style of a journal figure, and which of a symbol's
 * nozzles each stream meets.
 *
 * window.FSI:
 *   K           drawing units per icon unit (a square symbol is 56 units across, as a box is tall)
 *   types       {Type: {w, h, body, ports, g}}: the frame (icon units), the body's box (where a
 *               stream with no nozzle of its own meets the symbol), each nozzle's free end and
 *               the way it points out ("l" | "r" | "u" | "d"), and the drawing as markup.
 *               Generated (the block at the end of this file) from the symbols' own files by
 *               ~/.aspen-mcp/dev/block_icons/build_js.py; not edited by hand.
 *   shape(type) the symbol of an Aspen block type, its case ignored (Aspen and the docs spell
 *               a few differently: Cfuge, Vscrub), the plain vessel for a type with none:
 *               {key, w, h, body, ports, g}
 *   assign(fs, key)  where each stream of a flowsheet meets its blocks (below)
 *
 * Which nozzle a stream meets comes from the port Aspen connects it to (a snapshot's from_port and
 * to_port, "VD(OUT)"): PORTS below maps each type's ports onto nozzles. Several streams on one
 * port take the port's nozzles in the order of their other ends, so they do not cross; a port
 * with no nozzle, or more streams than nozzles, meets the body's wall instead, on the side its
 * role says: feeds left, vapour and gas up, liquid, bottoms and solids down, other products
 * right; a wall with no room left passes it on to the next side. Heat and work streams never
 * meet a nozzle. With no port at all (an older server), feeds take the inlet nozzles and
 * products the outlet ones, top to bottom in the order of their other ends.
 */
(function () {
  "use strict";
  const FSI = (window.FSI = { K: 0.875 });

  // Each type's ports, as Aspen names them over COM, onto nozzles: "PORT:nozzle,nozzle" (the
  // streams on that port take them in order); "A+B:nozzles" several ports sharing the nozzles;
  // "PORT:-" a port with no nozzle (its role's side), "PORT:-u" one whose wall is given. A port
  // not listed meets the wall its role says. Some types are listed also by the ids this repo's
  // docs use (OF, UF, SOL, ...): they only match where Aspen sends them.
  const FLASH = "F(IN):feed";
  const PLAIN = "F(IN):feed P(OUT):product";
  const SPLIT = "F(IN):feed P(OUT):product,product2";
  const COL = "F(IN):feed D(OUT):distillate B(OUT):bottoms CWD(OUT):-r";
  // (a liquid distillate takes the distillate nozzle first; a vapour one beside it leaves off the
  // top of the overhead line, a vapour one alone takes the distillate nozzle)
  const FRAC = "F(IN):feed LD(OUT):distillate VD(OUT):distillate,overhead B(OUT):bottoms SP(OUT):-r WD(OUT):-r";
  const GS = "F(IN):feed G(OUT):gas S(OUT):solids GAS(OUT):gas SOL(OUT):solids";
  const PORTS = {
    Mixer: "F(IN):feed,feed2 P(OUT):product",
    FSplit: SPLIT, SSplit: SPLIT,
    Makeup: "F(IN):feed FM(IN):makeup M(IN):makeup P(OUT):product O(OUT):-r",
    Flash2: `${FLASH} V(OUT):vapour L(OUT):liquid`,
    Flash3: `${FLASH} V(OUT):vapour L1(OUT):liquid1 L2(OUT):liquid2`,
    Decanter: `${FLASH} L1(OUT):liquid1 L2(OUT):liquid2`,
    Sep: "F(IN):feed P(OUT):product1,product2,product3",
    Sep2: "F(IN):feed O(OUT):product1 B(OUT):product2 P1(OUT):product1 P2(OUT):product2",
    Heater: PLAIN,
    HeatX: "H(IN):shell_in H(OUT):shell_out C(IN):tube_in C(OUT):tube_out",
    HXFlux: "H(IN):annulus_in H(OUT):annulus_out C(IN):tube_in C(OUT):tube_out HS(IN):tube_in HS(OUT):tube_out",
    MHeatX: "HF(IN)+CF(IN)+HLF(IN)+CLF(IN):in1,in2,in3 HP(OUT)+CP(OUT)+HLP(OUT)+CLP(OUT):out1,out2,out3 HWD(OUT):-d CWD(OUT):-d",
    RadFrac: FRAC, RateFrac: FRAC,
    MultiFrac: "F(IN):feed LD(OUT):distillate VD(OUT):distillate,overhead B(OUT):bottoms SP(OUT):product CWD(OUT):-r",
    PetroFrac: "MF(IN):feed LD(OUT):distillate VD(OUT):distillate,overhead SP(OUT):side1,side2 B(OUT):bottoms SF(IN):- SB(OUT):- WD(OUT):-r",
    SCFrac: "F(IN):feed SF(IN):steam D(OUT):distillate SP(OUT):side1,side2,side3 B(OUT):bottoms",
    DSTWU: COL, Distl: COL, ConSep: COL,
    Extract: "TF(IN):feed BF(IN):solvent TP(OUT):extract BP(OUT):raffinate SF(IN):- SP(OUT):- F(IN):feed L1(OUT):extract L2(OUT):raffinate",
    RStoic: PLAIN, RYield: PLAIN, RGibbs: PLAIN,
    REquil: "F(IN):feed L(OUT):product V(OUT):-u",
    RCSTR: "F(IN):feed P(OUT):product VI(IN):-l",
    RPlug: "F(IN):feed P(OUT):product C(IN):-u C(OUT):-d",
    RBatch: "BC(IN)+CF(IN):feed RP(OUT):product VP(OUT):-u",
    Fluidbed: "F(IN):feed G(IN):gas_in G(OUT):gas_out P(OUT):solids_out G2(IN):- H(IN):- H(OUT):-",
    Pump: PLAIN, Compr: PLAIN, Valve: PLAIN, Pipe: PLAIN, Pipeline: PLAIN,
    MCompr: "S1F(IN):feed FLS(OUT):product IF(IN):-l LK(OUT):-d",
    Crystallizer: "F(IN):feed V(OUT):vapour P(OUT):product",
    Crusher: PLAIN,
    Screen: "F(IN):feed O(OUT):oversize U(OUT):undersize MS(OUT):- OVER(OUT):oversize UNDER(OUT):undersize",
    Classifier: "F(IN):feed P(OUT):fines S(OUT):coarse G(IN):- FINES(OUT):fines COARSE(OUT):coarse",
    Granulator: "F(IN):feed G(OUT):gas P(OUT):product L(IN):- G(IN):-",
    Dryer: "FEED(IN):wet GAS(IN):gas PRODUCT(OUT):dry EXHAUST(OUT):exgas G2(IN):- WET(IN):wet DRY(OUT):dry EXGAS(OUT):exgas",
    Swash: "S(IN):feed L(IN):wash S(OUT):product L(OUT):filtrate F(IN):feed WASH(IN):wash P(OUT):product FILT(OUT):filtrate",
    CCD: "S(IN):feed L(IN):wash L(OUT):overflow S(OUT):underflow SF(IN):- SP(OUT):- PS(OUT):- F(IN):feed W(IN):wash OF(OUT):overflow UF(OUT):underflow",
    Cyclone: GS, ESP: GS, FabFl: GS,
    HyCyc: "F(IN):feed L(OUT):overflow S(OUT):underflow OF(OUT):overflow UF(OUT):underflow",
    CFuge: "F(IN):feed L(OUT):liquid P(OUT):solids O(OUT):- SOL(OUT):solids LIQ(OUT):liquid",
    Filter: "F(IN):feed L(OUT):liquid S(OUT):solids F2(IN):- P2(OUT):- SOL(OUT):solids FILT(OUT):liquid",
    CfFilter: "F(IN):feed P(OUT):permeate R(OUT):retentate FILT(OUT):permeate CONC(OUT):retentate",
    VScrub: "F(IN):feed L(IN):liquid_in G(OUT):gas S(OUT):liquid GAS(IN):feed LIQ(IN):liquid_in GOUT(OUT):gas LOUT(OUT):liquid",
    Electrolyzer: "FA(IN)+FS(IN)+FC(IN):feed PA(OUT):anode_gas PC(OUT):cathode_gas ANODE(OUT):anode_gas CATHODE(OUT):cathode_gas",
    Mult: PLAIN, ClChng: PLAIN, Analyzer: PLAIN,
    Dupl: "F(IN):feed P(OUT):product1,product2",
    Selector: "F(IN):feed1,feed2 P(OUT):product",
  };
  // heat and work: drawn dashed, on the wall (never a nozzle, but where PORTS gives one: HXFlux).
  // WD, CWD and HWD are free water drawn off (material): Pump and Compr have WD beside their WS
  const ENERGY = new Set(["HS", "WS", "CHS", "RHS", "MHS", "SHS", "PHS", "Q-IN", "Q-OUT"]);
  const UP = new Set(["V", "VD", "VP", "G", "GAS", "GOUT", "EXHAUST", "EXGAS"]);
  const DOWN = new Set(["L", "B", "BP", "S", "SOL", "LK", "U", "UF", "WD", "CWD", "HWD"]);
  const COLUMNS = new Set(["RadFrac", "RateFrac", "MultiFrac", "PetroFrac", "SCFrac", "DSTWU", "Distl", "ConSep", "Extract"]);
  const PASS = { in: ["l", "u", "d"], out: ["r", "d", "u"] };   // a full wall passes an end on, in this order
  const PORT_U = 10 / FSI.K;                                     // ends on a wall keep this apart (flowsheet.js PORT)

  /** "VD(OUT)" -> {base: "VD", dir: "OUT"}; null for anything else. */
  FSI.parsePort = function (id) {
    const m = /^\s*([A-Za-z0-9_-]+)\s*\(\s*(IN|OUT)\s*\)\s*$/i.exec(String(id || ""));
    return m ? { base: m[1].toUpperCase(), dir: m[2].toUpperCase() } : null;
  };
  FSI.isEnergy = (port) => { const p = FSI.parsePort(port); return !!p && ENERGY.has(p.base); };

  let lower = null;
  /** The symbol of an Aspen block type (its case ignored), the plain vessel for one with none. */
  FSI.shape = function (type) {
    if (!lower) {
      lower = {};
      Object.keys(FSI.types).forEach((k) => { lower[k.toLowerCase()] = k; });
    }
    const key = lower[String(type || "").toLowerCase()] || "_Generic";
    return Object.assign({ key }, FSI.types[key]);
  };

  // each type's table, read once: [{ports: Set of "BASE(DIR)", nozzles: [...], side: wall or
  // null}], in its order; the nozzles feeds and products of a stream with no port take
  const tables = {};
  function tableOf(key) {
    if (tables[key]) return tables[key];
    const t = FSI.types[key] || FSI.types._Generic, spec = PORTS[key];
    const groups = [], ins = new Set(), outs = new Set();
    if (spec) {
      spec.split(/\s+/).forEach((tok) => {
        const i = tok.lastIndexOf(":"), ports = tok.slice(0, i).split("+").map((p) => p.toUpperCase().replace(/\s+/g, ""));
        const rhs = tok.slice(i + 1), free = rhs[0] === "-", nozzles = free ? [] : rhs.split(",").filter((n) => t.ports[n]);
        groups.push({ ports: new Set(ports), nozzles, side: free && rhs[1] ? rhs[1] : null });
        ports.forEach((p) => nozzles.forEach((n) => (/\(IN\)$/.test(p) ? ins : outs).add(n)));
      });
    } else {
      // (no table: the user models and the plain vessel) feed in, the rest out
      Object.keys(t.ports).forEach((n) => (/^feed/.test(n) ? ins : outs).add(n));
    }
    // inlets left first (top to bottom), then the others; outlets the same from the right
    const order = (set, first) => [...set].sort((a, b) => {
      const p = t.ports[a], q = t.ports[b];
      return (p[2] === first ? 0 : 1) - (q[2] === first ? 0 : 1) || p[1] - q[1] || p[0] - q[0];
    });
    return (tables[key] = { groups, ins: order(ins, "l"), outs: order(outs, "r"), mapped: !!spec });
  }

  /** The wall a stream with no nozzle meets by its role: an inlet the left; a vapour or gas
   *  outlet the top; liquid, bottoms, solids and water drawn off the bottom (a column's water,
   *  beside its distillate: the right); any other outlet the right. */
  function roleSide(key, p, inlet) {
    if (inlet) return "l";
    if (!p) return "r";
    if ((p.base === "WD" || p.base === "CWD") && COLUMNS.has(key)) return "r";
    if (UP.has(p.base)) return "u";
    if (DOWN.has(p.base)) return "d";
    return "r";
  }
  /** How many ends a wall takes: PORT_U apart along its middle 70 %. */
  function capOf(t, side) {
    const b = t.body, len = side === "l" || side === "r" ? b[3] - b[1] : b[2] - b[0];
    return Math.floor((0.7 * len) / PORT_U) + 1;
  }

  /** Where each stream of fs ({blocks: [{name, type}], streams: [{name, from, to, from_port,
   *  to_port}]}) meets its blocks: Map stream name -> {a, b}, a its start, b its end, each null
   *  at a feed or product, else {block, key (the symbol), nozzle (its name, or null: the wall),
   *  side, tip ([x, y] icon units, or null), energy, bias: -1 or 1 for one passed on to the wall
   *  before or after a port's nozzles (up or left of them; down or right), else 0}. key(stream, end, axis): where the stream's
   *  other end lies along "x" or "y" (the order several on one port take their nozzles in). */
  FSI.assign = function (fs, key) {
    const out = new Map(), byBlock = new Map();
    const typeOf = new Map((fs.blocks || []).map((b) => [b.name, b.type]));
    (fs.streams || []).forEach((s) => {
      const energy = FSI.isEnergy(s.from_port) || FSI.isEnergy(s.to_port);
      const rec = { a: null, b: null, energy };
      out.set(s.name, rec);
      [["a", s.from, s.from_port, false], ["b", s.to, s.to_port, true]].forEach(([end, blk, port, inlet]) => {
        if (!blk) return;
        const e = { stream: s.name, end, inlet, port: FSI.parsePort(port), energy, block: blk };
        rec[end] = e;
        (byBlock.get(blk) || byBlock.set(blk, []).get(blk)).push(e);
      });
    });
    const sortBy = (list, axis) => list.sort((p, q) => key(p.stream, p.end, axis) - key(q.stream, q.end, axis) || (p.stream < q.stream ? -1 : p.stream > q.stream ? 1 : 0));
    byBlock.forEach((ends, blk) => {
      const sh = FSI.shape(typeOf.get(blk)), t = FSI.types[sh.key], tb = tableOf(sh.key), taken = new Set();
      const pin = (e, n) => { taken.add(n); Object.assign(e, { nozzle: n, side: t.ports[n][2], tip: [t.ports[n][0], t.ports[n][1]] }); };
      ends.forEach((e) => { e.key = sh.key; e.nozzle = null; e.side = null; e.tip = null; });
      // the table's ports, in its order, each onto its nozzles (one end a nozzle)
      tb.groups.forEach((g) => {
        const mine = ends.filter((e) => !e.side && e.port && g.ports.has(`${e.port.base}(${e.port.dir})`));
        if (!mine.length) return;
        if (g.side) { mine.forEach((e) => { e.want = g.side; }); return; }
        // (fewer streams than nozzles: the first ones the table lists, so a port's nozzles go in
        // its order of preference; then in order along the wall, as many streams take them)
        const left = g.nozzles.filter((n) => !taken.has(n)), free = mine.length < left.length ? left.slice(0, mine.length) : left;
        const sides = new Set(free.map((n) => t.ports[n][2]));
        const axis = [...sides].every((s) => s === "u" || s === "d") ? "x" : "y", ix = axis === "x" ? 0 : 1;
        const noz = free.slice().sort((a, b) => t.ports[a][ix] - t.ports[b][ix]);
        // more streams than nozzles: the middle ones take the nozzles, those before them and
        // after them meet the wall beside them (passed on up and down where it is full)
        const list = sortBy(mine, axis), extra = Math.max(0, list.length - noz.length), before = Math.floor(extra / 2);
        list.forEach((e, i) => {
          if (i < before) e.order = -1;
          else if (i - before < noz.length) pin(e, noz[i - before]);
          else e.order = 1;
        });
      });
      // a type with no table: each end onto a nozzle on its role's side, while one is free
      if (!tb.mapped) {
        ends.filter((e) => !e.side && e.port && !e.energy).forEach((e) => {
          const side = roleSide(sh.key, e.port, e.inlet), list = e.inlet ? tb.ins : tb.outs;
          const n = list.find((m) => !taken.has(m) && t.ports[m][2] === side);
          if (n) pin(e, n);
        });
      }
      // no port at all: feeds onto the inlet nozzles, products onto the outlet ones, in order
      // (more than there are: the middle ones, as above)
      [[true, tb.ins], [false, tb.outs]].forEach(([inlet, list]) => {
        const mine = ends.filter((e) => !e.side && !e.port && e.inlet === inlet && !e.energy);
        const noz = list.filter((n) => !taken.has(n)), before = Math.floor(Math.max(0, mine.length - noz.length) / 2);
        sortBy(mine, "y").forEach((e, i) => {
          if (i < before) e.order = -1;
          else if (i - before < noz.length) pin(e, noz[i - before]);
          else e.order = 1;
        });
      });
      // the rest meet the wall: their role's side, passed on while it is full
      const used = { l: 0, r: 0, u: 0, d: 0 };
      Object.values(t.ports).forEach((p) => { used[p[2]]++; });
      ends.filter((e) => !e.side).forEach((e) => {
        const role = e.want || (e.energy ? (e.inlet ? "l" : "r") : roleSide(sh.key, e.port, e.inlet));
        let pass = PASS[e.inlet ? "in" : "out"];
        if (e.order) pass = e.order < 0 ? ["u", "d"] : ["d", "u"];     // (before the nozzles: up; after: down)
        const seq = [role].concat(pass.filter((s) => s !== role));
        e.side = seq.find((s) => used[s] < capOf(t, s)) || role;
        used[e.side]++;
      });
      ends.forEach((e) => { e.bias = e.nozzle ? 0 : e.order || 0; delete e.want; delete e.order; delete e.port; delete e.stream; delete e.end; });
    });
    return out;
  };

  // ---- generated by ~/.aspen-mcp/dev/block_icons/build_js.py: do not edit below ----
  FSI.types = {
    "_Generic": { w: 64, h: 64, body: [20, 8, 44, 56], ports: {"feed":[15,32,"l"],"top":[32,3,"u"],"product":[49,32,"r"],"bottom":[32,61,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M15,32 H20 M44,32 H49 M32,3 V8 M32,56 V61\"/><path d=\"M20,14 A12,6 0 0 1 44,14 V50 A12,6 0 0 1 20,50 Z\" fill=\"#ffffff\"/></g>" },
    "Analyzer": { w: 32, h: 32, body: [6, 6, 26, 26], ports: {"feed":[1,16,"l"],"product":[31,16,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M1,16 H6 M26,16 H31\"/><path d=\"M6,6 H26 V26 H6 Z\" fill=\"#ffffff\"/><path d=\"M9.5,21 A6.5,6.5 0 0 1 22.5,21 Z\"/><path d=\"M16,21 L19.5,15\"/></g>" },
    "CCD": { w: 96, h: 48, body: [6, 12, 90, 36], ports: {"feed":[1,20,"l"],"wash":[80,6,"u"],"overflow":[16,6,"u"],"underflow":[80,43,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M1,20 H6 M80,6 V12 M16,6 V12 M80,36 V43\"/><path d=\"M38,16 H26 M70,16 H58\"/><path d=\"M16,36 V41 H32 V24 H38 M48,36 V41 H64 V24 H70\"/><path d=\"M6,12 H26 V28 L19,36 H13 L6,28 Z M38,12 H58 V28 L51,36 H45 L38,28 Z M70,12 H90 V28 L83,36 H77 L70,28 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M6,28 H26 L19,36 H13 Z M38,28 H58 L51,36 H45 Z M70,28 H90 L83,36 H77 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M6,28 H26 M38,28 H58 M70,28 H90\"/><path d=\"M6,12 H26 V28 L19,36 H13 L6,28 Z M38,12 H58 V28 L51,36 H45 L38,28 Z M70,12 H90 V28 L83,36 H77 L70,28 Z\"/></g>" },
    "CfFilter": { w: 96, h: 48, body: [14, 10, 82, 38], ports: {"feed":[3,24,"l"],"retentate":[93,24,"r"],"permeate":[48,43,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M3,24 H8 M88,24 H93 M48,38 V43\"/><path d=\"M8,19 H14 V29 H8 Z M82,19 H88 V29 H82 Z\" fill=\"#ffffff\"/><path d=\"M14,10 H82 V38 H14 Z\" fill=\"#ffffff\"/><path d=\"M14,19 H82 V29 H14 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M14,19 H82 M14,29 H82\" stroke-dasharray=\"2 4\"/><path d=\"M14,10 V38 M82,10 V38\"/></g>" },
    "CFuge": { w: 64, h: 64, body: [11, 18, 53, 56], ports: {"feed":[6,26,"l"],"solids":[58,40,"r"],"liquid":[32,61,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M6,26 H11 M53,40 H58 M32,56 V61\"/><path d=\"M11,18 H53 V46 L37,56 H27 L11,46 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M18,24 H22 V38 H42 V24 H46 V42 H18 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M18,22 V42 H46 V22\" stroke-dasharray=\"2 4\"/><path d=\"M32,9 V42\"/><path d=\"M11,18 H53 V46 L37,56 H27 L11,46 Z\"/><path d=\"M26,2 H38 V9 H26 Z\" fill=\"#ffffff\"/></g>" },
    "Classifier": { w: 64, h: 64, body: [16, 8, 48, 52], ports: {"feed":[11,32,"l"],"fines":[32,3,"u"],"coarse":[32,57,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M11,32 H16 M32,52 V57\"/><path d=\"M16,8 H48 V34 L36,52 H28 L16,34 Z\" fill=\"#ffffff\"/><path d=\"M32,3 V12\"/><path d=\"M24,12 H40 V26 H24 Z\" fill=\"#ffffff\"/><path d=\"M28,12 V26 M32,12 V26 M36,12 V26\"/></g>" },
    "ClChng": { w: 32, h: 32, body: [6, 6, 26, 26], ports: {"feed":[1,16,"l"],"product":[31,16,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M1,16 H6 M26,16 H31\"/><path d=\"M6,6 H26 V26 H6 Z\" fill=\"#ffffff\"/><circle cx=\"12\" cy=\"16\" r=\"3\" fill=\"#ffffff\"/><path d=\"M17,13 H23 V19 H17 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M17,13 H23 V19 H17 Z\"/></g>" },
    "Compr": { w: 64, h: 64, body: [14, 15, 50, 49], ports: {"feed":[9,32,"l"],"product":[55,32,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M9,32 H14 M50,32 H55\"/><path d=\"M14,15 L50,25 V39 L14,49 Z\" fill=\"#ffffff\"/></g>" },
    "ConSep": { w: 48, h: 96, body: [6, 13, 26, 83], ports: {"feed":[1,48,"l"],"distillate":[47,24,"r"],"bottoms":[47,92,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M1,48 H6\"/><path d=\"M16,13 V2 H38 V5\"/><path d=\"M38,19 V24\"/><path d=\"M26,24 H47\"/><path d=\"M38,75 V71 H26\"/><path d=\"M16,83 V92 H47\"/><path d=\"M38,89 V92\"/><path d=\"M6,18 A10,5 0 0 1 26,18 V78 A10,5 0 0 1 6,78 Z\" fill=\"#ffffff\"/><path d=\"M9,60 H23 L16,44 Z\"/><path d=\"M16,44 Q11,57 23,60\"/><circle cx=\"38\" cy=\"12\" r=\"7\" fill=\"#ffffff\"/><path d=\"M31,12 L33.5,8.5 L36.5,15.5 L39.5,8.5 L42.5,15.5 L45,12\"/><circle cx=\"38\" cy=\"82\" r=\"7\" fill=\"#ffffff\"/><path d=\"M31,82 L33.5,78.5 L36.5,85.5 L39.5,78.5 L42.5,85.5 L45,82\"/></g>" },
    "Crusher": { w: 64, h: 64, body: [10, 7, 54, 52], ports: {"feed":[32,2,"u"],"product":[32,58,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M32,2 V7 M32,52 V58\"/><path d=\"M10,7 H54 L48,15 V40 L38,52 H26 L16,40 V15 Z\" fill=\"#ffffff\"/><path d=\"M19,15 L22,19 L20,23 L24,27 L22,31 L26,35 L25,40 L30,44\"/><path d=\"M45,15 L42,19 L44,23 L40,27 L42,31 L38,35 L39,40 L34,44\"/></g>" },
    "Crystallizer": { w: 64, h: 64, body: [16, 8, 48, 55], ports: {"feed":[11,28,"l"],"vapour":[32,3,"u"],"product":[32,60,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M11,28 H16 M32,3 V8 M32,55 V60\"/><path d=\"M16,16 A16,8 0 0 1 48,16 V38 L36,55 H28 L16,38 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M16,22 H48 V38 L36,55 H28 L16,38 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M16,22 H48\"/><path d=\"M24,27 L27.5,31 L24,35 L20.5,31 Z M40,27 L43.5,31 L40,35 L36.5,31 Z M32,37 L35.5,41 L32,45 L28.5,41 Z\" fill=\"#ffffff\"/><path d=\"M16,16 A16,8 0 0 1 48,16 V38 L36,55 H28 L16,38 Z\"/></g>" },
    "Cyclone": { w: 64, h: 64, body: [18, 14, 44, 56], ports: {"feed":[12,18,"l"],"gas":[32,3,"u"],"solids":[32,61,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M12,18 H18 M32,56 V61\"/><path d=\"M18,14 H44 V30 L35,56 H29 L20,30 V22 H18 Z\" fill=\"#ffffff\"/><path d=\"M32,3 V7\"/><path d=\"M28,7 H36 V25 H28 Z\" fill=\"#ffffff\"/></g>" },
    "Decanter": { w: 96, h: 48, body: [10, 10, 86, 34], ports: {"feed":[5,22,"l"],"liquid1":[90,16,"r"],"liquid2":[72,39,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M5,22 H10 M85,16 H90 M72,34 V39\"/><path d=\"M16,10 H80 A6,12 0 0 1 80,34 H16 A6,12 0 0 1 16,10 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M10.3,25.5 H85.7\"/><path d=\"M16,10 H80 A6,12 0 0 1 80,34 H16 A6,12 0 0 1 16,10 Z\"/></g>" },
    "Distl": { w: 48, h: 96, body: [6, 13, 26, 83], ports: {"feed":[1,48,"l"],"distillate":[47,24,"r"],"bottoms":[47,92,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M1,48 H6\"/><path d=\"M16,13 V2 H38 V5\"/><path d=\"M38,19 V24\"/><path d=\"M26,24 H47\"/><path d=\"M38,75 V71 H26\"/><path d=\"M16,83 V92 H47\"/><path d=\"M38,89 V92\"/><path d=\"M6,18 A10,5 0 0 1 26,18 V78 A10,5 0 0 1 6,78 Z\" fill=\"#ffffff\"/><path d=\"M9,30 H23 M9,39 H23 M9,57 H23 M9,66 H23\" stroke-dasharray=\"2 4\"/><circle cx=\"38\" cy=\"12\" r=\"7\" fill=\"#ffffff\"/><path d=\"M31,12 L33.5,8.5 L36.5,15.5 L39.5,8.5 L42.5,15.5 L45,12\"/><circle cx=\"38\" cy=\"82\" r=\"7\" fill=\"#ffffff\"/><path d=\"M31,82 L33.5,78.5 L36.5,85.5 L39.5,78.5 L42.5,85.5 L45,82\"/></g>" },
    "Dryer": { w: 96, h: 48, body: [14, 13, 82, 33], ports: {"wet":[9,18,"l"],"gas":[9,28,"l"],"exgas":[76,8,"u"],"dry":[87,28,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M9,18 H14 M9,28 H14 M76,8 V13 M82,28 H87\"/><path d=\"M14,13 H82 V33 H14 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M14,26 H82 V33 H14 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M14,13 H82 V33 H14 Z\"/><path d=\"M28,10 H33 V36 H28 Z M63,10 H68 V36 H63 Z\" fill=\"#ffffff\"/><circle cx=\"30.5\" cy=\"39.5\" r=\"3\" fill=\"#ffffff\"/><circle cx=\"65.5\" cy=\"39.5\" r=\"3\" fill=\"#ffffff\"/></g>" },
    "DSTWU": { w: 48, h: 96, body: [6, 13, 26, 83], ports: {"feed":[1,48,"l"],"distillate":[47,24,"r"],"bottoms":[47,92,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M1,48 H6\"/><path d=\"M16,13 V2 H38 V5\"/><path d=\"M38,19 V24\"/><path d=\"M26,24 H47\"/><path d=\"M38,75 V71 H26\"/><path d=\"M16,83 V92 H47\"/><path d=\"M38,89 V92\"/><path d=\"M6,18 A10,5 0 0 1 26,18 V78 A10,5 0 0 1 6,78 Z\" fill=\"#ffffff\"/><path d=\"M10,36 V60 H22\"/><path d=\"M13,38 C14,51 16,55 23,56\"/><circle cx=\"38\" cy=\"12\" r=\"7\" fill=\"#ffffff\"/><path d=\"M31,12 L33.5,8.5 L36.5,15.5 L39.5,8.5 L42.5,15.5 L45,12\"/><circle cx=\"38\" cy=\"82\" r=\"7\" fill=\"#ffffff\"/><path d=\"M31,82 L33.5,78.5 L36.5,85.5 L39.5,78.5 L42.5,85.5 L45,82\"/></g>" },
    "Dupl": { w: 32, h: 32, body: [6, 6, 26, 26], ports: {"feed":[1,16,"l"],"product1":[31,11,"r"],"product2":[31,21,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M1,16 H6 M26,11 H31 M26,21 H31\"/><path d=\"M6,6 H26 V26 H6 Z\" fill=\"#ffffff\"/><path d=\"M10,10 H18 V18 H10 Z\" fill=\"#ffffff\"/><path d=\"M14,14 H22 V22 H14 Z\" fill=\"#ffffff\"/></g>" },
    "Electrolyzer": { w: 64, h: 64, body: [12, 20, 52, 54], ports: {"feed":[7,44,"l"],"anode_gas":[27,15,"u"],"cathode_gas":[37,15,"u"],"product":[57,44,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M7,44 H12 M27,15 V20 M37,15 V20 M52,44 H57\"/><path d=\"M12,20 H52 V54 H12 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M12,30 H52 V54 H12 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M12,30 H52\"/><path d=\"M32,24 V50\" stroke-dasharray=\"2 4\"/><path d=\"M12,20 H52 V54 H12 Z\"/><path d=\"M18,12 H22 V46 H18 Z\" fill=\"#ffffff\"/><path d=\"M42,12 H46 V46 H42 Z\" fill=\"#ffffff\"/><path d=\"M17,6 H23 M20,3 V9 M41,6 H47\"/></g>" },
    "ESP": { w: 64, h: 64, body: [7, 12, 57, 56], ports: {"feed":[2,26,"l"],"gas":[62,26,"r"],"solids":[32,61,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M2,26 H7 M57,26 H62 M32,56 V61\"/><path d=\"M14,12 H50 V16 L57,22 V30 L50,36 V40 L35,56 H29 L14,40 V36 L7,30 V22 L14,16 Z\" fill=\"#ffffff\"/><path d=\"M14,16 V40 H50 V16\"/><path d=\"M22,16 V36 M32,16 V36 M42,16 V36\"/><path d=\"M27,17 L25,20 L29,24 L25,28 L29,32 L27,35\"/><path d=\"M37,17 L35,20 L39,24 L35,28 L39,32 L37,35\"/></g>" },
    "Extract": { w: 48, h: 96, body: [14, 11, 34, 85], ports: {"feed":[9,22,"l"],"solvent":[9,74,"l"],"extract":[39,20,"r"],"raffinate":[24,91,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M9,22 H14 M9,74 H14 M34,20 H39 M24,86 V91\"/><path d=\"M14,16 A10,5 0 0 1 34,16 V80 A10,5 0 0 1 14,80 Z\" fill=\"#ffffff\"/><path d=\"M14,31 H18 M34,31 H30 M14,43 H18 M34,43 H30 M14,55 H18 M34,55 H30 M14,67 H18 M34,67 H30\"/><path d=\"M24,7 V70\"/><path d=\"M19,37 H29 M19,49 H29 M19,61 H29\"/><path d=\"M18,1 H30 V7 H18 Z\" fill=\"#ffffff\"/></g>" },
    "FabFl": { w: 64, h: 64, body: [11, 8, 53, 56], ports: {"feed":[6,32,"l"],"gas":[32,3,"u"],"solids":[32,61,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M6,32 H11 M32,3 V8 M32,56 V61\"/><path d=\"M11,8 H53 V42 L35,56 H29 L11,42 Z\" fill=\"#ffffff\"/><path d=\"M11,16 H53\"/><path d=\"M15,16 V35 A3,3 0 0 0 21,35 V16 M25,16 V35 A3,3 0 0 0 31,35 V16 M33,16 V35 A3,3 0 0 0 39,35 V16 M43,16 V35 A3,3 0 0 0 49,35 V16\" fill=\"#e6e6e6\"/></g>" },
    "Filter": { w: 64, h: 64, body: [17, 20, 47, 50], ports: {"feed":[5,47,"l"],"solids":[59,31,"r"],"liquid":[32,61,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M5,47 H10 M32,56 V61\"/><path d=\"M10,38 V50 L16,56 H48 L54,50 V38 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M10,43 H54 V50 L48,56 H16 L10,50 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M10,43 H54\"/><path d=\"M10,38 V50 L16,56 H48 L54,50 V38\"/><circle cx=\"32\" cy=\"35\" r=\"15\" fill=\"#ffffff\"/><circle cx=\"32\" cy=\"35\" r=\"3\"/><path d=\"M45,28 L53,31 H59\"/></g>" },
    "Flash2": { w: 64, h: 64, body: [20, 8, 44, 56], ports: {"feed":[15,28,"l"],"vapour":[32,3,"u"],"liquid":[32,61,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M15,28 H20 M32,3 V8 M32,56 V61\"/><path d=\"M20,14 A12,6 0 0 1 44,14 V50 A12,6 0 0 1 20,50 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M20,40 H44 V50 A12,6 0 0 1 20,50 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M20,17 H44 V22 H20 Z\" fill=\"#e6e6e6\"/><path d=\"M20,40 H44\"/><path d=\"M29,33.5 H35 L32,37.5 Z\" fill=\"#ffffff\"/><path d=\"M20,14 A12,6 0 0 1 44,14 V50 A12,6 0 0 1 20,50 Z\"/></g>" },
    "Flash3": { w: 96, h: 48, body: [10, 8, 86, 32], ports: {"feed":[6,14,"l"],"vapour":[72,3,"u"],"liquid1":[40,37,"d"],"liquid2":[64,46,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M6,14 H11 M72,3 V8 M40,32 V37 M64,42 V46\"/><path d=\"M16,8 H80 A6,12 0 0 1 80,32 H16 A6,12 0 0 1 16,8 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M10,20 H86 A6,12 0 0 1 80,32 H16 A6,12 0 0 1 10,20 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M57,31 V38.5 A7,3.5 0 0 0 71,38.5 V31 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M10,20 H86\"/><path d=\"M27,13.5 H33 L30,17.5 Z\" fill=\"#ffffff\"/><path d=\"M57,36 H71\"/><path d=\"M57,32 V38.5 A7,3.5 0 0 0 71,38.5 V32\"/><path d=\"M16,8 H80 A6,12 0 0 1 80,32 H16 A6,12 0 0 1 16,8 Z\"/></g>" },
    "Fluidbed": { w: 48, h: 96, body: [8, 6, 40, 87], ports: {"feed":[9,64,"l"],"gas_out":[24,2,"u"],"gas_in":[24,92,"d"],"solids_out":[39,72,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M9,64 H14 M24,2 V6 M24,87 V92 M34,72 H39\"/><path d=\"M8,14 A16,8 0 0 1 40,14 V36 L34,46 V82 A10,5 0 0 1 14,82 V46 L8,36 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M14,54 H34 V78 H14 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M14,54 H34\"/><path d=\"M14,78 H34\" stroke-dasharray=\"2 4\"/><path d=\"M8,14 A16,8 0 0 1 40,14 V36 L34,46 V82 A10,5 0 0 1 14,82 V46 L8,36 Z\"/></g>" },
    "FSplit": { w: 32, h: 32, body: [5, 3, 26, 29], ports: {"feed":[1,16,"l"],"product":[31,9,"r"],"product2":[31,23,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M1,16 H5 M26,9 H31 M26,23 H31\"/><path d=\"M26,3 L5,16 L26,29 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M11,16 H19 L26,9 M19,16 L26,23\"/><path d=\"M26,3 L5,16 L26,29 Z\"/></g>" },
    "Granulator": { w: 64, h: 64, body: [16, 8, 48, 54], ports: {"feed":[11,21,"l"],"gas":[32,3,"u"],"product":[32,59,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M32,3 V8 M32,54 V59\"/><path d=\"M16,16 A16,8 0 0 1 48,16 V46 A16,8 0 0 1 16,46 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M16,30 H48 V44 H16 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M16,30 H48\"/><path d=\"M11,21 H32 M27,27 L32,21 L37,27\"/><circle cx=\"22\" cy=\"39\" r=\"2.2\" fill=\"#ffffff\"/><circle cx=\"29\" cy=\"35\" r=\"2.2\" fill=\"#ffffff\"/><circle cx=\"36\" cy=\"39.5\" r=\"2.2\" fill=\"#ffffff\"/><circle cx=\"42.5\" cy=\"35\" r=\"2.2\" fill=\"#ffffff\"/><path d=\"M16,44 H48\" stroke-dasharray=\"2 4\"/><path d=\"M16,16 A16,8 0 0 1 48,16 V46 A16,8 0 0 1 16,46 Z\"/></g>" },
    "Heater": { w: 64, h: 64, body: [16, 16, 48, 48], ports: {"feed":[11,32,"l"],"product":[53,32,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M11,32 H16 M48,32 H53\"/><circle cx=\"32\" cy=\"32\" r=\"16\" fill=\"#ffffff\"/><path d=\"M16,32 L21.5,24 L28.5,40 L35.5,24 L42.5,40 L48,32\"/></g>" },
    "HeatX": { w: 96, h: 48, body: [8, 10, 88, 38], ports: {"tube_in":[3,24,"l"],"tube_out":[93,24,"r"],"shell_in":[28,5,"u"],"shell_out":[68,43,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M3,24 H8 M88,24 H93 M28,5 V10 M68,38 V43\"/><path d=\"M18,10 H78 A10,14 0 0 1 78,38 H18 A10,14 0 0 1 18,10 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M18,17 H78 V31 H18 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M38,10 V27 M48,38 V21 M58,10 V27\"/><path d=\"M18,10 V38 M78,10 V38\"/><path d=\"M18,10 H78 A10,14 0 0 1 78,38 H18 A10,14 0 0 1 18,10 Z\"/></g>" },
    "HXFlux": { w: 96, h: 48, body: [16, 14, 80, 34], ports: {"tube_in":[3,24,"l"],"tube_out":[93,24,"r"],"annulus_in":[24,9,"u"],"annulus_out":[72,39,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M3,24 H8 M88,24 H93 M24,9 V14 M72,34 V39\"/><path d=\"M16,14 H80 V34 H16 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M8,20 H88 V28 H8 Z\" fill=\"#e6e6e6\"/><path d=\"M16,20 V14 H80 V20 M80,28 V34 H16 V28\"/></g>" },
    "HyCyc": { w: 64, h: 64, body: [20, 12, 40, 56], ports: {"feed":[15,16,"l"],"overflow":[32,3,"u"],"underflow":[32,61,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M15,16 H20 M32,56 V61 M32,3 V7\"/><path d=\"M20,12 H40 V22 L34,56 H30 L24,22 V19 H20 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M29,7 H35 V24 H29 Z\" fill=\"#ffffff\"/><path d=\"M20,12 H40 V22 L34,56 H30 L24,22 V19 H20 Z\"/><path d=\"M29,12 V7 H35 V12\"/></g>" },
    "Makeup": { w: 64, h: 64, body: [22, 36, 42, 56], ports: {"feed":[17,46,"l"],"makeup":[17,20,"l"],"product":[47,46,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M17,46 H22 M17,20 H22 M42,46 H47 M32,30 V36\"/><path d=\"M22,15 L32,11 L42,15 V30 H22 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M22,24 H42 V30 H22 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M22,24 H42\"/><path d=\"M22,15 L32,11 L42,15 V30 H22 Z\"/><circle cx=\"32\" cy=\"46\" r=\"10\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M22,46 H42 M32,36 V46\"/><circle cx=\"32\" cy=\"46\" r=\"10\"/></g>" },
    "MCompr": { w: 96, h: 48, body: [12, 8, 36, 40], ports: {"feed":[7,24,"l"],"product":[89,24,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M7,24 H12 M36,24 H41 M55,24 H60 M84,24 H89\"/><path d=\"M12,8 L36,16 V32 L12,40 Z\" fill=\"#ffffff\"/><path d=\"M60,13 L84,19 V29 L60,35 Z\" fill=\"#ffffff\"/><circle cx=\"48\" cy=\"24\" r=\"7\" fill=\"#ffffff\"/><path d=\"M41,24 L43.5,20.5 L46.5,27.5 L49.5,20.5 L52.5,27.5 L55,24\"/></g>" },
    "MHeatX": { w: 96, h: 48, body: [26, 4, 70, 44], ports: {"in1":[21,14,"l"],"in2":[21,24,"l"],"in3":[21,34,"l"],"out1":[75,14,"r"],"out2":[75,24,"r"],"out3":[75,34,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M21,14 H26 M21,24 H26 M21,34 H26 M70,14 H75 M70,24 H75 M70,34 H75\"/><path d=\"M26,4 H70 V44 H26 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M26,14 H70 M26,24 H70 M26,34 H70\"/><path d=\"M26,4 H70 V44 H26 Z\"/></g>" },
    "Mixer": { w: 32, h: 32, body: [6, 3, 27, 29], ports: {"feed":[1,9,"l"],"feed2":[1,23,"l"],"product":[31,16,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M1,9 H6 M1,23 H6 M27,16 H31\"/><path d=\"M6,3 L27,16 L6,29 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M6,9 L13,16 L6,23 M13,16 H21\"/><path d=\"M6,3 L27,16 L6,29 Z\"/></g>" },
    "Mult": { w: 32, h: 32, body: [6, 6, 26, 26], ports: {"feed":[1,16,"l"],"product":[31,16,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M1,16 H6 M26,16 H31\"/><path d=\"M6,6 H26 V26 H6 Z\" fill=\"#ffffff\"/><path d=\"M11.5,11.5 L20.5,20.5 M20.5,11.5 L11.5,20.5\"/></g>" },
    "MultiFrac": { w: 48, h: 96, body: [4, 12, 20, 84], ports: {"feed":[1,50,"l"],"distillate":[47,24,"r"],"bottoms":[12,90,"d"],"product":[36,75,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M1,50 H4 M12,84 V90 M36,70 V75\"/><path d=\"M12,12 V2 H36 V5\"/><path d=\"M36,19 V24\"/><path d=\"M20,24 H47\"/><path d=\"M20,40 H30 M30,60 H20\"/><path d=\"M4,16 A8,4 0 0 1 20,16 V80 A8,4 0 0 1 4,80 Z\" fill=\"#ffffff\"/><path d=\"M4,28 H15 M20,34 H9 M4,40 H15 M20,46 H9 M4,52 H15 M20,58 H9 M4,64 H15 M20,70 H9\"/><path d=\"M30,34 A6,3 0 0 1 42,34 V66 A6,3 0 0 1 30,66 Z\" fill=\"#ffffff\"/><path d=\"M30,44 H38 M42,50 H34 M30,56 H38\"/><circle cx=\"36\" cy=\"12\" r=\"7\" fill=\"#ffffff\"/><path d=\"M29,12 L31.5,8.5 L34.5,15.5 L37.5,8.5 L40.5,15.5 L43,12\"/></g>" },
    "PetroFrac": { w: 48, h: 96, body: [16, 14, 32, 88], ports: {"feed":[8,88,"d"],"distillate":[47,24,"r"],"side1":[37,39,"r"],"side2":[37,51,"r"],"bottoms":[24,93,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M8,88 V82 M32,39 H37 M32,51 H37 M24,88 V93\"/><path d=\"M24,14 V2 H39 V5\"/><path d=\"M39,19 V24\"/><path d=\"M32,24 H47\"/><path d=\"M2,82 V58 L5,52 H6.5 V44 H9.5 V52 H11 L14,58 V82 Z\" fill=\"#ffffff\"/><path d=\"M2,58 H14\"/><path d=\"M8,82 V78 L5,75 L11,71 L5,67 L11,63 L16,63\"/><path d=\"M16,18 A8,4 0 0 1 32,18 V84 A8,4 0 0 1 16,84 Z\" fill=\"#ffffff\"/><path d=\"M16,30 H27 M32,36 H21 M16,42 H27 M32,48 H21 M16,54 H27 M32,72 H21 M16,78 H27\"/><circle cx=\"39\" cy=\"12\" r=\"7\" fill=\"#ffffff\"/><path d=\"M32,12 L34.5,8.5 L37.5,15.5 L40.5,8.5 L43.5,15.5 L46,12\"/></g>" },
    "Pipe": { w: 96, h: 48, body: [13, 20, 83, 28], ports: {"feed":[8,24,"l"],"product":[88,24,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M8,24 H13 M83,24 H88\"/><path d=\"M13,20 H83 V28 H13 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M13,20 H83 M13,28 H83\"/><path d=\"M13,16 V32 M83,16 V32\"/></g>" },
    "Pipeline": { w: 96, h: 48, body: [8, 14, 88, 42], ports: {"feed":[3,38,"l"],"product":[93,18,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M3,38 H8 M88,18 H93\"/><path d=\"M8,34 H32.3 L52.3,14 H88 V22 H55.7 L35.7,42 H8 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M8,34 H32.3 L52.3,14 H88 M8,42 H35.7 L55.7,22 H88\"/><path d=\"M8,30 V46 M88,10 V26\"/></g>" },
    "Pump": { w: 64, h: 64, body: [18, 20, 46, 48], ports: {"feed":[13,34,"l"],"product":[53,23,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M13,34 H18 M48,23 H53\"/><path d=\"M23,44 L19,56 H45 L41,44 Z\" fill=\"#ffffff\"/><path d=\"M32,20 H48 V26 H36 V20\" fill=\"#ffffff\"/><circle cx=\"32\" cy=\"34\" r=\"14\" fill=\"#ffffff\"/></g>" },
    "RadFrac": { w: 48, h: 96, body: [6, 13, 26, 83], ports: {"feed":[1,48,"l"],"distillate":[47,24,"r"],"bottoms":[47,92,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M1,48 H6\"/><path d=\"M16,13 V2 H38 V5\"/><path d=\"M38,19 V24\"/><path d=\"M26,24 H47\"/><path d=\"M38,75 V71 H26\"/><path d=\"M16,83 V92 H47\"/><path d=\"M38,89 V92\"/><path d=\"M6,18 A10,5 0 0 1 26,18 V78 A10,5 0 0 1 6,78 Z\" fill=\"#ffffff\"/><path d=\"M6,30 H20 M26,36 H12 M6,42 H20 M26,48 H12 M6,54 H20 M26,60 H12 M6,66 H20\"/><circle cx=\"38\" cy=\"12\" r=\"7\" fill=\"#ffffff\"/><path d=\"M31,12 L33.5,8.5 L36.5,15.5 L39.5,8.5 L42.5,15.5 L45,12\"/><circle cx=\"38\" cy=\"82\" r=\"7\" fill=\"#ffffff\"/><path d=\"M31,82 L33.5,78.5 L36.5,85.5 L39.5,78.5 L42.5,85.5 L45,82\"/></g>" },
    "RateFrac": { w: 48, h: 96, body: [6, 13, 26, 83], ports: {"feed":[1,48,"l"],"distillate":[47,24,"r"],"bottoms":[47,92,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M1,48 H6\"/><path d=\"M16,13 V2 H38 V5\"/><path d=\"M38,19 V24\"/><path d=\"M26,24 H47\"/><path d=\"M38,75 V71 H26\"/><path d=\"M16,83 V92 H47\"/><path d=\"M38,89 V92\"/><path d=\"M6,18 A10,5 0 0 1 26,18 V78 A10,5 0 0 1 6,78 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M6,26 H26 V43 H6 Z M6,53 H26 V70 H6 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M6,26 H26 M6,43 H26 M6,53 H26 M6,70 H26\"/><path d=\"M6,18 A10,5 0 0 1 26,18 V78 A10,5 0 0 1 6,78 Z\"/><circle cx=\"38\" cy=\"12\" r=\"7\" fill=\"#ffffff\"/><path d=\"M31,12 L33.5,8.5 L36.5,15.5 L39.5,8.5 L42.5,15.5 L45,12\"/><circle cx=\"38\" cy=\"82\" r=\"7\" fill=\"#ffffff\"/><path d=\"M31,82 L33.5,78.5 L36.5,85.5 L39.5,78.5 L42.5,85.5 L45,82\"/></g>" },
    "RBatch": { w: 64, h: 64, body: [18, 13, 46, 55], ports: {"feed":[13,24,"l"],"product":[32,61,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M14,30 V48 A18,9 0 0 0 50,48 V30 Z\" fill=\"#ffffff\"/><path d=\"M13,24 H18 M32,55 V61\"/><path d=\"M18,20 A14,7 0 0 1 46,20 V48 A14,7 0 0 1 18,48 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M18,30 H46 V48 A14,7 0 0 1 18,48 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M18,30 H46\"/><path d=\"M32,8 V50.5\"/><path d=\"M23,38 V46 A9,4.5 0 0 0 41,46 V38\"/><path d=\"M18,20 A14,7 0 0 1 46,20 V48 A14,7 0 0 1 18,48 Z\"/><path d=\"M26,1 H38 V8 H26 Z\" fill=\"#ffffff\"/></g>" },
    "RCSTR": { w: 64, h: 64, body: [16, 12, 48, 58], ports: {"feed":[11,23,"l"],"product":[32,62,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M11,23 H16 M32,58 V62\"/><path d=\"M16,20 A16,8 0 0 1 48,20 V50 A16,8 0 0 1 16,50 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M16,28 H48 V50 A16,8 0 0 1 16,50 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M16,28 H48\"/><path d=\"M32,8 V45\"/><ellipse cx=\"26.5\" cy=\"45\" rx=\"5.5\" ry=\"2\" fill=\"#ffffff\"/><ellipse cx=\"37.5\" cy=\"45\" rx=\"5.5\" ry=\"2\" fill=\"#ffffff\"/><path d=\"M16,20 A16,8 0 0 1 48,20 V50 A16,8 0 0 1 16,50 Z\"/><path d=\"M26,1 H38 V8 H26 Z\" fill=\"#ffffff\"/></g>" },
    "REquil": { w: 64, h: 64, body: [16, 12, 48, 58], ports: {"feed":[11,26,"l"],"product":[53,44,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M11,26 H16 M48,44 H53\"/><path d=\"M16,20 A16,8 0 0 1 48,20 V50 A16,8 0 0 1 16,50 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M20,28 H35 V22 L44,33 H20 Z\" fill=\"#ffffff\"/><path d=\"M44,37 H20 L29,48 V42 H44 Z\" fill=\"#ffffff\"/><path d=\"M16,20 A16,8 0 0 1 48,20 V50 A16,8 0 0 1 16,50 Z\"/></g>" },
    "RGibbs": { w: 64, h: 64, body: [16, 12, 48, 58], ports: {"feed":[11,26,"l"],"product":[53,44,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M11,26 H16 M48,44 H53\"/><path d=\"M16,20 A16,8 0 0 1 48,20 V50 A16,8 0 0 1 16,50 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M19.5,23 C23,41 27,45 32,45 C37,45 41,41 44.5,23\"/><circle cx=\"32\" cy=\"39\" r=\"4.5\" fill=\"#ffffff\"/><path d=\"M16,20 A16,8 0 0 1 48,20 V50 A16,8 0 0 1 16,50 Z\"/></g>" },
    "RPlug": { w: 96, h: 48, body: [10, 16, 86, 32], ports: {"feed":[5,24,"l"],"product":[91,24,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M5,24 H10 M86,24 H91\"/><path d=\"M14,16 H82 A4,8 0 0 1 82,32 H14 A4,8 0 0 1 14,16 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M20,16 H76 V32 H20 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M20,16 V32 M76,16 V32\"/><path d=\"M14,16 H82 A4,8 0 0 1 82,32 H14 A4,8 0 0 1 14,16 Z\"/></g>" },
    "RStoic": { w: 64, h: 64, body: [16, 12, 48, 58], ports: {"feed":[11,26,"l"],"product":[53,44,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M11,26 H16 M48,44 H53\"/><path d=\"M16,20 A16,8 0 0 1 48,20 V50 A16,8 0 0 1 16,50 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M20,31 H33 V24 L44,35 L33,46 V39 H20 Z\" fill=\"#ffffff\"/><path d=\"M16,20 A16,8 0 0 1 48,20 V50 A16,8 0 0 1 16,50 Z\"/></g>" },
    "RYield": { w: 64, h: 64, body: [16, 12, 48, 58], ports: {"feed":[11,26,"l"],"product":[53,44,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M11,26 H16 M48,44 H53\"/><path d=\"M16,20 A16,8 0 0 1 48,20 V50 A16,8 0 0 1 16,50 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M21,46 V35 H26 V46 Z M29.5,46 V23 H34.5 V46 Z M38,46 V30 H43 V46 Z\" fill=\"#ffffff\"/><path d=\"M19.5,46 H44.5\"/><path d=\"M16,20 A16,8 0 0 1 48,20 V50 A16,8 0 0 1 16,50 Z\"/></g>" },
    "SCFrac": { w: 48, h: 96, body: [6, 13, 26, 83], ports: {"feed":[1,58,"l"],"steam":[1,72,"l"],"distillate":[47,24,"r"],"side1":[31,38,"r"],"side2":[31,50,"r"],"side3":[31,62,"r"],"bottoms":[16,90,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M1,58 H6 M1,72 H6 M26,38 H31 M26,50 H31 M26,62 H31 M16,83 V90\"/><path d=\"M16,13 V2 H38 V5\"/><path d=\"M38,19 V24\"/><path d=\"M26,24 H47\"/><path d=\"M6,18 A10,5 0 0 1 26,18 V78 A10,5 0 0 1 6,78 Z\" fill=\"#ffffff\"/><circle cx=\"38\" cy=\"12\" r=\"7\" fill=\"#ffffff\"/><path d=\"M31,12 L33.5,8.5 L36.5,15.5 L39.5,8.5 L42.5,15.5 L45,12\"/></g>" },
    "Screen": { w: 64, h: 64, body: [8, 12, 56, 46], ports: {"feed":[3,16,"l"],"oversize":[61,33,"r"],"undersize":[32,45,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M3,16 H8 M56,33 H61 M32,38 V45\"/><path d=\"M8,12 L56,28 V46 L8,30 Z\" fill=\"#ffffff\"/><path d=\"M8,21 L56,37\" stroke-dasharray=\"2 4\"/></g>" },
    "Selector": { w: 32, h: 32, body: [6, 6, 26, 26], ports: {"feed1":[1,11,"l"],"feed2":[1,21,"l"],"product":[31,16,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M1,11 H6 M1,21 H6 M26,16 H31\"/><path d=\"M6,6 H26 V26 H6 Z\" fill=\"#ffffff\"/><path d=\"M6,11 H10 M6,21 H10 M21,16 H26\"/><path d=\"M21,16 L10.5,11.5\"/></g>" },
    "Sep": { w: 64, h: 64, body: [20, 8, 44, 56], ports: {"feed":[15,32,"l"],"product1":[49,20,"r"],"product2":[49,32,"r"],"product3":[49,44,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M15,32 H20 M44,20 H49 M44,32 H49 M44,44 H49\"/><path d=\"M20,14 A12,6 0 0 1 44,14 V50 A12,6 0 0 1 20,50 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M27,26 H44 M27,38 H44\"/><path d=\"M20,14 A12,6 0 0 1 44,14 V50 A12,6 0 0 1 20,50 Z\"/></g>" },
    "Sep2": { w: 64, h: 64, body: [20, 8, 44, 56], ports: {"feed":[15,32,"l"],"product1":[32,3,"u"],"product2":[32,61,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M15,32 H20 M32,3 V8 M32,56 V61\"/><path d=\"M20,14 A12,6 0 0 1 44,14 V50 A12,6 0 0 1 20,50 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M20,32 H44\"/><path d=\"M25,26 L32,19 L39,26 M25,38 L32,45 L39,38\"/><path d=\"M20,14 A12,6 0 0 1 44,14 V50 A12,6 0 0 1 20,50 Z\"/></g>" },
    "SSplit": { w: 32, h: 32, body: [5, 3, 26, 29], ports: {"feed":[1,16,"l"],"product":[31,9,"r"],"product2":[31,23,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M1,16 H5 M26,9 H31 M26,23 H31\"/><path d=\"M26,3 L5,16 L26,29 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M5,16 H26 V29 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M11,16 H26\"/><path d=\"M26,3 L5,16 L26,29 Z\"/></g>" },
    "Swash": { w: 64, h: 64, body: [8, 12, 56, 50], ports: {"feed":[3,26,"l"],"wash":[32,6,"u"],"filtrate":[61,17,"r"],"product":[32,56,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M3,26 H8 M56,17 H61 M32,50 V56\"/><path d=\"M8,12 H56 V36 L38,50 H26 L8,36 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M8,33 H56 V36 L38,50 H26 L8,36 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M8,33 H56\"/><path d=\"M32,6 V18 M18,18 H46\"/><path d=\"M15,23 L18,18 L21,23 M29,23 L32,18 L35,23 M43,23 L46,18 L49,23\"/><path d=\"M8,12 H56 V36 L38,50 H26 L8,36 Z\"/></g>" },
    "User": { w: 64, h: 64, body: [14, 16, 50, 48], ports: {"feed":[9,32,"l"],"top":[32,11,"u"],"product":[55,32,"r"],"bottom":[32,53,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M9,32 H14 M50,32 H55 M32,11 V16 M32,48 V53\"/><path d=\"M14,16 H50 V48 H14 Z\" fill=\"#ffffff\"/><path d=\"M32,25 V39\"/></g>" },
    "User2": { w: 64, h: 64, body: [14, 16, 50, 48], ports: {"feed":[9,32,"l"],"top":[32,11,"u"],"product":[55,32,"r"],"bottom":[32,53,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M9,32 H14 M50,32 H55 M32,11 V16 M32,48 V53\"/><path d=\"M14,16 H50 V48 H14 Z\" fill=\"#ffffff\"/><path d=\"M29,25 V39 M35,25 V39\"/></g>" },
    "User3": { w: 64, h: 64, body: [14, 16, 50, 48], ports: {"feed":[9,32,"l"],"top":[32,11,"u"],"product":[55,32,"r"],"bottom":[32,53,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M9,32 H14 M50,32 H55 M32,11 V16 M32,48 V53\"/><path d=\"M14,16 H50 V48 H14 Z\" fill=\"#ffffff\"/><path d=\"M26,25 V39 M32,25 V39 M38,25 V39\"/></g>" },
    "Valve": { w: 32, h: 32, body: [6, 14, 26, 26], ports: {"feed":[2,20,"l"],"product":[30,20,"r"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M2,20 H6 M26,20 H30\"/><path d=\"M16,20 V9\"/><path d=\"M6,14 L26,26 V14 L6,26 Z\" fill=\"#ffffff\"/><path d=\"M10,9 A6,5 0 0 1 22,9 Z\" fill=\"#ffffff\"/></g>" },
    "VScrub": { w: 96, h: 48, body: [8, 16, 68, 32], ports: {"feed":[3,24,"l"],"liquid_in":[32,15,"u"],"gas":[78,2,"u"],"liquid":[78,46,"d"]},
      g: "<g fill=\"none\" stroke=\"#1a1a1a\" stroke-width=\"1.5\" stroke-linejoin=\"round\" stroke-linecap=\"round\"><path d=\"M3,24 H8 M32,15 V21 M78,2 V7 M78,41 V46\"/><path d=\"M8,16 H16 L27,21 H37 L60,17 H68 V31 H60 L37,27 H27 L16,32 H8 Z\" fill=\"#ffffff\"/><path d=\"M68,12 A10,5 0 0 1 88,12 V36 A10,5 0 0 1 68,36 Z\" fill=\"#ffffff\" stroke=\"none\"/><path d=\"M68,33 H88 V36 A10,5 0 0 1 68,36 Z\" fill=\"#e6e6e6\" stroke=\"none\"/><path d=\"M68,33 H88\"/><path d=\"M68,12 A10,5 0 0 1 88,12 V36 A10,5 0 0 1 68,36 Z\"/></g>" },
  };
  // ---- end of generated block ----

  // A column's vapour distillate beside a liquid one leaves off the top of the overhead line,
  // where it turns down into the condenser: the symbols draw no nozzle there (the line is it).
  // [type, x of that corner]
  [["RadFrac", 38], ["RateFrac", 38], ["MultiFrac", 36], ["PetroFrac", 39]].forEach(([k, x]) => {
    if (FSI.types[k]) FSI.types[k].ports.overhead = [x, 2, "u"];
  });
})();
