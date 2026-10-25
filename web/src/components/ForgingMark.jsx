import React, { useEffect, useRef, useState } from "react";
import { BrandMark } from "./Visuals";

// The brand mark at work: a smith's hammer forging the forge-gate M on an anvil
// while the whole scene turns once every five seconds. Four blows land at the
// three-quarter views; each one heats the struck shoulder and throws sparks.
// Every frame is a pure function of the time within the loop, so the loop has
// no seam. Reduced motion gets one still frame: a blow just landed, seen nearly
// head-on.

const LOOP = 5000;
const BLOW = LOOP / 4;
const FIRST_BLOW = LOOP / 8;
const STILL = FIRST_BLOW + 90;
const STILL_TURN = -0.07;

// The canvas is 72 by 60 scene units. The stylesheet sizes a unit from the slot
// and lets the canvas overhang it, so the raised hammer and the sparks can leave
// the slot; the world origin, the M's base on the anvil, sits at ORIGIN.
const CANVAS_W = 72;
const ORIGIN = [36, 42];
const TILT = 15 * Math.PI / 180;
const DIST = 150;

const norm = ([x, y, z]) => { const l = Math.hypot(x, y, z); return [x / l, y / l, z / l]; };
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const mod = (a, n) => ((a % n) + n) % n;
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const LIGHT = norm([-0.45, 0.6, 0.66]);
const HALF = norm([LIGHT[0], LIGHT[1], LIGHT[2] + 1]);

// A planar profile extruded symmetrically along z: both caps plus one quad per edge,
// each wound counter-clockwise about its outward normal.
function prism(profile, depth) {
  const signed = profile.reduce((a, [x, y], i) => { const [x2, y2] = profile[(i + 1) % profile.length]; return a + x * y2 - x2 * y; }, 0);
  const pts = signed < 0 ? profile.slice().reverse() : profile;
  const n = pts.length;
  const faces = [{ cap: true, idx: pts.map((_, i) => n + i), normal: [0, 0, 1] }, { cap: true, idx: pts.map((_, i) => n - 1 - i), normal: [0, 0, -1] }];
  pts.forEach(([x, y], i) => {
    const j = (i + 1) % n, [x2, y2] = pts[j];
    faces.push({ idx: [i, j, n + j, n + i], normal: norm([y2 - y, x - x2, 0]) });
  });
  return { verts: [...pts.map(([x, y]) => [x, y, -depth]), ...pts.map(([x, y]) => [x, y, depth])], faces };
}

// The 32px mark's coordinates, with y turned upward and the base centred on the anvil.
const fromMark = pts => pts.map(([x, y]) => [x - 16, 27 - y]);
const GATE = prism(fromMark([[4, 9], [7, 6], [11.5, 6], [16, 13.5], [20.5, 6], [25, 6], [28, 9], [28, 25.5], [26.5, 27], [22, 27], [22, 10.5], [16, 20.5], [10, 10.5], [10, 27], [5.5, 27], [4, 25.5]]), 2.75);
const DOOR = prism(fromMark([[13, 27], [13, 24.75], [14.5, 23.25], [17.5, 23.25], [19, 24.75], [19, 27]]), 1.5);
const ANVIL = prism([[-9.5, -7.5], [9.5, -7.5], [9.5, -6.4], [5.5, -5.2], [5.5, -3.8], [13, -2.6], [13, 0], [-11.5, 0], [-19, -0.6], [-12.5, -2.6], [-5.5, -3.8], [-5.5, -5.2], [-9.5, -6.4]], 3.75);
// The hammer is drawn around its grip: a cross-peen head whose face lands on the
// M's right shoulder, and a haft running back past the hand.
const HEAD = prism([[-10.75, -3.25], [-6.75, -3.25], [-6.75, 1.1], [-8.2, 3.25], [-9.3, 3.25], [-10.75, 1.1]], 2);
const HAFT = prism([[-6.75, -0.6], [3, -0.85], [3, 0.85], [-6.75, 0.6]], 0.7);
const GRIP = [15.5, 24.25];
const CONTACT = [6.75, 21, 0];

