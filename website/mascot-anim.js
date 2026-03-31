import { prepareWithSegments, layoutNextLine } from '@chenglou/pretext';

const section = document.getElementById('mascot-engine-section');
const canvas = document.getElementById('mascot-canvas');
const ctx = canvas.getContext('2d');

let W = canvas.width = window.innerWidth;
let H = canvas.height = window.innerHeight;

window.addEventListener('resize', () => {
  W = canvas.width = window.innerWidth;
  H = canvas.height = window.innerHeight;
});

// ── Load Ellie SVG as an image ──────────────────────────────
const ellieImg = new Image();
ellieImg.src = 'assets/engram-logo.svg';

// ── Mascot physics state ────────────────────────────────────
const mascot = {
  x: W / 2,
  y: H / 2,
  targetX: W / 2,
  targetY: H / 2,
  vx: 0,
  vy: 0,
  size: 110,       // rendered width/height of the SVG body
  hitW: 120,       // bounding box for text collision
  hitH: 100,
  wobble: 0,
  time: 0,
  facingRight: true,
};

// ── Track mouse ─────────────────────────────────────────────
window.addEventListener('mousemove', (e) => {
  const rect = canvas.getBoundingClientRect();
  if (e.clientY >= rect.top && e.clientY <= rect.bottom) {
    mascot.targetX = e.clientX;
    mascot.targetY = e.clientY - rect.top;
  }
});

// ── Philosophy text ─────────────────────────────────────────
const rawText =
  `The traditional approach to AI memory is fundamentally broken. Generic RAG systems ` +
  `merely vectorize chat histories, indiscriminately dumping flat textual chunks into future ` +
  `prompts. They store what happened — but blindly discard the reasoning, the context, and ` +
  `most importantly: the roads not taken.\n\n` +
  `Welcome to Engram's Epistemic Engine. Developer intent is mapped into a strictly typed, ` +
  `temporal causal knowledge graph running entirely on your local machine. Every IDE session ` +
  `close, every command, every bug resolved — Engram intercepts and runs a multi-agent ` +
  `critique pipeline that isolates the actual logical decisions you made.\n\n` +
  `Through counterfactual extraction, Engram deliberately maps the alternative libraries, ` +
  `architectures, and frameworks that you actively rejected — saving exactly *why* you ` +
  `rejected them. Three months from now, if an autonomous agent resurfaces that same ` +
  `option, Engram traverses causal ancestry edges and preemptively halts the action.\n\n` +
  `This is not memory. This is artificial contextual wisdom. Move your cursor through the ` +
  `text to watch @chenglou/pretext calculate reflow-free text geometry at 60 FPS — while ` +
  `Ellie, the Engram mascot, gracefully parts the words around her. The elephant never forgets.`;

const fontSize = window.innerWidth > 768 ? 19 : 15;
const fontStr = `${fontSize}px "Space Grotesk", "Plus Jakarta Sans", sans-serif`;
const lineH = fontSize * 1.85;

// Precompute once — pretext skips all DOM reflows ✓
const prepared = prepareWithSegments(rawText, fontStr, { whiteSpace: 'pre-wrap' });

// ── Leg rendering ────────────────────────────────────────────
function drawLegs(speed, isMoving) {
  const s      = mascot.size * 0.5;   // half body size reference
  const legW   = s * 0.18;
  const legLen = s * 0.55;
  const bodyBottom = s * 0.38;        // offset below centre where legs attach
  const legColor = '#00c5a0';
  const shadowLeg = '#00a88a';

  // 4 legs: front-left, back-left (far/shadow), front-right, back-right (near)
  // Walk cycle using sine. Legs are paired diagonally (natural gait).
  const swing = isMoving ? Math.sin(mascot.time * 2.8) : 0;

  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  // ── FAR (behind) legs — drawn first, slightly dimmer ────
  ctx.lineWidth = legW * 1.1;
  ctx.strokeStyle = shadowLeg;

  // Far-front leg  (phase offset so opposite to near-front)
  const farFrontAngle =  swing * 0.45;
  const farBackAngle  = -swing * 0.45;

  const legPositions = [
    // far legs (behind body layer)
    { ox: -s * 0.25, phase: farFrontAngle,  layer: 'far' },
    { ox:  s * 0.22, phase: farBackAngle,   layer: 'far' },
    // near legs (in front of body layer)
    { ox: -s * 0.25, phase: -swing * 0.45,  layer: 'near' },
    { ox:  s * 0.22, phase:  swing * 0.45,  layer: 'near' },
  ];

  ['far', 'near'].forEach(layer => {
    ctx.strokeStyle = layer === 'far' ? shadowLeg : legColor;
    ctx.lineWidth   = layer === 'far' ? legW * 0.9 : legW;

    legPositions.filter(l => l.layer === layer).forEach(({ ox, phase }) => {
      const footX = ox + Math.sin(phase) * legLen * 0.4;
      const footY = bodyBottom + legLen + Math.abs(Math.cos(phase)) * (isMoving ? 8 : 0);

      ctx.beginPath();
      ctx.moveTo(ox, bodyBottom);
      ctx.quadraticCurveTo(ox + footX * 0.4, bodyBottom + legLen * 0.5, footX, footY);
      ctx.stroke();
    });
  });
}

