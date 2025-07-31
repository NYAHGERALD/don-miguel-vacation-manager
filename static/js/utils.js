// Utility functions for Don Miguel Vacation Manager
// Common helper functions and API utilities

// API Base URL
const API_BASE_URL = '/api';

// API Client class for making authenticated requests
export class ApiClient {
    constructor(authManager) {
        this.authManager = authManager;
    }

    // Make authenticated API request
    async request(endpoint, options = {}) {
        try {
            const token = await this.authManager.getCurrentUserToken();
            
            const defaultOptions = {
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                }
            };

            const mergedOptions = {
                ...defaultOptions,
                ...options,
                headers: {
                    ...defaultOptions.headers,
                    ...options.headers
                }
            };

            const response = await fetch(`${API_BASE_URL}${endpoint}`, mergedOptions);
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({ error: 'Request failed' }));
                throw new Error(error.error || `HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API request failed: ${endpoint}`, error);
            throw error;
        }
    }

    // GET request
    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    }

    // POST request
    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    // PUT request
    async put(endpoint, data = null) {
        const options = { method: 'PUT' };
        if (data) {
            options.body = JSON.stringify(data);
        }
        return this.request(endpoint, options);
    }

    // DELETE request
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }
}

// Date utilities
export class DateUtils {
    // Format date for display
    static formatDate(dateString, options = {}) {
        const defaultOptions = {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        };
        
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { ...defaultOptions, ...options });
    }

    // Format date for input fields
    static formatDateForInput(dateString) {
        const date = new Date(dateString);
        return date.toISOString().split('T')[0];
    }

    // Calculate business days between two dates
    static calculateBusinessDays(startDate, endDate) {
        const start = new Date(startDate);
        const end = new Date(endDate);
        let businessDays = 0;
        let currentDate = new Date(start);

        while (currentDate <= end) {
            const dayOfWeek = currentDate.getDay();
            if (dayOfWeek !== 0 && dayOfWeek !== 6) { // Not Sunday (0) or Saturday (6)
                businessDays++;
            }
            currentDate.setDate(currentDate.getDate() + 1);
        }

        return businessDays;
    }

    // Add business days to a date
    static addBusinessDays(startDate, days) {
        const date = new Date(startDate);
        let addedDays = 0;

        while (addedDays < days) {
            date.setDate(date.getDate() + 1);
            const dayOfWeek = date.getDay();
            if (dayOfWeek !== 0 && dayOfWeek !== 6) {
                addedDays++;
            }
        }

        return date;
    }

    // Get next business day
    static getNextBusinessDay(date) {
        const nextDay = new Date(date);
        nextDay.setDate(nextDay.getDate() + 1);
        
        while (nextDay.getDay() === 0 || nextDay.getDay() === 6) {
            nextDay.setDate(nextDay.getDate() + 1);
        }
        
        return nextDay;
    }

    // Check if date is weekend
    static isWeekend(date) {
        const day = new Date(date).getDay();
        return day === 0 || day === 6;
    }

    // Get relative time string
    static getRelativeTime(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffInSeconds = Math.floor((now - date) / 1000);

        if (diffInSeconds < 60) return 'just now';
        if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} minutes ago`;
        if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} hours ago`;
        if (diffInSeconds < 2592000) return `${Math.floor(diffInSeconds / 86400)} days ago`;
        
        return this.formatDate(dateString);
    }
}

// UI utilities
export class UIUtils {
    // Show toast notification
    static showToast(message, type = 'success', duration = 5000) {
        const toast = document.getElementById('toast');
        const toastIcon = document.getElementById('toastIcon');
        const toastMessage = document.getElementById('toastMessage');
        
        if (!toast || !toastIcon || !toastMessage) return;

        toastMessage.textContent = message;
        
        // Reset classes
        toast.className = 'toast';
        toastIcon.className = 'h-5 w-5';
        
        // Set type-specific styles
        const typeConfig = {
            success: {
                class: 'toast-success',
                iconClass: 'text-success-400',
                iconPath: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z'
            },
            error: {
                class: 'toast-error',
                iconClass: 'text-danger-400',
                iconPath: 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'
            },
            warning: {
                class: 'toast-warning',
                iconClass: 'text-warning-400',
                iconPath: 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'
            },
            info: {
                class: 'toast-info',
                iconClass: 'text-primary-400',
                iconPath: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'
            }
        };

        const config = typeConfig[type] || typeConfig.info;
        toast.classList.add(config.class);
        toastIcon.classList.add(config.iconClass);
        toastIcon.innerHTML = `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${config.iconPath}"></path>`;
        
        toast.classList.remove('hidden');
        
        // Auto-hide after duration
        setTimeout(() => {
            toast.classList.add('hidden');
        }, duration);
    }

    // Set loading state for buttons
    static setButtonLoading(button, isLoading, loadingText = 'Loading...', normalText = 'Submit') {
        const textElement = button.querySelector('[data-button-text]') || button.querySelector('span');
        const spinnerElement = button.querySelector('.spinner');
        
        button.disabled = isLoading;
        
        if (textElement) {
            textElement.textContent = isLoading ? loadingText : normalText;
        }
        
        if (spinnerElement) {
            spinnerElement.classList.toggle('hidden', !isLoading);
        }
    }