// Heat from dull red through the brand orange to white.
const RAMP = [[0, 96, 14, 0], [0.3, 196, 42, 0], [0.55, 255, 95, 5], [0.75, 255, 166, 62], [0.9, 255, 226, 152], [1, 255, 250, 232]];
function ramp(x) {
  const v = clamp(x, 0, 1);
  for (let i = 1; i < RAMP.length; i++) {
    if (v > RAMP[i][0]) continue;
    const [p0, ...a] = RAMP[i - 1], [p1, ...b] = RAMP[i], u = (v - p0) / (p1 - p0);
    return a.map((c, j) => c + (b[j] - c) * u);
  }
  return RAMP[RAMP.length - 1].slice(1);
}
const rgb = (c, a = 1) => `rgba(${clamp(Math.round(c[0]), 0, 255)}, ${clamp(Math.round(c[1]), 0, 255)}, ${clamp(Math.round(c[2]), 0, 255)}, ${a})`;

const metal = (base, amb, dif, spec, shine) => n => {
  const k = amb + dif * Math.max(0, dot(n, LIGHT)), g = spec * Math.max(0, dot(n, HALF)) ** shine;
  return [base[0] * k + 230 * g, base[1] * k + 238 * g, base[2] * k + 250 * g];
};
const IRON = metal([104, 130, 172], 0.38, 0.78, 0.5, 16);
const ANVIL_IRON = metal([70, 90, 124], 0.42, 0.72, 0.4, 12);
const STEEL = metal([140, 160, 194], 0.36, 0.74, 0.75, 22);
const HAFT_IRON = metal([94, 108, 134], 0.45, 0.65, 0.25, 10);
const EMBER = (n, heat) => ramp(0.42 + 0.3 * heat).map(c => c * (0.78 + 0.22 * Math.max(0, n[2])));

// The hammer's angle above the strike, in degrees, through one blow: rebound,
// settle, lift, a held breath at the top, then an accelerating fall.
const easeOut = u => 1 - (1 - u) ** 2;
const easeInOut = u => (u < 0.5 ? 4 * u ** 3 : 1 - (-2 * u + 2) ** 3 / 2);
const easeIn = u => u ** 3;
const SWING = [[0, 90, 0, 9, easeOut], [90, 200, 9, 5, easeInOut], [200, 880, 5, 58, easeInOut], [880, 1010, 58, 61, easeOut], [1010, BLOW, 61, 0, easeIn]];
function swing(d) {
  const [from, to, a, b, ease] = SWING.find(([, end]) => d < end) || SWING[SWING.length - 1];
  const deg = a + (b - a) * ease(clamp((d - from) / (to - from), 0, 1));
  const lift = deg / 61;
  return { angle: deg * Math.PI / 180, x: GRIP[0] + 0.8 * lift, y: GRIP[1] + 2.2 * lift };
}

