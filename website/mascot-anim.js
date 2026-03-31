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

// Mascot Physics & Procedural State
const mascot = {
  x: W / 2,
  y: H / 2,
  targetX: W / 2,
  targetY: H / 2,
  vx: 0,
  vy: 0,
  width: 160,   // Hitbox width
  height: 120,
  wobble: 0,
  time: 0
};

// Track mouse
window.addEventListener('mousemove', (e) => {
  // Only update if we are inspecting the canvas section
  const rect = canvas.getBoundingClientRect();
  if (e.clientY >= rect.top && e.clientY <= rect.bottom) {
    mascot.targetX = e.clientX;
    mascot.targetY = e.clientY - rect.top; // Relative Y
  }
});

// The massive philosophy text to wrap around the mascot!
const rawText = `The traditional approach to AI memory is fundamentally broken. Generic RAG systems merely vectorize chat histories, indiscriminately dumping flat textual chunks into future prompts. They store what happened, but they blindly discard the reasoning, the context, and most importantly: the roads not taken. 

Welcome to Engram's Epistemic Engine. We map developer intent into a strictly typed, temporal knowledge graph running entirely on your local machine.

Every time you type a command, close an IDE session, or resolve a bug, Engram intercepts the session. It runs a multi-agent critique pipeline that structurally isolates the actual logical decisions you made. 

But it doesn't stop there. Through counterfactual extraction, Engram deliberately maps the alternative libraries, architectures, or frameworks that you actively rejected during the session, saving exactly *why* you rejected them. 

The next time an autonomous agent suggests that same rejected library three months from now across an entirely different project, Engram traverses the causal ancestry edges and forcefully halts the agent with a preemptive warning limit. 

This isn't just memory. This is artificial contextual wisdom. 
Hover your cursor over the screen to dynamically witness the raw power of the @chenglou/pretext layout engine calculating text boundaries at 60 Frames Per Second without a single DOM reflow. The Elephant never forgets.`;


const fontSize = window.innerWidth > 768 ? 20 : 16;
const fontStr = `${fontSize}px "Space Grotesk", "Plus Jakarta Sans", sans-serif`;
const lineHeight = fontSize * 1.8;

// One-time pre-computation using pretext!
const preparedText = prepareWithSegments(rawText, fontStr, { whiteSpace: 'pre-wrap' });

