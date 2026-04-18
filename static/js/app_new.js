/* ============================================
   CELESTIAL ARC - APP FORM JAVASCRIPT
   Form Navigation & Interactions
   ============================================ */

let currentStep = 1;
let selectedPalm = null;
let uploadedFile = null;

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    calculateZodiacSign();
});

// Initialize app
function initializeApp() {
    console.log('✨ Celestial Arc App initialized successfully');
    
    // Event listeners
    document.getElementById('dob').addEventListener('change', calculateZodiacSign);
    
    // Upload area
    const uploadArea = document.getElementById('uploadArea');
    uploadArea.addEventListener('click', () => {
        document.getElementById('palmImage').click();
    });
}

/* ============================================
   STEP NAVIGATION
   ============================================ */

function goToStep(stepNumber) {
    // Validate current step before moving
    if (!validateStep(currentStep)) {
        showError('Please fill in all required fields');
        return;
    }

    // Hide current step
    document.getElementById(`step${currentStep}`).style.display = 'none';
    
    // Show new step
    document.getElementById(`step${stepNumber}`).style.display = 'block';
    
    // Update step indicator
    updateStepIndicator(stepNumber);
    
    // Update progress bar
    const progress = (stepNumber / 4) * 100;
    document.getElementById('progressFill').style.width = progress + '%';
    
    currentStep = stepNumber;
    
    // Scroll to top
    document.querySelector('.form-column').scrollIntoView({ behavior: 'smooth' });
}

function updateStepIndicator(stepNumber) {
    document.querySelectorAll('.step').forEach((step, index) => {
        if (index + 1 <= stepNumber) {
            step.classList.add('active');
        } else {
            step.classList.remove('active');
        }
    });
}

/* ============================================
   FORM VALIDATION
   ============================================ */

function validateStep(stepNumber) {
    switch(stepNumber) {
        case 1:
            return validateBirthInfo();
        case 2:
            return validatePalmChoice();
        case 3:
            return validateFileUpload();
        default:
            return true;
    }
}

function validateBirthInfo() {
    const name = document.getElementById('name').value.trim();
    const dob = document.getElementById('dob').value;
    const tob = document.getElementById('tob').value;
    const pob = document.getElementById('pob').value.trim();
    const gender = document.querySelector('input[name="gender"]:checked');
    
    if (!name || !dob || !tob || !pob || !gender) {
        return false;
    }
    
    // Validate date is not in future
    const birthDate = new Date(dob);
    if (birthDate > new Date()) {
        showError('Birth date cannot be in the future');
        return false;
    }
    
    return true;
}

function validatePalmChoice() {
    if (!selectedPalm) {
        showError('Please select a palm option');
        return false;
    }
    return true;
}

function validateFileUpload() {
    if (!uploadedFile) {
        showError('Please upload a palm image');
        return false;
    }
    return true;
}

/* ============================================
   PALM CHOICE SELECTION
   ============================================ */

function selectPalm(choice) {
    // Remove active class from all options
    document.querySelectorAll('.palm-option').forEach(option => {
        option.classList.remove('active');
    });
    
    // Add active class to selected option
    event.target.closest('.palm-option').classList.add('active');
    selectedPalm = choice;
    
    showSuccess(`Selected: ${choice.charAt(0).toUpperCase() + choice.slice(1)} hand`);
}

/* ============================================
   FILE UPLOAD HANDLING
   ============================================ */

function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('uploadArea').classList.add('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('uploadArea').classList.remove('drag-over');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileSelect({ target: { files: files } });
    }
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    
    if (!file) return;
    
    // Validate file type
    if (!file.type.startsWith('image/')) {
        showError('Please upload an image file');
        return;
    }
    
    // Validate file size (10MB max)
    if (file.size > 10 * 1024 * 1024) {
        showError('File size must be less than 10MB');
        return;
    }
    
    uploadedFile = file;
    
    // Display file preview
    const reader = new FileReader();
    reader.onload = (e) => {
        const uploadArea = document.getElementById('uploadArea');
        uploadArea.innerHTML = `
            <div class="upload-success">
                <div class="upload-icon">✅</div>
                <h3>File uploaded successfully!</h3>
                <p>${file.name}</p>
                <button type="button" class="btn-change-file" onclick="changeFile()">Change file</button>
            </div>
        `;
    };
    reader.readAsDataURL(file);
    
    showSuccess('File uploaded successfully!');
}

