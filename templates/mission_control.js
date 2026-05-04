/* ── Mission Control — canvas map + telemetry ──────────────────────── */
'use strict';

// State
let _pose    = { x: 0, y: 0, theta: 0, source: 'mock', confidence: 0 };
let _path    = [];
let _status  = {};
let _scale   = 80;   // pixels per meter
let _offsetX = 0;    // canvas pan offset (pixels)
let _offsetY = 0;
let _dragging = false;
let _dragStart = null;

// DOM refs (set in init)
let _canvas, _ctx, _wrap;

// ── Init ─────────────────────────────────────────────────────────────────────

function mcInit() {
  _canvas = document.getElementById('mc-map');
  _ctx    = _canvas.getContext('2d');
  _wrap   = document.getElementById('mc-map-wrap');

  mcResize();
  window.addEventListener('resize', mcResize);

  // Canvas pan via drag
  _canvas.addEventListener('mousedown', e => {
    _dragging  = true;
    _dragStart = { x: e.clientX - _offsetX, y: e.clientY - _offsetY };
  });
  _canvas.addEventListener('mousemove', e => {
    if (!_dragging) return;
    _offsetX = e.clientX - _dragStart.x;
    _offsetY = e.clientY - _dragStart.y;
    mcDraw();
  });
  window.addEventListener('mouseup', () => { _dragging = false; });

  // Mouse wheel zoom
  _canvas.addEventListener('wheel', e => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    _scale = Math.max(10, Math.min(400, _scale * factor));
    mcDraw();
  }, { passive: false });

  // Start polling
  mcPollPose();
  mcPollPath();
  mcPollStatus();
}

// ── Canvas sizing ─────────────────────────────────────────────────────────────

function mcResize() {
  const rect = _wrap.getBoundingClientRect();
  _canvas.width  = rect.width  || 600;
  _canvas.height = rect.height || 500;
  mcDraw();
}

// ── Drawing ───────────────────────────────────────────────────────────────────

function mcDraw() {
  const w = _canvas.width;
  const h = _canvas.height;
  const cx = w / 2 + _offsetX;   // world origin in canvas coords
  const cy = h / 2 + _offsetY;

  _ctx.clearRect(0, 0, w, h);

  // Background
  _ctx.fillStyle = getComputedStyle(document.documentElement)
    .getPropertyValue('--t-bg-deep') || '#080c10';
  _ctx.fillRect(0, 0, w, h);

  mcDrawGrid(cx, cy, w, h);
  mcDrawPath(cx, cy);
  mcDrawOrigin(cx, cy);
  mcDrawRobot(cx, cy);
  mcDrawScale(w, h);

  // Update coordinate display
  const el = document.getElementById('mc-coords');
  if (el) {
    el.textContent =
      `x: ${_pose.x.toFixed(2)} m   y: ${_pose.y.toFixed(2)} m   ` +
      `θ: ${((_pose.theta * 180 / Math.PI) % 360).toFixed(1)}°`;
  }
}

function mcDrawGrid(cx, cy, w, h) {
  const step = _scale;       // 1 m grid
  const primary   = 'rgba(30,50,70,0.8)';
  const secondary = 'rgba(20,35,50,0.5)';
  const text      = 'rgba(60,90,120,0.7)';

  _ctx.lineWidth = 1;
  _ctx.font = '9px monospace';

  // vertical lines
  for (let x = (cx % step); x < w; x += step) {
    const m = Math.round((x - cx) / step);
    _ctx.strokeStyle = m === 0 ? 'rgba(46,249,196,0.25)' :
                       m % 5 === 0 ? primary : secondary;
    _ctx.beginPath(); _ctx.moveTo(x, 0); _ctx.lineTo(x, h); _ctx.stroke();
    if (m !== 0 && m % 2 === 0) {
      _ctx.fillStyle = text;
      _ctx.fillText(m + 'm', x + 2, cy - 2);
    }
  }

  // horizontal lines
  for (let y = (cy % step); y < h; y += step) {
    const m = Math.round((cy - y) / step);   // Y inverted
    _ctx.strokeStyle = m === 0 ? 'rgba(46,249,196,0.25)' :
                       m % 5 === 0 ? primary : secondary;
    _ctx.beginPath(); _ctx.moveTo(0, y); _ctx.lineTo(w, y); _ctx.stroke();
    if (m !== 0 && m % 2 === 0) {
      _ctx.fillStyle = text;
      _ctx.fillText(m + 'm', cx + 2, y - 2);
    }
  }
}

function mcDrawPath(cx, cy) {
  if (_path.length < 2) return;
  _ctx.beginPath();
  _ctx.strokeStyle = 'rgba(46,249,196,0.45)';
  _ctx.lineWidth = 1.5;
  _ctx.lineJoin = 'round';

  const p0 = _path[0];
  _ctx.moveTo(cx + p0.x * _scale, cy - p0.y * _scale);
  for (let i = 1; i < _path.length; i++) {
    const p = _path[i];
    _ctx.lineTo(cx + p.x * _scale, cy - p.y * _scale);
  }
  _ctx.stroke();

  // Start dot
  _ctx.beginPath();
  _ctx.arc(cx + p0.x * _scale, cy - p0.y * _scale, 4, 0, Math.PI * 2);
  _ctx.fillStyle = 'rgba(46,249,196,0.6)';
  _ctx.fill();
}

