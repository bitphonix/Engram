/* ============================================
   ENGRAM — Graph Visualization
   D3 v7 force layout with nodes, edges, interactions
   ============================================ */

window.Graph = {
  svg: null,
  g: null,
  simulation: null,
  nodes: [],
  edges: [],
  width: 0,
  height: 0,
  currentFilter: 'all',
  
  // Domain color mapping
  domainColors: {
    database: 'var(--domain-database)',
    architecture: 'var(--domain-architecture)',
    authentication: 'var(--domain-authentication)',
    infrastructure: 'var(--domain-infrastructure)',
    deployment: 'var(--domain-deployment)',
    framework: 'var(--domain-framework)',
    'api-design': 'var(--domain-api-design)',
    other: 'var(--domain-other)'
  },

  /**
   * Initialize the graph
   */
  init() {
    this.svg = d3.select('#graph-svg');
    this.g = this.svg.append('g');
    
    // Define arrow markers
    const defs = this.svg.append('defs');
    
    ['caused-by', 'supersedes', 'similar-to'].forEach(type => {
      defs.append('marker')
        .attr('id', `arrow-${type}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', type === 'caused-by' ? 'var(--edge-caused)' : 
                      type === 'supersedes' ? 'var(--edge-supersedes)' : 'var(--edge-similar)');
    });
    
    // Zoom behavior
    const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (e) => this.g.attr('transform', e.transform));
    
    this.svg.call(zoom);
    
    this.resize();
    window.addEventListener('resize', () => this.resize());
  },

  /**
   * Handle resize
   */
  resize() {
    const parent = this.svg.node().parentElement;
    this.width = parent.clientWidth;
    this.height = parent.clientHeight;
    this.svg.attr('viewBox', [0, 0, this.width, this.height]);
  },

  /**
   * Render the network
   */
  render(data) {
    this.nodes = data.nodes || [];
    this.edges = data.edges || [];
    
    // Clear existing
    this.g.selectAll('*').remove();
    
    // Create simulation
    this.simulation = d3.forceSimulation(this.nodes)
      .force('link', d3.forceLink(this.edges)
        .id(d => d.id)
        .distance(d => d.type === 'CAUSED_BY' ? 100 : 150))
      .force('charge', d3.forceManyBody().strength(-250))
      .force('center', d3.forceCenter(this.width / 2, this.height / 2))
      .force('collision', d3.forceCollide().radius(d => 20 + d.weight * 15));
    
    // Draw edges
    const link = this.g.append('g')
      .selectAll('line')
      .data(this.edges)
      .join('line')
      .attr('class', d => `graph-edge ${d.type.toLowerCase().replace('_', '-')}`)
      .attr('marker-end', d => `url(#arrow-${d.type.toLowerCase().replace('_', '-')})`);
    
    // Draw nodes
    const node = this.g.append('g')
      .selectAll('g')
      .data(this.nodes)
      .join('g')
      .attr('class', d => `graph-node ${d.is_invalidated ? 'invalidated' : ''}`)
      .attr('data-domain', d => d.domain)
      .style('color', d => this.domainColors[d.domain] || this.domainColors.other)
      .style('--node-radius', d => 8 + (d.weight || 0) * 12)
      .call(d3.drag()
        .on('start', (e, d) => this.dragstarted(e, d))
        .on('drag', (e, d) => this.dragged(e, d))
        .on('end', (e, d) => this.dragended(e, d)));
    
    // Node glow (outer)
    node.append('circle')
      .attr('class', 'node-glow-outer')
      .attr('r', d => (8 + (d.weight || 0) * 12) * 2);
    
    // Node glow (inner)
    node.append('circle')
      .attr('class', 'node-glow-inner')
      .attr('r', d => (8 + (d.weight || 0) * 12) * 1.4);
    
    // Node core
    node.append('circle')
      .attr('class', 'node-core')
      .attr('r', d => 8 + (d.weight || 0) * 12);
    
    // Node labels
    node.append('text')
      .attr('class', 'node-label')
      .attr('dy', d => 24 + (d.weight || 0) * 12)
      .text(d => d.chosen?.substring(0, 25) || d.summary?.substring(0, 25));
    
    // Interactions
    node
      .on('mouseenter', (e, d) => this.onNodeHover(e, d, node, link))
      .on('mouseleave', () => this.onNodeLeave(node, link))
      .on('click', (e, d) => {
        e.stopPropagation();
        window.Panels.open('node', d);
      });
    
    // Double-click to release fixed position
    node.on('dblclick', (e, d) => {
      d.fx = null;
      d.fy = null;
      this.simulation.alpha(0.3).restart();
    });
    
    // Update positions on tick
    this.simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);
      
      node.attr('transform', d => `translate(${d.x},${d.y})`);
    });
    
    // Fit view after settling
    setTimeout(() => this.fitView(), 1500);
  },

  /**
   * Drag handlers
   */
  dragstarted(e, d) {
    if (!e.active) this.simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
  },

  dragged(e, d) {
    d.fx = e.x;
    d.fy = e.y;
  },

  dragended(e, d) {
    if (!e.active) this.simulation.alphaTarget(0);
  },

  /**
   * Node hover - highlight neighbors
   */
  onNodeHover(e, d, nodes, links) {
    const connectedIds = new Set();
    connectedIds.add(d.id);
    
    this.edges.forEach(edge => {
      if (edge.source.id === d.id) connectedIds.add(edge.target.id);
      if (edge.target.id === d.id) connectedIds.add(edge.source.id);
    });
    
    nodes.classed('dimmed', n => !connectedIds.has(n.id));
    nodes.classed('highlighted', n => connectedIds.has(n.id));
    
    // Show tooltip
    const tooltip = document.getElementById('tooltip');
    tooltip.innerHTML = `
      <div class="tooltip-title">${d.summary?.substring(0, 50)}...</div>
      <div class="tooltip-meta">${d.domain} | ${d.project_id} | weight: ${d.weight.toFixed(3)}</div>
    `;
    tooltip.classList.add('visible');
    tooltip.style.left = (e.clientX + 12) + 'px';
    tooltip.style.top = (e.clientY + 12) + 'px';
  },

  /**
   * Node leave - reset
   */
  onNodeLeave(nodes, links) {
    nodes.classed('dimmed', false).classed('highlighted', false);
    document.getElementById('tooltip').classList.remove('visible');
  },

  /**
   * Filter by domain
   */
  filter(domain) {
    this.currentFilter = domain;
    const nodes = this.g.selectAll('.graph-node');
    
    if (domain === 'all') {
      nodes.transition().duration(600).style('opacity', 1);
    } else {
      nodes.transition().duration(600)
        .style('opacity', d => d.domain === domain ? 1 : 0.15);
    }
  },

  /**
   * Highlight a specific node
   */
  highlightNode(id) {
    const node = this.g.selectAll('.graph-node')
      .filter(d => d.id === id);
    
    node.classed('highlighted', true);
    
    // Center on node
    const d = node.datum();
    if (d) {
      this.svg.transition().duration(750)
        .call(d3.zoom().transform, d3.zoomIdentity
          .translate(this.width / 2, this.height / 2)
          .scale(1.5)
          .translate(-d.x, -d.y));
    }
    
    setTimeout(() => node.classed('highlighted', false), 2000);
  },

  /**
   * Fit graph to view
   */
  fitView() {
    if (!this.nodes.length) return;
    
    const bounds = this.g.node().getBBox();
    const fullWidth = this.width;
    const fullHeight = this.height;
    const width = bounds.width;
    const height = bounds.height;
    const midX = bounds.x + width / 2;
    const midY = bounds.y + height / 2;
    
    if (width === 0 || height === 0) return;
    
    const scale = Math.min(fullWidth / width, fullHeight / height) * 0.85;
    const translate = [fullWidth / 2 - scale * midX, fullHeight / 2 - scale * midY];
    
    this.svg.transition().duration(750)
      .call(d3.zoom().transform, d3.zoomIdentity
        .translate(translate[0], translate[1])
        .scale(scale));
  },

  /**
   * Reload graph data
   */
  reload() {
    window.API.getNetwork().then(data => this.render(data));
  }
};
