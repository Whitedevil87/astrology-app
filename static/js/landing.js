/**
 * Celestial Arc - Landing Page JavaScript (Enhanced)
 * Premium slide-based scroll experience with mobile support
 */

// ============================================
// MOBILE MENU MANAGEMENT
// ============================================

function toggleMobileMenu() {
    const menu = document.getElementById('mobileMenu');
    const hamburger = document.getElementById('menuToggle');
    
    if (menu && hamburger) {
        menu.classList.toggle('active');
        hamburger.classList.toggle('active');
        hamburger.setAttribute('aria-expanded', menu.classList.contains('active'));
    }
}

function closeMobileMenu() {
    const menu = document.getElementById('mobileMenu');
    const hamburger = document.getElementById('menuToggle');
    
    if (menu && hamburger) {
        menu.classList.remove('active');
        hamburger.classList.remove('active');
        hamburger.setAttribute('aria-expanded', 'false');
    }
}

// Close mobile menu when clicking on a link
document.addEventListener('click', (e) => {
    const menu = document.getElementById('mobileMenu');
    const hamburger = document.getElementById('menuToggle');
    
    if (menu && hamburger && menu.classList.contains('active')) {
        if (e.target.closest('.mobile-menu-link')) {
            closeMobileMenu();
        }
    }
});

// Mobile menu toggle button
document.addEventListener('DOMContentLoaded', () => {
    const menuToggle = document.getElementById('menuToggle');
    if (menuToggle) {
        menuToggle.addEventListener('click', toggleMobileMenu);
    }
});

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

    // Subtle 3D motion for the hero planetary system
    setupAstrologySystemMotion();
});

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
// HERO ASTROLOGY SYSTEM PARALLAX
// ============================================

function setupAstrologySystemMotion() {
    const system = document.getElementById('astrologySystem');

    if (!system || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return;
    }

    const resetSystem = () => {
        system.style.setProperty('--tilt-x', '4deg');
        system.style.setProperty('--tilt-y', '-2deg');
        system.style.setProperty('--glow-x', '50%');
        system.style.setProperty('--glow-y', '38%');
    };

    resetSystem();

    system.addEventListener('pointermove', (event) => {
        const rect = system.getBoundingClientRect();
        const relativeX = (event.clientX - rect.left) / rect.width - 0.5;
        const relativeY = (event.clientY - rect.top) / rect.height - 0.5;

        const tiltX = 4 - relativeY * 4;
        const tiltY = -2 + relativeX * 5;
        const glowX = 50 + relativeX * 16;
        const glowY = 38 + relativeY * 16;

        system.style.setProperty('--tilt-x', `${tiltX.toFixed(2)}deg`);
        system.style.setProperty('--tilt-y', `${tiltY.toFixed(2)}deg`);
        system.style.setProperty('--glow-x', `${glowX.toFixed(2)}%`);
        system.style.setProperty('--glow-y', `${glowY.toFixed(2)}%`);
    });

    system.addEventListener('pointerleave', resetSystem);
}

// ============================================
// SCROLL TO APP FUNCTION
// ============================================

function scrollToApp() {
    // Close mobile menu if open
    closeMobileMenu();
    
    // Navigate to the astrology app with smooth transition
    document.body.style.opacity = '0.7';
    document.body.style.transition = 'opacity 0.4s ease-in';
    
    setTimeout(() => {
        window.location.href = '/app';
    }, 150);
}

// ============================================
// FAQ TOGGLE (ENHANCED WITH ARIA)
// ============================================

function toggleFAQ(button) {
    const faqItem = button.closest('.faq-item');

    // Close all other FAQ items (single-open behavior)
    document.querySelectorAll('.faq-item').forEach(item => {
        if (item !== faqItem) {
            const otherContent = item.querySelector('.faq-content');
            const otherToggle = item.querySelector('.faq-toggle');
            if (otherContent) {
                otherContent.classList.remove('active');
                otherContent.setAttribute('aria-hidden', 'true');
            }
            if (otherToggle) otherToggle.textContent = '+';
        }
    });

    // Toggle current
    const content = button.nextElementSibling;
    const toggle = button.querySelector('.faq-toggle');
    if (content) {
        content.classList.toggle('active');
        const isOpen = content.classList.contains('active');
        content.setAttribute('aria-hidden', !isOpen);
        if (toggle) toggle.textContent = isOpen ? '−' : '+';
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
        '.feature-card, .step, .preview-card, .faq-item'
    );
    featureCards.forEach(card => {
        observer.observe(card);
    });
});

// ============================================
// KEYBOARD ACCESSIBILITY
// ============================================

function setupKeyboardAccessibility() {
    const ctaButtons = document.querySelectorAll('.cta-button, .faq-header, .cta-nav-btn');

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
// NUMBER COUNTER ANIMATION
// ============================================

function animateCountUp(element, target, duration = 2000) {
    let current = 0;
    const increment = target / (duration / 16);
    
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            element.textContent = target;
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(current);
        }
    }, 16);
}

// Initialize counter animations on scroll
document.addEventListener('DOMContentLoaded', () => {
    const statsObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !entry.target.dataset.animated) {
                entry.target.dataset.animated = 'true';
                const statValues = entry.target.querySelectorAll('.stat-value');
                statValues.forEach(stat => {
                    const target = parseInt(stat.textContent, 10);
                    if (!isNaN(target)) {
                        animateCountUp(stat, target);
                    }
                });
                statsObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    const statsSection = document.querySelector('.hero-stats');
    if (statsSection) {
        statsObserver.observe(statsSection);
    }
});

// ============================================
// SMOOTH SCROLL POLYFILL
// ============================================

if (!('scrollBehavior' in document.documentElement.style)) {
    console.log('Smooth scroll not supported, using polyfill');
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
        setupKeyboardAccessibility,
        setupAstrologySystemMotion
    };
}