function changeFile() {
    document.getElementById('palmImage').click();
}

/* ============================================
   ZODIAC SIGN CALCULATION
   ============================================ */

function calculateZodiacSign() {
    const dob = document.getElementById('dob').value;
    
    if (!dob) return;
    
    const date = new Date(dob);
    const month = date.getMonth() + 1;
    const day = date.getDate();
    
    const zodiacSigns = [
        { name: 'Capricorn', symbol: '♑', start: [12, 22], end: [1, 19] },
        { name: 'Aquarius', symbol: '♒', start: [1, 20], end: [2, 18] },
        { name: 'Pisces', symbol: '♓', start: [2, 19], end: [3, 20] },
        { name: 'Aries', symbol: '♈', start: [3, 21], end: [4, 19] },
        { name: 'Taurus', symbol: '♉', start: [4, 20], end: [5, 20] },
        { name: 'Gemini', symbol: '♊', start: [5, 21], end: [6, 20] },
        { name: 'Cancer', symbol: '♋', start: [6, 21], end: [7, 22] },
        { name: 'Leo', symbol: '♌', start: [7, 23], end: [8, 22] },
        { name: 'Virgo', symbol: '♍', start: [8, 23], end: [9, 22] },
        { name: 'Libra', symbol: '♎', start: [9, 23], end: [10, 22] },
        { name: 'Scorpio', symbol: '♏', start: [10, 23], end: [11, 21] },
        { name: 'Sagittarius', symbol: '♐', start: [11, 22], end: [12, 21] }
    ];
    
    let zodiac = zodiacSigns[0];
    
    for (let sign of zodiacSigns) {
        const startDate = new Date(date.getFullYear(), sign.start[0] - 1, sign.start[1]);
        const endDate = new Date(date.getFullYear(), sign.end[0] - 1, sign.end[1]);
        
        if (date >= startDate && date <= endDate) {
            zodiac = sign;
            break;
        }
    }
    
    // Update zodiac display
    document.querySelector('.zodiac-symbol').textContent = zodiac.symbol;
    document.getElementById('zodiacName').textContent = zodiac.name;
    document.getElementById('zodiacDate').textContent = `${zodiac.start[0]}/${zodiac.start[1]} - ${zodiac.end[0]}/${zodiac.end[1]}`;
    
    // Animate zodiac symbol
    animateZodiacSymbol();
}

function animateZodiacSymbol() {
    const symbol = document.querySelector('.zodiac-symbol');
    symbol.style.animation = 'none';
    setTimeout(() => {
        symbol.style.animation = 'float 3s ease-in-out infinite';
    }, 10);
}

/* ============================================
   FORM SUBMISSION
   ============================================ */

function handleFormSubmit(e) {
    e.preventDefault();
    
    // Validate all steps
    for (let i = 1; i <= 3; i++) {
        if (!validateStep(i)) {
            goToStep(i);
            return;
        }
    }
    
    // Go to loading step
    goToStep(4);
    
    // Simulate processing
    simulateProcessing();
}

function simulateProcessing() {
    const progressText = document.getElementById('progressText');
    const steps = [
        'Initializing readings...',
        'Analyzing birth chart...',
        'Reading palm lines...',
        'Calculating destiny path...',
        'Processing Big Three...',
        'Generating compatibility insights...',
        'Creating personalized report...',
        'Finalizing predictions...'
    ];
    
    let stepIndex = 0;
    let progress = 0;
    
    const interval = setInterval(() => {
        if (stepIndex < steps.length) {
            progressText.textContent = steps[stepIndex];
            progress = (stepIndex / (steps.length - 1)) * 100;
            document.getElementById('loadingProgress').style.width = progress + '%';
            stepIndex++;
        } else {
            clearInterval(interval);
            // In production, redirect to results page
            showSuccess('Reading complete! Redirecting to your results...');
            setTimeout(() => {
                // window.location.href = '/results';
                alert('Your cosmic reading is ready! (In production, this would redirect to results page)');
            }, 2000);
        }
    }, 600);
}

