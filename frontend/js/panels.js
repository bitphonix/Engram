/* ============================================
   ENGRAM — Panel System
   Open/close/switch, content rendering for all modes
   ============================================ */

window.Panels = {
  panel: null,
  body: null,
  title: null,
  currentMode: null,

  /**
   * Initialize panel system
   */
  init() {
    this.panel = document.getElementById('panel');
    this.body = document.getElementById('panel-body');
    this.title = document.getElementById('panel-title');
    
    document.getElementById('panel-close').addEventListener('click', () => this.close());
    
    // Close on canvas click
    document.querySelector('.canvas').addEventListener('click', (e) => {
      if (e.target.id === 'graph-svg' || e.target.id === 'neural-bg') {
        this.close();
      }
    });
  },

  /**
   * Open panel with specific mode
   */
  open(mode, data = {}) {
    this.currentMode = mode;
    this.panel.classList.add('open');
    document.querySelector('.canvas').classList.add('dimmed');
    
    // Update rail buttons
    document.querySelectorAll('.rail-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    
    // Render content based on mode
    switch (mode) {
      case 'node':
        this.renderNodePanel(data);
        break;
      case 'search':
        this.renderSearchPanel(data);
        break;
      case 'ingest':
        this.renderIngestPanel();
        break;
      case 'capture':
        this.renderCapturePanel();
        break;
    }
  },

  /**
   * Close panel
   */
  close() {
    this.panel.classList.remove('open');
    document.querySelector('.canvas').classList.remove('dimmed');
    this.currentMode = null;
    
    // Reset rail
    document.querySelectorAll('.rail-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.mode === 'graph');
    });
  },

  /**
   * Render node details panel
   */
  renderNodePanel(node) {
    this.title.textContent = 'Decision Details';
    const domainColor = window.Graph.domainColors[node.domain] || 'var(--accent)';
    
    this.body.innerHTML = `
      <div class="panel-content">
        <h3 style="font-size: 1.125rem; line-height: 1.4; margin-bottom: 12px;">${node.summary}</h3>
        
        <div class="card-meta" style="margin-bottom: 16px;">
          <span class="tag tag-domain" style="--domain-color: ${domainColor}">${node.domain}</span>
          <span class="tag tag-project">${node.project_id}</span>
          ${node.is_invalidated ? '<span class="tag tag-invalidated">superseded</span>' : ''}
        </div>
        
        <div class="form-label">Chosen Option</div>
        <div style="color: ${domainColor}; font-family: 'JetBrains Mono', monospace; font-size: 0.875rem; margin-bottom: 16px;">
          ${node.chosen || 'N/A'}
        </div>
        
        <div class="form-label">Epistemic Weight</div>
        <div class="weight-bar">
          <div class="weight-fill" style="width: ${node.weight * 100}%; --domain-color: ${domainColor};"></div>
        </div>
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 20px;">
          ${node.weight.toFixed(3)}
        </div>
        
        <button class="btn btn-ghost btn-full" id="btn-load-episode">
          Load full episode →
        </button>
        
        <div id="episode-details" style="margin-top: 16px;"></div>
        
        <div class="danger-zone">
          <div class="danger-title">Danger Zone</div>
          <button class="btn btn-danger btn-full" id="btn-delete-decision">Delete decision</button>
        </div>
      </div>
    `;
    
    // Load episode handler
    document.getElementById('btn-load-episode').addEventListener('click', async () => {
      const details = document.getElementById('episode-details');
      details.innerHTML = '<div class="progress-bar"><div class="progress-fill"></div></div>';
      
      const data = await window.API.getDecision(node.id);
      
      if (data.decision) {
        details.innerHTML = `
          <div class="card" style="margin-bottom: 12px;">
            <div class="form-label">Reasoning</div>
            <p style="font-size: 0.8125rem; color: var(--text-secondary); line-height: 1.6;">
              ${data.decision.reasoning || 'No reasoning recorded.'}
            </p>
          </div>
          
          ${data.counterfactuals.length ? `
            <div class="section-header">Rejected Alternatives</div>
            ${data.counterfactuals.map(cf => `
              <div class="card" style="margin-bottom: 8px; border-left: 2px solid var(--warning);">
                <div style="color: var(--warning); font-weight: 500; font-size: 0.8125rem; margin-bottom: 4px;">
                  ${cf.rejected_option}
                </div>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px;">
                  ${cf.rejection_reason}
                </div>
                <span class="tag tag-concern">${cf.rejection_concern}</span>
              </div>
            `).join('')}
          ` : ''}
        `;
      }
    });
    
    // Delete handler
    document.getElementById('btn-delete-decision').addEventListener('click', async () => {
      if (confirm('Are you sure? This cannot be undone.')) {
        await window.API.deleteDecision(node.id);
        this.close();
        window.Graph.reload();
      }
    });
  },

  /**
   * Render search panel
   */
  renderSearchPanel(data) {
    this.title.textContent = 'Search';
    this.body.innerHTML = '<div class="panel-content" id="search-content"></div>';
    document.getElementById('search-content').innerHTML = window.Search.renderForm(data.query || '');
    
    if (data.query) {
      window.Search.submit(data.query);
    }
  },

  /**
   * Render ingest panel
   */
  renderIngestPanel() {
    this.title.textContent = 'Ingest Session';
    this.body.innerHTML = '<div class="panel-content" id="ingest-content"></div>';
    document.getElementById('ingest-content').innerHTML = window.Ingest.renderForm();
  },

  /**
   * Render capture panel
   */
  renderCapturePanel() {
    this.title.textContent = 'Capture';
    this.body.innerHTML = `
      <div class="panel-content">
        <p style="font-size: 0.875rem; color: var(--text-secondary); line-height: 1.6; margin-bottom: 16px;">
          Capture decisions from any webpage. Drag the button below to your bookmarks bar.
        </p>
        
        <a href="javascript:(function(){fetch(window.location.origin+'/ingest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:document.body.innerText.slice(0,50000),tool:'web',captured_via:'bookmarklet'})}).then(r=>r.json()).then(d=>alert('Engram: '+d.saved_decisions+' decisions saved')).catch(e=>alert('Engram error: '+e.message))})()" 
           class="bookmarklet" 
           onclick="event.preventDefault(); alert('Drag this to your bookmarks bar!');">
          <svg viewBox="0 0 24 24" width="16" height="16"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 8v8M8 12h8" fill="none" stroke="currentColor" stroke-width="2"/></svg>
          Capture to Engram
        </a>
        
        <div class="steps">
          <div class="step">
            <div class="step-number">1</div>
            <div class="step-content">Drag the button above to your bookmarks bar</div>
          </div>
          <div class="step">
            <div class="step-number">2</div>
            <div class="step-content">Visit any page with technical content (docs, GitHub, Stack Overflow)</div>
          </div>
          <div class="step">
            <div class="step-number">3</div>
            <div class="step-content">Click the bookmark to capture the page content</div>
          </div>
          <div class="step">
            <div class="step-number">4</div>
            <div class="step-content">Engram will extract and analyze any decisions found</div>
          </div>
        </div>
        
        <div class="info-box">
          <strong>Note:</strong> HTTPS is required for ChatGPT, Claude.ai, and other secure sites. 
          The bookmarklet captures up to 50KB of page content.
        </div>
      </div>
    `;
  }
};
