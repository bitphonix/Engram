
const canvas = document.getElementById('arch-canvas');
const ctx = canvas.getContext('2d');
const archSection = document.getElementById('architecture-scroll-container');

let W = canvas.width = window.innerWidth;
let H = canvas.height = window.innerHeight;

window.addEventListener('resize', () => {
  W = canvas.width = window.innerWidth;
  H = canvas.height = window.innerHeight;
});

let scrollY = 0;
let targetScroll = 0;
let smoothScroll = 0;
let t = 0;

// Colors
const C = {
  teal: '#0070f3',
  tealDim: '#0050b3',
  cyan: '#ff0080',
  amber: '#f59e0b',
  blue: '#3b82f6',
  purple: '#8b5cf6',
  red: '#ef4444',
  bg: 'transparent',
};

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  return {r,g,b};
}
function rgba(hex, a) {
  const {r,g,b} = hexToRgb(hex);
  return `rgba(${r},${g},${b},${a})`;
}

// ---- BACKGROUND STARS ----
const stars = Array.from({length:200}, () => ({
  x: Math.random()*W, y: Math.random()*H,
  r: Math.random()*1.2+0.2,
  a: Math.random()*0.5+0.1,
  speed: Math.random()*0.3+0.05,
  twinkle: Math.random()*Math.PI*2,
}));

function drawBackground(progress) {
  // We don't fill C.bg to allow the body background transition to shine through!
  
  // Nebula gradient
  const gx = W/2, gy = H*0.4;
  const ng = ctx.createRadialGradient(gx, gy, 0, gx, gy, W*0.8);
  ng.addColorStop(0, rgba('#00102a', 0.6));
  ng.addColorStop(0.5, rgba('#0a0515', 0.4));
  ng.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = ng;
  ctx.fillRect(0,0,W,H);

  // Secondary nebula accent hint
  const ng2 = ctx.createRadialGradient(W*0.7, H*0.6, 0, W*0.7, H*0.6, W*0.5);
  ng2.addColorStop(0, rgba('#200010', 0.4));
  ng2.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = ng2;
  ctx.fillRect(0,0,W,H);

  // Stars
  stars.forEach(s => {
    const twinkle = 0.5 + 0.5*Math.sin(t*0.5 + s.twinkle);
    ctx.beginPath();
    ctx.arc(s.x, s.y, s.r, 0, Math.PI*2);
    ctx.fillStyle = rgba('#e0eeff', s.a * twinkle);
    ctx.fill();
  });
}

// ---- SCROLL ----
// We keep global scroll listener for tracking general scrolling just in case
window.addEventListener('scroll', () => {
  scrollY = window.scrollY;
});

const totalScrollHeight = () => (archSection ? archSection.offsetHeight : 0) - window.innerHeight;

// NEW: Normalize the section explicitly based on viewport
function getSectionNorm() {
  if (!archSection) return 0;
  const rect = archSection.getBoundingClientRect();
  const maxScroll = archSection.offsetHeight - window.innerHeight;
  if(maxScroll <= 0) return 0;
  let rawNorm = -rect.top / maxScroll;
  return Math.max(0, Math.min(1, rawNorm));
}

function easeInOut(t) { return t<0.5 ? 2*t*t : -1+(4-2*t)*t; }
function lerp(a,b,t) { return a+(b-a)*t; }

// ---- GLOW HELPERS ----
function glowCircle(x, y, r, color, alpha=1, blur=20) {
  const g = ctx.createRadialGradient(x,y,0,x,y,r*3);
  const {red, green, blue} = (() => {
    const c = hexToRgb(color);
    return {red:c.r, green:c.g, blue:c.b};
  })();
  g.addColorStop(0, `rgba(${red},${green},${blue},${alpha*0.8})`);
  g.addColorStop(0.3, `rgba(${red},${green},${blue},${alpha*0.3})`);
  g.addColorStop(1, `rgba(${red},${green},${blue},0)`);
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(x,y,r*3,0,Math.PI*2);
  ctx.fill();
  ctx.beginPath();
  ctx.arc(x,y,r,0,Math.PI*2);
  ctx.fillStyle = `rgba(${red},${green},${blue},${alpha})`;
  ctx.fill();
}