function render() {
  requestAnimationFrame(render);
  
  // Only render if section is in viewport bounds roughly
  const secRect = section.getBoundingClientRect();
  if (secRect.bottom < -500 || secRect.top > window.innerHeight + 500) {
    return;
  }

  // Physics Update
  mascot.vx = (mascot.targetX - mascot.x) * 0.05;
  mascot.vy = (mascot.targetY - mascot.y) * 0.05;
  mascot.x += mascot.vx;
  mascot.y += mascot.vy;
  
  const speed = Math.sqrt(mascot.vx**2 + mascot.vy**2);
  mascot.wobble += 0.02;
  
  // Time advances faster if moving
  if (speed > 1) {
      mascot.time += speed * 0.03;
  } else {
      mascot.time += 0.05; // Idle swaying
  }

  // Clear background (Transparent to allow CSS theme to show through)
  ctx.clearRect(0, 0, W, H);

  // Layout Text Dynamically!
  ctx.font = fontStr;
  ctx.fillStyle = 'rgba(255, 255, 255, 0.4)'; // Faint text color
  ctx.textAlign = 'left';
  ctx.textBaseline = 'top';

  let cursor = { segmentIndex: 0, graphemeIndex: 0 };
  let y = Math.max(80, H * 0.15); // Start rendering text slightly down the canvas

  // Draw Context Grid Lines for sci-fi feel
  ctx.strokeStyle = 'rgba(0, 212, 170, 0.05)';
  ctx.lineWidth = 1;
  for(let i=0; i<W; i+=60) {
    ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, H); ctx.stroke();
  }

  // Pretext Core Loop
  while (true) {
    // Determine the available width and X-offset for this specific row!
    let currentWidth = W - 80; 
    let renderX = 40; 
    
    // Create a bounding box for the floating mascot
    const mascotTop = mascot.y - 40;
    const mascotBottom = mascot.y + mascot.height + 40;

    // If the text row intersects the mascot's elevation...
    if (y > mascotTop && y < mascotBottom) {
      if (mascot.x < W / 2) {
        // Mascot is on left side, float text to the right
        renderX = mascot.x + (mascot.width / 2) + 40;
        currentWidth = W - renderX - 40;
      } else {
        // Mascot is on right side, float text to the left
        renderX = 40;
        currentWidth = mascot.x - (mascot.width / 2) - 40;
      }
    }

    // Protection against crushing the text too small
    if (currentWidth < 150) currentWidth = 150; 

    // Ask Pretext to calculate exactly what fits in this row
    const line = layoutNextLine(preparedText, cursor, currentWidth);
    
    if (line === null) break; // Finished reading string!
    
    ctx.fillText(line.text, renderX, y);
    
    // Advance pre-text cursor state
    cursor = line.end;
    y += lineHeight;
  }

  // ==========================================
  // PROCEDURAL WALKING ELEPHANT RENDERER
  // ==========================================
  ctx.save();
  const dirX = mascot.vx > 0 ? 1 : -1; // Face movement direction
  ctx.translate(mascot.x, mascot.y);
  
  // Idle bob
  const isMoving = speed > 1;
  const bob = isMoving ? Math.abs(Math.sin(mascot.time*2)) * 6 : Math.sin(mascot.wobble) * 8;
  ctx.translate(0, bob);
  ctx.scale(dirX, 1); // Flip horizontally if moving left
  
  // Neon glow effects
  const elephantAlpha = 0.9;
  const bodyColor = 'rgba(0, 212, 170, ' + elephantAlpha + ')';
  const shadowColor = 'rgba(0, 212, 170, 0.4)';
  
  // Create an aura radius for the bounding box
  const g = ctx.createRadialGradient(0, 0, 0, 0, 0, 100);
  g.addColorStop(0, 'rgba(0, 212, 170, 0.2)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(0, 0, 120, 0, Math.PI*2); ctx.fill();

  ctx.fillStyle = bodyColor;
  ctx.strokeStyle = bodyColor;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  // Walk cycle sines
  const swingFront = isMoving ? Math.sin(mascot.time * 2) * 20 : 0;
  const swingBack = isMoving ? Math.cos(mascot.time * 2) * 20 : 0;

  // -- FAR LEGS (Drawn behind body, darker)
  ctx.fillStyle = shadowColor;
  ctx.strokeStyle = shadowColor;
  ctx.lineWidth = 14;
  // Far Front Leg
  ctx.beginPath(); ctx.moveTo(20, 10); ctx.lineTo(15 + swingBack, 40); ctx.stroke();
  // Far Back Leg
  ctx.beginPath(); ctx.moveTo(-20, 10); ctx.lineTo(-25 - swingFront, 40); ctx.stroke();

  // -- BODY (Stylized bean shape)
  ctx.fillStyle = bodyColor;
  ctx.beginPath();
  ctx.ellipse(0, 0, 45, 30, 0, 0, Math.PI * 2);
  ctx.fill();

  // -- HEAD
  const headY = isMoving ? Math.sin(mascot.time * 2 + 1) * 3 : 0;
  ctx.beginPath();
  ctx.arc(40, -10 + headY, 25, 0, Math.PI * 2);
  ctx.fill();

  // -- TRUNK (Bezier curve swaying)
  const trunkSway = isMoving ? Math.sin(mascot.time * 2 + 2) * 20 : Math.sin(mascot.wobble) * 10;
  ctx.lineWidth = 12;
  ctx.beginPath();
  ctx.moveTo(60, -5 + headY); // Base of trunk
  ctx.quadraticCurveTo(80 + trunkSway/2, 10, 65 + trunkSway, 35 - bob); 
  ctx.stroke();

  // -- NEAR LEGS (Drawn in front of body)
  ctx.strokeStyle = bodyColor;
  ctx.lineWidth = 16;
  // Near Front Leg
  ctx.beginPath(); ctx.moveTo(20, 10); ctx.lineTo(20 + swingFront, 45); ctx.stroke();
  // Near Back Leg
  ctx.beginPath(); ctx.moveTo(-20, 10); ctx.lineTo(-20 - swingBack, 45); ctx.stroke();

  // -- EARS (Flapping)
  const earFlap = isMoving ? Math.abs(Math.sin(mascot.time * 2)) * 10 : 0;
  ctx.beginPath();
  ctx.ellipse(35, -15 + headY, 15 + earFlap, 25, -Math.PI/6, 0, Math.PI * 2);
  ctx.fill();

  // -- EYE (Glowing white dot)
  ctx.fillStyle = '#ffffff';
  ctx.beginPath();
  ctx.arc(45, -15 + headY, 4, 0, Math.PI * 2);
  ctx.fill();

  // -- TAIL
  ctx.strokeStyle = bodyColor;
  ctx.lineWidth = 5;
  ctx.beginPath();
  ctx.moveTo(-40, -5);
  ctx.quadraticCurveTo(-60, 5, -55 + swingFront/2, 20);
  ctx.stroke();

  ctx.restore();
}

// Start Engine
render();
