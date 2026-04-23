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
