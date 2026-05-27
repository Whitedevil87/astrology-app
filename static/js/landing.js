/* ═══════════════════════════════════════════════════════════
   CELESTIAL ARC — Scroll-Driven Cinematic Engine v2
   
   Core: 288-frame image sequence controlled by scroll position.
   Architecture: position:sticky viewport inside tall scroll container.
   Rendering: High-DPR canvas with cover-fit and smooth interpolation.
   
   Scroll Architecture:
   ┌──────────────────────────────────────────────────┐
   │ .cinematic-scroll  (500vh tall)                  │
   │   ┌────────────────────────────────────────────┐ │
   │   │ .cinematic-sticky (100vh, position:sticky) │ │  ← pinned
   │   │   canvas + overlay + story-panels          │ │
   │   └────────────────────────────────────────────┘ │
   │   (remaining 400vh is invisible scroll runway)   │
   └──────────────────────────────────────────────────┘
   │ .cta-section (flows normally after scroll ends)  │
   
   Scroll height is set in CSS (--cinematic-scroll-height). Progress 0→1
   maps frames 1→288. Panels use wide overlap so copy stays readable longer.
   ═══════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  const isMobile = window.matchMedia('(max-width: 768px)').matches;
  const isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const isLowPower = isMobile || isReducedMotion;

  // ── CONFIGURATION ──────────────────────────────────────
  const CONFIG = {
    totalFrames: 288,
    frameStep: isMobile ? 2 : 1,
    frameBasePath: '/static/images/celestial-sequence-288/frame_',
    frameExtension: '.webp',

    // Story panel scroll ranges — wide overlap, long hold in the middle
    panels: {
      hero:         { start: -0.05, end: 0.34, overlay: 'overlay-hero' },
      engine:       { start: 0.26, end: 0.58, overlay: 'overlay-engine' },
      intelligence: { start: 0.50, end: 0.82, overlay: 'overlay-intelligence' },
      activation:   { start: 0.74, end: 1.06, overlay: 'overlay-activation' },
    },

    panelFadeZone: 0.09,

    preloadBatchSize: isMobile ? 6 : 12,
    preloadInterval: isMobile ? 50 : 20,

    navScrollThreshold: 40,
    particleCount: isMobile ? 0 : 18,
    particleMaxSize: 1.2,
    particleMinSize: 0.3,

    maxDpr: isMobile ? 1.25 : 2,
    enableParticles: !isLowPower,
    smoothingQuality: isMobile ? 'medium' : 'high',
  };

  // ── UTILITIES ──────────────────────────────────────────
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];
  const raf = requestAnimationFrame.bind(window);
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function clamp(val, min, max) {
    return Math.max(min, Math.min(max, val));
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  // Smooth-step for panel opacity transitions
  function smoothstep(edge0, edge1, x) {
    const t = clamp((x - edge0) / (edge1 - edge0), 0, 1);
    return t * t * (3 - 2 * t);
  }

  function padFrame(n) {
    return String(n).padStart(4, '0');
  }

  function framePath(idx) {
    return CONFIG.frameBasePath + padFrame(idx) + CONFIG.frameExtension;
  }

  /** Snap to loaded frame step on mobile (e.g. 2, 4, 6 …). */
  function snapFrameIndex(idx) {
    const step = CONFIG.frameStep;
    if (step <= 1) return clamp(Math.round(idx), 1, CONFIG.totalFrames);
    const snapped = Math.round((idx - 1) / step) * step + 1;
    return clamp(snapped, 1, CONFIG.totalFrames);
  }

  // ── IMAGE PRELOADER ────────────────────────────────────
  const imageCache = new Map();
  let loadedCount = 0;
  let preloadComplete = false;

  function preloadImage(idx) {
    return new Promise((resolve) => {
      if (imageCache.has(idx)) {
        resolve(imageCache.get(idx));
        return;
      }
      const img = new Image();
      img.onload = () => {
        imageCache.set(idx, img);
        loadedCount++;
        updatePreloadProgress();
        resolve(img);
      };
      img.onerror = () => {
        loadedCount++;
        updatePreloadProgress();
        resolve(null);
      };
      img.src = framePath(idx);
    });
  }

  function updatePreloadProgress() {
    const bar = $('#preloadBar');
    if (bar) {
      const pct = (loadedCount / CONFIG.totalFrames) * 100;
      bar.style.width = pct + '%';
    }
  }

  async function preloadAllFrames() {
    // Phase 1: Critical frames — first 15 + evenly spaced keyframes
    const critical = new Set();
    for (let i = 1; i <= 15; i++) critical.add(i);
    // Keyframes at every 10th frame
    for (let i = 20; i <= CONFIG.totalFrames; i += 10) critical.add(i);
    critical.add(CONFIG.totalFrames);

    const criticalArr = [...critical].sort((a, b) => a - b);
    await Promise.all(criticalArr.map(preloadImage));

    // Reveal the page once critical frames are ready
    hideLoader();

    // Immediately draw the first frame so the user doesn't see a black screen
    if (typeof renderFrame === 'function') {
      renderFrame(1, true);
    }

    // Show indicator if no scroll after 1 second
    setTimeout(() => {
      if (window.scrollY === 0) {
        const indicator = document.querySelector('.scroll-indicator');
        if (indicator) indicator.classList.add('scroll-indicator--visible');
      }
    }, 1000);

    // Hide indicator immediately upon scrolling
    window.addEventListener('scroll', function hideScrollIndicator() {
      if (window.scrollY > 0) {
        const indicator = document.querySelector('.scroll-indicator');
        if (indicator) indicator.classList.remove('scroll-indicator--visible');
        window.removeEventListener('scroll', hideScrollIndicator);
      }
    }, { passive: true });

    // Phase 2: Remaining frames in batches
    const remaining = [];
    for (let i = 1; i <= CONFIG.totalFrames; i++) {
      if (critical.has(i)) continue;
      if (CONFIG.frameStep > 1 && (i - 1) % CONFIG.frameStep !== 0 && i !== CONFIG.totalFrames) continue;
      remaining.push(i);
    }

    let idx = 0;
    while (idx < remaining.length) {
      const batch = remaining.slice(idx, idx + CONFIG.preloadBatchSize);
      await Promise.all(batch.map(preloadImage));
      idx += CONFIG.preloadBatchSize;
      // Yield to main thread
      if (idx < remaining.length) {
        await new Promise(r => setTimeout(r, CONFIG.preloadInterval));
      }
    }

    preloadComplete = true;
    const progressWrap = $('#preloadProgress');
    if (progressWrap) progressWrap.classList.add('preload-progress--hidden');
  }

  // ── PAGE LOADER ────────────────────────────────────────
  function hideLoader() {
    const loader = $('#pageLoader');
    if (!loader) return;
    loader.classList.add('page-loader--hidden');
    setTimeout(() => { loader.style.display = 'none'; }, 600);
  }

  // ── NAVIGATION ─────────────────────────────────────────
  function initNavigation() {
    const nav = $('#mainNav');
    const toggle = $('#navToggle');
    const mobileMenu = $('#mobileMenu');
    const mobileClose = $('#mobileMenuClose');
    if (!nav) return;

    let lastScrollY = 0;
    let ticking = false;

    function onScroll() {
      lastScrollY = window.scrollY;
      if (!ticking) {
        raf(() => {
          if (lastScrollY > CONFIG.navScrollThreshold) {
            nav.classList.add('nav--scrolled');
          } else {
            nav.classList.remove('nav--scrolled');
          }
          ticking = false;
        });
        ticking = true;
      }
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    if (toggle && mobileMenu) {
      toggle.addEventListener('click', () => {
        mobileMenu.classList.add('mobile-menu--active');
        document.body.style.overflow = 'hidden';
      });
      if (mobileClose) {
        mobileClose.addEventListener('click', () => {
          mobileMenu.classList.remove('mobile-menu--active');
          document.body.style.overflow = '';
        });
      }
      $$('[data-close-menu]', mobileMenu).forEach(el => {
        el.addEventListener('click', () => {
          mobileMenu.classList.remove('mobile-menu--active');
          document.body.style.overflow = '';
        });
      });
    }
  }

  // ── SCROLL PROGRESS BAR ────────────────────────────────
  function initScrollProgress() {
    const bar = $('#scrollProgress');
    if (!bar) return;

    let ticking = false;
    function update() {
      if (!ticking) {
        raf(() => {
          const scrollH = document.documentElement.scrollHeight - window.innerHeight;
          const pct = scrollH > 0 ? (window.scrollY / scrollH) * 100 : 0;
          bar.style.width = pct + '%';
          ticking = false;
        });
        ticking = true;
      }
    }
    window.addEventListener('scroll', update, { passive: true });
  }

  // ═══════════════════════════════════════════════════════════
  // CORE: SCROLL-DRIVEN FRAME SEQUENCE ENGINE
  // ═══════════════════════════════════════════════════════════

  let canvas, ctx;
  let currentFrame = -1;
  let scrollContainer;
  let panelElements = {};
  let overlayEl;
  let cinematicActive = false;
  let scrollRafPending = false;
  let lastPanelProgress = -1;
  let currentProgress = 0;

  function initCinematicEngine() {
    canvas = $('#cinematicCanvas');
    scrollContainer = $('#cinematicScroll');
    if (!canvas || !scrollContainer) return;

    ctx = canvas.getContext('2d', { alpha: false, desynchronized: true });
    if (!ctx) return;

    Object.keys(CONFIG.panels).forEach(key => {
      panelElements[key] = $('#panel-' + key);
    });
    overlayEl = $('#cinematicOverlay');

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas, { passive: true });
    window.addEventListener('scroll', onCinematicScroll, { passive: true });

    const io = new IntersectionObserver(([entry]) => {
      cinematicActive = entry.isIntersecting;
      if (cinematicActive) scheduleCinematicTick();
    }, { root: null, threshold: 0, rootMargin: '120px 0px' });
    io.observe(scrollContainer);

    cinematicActive = true;
    renderFrame(1, true);
    updateCinematicFromScroll();
  }

  function resizeCanvas() {
    if (!canvas) return;
    const dpr = Math.min(window.devicePixelRatio || 1, CONFIG.maxDpr);
    const w = window.innerWidth;
    const h = window.innerHeight;

    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';

    // Store for drawImage
    canvas._logicalW = w;
    canvas._logicalH = h;
    canvas._dpr = dpr;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Re-render current
    if (currentFrame > 0) renderFrame(currentFrame, true);
  }

  function onCinematicScroll() {
    if (!scrollContainer) return;
    scheduleCinematicTick();
  }

  function scheduleCinematicTick() {
    if (scrollRafPending) return;
    scrollRafPending = true;
    raf(() => {
      scrollRafPending = false;
      if (!scrollContainer) return;
      updateCinematicFromScroll();
    });
  }

  function updateCinematicFromScroll() {
    const rect = scrollContainer.getBoundingClientRect();
    const scrolled = -rect.top;
    const runway = scrollContainer.offsetHeight - window.innerHeight;
    if (runway <= 0) return;

    currentProgress = clamp(scrolled / runway, 0, 1);

    const rawFrame = 1 + currentProgress * (CONFIG.totalFrames - 1);
    const frameToRender = snapFrameIndex(rawFrame);
    if (frameToRender !== currentFrame) {
      renderFrame(frameToRender);
    }

    if (Math.abs(currentProgress - lastPanelProgress) > 0.002 || lastPanelProgress < 0) {
      updatePanels(currentProgress);
      lastPanelProgress = currentProgress;
    }
  }

  function renderFrame(idx, force) {
    idx = snapFrameIndex(clamp(idx, 1, CONFIG.totalFrames));
    if (idx === currentFrame && !force) return;

    const img = imageCache.get(idx);
    if (img) {
      drawImage(img);
      currentFrame = idx;
      return;
    }

    // Fallback: find nearest loaded frame
    for (let delta = 1; delta <= 15; delta++) {
      const lo = imageCache.get(idx - delta);
      if (lo) { drawImage(lo); currentFrame = idx; return; }
      const hi = imageCache.get(idx + delta);
      if (hi) { drawImage(hi); currentFrame = idx; return; }
    }
    currentFrame = idx;
  }

  function drawImage(img) {
    if (!ctx || !img) return;

    const cw = canvas._logicalW;
    const ch = canvas._logicalH;

    // Clear full canvas
    ctx.clearRect(0, 0, cw, ch);

    // Fill black background to prevent flash
    ctx.fillStyle = '#04070e';
    ctx.fillRect(0, 0, cw, ch);

    // Cover-fit: fill viewport while preserving aspect ratio
    const imgRatio = img.naturalWidth / img.naturalHeight;
    const canvasRatio = cw / ch;

    let sx, sy, sw, sh;

    if (canvasRatio > imgRatio) {
      // Viewport is wider than image — crop top/bottom
      sw = img.naturalWidth;
      sh = img.naturalWidth / canvasRatio;
      sx = 0;
      sy = (img.naturalHeight - sh) / 2;
    } else {
      // Viewport is taller than image — crop left/right
      sh = img.naturalHeight;
      sw = img.naturalHeight * canvasRatio;
      sx = (img.naturalWidth - sw) / 2;
      sy = 0;
    }

    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = CONFIG.smoothingQuality;
    ctx.drawImage(img, sx, sy, sw, sh, 0, 0, cw, ch);
  }

  // ── PANEL VISIBILITY (with smooth crossfade) ──────────
  let activePanelKey = null;
  let lastOverlayClass = 'overlay-hero';

  function updatePanels(progress) {
    let newActiveKey = null;
    const fade = CONFIG.panelFadeZone;

    Object.entries(CONFIG.panels).forEach(([key, range]) => {
      const panel = panelElements[key];
      if (!panel) return;

      // Calculate opacity with smooth fade zones at boundaries
      let opacity;
      if (progress < range.start - fade || progress > range.end + fade) {
        opacity = 0;
      } else if (progress >= range.start && progress <= range.end) {
        // Fade in at start
        const fadeIn = smoothstep(range.start, range.start + fade, progress);
        // Fade out at end
        const fadeOut = 1 - smoothstep(range.end - fade, range.end, progress);
        opacity = Math.min(fadeIn, fadeOut);
        // Keep full opacity in the middle
        if (progress > range.start + fade && progress < range.end - fade) {
          opacity = 1;
        }
      } else if (progress < range.start) {
        opacity = smoothstep(range.start - fade, range.start, progress);
      } else {
        opacity = 1 - smoothstep(range.end, range.end + fade, progress);
      }

      opacity = clamp(opacity, 0, 1);

      if (opacity > 0.01) {
        panel.style.opacity = String(opacity);
        const translateY = (1 - opacity) * 20;
        panel.style.transform = `translate3d(0, ${translateY}px, 0)`;
        panel.style.pointerEvents = opacity > 0.5 ? 'auto' : 'none';
        panel.classList.add('story-panel--active');

        if (opacity > 0.5) {
          newActiveKey = key;
          const panelProgress = (progress - range.start) / (range.end - range.start);
          animateCards(panel, panelProgress);
        }
      } else {
        panel.style.opacity = '0';
        panel.style.transform = 'translate3d(0, 20px, 0)';
        panel.style.pointerEvents = 'none';
        panel.classList.remove('story-panel--active');
      }
    });

    // Update overlay gradient
    if (newActiveKey && newActiveKey !== activePanelKey) {
      activePanelKey = newActiveKey;
      if (overlayEl) {
        const newClass = CONFIG.panels[newActiveKey].overlay;
        if (newClass !== lastOverlayClass) {
          overlayEl.classList.remove(lastOverlayClass);
          overlayEl.classList.add(newClass);
          lastOverlayClass = newClass;
        }
      }
    }
  }

  function animateCards(panel, progress) {
    const cards = $$('[data-card-reveal]', panel);
    cards.forEach((card, idx) => {
      const threshold = 0.12 + (idx * 0.1);
      if (progress >= threshold) {
        card.classList.add('card-visible');
      }
    });
  }

  // ── PARTICLE SYSTEM ────────────────────────────────────
  function initParticles() {
    if (!CONFIG.enableParticles || prefersReducedMotion) return;

    const particleCanvas = document.createElement('canvas');
    particleCanvas.style.cssText = 'position:absolute;inset:0;z-index:4;pointer-events:none;';

    const stickyEl = $('.cinematic-sticky');
    if (!stickyEl) return;
    stickyEl.appendChild(particleCanvas);

    const pCtx = particleCanvas.getContext('2d');
    if (!pCtx) return;

    let particles = [];
    let width = 0, height = 0;
    let animId = null;
    let isVisible = true;

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      particleCanvas.width = width * dpr;
      particleCanvas.height = height * dpr;
      particleCanvas.style.width = width + 'px';
      particleCanvas.style.height = height + 'px';
      pCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function createParticle() {
      return {
        x: Math.random() * width,
        y: Math.random() * height,
        size: CONFIG.particleMinSize + Math.random() * (CONFIG.particleMaxSize - CONFIG.particleMinSize),
        speedX: (Math.random() - 0.5) * 0.04,
        speedY: (Math.random() - 0.5) * 0.02,
        opacity: 0.03 + Math.random() * 0.15,
        pulse: Math.random() * Math.PI * 2,
        pulseSpeed: 0.001 + Math.random() * 0.003,
      };
    }

    function initP() {
      resize();
      particles = Array.from({ length: CONFIG.particleCount }, createParticle);
    }

    function drawParticles() {
      if (!isVisible) { animId = null; return; }

      pCtx.clearRect(0, 0, width, height);

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.x += p.speedX;
        p.y += p.speedY;
        p.pulse += p.pulseSpeed;

        if (p.x < -10) p.x = width + 10;
        if (p.x > width + 10) p.x = -10;
        if (p.y < -10) p.y = height + 10;
        if (p.y > height + 10) p.y = -10;

        const o = p.opacity * (0.5 + Math.sin(p.pulse) * 0.5);
        pCtx.beginPath();
        pCtx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        pCtx.fillStyle = `rgba(140, 170, 255, ${o})`;
        pCtx.fill();
      }

      animId = raf(drawParticles);
    }

    const visObserver = new IntersectionObserver(([entry]) => {
      isVisible = entry.isIntersecting;
      if (isVisible && !animId) {
        animId = raf(drawParticles);
      }
    }, { threshold: 0 });

    visObserver.observe(stickyEl);
    window.addEventListener('resize', resize);

    initP();
    animId = raf(drawParticles);
  }

  // ── CTA SECTION REVEAL ─────────────────────────────────
  function initCtaReveal() {
    const reveals = $$('.cta-section .reveal');
    if (!reveals.length) return;

    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('reveal--visible');
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

      reveals.forEach(el => observer.observe(el));
    } else {
      reveals.forEach(el => el.classList.add('reveal--visible'));
    }
  }

  // ── SMOOTH SCROLL TO APP ───────────────────────────────
  window.scrollToApp = function () {
    window.location.href = '/app';
  };

  // ── INITIALIZE ─────────────────────────────────────────
  async function init() {
    initNavigation();
    initScrollProgress();

    // Start preloading (hides loader once critical frames ready)
    preloadAllFrames();

    // Initialize cinematic engine
    initCinematicEngine();

    if (CONFIG.enableParticles) initParticles();

    // CTA reveal animations
    initCtaReveal();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
