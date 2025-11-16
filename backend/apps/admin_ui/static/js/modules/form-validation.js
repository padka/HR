/**
 * Form Validation Module
 * Provides inline error messages and real-time validation
 *
 * WCAG 2.1 Compliance:
 * - 3.3.1 Error Identification (Level A)
 * - 3.3.3 Error Suggestion (Level AA)
 */
(function() {
  'use strict';

  // Error messages in Russian
  const ERROR_MESSAGES = {
    valueMissing: 'Это поле обязательно для заполнения',
    typeMismatch: {
      email: 'Введите корректный email адрес',
      url: 'Введите корректный URL',
      tel: 'Введите корректный номер телефона'
    },
    tooShort: 'Значение слишком короткое (минимум {min} символов)',
    tooLong: 'Значение слишком длинное (максимум {max} символов)',
    rangeUnderflow: 'Значение должно быть не менее {min}',
    rangeOverflow: 'Значение должно быть не более {max}',
    patternMismatch: 'Значение не соответствует требуемому формату',
    badInput: 'Введите корректное значение'
  };

  /**
   * Get error message for input based on validity state
   * @param {HTMLInputElement|HTMLSelectElement|HTMLTextAreaElement} input
   * @returns {string}
   */
  function getErrorMessage(input) {
    const validity = input.validity;

    if (validity.valueMissing) {
      return ERROR_MESSAGES.valueMissing;
    }
    if (validity.typeMismatch) {
      return ERROR_MESSAGES.typeMismatch[input.type] || 'Некорректное значение';
    }
    if (validity.tooShort) {
      return ERROR_MESSAGES.tooShort.replace('{min}', input.minLength);
    }
    if (validity.tooLong) {
      return ERROR_MESSAGES.tooLong.replace('{max}', input.maxLength);
    }
    if (validity.rangeUnderflow) {
      return ERROR_MESSAGES.rangeUnderflow.replace('{min}', input.min);
    }
    if (validity.rangeOverflow) {
      return ERROR_MESSAGES.rangeOverflow.replace('{max}', input.max);
    }
    if (validity.patternMismatch) {
      // Use title attribute if provided for custom pattern error
      return input.title || ERROR_MESSAGES.patternMismatch;
    }
    if (validity.badInput) {
      return ERROR_MESSAGES.badInput;
    }

    return 'Проверьте правильность введенных данных';
  }

  /**
   * Show error for field with accessibility support
   * @param {HTMLElement} field - The .form-field container
   * @param {string} message - Error message to display
   */
  function showError(field, message) {
    field.classList.add('form-field--error');
    field.classList.remove('form-field--success');

    let errorElement = field.querySelector('.form-field__error');
    if (!errorElement) {
      errorElement = document.createElement('div');
      errorElement.className = 'form-field__error';
      errorElement.setAttribute('role', 'alert');
      errorElement.setAttribute('aria-live', 'polite');
      field.appendChild(errorElement);
    }

    errorElement.textContent = message;

    // Update aria-invalid on the input
    const input = field.querySelector('input, select, textarea');
    if (input) {
      input.setAttribute('aria-invalid', 'true');
      input.setAttribute('aria-describedby', errorElement.id || generateErrorId(input));
      if (!errorElement.id) {
        errorElement.id = generateErrorId(input);
      }
    }
  }

  /**
   * Clear error for field
   * @param {HTMLElement} field - The .form-field container
   */
  function clearError(field) {
    field.classList.remove('form-field--error');

    const errorElement = field.querySelector('.form-field__error');
    if (errorElement) {
      errorElement.textContent = '';
    }

    // Update aria-invalid on the input
    const input = field.querySelector('input, select, textarea');
    if (input) {
      input.setAttribute('aria-invalid', 'false');
      input.removeAttribute('aria-describedby');
    }
  }

  /**
   * Mark field as valid (show success state)
   * @param {HTMLElement} field - The .form-field container
   */
  function markValid(field) {
    field.classList.add('form-field--success');
    field.classList.remove('form-field--error');
    clearError(field);
  }

  /**
   * Generate unique error ID for aria-describedby
   * @param {HTMLElement} input
   * @returns {string}
   */
  function generateErrorId(input) {
    const inputId = input.id || input.name || 'field';
    return `${inputId}-error`;
  }

  /**
   * Validate single input and show/hide errors
   * @param {HTMLInputElement|HTMLSelectElement|HTMLTextAreaElement} input
   * @returns {boolean} - true if valid, false if invalid
   */
  function validateInput(input) {
    const field = input.closest('.form-field');
    if (!field) return true;

    // Skip validation if field is not required and empty
    if (!input.required && !input.value.trim()) {
      clearError(field);
      field.classList.remove('form-field--success');
      return true;
    }

    if (!input.checkValidity()) {
      const message = getErrorMessage(input);
      showError(field, message);
      return false;
    } else {
      // Mark as valid only if required or has value
      if (input.required || input.value.trim()) {
        markValid(field);
      }
      return true;
    }
  }

  /**
   * Initialize form validation with event listeners
   * @param {HTMLFormElement} form
   */
  function initFormValidation(form) {
    const inputs = form.querySelectorAll('input, select, textarea');

    // Validate on blur (when user leaves field)
    inputs.forEach(input => {
      input.addEventListener('blur', () => {
        validateInput(input);
      });

      // Clear error on input (after user starts fixing)
      // Debounced re-validation after user stops typing
      let inputTimeout;
      input.addEventListener('input', () => {
        const field = input.closest('.form-field');
        if (field && field.classList.contains('form-field--error')) {
          // Clear timeout and set new one
          clearTimeout(inputTimeout);
          inputTimeout = setTimeout(() => {
            validateInput(input);
          }, 300);
        }
      });
    });

    // Validate all fields on submit
    form.addEventListener('submit', (e) => {
      let hasErrors = false;
      let firstErrorField = null;

      inputs.forEach(input => {
        if (!validateInput(input)) {
          hasErrors = true;
          if (!firstErrorField) {
            firstErrorField = input;
          }
        }
      });

      if (hasErrors) {
        e.preventDefault();

        // Focus first error field and scroll to it
        if (firstErrorField) {
          firstErrorField.focus();

          // Smooth scroll to first error with offset for fixed header
          const yOffset = -120; // Offset for fixed header
          const y = firstErrorField.getBoundingClientRect().top + window.pageYOffset + yOffset;

          window.scrollTo({
            top: y,
            behavior: 'smooth'
          });
        }

        // Announce errors to screen readers
        announceErrors(inputs);
      }
    });
  }

  /**
   * Announce validation errors to screen readers
   * @param {NodeList} inputs
   */
  function announceErrors(inputs) {
    const errorCount = Array.from(inputs).filter(input => !input.checkValidity()).length;

    if (errorCount === 0) return;

    // Create or update announcement element
    let announcer = document.getElementById('form-validation-announcer');
    if (!announcer) {
      announcer = document.createElement('div');
      announcer.id = 'form-validation-announcer';
      announcer.setAttribute('role', 'status');
      announcer.setAttribute('aria-live', 'polite');
      announcer.style.position = 'absolute';
      announcer.style.left = '-10000px';
      announcer.style.width = '1px';
      announcer.style.height = '1px';
      announcer.style.overflow = 'hidden';
      document.body.appendChild(announcer);
    }

    const message = errorCount === 1
      ? 'Обнаружена 1 ошибка в форме. Пожалуйста, исправьте ее.'
      : `Обнаружено ${errorCount} ошибок в форме. Пожалуйста, исправьте их.`;

    announcer.textContent = message;
  }

  /**
   * Initialize all forms on page with data-validate="true"
   */
  function init() {
    const forms = document.querySelectorAll('form[data-validate="true"]');
    forms.forEach(form => initFormValidation(form));
  }

  // Auto-initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Export for manual initialization and testing
  window.FormValidation = {
    init,
    initFormValidation,
    validateInput,
    showError,
    clearError,
    markValid
  };
})();