function glowLine(x1,y1,x2,y2,color,alpha=0.7,width=1.5) {
  const {r,g,b} = hexToRgb(color);
  ctx.save();
  ctx.shadowBlur = 15;
  ctx.shadowColor = color;
  ctx.strokeStyle = `rgba(${r},${g},${b},${alpha})`;
  ctx.lineWidth = width;
  ctx.beginPath();
  ctx.moveTo(x1,y1);
  ctx.lineTo(x2,y2);
  ctx.stroke();
  ctx.restore();
}

function glowText(text, x, y, color, size=11, alpha=1, tracking=2) {
  const {r,g,b} = hexToRgb(color);
  ctx.save();
  ctx.font = `${size}px "Courier New", monospace`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.shadowBlur = 12;
  ctx.shadowColor = color;
  ctx.fillStyle = `rgba(${r},${g},${b},${alpha})`;
  ctx.letterSpacing = `${tracking}px`;
  ctx.fillText(text, x, y);
  ctx.restore();
}

function glassPanel(x, y, w, h, color, alpha=0.7, borderAlpha=0.4) {
  const {r,g,b} = hexToRgb(color);
  ctx.save();
  ctx.shadowBlur = 30;
  ctx.shadowColor = color;
  ctx.fillStyle = `rgba(10,10,10,0.75)`;
  roundRect(x,y,w,h,8);
  ctx.fill();
  ctx.fillStyle = `rgba(${r},${g},${b},0.06)`;
  roundRect(x,y,w,h,8);
  ctx.fill();
  ctx.strokeStyle = `rgba(${r},${g},${b},${borderAlpha})`;
  ctx.lineWidth = 1.5;
  ctx.shadowBlur = 15;
  roundRect(x,y,w,h,8);
  ctx.stroke();
  ctx.restore();
}

function roundRect(x,y,w,h,r) {
  ctx.beginPath();
  ctx.moveTo(x+r,y);
  ctx.lineTo(x+w-r,y);
  ctx.quadraticCurveTo(x+w,y,x+w,y+r);
  ctx.lineTo(x+w,y+h-r);
  ctx.quadraticCurveTo(x+w,y+h,x+w-r,y+h);
  ctx.lineTo(x+r,y+h);
  ctx.quadraticCurveTo(x,y+h,x,y+h-r);
  ctx.lineTo(x,y+r);
  ctx.quadraticCurveTo(x,y,x+r,y);
  ctx.closePath();
}

// ---- PARTICLES ----
class ParticleSystem {
  constructor(x,y,targetX,targetY,color,count=30) {
    this.particles = [];
    this.color = color;
    this.srcX = x; this.srcY = y;
    this.tgtX = targetX; this.tgtY = targetY;
    for(let i=0;i<count;i++) {
      this.particles.push(this.spawn(Math.random()));
    }
  }
  spawn(progress=0) {
    const spread = 30;
    return {
      x: this.srcX + (Math.random()-0.5)*spread,
      y: this.srcY,
      progress: progress,
      speed: 0.002 + Math.random()*0.003,
      size: Math.random()*1.5+0.5,
      alpha: Math.random()*0.7+0.3,
      wobble: Math.random()*Math.PI*2,
      wobbleSpeed: Math.random()*2+1,
    };
  }
  update() {
    this.particles.forEach(p => {
      p.progress += p.speed;
      if(p.progress >= 1) {
        Object.assign(p, this.spawn(0));
      }
      const t2 = easeInOut(p.progress);
      p.x = lerp(this.srcX, this.tgtX, t2) + Math.sin(t*p.wobbleSpeed + p.wobble)*4*(1-t2);
      p.y = lerp(this.srcY, this.tgtY, t2);
    });
  }
  draw(alpha=1) {
    const {r,g,b} = hexToRgb(this.color);
    this.particles.forEach(p => {
      const fade = p.progress < 0.1 ? p.progress/0.1 : p.progress > 0.85 ? (1-p.progress)/0.15 : 1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI*2);
      ctx.fillStyle = `rgba(${r},${g},${b},${p.alpha*fade*alpha})`;
      ctx.fill();
      const g2 = ctx.createRadialGradient(p.x,p.y,0,p.x,p.y,p.size*4);
      g2.addColorStop(0, `rgba(${r},${g},${b},${p.alpha*fade*alpha*0.3})`);
      g2.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = g2;
      ctx.beginPath();
      ctx.arc(p.x,p.y,p.size*4,0,Math.PI*2);
      ctx.fill();
    });
  }
}

