import yt_dlp
import os
import traceback

url = "https://www.instagram.com/p/DU51yg_kV70/?utm_source=ig_web_copy_link&igsh=NTc4MTIwNjQ2YQ=="

ydl_opts = {
    'ignoreconfig': True,
    'quiet': False,
    'no_warnings': False,
    'noplaylist': True,
    'outtmpl': 'downloads/test_%(id)s.%(ext)s',
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    },
    'cookiefile': 'instagram_cookies.txt',
    'format': 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best',
    'merge_output_format': 'mp4',
}

os.makedirs("downloads", exist_ok=True)

try:
    print("Starting download with cookies...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        print(f"Success! Title: {info.get('title', 'Unknown')}")
        print(f"Files in downloads:")
        for f in os.listdir('downloads'):
            print(f"  - {f}")
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
