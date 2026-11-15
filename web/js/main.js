import { loadIndex, loadSite, timeOf, fmtUTC, dateBounds, rangeToIndices, metrics, fmt } from "./data.js";
import { createPanorama } from "./polar.js";
import { createMap } from "./map.js";
import { createTimeline } from "./timeline.js";
import { createCompare } from "./compare.js";

const $ = (id) => document.getElementById(id);
const S = { sites: [], cur: null, a: 0, b: 0, i: 0, timer: null, min: "", max: "" };
let pano, map, timeline, compare;

const MES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const lastDay = (y, m) => new Date(Date.UTC(y, m, 0)).getUTCDate();   // m = 1..12
const clamp = (d) => (d < S.min ? S.min : d > S.max ? S.max : d);   // fechas ISO: se comparan como texto
const pad = (n) => String(n).padStart(2, "0");

function periodRange(y, m = 0) {
  const start = m
    ? `${y}-${pad(m)}-01`
    : `${y}-01-01`;

  const end = m
    ? `${y}-${pad(m)}-${lastDay(y, m)}`
    : `${y}-12-31`;

  return [clamp(start), clamp(end)];
}

function updateMonthAvailability(year) {
  const select = $("month");

  select.disabled = year === "all" || year === "custom";

  for (const option of select.options) {
    if (!/^\d+$/.test(option.value)) continue;

    const m = Number(option.value);
    const start = `${year}-${pad(m)}-01`;
    const end = `${year}-${pad(m)}-${lastDay(Number(year), m)}`;

    option.disabled = end < S.min || start > S.max;
  }
}

function syncPeriodSelectors() {
  const start = $("start").value;
  const end = $("end").value;

  // Todo el periodo
  if (start === S.min && end === S.max) {
    $("year").value = "all";
    $("month").value = "all";
    updateMonthAvailability("all");
    return;
  }

  const [y0] = S.min.split("-").map(Number);
  const [y1] = S.max.split("-").map(Number);

  // Buscar si coincide con un año completo
  for (let y = y0; y <= y1; y++) {
    const [s, e] = periodRange(y);

    if (start === s && end === e) {
      $("year").value = String(y);
      $("month").value = "all";
      updateMonthAvailability(y);
      return;
    }
  }

  // Buscar si coincide con un mes completo
  for (let y = y0; y <= y1; y++) {
    for (let m = 1; m <= 12; m++) {
      const [s, e] = periodRange(y, m);

      if (start === s && end === e) {
        $("year").value = String(y);
        $("month").value = String(m);
        updateMonthAvailability(y);
        return;
      }
    }
  }

  // Rango personalizado
  $("year").value = "custom";
  $("month").value = "custom";
  updateMonthAvailability("custom");
}
function setRange(s, e) { $("start").value = clamp(s); $("end").value = clamp(e); applyRange(); }
// Umbrales de nivel: referencia visual propia, no un estándar de misión
const level = (v, hi, mid) => (v >= hi ? ["Alto", "ok"] : v >= mid ? ["Medio", "mid"] : ["Crítico", "bad"]);

function showError(msg) { $("error").textContent = msg; $("error").hidden = false; }
const metricsOf = (site) => { const [a, b] = rangeToIndices(site, $("start").value, $("end").value); return metrics(site, a, b); };

function pick(site) {
  S.cur = site;
  map.select(site);
  $("s-name").textContent = site.site.name;
  $("s-info").textContent = `lat ${site.site.lat}° · lon ${site.site.lon}° · altura del terreno ${site.meta.site_height_m} m`;
  $("s-note").textContent = site.site.note;
  pano.setSite(site);
  applyRange();
}

