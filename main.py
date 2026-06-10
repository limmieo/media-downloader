from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask
from pydantic import BaseModel
import os
import re
import json
import logging
import tempfile
import time
import shutil
import uuid
import subprocess
import urllib.parse
import mimetypes
import datetime
import traceback
from typing import Optional, Dict, List
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, urljoin, urlunparse
import yt_dlp
import instaloader
import zipfile
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
from converter import MediaConverter

# Load environment variables from .env if present (for optional integrations)
load_dotenv()

# Ensure the downloads directory exists
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# FFmpeg configuration - try to find FFmpeg in common locations
def get_ffmpeg_path():
    """Find FFmpeg executable path."""
    common_paths = [
        r"C:\ffmpeg-7.1.1-essentials_build\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        "ffmpeg",  # System PATH
    ]
    
    for path in common_paths:
        try:
            result = subprocess.run([path, "-version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                return path
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            continue
    
    return "ffmpeg"  # Fallback to system PATH

FFMPEG_PATH = get_ffmpeg_path()

# Load environment variables from .env if present (for optional integrations)
load_dotenv()

def extract_tiktok_video_id(url: str) -> str:
    """Extract video ID from various TikTok URL formats."""
    # Handle mobile links
    if '@' in url and '/video/' in url:
        return url.split('/video/')[1].split('?')[0].split('#')[0]
    
    # Handle web links
    if 'tiktok.com/' in url and '/video/' in url:
        return url.split('/video/')[1].split('?')[0].split('#')[0]
    
    # Handle v.tiktok.com links
    if 'v.tiktok.com/' in url:
        # We need to follow the redirect to get the actual video ID
        try:
            response = requests.head(url, allow_redirects=True, timeout=5)
            if response.status_code == 200:
                return extract_tiktok_video_id(response.url)
        except Exception:
            pass
    
    # If we can't extract the ID, return the input as is (might already be an ID)
    return url

def cleanup_old_files(max_files: int = 5):
    """Clean up old files in the downloads folder, keeping only the most recent ones."""
    try:
        # Get all files in the downloads folder
        files = [os.path.join(DOWNLOAD_FOLDER, f) for f in os.listdir(DOWNLOAD_FOLDER) 
                if os.path.isfile(os.path.join(DOWNLOAD_FOLDER, f))]
        
        # Sort files by modification time (newest first)
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        # Delete files beyond the max_files limit
        for file_path in files[max_files:]:
            try:
                os.remove(file_path)
                logger.info(f"Deleted old file: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {str(e)}")
    except Exception as e:
        logger.error(f"Error in cleanup_old_files: {str(e)}")


# TikTok API endpoints
TIKTOK_API_DOMAIN = "https://api16-normal-c-useast1a.tiktokv.com"
TIKTOK_VIDEO_URL = f"{TIKTOK_API_DOMAIN}/aweme/v1/feed/"
TIKTOK_VIDEO_INFO = f"{TIKTOK_API_DOMAIN}/aweme/v1/aweme/detail/"

# TikTok downloader API endpoints
# TikWM requires POST to /api/ with form data: url=<tiktok_url>
TIKWM_API = "https://www.tikwm.com/api/"


# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# In-memory storage for download history
download_history = []

def add_to_history(item: dict):
    """Add an item to download history."""
    download_history.append(item)
    # Keep only the last 100 items
    if len(download_history) > 100:
        download_history.pop(0)

def cleanup_temp_file(path: str):
    """Clean up temporary file after sending the response."""
    try:
        if os.path.exists(path):
            os.unlink(path)
            logger.info(f"Cleaned up temporary file: {path}")
    except Exception as e:
        logger.error(f"Error cleaning up temporary file {path}: {e}")

def get_tiktok_video_id(url: str) -> str:
    """Extract TikTok video ID from URL."""
    # Handle different TikTok URL formats
    patterns = [
        r'vm.tiktok.com/[^/]+',
        r'tiktok.com/@[^/]+/video/(\d+)',
        r'tiktok.com/t/([a-zA-Z0-9]+)',
        r'tiktok.com/v/(\d+)',
        r'tiktok.com/.*?/video/(\d+)',
        r'tiktok.com/.*?/v/(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1) if len(match.groups()) > 0 else match.group(0)
    
    # If no pattern matches, try to get the last part of the URL
    return url.split('/')[-1].split('?')[0]

def get_tiktok_video_info(video_id: str) -> dict:
    """Get TikTok video information using tikwm.com API."""
    logger.info(f"Getting video info for video ID: {video_id}")
    
    try:
        # First, try to get video info from tikwm API
        url = f"https://www.tiktok.com/@{video_id.split('_')[0]}/video/{video_id}"
        response = requests.post(
            f"{TIKWM_API}info",
            json={"url": url},
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json',
                'Origin': 'https://tikwm.com',
                'Referer': 'https://tikwm.com/',
                'Content-Type': 'application/json'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 0 and data.get('data'):
                video_data = data['data']
                # Get the highest quality video URL
                video_url = video_data.get('play')
                if not video_url and video_data.get('download_url'):
                    video_url = video_data['download_url']
                
                if video_url:
                    return {
                        'status': 'success',
                        'data': {
                            'aweme_id': video_id,
                            'desc': video_data.get('title', ''),
                            'author': video_data.get('author', {}).get('nickname', ''),
                            'video': {
                                'play_addr': {
                                    'url_list': [video_url]
                                },
                                'cover': video_data.get('cover')
                            },
                            'music': {
                                'title': video_data.get('music', {}).get('title', ''),
                                'author': video_data.get('music', {}).get('author', '')
                            }
                        }
                    }
        
        # If we got here, the API request failed
        error_msg = f"API request failed with status {response.status_code}"
        if response.status_code == 200 and 'msg' in data:
            error_msg = data['msg']
        raise Exception(error_msg)
        
    except Exception as e:
        logger.error(f"Error in get_tiktok_video_info: {str(e)}", exc_info=True)
        return {
            'status': 'error', 
            'message': f'Failed to fetch video information: {str(e)}'
        }
        
    except Exception as e:
        logger.error(f"Error in get_tiktok_video_info: {str(e)}", exc_info=True)
        return {
            'status': 'error', 
            'message': f'Failed to fetch video information: {str(e)}'
        }

def _try_tiktok_api(video_id: str, headers: dict) -> dict:
    """Try to get video info from TikTok API."""
    try:
        response = requests.get(
            f"https://api16-core-c-useast1a.tiktokv.com/aweme/v1/feed/?aweme_id={video_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('aweme_list') and len(data['aweme_list']) > 0:
                return {
                    'status': 'success',
                    'data': data['aweme_list'][0]
                }
    except Exception as e:
        logger.warning(f"TikTok API method failed: {str(e)}")
    
    return {'status': 'error'}

def _try_tiktok_embed(video_id: str, headers: dict) -> dict:
    """Try to get video info from embed page."""

def _try_tiktok_oembed(video_id: str, headers: dict) -> dict:
    """Try to get video info from oEmbed endpoint."""
    try:
        url = f'https://www.tiktok.com/embed/v2/{video_id}'
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            script_tag = soup.find('script', {'id': 'SIGI_STATE'})
            
            if script_tag:
                data = json.loads(script_tag.string)
                video_data = data.get('ItemModule', {}).get(video_id, {})
                
                if video_data:
                    output_file_path = os.path.join(DOWNLOAD_FOLDER, f"{video_id}.mp4")
                    if os.path.exists(output_file_path):
                        abs_out = os.path.abspath(output_file_path)
                        return {
                            "success": True,
                            "filePath": abs_out,
                            "message": "File already exists"
                        }
                    else:
                        return {
                            'status': 'success',
                            'data': {
                                'aweme_id': video_id,
                                'desc': video_data.get('desc', ''),
                                'author': video_data.get('author', ''),
                                'video': {
                                    'play_addr': {
                                        'url_list': [video_data.get('video', {}).get('downloadAddr', '')]
                                },
                                'cover': video_data.get('covers', [''])[0]
                            },
                            'music': video_data.get('music', {})
                        }
                    }
    except Exception as e:
        logger.warning(f"TikTok embed method failed: {str(e)}")
    
    return {'status': 'error'}

def _try_tiktok_webpage(video_id: str, headers: dict) -> dict:
    """Try to get video info by scraping the webpage."""
    try:
        url = f'https://www.tiktok.com/@tiktok/video/{video_id}'
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Look for JSON data in the page
            match = re.search(r'<script[^>]*>window\[\'\"]SIGI_STATE\[\'\"\]=(.*?)<\/script>', response.text)
            if match:
                data = json.loads(match.group(1))
                video_data = data.get('ItemModule', {}).get(video_id, {})
                
                if video_data:
                    return {
                        'status': 'success',
                        'data': {
                            'aweme_id': video_id,
                            'desc': video_data.get('desc', ''),
                            'author': video_data.get('author', ''),
                            'video': {
                                'play_addr': {
                                    'url_list': [video_data.get('video', {}).get('downloadAddr', '')]
                                },
                                'cover': video_data.get('covers', [''])[0]
                            }
                        }
                    }
    except Exception as e:
        logger.warning(f"TikTok webpage method failed: {str(e)}")
    
    return {'status': 'error'}

def sanitize_filename(filename: str) -> str:
    """
    Remove or replace special characters in filenames to make them filesystem-safe.
    
    Args:
        filename: The original filename to sanitize
        
    Returns:
        A sanitized version of the filename with special characters removed or replaced
    """
    # Replace full-width characters with their ASCII equivalents
    filename = filename.replace('｜', '|')  # Full-width vertical bar to ASCII
    filename = filename.replace('：', ':')  # Full-width colon to ASCII
    filename = filename.replace('／', '-')  # Full-width slash to hyphen
    
    # Remove other special characters that are problematic in filenames
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    
    # Replace multiple spaces with single space and strip leading/trailing spaces
    filename = re.sub(r'\s+', ' ', filename).strip()
    
    return filename

def safe_filename(filename: str, default_extension: str = 'mp3') -> str:
    """
    Convert a filename to be safe for HTTP headers by removing non-ASCII characters.
    
    Args:
        filename: The original filename
        default_extension: Default extension to use if none is present
        
    Returns:
        A filename with only ASCII characters, suitable for HTTP headers
    """
    # Remove any path components
    filename = os.path.basename(filename)
    
    # Split into name and extension
    name, ext = os.path.splitext(filename)
    
    # If no extension, use the default
    if not ext:
        ext = f".{default_extension}"
    
    # Keep only ASCII letters, digits, dots, hyphens, and underscores
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
    
    # Ensure the filename isn't empty
    if not safe_name.strip():
        safe_name = f"download_{int(time.time())}"
    
    return f"{safe_name}{ext}"

# Configure logging (console + rotating file)
from logging.handlers import RotatingFileHandler

log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)

# File handler
os.makedirs('logs', exist_ok=True)
file_handler = RotatingFileHandler('logs/app.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(log_formatter)

# Avoid duplicate handlers across reloads by checking handler types
has_console = any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
if not has_console:
    logger.addHandler(console_handler)

has_rotating_file = any(isinstance(h, RotatingFileHandler) for h in logger.handlers)
if not has_rotating_file:
    logger.addHandler(file_handler)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# File serving endpoint for downloaded files
@app.get("/file/{file_path:path}")
async def serve_file(file_path: str):
    """Serve a downloaded file"""
    try:
        # Decode the file path
        import urllib.parse
        decoded_path = urllib.parse.unquote(file_path)
        
        if os.path.exists(decoded_path) and os.path.isfile(decoded_path):
            return FileResponse(decoded_path)
        else:
            raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        logger.error(f"Error serving file {file_path}: {e}")
        raise HTTPException(status_code=404, detail="File not found")

# YouTube download endpoint
@app.get("/youtube/download")
async def download_youtube_endpoint(url: str, format: str = "mp3"):
    """
    Download a YouTube video in the specified format.
    
    Args:
        url: YouTube video URL
        format: Output format (mp3 or mp4)
        
    Returns:
        JSON response with download status and file path
    """
    try:
        # Create a unique base name
        video_id = url.split("v=")[-1].split("&")[0]
        timestamp = int(time.time())
        base = f"youtube_{video_id}_{timestamp}"
        
        # Build robust yt-dlp options
        ydl_opts = {
            # Ignore any global/user yt-dlp config files that may set incompatible formats
            'ignoreconfig': True,
            'quiet': False,
            'no_warnings': True,
            'noplaylist': True,
            'extract_flat': False,
            # Ensure ffmpeg can be found (from our app's detection)
            'ffmpeg_location': FFMPEG_PATH,
            # Use JavaScript runtime for YouTube extraction
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios'],
                }
            },
            # Add user agent to avoid 403 errors
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            # Use cookies if available (optional, helps with some videos)
            'nocheckcertificate': True,
        }

        if format.lower() == 'mp3':
            # Audio-only with ffmpeg extraction to MP3
            filepath = os.path.join(DOWNLOAD_FOLDER, f"{base}.mp3")
            ydl_opts.update({
                'format': 'bestaudio/best',
                'outtmpl': filepath,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'prefer_ffmpeg': True,
            })
        else:
            # Video: prefer MP4 (progressive or merged), with fallbacks
            # Try best MP4 video + M4A audio, then best progressive MP4, then any best
            filepath = os.path.join(DOWNLOAD_FOLDER, f"{base}.mp4")
            ydl_opts.update({
                'format': 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best',
                'outtmpl': filepath,
                'merge_output_format': 'mp4',
                'prefer_ffmpeg': True,
            })

        def _attempt_download(opts):
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=True)

        info = None
        try:
            info = _attempt_download(ydl_opts)
        except Exception as e1:
            logger.warning(f"Primary yt-dlp format selection failed: {e1}. Retrying with generic fallback...")
            # Fallback to the most generic selectors
            fallback_opts = dict(ydl_opts)
            if format.lower() == 'mp3':
                fallback_opts['format'] = 'bestaudio/best'
            else:
                fallback_opts['format'] = 'best'
            info = _attempt_download(fallback_opts)

        filename = os.path.basename(filepath)
        return {
            "success": True,
            "message": "Download completed successfully",
            "filePath": filepath,
            "filename": filename,
            "title": info.get('title', 'video')
        }
        
    except Exception as e:
        logger.error(f"YouTube download error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to download video"
        }

# Create directories if they don't exist
os.makedirs("downloads", exist_ok=True)
os.makedirs("converted", exist_ok=True)

def cleanup_folder(folder_path, max_files=5, exclude_file=None):
    """Keep only the most recent files in a folder, delete older ones"""
    try:
        if not os.path.exists(folder_path):
            return
        
        # Get all files in the folder with their modification times
        files = []
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                # Skip the excluded file
                if exclude_file and os.path.abspath(file_path) == os.path.abspath(exclude_file):
                    continue
                files.append((file_path, os.path.getmtime(file_path)))
        
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x[1], reverse=True)
        
        # Delete files beyond the limit
        if len(files) > max_files:
            for file_path, _ in files[max_files:]:
                try:
                    os.remove(file_path)
                    logger.info(f"Deleted old file: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to delete file {file_path}: {e}")
    except Exception as e:
        logger.error(f"Error cleaning up folder {folder_path}: {e}")

def run_ffmpeg_command(cmd):
    """Helper function to run ffmpeg commands with error handling"""
    try:
        # Ensure the command starts with ffmpeg path
        if cmd[0].lower() == 'ffmpeg':
            cmd[0] = FFMPEG_PATH
        
        logger.info(f"Executing FFmpeg command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            shell=True  # Use shell=True to help with path resolution
        )
        logger.info(f"FFmpeg command executed successfully")
        return True, ""
    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg error: {e.stderr}"
        logger.error(f"{error_msg}\nCommand: {' '.join(cmd)}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"{error_msg}\nCommand: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        return False, error_msg

@app.get("/")
async def index():
    return templates.TemplateResponse("index.html", {"request": {}})

@app.get("/converted/{filename}")
async def get_converted_file(filename: str):
    """Serve converted files"""
    file_path = f"converted/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine media type based on file extension
    if filename.lower().endswith('.mp3'):
        media_type = 'audio/mpeg'
    elif filename.lower().endswith('.mp4'):
        media_type = 'video/mp4'
    else:
        media_type = 'application/octet-stream'
    
    return FileResponse(
        file_path,
        filename=filename,
        media_type=media_type
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"An error occurred: {str(exc)}"}
    )

@app.post("/convert")
async def convert_video(
    file: UploadFile = File(...),
    output_format: str = Form("mp4"),  # 'mp4' or 'mp3'
):
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file uploaded")
            
        # Create directories if they don't exist
        os.makedirs("downloads", exist_ok=True)
        os.makedirs("converted", exist_ok=True)
        
        # Generate file paths with correct extensions
        file_stem = Path(file.filename).stem
        timestamp = int(time.time())
        
        # Ensure input file has a valid extension
        input_ext = Path(file.filename).suffix.lower()
        if not input_ext:
            input_ext = '.mp4'  # Default extension if none provided
            
        input_path = f"downloads/{file_stem}_{timestamp}{input_ext}"
        
        # Ensure output file has the correct extension and naming based on output_format
        output_ext = f".{output_format.lower()}"
        if not output_ext.startswith('.'):
            output_ext = f".{output_ext}"
        
        # Add '_audio' suffix for audio files
        if output_ext.lower() == '.mp3':
            output_filename = f"{file_stem}_audio{output_ext}"
        else:
            output_filename = f"{file_stem}{output_ext}"
        output_path = f"converted/{output_filename}"
        
        # Save uploaded file
        logger.info(f"Saving uploaded file to {input_path}")
        with open(input_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Build ffmpeg command based on output format
        if output_format.lower() == 'mp3':
            # Extract audio to MP3 (robust):
            # -y overwrite, -vn drop video, libmp3lame codec for compatibility
            cmd = [
                'ffmpeg',
                '-y',                      # Overwrite output if exists
                '-i', input_path,          # Input file
                '-vn',                     # No video
                '-c:a', 'libmp3lame',      # MP3 encoder
                '-b:a', '192k',            # Audio bitrate
                output_path
            ]
        else:
            # Convert video to MP4
            cmd = [
                'ffmpeg',
                '-y',                      # Overwrite output if exists
                '-i', input_path,          # Input file
                '-c:v', 'libx264',        # Video codec
                '-crf', '23',             # Constant Rate Factor (lower = better quality, 23 is default)
                '-preset', 'medium',      # Encoding speed/compression ratio
                '-c:a', 'aac',            # Audio codec
                '-b:a', '192k',           # Audio bitrate
                '-movflags', '+faststart', # Optimize for web streaming
                output_path
            ]
        
        logger.info(f"Starting conversion with command: {' '.join(cmd)}")
        
        # Run the ffmpeg command
        success, error = run_ffmpeg_command(cmd)
        
        # Clean up the input file
        if os.path.exists(input_path):
            os.remove(input_path)
            
        if not success:
            raise HTTPException(status_code=500, detail=f"Conversion failed: {error}")
        
        # Check if output file was created
        if not os.path.exists(output_path):
            raise HTTPException(status_code=500, detail="Conversion failed: Output file was not created")
        
        # Clean up old files in the converted folder (keep only 5 most recent)
        cleanup_folder("converted", max_files=5)
        
        logger.info(f"Conversion successful: {output_path}")
        
        # Return JSON response expected by renderer
        abs_out = os.path.abspath(output_path)
        return {
            "success": True,
            "filename": output_filename,
            "message": "Conversion successful",
            "filePath": abs_out,
            "file_type": output_format.lower()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Conversion error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during conversion: {str(e)}"
        )

@app.post("/download/tiktok")
async def download_tiktok(request: Request):
    """Download TikTok video using tikwm.com API."""
    temp_path = None
    max_retries = 3
    
    async def log_progress(progress: float):
        """Log download progress"""
        logger.info(f"Download progress: {progress:.1f}%")
    
    try:
        # Parse request body
        try:
            data = await request.json()
            url = data.get('url', '').strip()
            if not url:
                raise ValueError("URL is required")
        except Exception as e:
            logger.error(f"Error parsing request: {e}")
            raise HTTPException(status_code=400, detail=str(e) or "Invalid request data")
        
        logger.info(f"=== Starting TikTok Download for URL: {url} ===")
        
        # Extract video ID from URL (best-effort) and validate input URL
        video_id = get_tiktok_video_id(url)
        if not video_id:
            raise HTTPException(status_code=400, detail="Invalid TikTok URL")

        # Resolve short/redirect links to a canonical URL
        def _resolve_tiktok_url(u: str) -> str:
            try:
                if not u.startswith("http"):
                    u = "https://" + u
                r = requests.head(u, allow_redirects=True, timeout=10)
                return r.url or u
            except Exception:
                return u

        resolved_url = _resolve_tiktok_url(url)
        # Validate that the resolved URL contains a numeric video id; if not, warn but proceed (TikWM can handle many share links)
        id_match = re.search(r"/video/(\d+)", resolved_url)
        if not id_match:
            logger.warning(f"URL may be a short/share link; proceeding anyway: {resolved_url}")
        else:
            logger.info(f"Resolved TikTok URL: {resolved_url}")
        # Build the clean input for TikWM: prefer numeric ID
        video_id_num = id_match.group(1) if id_match else None
        if video_id_num:
            tikwm_input = video_id_num
        else:
            # Strip query/fragment
            try:
                from urllib.parse import urlparse, urlunparse
                p = urlparse(resolved_url)
                tikwm_input = urlunparse((p.scheme, p.netloc, p.path, '', '', ''))
            except Exception:
                tikwm_input = resolved_url.strip()
        
        # Create temp directory if it doesn't exist
        temp_dir = os.path.join(os.getcwd(), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Generate a temporary file path
        temp_path = os.path.join(temp_dir, f"tiktok_{int(time.time())}.mp4")
        
        # Try downloading with retries
        for attempt in range(max_retries):
            try:
                # Get video info from tikwm API via GET ?url=...
                payload = {"url": tikwm_input, "hd": 1, "web": 1}
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/json',
                    'Origin': 'https://tikwm.com',
                    'Referer': 'https://tikwm.com/',
                    'X-Requested-With': 'XMLHttpRequest'
                }

                logger.info(f"Fetching video info (attempt {attempt + 1}/{max_retries}) via GET...")
                # Try non-www first, then www as fallback
                api_urls = [
                    "https://tikwm.com/api",
                    "https://www.tikwm.com/api"
                ]
                last_exc = None
                data = None
                for api_url in api_urls:
                    try:
                        resp = requests.get(api_url, params=payload, headers=headers, timeout=20)
                        resp.raise_for_status()
                        data = resp.json()
                        break
                    except Exception as _e:
                        last_exc = _e
                        logger.warning(f"GET {api_url} failed: {str(_e)}")
                        continue
                if data is None:
                    raise Exception(f"All TikWM endpoints failed: {last_exc}")
                if data.get('code') != 0 or not data.get('data'):
                    error_msg = data.get('msg', 'No video data found in API response')
                    logger.error(f"TikWM error: code={data.get('code')} msg={error_msg} input={tikwm_input}")
                    raise Exception(f"API error: {error_msg}")
                
                video_data = data['data']
                # Collect candidate URLs (highest quality first)
                candidates_raw = [
                    video_data.get('hdplay'),
                    video_data.get('play'),
                    video_data.get('wmplay'),
                    video_data.get('download_url')
                ]
                candidates_raw = [u for u in candidates_raw if u]
                if not candidates_raw:
                    logger.error(f"No usable video URL in TikWM response: keys={list(video_data.keys())}")
                    raise Exception("No video URL found in API response")

                # Normalize to absolute URLs
                from urllib.parse import urljoin
                base = "https://www.tikwm.com"
                def normalize(u: str) -> str:
                    if u.startswith('//'):
                        return 'https:' + u
                    if u.startswith('/'):
                        return urljoin(base, u)
                    return u

                candidates = [normalize(u) for u in candidates_raw]

                # Probe candidates via HEAD to choose the largest Content-Length
                best_url = None
                best_size = -1
                probe_headers = {
                    'User-Agent': headers['User-Agent'],
                    'Referer': headers['Referer'],
                    'Accept': '*/*'
                }
                for cu in candidates:
                    try:
                        r_head = requests.head(cu, headers=probe_headers, allow_redirects=True, timeout=15)
                        if r_head.status_code >= 400:
                            logger.warning(f"HEAD probe failed {r_head.status_code} for {cu}")
                            continue
                        size = int(r_head.headers.get('content-length', '0') or '0')
                        logger.info(f"Candidate {cu} content-length={size}")
                        if size > best_size:
                            best_size = size
                            best_url = cu
                    except Exception as pe:
                        logger.warning(f"HEAD probe error for {cu}: {pe}")
                        continue

                video_url = best_url or candidates[0]
                
                # Generate a safe filename
                video_title = video_data.get('title', f'tiktok_{video_id}')
                safe_title = re.sub(r'[^\w\s-]', '', video_title).strip()
                safe_title = safe_title[:100]  # Limit length
                filename = f"{safe_title}.mp4"
                
                # Download the video with progress tracking
                logger.info(f"Downloading video from: {video_url}")
                video_headers = {
                    'User-Agent': headers['User-Agent'],
                    'Referer': headers['Referer'],
                    'Accept': 'video/mp4,video/*;q=0.9,*/*;q=0.8'
                }
                video_response = requests.get(video_url, headers=video_headers, stream=True, timeout=60)
                video_response.raise_for_status()
                
                # Get total size for progress tracking
                total_size = int(video_response.headers.get('content-length', 0))
                downloaded_size = 0
                
                # Save video to temp file
                with open(temp_path, 'wb') as f:
                    for chunk in video_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            # Log progress every 5%
                            if total_size > 0 and (downloaded_size * 100 // total_size) % 5 == 0:
                                progress = (downloaded_size / total_size) * 100
                                await log_progress(progress)
                
                # Verify the file was downloaded correctly
                if os.path.getsize(temp_path) == 0:
                    raise Exception("Downloaded file is empty")
                
                logger.info("Download completed successfully")
                
                # Add to download history
                add_to_history({
                    'type': 'tiktok',
                    'title': video_title,
                    'url': url,
                    'filename': filename,
                    'timestamp': int(time.time())
                })
                
                # Clean up old files
                cleanup_old_files()
                
                # Move temp file into downloads with sanitized name, keep it, and return JSON
                os.makedirs('downloads', exist_ok=True)
                dest_path = os.path.join('downloads', filename)
                try:
                    if os.path.abspath(temp_path) != os.path.abspath(dest_path):
                        if os.path.exists(dest_path):
                            os.remove(dest_path)
                        shutil.move(temp_path, dest_path)
                    else:
                        # Already in place
                        pass
                except Exception as e:
                    logger.warning(f"Move failed, keeping temp file: {e}")
                    dest_path = temp_path

                # Clean up old files but keep most recent 5
                cleanup_folder('downloads', max_files=5)

                return {
                    "success": True,
                    "filePath": os.path.abspath(dest_path),
                    "title": video_title,
                    "format": 'mp4'
                }
                
            except Exception as e:
                if attempt == max_retries - 1:  # Last attempt
                    logger.error(f"All download attempts failed: {str(e)}")
                    raise
                
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying...")
                time.sleep(1)  # Wait before retrying
                
    except Exception as e:
        # Clean up temp file if something went wrong
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up temp file: {cleanup_error}")
        
        error_msg = f"Failed to download TikTok video: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/download/youtube")
async def download_youtube(request: Request):
    try:
        # Log the raw request data for debugging
        raw_body = await request.body()
        logger.info(f"Raw request body: {raw_body}")
        
        try:
            data = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
            
        logger.info(f"Received request data: {data}")
        
        url = data.get('url')
        raw_format = (data.get('format') or 'mp4')
        normalized = str(raw_format).strip().lower()
        if normalized in ['video', 'mp4']:
            format_type = 'video'
        elif normalized in ['audio', 'mp3']:
            format_type = 'audio'
        else:
            format_type = 'video'
        
        if not url:
            logger.error("No URL provided in request")
            raise HTTPException(status_code=400, detail="URL is required")
            
        logger.info(f"Starting YouTube download for URL: {url}, format: {format_type}")
        
        # Create downloads directory if it doesn't exist
        os.makedirs("downloads", exist_ok=True)
        
        # Configure different options for video vs audio
        if format_type == "video":
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': 'downloads/%(title)s.%(ext)s',
                'merge_output_format': 'mp4',
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
                'ffmpeg_location': os.path.dirname(FFMPEG_PATH) if os.path.dirname(FFMPEG_PATH) else None,
                'logger': logging.getLogger(__name__),
                'progress_hooks': [
                    lambda d: logger.info(f"Video download progress: {d.get('_percent_str', '')} - {d.get('_speed_str', '')}")
                ],
                'quiet': False,
                'no_warnings': False,
            }
        else:
            # For audio downloads
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'downloads/%(title)s.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'ffmpeg_location': os.path.dirname(FFMPEG_PATH) if os.path.dirname(FFMPEG_PATH) else None,
                'logger': logging.getLogger(__name__),
                'progress_hooks': [
                    lambda d: logger.info(f"Audio download progress: {d.get('_percent_str', '')} - {d.get('_speed_str', '')}")
                ],
                'quiet': False,
                'no_warnings': False,
                'extractaudio': True,  # Only keep the audio
                'audioformat': 'mp3',  # Convert to mp3
                'noplaylist': True,    # Download only the video, not the whole playlist
            }
        
        attempts = [ydl_opts]
        if format_type == "video":
            fallback_opts = dict(ydl_opts)
            fallback_opts['format'] = 'bestvideo+bestaudio/best'
            fallback_opts.setdefault('merge_output_format', 'mp4')
            fallback_opts.setdefault('postprocessors', [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }])
            attempts.append(fallback_opts)

        info = None
        prepared = None
        dir_name = 'downloads'
        last_error = None

        for attempt_index, opts in enumerate(attempts, start=1):
            try:
                attempt_label = "primary" if attempt_index == 1 else f"fallback #{attempt_index - 1}"
                logger.info(f"Extracting video info... ({attempt_label})")
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    logger.info(f"Video info: {info.get('title', 'Unknown')}")

                    prepared = ydl.prepare_filename(info)
                    logger.info(f"Prepared filename (pre-postprocessing): {prepared}")
                dir_name = os.path.dirname(prepared) or 'downloads'
                break
            except yt_dlp.DownloadError as e:
                last_error = e
                logger.warning(
                    f"YouTube download attempt {attempt_index} with format '{opts.get('format')}' failed: {e}"
                )
                info = None
                continue

        if info is None or prepared is None:
            error_msg = f"YouTube download error: {last_error}" if last_error else "YouTube download error"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=str(last_error) if last_error else error_msg)

        orig_base = os.path.basename(prepared)
        title_stem = os.path.splitext(orig_base)[0]

        # Desired extension after post-processing
        desired_ext = '.mp4' if format_type == 'video' else '.mp3'

        # After yt-dlp postprocessing, the extension may have changed (e.g., to .mp3)
        # Search the downloads directory for a file that matches the title stem
        try:
            candidates = os.listdir(dir_name)
        except FileNotFoundError:
            candidates = []

        logger.info(f"Directory contents after download: {candidates}")

        def find_output_file():
            lower_stem = title_stem.lower()
            preferred_match = None
            fallback_match = None
            for f in candidates:
                f_lower = f.lower()
                if f_lower.startswith(lower_stem):
                    full = os.path.join(dir_name, f)
                    if f_lower.endswith(desired_ext):
                        preferred_match = full
                        break
                    if fallback_match is None:
                        fallback_match = full
            return preferred_match or fallback_match

        found_path = find_output_file()
        if not found_path:
            error_msg = f"Downloaded file not found for title: {title_stem} in {dir_name}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        # Compute sanitized final name with correct extension
        sanitized_stem = sanitize_filename(title_stem)
        final_basename = sanitized_stem + desired_ext
        final_path = os.path.join(dir_name, final_basename)

        # If the found file path doesn't already match the sanitized final path, rename it
        try:
            if os.path.abspath(found_path) != os.path.abspath(final_path):
                if os.path.exists(final_path):
                    os.remove(final_path)
                os.rename(found_path, final_path)
                logger.info(f"Renamed output file to sanitized name: {final_path}")
        except Exception as e:
            logger.warning(f"Could not rename file to sanitized name: {e}. Using found file path.")
            final_path = found_path

        filename = final_path
        abs_path = os.path.abspath(filename)
        logger.info(f"Resolved output filename: {filename}")
        logger.info(f"Absolute path: {abs_path}")

        # Check if file exists (case-insensitive on Windows)
        if not os.path.exists(filename):
            dir_path = os.path.dirname(filename)
            file_name = os.path.basename(filename)
            try:
                files = os.listdir(dir_path)
                logger.info(f"Directory contents: {files}")
                for f in files:
                    if f.lower() == file_name.lower():
                        filename = os.path.join(dir_path, f)
                        logger.info(f"Found matching file with different case: {filename}")
                        break
            except Exception as e:
                logger.error(f"Error listing directory contents: {str(e)}")

            if not os.path.exists(filename):
                error_msg = f"Downloaded file not found at: {filename}"
                logger.error(error_msg)
                raise HTTPException(status_code=500, detail=error_msg)

        safe_name = safe_filename(
            os.path.basename(filename),
            default_extension='mp4' if format_type == 'video' else 'mp3'
        )

        logger.info(f"Sending file response for: {filename} (safe name: {safe_name})")

        if not os.path.exists(filename):
            error_msg = f"File not found after download: {filename}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        cleanup_folder("downloads")
        return {
            "success": True,
            "filePath": os.path.abspath(filename),
            "title": info.get('title') or os.path.splitext(os.path.basename(filename))[0],
            "format": 'mp4' if format_type == 'video' else 'mp3'
        }
            
    except HTTPException as he:
        logger.error(f"HTTP Exception: {he.detail}")
        raise
    except json.JSONDecodeError as je:
        error_msg = f"Invalid JSON data: {str(je)}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_msg = f"Unexpected error in YouTube download: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    finally:
        logger.info("YouTube download request completed")