// ── Main render ──────────────────────────────────────────────
function render() {
  requestAnimationFrame(render);

  // Skip if section not near viewport
  const secRect = section.getBoundingClientRect();
  if (secRect.bottom < -300 || secRect.top > window.innerHeight + 300) return;

  // ── Physics ──────────────────────────────────────────────
  mascot.vx = (mascot.targetX - mascot.x) * 0.055;
  mascot.vy = (mascot.targetY - mascot.y) * 0.055;
  mascot.x += mascot.vx;
  mascot.y += mascot.vy;
  mascot.wobble += 0.018;

  const speed     = Math.sqrt(mascot.vx ** 2 + mascot.vy ** 2);
  const isMoving  = speed > 1.2;

  if (isMoving) {
    mascot.time    += speed * 0.025;
    mascot.facingRight = mascot.vx > 0;
  } else {
    mascot.time += 0.04;
  }

  // ── Clear ────────────────────────────────────────────────
  ctx.clearRect(0, 0, W, H);

  // Subtle grid
  ctx.strokeStyle = 'rgba(0,197,160,0.04)';
  ctx.lineWidth = 1;
  for (let i = 0; i < W; i += 60) {
    ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, H); ctx.stroke();
  }
  for (let j = 0; j < H; j += 60) {
    ctx.beginPath(); ctx.moveTo(0, j); ctx.lineTo(W, j); ctx.stroke();
  }

  // ── Pretext text layout with mascot collision ────────────
  ctx.font          = fontStr;
  ctx.fillStyle     = 'rgba(220,240,255,0.38)';
  ctx.textAlign     = 'left';
  ctx.textBaseline  = 'top';

  const hW = mascot.hitW / 2;
  const hH = mascot.hitH / 2;

  let cursor = { segmentIndex: 0, graphemeIndex: 0 };
  let y = Math.max(60, H * 0.06);
  const margin = 36;

  while (true) {
    let renderX = margin;
    let maxW = W - margin * 2;

    // Does this text row hit the mascot's Y range?
    if (y + lineH > mascot.y - hH && y < mascot.y + hH) {
      const mascotLeft  = mascot.x - hW;
      const mascotRight = mascot.x + hW;
      const mid         = W / 2;

      if (mascot.x < mid) {
        // Mascot on left → shrink left edge, push text right
        renderX = Math.min(mascotRight + 16, W - margin - 160);
        maxW    = W - renderX - margin;
      } else {
        // Mascot on right → shrink width so text stays left
        renderX = margin;
        maxW    = Math.max(160, mascotLeft - 16 - margin);
      }
    }

    if (maxW < 120) maxW = 120;

    const line = layoutNextLine(prepared, cursor, maxW);
    if (line === null) break;

    ctx.fillText(line.text, renderX, y);
    cursor = line.end;
    y += lineH;

    if (y > H) break; // Clip below canvas
  }

  // ── Draw Ellie ───────────────────────────────────────────
  const s        = mascot.size;
  const bob      = isMoving
    ? Math.abs(Math.sin(mascot.time * 2.8)) * 5
    : Math.sin(mascot.wobble) * 7;
  const squishY  = isMoving ? 1 - Math.abs(Math.sin(mascot.time * 2.8)) * 0.06 : 1;
  const squishX  = isMoving ? 1 + Math.abs(Math.sin(mascot.time * 2.8)) * 0.04 : 1;

  ctx.save();
  ctx.translate(mascot.x, mascot.y + bob);
  ctx.scale(mascot.facingRight ? 1 : -1, 1);
  ctx.scale(squishX, squishY);

  // Aura glow
  const glow = ctx.createRadialGradient(0, 0, 0, 0, 0, s * 0.95);
  glow.addColorStop(0, 'rgba(0,197,160,0.18)');
  glow.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = glow;
  ctx.beginPath(); ctx.arc(0, 0, s * 0.95, 0, Math.PI * 2); ctx.fill();

  // ── Legs (behind SVG body) ───────────────────────────────
  drawLegs(speed, isMoving);

  // ── SVG body on top ──────────────────────────────────────
  if (ellieImg.complete && ellieImg.naturalWidth > 0) {
    ctx.drawImage(ellieImg, -s / 2, -s / 2, s, s);
  } else {
    // Cute fallback pill if SVG is still loading
    ctx.fillStyle = '#00c5a0';
    ctx.beginPath();
    ctx.ellipse(0, 0, s * 0.42, s * 0.32, 0, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.restore();
}

render();
