/**
 * Animated Counter with Number Morphing & Sparkles
 * Creates "growing" numbers effect from 0 to target value
 * Symbolizes dynamic metrics and real-time data updates
 */

(function() {
  'use strict';

  // Configuration
  const config = {
    duration: 1500,        // Animation duration in ms
    easing: 'easeOutCubic', // Easing function name
    startDelay: 100,       // Delay before starting animation
    sparklesCount: 8,      // Number of sparkles on completion
    sparklesDuration: 800, // Sparkles animation duration
    observerThreshold: 0.5, // IntersectionObserver threshold
    replayOnScroll: false, // Replay animation on scroll back
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches
  };

  // Easing functions
  const easings = {
    linear: t => t,
    easeInQuad: t => t * t,
    easeOutQuad: t => t * (2 - t),
    easeInOutQuad: t => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t,
    easeInCubic: t => t * t * t,
    easeOutCubic: t => (--t) * t * t + 1,
    easeInOutCubic: t => t < 0.5 ? 4 * t * t * t : (t - 1) * (2 * t - 2) * (2 * t - 2) + 1,
    easeOutElastic: t => {
      const p = 0.3;
      return Math.pow(2, -10 * t) * Math.sin((t - p / 4) * (2 * Math.PI) / p) + 1;
    }
  };

  /**
   * Animate number from start to end
   * @param {HTMLElement} element - The element containing the number
   * @param {number} start - Starting value
   * @param {number} end - Target value
   * @param {number} duration - Animation duration in ms
   * @param {Function} callback - Callback on completion
   */
  function animateValue(element, start, end, duration, callback) {
    if (config.reducedMotion) {
      element.textContent = end;
      if (callback) callback();
      return;
    }

    const startTime = performance.now();
    const easingFunc = easings[config.easing] || easings.easeOutCubic;
    let rafId;

    function updateValue(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easedProgress = easingFunc(progress);
      const currentValue = Math.floor(start + (end - start) * easedProgress);

      element.textContent = currentValue;

      if (progress < 1) {
        rafId = requestAnimationFrame(updateValue);
      } else {
        element.textContent = end;
        if (callback) callback();
      }
    }

    rafId = requestAnimationFrame(updateValue);

    // Return cleanup function
    return () => {
      if (rafId) cancelAnimationFrame(rafId);
    };
  }

  /**
   * Create sparkle element
   * @param {number} x - X position
   * @param {number} y - Y position
   * @param {number} angle - Direction angle
   * @param {number} distance - Travel distance
   * @returns {HTMLElement}
   */
  function createSparkle(x, y, angle, distance) {
    const sparkle = document.createElement('div');
    sparkle.className = 'counter-sparkle';

    const tx = Math.cos(angle) * distance;
    const ty = Math.sin(angle) * distance;

    sparkle.style.cssText = `
      position: absolute;
      left: ${x}px;
      top: ${y}px;
      width: ${Math.random() * 4 + 3}px;
      height: ${Math.random() * 4 + 3}px;
      background: var(--accent);
      border-radius: 50%;
      pointer-events: none;
      --tx: ${tx}px;
      --ty: ${ty}px;
      animation: sparkleFloat ${config.sparklesDuration}ms ease-out forwards;
      box-shadow: 0 0 8px var(--accent);
      z-index: 100;
    `;

    return sparkle;
  }

  /**
   * Spawn sparkles around element
   * @param {HTMLElement} element - The element to spawn sparkles around
   */
  function spawnSparkles(element) {
    if (config.reducedMotion) return;

    const rect = element.getBoundingClientRect();
    const container = element.closest('.metric-card') || element.parentElement;

    if (!container) return;

    // Make container position relative if not already
    const position = getComputedStyle(container).position;
    if (position === 'static') {
      container.style.position = 'relative';
    }

    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    const baseDistance = 40;
    const distanceVariation = 20;

    for (let i = 0; i < config.sparklesCount; i++) {
      const angle = (Math.PI * 2 * i) / config.sparklesCount;
      const distance = baseDistance + Math.random() * distanceVariation;

      const sparkle = createSparkle(centerX, centerY, angle, distance);
      container.appendChild(sparkle);

      // Remove sparkle after animation
      setTimeout(() => {
        sparkle.remove();
      }, config.sparklesDuration);
    }

    // Add pulsing effect to value
    element.style.animation = 'counterPulse 0.3s ease-out';
    setTimeout(() => {
      element.style.animation = '';
    }, 300);
  }

  /**
   * Initialize counter animation for a value element
   * @param {HTMLElement} valueElement - The element containing the number
   */
  function initCounter(valueElement) {
    // Get target value
    const targetValue = parseInt(valueElement.getAttribute('data-count-value') || valueElement.textContent);

    if (isNaN(targetValue)) {
      console.warn('Counter: Invalid target value', valueElement);
      return;
    }

    // Store original value
    valueElement.setAttribute('data-count-value', targetValue);

    // Set to 0 initially (will be animated)
    if (!config.reducedMotion) {
      valueElement.textContent = '0';
    }

    // Create IntersectionObserver
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            // Start animation after delay
            setTimeout(() => {
              animateValue(valueElement, 0, targetValue, config.duration, () => {
                // Spawn sparkles on completion
                spawnSparkles(valueElement);
              });
            }, config.startDelay);

            // Unobserve if we don't want replay
            if (!config.replayOnScroll) {
              observer.unobserve(entry.target);
            }
          } else if (config.replayOnScroll) {
            // Reset to 0 when scrolled out
            valueElement.textContent = '0';
          }
        });
      },
      {
        threshold: config.observerThreshold,
        rootMargin: '0px'
      }
    );

    observer.observe(valueElement);

    // Store cleanup function
    valueElement._counterCleanup = () => {
      observer.disconnect();
    };
  }

  /**
   * Initialize all counters on the page
   */
  function init() {
    // Find all metric card values
    const valueElements = document.querySelectorAll('.metric-card__value');

    if (valueElements.length === 0) {
      console.warn('Animated Counter: No .metric-card__value elements found');
      return;
    }

    console.log(`Initializing animated counters for ${valueElements.length} element(s)`);

    valueElements.forEach(element => {
      initCounter(element);
    });

    // Add stagger delay for multiple counters
    if (valueElements.length > 1 && !config.reducedMotion) {
      valueElements.forEach((element, index) => {
        const observer = element._counterObserver;
        // Add progressive delay
        const staggerDelay = index * 150; // 150ms between each
        element.style.setProperty('--counter-delay', `${staggerDelay}ms`);
      });
    }
  }

  /**
   * Manual trigger for counter animation (for testing or dynamic content)
   * @param {HTMLElement} element - The value element to animate
   */
  window.triggerCounterAnimation = function(element) {
    const targetValue = parseInt(element.getAttribute('data-count-value') || element.textContent);
    if (!isNaN(targetValue)) {
      animateValue(element, 0, targetValue, config.duration, () => {
        spawnSparkles(element);
      });
    }
  };

  /**
   * Update counter configuration
   * @param {Object} newConfig - Configuration options to update
   */
  window.updateCounterConfig = function(newConfig) {
    Object.assign(config, newConfig);
  };

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Handle dynamic content additions
  const observer = new MutationObserver((mutations) => {
    mutations.forEach(mutation => {
      mutation.addedNodes.forEach(node => {
        if (node.nodeType === 1) {
          // Check if added node is a metric card
          if (node.classList && node.classList.contains('metric-card')) {
            const valueElement = node.querySelector('.metric-card__value');
            if (valueElement) {
              initCounter(valueElement);
            }
          }
          // Check if added node contains metric cards
          const valueElements = node.querySelectorAll && node.querySelectorAll('.metric-card__value');
          if (valueElements && valueElements.length > 0) {
            valueElements.forEach(initCounter);
          }
        }
      });
    });
  });

  // Observe dashboard metrics section
  window.addEventListener('load', () => {
    const metricsSection = document.querySelector('.dashboard-metrics');
    if (metricsSection) {
      observer.observe(metricsSection, {
        childList: true,
        subtree: true
      });
    }
  });

})();
