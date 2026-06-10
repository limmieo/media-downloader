import requests
import json
import http.cookiejar
import os
import re

url = "https://www.instagram.com/p/DU51yg_kV70/"
shortcode = "DU51yg_kV70"

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
    'X-IG-App-ID': '936619743392459',
    'X-Requested-With': 'XMLHttpRequest',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Get CSRF token from cookies
csrf_token = None
for cookie in jar:
    if cookie.name == 'csrftoken':
        csrf_token = cookie.value
        headers['X-CSRFToken'] = csrf_token
        break

try:
    # Try the web page first to extract data
    print(f"Fetching page HTML...")
    response = session.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    # Look for embedded JSON in script tags
    patterns = [
        r'<script type="application/ld\+json">(.+?)</script>',
        r'window\.__additionalDataLoaded\([^,]+,(.+?)\);</script>',
        r'"graphql":\s*({.+?"shortcode_media".+?})',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, response.text, re.DOTALL)
        if matches:
            print(f"Found data with pattern: {pattern[:50]}...")
            for match in matches:
                try:
                    data = json.loads(match)
                    
                    # Try to find image URLs
                    def find_images(obj, images=None):
                        if images is None:
                            images = []
                        if isinstance(obj, dict):
                            if 'display_url' in obj and obj['display_url']:
                                images.append(obj['display_url'])
                            elif 'display_resources' in obj:
                                for res in obj['display_resources']:
                                    if res.get('src'):
                                        images.append(res['src'])
                            for value in obj.values():
                                find_images(value, images)
                        elif isinstance(obj, list):
                            for item in obj:
                                find_images(item, images)
                        return images
                    
                    images = find_images(data)
                    if images:
                        print(f"\nFound {len(images)} image URL(s)!")
                        for idx, img_url in enumerate(images[:4], 1):  # Limit to 4 images
                            print(f"  {idx}. {img_url[:80]}...")
                            
                            # Download
                            img_response = session.get(img_url, headers=headers, timeout=30)
                            img_response.raise_for_status()
                            
                            filename = f"downloads/instagram_photo_{idx}.jpg"
                            os.makedirs("downloads", exist_ok=True)
                            with open(filename, 'wb') as f:
                                f.write(img_response.content)
                            print(f"     ✓ Saved to {filename}")
                        
                        exit(0)
                except json.JSONDecodeError:
                    continue
    
    print("\nNo images found in embedded data. Trying direct GraphQL query...")
    
    # Try GraphQL API
    graphql_url = f"https://www.instagram.com/graphql/query/?query_hash=2b0673e0dc4580674a88d426fe00ea90&variables=%7B%22shortcode%22%3A%22{shortcode}%22%7D"
    
    graphql_response = session.get(graphql_url, headers=headers, timeout=30)
    print(f"GraphQL Status: {graphql_response.status_code}")
    
    if graphql_response.status_code == 200:
        data = graphql_response.json()
        print(json.dumps(data, indent=2)[:500])
    else:
        print(f"GraphQL failed: {graphql_response.text[:200]}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
