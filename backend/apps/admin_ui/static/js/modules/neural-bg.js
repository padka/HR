/**
 * Neural Network Background Effect
 * Creates animated AI-themed background with nodes and connections
 * Symbolizes intelligent recruitment automation
 */

(function() {
  'use strict';

  const svg = document.getElementById('neuralNetwork');
  if (!svg) {
    console.warn('Neural network SVG container not found');
    return;
  }

  const nodesGroup = svg.getElementById('nodes');
  const connectionsGroup = svg.getElementById('connections');

  // Configuration
  const config = {
    numNodes: 18,
    connectionDistance: 220,
    nodeMinRadius: 2,
    nodeMaxRadius: 5,
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches
  };

  const nodes = [];

  /**
   * Initialize SVG viewBox
   */
  function initSVG() {
    svg.setAttribute('viewBox', `0 0 ${window.innerWidth} ${window.innerHeight}`);
    svg.setAttribute('width', window.innerWidth);
    svg.setAttribute('height', window.innerHeight);
  }

  /**
   * Generate random node positions
   */
  function generateNodes() {
    for (let i = 0; i < config.numNodes; i++) {
      const x = Math.random() * window.innerWidth;
      const y = Math.random() * window.innerHeight;
      const radius = Math.random() * (config.nodeMaxRadius - config.nodeMinRadius) + config.nodeMinRadius;

      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', x);
      circle.setAttribute('cy', y);
      circle.setAttribute('r', radius);
      circle.classList.add('neural-node');
      circle.style.setProperty('--idx', i);

      nodesGroup.appendChild(circle);
      nodes.push({ x, y, element: circle });
    }
  }

  /**
   * Connect nearby nodes with lines
   */
  function connectNodes() {
    nodes.forEach((node, i) => {
      nodes.forEach((otherNode, j) => {
        if (i >= j) return;

        const dx = node.x - otherNode.x;
        const dy = node.y - otherNode.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < config.connectionDistance) {
          const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
          line.setAttribute('x1', node.x);
          line.setAttribute('y1', node.y);
          line.setAttribute('x2', otherNode.x);
          line.setAttribute('y2', otherNode.y);
          line.classList.add('neural-connection');
          line.style.setProperty('--idx', i + j);

          // Calculate line length for dash animation
          const lineLength = Math.ceil(dist);
          line.style.setProperty('--line-length', lineLength);
          line.setAttribute('stroke-dasharray', lineLength);
          line.setAttribute('stroke-dashoffset', lineLength);

          connectionsGroup.appendChild(line);
        }
      });
    });
  }

  /**
   * Handle window resize
   */
  function handleResize() {
    // Clear existing nodes and connections
    nodesGroup.innerHTML = '';
    connectionsGroup.innerHTML = '';
    nodes.length = 0;

    // Reinitialize
    initSVG();
    generateNodes();
    connectNodes();
  }

  /**
   * Add interaction: enhance glow on metric card hover
   */
  function addInteractions() {
    const metricCards = document.querySelectorAll('.metric-card');
    const dashboardHero = document.querySelector('.dashboard-hero');

    const elements = [...metricCards];
    if (dashboardHero) elements.push(dashboardHero);

    elements.forEach(element => {
      element.addEventListener('mouseenter', () => {
        svg.classList.add('neural-bg--enhanced');
      });

      element.addEventListener('mouseleave', () => {
        svg.classList.remove('neural-bg--enhanced');
      });
    });
  }

  /**
   * Initialize the neural network effect
   */
  function init() {
    // Skip animations if reduced motion is preferred
    if (config.reducedMotion) {
      svg.style.opacity = '0.15';
      svg.style.animation = 'none';
    }

    initSVG();
    generateNodes();
    connectNodes();
    addInteractions();

    // Throttled resize handler
    let resizeTimeout;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(handleResize, 250);
    });
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
