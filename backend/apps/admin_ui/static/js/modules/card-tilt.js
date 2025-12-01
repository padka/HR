/**
 * 3D Card Tilt + Holographic Shine Effect
 * Interactive micro-animations for metric cards
 * Creates premium, high-tech feel for HR dashboard
 */

(function() {
  'use strict';

  // Configuration
  const config = {
    maxTilt: 8, // Maximum tilt angle in degrees
    perspective: 1000, // 3D perspective in pixels
    scale: 1.02, // Scale on hover
    transitionSpeed: 400, // Transition duration in ms
    easing: 'cubic-bezier(0.22, 1, 0.36, 1)', // Smooth ease-out
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches
  };

  /**
   * Initialize 3D tilt effect for a card
   * @param {HTMLElement} card - The card element to apply effect to
   */
  function initCardTilt(card) {
    // Skip if reduced motion is preferred
    if (config.reducedMotion) {
      card.style.transition = 'box-shadow 0.2s ease';
      return;
    }

    let rafId = null;
    let currentRotateX = 0;
    let currentRotateY = 0;
    let targetRotateX = 0;
    let targetRotateY = 0;

    /**
     * Calculate tilt based on mouse position
     * @param {MouseEvent} e - Mouse event
     */
    function handleMouseMove(e) {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const centerX = rect.width / 2;
      const centerY = rect.height / 2;

      // Calculate rotation angles
      targetRotateX = ((y - centerY) / centerY) * config.maxTilt;
      targetRotateY = ((centerX - x) / centerX) * config.maxTilt;

      // Start animation loop if not already running
      if (!rafId) {
        animate();
      }
    }

    /**
     * Smooth animation loop using lerp (linear interpolation)
     */
    function animate() {
      const lerpFactor = 0.15; // Smoothing factor (lower = smoother but slower)

      // Lerp towards target rotation
      currentRotateX += (targetRotateX - currentRotateX) * lerpFactor;
      currentRotateY += (targetRotateY - currentRotateY) * lerpFactor;

      // Apply transformation
      card.style.transform = `
        perspective(${config.perspective}px)
        rotateX(${currentRotateX}deg)
        rotateY(${currentRotateY}deg)
        scale3d(${config.scale}, ${config.scale}, ${config.scale})
      `;

      // Continue animation if not close enough to target
      if (
        Math.abs(targetRotateX - currentRotateX) > 0.01 ||
        Math.abs(targetRotateY - currentRotateY) > 0.01
      ) {
        rafId = requestAnimationFrame(animate);
      } else {
        rafId = null;
      }
    }

    /**
     * Reset card to neutral position
     */
    function handleMouseLeave() {
      targetRotateX = 0;
      targetRotateY = 0;

      // Cancel any ongoing animation
      if (rafId) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }

      // Smooth transition back to neutral
      card.style.transition = `transform ${config.transitionSpeed}ms ${config.easing}`;
      card.style.transform = `
        perspective(${config.perspective}px)
        rotateX(0deg)
        rotateY(0deg)
        scale3d(1, 1, 1)
      `;

      // Remove transition after animation completes
      setTimeout(() => {
        card.style.transition = '';
        currentRotateX = 0;
        currentRotateY = 0;
      }, config.transitionSpeed);
    }

    /**
     * Trigger holographic shine effect on click
     */
    function handleClick() {
      card.classList.add('metric-card--shine-active');
      setTimeout(() => {
        card.classList.remove('metric-card--shine-active');
      }, 600);
    }

    // Attach event listeners
    card.addEventListener('mousemove', handleMouseMove);
    card.addEventListener('mouseleave', handleMouseLeave);
    card.addEventListener('click', handleClick);

    // Initialize transform style
    card.style.transformStyle = 'preserve-3d';
    card.style.willChange = 'transform';

    // Cleanup function for potential future use
    return () => {
      card.removeEventListener('mousemove', handleMouseMove);
      card.removeEventListener('mouseleave', handleMouseLeave);
      card.removeEventListener('click', handleClick);
      if (rafId) cancelAnimationFrame(rafId);
    };
  }

  /**
   * Initialize effect for all metric cards
   */
  function init() {
    const cards = document.querySelectorAll('.metric-card[data-tilt]');

    if (cards.length === 0) {
      console.warn('No .metric-card elements found for tilt effect');
      return;
    }

    console.log(`Initializing 3D tilt effect for ${cards.length} card(s)`);

    cards.forEach(card => {
      initCardTilt(card);
    });

    // Add accessibility: keyboard focus should also trigger effect
    cards.forEach(card => {
      card.addEventListener('focus', () => {
        if (!config.reducedMotion) {
          card.style.transform = `
            perspective(${config.perspective}px)
            scale3d(${config.scale}, ${config.scale}, ${config.scale})
          `;
        }
      });

      card.addEventListener('blur', () => {
        card.style.transform = '';
      });
    });
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Handle dynamic card additions (if needed in future)
  window.addEventListener('load', () => {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
          if (node.nodeType === 1 && node.matches('.metric-card[data-tilt]')) {
            initCardTilt(node);
          }
        });
      });
    });

    // Observe only the dashboard-metrics section
    const metricsSection = document.querySelector('.dashboard-metrics');
    if (metricsSection) {
      observer.observe(metricsSection, {
        childList: true,
        subtree: true
      });
    }
  });

})();
