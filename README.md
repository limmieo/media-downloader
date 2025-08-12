# Media Downloader
🎵📥 Media Downloader

A professional-grade web application for downloading and converting media from various sources, showcasing modern web development skills and best practices. This project demonstrates expertise in full-stack development, API design, and user experience implementation.

## 🚀 Key Features & Technical Highlights

- **Full-Stack Architecture**: Built with FastAPI (Python) backend and modern JavaScript frontend
- **Robust Error Handling**: Comprehensive error handling and logging throughout the application
- **Performance Optimized**: Efficient file handling and background processing
- **Clean Codebase**: Well-structured, documented code following best practices
- **Modern UI/UX**: Responsive design with intuitive user interactions
- **Secure File Handling**: Safe file operations and sanitization

## 🛠 Technical Stack

- **Backend**: Python, FastAPI, yt-dlp, FFmpeg
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Tools**: Git, GitHub, Virtual Environments
- **Best Practices**: RESTful API design, Error Handling, Logging, Security

## ✨ Features

- **YouTube Integration**
  - Download videos in multiple formats and qualities
  - Extract high-quality audio (MP3) from videos
  - Handle various video formats and codecs

- **File Management**
  - Automatic file organization
  - Background processing for large files
  - Cleanup of temporary files

- **User Experience**
  - Modern, responsive UI with dark/light mode
  - Real-time progress tracking
  - Intuitive drag-and-drop interface
  - Error handling with user-friendly messages

- **Developer Experience**
  - Well-documented code
  - Modular architecture
  - Environment configuration
  - Comprehensive logging

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- FFmpeg (for video processing)
- Node.js 14+ (for frontend development)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/media-downloader.git
   cd media-downloader
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # On Windows
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install frontend dependencies (if needed):
   ```bash
   cd static
   npm install
   ```

## Usage

1. Start the server:
   ```bash
   uvicorn main:app --reload
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:8000
   ```

## Configuration

Create a `.env` file in the project root with any necessary environment variables.

## 🧭 Why This Project?
This app was built to make collecting reference clips and music fast and frustration-free. It’s designed to be easy for creators and solid for engineers reviewing the code. You’ll find clean architecture, safe file handling, robust logging, and a modern UI with thoughtful UX details.

## 🏗️ How It Works
- Client (Vanilla JS) sends requests to a FastAPI backend
- Backend uses yt-dlp to fetch media and FFmpeg for conversions
- Files are sanitized, saved locally, and streamed back to the browser
- Strict error handling and logs provide clear diagnostics

```
[Browser 🧑‍💻] ⇄ [FastAPI 🔧] → yt-dlp ⤵ → FFmpeg 🎬 → [downloads/ + response]
```

## 🔌 API Endpoints
- POST `/convert` — Upload a file; convert to mp4 or mp3
- POST `/download/youtube` — Download YouTube as video or audio (mp4/mp3)
- GET `/converted/{filename}` — Serve converted files

Example request body for YouTube:
```json
{ "url": "https://youtu.be/...", "format": "audio" }
```

## 🖼️ Screenshots & Demo
Coming soon! Planned: short GIF of the drag‑and‑drop upload + YouTube download flow.

## 🧪 What Reviewers Can Look For
- Clear separation of concerns in `main.py`
- Safe filename handling: `sanitize_filename()` and `safe_filename()` to avoid Unicode/header issues
- Defensive error handling and detailed logging
- Simple, readable frontend in `static/js/main.js` with graceful error UX

## 🗺️ Roadmap
- TikTok downloader with watermark removal
- Queue for large conversions + progress events
- Optional cloud storage backend (S3/Azure Blob)
- Dockerfile for one‑command deploy

## ❓ FAQ
- Why not ffmpeg-python? → We use system FFmpeg via subprocess for reliability on Windows.
- Does it work offline? → Conversions do; downloads require internet.
- Where are files stored? → `downloads/` and `converted/` limited with cleanup.

## 🤝 Contributing
Issues and PRs are welcome! If you’d like a good first issue, try adding a progress bar that streams backend progress updates to the UI.

## 📄 License

MIT
