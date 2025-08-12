# Media Downloader

A modern web application for downloading and converting media from various sources like YouTube and TikTok.

## Features

- Download YouTube videos in multiple formats
- Extract audio from videos
- Convert between different video formats
- Modern, responsive UI with dark mode support
- Background processing for large files

## Requirements

- Python 3.8+
- FFmpeg
- Node.js (for frontend development)

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

## License

MIT
