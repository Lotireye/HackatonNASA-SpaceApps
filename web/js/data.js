const DAY_MS = 86_400_000;

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}

export const loadIndex = () => getJSON("data/sites.json");
export const loadSite = (file) => getJSON(`data/${file}`);
export const timeOf = (site, i) => new Date(Date.parse(site.t0) + i * site.step_h * 3_600_000);
export const fmtUTC = (d) => d.toISOString().slice(0, 16).replace("T", " ") + " UTC";
export const fmt = (v, n = 1) => (v == null || Number.isNaN(v) ? "n/d" : v.toFixed(n));

export function dateBounds(site) {
  return { min: timeOf(site, 0).toISOString().slice(0, 10), max: timeOf(site, site.n - 1).toISOString().slice(0, 10) };
}

// Fechas "YYYY-MM-DD" (el día final entra completo) -> índices [i0, i1) de las series
export function rangeToIndices(site, startStr, endStr) {
  const t0 = Date.parse(site.t0), step = site.step_h * 3_600_000;
  const a = Date.parse(`${startStr}T00:00:00Z`), b = Date.parse(`${endStr}T00:00:00Z`) + DAY_MS;
  return [Math.max(0, Math.floor((a - t0) / step)), Math.min(site.n, Math.ceil((b - t0) / step))];
}

// Rachas consecutivas de igual valor: [inicio, fin, valor]
export const runs = (v, a, b) => {
  const o = []; let s = a;
  for (let k = a + 1; k <= b; k++) if (k === b || v[k] !== v[s]) { o.push([s, k, v[s]]); s = k; }
  return o;
};

function longestRun(flags, a, b, want) {
  let best = 0, cur = 0;
  for (let k = a; k < b; k++) { if (flags[k] === want) { cur++; if (cur > best) best = cur; } else cur = 0; }
  return best;
}

// Mismas definiciones que MetricsCalculator.summarize (criterio del centro del disco)
export function metricsForRange(site, a, b) {
  const sun = site.sun.visible, earth = site.earth.visible, n = b - a;
  let s = 0, e = 0, both = 0;
  for (let k = a; k < b; k++) { s += sun[k]; e += earth[k]; both += sun[k] & earth[k]; }
  return { pct_sun: (100 * s) / n, pct_earth: (100 * e) / n, pct_both: (100 * both) / n,
    max_dark_h: longestRun(sun, a, b, 0) * site.step_h, max_no_earth_h: longestRun(earth, a, b, 0) * site.step_h };
}

function frac(body, a, b) {
  const f = body.fraction;
  if (!f) return null;
  let e = 0, y = 0, z = 0;
  for (let k = a; k < b; k++) { e += f[k]; y += f[k] > 0; z += f[k] >= 1; }
  const n = b - a;
  return { energy: (100 * e) / n, any: (100 * y) / n, full: (100 * z) / n };
}

// Rango completo: valores exactos del pipeline. Rango parcial: aproximados desde `fraction` (redondeada a 2 decimales).
export function metrics(site, a, b) {
  const m = metricsForRange(site, a, b), M = site.metrics, whole = a === 0 && b === site.n;
  const s = frac(site.sun, a, b), e = frac(site.earth, a, b);
  return { ...m, exact: whole,
    sun_energy_pct: whole ? M.sun_energy_pct : s?.energy, pct_sun_any: whole ? M.pct_sun_any : s?.any,
    pct_sun_full: whole ? M.pct_sun_full : s?.full, pct_earth_any: whole ? M.pct_earth_any : e?.any,
    pct_earth_full: whole ? M.pct_earth_full : e?.full };
}