function drawDashFlow(x1,y1,x2,y2,color,progress,alpha=0.8) {
  const {r,g,b} = hexToRgb(color);
  const dx = x2-x1, dy = y2-y1;
  const len = Math.sqrt(dx*dx+dy*dy);
  const dashLen = 12, gapLen = 10;
  const period = dashLen + gapLen;
  const offset = (t*60) % period;

  ctx.save();
  ctx.strokeStyle = `rgba(${r},${g},${b},${alpha*0.3})`;
  ctx.lineWidth = 1;
  ctx.setLineDash([dashLen, gapLen]);
  ctx.lineDashOffset = -offset;
  ctx.shadowBlur = 8;
  ctx.shadowColor = color;
  ctx.beginPath();
  ctx.moveTo(x1,y1);
  ctx.lineTo(x2,y2);
  ctx.stroke();
  const dotT = ((t*0.04) % 1);
  const dotX = x1 + dx*dotT;
  const dotY = y1 + dy*dotT;
  ctx.setLineDash([]);
  glowCircle(dotX, dotY, 2.5, color, alpha);
  ctx.restore();
}

// ==== STAGE FUNCTIONS ====

let s1Particles = null;
function drawStage1(progress, centerY) {
  const fade = Math.min(1, progress*3);
  if(fade <= 0) return;

  const positions = [
    {x: W/2-220, label:'Claude / Cursor\nVS Code', sub:'MCP', color: C.teal},
    {x: W/2,     label:'Manual\nPaste', sub:'', color: C.cyan},
    {x: W/2+220, label:'Bookmarklet', sub:'', color: C.tealDim},
  ];

  const pW = 140, pH = 90;

  positions.forEach((p, i) => {
    const bob = Math.sin(t*0.8 + i*1.2)*5;
    const y = centerY + bob;
    const angle = (i-1)*0.08;

    ctx.save();
    ctx.translate(p.x, y);
    ctx.rotate(angle);

    glassPanel(-pW/2, -pH/2, pW, pH, p.color, 0.7*fade, 0.5*fade);

    const {r,g,b} = hexToRgb(p.color);
    ctx.fillStyle = `rgba(${r},${g},${b},0.15)`;
    roundRect(-pW/2, -pH/2, pW, 18, 0);
    ctx.fill();

    ['#ef4444','#f59e0b','#22c55e'].forEach((c,ci) => {
      ctx.beginPath();
      ctx.arc(-pW/2+8+ci*12, -pH/2+9, 3, 0, Math.PI*2);
      ctx.fillStyle = rgba(c, 0.7*fade);
      ctx.fill();
    });

    for(let ln=0; ln<4; ln++) {
      const lw = (30 + Math.random()*60 + i*10 + ln*7) % 80 + 20;
      const indent = ln>0 ? 8 : 0;
      ctx.fillStyle = `rgba(${r},${g},${b},${(0.15+ln*0.05)*fade})`;
      roundRect(-pW/2+8+indent, -pH/2+26+ln*12, lw, 4, 2);
      ctx.fill();
    }

    const lines = p.label.split('\n');
    lines.forEach((line, li) => {
      glowText(line, 0, pH/2+14+li*14, p.color, 9, 0.9*fade, 1);
    });

    if(p.sub === 'MCP') {
      const bx = pW/2-20, by = -pH/2+5;
      ctx.save();
      ctx.fillStyle = rgba(C.teal, 0.9*fade);
      roundRect(bx-12, by-5, 24, 14, 4);
      ctx.fill();
      ctx.font = 'bold 8px Courier New';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#080c14';
      ctx.fillText('MCP', bx, by+2);
      ctx.restore();
    }

    const pulseSz = (Math.sin(t*2+i)*0.3+0.7)*pW*0.6;
    ctx.strokeStyle = `rgba(${r},${g},${b},${0.1*fade})`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.ellipse(0, 0, pulseSz, pulseSz*0.3, 0, 0, Math.PI*2);
    ctx.stroke();

    ctx.restore();

    for(let a=0;a<3;a++) {
      const ay = y + pH/2 + 20 + a*12;
      const af = (Math.sin(t*2+a*0.8)*0.5+0.5)*fade;
      ctx.save();
      ctx.strokeStyle = rgba(p.color, af*0.5);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(p.x-5, ay);
      ctx.lineTo(p.x, ay+6);
      ctx.lineTo(p.x+5, ay);
      ctx.stroke();
      ctx.restore();
    }
  });

  if(!s1Particles) {
    s1Particles = positions.map(p =>
      new ParticleSystem(p.x, centerY+60, W/2, centerY+160, p.color, 25)
    );
  }
  s1Particles.forEach(ps => { ps.update(); ps.draw(fade*0.8); });
}

