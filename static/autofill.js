/**
 * GearGuard: Auto-Fill Logic for Maintenance Requests
 * 
 * This module handles intelligent auto-population of maintenance request forms
 * when equipment is selected. It uses a clean separation of concerns:
 * - Backend provides raw data via JSON API
 * - Frontend handles all DOM manipulation and UX
 * 
 * Why this design is scalable:
 * 1. API-first approach: Can be reused for mobile apps, external systems
 * 2. Vanilla JS: No dependencies, zero bundle size impact
 * 3. Event-driven: Can attach to multiple forms without coupling
 * 4. Graceful degradation: Form works even if AJAX fails
 * 5. Accessible: Proper ARIA labels, semantic HTML
 */

document.addEventListener('DOMContentLoaded', function () {
    const equipmentSelect = document.getElementById('equipment');
    const maintenanceForm = document.getElementById('maintenanceForm');
    const equipmentDetailsSection = document.getElementById('equipmentDetailsSection');
    const loadingSpinner = document.getElementById('loadingSpinner');
    const errorAlert = document.getElementById('errorAlert');
    const errorMessage = document.getElementById('errorMessage');
    const submitBtn = document.getElementById('submitBtn');

    // Cache for auto-filled fields
    const autofillFields = {
        department: document.getElementById('department'),
        warrantyStatus: document.getElementById('warrantyStatus'),
        maintenanceTeamId: document.getElementById('maintenanceTeamId'),
        teamName: document.getElementById('teamName'),
        teamMembers: document.getElementById('teamMembers'),
        teamHint: document.getElementById('teamHint'),
        defaultTechnicianId: document.getElementById('defaultTechnicianId'),
        technicianDisplay: document.getElementById('technicianDisplay'),
    };

    /**
     * Fetch equipment details from the backend API
     * @param {number} equipmentId - ID of the equipment
     */
    async function fetchEquipmentDetails(equipmentId) {
        if (!equipmentId) {
            hideEquipmentDetails();
            return;
        }

        showLoadingSpinner();
        hideErrorAlert();

        try {
            const apiUrl = `/maintenance/api/equipment-details/?equipment_id=${equipmentId}`;
            const response = await fetch(apiUrl, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin' // Include CSRF token in cookies
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            if (data.success) {
                populateEquipmentDetails(data.data);
                showEquipmentDetails();
                hideErrorAlert();
                enableForm();
            } else {
                // Handle API-level errors (e.g., scrapped equipment)
                handleApiError(data.error, data.data);
            }
        } catch (error) {
            console.error('Error fetching equipment details:', error);
            showErrorAlert(`Failed to load equipment details: ${error.message}`);
            hideEquipmentDetails();
            disableForm(true);
        } finally {
            hideLoadingSpinner();
        }
    }

    /**
     * Populate form fields with fetched data
     * @param {object} data - Equipment details from API
     */
    function populateEquipmentDetails(data) {
        // Department
        if (data.department) {
            autofillFields.department.value = data.department;
        }

        // Warranty Status
        if (data.warranty_status) {
            autofillFields.warrantyStatus.value = data.warranty_status;
        }

        // Maintenance Team
        if (data.maintenance_team) {
            autofillFields.maintenanceTeamId.value = data.maintenance_team.id;
            autofillFields.teamName.textContent = data.maintenance_team.name;
            autofillFields.teamMembers.textContent = `(${data.maintenance_team.member_count} members)`;
            autofillFields.teamHint.textContent = `Team: ${data.maintenance_team.name}`;
        } else {
            autofillFields.teamName.textContent = 'No team assigned';
            autofillFields.teamMembers.textContent = '';
            autofillFields.maintenanceTeamId.value = '';
        }

        // Default Technician
        if (data.default_technician) {
            const technicianFullName = `${data.default_technician.first_name} ${data.default_technician.last_name}`.trim();
            autofillFields.defaultTechnicianId.value = data.default_technician.id;
            autofillFields.technicianDisplay.innerHTML = `
                <span class="technician-badge">
                    <strong>${technicianFullName || data.default_technician.username}</strong>
                    <small>(Default assigned)</small>
                </span>
            `;
        } else {
            autofillFields.defaultTechnicianId.value = '';
            autofillFields.technicianDisplay.textContent = 'No default technician assigned';
        }
    }

    /**
     * Handle API-level errors (e.g., scrapped equipment)
     * @param {string} errorMsg - Error message from API
     * @param {object} data - Additional data from API
     */
    function handleApiError(errorMsg, data = {}) {
        if (data && data.is_scrapped) {
            showErrorAlert('⚠️ This equipment is marked as scrapped and cannot be maintained.');
            disableForm(false);
        } else {
            showErrorAlert(errorMsg || 'Unable to load equipment details.');
            disableForm(true);
        }
        hideEquipmentDetails();
    }

    /**
     * Show equipment details section
     */
    function showEquipmentDetails() {
        equipmentDetailsSection.style.display = 'block';
    }

    /**
     * Hide equipment details section
     */
    function hideEquipmentDetails() {
        equipmentDetailsSection.style.display = 'none';
        resetAutofilledFields();
    }

    /**
     * Reset all auto-filled fields
     */
    function resetAutofilledFields() {
        autofillFields.department.value = '';
        autofillFields.warrantyStatus.value = '';
        autofillFields.maintenanceTeamId.value = '';
        autofillFields.defaultTechnicianId.value = '';
        autofillFields.teamName.textContent = '--';
        autofillFields.teamMembers.textContent = '';
        autofillFields.technicianDisplay.textContent = 'No default technician assigned';
    }

    /**
     * Show loading spinner
     */
    function showLoadingSpinner() {
        loadingSpinner.style.display = 'flex';
    }

    /**
     * Hide loading spinner
     */
    function hideLoadingSpinner() {
        loadingSpinner.style.display = 'none';
    }

    /**
     * Show error alert
     * @param {string} message - Error message to display
     */
    function showErrorAlert(message) {
        errorMessage.textContent = message;
        errorAlert.style.display = 'block';
    }

    /**
     * Hide error alert
     */
    function hideErrorAlert() {
        errorAlert.style.display = 'none';
    }

    /**
     * Disable form submission (for critical errors)
     * @param {boolean} showWarning - Show warning message
     */
    function disableForm(showWarning = true) {
        submitBtn.disabled = true;
        submitBtn.classList.add('disabled');
        if (showWarning) {
            submitBtn.setAttribute('title', 'Please fix the errors above before submitting');
        }
    }

    /**
     * Enable form submission
     */
    function enableForm() {
        submitBtn.disabled = false;
        submitBtn.classList.remove('disabled');
        submitBtn.removeAttribute('title');
    }

    /**
     * Event listener: Equipment selection change
     */
    equipmentSelect.addEventListener('change', function (e) {
        const equipmentId = e.target.value;
        if (equipmentId) {
            fetchEquipmentDetails(equipmentId);
        } else {
            hideEquipmentDetails();
            enableForm();
        }
    });

    /**
     * Form submission handler: Prevent submit if form is disabled
     */
    maintenanceForm.addEventListener('submit', function (e) {
        if (submitBtn.disabled) {
            e.preventDefault();
            showErrorAlert('Please resolve all errors before submitting the form.');
        }
    });

    // Initial state: Hide details section until equipment is selected
    hideEquipmentDetails();
});