// Sparks for each blow, seeded so every loop throws the same ones.
function seeded(seed) {
  let s = seed;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
// They burst from the rim of the hammer face, mostly outward and a little upward,
// then slow in the air and arc down as they cool.
const DRAG = 300;
const GRAVITY = 0.00007;
const SPARKS = [0, 1, 2, 3].map(k => {
  const rand = seeded(97 + 131 * k);
  return Array.from({ length: 26 }, () => {
    const psi = rand() * Math.PI * 2, rise = -0.15 + 1.05 * rand(), speed = 0.035 + 0.07 * rand() ** 1.6;
    return {
      origin: [CONTACT[0] + 2.2 * Math.cos(psi), CONTACT[1] + 0.2, 2.2 * Math.sin(psi)],
      velocity: [speed * Math.cos(rise) * Math.cos(psi), speed * Math.sin(rise), speed * Math.cos(rise) * Math.sin(psi)],
      life: 280 + 420 * rand(), bright: 0.55 + 0.45 * rand(), width: rand(),
    };
  });
});
function sparkAt(spark, age) {
  const e = DRAG * (1 - Math.exp(-age / DRAG)), [x, y, z] = spark.origin, [vx, vy, vz] = spark.velocity;
  return [x + vx * e, y + vy * e - 0.5 * GRAVITY * age * age, z + vz * e];
}

function camera(theta, unit) {
  const ct = Math.cos(theta), st = Math.sin(theta), cx = Math.cos(TILT), sx = Math.sin(TILT);
  const turn = ([x, y, z]) => { const x1 = x * ct + z * st, z1 = -x * st + z * ct; return [x1, y * cx - z1 * sx, y * sx + z1 * cx]; };
  const screen = ([x, y, z]) => { const k = DIST / (DIST - z) * unit; return [ORIGIN[0] * unit + x * k, ORIGIN[1] * unit - y * k]; };
  return { turn, screen, at: p => screen(turn(p)) };
}

const STILL_SOLID = { place: p => p, orient: n => n };

// Gathers the faces of a solid that look toward the camera. A shell's near cap is
// held back, because nothing inside the shell's own slab can cover it.
function collect(solid, cam, faces, holdCap) {
  const view = solid.shape.verts.map(v => cam.turn(solid.place(v)));
  const screen = view.map(cam.screen);
  let cap = null;
  for (const f of solid.shape.faces) {
    const n = cam.turn(solid.orient(f.normal));
    const c = [0, 1, 2].map(j => f.idx.reduce((sum, i) => sum + view[i][j], 0) / f.idx.length);
    if (n[0] * -c[0] + n[1] * -c[1] + n[2] * (DIST - c[2]) <= 0) continue;
    const face = { pts: f.idx.map(i => screen[i]), n, z: c[2], cap: f.cap, solid };
    if (f.cap && holdCap) cap = face; else faces.push(face);
  }
  return cap;
}

function fill(ctx, face, heat) {
  const color = face.solid.tone(face.n, heat);
  ctx.beginPath();
  face.pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
  ctx.closePath();
  let paint = rgb(color);
  if (face.cap && face.solid.sheen) {
    const ys = face.pts.map(p => p[1]), sheen = ctx.createLinearGradient(0, Math.min(...ys), 0, Math.max(...ys));
    sheen.addColorStop(0, rgb(color.map(c => c * 1.16)));
    sheen.addColorStop(1, rgb(color.map(c => c * 0.82)));
    paint = sheen;
  }
  ctx.fillStyle = paint;
  ctx.strokeStyle = paint;
  ctx.fill();
  ctx.stroke();
}

// Draws solids as one body: their faces back to front, then the first solid's near cap.
function drawBody(ctx, solids, cam, heat) {
  const faces = [];
  const cap = solids.map((solid, i) => collect(solid, cam, faces, i === 0))[0];
  faces.sort((a, b) => a.z - b.z).forEach(face => fill(ctx, face, heat));
  if (cap) fill(ctx, cap, heat);
}

function glow(ctx, [x, y], radius, color, alpha) {
  const g = ctx.createRadialGradient(x, y, 0, x, y, radius);
  g.addColorStop(0, rgb(color, alpha));
  g.addColorStop(1, rgb(color, 0));
  ctx.fillStyle = g;
  ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2);
}