function drawStage2(progress, centerY) {
  const fade = Math.min(1, progress*3);
  if(fade <= 0) return;

  const nodes = [
    {x:W/2-260, label:'TRIAGE', sub:'High signal?', shape:'diamond', color:'#6b7280', size:18},
    {x:W/2-80,  label:'EXTRACTOR', sub:'Decisions + Alts', shape:'hex', color:C.teal, size:24},
    {x:W/2+90,  label:'CRITIQUE', sub:'Quality 0-10', shape:'circle', color:C.amber, size:20},
    {x:W/2+270, label:'GRAPH WRITER', sub:'Embed + Link', shape:'cube', color:C.teal, size:26},
  ];

  for(let i=0;i<nodes.length-1;i++) {
    const n1 = nodes[i], n2 = nodes[i+1];
    drawDashFlow(n1.x+n1.size, centerY, n2.x-n2.size, centerY, n1.color, 1, fade*0.7);
    const ax = n2.x - n2.size - 2;
    ctx.save();
    ctx.fillStyle = rgba(n2.color, fade*0.8);
    ctx.beginPath();
    ctx.moveTo(ax+8, centerY);
    ctx.lineTo(ax, centerY-4);
    ctx.lineTo(ax, centerY+4);
    ctx.fill();
    ctx.restore();
  }

  const n2 = nodes[1], n3 = nodes[2];
  const arcX = (n2.x + n3.x) / 2;
  const arcY = centerY - 65;
  const retryT = (t*0.4) % 1;
  ctx.save();
  ctx.strokeStyle = rgba(C.amber, 0.6*fade);
  ctx.lineWidth = 2;
  ctx.setLineDash([8,6]);
  ctx.lineDashOffset = -(t*40 % 28);
  ctx.beginPath();
  ctx.moveTo(n3.x, centerY - n3.size);
  ctx.quadraticCurveTo(arcX, arcY - 30, n2.x, centerY - n2.size);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.restore();

  glowText('retry score<7', arcX, arcY - 42, C.amber, 9, 0.9*fade, 1);
  const aParam = retryT;
  const arcBezX = (1-aParam)*(1-aParam)*n3.x + 2*(1-aParam)*aParam*arcX + aParam*aParam*n2.x;
  const arcBezY = (1-aParam)*(1-aParam)*(centerY-n3.size) + 2*(1-aParam)*aParam*(arcY-30) + aParam*aParam*(centerY-n2.size);
  glowCircle(arcBezX, arcBezY, 3, C.amber, 0.9*fade);

  nodes.forEach((n, i) => {
    const bob = Math.sin(t*0.9 + i*0.7)*4;
    const nx = n.x, ny = centerY + bob;
    const pulse = 1 + Math.sin(t*2+i)*0.15;

    ctx.save();
    ctx.translate(nx, ny);
    glowCircle(0, 0, n.size*pulse*1.8, n.color, 0.25*fade);

    if(n.shape === 'diamond') {
      ctx.fillStyle = rgba('#080c14', 0.9);
      ctx.strokeStyle = rgba(n.color, 0.8*fade);
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, -n.size*1.3); ctx.lineTo(n.size*1.1, 0); ctx.lineTo(0, n.size*1.3); ctx.lineTo(-n.size*1.1, 0);
      ctx.closePath(); ctx.fill(); ctx.stroke();
    } else if(n.shape === 'hex') {
      ctx.fillStyle = rgba('#080c14', 0.9);
      ctx.strokeStyle = rgba(n.color, 0.9*fade);
      ctx.lineWidth = 2;
      ctx.beginPath();
      for(let a=0;a<6;a++) {
        const angle = (a*Math.PI/3) - Math.PI/6;
        const hx = Math.cos(angle)*n.size*1.2, hy = Math.sin(angle)*n.size*1.2;
        a===0 ? ctx.moveTo(hx,hy) : ctx.lineTo(hx,hy);
      }
      ctx.closePath(); ctx.fill(); ctx.stroke();
    } else if(n.shape === 'cube') {
      const s = n.size;
      ctx.fillStyle = rgba('#080c14', 0.9);
      ctx.strokeStyle = rgba(n.color, 0.9*fade);
      ctx.lineWidth = 2;
      ctx.fillRect(-s,-s,s*2,s*2); ctx.strokeRect(-s,-s,s*2,s*2);
      ctx.beginPath();
      ctx.moveTo(-s,-s);ctx.lineTo(-s+8,-s-8);ctx.lineTo(s+8,-s-8);ctx.lineTo(s,-s);ctx.closePath();
      ctx.fillStyle = rgba(n.color, 0.15*fade); ctx.fill();
      ctx.strokeStyle = rgba(n.color, 0.6*fade); ctx.lineWidth = 1.5; ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(s,-s);ctx.lineTo(s+8,-s-8);ctx.lineTo(s+8,s-8);ctx.lineTo(s,s);ctx.closePath();
      ctx.fillStyle = rgba(n.color, 0.08*fade); ctx.fill(); ctx.stroke();
    } else {
      glowCircle(0, 0, n.size*pulse, n.color, 0.8*fade);
    }

    glowText(n.label, 0, n.size*2 + 18, n.color, 9, 0.95*fade, 2);
    glowText(n.sub, 0, n.size*2 + 32, '#8899aa', 8, 0.7*fade, 0);
    ctx.restore();
  });

  const inFlow = Math.min(1, progress*5);
  if(inFlow > 0) {
    for(let i=0;i<5;i++) {
      const pt = ((t*0.3 + i/5) % 1);
      const px = lerp(W/2-30, nodes[0].x, easeInOut(pt));
      const py = lerp(centerY-80, centerY, easeInOut(pt));
      glowCircle(px, py, 2, C.teal, pt < 0.9 ? inFlow*0.8 : 0);
    }
  }
}

