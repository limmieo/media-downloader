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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
            # Extract audio to MP3
            cmd = [
                'ffmpeg',
                '-i', input_path,          # Input file
                '-q:a', '0',              # Best audio quality (VBR)
                '-map', 'a',              # Only audio streams
                output_path
            ]
        else:
            # Convert video to MP4
            cmd = [
                'ffmpeg',
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
                
                filename = ydl.prepare_filename(info)
                logger.info(f"Prepared filename: {filename}")
                
                # Sanitize the filename to handle special characters
                dir_name = os.path.dirname(filename)
                base_name = os.path.basename(filename)
                sanitized_name = sanitize_filename(base_name)
                
                # For audio downloads, ensure .mp3 extension
                if format_type == "audio":
                    if not sanitized_name.lower().endswith('.mp3'):
                        sanitized_name = os.path.splitext(sanitized_name)[0] + '.mp3'
                
                filename = os.path.join(dir_name, sanitized_name)
                # Get the absolute path for better debugging
                abs_path = os.path.abspath(filename)
                logger.info(f"Final output filename: {filename}")
                logger.info(f"Absolute path: {abs_path}")
                logger.info(f"Directory contents before download: {os.listdir(os.path.dirname(abs_path))}")
                
                logger.info(f"Download complete. Checking if file exists: {filename}")
                logger.info(f"Directory contents after download: {os.listdir(os.path.dirname(abs_path))}")
                
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
