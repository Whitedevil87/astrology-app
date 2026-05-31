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

  // ── NETWORK AWARENESS ─────────────────────────────────
  // Use Network Information API to serve lighter experience on slow connections
  const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  const effectiveType = conn ? conn.effectiveType : '4g';
  const isSlowNet = effectiveType === '2g' || effectiveType === 'slow-2g';
  const isMediumNet = effectiveType === '3g';

  // ── CONFIGURATION ──────────────────────────────────────
  const CONFIG = {
    totalFrames: 288,
    // Skip frames on mobile/slow connections to reduce download volume
    frameStep: isSlowNet ? 6 : (isMediumNet ? 3 : (isMobile ? 3 : 1)),
    frameBasePath: '/static/images/celestial-sequence-288/frame_',
    frameExtension: '.webp',

    // Story panel scroll ranges — Strict gaps to prevent ghosting/overlap
    panels: {
      hero:         { start: -0.05, end: 0.28, overlay: 'overlay-hero' },
      engine:       { start: 0.32, end: 0.58, overlay: 'overlay-engine' },
      intelligence: { start: 0.62, end: 0.88, overlay: 'overlay-intelligence' },
      activation:   { start: 0.92, end: 1.15, overlay: 'overlay-activation' },
    },

    panelFadeZone: 0.05,

    // Phase 2 background loading — batches & intervals
    preloadBatchSize: isSlowNet ? 4 : (isMobile ? 6 : 16),
    preloadInterval: isSlowNet ? 200 : (isMobile ? 80 : 30),

    navScrollThreshold: 40,
    particleCount: isMobile ? 30 : 80,
    particleMaxSize: 1.2,
    particleMinSize: 0.3,

    maxDpr: isMobile ? 1.0 : 1.5,
    enableParticles: true,
    smoothingQuality: isMobile ? 'medium' : 'low',

    // CRITICAL: how many frames before we hide the loader and show the page
    // OLD: ~43 frames (~3 MB) — FIXED: 5 frames (~350 KB)
    criticalFrameCount: isSlowNet ? 3 : 5,
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

  // Phase text cycling for the cinematic loader
  const LOADER_PHASES = [
    'Mapping planetary positions',
    'Calculating Dashas & Antardashas',
    'Reading your Nakshatra',
    'Activating Vedic AI engine',
    'Aligning cosmic blueprint',
  ];
  let phaseIdx = 0;
  let phaseTimer = null;

  function startPhaseTimer() {
    const el = document.getElementById('loaderPhase');
    if (!el) return;
    phaseTimer = setInterval(() => {
      phaseIdx = (phaseIdx + 1) % LOADER_PHASES.length;
      el.style.opacity = '0';
      setTimeout(() => {
        el.textContent = LOADER_PHASES[phaseIdx];
        el.style.opacity = '1';
      }, 300);
    }, 1800);
  }

  function stopPhaseTimer() {
    if (phaseTimer) { clearInterval(phaseTimer); phaseTimer = null; }
  }

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
    // Update top preload bar
    const bar = document.getElementById('preloadBar');
    if (bar) {
      const pct = (loadedCount / CONFIG.totalFrames) * 100;
      bar.style.width = pct + '%';
    }
    // Update cinematic loader inner bar
    const inner = document.getElementById('loaderBarInner');
    if (inner) {
      // Show progress relative to critical frames for the loader bar
      const pct = Math.min((loadedCount / CONFIG.criticalFrameCount) * 100, 100);
      inner.style.width = pct + '%';
    }
    // Update SVG arc (stroke-dashoffset from 553 → 0)
    const arc = document.getElementById('loaderArc');
    if (arc) {
      const progress = Math.min(loadedCount / CONFIG.criticalFrameCount, 1);
      arc.style.strokeDashoffset = String(553 * (1 - progress));
    }
  }

  async function preloadAllFrames() {
    // ── PHASE 1: CRITICAL (just 5 frames) ────────────────
    // Only load enough to show the first frame and start interacting.
    // OLD approach loaded ~43 frames (~3 MB) — we now load 5 (~350 KB).
    const critical = new Set();
    for (let i = 1; i <= CONFIG.criticalFrameCount; i++) critical.add(i);

    await Promise.all([...critical].map(preloadImage));

    // Page is now ready — hide loader, show content
    stopPhaseTimer();
    hideLoader();

    // Draw the first frame immediately
    if (typeof renderFrame === 'function') {
      renderFrame(1, true);
    }

    // Show scroll indicator after 1 second if user hasn't scrolled
    setTimeout(() => {
      if (window.scrollY === 0) {
        const indicator = document.querySelector('.scroll-indicator');
        if (indicator) indicator.classList.add('scroll-indicator--visible');
      }
    }, 1000);

    window.addEventListener('scroll', function hideScrollIndicator() {
      if (window.scrollY > 0) {
        const indicator = document.querySelector('.scroll-indicator');
        if (indicator) indicator.classList.remove('scroll-indicator--visible');
        window.removeEventListener('scroll', hideScrollIndicator);
      }
    }, { passive: true });

    // ── PHASE 2: SCROLL-PRIORITY BACKGROUND LOADING ───────
    // Load in scroll order: hero frames first, then rest.
    // Use requestIdleCallback so we don't compete with scroll/render.
    const remaining = [];

    // Priority A: hero scroll range (frames 1-80) — fill gaps
    for (let i = 1; i <= 80; i++) {
      if (critical.has(i)) continue;
      if (CONFIG.frameStep > 1 && (i - 1) % CONFIG.frameStep !== 0 && i !== CONFIG.totalFrames) continue;
      remaining.push(i);
    }
    // Priority B: engine panel range (frames 80-160)
    for (let i = 81; i <= 160; i++) {
      if (CONFIG.frameStep > 1 && (i - 1) % CONFIG.frameStep !== 0 && i !== CONFIG.totalFrames) continue;
      remaining.push(i);
    }
    // Priority C: remaining frames
    for (let i = 161; i <= CONFIG.totalFrames; i++) {
      if (CONFIG.frameStep > 1 && (i - 1) % CONFIG.frameStep !== 0 && i !== CONFIG.totalFrames) continue;
      remaining.push(i);
    }

    // Load remaining in batches, yielding to idle time between batches
    const loadBatch = async (startIdx) => {
      if (startIdx >= remaining.length) {
        preloadComplete = true;
        const progressWrap = document.getElementById('preloadProgress');
        if (progressWrap) progressWrap.classList.add('preload-progress--hidden');
        return;
      }
      const batch = remaining.slice(startIdx, startIdx + CONFIG.preloadBatchSize);
      await Promise.all(batch.map(preloadImage));

      const nextIdx = startIdx + CONFIG.preloadBatchSize;
      // Use requestIdleCallback if available, else setTimeout
      if (window.requestIdleCallback) {
        requestIdleCallback(() => loadBatch(nextIdx), { timeout: 2000 });
      } else {
        setTimeout(() => loadBatch(nextIdx), CONFIG.preloadInterval);
      }
    };

    // Small delay before starting background load so first paint is fully settled
    setTimeout(() => loadBatch(0), 400);
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
      if (force || canvas._lastDrawnIdx !== idx) {
        drawImage(img);
        canvas._lastDrawnIdx = idx;
      }
      currentFrame = idx;
      return;
    }

    // Fallback: find nearest loaded frame
    let foundImg = null;
    let foundIdx = -1;
    for (let delta = 1; delta <= 15; delta++) {
      if (imageCache.has(idx - delta)) {
        foundImg = imageCache.get(idx - delta);
        foundIdx = idx - delta;
        break;
      }
      if (imageCache.has(idx + delta)) {
        foundImg = imageCache.get(idx + delta);
        foundIdx = idx + delta;
        break;
      }
    }
    
    if (foundImg && (force || canvas._lastDrawnIdx !== foundIdx)) {
      drawImage(foundImg);
      canvas._lastDrawnIdx = foundIdx;
    }
    currentFrame = idx;
  }

  function drawImage(img) {
    if (!ctx || !img) return;

    const cw = canvas._logicalW;
    const ch = canvas._logicalH;

    // Fill black background to prevent flash (clearRect is redundant on opaque canvas)
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
      
      // Fast scroll safety: completely zero out if outside bounds
      if (progress < range.start || progress > range.end) {
        opacity = 0;
      } else {
        // Fade in from range.start -> range.start + fade
        const fadeIn = smoothstep(range.start, range.start + fade, progress);
        // Fade out from range.end - fade -> range.end
        const fadeOut = 1 - smoothstep(range.end - fade, range.end, progress);
        
        opacity = Math.min(fadeIn, fadeOut);
      }

      opacity = clamp(opacity, 0, 1);

      const lastOp = panel._lastOpacity !== undefined ? panel._lastOpacity : -1;
      
      // Skip redundant DOM updates if opacity hasn't changed significantly, 
      // but force updates when it approaches 0 to ensure elements fully hide
      if (Math.abs(opacity - lastOp) < 0.015 && opacity > 0.01 && opacity < 1) {
        if (opacity > 0.5) {
          newActiveKey = key;
          const panelProgress = (progress - range.start) / (range.end - range.start);
          animateCards(panel, panelProgress);
        }
        return; 
      }
      panel._lastOpacity = opacity;

      if (opacity > 0.01) {
        panel.style.opacity = String(opacity);
        // Add subtle translate to the entry, creating a cinematic glide
        const translateY = (1 - opacity) * 40; 
        panel.style.transform = `translate3d(0, ${translateY}px, 0)`;
        
        const pointer = opacity > 0.5 ? 'auto' : 'none';
        if (panel._lastPointer !== pointer) {
          panel.style.pointerEvents = pointer;
          panel._lastPointer = pointer;
        }
        
        if (!panel._isActive) {
          panel.classList.add('story-panel--active');
          panel._isActive = true;
        }

        if (opacity > 0.5) {
          newActiveKey = key;
          const panelProgress = (progress - range.start) / (range.end - range.start);
          animateCards(panel, panelProgress);
        }
      } else {
        if (panel._isActive !== false) {
          panel.style.opacity = '0';
          panel.style.transform = 'translate3d(0, 40px, 0)';
          panel.style.pointerEvents = 'none';
          panel._lastPointer = 'none';
          panel.classList.remove('story-panel--active');
          panel._isActive = false;
        }
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
    // Select all text blocks and cards to animate them line-by-line
    const elements = $$('.section-label, .section-title, .section-subtitle, .gold-accent-line, .engine-card, .intel-card, [data-card-reveal]', panel);
    
    elements.forEach((el, idx) => {
      // Calculate a staggered threshold for each line (starts at 5% of panel, adds 6% per element)
      const threshold = 0.05 + (idx * 0.06); 
      if (progress >= threshold) {
        el.classList.add('card-visible');
      } else {
        el.classList.remove('card-visible'); // Reverse animation when scrolling up
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

    // Start phase timer animation in the cinematic loader
    startPhaseTimer();

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