function applyRange() {
  const [a, b] = rangeToIndices(S.cur, $("start").value, $("end").value);
  if (!(b > a)) return showError("El rango de fechas no es válido: revisa Desde y Hasta.");
  syncPeriodSelectors();
  $("error").hidden = true;
  S.a = a; S.b = b; S.i = Math.min(Math.max(S.i, a), b - 1);
  const t = $("time"); t.min = a; t.max = b - 1; t.value = S.i;
  $("active").textContent = `${S.cur.site.name} · ${$("start").value} → ${$("end").value}`;
  const m = metrics(S.cur, a, b);
  kpis(m); science(m);
  timeline.draw(S.cur, a, b);
  render();
}

const card = (ic, t, v, s, l, c) => `<div class="card"><span class="ic">${ic}</span><div><small>${t}</small><strong>${v}</strong><span class="muted">${s}</span></div>${l ? `<em class="lv ${c}">${l}</em>` : ""}</div>`;

function kpis(m) {
  const sun = m.sun_energy_pct ?? m.pct_sun, [ls, cs] = level(sun, 30, 10), [le, ce] = level(m.pct_earth, 80, 30);
  $("kpis").innerHTML =
    card("☀️", "Luz solar disponible", `${fmt(sun)}%`, "del periodo seleccionado", ls, cs) +
    card("🌍", "Conexión con la Tierra", `${fmt(m.pct_earth)}%`, m.pct_earth_full != null ? `visibilidad directa · disco completo ${fmt(m.pct_earth_full)}%` : "visibilidad directa", le, ce) +
    card("🌙", "Noche continua máxima", `${fmt(m.max_dark_h, 0)} h`, `≈ ${fmt(m.max_dark_h / 24, 0)} días sin luz solar`);
}

function science(m) {
  const s = S.cur, row = (l, v) => `<tr><td>${l}</td><td>${fmt(v)} %</td></tr>`, txt = (l, v) => `<tr><td>${l}</td><td>${v}</td></tr>`;
  $("science").innerHTML =
    `<h3>Criterios de visibilidad${m.exact ? "" : " (aproximados en rangos parciales)"}</h3><table>` +
    row("Sol · centro del disco", m.pct_sun) + row("Sol · energía (ponderada por área)", m.sun_energy_pct) +
    row("Sol · algún pedazo", m.pct_sun_any) + row("Sol · completo", m.pct_sun_full) +
    row("Tierra · centro del disco", m.pct_earth) + row("Tierra · algún pedazo", m.pct_earth_any) +
    row("Tierra · disco completo", m.pct_earth_full) + row("Sol y Tierra a la vez (centro)", m.pct_both) +
    `</table><h3>Modelo topográfico</h3><table>` +
    txt("DEM", s.meta.dem) + txt("Resolución", `${s.meta.pixel_m} m/px`) + txt("Radio del horizonte", `${s.meta.radius_km} km`) +
    txt("Azimuts", s.meta.n_azimuths) + txt("Altura del observador", `${s.meta.observer_height_m} m`) +
    txt("Rayos truncados por el borde del DEM", `${s.meta.truncated_pct ?? "n/d"}%`) + txt("Azimuts sin dato", s.meta.horizon_gaps) +
    `</table><a class="cta small" href="data/${s._file}" download>Descargar JSON crudo</a>`;
}

function render() {
  const s = S.cur;
  pano.update(s, S.i, S.b);
  timeline.setCursor(S.i);
  $("when").textContent = fmtUTC(timeOf(s, S.i));
  const st = (n, bd) => `${n}: ${bd.visible[S.i] ? "visible" : "no visible"} · az ${bd.az[S.i].toFixed(1)}° · el ${bd.el[S.i].toFixed(2)}°`;
  $("now").textContent = `${st("Sol", s.sun)}  |  ${st("Tierra", s.earth)}`;
}

function play() {
  if (S.timer) { clearInterval(S.timer); S.timer = null; $("play").textContent = "▶"; return; }
  const step = Math.max(1, Math.round(6 / S.cur.step_h));   // 6 h por cuadro
  $("play").textContent = "⏸";
  S.timer = setInterval(() => { S.i += step; if (S.i >= S.b) S.i = S.a; $("time").value = S.i; render(); }, 50);
}

