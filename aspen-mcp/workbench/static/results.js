/* Results panel: a chart plus a table for every loop and optimize step of a tab's last
 * real run, and every table and plot statement's table or chart.
 *
 * The results are a row of chips, one line (it scrolls sideways when there are many): each
 * chip says what kind it is with its icon; the results one statement made together (a pinch
 * run: targets, streams, curves, matches) name only their part, and the panel opens on the
 * statement's first (its summary). The CSV button sits in the dock's bar (app-layout.js asks
 * R.exportShown). Chart and table sit side by side; a narrow panel shows one of them, with a
 * Chart | Table switch in the bar. A chart is drawn at its box's real size: a short one
 * drops its x axis title (under 120 px), then the x tick labels (under 90 px); tick labels
 * carry as many decimals as their spacing needs.
 *
 * A loop (sweep, until, repeat, seek) records a row per pass: its loop variable and every
 * program variable, each with its unit. The chart plots one chosen column against the loop
 * variable; passes whose run ended in errors (last_run_ok = 0) are a red cross.
 *
 * An optimize step shows its evaluations. With one objective: each evaluation against its
 * number, plus the best feasible value so far. With two or more: one objective against
 * another, the Pareto front joined up and the best compromise ringed. Its table is the
 * Pareto set. Every item exports to CSV; the table is the accessible view of the chart.
 *
 * A pinch run's match table follows the heat plan the flowsheet shows (opt.plan): only that
 * plan's matches, with a switch to show them all. Columns of words are left aligned.
 *
 * Where the block program left the model (results.state, a server with "finish"): one line
 * under the chips in plain words ("The model is back at its start values · the confirming run converged"), its inputs and values
 * on a click, the ones that could not be put back first and in red; a re-run refused (Aspen's
 * internal fault: never asked) says so in its own words and colour, the server's sentence in the
 * tooltip. A known refusal the server worded shows in the UI's words. A sweep's, design spec's
 * or optimization's result the server can write back (its "apply", a server with
 * "apply_point") gets an Apply button on each table row, Apply best point (a design spec:
 * its answer) at that line's end, and a point clicked on its chart becomes "Apply this
 * point"; each sends apply_point, and all are off while a program runs on the model (opt.apply.why).
 */
