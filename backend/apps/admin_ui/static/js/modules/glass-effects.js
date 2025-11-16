/**
 * Liquid Glass Effects Module
 * Adds interactive micro-animations and effects to liquid glass components
 */
(function() {
  'use strict';

  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /**
   * Add parallax tilt effect to glass cards on hover
   */
  function initCardParallax() {
    if (prefersReducedMotion) return;

    const cards = document.querySelectorAll('.liquid-glass-card--interactive, .liquid-glass-card[data-parallax]');

    cards.forEach(card => {
      let frame = null;
      let currentX = 0;
      let currentY = 0;
      let targetX = 0;
      let targetY = 0;
      const ease = 0.10;
      const maxTilt = 3; // degrees

      const handleMouseMove = (e) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const centerX = rect.width / 2;
        const centerY = rect.height / 2;

        // Calculate rotation based on mouse position
        targetX = ((y - centerY) / centerY) * maxTilt;
        targetY = ((centerX - x) / centerX) * maxTilt;

        if (!frame) {
          animate();
        }
      };

      const handleMouseLeave = () => {
        targetX = 0;
        targetY = 0;
        if (!frame) {
          animate();
        }
      };

      function animate() {
        // Smoothly interpolate to target rotation
        currentX += (targetX - currentX) * ease;
        currentY += (targetY - currentY) * ease;

        card.style.transform = `perspective(1000px) rotateX(${currentX}deg) rotateY(${currentY}deg) translateZ(10px)`;

        // Continue animation if not close enough to target
        if (Math.abs(currentX - targetX) > 0.01 || Math.abs(currentY - targetY) > 0.01) {
          frame = requestAnimationFrame(animate);
        } else {
          // Reset to target and stop animation
          currentX = targetX;
          currentY = targetY;
          if (targetX === 0 && targetY === 0) {
            card.style.transform = '';
          }
          frame = null;
        }
      }

      card.addEventListener('mousemove', handleMouseMove);
      card.addEventListener('mouseleave', handleMouseLeave);

      // Store cleanup function
      card._parallaxCleanup = () => {
        if (frame) {
          cancelAnimationFrame(frame);
        }
        card.removeEventListener('mousemove', handleMouseMove);
        card.removeEventListener('mouseleave', handleMouseLeave);
        card.style.transform = '';
      };
    });
  }

  /**
   * Add ripple effect to buttons on click
   */
  function initButtonRipple() {
    if (prefersReducedMotion) return;

    const buttons = document.querySelectorAll('.liquid-glass-btn, .btn, button');

    buttons.forEach(button => {
      const handleClick = (e) => {
        // Create ripple element
        const ripple = document.createElement('span');
        const rect = button.getBoundingClientRect();

        // Calculate ripple size and position
        const size = Math.max(rect.width, rect.height);
        const x = e.clientX - rect.left - size / 2;
        const y = e.clientY - rect.top - size / 2;

        ripple.style.width = ripple.style.height = size + 'px';
        ripple.style.left = x + 'px';
        ripple.style.top = y + 'px';
        ripple.classList.add('ripple');

        // Ensure button has position relative
        const position = window.getComputedStyle(button).position;
        if (position === 'static') {
          button.style.position = 'relative';
        }

        // Ensure overflow hidden
        button.style.overflow = 'hidden';

        // Add ripple to button
        button.appendChild(ripple);

        // Remove ripple after animation
        setTimeout(() => {
          if (ripple.parentNode === button) {
            ripple.remove();
          }
        }, 650);
      };

      button.addEventListener('click', handleClick);

      // Store cleanup function
      button._rippleCleanup = () => {
        button.removeEventListener('click', handleClick);
        // Remove any lingering ripples
        button.querySelectorAll('.ripple').forEach(r => r.remove());
      };
    });
  }

  /**
   * Add subtle floating animation to specific elements
   */
  function initFloatingElements() {
    if (prefersReducedMotion) return;

    const elements = document.querySelectorAll('[data-float]');

    elements.forEach((el, index) => {
      // Add slight delay to each element for staggered effect
      const delay = index * 0.3;
      el.style.animationDelay = `${delay}s`;
      el.classList.add('liquid-float');
    });
  }

  /**
   * Add glow pulse effect to highlighted elements
   */
  function initGlowPulse() {
    if (prefersReducedMotion) return;

    const elements = document.querySelectorAll('[data-glow-pulse]');

    elements.forEach((el, index) => {
      // Add slight delay to each element
      const delay = index * 0.5;
      el.style.animationDelay = `${delay}s`;
      el.classList.add('liquid-glow-pulse');
    });
  }

  /**
   * Add smooth scroll with easing for anchor links
   */
  function initSmoothScroll() {
    const links = document.querySelectorAll('a[href^="#"]');

    links.forEach(link => {
      link.addEventListener('click', (e) => {
        const href = link.getAttribute('href');
        if (href === '#' || href === '#!') return;

        const target = document.querySelector(href);
        if (!target) return;

        e.preventDefault();

        const offset = 80; // Offset for fixed headers
        const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - offset;

        window.scrollTo({
          top: targetPosition,
          behavior: 'smooth'
        });
      });
    });
  }

  /**
   * Add entrance animations to elements when they come into view
   */
  function initIntersectionObserver() {
    if (prefersReducedMotion) return;
    if (!('IntersectionObserver' in window)) return;

    const elements = document.querySelectorAll('[data-animate-in]');

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    });

    elements.forEach(el => {
      el.style.opacity = '0';
      el.style.transform = 'translateY(20px)';
      el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';

      el.addEventListener('transitionend', function handler() {
        if (el.classList.contains('is-visible')) {
          el.style.opacity = '';
          el.style.transform = '';
          el.style.transition = '';
          el.removeEventListener('transitionend', handler);
        }
      });

      observer.observe(el);
    });

    // Apply visible class immediately for elements already in view
    elements.forEach(el => {
      const rect = el.getBoundingClientRect();
      if (rect.top < window.innerHeight && rect.bottom > 0) {
        el.classList.add('is-visible');
        el.style.opacity = '1';
        el.style.transform = 'translateY(0)';
      }
    });
  }

  /**
   * Add interactive hover effect to table rows
   */
  function initTableRowEffects() {
    const tables = document.querySelectorAll('.liquid-glass-table table, table.list-table');

    tables.forEach(table => {
      const rows = table.querySelectorAll('tbody tr');

      rows.forEach(row => {
        // Skip if row already has hover handler
        if (row._hoverHandlerAdded) return;

        const handleMouseEnter = () => {
          row.style.transform = 'translateX(4px)';
        };

        const handleMouseLeave = () => {
          row.style.transform = '';
        };

        row.addEventListener('mouseenter', handleMouseEnter);
        row.addEventListener('mouseleave', handleMouseLeave);

        row._hoverHandlerAdded = true;
        row._hoverCleanup = () => {
          row.removeEventListener('mouseenter', handleMouseEnter);
          row.removeEventListener('mouseleave', handleMouseLeave);
          row.style.transform = '';
        };
      });
    });
  }

  /**
   * Cleanup function to remove all effects
   */
  function cleanup() {
    // Cleanup parallax cards
    document.querySelectorAll('.liquid-glass-card').forEach(card => {
      if (card._parallaxCleanup) {
        card._parallaxCleanup();
        delete card._parallaxCleanup;
      }
    });

    // Cleanup ripple buttons
    document.querySelectorAll('button, .btn, .liquid-glass-btn').forEach(button => {
      if (button._rippleCleanup) {
        button._rippleCleanup();
        delete button._rippleCleanup;
      }
    });

    // Cleanup table rows
    document.querySelectorAll('tbody tr').forEach(row => {
      if (row._hoverCleanup) {
        row._hoverCleanup();
        delete row._hoverCleanup;
        delete row._hoverHandlerAdded;
      }
    });

    // Remove animation classes
    document.querySelectorAll('.liquid-float, .liquid-glow-pulse').forEach(el => {
      el.classList.remove('liquid-float', 'liquid-glow-pulse');
      el.style.animationDelay = '';
    });
  }

  /**
   * Initialize all effects
   */
  function init() {
    // Only run if document is ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
      return;
    }

    console.log('[Liquid Glass] Initializing effects...');

    initCardParallax();
    initButtonRipple();
    initFloatingElements();
    initGlowPulse();
    initSmoothScroll();
    initIntersectionObserver();
    initTableRowEffects();

    console.log('[Liquid Glass] Effects initialized');
  }

  /**
   * Re-initialize effects on dynamic content
   */
  function refresh() {
    console.log('[Liquid Glass] Refreshing effects...');
    initCardParallax();
    initButtonRipple();
    initTableRowEffects();
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Export to window for manual control
  window.LiquidGlass = {
    init,
    refresh,
    cleanup
  };
})();
