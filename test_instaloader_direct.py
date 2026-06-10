import instaloader
import os

url = "https://www.instagram.com/p/DU51yg_kV70/?utm_source=ig_web_copy_link&igsh=NTc4MTIwNjQ2YQ=="
shortcode = url.split('/p/')[1].split('/')[0].split('?')[0]

print(f"Shortcode: {shortcode}")

downloads_dir = os.path.join(os.getcwd(), 'downloads')
os.makedirs(downloads_dir, exist_ok=True)

try:
    L = instaloader.Instaloader(
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False
    )
    
    print("Fetching post...")
    post = instaloader.Post.from_shortcode(L.context, shortcode)
    print(f"Post found: {post.caption[:50] if post.caption else 'No caption'}")
    
    print("Downloading...")
    L.download_post(post, target="downloads")
    
    print("Download complete!")
    print("Files in downloads:")
    for f in os.listdir(downloads_dir):
        print(f"  - {f}")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
