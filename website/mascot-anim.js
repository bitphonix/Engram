import { prepareWithSegments, layoutWithLines } from '@chenglou/pretext';

const section = document.getElementById('mascot-engine-section');
const canvas  = document.getElementById('mascot-canvas');
const ctx     = canvas.getContext('2d');

let W = canvas.width  = canvas.offsetWidth  || window.innerWidth;
let H = canvas.height = canvas.offsetHeight || window.innerHeight;

window.addEventListener('resize', () => {
  W = canvas.width  = canvas.offsetWidth  || window.innerWidth;
  H = canvas.height = canvas.offsetHeight || window.innerHeight;
  buildChars();
});

// ── Ellie SVG ───────────────────────────────────────────────
const ellieImg = new Image();
ellieImg.src = 'assets/engram-logo.svg';

// ── Mascot state ────────────────────────────────────────────
const mascot = {
  x: W / 2, y: H / 2,
  targetX: W / 2, targetY: H / 2,
  vx: 0, vy: 0,
  size: 110,
  wobble: 0, time: 0,
  facingRight: true,
};

window.addEventListener('mousemove', (e) => {
  const rect = canvas.getBoundingClientRect();
  if (e.clientY >= rect.top && e.clientY <= rect.bottom) {
    mascot.targetX = e.clientX;
    mascot.targetY = e.clientY - rect.top;
  }
});

// ── Text ─────────────────────────────────────────────────────
const rawText =
  `The traditional approach to AI memory is fundamentally broken. Generic RAG systems ` +
  `merely vectorize chat histories — discarding the reasoning and the roads not taken.\n\n` +
  `Welcome to Engram. Developer intent mapped into a strictly typed, temporal causal ` +
  `knowledge graph running entirely on your local machine. Every IDE session, Engram ` +
  `intercepts and runs a multi-agent critique pipeline that isolates the actual decisions made.\n\n` +
  `Through counterfactual extraction, Engram maps the alternative libraries, architectures ` +
  `and frameworks you rejected — saving exactly why. When an autonomous agent resurfaces ` +
  `that same option three months later, Engram traverses causal ancestry and halts it cold.\n\n` +
  `This is not memory. This is artificial contextual wisdom.\n` +
  `Move your cursor through the letters and watch them scatter. Ellie never forgets.`;

const FONT        = '16px Georgia, serif';
const LINE_HEIGHT = 30;
const PADDING     = 48;

// ── Character particles ───────────────────────────────────────
let chars = [];

function buildChars() {
  chars = [];
  ctx.font = FONT;

  const maxWidth = W - PADDING * 2;
  const prepared = prepareWithSegments(rawText, FONT, { whiteSpace: 'pre-wrap' });
  const { lines } = layoutWithLines(prepared, maxWidth, LINE_HEIGHT);

  let y = PADDING + LINE_HEIGHT;

  for (const line of lines) {
    let x = PADDING;
    for (const ch of line.text) {
      chars.push({ char: ch, baseX: x, baseY: y, x, y, vx: 0, vy: 0 });
      x += ctx.measureText(ch).width;
    }
    y += LINE_HEIGHT;
  }
}

// ── Walking legs ─────────────────────────────────────────────
function drawLegs(isMoving) {
  const s          = mascot.size * 0.5;
  const legW       = s * 0.18;
  const legLen     = s * 0.55;
  const bodyBottom = s * 0.38;
  const swing      = isMoving ? Math.sin(mascot.time * 2.8) : 0;

  ctx.lineCap   = 'round';
  ctx.lineJoin  = 'round';

  const legDefs = [
    { ox: -s * 0.25, phase:  swing * 0.45,  layer: 'far'  },
    { ox:  s * 0.22, phase: -swing * 0.45,  layer: 'far'  },
    { ox: -s * 0.25, phase: -swing * 0.45,  layer: 'near' },
    { ox:  s * 0.22, phase:  swing * 0.45,  layer: 'near' },
  ];

  ['far', 'near'].forEach(layer => {
    ctx.strokeStyle = layer === 'far' ? '#00a88a' : '#00c5a0';
    ctx.lineWidth   = layer === 'far' ? legW * 0.85 : legW;

    legDefs.filter(l => l.layer === layer).forEach(({ ox, phase }) => {
      const footX = ox + Math.sin(phase) * legLen * 0.4;
      const footY = bodyBottom + legLen + (isMoving ? Math.abs(Math.cos(phase)) * 8 : 0);
      ctx.beginPath();
      ctx.moveTo(ox, bodyBottom);
      ctx.quadraticCurveTo(ox + footX * 0.4, bodyBottom + legLen * 0.5, footX, footY);
      ctx.stroke();
    });
  });
}

// ── Physics constants ─────────────────────────────────────────
const REPEL_RADIUS = 130;   // px — how far Ellie pushes letters
const REPEL_FORCE  = 9;     // impulse strength
const SPRING       = 0.07;  // how fast letters spring back
const DAMPING      = 0.74;  // energy lost each frame (< 1)

