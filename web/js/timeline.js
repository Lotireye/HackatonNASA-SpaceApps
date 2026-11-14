// Línea de tiempo: dos filas (Sol y Tierra) sobre el rango de fechas elegido.
// Cada columna agrupa varias muestras; su intensidad es la fracción media del disco
// sobre el horizonte (0 = oculto, 1 = completo). Hacer clic o arrastrar mueve el
// momento mostrado en el panorama.

const DAY_MS = 86400e3;
const H = 110; // alto en px CSS
const L = 54; // margen izquierdo (etiquetas de fila)
const R = 10;
const ROW_H = 30;
const ROWS = [
  { key: "sun", label: "Sol", y: 6 },
  { key: "earth", label: "Tierra", y: 44 },
];
const CURSOR_TOP = 2;
const CURSOR_BOTTOM = 78;
const AXIS_Y = 98;
const FONT = '11px "Instrument Sans", system-ui, sans-serif';

export class Timeline {
  constructor(container, onSeek) {
    this.onSeek = onSeek;
    this.canvas = document.createElement("canvas");
    this.canvas.setAttribute("role", "img");
    this.canvas.setAttribute("aria-label", "Línea de tiempo con las horas de Sol y de Tierra visibles en el rango elegido");
    container.replaceChildren(this.canvas);
    this.ctx = this.canvas.getContext("2d");

    this.d = null;
    this.i0 = 0;
    this.i1 = 0;
    this.t = 0;
    this.w = 0;
    this.bins = null;
    this.drag = false;
    this.#readColors();

    new ResizeObserver(() => this.#resize()).observe(container);
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      this.#readColors();
      this.#draw();
    });

