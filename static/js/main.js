// FICHIER: static/js/main.js
// JAVASCRIPT PRINCIPAL POUR DOCMIND
// ============================================

// Attendre que le DOM soit chargé
document.addEventListener('DOMContentLoaded', function() {

    // Auto-hide alerts après 5 secondes
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Confirmation de suppression
    const deleteButtons = document.querySelectorAll('[data-confirm-delete]');
    deleteButtons.forEach(function(button) {
        button.addEventListener('click', function(e) {
            if (!confirm('Êtes-vous sûr de vouloir supprimer cet élément ?')) {
                e.preventDefault();
            }
        });
    });

    // File upload drag and drop
    const fileInput = document.getElementById('id_file');
    if (fileInput) {
        const dropZone = document.createElement('div');
        dropZone.className = 'file-upload-zone mb-3';
        dropZone.innerHTML = '<i class="bi bi-cloud-upload display-4 text-muted"></i><p class="mt-2">Glissez-déposez votre fichier ici ou cliquez pour parcourir</p>';

        if (fileInput.parentNode) {
            fileInput.parentNode.insertBefore(dropZone, fileInput);
            fileInput.style.display = 'none';
        }

        // Click to upload
        dropZone.addEventListener('click', function() {
            fileInput.click();
        });

        // Drag and drop handlers
        dropZone.addEventListener('dragover', function(e) {
            e.preventDefault();
            dropZone.classList.add('dragging');
        });

        dropZone.addEventListener('dragleave', function() {
            dropZone.classList.remove('dragging');
        });

        dropZone.addEventListener('drop', function(e) {
            e.preventDefault();
            dropZone.classList.remove('dragging');

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                fileInput.files = files;
                updateFileLabel(files[0].name);
            }
        });

        // Update label when file is selected
        fileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                updateFileLabel(this.files[0].name);
            }
        });

        function updateFileLabel(filename) {
            dropZone.innerHTML = '<i class="bi bi-file-check display-4 text-success"></i><p class="mt-2">' + filename + '</p>';
        }
    }

    // Tooltips Bootstrap
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Popovers Bootstrap
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});

// Fonction utilitaire pour copier du texte
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showToast('Copié dans le presse-papiers!', 'success');
    }, function() {
        showToast('Erreur lors de la copie', 'danger');
    });
}

// Afficher un toast message
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        const container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '11';
        document.body.appendChild(container);
    }

    const toastHTML = `
        <div class="toast align-items-center text-white bg-${type} border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;

    const toastElement = document.createElement('div');
    toastElement.innerHTML = toastHTML;
    document.getElementById('toastContainer').appendChild(toastElement.firstElementChild);

    const toast = new bootstrap.Toast(toastElement.firstElementChild);
    toast.show();

    // Remove toast after it's hidden
    toastElement.firstElementChild.addEventListener('hidden.bs.toast', function() {
        this.remove();
    });
}

// Fonction pour loader
function showLoader(element) {
    if (typeof element === 'string') {
        element = document.querySelector(element);
    }
    if (element) {
        element.innerHTML = '<div class="spinner-wrapper"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Chargement...</span></div></div>';
    }
}

// AJAX helper
function ajaxRequest(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        }
    };

    // Add CSRF token for POST requests
    if (method !== 'GET') {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfToken) {
            options.headers['X-CSRFToken'] = csrfToken.value;
        }
    }

    // Add data for POST requests
    if (data && method !== 'GET') {
        if (data instanceof FormData) {
            options.body = data;
        } else {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(data);
        }
    }

    return fetch(url, options)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        });
}

// Export functions for global use
window.DocMind = {
    copyToClipboard,
    showToast,
    showLoader,
    ajaxRequest
};
