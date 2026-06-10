import yt_dlp
import json

url = "https://www.instagram.com/p/DU51yg_kV70/?utm_source=ig_web_copy_link&igsh=NTc4MTIwNjQ2YQ=="

ydl_opts = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'skip_download': True,
    'ignoreerrors': True,
    'cookiefile': 'instagram_cookies.txt',
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    },
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
        print(f"Type: {info.get('_type')}")
        print(f"Number of entries: {len(info.get('entries', []))}")
        
        if info.get('_type') == 'playlist':
            for idx, entry in enumerate(info.get('entries', [])):
                print(f"\n--- Entry {idx+1} ---")
                if entry:
                    print(f"  ID: {entry.get('id')}")
                    print(f"  URL: {entry.get('url')}")
                    print(f"  Thumbnail: {entry.get('thumbnail')}")
                    print(f"  Display URL: {entry.get('display_url')}")
                    print(f"  All keys: {list(entry.keys())}")
                else:
                    print("  Entry is None")
        else:
            print(f"\nSingle entry:")
            print(f"  URL: {info.get('url')}")
            print(f"  Thumbnail: {info.get('thumbnail')}")
            print(f"  Display URL: {info.get('display_url')}")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