/* ============================================
   SIDEBAR NAVIGATION
   ============================================ */

function toggleSidebar() {
    const sidebar = document.querySelector('.app-sidebar');
    sidebar.classList.toggle('open');
}

function closeSidebar() {
    document.querySelector('.app-sidebar').classList.remove('open');
}

function navigateToHome() {
    showInfo('Navigating to home...');
    closeSidebar();
}

function navigateToReading() {
    showInfo('Navigating to your reading...');
    closeSidebar();
}

function navigateToHistory() {
    showInfo('Viewing reading history...');
    closeSidebar();
}

function navigateToProfile() {
    showInfo('Editing profile...');
    closeSidebar();
}

function logout() {
    if (confirm('Are you sure you want to logout?')) {
        showSuccess('Logged out successfully. Redirecting...');
        // window.location.href = '/logout';
    }
}

/* ============================================
   NOTIFICATIONS
   ============================================ */

function showError(message) {
    showNotification(message, 'error');
}

function showSuccess(message) {
    showNotification(message, 'success');
}

function showInfo(message) {
    showNotification(message, 'info');
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span class="notification-icon">${getNotificationIcon(type)}</span>
            <span class="notification-message">${message}</span>
        </div>
        <button class="notification-close" onclick="this.parentElement.remove()">✕</button>
    `;
    
    // Add styles if not already present
    if (!document.getElementById('notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            .notification {
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 1rem 1.5rem;
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 1rem;
                z-index: 9999;
                animation: slideInRight 0.3s ease;
                max-width: 400px;
            }
            
            .notification-success {
                background: rgba(16, 185, 129, 0.1);
                border: 1px solid rgba(16, 185, 129, 0.3);
                color: #10b981;
            }
            
            .notification-error {
                background: rgba(255, 0, 110, 0.1);
                border: 1px solid rgba(255, 0, 110, 0.3);
                color: #ff006e;
            }
            
            .notification-info {
                background: rgba(0, 217, 255, 0.1);
                border: 1px solid rgba(0, 217, 255, 0.3);
                color: #00d9ff;
            }
            
            .notification-content {
                display: flex;
                align-items: center;
                gap: 0.8rem;
            }
            
            .notification-icon {
                font-size: 1.2rem;
            }
            
            .notification-message {
                font-weight: 500;
            }
            
            .notification-close {
                background: none;
                border: none;
                color: inherit;
                font-size: 1.2rem;
                cursor: pointer;
                padding: 0;
            }
            
            @keyframes slideInRight {
                from {
                    transform: translateX(400px);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
        `;
        document.head.appendChild(style);
    }
    
    document.body.appendChild(notification);
    
    // Auto remove after 4 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

function getNotificationIcon(type) {
    const icons = {
        success: '✅',
        error: '❌',
        info: 'ℹ️'
    };
    return icons[type] || '📢';
}

/* ============================================
   UTILITY FUNCTIONS
   ============================================ */

function debounce(func, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
}

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
   EXPORT FUNCTIONS
   ============================================ */

window.celestialAppForm = {
    goToStep,
    selectPalm,
    handleDragOver,
    handleDrop,
    handleFileSelect,
    changeFile,
    calculateZodiacSign,
    handleFormSubmit,
    toggleSidebar,
    closeSidebar,
    navigateToHome,
    navigateToReading,
    navigateToHistory,
    navigateToProfile,
    logout,
    showError,
    showSuccess,
    showInfo,
    showNotification
};

console.log('✨ Celestial Arc App Form loaded and ready');