(function () {
  "use strict";

  // choice: tab id -> {item, y, ox, oy, view, all, pin, ms}; pending: tab id -> an apply sent
  // and not answered yet; onRefresh: redraw the shown tab's results (app-layout.js)
  const R = (window.WBR = { choice: {}, pending: {}, onExport: null, onRefresh: null });
  const SERIES = "#2a78d6", SECOND = "#eb6834", CRITICAL = "#d03b3b", INK = "#1f2a37", GRID = "#e6e9ef", SURFACE = "#ffffff", PIN = "#1d5fc4";
  const { esc, icon, num, sideways, stripView, t, tn } = WBA;
  const fmt = (v) => (v === null || v === undefined || Number.isNaN(v) ? "—"
    : typeof v === "number" ? Number(v.toPrecision(6)).toString() : String(v));
  /** A legend entry: its swatch and its words (the words in its tooltip too: a caption short of
   *  room shows the swatches only). */
  const key = (sw, text) => `<span class="res-key" title="${esc(text)}">${sw}<span class="kt">${esc(text)}</span></span>`;
  const XMARK = `<span class="x">✕</span>`;

  /** A tick label's width in px (style.css: 10.5 px, tabular figures, so each digit as a 0),
   *  measured by the browser's text engine (a canvas), each once; an estimate without one. */
  const widths = new Map();
  let pen = null;
  function tickWidth(s) {
    const k = String(s).replace(/[0-9]/g, "0");
    let w = widths.get(k);
    if (w !== undefined) return w;
    if (pen === null) { try { pen = document.createElement("canvas").getContext("2d") || false; } catch (e) { pen = false; } }
    if (pen) { pen.font = '10.5px "Segoe UI Variable Text", "Segoe UI", "Microsoft JhengHei UI", sans-serif'; w = pen.measureText(k).width; }
    else w = k.length * 6.2;
    if (widths.size > 2000) widths.clear();
    widths.set(k, w);
    return w;
  }

  function niceTicks(min, max, n) {
    if (!(isFinite(min) && isFinite(max))) return [0, 1];
    if (min === max) { const d = Math.abs(min) * 0.05 || 1; min -= d; max += d; }
    const raw = (max - min) / n, mag = Math.pow(10, Math.floor(Math.log10(raw))), e = raw / mag;
    const step = (e >= 7.5 ? 10 : e >= 3.5 ? 5 : e >= 1.5 ? 2 : 1) * mag;
    const out = [];
    for (let v = Math.floor(min / step) * step; v <= Math.ceil(max / step) * step + step / 2; v += step) {
      out.push(Number(v.toPrecision(12)));
    }
    return out;
  }
  /** Tick labels with the decimals their spacing needs (a step of 0.02: two), the same for
   *  every tick of an axis; very large or very small numbers in exponent form. */
  function tickFormat(ticks) {
    const step = ticks.length > 1 ? Math.abs(ticks[1] - ticks[0]) : Math.abs(ticks[0]) || 1;
    const big = Math.max(...ticks.map((v) => Math.abs(v)));
    const clean = (v) => (Math.abs(v) < step * 1e-6 ? 0 : v);
    if (big >= 1e6 || (big > 0 && big < 1e-3)) {
      const d = Math.max(0, Math.min(6, Math.ceil(Math.log10(big / step) - 1e-9)));
      return (v) => (clean(v) === 0 ? "0" : clean(v).toExponential(d).replace("e+", "e"));
    }
    const d = step >= 1 ? 0 : Math.min(10, Math.ceil(-Math.log10(step) - 1e-9));
    return (v) => clean(v).toFixed(d);
  }

  // ---------------------------------------------------------------- one chart, any marks
  const cross = (cx, cy) => `<path d="M${cx - 4},${cy - 4} L${cx + 4},${cy + 4} M${cx + 4},${cy - 4} L${cx - 4},${cy + 4}" stroke="${SURFACE}" stroke-width="5"/>
      <path d="M${cx - 4},${cy - 4} L${cx + 4},${cy + 4} M${cx + 4},${cy - 4} L${cx - 4},${cy + 4}" stroke="${CRITICAL}" stroke-width="2.2" stroke-linecap="round"/>`;

  /** spec: {points: [{x, y, mark: dot|hi|x|base|none, tip, ring?, pick?, pin?}], lines: [{pts, color, step?, dash?}],
   *  vlines?: [{x, color, dash?}], xdom?: [lo, hi], ydom?: [lo|null, hi|null], xlabel, yunit,
   *  byX, ref?: {y}}. y null on a "base" point pins it to the axis (a failed evaluation); a
   *  "none" point is not drawn but answers the hover; ref draws a horizontal target line (the
   *  legend names it); a domain given fixes that axis, and lines are clipped to the plot.
   *  A point with a pick can be chosen by a click (spec.onPick(pick)); the chosen one (pin) is
   *  ringed in dashes.
   *  Returns {byX, draw(W, H)}: drawn at the box's real size, so text is never stretched. */
  function chart(spec) {
    return { byX: spec.byX, draw: (W, H) => Object.assign(drawChart(spec, W, H), { onPick: spec.onPick || null }) };
  }
  let clipN = 0;

  /** Ticks over [lo, hi]; a fixed domain keeps its ends, an automatic one rounds them out. */
  function axis(lo, hi, n, fixed) {
    if (!fixed) { const t = niceTicks(lo, hi, n); return { ticks: t, a: t[0], b: t[t.length - 1] }; }
    return { ticks: niceTicks(lo, hi, n).filter((v) => v >= lo - 1e-9 && v <= hi + 1e-9), a: lo, b: hi };
  }

  /** The chart at W × H px. Under 120 px tall it drops the x axis title, under 90 px the x
   *  tick labels too, and keeps two y ticks; a narrow one takes fewer x ticks. Its margins
   *  make room for the widest y tick label and half the last x tick label, so no text is cut
   *  at the chart's edges; the y unit starts at its left edge. */
  function drawChart(spec, W, H) {
    const noTitle = H < 120, noTicks = H < 90;
    const plotted = spec.points.filter((p) => num(p.x) && (num(p.y) || p.mark === "base"));
    const ys = plotted.filter((p) => num(p.y)).map((p) => p.y).concat(...spec.lines.map((l) => l.pts.map((p) => p.y).filter(num)))
      .concat(spec.ref && num(spec.ref.y) ? [spec.ref.y] : []);
    const xs = plotted.map((p) => p.x).concat(...spec.lines.map((l) => l.pts.map((p) => p.x).filter(num)));
    const xd = spec.xdom || [], yd = spec.ydom || [];
    const xfix = num(xd[0]) && num(xd[1]) && xd[0] !== xd[1];
    const ylo = num(yd[0]) ? yd[0] : ys.length ? Math.min(...ys) : 0, yhi = num(yd[1]) ? yd[1] : ys.length ? Math.max(...ys) : 1;
    const xa = axis(xfix ? Math.min(xd[0], xd[1]) : Math.min(...xs), xfix ? Math.max(xd[0], xd[1]) : Math.max(...xs), W < 360 ? 3 : 5, xfix);
    const ya = axis(Math.min(ylo, yhi), Math.max(ylo, yhi), noTitle ? 2 : 4, num(yd[0]) && num(yd[1]) && yd[0] !== yd[1]);
    const xt = xa.ticks, yt = ya.ticks, x0 = xa.a, x1 = xa.b, y0 = ya.a, y1 = ya.b;
    const fx = tickFormat(xt), fy = tickFormat(yt);
    const M = { l: Math.max(62, Math.ceil(Math.max(0, ...yt.map((v) => tickWidth(fy(v))))) + 12),
                r: noTicks || !xt.length ? 16 : Math.max(16, Math.ceil(tickWidth(fx(xt[xt.length - 1])) / 2) + 3),
                t: noTicks ? 20 : 22, b: noTicks ? 10 : noTitle ? 22 : 34 };
    const sx = (v) => M.l + ((v - x0) / (x1 - x0 || 1)) * (W - M.l - M.r);
    const sy = (v) => H - M.b - ((v - y0) / (y1 - y0 || 1)) * (H - M.t - M.b);
    const clip = `rc${++clipN}`;
    const parts = [`<clipPath id="${clip}"><rect x="${M.l}" y="${M.t}" width="${W - M.l - M.r}" height="${H - M.t - M.b}"/></clipPath>`];
    // every gridline; a label on every one, or every other (…) where they would sit closer than 13 px
    const every = Math.max(1, Math.ceil(13 / ((H - M.t - M.b) / Math.max(1, yt.length - 1))));
    yt.forEach((v, i) => parts.push(`<line x1="${M.l}" x2="${W - M.r}" y1="${sy(v)}" y2="${sy(v)}" stroke="${GRID}" stroke-width="1"/>`
      + (i % every ? "" : `<text x="${M.l - 6}" y="${sy(v) + 4}" class="tk" text-anchor="end">${esc(fy(v))}</text>`)));
    if (!noTicks) xt.forEach((v) => parts.push(`<text x="${sx(v)}" y="${H - M.b + 16}" class="tk" text-anchor="middle">${esc(fx(v))}</text>`));
    parts.push(`<line x1="${M.l}" x2="${W - M.r}" y1="${H - M.b}" y2="${H - M.b}" stroke="#c9ced8" stroke-width="1"/>`);
    if (!noTitle) parts.push(`<text x="${(M.l + W - M.r) / 2}" y="${H - 4}" class="ax" text-anchor="middle">${esc(spec.xlabel)}</text>`);
    if (spec.yunit) parts.push(`<text x="4" y="${noTicks ? 12 : M.t - 7}" class="ax" text-anchor="start">${esc(spec.yunit)}</text>`);
    if (spec.ref && num(spec.ref.y)) {
      const ry = sy(spec.ref.y);
      parts.push(`<line x1="${M.l}" x2="${W - M.r}" y1="${ry}" y2="${ry}" stroke="${INK}" stroke-width="1" opacity=".55"/>`);
    }
    const dash = (l) => (l.dash ? ' stroke-dasharray="6 4"' : "");
    parts.push(`<g clip-path="url(#${clip})">`);
    (spec.vlines || []).forEach((v) => {
      if (num(v.x)) parts.push(`<line x1="${sx(v.x)}" x2="${sx(v.x)}" y1="${M.t}" y2="${H - M.b}" stroke="${v.color}" stroke-width="2"${dash(v)}/>`);
    });
    spec.lines.forEach((l) => {
      let d = "", prev = null;
      l.pts.forEach((p) => {
        if (!num(p.x) || !num(p.y)) { prev = null; return; }          // a gap where a point has no value
        const X = sx(p.x).toFixed(1), Y = sy(p.y).toFixed(1);
        d += prev ? (l.step ? `L${X},${prev[1]} L${X},${Y} ` : `L${X},${Y} `) : `M${X},${Y} `;
        prev = [X, Y];
      });
      if (d) parts.push(`<path d="${d}" fill="none" stroke="${l.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"${dash(l)}/>`);
    });
    parts.push("</g>");
    plotted.forEach((p) => {
      p.px = sx(p.x);
      p.py = num(p.y) ? Math.min(H - M.b, Math.max(M.t, sy(p.y))) : H - M.b;
      if (p.mark === "none") return;
      if (p.mark === "x" || p.mark === "base") parts.push(cross(p.px, p.py));
      else parts.push(`<circle cx="${p.px}" cy="${p.py}" r="${p.mark === "hi" ? 5 : 4}" fill="${p.mark === "hi" ? SECOND : SERIES}" stroke="${SURFACE}" stroke-width="2"/>`);
      if (p.ring) parts.push(`<circle cx="${p.px}" cy="${p.py}" r="9" fill="none" stroke="${INK}" stroke-width="2"/>`);
      if (p.pin) parts.push(`<circle cx="${p.px}" cy="${p.py}" r="12" fill="none" stroke="${PIN}" stroke-width="2" stroke-dasharray="4 3"/>`);
    });
    parts.push(`<line class="xh" x1="0" x2="0" y1="${M.t}" y2="${H - M.b}" stroke="#8a94a3" stroke-width="1" visibility="hidden"/>
      <rect class="hit" x="${M.l}" y="${M.t}" width="${W - M.l - M.r}" height="${H - M.t - M.b}" fill="transparent"/>`);
    const pickable = !!spec.onPick && plotted.some((p) => p.pick !== undefined);
    return { svg: `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" class="res-chart${pickable ? " pick" : ""}">${parts.join("")}</svg>`,
             pts: plotted, byX: spec.byX, W, H };
  }

  /** The point nearest the pointer, in its tooltip (and the crosshair on it, by x). Once a
   *  frame at most; the chart's box is read when the pointer comes in, the tooltip's size once
   *  each time it says something else: nothing is measured on a plain move. A click chooses
   *  the point nearest it, when it can be chosen (c.onPick). */
  function hover(el, c) {
    const { W, H } = c;
    const svg = el.querySelector(".res-chart"), tip = el.querySelector(".res-tip");
    if (!svg) return;
    const xh = svg.querySelector(".xh"), hit = svg.querySelector(".hit");
    let r = null, at = null, frame = 0, cur = null;
    const nearest = () => {
      if (!r) r = svg.getBoundingClientRect();
      const mx = ((at.x - r.left) / r.width) * W, my = ((at.y - r.top) / r.height) * H;
      let best = null, bd = Infinity;
      c.pts.forEach((p) => {
        const d = c.byX ? Math.abs(p.px - mx) : Math.hypot(p.px - mx, p.py - my);
        if (d < bd) { bd = d; best = p; }
      });
      return best;
    };
    const show = () => {
      frame = 0;
      if (!at) return;
      const best = nearest();
      if (!best || best === cur) return;
      cur = best;
      if (c.byX) { xh.setAttribute("x1", best.px); xh.setAttribute("x2", best.px); xh.setAttribute("visibility", "visible"); }
      tip.innerHTML = best.tip;
      tip.classList.remove("hidden");
      const tw = tip.offsetWidth, th = tip.offsetHeight;
      const left = (best.px / W) * r.width, top = (best.py / H) * r.height;
      tip.style.left = Math.max(0, Math.min(left + 12, r.width - tw - 4)) + "px";
      tip.style.top = Math.max(top - th - 8, 0) + "px";
    };
    hit.addEventListener("mouseenter", () => { r = svg.getBoundingClientRect(); });
    if (c.onPick) hit.addEventListener("click", (ev) => {
      at = { x: ev.clientX, y: ev.clientY };
      const p = nearest();
      if (p && p.pick !== undefined) c.onPick(p.pick);
    });
    hit.addEventListener("mousemove", (ev) => {
      at = { x: ev.clientX, y: ev.clientY };
      if (!frame) frame = requestAnimationFrame(show);
    });
    hit.addEventListener("mouseleave", () => {
      cancelAnimationFrame(frame);
      frame = 0;
      r = at = cur = null;
      xh.setAttribute("visibility", "hidden");
      tip.classList.add("hidden");
    });
  }

  // ---------------------------------------------------------------- loop tables
  const failed = (row) => row.last_run_ok === 0;
  const unitOf = (tb, col) => ((tb.units || {})[col]) || (col === tb.var ? tb.unit : null) || "";
  const withUnit = (tb, col) => (unitOf(tb, col) ? `${col} [${unitOf(tb, col)}]` : col);
  /** A path in words (labels.js): "MEOHCOL › Reflux ratio" (in Chinese, our gloss beside it). */
  const pathWords = (p) => WBL.say(p);
  /** A sweep's or design spec's loop variable (sweep_value) is shown as the input it steps,
   *  in words; the CSV keeps its name. Any other column as it is. */
  const swept = (tb) => ["sweep", "seek"].includes(tb.kind || "sweep") && !!tb.path;
  // (a chart or table made from a loop's results carries the loop's path too; a table column
  // keyed by its path -- a picked property, {row} for each row -- is named by its field)
  const colName = (tb, col) => (col === tb.var && tb.path && (swept(tb) || ["plot", "table"].includes(tb.kind)) ? pathWords(tb.path)
    : (tb.paths || {})[col] ? pathWords(tb.paths[col])     // (a variable a read set: what it read, in words)
    : /^\\Data\\/.test(col) ? WBL.text(WBL.of(col), "name") : col);
  const shownUnit = (tb, col) => (unitOf(tb, col) ? `${colName(tb, col)} [${unitOf(tb, col)}]` : colName(tb, col));
  /** A result's title: a sweep names the input it steps, a design spec that and its goal, in
   *  words; a loop until its condition; a table, chart or repeat its own label. */
  const kindTitle = (tb) => {
    const kind = tb.kind || "sweep";
    if (["repeat", "table", "plot", "until"].includes(kind)) return t("res_kind_" + kind, tb.label || "");
    const what = tb.path ? pathWords(tb.path) : pathWords(tb.label);
    const goal = kind === "seek" && tb.label && tb.label !== tb.path ? String(tb.label) : "";
    return t("res_kind_" + kind, goal ? `${what} → ${goal}` : what);
  };
  /** A column of words (its first value is text that is no number): left aligned. */
  const isText = (rows, col) => {
    const v = rows.map((r) => r[col]).find((x) => x !== null && x !== undefined && x !== "");
    return typeof v === "string" && !isFinite(Number(v));
  };

  /** rowCls(row, i): a row's class ("bad": its run failed; "pl": in the heat plan shown; "pin":
   *  the point chosen on the chart). apCell(row, i): a first column of Apply buttons. */
  function tableHtml(tb, rowCls, rows, apCell) {
    const list = rows || tb.rows, tx = new Set(tb.columns.filter((col) => isText(tb.rows, col)));
    const cls = (col) => (tx.has(col) ? ' class="tx"' : "");
    const head = (apCell ? `<th class="ap"></th>` : "") + tb.columns.map((col) => `<th${cls(col)}${colName(tb, col) !== col ? ` title="${esc(col)}"` : ""}>${esc(colName(tb, col))}${unitOf(tb, col) ? ` <small>[${esc(unitOf(tb, col))}]</small>` : ""}</th>`).join("");
    const body = list.map((r, i) => { const c = rowCls ? rowCls(r, i) : ""; return `<tr${c ? ` class="${c}"` : ""}>`
      + (apCell ? `<td class="ap">${apCell(r, i)}</td>` : "") + `${tb.columns.map((col) =>
      `<td${cls(col)}>${col === "last_run_ok" && failed(r) ? `<span class="x">✕</span> 0` : esc(fmt(r[col]))}</td>`).join("")}</tr>`; }).join("");
    return `<table class="res-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }
  const tableCsv = (tb) => [tb.columns.map((col) => withUnit(tb, col))].concat(tb.rows.map((r) => tb.columns.map((col) => r[col])));

  /** The rows of a pinch match table that belong to plan k (0 based): in each pinch region,
   *  its k-th alternative, or its last where it has fewer (app-heat.js, heatPlan, draws the same).
   *  The rows come region by region (its first column), each alternative numbered (its
   *  second); a row without a number (a region with no match) always belongs. */
  function planRows(tb, k) {
    const [rc, oc] = tb.columns, regions = (tb.heat && tb.heat.regions) || [];
    let ri = -1, prev;
    return tb.rows.filter((r) => {
      if (ri < 0 || r[rc] !== prev) { ri++; prev = r[rc]; }
      const n = ((regions[ri] || {}).alts || []).length;
      return r[oc] === null || r[oc] === undefined || !n || Number(r[oc]) === Math.min(k, n - 1) + 1;
    });
  }

  /** A table statement's table: no chart, the rows as they are. A pinch match table while
   *  the flowsheet shows a heat plan (plan: its index): that plan's rows, or all of them with
   *  the plan's marked, and the switch between the two. */
  function plainView(tb, ch, plan) {
    if (!tb.heat || plan === null || plan === undefined) {
      return { count: tn("res_rows", tb.rows.length), cap: "", chart: null, table: tableHtml(tb), csv: tableCsv(tb) };
    }
    const mine = planRows(tb, plan), all = !!ch.all, set = new Set(mine);
    const sw = `<button class="res-pl${all ? "" : " on"}" data-r="all" title="${esc(t("tip_res_plan", plan + 1))}">`
      + `${icon("flame")}<span class="bt">${esc(all ? t("res_plan_only", plan + 1) : t("res_plan_all", tb.rows.length))}</span></button>`;
    return { count: tn("res_rows", all ? tb.rows.length : mine.length), extra: sw, cap: "", chart: null, csv: tableCsv(tb),
      table: all ? tableHtml(tb, (r) => (set.has(r) ? "pl" : "")) : tableHtml(tb, null, mine) };
  }

  // curves without a colour of their own take these, in order
  const PALETTE = [SERIES, SECOND, "#1d9a6c", "#8b5cf6", "#c28a00", "#8a94a3"];
  const swatch = (color, dash) => `<i class="sw line" style="background:${dash
    ? `repeating-linear-gradient(90deg, ${color} 0 4px, transparent 4px 7px)` : color}"></i>`;

  /** A plot statement's chart: its curves and vertical lines on the axes it asked for. */
  function plotView(tb) {
    let k = 0;
    const colour = (c) => c || PALETTE[k++ % PALETTE.length];
    const lines = (tb.lines || []).map((ln) => ({ pts: ln.pts.map(([x, y]) => ({ x, y })), color: colour(ln.color), dash: ln.dash, label: colName(tb, ln.label) }));
    const vlines = (tb.vlines || []).map((v) => ({ x: v.x, color: v.color || INK, dash: v.dash, label: v.label }));
    const series = tb.columns.filter((c) => c !== tb.var);
    const hoverAt = tb.rows.map((r) => ({ x: r[tb.var], y: series.map((c) => r[c]).find(num), mark: "none",
      tip: `<b>${esc(colName(tb, tb.var))} = ${esc(fmt(r[tb.var]))}</b>` + series.filter((c) => num(r[c]))
        .map((c) => `<br>${esc(colName(tb, c))} = ${esc(fmt(r[c]))}`).join("") }));
    const c = chart({ points: hoverAt, lines, vlines, xdom: tb.xrange, ydom: tb.yrange,
      xlabel: tb.xlabel || shownUnit(tb, tb.var), yunit: tb.ylabel || unitOf(tb, series[0]) || "", byX: true });
    const named = new Set();                      // a curve drawn in pieces is named once
    const legend = lines.concat(vlines).filter((l) => l.label && !named.has(l.label) && named.add(l.label))
      .map((l) => key(swatch(l.color, l.dash), l.label)).join("");
    return { count: tn("res_points", tb.rows.length), cap: legend, chart: c, table: tableHtml(tb), csv: tableCsv(tb) };
  }

  function tableView(tb, ch, plan, A) {
    if (tb.kind === "table") return plainView(tb, ch, plan);
    if (tb.kind === "plot") return plotView(tb);
    // a sweep's or design spec's row can be written back into the model (apply_point)
    const ap = A.can(tb) && swept(tb), pinned = (i) => ap && !!ch.pin && ch.pin.key === tb.id && ch.pin.pick === i;
    const input = (r) => `${colName(tb, tb.var)} = ${fmt(r[tb.var])}${unitOf(tb, tb.var) ? " " + unitOf(tb, tb.var) : ""}`;
    const cols = tb.columns.filter((c) => c !== tb.var && c !== "last_run_ok");
    // a design spec opens on its measure, which is what it is about
    const first = tb.kind === "seek" && cols.includes(tb.measure) ? tb.measure : cols[0];
    const y = cols.includes(ch.y) ? ch.y : first;
    const tipFor = (r) => `<b>${esc(colName(tb, tb.var))} = ${esc(fmt(r[tb.var]))} ${esc(unitOf(tb, tb.var))}</b><br>`
      + `${esc(colName(tb, y))} = ${esc(fmt(r[y]))} ${esc(unitOf(tb, y))}` + (failed(r) ? `<br><span class="x">✕</span> ${esc(t("res_failed"))}` : "");
    // a design spec tries values out of order: draw the curve sorted, the target, and ring the answer
    const seek = tb.kind === "seek";
    const line = tb.rows.map((r) => ({ x: r[tb.var], y: r[y] }));
    if (seek) line.sort((a, b) => a.x - b.x);
    const c = y ? chart({
      points: tb.rows.map((r, i) => ({ x: r[tb.var], y: r[y], mark: failed(r) ? "x" : "dot", tip: tipFor(r) + (ap ? PICK() : ""),
        ring: seek && num(tb.answer) && r[tb.var] === tb.answer, pick: ap ? i : undefined, pin: pinned(i) })),
      lines: [{ pts: line, color: SERIES }],
      ref: seek && y === tb.measure ? { y: tb.target } : null,
      xlabel: shownUnit(tb, tb.var), yunit: unitOf(tb, y), byX: true, onPick: ap ? A.onPick(tb.id) : null,
    }) : null;
    const controls = cols.length ? `<label>${esc(t("res_y"))} <select data-r="y">${cols.map((col) =>
      `<option value="${esc(col)}"${col === y ? " selected" : ""}>${esc(shownUnit(tb, col))}</option>`).join("")}</select></label>` : "";
    let legend = tb.rows.some(failed) ? key(XMARK, t("res_failed")) : "";
    if (seek && y === tb.measure && num(tb.target)) legend += key(`<i class="sw ref"></i>`, t("res_target", fmt(tb.target)));
    if (seek && num(tb.answer)) legend += key(`<i class="sw ring"></i>`, t("res_answer", fmt(tb.answer), unitOf(tb, tb.var)));
    const pin = ap && ch.pin && ch.pin.key === tb.id && tb.rows[ch.pin.pick] ? t("ap_pin_row", ch.pin.pick + 1) : null;
    const best = ap && seek && num(tb.answer)
      ? { label: t("ap_answer"), tip: t("tip_ap_answer", `${fmt(tb.answer)}${unitOf(tb, tb.var) ? " " + unitOf(tb, tb.var) : ""}`) } : null;
    return { count: tn("res_points", tb.rows.length), cap: controls + legend, chart: c, pin, best, csv: tableCsv(tb),
      table: tableHtml(tb, (r, i) => [failed(r) ? "bad" : "", pinned(i) ? "pin" : ""].filter(Boolean).join(" "), null,
        ap ? (r, i) => A.button("r" + i, t("ap_row"), t("tip_ap_row", input(r)), "res-apr") : null) };
  }

  // ---------------------------------------------------------------- optimize results
  function optView(o, ch, A) {
    const objs = o.objectives, vars = o.variables;
    const oname = (b) => (b.unit ? `${b.name} [${b.unit}]` : b.name);
    const ok = o.evals.filter((e) => e.ok).length;
    // a point can be written back into the model (apply_point): a Pareto row by its index, an
    // evaluation on the chart as {eval: index}
    const ap = A.can(o), mine = ap && ch.pin && ch.pin.key === o.id ? ch.pin.pick : undefined;
    const isPin = (pick) => mine !== undefined && (typeof pick === "object" ? typeof mine === "object" && mine.eval === pick.eval : mine === pick);
    const hint = ap ? PICK() : "";
    let c, legend;
    if (objs.length === 1) {
      const dir = objs[0].direction === "maximize" ? 1 : -1;
      let best = null;
      const trail = o.evals.map((e, i) => {
        const v = e.f[0];
        if (e.ok && num(v) && (best === null || dir * (v - best) > 0)) best = v;
        return { x: i + 1, y: best };
      });
      c = chart({
        points: o.evals.map((e, i) => ({ x: i + 1, y: e.f[0], mark: e.ok ? "dot" : num(e.f[0]) ? "x" : "base",
          tip: `<b>#${i + 1}</b><br>${esc(objs[0].name)} = ${esc(fmt(e.f[0]))} ${esc(objs[0].unit || "")}`
            + vars.map((v, k) => `<br>${esc(v.name)} = ${esc(fmt(e.x[k]))} ${esc(v.unit || "")}`).join("")
            + (e.ok ? "" : `<br><span class="x">✕</span> ${esc(t("res_infeasible"))}`) + hint,
          pick: ap ? { eval: i } : undefined, pin: isPin({ eval: i }) })),
        lines: [{ pts: trail, color: SECOND, step: true }],
        xlabel: t("res_eval"), yunit: objs[0].unit || "", byX: true, onPick: ap ? A.onPick(o.id) : null,
      });
      legend = key(`<i class="sw dot"></i>`, t("res_all")) + key(`<i class="sw line"></i>`, t("res_best"));
    } else {
      const ix = Math.min(ch.ox ?? 0, objs.length - 1), iy = Math.min(ch.oy ?? 1, objs.length - 1);
      const tipFor = (x, f, label) => `<b>${esc(label)}</b>`
        + objs.map((b, k) => `<br>${esc(b.name)} = ${esc(fmt(f[k]))} ${esc(b.unit || "")}`).join("")
        + vars.map((v, k) => `<br>${esc(v.name)} = ${esc(fmt(x[k]))} ${esc(v.unit || "")}`).join("");
      const front = o.pareto.map((p, k) => ({ p, k })).sort((a, b) => a.p.f[ix] - b.p.f[ix]);
      c = chart({
        points: o.evals.map((e, i) => ({ e, i })).filter(({ e }) => num(e.f[ix]) && num(e.f[iy])).map(({ e, i }) => ({
          x: e.f[ix], y: e.f[iy], mark: e.ok ? "dot" : "x", tip: tipFor(e.x, e.f, e.ok ? t("res_all") : t("res_infeasible")) + hint,
          pick: ap ? { eval: i } : undefined, pin: isPin({ eval: i }) }))
          .concat(front.map(({ p, k }) => ({ x: p.f[ix], y: p.f[iy], mark: "hi", ring: p.best,
            tip: tipFor(p.x, p.f, p.best ? t("res_compromise") : t("res_pareto")) + hint, pick: ap ? k : undefined, pin: isPin(k) }))),
        lines: [{ pts: front.map(({ p }) => ({ x: p.f[ix], y: p.f[iy] })), color: SECOND }],
        xlabel: oname(objs[ix]), yunit: objs[iy].unit || "", byX: false, onPick: ap ? A.onPick(o.id) : null,
      });
      const pick = (key, cur) => `<select data-r="${key}">${objs.map((b, k) =>
        `<option value="${k}"${k === cur ? " selected" : ""}>${esc(oname(b))}</option>`).join("")}</select>`;
      legend = `<label>${esc(t("res_x"))} ${pick("ox", ix)}</label><label>${esc(t("res_y"))} ${pick("oy", iy)}</label>`
        + key(`<i class="sw dot"></i>`, t("res_all")) + key(`<i class="sw hi"></i>`, t("res_pareto")) + key(`<i class="sw ring"></i>`, t("res_compromise"));
    }
    if (o.evals.some((e) => !e.ok)) legend += key(XMARK, t("res_infeasible"));
    const cols = vars.map((v) => (v.unit ? `${v.name} [${v.unit}]` : v.name)).concat(objs.map(oname));
    const head = (ap ? `<th class="ap"></th>` : "") + cols.map((h) => `<th>${esc(h)}</th>`).join("") + "<th></th>";
    // an Apply button's tooltip names the inputs it writes (the first three, then "…")
    const inputs = (x) => vars.slice(0, 3).map((v, k) => `${v.name} = ${fmt(x[k])}${v.unit ? " " + v.unit : ""}`).join(", ") + (vars.length > 3 ? ", …" : "");
    const body = o.pareto.map((p, k) => `<tr${isPin(k) ? ' class="pin"' : ""}>`
      + (ap ? `<td class="ap">${A.button("r" + k, t("ap_row"), t("tip_ap_row", inputs(p.x)), "res-apr")}</td>` : "")
      + `${p.x.concat(p.f).map((v) => `<td>${esc(fmt(v))}</td>`).join("")}<td>${p.best ? "★" : ""}</td></tr>`).join("");
    const csv = [["eval"].concat(cols, ["feasible"])].concat(o.evals.map((e, i) => [i + 1].concat(e.x, e.f, [e.ok ? 1 : 0])));
    const pin = mine === undefined ? null : typeof mine === "object" ? (o.evals[mine.eval] ? t("ap_pin_eval", mine.eval + 1) : null)
      : o.pareto[mine] ? t("ap_pin_row", mine + 1) : null;
    return { count: t("res_feasible", ok, o.evals.length), cap: legend, chart: c, csv, pin,
      best: ap && ok ? { label: t("ap_best"), tip: t("tip_ap_best") } : null,
      table: `<table class="res-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>` };
  }

  // ---------------------------------------------------------------- where the model is; applying a point
  /** A chart tooltip's last line on a point that can be chosen. */
  const PICK = () => `<br><small class="pk">${esc(t("res_pick"))}</small>`;
  const KEPT = ["sweep", "seek", "opt_last", "opt_best", "set"];
  const KINDS = ["restored", "kept", "mixed", "partial", "applied"];
  const PEND_MS = 90000;             // an apply unanswered this long stops holding the buttons
  let msAnim = null;                 // the tab whose details just opened: they slide in, once
  const valueOf = (e) => (e.value === null || e.value === undefined ? "—" : `${fmt(e.value)}${e.unit ? " " + e.unit : ""}`);

  /** A refusal the server worded, in the UI's own words where it is a known one (diag.js's
   *  WBD.refusal: busy, paused, read-only, inputs incomplete, Aspen's internal fault), else null. */
  const refusal = (s) => (window.WBD && WBD.refusal ? WBD.refusal(s) : null);
  /** results.state in words: {head, run, runTip, level ("" | "warn" | "bad" | "refused"), ic, rows,
   *  text}. A point applied names its result and row; a program's end, what it did with each input
   *  it changed. The rows put the inputs that could not be put back first; text is the server's
   *  own words, kept for when something went wrong (they carry the detail). A re-run refused
   *  (Aspen never asked: its internal fault) is no failed run: its own words and colour, the
   *  server's sentence in the tooltip, not in the details. */
  function stateView(st, items, title) {
    const applied = st.source !== undefined && st.source !== null && Array.isArray(st.values);
    const kept = st.kept || [], lost = st.failed || [];
    let head;
    if (applied) {
      const it = items.find((i) => i.key === st.source), name = it ? title(it) : String(st.source);
      const r = st.row;
      const what = r === "best" ? t(it && !it.opt ? "ms_ap_answer" : "ms_ap_best", name)
        : r && typeof r === "object" && num(r.eval) ? t("ms_ap_eval", r.eval + 1, name)
        : num(r) ? t("ms_ap_row", r + 1, name) : name;
      head = t(st.kind === "partial" ? "ms_ap_partial" : "ms_applied", what);
    } else if (st.kind === "restored") head = t("ms_restored");
    else if (st.kind === "kept") {
      const whys = [...new Set(kept.map((k) => k.why))];
      head = whys.length === 1 && KEPT.includes(whys[0]) ? t("ms_kept_" + whys[0]) : t("ms_kept");
    } else if (st.kind === "mixed") head = t("ms_mixed");
    else if (st.kind === "partial") head = tn("ms_partial", lost.length);
    else head = t("ms_where_unknown");
    const refused = st.run === "refused";
    const level = st.kind === "partial" || !KINDS.includes(st.kind) || st.run === "error" ? "bad" : refused ? "refused" : st.run === "warn" ? "warn" : "";
    const known = (w) => { const r = refusal(w); return r ? r.words : String(w || ""); };
    const rows = lost.map((e) => ({ tag: t("ms_t_failed"), bad: true, path: e.path,
      val: e.value === null || e.value === undefined ? "" : t("ms_start", valueOf(e)),
      why: e.why === "empty" ? t("ms_why_empty") : e.why === "gone" ? t("ms_why_gone") : known(e.why),
      whyTip: ["empty", "gone"].includes(e.why) || !refusal(e.why) ? "" : String(e.why) }))
      .concat((applied ? st.values : []).map((e) => ({ tag: t("ms_t_applied"), path: e.path, val: valueOf(e) })))
      .concat((st.restored || []).map((e) => ({ tag: t("ms_t_restored"), path: e.path, val: valueOf(e) })))
      .concat(kept.map((e) => ({ tag: t(KEPT.includes(e.why) ? "ms_t_" + e.why : "ms_t_set"), path: e.path, val: valueOf(e) })));
    // refused: why, in the UI's words ("Not re-run: Aspen internal fault"); the server's sentence in the tooltip
    const why = refused ? refusal(st.text) : null;
    const run = refused ? (why ? t("ms_run_refused", why.words) : t("ms_run_refused0"))
      : { ok: t("ms_run_ok"), warn: t("ms_run_warn"), error: t("ms_run_error") }[st.run] || "";
    // the details' words: a known refusal the server quoted for an input reads as the UI says it (the
    // whole text as it came in their tooltip)
    const said = String(st.text || "");
    let text = level && level !== "refused" ? said : "";
    rows.forEach((r) => { if (text && r.whyTip) text = text.split(r.whyTip).join(r.why); });
    if (text && why) text = text.replace(/Cannot (?:run|reinitialize) simulation '[^']*':[^）)]*/g, why.words);   // (a refused re-run quoted)
    return { head, level, rows, run, runTip: refused ? said : "", text, textTip: text && text !== said ? said : "",
      ic: level === "refused" ? "info" : level ? "warn" : st.kind === "restored" ? "undo" : "check" };
  }

  // ---------------------------------------------------------------- panel
  const csvCell = (v) => (v === null || v === undefined ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
  /** The results one statement made together share its id before a colon ("s1:targets"). */
  const group = (key) => { const s = String(key), i = s.indexOf(":"); return i > 0 ? s.slice(0, i) : null; };
  /** Narrower than NARROW, or shorter than SHORT, the panel shows the chart or the table, not
   *  both; a short one opens on the table (its rows read in little room, a chart does not). */
  const NARROW = 700, SHORT = 170;

  /** Render a tab's results into el. Re-renders only when the data, a choice, the panel's
   *  size or the heat plan shown (opt.plan: its index, or null) changed. The data is told by
   *  its shape, the run it came from (opt.ver) and the shown item's first and last rows: a
   *  rerun makes the same tables, of the same sizes, with new numbers.
   *  opt.apply (app-layout.js): {why: why a point cannot be applied now ("" when it can), stamp: what changes when the server answers,
   *  send(source, row | "best" | {eval})}. */
  R.render = function (el, tab, results, opt) {
    const plan = opt && opt.plan !== undefined ? opt.plan : null;
    const items = (results.tables || []).map((x) => ({ x, key: x.id, opt: false }))
      .concat((results.opts || []).map((x) => ({ x, key: x.id, opt: true })));
    if (!items.length) {
      el.innerHTML = `<div class="hint">${esc(t("res_none"))}</div>`;
      el.dataset.sig = el.dataset.frame = "";
      el.wbExport = el.wbParts = null;
      return;
    }
    const ch = (R.choice[tab.id] = R.choice[tab.id] || {});
    // where the model is, and applying a point: a point sent waits for the server's answer (a
    // message or a new state), a point chosen on a chart belongs to the run it was chosen in
    const ap = opt && opt.apply ? opt.apply : null;
    const st = ap && results.state && typeof results.state === "object" ? results.state : null;
    const stSig = JSON.stringify(results.state || null);
    let pend = R.pending[tab.id] || null;
    if (pend && (!ap || pend.stamp !== ap.stamp || pend.st !== stSig || Date.now() > pend.until)) { delete R.pending[tab.id]; pend = null; }
    if (ch.pin && (ch.pin.ver !== (opt && opt.ver) || !items.some((i) => i.key === ch.pin.key))) delete ch.pin;
    const A = {
      can: (x) => !!(ap && x.apply),
      /** An Apply button (data-ap: "r<i>" a table row, "best", "pin"): off, saying why, while a
       *  point cannot be applied or one sent waits for its answer; that one reads "Applying…". */
      button: (key, label, tip, cls, ic) => {
        const why = (ap && ap.why) || (pend ? t("tip_ap_pending") : "");
        return `<button class="${cls}" data-ap="${key}"${why ? " disabled" : ""} title="${esc(why || tip)}">${ic ? icon(ic) : ""}`
          + `<span class="bt">${esc(pend && pend.what === key ? t("ap_pending") : label)}</span></button>`;
      },
      /** A click on a chart point chooses it, a second click on it lets it go. */
      onPick: (key) => (pick) => {
        if (ch.pin && ch.pin.key === key && JSON.stringify(ch.pin.pick) === JSON.stringify(pick)) delete ch.pin;
        else ch.pin = { key, pick, ver: opt && opt.ver };
        R.render(el, tab, results, opt);
      },
    };
    // none chosen: the newest, or the first of what its statement made (a pinch run: targets)
    const last = items[items.length - 1], g = group(last.key);
    const it = items.find((i) => i.key === ch.item) || (g && items.find((i) => group(i.key) === g)) || last;
    const size = (i) => (i.opt ? i.x.evals.length : i.x.rows.length);
    const narrow = el.clientWidth < NARROW, short = el.clientHeight < SHORT;
    const box = [Math.round(el.clientWidth / 8), Math.round(el.clientHeight / 8)];   // redraw when the panel resizes
    const rows = it.opt ? it.x.evals : it.x.rows, ends = rows.length ? [rows[0], rows[rows.length - 1]] : [];
    const sig = JSON.stringify([tab.id, I18N.lang, it.key, ch, box, narrow, short, it.x.heat ? plan : null,
      items.map((i) => [i.key, size(i), i.opt ? 0 : i.x.columns.length]), opt && opt.ver, ends,
      stSig, ap && ap.why, pend && pend.what, WBL.ver]);
    if (el.dataset.sig === sig) return;
    el.dataset.sig = sig;
    const view = it.opt ? optView(it.x, ch, A) : tableView(it.x, ch, plan, A);
    const alg = (k) => (window.WB && WB.algName ? WB.algName(k) : k);   // "NSGA-II", as the step names it
    const title = (i) => (i.opt ? t("res_kind_opt", alg(i.x.algorithm || "")) : kindTitle(i.x));
    // a chip: its kind's icon and its name (a table's or chart's own label, a group's part)
    const grouped = (i) => { const k = group(i.key); return !!k && items.filter((x) => group(x.key) === k).length > 1; };
    const name = (i) => {
      if (i.opt || !["table", "plot"].includes(i.x.kind)) return title(i);
      const label = String(i.x.label || "");
      return grouped(i) && label.includes(": ") ? label.slice(label.lastIndexOf(": ") + 2) : label || title(i);
    };
    const names = items.map(name), twice = names.filter((n, k) => names.indexOf(n) !== k);
    const chips = items.map((i, k) => `<button class="res-chip${i === it ? " on" : ""}" data-item="${esc(i.key)}" title="${esc(title(i))}">`
      + `${icon(i.opt ? "target" : i.x.kind === "table" ? "table" : "chart")}<span class="bt">${esc(twice.includes(names[k]) ? title(i) : names[k])}</span></button>`).join("");
    // one line under the chips: where the model was left (a click shows its inputs in place of
    // the chart and table, and again brings them back), and at its end Apply best point / Apply
    // this point (a point chosen on the chart, with its ×)
    const sv = st ? stateView(st, items, title) : null;
    const apHtml = view.pin ? `<span class="res-pin">${A.button("pin", `${t("ap_pin")} · ${view.pin}`, t("tip_ap_pin", view.pin), "res-ap", "target")}`
        + `<button class="res-unpin" data-ap="unpin" title="${esc(t("tip_ap_unpin"))}" aria-label="${esc(t("tip_ap_unpin"))}">${icon("close")}</button></span>`
      : view.best ? A.button("best", view.best.label, view.best.tip, "res-ap", "check") : "";
    const more = !!(sv && (sv.rows.length || sv.text)), open = more && !!ch.ms;
    const headIn = sv ? `${icon(sv.ic)}<span class="mt">${esc(sv.head)}</span>${sv.run ? `<span class="mr">· ${esc(sv.run)}</span>` : ""}` : "";
    // (its whole words in its tooltip too: a narrow dock cuts them, and drops the re-run's)
    const mtip = sv ? `${sv.head}${sv.run ? " · " + sv.run : ""}
${sv.runTip ? sv.runTip + "\n" : ""}${t("tip_ms")}` : "";
    const head = !sv ? `<span class="grow"></span>`
      : more ? `<button class="res-mst" data-ms="1" aria-expanded="${open}" title="${esc(mtip)}">${headIn}${icon(open ? "chevron-up" : "chevron-down")}</button>`
      : `<span class="res-mst" title="${esc(mtip)}">${headIn}</span>`;
    const msLine = sv || apHtml ? `<div class="res-ms${sv && sv.level ? " " + sv.level : ""}">${head}${apHtml}</div>` : "";
    const details = open ? `<div class="res-msd${msAnim === tab.id ? " in" : ""}"><ul>${sv.rows.map((r) => `<li${r.bad ? ' class="bad"' : ""}>`
      + `<span class="mtag">${esc(r.tag)}</span><span class="mp" title="${esc(r.path)}">${esc(pathWords(r.path))}</span>`
      + `<span class="mv">${esc(r.val)}</span>${r.why ? `<span class="mw"${r.whyTip ? ` title="${esc(r.whyTip)}"` : ""}>${esc(r.why)}</span>` : ""}</li>`).join("")}</ul>`
      + (sv.text ? `<p class="ms-tx"${sv.textTip ? ` title="${esc(sv.textTip)}"` : ""}>${esc(sv.text)}</p>` : "") + `</div>` : "";
    msAnim = null;
    // narrow or short: the chart or the table, and the switch between them
    const vw = view.chart && (narrow || short) && !open ? ch.view || (short ? "table" : "chart") : null;
    const sw = vw ? `<span class="res-view" title="${esc(t("tip_res_view"))}">`
      + `<button data-v="chart" class="${vw === "chart" ? "on" : ""}">${esc(t("res_chart"))}</button>`
      + `<button data-v="table" class="${vw === "table" ? "on" : ""}">${esc(t("res_table"))}</button></span>` : "";
    const withChart = !open && view.chart && vw !== "table", withTable = !open && (!view.chart || vw !== "chart");
    const keep = el.querySelector(".res-chips"), scrolled = keep ? keep.scrollLeft : 0;
    const tail = `<span class="res-n">${esc(view.count || "")}</span>${view.extra || ""}${sw}`;
    const parts = { chips, tail, ms: msLine, details: open ? details : "", cap: view.cap || "", table: withTable ? view.table : "" };
    // the same frame (the item shown, its layout) with new data -- a loop's next pass, a live chart's
    // point: its parts written in place, the chart's svg kept; the scroll, the pointer's tooltip stay
    const frame = JSON.stringify([tab.id, it.key, open, !!withChart, !!withTable, !!view.cap, !!msLine]);
    const was = el.wbParts, same = !!was && el.dataset.frame === frame && !!keep;
    if (same) {
      if (was.chips !== chips) keep.innerHTML = chips;
      if (was.tail !== tail) {
        while (keep.nextSibling) keep.nextSibling.remove();
        keep.insertAdjacentHTML("afterend", tail);
      }
      const put = (sel, html, outer) => { const x = el.querySelector(sel); if (x) { if (outer) x.outerHTML = html; else x.innerHTML = html; } };
      if (was.ms !== msLine) put(".res-ms", msLine, true);
      if (was.details !== parts.details) put(".res-msd", parts.details.replace('class="res-msd in"', 'class="res-msd"'), true);
      if (was.cap !== parts.cap) put(".res-cap", parts.cap);
      if (was.table !== parts.table) put(".res-tbl", parts.table);
    } else {
      el.innerHTML = `<div class="res-bar"><div class="res-chips">${chips}</div>${tail}</div>` + msLine
        + (open ? details : `<div class="res-body${withChart && withTable ? " both" : ""}">`
        + (withChart ? `<div class="res-pc">${view.cap ? `<div class="res-cap">${view.cap}</div>` : ""}`
          + `<div class="res-plot"><div class="res-svg"></div><div class="res-tip plate hidden"></div></div></div>` : "")
        + (withTable ? `<div class="res-tbl">${view.table}</div>` : "") + `</div>`);
      el.dataset.frame = frame;
    }
    el.wbParts = parts;
    const strip = el.querySelector(".res-chips");
    strip.scrollLeft = scrolled;
    stripView(strip, strip.querySelector(".res-chip.on"));   // the chip shown in view
    if (!same) sideways(strip);
    el.querySelectorAll("[data-item]").forEach((b) => (b.onclick = () => {
      if (ch.item === b.dataset.item) return;
      ch.item = b.dataset.item;
      R.render(el, tab, results, opt);
    }));
    el.querySelectorAll("[data-v]").forEach((b) => (b.onclick = () => { ch.view = b.dataset.v; R.render(el, tab, results, opt); }));
    el.querySelectorAll('[data-r="all"]').forEach((b) => (b.onclick = () => { ch.all = !ch.all; R.render(el, tab, results, opt); }));
    el.querySelectorAll("[data-ms]").forEach((b) => (b.onclick = () => {
      ch.ms = !ch.ms;
      msAnim = ch.ms ? tab.id : null;
      R.render(el, tab, results, opt);
    }));
    el.querySelectorAll("[data-ap]").forEach((b) => (b.onclick = () => {
      const k = b.dataset.ap;
      if (k === "unpin") { delete ch.pin; R.render(el, tab, results, opt); return; }
      if (b.disabled || !ap || !ap.send) return;
      const row = k === "best" ? "best" : k === "pin" ? (ch.pin ? ch.pin.pick : null) : Number(k.slice(1));
      if (row === null || row === undefined || (typeof row === "number" && !Number.isInteger(row))) return;
      ap.send(it.key, row);
      R.pending[tab.id] = { what: k, stamp: ap.stamp, st: stSig, until: Date.now() + PEND_MS };
      setTimeout(() => { if (R.onRefresh) R.onRefresh(); }, PEND_MS + 100);
      R.render(el, tab, results, opt);
    }));
    el.querySelectorAll("select").forEach((s) => (s.onchange = () => {
      ch[s.dataset.r] = s.dataset.r === "ox" || s.dataset.r === "oy" ? Number(s.value) : s.value;
      R.render(el, tab, results, opt);
    }));
    el.wbExport = () => {
      const file = `${tab.title}_${title(it)}`.replace(/[\\/:*?"<>|\s]+/g, "_") + ".csv";
      if (R.onExport) R.onExport(file, view.csv.map((row) => row.map(csvCell).join(",")).join("\r\n") + "\r\n");
    };
    if (!withChart) return;
    const plot = el.querySelector(".res-plot"), cap = el.querySelector(".res-cap");
    // a caption that wraps where the chart is short of room keeps to one line: the axis
    // choices and the legend's swatches (their words in their tooltips)
    if (cap && plot.clientHeight < 90 && cap.offsetHeight > 30) cap.classList.add("one");
    const W = Math.floor(plot.clientWidth), H = Math.floor(plot.clientHeight);
    if (W < 120 || H < 40) {                             // too small to read: the table, or a bigger dock
      plot.querySelector(".res-svg").innerHTML = `<div class="hint res-small">${esc(t("res_small"))}</div>`;
      return;
    }
    const drawn = view.chart.draw(W, H), sbox = plot.querySelector(".res-svg"), had = sbox.querySelector("svg.res-chart");
    const tmp = had && document.createElement("div");
    if (tmp) tmp.innerHTML = drawn.svg;
    const nw = tmp && tmp.querySelector("svg.res-chart");
    if (nw) {                                            // (the same svg, its contents new)
      [...had.attributes].forEach((a) => { if (!nw.hasAttribute(a.name)) had.removeAttribute(a.name); });
      [...nw.attributes].forEach((a) => { if (had.getAttribute(a.name) !== a.value) had.setAttribute(a.name, a.value); });
      had.replaceChildren(...nw.childNodes);
      [...sbox.childNodes].forEach((x) => { if (x !== had) x.remove(); });
    } else sbox.innerHTML = drawn.svg;
    hover(el, drawn);
  };
  /** The dock's CSV button: the result shown, as a file; whether there is one. */
  R.exportShown = (el) => { if (el && el.wbExport) el.wbExport(); };
  R.canExport = (el) => !!(el && el.wbExport);
})();
