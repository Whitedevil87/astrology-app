/**
 * Celestial Arc - Landing Page JavaScript
 * Premium slide-based scroll experience
 */

// ============================================
// SLIDE NAVIGATION SYSTEM
// ============================================

let currentSlideIndex = 0;
let isScrolling = false;

const slides = [];
let slideIndicators = null;

document.addEventListener('DOMContentLoaded', () => {
    // Initialize slides
    initializeSlides();
    
    // Keyboard accessibility for buttons
    setupKeyboardAccessibility();

    // Smooth scroll snapping for supported browsers
    setupScrollSnapping();

    // Add keyboard navigation
    setupSlideKeyboardNavigation();

    // Live animated starfield
    initStarfield();
});

// ============================================
// LIVE STARFIELD ANIMATION (Canvas)
// ============================================

function initStarfield() {
    const canvas = document.getElementById('starfield-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    // --- Static twinkling stars ---
    const STAR_COLORS = ['#ffffff', '#cce8ff', '#ffe8b0', '#d4c8ff', '#b8e8ff'];
    const stars = Array.from({ length: 220 }, () => ({
        x: Math.random(),
        y: Math.random(),
        r: Math.random() * 1.6 + 0.25,
        baseOp: Math.random() * 0.55 + 0.15,
        speed: Math.random() * 0.022 + 0.005,
        phase: Math.random() * Math.PI * 2,
        color: STAR_COLORS[Math.floor(Math.random() * STAR_COLORS.length)]
    }));

    // --- Shooting stars ---
    const shooters = [];

    function spawnShooter() {
        if (document.hidden) return;
        const angle = (Math.PI / 5) + (Math.random() - 0.5) * 0.5;
        const speed = Math.random() * 8 + 5;
        shooters.push({
            x: Math.random() * canvas.width * 0.75,
            y: Math.random() * canvas.height * 0.45,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed,
            len: Math.random() * 100 + 55,
            life: 0,
            maxLife: Math.random() * 45 + 28
        });
    }

    // First one appears quickly
    setTimeout(spawnShooter, 800);
    let shootTimer = setInterval(spawnShooter, 3200);

    let frame = 0;
    let animId;

    function animate() {
        animId = requestAnimationFrame(animate);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        frame++;

        // Twinkling stars
        stars.forEach(s => {
            const tw = Math.sin(frame * s.speed + s.phase);
            const op = Math.max(0.04, s.baseOp + tw * 0.32);

            ctx.globalAlpha = op;
            ctx.fillStyle = s.color;
            ctx.beginPath();
            ctx.arc(s.x * canvas.width, s.y * canvas.height, s.r, 0, Math.PI * 2);
            ctx.fill();

            // Soft halo glow on larger stars
            if (s.r > 1.15) {
                ctx.globalAlpha = op * 0.22;
                ctx.beginPath();
                ctx.arc(s.x * canvas.width, s.y * canvas.height, s.r * 3.2, 0, Math.PI * 2);
                ctx.fill();
            }
        });

        // Shooting stars
        for (let i = shooters.length - 1; i >= 0; i--) {
            const ss = shooters[i];
            ss.life++;
            ss.x += ss.vx;
            ss.y += ss.vy;

            const prog = ss.life / ss.maxLife;
            const fade = prog < 0.25 ? prog / 0.25 : 1 - (prog - 0.25) / 0.75;
            const mag = Math.hypot(ss.vx, ss.vy);
            const tailX = ss.x - (ss.vx / mag) * ss.len;
            const tailY = ss.y - (ss.vy / mag) * ss.len;

            const grad = ctx.createLinearGradient(tailX, tailY, ss.x, ss.y);
            grad.addColorStop(0, 'rgba(255,255,255,0)');
            grad.addColorStop(0.6, `rgba(180,220,255,${fade * 0.5})`);
            grad.addColorStop(1, `rgba(220,240,255,${fade * 0.95})`);

            ctx.globalAlpha = 1;
            ctx.beginPath();
            ctx.moveTo(tailX, tailY);
            ctx.lineTo(ss.x, ss.y);
            ctx.strokeStyle = grad;
            ctx.lineWidth = 1.8;
            ctx.lineCap = 'round';
            ctx.stroke();

            // Bright head dot
            ctx.globalAlpha = fade * 0.9;
            ctx.fillStyle = '#dff0ff';
            ctx.beginPath();
            ctx.arc(ss.x, ss.y, 1.8, 0, Math.PI * 2);
            ctx.fill();

            if (ss.life >= ss.maxLife) shooters.splice(i, 1);
        }

        ctx.globalAlpha = 1;
    }

    animate();

    // Pause when tab is hidden for performance
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            cancelAnimationFrame(animId);
            clearInterval(shootTimer);
        } else {
            animate();
            shootTimer = setInterval(spawnShooter, 3200);
        }
    });
}

function initializeSlides() {
    // Gather all slide sections
    const sections = document.querySelectorAll('body > section, body > .zodiac-strip, body > .footer');
    sections.forEach((section, index) => {
        section.dataset.slideIndex = index;
        slides.push(section);
    });

    // Create slide indicators
    createSlideIndicators();
    updateActiveSlide(0);
}

