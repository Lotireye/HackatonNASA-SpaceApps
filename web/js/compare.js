// Comparador de dos sitios sobre el mismo rango de fechas
import { fmt } from "./data.js";

const ROWS = [["Luz solar (energía)", "sun_energy_pct", "%"], ["Sol · centro del disco", "pct_sun", "%"],
  ["Tierra · centro del disco", "pct_earth", "%"], ["Tierra · disco completo", "pct_earth_full", "%"],
  ["Tierra · algún pedazo", "pct_earth_any", "%"], ["Sol y Tierra a la vez", "pct_both", "%"],
  ["Noche más larga", "max_dark_h", "h"], ["Mayor apagón de comunicación", "max_no_earth_h", "h"]];

// metricsOf(site) -> métricas del rango de fechas activo
export function createCompare(sites, metricsOf) {
  const $ = (id) => document.getElementById(id);
  const dlg = $("dlg"), sel = $("cmp-b"), tab = $("cmp-t");
  let cur = null;
  sites.forEach((s, i) => sel.add(new Option(s.site.name, i)));

  function fill() {
    const A = cur, B = sites[+sel.value], mA = metricsOf(A), mB = metricsOf(B);
    const c = (m, k, u) => `<td>${fmt(m[k], u === "h" ? 0 : 1)} ${u}</td>`;
    tab.innerHTML = `<tr><th></th><th>${A.site.name}</th><th>${B.site.name}</th></tr>` +
      ROWS.map(([l, k, u]) => `<tr><td>${l}</td>${c(mA, k, u)}${c(mB, k, u)}</tr>`).join("");
  }
  sel.onchange = fill;

  return {
    open(site) {
      cur = site;
      if (sites[+sel.value] === cur) sel.value = sites.findIndex((s) => s !== cur);
      fill();
      dlg.showModal();
    },
  };
}
