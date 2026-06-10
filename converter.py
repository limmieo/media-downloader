import os
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MediaConverter:
    """Handles media file conversion using FFmpeg."""
    
    @staticmethod
    def is_ffmpeg_installed():
        """Check if FFmpeg is installed and available in the system PATH."""
        try:
            subprocess.run(
                ['ffmpeg', '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    @staticmethod
    def get_supported_formats():
        """Return a list of supported output formats."""
        return {
            'video': ['mp4', 'avi', 'mov', 'mkv', 'webm'],
            'audio': ['mp3', 'wav', 'aac', 'ogg', 'm4a'],
            'image': ['jpg', 'jpeg', 'png', 'gif', 'webp']
        }
    
    @staticmethod
    def get_format_category(format_name: str) -> str:
        """Determine the category of a format (video, audio, or image)."""
        formats = MediaConverter.get_supported_formats()
        for category, exts in formats.items():
            if format_name.lower() in exts:
                return category
        return 'unknown'
    
    @classmethod
    def convert_file(cls, input_path: str, output_path: str, format: str = None):
        """
        Convert a media file to the specified format.
        
        Args:
            input_path: Path to the input file
            output_path: Path where the output file will be saved
            format: Output format (if not specified, will be determined from output_path)
            
        Returns:
            dict: Result of the conversion with success status and message
        """
        try:
            # Ensure input file exists
            if not os.path.isfile(input_path):
                raise FileNotFoundError(f"Input file not found: {input_path}")
            
            # Ensure output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            # Determine format from output path if not specified
            if format is None:
                format = Path(output_path).suffix.lstrip('.').lower()
                if not format:
                    raise ValueError("Could not determine output format from path")
            
            format = format.lower()
            format_category = cls.get_format_category(format)
            
            if format_category == 'unknown':
                raise ValueError(f"Unsupported output format: {format}")
            
            # Build FFmpeg command based on format
            cmd = ['ffmpeg', '-y', '-i', input_path]
            
            # Add format-specific options
            if format_category == 'video':
                # For video formats, try to maintain reasonable quality
                cmd.extend([
                    '-c:v', 'libx264',  # H.264 codec for video
                    '-preset', 'medium',  # Balance between speed and compression
                    '-crf', '23',  # Constant Rate Factor (lower = better quality, 23 is default)
                    '-pix_fmt', 'yuv420p',  # Standard pixel format for compatibility
                    '-movflags', '+faststart',  # Enable streaming
                    '-c:a', 'aac',  # AAC audio codec
                    '-b:a', '192k'  # Audio bitrate
                ])
            elif format_category == 'audio':
                # For audio formats, strip video and convert audio
                cmd.extend([
                    '-vn',  # No video
                    '-c:a', 'libmp3lame' if format == 'mp3' else 'aac',
                    '-b:a', '192k',
                    '-ar', '44100',
                    '-ac', '2'  # Stereo
                ])
            elif format_category == 'image':
                # For image extraction, get first frame
                cmd.extend([
                    '-vframes', '1',  # Extract only one frame
                    '-q:v', '2'  # Image quality (2-31, lower is better)
                ])
            
            # Add output path
            cmd.append(output_path)
            
            # Run the command
            logger.info(f"Running command: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Stream output for progress if needed
            for line in process.stderr:
                logger.debug(line.strip())
            
            # Wait for the process to complete
            process.wait()
            
            if process.returncode != 0:
                raise subprocess.CalledProcessError(
                    process.returncode, 
                    cmd, 
                    process.stderr.read()
                )
            
            # Verify output file was created
            if not os.path.isfile(output_path):
                raise RuntimeError("Output file was not created")
            
            return {
                'success': True,
                'message': 'Conversion completed successfully',
                'output_path': output_path,
                'file_size': os.path.getsize(output_path)
            }
            
        except Exception as e:
            logger.error(f"Conversion failed: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': str(e),
                'output_path': output_path if os.path.exists(output_path) else None
            }

# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python converter.py <input_file> <output_file> [format]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    format = sys.argv[3] if len(sys.argv) > 3 else None
    
    result = MediaConverter.convert_file(input_file, output_file, format)
    print(f"Conversion {'succeeded' if result['success'] else 'failed'}: {result['message']}")
    if result['success']:
        print(f"Output file: {result['output_path']} ({result['file_size']} bytes)")
