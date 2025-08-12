class Notification {
    constructor(type, message) {
        this.type = type;
        this.message = message;
        this.element = this.createNotification();
        this.show();
    }

    createNotification() {
        const notification = document.createElement('div');
        notification.className = `notification ${this.type}`;
        
        const icon = this.getIcon(this.type);
        notification.innerHTML = `
            <div style="display: flex; align-items: center; gap: 0.75rem;">
                <i class="${icon}" style="font-size: 1.2rem;"></i>
                <span>${this.message}</span>
            </div>
        `;
        return notification;
    }

    getIcon(type) {
        switch(type) {
            case 'success': return 'fas fa-check-circle';
            case 'error': return 'fas fa-exclamation-circle';
            case 'info': return 'fas fa-info-circle';
            default: return 'fas fa-bell';
        }
    }

    show() {
        const notifications = document.getElementById('notifications');
        notifications.appendChild(this.element);
        
        // Remove notification after 6 seconds
        setTimeout(() => {
            this.element.style.transform = 'translateX(100%)';
            this.element.style.opacity = '0';
            setTimeout(() => {
                if (this.element.parentNode) {
                    this.element.remove();
                }
            }, 300);
        }, 6000);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Initialize theme
    initializeTheme();
    
    // Initialize download history
    loadDownloadHistory();

    // Tab switching
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.tab;
            
            // Remove active class from all tabs
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Add active class to selected tab and content
            btn.classList.add('active');
            document.getElementById(targetId).classList.add('active');
        });
    });

    // Video converter
    const convertForm = document.getElementById('convert-form');
    const videoFileInput = document.getElementById('video-file');
    const uploadZone = document.getElementById('upload-zone');
    const progressContainer = document.getElementById('progress-container');
    const progressFill = document.getElementById('progress-fill');

    // Upload zone click handler
    uploadZone.addEventListener('click', () => {
        videoFileInput.click();
    });

    // File input change handler
    videoFileInput.addEventListener('change', (e) => {
        const files = e.target.files;
        if (files.length > 0) {
            updateUploadZoneContent(files);
        }
    });

    // Drag and drop functionality
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.style.borderColor = 'rgba(102, 126, 234, 0.5)';
        uploadZone.style.backgroundColor = 'rgba(102, 126, 234, 0.05)';
    });

    uploadZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadZone.style.borderColor = '';
        uploadZone.style.backgroundColor = '';
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.style.borderColor = '';
        uploadZone.style.backgroundColor = '';
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            videoFileInput.files = files;
            updateUploadZoneContent(files);
        }
    });

    function updateUploadZoneContent(files) {
        const uploadContent = uploadZone.querySelector('.upload-content');
        const fileList = Array.from(files).map(file => 
            `<div style="margin: 0.25rem 0; color: #667eea;">${file.name}</div>`
        ).join('');
        
        uploadContent.innerHTML = `
            <div class="upload-icon">
                <i class="fas fa-file-video"></i>
            </div>
            <h3>Files Selected</h3>
            <div style="margin: 1rem 0;">${fileList}</div>
            <p style="font-size: 0.875rem; color: var(--text-muted);">
                Click to select different files or drag new ones
            </p>
        `;
    }

    function showProgress(show = true) {
        if (show) {
            progressContainer.style.display = 'block';
            uploadZone.style.display = 'none';
        } else {
            progressContainer.style.display = 'none';
            uploadZone.style.display = 'block';
        }
    }

    function updateProgress(percent) {
        progressFill.style.width = `${percent}%`;
    }

    // Update button text based on selected format
    function updateConvertButtonText() {
        const format = document.querySelector('input[name="output-format"]:checked').value;
        const button = document.getElementById('convert-button');
        const icon = format === 'mp3' ? 'music' : 'video';
        const text = format === 'mp3' ? 'Extract Audio' : 'Convert to MP4';
        button.innerHTML = `<i class="fas fa-${icon}"></i> <span>${text}</span>`;
    }

    // Update button text when format changes
    document.querySelectorAll('input[name="output-format"]').forEach(radio => {
        radio.addEventListener('change', updateConvertButtonText);
    });
    
    // Set initial button text
    updateConvertButtonText();

    convertForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        if (videoFileInput.files.length === 0) {
            new Notification('error', 'Please select at least one video file');
            return;
        }
        
        const outputFormat = document.querySelector('input[name="output-format"]:checked').value;
        const submitBtn = convertForm.querySelector('.action-btn');
        const originalBtnContent = submitBtn.innerHTML;
        
        try {
            // Show loading state
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="loading"></span> Converting...';
            showProgress(true);
            
            // Hide any previous preview
            document.getElementById('preview-section').classList.add('hidden');
            
            // Simulate progress (since we can't track real progress easily)
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += Math.random() * 15;
                if (progress > 90) progress = 90;
                updateProgress(progress);
            }, 500);

            const formData = new FormData();
            formData.append('file', videoFileInput.files[0]);
            formData.append('output_format', outputFormat);
            
            try {
                const response = await fetch('/convert', {
                    method: 'POST',
                    body: formData
                });

                clearInterval(progressInterval);
                updateProgress(100);

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || 'Conversion failed');
                }

                const result = await response.json();
                
                // Show preview section
                const previewSection = document.getElementById('preview-section');
                const previewContent = document.getElementById('preview-content');
                const downloadBtn = document.getElementById('download-btn');
                
                // Clear previous preview
                previewContent.innerHTML = '';
                
                // Create preview based on file type
                if (outputFormat === 'mp3') {
                    // Audio preview
                    const audio = document.createElement('audio');
                    audio.controls = true;
                    audio.src = result.file_path;
                    audio.className = 'w-full max-w-full';
                    previewContent.appendChild(audio);
                    
                    // Set up download button
                    downloadBtn.onclick = (e) => {
                        e.preventDefault();
                        window.location.href = result.file_path;
                    };
                    downloadBtn.innerHTML = '<i class="fas fa-download"></i> Download Audio';
                } else {
                    // Video preview
                    const video = document.createElement('video');
                    video.controls = true;
                    video.src = result.file_path;
                    video.className = 'w-full max-w-full';
                    previewContent.appendChild(video);
                    
                    // Set up download button
                    downloadBtn.onclick = (e) => {
                        e.preventDefault();
                        window.location.href = result.file_path;
                    };
                    downloadBtn.innerHTML = '<i class="fas fa-download"></i> Download Video';
                }
                
                // Show preview section
                previewSection.classList.remove('hidden');
                
                // Scroll to preview
                previewSection.scrollIntoView({ behavior: 'smooth' });
                
                new Notification('success', 'Conversion complete! Preview your file below.');
            } catch (error) {
                console.error('Error processing response:', error);
                throw error; // Re-throw to be caught by the outer catch
            }
            
        } catch (error) {
            console.error('Conversion error:', error);
            new Notification('error', `Conversion failed: ${error.message}`);
        } finally {
            // Reset UI state
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnContent;
            showProgress(false);
            updateProgress(0);
        }
    });

    // YouTube downloader with enhanced features
    const youtubeForm = document.getElementById('youtube-form');
    const youtubeUrlInput = document.getElementById('youtube-url');
    const youtubeThumbnail = document.getElementById('youtube-thumbnail');
    const youtubeProgress = document.getElementById('youtube-progress');
    const youtubeProgressFill = document.getElementById('youtube-progress-fill');
    const youtubeProgressText = document.getElementById('youtube-progress-text');
    
    // Thumbnail preview on URL input
    let thumbnailTimeout;
    youtubeUrlInput.addEventListener('input', (e) => {
        clearTimeout(thumbnailTimeout);
        const url = e.target.value.trim();
        
        if (url && isValidYouTubeUrl(url)) {
            thumbnailTimeout = setTimeout(() => {
                fetchYouTubeThumbnail(url);
            }, 500);
        } else {
            youtubeThumbnail.classList.add('hidden');
        }
    });
    youtubeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const url = document.getElementById('youtube-url').value;
        const format = document.querySelector('input[name="format"]:checked').value;
        const submitBtn = youtubeForm.querySelector('button[type="submit"]');
        const originalBtnText = submitBtn.innerHTML;

        try {
            // Show loading state and progress
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="loading"></span> Processing...';
            youtubeProgress.classList.remove('hidden');
            
            // Simulate progress (since we can't get real progress from backend yet)
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += Math.random() * 15;
                if (progress > 90) progress = 90;
                youtubeProgressFill.style.width = progress + '%';
                youtubeProgressText.textContent = `Downloading... ${Math.round(progress)}%`;
            }, 500);
            
            try {
                const response = await fetch('/download/youtube', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/octet-stream'  // Explicitly ask for a file
                    },
                    body: JSON.stringify({ url, format })
                });

                // Check if the response is a file download
                const contentType = response.headers.get('content-type') || '';
                
                if (contentType.includes('application/json')) {
                    // Handle JSON error response
                    const errorData = await response.json();
                    throw new Error(errorData.detail || 'Download failed');
                }

                if (!response.ok) {
                    throw new Error(`Server returned ${response.status}: ${response.statusText}`);
                }

                // Get filename from content-disposition or generate one
                let filename = `youtube_${format}_${Date.now()}.${format === 'video' ? 'mp4' : 'mp3'}`;
                const contentDisposition = response.headers.get('content-disposition');
                
                if (contentDisposition) {
                    const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
                    if (filenameMatch && filenameMatch[1]) {
                        // Remove quotes if present
                        filename = filenameMatch[1].replace(/['"]/g, '');
                    }
                }

                // Create a Blob URL and render inline playback instead of auto-downloading
                const blob = await response.blob();

                if (blob.size === 0) {
                    throw new Error('Received empty file from server');
                }

                const mediaUrl = window.URL.createObjectURL(blob);

                // Reuse global preview section
                const previewSection = document.getElementById('preview-section');
                const previewContent = document.getElementById('preview-content');
                const downloadBtn = document.getElementById('download-btn');

                // Clear any prior content
                previewContent.innerHTML = '';

                const isVideo = filename.toLowerCase().endsWith('.mp4');
                const isAudio = filename.toLowerCase().endsWith('.mp3');

                if (isVideo) {
                    const video = document.createElement('video');
                    video.src = mediaUrl;
                    video.controls = true;
                    video.autoplay = true;
                    video.style.width = '100%';
                    video.style.maxHeight = '60vh';
                    video.style.borderRadius = '12px';
                    previewContent.appendChild(video);
                } else if (isAudio) {
                    const audio = document.createElement('audio');
                    audio.src = mediaUrl;
                    audio.controls = true;
                    audio.autoplay = true;
                    audio.style.width = '100%';
                    previewContent.appendChild(audio);
                }

                // Configure download button (user can choose to download after preview)
                downloadBtn.href = mediaUrl;
                downloadBtn.download = filename;
                downloadBtn.innerHTML = `<i class="fas fa-download"></i> Download ${isAudio ? 'Audio' : 'Video'}`;

                // Add to download history
                addToDownloadHistory({
                    title: filename,
                    type: isAudio ? 'audio' : 'video',
                    size: blob.size,
                    url: mediaUrl,
                    filename: filename,
                    timestamp: Date.now()
                });

                // Show the preview section and scroll into view
                previewSection.classList.remove('hidden');
                previewSection.scrollIntoView({ behavior: 'smooth' });

                new Notification('success', 'Ready! Playing your media below.');
                
            } catch (error) {
                console.error('Download error:', error);
                throw error;  // Re-throw to be caught by the outer catch
                
            } finally {
                clearInterval(progressInterval);
            }
            
        } catch (error) {
            console.error('Download error:', error);
            new Notification('error', `Error: ${error.message || 'Failed to download video'}`);
        } finally {
            // Reset button state
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnText;
            youtubeProgress.classList.add('hidden');
            youtubeProgressFill.style.width = '0%';
        }
    });

    // TikTok downloader
    const tiktokForm = document.getElementById('tiktok-form');
    const tiktokUrlInput = document.getElementById('tiktok-url');
    const tiktokProgress = document.createElement('div');
    tiktokProgress.className = 'progress-container hidden';
    tiktokProgress.innerHTML = `
        <div class="progress-bar">
            <div class="progress-fill" id="tiktok-progress-fill"></div>
        </div>
        <div class="progress-text" id="tiktok-progress-text">Processing...</div>
    `;
    tiktokForm.appendChild(tiktokProgress);
    
    tiktokForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const url = tiktokUrlInput.value.trim();
        if (!url) {
            new Notification('error', 'Please enter a TikTok URL');
            return;
        }
        
        const submitBtn = tiktokForm.querySelector('button[type="submit"]');
        const originalBtnText = submitBtn.innerHTML;
        const progressFill = document.getElementById('tiktok-progress-fill');
        const progressText = document.getElementById('tiktok-progress-text');
        
        try {
            // Show loading state
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="loading"></span> Processing...';
            tiktokProgress.classList.remove('hidden');
            progressFill.style.width = '0%';
            
            // Simulate progress (since we can't get real progress from backend yet)
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += Math.random() * 15;
                if (progress > 90) progress = 90;
                progressFill.style.width = progress + '%';
                progressText.textContent = `Downloading... ${Math.round(progress)}%`;
            }, 500);
            
            // Make the API request
            console.log('Sending request to /download/tiktok with URL:', url);
            const response = await fetch('/download/tiktok', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url })
            });
            
            clearInterval(progressInterval);
            
            console.log('Response status:', response.status, response.statusText);
            
            if (!response.ok) {
                let errorDetail = 'Failed to download TikTok video';
                try {
                    const errorData = await response.json();
                    console.error('Error response:', errorData);
                    errorDetail = errorData.detail || JSON.stringify(errorData);
                } catch (e) {
                    const text = await response.text();
                    console.error('Failed to parse error response:', text);
                    errorDetail = `Server responded with ${response.status}: ${response.statusText}`;
                }
                throw new Error(errorDetail);
            }
            
            // Get the filename from Content-Disposition header
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'tiktok_video.mp4';
            if (contentDisposition) {
                const match = contentDisposition.match(/filename="?([^"]+)"?/);
                if (match && match[1]) {
                    filename = match[1];
                }
            }
            
            // Get the blob and create a download link
            const blob = await response.blob();
            const mediaUrl = URL.createObjectURL(blob);
            
            // Update progress to 100%
            progressFill.style.width = '100%';
            progressText.textContent = 'Download complete!';
            
            // Create a preview section similar to YouTube
            const previewSection = document.getElementById('preview-section');
            const previewContent = document.getElementById('preview-content');
            const downloadBtn = document.getElementById('download-btn');

            // Clear previous preview content
            previewContent.innerHTML = '';

            // Create and append video element
            const video = document.createElement('video');
            video.src = mediaUrl;
            video.controls = true;
            video.autoplay = true;
            video.style.width = '100%';
            video.style.maxHeight = '60vh';
            video.style.borderRadius = '12px';
            previewContent.appendChild(video);

            // Set up download button
            downloadBtn.href = mediaUrl;
            downloadBtn.download = filename;
            downloadBtn.innerHTML = '<i class="fas fa-download"></i> Download Video';
            
            // Add to download history
            addToDownloadHistory({
                title: filename.replace(/\.mp4$/, ''),
                type: 'video',
                size: blob.size,
                url: mediaUrl,
                filename: filename,
                timestamp: Date.now()
            });
            
            // Show the preview section and scroll into view
            previewSection.classList.remove('hidden');
            previewSection.scrollIntoView({ behavior: 'smooth' });
            
            new Notification('success', 'TikTok video downloaded successfully!');
            
        } catch (error) {
            console.error('Error downloading TikTok video:', error);
            new Notification('error', error.message || 'Failed to download TikTok video');
        } finally {
            // Reset button state
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnText;
            tiktokProgress.classList.add('hidden');
            progressFill.style.width = '0%';
        }
    });
    
    // Theme toggle functionality
    const themeToggle = document.getElementById('theme-toggle');
    themeToggle.addEventListener('click', toggleTheme);
    
    // Download history functionality
    const clearHistoryBtn = document.getElementById('clear-history');
    clearHistoryBtn.addEventListener('click', clearDownloadHistory);
    
    // Show download history if there are items
    if (getDownloadHistory().length > 0) {
        document.getElementById('download-history').classList.remove('hidden');
    }
});

