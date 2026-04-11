/**
 * Celestial Arc - Landing Page JavaScript
 * Minimal, performance-optimized interactions
 */

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

    // Keyboard accessibility for buttons
    setupKeyboardAccessibility();
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
