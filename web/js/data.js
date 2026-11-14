// Carga de datos y cálculo de métricas sobre los arrays ya precalculados.
// El frontend no calcula física: solo filtra por fechas y recuenta.

const HOUR_MS = 3600e3;
const DAY_MS = 24 * HOUR_MS;
// Umbral para "disco completo" sobre el horizonte (la fracción va de 0 a 1).
const FULL_THRESHOLD = 0.9999;

async function fetchJson(url) {
  const r = await fetch(url);
  if (!r.ok) {
    throw new Error(`No pude cargar ${url} (HTTP ${r.status}). ¿Corriste python -m pipeline.build y abriste la web con un servidor (python -m http.server 8000)?`);
  }
  return r.json();
}

export function loadIndex() {
  return fetchJson("data/sites.json");
}

export function loadSite(file) {
  return fetchJson(`data/${file}`);
}

// Rango de fechas (YYYY-MM-DD, ambas inclusivas, en UTC) -> índices [i0, i1) del array.
export function rangeToIndices(d, fromStr, toStr) {
  const t0 = Date.parse(d.t0);
  const step = d.step_h * HOUR_MS;
  const tEnd = t0 + d.n * step;

  let a = fromStr ? Date.parse(`${fromStr}T00:00:00Z`) : t0;
  let b = toStr ? Date.parse(`${toStr}T00:00:00Z`) + DAY_MS : tEnd;
  a = Math.min(Math.max(a, t0), tEnd);
  b = Math.min(Math.max(b, t0), tEnd);

  const i0 = Math.ceil((a - t0) / step);
  const i1 = Math.ceil((b - t0) / step);
  return [Math.max(0, i0), Math.min(d.n, i1)];
}

// Primer y último día (YYYY-MM-DD) cubiertos por el JSON.
export function dateBounds(d) {
  const t0 = Date.parse(d.t0);
  const last = t0 + d.n * d.step_h * HOUR_MS - 1;
  return [new Date(t0).toISOString().slice(0, 10), new Date(last).toISOString().slice(0, 10)];
}

// Racha más larga de "no visible" dentro de [i0, i1); se corta en los bordes del rango.
function longestRunOf(flags, i0, i1, value) {
  let best = 0;
  let cur = 0;
  for (let i = i0; i < i1; i++) {
    if (Boolean(flags[i]) === value) {
      cur++;
      if (cur > best) best = cur;
    } else {
      cur = 0;
    }
  }
  return best;
}

// Mismas definiciones que MetricsCalculator (summarize + summarize_disk) en Python.
export function metricsForRange(d, i0, i1) {
  const n = i1 - i0;
  if (n <= 0) return null;

  const sv = d.sun.visible;
  const ev = d.earth.visible;
  let sun = 0, earth = 0, both = 0;
  for (let i = i0; i < i1; i++) {
    const s = Boolean(sv[i]);
    const e = Boolean(ev[i]);
    if (s) sun++;
    if (e) earth++;
    if (s && e) both++;
  }
  const pct = (c) => (100 * c) / n;

  const m = {
    pct_sun: pct(sun),
    pct_earth: pct(earth),
    pct_both: pct(both),
    max_dark_h: longestRunOf(sv, i0, i1, false) * d.step_h,
    max_no_earth_h: longestRunOf(ev, i0, i1, false) * d.step_h,
  };

  // Métricas de disco: solo si el JSON trae `fraction`.
  const sf = d.sun.fraction;
  const ef = d.earth.fraction;
  if (sf && ef) {
    let sEnergy = 0, sAny = 0, sFull = 0, eAny = 0, eFull = 0;
    for (let i = i0; i < i1; i++) {
      sEnergy += sf[i];
      if (sf[i] > 0) sAny++;
      if (sf[i] >= FULL_THRESHOLD) sFull++;
      if (ef[i] > 0) eAny++;
      if (ef[i] >= FULL_THRESHOLD) eFull++;
    }
    m.sun_energy_pct = (100 * sEnergy) / n;
    m.pct_sun_any = pct(sAny);
    m.pct_sun_full = pct(sFull);
    m.pct_earth_any = pct(eAny);
    m.pct_earth_full = pct(eFull);
  }
  return m;
}

// Con el rango completo, las métricas de JS deben coincidir con las que escribió Python.
// Devuelve la lista de diferencias (vacía si todo coincide).
export function compareWithPython(d, tol = 0.15) {
  const js = metricsForRange(d, 0, d.n);
  const diffs = [];
  for (const [key, py] of Object.entries(d.metrics)) {
    if (!(key in js)) continue;
    const delta = Math.abs(js[key] - py);
    if (delta > tol) diffs.push({ key, js: js[key], python: py, delta });
  }
  return diffs;
}