function seek(i) { S.i = i; $("time").value = i; render(); }

async function init() {
  if (typeof d3 === "undefined") return showError("No cargó D3 (sin internet o bloqueado por la red). Descárgalo con: curl -o web/js/d3.min.js https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js y en index.html cambia el <script> de D3 por js/d3.min.js");
  const need = ["map", "tl", "panorama", "kpis", "science", "cmp-b", "cmp-t", "dlg", "start", "end", "time", "play", "when", "now", "active", "sci", "open-cmp", "cmp", "s-name", "s-info", "s-note", "year", "month"];
  const missing = need.filter((id) => !$(id));
  if (missing.length) return showError(`Tu index.html no es la versión nueva: faltan los elementos ${missing.join(", ")}. Reemplaza también index.html y css/style.css.`);
  try {
    const idx = await loadIndex();
    S.sites = await Promise.all(idx.map(async (e) => Object.assign(await loadSite(e.file), { _file: e.file })));
  } catch (err) {
    return showError(`No pude cargar los datos (${err.message}). Sirve la carpeta web con: cd web && python -m http.server 8000`);
  }
  pano = createPanorama($("panorama"));
  map = createMap($("map"), pick);
  timeline = createTimeline($("tl"), seek);
  compare = createCompare(S.sites, metricsOf);
  $("sci").addEventListener("change", (e) => {
      document.body.classList.toggle(
          "sci-on",
          e.target.checked
      );
  });
  const { min, max } = dateBounds(S.sites[0]);
  S.min = min; S.max = max;
  for (const id of ["start", "end"]) { $(id).min = min; $(id).max = max; }
  $("start").value = min; $("end").value = max;

  // Selectores de año y mes: se llenan con lo que realmente cubren los datos
  // Selectores de año y mes
  const [y0] = S.min.split("-").map(Number);
  const [y1] = S.max.split("-").map(Number);

  // Años disponibles
  for (let y = y0; y <= y1; y++) {
    $("year").add(new Option(String(y), y));
  }

  // Opción para rangos personalizados
  $("year").add(new Option("Personalizado", "custom"));
  $("month").add(new Option("Personalizado", "custom"));
  
  // Meses disponibles
  MES.forEach((mes, i) => {
   const nombre = mes.charAt(0).toUpperCase() + mes.slice(1);
   $("month").add(new Option(nombre, i + 1));
  });

  // Selección de año
  $("year").onchange = () => {
   const y = $("year").value;

   if (y === "all") {
     $("month").value = "all";
     setRange(S.min, S.max);
     return;
   }

  if (y === "custom") return;

  updateMonthAvailability(y);

  const m = $("month").value;

  if (m !== "all" && m !== "custom") {
    const [s, e] = periodRange(Number(y), Number(m));
    setRange(s, e);
  } else {
    $("month").value = "all";
    const [s, e] = periodRange(Number(y));
    setRange(s, e);
  }
};

// Selección de mes
$("month").onchange = () => {
  const y = $("year").value;
  const m = $("month").value;

  if (y === "all" || y === "custom") return;
  if (m === "custom") return;

  if (m === "all") {
    const [s, e] = periodRange(Number(y));
    setRange(s, e);
    return;
  }

  const [s, e] = periodRange(Number(y), Number(m));
  setRange(s, e);
};

// Cambios manuales de fechas
$("start").onchange = $("end").onchange = applyRange;
  $("play").onclick = play;
  $("open-cmp").onclick = $("cmp").onclick = () => compare.open(S.cur);

  let bg = null;   // relieve de fondo, opcional
  try { const r = await fetch("data/map.json"); if (r.ok) bg = { ...(await r.json()), href: "data/map.png" }; } catch { /* sin fondo */ }
  map.draw(S.sites, bg);
  pick(S.sites[0]);
}
init();
