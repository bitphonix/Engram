/* ============================================
   ENGRAM — Search Module
   Context retrieval, results display, briefing
   ============================================ */

window.Search = {
  /**
   * Render search form
   */
  renderForm(prefillQuery = '') {
    return `
      <div class="form-group">
        <label class="form-label">Query</label>
        <input type="text" class="form-input" id="search-query" placeholder="e.g., database for high throughput" value="${prefillQuery}">
      </div>
      
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Domain (optional)</label>
          <select class="form-select" id="search-domain">
            <option value="">All domains</option>
            <option value="database">Database</option>
            <option value="architecture">Architecture</option>
            <option value="authentication">Authentication</option>
            <option value="infrastructure">Infrastructure</option>
            <option value="deployment">Deployment</option>
            <option value="framework">Framework</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Concerns (optional)</label>
          <input type="text" class="form-input" id="search-concerns" placeholder="e.g., performance, cost">
        </div>
      </div>
      
      <button class="btn btn-accent btn-full" id="btn-retrieve">
        Retrieve →
      </button>
      
      <div id="search-results"></div>
    `;
  },

  /**
   * Submit search
   */
  async submit(query) {
    const btn = document.getElementById('btn-retrieve');
    const results = document.getElementById('search-results');
    
    if (!query) query = document.getElementById('search-query').value;
    if (!query.trim()) return;
    
    btn.classList.add('btn-loading');
    btn.disabled = true;
    results.innerHTML = '<div class="progress-bar" style="margin-top: 20px;"><div class="progress-fill"></div></div>';
    
    const domain = document.getElementById('search-domain')?.value;
    const concerns = document.getElementById('search-concerns')?.value;
    
    const data = await window.API.context({
      query,
      domain: domain || undefined,
      concerns: concerns ? concerns.split(',').map(c => c.trim()) : undefined
    });
    
    btn.classList.remove('btn-loading');
    btn.disabled = false;
    
    this.renderResults(data);
  },

  /**
   * Render search results
   */
  renderResults(data) {
    const container = document.getElementById('search-results');
    
    let html = '';
    
    // Warnings section
    if (data.level4_warnings?.length) {
      html += `<div class="section-header" style="color: var(--warning);">⚠ Warnings — Past Rejections</div>`;
      html += data.level4_warnings.map(w => `
        <div class="warning-card">
          <div class="warning-header">
            <span>⚠</span>
            <span class="warning-title">You rejected ${w.counterfactual.rejected_option}</span>
          </div>
          <div class="warning-reason">${w.counterfactual.rejection_reason}</div>
          <div class="warning-meta">
            <span class="tag tag-concern">${w.counterfactual.rejection_concern}</span>
            <span class="tag tag-project">${w.session.project_id}</span>
          </div>
        </div>
      `).join('');
    }
    
    // Decisions section
    if (data.level1_decisions?.length) {
      html += `<div class="section-header">Related Decisions</div>`;
      html += data.level1_decisions.map(d => {
        const domainColor = window.Graph.domainColors[d.domain] || 'var(--accent)';
        return `
          <div class="card card-clickable" onclick="window.Graph.highlightNode('${d.id}')">
            <div class="card-title">${d.summary}</div>
            <div class="card-meta">
              <span class="tag tag-domain" style="--domain-color: ${domainColor}">${d.domain}</span>
              <span class="tag tag-project">${d.project_id}</span>
              <span class="card-score">${(d.score * 100).toFixed(0)}% match</span>
            </div>
          </div>
        `;
      }).join('');
    }
    
    // Briefing section
    if (data.briefing) {
      html += `<div class="section-header">Generated Briefing</div>`;
      html += `
        <div class="briefing">
          <button class="briefing-copy" onclick="navigator.clipboard.writeText(this.nextElementSibling.textContent); this.textContent='Copied!'; setTimeout(() => this.textContent='Copy', 1500)">Copy</button>
          <div>${data.briefing}</div>
        </div>
      `;
    }
    
    if (!html) {
      html = '<div style="text-align: center; padding: 40px; color: var(--text-muted);">No results found</div>';
    }
    
    container.innerHTML = html;
  }
};

// Wire up search button after panel renders
document.addEventListener('click', (e) => {
  if (e.target.id === 'btn-retrieve') {
    window.Search.submit();
  }
});