const neo4jNodes = [
  {x:-50,y:-20,r:6,c:C.teal},{x:0,y:-40,r:5,c:C.purple},
  {x:40,y:-10,r:6,c:C.teal},{x:-10,y:25,r:4,c:'#ef4444'},
  {x:35,y:30,r:5,c:C.purple},
];
const neo4jEdges = [
  {a:0,b:1,c:C.teal,label:'CAUSED_BY'},
  {a:1,b:2,c:C.purple,label:'SIMILAR_TO'},
  {a:2,b:4,c:C.purple,label:'SIMILAR_TO'},
  {a:0,b:3,c:'#ef4444',label:'SUPERSEDES'},
  {a:3,b:4,c:C.teal,label:'CAUSED_BY'},
];
const chromaDots = Array.from({length:40}, () => ({
  x: (Math.random()-0.5)*100, y: (Math.random()-0.5)*70,
  c: Math.random() < 0.5 ? C.teal : C.purple,
  r: Math.random()*2+1, a: Math.random()*0.6+0.3,
  cluster: Math.floor(Math.random()*3),
}));

function drawStage3(progress, centerY) {
  const fade = Math.min(1, progress*3);
  if(fade <= 0) return;

  const leftX = W/2 - 200, rightX = W/2 + 200;
  const pW = 190, pH = 150;
  const srcX = W/2, srcY = centerY - 40;
  const leftPY = centerY + 20, rightPY = centerY + 20;

  ctx.save();
  ctx.strokeStyle = rgba(C.teal, 0.4*fade);
  ctx.lineWidth = 1.5;
  ctx.setLineDash([6,4]);
  ctx.lineDashOffset = -(t*30 % 20);
  ctx.beginPath(); ctx.moveTo(srcX, srcY); ctx.quadraticCurveTo(srcX-60, srcY+30, leftX, leftPY); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(srcX, srcY); ctx.quadraticCurveTo(srcX+60, srcY+30, rightX, rightPY); ctx.stroke();
  ctx.setLineDash([]);
  ctx.restore();

  const nBob = Math.sin(t*0.7)*4;
  ctx.save();
  ctx.translate(leftX, centerY + nBob);
  glassPanel(-pW/2, -pH/2, pW, pH, C.purple, 0.8, 0.5*fade);

  neo4jEdges.forEach(e => {
    const na = neo4jNodes[e.a], nb = neo4jNodes[e.b];
    const {r,g,b} = hexToRgb(e.c);
    ctx.strokeStyle = `rgba(${r},${g},${b},${0.7*fade})`;
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(na.x, na.y); ctx.lineTo(nb.x, nb.y); ctx.stroke();
  });
  neo4jNodes.forEach(n => { glowCircle(n.x, n.y, n.r, n.c, 0.9*fade, 10); });

  glowText('NEO4J AURADB', 0, pH/2-30, C.purple, 9, 0.95*fade, 2);
  glowText('Causal Knowledge', 0, pH/2-16, '#8899aa', 8, 0.7*fade, 0);
  ctx.restore();

  const cBob = Math.sin(t*0.7+1)*4;
  ctx.save();
  ctx.translate(rightX, centerY + cBob);
  glassPanel(-pW/2, -pH/2, pW, pH, C.teal, 0.8, 0.5*fade);

  const clusterCenters = [{x:-30,y:-15},{x:20,y:-25},{x:5,y:20}];
  chromaDots.forEach(d => {
    const cc = clusterCenters[d.cluster];
    const dx = d.x*0.5 + cc.x*0.5, dy = d.y*0.4 + cc.y*0.6;
    const {r,g,b} = hexToRgb(d.c);
    ctx.beginPath(); ctx.arc(dx, dy, d.r, 0, Math.PI*2);
    ctx.fillStyle = `rgba(${r},${g},${b},${d.a*fade})`; ctx.fill();
  });
  clusterCenters.forEach((cc, i) => {
    const cr = [22,18,20][i];
    const cc2 = [C.teal, C.purple, C.cyan][i];
    ctx.strokeStyle = rgba(cc2, 0.15*fade);
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.ellipse(cc.x, cc.y, cr, cr*0.8, i*0.3, 0, Math.PI*2); ctx.stroke();
  });

  glowText('CHROMADB LOCAL', 0, pH/2-30, C.teal, 9, 0.95*fade, 2);
  glowText('Vector Embeddings', 0, pH/2-16, '#8899aa', 8, 0.7*fade, 0);
  ctx.restore();
}