// Paints the scene at time t in the loop, turned by `turn` of a full revolution.
function paintScene(ctx, layer, t, unit, turn = t / LOOP) {
  const { width, height } = ctx.canvas;
  for (const c of [ctx, layer]) {
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.globalCompositeOperation = "source-over";
    c.clearRect(0, 0, width, height);
    c.lineJoin = "round";
    c.lineWidth = 0.35 * unit;
  }
  if (!width || !unit) return;
  const cam = camera(2 * Math.PI * turn, unit);
  const ages = [0, 1, 2, 3].map(k => mod(t - FIRST_BLOW - k * BLOW, LOOP));
  const heat = clamp(0.28 + 0.8 * ages.reduce((sum, a) => sum + Math.exp(-a / 380), 0), 0, 1);
  const contact = cam.at(CONTACT);

  // A soft shadow grounds the anvil.
  const [sx, sy] = cam.at([0, -7.6, 0]);
  ctx.save();
  ctx.translate(sx, sy);
  ctx.scale(1, 0.26);
  glow(ctx, [0, 0], 18 * unit, [2, 8, 20], 0.55);
  ctx.restore();

  drawBody(ctx, [{ ...STILL_SOLID, shape: ANVIL, tone: ANVIL_IRON }], cam, heat);

  // The M and its furnace door go to their own layer so the heat can soak into the metal alone.
  drawBody(layer, [{ ...STILL_SOLID, shape: GATE, tone: IRON, sheen: true }, { ...STILL_SOLID, shape: DOOR, tone: EMBER }], cam, heat);
  layer.globalCompositeOperation = "source-atop";
  const hot = layer.createRadialGradient(contact[0], contact[1], 0, contact[0], contact[1], (4 + 6 * heat) * unit);
  hot.addColorStop(0, rgb(ramp(0.15 + 0.85 * heat), 0.55 + 0.4 * heat));
  hot.addColorStop(0.45, rgb(ramp(0.1 + 0.55 * heat), 0.2 + 0.4 * heat));
  hot.addColorStop(1, rgb(ramp(0.1), 0));
  layer.fillStyle = hot;
  layer.fillRect(0, 0, width, height);
  ctx.drawImage(layer.canvas, 0, 0);

  const pose = swing(mod(t - FIRST_BLOW, BLOW));
  const c = Math.cos(pose.angle), s = Math.sin(pose.angle);
  const orient = ([x, y, z]) => [x * c + y * s, -x * s + y * c, z];
  const place = p => { const [x, y, z] = orient(p); return [pose.x + x, pose.y + y, z]; };
  const depth = p => cam.turn(place(p))[2];
  const hammer = [{ shape: HEAD, tone: STEEL, centre: [-8.75, 0, 0] }, { shape: HAFT, tone: HAFT_IRON, centre: [-1.9, 0, 0] }];
  hammer.sort((a, b) => depth(a.centre) - depth(b.centre)).forEach(part => drawBody(ctx, [{ ...part, place, orient }], cam, heat));

  // Light: the forge glow, the flash of each blow, then the sparks.
  ctx.globalCompositeOperation = "lighter";
  glow(ctx, contact, (10 + 8 * heat) * unit, ramp(0.6), 0.22 * heat * heat);
  ages.forEach(a => { if (a < 150) glow(ctx, contact, (4 + 14 * a / 150) * unit, [255, 214, 150], 0.7 * (1 - a / 150) ** 2); });
  ctx.lineCap = "round";
  ages.forEach((age, k) => SPARKS[k].forEach(spark => {
    if (age >= spark.life) return;
    const f = age / spark.life, [x0, y0] = cam.at(sparkAt(spark, Math.max(0, age - 40))), [x1, y1] = cam.at(sparkAt(spark, age));
    ctx.strokeStyle = rgb(ramp(1 - 0.7 * f), spark.bright * (1 - f) ** 0.6);
    ctx.lineWidth = (0.7 + 0.5 * spark.width) * unit;
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.stroke();
  }));
}

export function ForgingMark() {
  const canvasRef = useRef(null);
  const [drawable, setDrawable] = useState(true);
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas && canvas.getContext && canvas.getContext("2d");
    const layer = ctx ? document.createElement("canvas").getContext("2d") : null;
    if (!layer) { setDrawable(false); return undefined; }
    const reduce = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
    let frame = 0, ratio = 0, unit = 0, visible = true;
    const fit = () => {
      ratio = window.devicePixelRatio || 1;
      const box = canvas.getBoundingClientRect(), w = Math.round(box.width * ratio), h = Math.round(box.height * ratio);
      if (canvas.width !== w || canvas.height !== h) { canvas.width = layer.canvas.width = w; canvas.height = layer.canvas.height = h; }
      unit = w / CANVAS_W;
    };
    const tick = now => {
      if (ratio !== (window.devicePixelRatio || 1)) fit();
      paintScene(ctx, layer, now % LOOP, unit);
      frame = requestAnimationFrame(tick);
    };
    const run = () => {
      cancelAnimationFrame(frame);
      if (reduce && reduce.matches) paintScene(ctx, layer, STILL, unit, STILL_TURN);
      else if (visible) frame = requestAnimationFrame(tick);
    };
    const resized = typeof ResizeObserver === "function" ? new ResizeObserver(() => { fit(); run(); }) : null;
    const seen = typeof IntersectionObserver === "function" ? new IntersectionObserver(entries => { visible = entries[entries.length - 1].isIntersecting; run(); }) : null;
    if (resized) resized.observe(canvas);
    if (seen) seen.observe(canvas);
    if (reduce && reduce.addEventListener) reduce.addEventListener("change", run);
    fit();
    run();
    return () => {
      cancelAnimationFrame(frame);
      if (resized) resized.disconnect();
      if (seen) seen.disconnect();
      if (reduce && reduce.removeEventListener) reduce.removeEventListener("change", run);
    };
  }, []);
  if (!drawable) return <BrandMark />;
  return <span className="brand-forge" aria-hidden="true"><canvas ref={canvasRef} /></span>;
}
