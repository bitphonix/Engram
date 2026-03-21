/* ============================================
   ENGRAM — API Module
   All fetch calls centralized
   ============================================ */

window.API = {
  /**
   * Get graph statistics
   * @returns {Promise<{active_decisions, total_counterfactuals, total_sessions, avg_epistemic_weight}>}
   */
  getStats: () => 
    fetch('/graph/stats')
      .then(r => r.json())
      .catch(err => {
        console.error('API.getStats failed:', err);
        return { active_decisions: 0, total_counterfactuals: 0, total_sessions: 0, avg_epistemic_weight: 0 };
      }),

  /**
   * Get full network data
   * @returns {Promise<{nodes: Array, edges: Array}>}
   */
  getNetwork: () => 
    fetch('/graph/network')
      .then(r => r.json())
      .catch(err => {
        console.error('API.getNetwork failed:', err);
        return { nodes: [], edges: [] };
      }),

  /**
   * Ingest new session data
   * @param {Object} body - Session content and metadata
   * @returns {Promise<Object>}
   */
  ingest: (body) => 
    fetch('/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
      .then(r => r.json())
      .catch(err => {
        console.error('API.ingest failed:', err);
        return { error: err.message, saved_decisions: 0, saved_counterfactuals: 0 };
      }),

  /**
   * Retrieve context for a query
   * @param {Object} body - Query and filters
   * @returns {Promise<Object>}
   */
  context: (body) => 
    fetch('/context', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
      .then(r => r.json())
      .catch(err => {
        console.error('API.context failed:', err);
        return { level1_decisions: [], level4_warnings: [], briefing: '' };
      }),

  /**
   * Search decisions
   * @param {Object} body - Search query
   * @returns {Promise<Object>}
   */
  search: (body) => 
    fetch('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
      .then(r => r.json())
      .catch(err => {
        console.error('API.search failed:', err);
        return { decisions: [], warnings: [] };
      }),

  /**
   * Get single decision details
   * @param {string} id - Decision ID
   * @returns {Promise<Object>}
   */
  getDecision: (id) => 
    fetch(`/decisions/${id}`)
      .then(r => r.json())
      .catch(err => {
        console.error('API.getDecision failed:', err);
        return { decision: null, counterfactuals: [] };
      }),

  /**
   * Delete a decision
   * @param {string} id - Decision ID
   * @returns {Promise<Object>}
   */
  deleteDecision: (id) => 
    fetch(`/decisions/${id}`, { method: 'DELETE' })
      .then(r => r.json())
      .catch(err => {
        console.error('API.deleteDecision failed:', err);
        return { error: err.message };
      }),

  /**
   * Run the inference engine
   * @returns {Promise<Object>}
   */
  runEngine: () => 
    fetch('/graph/run-engine', { method: 'POST' })
      .then(r => r.json())
      .catch(err => {
        console.error('API.runEngine failed:', err);
        return { error: err.message };
      })
};
