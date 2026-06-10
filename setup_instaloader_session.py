import instaloader
import http.cookiejar
import os

# Read yt_dlp cookies and convert to instaloader session
cookies_file = 'instagram_cookies.txt'

if not os.path.exists(cookies_file):
    print("Error: instagram_cookies.txt not found")
    exit(1)

# Parse Netscape cookies
jar = http.cookiejar.MozillaCookieJar(cookies_file)
jar.load(ignore_discard=True, ignore_expires=True)

# Find sessionid cookie
sessionid = None
for cookie in jar:
    if cookie.name == 'sessionid':
        sessionid = cookie.value
        print(f"Found sessionid: {sessionid[:20]}...")
        break

if not sessionid:
    print("Error: No sessionid cookie found in instagram_cookies.txt")
    print("Available cookies:")
    for cookie in jar:
        print(f"  - {cookie.name}")
    exit(1)

# Create instaloader session
L = instaloader.Instaloader()

# Set session manually
L.context._session.cookies.set('sessionid', sessionid, domain='.instagram.com', path='/')

# Save session
try:
    L.save_session_to_file('instaloader_session')
    print("Successfully created instaloader_session file")
except Exception as e:
    print(f"Error saving session: {e}")
    
# Test the session
try:
    L.test_login()
    print("Session is valid and logged in!")
except Exception as e:
    print(f"Session test failed: {e}")
