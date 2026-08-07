"use strict";
// Maze Game GUI — spectator only.
// Polls /view?viewer_key=... and renders the board. No manual control.

const $ = (id) => document.getElementById(id);
const GRID = 80; // grid edge (matches server config.GRID_SIZE)

const state = {
  base: "",
  viewerKey: "",
  tick: 0,
  players: [],          // [{id,name,current_position,life,coins_captured,motion_count,alive}]
  coins: [],            // [[x,y], ...]
  obstacles: [],        // [[x,y], ...]  (filled once per world)
  colors: new Map(),    // id -> color (random, cached per session)
  polling: null,
};

// --- persistence (server url + viewer key only) ---------------------------
function loadStored() {
  try {
    const s = JSON.parse(localStorage.getItem("maze-gui") || "{}");
    if (s.base) $("base-url").value = s.base;
    if (s.viewerKey) $("viewer-key").value = s.viewerKey;
  } catch (e) { /* ignore */ }
}
function saveStored() {
  localStorage.setItem("maze-gui", JSON.stringify({
    base: state.base,
    viewerKey: state.viewerKey,
  }));
}

// --- toast ----------------------------------------------------------------
let toastTimer = null;
function toast(msg, kind = "") {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast" + (kind ? " " + kind : "");
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 5000);
}

// --- per-player color (curated palette, cached by id) ---------------------
// Curated ~32-color palette, hand-tuned so every hue stays vivid on the dark
// board (yellows/greens/cyans brightened so they don't read as muddy). Players
// cycle by id; beyond the palette we fall back to a golden-angle HSL spread so
// 30+ players never silently repeat a color. Stable across reconnects/polls.
const PALETTE = [
  "#f87171", "#60a5fa", "#fbbf24", "#22d3ee", // red, blue, amber, cyan
  "#fb923c", "#a78bfa", "#4ade80", "#f472b6", // orange, violet, green, pink
  "#facc15", "#818cf8", "#2dd4bf", "#fb7185", // yellow, indigo, teal, rose
  "#a3e635", "#c084fc", "#38bdf8", "#fda4af", // lime, purple, sky, light-rose
  "#fde047", "#7c3aed", "#10b981", "#ec4899", // bright-yellow, deep-violet, emerald, magenta
  "#fcd34d", "#6366f1", "#14b8a6", "#f9a8d4", // gold, deep-indigo, teal-2, light-pink
  "#bef264", "#d946ef", "#0ea5e9", "#f87171", // soft-lime, fuchsia, sky-2, red-2 (deep)
  "#fdba74", "#8b5cf6", "#65a30d", "#e11d48", // light-orange, deep-purple, olive, crimson
];
function colorFor(id) {
  let c = state.colors.get(id);
  if (c) return c;
  const n = Number(id);
  const i = (n - 1) % PALETTE.length;
  if (n - 1 < PALETTE.length) {
    c = PALETTE[i];
  } else {
    // overflow: golden-angle hue at fixed vivid S/L for >32 players
    const hue = ((n * 137.508) % 360 + 360) % 360;
    c = `hsl(${hue.toFixed(1)} 70% 62%)`;
  }
  state.colors.set(id, c);
  return c;
}

// --- HTTP ----------------------------------------------------------------
async function apiGet(path, params) {
  const u = new URL(state.base + path, state.base || "http://x");
  if (params) for (const k in params) if (params[k] != null) u.searchParams.set(k, params[k]);
  const res = await fetch(u.toString());
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || res.statusText), { code: data.code });
  return data;
}

// --- spectator polling -----------------------------------------------------
async function pollView() {
  try {
    const v = await apiGet("/view", { viewer_key: state.viewerKey });
    state.tick = v.current_tick;
    state.players = v.players || [];
    state.coins = v.coins_uncollected_location || [];
    if (v.obstacles_location && v.obstacles_location.length) {
      state.obstacles = v.obstacles_location;
    }
    render();
    $("conn").textContent = "live";
    $("conn").style.color = "var(--accent2)";
  } catch (e) {
    $("conn").textContent = "error: " + (e.code || e.message);
    $("conn").style.color = "var(--danger)";
  }
}

function startPolling() {
  stopPolling();
  pollView(); // immediate
  state.polling = setInterval(pollView, 1000);
}
function stopPolling() {
  if (state.polling) clearInterval(state.polling);
  state.polling = null;
}

// --- rendering ------------------------------------------------------------
const canvas = $("board");
const ctx = canvas.getContext("2d");
let cell = 9; // recomputed in resize()

function resize() {
  const wrap = $("board-wrap");
  const avail = Math.min(wrap.clientWidth - 16, window.innerHeight - 110);
  const px = Math.max(300, avail);
  cell = Math.floor(px / GRID);            // integer cells stay crisp
  const dim = cell * GRID;
  canvas.width = dim;
  canvas.height = dim;
  canvas.style.width = dim + "px";
  canvas.style.height = dim + "px";
  render();
}
window.addEventListener("resize", resize);

