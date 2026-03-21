/* ============================================
   ENGRAM — Ingest Module
   Ingest form, submission, animated result metrics
   ============================================ */

window.Ingest = {
  /**
   * Render ingest form
   */
  renderForm() {
    return `
      <div class="form-group">
        <label class="form-label">Session Content</label>
        <textarea class="form-textarea" id="ingest-content" placeholder="Paste your conversation, decision log, or technical discussion here..."></textarea>
      </div>
      
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Project ID</label>
          <input type="text" class="form-input" id="ingest-project" placeholder="e.g., myapp-backend">
        </div>
        <div class="form-group">
          <label class="form-label">Tool</label>
          <input type="text" class="form-input" id="ingest-tool" placeholder="e.g., claude, chatgpt">
        </div>
      </div>
      
      <button class="btn btn-accent btn-full" id="btn-ingest-submit">
        Ingest →
      </button>
      
      <div id="ingest-results"></div>
    `;
  },

  /**
   * Submit ingest
   */
  async submit() {
    const content = document.getElementById('ingest-content').value.trim();
    const projectId = document.getElementById('ingest-project').value.trim();
    const tool = document.getElementById('ingest-tool').value.trim();
    const btn = document.getElementById('btn-ingest-submit');
    const results = document.getElementById('ingest-results');
    
    if (!content) {
      alert('Please enter session content');
      return;
    }
    
    btn.classList.add('btn-loading');
    btn.disabled = true;
    results.innerHTML = '<div class="progress-bar" style="margin-top: 20px;"><div class="progress-fill"></div></div>';
    
    const data = await window.API.ingest({
      content,
      project_id: projectId || undefined,
      tool: tool || undefined
    });
    
    btn.classList.remove('btn-loading');
    btn.disabled = false;
    
    this.renderResults(data);
    
    // Refresh stats and graph
    window.App.refreshStats();
    window.Graph.reload();
  },

  /**
   * Render ingest results with animated metrics
   */
  renderResults(data) {
    const container = document.getElementById('ingest-results');
    
    if (data.error) {
      container.innerHTML = `<div style="color: var(--edge-supersedes); margin-top: 16px; font-size: 0.875rem;">Error: ${data.error}</div>`;
      return;
    }
    
    const metrics = [
      { label: 'decisions saved', value: data.saved_decisions || 0 },
      { label: 'counterfactuals', value: data.saved_counterfactuals || 0 },
      { label: 'primary domain', value: data.domain_primary || '—', isText: true },
      { label: 'critique score', value: data.critique_score || 0, isDecimal: true }
    ];
    
    let html = '<div class="metrics-grid" style="margin-top: 20px;">';
    
    metrics.forEach((m, i) => {
      html += `
        <div class="metric-card">
          <div class="metric-value" id="metric-${i}" data-target="${m.isText ? '' : m.value}" data-decimal="${m.isDecimal || false}">
            ${m.isText ? m.value : '0'}
          </div>
          <div class="metric-label">${m.label}</div>
        </div>
      `;
    });
    
    html += '</div>';
    
    if (data.session_summary) {
      html += `
        <div class="card" style="margin-top: 16px;">
          <div class="form-label">Session Summary</div>
          <p style="font-size: 0.8125rem; color: var(--text-secondary); line-height: 1.6;">
            ${data.session_summary}
          </p>
        </div>
      `;
    }
    
    container.innerHTML = html;
    
    // Animate number counters
    metrics.forEach((m, i) => {
      if (m.isText) return;
      
      const el = document.getElementById(`metric-${i}`);
      const target = parseFloat(m.value) || 0;
      const isDecimal = m.isDecimal;
      const duration = 800;
      const start = performance.now();
      
      const animate = (now) => {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = target * eased;
        
        el.textContent = isDecimal ? current.toFixed(3) : Math.round(current);
        
        if (progress < 1) {
          requestAnimationFrame(animate);
        }
      };
      
      requestAnimationFrame(animate);
    });
  }
};

// Wire up ingest button
document.addEventListener('click', (e) => {
  if (e.target.id === 'btn-ingest-submit') {
    window.Ingest.submit();
  }
});