@app.post("/download/instagram")
async def download_instagram(request: Request):
    try:
        data = await request.json()
        url = (data.get('url') or '').strip()
        if not url:
            raise HTTPException(status_code=400, detail="URL is required")

        raw_format = (data.get('format') or 'mp4')
        normalized = str(raw_format).strip().lower()
        if normalized in ['video', 'mp4']:
            format_type = 'video'
        elif normalized in ['audio', 'mp3']:
            format_type = 'audio'
        else:
            format_type = 'video'

        logger.info(f"Starting Instagram download for URL: {url}, format: {format_type}")
        os.makedirs("downloads", exist_ok=True)

        base = f"instagram_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        outtmpl = os.path.join("downloads", base + ".%(ext)s")

        ydl_opts = {
            'ignoreconfig': True,
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,
            'outtmpl': outtmpl,
            'ffmpeg_location': FFMPEG_PATH,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
            'extractor_args': {
                'instagram': {
                    'api_version': 'v1',
                }
            },
            'age_limit': None,
            'skip_unavailable_fragments': True,
        }
        
        cookies_file = os.path.join(os.getcwd(), 'instagram_cookies.txt')
        if os.path.exists(cookies_file):
            ydl_opts['cookiefile'] = cookies_file
            logger.info(f"Using cookies from {cookies_file}")

        if format_type == 'audio':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'prefer_ffmpeg': True,
            })
            desired_ext = '.mp3'
        else:
            ydl_opts.update({
                'format': 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best',
                'merge_output_format': 'mp4',
                'prefer_ffmpeg': True,
            })
            desired_ext = '.mp4'

        info = None
        downloaded_path = None
        is_photo = False
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                is_playlist = info.get('_type') == 'playlist'
                entries = info.get('entries', []) if is_playlist else [info]
                
                if is_playlist and entries:
                    for entry in entries:
                        try:
                            prepared = ydl.prepare_filename(entry)
                            if prepared and os.path.exists(prepared):
                                downloaded_path = prepared
                                break
                        except:
                            continue
                else:
                    try:
                        prepared = ydl.prepare_filename(info)
                        if prepared and os.path.exists(prepared):
                            downloaded_path = prepared
                    except:
                        pass
        
        except Exception as e:
            error_msg = str(e)
            if "No video formats found" in error_msg or "No media found" in error_msg:
                logger.info(f"No video found, attempting to download photos with gallery-dl: {url}")
                is_photo = True
                
                try:
                    downloads_dir = os.path.join(os.getcwd(), 'downloads')
                    os.makedirs(downloads_dir, exist_ok=True)
                    
                    gallery_dl_cmd = [
                        'gallery-dl',
                        '--cookies', cookies_file if os.path.exists(cookies_file) else '',
                        '--destination', downloads_dir,
                        '--directory', '',
                        '--filename', f'{base}_{{num}}.{{extension}}',
                        '--no-part',
                        url
                    ]
                    
                    if not os.path.exists(cookies_file):
                        gallery_dl_cmd.remove('--cookies')
                        gallery_dl_cmd.remove('')
                    
                    logger.info(f"Running gallery-dl for Instagram photos")
                    result = subprocess.run(
                        gallery_dl_cmd,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    if result.returncode != 0:
                        logger.error(f"gallery-dl failed: {result.stderr}")
                        raise Exception(f"gallery-dl failed: {result.stderr or result.stdout}")
                    
                    # gallery-dl creates subdirectories like downloads/instagram/username/
                    # Search recursively for ALL jpg/png files created in the last minute
                    found_files = []
                    current_time = time.time()
                    
                    for root, dirs, files in os.walk(downloads_dir):
                        for f in files:
                            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                                full_path = os.path.join(root, f)
                                # Check if file was created in the last 60 seconds
                                if (current_time - os.path.getctime(full_path)) < 60:
                                    found_files.append((full_path, os.path.getctime(full_path)))
                    
                    if found_files:
                        # Sort by creation time and filename
                        found_files.sort(key=lambda x: (x[1], x[0]), reverse=True)
                        
                        if len(found_files) == 1:
                            # Single image
                            source_path = found_files[0][0]
                            final_path = os.path.join(downloads_dir, f"{base}.jpg")
                            
                            try:
                                if source_path != final_path:
                                    if os.path.exists(final_path):
                                        os.remove(final_path)
                                    shutil.copy2(source_path, final_path)
                                    downloaded_path = final_path
                                else:
                                    downloaded_path = source_path
                                logger.info(f"Downloaded single Instagram photo: {downloaded_path}")
                            except Exception as copy_err:
                                logger.error(f"Failed to copy file: {str(copy_err)}\n{traceback.format_exc()}")
                                downloaded_path = source_path
                        else:
                            # Multiple images - return array of paths instead of zip
                            logger.info(f"Found {len(found_files)} Instagram photos, returning as array")
                            downloaded_path = [os.path.abspath(fp) for fp, _ in found_files]
                        
                        info = {'title': 'instagram_photos'}
                    
                    if not downloaded_path:
                        raise Exception("gallery-dl completed but no image file was found")
                        
                except Exception as photo_error:
                    logger.error(f"Photo download failed: {str(photo_error)}\n{traceback.format_exc()}")
                    raise HTTPException(status_code=500, detail=f"Failed to download Instagram photos: {str(photo_error)}")
            else:
                logger.error(f"Instagram download error: {str(e)}\n{traceback.format_exc()}")
                raise HTTPException(status_code=500, detail=f"Instagram download failed: {str(e)}")

        if downloaded_path is None:
            downloads_dir = os.path.join(os.getcwd(), 'downloads')
            candidates = []
            try:
                candidates = sorted(os.listdir(downloads_dir), key=lambda x: os.path.getmtime(os.path.join(downloads_dir, x)), reverse=True)
            except Exception:
                candidates = []

            for f in candidates:
                full = os.path.join(downloads_dir, f)
                if not os.path.isfile(full):
                    continue
                if os.path.getmtime(full) < (time.time() - 30):
                    break
                f_lower = f.lower()
                if f_lower.endswith(('.mp4', '.jpg', '.jpeg', '.png', '.webp')):
                    downloaded_path = full
                    if f_lower.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        is_photo = True
                    break

        # Validate downloaded_path (can be string or list)
        if not downloaded_path:
            raise HTTPException(
                status_code=500,
                detail="Instagram download failed. Could not find downloaded file."
            )
        
        if isinstance(downloaded_path, str) and not os.path.exists(downloaded_path):
            raise HTTPException(
                status_code=500,
                detail="Instagram download failed. Could not find downloaded file."
            )

        # Handle array of paths (multiple images) or single path
        if isinstance(downloaded_path, list):
            # Multiple images - return array
            # Don't run cleanup for multiple images - files are still being accessed by frontend
            return {
                "success": True,
                "filePaths": downloaded_path,  # Array of paths
                "isMultiple": True,
                "title": (info.get('title') if isinstance(info, dict) else None) or "instagram_photos",
                "format": 'jpg'
            }
        else:
            # Single file
            cleanup_folder("downloads", exclude_file=downloaded_path)
            return {
                "success": True,
                "filePath": os.path.abspath(downloaded_path),
                "isMultiple": False,
                "title": (info.get('title') if isinstance(info, dict) else None) or "instagram_video",
                "format": 'mp4' if format_type == 'video' else 'mp3'
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Instagram download error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Instagram download failed: {str(e)}")

@app.get("/recent")
async def recent_files():
    try:
        entries = []
        for folder, ftype in [("downloads", "download"), ("converted", "converted")]:
            if not os.path.isdir(folder):
                continue
            for name in os.listdir(folder):
                full = os.path.join(folder, name)
                if os.path.isfile(full):
                    try:
                        mtime = os.path.getmtime(full)
                        ext = os.path.splitext(name)[1].lower()
                        media_type = 'audio' if ext in ['.mp3', '.wav', '.m4a', '.aac', '.ogg'] else 'video'
                        entries.append({
                            "filePath": os.path.abspath(full),
                            "filename": name,
                            "modified": mtime,
                            "source": ftype,
                            "mediaType": media_type,
                        })
                    except Exception:
                        continue
        # Sort by modified desc and keep last 5
        entries.sort(key=lambda x: x["modified"], reverse=True)
        return {"success": True, "items": entries[:5]}
    except Exception as e:
        logger.error(f"/recent error: {e}")
        return {"success": False, "items": [], "error": str(e)}


def _audd_recognize(file_path: str, api_key: str) -> dict:
    """Recognize audio using AudD API. Returns parsed JSON or error dict.
    Requires AUDD_API_KEY in environment.
    """
    try:
        if not os.path.exists(file_path):
            return {"status": "error", "error": f"File not found: {file_path}"}
        with open(file_path, 'rb') as f:
            files = {"file": (os.path.basename(file_path), f, "audio/mpeg")}
            data = {
                "api_token": api_key,
                "return": "spotify,deezer,apple_music",
            }
            r = requests.post("https://api.audd.io/", data=data, files=files, timeout=45)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.warning(f"AudD recognition error: {e}")
        return {"status": "error", "error": str(e)}


@app.post("/copyright/check")
async def check_copyright(request: Request):
    """
    Best-effort assessment whether media is usable for commercial use.
    Inputs (JSON): { url?, platform?: 'youtube'|'tiktok'|..., filePath?, mode?: 'auto'|'metadata'|'fingerprint' }
    Returns: { success, source, assessment: { allowedCommercialUse, riskLevel, confidence, license, notes[], recognized?, summary } }
    NOTE: This is NOT legal advice.
    """
    try:
        try:
            payload = await request.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

        url = (payload.get("url") or "").strip() or None
        platform = (payload.get("platform") or "").strip().lower() or None
        file_path = payload.get("filePath") or None
        mode = (payload.get("mode") or "auto").strip().lower()

        if not url and not file_path:
            raise HTTPException(status_code=400, detail="Provide 'url' or 'filePath'")

        # Auto-detect platform from URL if not provided
        if url and not platform:
            if "youtu" in url:
                platform = "youtube"
            elif "tiktok.com" in url:
                platform = "tiktok"
            else:
                platform = "generic"

        notes: List[str] = []
        license_str: Optional[str] = None
        allowed: Optional[bool] = None
        risk = "medium"
        confidence = 0.4
        recognized: Optional[Dict] = None

        # 1) Metadata assessment via yt-dlp (if URL present)
        info = None
        if url and mode in ("auto", "metadata"):
            try:
                with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                    info = ydl.extract_info(url, download=False)
            except Exception as e:
                notes.append(f"Metadata extraction failed: {e}")

            if platform == "youtube":
                license_str = (info or {}).get("license")
                if license_str:
                    notes.append(f"YouTube license: {license_str}")
                # Heuristic: Creative Commons often indicates commercial use allowed with attribution
                if license_str and "creative commons" in license_str.lower():
                    allowed = True
                    risk = "medium"
                    confidence = max(confidence, 0.7)
                    notes.append("CC-BY on YouTube typically allows commercial use with attribution. Verify terms and give proper credit.")
                else:
                    # Standard YouTube license or unknown
                    allowed = False
                    risk = "high"
                    confidence = max(confidence, 0.7)
                    notes.append("Standard YouTube License or unknown license: commercial use not permitted.")

                # If clearly a music track, increase caution
                cats = ((info or {}).get("categories") or [])
                if any((c or "").lower() == "music" for c in cats) or (info and (info.get("track") or info.get("artist"))):
                    notes.append("Detected music-related metadata; heightened infringement risk.")

            elif platform == "tiktok":
                allowed = False
                risk = "high"
                confidence = max(confidence, 0.6)
                notes.append("TikTok sounds and music are generally not licensed for commercial use outside TikTok.")
                music_meta = (info or {}).get("music")
                if isinstance(music_meta, dict):
                    title = music_meta.get("title") or ""
                    author = music_meta.get("author") or ""
                    if title or author:
                        notes.append(f"Detected music: {title} by {author}")
            else:
                notes.append("Unknown platform; cannot determine license from metadata.")

        # 2) Optional fingerprinting via AudD if file available and API key present
        audd_key = os.getenv("AUDD_API_KEY")
        if file_path and (mode in ("auto", "fingerprint")) and audd_key:
            try:
                resp = _audd_recognize(file_path, audd_key)
                if resp and resp.get("result"):
                    r = resp["result"]
                    recognized = {
                        "title": r.get("title"),
                        "artist": r.get("artist"),
                        "album": (r.get("album", {}) or {}).get("title") if isinstance(r.get("album"), dict) else r.get("album"),
                        "label": r.get("label"),
                        "timecode": r.get("timecode"),
                    }
                    # Recognized commercial track => high risk, not allowed
                    allowed = False
                    risk = "high"
                    confidence = max(confidence, 0.85)
                    notes.append(f"Audio fingerprint matched: {recognized.get('title') or ''} - {recognized.get('artist') or ''}")
                elif resp and resp.get("status") == "error":
                    notes.append(f"AudD error: {resp.get('error')}")
                else:
                    notes.append("AudD: No match found. This doesn't guarantee rights.")
            except Exception as e:
                notes.append(f"AudD recognition failed: {e}")
        elif file_path and (mode in ("auto", "fingerprint")) and not audd_key:
            notes.append("Set AUDD_API_KEY in .env to enable audio fingerprint checks.")

        # Summary
        if allowed is True:
            summary = "Likely OK with attribution (Creative Commons detected). Verify terms and credits."
        elif allowed is False:
            summary = "Not safe for commercial use (standard/unknown license or copyrighted content)."
        else:
            summary = "Unable to determine. Treat as not safe unless you own or have explicit rights."

        return {
            "success": True,
            "source": platform or ("file" if file_path else None),
            "assessment": {
                "allowedCommercialUse": allowed,
                "riskLevel": risk,
                "confidence": round(confidence, 2),
                "license": license_str,
                "notes": notes,
                "recognized": recognized,
                "summary": summary,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"/copyright/check error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