// Equilateral triangle pointing up, centered at (cx,cy), circumradius r.
function drawTriangle(cx, cy, r, fill, stroke) {
  ctx.beginPath();
  ctx.moveTo(cx, cy - r);
  ctx.lineTo(cx - r * 0.8660, cy + r * 0.5);
  ctx.lineTo(cx + r * 0.8660, cy + r * 0.5);
  ctx.closePath();
  if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  if (stroke) { ctx.strokeStyle = stroke; ctx.stroke(); }
}

function render() {
  const dim = cell * GRID;
  ctx.clearRect(0, 0, dim, dim);
  ctx.fillStyle = "#05070a";
  ctx.fillRect(0, 0, dim, dim);

  // obstacles
  ctx.fillStyle = "#2a323c";
  for (const [x, y] of state.obstacles) {
    ctx.fillRect(x * cell, y * cell, cell, cell);
  }

  // coins (gold, pulsing by tick)
  const pulse = 0.5 + 0.5 * Math.sin((state.tick || 0) * 0.6);
  for (const [x, y] of state.coins) {
    const cx = x * cell + cell / 2;
    const cy = y * cell + cell / 2;
    ctx.fillStyle = `rgba(255,200,0,${0.35 + 0.4 * pulse})`;
    ctx.beginPath(); ctx.arc(cx, cy, cell * 0.9, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#ffd33d";
    ctx.beginPath(); ctx.arc(cx, cy, cell * 0.42, 0, Math.PI * 2); ctx.fill();
  }

  // players: bigger triangles, one random color each
  const r = cell * 1.2; // circumradius → big bold triangles (overflow into neighbours is fine)
  for (const p of state.players) {
    const [x, y] = p.current_position;
    const cx = x * cell + cell / 2;
    const cy = y * cell + cell / 2;
    ctx.lineWidth = Math.max(1, cell * 0.08);
    drawTriangle(cx, cy, r, colorFor(p.id), "rgba(0,0,0,0.85)");
    // life pip along the bottom edge of the cell (under the triangle base)
    const life = Math.max(0, Math.min(150, p.life));
    ctx.fillStyle = life > 50 ? "#3fb950" : life > 20 ? "#d29922" : "#f85149";
    const bh = Math.max(1, cell * 0.16);
    ctx.fillRect(x * cell, y * cell + cell - bh, Math.round(cell * (life / 150)), bh);
  }

  $("hud").textContent =
    `tick ${state.tick} · ${state.players.length} alive · ${state.coins.length} coins · ${cell}px`;

  renderPanels();
}

function renderPanels() {
  // players, sorted by life desc
  $("pcount").textContent = `(${state.players.length})`;
  const list = $("players");
  list.innerHTML = "";
  for (const p of [...state.players].sort((a, b) => b.life - a.life)) {
    const li = document.createElement("li");
    const lifePct = Math.max(0, Math.min(100, Math.round((p.life / 150) * 100)));
    li.innerHTML = `
      <svg class="swatch" viewBox="0 0 10 10" aria-hidden="true"><polygon points="5,1 9,9 1,9" fill="${colorFor(p.id)}" stroke="rgba(0,0,0,0.8)"/></svg>
      <span class="name">${escapeHtml(p.name)}</span>
      <span class="bar"><i style="width:${lifePct}%"></i></span>
      <span class="lv">${p.life}</span>
      <span class="pos" title="coins captured">c${p.coins_captured}</span>
      <span class="pos" title="movements">m${p.motion_count}</span>`;
    list.appendChild(li);
  }

  // coins
  $("ccount").textContent = `(${state.coins.length})`;
  const cl = $("coins");
  cl.innerHTML = "";
  for (const [x, y] of state.coins) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="dot" style="background:#ffd33d"></span> [${x}, ${y}]`;
    cl.appendChild(li);
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// --- connect / disconnect -------------------------------------------------
async function connect() {
  let base = $("base-url").value.trim().replace(/\/+$/, "");
  if (!base) {
    base = window.location.origin; // default to the host that served this page
    $("base-url").value = base;
  }
  state.base = base;
  state.viewerKey = $("viewer-key").value.trim();
  saveStored();
  try {
    const h = await apiGet("/health", {});
    toast(`connected · seed ${h.gen_seed}`, "ok");
    startPolling();
    $("btn-connect").disabled = true;
    $("btn-disconnect").disabled = false;
  } catch (e) {
    toast("connect failed: " + (e.code || e.message), "err");
  }
}
function disconnect() {
  stopPolling();
  $("conn").textContent = "stopped";
  $("conn").style.color = "var(--muted)";
  $("btn-connect").disabled = false;
  $("btn-disconnect").disabled = true;
}

// --- init -----------------------------------------------------------------
function init() {
  loadStored();
  if (!$("base-url").value) $("base-url").value = window.location.origin;
  $("btn-connect").addEventListener("click", connect);
  $("btn-disconnect").addEventListener("click", disconnect);
  resize();
  // auto-connect if a viewer key is saved or we're same-origin with the API server
  if ($("viewer-key").value.trim() || window.location.pathname.startsWith("/gui")) connect();
}

init();
