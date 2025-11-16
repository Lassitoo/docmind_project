// Upload Handler for Document Actions

document.addEventListener('DOMContentLoaded', function() {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const browseBtn = document.getElementById('browseBtn');
    const selectedFilesDiv = document.getElementById('selectedFiles');
    const uploadForm = document.getElementById('uploadForm');
    let selectedFiles = [];

    // Browse button click
    browseBtn.addEventListener('click', function() {
        fileInput.click();
    });

    // Upload zone click
    uploadZone.addEventListener('click', function(e) {
        if (e.target !== browseBtn) {
            fileInput.click();
        }
    });

    // File input change
    fileInput.addEventListener('change', function(e) {
        handleFiles(e.target.files);
    });

    // Drag and drop
    uploadZone.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', function(e) {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });

    function handleFiles(files) {
        selectedFiles = Array.from(files).filter(file => {
            return file.name.endsWith('.pdf') || file.name.endsWith('.zip');
        });

        displaySelectedFiles();
    }

    function displaySelectedFiles() {
        selectedFilesDiv.innerHTML = '';
        
        if (selectedFiles.length === 0) {
            selectedFilesDiv.innerHTML = '<p class="text-muted small">Aucun fichier sélectionné</p>';
            return;
        }

        selectedFiles.forEach((file, index) => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            fileItem.innerHTML = `
                <span><i class="fas fa-file-pdf me-2"></i>${file.name}</span>
                <i class="fas fa-times remove-file" data-index="${index}"></i>
            `;
            selectedFilesDiv.appendChild(fileItem);
        });

        // Remove file listeners
        document.querySelectorAll('.remove-file').forEach(btn => {
            btn.addEventListener('click', function() {
                const index = parseInt(this.getAttribute('data-index'));
                selectedFiles.splice(index, 1);
                displaySelectedFiles();
            });
        });
    }

    // Form submission
    uploadForm.addEventListener('submit', function(e) {
        if (selectedFiles.length === 0) {
            e.preventDefault();
            alert('Veuillez sélectionner au moins un fichier');
            return;
        }

        // Create new FileList with selected files
        const dataTransfer = new DataTransfer();
        selectedFiles.forEach(file => {
            dataTransfer.items.add(file);
        });
        fileInput.files = dataTransfer.files;
    });
});