function drawStage4(progress, centerY) {
  const fade = Math.min(1, progress*3);
  if(fade <= 0) return;

  const layers = [
    {label:'SEMANTIC SEARCH', sub:'Cosine similarity', color:C.teal, w:320, h:42},
    {label:'CAUSAL ANCESTRY', sub:'Upstream chains', color:C.blue, w:270, h:42},
    {label:'FULL EPISODE', sub:'Decision + counterparts', color:C.purple, w:220, h:42},
    {label:'COUNTERFACTUAL', sub:'Rejected roads', color:C.amber, w:170, h:48},
  ];

  let cy = centerY - 75;
  layers.forEach((l, i) => {
    const bob = Math.sin(t*0.6 + i*0.5)*3;
    const yy = cy + bob;
    const pulseMult = i === 3 ? (1 + Math.sin(t*3)*0.08) : 1;
    const lFade = Math.min(1, (progress - i*0.05)*4);
    if(lFade <= 0) { cy += l.h + 8; return; }

    const lw = l.w * pulseMult, lh = l.h * pulseMult;
    glassPanel(W/2 - lw/2, yy - lh/2, lw, lh, l.color, 0.8, (0.4 + (i===3?0.3:0))*fade);

    if(i === 3) {
      const pr = (Math.sin(t*3)*0.5+0.5) * 20;
      ctx.strokeStyle = rgba(C.amber, (0.4 - pr/50)*fade);
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.ellipse(W/2, yy, lw/2 + pr, lh/2 + pr*0.4, 0, 0, Math.PI*2); ctx.stroke();
    }

    glowText(l.label, W/2, yy - 8, l.color, 10, 0.95*lFade, 2);
    glowText(l.sub, W/2, yy + 8, '#8899aa', 8, 0.75*lFade, 0);

    for(let p=0;p<4;p++) {
      const pt = ((t*0.4 + p/4 + i*0.2) % 1);
      if(pt > 0 && pt < 0.95) {
        const px = lerp(W/2 - lw/2 + 20, W/2 + lw/2 - 20, pt);
        const py2 = yy + (Math.random()-0.5)*6;
        glowCircle(px, yy, 1.5, l.color, pt*(1-pt)*4*fade*0.6);
      }
    }
    cy += l.h + 10;
  });

  ctx.save();
  ctx.strokeStyle = rgba(C.teal, 0.15*fade);
  ctx.lineWidth = 1;
  ctx.setLineDash([3,5]);
  const topW = layers[0].w/2, botW = layers[3].w/2;
  const topY = centerY - 75 - layers[0].h/2;
  const botY = centerY - 75 + (layers[0].h+10)*3 + layers[3].h/2;
  ctx.beginPath(); ctx.moveTo(W/2-topW, topY); ctx.lineTo(W/2-botW, botY); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(W/2+topW, topY); ctx.lineTo(W/2+botW, botY); ctx.stroke();
  ctx.setLineDash([]);
  ctx.restore();
}