    // Show/hide modal
    static showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }
    }

    static hideModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('hidden');
            document.body.style.overflow = '';
        }
    }

    // Setup modal close handlers
    static setupModalCloseHandlers(modalId, closeButtonIds = []) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        // Close on backdrop click
        modal.addEventListener('click', (event) => {
            if (event.target === modal) {
                this.hideModal(modalId);
            }
        });

        // Close on close button clicks
        closeButtonIds.forEach(buttonId => {
            const button = document.getElementById(buttonId);
            if (button) {
                button.addEventListener('click', () => this.hideModal(modalId));
            }
        });

        // Close on Escape key
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && !modal.classList.contains('hidden')) {
                this.hideModal(modalId);
            }
        });
    }

    // Animate element
    static animateElement(element, animation = 'fade-in') {
        element.classList.add(animation);
        
        // Remove animation class after animation completes
        setTimeout(() => {
            element.classList.remove(animation);
        }, 500);
    }

    // Debounce function
    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Throttle function
    static throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    // Copy to clipboard
    static async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showToast('Copied to clipboard', 'success');
        } catch (error) {
            console.error('Failed to copy to clipboard:', error);
            this.showToast('Failed to copy to clipboard', 'error');
        }
    }

    // Format file size
    static formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Generate initials from name
    static getInitials(firstName, lastName) {
        return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
    }

    // Validate form fields
    static validateForm(formElement, rules = {}) {
        let isValid = true;
        const errors = {};

        Object.keys(rules).forEach(fieldName => {
            const field = formElement.querySelector(`[name="${fieldName}"]`);
            const rule = rules[fieldName];
            
            if (!field) return;

            const value = field.value.trim();
            
            // Required validation
            if (rule.required && !value) {
                errors[fieldName] = rule.requiredMessage || `${fieldName} is required`;
                isValid = false;
                return;
            }

            // Skip other validations if field is empty and not required
            if (!value && !rule.required) return;

            // Email validation
            if (rule.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
                errors[fieldName] = rule.emailMessage || 'Please enter a valid email address';
                isValid = false;
            }

            // Min length validation
            if (rule.minLength && value.length < rule.minLength) {
                errors[fieldName] = rule.minLengthMessage || `Minimum ${rule.minLength} characters required`;
                isValid = false;
            }

            // Max length validation
            if (rule.maxLength && value.length > rule.maxLength) {
                errors[fieldName] = rule.maxLengthMessage || `Maximum ${rule.maxLength} characters allowed`;
                isValid = false;
            }

            // Custom validation
            if (rule.custom && !rule.custom(value)) {
                errors[fieldName] = rule.customMessage || 'Invalid value';
                isValid = false;
            }
        });

        return { isValid, errors };
    }

    // Show form validation errors
    static showFormErrors(errors) {
        Object.keys(errors).forEach(fieldName => {
            const errorElement = document.getElementById(`${fieldName}Error`);
            const field = document.querySelector(`[name="${fieldName}"]`);
            
            if (errorElement) {
                errorElement.textContent = errors[fieldName];
                errorElement.classList.remove('hidden');
            }
            
            if (field) {
                field.classList.add('border-danger-500');
                field.classList.remove('border-secondary-300');
            }
        });
    }

    // Clear form errors
    static clearFormErrors(formElement) {
        const errorElements = formElement.querySelectorAll('.form-error');
        const inputElements = formElement.querySelectorAll('.form-input');
        
        errorElements.forEach(el => el.classList.add('hidden'));
        inputElements.forEach(el => {
            el.classList.remove('border-danger-500');
            el.classList.add('border-secondary-300');
        });
    }
}

// Local storage utilities
export class StorageUtils {
    // Set item with expiration
    static setItem(key, value, expirationMinutes = null) {
        const item = {
            value,
            timestamp: Date.now(),
            expiration: expirationMinutes ? Date.now() + (expirationMinutes * 60 * 1000) : null
        };
        
        localStorage.setItem(key, JSON.stringify(item));
    }

    // Get item with expiration check
    static getItem(key) {
        const itemStr = localStorage.getItem(key);
        if (!itemStr) return null;

        try {
            const item = JSON.parse(itemStr);
            
            // Check expiration
            if (item.expiration && Date.now() > item.expiration) {
                localStorage.removeItem(key);
                return null;
            }
            
            return item.value;
        } catch (error) {
            console.error('Error parsing stored item:', error);
            localStorage.removeItem(key);
            return null;
        }
    }

    // Remove item
    static removeItem(key) {
        localStorage.removeItem(key);
    }

    // Clear all items
    static clear() {
        localStorage.clear();
    }

    // Get all keys
    static getAllKeys() {
        return Object.keys(localStorage);
    }
}

// Export utilities
export default {
    ApiClient,
    DateUtils,
    UIUtils,
    StorageUtils
};