function createSlideIndicators() {
    const indicatorContainer = document.createElement('div');
    indicatorContainer.className = 'slide-indicators';
    
    slides.forEach((_, index) => {
        const dot = document.createElement('button');
        dot.className = 'slide-indicator-dot';
        dot.title = `Slide ${index + 1}`;
        dot.onclick = () => navigateToSlide(index);
        indicatorContainer.appendChild(dot);
    });

    document.body.appendChild(indicatorContainer);
    slideIndicators = document.querySelectorAll('.slide-indicator-dot');
}

function updateActiveSlide(index) {
    if (slideIndicators) {
        slideIndicators.forEach((dot, i) => {
            dot.classList.toggle('active', i === index);
        });
    }
    currentSlideIndex = index;
}

function navigateToSlide(index) {
    if (index < 0 || index >= slides.length || isScrolling) return;
    
    isScrolling = true;
    slides[index].scrollIntoView({ behavior: 'smooth', block: 'start' });
    updateActiveSlide(index);
    
    setTimeout(() => {
        isScrolling = false;
    }, 1000);
}

function setupScrollSnapping() {
    // Detect current slide on scroll
    let scrollTimeout;
    window.addEventListener('scroll', () => {
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(() => {
            const scrollY = window.scrollY;
            let closestIndex = 0;
            let closestDistance = Infinity;

            slides.forEach((slide, index) => {
                const slideTop = slide.offsetTop;
                const distance = Math.abs(scrollY - slideTop);
                if (distance < closestDistance) {
                    closestDistance = distance;
                    closestIndex = index;
                }
            });

            updateActiveSlide(closestIndex);
        }, 100);
    });
}

function setupSlideKeyboardNavigation() {
    document.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowDown' || e.key === ' ') {
            e.preventDefault();
            navigateToSlide(currentSlideIndex + 1);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            navigateToSlide(currentSlideIndex - 1);
        }
    });
}

// ============================================
// SCROLL TO APP FUNCTION
// ============================================

function scrollToApp() {
    // Navigate to the astrology app with smooth transition
    document.body.style.opacity = '0.7';
    document.body.style.transition = 'opacity 0.4s ease-in';
    
    setTimeout(() => {
        window.location.href = '/app';
    }, 150);
}

// ============================================
// FAQ TOGGLE
// ============================================

function toggleFAQ(button) {
    const faqItem = button.closest('.faq-item') || button.closest('.faq-card') || button.parentElement;

    // Close all other FAQ items (single-open behavior)
    document.querySelectorAll('.faq-item, .faq-card').forEach(item => {
        if (item !== faqItem) {
            const otherContent = item.querySelector('.faq-content');
            const otherToggle = item.querySelector('.faq-toggle');
            if (otherContent) otherContent.classList.remove('active');
            if (otherToggle) otherToggle.textContent = '+';
        }
    });

    // Toggle current
    const content = button.nextElementSibling;
    const toggle = button.querySelector('.faq-toggle');
    if (content) {
        content.classList.toggle('active');
        if (toggle) toggle.textContent = content.classList.contains('active') ? '−' : '+';
    }
}

// ============================================
// INTERSECTION OBSERVER FOR LAZY ANIMATIONS
// ============================================

const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.animation = 'fade-in 0.6s ease-out forwards';
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Observe feature cards for lazy animation
document.addEventListener('DOMContentLoaded', () => {
    const featureCards = document.querySelectorAll(
        '.feature-card, .feature-bento-item, .step, .step-card, .faq-card, .faq-item'
    );
    featureCards.forEach(card => {
        observer.observe(card);
    });
});

// ============================================
// KEYBOARD ACCESSIBILITY
// ============================================

function setupKeyboardAccessibility() {
    const ctaButtons = document.querySelectorAll('.cta-button, .faq-question, .faq-header, .cta-nav-btn');

    ctaButtons.forEach(button => {
        button.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                button.click();
            }
        });
    });
}

// ============================================
// SMOOTH LOAD ANIMATION
// ============================================

window.addEventListener('load', () => {
    // Ensure hero content is visible
    const heroContent = document.querySelector('.hero-content');
    if (heroContent) {
        heroContent.style.opacity = '1';
    }
});

// ============================================
// PREFERS-REDUCED-MOTION
// ============================================

if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    document.documentElement.style.scrollBehavior = 'auto';
    // Remove animations via CSS is already handled in landing.css
}

// ============================================
// PERFORMANCE MONITORING (Optional)
// ============================================

// Log core web vitals if available
if ('PerformanceObserver' in window) {
    try {
        const perfObserver = new PerformanceObserver((list) => {
            list.getEntries().forEach((entry) => {
                console.log(`${entry.name}: ${entry.duration.toFixed(2)}ms`);
            });
        });
        perfObserver.observe({ entryTypes: ['measure'] });
    } catch (e) {
        // Silently fail if not supported
    }
}

// ============================================
// SMOOTH ANCHOR LINKS
// ============================================

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth' });
        }
    });
});

// Export for testing or external use if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        scrollToApp,
        toggleFAQ,
        setupKeyboardAccessibility
    };
}
