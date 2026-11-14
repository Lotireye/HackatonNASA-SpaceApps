// Comparador: dos opciones (A y B), cada una con su sitio y su rango de fechas.
// Sirve para comparar sitios entre sí o el mismo sitio en dos épocas.
// Usa las mismas métricas que la vista principal (metricsForRange).

import { dateBounds, rangeToIndices, metricsForRange, fmt, pct, hours } from "./data.js";

const MIN_DAYS = 90; // por debajo de esto las cifras no son concluyentes

// better: qué dirección es mejor; kind: cómo se formatea; tone: color de la barra.
const ROWS = [
  { label: "Energía solar", key: "sun_energy_pct", fb: "pct_sun", kind: "pct", tone: "sun", better: "high" },
  { label: "Centro del Sol visible", key: "pct_sun", kind: "pct", tone: "sun", better: "high" },
  { label: "Noche más larga", key: "max_dark_h", kind: "h", tone: "sun", better: "low" },
  { label: "Tierra completa", key: "pct_earth_full", fb: "pct_earth", kind: "pct", tone: "earth", better: "high" },
  { label: "Tierra, centro del disco", key: "pct_earth", kind: "pct", tone: "earth", better: "high" },
  { label: "Tierra, algún pedazo", key: "pct_earth_any", fb: "pct_earth", kind: "pct", tone: "earth", better: "high" },
  { label: "Periodo más largo sin Tierra", key: "max_no_earth_h", kind: "h", tone: "earth", better: "low" },
  { label: "Sol y Tierra a la vez", key: "pct_both", kind: "pct", tone: "both", better: "high" },
];

function h(tag, props = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else node.setAttribute(k, v);
  }
  node.append(...kids);
  return node;
}

export class Comparator {
  // sites: lista del índice (name, file...); getSite(entry) -> Promise con el JSON del sitio.
  constructor(container, { sites, getSite }) {
    this.sites = sites;
    this.getSite = getSite;

    const controls = h("div", { class: "cmp-controls" });
    this.cols = ["A", "B"].map((name, k) => this.#column(name, Math.min(k, sites.length - 1), controls));

    this.thead = h("tr");
    this.tbody = h("tbody");
    this.notes = h("p", { class: "cmp-note" });
    const table = h("table", { class: "cmp-table" }, h("thead", {}, this.thead), this.tbody);
    container.replaceChildren(controls, table, this.notes);

    for (const col of this.cols) this.#load(col);
  }

  #column(name, siteIdx, parent) {
    const select = h(
      "select",
      { "aria-label": `Sitio de la opción ${name}` },
      ...this.sites.map((s, i) => h("option", { value: String(i) }, s.name)),
    );
    select.value = String(siteIdx);
    const from = h("input", { type: "date", "aria-label": `Desde, opción ${name}` });
    const to = h("input", { type: "date", "aria-label": `Hasta, opción ${name}` });
    const note = h("p", { class: "cmp-note" });

    parent.append(
      h(
        "div",
        { class: "cmp-col" },
        h("h3", {}, `Opción ${name}`),
        h("label", {}, "Sitio", select),
        h("div", { class: "cmp-dates" }, h("label", {}, "Desde", from), h("label", {}, "Hasta", to)),
        note,
      ),
    );

    const col = { name, select, from, to, note, data: null, tok: 0 };
    select.addEventListener("change", () => this.#load(col));
    from.addEventListener("change", () => this.#render());
    to.addEventListener("change", () => this.#render());
    return col;
  }

  async #load(col) {
    const tok = ++col.tok; // si el usuario cambia rápido de sitio, gana la última elección
    try {
      const d = await this.getSite(this.sites[Number(col.select.value)]);
      if (tok !== col.tok) return;
      col.data = d;
      const [min, max] = dateBounds(d);
      for (const input of [col.from, col.to]) {
        input.min = min;
        input.max = max;
      }
      if (!col.from.value) col.from.value = min;
      if (!col.to.value) col.to.value = max;
    } catch (err) {
      col.data = null;
      this.notes.textContent = err.message;
      return;
    }
    this.#render();
  }

  #compute(col) {
    const d = col.data;
    if (!d) return { title: "…", m: null };
    if (col.from.value && col.to.value && col.from.value > col.to.value) {
      col.note.textContent = "La fecha final es anterior a la inicial.";
      return { title: d.site.name, m: null };
    }
    const [i0, i1] = rangeToIndices(d, col.from.value, col.to.value);
    const days = ((i1 - i0) * d.step_h) / 24;
    col.note.textContent =
      days > 0 && days < MIN_DAYS ? `Rango de ${fmt(days, 0)} días: con ventanas cortas las cifras cambian mucho según la época.` : "";
    return { title: d.site.name, m: metricsForRange(d, i0, i1) };
  }

  #render() {
    const results = this.cols.map((col) => this.#compute(col));

    this.thead.replaceChildren(
      h("th", { scope: "col" }, "Métrica"),
      ...results.map((r, k) => h("th", { scope: "col" }, `${this.cols[k].name}: ${r.title}`)),
    );

    this.tbody.replaceChildren(
      ...ROWS.map((row) => {
        const vals = results.map((r) => (r.m ? (r.m[row.key] ?? (row.fb ? r.m[row.fb] : null) ?? null) : null));
        let best = -1;
        if (vals[0] != null && vals[1] != null && Math.abs(vals[0] - vals[1]) >= 0.05) {
          const aWins = row.better === "high" ? vals[0] > vals[1] : vals[0] < vals[1];
          best = aWins ? 0 : 1;
        }
        return h("tr", {}, h("th", { scope: "row" }, row.label), ...vals.map((v, k) => this.#cell(row, v, best === k)));
      }),
    );

    // Aviso de transparencia: rayos del horizonte que salen del DEM (cifras como cota superior).
    const warned = new Set();
    const msgs = [];
    for (const col of this.cols) {
      const d = col.data;
      if (d && d.meta.truncated_pct > 0 && !warned.has(d.site.name)) {
        warned.add(d.site.name);
        msgs.push(`${d.site.name}: el ${fmt(d.meta.truncated_pct)}% de los rayos del horizonte sale del mapa; sus cifras pueden estar sobreestimadas.`);
      }
    }
    this.notes.textContent = msgs.join(" ");
  }

  #cell(row, v, isBest) {
    const td = h("td", { class: `tone-${row.tone}${isBest ? " best" : ""}` });
    td.append(h("span", { class: "num" }, v == null ? "–" : row.kind === "h" ? hours(v) : pct(v)));
    if (isBest) td.append(h("span", { class: "tag" }, "mejor"));
    if (row.kind === "pct" && v != null) {
      td.append(h("div", { class: "cmp-bar" }, h("i", { style: `width:${Math.min(100, Math.max(0, v))}%` })));
    }
    return td;
  }
}