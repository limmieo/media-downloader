import subprocess
import os
import json

url = "https://www.instagram.com/p/DU51yg_kV70/"

# Test gallery-dl with cookies
cmd = [
    'gallery-dl',
    '--cookies', 'instagram_cookies.txt',
    '--destination', 'downloads',
    '--filename', 'instagram_{num}.{extension}',
    url
]

print(f"Running: {' '.join(cmd)}")
result = subprocess.run(cmd, capture_output=True, text=True)

print(f"\nReturn code: {result.returncode}")
print(f"\nStdout:\n{result.stdout}")
if result.stderr:
    print(f"\nStderr:\n{result.stderr}")

print("\nFiles in downloads:")
for f in os.listdir('downloads'):
    if 'instagram' in f.lower():
        print(f"  - {f}")
