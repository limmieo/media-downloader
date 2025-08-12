 

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
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
import unicodedata

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

def sanitize_filename(name: str) -> str:
    """Sanitize a filename stem:
    - Normalize to NFC
    - Remove control and invalid filesystem characters
    - Collapse whitespace and trim
    - Return ASCII-only by removing non-ASCII characters
    """
    if not isinstance(name, str):
        name = str(name)
    s = unicodedata.normalize('NFC', name)
    # Remove invalid characters for Windows filesystems
    s = re.sub(r'[\\/*?:"<>|]', ' ', s)
    # Remove control chars
    s = re.sub(r'[\x00-\x1f\x7f]', '', s)
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    # Remove non-ASCII for safety in HTTP headers and cross-platform
    s = s.encode('ascii', errors='ignore').decode('ascii')
    # Fallback if empty
    if not s:
        s = 'download'
    # Limit length
    return s[:120]

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
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import urlparse
from schemas import ConvertResponse, ErrorResponse

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

# Root index route
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# CORS (tight allowlist: adjust as needed)
ALLOWED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Create directories if they don't exist
os.makedirs("downloads", exist_ok=True)
os.makedirs("converted", exist_ok=True)

# Simple in-memory job manager (can be swapped for Redis/DB later)
import asyncio
import uuid

class Job:
    def __init__(self, job_type: str):
        self.id = str(uuid.uuid4())
        self.type = job_type
        self.state = "queued"  # queued|running|done|error
        self.progress = 0.0
        self.message = ""
        self.result: dict | None = None
        self.events: asyncio.Queue[str] = asyncio.Queue()
        self.created_at = time.time()

    def to_dict(self):
        return {
            "id": self.id,
            "state": self.state,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "type": self.type,
        }

jobs: dict[str, Job] = {}

async def sse_event_generator(job: Job):
    try:
        # Send initial state
        yield f"data: {json.dumps(job.to_dict())}\n\n"
        while True:
            msg = await job.events.get()
            yield f"data: {msg}\n\n"
    except asyncio.CancelledError:
        return

def job_emit(job: Job, progress: float | None = None, message: str | None = None, result: dict | None = None):
    if progress is not None:
        job.progress = float(max(0.0, min(100.0, progress)))
    if message is not None:
        job.message = message
    if result is not None:
        job.result = result
    # Push event payload
    payload = json.dumps(job.to_dict())
    try:
        job.events.put_nowait(payload)
    except Exception:
        pass

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
        ffmpeg_path = r"C:\\ffmpeg-7.1.1-essentials_build\\bin\\ffmpeg.exe"

        # Ensure the command starts with ffmpeg path
        if isinstance(cmd, list) and cmd and str(cmd[0]).lower() == 'ffmpeg':
            cmd[0] = ffmpeg_path

        logger.info(f"Executing FFmpeg command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            shell=False,
            timeout=900  # 15 minutes default timeout
        )
        logger.info("FFmpeg command executed successfully")
        return True, ""
    except subprocess.TimeoutExpired:
        error_msg = "FFmpeg timed out"
        logger.error(f"{error_msg}\nCommand: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        return False, error_msg
    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg error: {e.stderr}"
        logger.error(f"{error_msg}\nCommand: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"{error_msg}\nCommand: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        return False, error_msg

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"An error occurred: {str(exc)}",
            "code": "internal_error"
        }
    )

def _is_allowed_host(url: str, allowed_hosts: set[str]) -> bool:
    try:
        p = urlparse(url)
        host = (p.netloc or '').lower()
        host = host.split(':')[0]  # strip port
        return host in allowed_hosts
    except Exception:
        return False

# Job management endpoints
@app.post("/v1/jobs")
async def create_job(job_type: str = Form("generic")):
    job = Job(job_type)
    jobs[job.id] = job
    return {"id": job.id, "state": job.state, "type": job.type}

@app.get("/v1/jobs/{job_id}")
async def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()

