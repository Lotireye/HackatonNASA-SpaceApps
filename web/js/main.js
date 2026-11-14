import { loadIndex, loadSite, rangeToIndices, dateBounds, metricsForRange, compareWithPython } from "./data.js";
import { Panorama } from "./polar.js";
import { Timeline } from "./timeline.js";

const MIN_DAYS_NOTE = 90; // por debajo de esto avisamos que las cifras no son concluyentes

const $ = (id) => document.getElementById(id);
const fmt = (v, d = 1) => v.toLocaleString("es", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (v) => (v == null ? "–" : `${fmt(v)}%`);
const hours = (h) => (h == null ? "–" : h >= 48 ? `${fmt(h, 0)} h (${fmt(h / 24)} días)` : `${fmt(h, 0)} h`);

const state = { index: [], cache: new Map(), data: null, bounds: null, range: [0, 0], t: 0, timer: null, pano: null, timeline: null };

// ---- tiempo: deslizador, reproducción y estado actual de Sol y Tierra ----
const FRAME_HOURS = 6; // cuánto avanza cada cuadro al reproducir

function fmtTime(d, i) {
  const ms = Date.parse(d.t0) + i * d.step_h * 3600e3;
  return `${new Date(ms).toISOString().replace("T", " ").slice(0, 16)} UTC`;
}

function bodyText(name, b, i) {
  const f = b.fraction ? b.fraction[i] : b.visible[i] ? 1 : 0;
  const estado = f >= 0.9999 ? "completo" : f > 0 ? "parcial" : "oculto";
  return `${name}: ${estado}, azimut ${fmt(b.az[i], 0)}°, elevación ${fmt(b.el[i])}°`;
}

function drawTime() {
  const d = state.data;
  if (!d) return;
  state.pano.setTime(state.t);
  state.timeline.setTime(state.t);
  $("t").value = state.t;
  $("t-label").textContent = fmtTime(d, state.t);
  $("chip-sun").textContent = bodyText("Sol", d.sun, state.t);
  $("chip-earth").textContent = bodyText("Tierra", d.earth, state.t);
}

function syncTime(i0, i1) {
  const slider = $("t");
  slider.min = i0;
  slider.max = i1 - 1;
  if (state.t < i0 || state.t >= i1) state.t = i0;
  drawTime();
}

function stop() {
  if (state.timer) clearInterval(state.timer);
  state.timer = null;
  $("play").textContent = "Reproducir";
}

function togglePlay() {
  if (state.timer) return stop();
  if (!state.data) return;
  $("play").textContent = "Pausar";
  state.timer = setInterval(() => {
    const [i0, i1] = state.range;
    const k = Math.max(1, Math.round(FRAME_HOURS / state.data.step_h));
    state.t = state.t + k >= i1 ? i0 : state.t + k;
    drawTime();
  }, 90);
}

function showError(msg) {
  const el = $("error");
  el.textContent = msg;
  el.hidden = !msg;
}

function latLon(site) {
  const ns = site.lat < 0 ? "S" : "N";
  const ew = site.lon < 0 ? "O" : "E";
  return `${fmt(Math.abs(site.lat), 2)}°${ns}, ${fmt(Math.abs(site.lon), 2)}°${ew}`;
}

async function selectSite(i) {
  const entry = state.index[i];
  showError("");
  try {
    if (!state.cache.has(entry.file)) {
      const d = await loadSite(entry.file);
      state.cache.set(entry.file, d);
      // Chequeo de consistencia: JS vs Python con el rango completo.
      const diffs = compareWithPython(d);
      if (diffs.length) console.warn(`[${d.site.name}] las métricas de JS no coinciden con las de Python:`, diffs);
      else console.info(`[${d.site.name}] métricas de JS = Python (rango completo)`);
    }
  } catch (err) {
    showError(err.message);
    return;
  }
  state.data = state.cache.get(entry.file);
  state.bounds = dateBounds(state.data);
  stop();
  state.pano.setSite(state.data);
  state.t = 0;

  const [min, max] = state.bounds;
  for (const id of ["from", "to"]) {
    $(id).min = min;
    $(id).max = max;
  }
  $("from").value = min;
  $("to").value = max;

  $("site-info").textContent = [latLon(state.data.site), state.data.site.note].filter(Boolean).join(". ");
  render();
}

function render() {
  const d = state.data;
  if (!d) return;

  const from = $("from").value;
  const to = $("to").value;
  const note = $("range-note");

  if (from && to && from > to) {
    note.textContent = "La fecha final es anterior a la inicial. Cambia una de las dos.";
    note.hidden = false;
    return;
  }

  const [i0, i1] = rangeToIndices(d, from, to);
  const m = metricsForRange(d, i0, i1);
  if (!m) {
    note.textContent = "No hay datos en ese rango.";
    note.hidden = false;
    return;
  }

  state.range = [i0, i1];
  state.timeline.setRange(d, i0, i1);
  syncTime(i0, i1);

  const days = ((i1 - i0) * d.step_h) / 24;
  note.hidden = days >= MIN_DAYS_NOTE;
  if (days < MIN_DAYS_NOTE) {
    note.textContent = `El rango es de ${fmt(days, 0)} días. Con ventanas cortas las cifras cambian mucho según la época; para comparar sitios usa al menos ${MIN_DAYS_NOTE} días.`;
  }

  // Luz solar
  $("sun-energy").textContent = pct(m.sun_energy_pct ?? m.pct_sun);
  $("sun-center").textContent = pct(m.pct_sun);
  $("max-dark").textContent = hours(m.max_dark_h);

  // Tierra como rango: completa / centro / algún pedazo
  const eFull = m.pct_earth_full ?? m.pct_earth;
  const eAny = m.pct_earth_any ?? m.pct_earth;
  $("earth-full").textContent = pct(eFull);
  $("earth-any").textContent = pct(eAny);
  $("l-full").textContent = pct(eFull);
  $("l-center").textContent = pct(m.pct_earth);
  $("l-any").textContent = pct(eAny);
  const bar = $("earth-range");
  bar.style.setProperty("--full", `${eFull}%`);
  bar.style.setProperty("--any", `${eAny}%`);
  bar.style.setProperty("--center", `${m.pct_earth}%`);
  $("max-no-earth").textContent = hours(m.max_no_earth_h);

  // Ambos
  $("both").textContent = pct(m.pct_both);

  // Transparencia del cálculo
  const meta = d.meta;
  let text = `DEM de ${meta.pixel_m} m, radio de ${fmt(meta.radius_km, 0)} km, observador a ${fmt(meta.observer_height_m, 0)} m sobre el suelo. Paso de ${fmt(d.step_h, 0)} h.`;
  const meta$ = $("meta");
  meta$.textContent = text;
  const warns = [];
  if (meta.truncated_pct > 0) warns.push(`El ${fmt(meta.truncated_pct)}% de los rayos del horizonte sale del mapa; las cifras de luz y Tierra pueden estar sobreestimadas.`);
  if (meta.horizon_gaps > 0) warns.push(`Hay ${meta.horizon_gaps} azimuts sin dato de terreno.`);
  for (const w of warns) {
    const s = document.createElement("span");
    s.className = "warn";
    s.textContent = w;
    meta$.appendChild(s);
  }
}

async function init() {
  try {
    state.index = await loadIndex();
  } catch (err) {
    showError(err.message);
    return;
  }

  const select = $("site");
  state.index.forEach((s, i) => {
    const opt = document.createElement("option");
    opt.value = i;
    opt.textContent = s.name;
    select.appendChild(opt);
  });

  select.addEventListener("change", () => selectSite(Number(select.value)));
  $("from").addEventListener("change", render);
  $("to").addEventListener("change", render);
  $("reset").addEventListener("click", () => {
    if (!state.bounds) return;
    $("from").value = state.bounds[0];
    $("to").value = state.bounds[1];
    render();
  });

  state.pano = new Panorama($("pano-svg"));
  state.timeline = new Timeline($("timeline"), (i) => {
    stop();
    state.t = i;
    drawTime();
  });
  $("play").addEventListener("click", togglePlay);
  $("t").addEventListener("input", (e) => {
    stop();
    state.t = Number(e.target.value);
    drawTime();
  });

  await selectSite(0);
}

init();