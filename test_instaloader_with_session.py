import instaloader
import os
import time

url = "https://www.instagram.com/p/DU51yg_kV70/"
shortcode = "DU51yg_kV70"

L = instaloader.Instaloader(
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    save_metadata=False,
    compress_json=False,
    post_metadata_txt_pattern='',
    filename_pattern='{shortcode}'
)

try:
    L.load_session_from_file('instaloader_session')
    print("Session loaded successfully")
except Exception as e:
    print(f"Failed to load session: {e}")

try:
    print(f"Fetching post {shortcode}...")
    post = instaloader.Post.from_shortcode(L.context, shortcode)
    print(f"Post found! Caption: {post.caption[:50] if post.caption else 'No caption'}...")
    print(f"Is video: {post.is_video}")
    print(f"Media count: {post.mediacount}")
    
    print("\nDownloading to downloads folder...")
    os.makedirs("downloads", exist_ok=True)
    L.download_post(post, target="downloads")
    
    print("\nDownloaded files:")
    for f in os.listdir('downloads'):
        full_path = os.path.join('downloads', f)
        if os.path.getmtime(full_path) > (time.time() - 30):
            print(f"  - {f}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
