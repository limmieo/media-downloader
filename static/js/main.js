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

document.addEventListener('DOMContentLoaded', () => {
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

    // YouTube downloader
    const youtubeForm = document.getElementById('youtube-form');
    const youtubePreviewBtn = document.getElementById('youtube-preview-btn');
    const youtubePreview = document.getElementById('youtube-preview');
    const youtubeIframe = document.getElementById('youtube-iframe');
    const youtubePreviewTitle = document.getElementById('youtube-preview-title');

    // Helper: extract YouTube video ID from various URL formats
    function extractYouTubeId(url) {
        try {
            // Handle youtu.be/<id>
            const short = url.match(/^https?:\/\/(?:www\.)?youtu\.be\/([\w-]{11})/i);
            if (short) return short[1];

            // Handle youtube.com/watch?v=<id> and variations
            const u = new URL(url);
            if ((u.hostname.includes('youtube.com') || u.hostname.includes('youtu.be')) && u.searchParams.get('v')) {
                const id = u.searchParams.get('v');
                if (id && id.length === 11) return id;
            }

            // Handle embed URLs
            const embed = url.match(/youtube\.com\/(?:embed|v)\/([\w-]{11})/i);
            if (embed) return embed[1];
        } catch (e) {
            // ignore parse errors
        }
        return null;
    }

    // Handle YouTube preview click
    if (youtubePreviewBtn) {
        youtubePreviewBtn.addEventListener('click', async () => {
            const urlInput = document.getElementById('youtube-url');
            const url = (urlInput?.value || '').trim();

            if (!url) {
                new Notification('error', 'Please paste a YouTube URL first.');
                return;
            }

            const videoId = extractYouTubeId(url);
            if (!videoId) {
                new Notification('error', 'That does not look like a valid YouTube URL.');
                return;
            }

            // Build embed URL
            const embedUrl = `https://www.youtube.com/embed/${videoId}`;
            youtubeIframe.src = embedUrl;
            youtubePreview.classList.remove('hidden');

            // Try to fetch a title via oEmbed (best-effort)
            youtubePreviewTitle.textContent = '';
            try {
                const oembed = await fetch(`https://www.youtube.com/oembed?url=${encodeURIComponent(url)}&format=json`);
                if (oembed.ok) {
                    const data = await oembed.json();
                    if (data && data.title) {
                        youtubePreviewTitle.textContent = data.title;
                    }
                }
            } catch (_) {
                // no-op if blocked
            }

            new Notification('info', 'Showing YouTube preview.');
        });
    }
    youtubeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const url = document.getElementById('youtube-url').value;
        const format = document.querySelector('input[name="format"]:checked').value;
        const submitBtn = youtubeForm.querySelector('button[type="submit"]');
        const originalBtnText = submitBtn.innerHTML;

        try {
            // Show loading state
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="loading"></span> Processing...';
            
            // Show loading state with progress
            const progressInterval = setInterval(() => {
                if (submitBtn.innerHTML.includes('%')) return;
                submitBtn.innerHTML = '<span class="loading"></span> Downloading...';
            }, 1000);
            
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

                // Create download link and trigger download
                const blob = await response.blob();
                
                // Check if the blob is empty
                if (blob.size === 0) {
                    throw new Error('Received empty file from server');
                }
                
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = filename;
                a.style.display = 'none';
                document.body.appendChild(a);
                a.click();
                
                // Cleanup
                setTimeout(() => {
                    window.URL.revokeObjectURL(downloadUrl);
                    document.body.removeChild(a);
                }, 100);
                
                new Notification('success', 'Download completed successfully!');
                
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
        }
    });

    // TikTok downloader (placeholder for now)
    const tiktokForm = document.getElementById('tiktok-form');
    tiktokForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        new Notification('info', 'TikTok download feature coming soon!');
    });
});
