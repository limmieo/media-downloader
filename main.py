from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask
from pydantic import BaseModel
import os
import re
import json
import logging
import tempfile
import time
import shutil
from typing import Optional, Dict, List
from pathlib import Path
import subprocess
import urllib.parse
import mimetypes
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import yt_dlp as yt_dlp
import os
import logging
import shutil
import uuid
import subprocess
import json
import re
import time
import traceback
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

# Ensure the downloads directory exists
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

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

def safe_filename(filename: str, extension: str) -> str:
    """Create a safe filename by removing invalid characters."""
    # Remove invalid filename characters
    safe = re.sub(r'[\\/*?:"<>|]', '', filename)
    # Replace spaces with underscores
    safe = safe.replace(' ', '_')
    # Limit length and add extension
    return f"{safe[:100]}.{extension}" if len(safe) > 100 else f"{safe}.{extension}"

# TikTok API endpoints
TIKTOK_API_DOMAIN = "https://api16-normal-c-useast1a.tiktokv.com"
TIKTOK_VIDEO_URL = f"{TIKTOK_API_DOMAIN}/aweme/v1/feed/"
TIKTOK_VIDEO_INFO = f"{TIKTOK_API_DOMAIN}/aweme/v1/aweme/detail/"

# TikTok downloader API endpoints
# TikWM requires POST to /api/ with form data: url=<tiktok_url>
TIKWM_API = "https://www.tikwm.com/api/"

# Download folder
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

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
    try:
        url = f'https://www.tiktok.com/oembed?url=https://www.tiktok.com/@tiktok/video/{video_id}'
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'status': 'success',
                'data': {
                    'aweme_id': video_id,
                    'desc': data.get('title', ''),
                    'author': data.get('author_name', ''),
                    'video': {
                        'play_addr': {
                            'url_list': [data.get('thumbnail_url', '').replace('_720x720', '')]
                        },
                        'cover': data.get('thumbnail_url', '')
                    }
                }
            }
    except Exception as e:
        logger.warning(f"TikTok oEmbed method failed: {str(e)}")
    
    return {'status': 'error'}

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

# Create directories if they don't exist
os.makedirs("downloads", exist_ok=True)
os.makedirs("converted", exist_ok=True)

def cleanup_folder(folder_path, max_files=5):
    """Keep only the most recent files in a folder, delete older ones"""
    try:
        if not os.path.exists(folder_path):
            return
        
        # Get all files in the folder with their modification times
        files = []
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
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
        # Use the full path to ffmpeg
        ffmpeg_path = r"C:\ffmpeg-7.1.1-essentials_build\bin\ffmpeg.exe"
        
        # Ensure the command starts with ffmpeg path
        if cmd[0].lower() == 'ffmpeg':
            cmd[0] = ffmpeg_path
        
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
        
        # Return JSON response with file info instead of auto-downloading
        return {
            "filename": output_filename,
            "message": "Conversion successful",
            "file_path": f"/converted/{output_filename}",
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
                
                # Return the file for download
                return FileResponse(
                    temp_path,
                    filename=filename,
                    media_type='video/mp4',
                    headers={
                        'Content-Disposition': f'attachment; filename="{filename}"',
                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                        'Pragma': 'no-cache',
                        'Expires': '0'
                    },
                    background=BackgroundTask(cleanup_temp_file, temp_path)
                )
                
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
        format_type = data.get('format', 'video')
        
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
                'ffmpeg_location': r"C:\\ffmpeg-7.1.1-essentials_build\\bin",
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
                'ffmpeg_location': r"C:\\ffmpeg-7.1.1-essentials_build\\bin",
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
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info("Extracting video info...")
                info = ydl.extract_info(url, download=True)
                logger.info(f"Video info: {info.get('title', 'Unknown')}")
                
                prepared = ydl.prepare_filename(info)
                logger.info(f"Prepared filename (pre-postprocessing): {prepared}")

                dir_name = os.path.dirname(prepared) or 'downloads'
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
                    preferred = None
                    fallback = None
                    for f in candidates:
                        f_lower = f.lower()
                        if f_lower.startswith(lower_stem):
                            full = os.path.join(dir_name, f)
                            # Prefer desired extension
                            if f_lower.endswith(desired_ext):
                                return full
                            # Keep first match as fallback
                            if fallback is None:
                                fallback = full
                    return preferred or fallback

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
                        # If destination exists, remove it to avoid replace errors
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
                    # Try to find the file with a different case
                    dir_path = os.path.dirname(filename)
                    file_name = os.path.basename(filename)
                    
                    # List all files in the directory
                    try:
                        files = os.listdir(dir_path)
                        logger.info(f"Directory contents: {files}")
                        
                        # Try to find a matching file (case-insensitive)
                        for f in files:
                            if f.lower() == file_name.lower():
                                filename = os.path.join(dir_path, f)
                                logger.info(f"Found matching file with different case: {filename}")
                                break
                    except Exception as e:
                        logger.error(f"Error listing directory contents: {str(e)}")
                    
                    # If we still can't find the file, raise an error
                    if not os.path.exists(filename):
                        error_msg = f"Downloaded file not found at: {filename}"
                        logger.error(error_msg)
                        raise HTTPException(status_code=500, detail=error_msg)
                
                # Get a safe version of the filename for headers
                safe_name = safe_filename(
                    os.path.basename(filename),
                    default_extension='mp4' if format_type == 'video' else 'mp3'
                )
                
                logger.info(f"Sending file response for: {filename} (safe name: {safe_name})")
                
                # Ensure the file exists and is readable
                if not os.path.exists(filename):
                    error_msg = f"File not found after download: {filename}"
                    logger.error(error_msg)
                    raise HTTPException(status_code=500, detail=error_msg)
                
                # Clean up old files in the downloads directory
                cleanup_folder("downloads")
                
                return FileResponse(
                    filename,
                    filename=safe_name,
                    media_type='video/mp4' if format_type == "video" else 'audio/mpeg',
                    headers={
                        "Content-Disposition": f"attachment; filename=\"{safe_name}\"",
                        "Access-Control-Expose-Headers": "Content-Disposition"
                    }
                )
                
        except yt_dlp.DownloadError as e:
            error_msg = f"YouTube download error: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
            
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
