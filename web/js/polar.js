// Panorama del horizonte: azimut (x, 0° = norte, hacia el este) contra elevación (y).
// Se usa azimut-elevación y no un polar redondo porque Sol y Tierra nunca pasan de
// ~15° sobre el horizonte y en un círculo quedarían aplastados contra el borde.
// El terreno se dibuja ENCIMA de Sol y Tierra, con algo de transparencia: un astro
// tapado se ve tenue detrás de la montaña.

const NS = "http://www.w3.org/2000/svg";
const W = 900;
const H = 380;
const M = { l: 44, r: 16, t: 14, b: 30 };
const TRAIL_DAYS = 30;
const TRAIL_STEP_H = 6;
const FULL = 0.9999;
const CARDINALS = ["N", "NE", "E", "SE", "S", "SO", "O", "NO", "N"];
const BODIES = { sun: "Sol", earth: "Tierra" };

function el(tag, attrs, parent) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

export class Panorama {
  constructor(container) {
    this.svg = el("svg", {
      viewBox: `0 0 ${W} ${H}`,
      role: "img",
      "aria-label": "Panorama del horizonte con la posición del Sol y de la Tierra",
    });
    container.replaceChildren(this.svg);
    this.d = null;
  }

  x(az) {
    return M.l + (az / 360) * (W - M.l - M.r);
  }

  y(elev) {
    return M.t + ((this.ymax - elev) / (this.ymax - this.ymin)) * (H - M.t - M.b);
  }

  // Dibuja todo lo que no cambia con el tiempo (ejes, terreno) para un sitio.
  setSite(d) {
    this.d = d;
    [this.ymin, this.ymax] = this.#elevationRange(d);
    this.svg.replaceChildren();

    const defs = el("defs", {}, this.svg);
    const clip = el("clipPath", { id: "pano-clip" }, defs);
    el("rect", { x: M.l, y: M.t, width: W - M.l - M.r, height: H - M.t - M.b }, clip);

    this.#grid();

    const plot = el("g", { "clip-path": "url(#pano-clip)" }, this.svg);
    this.trails = {};
    this.dots = {};
    for (const key of Object.keys(BODIES)) {
      this.trails[key] = el("path", { class: `trail ${key}` }, plot);
    }
    for (const [key, name] of Object.entries(BODIES)) {
      const g = el("g", {}, plot);
      const circle = el("circle", { class: `dot ${key}`, r: 7 }, g);
      const label = el("text", { class: "dot-label" }, g);
      label.textContent = name;
      this.dots[key] = { circle, label };
    }

    this.#terrain(plot);
    this.#axisLabels();
  }

  // Mueve Sol y Tierra al instante i (índice del array) y redibuja su estela.
  setTime(i) {
    const d = this.d;
    if (!d) return;
    for (const key of Object.keys(BODIES)) {
      const b = d[key];
      const f = b.fraction ? b.fraction[i] : b.visible[i] ? 1 : 0;
      const px = this.x(b.az[i]);
      const py = this.y(b.el[i]);
      const { circle, label } = this.dots[key];

      circle.setAttribute("cx", px.toFixed(1));
      circle.setAttribute("cy", py.toFixed(1));
      circle.setAttribute("fill-opacity", f >= FULL ? 1 : f > 0 ? 0.5 : 0); // lleno, parcial, hueco

      const flip = px > W - 70;
      label.setAttribute("x", (px + (flip ? -11 : 11)).toFixed(1));
      label.setAttribute("y", (py + 4).toFixed(1));
      label.setAttribute("text-anchor", flip ? "end" : "start");

      this.trails[key].setAttribute("d", this.#trail(b, i));
    }
  }

  #elevationRange(d) {
    let lo = 0;
    let hi = 0;
    const scan = (arr) => {
      for (const v of arr) {
        if (v == null) continue;
        if (v < lo) lo = v;
        if (v > hi) hi = v;
      }
    };
    scan(d.sun.el);
    scan(d.earth.el);
    scan(d.horizon);
    return [Math.floor(lo - 1), Math.ceil(hi + 1)];
  }

  #grid() {
    const range = this.ymax - this.ymin;
    const step = range > 30 ? 10 : range > 14 ? 5 : 2;
    for (let v = Math.ceil(this.ymin / step) * step; v <= this.ymax; v += step) {
      el("line", { class: v === 0 ? "zero" : "grid", x1: this.x(0), x2: this.x(360), y1: this.y(v), y2: this.y(v) }, this.svg);
      const t = el("text", { x: M.l - 6, y: this.y(v) + 4, "text-anchor": "end" }, this.svg);
      t.textContent = `${v}°`;
    }
    for (let k = 0; k <= 8; k++) {
      el("line", { class: "grid", x1: this.x(k * 45), x2: this.x(k * 45), y1: this.y(this.ymax), y2: this.y(this.ymin) }, this.svg);
    }
  }

  #axisLabels() {
    for (let k = 0; k <= 8; k++) {
      const t = el("text", { x: this.x(k * 45), y: H - 10, "text-anchor": "middle" }, this.svg);
      t.textContent = CARDINALS[k];
    }
  }

  #terrain(parent) {
    const h = this.d.horizon;
    const n = h.length;
    let line = "";
    for (let k = 0; k <= n; k++) {
      const az = (k * 360) / n;
      const v = h[k % n] ?? 0; // sin dato se trata como horizonte plano, igual que en Python
      line += `${k ? "L" : "M"}${this.x(az).toFixed(1)} ${this.y(v).toFixed(1)}`;
    }
    const area = `${line}L${this.x(360).toFixed(1)} ${this.y(this.ymin).toFixed(1)}L${this.x(0).toFixed(1)} ${this.y(this.ymin).toFixed(1)}Z`;
    el("path", { class: "terrain", d: area }, parent);
    el("path", { class: "ridge", d: line }, parent);
  }

  // Estela de los últimos TRAIL_DAYS días hasta el instante i; se corta al cruzar 360°→0°.
  #trail(b, i) {
    const d = this.d;
    const stride = Math.max(1, Math.round(TRAIL_STEP_H / d.step_h));
    const from = Math.max(0, i - Math.round((TRAIL_DAYS * 24) / d.step_h));
    const idx = [];
    for (let j = i; j >= from; j -= stride) idx.push(j);
    idx.reverse();

    let path = "";
    let prevAz = null;
    for (const j of idx) {
      const az = b.az[j];
      const pt = `${this.x(az).toFixed(1)} ${this.y(b.el[j]).toFixed(1)}`;
      path += prevAz === null || Math.abs(az - prevAz) > 180 ? `M${pt}` : `L${pt}`;
      prevAz = az;
    }
    return path;
  }
}