// Helper Functions
function isValidYouTubeUrl(url) {
    const patterns = [
        /^https?:\/\/(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)([\w-]{11})/,
        /^https?:\/\/(www\.)?youtube\.com\/embed\/([\w-]{11})/
    ];
    return patterns.some(pattern => pattern.test(url));
}

async function fetchYouTubeThumbnail(url) {
    try {
        const response = await fetch(`https://www.youtube.com/oembed?url=${encodeURIComponent(url)}&format=json`);
        if (response.ok) {
            const data = await response.json();
            showThumbnail(data);
        }
    } catch (error) {
        console.log('Could not fetch thumbnail:', error);
    }
}

function showThumbnail(data) {
    const thumbnail = document.getElementById('youtube-thumbnail');
    const img = document.getElementById('youtube-thumb-img');
    const title = document.getElementById('youtube-thumb-title');
    const duration = document.getElementById('youtube-thumb-duration');

    // Guard against missing elements to avoid null.src errors
    if (!thumbnail || !img || !title || !duration) {
        console.warn('Thumbnail elements not found; skipping preview render');
        return;
    }

    img.src = data.thumbnail_url;
    title.textContent = data.title;
    duration.textContent = `by ${data.author_name}`;

    thumbnail.classList.remove('hidden');
}

// Theme Management
function initializeTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.body.className = savedTheme === 'light' ? 'light-theme' : '';
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const isLight = document.body.classList.contains('light-theme');
    const newTheme = isLight ? 'dark' : 'light';
    
    document.body.className = newTheme === 'light' ? 'light-theme' : '';
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
    
    new Notification('info', `Switched to ${newTheme} theme`);
}

