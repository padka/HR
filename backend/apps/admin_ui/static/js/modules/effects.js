const reduceMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
let prefersReducedMotion = reduceMotionQuery.matches;

const hoverRegistry = new WeakSet();
const rippleRegistry = new WeakSet();
const tiltRegistry = new WeakMap();

function parseEffects(el) {
  return (el.dataset.effects || '')
    .split(/\s+/)
    .map(effect => effect.trim())
    .filter(Boolean);
}

function attachHoverState(el) {
  if (hoverRegistry.has(el)) {
    return;
  }
  const activate = () => el.classList.add('is-hovered');
  const deactivate = () => el.classList.remove('is-hovered');
  el.addEventListener('pointerenter', activate);
  el.addEventListener('pointerleave', deactivate);
  el.addEventListener('focus', activate);
  el.addEventListener('blur', deactivate);
  hoverRegistry.add(el);
}

function attachRippleEffect(el) {
  if (prefersReducedMotion || rippleRegistry.has(el)) {
    return;
  }
  const onClick = (event) => {
    const rect = el.getBoundingClientRect();
    const diameter = Math.max(rect.width, rect.height);
    const ripple = document.createElement('span');
    ripple.className = 'surface__ripple';
    ripple.style.position = 'absolute';
    ripple.style.width = ripple.style.height = `${diameter}px`;
    ripple.style.left = `${event.clientX - rect.left - diameter / 2}px`;
    ripple.style.top = `${event.clientY - rect.top - diameter / 2}px`;
    ripple.style.borderRadius = '50%';
    ripple.style.background = 'radial-gradient(circle, rgba(255,255,255,.30) 0%, rgba(255,255,255,0) 60%)';
    ripple.style.transform = 'scale(0)';
    ripple.style.opacity = '0.7';
    ripple.style.pointerEvents = 'none';
    ripple.style.transition = 'transform .45s ease, opacity .6s ease';
    el.appendChild(ripple);
    requestAnimationFrame(() => {
      ripple.style.transform = 'scale(1)';
      ripple.style.opacity = '0';
    });
    window.setTimeout(() => ripple.remove(), 620);
  };

  const computed = window.getComputedStyle(el);
  if (computed.position === 'static') {
    el.style.position = 'relative';
  }
  if (computed.overflow === 'visible') {
    el.style.overflow = 'hidden';
  }

  el.addEventListener('click', onClick);
  rippleRegistry.add(el);
}

function scheduleTilt(el, state) {
  state.frame = window.requestAnimationFrame(() => {
    state.currentX += (state.targetX - state.currentX) * state.ease;
    state.currentY += (state.targetY - state.currentY) * state.ease;
    const transform = `perspective(${state.perspective}px) rotateX(${state.currentX}deg) rotateY(${state.currentY}deg)`;
    el.style.transform = transform;
    if (Math.abs(state.currentX - state.targetX) > 0.01 || Math.abs(state.currentY - state.targetY) > 0.01) {
      scheduleTilt(el, state);
    } else {
      window.cancelAnimationFrame(state.frame);
      state.frame = null;
    }
  });
}

function attachTiltEffect(el) {
  if (prefersReducedMotion || tiltRegistry.has(el)) {
    return;
  }
  const state = {
    frame: null,
    targetX: 0,
    targetY: 0,
    currentX: 0,
    currentY: 0,
    ease: parseFloat(el.dataset.tiltEase || '0.12'),
    max: parseFloat(el.dataset.tiltMax || '2.4'),
    perspective: parseFloat(el.dataset.tiltPerspective || '900')
  };

  const onPointerMove = (event) => {
    const rect = el.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    state.targetX = (0.5 - y) * state.max;
    state.targetY = (x - 0.5) * state.max;
    if (!state.frame) {
      scheduleTilt(el, state);
    }
  };

  const onLeave = () => {
    state.targetX = 0;
    state.targetY = 0;
    if (!state.frame) {
      scheduleTilt(el, state);
    }
  };

  const passiveOptions = { passive: true };
  let usedPassive = false;
  try {
    el.addEventListener('pointermove', onPointerMove, passiveOptions);
    usedPassive = true;
  } catch (err) {
    el.addEventListener('pointermove', onPointerMove);
  }
  el.addEventListener('pointerleave', onLeave);
  el.addEventListener('pointercancel', onLeave);
  el.addEventListener('blur', onLeave);
  el.addEventListener('focusout', onLeave);

  state.cleanup = () => {
    if (state.frame) {
      window.cancelAnimationFrame(state.frame);
      state.frame = null;
    }
    el.style.transform = '';
    if (usedPassive) {
      el.removeEventListener('pointermove', onPointerMove, passiveOptions);
    } else {
      el.removeEventListener('pointermove', onPointerMove);
    }
    el.removeEventListener('pointerleave', onLeave);
    el.removeEventListener('pointercancel', onLeave);
    el.removeEventListener('blur', onLeave);
    el.removeEventListener('focusout', onLeave);
    tiltRegistry.delete(el);
  };

  tiltRegistry.set(el, state);
}

function disableTilt(el) {
  const state = tiltRegistry.get(el);
  if (!state) {
    return;
  }
  if (state.cleanup) {
    state.cleanup();
  } else {
    el.style.transform = '';
    tiltRegistry.delete(el);
  }
}

function initInteractiveEffects(root = document) {
  const nodes = Array.from(root.querySelectorAll('[data-effects]'));

  nodes.forEach((el) => {
    const effects = parseEffects(el);
    if (effects.includes('hover')) {
      attachHoverState(el);
    }
    if (effects.includes('tilt')) {
      attachTiltEffect(el);
    }
    if (effects.includes('ripple')) {
      attachRippleEffect(el);
    }
  });

  if (!prefersReducedMotion) {
    const rippleTargets = Array.from(root.querySelectorAll('button, .btn'));
    rippleTargets.forEach(attachRippleEffect);
  } else {
    nodes
      .filter(el => parseEffects(el).includes('tilt'))
      .forEach(disableTilt);
  }
}

function autoInit() {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initInteractiveEffects());
  } else {
    initInteractiveEffects();
  }
}

autoInit();

if (typeof reduceMotionQuery.addEventListener === 'function') {
  reduceMotionQuery.addEventListener('change', (event) => {
    prefersReducedMotion = event.matches;
    if (prefersReducedMotion) {
      document.querySelectorAll('[data-effects~="tilt"]').forEach(disableTilt);
    } else {
      initInteractiveEffects();
    }
  });
}

window.DashboardEffects = Object.assign({}, window.DashboardEffects, {
  init: initInteractiveEffects,
  refresh: initInteractiveEffects
});

export { initInteractiveEffects };
