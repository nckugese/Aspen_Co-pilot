/* Aspen Workbench blocks: definitions, toolbox, and program <-> workspace conversion.
 *
 * The program is the server's JSON (see tools/workbench_tools.py). Statement ids are the
 * Blockly block ids, so the server can highlight the running block and the LLM can
 * insert after a block it read. Every tab has its own workspace; WB.data holds the
 * flowsheet, catalog and unit choices of the session whose workspace is being worked on.
 *
 * The program is the stack under "when Run is pressed" plus every procedure stack. Other
 * stacks lying on the workspace are "loose": not part of the program, but kept with each
 * version of it, so undo puts back exactly what was on screen.
 */
(function () {
  "use strict";
  const { feature } = WBA;

  const WB = (window.WB = {
    data: { flowsheet: { blocks: [], streams: [], components: [] }, catalog: { stream_props: [], block_params: {} }, units: {} },
    known: { streams: new Set(), blocks: new Set(), comps: new Set(), params: new Set(), units: new Set(), procs: new Set(),
      types: new Set(), stypes: new Set(), ports: new Set(), methods: new Set() },
  });

  // Scratch's hues at close to Scratch's saturation: the blocks are the content, so they carry
  // the colour the calm window around them leaves out. Each is as light as it can
  // be while the white words on it keep at least 3:1 -- the warm ones (the hat's gold, the
  // studies' orange) a little darker than Scratch's for it. The hues stay at least 12 degrees
  // apart: calculate teal (not optimize's green), heat integration red (not the procedures'
  // pink, nor the variables' orange), flowsheet changes magenta; results a quiet slate beside
  // the inputs' purple; a step this page does not know, grey
  const COLOUR = { event: "#C78500", action: "#4A92F7", control: "#EC6E06", opt: "#23A84B", path: "#9966FF",
    result: "#6E7FA3", variable: "#F76134", calc: "#09A48F", table: "#099CD2", proc: "#F25481", pinch: "#DE3835",
    struct: "#D458E4", other: "#89929F", group: "#5b6778" };
  const GROUP_TITLE_MAX = 60;                // a group heading's title (tools/wb_plan.GROUP_TITLE_MAX)
  const NONE = "_";
  const ROW = "{row}";                       // in a table column: the row's name
  const msg = (key) => Blockly.Msg[key] || key;
  const names = (text) => String(text ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  // the optimize step's algorithms: [name shown, the server's key]
  const ALGS = [["AFM-CBO", "afmcbo"], ["CBO", "cbo"], ["BO", "bo"], ["NSGA-II", "nsga2"], ["NSGA-III", "nsga3"],
    ["DE / GDE3", "de"], ["PSO / MOPSO", "pso"], ["%{BKY_WB_ALG_GRADIENT}", "gradient"], ["%{BKY_WB_ALG_GRID}", "grid"]];
  /** An algorithm's name as the optimize step shows it, from the server's key (the key itself
   *  for one the step does not list). */
  WB.algName = (key) => {
    const a = ALGS.find((x) => x[1] === key);
    return a ? a[0].replace(/^%\{BKY_(\w+)\}$/, (m, k) => msg(k)) : key;
  };

  /** "a, max(b, c), 2" -> ["a", "max(b, c)", "2"]: commas inside brackets stay. */
  function splitArgs(text) {
    const out = [];
    let depth = 0, cur = "";
    for (const ch of String(text ?? "")) {
      if (ch === "," && depth === 0) { out.push(cur); cur = ""; continue; }
      if (ch === "(" || ch === "[") depth++;
      if (ch === ")" || ch === "]") depth--;
      cur += ch;
    }
    out.push(cur);
    return out.map((s) => s.trim()).filter(Boolean);
  }

  // ------------------------------------------------------------------ option lists
  function merge(opts, extra) {
    const have = new Set(opts.map((o) => o[1]));
    extra.forEach((v) => { if (v && !have.has(v)) opts.push([v, v]); });
    return opts.length ? opts : [["—", NONE]];
  }
  /** A stream, block or component menu ends with "each row" for a typed table column (wb_tcol):
   *  the menu the user opens offers it there only (or where it is picked already); a load, an
   *  undo or a paste always may set it. */
  const inTcol = (blk) => { for (let x = blk; x; x = x.getParent()) if (x.type === "wb_tcol") return true; return false; };
  const withRow = (field, opts) => {
    const blk = srcOf(field), rest = opts.filter((o) => o[1] !== ROW);
    const offer = WB.menuFor !== field || curOf(field) === ROW || (blk && inTcol(blk));
    return offer ? rest.concat([[msg("WB_ROW_OPT"), ROW]]) : rest;
  };
  /** Names WB.known holds that ``field``'s menu may add: all of them while a load, an undo or a
   *  paste checks a value (so none is refused); in the menu the user opens only those a block of
   *  this workspace uses -- WB.known gathers the names of every tab's program, and another
   *  model's streams do not belong in this one's menu. */
  function knownFor(field, set) {
    if (WB.menuFor !== field) return [...set];
    const blk = srcOf(field), ws = blk && blk.workspace, used = new Set();
    if (ws) ws.getAllBlocks(false).forEach((b) => b.inputList.forEach((i) => i.fieldRow.forEach((f) => {
      const v = f.getValue && f.getValue();
      if (typeof v === "string") used.add(v);
    })));
    return [...set].filter((n) => used.has(n));
  }
  function streamOpts() {
    const pl = WB.placed(srcOf(this) && srcOf(this).workspace);
    return withRow(this, merge(WB.data.flowsheet.streams.map((s) => [s.name, s.name]), [...pl.streams, ...knownFor(this, WB.known.streams)]));
  }
  /** The flowsheet's blocks, then those a place step puts down, "NAME (Type)". */
  function blockList(ws, field) {
    const opts = WB.data.flowsheet.blocks.map((b) => [b.type ? `${b.name} (${b.type})` : b.name, b.name]);
    WB.placed(ws).blocks.forEach((ty, n) => { if (!opts.some((o) => o[1] === n)) opts.push([ty ? `${n} (${ty})` : n, n]); });
    return merge(opts, field ? knownFor(field, WB.known.blocks) : [...WB.known.blocks]);
  }
  function blockOpts() {
    return withRow(this, blockList(srcOf(this) && srcOf(this).workspace, this));
  }
  function compOpts() {
    const opts = withRow(this, merge(WB.data.flowsheet.components.map((c) => [c, c]), knownFor(this, WB.known.comps)));
    if (!opts.some((o) => o[1] === NONE)) opts.push(["—", NONE]);   // the hidden value of a property without a component
    return opts;
  }
  /** In a slot that writes (set, sweep, design spec, decision variable) a stream or block
   *  menu lists inputs only, so a result cannot be picked there; elsewhere, everything. Only
   *  the menu the user opens is narrowed (MenuDropdown): loading, pasting and undo set a
   *  field after its block is already plugged in, and must not have their value refused. */
  function propOpts() {
    const blk = this && this.getSourceBlock ? this.getSourceBlock() : null;
    const cur = this && this.getValue ? this.getValue() : null;
    let props = WB.data.catalog.stream_props;
    if (blk && WB.menuFor === this && inWriteSlot(blk)) props = props.filter((p) => p.input || p.key === cur);
    return props.length ? props.map((p) => [optWords(p.label), p.key]) : [["—", NONE]];
  }
  /** A menu item's words: Aspen's English, with our Chinese beside it in Chinese, "Reflux ratio (…)" (labels.js). */
  const optWords = (label) => WBL.name(label);
  function streamProp(key) {
    return WB.data.catalog.stream_props.find((p) => p.key === key);
  }
  /** The stream fields the toolbox's blocks start on (catalog.stream_props keys: the docs' paths). */
  const STREAM_T = "Output\\RES_TEMP", STREAM_IN = "Input\\TEMP\\MIXED", STREAM_X = "Output\\MOLEFRAC\\MIXED\\{C}";
  const STREAM_P = "Output\\RES_PRES", STREAM_F = "Output\\TOT_FLOW";
  /** A block's type, upper-cased: the flowsheet's, else (given the workspace) the type a place
   *  step there gives it; "" when neither knows it. */
  function blockType(name, ws) {
    const b = WB.data.flowsheet.blocks.find((x) => x.name === name);
    if (b) return (b.type || "").toUpperCase();
    const placed = ws ? WB.placed(ws).blocks.get(up(name)) : null;
    return placed ? placed.toUpperCase() : "";
  }
  function paramOpts(field) {
    const blk = field && field.getSourceBlock ? field.getSourceBlock() : null;
    const bname = blk ? blk.getFieldValue("B") : null;
    // "each row" may be any block of the flowsheet: offer the parameters of all their types
    const types = bname === ROW ? [...new Set(WB.data.flowsheet.blocks.map((b) => (b.type || "").toUpperCase()))] : [blockType(bname, blk && blk.workspace)];
    const seen = new Set();
    const list = types.flatMap((ty) => WB.data.catalog.block_params[ty] || [])
      .filter((p) => !seen.has(p.path) && seen.add(p.path)).map((p) => [optWords(p.label), p.path]);
    let opts = merge(list, WB.known.params);
    // a field the program names that the catalog does not, in words: the server's name of it on
    // this block ("Feed stage · FEED", the Chinese beside it in Chinese), else its code
    const own = bname && bname !== ROW && bname !== NONE ? bname : null;
    const word = (rel) => {
      const lc = own ? WBL.of(`\\Data\\Blocks\\${own}\\${rel}`) : null;
      return lc && lc.src && lc.src !== "code" ? WBL.text(lc, "name") : WBL.param(rel);
    };
    opts = opts.map((o) => (o[0] === o[1] && String(o[1]).includes("\\") ? [word(o[1]), o[1]] : o));
    if (blk && blk.getParent && WB.menuFor === field && inWriteSlot(blk)) {
      const cur = field.getValue ? field.getValue() : null;
      opts = opts.filter((o) => String(o[1]).startsWith("Input") || o[1] === cur);
      if (!opts.length) opts = [["—", NONE]];
    }
    return opts[0][1] === NONE ? [[msg("WB_NO_PARAMS"), NONE]] : opts;
  }
  /** The procedures of the workspace a call block sits in (the flyout's is the main one). */
  function procNames(blk) {
    let ws = blk && blk.workspace;
    if (ws && ws.isFlyout && ws.targetWorkspace) ws = ws.targetWorkspace;
    return ws ? ws.getTopBlocks(false).filter((b) => b.type === "wb_proc").map((b) => b.getFieldValue("NAME")) : [];
  }
  function procOpts() {
    const blk = this && this.getSourceBlock ? this.getSourceBlock() : null;
    const opts = merge(procNames(blk).map((n) => [n, n]), WB.known.procs);
    return opts[0][1] === NONE ? [[msg("WB_NO_PROCS"), NONE]] : opts;
  }

  // ------------------------------------------------------------------ picked lists (wb-blocks)
  // A text field that says what it is for while empty (quiet, style.css .wb-ph): "auto", "condition".
  class PhField extends Blockly.FieldTextInput {
    constructor(value, ph, validator) { super(value, validator); this.wbPh = ph; }
    getDisplayText_() {
      const s = String(this.getText() || "");
      return s || !this.wbPh ? super.getDisplayText_() : msg(this.wbPh);
    }
    render_() {
      super.render_();
      if (this.textElement_) this.textElement_.classList.toggle("wb-ph", !!this.wbPh && !String(this.getValue() ?? ""));
    }
  }
  /** A text field that offers the program's variable names while it is edited (a list under the
   *  editor; typing stays free): mode "name" the whole text, "list" the comma-separated name at
   *  the caret, "expr" the name being typed in an expression, "brace" a {name} in a text. */
  class SuggestField extends PhField {
    constructor(value, mode, ph, validator) { super(value, ph || null, validator); this.wbMode = mode || "name"; }
    static fromJson(o) {
      return new SuggestField(Blockly.utils.parsing.replaceMessageReferences(o.text || ""), o.mode, o.ph);
    }
    /** [start, end, token] of the part of text the caret is in that a pick replaces; null: none. */
    wbAt(text, caret) {
      const before = text.slice(0, caret);
      if (this.wbMode === "name") return [0, text.length, text.trim()];
      if (this.wbMode === "list") {
        const a = before.lastIndexOf(",") + 1, z = text.indexOf(",", caret);
        return [a, z < 0 ? text.length : z, text.slice(a, z < 0 ? text.length : z).trim()];
      }
      const m = (this.wbMode === "brace" ? /\{(\w*)$/ : /(?<![\w.])([A-Za-z_]\w*)$/).exec(before);
      if (!m) return this.wbMode === "expr" && !/[\w.)]$/.test(before) ? [caret, caret, ""] : null;
      return [caret - m[0].length, caret, m[1]];
    }
    showEditor_(e, quiet) {
      super.showEditor_(e, quiet);
      const input = this.htmlInput_, div = Blockly.WidgetDiv.getDiv();
      if (!input || !div) return;
      const list = document.createElement("div");
      list.className = "wb-sugg";
      div.appendChild(list);
      const refresh = () => {
        const at = this.wbAt(input.value, input.selectionStart ?? input.value.length);
        const all = at ? namesFor(srcOf(this), this) : [];
        const tok = at ? at[2].toLowerCase() : "";
        const hits = all.filter((v) => v.name.toLowerCase().startsWith(tok) && v.name.toLowerCase() !== tok).slice(0, 8);
        list.replaceChildren(...hits.map((v) => {
          const it = document.createElement("div");
          it.className = "wb-sugg-i";
          it.innerHTML = `<b></b><small></small>`;
          it.firstChild.textContent = v.name;
          it.lastChild.textContent = v.path ? WBL.say(v.path) : "";
          it.addEventListener("mousedown", (ev) => {
            ev.preventDefault();
            const [a, z] = this.wbAt(input.value, input.selectionStart ?? input.value.length);
            const ins = this.wbMode === "brace" ? `{${v.name}}` : this.wbMode === "list" && a > 0 ? ` ${v.name}` : v.name;
            input.value = input.value.slice(0, a) + ins + input.value.slice(z);
            input.setSelectionRange(a + ins.length, a + ins.length);
            input.dispatchEvent(new Event("input", { bubbles: true }));
            if (this.wbMode === "name") Blockly.WidgetDiv.hide(); else refresh();
          });
          return it;
        }));
        list.style.display = hits.length ? "" : "none";
      };
      ["input", "click", "keyup"].forEach((k) => input.addEventListener(k, refresh));
      refresh();
    }
  }
  try { Blockly.fieldRegistry.register("wb_suggest", SuggestField); } catch (e) { /* registered already */ }
  /** A menu whose value is text -- one name, or several separated by commas (multi: a checklist,
   *  each pick ticked or not, the menu kept open) -- so a program's value is never refused,
   *  whether or not the list knows it yet. gen(field): [[words, value]], {head: words} a heading
   *  in a checklist. empty: the words for no value (a key of Blockly.Msg). */
  class ListField extends Blockly.FieldDropdown {
    constructor(gen, opt) {
      opt = opt || {};
      let me = null;
      super(function () {
        const o = me ? me.wbItems().filter(Array.isArray).map((x) => [x[0], x[1]]) : [];   // (a third element: its short words)
        const cur = me ? String(me.getValue() ?? "") : "";
        if (!opt.multi && cur && !o.some((x) => x[1] === cur)) o.push([me.wbWord(cur), cur]);
        return o.length ? o : [[msg(opt.empty || "WB_LIST_NONE"), ""]];
      });
      me = this;
      // its tooltip: the pick in full words (the face may be cut), a variable list's names under them
      this.setTooltip(() => {
        const v = String(this.getValue() ?? ""), full = opt.multi ? names(v).map((n) => this.wbWord(n)).join(", ") : this.wbWord(v);
        return !v ? "" : (opt.multi || opt.names) && full !== v ? `${full}\n${v}` : full;
      });
      this.wbGen = gen;
      this.wbOpt = opt;
      this.setValue(opt.value ?? "");
    }
    wbItems() { try { return this.wbGen(this) || []; } catch (e) { return []; } }
    /** A value's words: its item's, else (gone from the list) the value itself, marked. */
    wbWord(v, face) {
      const hit = this.wbItems().find((o) => Array.isArray(o) && o[1] === v);
      const o = this.wbOpt || {};
      return hit ? (face && hit[2]) || hit[0] : o.word ? o.word(v) : o.gone ? msg(o.gone).replace("{0}", v) : v;
    }
    doClassValidation_(v) { return v == null ? null : String(v); }
    doValueUpdate_(v) {
      this.value_ = v;
      this.isDirty_ = true;
      this.selectedOption = [this.getText_(), v];
    }
    getText_() {
      const v = String(this.value_ ?? ""), o = this.wbOpt || {};
      const own = !v && !o.multi ? this.wbItems().find((x) => Array.isArray(x) && x[1] === "") : null;   // ("" may be a choice: x's own)
      if (own) return own[2] || own[0];
      if (!v) return msg(o.empty || "WB_LIST_NONE");
      // (a checklist shows the names it holds -- its menu has their words -- so the block stays narrow)
      return o.multi ? cap(names(v).map((n) => this.wbWord(n, true)).join(", "), FACE_MAX * 2) : cap(this.wbWord(v, true), FACE_MAX);
    }
    showEditor_(e) {
      if (!this.wbOpt.multi) {
        WB.menuFor = this;
        try { return super.showEditor_(e); } finally { WB.menuFor = null; }
      }
      const DD = Blockly.DropDownDiv, box = document.createElement("div"), items = this.wbItems();
      DD.clearContent();
      box.className = "wb-checks";
      const tick = () => {
        // the names kept in their order (one the list does not offer stays), a new tick last
        const on = new Set([...box.querySelectorAll("input:checked")].map((x) => x.value));
        const known = new Set(items.filter(Array.isArray).map((o) => o[1]));
        const kept = names(this.getValue()).filter((n) => !known.has(n) || on.has(n));
        grouped(() => this.setValue(kept.concat([...on].filter((n) => !kept.includes(n))).join(", ")));
      };
      const cur = new Set(names(this.getValue()));
      items.forEach((it) => {
        if (!Array.isArray(it)) {
          const h = document.createElement("div");
          h.className = "wb-checks-h";
          h.textContent = it.head;
          box.appendChild(h);
          return;
        }
        const row = document.createElement("label"), cb = document.createElement("input");
        cb.type = "checkbox";
        cb.value = it[1];
        cb.checked = cur.has(it[1]);
        cb.addEventListener("change", tick);
        row.append(cb, document.createTextNode(it[0]));
        if (it[0] !== it[1]) { const sm = document.createElement("small"); sm.textContent = it[1]; row.appendChild(sm); }
        box.appendChild(row);
      });
      if (!items.some(Array.isArray)) {
        const none = document.createElement("div");
        none.className = "wb-checks-h";
        none.textContent = msg(this.wbOpt.none || "WB_LIST_NONE");
        box.appendChild(none);
      }
      DD.getContentDiv().appendChild(box);
      DD.setColour("#ffffff", "#d5dbe5");
      DD.showPositionedByField(this, () => {});
    }
  }
  WB.ListField = ListField;

  // The program's loops and the variables they leave, for the menus that name them: a loop by
  // its block's id (the statement's), shown as what it varies; a variable by its name, shown
  // with the result it holds.
  const LOOP_WORD = { wb_sweep: "WB_LOOP_SWEEP", wb_seek: "WB_LOOP_SEEK", wb_repeat: "WB_LOOP_REPEAT", wb_until: "WB_LOOP_UNTIL" };
  const mainWs = (ws) => (ws && ws.isFlyout && ws.targetWorkspace ? ws.targetWorkspace : ws);
  /** The steps of a workspace's program in the order they run (main, then procedures). */
  function progBlocks(ws) {
    ws = mainWs(ws);
    if (!ws) return [];
    const out = [], walk = (b) => {
      for (let x = b; x; x = x.getNextBlock()) {
        out.push(x);
        x.inputList.forEach((inp) => {
          if (inp.type === Blockly.inputs.inputTypes.STATEMENT && inp.connection && inp.connection.targetBlock()
              && !inp.connection.getCheck()) walk(inp.connection.targetBlock());
        });
      }
    };
    const tops = ws.getTopBlocks(true);
    tops.filter((b) => b.type === "wb_start").forEach(walk);
    tops.filter((b) => b.type === "wb_proc").forEach(walk);
    return out.filter((b) => !b.isInsertionMarker());
  }
  /** A loop's words: its kind and what it varies ("Sweep: ESTCOL › Reflux ratio"). */
  function loopWords(b, short) {
    const what = b.type === "wb_repeat" ? String(b.getFieldValue("TIMES"))
      : b.type === "wb_until" ? String(b.getFieldValue("COND") || "")
        : (() => { const p = pathOf(b.getInputTargetBlock("PATH")); return p ? (short ? shortSay(p) : WBL.say(p)) : "—"; })();
    return msg(LOOP_WORD[b.type]).replace("{0}", what);
  }
  function loopOpts() {
    const blk = srcOf(this);
    return progBlocks(blk && blk.workspace).filter((b) => LOOPS.includes(b.type)).map((b) => [loopWords(b), b.id, loopWords(b, true)]);
  }
  /** The loop variable a loop records first (the server's: sweep_value, seek_value, i). */
  const loopVar = (b) => (b.type === "wb_sweep" ? "sweep_value" : b.type === "wb_seek" ? "seek_value" : "i");
  const PINCH_VARS = ["qh", "qc", "recovery", "hot_now", "cold_now", "t_hot", "t_cold"];
  /** The variables one step sets: [{name, path?}]. */
  function setsOf(b) {
    const f = (n) => text(b.getFieldValue(n));
    switch (b.type) {
      case "wb_read": return f("AS") ? [{ name: f("AS"), path: pathOf(b.getInputTargetBlock("PATH")) }] : [];
      case "wb_calc": return f("AS") ? [{ name: f("AS") }] : [];
      case "wb_run": return [{ name: "last_run_ok" }];
      case "wb_pinch": return PINCH_VARS.map((k) => ({ name: `pinch_${k}` }));
      case "wb_sweep": case "wb_seek": case "wb_repeat": case "wb_until": return [{ name: loopVar(b) }];
      default: return [];
    }
  }
  /** The step a block is part of: itself, the statement a value is plugged into, the step holding
   *  a list's row (a chart's line, a table's column, an optimize goal). */
  function ownerStep(b) {
    let s = b;
    while (s && (s.outputConnection || (s.previousConnection && s.previousConnection.getCheck()))) {
      s = s.outputConnection ? s.getParent() : s.getSurroundParent();
    }
    return s;
  }
  /** The variables set anywhere inside a loop's (or procedure's) body. */
  const bodySets = (b) => { const body = b.getInputTargetBlock("BODY"); return body ? body.getDescendants(true).flatMap(setsOf) : []; };
  /** Names only one block knows: a chart's x in its formulas, an expression goal's terms. */
  function localNames(b) {
    const out = [];
    for (let x = b; x; x = x.getParent()) {
      if (x.type === "wb_plot") out.push({ name: "x", local: true });
      if (x.type === "wb_optobjx" || x.type === "wb_optconx") {
        for (let t = x.getInputTargetBlock("TERMS"); t; t = t.getNextBlock()) out.push({ name: text(t.getFieldValue("NAME")), local: true });
      }
    }
    return out;
  }
  /** The variables a block may use, as {name, path?}: its own (localNames), those the steps
   *  before its step set, the loops around it (their variable, what their bodies set: a later
   *  pass sees them), its procedure's parameters, and what any procedure sets. A block outside
   *  the program (a loose stack, the toolbox): every name the program sets. */
  function namesFor(blk, noLocal) {
    if (!blk) return [];
    const steps = progBlocks(blk.workspace), st = ownerStep(blk), at = steps.indexOf(st);
    const out = new Map(), add = (v) => { if (v && v.name && !out.has(v.name)) out.set(v.name, v); };
    if (!noLocal) localNames(blk).forEach(add);
    (at < 0 ? steps : steps.slice(0, at)).forEach((b) => setsOf(b).forEach(add));
    for (let x = st; x; x = x.getSurroundParent()) if (LOOPS.includes(x.type)) add({ name: loopVar(x) });
    if (st && LOOPS.includes(st.type) && blk === st) bodySets(st).forEach(add);   // (its own fields: after a pass)
    const root = st && st.getRootBlock();
    if (root && root.type === "wb_proc") names(root.getFieldValue("PARAMS")).forEach((n) => add({ name: n }));
    steps.filter((b) => b.getRootBlock().type === "wb_proc").forEach((b) => setsOf(b).forEach(add));
    return [...out.values()];
  }
  // the names an expression uses: not a function's (a "(" follows), a constant, a number's exponent, {row}
  const IDENT = /(?<![\w.{])([A-Za-z_]\w*)\b(?!\s*\()/g, CONSTS = new Set(["pi", "e", "inf"]);
  const exprNames = (s) => [...String(s ?? "").matchAll(IDENT)].map((m) => m[1]).filter((n) => !CONSTS.has(n));
  const braceNames = (s) => [...String(s ?? "").matchAll(/\{(\w+)\}/g)].map((m) => m[1]).filter((n) => n !== "row");
  /** The variable names a block uses (its own fields; a value plugged in is a block of its own). */
  function usesOf(b) {
    const f = (n) => String(b.getFieldValue(n) ?? "");
    switch (b.type) {
      case "wb_var": return f("NAME").trim() ? [f("NAME").trim()] : [];
      case "wb_calc": case "wb_expr": case "wb_optobjx": case "wb_optconx": return exprNames(f("EXPR"));
      case "wb_until": return exprNames(f("COND")).concat(recNames(f("REC")));
      case "wb_seek": return exprNames(f("MEASURE")).concat(recNames(f("REC")));
      case "wb_sweep": case "wb_repeat": return recNames(f("REC"));
      case "wb_set": return f("VALUE").trim().startsWith("=") ? exprNames(f("VALUE").trim().slice(1)) : [];
      case "wb_if": return isNaN(Number(f("RIGHT"))) ? exprNames(f("RIGHT")) : [];
      case "wb_call": return exprNames(f("ARGS"));
      case "wb_log": return braceNames(f("TEXT"));
      case "wb_save": return braceNames(f("PATH"));
      case "wb_pline": return exprNames([f("EXPR"), f("FROM"), f("TO")].join(" "));
      case "wb_pvline": return exprNames(f("X"));
      case "wb_plot": return exprNames(["XFROM", "XTO", "YFROM", "YTO"].map(f).join(" "));
      default: return [];
    }
  }
  const NAMES_WARN = "wb-names";
  /** Every step of the program that uses a name nothing sets before it says so; a chart's formula
   *  using x where the program has a variable x says that x is the chart's. */
  function checkNames(ws) {
    if (!ws || ws.isFlyout) return;
    const steps = new Set(progBlocks(ws));
    ws.getAllBlocks(false).forEach((b) => {
      if (b.isInsertionMarker()) return;
      const uses = steps.has(ownerStep(b)) ? [...new Set(usesOf(b))] : [];
      let text = null;
      if (uses.length) {
        const known = namesFor(b), has = new Set(known.map((v) => v.name)), missing = uses.filter((n) => !has.has(n));
        if (missing.length) text = msg("WB_NAME_UNDEF").replace("{0}", missing.join(", "));
        else if (b.type === "wb_pline" && uses.includes("x") && namesFor(b, true).some((v) => v.name === "x")) text = msg("WB_PLOT_XNOTE");
      }
      if (b.wbNamesWarn !== text) { b.wbNamesWarn = text; b.setWarningText(text, NAMES_WARN); }
    });
  }
  /** Each workspace checks its names a moment after a change (not on every keystroke's render). */
  WB.watchNames = function (ws) {
    let t = null;
    ws.addChangeListener((e) => {
      if (e.isUiEvent) return;
      clearTimeout(t);
      t = setTimeout(() => checkNames(ws), 150);
    });
  };
  /** A variable as a menu shows it: its name, and the result it holds when a read sets it. */
  const varWords = (v) => (v.path ? WBL.say(v.path) : v.name);
  /** A menu item as {name, path} with its words in full (the list) and short (the block face). */
  const varItem = (v) => [varWords(v), v.name, v.path ? shortSay(v.path) : v.name];
  // A block face keeps a picked item short: the object and the field in the interface's language
  // (our Chinese, or Aspen's English), its qualifiers -- "BOTM › Mole fraction · PG" -- cut with "…"
  const FACE_MAX = 28;
  const cap = (t, n) => { const a = [...String(t ?? "")]; return a.length > n ? a.slice(0, n - 1).join("") + "…" : a.join(""); };
  function shortSay(path) {
    const lc = WBL.of(path) || {}, zhWords = I18N.lang === "zh" && lc.gl ? String(lc.gl).split(/[，,]/)[0] : null;
    const field = String(zhWords || lc.field || "").replace(/\s*\(result\)\s*$/i, "");
    return [[lc.obj, field].filter(Boolean).join(" › ")].concat((lc.q || []).map(String)).filter(Boolean).join(" · ") || WBL.say(path);
  }
  /** The columns a loop's results have: its variable, then what each pass records (its record
   *  list, else every variable set inside it), each once. */
  function loopCols(loop) {
    const body = loop.getInputTargetBlock("BODY"), inside = [];
    (body ? body.getDescendants(true) : []).forEach((d) => setsOf(d).forEach((v) => inside.push(v)));
    const rec = recNames(loop.getFieldValue("REC"));
    const list = rec.length ? rec.map((n) => inside.find((v) => v.name === n) || { name: n }) : inside;
    const seen = new Set([loopVar(loop)]);
    return list.filter((v) => !seen.has(v.name) && seen.add(v.name));
  }
  /** The loop a data line or a loop table names (null: none such). */
  function loopNamed(blk) {
    const id = blk && blk.getFieldValue("LOOP");
    const b = id ? mainWs(blk.workspace).getBlockById(id) : null;
    return b && LOOPS.includes(b.type) ? b : null;
  }
  /** A data line's or loop table's columns: y (every recorded variable but the loop's own). */
  function colOpts() {
    const loop = loopNamed(srcOf(this));
    return loop ? loopCols(loop).filter((v) => v.name !== "last_run_ok").map(varItem) : [];
  }
  /** A data line's x: the loop's own input (the default, ""), or one of its variables. */
  function xOpts() {
    const loop = loopNamed(srcOf(this));
    return [[msg("WB_PDATA_XOWN"), ""]].concat(loop ? loopCols(loop).map(varItem) : []);
  }
  /** A loop picked by the user (or still empty): the first loop, its first column. */
  function fillLoop(block) {
    if (block.isInsertionMarker()) return;
    const lf = block.getField("LOOP");
    if (!lf.getValue()) {
      const first = lf.wbItems()[0];
      if (first) lf.setValue(first[1]);
    }
    const yf = block.getField("Y"), was = block.wbLoopWas, now = lf.getValue();
    block.wbLoopWas = now;
    if (was !== now) block.inputList.forEach((i) => i.fieldRow.forEach((f) => { if (f instanceof ListField && f !== lf && block.rendered) f.forceRerender(); }));
    if (!yf || !yf.wbOpt.fill || !loopNamed(block)) return;
    const cols = yf.wbItems().filter(Array.isArray).map((o) => o[1]);
    // empty, or another loop picked and none of its columns chosen: its first column
    if (cols.length && (!yf.getValue() || (was !== undefined && was !== now && !names(yf.getValue()).some((n) => cols.includes(n))))) {
      yf.setValue(cols[0]);
      const xf = block.getField("X");
      if (xf && xf.getValue() && !cols.includes(xf.getValue())) xf.setValue("");
    }
  }
  /** A chart's y range: shown once it holds something, or the block's menu opened it. */
  function syncPlot(block) {
    const on = !!(text(block.getFieldValue("YFROM")) || text(block.getFieldValue("YTO")) || block.wbYOpen);
    ["YRL", "YFROM", "YDASH", "YTO"].forEach((n) => visible(block, block.getField(n), on));
  }
  const LOOP_GONE = "wb-loop-gone";
  /** A data line or loop table naming no loop of the program says so. */
  function checkLoopPick(block) {
    if (!block.rendered || block.isInFlyout || block.isInsertionMarker()) return;
    const text = block.getFieldValue("LOOP") && !loopNamed(block) ? msg("WB_LOOP_GONE_TIP") : !block.getFieldValue("LOOP") ? msg("WB_LOOP_PICK") : null;
    if (block.wbLoopGone !== text) { block.wbLoopGone = text; block.setWarningText(text, LOOP_GONE); }
  }

  // A table's rows: the flowsheet's streams, then its blocks (and those its place steps put down).
  /** The model's blocks and those its place steps put down, "NAME (Type)" (not names other programs used). */
  function fsBlocks(ws) {
    const opts = WB.data.flowsheet.blocks.map((b) => [b.type ? `${b.name} (${b.type})` : b.name, b.name]);
    WB.placed(ws).blocks.forEach((ty, n) => { if (!opts.some((o) => o[1] === n)) opts.push([ty ? `${n} (${ty})` : n, n]); });
    return opts;
  }
  function rowOpts() {
    const blk = srcOf(this), ws = blk && blk.workspace, pl = WB.placed(ws);
    const streams = [...new Set(WB.data.flowsheet.streams.map((s) => s.name).concat([...pl.streams]))];
    const blocks = fsBlocks(ws);
    return [{ head: msg("WB_TABLE_STREAMS") }].concat(streams.map((n) => [n, n]), [{ head: msg("WB_TABLE_BLOCKS") }], blocks);
  }
  /** What a table lists: "block" when its first row is a block, else "stream". */
  function rowKind(table) {
    const first = table ? names(table.getFieldValue("ROWS"))[0] : null;
    return first && blockList(table.workspace).some((o) => o[1] === first) ? "block" : "stream";
  }
  /** A table column's property: a stream's ("s:" and the catalog's key) or a block's ("b:" and
   *  its path under the block) -- the kind the table's rows are; the blocks' of their types. */
  function tpropOpts() {
    const blk = srcOf(this), table = blk && blk.getSurroundParent && blk.getSurroundParent();
    if (rowKind(table) === "stream") return WB.data.catalog.stream_props.map((p) => [optWords(p.label), "s:" + p.key]);
    const types = [...new Set(names(table.getFieldValue("ROWS")).map((n) => blockType(n, table.workspace)))];
    const seen = new Set();
    return types.flatMap((ty) => WB.data.catalog.block_params[ty] || [])
      .filter((p) => !seen.has(p.path) && seen.add(p.path)).map((p) => [optWords(p.label), "b:" + p.path]);
  }
  function tpropWord(v) {
    const s = String(v || "");
    if (s.startsWith("s:")) { const sp = streamProp(s.slice(2)); return sp ? optWords(sp.label) : s.slice(2); }
    return s.startsWith("b:") ? WBL.param(s.slice(2)) : s;
  }
  /** A column's path, {row} for the row: \Data\Streams\{row}\Output\RES_TEMP. */
  function tpropPath(c) {
    const v = String(c.getFieldValue("P") || "");
    if (v.startsWith("b:")) return `\\Data\\Blocks\\${ROW}\\${v.slice(2)}`;
    const sp = streamProp(v.slice(2)), comp = c.getFieldValue("C");
    return sp ? `\\Data\\Streams\\${ROW}\\` + sp.path.replace("{C}", comp === NONE ? "" : comp) : null;
  }
  function syncTprop(block) {
    const v = String(block.getFieldValue("P") || ""), sp = v.startsWith("s:") ? streamProp(v.slice(2)) : null;
    visible(block, block.getField("C"), !!(sp && sp.comp));
  }
  const TABLE_WARN = "wb-table";
  /** A table of properties with no rows ticked, or a table in a loop, says so. */
  function checkTable(block) {
    if (!block.rendered || block.isInFlyout || block.isInsertionMarker()) return;
    const cols = block.getInputTargetBlock("COLS");
    const props = !!cols && cols.getDescendants(false).some((d) => d.type === "wb_tprop");
    const text = props && !names(block.getFieldValue("ROWS")).length ? msg("WB_TABLE_NOROWS")
      : loopOf(block) ? msg("WB_TABLE_IN_LOOP") : null;
    if (block.wbTableWarn !== text) { block.wbTableWarn = text; block.setWarningText(text, TABLE_WARN); }
  }

  /** Unit choices for the PATH plugged into this field's block. "_" keeps the field's unit.
   *  Before the path is known (while a program loads) every unit the program named is
   *  offered, so loading never rejects a unit it cannot check yet. */
  function unitOpts() {
    const blk = this && this.getSourceBlock ? this.getSourceBlock() : null;
    const path = blk ? pathOf(blk.getInputTargetBlock("PATH")) : null;
    const info = path ? WB.data.units[path] : null;
    const cur = this && this.getValue ? this.getValue() : null;
    const opts = [[info && info.unit ? `(${info.unit})` : I18N.t("unit_unknown"), NONE]];
    const units = info ? info.units || [] : [...WB.known.units];
    units.forEach((u) => opts.push([u, u]));
    if (cur && cur !== NONE && !units.includes(cur)) opts.push([cur, cur]);
    return opts;
  }
  function syncUnit(block) {
    const f = block.getField("UNIT");
    if (!f) return;
    const path = pathOf(block.getInputTargetBlock("PATH"));
    const info = path ? WB.data.units[path] : null;
    const want = !(info && !info.unit);                 // a unitless field has no menu
    if (info && f.getValue() !== NONE && !(info.units || []).includes(f.getValue())) f.setValue(NONE);
    // the "(current unit)" label is fixed when the value is set; the unit may arrive later
    const keep = info && info.unit ? `(${info.unit})` : I18N.t("unit_unknown");
    if (f.getValue() === NONE && f.getText() !== keep && info && (info.units || []).length) {
      Blockly.Events.disable();
      try { f.setValue(info.units[0]); f.setValue(NONE); } finally { Blockly.Events.enable(); }
    }
    visible(block, f, want);
  }
  function visible(block, field, want) {
    if (field && field.isVisible() !== want) {
      field.setVisible(want);
      if (block.rendered) block.queueRender();
    }
  }

  // A loop's record list: the names of the variables each pass records, or "all" for every
  // one. "All" is a word in either language, or "*" as older programs wrote it; the field shows
  // the current language's word (WB_REC_ALL), and the program leaves the list out for it.
  const allWord = (n) => n === "*" || n === "全部" || /^all$/i.test(n) || n === msg("WB_REC_ALL");
  const recNames = (text) => names(text).filter((n) => !allWord(n));

  // A loop records a row per pass. One that records every variable (its record list "all" or
  // empty) but has nothing inside that reads a result records only its own variable: it says
  // so, as a warning of its own id, until a step inside reads (a call or a pinch run may too).
  const LOOPS = ["wb_sweep", "wb_seek", "wb_repeat", "wb_until"];
  const READERS = ["wb_read", "wb_calc", "wb_table", "wb_call", "wb_pinch"];
  const LOOP_WARN = "wb-loop-noread";
  function checkLoopRead(block) {
    if (!block.rendered || block.isInFlyout || block.isInsertionMarker()) return;
    const body = block.getInputTargetBlock("BODY");
    const reads = !!body && body.getDescendants(false).some((b) => READERS.includes(b.type));
    const all = !recNames(block.getFieldValue("REC")).length;
    let text = null;
    if (!reads && all) {
      const path = block.getInput("PATH") ? pathOf(block.getInputTargetBlock("PATH")) : null;
      const own = block.type === "wb_sweep" ? "sweep_value" : block.type === "wb_seek" ? "seek_value" : "i";
      text = msg("WB_LOOP_NOREAD").replace("{0}", path ? WBL.say(path) : own);
    }
    if (block.wbLoopWarn !== text) { block.wbLoopWarn = text; block.setWarningText(text, LOOP_WARN); }
  }

  /** A loop's last row: which variables each pass records in its Results table. */
  function recordRow(block) {
    const f = new SuggestField(msg("WB_REC_ALL"), "list");
    f.setTooltip(msg("WB_RECORD_TIP"));
    block.appendDummyInput("RECROW").appendField(msg("WB_RECORD")).appendField(f, "REC");
  }

  // Where a sweep, seek or optimize step leaves the input it changed once the program ends
  // (the server's "finish"; its default first, as workbench_tools._FINISH).
  const FIN = { sweep: ["restore", "last"], seek: ["last", "restore"], optimize: ["restore", "best", "last"] };
  const FIN_OF = { wb_sweep: "sweep", wb_seek: "seek", wb_optimize: "optimize" };
  const FIN_WORD = { restore: "WB_FIN_RESTORE", last: "WB_FIN_LAST", best: "WB_FIN_BEST" };
  function finishRow(block) {
    const kind = FIN_OF[block.type];
    if (!kind) return;
    const f = new Blockly.FieldDropdown(FIN[kind].map((v) => [msg(kind === "seek" && v === "last" ? "WB_FIN_ANSWER" : FIN_WORD[v]), v]));
    f.setTooltip(msg("WB_FINISH_TIP"));
    if (kind !== "optimize") block.appendEndRowInput("FINBR");   // a loop's rows are inline: a row of its own
    block.appendDummyInput("FINROW").appendField(msg("WB_FINISH")).appendField(f, "FINISH");
  }

  // A step's "why": one line saying why the step is there, under its block -- a quiet
  // note one can click into and edit. Only a step that has one shows the row (the block's
  // menu adds or removes it). It rides in the block's extra state ({why}), so undo, copy and
  // paste, and a language switch keep it. A program run records it as the reason of what the
  // step writes (reason_src "why").
  // The row is secondary to its step: a small pale line (style.css .wb-why), drawn while
  // learning mode is on (learn.js); otherwise it is kept but not drawn (the input hidden, so
  // the field, its undo and the program are as they were), and the step's tooltip leads with
  // it. "Edit the note" (WB_WHY_EDIT) in the menu draws it until the editor closes.
  const STEPS = ["wb_set", "wb_run", "wb_read", "wb_save", "wb_calc", "wb_def", "wb_until", "wb_seek", "wb_log", "wb_if",
    "wb_repeat", "wb_sweep", "wb_table", "wb_ltable", "wb_plot", "wb_call", "wb_pinch", "wb_proc", "wb_optimize",
    "wb_place", "wb_connect", "wb_remove", "wb_component", "wb_method", "wb_other", "wb_yourturn", "wb_group"];
  const WHY_MAX = 300, WHY_COLS = 60;        // as the server keeps it; the block shows 60 columns (a CJK character is two)
  /** The server's form of a note: one line, trimmed, at most WHY_MAX characters. */
  const cleanWhy = (v) => String(v ?? "").split(/\s+/).filter(Boolean).join(" ").slice(0, WHY_MAX);
  const wide = (ch) => /[ᄀ-ᅟ⺀-꓏가-힣豈-﫿︰-﹏＀-｠￠-￦]/.test(ch) || ch.codePointAt(0) > 0xffff;
  /** A note as the block shows it: WHY_COLS columns at most, then "…" (the tooltip has it whole). */
  function whyShort(s) {
    let w = 0, out = "";
    for (const ch of s) {
      w += wide(ch) ? 2 : 1;
      if (w > WHY_COLS) return out.trimEnd() + "…";
      out += ch;
    }
    return s;
  }
  let whyIcon = null;                         // the note's icon: the sprite's speech bubble, in white
  function whySrc() {
    if (whyIcon) return whyIcon;
    const sym = document.getElementById("i-chat"), inner = sym ? sym.innerHTML : '<path d="M3 4h10v6H7l-3 2.5V10H3z"/>';
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none" stroke="#fff" stroke-opacity=".74" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
    return (whyIcon = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`);
  }
  /** The note's text field: quiet (style.css .wb-why), cut to WHY_COLS columns, its words in
   *  the tooltip; an empty one says what it is for, and closes its row once left empty. */
  const WHY_H = 18, WHY_PAD = 6, WHY_GAP = [0, 6];   // the note's line: shorter than a field (zelos draws one 32 px tall); its gaps above, below
  /** Learning mode is on (the notes drawn under their steps). */
  const whyLearn = () => !!(window.WBLP && typeof WBLP.learnOn === "function" && WBLP.learnOn());
  class WhyField extends Blockly.FieldTextInput {
    initView() {
      super.initView();
      const g = this.getSvgRoot();
      if (g) g.classList.add("wb-why");
      if (this.textElement_) this.textElement_.classList.add("wb-why-t");   // (its own key in Blockly's width cache)
    }
    /** A line WHY_H tall around its smaller text (the row follows: the block grows by little). */
    updateSize_() {
      super.updateSize_(WHY_PAD);
      this.size_.height = WHY_H;
      this.positionTextElement_(WHY_PAD, Math.max(0, this.size_.width - 2 * WHY_PAD));
      this.positionBorderRect_();
    }
    getDisplayText_() {
      const s = String(this.getText() || "");
      return (s ? whyShort(s) : msg("WB_WHY_PH")).replace(/\s/g, " ");
    }
    onFinishEditing_(value) {
      if (super.onFinishEditing_) super.onFinishEditing_(value);
      setTimeout(() => {                       // (after the editor is gone)
        const b = this.getSourceBlock();
        if (!b || b.isDeadOrDying() || !b.getInput("WHY")) return;
        b.wbWhyOpen = false;                   // (drawn for the editor alone: hidden again outside learning mode)
        if (!cleanWhy(this.getValue())) whySet(b, null);
        else b.whyShow();
      });
    }
  }
  /** Show (text, "" an empty row to type in) or remove (null) a block's note, as one undo step. */
  function whySet(block, text) {
    const BC = Blockly.Events.BlockChange, state = () => (BC && BC.getExtraBlockState_ ? BC.getExtraBlockState_(block) : JSON.stringify(block.saveExtraState() || {}));
    const before = state();
    block.setWhy(text);
    const after = state();
    if (before !== after && Blockly.Events.isEnabled()) Blockly.Events.fire(new (Blockly.Events.get(Blockly.Events.BLOCK_CHANGE))(block, "mutation", null, before, after));
  }
  const WHY_MIXIN = {
    wbStep: true,
    saveExtraState() { return this.getInput("WHY") ? { why: String(this.getFieldValue("WHYTXT") || "") } : null; },
    loadExtraState(s) { this.setWhy(s && typeof s.why === "string" ? s.why : null); },
    /** The note's row: text (cut to the server's form) shown, "" an empty row, null none. */
    setWhy(text) {
      const has = !!this.getInput("WHY");
      if (text == null) {
        if (has) this.removeInput("WHY");
        if (this.getInput("WHYBR")) this.removeInput("WHYBR");
        const ex = extras(this);                 // (and an older page's note in the data: gone too)
        if ("why" in ex) { delete ex.why; this.data = Object.keys(ex).length ? JSON.stringify(ex) : null; }
        return;
      }
      const v = cleanWhy(text);
      if (!v) this.wbWhyOpen = true;             // an empty row to type in: drawn until its editor closes
      if (has) { if (this.getFieldValue("WHYTXT") !== v) this.setFieldValue(v, "WHYTXT"); this.whyShow(); return; }
      // a row of its own at the block's foot: inline rows go on after a field, so they end first
      const last = this.inputList[this.inputList.length - 1];
      if (this.getInputsInline() && last && !(last.connection && last.connection.type === Blockly.ConnectionType.NEXT_STATEMENT)) this.appendEndRowInput("WHYBR");
      const f = new WhyField(v);
      f.setTooltip(() => (this.getField("WHYTXT") ? msg("WB_WHY_TIP").replace("{0}", this.getFieldValue("WHYTXT") || msg("WB_WHY_PH")) : ""));
      this.appendDummyInput("WHY").appendField(new Blockly.FieldImage(whySrc(), 10, 10, ""), "WHYICON").appendField(f, "WHYTXT");
      this.whyShow();
    },
    /** Draw the note's row (learning mode, or open to edit) or keep it undrawn; true when drawn. */
    whyShow() {
      const on = whyLearn() || !!this.wbWhyOpen;
      let moved = false;
      ["WHYBR", "WHY"].forEach((n) => {
        const i = this.getInput(n);
        if (i && i.isVisible() !== on) { i.setVisible(on); moved = true; }
      });
      if (moved && this.rendered && typeof this.queueRender === "function") this.queueRender();
      return on;
    },
    /** Its note, in the server's form ("" for none). */
    getWhy() { return this.getInput("WHY") ? cleanWhy(this.getFieldValue("WHYTXT")) : ""; },
  };
  /** Learning mode switched since ws drew its notes: each step's row drawn or not again. */
  WB.whyShow = function (ws) {
    const on = whyLearn();
    if (!ws || ws.wbWhyLearn === on) return;
    ws.wbWhyLearn = on;
    ws.getAllBlocks(false).forEach((b) => { if (b.wbStep && b.getInput("WHY")) b.whyShow(); });
  };
  /** A step's path, and a path block's own: where it sits in Aspen's navigation tree, for the
   *  tooltip ("Blocks › ESTCOL (RadFrac) › Reflux ratio"); null where the step has no path. */
  function whereOf(block) {
    const slot = ["PATH", "VAL", "LEFT"].find((n) => block.getInput(n));      // (a column's value, a condition's left side)
    const p = /^wb_(stream|block|path)$/.test(block.type) ? pathOf(block) : slot ? pathOf(block.getInputTargetBlock(slot)) : null;
    return p && String(p).startsWith("\\Data\\") && String(p).split("\\").filter(Boolean).length > 2 ? WBL.full(p) : null;
  }
  /** The steps take a note (WHY_MIXIN, the block menu's two items); every block with an Aspen
   *  path says where it sits in Aspen in its tooltip. */
  function dressSteps() {
    STEPS.forEach((type) => Object.assign(Blockly.Blocks[type], WHY_MIXIN));
    // the note's row as tall as its line (zelos gives a row without a connection 32 px at least),
    // close under the step's row: a small gap above it, a little more below
    const RI = Blockly.zelos && Blockly.zelos.RenderInfo;
    if (RI && !RI.prototype.wbWhyRow) {
      const add = RI.prototype.addInput_, gap = RI.prototype.getSpacerRowHeight_;
      RI.prototype.addInput_ = function (input, row) {
        add.call(this, input, row);
        const b = input && input.name === "WHY" ? input.getSourceBlock() : null;
        if (b && b.wbStep) { row.minHeight = WHY_H; row.wbWhy = true; }
      };
      RI.prototype.getSpacerRowHeight_ = function (prev, next) {
        if (next && next.wbWhy) return WHY_GAP[0];
        if (prev && prev.wbWhy) return WHY_GAP[1];
        return gap.call(this, prev, next);
      };
      RI.prototype.wbWhyRow = true;
    }
    ["wb_set", "wb_read", "wb_sweep", "wb_seek", "wb_optvar", "wb_optobj", "wb_optcon", "wb_optterm", "wb_tcol", "wb_if",
      "wb_stream", "wb_block", "wb_path", "wb_yourturn"].forEach((type) => {
      const def = Blockly.Blocks[type], init = def.init;
      def.init = function () {
        init.call(this);
        const block = this, base = this.tooltip;
        this.setTooltip(() => {
          const tip = typeof base === "function" ? base() : String(base || "");
          const where = whereOf(block);
          return where ? `${tip}${tip ? "\n" : ""}${msg("WB_WHY_WHERE").replace("{0}", where)}` : tip;
        });
      };
    });
    const reg = Blockly.ContextMenuRegistry && Blockly.ContextMenuRegistry.registry, BLOCK = Blockly.ContextMenuRegistry.ScopeType.BLOCK;
    const may = (b) => !!b && b.wbStep && !b.isInFlyout && !b.isInsertionMarker() && b.isEditable();
    if (reg && !reg.getItem("wb_why_add")) {
      reg.register({ id: "wb_why_add", scopeType: BLOCK, weight: 5, displayText: () => msg("WB_WHY_ADD"),
        preconditionFn: (scope) => (may(scope.block) && !scope.block.getInput("WHY") ? "enabled" : "hidden"),
        callback: (scope) => {
          const b = scope.block;
          whySet(b, "");
          const after = Blockly.renderManagement && Blockly.renderManagement.finishQueuedRenders ? Blockly.renderManagement.finishQueuedRenders() : Promise.resolve();
          after.then(() => { const f = !b.isDeadOrDying() && b.getField("WHYTXT"); if (f) f.showEditor(); });
        } });
      reg.register({ id: "wb_why_remove", scopeType: BLOCK, weight: 5, displayText: () => msg("WB_WHY_REMOVE"),
        preconditionFn: (scope) => (may(scope.block) && scope.block.getInput("WHY") ? "enabled" : "hidden"),
        callback: (scope) => whySet(scope.block, null) });
    }
    // a note not drawn (outside learning mode): drawn to edit, until its editor closes
    if (reg && !reg.getItem("wb_why_edit")) {
      reg.register({ id: "wb_why_edit", scopeType: BLOCK, weight: 5, displayText: () => msg("WB_WHY_EDIT"),
        preconditionFn: (scope) => (may(scope.block) && scope.block.getInput("WHY") && !scope.block.getInput("WHY").isVisible() ? "enabled" : "hidden"),
        callback: (scope) => {
          const b = scope.block;
          b.wbWhyOpen = true;
          b.whyShow();
          const after = Blockly.renderManagement && Blockly.renderManagement.finishQueuedRenders ? Blockly.renderManagement.finishQueuedRenders() : Promise.resolve();
          after.then(() => { const f = !b.isDeadOrDying() && b.getField("WHYTXT"); if (f) f.showEditor(); });
        } });
    }
    // a step whose note is not drawn: its tooltip leads with it
    STEPS.forEach((type) => {
      const def = Blockly.Blocks[type], init = def.init;
      def.init = function () {
        init.call(this);
        const block = this, base = this.tooltip;
        this.setTooltip(() => {
          const tip = typeof base === "function" ? base() : String(base || "");
          const row = block.getInput("WHY"), why = row && !row.isVisible() ? block.getWhy() : "";
          return why ? `${msg("WB_WHY_LINE").replace("{0}", why)}${tip ? "\n" : ""}${tip}` : tip;
        });
      };
    });
    // What is this field?: a step's path, or a path block, where the server and the
    // window make help cards (feature "field_help"); the page opens the card (WB.onFieldHelp)
    if (reg && !reg.getItem("wb_field_help")) {
      reg.register({ id: "wb_field_help", scopeType: BLOCK, weight: 6, displayText: () => msg("WB_FIELD_HELP"),
        preconditionFn: (scope) => (typeof WB.onFieldHelp === "function" && (WB.fieldHelpOn ? WB.fieldHelpOn() : feature("field_help"))
          && WB.fieldPathOf(scope.block) ? "enabled" : "hidden"),
        callback: (scope) => WB.onFieldHelp(scope.block) });
    }
    // Ask AI about a step of the program, beside its note: the page asks (WB.onAsk); a
    // loose stack is no step
    const askable = (b) => !!b && b.wbStep && typeof WB.onAsk === "function" && !b.isInFlyout && !b.isInsertionMarker() && !!WB.stepOf(b);
    if (reg && !reg.getItem("wb_ask_step")) {
      reg.register({ id: "wb_ask_step", scopeType: BLOCK, weight: 6, displayText: () => msg("WB_ASK_STEP"),
        preconditionFn: (scope) => (askable(scope.block) ? "enabled" : "hidden"),
        callback: (scope) => WB.onAsk(scope.block) });
    }
    // Turn a step off: it stays in the program, greyed, and does not run (off: true); a loop
    // or if takes the steps inside with it, so theirs is greyed and not offered. It stands in for
    // Blockly's own "Disable block", whose blocks looked the same but ran all the same (HIDE).
    const offable = (b) => !!b && b.wbStep && b.type !== "wb_proc" && !b.isInFlyout && !b.isInsertionMarker() && b.isEditable();
    if (reg && !reg.getItem("wb_off")) {
      reg.register({ id: "wb_off", scopeType: BLOCK, weight: 5,
        displayText: (scope) => msg(scope.block && scope.block.hasDisabledReason(OFF) ? "WB_OFF_REMOVE" : "WB_OFF_ADD"),
        preconditionFn: (scope) => (!offable(scope.block) ? "hidden" : scope.block.getInheritedDisabled() ? "disabled" : "enabled"),
        callback: (scope) => grouped(() => scope.block.setDisabledReason(!scope.block.hasDisabledReason(OFF), OFF)) });
    }
    // A block's menu: the page's items first (ids wb_*): what the step does (turned off, a
    // breakpoint), its note, then help on it; then under a line Blockly's own that a program
    // keeps: Duplicate, Delete. Blockly's comment, inline inputs, collapse and help are not
    // offered: the program the server keeps has no place for them, so they would be gone with the
    // next version.
    const HIDE = new Set(["blockComment", "blockInline", "blockCollapseExpand", "blockHelp", "blockDisable"]);
    const ORDER = ["wb_off", "wb_brk", "wb_why_add", "wb_why_edit", "wb_why_remove", "wb_yt_check", "wb_yt_answer", "wb_plot_yr", "wb_field_help", "wb_ask_step"];
    const rank = (o) => (ORDER.includes(o.id) ? ORDER.indexOf(o.id) : ORDER.length);
    if (reg && !reg.wbGrouped) {
      reg.wbGrouped = true;
      const all = reg.getContextMenuOptions.bind(reg);
      reg.getContextMenuOptions = (scope, e) => {
        const opts = all(scope, e);
        if (!scope || !scope.block) return opts;
        const kept = opts.filter((o) => !HIDE.has(o.id)), theirs = kept.filter((o) => !/^wb_/.test(o.id));
        const ours = kept.filter((o) => /^wb_/.test(o.id)).sort((a, z) => rank(a) - rank(z));
        return ours.length && theirs.length ? ours.concat([{ id: "wb_sep", scope, weight: 0, separator: true }], theirs) : ours.concat(theirs);
      };
    }
  }
  /** A step's place in its tab's program, counted as the server counts them (the main program,
   *  then the procedures by name; a step before the steps inside it): {n (from 1), total, kind
   *  (its do: "sweep"), path (what it sets, reads or varies; null)}. null: not a step of the
   *  program (a loose stack, the start). */
  /** The Aspen field a block names, for its help card: a step's path slot, or a
   *  path block itself -- {path, at: the path block} -- where it names a field (\Data\ and a
   *  field under an object); else null. */
  WB.fieldPathOf = function (blk) {
    if (!blk || blk.isInFlyout || (blk.isInsertionMarker && blk.isInsertionMarker())) return null;
    const PATHS = /^wb_(stream|block|path)$/;
    const at = PATHS.test(blk.type) ? blk : blk.getInput && blk.getInput("PATH") ? blk.getInputTargetBlock("PATH") : null;
    const p = at && PATHS.test(at.type) ? pathOf(at) : null;
    return p && String(p).startsWith("\\Data\\") && String(p).split("\\").filter(Boolean).length > 3 ? { path: String(p), at } : null;
  };
  WB.stepOf = function (blk) {
    const root = blk && blk.workspace ? blk.getRootBlock() : null;
    if (!root || (root.type !== "wb_start" && root.type !== "wb_proc")) return null;
    const ids = [];
    const walk = (list) => (list || []).forEach((st) => { ids.push(st.id); ["then", "else", "body"].forEach((k) => walk(st[k])); });
    walk(WB.workspaceToProgram(blk.workspace));
    const n = ids.indexOf(blk.id);
    if (n < 0) return null;
    const at = blk.getInput("PATH") ? blk.getInputTargetBlock("PATH") : null;
    return { n: n + 1, total: ids.length, kind: blk.type.replace(/^wb_/, ""), path: at ? pathOf(at) : null };
  };

  // ------------------------------------------------------------------ flowsheet changes
  // Five steps change the flowsheet itself (the server's place, connect, remove, component,
  // method): names, types and ports only; a block's settings are set steps. Where the server
  // runs them they have a category of their own, and a step can be turned off (off: true; the block's disabled reason OFF). They cannot sit in a loop: a
  // drag into one is refused (WriteChecker), one that arrives there (the AI's program, a paste)
  // says why. A menu left at "—" (no stream yet) keeps its step out of the program until it is
  // filled in: the server refuses such a statement, and with it the user's whole edit.
  const STRUCT = ["wb_place", "wb_connect", "wb_remove", "wb_component", "wb_method"];
  const OFF = "wb_off", STRUCT_LOOP = "wb-struct-loop", STRUCT_TODO = "wb-struct-todo";
  /** The server groups a program's steps under headings (catalog.features groups). */
  const groupsOn = () => feature("groups");
  const up = (v) => String(v ?? "").trim().toUpperCase();
  const srcOf = (field) => (field && field.getSourceBlock ? field.getSourceBlock() : null);
  const curOf = (field) => (field && field.getValue ? field.getValue() : null);
  /** A palette tab's heading in the type menu (a value no type has; TypeDropdown makes it unpickable). */
  const TAB = "\u0001";
  const STYPES = ["MATERIAL", "HEAT", "WORK"];
  const METHODS = ["NRTL", "NRTL-RK", "NRTL-HOC", "UNIQUAC", "UNIQ-RK", "UNIFAC", "WILSON", "WILS-RK", "PENG-ROB", "PR-BM",
    "RK-SOAVE", "RKS-BM", "PSRK", "SR-POLAR", "IDEAL", "CHAO-SEA", "GRAYSON", "BK10", "ELECNRTL", "ENRTL-RK", "STEAM-TA", "IAPWS-95"];
  /** A gloss list (a Blockly.Msg "HeatX <words>|…"; empty in English) as {NAME: words}. */
  const glosses = {};
  WB.gloss = function (key) {
    const src = String(Blockly.Msg[key] || "");
    if (!glosses[key] || glosses[key].src !== src) {
      const map = {};
      src.split("|").forEach((pair) => { const i = pair.indexOf(" "); if (i > 0) map[pair.slice(0, i).toUpperCase()] = pair.slice(i + 1); });
      glosses[key] = { src, map };
    }
    return glosses[key].map;
  };
  const glossed = (name, g) => (g ? `${name}（${g}）` : name);
  /** The port table (catalog.ports), any case: {by: {TYPE: [ports]}, names: {TYPE: as written}}. */
  function portTable() {
    const src = (WB.data.catalog && WB.data.catalog.ports) || {};
    if (portTable.src !== src) {
      const by = {}, names = {};
      Object.keys(src).forEach((ty) => { const k = ty.toUpperCase(); if (!by[k]) { by[k] = [].concat(src[ty] || []); names[k] = ty; } });
      Object.assign(portTable, { src, by, names });
    }
    return portTable;
  }
  const portsOf = (type) => portTable().by[up(type)] || [];
  /** "C(IN) (cold side inlet)": a port with what it is, where the language has words for it. */
  WB.portLabel = function (p) {
    const g = WB.gloss("WB_GLOSS_PORT"), m = /^(.+)\((IN|OUT)\)$/i.exec(String(p || ""));
    if (!m || !Object.keys(g).length) return String(p || "?");
    return `${p}（${g[m[1].toUpperCase()] || ""}${msg(m[2].toUpperCase() === "IN" ? "WB_PORT_IN" : "WB_PORT_OUT")}）`;
  };
  /** What the place steps in a workspace put down: {blocks: Map(NAME -> type), streams: Set(NAME)}. */
  WB.placed = function (ws) {
    const out = { blocks: new Map(), streams: new Set() };
    if (ws && ws.isFlyout && ws.targetWorkspace) ws = ws.targetWorkspace;
    (ws ? ws.getAllBlocks(false) : []).forEach((b) => {
      const n = b.type === "wb_place" && !b.isInsertionMarker() ? up(b.getFieldValue("NAME")) : "";
      if (!n) return;
      if (b.getFieldValue("KIND") === "stream") out.streams.add(n);
      else out.blocks.set(n, String(b.getFieldValue("BTYPE") || ""));
    });
    return out;
  };
  /** A name no block or stream has yet (B1, B2… / S1, S2…), for a new place step. */
  function freeName(prefix, ws) {
    const fs = WB.data.flowsheet, pl = WB.placed(ws);
    const taken = new Set(fs.blocks.map((b) => up(b.name)).concat(fs.streams.map((s) => up(s.name)), [...pl.blocks.keys()], [...pl.streams]));
    let i = 1;
    while (taken.has(prefix + i)) i++;
    return prefix + i;
  }
  /** Names, as Aspen keeps them: upper case, no spaces; an empty one is refused. */
  const nameCheck = (v) => up(v).replace(/\s+/g, "") || null;
  /** Options that keep every value a program named (WB.known), so loading is never refused. */
  function known(opts, extra) {
    const out = opts.slice();
    extra.forEach((v) => { if (v && !out.some((o) => o[1] === v)) out.push([v, v]); });
    return out.length ? out : [["—", NONE]];
  }
  /** The place step's types: Aspen's model palette tab by tab (catalog.palette, the most used tab
   *  first), each under its name; then, past a line, any other type of the port table or the model. */
  function typeOpts() {
    const g = WB.gloss("WB_GLOSS_TYPE"), tb = portTable(), seen = new Set(), opts = [];
    const add = (ty) => { const k = up(ty); if (ty && !seen.has(k)) { seen.add(k); opts.push([glossed(ty, g[k]), ty]); } };
    ((WB.data.catalog && WB.data.catalog.palette) || []).forEach((p) => {
      opts.push([WBL.titleText(p.title), TAB + p.title]);
      p.types.forEach(add);
    });
    const n = opts.length;
    Object.keys(tb.names).sort().forEach((k) => add(tb.names[k]));
    WB.data.flowsheet.blocks.forEach((b) => add(b.type));
    if (n && opts.length > n) opts.splice(n, 0, Blockly.FieldDropdown.SEPARATOR);
    return known(opts, [...WB.known.types, curOf(this)]);
  }
  function stypeOpts() {
    const g = WB.gloss("WB_GLOSS_STREAM");
    return known(STYPES.map((ty) => [glossed(ty, g[ty]), ty]), [...WB.known.stypes, curOf(this)]);
  }
  function sStreamOpts() {
    const blk = srcOf(this), pl = WB.placed(blk && blk.workspace);
    return known(WB.data.flowsheet.streams.map((s) => [s.name, s.name]), [...pl.streams, ...knownFor(this, WB.known.streams), curOf(this)]);
  }
  function sBlockOpts() {
    const blk = srcOf(this), opts = blockList(blk && blk.workspace, this), cur = curOf(this);
    return cur && cur !== NONE && !opts.some((o) => o[1] === cur) ? opts.concat([[cur, cur]]) : opts;
  }
  function sCompOpts() {
    return known(WB.data.flowsheet.components.map((c) => [c, c]), [...knownFor(this, WB.known.comps), curOf(this)]);
  }
  function methodOpts() {
    return known(METHODS.map((m) => [m, m]), [...WB.known.methods, curOf(this)]);
  }
  /** The ports of the chosen block's type, in the menu the user opens; everywhere else every
   *  port (a load, an undo or a paste sets a port before or apart from its block). */
  function portOpts() {
    const blk = srcOf(this), cur = curOf(this);
    const own = blk ? portsOf(blockType(blk.getFieldValue("B"), blk.workspace)) : [];
    let list = own;
    if (!(own.length && WB.menuFor === this)) {
      const all = new Set(own);
      Object.values(portTable().by).forEach((ps) => ps.forEach((p) => all.add(p)));
      WB.known.ports.forEach((p) => all.add(p));
      list = [...all];
    }
    if (cur && cur !== NONE && !list.includes(cur)) list = list.concat([cur]);
    return list.length ? list.map((p) => [WB.portLabel(p), p]) : [["—", NONE]];
  }
  /** After the user picks (by: the field picked): a port the block has. Taking a stream off,
   *  the port it is on at that block, where the flowsheet says; the stream (or the kind)
   *  picked, the block it is on too, unless the block chosen is one of its ends. */
  function fixPort(block, by) {
    const pf = block.getField("PORT"), bf = block.getField("B");
    if (!pf || !pf.isVisible()) return;
    if (block.type === "wb_remove") {
      const s = WB.data.flowsheet.streams.find((x) => x.name === block.getFieldValue("S"));
      const ends = s ? [[s.to, s.to_port], [s.from, s.from_port]].filter((e) => e[0]) : [];
      let at = ends.find((e) => e[0] === bf.getValue());
      if (!at && by !== "B" && ends.length) { at = ends[0]; bf.getOptions(false); bf.setValue(at[0]); }
      if (at && at[1] && pf.getOptions(false).some((o) => o[1] === at[1])) { pf.setValue(at[1]); return; }
    }
    const own = portsOf(blockType(bf.getValue(), block.workspace));
    if (own.length && !own.includes(pf.getValue())) { pf.getOptions(false); pf.setValue(own[0]); }
  }
  /** A menu left at "—" (a visible one): the step is not filled in. */
  const structTodo = (block) => block.inputList.some((inp) => inp.fieldRow.some((f) =>
    f.name && f.isVisible() && f instanceof Blockly.FieldDropdown && f.getValue() === NONE));
  /** The loop a block sits in (any depth), or null. */
  function loopOf(block) {
    for (let x = block.getSurroundParent(); x; x = x.getSurroundParent()) if (LOOPS.includes(x.type)) return x;
    return null;
  }
  /** A flowsheet change in a loop, or not filled in, says so (a warning each). */
  function checkStruct(block) {
    if (!block.rendered || block.isInFlyout || block.isInsertionMarker()) return;
    const loop = loopOf(block) ? msg("WB_STRUCT_IN_LOOP") : null, todo = structTodo(block) ? msg("WB_STRUCT_TODO") : null;
    if (block.wbLoopStruct !== loop) { block.wbLoopStruct = loop; block.setWarningText(loop, STRUCT_LOOP); }
    if (block.wbTodo !== todo) { block.wbTodo = todo; block.setWarningText(todo, STRUCT_TODO); }
  }
  /** Whether a stack (the block, the steps under and inside it) holds a flowsheet change. */
  const hasStruct = (blk) => !!blk && blk.getDescendants(false).some((d) => STRUCT.includes(d.type));
  /** Whether a step dropped on a statement connection would sit in a loop: after a block (its
   *  next), where that block sits; in a block's slot, in that block. */
  function loopAt(conn) {
    const blk = conn.getSourceBlock();
    if (conn !== blk.nextConnection && LOOPS.includes(blk.type)) return true;
    return !!loopOf(blk);
  }
  /** The tooltip of a flowsheet change: what it does in Aspen's words, and that a loop is no place for it. */
  function structTip(b) {
    const f = (n) => b.getFieldValue(n), kind = f("KIND");
    const tip = b.type === "wb_place" ? (kind === "stream" ? msg("WB_PLACE_S_TIP").replace(/\{0\}/g, f("STYPE")) : msg("WB_PLACE_TIP").replace(/\{0\}/g, f("BTYPE")))
      : b.type === "wb_connect" ? msg("WB_CONNECT_TIP") : b.type === "wb_remove" ? msg("WB_REMOVE_TIP")
        : b.type === "wb_component" ? msg("WB_COMP_TIP") : msg("WB_METHOD_TIP");
    return `${tip}\n${msg("WB_STRUCT_NOLOOP")}`;
  }
  /** Which fields a kind menu shows: the place step's two type menus, what remove names, a component typed or picked. */
  const SHOWN = {
    wb_place: (k) => ({ BTYPE: k !== "stream", STYPE: k === "stream" }),
    wb_remove: (k) => ({ LS: k === "conn", S: k !== "block", BR: k === "conn", LFROM: k === "conn", B: k !== "stream", LOF: k === "conn", PORT: k === "conn" }),
    wb_component: (k) => ({ ADD: k !== "remove", REM: k === "remove" }),
  };
  /** The kind menu's validator (every value it takes: a pick, a load, an undo) shows the kind's
   *  fields (and a disconnect's second row), and swaps a place step's untouched name for one of
   *  its kind (B1 -> S1; a loaded name is set after, and wins). */
  function onKind(v) {
    const blk = srcOf(this), show = blk && SHOWN[blk.type], nf = blk && blk.getField("NAME"), pre = v === "stream" ? "S" : "B";
    if (show) Object.entries(show(v)).forEach(([name, want]) => {
      const inp = blk.getField(name) ? null : blk.getInput(name);
      if (!inp) visible(blk, blk.getField(name), want);
      else if (inp.isVisible() !== want) { inp.setVisible(want); if (blk.rendered) blk.queueRender(); }
    });
    if (nf && blk.wbAuto && nf.getValue() === blk.wbAuto && !blk.wbAuto.startsWith(pre)) nf.setValue((blk.wbAuto = freeName(pre, blk.workspace)));
    return v;
  }
  /** A struct block's kind menu; the user's pick of a disconnect points it at a real port. */
  function kindField(options) {
    const f = new PickDropdown(options, onKind);
    f.onPick = function () { const blk = srcOf(this); if (blk && blk.type === "wb_remove") fixPort(blk, "KIND"); };
    return f;
  }
  /** A stream or block menu whose pick moves the port to one that fits (fixPort). */
  function pickField(gen, name) {
    const f = new PickDropdown(gen);
    f.onPick = function () { const blk = srcOf(this); if (blk) fixPort(blk, name); };
    return f;
  }

  // ------------------------------------------------------------------ the manual step
  // wb_yourturn, the server's yourturn: the run pauses there until the user sets the input in
  // its slot (in the inspector or Aspen's own window) and presses Done (app-turn.js). Its hint is
  // required, as the server's; a check (expect: an op and a number, {variable} or option code)
  // and the answer the program writes on Show answer are rows of their own, shown only when they
  // hold something (the block's menu adds or removes each; one left empty closes), riding in the
  // block's extra state beside its note. A step without its field or hint, or with a field
  // that is no input, is not sent (the server would refuse the whole edit) and says so; one in a
  // loop says the server will refuse it (yt_in_loop). Its words are the interface's (i18n.js yt_*).
  // While its tab's program runs (WB.ytHide, from app-turn.js), the answer row says "(hidden)" and
  // does not open to be read (the practice gives nothing away) until Show answer is pressed for
  // it; the program's editing is as ever once the run ends.
  const ui = (key) => I18N.t(key);
  const YT_OPS = [[">", ">"], ["≥", ">="], ["<", "<"], ["≤", "<="], ["=", "=="], ["≠", "!="]];
  const YT_ROWS = { exp: ["YTEBR", "YTEXP"], ans: ["YTABR", "YTANS"] };
  const YT_ORDER = ["PATH", "YTBR1", "HINTROW", "YTEBR", "YTEXP", "YTABR", "YTANS", "WHYBR", "WHY"];
  const YT_LOOP = "wb-yt-loop", YT_TODO = "wb-yt-todo";
  /** A path the server takes for a manual step: an input's (\Data\...\Input\<field>). */
  const ytInput = (p) => {
    const parts = String(p || "").split("\\").filter(Boolean).map((x) => x.toLowerCase());
    return String(p || "").startsWith("\\") && parts[0] === "data" && parts.slice(1, -1).includes("input") && !parts.includes("output");
  };
  /** The hint, check or answer field: an empty one shows what it is for, and a check or answer
   *  row left empty closes (as a note's row does); an answer hidden while its program runs says so
   *  and does not open (the value stays the field's). */
  class YtField extends Blockly.FieldTextInput {
    constructor(value, ph, row) { super(value); this.wbPh = ph; this.wbRow = row; }
    hidden_() { const b = this.wbRow === "ans" && this.getSourceBlock(); return !!(b && b.wbYtHide); }
    getDisplayText_() {
      const s = String(this.getText() || "");
      if (s && this.hidden_()) return ui("yt_ans_hidden");
      return (s ? super.getDisplayText_() : ui(this.wbPh)).replace(/\s/g, " ");
    }
    showEditor_(e, quiet) { if (!this.hidden_()) super.showEditor_(e, quiet); }
    onFinishEditing_(value) {
      if (super.onFinishEditing_) super.onFinishEditing_(value);
      if (!this.wbRow || String(value ?? "").trim()) return;
      setTimeout(() => {                       // (after the editor is gone)
        const b = this.getSourceBlock();
        if (b && !b.isDeadOrDying() && b.getInput(YT_ROWS[this.wbRow][1]) && !String(this.getValue() ?? "").trim()) ytSet(b, this.wbRow, null);
      });
    }
  }
  /** Show (a value, "" an empty row to type in) or remove (null) a manual step's check or answer
   *  row, as one undo step. */
  function ytSet(block, kind, value) {
    const BC = Blockly.Events.BlockChange, state = () => (BC && BC.getExtraBlockState_ ? BC.getExtraBlockState_(block) : JSON.stringify(block.saveExtraState() || {}));
    const before = state();
    block.setYt(kind, value);
    const after = state();
    if (before !== after && Blockly.Events.isEnabled()) Blockly.Events.fire(new (Blockly.Events.get(Blockly.Events.BLOCK_CHANGE))(block, "mutation", null, before, after));
  }
  const YT_STATE = {
    saveExtraState() {
      const s = WHY_MIXIN.saveExtraState.call(this) || {};
      if (this.getInput("YTEXP")) s.expect = { op: this.getFieldValue("YTOP"), value: String(this.getFieldValue("YTEXP") ?? "") };
      if (this.getInput("YTANS")) s.answer = String(this.getFieldValue("YTANS") ?? "");
      return Object.keys(s).length ? s : null;
    },
    loadExtraState(s) {
      WHY_MIXIN.loadExtraState.call(this, s);
      const e = s && s.expect && typeof s.expect === "object" ? s.expect : null;
      this.setYt("exp", e ? { op: e.op, value: String(e.value ?? "") } : null);
      this.setYt("ans", s && s.answer != null ? String(s.answer) : null);
    },
    /** kind "exp" (value {op, value} or a text), "ans" (a text); null: no row. The rows stay in
     *  order: the check, the answer, then the note. */
    setYt(kind, value) {
      const [br, name] = YT_ROWS[kind], has = !!this.getInput(name);
      if (value == null) {
        if (has) this.removeInput(name);
        if (this.getInput(br)) this.removeInput(br);
        return;
      }
      const v = kind === "exp" && typeof value === "object" ? value : { value };
      if (!has) {
        this.appendEndRowInput(br);
        const row = this.appendDummyInput(name);
        if (kind === "exp") {
          row.appendField(ui("yt_blk_check")).appendField(new Blockly.FieldDropdown(YT_OPS), "YTOP")
            .appendField(new YtField("", "yt_blk_ph", "exp"), "YTEXP");
          this.getField("YTEXP").setTooltip(() => ui("tip_yt_check"));
        } else {
          row.appendField(ui("yt_blk_answer")).appendField(new YtField("", "yt_blk_ph", "ans"), "YTANS");
          this.getField("YTANS").setTooltip(() => ui(this.wbYtHide ? "tip_yt_ans_hidden" : "tip_yt_answer"));
        }
        YT_ORDER.forEach((n) => { if (this.getInput(n)) this.moveInputBefore(n, null); });
      }
      if (kind === "exp") {
        if (YT_OPS.some((o) => o[1] === v.op) && this.getFieldValue("YTOP") !== v.op) this.setFieldValue(v.op, "YTOP");
        if (this.getFieldValue("YTEXP") !== String(v.value ?? "")) this.setFieldValue(String(v.value ?? ""), "YTEXP");
      } else if (this.getFieldValue("YTANS") !== String(v.value ?? "")) this.setFieldValue(String(v.value ?? ""), "YTANS");
    },
  };
  /** The manual steps' answers hidden or shown (WB.ytHide): hide(block) says for each of the
   *  workspace's manual steps; an answer row changed is drawn again. */
  WB.ytHide = function (ws, hide) {
    if (!ws || typeof ws.getBlocksByType !== "function") return;
    ws.getBlocksByType("wb_yourturn", false).forEach((b) => {
      const want = !!hide(b);
      if (!!b.wbYtHide === want) return;
      b.wbYtHide = want;
      const f = b.getField("YTANS");
      if (f && b.rendered) f.forceRerender();
    });
  };
  /** A manual step in a loop says the server refuses it; one not filled in, that it does not run. */
  function checkTurn(block) {
    if (!block.rendered || block.isInFlyout || block.isInsertionMarker()) return;
    const loop = loopOf(block) ? ui("yt_loop_err") : null;
    const p = pathOf(block.getInputTargetBlock("PATH")), todo = !ytInput(p) || !cleanWhy(block.getFieldValue("HINT")) ? ui("yt_todo") : null;
    if (block.wbYtLoop !== loop) { block.wbYtLoop = loop; block.setWarningText(loop, YT_LOOP); }
    if (block.wbYtTodo !== todo) { block.wbYtTodo = todo; block.setWarningText(todo, YT_TODO); }
  }
  /** The block's menu: Add or Remove check, Add or Remove answer (an added row opens to type in). */
  function turnMenu(reg, BLOCK) {
    if (!reg || reg.getItem("wb_yt_check")) return;
    const may = (b) => !!b && b.type === "wb_yourturn" && !b.isInFlyout && !b.isInsertionMarker() && b.isEditable();
    [["wb_yt_check", "exp", "yt_menu_check"], ["wb_yt_answer", "ans", "yt_menu_answer"]].forEach(([id, kind, key]) => {
      reg.register({ id, scopeType: BLOCK, weight: 5,
        displayText: (scope) => ui(`${key}_${scope.block && scope.block.getInput(YT_ROWS[kind][1]) ? "rm" : "add"}`),
        preconditionFn: (scope) => (may(scope.block) ? "enabled" : "hidden"),
        callback: (scope) => {
          const b = scope.block;
          if (b.getInput(YT_ROWS[kind][1])) { ytSet(b, kind, null); return; }
          ytSet(b, kind, kind === "exp" ? { op: ">=", value: "" } : "");
          const after = Blockly.renderManagement && Blockly.renderManagement.finishQueuedRenders ? Blockly.renderManagement.finishQueuedRenders() : Promise.resolve();
          after.then(() => { const f = !b.isDeadOrDying() && b.getField(YT_ROWS[kind][1]); if (f) f.showEditor(); });
        } });
    });
  }

  // ------------------------------------------------------------------ block definitions
  let defined = false;
  function defineBlocks() {
    if (defined) return;
    defined = true;
    patchTextEditor();
    Blockly.Extensions.register("wb_rec", function () {
      this.getField("REC").setTooltip(msg("WB_RECORD_TIP"));
      this.setOnChange(function () { checkLoopRead(this); });
    });
    Blockly.Extensions.register("wb_finish", function () { finishRow(this); });
    // an if compares with a number, a variable or an expression
    Blockly.Extensions.register("wb_ifright", function () { this.getField("RIGHT").setTooltip(msg("WB_IF_RIGHT_TIP")); });
    // the blocks a pinch leaves out: ticked from the flowsheet's blocks
    Blockly.Extensions.register("wb_pinchexcl", function () {
      const inp = this.getField("EXCL").getParentInput();
      inp.removeField("EXCL");
      inp.appendField(new ListField(function () { const blk = srcOf(this); return fsBlocks(blk && blk.workspace); },
        { multi: true, empty: "WB_PINCH_EXCL_NONE" }), "EXCL");
    });
    // a read's variable named after what it reads (feed_res_temp), and renamed with it while it
    // keeps that name and nothing else uses it; a name typed or loaded stays
    Blockly.Extensions.register("wb_readname", function () {
      this.setOnChange(function () {
        if (this.isInFlyout || this.isInsertionMarker()) return;
        const p = pathOf(this.getInputTargetBlock("PATH")), as = text(this.getFieldValue("AS")), was = this.wbPathSig;
        this.wbPathSig = p;
        if (!p) return;
        if (!as) { this.setFieldValue(varName(p), "AS"); return; }
        if (was === undefined || was === p || !was || as !== varName(was)) return;
        const used = this.workspace.getAllBlocks(false).some((b) => b !== this && usesOf(b).includes(as));
        if (!used) this.setFieldValue(varName(p), "AS");
      });
    });
    // a group heading's title as the server keeps it: one line, GROUP_TITLE_MAX characters at most
    Blockly.Extensions.register("wb_group", function () {
      this.getField("TITLE").setValidator((v) => String(v ?? "").replace(/\s+/g, " ").slice(0, GROUP_TITLE_MAX));
    });
    Blockly.Extensions.register("wb_kind", function () { this.setOnChange(function () { syncKind(this); checkWritable(this); }); });
    Blockly.registry.register(Blockly.registry.Type.CONNECTION_CHECKER, "wb_write", WriteChecker, true);
    const colours = [["%{BKY_WB_C_AUTO}", "auto"], ["%{BKY_WB_C_BLACK}", "#1f2a37"], ["%{BKY_WB_C_BLUE}", "#2a78d6"],
      ["%{BKY_WB_C_RED}", "#d03b3b"], ["%{BKY_WB_C_ORANGE}", "#eb6834"], ["%{BKY_WB_C_GREEN}", "#1d9a6c"],
      ["%{BKY_WB_C_PURPLE}", "#8b5cf6"], ["%{BKY_WB_C_GRAY}", "#8a94a3"]];
    const rec = { message2: "%{BKY_WB_RECORD} %1", args2: [{ type: "wb_suggest", name: "REC", text: "%{BKY_WB_REC_ALL}", mode: "list" }], extensions: ["wb_rec"] };
    Blockly.common.defineBlocksWithJsonArray([
      { type: "wb_start", message0: "%{BKY_WB_START}", nextStatement: null, style: "hat_blocks", tooltip: "%{BKY_WB_START_TIP}" },
      { type: "wb_run", message0: "%{BKY_WB_RUN}", args0: [{ type: "field_checkbox", name: "REINIT", checked: false }],
        previousStatement: null, nextStatement: null, colour: COLOUR.action, tooltip: "%{BKY_WB_RUN_TIP}" },
      { type: "wb_read", message0: "%{BKY_WB_READ}", inputsInline: true,
        args0: [{ type: "input_value", name: "PATH", check: "Path" }, { type: "wb_suggest", name: "AS", text: "", mode: "name", ph: "WB_READ_AUTO" }],
        previousStatement: null, nextStatement: null, colour: COLOUR.action, tooltip: "%{BKY_WB_READ_TIP}", extensions: ["wb_readname"] },
      { type: "wb_log", message0: "%{BKY_WB_LOG}", args0: [{ type: "wb_suggest", name: "TEXT", text: "", mode: "brace", ph: "WB_LOG_PH" }],
        previousStatement: null, nextStatement: null, colour: COLOUR.action, tooltip: "%{BKY_WB_LOG_TIP}" },
      { type: "wb_save", message0: "%{BKY_WB_SAVE}", args0: [{ type: "field_input", name: "PATH", text: "" }],
        previousStatement: null, nextStatement: null, colour: COLOUR.action, tooltip: "%{BKY_WB_SAVE_TIP}" },
      { type: "wb_if", message0: "%{BKY_WB_IF}", inputsInline: true,
        args0: [{ type: "input_value", name: "LEFT", check: ["Path", "Var"] },
                { type: "field_dropdown", name: "OP", options: [[">", ">"], ["≥", ">="], ["<", "<"], ["≤", "<="], ["=", "=="], ["≠", "!="]] },
                { type: "wb_suggest", name: "RIGHT", text: "0", mode: "expr" }],
        message1: "%{BKY_WB_THEN}", args1: [{ type: "input_statement", name: "THEN" }],
        message2: "%{BKY_WB_ELSE}", args2: [{ type: "input_statement", name: "ELSE" }],
        previousStatement: null, nextStatement: null, colour: COLOUR.control, extensions: ["wb_ifright"] },
      Object.assign({ type: "wb_repeat", message0: "%{BKY_WB_REPEAT}", args0: [{ type: "field_number", name: "TIMES", value: 3, min: 1, precision: 1 }],
        message1: "%1", args1: [{ type: "input_statement", name: "BODY" }],
        previousStatement: null, nextStatement: null, colour: COLOUR.control }, rec),
      Object.assign({ type: "wb_until", message0: "%{BKY_WB_UNTIL}", inputsInline: true,
        args0: [{ type: "wb_suggest", name: "COND", text: "", mode: "expr", ph: "WB_UNTIL_PH" },
                { type: "field_number", name: "MAX", value: 50, min: 1, precision: 1 }],
        message1: "%1", args1: [{ type: "input_statement", name: "BODY" }],
        previousStatement: null, nextStatement: null, colour: COLOUR.control, tooltip: "%{BKY_WB_UNTIL_TIP}" }, rec),
      { type: "wb_optimize", message0: "%{BKY_WB_OPT}",
        args0: [{ type: "field_dropdown", name: "ALG", options: ALGS },
                { type: "field_number", name: "BUDGET", value: 100, min: 2, precision: 1 }],
        message1: "%{BKY_WB_OPT_VARS}", args1: [{ type: "input_statement", name: "VARS", check: "OptVar" }],
        message2: "%{BKY_WB_OPT_OBJS}", args2: [{ type: "input_statement", name: "OBJS", check: "OptObj" }],
        message3: "%{BKY_WB_OPT_CONS}", args3: [{ type: "input_statement", name: "CONS", check: "OptCon" }],
        previousStatement: null, nextStatement: null, colour: COLOUR.opt, tooltip: "%{BKY_WB_OPT_TIP}", extensions: ["wb_finish"] },
      { type: "wb_optvar", message0: "%{BKY_WB_OPTVAR}", inputsInline: true,
        args0: [{ type: "input_value", name: "PATH", check: "Path" }, { type: "field_number", name: "LO", value: 0 },
                { type: "field_number", name: "HI", value: 1 }],
        previousStatement: "OptVar", nextStatement: "OptVar", colour: COLOUR.opt },
      { type: "wb_optobj", message0: "%1 %2", inputsInline: true,
        args0: [{ type: "field_dropdown", name: "DIR", options: [["%{BKY_WB_MIN}", "minimize"], ["%{BKY_WB_MAX}", "maximize"]] },
                { type: "input_value", name: "PATH", check: ["Path", "Var"] }],
        previousStatement: "OptObj", nextStatement: "OptObj", colour: COLOUR.opt, tooltip: "%{BKY_WB_OPTGOAL_TIP}" },
      { type: "wb_optcon", message0: "%1 %2 %3", inputsInline: true, tooltip: "%{BKY_WB_OPTGOAL_TIP}",
        args0: [{ type: "input_value", name: "PATH", check: ["Path", "Var"] },
                { type: "field_dropdown", name: "OP", options: [["≥", "lower"], ["≤", "upper"]] },
                { type: "field_number", name: "VAL", value: 0 }],
        previousStatement: "OptCon", nextStatement: "OptCon", colour: COLOUR.opt },
      { type: "wb_optobjx", message0: "%1 %2", inputsInline: true, tooltip: "%{BKY_WB_OPTX_TIP}",
        args0: [{ type: "field_dropdown", name: "DIR", options: [["%{BKY_WB_MIN}", "minimize"], ["%{BKY_WB_MAX}", "maximize"]] },
                { type: "wb_suggest", name: "EXPR", text: "a + b", mode: "expr" }],
        message1: "%{BKY_WB_OPT_WHERE}", args1: [{ type: "input_statement", name: "TERMS", check: "OptTerm" }],
        previousStatement: "OptObj", nextStatement: "OptObj", colour: COLOUR.opt },
      { type: "wb_optconx", message0: "%1 %2 %3", inputsInline: true, tooltip: "%{BKY_WB_OPTX_TIP}",
        args0: [{ type: "wb_suggest", name: "EXPR", text: "a + b", mode: "expr" },
                { type: "field_dropdown", name: "OP", options: [["≥", "lower"], ["≤", "upper"]] },
                { type: "field_number", name: "VAL", value: 0 }],
        message1: "%{BKY_WB_OPT_WHERE}", args1: [{ type: "input_statement", name: "TERMS", check: "OptTerm" }],
        previousStatement: "OptCon", nextStatement: "OptCon", colour: COLOUR.opt },
      // two rows (ΔTmin, then the two choices), so the block fits a flyout beside the list
      { type: "wb_pinch", message0: "%{BKY_WB_PINCH}", tooltip: "%{BKY_WB_PINCH_TIP}",
        args0: [{ type: "field_number", name: "DTMIN", value: 10, min: 0.1 }],
        message1: "%{BKY_WB_PINCH_OPTS}",
        args1: [{ type: "field_checkbox", name: "AUTO", checked: true }, { type: "field_checkbox", name: "MATCH", checked: true }],
        message2: "%{BKY_WB_PINCH_EXCL}", args2: [{ type: "field_input", name: "EXCL", text: "" }],
        message3: "%{BKY_WB_PINCH_MORE}", args3: [{ type: "input_statement", name: "STREAMS", check: "PStream" }],
        previousStatement: null, nextStatement: null, colour: COLOUR.pinch, extensions: ["wb_pinchexcl"] },
      { type: "wb_pstream", message0: "%{BKY_WB_PSTREAM}", inputsInline: true, tooltip: "%{BKY_WB_PSTREAM_TIP}",
        args0: [{ type: "field_input", name: "NAME", text: "S1" },
                { type: "input_value", name: "TIN", check: ["Path", "Var"] },
                { type: "input_value", name: "TOUT", check: ["Path", "Var"] },
                { type: "input_value", name: "DUTY", check: ["Path", "Var"] }],
        previousStatement: "PStream", nextStatement: "PStream", colour: COLOUR.pinch },
      { type: "wb_optterm", message0: "%1 = %2", inputsInline: true,
        args0: [{ type: "field_input", name: "NAME", text: "a" }, { type: "input_value", name: "PATH", check: "Path" }],
        previousStatement: "OptTerm", nextStatement: "OptTerm", colour: COLOUR.opt },
      { type: "wb_path", message0: "%{BKY_WB_PATH}", args0: [{ type: "field_input", name: "RAW", text: "\\Data\\" }],
        output: "Path", colour: COLOUR.path, tooltip: "%{BKY_WB_PATH_TIP}", extensions: ["wb_kind"] },
      { type: "wb_var", message0: "%{BKY_WB_VAR}", args0: [{ type: "wb_suggest", name: "NAME", text: "", mode: "name", ph: "WB_VAR_PH" }],
        output: "Var", colour: COLOUR.variable },
      { type: "wb_calc", message0: "%{BKY_WB_CALC}", inputsInline: true,
        args0: [{ type: "field_input", name: "AS", text: "y" }, { type: "wb_suggest", name: "EXPR", text: "", mode: "expr", ph: "WB_EXPR_PH" },
                { type: "field_input", name: "UNIT", text: "" }],
        previousStatement: null, nextStatement: null, colour: COLOUR.calc, tooltip: "%{BKY_WB_CALC_TIP}" },
      { type: "wb_def", message0: "%{BKY_WB_DEF}", inputsInline: true,
        args0: [{ type: "field_input", name: "NAME", text: "f" }, { type: "field_input", name: "PARAMS", text: "x, y" },
                { type: "field_input", name: "EXPR", text: "x * y / 2" }],
        previousStatement: null, nextStatement: null, colour: COLOUR.calc, tooltip: "%{BKY_WB_DEF_TIP}" },
      { type: "wb_expr", message0: "%{BKY_WB_EXPR}", args0: [{ type: "wb_suggest", name: "EXPR", text: "", mode: "expr", ph: "WB_EXPR_PH" }],
        output: "Var", colour: COLOUR.calc, tooltip: "%{BKY_WB_EXPR_TIP}" },
      { type: "wb_pline", message0: "%{BKY_WB_PLINE}", inputsInline: true,
        args0: [{ type: "field_input", name: "LABEL", text: "%{BKY_WB_LINE_NAME}" }, { type: "wb_suggest", name: "EXPR", text: "x", mode: "expr" },
                { type: "field_input", name: "FROM", text: "" }, { type: "field_input", name: "TO", text: "" },
                { type: "field_dropdown", name: "COLOR", options: colours }, { type: "field_checkbox", name: "DASH", checked: false }],
        previousStatement: "PlotLine", nextStatement: "PlotLine", colour: COLOUR.table, tooltip: "%{BKY_WB_PLINE_TIP}" },
      { type: "wb_pvline", message0: "%{BKY_WB_PVLINE}", inputsInline: true,
        args0: [{ type: "field_input", name: "LABEL", text: "x = 1" }, { type: "field_input", name: "X", text: "1" },
                { type: "field_dropdown", name: "COLOR", options: colours }, { type: "field_checkbox", name: "DASH", checked: false }],
        previousStatement: "PlotLine", nextStatement: "PlotLine", colour: COLOUR.table, tooltip: "%{BKY_WB_PVLINE_TIP}" },
      // a step of a kind this page does not know (a newer server's): kept whole in its data, runs as written
      { type: "wb_other", message0: "%{BKY_WB_OTHER}", args0: [{ type: "field_label_serializable", name: "KIND", text: "?" }],
        previousStatement: null, nextStatement: null, colour: COLOUR.other, tooltip: "%{BKY_WB_OTHER_TIP}" },
      // feature "groups": a group heading, flat, no body -- the top-level steps
      // under it up to the next heading are its group (tools/wb_plan.groups); its title one line
      { type: "wb_group", message0: "%{BKY_WB_GROUP}", args0: [{ type: "field_input", name: "TITLE", text: "" }],
        previousStatement: null, nextStatement: null, colour: COLOUR.group, tooltip: "%{BKY_WB_GROUP_TIP}", extensions: ["wb_group"] },
    ]);

    // the flowsheet's own changes ("flowsheet changes" above): one row each, its kind menu
    // (where it has more than one form) showing that form's fields
    const struct = (block) => {
      block.setPreviousStatement(true);
      block.setNextStatement(true);
      block.setColour(COLOUR.struct);
      block.setTooltip(() => structTip(block));
      block.setOnChange(function () { checkStruct(this); });
      const k = block.getField("KIND");
      if (k) onKind.call(k, k.getValue());               // (the kind's fields, before any value is loaded)
    };
    Blockly.Blocks.wb_place = {
      init() {
        this.wbAuto = freeName("B", this.workspace);
        this.appendDummyInput()
          .appendField(msg("WB_PLACE"))
          .appendField(kindField(() => [[msg("WB_K_BLOCK"), "block"], [msg("WB_K_STREAM"), "stream"]]), "KIND")
          .appendField(msg("WB_PLACE_NAME"))
          .appendField(new Blockly.FieldTextInput(this.wbAuto, nameCheck), "NAME")
          .appendField(msg("WB_PLACE_TYPE"))
          .appendField(new TypeDropdown(typeOpts), "BTYPE")
          .appendField(new Blockly.FieldDropdown(stypeOpts), "STYPE");
        const bt = this.getField("BTYPE"), types = bt.getOptions(false).filter((o) => Array.isArray(o) && !o[1].startsWith(TAB));
        const first = types.find((o) => o[1] === "HeatX") || types[0];
        if (first) bt.setValue(first[1]);
        struct(this);
      },
    };
    Blockly.Blocks.wb_connect = {
      init() {
        this.appendDummyInput()
          .appendField(msg("WB_CONNECT"))
          .appendField(new Blockly.FieldDropdown(sStreamOpts), "S")
          .appendField(msg("WB_CONNECT_TO"))
          .appendField(pickField(sBlockOpts, "B"), "B")
          .appendField(msg("WB_CONNECT_OF"))
          .appendField(new MenuDropdown(portOpts), "PORT");
        struct(this);
        fixPort(this);
      },
    };
    // (a disconnect names four things: two rows, the stream, then where it comes off; BR, the
    // row's end, shows for that form only)
    Blockly.Blocks.wb_remove = {
      init() {
        this.appendDummyInput()
          .appendField(msg("WB_REMOVE"))
          .appendField(kindField(() => [[msg("WB_K_BLOCK"), "block"], [msg("WB_K_STREAM"), "stream"], [msg("WB_K_CONN"), "conn"]]), "KIND")
          .appendField(msg("WB_RM_S"), "LS")
          .appendField(pickField(sStreamOpts, "S"), "S");
        this.appendEndRowInput("BR");
        this.appendDummyInput()
          .appendField(msg("WB_RM_FROM"), "LFROM")
          .appendField(pickField(sBlockOpts, "B"), "B")
          .appendField(msg("WB_RM_OF"), "LOF")
          .appendField(new MenuDropdown(portOpts), "PORT");
        this.setInputsInline(true);
        struct(this);
      },
    };
    Blockly.Blocks.wb_component = {
      init() {
        this.appendDummyInput()
          .appendField(kindField(() => [[msg("WB_COMP_ADD"), "add"], [msg("WB_COMP_REMOVE"), "remove"]]), "KIND")
          .appendField(msg("WB_COMP"))
          .appendField(new Blockly.FieldTextInput("WATER", nameCheck), "ADD")
          .appendField(new Blockly.FieldDropdown(sCompOpts), "REM");
        struct(this);
      },
    };
    Blockly.Blocks.wb_method = {
      init() {
        this.appendDummyInput().appendField(msg("WB_METHOD")).appendField(new Blockly.FieldDropdown(methodOpts), "METHOD");
        struct(this);
      },
    };

    // two rows, as the sweep: what is adjusted, then its bounds (in their unit) and the target
    Blockly.Blocks.wb_seek = {
      init() {
        this.appendValueInput("PATH").setCheck("Path").appendField(msg("WB_SEEK"));
        this.appendEndRowInput("ROW1");
        this.appendDummyInput("RANGE")
          .appendField(msg("WB_SEEK_FROM"))
          .appendField(new Blockly.FieldNumber(0), "LO")
          .appendField(msg("WB_SEEK_TO"))
          .appendField(new Blockly.FieldNumber(1), "HI")
          .appendField(new Blockly.FieldDropdown(unitOpts), "UNIT")
          .appendField(msg("WB_SEEK_UNTIL"))
          .appendField(new SuggestField("", "expr", "WB_SEEK_PH"), "MEASURE")
          .appendField("=")
          .appendField(new Blockly.FieldNumber(0), "TARGET");
        this.appendStatementInput("BODY");
        recordRow(this);
        finishRow(this);
        this.setInputsInline(true);
        this.setPreviousStatement(true);
        this.setNextStatement(true);
        this.setColour(COLOUR.control);
        this.setTooltip(msg("WB_SEEK_TIP"));
        this.setOnChange(function () {
          syncUnit(this);
          checkLoopRead(this);
          // its measure, while empty: the first variable its body reads
          const first = !this.isInFlyout && !text(this.getFieldValue("MEASURE")) && bodySets(this).find((v) => v.path);
          if (first) this.setFieldValue(first.name, "MEASURE");
        });
      },
    };

    Blockly.Blocks.wb_set = {
      init() {
        this.appendValueInput("PATH").setCheck("Path").appendField(msg("WB_SET"));
        this.appendDummyInput()
          .appendField(msg("WB_SET_TO"))
          .appendField(new Blockly.FieldTextInput("0"), "VALUE")
          .appendField(new Blockly.FieldDropdown(unitOpts), "UNIT");
        this.setInputsInline(true);
        this.setPreviousStatement(true);
        this.setNextStatement(true);
        this.setColour(COLOUR.action);
        this.setTooltip(msg("WB_SET_TIP"));
        this.setOnChange(function () { syncUnit(this); });
      },
    };
    // two rows: what is swept, then the range in its unit and the points, so a long path does
    // not push the range past the edge of a flyout or a column (the fields keep their names)
    Blockly.Blocks.wb_sweep = {
      init() {
        this.appendValueInput("PATH").setCheck("Path").appendField(msg("WB_SWEEP"));
        this.appendEndRowInput("ROW1");
        this.appendDummyInput("RANGE")
          .appendField(msg("WB_SWEEP_FROM"))
          .appendField(new Blockly.FieldNumber(0), "FROM")
          .appendField(msg("WB_SWEEP_TO"))
          .appendField(new Blockly.FieldNumber(1), "TO")
          .appendField(new Blockly.FieldDropdown(unitOpts), "UNIT")
          .appendField(msg("WB_SWEEP_IN"))
          .appendField(new Blockly.FieldNumber(5, 1, undefined, 1), "STEPS")
          .appendField(msg("WB_SWEEP_PTS"));
        this.appendStatementInput("BODY");
        recordRow(this);
        finishRow(this);
        this.setInputsInline(true);
        this.setPreviousStatement(true);
        this.setNextStatement(true);
        this.setColour(COLOUR.control);
        this.setTooltip(msg("WB_SWEEP_TIP"));
        this.setOnChange(function () { syncUnit(this); checkLoopRead(this); });
      },
    };
    Blockly.Blocks.wb_stream = {
      init() {
        this.appendDummyInput()
          .appendField(msg("WB_STREAM"))
          .appendField(new MenuDropdown(streamOpts), "S")
          .appendField(msg("WB_STREAM_OF"))
          .appendField(new MenuDropdown(propOpts), "P")
          .appendField(new MenuDropdown(compOpts), "C");
        this.setOutput(true, "Path");
        this.setColour(COLOUR.path);
        this.setTooltip(msg("WB_STREAM_TIP"));
        this.setOnChange(function () { syncStream(this); syncKind(this); checkWritable(this); });
      },
    };
    Blockly.Blocks.wb_block = {
      init() {
        const self = this;
        this.appendDummyInput()
          .appendField(msg("WB_BLOCK"))
          .appendField(new MenuDropdown(blockOpts, function (v) {
            setTimeout(() => {
              const pf = self.getField("P");
              if (!pf) return;
              const opts = pf.getOptions(false);
              if (!opts.some((o) => o[1] === pf.getValue())) pf.setValue(opts[0][1]);
            });
            return v;
          }), "B")
          .appendField(msg("WB_BLOCK_OF"))
          .appendField(new MenuDropdown(function () { return paramOpts(this); }), "P");
        // the part's menu was first built before the field had its block, so from the parts a
        // program named (their paths as labels): the first part of this unit's type, labelled as
        // the type names it (a saved program's part is set after this)
        const pf = this.getField("P"), opts = pf.getOptions(false);
        if (!opts.some((o) => o[1] === pf.getValue())) pf.setValue(opts[0][1]);
        else if (pf.doValueUpdate_) pf.doValueUpdate_(pf.getValue());
        this.setOutput(true, "Path");
        this.setColour(COLOUR.path);
        this.setTooltip(msg("WB_BLOCK_TIP"));
        this.setOnChange(function () { syncKind(this); checkWritable(this); });
      },
    };
    Blockly.Blocks.wb_tcol = {
      init() {
        this.appendValueInput("VAL").setCheck(["Path", "Var"])
          .appendField(msg("WB_TCOL"))
          .appendField(new Blockly.FieldTextInput(msg("WB_TCOL_NAME")), "LABEL")
          .appendField("=");
        this.appendDummyInput("UNITROW").appendField(msg("WB_TCOL_UNIT"), "UNITLBL").appendField(new Blockly.FieldTextInput(""), "UNIT");
        this.setInputsInline(true);
        this.setPreviousStatement(true, "TableCol");
        this.setNextStatement(true, "TableCol");
        this.setColour(COLOUR.table);
        this.setTooltip(msg("WB_TCOL_TIP"));
        this.setOnChange(function () { syncTcol(this); });
      },
    };
    // a chart in rows: its title; the x axis (its range empty: fitted to the data); the y axis,
    // its range shown only once set (the block's menu adds it); then its lines
    Blockly.Blocks.wb_plot = {
      init() {
        const ph = (v, key) => new PhField(v, key);
        this.appendDummyInput().appendField(msg("WB_PLOT_T")).appendField(new Blockly.FieldTextInput(msg("WB_PLOT_NAME")), "TITLE");
        this.appendDummyInput("XROW").appendField(msg("WB_PLOT_X")).appendField(ph("", "WB_PLOT_XPH"), "XLABEL")
          .appendField(msg("WB_PLOT_RANGE")).appendField(ph("", "WB_PLOT_AUTO"), "XFROM").appendField("–").appendField(ph("", "WB_PLOT_AUTO"), "XTO");
        this.appendDummyInput("YROW").appendField(msg("WB_PLOT_Y")).appendField(ph("", "WB_PLOT_YPH"), "YLABEL")
          .appendField(msg("WB_PLOT_RANGE"), "YRL").appendField(ph("", "WB_PLOT_AUTO"), "YFROM").appendField("–", "YDASH").appendField(ph("", "WB_PLOT_AUTO"), "YTO");
        this.appendStatementInput("SERIES").setCheck("PlotLine");
        this.getField("XFROM").setTooltip(msg("WB_PLOT_RANGE_TIP"));
        this.getField("XTO").setTooltip(msg("WB_PLOT_RANGE_TIP"));
        this.setPreviousStatement(true);
        this.setNextStatement(true);
        this.setColour(COLOUR.table);
        this.setTooltip(msg("WB_PLOT_TIP"));
        syncPlot(this);
        this.setOnChange(function () { syncPlot(this); });
      },
    };
    // a line of a loop's results: which loop, its y column(s), then its x and how it is drawn
    Blockly.Blocks.wb_pdata = {
      init() {
        this.appendDummyInput()
          .appendField(msg("WB_PDATA"))
          .appendField(new ListField(loopOpts, { empty: "WB_LOOP_NONE", gone: "WB_LOOP_GONE" }), "LOOP")
          .appendField(msg("WB_PDATA_Y"))
          .appendField(new ListField(colOpts, { multi: true, empty: "WB_PDATA_YPICK", none: "WB_PDATA_YNONE", fill: true }), "Y");
        this.appendEndRowInput("BR");
        this.appendDummyInput()
          .appendField(msg("WB_PDATA_X"))
          .appendField(new ListField(xOpts, { names: true }), "X")
          .appendField(msg("WB_PDATA_LABEL"))
          .appendField(new PhField("", "WB_PDATA_LABELPH"), "LABEL")
          .appendField(new Blockly.FieldDropdown(colours.map(([t, v]) => [t.replace(/^%\{BKY_(\w+)\}$/, (m, k) => msg(k)), v])), "COLOR")
          .appendField(msg("WB_DASHED"))
          .appendField(new Blockly.FieldCheckbox(false), "DASH");
        this.setInputsInline(true);
        this.setPreviousStatement(true, "PlotLine");
        this.setNextStatement(true, "PlotLine");
        this.setColour(COLOUR.table);
        this.setTooltip(msg("WB_PDATA_TIP"));
        fillLoop(this);
        this.setOnChange(function () { fillLoop(this); checkLoopPick(this); });
      },
    };
    // a table: its rows ticked from the flowsheet's streams and blocks, a column per property below
    Blockly.Blocks.wb_table = {
      init() {
        this.appendDummyInput()
          .appendField(msg("WB_TABLE_T"))
          .appendField(new Blockly.FieldTextInput(msg("WB_TABLE_NAME")), "TITLE")
          .appendField(msg("WB_TABLE_ROWS"))
          .appendField(new ListField(rowOpts, { multi: true, empty: "WB_TABLE_ROWPICK" }), "ROWS");
        this.appendStatementInput("COLS").setCheck("TableCol");
        this.setPreviousStatement(true);
        this.setNextStatement(true);
        this.setColour(COLOUR.table);
        this.setTooltip(msg("WB_TABLE_TIP"));
        this.setOnChange(function () { checkTable(this); });
      },
    };
    // a column of such a table: a property, the row implied (its component, for a property that has one)
    Blockly.Blocks.wb_tprop = {
      init() {
        this.appendDummyInput()
          .appendField(msg("WB_TPROP"))
          .appendField(new ListField(tpropOpts, { word: tpropWord, value: "s:" + STREAM_T }), "P")
          .appendField(new MenuDropdown(compOpts), "C");
        this.setPreviousStatement(true, "TableCol");
        this.setNextStatement(true, "TableCol");
        this.setColour(COLOUR.table);
        this.setTooltip(msg("WB_TPROP_TIP"));
        syncTprop(this);
        this.setOnChange(function () { syncTprop(this); });
      },
    };
    // a loop's results as a table: which loop, which of its variables (none ticked: all)
    Blockly.Blocks.wb_ltable = {
      init() {
        this.appendDummyInput()
          .appendField(msg("WB_LTABLE"))
          .appendField(new Blockly.FieldTextInput(msg("WB_TABLE_NAME")), "TITLE")
          .appendField(msg("WB_LTABLE_FROM"))
          .appendField(new ListField(loopOpts, { empty: "WB_LOOP_NONE", gone: "WB_LOOP_GONE" }), "LOOP");
        this.appendEndRowInput("BR");
        this.appendDummyInput()
          .appendField(msg("WB_LTABLE_VARS"))
          .appendField(new ListField(colOpts, { multi: true, empty: "WB_LTABLE_ALL", none: "WB_PDATA_YNONE" }), "VARS");
        this.setInputsInline(true);
        this.setPreviousStatement(true);
        this.setNextStatement(true);
        this.setColour(COLOUR.table);
        this.setTooltip(msg("WB_LTABLE_TIP"));
        fillLoop(this);
        this.setOnChange(function () { fillLoop(this); checkLoopPick(this); });
      },
    };
    Blockly.Blocks.wb_proc = {
      init() {
        this.appendDummyInput()
          .appendField(msg("WB_PROC"))
          .appendField(new Blockly.FieldTextInput("my_steps"), "NAME")
          .appendField("(")
          .appendField(new Blockly.FieldTextInput(""), "PARAMS")
          .appendField(")");
        this.setNextStatement(true);
        this.setStyle("proc_blocks");
        this.setTooltip(msg("WB_PROC_TIP"));
        this.setOnChange(function (e) {                   // a renamed procedure takes its calls along
          if (this.isInFlyout || e.type !== Blockly.Events.BLOCK_CHANGE || e.blockId !== this.id || e.name !== "NAME") return;
          if (!e.oldValue || e.oldValue === e.newValue) return;
          this.workspace.getAllBlocks(false).filter((b) => b.type === "wb_call" && b.getFieldValue("NAME") === e.oldValue)
            .forEach((b) => { const f = b.getField("NAME"); f.getOptions(false); f.setValue(e.newValue); });
        });
      },
    };
    Blockly.Blocks.wb_call = {
      init() {
        this.appendDummyInput()
          .appendField(msg("WB_CALL"))
          .appendField(new Blockly.FieldDropdown(procOpts), "NAME")
          .appendField(msg("WB_CALL_WITH"), "WITH")
          .appendField(new Blockly.FieldTextInput(""), "ARGS");
        this.setPreviousStatement(true);
        this.setNextStatement(true);
        this.setColour(COLOUR.proc);
        this.setTooltip(msg("WB_CALL_TIP"));
        this.setOnChange(function () { syncCall(this); });
      },
    };
    // the manual step: "Manual step: set [input]", then its hint; the check and the
    // answer rows only when they hold something (YT_STATE)
    Blockly.Blocks.wb_yourturn = {
      init() {
        this.appendValueInput("PATH").setCheck("Path").appendField(ui("yt_blk_set"));
        this.appendEndRowInput("YTBR1");
        this.appendDummyInput("HINTROW").appendField(ui("yt_blk_hint")).appendField(new YtField(ui("yt_blk_hint_def"), "yt_blk_hint_ph", null), "HINT");
        this.setInputsInline(true);
        this.setPreviousStatement(true);
        this.setNextStatement(true);
        this.setColour(COLOUR.action);
        this.setTooltip(() => ui("tip_yt"));
        this.setOnChange(function () { checkTurn(this); });
      },
    };
    dressSteps();
    Object.assign(Blockly.Blocks.wb_yourturn, YT_STATE);   // (its note's state and its own rows)
    turnMenu(Blockly.ContextMenuRegistry && Blockly.ContextMenuRegistry.registry, Blockly.ContextMenuRegistry.ScopeType.BLOCK);
    plotMenu(Blockly.ContextMenuRegistry && Blockly.ContextMenuRegistry.registry, Blockly.ContextMenuRegistry.ScopeType.BLOCK);
  }
  /** A chart's menu: Set y range (its fields shown, the first opened) or Remove y range. */
  function plotMenu(reg, BLOCK) {
    if (!reg || reg.getItem("wb_plot_yr")) return;
    const may = (b) => !!b && b.type === "wb_plot" && !b.isInFlyout && !b.isInsertionMarker() && b.isEditable();
    const has = (b) => !!(text(b.getFieldValue("YFROM")) || text(b.getFieldValue("YTO")) || b.wbYOpen);
    reg.register({ id: "wb_plot_yr", scopeType: BLOCK, weight: 5,
      displayText: (scope) => msg(scope.block && has(scope.block) ? "WB_PLOT_YR_RM" : "WB_PLOT_YR_ADD"),
      preconditionFn: (scope) => (may(scope.block) ? "enabled" : "hidden"),
      callback: (scope) => {
        const b = scope.block;
        if (has(b)) {
          b.wbYOpen = false;
          grouped(() => { b.setFieldValue("", "YFROM"); b.setFieldValue("", "YTO"); });
          syncPlot(b);
          return;
        }
        b.wbYOpen = true;
        syncPlot(b);
        const after = Blockly.renderManagement && Blockly.renderManagement.finishQueuedRenders ? Blockly.renderManagement.finishQueuedRenders() : Promise.resolve();
        after.then(() => { if (!b.isDeadOrDying()) b.getField("YFROM").showEditor(); });
      } });
  }

  // A result can be read but not set. Result blocks look different (slate, not purple), a
  // user cannot drop one into a slot that writes (WriteChecker), the menus there list inputs
  // only, and one that arrives anyway (an AI's program, a paste) carries a warning.
  const WRITE_SLOT = { wb_set: "PATH", wb_sweep: "PATH", wb_seek: "PATH", wb_optvar: "PATH", wb_yourturn: "PATH" };
  function isResult(block) {
    if (block.type === "wb_stream") {
      const sp = streamProp(block.getFieldValue("P"));
      return !!(sp && !sp.input);
    }
    if (block.type === "wb_block") return String(block.getFieldValue("P") || "").startsWith("Output");
    if (block.type === "wb_path") return /\\Output\\/i.test(String(block.getFieldValue("RAW") || ""));
    return false;
  }
  function inWriteSlot(block) {
    const parent = block.getParent && block.getParent();
    const slot = parent && WRITE_SLOT[parent.type];
    return !!slot && parent.getInputTargetBlock(slot) === block;
  }
  /** Inputs purple, results slate: the colour says what can be set. */
  function syncKind(block) {
    const want = (isResult(block) ? COLOUR.result : COLOUR.path).toLowerCase();
    if (String(block.getColour()).toLowerCase() !== want) block.setColour(want);
  }

  /** Refuses a result dropped on a slot that writes -- while the user drags (Blockly's drag
   *  checks, asked only of the connections a drag could make). Loading a program, pasting
   *  and undo never refuse (they would fail half-way); the warning and the server's check
   *  before a run catch those. Nor does a block taken from the flyout, which Blockly builds
   *  mid-drag and connects before its fields are set (a stream holding its first property,
   *  a result, would be refused and the block come out broken). */
  class WriteChecker extends Blockly.ConnectionChecker {
    doDragChecks(a, b, distance) {
      if (!super.doDragChecks(a, b, distance)) return false;
      // a flowsheet change never goes into a loop: a stack holding one dropped into a loop's
      // body, or a loop dragged around a stack holding one (the stack goes where the NEXT side is)
      const NEXT = Blockly.ConnectionType.NEXT_STATEMENT, PREV = Blockly.ConnectionType.PREVIOUS_STATEMENT;
      const pair = a.type === NEXT && b.type === PREV ? [a, b] : a.type === PREV && b.type === NEXT ? [b, a] : null;
      if (pair && hasStruct(pair[1].getSourceBlock()) && loopAt(pair[0])) {
        if (WB.onRefuse) WB.onRefuse("struct");
        return false;
      }
      const VALUE = Blockly.ConnectionType.INPUT_VALUE;
      const inp = a.type === VALUE ? a : b.type === VALUE ? b : null;
      if (!inp) return true;
      const parent = inp.getSourceBlock(), child = (inp === a ? b : a).getSourceBlock();
      const input = parent.inputList.find((i) => i.connection === inp);
      if (!input || WRITE_SLOT[parent.type] !== input.name || !isResult(child)) return true;
      if (WB.onRefuse) WB.onRefuse();
      return false;
    }
  }
  /** A long text shows shortened with "…" on its block (Blockly cuts at 50 characters),
   *  but its editor opens wide enough for the whole line, up to 80% of the window, and grows
   *  as one types. Blockly sizes the editor to the field (after a render) on opening and on
   *  every keystroke; this widens it right after, and keeps it inside the window. */
  let measure = null;
  function widenEditor() {
    const div = Blockly.WidgetDiv.getDiv(), input = div && div.querySelector("input.blocklyHtmlInput");
    if (!input || !div.firstChild) return;
    measure = measure || document.createElement("canvas").getContext("2d");
    const cs = getComputedStyle(input);
    measure.font = cs.font;
    const pad = parseFloat(cs.paddingLeft || 0) + parseFloat(cs.paddingRight || 0) + 18;
    const want = Math.min(measure.measureText(input.value || "").width + pad, window.innerWidth * 0.8);
    const r = div.getBoundingClientRect();
    if (want <= r.width + 1) return;
    div.style.width = `${want}px`;
    const over = r.left + want - (window.innerWidth - 8);
    if (over > 0) div.style.left = `${parseFloat(div.style.left || 0) - over}px`;
  }
  function patchTextEditor() {
    const base = Blockly.FieldTextInput.prototype.resizeEditor_;
    if (!base || base.wbWide) return;
    const wide = function () {
      base.call(this);
      // Blockly sizes the editor once queued renders finish: widen after that, and once more
      // a frame later in case its sizing landed last
      const after = Blockly.renderManagement && Blockly.renderManagement.finishQueuedRenders
        ? Blockly.renderManagement.finishQueuedRenders() : Promise.resolve();
      after.then(() => { widenEditor(); requestAnimationFrame(widenEditor); });
    };
    wide.wbWide = true;
    Blockly.FieldTextInput.prototype.resizeEditor_ = wide;
  }

  /** A dropdown that says when its menu is being built for the user to pick from. */
  class MenuDropdown extends Blockly.FieldDropdown {
    showEditor_(e) {
      WB.menuFor = this;
      try { return super.showEditor_(e); } finally { WB.menuFor = null; }
    }
  }
  /** The type menu: a palette tab's name is a heading (not a choice; Aspen's English in its tooltip). */
  class TypeDropdown extends Blockly.FieldDropdown {
    showEditor_(e) {
      super.showEditor_(e);
      (this.menu_ ? this.menu_.menuItems : []).forEach((it) => {
        const v = String(it.getValue ? it.getValue() : "");          // (a line has no value)
        if (!v.startsWith(TAB)) return;
        it.setEnabled(false);
        it.getElement().classList.add("wb-menu-tab");
        it.getElement().title = v.slice(1);
      });
    }
  }
  /** A dropdown that says when the user picked from it (onPick), as a load or an undo does not. */
  class PickDropdown extends MenuDropdown {
    onItemSelected_(menu, item) {
      grouped(() => { super.onItemSelected_(menu, item); if (this.onPick) this.onPick(); });   // (one undo step)
    }
  }
  function checkWritable(block) {
    if (!block.rendered || block.isInFlyout) return;
    const parent = block.getParent();
    const slot = parent && WRITE_SLOT[parent.type];
    const writes = !!slot && parent.getInputTargetBlock(slot) === block;
    const text = writes && isResult(block) ? msg("WB_RESULT_WARN") : null;
    if (block.wbWarn !== text) { block.wbWarn = text; block.setWarningText(text); }
  }

  function syncStream(block) {
    const sp = streamProp(block.getFieldValue("P"));
    visible(block, block.getField("C"), !!(sp && sp.comp));
  }
  /** A column's unit labels an expression; a path brings its own. */
  function syncTcol(block) {
    const v = block.getInputTargetBlock("VAL");
    const want = !v || v.type === "wb_expr" || v.type === "wb_var";
    visible(block, block.getField("UNITLBL"), want);
    visible(block, block.getField("UNIT"), want);
  }
  /** "with …" only when the procedure takes values (or some were typed already). */
  function syncCall(block) {
    const name = block.getFieldValue("NAME");
    let ws = block.workspace;
    if (ws && ws.isFlyout && ws.targetWorkspace) ws = ws.targetWorkspace;
    const proc = ws && ws.getTopBlocks(false).find((b) => b.type === "wb_proc" && b.getFieldValue("NAME") === name);
    const want = !!(proc && names(proc.getFieldValue("PARAMS")).length) || !!String(block.getFieldValue("ARGS") || "").trim();
    visible(block, block.getField("WITH"), want);
    visible(block, block.getField("ARGS"), want);
  }

  // ------------------------------------------------------------------ theme + toolbox
  function theme() {
    return Blockly.Theme.defineTheme("wb", {
      name: "wb",
      base: Blockly.Themes.Classic,
      blockStyles: {
        hat_blocks: { colourPrimary: COLOUR.event, colourSecondary: "#A36D00", colourTertiary: "#8A5C00", hat: "cap" },
        proc_blocks: { colourPrimary: COLOUR.proc, colourSecondary: "#E23264", colourTertiary: "#CC2453", hat: "cap" },
      },
      // the category list is a glass capsule inside a clear strip (style.css), so the grid shows
      // around it; the flyout is a frosted sheet, pale enough that the blocks under it do not
      // smear into colour
      componentStyles: { workspaceBackgroundColour: "#F5F7FB", toolboxBackgroundColour: "transparent",
        flyoutBackgroundColour: "#FAFBFD", flyoutOpacity: 0.84 },
      fontStyle: { family: '"Segoe UI Variable Text", "Segoe UI", "Microsoft JhengHei UI", sans-serif', weight: "600", size: 12 },
    });
  }
  const b = (type, extra) => Object.assign({ kind: "block", type }, extra || {});
  const label = (key) => ({ kind: "label", text: msg(key), "web-class": "wb-flabel" });
  /** "name = path" rows for an expression goal, as a toolbox block holds them. */
  const terms = (...names) => names.reduceRight((next, n) =>
    ({ block: Object.assign({ type: "wb_optterm", fields: { NAME: n } }, next ? { next } : {}) }), null);
  /** Table columns, one per stream property (catalog keys), as a toolbox block holds them. */
  const tprops = (...keys) => keys.reduceRight((next, k) =>
    ({ block: Object.assign({ type: "wb_tprop", fields: { P: "s:" + k } }, next ? { next } : {}) }), null);
  const withPath = (type, fields) => b(type, { inputs: { PATH: { block: { type: "wb_stream", fields } } } });
  // ready to use: a loop over a block's input that runs the simulation and reads a result each
  // pass, and an optimize step with a decision variable and an objective in it (the block's
  // menus open on the flowsheet's first block and its first input)
  const unitPath = () => ({ block: { type: "wb_block" } });
  const resultPath = () => ({ block: { type: "wb_stream", fields: { P: STREAM_T } } });
  const runRead = () => ({ block: { type: "wb_run", next: { block: { type: "wb_read", inputs: { PATH: resultPath() } } } } });
  // (the design spec's example: its "until" names the variable its read stores, x, the read's own)
  const filledLoop = (type) => b(type, Object.assign({},
    { inputs: { PATH: unitPath(), BODY: runRead() } }));
  const filledOpt = () => b("wb_optimize", { inputs: {
    VARS: { block: { type: "wb_optvar", inputs: { PATH: unitPath() } } },
    OBJS: { block: { type: "wb_optobj", inputs: { PATH: resultPath() } } } } });
  /** A category of the list. key names its icon (style.css, .wbi-<key>: a CSS mask on the
   *  row's icon span), its short label in a narrow list and its one-line description, the
   *  row's tooltip (i18n.js cs_<key>, cd_<key>; app-program.js, dressToolbox). */
  const cat = (key, name, colour, contents) => ({ kind: "category", name: msg(name), colour, contents,
    cssconfig: { icon: `blocklyToolboxCategoryIcon wbi wbi-${key}` } });
  // By task, most used first, in Aspen's terms (Sensitivity, Design Spec, Pinch): what a
  // newcomer wants to do, not how a program is built; the programmer's parts (conditions,
  // repeats, calculations, procedures, the start block) wait under Advanced. Each category
  // opens on the blocks one reaches for most, some already holding a stream, so a first
  // program needs only drags and dropdowns. Only the toolbox is arranged here: the blocks,
  // their fields and the program they make are the same wherever they sit.
  WB.toolbox = () => ({
    kind: "categoryToolbox",
    contents: [
      cat("run", "WB_CAT_RUN", COLOUR.action, [
        label("WB_L_SET"), withPath("wb_set", { P: STREAM_IN }),
        label("WB_L_RUN"), b("wb_run"),
        label("WB_L_READ"), withPath("wb_read", { P: STREAM_T }),
        label("WB_L_SAVE"), b("wb_save"),
        // the manual step, last
        { kind: "label", text: ui("yt_block"), "web-class": "wb-flabel" }, withPath("wb_yourturn", { P: STREAM_IN }),
      ]),
      cat("paths", "WB_CAT_PATHS", COLOUR.path, [
        label("WB_L_INPUTS"), b("wb_stream", { fields: { P: STREAM_IN } }), b("wb_block"),
        label("WB_L_RESULTS"), b("wb_stream", { fields: { P: STREAM_T } }),
        label("WB_L_PATH_RAW"), b("wb_path"),
      ]),
      cat("study", "WB_CAT_STUDY", COLOUR.control, [
        label("WB_L_SWEEP"), filledLoop("wb_sweep"), b("wb_sweep"),
        label("WB_L_SEEK"), filledLoop("wb_seek"), b("wb_seek"),
      ]),
      cat("opt", "WB_CAT_OPT", COLOUR.opt, [
        label("WB_L_OPT_READY"), filledOpt(),
        label("WB_L_OPT_PARTS"), b("wb_optimize"), b("wb_optvar"), b("wb_optobj"), b("wb_optcon"),
        label("WB_L_OPTX"), b("wb_optobjx", { inputs: { TERMS: terms("a", "b") } }),
        b("wb_optconx", { inputs: { TERMS: terms("a", "b") } }), b("wb_optterm"),
        label("WB_L_OPTVAR"), b("wb_optobj", { inputs: { PATH: { block: { type: "wb_var", fields: { NAME: "y" } } } } }),
        b("wb_optcon", { inputs: { PATH: { block: { type: "wb_var", fields: { NAME: "y" } } } } }),
      ]),
      cat("pinch", "WB_CAT_PINCH", COLOUR.pinch, [b("wb_pinch"), b("wb_pstream")]),
      // each form ready (a place step names a free B1 or S1)
      cat("struct", "WB_CAT_STRUCT", COLOUR.struct, [
        label("WB_L_PLACE"), b("wb_place"), b("wb_place", { fields: { KIND: "stream", STYPE: "MATERIAL" } }),
        label("WB_L_CONNECT"), b("wb_connect"),
        label("WB_L_REMOVE"), b("wb_remove"),
        label("WB_L_COMP"), b("wb_component"), b("wb_method"),
      ]),
      cat("table", "WB_CAT_TABLE", COLOUR.table, [
        // a table of streams' temperature, pressure and flow, ready but for its rows; a loop's results
        label("WB_L_TABLE"),
        b("wb_table", { inputs: { COLS: tprops(STREAM_T, STREAM_P, STREAM_F) } }), b("wb_tprop"),
        label("WB_L_LTABLE"), b("wb_ltable"),
        label("WB_L_PLOT"), b("wb_plot", { inputs: { SERIES: { block: { type: "wb_pdata" } } } }), b("wb_pdata"), b("wb_pline"), b("wb_pvline"),
        label("WB_L_LOG"), b("wb_log"),
        label("WB_L_SAVE_EACH"), b("wb_save", { fields: { PATH: "case_{i}.bkp" } }),
      ]),
      cat("adv", "WB_CAT_ADV", COLOUR.proc, [
        label("WB_L_ADV_FLOW"), b("wb_if"), b("wb_repeat"), b("wb_until"),
        label("WB_L_ADV_CALC"), b("wb_calc"), b("wb_def"), b("wb_expr"), b("wb_var"),
        label("WB_L_ADV_TABLE"), b("wb_tcol"),
        label("WB_L_PROCS"), b("wb_proc"), b("wb_call"),
        ...(groupsOn() ? [label("WB_L_GROUP"), b("wb_group")] : []),
        label("WB_L_MAIN"), b("wb_start"),
      ]),
    ],
  });

  // ------------------------------------------------------------------ workspace -> program
  function pathOf(blk) {
    if (!blk) return null;
    if (blk.type === "wb_stream") {
      const sp = streamProp(blk.getFieldValue("P"));
      if (!sp) return null;
      const c = blk.getFieldValue("C");
      return `\\Data\\Streams\\${blk.getFieldValue("S")}\\` + sp.path.replace("{C}", c === NONE ? "" : c);
    }
    if (blk.type === "wb_block") {
      const p = blk.getFieldValue("P");
      return p === NONE ? null : `\\Data\\Blocks\\${blk.getFieldValue("B")}\\${p}`;
    }
    if (blk.type === "wb_path") return blk.getFieldValue("RAW");
    return null;
  }
  WB.pathOf = pathOf;
  const numOrText = (v) => (v === "" || v === null || isNaN(Number(v)) ? v : Number(v));
  const text = (v) => String(v ?? "").trim();
  function extras(blk) {
    try { return blk.data ? JSON.parse(blk.data) : {}; } catch (e) { return {}; }
  }
  function chain(first, fn) {
    const out = [];
    for (let x = first; x; x = x.getNextBlock()) { const v = fn(x); if (v) out.push(v); }
    return out;
  }
  function unitOf(blk) {
    const u = blk.getFieldValue("UNIT");
    return u && u !== NONE ? { unit: u } : {};
  }
  /** A loop's record list: absent (all variables) for "all" (in either language, or "*") or nothing. */
  function recOf(blk) {
    const list = recNames(blk.getFieldValue("REC"));
    return list.length ? { record: list } : {};
  }
  const checked = (blk, name) => blk.getFieldValue(name) === "TRUE";
  /** A pinch stream's temperature or duty: a path, or an expression (as text either way). */
  function fieldOf(v) {
    if (v && v.type === "wb_var") return v.getFieldValue("NAME");
    if (v && v.type === "wb_expr") return v.getFieldValue("EXPR");
    return pathOf(v) || "";
  }
  /** An optimize objective or constraint: a path, or an expression over program variables. */
  function goalOf(v) {
    if (v && (v.type === "wb_optobjx" || v.type === "wb_optconx")) {
      const paths = {};
      chain(v.getInputTargetBlock("TERMS"), (t) => { paths[text(t.getFieldValue("NAME"))] = pathOf(t.getInputTargetBlock("PATH")) || ""; return null; });
      return { expr: v.getFieldValue("EXPR"), paths };
    }
    if (v && v.type === "wb_var") return { expr: v.getFieldValue("NAME") };
    if (v && v.type === "wb_expr") return { expr: v.getFieldValue("EXPR") };
    return { path: pathOf(v) };
  }
  function colOf(c) {
    if (c.type === "wb_tprop") return Object.assign(extras(c), { path: tpropPath(c) });   // (no label: named by its field)
    const v = c.getInputTargetBlock("VAL");
    const col = { label: c.getFieldValue("LABEL") };
    if (v && v.type === "wb_expr") col.expr = v.getFieldValue("EXPR");
    else if (v && v.type === "wb_var") col.expr = v.getFieldValue("NAME");
    else if (v) col.path = pathOf(v);
    if (col.expr != null && text(c.getFieldValue("UNIT"))) col.unit = text(c.getFieldValue("UNIT"));
    return Object.assign(extras(c), col);
  }
  function lineOf(l) {
    const colour = l.getFieldValue("COLOR");
    const line = { label: l.getFieldValue("LABEL") };
    if (l.type === "wb_pdata") {                           // a loop's results: its x only when not the loop's own
      if (!text(line.label)) delete line.label;
      Object.assign(line, { loop: l.getFieldValue("LOOP"), ycols: names(l.getFieldValue("Y")) },
        text(l.getFieldValue("X")) ? { xcol: text(l.getFieldValue("X")) } : {});
    } else if (l.type === "wb_pvline") line.x = numOrText(text(l.getFieldValue("X")));
    else {
      line.expr = l.getFieldValue("EXPR");
      if (text(l.getFieldValue("FROM"))) line.from = numOrText(text(l.getFieldValue("FROM")));
      if (text(l.getFieldValue("TO"))) line.to = numOrText(text(l.getFieldValue("TO")));
    }
    if (colour && colour !== "auto") line.color = colour;
    if (checked(l, "DASH")) line.dash = true;
    return Object.assign(extras(l), line);
  }
  function stmtOf(blk) {
    const id = blk.id, f = (n) => blk.getFieldValue(n), inp = (n) => blk.getInputTargetBlock(n);
    let st;
    switch (blk.type) {
      case "wb_set": {
        const value = text(f("VALUE"));                    // "=expr" is an expression, like a spreadsheet
        st = Object.assign({ do: "set", path: pathOf(inp("PATH")) },
          value.startsWith("=") ? { expr: value.slice(1).trim() } : { value: numOrText(value) }, unitOf(blk));
        break;
      }
      case "wb_run": st = Object.assign({ do: "run" }, checked(blk, "REINIT") ? { reinit: true } : {}); break;
      case "wb_read": st = { do: "read", path: pathOf(inp("PATH")), as: f("AS") }; break;
      case "wb_save": st = Object.assign({ do: "save" }, text(f("PATH")) ? { path: text(f("PATH")) } : {}); break;
      case "wb_calc": {
        st = { do: "calc", as: f("AS"), expr: f("EXPR") };
        if (text(f("UNIT"))) st.unit = text(f("UNIT"));
        break;
      }
      case "wb_def": st = { do: "def", name: f("NAME"), params: names(f("PARAMS")), expr: f("EXPR") }; break;
      case "wb_until": st = Object.assign({ do: "until", cond: f("COND"), max: Number(f("MAX")), body: chain(inp("BODY"), stmtOf) }, recOf(blk)); break;
      case "wb_seek":
        st = Object.assign({ do: "seek", path: pathOf(inp("PATH")), lower: Number(f("LO")), upper: Number(f("HI")) },
          unitOf(blk), { measure: f("MEASURE"), target: Number(f("TARGET")), body: chain(inp("BODY"), stmtOf) }, recOf(blk));
        break;
      case "wb_log": st = { do: "log", text: f("TEXT") }; break;
      case "wb_if": {
        const l = inp("LEFT");
        const left = !l ? {} : l.type === "wb_var" ? { var: l.getFieldValue("NAME") }
          : l.type === "wb_expr" ? { expr: l.getFieldValue("EXPR") } : { path: pathOf(l) };
        st = { do: "if", left, op: f("OP"), right: numOrText(text(f("RIGHT")) || "0"), then: chain(inp("THEN"), stmtOf), else: chain(inp("ELSE"), stmtOf) };
        break;
      }
      case "wb_repeat": st = Object.assign({ do: "repeat", times: Number(f("TIMES")), body: chain(inp("BODY"), stmtOf) }, recOf(blk)); break;
      case "wb_sweep":
        st = Object.assign({ do: "sweep", path: pathOf(inp("PATH")), from: Number(f("FROM")), to: Number(f("TO")),
          steps: Number(f("STEPS")) }, unitOf(blk), { body: chain(inp("BODY"), stmtOf) }, recOf(blk));
        break;
      case "wb_table": {                                   // (a loaded table keeps the row heading it came with)
        const ex = extras(blk), rows = names(f("ROWS"));
        const rl = "row_label" in ex ? ex.row_label : rows.length ? msg(rowKind(blk) === "block" ? "WB_TABLE_RL_B" : "WB_TABLE_RL_S") : "";
        st = Object.assign({ do: "table", title: f("TITLE") }, rl == null ? {} : { row_label: rl }, { rows, columns: chain(inp("COLS"), colOf) });
        break;
      }
      case "wb_ltable":
        st = Object.assign({ do: "table", title: f("TITLE"), loop: f("LOOP") }, names(f("VARS")).length ? { vars: names(f("VARS")) } : {});
        break;
      case "wb_plot":
        st = { do: "plot", title: f("TITLE") };                // (no x range: the data lines' own)
        if (text(f("XFROM"))) st.x_from = numOrText(text(f("XFROM")));
        if (text(f("XTO"))) st.x_to = numOrText(text(f("XTO")));
        Object.assign(st, { xlabel: f("XLABEL"), ylabel: f("YLABEL"), series: chain(inp("SERIES"), lineOf) });
        if (text(f("YFROM"))) st.y_from = numOrText(text(f("YFROM")));
        if (text(f("YTO"))) st.y_to = numOrText(text(f("YTO")));
        break;
      case "wb_call":
        st = Object.assign({ do: "call", name: f("NAME") }, splitArgs(f("ARGS")).length ? { args: splitArgs(f("ARGS")) } : {});
        break;
      case "wb_pinch":
        st = { do: "pinch", dtmin: Number(f("DTMIN")), auto: checked(blk, "AUTO"), matches: checked(blk, "MATCH"),
          exclude: names(f("EXCL")), streams: chain(inp("STREAMS"), (r) => ({ name: text(r.getFieldValue("NAME")),
            t_in: fieldOf(r.getInputTargetBlock("TIN")), t_out: fieldOf(r.getInputTargetBlock("TOUT")),
            duty: fieldOf(r.getInputTargetBlock("DUTY")) })) };
        break;
      case "wb_proc":
        st = { do: "proc", name: f("NAME"), params: names(f("PARAMS")), body: chain(blk.getNextBlock(), stmtOf) };
        break;
      case "wb_optimize":
        st = {
          do: "optimize", algorithm: f("ALG"), eval_budget: Number(f("BUDGET")),
          variables: chain(inp("VARS"), (v) => ({ path: pathOf(v.getInputTargetBlock("PATH")), lower: Number(v.getFieldValue("LO")), upper: Number(v.getFieldValue("HI")) })),
          objectives: chain(inp("OBJS"), (o) => ({ ...goalOf(o.type === "wb_optobjx" ? o : o.getInputTargetBlock("PATH")), direction: o.getFieldValue("DIR") })),
          constraints: chain(inp("CONS"), (c) => ({ ...goalOf(c.type === "wb_optconx" ? c : c.getInputTargetBlock("PATH")), [c.getFieldValue("OP")]: Number(c.getFieldValue("VAL")) })),
        };
        break;
      // only the fields of the step's form (the others' values stay on the block, unsent);
      // a stream's type only when it is not the default, unless the program wrote it (keepRest)
      case "wb_place":
        st = f("KIND") === "stream" ? Object.assign({ do: "place", stream: up(f("NAME")) }, f("STYPE") !== "MATERIAL" ? { type: f("STYPE") } : {})
          : { do: "place", block: up(f("NAME")), type: f("BTYPE") };
        break;
      case "wb_connect": st = { do: "connect", stream: f("S"), block: f("B"), port: f("PORT") }; break;
      case "wb_remove":
        st = f("KIND") === "block" ? { do: "remove", block: f("B") } : f("KIND") === "stream" ? { do: "remove", stream: f("S") }
          : { do: "remove", stream: f("S"), block: f("B"), port: f("PORT") };
        break;
      case "wb_component": st = f("KIND") === "remove" ? { do: "component", remove: f("REM") } : { do: "component", add: up(f("ADD")) }; break;
      case "wb_method": st = { do: "method", method: f("METHOD") }; break;
      case "wb_yourturn": {                                // (not filled in: not sent, checkTurn says so)
        const path = pathOf(inp("PATH")), hint = cleanWhy(f("HINT"));
        if (!ytInput(path) || !hint) return null;
        st = { do: "yourturn", path, hint };
        const ev = blk.getInput("YTEXP") ? text(f("YTEXP")) : "", av = blk.getInput("YTANS") ? text(f("YTANS")) : "";
        if (ev) st.expect = { op: f("YTOP"), value: numOrText(ev) };
        if (av) st.answer = numOrText(av);
        break;
      }
      case "wb_other": st = {}; break;                     // the statement is its data, as it came
      case "wb_group": {                                   // a heading: its title, when it has one (why: its note)
        const title = String(f("TITLE") || "").replace(/\s+/g, " ").trim();
        st = Object.assign({ do: "group" }, title ? { title } : {});
        break;
      }
      default: return null;
    }
    if (STRUCT.includes(blk.type) && structTodo(blk)) return null;   // not filled in: not sent (checkStruct says so)
    const ex = extras(blk);
    if (ex.row_label === null) delete ex.row_label;        // (a table loaded without a row heading: still without)
    const off = blk.type !== "wb_proc" && blk.hasDisabledReason(OFF);   // turned off: the block's reason decides
    if (blk.type !== "wb_proc") {
      delete ex.off;
      if (off) st.off = true;
    }
    if (blk.getInput("WHY")) {                             // the note's row decides
      delete ex.why;
      if (blk.getWhy()) st.why = blk.getWhy();
    }
    if (blk.getField("FINISH")) {                          // the row decides; its default is left out
      delete ex.finish;
      if (f("FINISH") !== FIN[st.do][0]) st.finish = f("FINISH");
    }
    return Object.assign(ex, st, { id });
  }
  /** The program: the start stack, then the procedures (by name, so moving one is no edit). */
  WB.workspaceToProgram = function (ws) {
    const tops = ws.getTopBlocks(false);
    const start = tops.find((x) => x.type === "wb_start");
    const procs = tops.filter((x) => x.type === "wb_proc")
      .sort((a, z) => String(a.getFieldValue("NAME")).localeCompare(String(z.getFieldValue("NAME"))));
    return (start ? chain(start.getNextBlock(), stmtOf) : []).concat(procs.map(stmtOf));
  };
  /** Every other stack on the workspace, as Blockly saves it, positions included. */
  WB.looseStacks = function (ws) {
    return ws.getTopBlocks(true).filter((x) => x.type !== "wb_start" && x.type !== "wb_proc" && !x.isInsertionMarker())
      .map((x) => Blockly.serialization.blocks.save(x, { addCoordinates: true }));
  };

  // ------------------------------------------------------------------ program -> workspace
  const reEsc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  /** The blocks the program being loaded puts down (its place steps, at any depth): a field of
   *  one is picked from that block's menus, "H1 (HeatX) › SPEC", though the catalog does not
   *  list it, rather than shown as its raw path; so is one of a block the flowsheet already has
   *  (COL's Input\CONDENSER, Input\FEED_STAGE\FEED). WB.loadProgram sets it for the load; only
   *  where the server names fields (labels.js), so the field's menu reads in words. */
  let placing = new Set();
  function placedIn(list, out) {
    (list || []).forEach((s) => {
      if (!s || typeof s !== "object") return;
      if (s.do === "place" && s.block) out.add(up(s.block));
      ["body", "then", "else"].forEach((k) => placedIn(s[k], out));
    });
    return out;
  }
  function pathJson(p) {
    if (!p) return undefined;
    const cat = WB.data.catalog;
    let m = /^\\Data\\Streams\\([^\\]+)\\(.+)$/.exec(p);
    if (m) {
      for (const sp of cat.stream_props) {
        const re = new RegExp("^" + reEsc(sp.path).replace(reEsc("{C}"), "([^\\\\]+)") + "$");
        const mm = re.exec(m[2]);
        if (mm) {
          WB.known.streams.add(m[1]);
          if (mm[1]) WB.known.comps.add(mm[1]);
          return { block: { type: "wb_stream", fields: { S: m[1], P: sp.key, C: mm[1] || NONE } } };
        }
      }
    }
    m = /^\\Data\\Blocks\\([^\\]+)\\(.+)$/.exec(p);
    if (m) {
      const all = Object.values(cat.block_params).flat().map((x) => x.path);
      const own = placing.has(up(m[1])) || ((WB.data.flowsheet || {}).blocks || []).some((x) => up(x.name) === up(m[1]));
      const placed = own && /^(Input|Output)\\[^\\]/.test(m[2]);
      if (all.includes(m[2]) || placed) {
        WB.known.blocks.add(m[1]);
        WB.known.params.add(m[2]);
        return { block: { type: "wb_block", fields: { B: m[1], P: m[2] } } };
      }
    }
    return { block: { type: "wb_path", fields: { RAW: p } } };
  }
  const own = (g) => g.expr != null && g.expr !== "" && g.paths && Object.keys(g.paths).length > 0;
  function termsJson(paths) {
    return listJson(Object.entries(paths || {}), ([n, p]) => {
      const j = { type: "wb_optterm", fields: { NAME: n }, inputs: {} };
      const v = pathJson(p);
      if (v) j.inputs.PATH = v;
      return j;
    });
  }
  function goalJson(g) {
    if (g.expr == null || g.expr === "") return pathJson(g.path);
    const e = String(g.expr).trim();
    return /^[A-Za-z_]\w*$/.test(e) ? { block: { type: "wb_var", fields: { NAME: e } } }
      : { block: { type: "wb_expr", fields: { EXPR: e } } };
  }
  function listJson(list, fn) {
    let head, prev;
    (list || []).forEach((s) => {
      const j = fn(s);
      if (!j) return;
      if (prev) prev.next = { block: j }; else head = j;
      prev = j;
    });
    return head ? { block: head } : undefined;
  }
  function unitField(s) {
    if (s.unit) WB.known.units.add(s.unit);
    return s.unit || NONE;
  }
  /** A loop's record field: the names it records, or the current language's "all". */
  const recText = (s) => recNames([].concat(s.record || []).join(",")).join(", ") || msg("WB_REC_ALL");
  /** Every loop's "all" in a saved stack (Blockly's JSON) in the current language's word, so a
   *  stack saved with "*" or in the other language reads as today's (the program is the same). */
  function recWords(j) {
    if (!j || typeof j !== "object") return j;
    if (Array.isArray(j)) { j.forEach(recWords); return j; }
    const f = j.fields;
    if (f && typeof f.REC === "string" && LOOPS.includes(j.type) && !recNames(f.REC).length) f.REC = msg("WB_REC_ALL");
    Object.values(j).forEach((v) => { if (v && typeof v === "object") recWords(v); });
    return j;
  }
  /** Fields a block does not show ride along in its data, so an edit keeps them. */
  function keepRest(j, s, handled) {
    const rest = Object.assign({}, s);
    handled.forEach((k) => delete rest[k]);
    if (Object.keys(rest).length) j.data = JSON.stringify(rest);
    return j;
  }
  function colJson(c) {
    // a property of each row, without a label of its own: a column picked by its property
    const m = !c.label && c.expr == null && /^\\Data\\(Streams|Blocks)\\\{row\}\\(.+)$/.exec(String(c.path || ""));
    if (m && m[1] === "Blocks") return keepRest({ type: "wb_tprop", fields: { P: "b:" + m[2] } }, c, ["path"]);
    if (m) {
      for (const sp of WB.data.catalog.stream_props) {
        const mm = new RegExp("^" + reEsc(sp.path).replace(reEsc("{C}"), "([^\\\\]+)") + "$").exec(m[2]);
        if (!mm) continue;
        if (mm[1]) WB.known.comps.add(mm[1]);
        return keepRest({ type: "wb_tprop", fields: { P: "s:" + sp.key, C: mm[1] || NONE } }, c, ["path"]);
      }
    }
    const val = c.path ? pathJson(c.path) : c.expr != null ? { block: { type: "wb_expr", fields: { EXPR: String(c.expr) } } } : undefined;
    return keepRest({ type: "wb_tcol", fields: { LABEL: c.label || "", UNIT: c.unit || "" }, inputs: val ? { VAL: val } : {} },
      c, ["label", "path", "expr", "unit"]);
  }
  function lineJson(l) {
    if (l.loop != null && l.loop !== "") {
      return keepRest({ type: "wb_pdata", fields: { LOOP: String(l.loop), Y: [].concat(l.ycols || []).join(", "), X: String(l.xcol ?? ""),
        LABEL: l.label || "", COLOR: l.color || "auto", DASH: !!l.dash } }, l, ["label", "loop", "ycols", "xcol", "color", "dash"]);
    }
    const vertical = l.x != null && l.x !== "";
    const j = { type: vertical ? "wb_pvline" : "wb_pline", fields: { LABEL: l.label || "", COLOR: l.color || "auto", DASH: !!l.dash } };
    if (vertical) j.fields.X = String(l.x);
    else Object.assign(j.fields, { EXPR: String(l.expr ?? ""), FROM: String(l.from ?? ""), TO: String(l.to ?? "") });
    return keepRest(j, l, ["label", "x", "expr", "from", "to", "color", "dash"]);
  }
  const HANDLED = {
    set: ["path", "value", "expr", "unit"], run: ["reinit"], read: ["path", "as"], log: ["text"], save: ["path"],
    if: ["left", "op", "right", "then", "else"], repeat: ["times", "body", "record"],
    sweep: ["path", "from", "to", "steps", "unit", "body", "record"],
    calc: ["as", "expr", "unit"], def: ["name", "params", "expr"], until: ["cond", "max", "body", "record"],
    seek: ["path", "lower", "upper", "unit", "measure", "target", "body", "record"],
    table: ["title", "rows", "columns"],
    plot: ["title", "x_from", "x_to", "y_from", "y_to", "xlabel", "ylabel", "series"],
    call: ["name", "args"], proc: ["name", "params", "body"],
    pinch: ["dtmin", "auto", "matches", "exclude", "streams"],
    optimize: ["algorithm", "eval_budget", "variables", "objectives", "constraints"],
    place: ["block", "stream", "type"], connect: ["stream", "block", "port"], remove: ["block", "stream", "port"],
    component: ["add", "remove"], method: ["method"],
    yourturn: ["path", "hint", "expect", "answer"],
    group: ["title"],
  };
  /** The names a flowsheet change gives, kept for its menus (so loading never refuses one). */
  function knowStruct(s) {
    if (s.stream != null) WB.known.streams.add(up(s.stream));
    if (s.block != null) WB.known.blocks.add(up(s.block));
    if (s.port) WB.known.ports.add(up(s.port));
  }
  function stmtJson(s) {
    const j = { id: s.id, fields: {}, inputs: {} };
    const put = (name, value) => { if (value) j.inputs[name] = value; };
    let handled = HANDLED[s.do] || [];
    switch (s.do) {
      case "set":
        j.type = "wb_set"; put("PATH", pathJson(s.path));
        j.fields.VALUE = s.expr != null && s.expr !== "" ? "=" + s.expr : String(s.value ?? ""); j.fields.UNIT = unitField(s);
        break;
      case "run": j.type = "wb_run"; j.fields.REINIT = !!s.reinit; break;
      case "read": j.type = "wb_read"; put("PATH", pathJson(s.path)); j.fields.AS = s.as || "x"; break;
      case "save": j.type = "wb_save"; j.fields.PATH = s.path || ""; break;
      case "calc": j.type = "wb_calc"; Object.assign(j.fields, { AS: s.as || "y", EXPR: s.expr || "", UNIT: s.unit || "" }); break;
      case "def":
        j.type = "wb_def";
        Object.assign(j.fields, { NAME: s.name || "f", PARAMS: [].concat(s.params || []).join(", "), EXPR: s.expr || "" });
        break;
      case "until":
        j.type = "wb_until"; Object.assign(j.fields, { COND: s.cond || "", MAX: Number(s.max || 100), REC: recText(s) });
        put("BODY", listJson(s.body, stmtJson));
        break;
      case "seek":
        j.type = "wb_seek"; put("PATH", pathJson(s.path));
        Object.assign(j.fields, { LO: Number(s.lower || 0), HI: Number(s.upper || 0), UNIT: unitField(s),
          MEASURE: s.measure || "", TARGET: Number(s.target || 0), REC: recText(s) });
        put("BODY", listJson(s.body, stmtJson));
        break;
      case "log": j.type = "wb_log"; j.fields.TEXT = s.text || ""; break;
      case "if": {
        j.type = "wb_if";
        const left = s.left || {};
        put("LEFT", left.var != null ? { block: { type: "wb_var", fields: { NAME: left.var } } }
          : left.expr != null ? { block: { type: "wb_expr", fields: { EXPR: left.expr } } } : pathJson(left.path));
        j.fields.OP = s.op || ">"; j.fields.RIGHT = String(s.right ?? 0);
        put("THEN", listJson(s.then, stmtJson)); put("ELSE", listJson(s.else, stmtJson));
        break;
      }
      case "repeat":
        j.type = "wb_repeat"; Object.assign(j.fields, { TIMES: Number(s.times || 1), REC: recText(s) });
        put("BODY", listJson(s.body, stmtJson));
        break;
      case "sweep":
        j.type = "wb_sweep"; put("PATH", pathJson(s.path));
        Object.assign(j.fields, { FROM: Number(s.from || 0), TO: Number(s.to || 0), STEPS: Number(s.steps || 2), UNIT: unitField(s), REC: recText(s) });
        put("BODY", listJson(s.body, stmtJson));
        break;
      case "table":
        if (s.loop != null && s.loop !== "") {             // a loop's results
          j.type = "wb_ltable";
          Object.assign(j.fields, { TITLE: s.title || "", LOOP: String(s.loop), VARS: [].concat(s.vars || []).join(", ") });
          handled = ["title", "loop", "vars"];
          break;
        }
        j.type = "wb_table";                               // (its row heading rides in its data; none: null)
        Object.assign(j.fields, { TITLE: s.title || "", ROWS: [].concat(s.rows || []).join(", ") });
        put("COLS", listJson(s.columns, colJson));
        if (!("row_label" in s)) s = Object.assign({ row_label: null }, s);
        break;
      case "plot":
        j.type = "wb_plot";
        Object.assign(j.fields, { TITLE: s.title || "", XFROM: String(s.x_from ?? ""), XTO: String(s.x_to ?? ""),
          YFROM: String(s.y_from ?? ""), YTO: String(s.y_to ?? ""), XLABEL: s.xlabel || "", YLABEL: s.ylabel || "" });
        put("SERIES", listJson(s.series, lineJson));
        break;
      case "pinch":
        j.type = "wb_pinch";
        Object.assign(j.fields, { DTMIN: Number(s.dtmin ?? 10), AUTO: s.auto !== false, MATCH: s.matches !== false,
          EXCL: [].concat(s.exclude || []).join(", ") });
        put("STREAMS", listJson(s.streams, (r) => {
          const row = { type: "wb_pstream", fields: { NAME: r.name || "" }, inputs: {} };
          [["TIN", r.t_in], ["TOUT", r.t_out], ["DUTY", r.duty]].forEach(([k, v]) => {
            const val = String(v ?? "").trim();
            if (val) row.inputs[k] = val.startsWith("\\") ? pathJson(val) : goalJson({ expr: val });
          });
          return row;
        }));
        break;
      case "call":
        j.type = "wb_call";
        if (s.name) WB.known.procs.add(s.name);
        Object.assign(j.fields, { NAME: s.name || NONE, ARGS: [].concat(s.args || []).join(", ") });
        break;
      case "optimize":
        j.type = "wb_optimize"; j.fields.ALG = s.algorithm || "afmcbo"; j.fields.BUDGET = Number(s.eval_budget || 100);
        put("VARS", listJson(s.variables, (v) => ({ type: "wb_optvar", fields: { LO: Number(v.lower ?? 0), HI: Number(v.upper ?? 1) }, inputs: { PATH: pathJson(v.path) } })));
        put("OBJS", listJson(s.objectives, (o) => own(o)
          ? { type: "wb_optobjx", fields: { DIR: o.direction || "minimize", EXPR: String(o.expr) }, inputs: { TERMS: termsJson(o.paths) } }
          : { type: "wb_optobj", fields: { DIR: o.direction || "minimize" }, inputs: { PATH: goalJson(o) } }));
        put("CONS", listJson((s.constraints || []).flatMap((c) => ["lower", "upper"].filter((k) => c[k] != null).map((k) => ({ path: c.path, expr: c.expr, paths: c.paths, op: k, val: c[k] }))),
          (c) => own(c)
            ? { type: "wb_optconx", fields: { EXPR: String(c.expr), OP: c.op, VAL: Number(c.val) }, inputs: { TERMS: termsJson(c.paths) } }
            : { type: "wb_optcon", fields: { OP: c.op, VAL: Number(c.val) }, inputs: { PATH: goalJson(c) } }));
        break;
      case "place":
        j.type = "wb_place";
        knowStruct(s);
        if (s.block == null && s.stream != null) {
          const ty = up(s.type) || "MATERIAL";
          if (!STYPES.includes(ty)) WB.known.stypes.add(ty);
          Object.assign(j.fields, { KIND: "stream", NAME: up(s.stream), STYPE: ty });
          if (ty === "MATERIAL" && s.type != null) handled = ["block", "stream"];   // written out: it stays so (stmtOf)
        } else {
          const ty = String(s.type ?? "").trim();
          if (ty) WB.known.types.add(ty);
          Object.assign(j.fields, { KIND: "block", NAME: up(s.block) }, ty ? { BTYPE: ty } : {});
        }
        break;
      case "connect":
        j.type = "wb_connect";
        knowStruct(s);
        Object.assign(j.fields, { S: up(s.stream), B: up(s.block), PORT: up(s.port) });
        break;
      case "remove":
        j.type = "wb_remove";
        knowStruct(s);
        j.fields.KIND = s.port ? "conn" : s.block != null ? "block" : "stream";
        if (s.stream != null) j.fields.S = up(s.stream);
        if (s.block != null) j.fields.B = up(s.block);
        if (s.port) j.fields.PORT = up(s.port);
        break;
      case "component":
        j.type = "wb_component";
        if (s.add == null && s.remove != null) {
          WB.known.comps.add(up(s.remove));
          Object.assign(j.fields, { KIND: "remove", REM: up(s.remove) });
        } else Object.assign(j.fields, { KIND: "add", ADD: up(s.add) });
        break;
      case "method": j.type = "wb_method"; WB.known.methods.add(up(s.method)); j.fields.METHOD = up(s.method); break;
      case "yourturn": {                                   // the manual step: the check and the answer ride in its extra state
        j.type = "wb_yourturn"; put("PATH", pathJson(s.path)); j.fields.HINT = String(s.hint ?? "");
        const e = s.expect && typeof s.expect === "object" && s.expect.value != null && String(s.expect.value) !== "" ? s.expect : null, ex = {};
        if (e) ex.expect = { op: YT_OPS.some((o) => o[1] === e.op) ? e.op : ">=", value: String(e.value) };
        if (s.answer != null && String(s.answer) !== "") ex.answer = String(s.answer);
        if (Object.keys(ex).length) j.extraState = ex;
        break;
      }
      case "proc": return null;                            // a proc is a stack of its own (procJson)
      case "group":                                        // a group heading; a server without groups: kept whole (below)
        if (groupsOn()) { j.type = "wb_group"; j.fields.TITLE = String(s.title ?? ""); break; }
      // falls through
      default:                                             // a kind this page does not know: kept whole, as written
        j.type = "wb_other";
        j.fields.KIND = String(s.do ?? "?");
        return offJson(keepRest(whyJson(j, s), s, ["id", "why", "off"]), s);
    }
    const fin = FIN[s.do] || null;
    if (fin) j.fields.FINISH = fin.includes(s.finish) ? s.finish : fin[0];
    return offJson(keepRest(whyJson(j, s), s, ["do", "id"].concat(handled, fin ? ["finish"] : [], ["why", "off"])), s);
  }
  /** A turned-off step (off: true) loads turned off. */
  function offJson(j, s) {
    if (s.off === true) j.disabledReasons = [OFF];
    return j;
  }
  function procJson(s) {
    const j = { type: "wb_proc", id: s.id, fields: { NAME: s.name || "my_steps", PARAMS: [].concat(s.params || []).join(", ") } };
    const body = listJson(s.body, stmtJson);
    if (body) j.next = body;
    return keepRest(whyJson(j, s), s, ["do", "id"].concat(HANDLED.proc, ["why"]));
  }
  /** A statement's note as the block's extra state (its row). */
  function whyJson(j, s) {
    const why = cleanWhy(s.why);
    if (why) j.extraState = Object.assign(j.extraState || {}, { why });   // (beside a manual step's rows)
    return j;
  }

  function tidy(ws) {
    const all = ws.getAllBlocks(false);
    all.filter((x) => x.type === "wb_stream").forEach(syncStream);
    all.filter((x) => x.type === "wb_stream" || x.type === "wb_block" || x.type === "wb_path")
      .forEach((x) => { syncKind(x); checkWritable(x); });
    all.filter((x) => x.type === "wb_set" || x.type === "wb_sweep" || x.type === "wb_seek").forEach(syncUnit);
    all.filter((x) => x.type === "wb_tcol").forEach(syncTcol);
    all.filter((x) => x.type === "wb_tprop").forEach(syncTprop);
    all.filter((x) => x.type === "wb_table").forEach(checkTable);
    all.filter((x) => x.type === "wb_pdata" || x.type === "wb_ltable").forEach(checkLoopPick);
    all.filter((x) => x.type === "wb_plot").forEach(syncPlot);
    checkNames(ws);
    all.filter((x) => x.type === "wb_call").forEach(syncCall);
    all.filter((x) => LOOPS.includes(x.type)).forEach(checkLoopRead);
    all.filter((x) => STRUCT.includes(x.type)).forEach(checkStruct);
    all.filter((x) => x.type === "wb_yourturn").forEach(checkTurn);
  }
  WB.tidy = tidy;

  /** Show a version: the program (start stack and procedures) and, when the version has
   *  them, its loose stacks; without (an older version), the loose stacks on screen stay.
   *  Returns the view the workspace had, {x, y}, for the caller to put back (clearing it
   *  scrolls it home). Nothing here scrolls: Blockly's scroll closes the open field editor
   *  and menu on every workspace, so one off screen must not scroll (see keepView). */
  WB.loadProgram = function (ws, program, loose) {
    const tops = ws.getTopBlocks(false), sx = ws.scrollX, sy = ws.scrollY;
    const keep = Array.isArray(loose) ? loose : tops.filter((x) => x.type !== "wb_start" && x.type !== "wb_proc")
      .map((x) => Blockly.serialization.blocks.save(x, { addCoordinates: true }));
    const start = tops.find((x) => x.type === "wb_start");
    const pos = start ? start.getRelativeToSurfaceXY() : { x: 40, y: 40 };
    const procAt = {};                                     // procedures stay where the user put them
    tops.filter((x) => x.type === "wb_proc").forEach((x) => { procAt[x.getFieldValue("NAME")] = x.getRelativeToSurfaceXY(); });
    const main = (program || []).filter((s) => s.do !== "proc"), procs = (program || []).filter((s) => s.do === "proc");
    WB.known.procs = new Set(procs.map((p) => p.name).filter(Boolean));
    const startJson = { type: "wb_start", id: "wb_start", x: pos.x, y: pos.y };
    placing = placedIn(program, new Set());
    let body, procsJson;
    try {
      body = listJson(main, stmtJson);
      procsJson = procs.map(procJson);
    } finally { placing = new Set(); }
    if (body) startJson.next = body;
    ws.clear();
    Blockly.serialization.blocks.append(startJson, ws);
    // (a copy: the stacks may be the server's state, which the page compares versions with)
    keep.forEach((j) => Blockly.serialization.blocks.append(recWords(JSON.parse(JSON.stringify(j))), ws));
    // the procedures wait off to the side, apart, while every block takes its final size (tidy,
    // and the render Blockly would do in the next frame), so they are placed by those sizes:
    // placed at once, one the program has grown under would be nudged aside by Blockly's bump
    const PARK = -1e6, moveTo = (blk, x, y) => { const at = blk.getRelativeToSurfaceXY(); blk.moveBy(x - at.x, y - at.y); };
    const placed = procs.map((p, i) => ({ at: procAt[p.name],
      blk: Blockly.serialization.blocks.append(Object.assign(procsJson[i], { x: PARK + i * 1e4, y: PARK }), ws) }));
    tidy(ws);
    Blockly.renderManagement.triggerQueuedRenders(ws);
    const fresh = new Set();
    placed.forEach(({ blk, at }) => { if (at) moveTo(blk, at.x, at.y); else fresh.add(blk); });
    // a longer main stack pushes the procedures it now reaches down; one new to the screen
    // goes under the main stack and those already there, where scrolling down finds it
    // (beside it, it would start past the right edge of a narrow column)
    WB.clearOfMain(ws, fresh);
    const area = mainArea(ws);
    let py = area ? area.bottom + 56 : pos.y;
    if (area) procsIn(ws, area).filter((p) => !fresh.has(p.b)).forEach((p) => { py = Math.max(py, p.r.bottom + 40); });
    fresh.forEach((blk) => {
      moveTo(blk, area ? area.left : pos.x, py);
      py += blk.getHeightWidth().height + 40;
    });
    return { x: sx, y: sy };
  };

  /** Where the main program lies (workspace units): each of its blocks' own box, and the
   *  column and height they take together. */
  function mainArea(ws) {
    const start = ws.getTopBlocks(false).find((x) => x.type === "wb_start");
    if (!start) return null;
    const own = start.getDescendants(false).map((b) => b.getBoundingRectangleWithoutChildren());
    return { own, left: Math.min(...own.map((o) => o.left)), right: Math.max(...own.map((o) => o.right)),
             top: Math.min(...own.map((o) => o.top)), bottom: Math.max(...own.map((o) => o.bottom)) };
  }
  /** The procedures in the main program's column, not above it, top first. */
  function procsIn(ws, area) {
    return ws.getTopBlocks(false).filter((x) => x.type === "wb_proc").map((b) => ({ b, r: b.getBoundingRectangle() }))
      .filter((p) => p.r.left < area.right && p.r.right > area.left && p.r.bottom > area.top)
      .sort((a, z) => a.r.top - z.r.top);
  }
  /** The bottom of the main program (workspace units), to tell when it grew. */
  WB.mainEnd = function (ws) {
    const start = ws.getTopBlocks(false).find((x) => x.type === "wb_start");
    return start ? start.getBoundingRectangle().bottom : 0;
  };
  /** A procedure the main program now reaches (it grew: the AI added steps, an older version
   *  came back longer, a step was dropped in) moves down under it, and every procedure below
   *  it in the program's column with it, so their order and gaps stay. One beside the program,
   *  clear of its blocks, stays where it is. skip: procedures not placed yet. Returns the
   *  procedures it moved. */
  WB.clearOfMain = function (ws, skip) {
    const area = mainArea(ws), M = 16, moved = new Set();
    if (!area) return moved;
    const col = procsIn(ws, area).filter((p) => !(skip && skip.has(p.b)));
    const hit = col.find((p) => area.own.some((o) => p.r.left < o.right + M && p.r.right > o.left - M
                                                    && p.r.top < o.bottom + M && p.r.bottom > o.top - M));
    if (!hit) return moved;
    const dy = area.bottom + 56 - hit.r.top;
    col.filter((p) => p.r.top >= hit.r.top).forEach((p) => { p.b.moveBy(0, dy); moved.add(p.b); });
    return moved;
  };

  /** Re-create every block so its text follows the current language. Returns the view it
   *  had, {x, y}, to put back as WB.loadProgram's. A loop's "all" in the program follows the
   *  language too (the program is the same); the loose stacks keep their text, so a tab saved
   *  to a .awb does not turn unsaved by a language switch. */
  /** A block's field the catalog does not name, in the server's words once they came
   *  (WBL.onChange): its menu made again, the words on the block put in place. No event: the
   *  value is as it was. */
  WB.paramWords = function (ws) {
    if (!ws) return;
    ws.getAllBlocks(false).forEach((b) => {
      const f = b.type === "wb_block" && b.getField("P");
      if (!f || !String(f.getValue() || "").includes("\\")) return;
      const was = f.getText(), hit = f.getOptions(false).find((o) => o[1] === f.getValue());
      if (!hit || hit[0] === was || typeof hit[0] !== "string") return;
      f.selectedOption = hit;
      f.forceRerender();
    });
  };

  WB.relabel = function (ws) {
    ws.getTopBlocks(false).filter((x) => x.type === "wb_proc").forEach((x) => WB.known.procs.add(x.getFieldValue("NAME")));
    const json = Blockly.serialization.workspaces.save(ws), sx = ws.scrollX, sy = ws.scrollY;
    ((json.blocks && json.blocks.blocks) || []).filter((j) => j.type === "wb_start" || j.type === "wb_proc").forEach(recWords);
    ws.clear();
    ws.updateToolbox(WB.toolbox());
    Blockly.serialization.workspaces.load(json, ws);
    tidy(ws);
    return { x: sx, y: sy };
  };

  function place(ws, clientX, clientY) {
    if (clientX != null && Blockly.utils.svgMath && Blockly.utils.svgMath.screenToWsCoordinates) {
      const c = Blockly.utils.svgMath.screenToWsCoordinates(ws, new Blockly.utils.Coordinate(clientX, clientY));
      return { x: c.x, y: c.y };
    }
    const m = ws.getMetricsManager().getViewMetrics(true);
    return { x: m.left + 40 + Math.random() * 60, y: m.top + 40 + Math.random() * 60 };
  }
  /** A block the user added (Ctrl+Z takes it away again). */
  function added(ws, json) {
    const blk = Blockly.serialization.blocks.append(json, ws, { recordUndo: true });
    tidy(ws);
    return blk;
  }

  // ------------------------------------------------------------------ adding to the program
  // What the inspector adds (a row's ⊕ menu, a double-click, the path block) goes into the
  // program where the user is working: after the step picked last, else at the main
  // program's end. Blockly 13 lets go of its selection when the focus leaves the workspace
  // (for the inspector, say), but keeps the block passively focused: that one counts.

  /** The block picked last in ws: selected, or focused before the focus went elsewhere. */
  WB.focused = function (ws) {
    const sel = Blockly.getSelected && Blockly.getSelected();
    if (sel && sel.workspace === ws && sel.type) return sel;
    const el = ws.getParentSvg().querySelector(".blocklyActiveFocus, .blocklyPassiveFocus");
    const g = el && el.closest(".blocklyBlock");
    return g && g.dataset.id ? ws.getBlockById(g.dataset.id) : null;
  };
  /** The step a new one goes after: the block picked last, or the step it belongs to (a value
   *  stands for the block it is plugged into; a row of a typed list, such as a decision
   *  variable, for the block holding the list), when that step is part of the program (under
   *  the start block or in a procedure; a hat counts: the new step goes first). Else null. */
  WB.anchor = function (ws) {
    let blk = WB.focused(ws);
    while (blk && (blk.outputConnection || (blk.previousConnection && blk.previousConnection.getCheck()))) {
      blk = blk.outputConnection ? blk.getParent() : blk.getSurroundParent();
    }
    const root = blk && blk.getRootBlock();
    return root && (root.type === "wb_start" || root.type === "wb_proc") && blk.nextConnection ? blk : null;
  };
  /** The loop (sweep, design spec, repeat, until) the anchor is, or lies in (the innermost),
   *  else null: where a read may go in each pass or after the loop. */
  WB.loopOf = function (ws) {
    for (let x = WB.anchor(ws); x; x = x.getSurroundParent()) if (LOOPS.includes(x.type)) return x;
    return null;
  };

  // ------------------------------------------------------------------ links to the flowsheet
  // A stream or block picked on the flowsheet marks every step that names it (app-inspector.js,
  // markRefs); a block selected here marks what it names on the flowsheet (FS.mark).

  /** The stream or block a path block names ({kind, name}), or null: a stream's or block's
   *  menu, or a raw path under \Data\Streams or \Data\Blocks. */
  function targetOf(b) {
    if (!b) return null;
    if (b.type === "wb_stream") return { kind: "stream", name: String(b.getFieldValue("S") || "") };
    if (b.type === "wb_block") return { kind: "block", name: String(b.getFieldValue("B") || "") };
    if (b.type !== "wb_path") return null;
    const m = /^\\Data\\(Streams|Blocks)\\([^\\]+)/i.exec(String(b.getFieldValue("RAW") || ""));
    return m ? { kind: m[1].toLowerCase() === "streams" ? "stream" : "block", name: m[2] } : null;
  }
  const same = (a, z) => !!a && !!z && a.kind === z.kind && a.name.toUpperCase() === z.name.toUpperCase();

  /** The steps whose paths name target: each statement (or row of a typed list, such as a
   *  decision variable) holding a path block that names it, however deep the value sits. */
  WB.refsTo = function (ws, target) {
    const out = new Set();
    if (!target) return [];
    ws.getAllBlocks(false).forEach((b) => {
      if (b.isInsertionMarker() || !same(targetOf(b), target)) return;
      let s = b;
      while (s && s.outputConnection) s = s.getParent();
      if (s) out.add(s);
    });
    return [...out];
  };
  /** What a block names on the flowsheet: its own path, and the paths plugged into it (not
   *  those of the steps inside it), each once. */
  WB.targetsIn = function (blk) {
    const out = [];
    const walk = (b) => {
      const tg = targetOf(b);
      if (tg && tg.name && !out.some((x) => same(x, tg))) out.push(tg);
      b.inputList.forEach((inp) => {
        const c = inp.connection;
        if (c && c.type === Blockly.ConnectionType.INPUT_VALUE && c.targetBlock()) walk(c.targetBlock());
      });
    };
    if (blk) walk(blk);
    return out;
  };

  /** Blockly events of one user action, as one undo step. */
  function grouped(fn) {
    const own = !Blockly.Events.getGroup();
    if (own) Blockly.Events.setGroup(true);
    try { return fn(); } finally { if (own) Blockly.Events.setGroup(false); }
  }

  /** Put statements (toolbox JSON) into the program after the block afterId, whose next step
   *  moves down under them; without one, at the main program's end. One undo step. Returns
   *  the new blocks. */
  WB.appendStatements = function (ws, stmts, afterId) {
    let after = afterId ? ws.getBlockById(afterId) : null;
    if (!after) {
      after = ws.getTopBlocks(false).find((x) => x.type === "wb_start");
      while (after && after.getNextBlock()) after = after.getNextBlock();
    }
    if (!after || !after.nextConnection) return [];
    return grouped(() => {
      const rest = after.getNextBlock();
      if (rest) rest.unplug(false);
      let at = after.nextConnection;
      const made = stmts.map((json) => {
        const blk = Blockly.serialization.blocks.append(json, ws, { recordUndo: true });
        at.connect(blk.previousConnection);
        let end = blk;
        while (end.getNextBlock()) end = end.getNextBlock();
        at = end.nextConnection;
        return blk;
      });
      if (rest && at) at.connect(rest.previousConnection);
      tidy(ws);
      return made;
    });
  };

  /** Put statements into a loop, so they run at every pass: after the last run step in its
   *  body (and the reads right after it, so reads keep the order they were added in), else at
   *  the body's end; into an empty body as its first steps. One undo step. Returns the new
   *  blocks. */
  WB.appendInto = function (ws, loop, stmts) {
    let after = null;
    for (let x = loop.getInputTargetBlock("BODY"); x; x = x.getNextBlock()) if (x.type === "wb_run") after = x;
    while (after && after.getNextBlock() && after.getNextBlock().type === "wb_read") after = after.getNextBlock();
    if (!after) for (let x = loop.getInputTargetBlock("BODY"); x; x = x.getNextBlock()) after = x;
    if (after) return WB.appendStatements(ws, stmts, after.id);
    return grouped(() => {
      let at = loop.getInput("BODY").connection;
      const made = stmts.map((json) => {
        const blk = Blockly.serialization.blocks.append(json, ws, { recordUndo: true });
        at.connect(blk.previousConnection);
        let end = blk;
        while (end.getNextBlock()) end = end.getNextBlock();
        at = end.nextConnection;
        return blk;
      });
      tidy(ws);
      return made;
    });
  };

  /** Put a decision variable, objective or constraint (json) into input (VARS, OBJS, CONS) of
   *  an optimize step: the one holding the block picked last (from), else the main program's
   *  last, else a new one at the program's end. Returns {blk, opt, made: the step is new}. */
  WB.addToOptimize = function (ws, json, input, from) {
    let opt = null;
    for (let x = from; x && !opt; x = x.getSurroundParent()) if (x.type === "wb_optimize") opt = x;
    if (!opt) {
      const start = ws.getTopBlocks(false).find((x) => x.type === "wb_start");
      opt = (start ? start.getDescendants(true) : []).filter((x) => x.type === "wb_optimize").pop() || null;
    }
    return grouped(() => {
      const made = !opt;
      if (made) opt = WB.appendStatements(ws, [{ type: "wb_optimize" }], null)[0];
      if (!opt) return { blk: null, opt: null, made };
      let last = opt.getInputTargetBlock(input);
      while (last && last.getNextBlock()) last = last.getNextBlock();
      const blk = Blockly.serialization.blocks.append(json, ws, { recordUndo: true });
      (last ? last.nextConnection : opt.getInput(input).connection).connect(blk.previousConnection);
      tidy(ws);
      return { blk, opt, made };
    });
  };

  /** A range around a value: ±20 %, low to high (a negative value too). None for zero or a
   *  value that is not a number: the block keeps its own and the user fills it in. */
  function around(v) {
    const x = typeof v === "number" ? v : v === null || v === "" ? NaN : Number(v);
    if (!isFinite(x) || x === 0) return null;
    const r4 = (n) => Number(n.toPrecision(4)), a = r4(x * 0.8), z = r4(x * 1.2);
    return x > 0 ? [a, z] : [z, a];
  }
  /** An inspector row as a block (toolbox JSON): set its value; sweep it (±20 %, five points)
   *  or adjust it to a target, running the simulation each pass; read it; or, for an optimize
   *  step, a decision variable (±20 %), an objective (minimize) or a constraint (at least its
   *  value now). Numbers are in the field's current unit, which the unit menus keep. */
  WB.rowBlock = function (row, what) {
    if (row.unit || row.units) WB.data.units[row.path] = { unit: row.unit || null, units: row.units || [] };
    const path = pathJson(row.path), r = around(row.value), run = { block: { type: "wb_run" } };
    const range = (lo, hi) => (r ? { [lo]: r[0], [hi]: r[1] } : {});
    const now = typeof row.value === "number" && isFinite(row.value) ? row.value : 0;
    switch (what) {
      case "set": return { type: "wb_set", fields: { VALUE: String(row.value ?? ""), UNIT: NONE }, inputs: { PATH: path } };
      case "read": return { type: "wb_read", fields: { AS: varName(row.path) }, inputs: { PATH: path } };
      case "sweep": return { type: "wb_sweep", fields: Object.assign({ STEPS: 5, UNIT: NONE }, range("FROM", "TO")), inputs: { PATH: path, BODY: run } };
      case "seek": return { type: "wb_seek", fields: Object.assign({ UNIT: NONE, MEASURE: "" }, range("LO", "HI")), inputs: { PATH: path, BODY: run } };
      case "optvar": return { type: "wb_optvar", fields: range("LO", "HI"), inputs: { PATH: path } };
      case "optobj": return { type: "wb_optobj", fields: { DIR: "minimize" }, inputs: { PATH: path } };
      case "optcon": return { type: "wb_optcon", fields: { OP: "lower", VAL: Number(now.toPrecision(6)) }, inputs: { PATH: path } };
      default: return null;
    }
  };

  /** Where a new path block goes: right of the step it is meant for (anchor), else right of
   *  the main program's last step, level with its top; in reach of the program, not on it. */
  function beside(ws, anchor) {
    let blk = anchor;
    if (!blk) {
      blk = ws.getTopBlocks(false).find((x) => x.type === "wb_start");
      while (blk && blk.getNextBlock()) blk = blk.getNextBlock();
    }
    if (!blk) return place(ws);
    const r = blk.getBoundingRectangleWithoutChildren();
    return { x: r.right + 24, y: r.top };
  }

  WB.newReporter = function (ws, target, anchor) {
    let json;
    if (target.kind === "stream") {
      const comps = WB.data.flowsheet.components;
      json = { type: "wb_stream", fields: { S: target.name, P: comps.length ? STREAM_X : STREAM_T, C: comps[0] || NONE } };
    } else {
      json = { type: "wb_block", fields: { B: target.name } };
      json.fields.P = paramOpts({ getSourceBlock: () => ({ getFieldValue: () => target.name }) })[0][1];
    }
    return added(ws, Object.assign(json, beside(ws, anchor)));
  };

  /** A variable name for a read block: the object and the property, e.g. botm_molefrac_propyl1. */
  function varName(path) {
    const parts = String(path).split("\\").filter(Boolean);
    const obj = parts[2] || "x";
    const rest = parts.slice(4).filter((p) => p.toUpperCase() !== "MIXED");
    return [obj].concat(rest).join("_").toLowerCase().replace(/[^\w]+/g, "_").slice(0, 40);
  }

  /** An inspector row dropped on the workspace: an input becomes a set block holding its
   *  current value (in the field's current unit), a result becomes a read block. */
  WB.dropRow = function (ws, row, clientX, clientY) {
    if (row.unit || row.units) WB.data.units[row.path] = { unit: row.unit || null, units: row.units || [] };
    const path = pathJson(row.path);
    const json = row.input && row.enterable !== false
      ? { type: "wb_set", fields: { VALUE: String(row.value ?? ""), UNIT: NONE }, inputs: { PATH: path } }
      : { type: "wb_read", fields: { AS: varName(row.path) }, inputs: { PATH: path } };
    return added(ws, Object.assign(json, place(ws, clientX, clientY)));
  };

  /** A workspace in el. Zoom and Fit are the page's own (the capsule over the canvas, app-program.js),
   *  not Blockly's buttons, which sat over the blocks; the scrollbars are thin. */
  WB.init = function (el) {
    defineBlocks();
    Blockly.Scrollbar.scrollbarThickness = 8;         // read when a workspace makes its scrollbars
    const ws = Blockly.inject(el, {
      renderer: "zelos", theme: theme(), toolbox: WB.toolbox(), media: "blockly/media/", trashcan: true, sounds: false,
      plugins: { connectionChecker: "wb_write" },
      grid: { spacing: 24, length: 2, colour: "#cfd6e0", snap: false },
      zoom: { controls: false, wheel: true, startScale: 0.8, maxScale: 2, minScale: 0.3, scaleSpeed: 1.15 },
      move: { scrollbars: true, drag: true, wheel: false },
    });
    WB.watchNames(ws);
    return ws;
  };
})();
