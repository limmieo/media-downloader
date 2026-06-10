import yt_dlp
import os
import time

url = "https://www.instagram.com/p/DU51yg_kV70/?utm_source=ig_web_copy_link&igsh=NTc4MTIwNjQ2YQ=="

ydl_opts = {
    'quiet': False,
    'no_warnings': False,
    'outtmpl': 'downloads/ig_test_%(id)s.%(ext)s',
    'cookiefile': 'instagram_cookies.txt',
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    },
    'ignoreerrors': True,
    'extract_flat': False,
}

os.makedirs("downloads", exist_ok=True)

print("Attempting to download Instagram photos...")
try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        print(f"\nExtraction complete!")
        print(f"Type: {info.get('_type')}")
        print(f"Entries: {len(info.get('entries', []))}")
        
        print("\nFiles in downloads:")
        for f in os.listdir('downloads'):
            full_path = os.path.join('downloads', f)
            if os.path.getmtime(full_path) > (time.time() - 30):
                print(f"  - {f}")
                
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
