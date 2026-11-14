// Mapa del polo sur: proyección estereográfica polar, vista desde arriba del polo
// (0° arriba, 90°E a la derecha, igual que las imágenes de LOLA). Cada sitio es un
// punto cuya intensidad indica la métrica elegida, con valores del periodo completo
// del índice (sites.json). Clic o Enter sobre un sitio lo elige en la vista principal.

import { pct } from "./data.js";

const NS = "http://www.w3.org/2000/svg";
const SIZE = 440;
const C = SIZE / 2;
const R = 190; // radio que corresponde al borde del mapa (80°S)
const LAT_EDGE = -80;
const RAD = Math.PI / 180;
const K0 = Math.tan(((90 + LAT_EDGE) * RAD) / 2);

const METRICS = [
  { key: "sun_energy_pct", fb: "pct_sun", label: "Luz solar", tone: "sun" },
  { key: "pct_earth_full", fb: "pct_earth", label: "Tierra completa", tone: "earth" },
  { key: "pct_both", label: "Sol y Tierra a la vez", tone: "both" },
];

function el(tag, attrs, parent) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

// Estereográfica polar sur: r crece con tan(colatitud/2). x = sin(lon), y = cos(lon).
function radius(lat) {
  return (R * Math.tan(((90 + lat) * RAD) / 2)) / K0;
}

function project(lat, lon) {
  const r = radius(lat);
  return [C + r * Math.sin(lon * RAD), C - r * Math.cos(lon * RAD)];
}

function lonLabel(lon) {
  if (lon === 0 || lon === 180) return `${lon}°`;
  return lon > 0 ? `${lon}°E` : `${-lon}°O`;
}

export class PoleMap {
  constructor(container, sites, onSelect) {
    this.sites = sites;
    this.onSelect = onSelect;
    this.metric = METRICS[0];
    this.sel = -1;
    this.nodes = [];

    const select = document.createElement("select");
    select.setAttribute("aria-label", "Métrica con la que se colorean los sitios");
    METRICS.forEach((m, i) => {
      const opt = document.createElement("option");
      opt.value = String(i);
      opt.textContent = m.label;
      select.appendChild(opt);
    });
    select.addEventListener("change", () => this.#setMetric(METRICS[Number(select.value)]));
    const label = document.createElement("label");
    label.append("Colorear por ", select);

    const head = document.createElement("div");
    head.className = "map-head";
    const title = document.createElement("h2");
    title.textContent = "Mapa del polo sur";
    head.append(title, label);

    this.svg = el("svg", {
      viewBox: `0 0 ${SIZE} ${SIZE}`,
      role: "group",
      "aria-label": "Mapa del polo sur de la Luna con los sitios de aterrizaje",
      class: `tone-${this.metric.tone}`,
    });

    const legend = document.createElement("p");
    legend.className = "hint";
    legend.textContent = "Cuanto más intenso el punto, más tiempo del periodo completo. Haz clic en un sitio para verlo en el panorama.";

    container.replaceChildren(head, this.svg, legend);
    this.#drawBase();
    this.#drawSites();
  }

  setSelected(i) {
    this.sel = i;
    this.nodes.forEach((n, k) => {
      n.g.classList.toggle("sel", k === i);
      n.g.setAttribute("aria-pressed", String(k === i));
    });
  }

  #value(site) {
    const m = site.metrics || {};
    return m[this.metric.key] ?? (this.metric.fb ? m[this.metric.fb] : null) ?? null;
  }

  #drawBase() {
    const g = el("g", { class: "base" }, this.svg);
    el("circle", { class: "ring", cx: C, cy: C, r: R }, g);
    for (const lat of [-82, -84, -86, -88]) {
      el("circle", { class: "ring", cx: C, cy: C, r: radius(lat).toFixed(1) }, g);
    }
    // etiquetas de latitud, junto al meridiano 15°E
    for (const lat of [-80, -82, -84, -86, -88]) {
      const r = radius(lat);
      const t = el("text", { x: (C + r * Math.sin(15 * RAD) + 3).toFixed(1), y: (C - r * Math.cos(15 * RAD) + 3).toFixed(1) }, g);
      t.textContent = `${-lat}°S`;
    }
    for (let lon = -150; lon <= 180; lon += 30) {
      const a = lon * RAD;
      el("line", { class: "mer", x1: C, y1: C, x2: (C + R * Math.sin(a)).toFixed(1), y2: (C - R * Math.cos(a)).toFixed(1) }, g);
      const t = el("text", { x: (C + (R + 15) * Math.sin(a)).toFixed(1), y: (C - (R + 15) * Math.cos(a) + 3).toFixed(1), "text-anchor": "middle" }, g);
      t.textContent = lonLabel(lon);
    }
    el("path", { class: "pole", d: `M${C - 4} ${C}H${C + 4}M${C} ${C - 4}V${C + 4}` }, g);
  }

  #drawSites() {
    this.sites.forEach((s, i) => {
      const [x, y] = project(s.lat, s.lon);
      const g = el("g", { class: "site", tabindex: 0, role: "button", "aria-pressed": "false" }, this.svg);
      const tip = el("title", {}, g);
      el("circle", { class: "halo", cx: x.toFixed(1), cy: y.toFixed(1), r: 12 }, g);
      const dot = el("circle", { class: "dot", cx: x.toFixed(1), cy: y.toFixed(1), r: 7 }, g);

      // El texto va hacia el lado con más espacio.
      const anchor = x < 130 ? "start" : x > 310 ? "end" : x < C ? "end" : "start";
      const text = el("text", { class: "name", x: (x + (anchor === "start" ? 14 : -14)).toFixed(1), y: (y + 4).toFixed(1), "text-anchor": anchor }, g);
      const nameSpan = el("tspan", {}, text);
      nameSpan.textContent = s.name;
      const valSpan = el("tspan", { class: "val", dx: 5 }, text);

      const choose = () => this.onSelect(i);
      g.addEventListener("click", choose);
      g.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          choose();
        }
      });
      this.nodes.push({ g, dot, valSpan, tip, site: s });
    });
    this.#paint();
  }

  #setMetric(metric) {
    this.metric = metric;
    this.svg.setAttribute("class", `tone-${metric.tone}`);
    this.#paint();
  }

  #paint() {
    for (const n of this.nodes) {
      const v = this.#value(n.site);
      n.dot.setAttribute("fill-opacity", v == null ? 0 : Math.min(1, Math.max(0, v / 100)).toFixed(2));
      n.valSpan.textContent = v == null ? "" : pct(v);
      const txt = `${n.site.name}, ${this.metric.label}: ${v == null ? "sin dato" : pct(v)}`;
      n.tip.textContent = txt;
      n.g.setAttribute("aria-label", txt);
    }
  }
}