    this.canvas.addEventListener("pointerdown", (e) => {
      this.canvas.setPointerCapture(e.pointerId);
      this.drag = true;
      this.#seek(e);
    });
    this.canvas.addEventListener("pointermove", (e) => {
      if (this.drag) this.#seek(e);
    });
    const end = () => (this.drag = false);
    this.canvas.addEventListener("pointerup", end);
    this.canvas.addEventListener("pointercancel", end);
  }

  setRange(d, i0, i1) {
    this.d = d;
    this.i0 = i0;
    this.i1 = i1;
    this.#computeBins();
    this.#draw();
  }

  setTime(i) {
    this.t = i;
    this.#draw();
  }

  get #plotW() {
    return this.w - L - R;
  }

  #readColors() {
    const css = getComputedStyle(document.documentElement);
    const v = (name) => css.getPropertyValue(name).trim() || "#888";
    this.colors = { sun: v("--sun"), earth: v("--earth"), line: v("--line"), text: v("--text"), muted: v("--muted") };
  }

  #resize() {
    const w = this.canvas.parentElement.clientWidth;
    if (!w) return;
    const dpr = window.devicePixelRatio || 1;
    this.w = w;
    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(H * dpr);
    this.canvas.style.height = `${H}px`;
    this.dpr = dpr;
    this.#computeBins();
    this.#draw();
  }

  // Media de fracción (o de visible si no hay fraction) por columna.
  #computeBins() {
    if (!this.d || this.#plotW <= 0) return;
    const n = this.i1 - this.i0;
    if (n <= 0) return;
    const nb = Math.max(1, Math.min(Math.floor(this.#plotW), n));
    this.bins = { nb };
    for (const { key } of ROWS) {
      const arr = this.d[key].fraction ?? this.d[key].visible;
      const out = new Float32Array(nb);
      for (let c = 0; c < nb; c++) {
        const s = this.i0 + Math.floor((c * n) / nb);
        const e = this.i0 + Math.floor(((c + 1) * n) / nb);
        let sum = 0;
        for (let j = s; j < e; j++) sum += arr[j];
        out[c] = e > s ? sum / (e - s) : 0;
      }
      this.bins[key] = out;
    }
  }

  #seek(e) {
    const n = this.i1 - this.i0;
    if (!this.d || n <= 0 || this.#plotW <= 0) return;
    const x = e.clientX - this.canvas.getBoundingClientRect().left;
    const idx = this.i0 + Math.floor(((x - L) / this.#plotW) * n);
    this.onSeek(Math.min(this.i1 - 1, Math.max(this.i0, idx)));
  }

  // Marcas del eje: meses, semanas o días según el largo del rango.
  #ticks() {
    const { d, i0, i1 } = this;
    const stepMs = d.step_h * 3600e3;
    const ms0 = Date.parse(d.t0);
    const startMs = ms0 + i0 * stepMs;
    const endMs = ms0 + i1 * stepMs;
    const days = (endMs - startMs) / DAY_MS;
    const mode = days > 150 ? "month" : days > 40 ? "week" : "day";
    const dayStep = days > 14 ? 2 : 1;

    let cur = new Date(startMs);
    cur.setUTCHours(0, 0, 0, 0);
    if (cur.getTime() < startMs) cur = new Date(cur.getTime() + DAY_MS);
    const first = cur.getTime();

    const ticks = [];
    for (; cur.getTime() < endMs; cur = new Date(cur.getTime() + DAY_MS)) {
      const dd = cur.getUTCDate();
      const dayIdx = Math.round((cur.getTime() - first) / DAY_MS);
      const ok = mode === "month" ? dd === 1 : mode === "week" ? [1, 8, 15, 22].includes(dd) : dayIdx % dayStep === 0;
      if (!ok) continue;
      const mon = cur.toLocaleDateString("es", { month: "short", timeZone: "UTC" });
      ticks.push({
        i: (cur.getTime() - ms0) / stepMs,
        label: mode === "month" ? mon : `${dd} ${mon}`,
      });
    }
    return ticks;
  }

  #draw() {
    const ctx = this.ctx;
    if (!ctx || !this.d || !this.bins || this.w <= 0) return;
    const n = this.i1 - this.i0;
    const pw = this.#plotW;
    const c = this.colors;

    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.clearRect(0, 0, this.w, H);
    ctx.font = FONT;
    ctx.textBaseline = "middle";

    for (const { key, label, y } of ROWS) {
      ctx.globalAlpha = 1;
      ctx.fillStyle = c.line;
      ctx.fillRect(L, y, pw, ROW_H);

      ctx.fillStyle = c[key];
      const colW = pw / this.bins.nb;
      const vals = this.bins[key];
      for (let k = 0; k < this.bins.nb; k++) {
        const v = vals[k];
        if (v <= 0) continue;
        ctx.globalAlpha = 0.25 + 0.75 * v; // cualquier pedazo visible se nota; el completo es el más intenso
        ctx.fillRect(L + k * colW, y, colW + 0.5, ROW_H);
      }

      ctx.globalAlpha = 1;
      ctx.fillStyle = c.muted;
      ctx.textAlign = "right";
      ctx.fillText(label, L - 8, y + ROW_H / 2);
    }

    // eje de fechas
    ctx.fillStyle = c.muted;
    ctx.strokeStyle = c.muted;
    ctx.lineWidth = 1;
    ctx.textAlign = "center";
    let lastX = -Infinity;
    for (const { i, label } of this.#ticks()) {
      const x = L + ((i - this.i0) / n) * pw;
      if (x < L || x > L + pw) continue;
      ctx.beginPath();
      ctx.moveTo(x + 0.5, CURSOR_BOTTOM);
      ctx.lineTo(x + 0.5, CURSOR_BOTTOM + 4);
      ctx.stroke();
      if (x - lastX >= 44) {
        ctx.fillText(label, x, AXIS_Y);
        lastX = x;
      }
    }

    // cursor del momento actual
    if (this.t >= this.i0 && this.t < this.i1) {
      const x = L + ((this.t - this.i0 + 0.5) / n) * pw;
      ctx.strokeStyle = c.text;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x, CURSOR_TOP);
      ctx.lineTo(x, CURSOR_BOTTOM);
      ctx.stroke();
    }
  }
}