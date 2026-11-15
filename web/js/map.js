// Mapa polar esquemático (proyección estereográfica polar sur; lon 0 arriba, lon 90E a la derecha)
const R = 1737.4, EXT = 320, K = 270 / EXT, C = 300;      // radio lunar (km), alcance (km), px/km, centro
const rho = (lat) => 2 * R * Math.tan(((90 + lat) * Math.PI) / 360);

export function createMap(el, onPick) {
  const svg = d3.select(el);

  function draw(sites, bg) {
    svg.html("");
    if (bg) {   // relieve exportado del DEM (pipeline/export_map.py); bg trae los límites en metros
      const k = K / 1000;
      svg.append("image").attr("href", bg.href).attr("preserveAspectRatio", "none").attr("opacity", 0.9)
        .attr("x", C + bg.left_m * k).attr("y", C - bg.top_m * k)
        .attr("width", (bg.right_m - bg.left_m) * k).attr("height", (bg.top_m - bg.bottom_m) * k);
    }
    for (const lat of [-80, -85, -88]) {
      svg.append("circle").attr("class", "ring").attr("cx", C).attr("cy", C).attr("r", rho(lat) * K);
      svg.append("text").attr("class", "rl").attr("x", C + 16).attr("y", C - rho(lat) * K - 4).text(`${-lat}°S`);
    }
    svg.append("path").attr("class", "ring").attr("d", `M${C} 24V576M24 ${C}H576`);
    [["0°", C, 16], ["90°E", 584, C + 4], ["180°", C, 596], ["90°O", 16, C + 4]]
      .forEach(([t, x, y]) => svg.append("text").attr("class", "rl").attr("x", x).attr("y", y).text(t));

    const g = svg.selectAll("g.pin").data(sites).join("g").attr("class", "pin").attr("tabindex", 0).attr("role", "button")
      .attr("aria-label", (d) => `Seleccionar ${d.site.name}`)
      .attr("transform", (d) => {
        const r = rho(d.site.lat) * K, l = (d.site.lon * Math.PI) / 180;
        return `translate(${C + r * Math.sin(l)},${C - r * Math.cos(l)})`;
      })
      .on("click", (e, d) => onPick(d))
      .on("keydown", (e, d) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPick(d); } });
    g.append("title").text((d) => `${d.site.name} · ${d.site.lat}°, ${d.site.lon}° · altura ${d.meta.site_height_m} m`);
    g.append("circle").attr("r", 7);
    g.append("text").attr("x", 12).attr("y", 4).text((d) => d.site.name);
  }

  const select = (site) => svg.selectAll(".pin").classed("sel", (d) => d === site);
  return { draw, select };
}
