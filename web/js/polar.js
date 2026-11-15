// Panorama del horizonte: azimut (x) vs elevación (y). El terreno se dibuja encima de Sol y Tierra.
const W = 960, H = 380;
const M = { top: 14, right: 16, bottom: 34, left: 46 };
const TRAIL_DAYS = 30;
const DIRS = { 0: "N", 45: "NE", 90: "E", 135: "SE", 180: "S", 225: "SO", 270: "O", 315: "NO", 360: "N" };

export function createPanorama(root) {
  const svg = d3.select(root).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("width", "100%")
    .attr("role", "img").attr("aria-label", "Horizonte del sitio con la posición del Sol y de la Tierra");
  svg.append("defs").append("clipPath").attr("id", "plot-clip").append("rect")
    .attr("x", M.left).attr("y", M.top).attr("width", W - M.left - M.right).attr("height", H - M.top - M.bottom);

  const x = d3.scaleLinear([0, 360], [M.left, W - M.right]);
  const y = d3.scaleLinear([-10, 15], [H - M.bottom, M.top]);
  const line = d3.line().x((p) => x(p[0])).y((p) => y(p[1]));

  const gGrid = svg.append("g");
  const plot = svg.append("g").attr("clip-path", "url(#plot-clip)");
  const sunTrail = plot.append("path").attr("class", "trail sun");
  const earthTrail = plot.append("path").attr("class", "trail earth");
  const sunDot = plot.append("circle").attr("r", 6).attr("class", "body sun");
  const earthDot = plot.append("circle").attr("r", 9).attr("class", "body earth");
  const gTerrain = svg.append("g");
  const gAxes = svg.append("g");

  function setSite(site) {
    const hv = site.horizon.filter((v) => v !== null);
    const lo = Math.min(d3.min(site.earth.el), d3.min(site.sun.el), d3.min(hv) ?? 0, -2) - 1;
    const hi = Math.max(d3.max(site.earth.el), d3.max(site.sun.el), d3.max(hv) ?? 0, 4) + 2;
    y.domain([lo, hi]);
    for (const g of [gGrid, gTerrain, gAxes]) g.selectAll("*").remove();

    gGrid.selectAll("line.v").data(d3.range(0, 361, 45)).join("line").attr("class", "v")
      .attr("x1", (d) => x(d)).attr("x2", (d) => x(d)).attr("y1", M.top).attr("y2", H - M.bottom);
    gGrid.append("line").attr("class", "zero").attr("x1", M.left).attr("x2", W - M.right).attr("y1", y(0)).attr("y2", y(0));

    const pts = site.horizon.map((el, k) => ({ az: (k * 360) / site.horizon.length, el }));
    pts.push({ az: 360, el: site.horizon[0] });
    gTerrain.append("path").datum(pts).attr("class", "terrain")
      .attr("d", d3.area().defined((p) => p.el !== null).x((p) => x(p.az)).y0(y(lo)).y1((p) => y(p.el)));
    gTerrain.append("path").datum(pts).attr("class", "ridge")
      .attr("d", d3.line().defined((p) => p.el !== null).x((p) => x(p.az)).y((p) => y(p.el)));

    gAxes.append("g").attr("transform", `translate(0,${H - M.bottom})`)
      .call(d3.axisBottom(x).tickValues(d3.range(0, 361, 45)).tickFormat((d) => `${DIRS[d]} ${d}°`));
    gAxes.append("g").attr("transform", `translate(${M.left},0)`).call(d3.axisLeft(y).ticks(8).tickFormat((d) => `${d}°`));
  }

  // Trayectoria como un path; se corta cuando el azimut salta de 360° a 0°
  function trailD(body, a, b) {
    let d = "", seg = [];
    const flush = () => { if (seg.length > 1) d += line(seg); seg = []; };
    for (let k = a; k < b; k++) {
      if (seg.length && Math.abs(body.az[k] - body.az[k - 1]) > 180) flush();
      seg.push([body.az[k], body.el[k]]);
    }
    flush();
    return d;
  }

  const place = (dot, body, i) => dot.attr("cx", x(body.az[i])).attr("cy", y(body.el[i])).classed("hidden", body.visible[i] !== 1);

  // i: instante actual; end: fin (exclusivo) del rango elegido
  function update(site, i, end) {
    const stop = Math.min(end, i + Math.round((TRAIL_DAYS * 24) / site.step_h));
    sunTrail.attr("d", trailD(site.sun, i, stop));
    earthTrail.attr("d", trailD(site.earth, i, stop));
    place(sunDot, site.sun, i);
    place(earthDot, site.earth, i);
  }

  return { setSite, update };
}
