/* ============================================
   ENGRAM — Neural Background
   Canvas 2D animated particles + connections
   ============================================ */

window.NeuralBg = {
  canvas: null,
  ctx: null,
  particles: [],
  animationId: null,
  
  // Configuration
  config: {
    particleCount: 70,
    connectionDistance: 150,
    particleSpeed: 0.3,
    fireProbability: 0.005
  },

  /**
   * Initialize the neural background
   */
  init() {
    this.canvas = document.getElementById('neural-bg');
    if (!this.canvas) return;
    
    this.ctx = this.canvas.getContext('2d');
    this.resize();
    this.createParticles();
    this.animate();
    
    window.addEventListener('resize', () => this.resize());
  },

  /**
   * Resize canvas to fill viewport
   */
  resize() {
    const parent = this.canvas.parentElement;
    this.canvas.width = parent.clientWidth;
    this.canvas.height = parent.clientHeight;
  },

  /**
   * Create particle array
   */
  createParticles() {
    this.particles = [];
    for (let i = 0; i < this.config.particleCount; i++) {
      this.particles.push({
        x: Math.random() * this.canvas.width,
        y: Math.random() * this.canvas.height,
        vx: (Math.random() - 0.5) * this.config.particleSpeed,
        vy: (Math.random() - 0.5) * this.config.particleSpeed,
        radius: Math.random() * 2 + 1.5,
        opacity: Math.random() * 0.15 + 0.05,
        firing: 0,
        fireIntensity: 0
      });
    }
  },

  /**
   * Update particle positions and states
   */
  update() {
    this.particles.forEach(p => {
      // Move
      p.x += p.vx;
      p.y += p.vy;
      
      // Bounce off edges
      if (p.x < 0 || p.x > this.canvas.width) p.vx *= -1;
      if (p.y < 0 || p.y > this.canvas.height) p.vy *= -1;
      
      // Random firing (neuron activation)
      if (p.firing <= 0 && Math.random() < this.config.fireProbability) {
        p.firing = 20 + Math.random() * 20;
        p.fireIntensity = 0.3 + Math.random() * 0.2;
      }
      
      if (p.firing > 0) {
        p.firing--;
      }
    });
  },

  /**
   * Draw the neural network
   */
  draw() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    
    // Clear with fade for trails
    ctx.fillStyle = 'rgba(10, 15, 26, 0.15)';
    ctx.fillRect(0, 0, w, h);
    
    // Draw connections
    this.particles.forEach((p1, i) => {
      this.particles.slice(i + 1).forEach(p2 => {
        const dx = p1.x - p2.x;
        const dy = p1.y - p2.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        
        if (dist < this.config.connectionDistance) {
          const opacity = (1 - dist / this.config.connectionDistance) * 0.08;
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.strokeStyle = `rgba(0, 212, 170, ${opacity})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      });
    });
    
    // Draw particles
    this.particles.forEach(p => {
      // Fire glow
      if (p.firing > 0) {
        const fireOpacity = (p.firing / 40) * p.fireIntensity;
        const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.radius * 4);
        gradient.addColorStop(0, `rgba(0, 212, 170, ${fireOpacity})`);
        gradient.addColorStop(1, 'rgba(0, 212, 170, 0)');
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius * 4, 0, Math.PI * 2);
        ctx.fill();
      }
      
      // Core particle
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0, 212, 170, ${p.opacity + (p.firing > 0 ? 0.4 : 0)})`;
      ctx.fill();
    });
  },

  /**
   * Animation loop
   */
  animate() {
    this.update();
    this.draw();
    this.animationId = requestAnimationFrame(() => this.animate());
  },

  /**
   * Stop animation
   */
  stop() {
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
    }
  }
};