// ── Main render loop ──────────────────────────────────────────
function render() {
  requestAnimationFrame(render);

  const secRect = section.getBoundingClientRect();
  if (secRect.bottom < -300 || secRect.top > window.innerHeight + 300) return;

  // ── Mascot physics ─────────────────────────────────────────
  mascot.vx = (mascot.targetX - mascot.x) * 0.055;
  mascot.vy = (mascot.targetY - mascot.y) * 0.055;
  mascot.x += mascot.vx;
  mascot.y += mascot.vy;
  mascot.wobble += 0.018;

  const speed    = Math.sqrt(mascot.vx ** 2 + mascot.vy ** 2);
  const isMoving = speed > 1.2;

  if (isMoving) {
    mascot.time   += speed * 0.025;
    mascot.facingRight = mascot.vx > 0;
  } else {
    mascot.time += 0.04;
  }

  // ── Character particle physics ─────────────────────────────
  for (const c of chars) {
    const dx   = c.x - mascot.x;
    const dy   = c.y - (mascot.y + mascot.size * 0.05); // centre on body, not feet
    const dist = Math.sqrt(dx * dx + dy * dy);

    // Repulsion from Ellie
    if (dist < REPEL_RADIUS && dist > 0.5) {
      const strength = ((REPEL_RADIUS - dist) / REPEL_RADIUS) ** 2;
      c.vx += (dx / dist) * strength * REPEL_FORCE;
      c.vy += (dy / dist) * strength * REPEL_FORCE;
    }

    // Spring back to original grid position
    c.vx += (c.baseX - c.x) * SPRING;
    c.vy += (c.baseY - c.y) * SPRING;

    // Damping
    c.vx *= DAMPING;
    c.vy *= DAMPING;

    c.x += c.vx;
    c.y += c.vy;
  }

  // ── Clear ──────────────────────────────────────────────────
  ctx.clearRect(0, 0, W, H);

  // Subtle grid
  ctx.strokeStyle = 'rgba(0,197,160,0.035)';
  ctx.lineWidth = 1;
  for (let i = 0; i < W; i += 60) {
    ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, H); ctx.stroke();
  }
  for (let j = 0; j < H; j += 60) {
    ctx.beginPath(); ctx.moveTo(0, j); ctx.lineTo(W, j); ctx.stroke();
  }

  // ── Draw characters ────────────────────────────────────────
  ctx.font         = FONT;
  ctx.textBaseline = 'alphabetic';

  for (const c of chars) {
    const displaced = Math.hypot(c.x - c.baseX, c.y - c.baseY);

    if (displaced > 1.5) {
      // Letters close to Ellie heat up: teal → warm white → hot yellow
      const t = Math.min(1, displaced / 60);
      const r = Math.round(lerp(0,   255, t));
      const g = Math.round(lerp(197, 220, t));
      const b = Math.round(lerp(160, 80,  t));
      const a = 0.3 + t * 0.65;
      ctx.fillStyle = `rgba(${r},${g},${b},${a})`;
    } else {
      ctx.fillStyle = 'rgba(210, 235, 255, 0.36)';
    }

    ctx.fillText(c.char, c.x, c.y);
  }

  // ── Draw Ellie ─────────────────────────────────────────────
  const bob     = isMoving
    ? Math.abs(Math.sin(mascot.time * 2.8)) * 5
    : Math.sin(mascot.wobble) * 7;
  const squishY = isMoving ? 1 - Math.abs(Math.sin(mascot.time * 2.8)) * 0.06 : 1;
  const squishX = isMoving ? 1 + Math.abs(Math.sin(mascot.time * 2.8)) * 0.04 : 1;

  ctx.save();
  ctx.translate(mascot.x, mascot.y + bob);
  ctx.scale(mascot.facingRight ? 1 : -1, 1);
  ctx.scale(squishX, squishY);

  // Aura glow
  const glow = ctx.createRadialGradient(0, 0, 0, 0, 0, mascot.size * 0.95);
  glow.addColorStop(0, 'rgba(0,197,160,0.2)');
  glow.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = glow;
  ctx.beginPath(); ctx.arc(0, 0, mascot.size * 0.95, 0, Math.PI * 2); ctx.fill();

  // Legs behind body
  drawLegs(isMoving);

  // Ellie SVG body on top
  if (ellieImg.complete && ellieImg.naturalWidth > 0) {
    ctx.drawImage(ellieImg, -mascot.size / 2, -mascot.size / 2, mascot.size, mascot.size);
  } else {
    ctx.fillStyle = '#00c5a0';
    ctx.beginPath();
    ctx.ellipse(0, 0, mascot.size * 0.42, mascot.size * 0.32, 0, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.restore();
}

function lerp(a, b, t) { return a + (b - a) * t; }

// Init
ellieImg.onload  = () => {};  // img pre-warms decode
buildChars();
render();
