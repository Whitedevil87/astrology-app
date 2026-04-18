/* ============================================
   CELESTIAL ARC - LANDING PAGE JAVASCRIPT
   Premium Interactions & Animations
   ============================================ */

document.addEventListener('DOMContentLoaded', () => {
    initializeLanding();
});

// Initialize all landing page features
function initializeLanding() {
    initializeFAQ();
    initializeScrollAnimations();
    initializeScrollToApp();
    initializeNavigation();
    // Performance optimization: use passive listeners
    window.addEventListener('scroll', throttle(() => {}, 100), { passive: true });
}

/* ============================================
   FAQ TOGGLE FUNCTIONALITY
   ============================================ */

function initializeFAQ() {
    const faqHeaders = document.querySelectorAll('.faq-header');
    
    faqHeaders.forEach(header => {
        header.addEventListener('click', () => {
            const faqContent = header.nextElementSibling;
            const isActive = faqContent.classList.contains('active');
            
            // Close all other FAQs
            document.querySelectorAll('.faq-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Toggle current FAQ
            if (!isActive) {
                faqContent.classList.add('active');
                header.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        });
    });
    
    // Single keydown listener for all FAQs
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.faq-content').forEach(content => {
                content.classList.remove('active');
            });
        }
    }, { once: false });
}

/* ============================================
   SCROLL-TRIGGERED ANIMATIONS
   ============================================ */

function initializeScrollAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.animation = `fadeInUp 0.8s cubic-bezier(0.4, 0, 0.2, 1) forwards`;
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // Observe all feature cards, testimonials, and other elements
    document.querySelectorAll('.feature-card, .testimonial-card, .faq-item').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        observer.observe(el);
    });
}

// Add keyframe animation to document
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes slideInLeft {
        from {
            opacity: 0;
            transform: translateX(-30px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    
    @keyframes slideInRight {
        from {
            opacity: 0;
            transform: translateX(30px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
`;
document.head.appendChild(style);

/* ============================================
   SCROLL TO APP FUNCTIONALITY
   ============================================ */

function initializeScrollToApp() {
    const ctaButtons = document.querySelectorAll('[data-scroll-to-app]');
    
    ctaButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            scrollToApp();
        });
    });
}

function scrollToApp() {
    // Navigate to the app form
    window.location.href = '/app';
}

/* ============================================
   SMOOTH NAVIGATION
   ============================================ */

function initializeNavigation() {
    // Smooth scroll for internal links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#') {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    });
    
    // Update active nav link on scroll
    updateActiveNavLink();
    window.addEventListener('scroll', updateActiveNavLink);
}

function updateActiveNavLink() {
    const sections = document.querySelectorAll('section, .hero');
    const navLinks = document.querySelectorAll('.nav-link');
    
    let current = '';
    sections.forEach(section => {
        const sectionTop = section.offsetTop;
        const sectionHeight = section.clientHeight;
        
        if (window.pageYOffset >= sectionTop - 200) {
            current = section.getAttribute('id');
        }
    });
    
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === `#${current}`) {
            link.classList.add('active');
        }
    });
}

/* ============================================
   MOUSE FOLLOW EFFECT
   ============================================ */

// Performance optimization: Mouse follow effect disabled to reduce lag
// Can be re-enabled with requestAnimationFrame if needed
// document.addEventListener('mousemove', (e) => { ... });

/* ============================================
   BUTTON RIPPLE EFFECT
   ============================================ */

document.querySelectorAll('.btn-primary, .btn-secondary').forEach(button => {
    button.addEventListener('click', (e) => {
        const ripple = document.createElement('span');
        const rect = button.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = e.clientX - rect.left - size / 2;
        const y = e.clientY - rect.top - size / 2;
        
        ripple.style.width = ripple.style.height = size + 'px';
        ripple.style.left = x + 'px';
        ripple.style.top = y + 'px';
        ripple.style.position = 'absolute';
        ripple.style.borderRadius = '50%';
        ripple.style.background = 'radial-gradient(circle, rgba(255,255,255,0.8), transparent)';
        ripple.style.pointerEvents = 'none';
        ripple.style.animation = 'ripple 0.6s ease-out';
        
        button.style.position = 'relative';
        button.style.overflow = 'hidden';
        button.appendChild(ripple);
        
        ripple.addEventListener('animationend', () => ripple.remove());
    });
});

// Add ripple animation
const rippleStyle = document.createElement('style');
rippleStyle.textContent = `
    @keyframes ripple {
        to {
            transform: scale(4);
            opacity: 0;
        }
    }
`;
document.head.appendChild(rippleStyle);

/* ============================================
   ACTIVE SECTION TRACKING
   ============================================ */

window.addEventListener('scroll', () => {
    // Update navbar background based on scroll
    const navbar = document.querySelector('.navbar');
    if (window.scrollY > 100) {
        navbar.style.background = 'rgba(15, 10, 31, 0.8)';
    } else {
        navbar.style.background = 'rgba(15, 10, 31, 0.5)';
    }
});

/* ============================================
   PERFORMANCE OPTIMIZATIONS
   ============================================ */

// Debounce function for scroll events
function debounce(func, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
}

// Throttle function for smooth animations
function throttle(func, delay) {
    let lastCall = 0;
    return function(...args) {
        const now = Date.now();
        if (now - lastCall >= delay) {
            func.apply(this, args);
            lastCall = now;
        }
    };
}

/* ============================================
   LAZY LOADING FOR IMAGES
   ============================================ */

if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                if (img.dataset.src) {
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                }
                observer.unobserve(img);
            }
        });
    });
    
    document.querySelectorAll('img[data-src]').forEach(img => {
        imageObserver.observe(img);
    });
}

/* ============================================
   UTILITY FUNCTIONS
   ============================================ */

// Get element by data attribute
function getElementByData(dataName, dataValue) {
    return document.querySelector(`[data-${dataName}="${dataValue}"]`);
}

// Animate element to target value
function animateValue(element, start, end, duration = 1000) {
    const range = end - start;
    const increment = range / (duration / 16);
    let current = start;
    
    const timer = setInterval(() => {
        current += increment;
        if ((increment > 0 && current >= end) || (increment < 0 && current <= end)) {
            element.textContent = end;
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(current);
        }
    }, 16);
}

/* ============================================
   FORM UTILITIES (for FAQ interactions)
   ============================================ */

// Toggle class on element
function toggleClass(element, className) {
    if (element) {
        element.classList.toggle(className);
    }
}

// Add class to element
function addClass(element, className) {
    if (element) {
        element.classList.add(className);
    }
}

// Remove class from element
function removeClass(element, className) {
    if (element) {
        element.classList.remove(className);
    }
}

/* ============================================
   KEYBOARD SHORTCUTS
   ============================================ */

document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K to focus on main CTA
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const mainCTA = document.querySelector('[data-scroll-to-app]');
        if (mainCTA) {
            mainCTA.focus();
            mainCTA.click();
        }
    }
    
    // Escape to close modals/FAQs
    if (e.key === 'Escape') {
        document.querySelectorAll('.faq-content').forEach(content => {
            content.classList.remove('active');
        });
    }
});

/* ============================================
   EXPORT FUNCTIONS FOR EXTERNAL USE
   ============================================ */

window.celestialArc = {
    scrollToApp,
    initializeLanding,
    debounce,
    throttle,
    toggleClass,
    addClass,
    removeClass,
    animateValue
};

console.log('✨ Celestial Arc Premium Landing Page initialized successfully');