function updateThemeIcon(theme) {
    const icon = document.querySelector('#theme-toggle i');
    icon.className = theme === 'light' ? 'fas fa-sun' : 'fas fa-moon';
}

// Download History Management
function getDownloadHistory() {
    return JSON.parse(localStorage.getItem('downloadHistory') || '[]');
}

function addToDownloadHistory(item) {
    const history = getDownloadHistory();
    history.unshift(item); // Add to beginning
    
    // Keep only last 10 items
    if (history.length > 10) {
        history.splice(10);
    }
    
    localStorage.setItem('downloadHistory', JSON.stringify(history));
    renderDownloadHistory();
    
    // Show history section
    document.getElementById('download-history').classList.remove('hidden');
}

function loadDownloadHistory() {
    renderDownloadHistory();
}

function renderDownloadHistory() {
    const history = getDownloadHistory();
    const historyList = document.getElementById('history-list');
    
    if (history.length === 0) {
        historyList.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 2rem;">No downloads yet</p>';
        return;
    }
    
    historyList.innerHTML = history.map(item => `
        <div class="history-item">
            <div class="history-info">
                <div class="history-title">${item.title}</div>
                <div class="history-meta">
                    ${item.type.toUpperCase()} • ${formatFileSize(item.size)} • ${formatDate(item.timestamp)}
                </div>
            </div>
            <div class="history-actions">
                <button onclick="downloadHistoryItem('${item.url}', '${item.filename}')" title="Download again">
                    <i class="fas fa-download"></i>
                </button>
                <button onclick="removeHistoryItem(${item.timestamp})" title="Remove from history">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `).join('');
}

function downloadHistoryItem(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    new Notification('success', 'Download started!');
}

function removeHistoryItem(timestamp) {
    const history = getDownloadHistory().filter(item => item.timestamp !== timestamp);
    localStorage.setItem('downloadHistory', JSON.stringify(history));
    renderDownloadHistory();
    
    if (history.length === 0) {
        document.getElementById('download-history').classList.add('hidden');
    }
}

function clearDownloadHistory() {
    localStorage.removeItem('downloadHistory');
    renderDownloadHistory();
    document.getElementById('download-history').classList.add('hidden');
    new Notification('success', 'Download history cleared!');
}

// Utility Functions
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(timestamp) {
    return new Date(timestamp).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}