function drawStage5(progress, centerY) {
  const fade = Math.min(1, progress*3);
  if(fade <= 0) return;

  const panels = [
    {x:W/2-210, label:'MCP CONTEXT', sub:'→ IDE Session', icon:'⬡', color:C.teal},
    {x:W/2,     label:'BRIEFING', sub:'Context doc', icon:'≡', color:C.cyan},
    {x:W/2+210, label:'CLI SEARCH', sub:'$ engram ...', icon:'>', color:C.tealDim},
  ];

  const pW = 150, pH = 90;

  panels.forEach((p, i) => {
    const bob = Math.sin(t*0.7 + i*1.3)*5;
    const y = centerY + bob;

    ctx.save();
    ctx.translate(p.x, y);
    glassPanel(-pW/2, -pH/2, pW, pH, p.color, 0.7*fade, 0.5*fade);

    const {r,g,b} = hexToRgb(p.color);
    ctx.font = '18px Courier New';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = `rgba(${r},${g},${b},${0.6*fade})`;
    ctx.fillText(p.icon, 0, -15);

    for(let ln=0;ln<3;ln++) {
      const lw = [60,45,70][ln];
      ctx.fillStyle = `rgba(${r},${g},${b},${(0.1+ln*0.04)*fade})`;
      roundRect(-pW/2+10, 5+ln*12, lw, 4, 2); ctx.fill();
    }

    glowText(p.label, 0, pH/2+12, p.color, 9, 0.95*fade, 2);
    glowText(p.sub, 0, pH/2+26, '#8899aa', 8, 0.7*fade, 0);

    for(let pt=0;pt<4;pt++) {
      const ptt = ((t*0.35 + pt/4) % 1);
      const py2 = lerp(y-80, y - pH/2, easeInOut(ptt));
      glowCircle(p.x + (Math.random()-0.5)*8, py2, 1.5, p.color, 0.6*fade);
    }
    ctx.restore();
  });
}

// ==== UI SYNC (THE FIX) ====
function updateUI(norm) {
  const stageCount = 5;
  
  // Update progress dots cleanly
  let activeIndex = Math.round(norm * (stageCount - 1));
  activeIndex = Math.max(0, Math.min(activeIndex, stageCount - 1));
  
  const dots = document.querySelectorAll('.prog-dot');
  dots.forEach((d,i) => {
    d.classList.toggle('active', i === activeIndex);
  });

  // Calculate and fade labels exactly when they approach the center view
  const labels = document.querySelectorAll('.stage-label');
  labels.forEach((el, i) => {
    const stagePos = (i / (stageCount - 1)); // 0, 0.25, 0.5, 0.75, 1.0
    const distanceToCenter = Math.abs(norm - stagePos);
    
    // Tight visible window so title only appears when its stage is prominently centered
    const visible = distanceToCenter < 0.18;
    el.classList.toggle('visible', visible);
  });

  const hint = document.getElementById('scroll-hint');
  hint.style.opacity = norm < 0.02 ? '1' : '0';
}

function getStageCenterY(stageIndex, numStages=5) {
  const norm = smoothScroll; // Now directly using the 0-1 norm
  const stageY = (stageIndex / (numStages-1));
  const relativeY = stageY - norm;
  return H * 0.5 + relativeY * H * 3.5;
}