@app.get("/v1/jobs/{job_id}/events")
async def job_events(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return StreamingResponse(sse_event_generator(job), media_type="text/event-stream")

@app.post("/download/tiktok")
@app.post("/v1/download/tiktok")
async def download_tiktok(request: Request, job_id: str | None = None):
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
        job: Job | None = None
        if job_id and job_id in jobs:
            job = jobs[job_id]
            job.state = "running"
            job_emit(job, progress=0.0, message="Starting TikTok download")

        # Validate allowed host for TikTok
        allowed_tiktok_hosts = {"www.tiktok.com", "tiktok.com", "vm.tiktok.com", "t.tiktok.com"}
        if urlparse(url).scheme in {"file"} or not _is_allowed_host(url, allowed_tiktok_hosts):
            raise HTTPException(status_code=400, detail="Unsupported or unsafe TikTok URL host")
        
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
                
                # Generate a sanitized filename stem and final path in downloads/
                video_title = video_data.get('title', f'tiktok_{video_id}')
                stem = sanitize_filename(video_title)
                os.makedirs("downloads", exist_ok=True)
                final_path = os.path.join("downloads", f"{stem}.mp4")
                
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
                                if job:
                                    job_emit(job, progress=progress, message=f"Downloading {progress:.1f}%")
                
                # Verify the file was downloaded correctly
                if os.path.getsize(temp_path) == 0:
                    raise Exception("Downloaded file is empty")
                
                logger.info("Download completed successfully")

                # Add to download history
                add_to_history({
                    'type': 'tiktok',
                    'title': stem,
                    'url': url,
                    'filename': f"{stem}.mp4",
                    'timestamp': int(time.time())
                })
                
                # Move from temp to downloads and clean up old files
                try:
                    # Remove existing file if same name exists
                    if os.path.exists(final_path):
                        os.remove(final_path)
                    shutil.move(temp_path, final_path)
                    logger.info(f"Moved TikTok download to: {final_path}")
                finally:
                    # Ensure temp file is not left behind
                    try:
                        if os.path.exists(temp_path):
                            os.unlink(temp_path)
                    except Exception:
                        pass
                cleanup_folder("downloads", max_files=5)
                
                # Return the file for download
                if job:
                    job.state = "done"
                    job_emit(job, progress=100.0, message="TikTok download complete", result={"filename": f"{stem}.mp4"})

                return FileResponse(
                    final_path,
                    filename=f"{stem}.mp4",
                    media_type='video/mp4',
                    headers={
                        'Content-Disposition': f'attachment; filename="{stem}.mp4"',
                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                        'Pragma': 'no-cache',
                        'Expires': '0'
                    }
                )
                
            except Exception as e:
                if attempt == max_retries - 1:  # Last attempt
                    logger.error(f"All download attempts failed: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"Failed to download TikTok video: {str(e)}")
                    raise
                
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying...")
                time.sleep(1)  # Wait before retrying
                
    except HTTPException as he:
        # Preserve explicit HTTP errors like 400 for invalid hosts
        raise he
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
        if job_id and job_id in jobs:
            j = jobs[job_id]
            j.state = "error"
            job_emit(j, message=error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/download/youtube")
@app.post("/v1/download/youtube")
async def download_youtube(request: Request, job_id: str | None = None):
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

        # Validate allowed host for YouTube
        allowed_youtube_hosts = {"www.youtube.com", "youtube.com", "youtu.be", "m.youtube.com"}
        if urlparse(url).scheme in {"file"} or not _is_allowed_host(url, allowed_youtube_hosts):
            raise HTTPException(status_code=400, detail="Unsupported or unsafe YouTube URL host")
        
        # Create downloads directory if it doesn't exist
        os.makedirs("downloads", exist_ok=True)
        job: Job | None = None
        if job_id and job_id in jobs:
            job = jobs[job_id]
            job.state = "running"
            job_emit(job, progress=0.0, message="Starting YouTube download")
        
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

                # File prepared; ready to return response payload
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
                
                if job:
                    job.state = "done"
                    job_emit(job, progress=100.0, message="YouTube download complete", result={"file_path": final_path})
                safe_path_for_url = "/" + final_path.replace("\\", "/")
                return {
                    "filename": os.path.basename(final_path),
                    "message": "Download successful",
                    "file_path": safe_path_for_url
                }
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
