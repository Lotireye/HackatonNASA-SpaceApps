// Dos filas (Sol, Tierra): bloques de visibilidad vs. oscuridad en el rango elegido
import { runs } from "./data.js";

const W = 1000;

export function createTimeline(el, onSeek) {
  let a = 0, b = 1;

  el.addEventListener("click", (ev) => {
    const r = el.getBoundingClientRect();
    onSeek(Math.min(b - 1, a + Math.floor(((ev.clientX - r.left) / r.width) * (b - a))));
  });

  function draw(site, i0, i1) {
    a = i0; b = i1;
    const n = b - a;
    const row = (body, cls, y) => runs(body.visible, a, b).map(([p, q, v]) =>
      `<rect class="${v ? "on" : "off"} ${cls}" x="${((p - a) / n) * W}" y="${y}" width="${Math.max(((q - p) / n) * W, 0.5)}" height="18"/>`).join("");
    el.innerHTML = row(site.sun, "sun", 2) + row(site.earth, "earth", 24) + `<line id="cur" y1="0" y2="44"/>`;
  }

  function setCursor(i) {
    const c = el.querySelector("#cur");
    if (!c) return;
    const x = ((i - a) / (b - a)) * W;
    c.setAttribute("x1", x); c.setAttribute("x2", x);
  }

  return { draw, setCursor };
}
