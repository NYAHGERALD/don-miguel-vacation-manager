// Authentication utilities for Don Miguel Vacation Manager
// Firebase Authentication helper functions

import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js';
import { 
    getAuth, 
    signInWithEmailAndPassword, 
    createUserWithEmailAndPassword,
    signInWithPopup, 
    GoogleAuthProvider,
    signOut,
    onAuthStateChanged,
    updateProfile
} from 'https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js';

// Firebase configuration
const firebaseConfig = {
    apiKey: "your-api-key-here",
    authDomain: "your-project-id.firebaseapp.com",
    projectId: "your-project-id",
    storageBucket: "your-project-id.appspot.com",
    messagingSenderId: "123456789",
    appId: "your-app-id-here"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();

// Configure Google Auth Provider
googleProvider.setCustomParameters({
    prompt: 'select_account'
});

// Authentication state management
export class AuthManager {
    constructor() {
        this.currentUser = null;
        this.authStateCallbacks = [];
    }

    // Add auth state change callback
    onAuthStateChange(callback) {
        this.authStateCallbacks.push(callback);
        
        // Set up Firebase auth state listener
        onAuthStateChanged(auth, (user) => {
            this.currentUser = user;
            this.authStateCallbacks.forEach(cb => cb(user));
        });
    }

    // Sign in with email and password
    async signInWithEmail(email, password) {
        try {
            const userCredential = await signInWithEmailAndPassword(auth, email, password);
            const idToken = await userCredential.user.getIdToken();
            localStorage.setItem('authToken', idToken);
            return userCredential.user;
        } catch (error) {
            throw this.handleAuthError(error);
        }
    }

    // Sign up with email and password
    async signUpWithEmail(email, password, additionalData = {}) {
        try {
            const userCredential = await createUserWithEmailAndPassword(auth, email, password);
            
            // Update profile if display name provided
            if (additionalData.displayName) {
                await updateProfile(userCredential.user, {
                    displayName: additionalData.displayName
                });
            }

            const idToken = await userCredential.user.getIdToken();
            localStorage.setItem('authToken', idToken);
            return userCredential.user;
        } catch (error) {
            throw this.handleAuthError(error);
        }
    }

    // Sign in with Google
    async signInWithGoogle() {
        try {
            const result = await signInWithPopup(auth, googleProvider);
            const idToken = await result.user.getIdToken();
            localStorage.setItem('authToken', idToken);
            return result.user;
        } catch (error) {
            throw this.handleAuthError(error);
        }
    }

    // Sign out
    async signOut() {
        try {
            await signOut(auth);
            localStorage.removeItem('authToken');
        } catch (error) {
            console.error('Sign out error:', error);
            throw error;
        }
    }

    // Get current user token
    async getCurrentUserToken() {
        if (!this.currentUser) {
            throw new Error('No authenticated user');
        }
        return await this.currentUser.getIdToken();
    }

    // Check if user is authenticated
    isAuthenticated() {
        return !!this.currentUser;
    }

    // Get user info for UI
    getUserInfo() {
        if (!this.currentUser) return null;

        const displayName = this.currentUser.displayName || 'User';
        const email = this.currentUser.email || '';
        const names = displayName.split(' ');
        const initials = names.map(name => name.charAt(0)).join('').toUpperCase().substring(0, 2);

        return {
            uid: this.currentUser.uid,
            email,
            displayName,
            initials,
            photoURL: this.currentUser.photoURL
        };
    }

    // Handle authentication errors
    handleAuthError(error) {
        let errorMessage = 'An authentication error occurred.';
        
        switch (error.code) {
            case 'auth/user-not-found':
                errorMessage = 'No account found with this email address.';
                break;
            case 'auth/wrong-password':
                errorMessage = 'Incorrect password.';
                break;
            case 'auth/invalid-email':
                errorMessage = 'Invalid email address.';
                break;
            case 'auth/user-disabled':
                errorMessage = 'This account has been disabled.';
                break;
            case 'auth/too-many-requests':
                errorMessage = 'Too many failed attempts. Please try again later.';
                break;
            case 'auth/email-already-in-use':
                errorMessage = 'An account with this email already exists.';
                break;
            case 'auth/weak-password':
                errorMessage = 'Password is too weak. Please choose a stronger password.';
                break;
            case 'auth/popup-closed-by-user':
                errorMessage = 'Sign-in was cancelled.';
                break;
            case 'auth/popup-blocked':
                errorMessage = 'Pop-up was blocked. Please allow pop-ups and try again.';
                break;
            case 'auth/account-exists-with-different-credential':
                errorMessage = 'An account already exists with this email using a different sign-in method.';
                break;
            default:
                errorMessage = error.message || errorMessage;
        }

        return new Error(errorMessage);
    }

    // Redirect to login if not authenticated
    requireAuth(redirectUrl = '/login') {
        if (!this.isAuthenticated()) {
            window.location.href = redirectUrl;
            return false;
        }
        return true;
    }

    // Redirect to dashboard if already authenticated
    redirectIfAuthenticated(redirectUrl = '/dashboard') {
        if (this.isAuthenticated()) {
            window.location.href = redirectUrl;
            return true;
        }
        return false;
    }
}

// Create global auth manager instance
export const authManager = new AuthManager();

// Password strength checker
export class PasswordStrengthChecker {
    static check(password) {
        const requirements = {
            length: password.length >= 8,
            uppercase: /[A-Z]/.test(password),
            lowercase: /[a-z]/.test(password),
            number: /\d/.test(password),
            special: /[!@#$%^&*(),.?":{}|<>]/.test(password)
        };

        const score = Object.values(requirements).filter(Boolean).length;
        let strength = 'weak';
        let color = 'danger';

        if (score >= 4) {
            strength = 'strong';
            color = 'success';
        } else if (score >= 3) {
            strength = 'good';
            color = 'warning';
        }

        return {
            requirements,
            score,
            strength,
            color,
            percentage: (score / 5) * 100
        };
    }

    static updateUI(password, strengthElement, textElement, requirementsElement) {
        const result = this.check(password);
        
        // Update strength bar
        strengthElement.style.width = `${result.percentage}%`;
        strengthElement.className = `h-2 rounded-full transition-all duration-300 bg-${result.color}-500`;
        
        // Update strength text
        textElement.textContent = result.strength.charAt(0).toUpperCase() + result.strength.slice(1);
        textElement.className = `text-xs text-${result.color}-600`;
        
        // Update requirements if provided
        if (requirementsElement) {
            Object.keys(result.requirements).forEach(req => {
                const element = requirementsElement.querySelector(`#req-${req}`);
                if (element) {
                    const svg = element.querySelector('svg');
                    if (result.requirements[req]) {
                        svg.classList.remove('text-secondary-400');
                        svg.classList.add('text-success-500');
                    } else {
                        svg.classList.remove('text-success-500');
                        svg.classList.add('text-secondary-400');
                    }
                }
            });
        }
    }
}

// Form validation utilities
export class FormValidator {
    static validateEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    static validatePhone(phone) {
        const phoneRegex = /^\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})$/;
        return phoneRegex.test(phone);
    }

    static validateRequired(value) {
        return value && value.trim().length > 0;
    }

    static validateLength(value, minLength, maxLength = null) {
        if (!value) return false;
        if (value.length < minLength) return false;
        if (maxLength && value.length > maxLength) return false;
        return true;
    }

    static showFieldError(fieldId, message) {
        const field = document.getElementById(fieldId);
        const errorElement = document.getElementById(`${fieldId}Error`);
        
        if (field) {
            field.classList.add('border-danger-500', 'focus:border-danger-500', 'focus:ring-danger-500');
            field.classList.remove('border-secondary-300', 'focus:border-primary-500', 'focus:ring-primary-500');
        }
        
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.classList.remove('hidden');
        }
    }

    static clearFieldError(fieldId) {
        const field = document.getElementById(fieldId);
        const errorElement = document.getElementById(`${fieldId}Error`);
        
        if (field) {
            field.classList.remove('border-danger-500', 'focus:border-danger-500', 'focus:ring-danger-500');
            field.classList.add('border-secondary-300', 'focus:border-primary-500', 'focus:ring-primary-500');
        }
        
        if (errorElement) {
            errorElement.classList.add('hidden');
        }
    }

    static clearAllErrors(formElement) {
        const errorElements = formElement.querySelectorAll('.form-error');
        const inputElements = formElement.querySelectorAll('.form-input');
        
        errorElements.forEach(el => el.classList.add('hidden'));
        inputElements.forEach(el => {
            el.classList.remove('border-danger-500', 'focus:border-danger-500', 'focus:ring-danger-500');
            el.classList.add('border-secondary-300', 'focus:border-primary-500', 'focus:ring-primary-500');
        });
    }
}

// Export default auth manager
export default authManager;