function drawFeedbackLoop(y1, y5) {
  // Only draw if part of the line might be visible
  if (y5 < -500 || y1 > H + 500) return;

  const startX = W/2 - 280; // Left side of stage 5
  const endX = W/2 - 290;   // Left side of stage 1
  const midY = (y1 + y5) / 2;
  const cpX = W/2 - 450;    // Arching far left out of the main column

  ctx.save();
  // Faint glowing line
  ctx.strokeStyle = rgba(C.teal, 0.2);
  ctx.lineWidth = 1.5;
  ctx.setLineDash([10, 10]);
  
  // Animate dashes upwards (drawing from y5 up to y1)
  ctx.lineDashOffset = -(t * 30 % 20); 

  ctx.beginPath();
  ctx.moveTo(startX, y5);
  ctx.quadraticCurveTo(cpX, midY, endX, y1 + 60);
  ctx.stroke();

  // Reset dash for particles and text
  ctx.setLineDash([]);

  // Traveling light pulses along the bezier curve
  for(let i=0; i<4; i++) {
    const p = (t * 0.15 + i/4) % 1; // 0 to 1
    const pInv = 1 - p;
    // Quadratic bezier interpolation
    const cx = pInv*pInv * startX + 2*pInv*p * cpX + p*p * endX;
    const cy = pInv*pInv * y5 + 2*pInv*p * midY + p*p * (y1 + 60);
    
    // Fade pulse out near the very ends
    const edgeFade = p < 0.05 ? p/0.05 : (p > 0.95 ? (1-p)/0.05 : 1);
    
    glowCircle(cx, cy, 2.5, C.teal, 0.8 * edgeFade);
  }

  // Label positioned midway along the curve
  const textP = 0.5;
  const textX = (1-textP)*(1-textP)*startX + 2*(1-textP)*textP*cpX + textP*textP*endX;
  const textY = (1-textP)*(1-textP)*y5 + 2*(1-textP)*textP*midY + textP*textP*(y1 + 60);
  
  ctx.save();
  ctx.translate(textX - 10, textY);
  ctx.rotate(-Math.PI/2 - 0.1); // Rotated to align nicely with typical scroll
  glowText('feedback loop →', 0, 0, C.teal, 10, 0.4, 2);
  ctx.restore();

  ctx.restore();
}

function render() {
  t += 0.016;

  if(!archSection) {
     requestAnimationFrame(render);
     return;
  }

  const rect = archSection.getBoundingClientRect();
  if (rect.bottom < 0 || rect.top > window.innerHeight) {
     requestAnimationFrame(render);
     return; // Skip expensive drawing if not in view
  }

  targetScroll = getSectionNorm();
  smoothScroll += (targetScroll - smoothScroll) * 0.06;

  const norm = smoothScroll;

  updateUI(norm);

  ctx.clearRect(0,0,W,H);
  drawBackground(norm);

  // Draw the global feedback loop connecting Stage 5 back to Stage 1
  const stage1Y = getStageCenterY(0);
  const stage5Y = getStageCenterY(4);
  drawFeedbackLoop(stage1Y, stage5Y);

  const stagePositions = [0, 0.25, 0.5, 0.75, 1];

  stagePositions.forEach((sp, i) => {
    const relNorm = norm - sp;
    const dist = Math.abs(relNorm) * 4;
    const stageFade = Math.max(0, 1 - dist*0.7);
    const cy = getStageCenterY(i);

    if(cy < -200 || cy > H+200) return;

    const stageProgress = (norm - (i-0.5)/4.5) * 5;
    const clampedProgress = Math.max(0, Math.min(2, stageProgress));

    ctx.save();
    ctx.globalAlpha = stageFade;

    switch(i) {
      case 0: drawStage1(clampedProgress, cy); break;
      case 1: drawStage2(clampedProgress, cy); break;
      case 2: drawStage3(clampedProgress, cy); break;
      case 3: drawStage4(clampedProgress, cy); break;
      case 4: drawStage5(clampedProgress, cy); break;
    }

    ctx.restore();
  });

  ctx.strokeStyle = rgba(C.teal, 0.03);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(W/2, 0); ctx.lineTo(W/2, H);
  ctx.stroke();

  requestAnimationFrame(render);
}

render();
