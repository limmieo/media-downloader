import requests
import json
import re
import http.cookiejar
import os

url = "https://www.instagram.com/p/DU51yg_kV70/"

# Load cookies
cookies_file = 'instagram_cookies.txt'
jar = http.cookiejar.MozillaCookieJar(cookies_file)
jar.load(ignore_discard=True, ignore_expires=True)

# Convert to requests session
session = requests.Session()
for cookie in jar:
    session.cookies.set(cookie.name, cookie.value, domain=cookie.domain, path=cookie.path)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

try:
    print(f"Fetching {url}...")
    response = session.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    print(f"Status: {response.status_code}")
    
    # Extract JSON data from page
    pattern = r'window\._sharedData\s*=\s*({.+?});</script>'
    match = re.search(pattern, response.text)
    
    if match:
        data = json.loads(match.group(1))
        print("Found _sharedData!")
        
        # Navigate to post data
        entry_data = data.get('entry_data', {})
        post_page = entry_data.get('PostPage', [{}])[0]
        media = post_page.get('graphql', {}).get('shortcode_media', {})
        
        if media:
            print(f"\nPost type: {'Video' if media.get('is_video') else 'Photo'}")
            print(f"Media count: {media.get('edge_sidecar_to_children', {}).get('edges', []).__len__() or 1}")
            
            # Get image URLs
            image_urls = []
            
            # Check if it's a carousel
            if 'edge_sidecar_to_children' in media:
                for edge in media['edge_sidecar_to_children']['edges']:
                    node = edge['node']
                    if node.get('display_url'):
                        image_urls.append(node['display_url'])
            elif media.get('display_url'):
                image_urls.append(media['display_url'])
            
            print(f"\nFound {len(image_urls)} image(s):")
            for idx, img_url in enumerate(image_urls, 1):
                print(f"  {idx}. {img_url[:80]}...")
                
                # Download image
                img_response = session.get(img_url, headers=headers, timeout=30)
                img_response.raise_for_status()
                
                filename = f"downloads/instagram_photo_{idx}.jpg"
                os.makedirs("downloads", exist_ok=True)
                with open(filename, 'wb') as f:
                    f.write(img_response.content)
                print(f"     Saved to {filename}")
        else:
            print("No media data found")
    else:
        # Try alternative pattern
        pattern2 = r'<script type="application/ld\+json">({.+?})</script>'
        match2 = re.search(pattern2, response.text)
        if match2:
            print("Found LD+JSON data")
            data = json.loads(match2.group(1))
            print(json.dumps(data, indent=2)[:500])
        else:
            print("Could not find JSON data in page")
            print(f"Page length: {len(response.text)} chars")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
