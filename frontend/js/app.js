/* ============================================
   ENGRAM — Application Controller
   Init, stats polling, event wiring, bookmarklet
   ============================================ */

window.App = {
  statsInterval: null,
  previousStats: {},

  /**
   * Initialize the application
   */
  init() {
    // Initialize modules
    window.NeuralBg.init();
    window.Graph.init();
    window.Panels.init();
    
    // Load initial data
    this.refreshStats();
    window.API.getNetwork().then(data => window.Graph.render(data));
    
    // Start polling
    this.statsInterval = setInterval(() => this.refreshStats(), 30000);
    
    // Wire up events
    this.wireEvents();
  },

  /**
   * Refresh stats with animation
   */
  async refreshStats() {
    const data = await window.API.getStats();
    
    const stats = [
      { id: 'stat-decisions', value: data.active_decisions || 0, decimals: 0 },
      { id: 'stat-counterfactuals', value: data.total_counterfactuals || 0, decimals: 0 },
      { id: 'stat-weight', value: data.avg_epistemic_weight || 0, decimals: 3 }
    ];
    
    stats.forEach(stat => {
      const el = document.getElementById(stat.id);
      if (!el) return;
      
      const previous = this.previousStats[stat.id] || 0;
      const current = stat.value;
      
      if (previous !== current) {
        // Flash animation
        el.classList.add('flash');
        setTimeout(() => el.classList.remove('flash'), 300);
        
        // Count up animation
        const duration = 800;
        const start = performance.now();
        
        const animate = (now) => {
          const elapsed = now - start;
          const progress = Math.min(elapsed / duration, 1);
          const eased = 1 - Math.pow(1 - progress, 3);
          const value = previous + (current - previous) * eased;
          
          el.textContent = stat.decimals === 0 
            ? Math.round(value).toString()
            : value.toFixed(stat.decimals);
          
          if (progress < 1) {
            requestAnimationFrame(animate);
          }
        };
        
        requestAnimationFrame(animate);
        this.previousStats[stat.id] = current;
      }
    });
  },

  /**
   * Wire up all event listeners
   */
  wireEvents() {
    // Rail buttons
    document.querySelectorAll('.rail-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const mode = btn.dataset.mode;
        if (mode === 'graph') {
          window.Panels.close();
        } else {
          window.Panels.open(mode);
        }
      });
    });
    
    // Filter pills
    document.querySelectorAll('.pill').forEach(pill => {
      pill.addEventListener('click', () => {
        document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        window.Graph.filter(pill.dataset.domain);
      });
    });
    
    // Header search
    const searchInput = document.querySelector('.search-input');
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && searchInput.value.trim()) {
        window.Panels.open('search', { query: searchInput.value.trim() });
      }
    });
    
    // Header buttons
    document.getElementById('btn-ingest').addEventListener('click', () => {
      window.Panels.open('ingest');
    });
    
    document.getElementById('btn-run-engine').addEventListener('click', async () => {
      const btn = document.getElementById('btn-run-engine');
      btn.classList.add('btn-loading');
      btn.disabled = true;
      
      await window.API.runEngine();
      
      btn.classList.remove('btn-loading');
      btn.disabled = false;
      
      this.refreshStats();
      window.Graph.reload();
    });
    
    // Graph toolbar
    document.getElementById('btn-reset-view').addEventListener('click', () => {
      window.Graph.fitView();
    });
    
    document.getElementById('btn-refresh').addEventListener('click', () => {
      window.Graph.reload();
    });
  }
};

// Start on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  window.App.init();
});
