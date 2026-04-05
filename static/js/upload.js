/**
 * Upload Page JavaScript
 * Handles drag-and-drop, file preview, upload, and processing status polling.
 */

document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const dropzoneContent = document.getElementById('dropzoneContent');
    const filePreview = document.getElementById('filePreview');
    const previewIcon = document.getElementById('previewIcon');
    const previewName = document.getElementById('previewName');
    const previewSize = document.getElementById('previewSize');
    const previewMedia = document.getElementById('previewMedia');
    const removeFile = document.getElementById('removeFile');
    const uploadProgress = document.getElementById('uploadProgress');
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');
    const progressLabel = document.getElementById('progressLabel');
    const progressDetail = document.getElementById('progressDetail');
    const uploadActions = document.getElementById('uploadActions');
    const startAnalysis = document.getElementById('startAnalysis');
    const processingOverlay = document.getElementById('processingOverlay');
    const processingBar = document.getElementById('processingBar');
    const processingPercent = document.getElementById('processingPercent');
    const processingStatus = document.getElementById('processingStatus');
    const procElapsed = document.getElementById('procElapsed');
    const procFrames = document.getElementById('procFrames');

    let selectedFile = null;
    let jobId = null;
    let pollInterval = null;
    let elapsedTimer = null;
    let elapsedSeconds = 0;

    const IMAGE_EXT = ['.jpg', '.jpeg', '.png', '.bmp', '.webp'];
    const VIDEO_EXT = ['.mp4', '.avi', '.mov', '.mkv', '.wmv'];

    // ── Drop Zone Events ───────────────────────────────────────
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) handleFile(files[0]);
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) handleFile(fileInput.files[0]);
    });

    removeFile.addEventListener('click', (e) => {
        e.stopPropagation();
        resetUpload();
    });

    startAnalysis.addEventListener('click', () => {
        if (selectedFile) uploadFile(selectedFile);
    });

    // ── Handle File Selection ──────────────────────────────────
    function handleFile(file) {
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        const allExt = [...IMAGE_EXT, ...VIDEO_EXT];

        if (!allExt.includes(ext)) {
            alert('Unsupported file format. Please upload JPG, PNG, MP4, AVI, or MOV files.');
            return;
        }

        if (file.size > 500 * 1024 * 1024) {
            alert('File too large. Maximum size is 500MB.');
            return;
        }

        selectedFile = file;
        const isVideo = VIDEO_EXT.includes(ext);

        // Update preview
        dropzoneContent.style.display = 'none';
        filePreview.style.display = 'block';
        uploadActions.style.display = 'block';

        previewName.textContent = file.name;
        previewSize.textContent = formatFileSize(file.size);
        previewIcon.className = isVideo ? 'fas fa-video preview-file-icon' : 'fas fa-image preview-file-icon';

        // Show media preview
        previewMedia.innerHTML = '';
        const url = URL.createObjectURL(file);

        if (isVideo) {
            const video = document.createElement('video');
            video.src = url;
            video.controls = true;
            video.muted = true;
            video.style.maxWidth = '100%';
            video.style.maxHeight = '320px';
            video.style.borderRadius = '8px';
            previewMedia.appendChild(video);
        } else {
            const img = document.createElement('img');
            img.src = url;
            img.style.maxWidth = '100%';
            img.style.maxHeight = '320px';
            img.style.borderRadius = '8px';
            previewMedia.appendChild(img);
        }
    }

    // ── Upload File ────────────────────────────────────────────
    function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        uploadActions.style.display = 'none';
        uploadProgress.style.display = 'block';
        progressLabel.textContent = 'Uploading...';
        progressDetail.textContent = 'Sending file to server...';

        const xhr = new XMLHttpRequest();

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = percent + '%';
                progressPercent.textContent = percent + '%';
                progressDetail.textContent = `${formatFileSize(e.loaded)} / ${formatFileSize(e.total)}`;
            }
        });

        xhr.addEventListener('load', () => {
            if (xhr.status === 200) {
                const data = JSON.parse(xhr.responseText);
                jobId = data.job_id;
                progressLabel.textContent = 'Upload complete!';
                progressDetail.textContent = 'Starting AI analysis...';

                setTimeout(() => {
                    uploadProgress.style.display = 'none';
                    showProcessing();
                    startPolling();
                }, 800);
            } else {
                progressLabel.textContent = 'Upload failed';
                try {
                    const err = JSON.parse(xhr.responseText);
                    progressDetail.textContent = err.error || 'Unknown error';
                } catch {
                    progressDetail.textContent = 'Server error';
                }
            }
        });

        xhr.addEventListener('error', () => {
            progressLabel.textContent = 'Upload failed';
            progressDetail.textContent = 'Network error. Please try again.';
        });

        xhr.open('POST', '/api/upload');
        xhr.send(formData);
    }

    // ── Processing Overlay ─────────────────────────────────────
    function showProcessing() {
        processingOverlay.style.display = 'flex';
        elapsedSeconds = 0;
        elapsedTimer = setInterval(() => {
            elapsedSeconds++;
            procElapsed.textContent = elapsedSeconds + 's';
        }, 1000);
    }

    function hideProcessing() {
        processingOverlay.style.display = 'none';
        if (elapsedTimer) clearInterval(elapsedTimer);
    }

    // ── Poll for Status ────────────────────────────────────────
    function startPolling() {
        pollInterval = setInterval(async () => {
            try {
                const res = await fetch(`/api/status/${jobId}`);
                const data = await res.json();

                if (data.status === 'processing') {
                    const pct = data.progress || 0;
                    processingBar.style.width = pct + '%';
                    processingPercent.textContent = pct + '%';
                    processingStatus.textContent = data.message || 'Analyzing...';
                    procFrames.textContent = data.message || '--';
                } else if (data.status === 'completed') {
                    clearInterval(pollInterval);
                    processingBar.style.width = '100%';
                    processingPercent.textContent = '100%';
                    processingStatus.textContent = 'Analysis complete! Redirecting...';

                    setTimeout(() => {
                        hideProcessing();
                        window.location.href = `/results/${jobId}`;
                    }, 1200);
                } else if (data.status === 'error') {
                    clearInterval(pollInterval);
                    hideProcessing();
                    alert('Processing error: ' + (data.error || 'Unknown error'));
                    resetUpload();
                }
            } catch (e) {
                console.error('Poll error:', e);
            }
        }, 1000);
    }

    // ── Reset ──────────────────────────────────────────────────
    function resetUpload() {
        selectedFile = null;
        fileInput.value = '';
        dropzoneContent.style.display = 'block';
        filePreview.style.display = 'none';
        uploadActions.style.display = 'none';
        uploadProgress.style.display = 'none';
        progressBar.style.width = '0%';
        progressPercent.textContent = '0%';
        previewMedia.innerHTML = '';
    }
});