function mcDrawOrigin(cx, cy) {
  // X axis (red)
  _ctx.strokeStyle = 'rgba(240,80,80,0.6)';
  _ctx.lineWidth = 1.5;
  _ctx.beginPath(); _ctx.moveTo(cx, cy); _ctx.lineTo(cx + 30, cy); _ctx.stroke();
  // Y axis (green)
  _ctx.strokeStyle = 'rgba(80,220,80,0.6)';
  _ctx.beginPath(); _ctx.moveTo(cx, cy); _ctx.lineTo(cx, cy - 30); _ctx.stroke();
  // Origin dot
  _ctx.beginPath();
  _ctx.arc(cx, cy, 3, 0, Math.PI * 2);
  _ctx.fillStyle = 'rgba(255,255,255,0.3)';
  _ctx.fill();
}

function mcDrawRobot(cx, cy) {
  const rx = cx + _pose.x * _scale;
  const ry = cy - _pose.y * _scale;   // Y inverted in canvas
  const th = -_pose.theta;            // canvas angles are CW

  _ctx.save();
  _ctx.translate(rx, ry);
  _ctx.rotate(th);

  const size = 14;

  // Glow ring
  _ctx.beginPath();
  _ctx.arc(0, 0, size + 4, 0, Math.PI * 2);
  _ctx.strokeStyle = 'rgba(46,249,196,0.2)';
  _ctx.lineWidth = 3;
  _ctx.stroke();

  // Body (arrow/triangle pointing +X = forward)
  _ctx.beginPath();
  _ctx.moveTo(size, 0);
  _ctx.lineTo(-size * 0.6, -size * 0.55);
  _ctx.lineTo(-size * 0.3, 0);
  _ctx.lineTo(-size * 0.6, size * 0.55);
  _ctx.closePath();
  _ctx.fillStyle   = 'rgba(46,249,196,0.85)';
  _ctx.strokeStyle = '#fff';
  _ctx.lineWidth   = 1;
  _ctx.fill();
  _ctx.stroke();

  _ctx.restore();
}

function mcDrawScale(w, h) {
  // 1m scale bar in bottom-right of canvas
  const barW = _scale;
  const bx = w - barW - 15;
  const by = h - 18;
  _ctx.strokeStyle = 'rgba(180,200,220,0.5)';
  _ctx.lineWidth = 1.5;
  _ctx.beginPath(); _ctx.moveTo(bx, by); _ctx.lineTo(bx + barW, by); _ctx.stroke();
  _ctx.beginPath(); _ctx.moveTo(bx, by - 4); _ctx.lineTo(bx, by + 4); _ctx.stroke();
  _ctx.beginPath(); _ctx.moveTo(bx + barW, by - 4); _ctx.lineTo(bx + barW, by + 4); _ctx.stroke();
  _ctx.fillStyle = 'rgba(140,170,200,0.7)';
  _ctx.font = '10px monospace';
  _ctx.textAlign = 'center';
  _ctx.fillText('1 m', bx + barW / 2, by - 6);
  _ctx.textAlign = 'start';
}

// ── API polling ───────────────────────────────────────────────────────────────

function mcPollPose() {
  fetch('/api/mc/pose')
    .then(r => r.json())
    .then(data => {
      _pose = data;
      mcUpdateTelemetry();
      mcDraw();
    })
    .catch(() => {})
    .finally(() => setTimeout(mcPollPose, 500));
}

function mcPollPath() {
  fetch('/api/mc/path?limit=500')
    .then(r => r.json())
    .then(data => {
      _path = data.points || [];
      document.getElementById('mc-history-count').textContent =
        `${data.total} pts stored`;
    })
    .catch(() => {})
    .finally(() => setTimeout(mcPollPath, 1000));
}

function mcPollStatus() {
  fetch('/api/mc/status')
    .then(r => r.json())
    .then(data => {
      _status = data;
      mcUpdateStatus();
    })
    .catch(() => {})
    .finally(() => setTimeout(mcPollStatus, 2000));
}

// ── UI updates ────────────────────────────────────────────────────────────────

function mcUpdateTelemetry() {
  setText('mc-x',          _pose.x.toFixed(3) + ' m');
  setText('mc-y',          _pose.y.toFixed(3) + ' m');
  setText('mc-theta',      (_pose.theta * 180 / Math.PI).toFixed(1) + '°');
  setText('mc-source',     _pose.source);
  setText('mc-conf-val',   (_pose.confidence * 100).toFixed(0) + '%');
  setText('mc-ts',         formatTs(_pose.timestamp));

  const fill = document.getElementById('mc-confidence-fill');
  if (fill) fill.style.width = (_pose.confidence * 100) + '%';
}

function mcUpdateStatus() {
  const badge = document.getElementById('mc-slam-badge');
  if (!badge) return;
  const mode = _status.mode || 'offline';
  badge.textContent = 'SLAM: ' + mode.toUpperCase();
  badge.className = '';
  if      (mode === 'mock')        badge.classList.add('mock');
  else if (mode === 'lidar_basic') badge.classList.add('lidar');
  else if (mode === 'slam')        badge.classList.add('slam');
  else                             badge.classList.add('offline');

  setText('mc-lidar-status',  _status.lidar_available  ? 'ONLINE' : 'OFFLINE');
  setText('mc-slam-status',   _status.slam_available   ? 'ONLINE' : 'OFFLINE');
}

// ── Controls ──────────────────────────────────────────────────────────────────

function mcCenterView() {
  _offsetX = 0;
  _offsetY = 0;
  mcDraw();
}

function mcZoomIn()  { _scale = Math.min(400, _scale * 1.25); mcDraw(); }
function mcZoomOut() { _scale = Math.max(10,  _scale * 0.8);  mcDraw(); }

function mcReset() {
  if (!confirm('Reset trajectory? This clears the path history.')) return;
  fetch('/api/mc/reset', { method: 'POST' })
    .then(() => { _path = []; mcCenterView(); })
    .catch(() => {});
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function formatTs(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour12: false });
  } catch { return iso; }
}

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', mcInit);
