import zipfile
import os
import time

downloads_dir = "downloads"
base = f"instagram_{int(time.time())}"

# Find all recently created images
found_files = []
for root, dirs, files in os.walk(downloads_dir):
    for f in files:
        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            full_path = os.path.join(root, f)
            found_files.append(full_path)

print(f"Found {len(found_files)} image files:")
for f in found_files[:5]:
    print(f"  - {f}")

if found_files:
    zip_path = os.path.join(downloads_dir, f"{base}.zip")
    print(f"\nCreating zip: {zip_path}")
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for idx, file_path in enumerate(found_files[:4], 1):
                ext = os.path.splitext(file_path)[1]
                arcname = f"image_{idx}{ext}"
                print(f"  Adding: {file_path} as {arcname}")
                zipf.write(file_path, arcname)
        
        print(f"\nSuccess! Created: {zip_path}")
        print(f"Size: {os.path.getsize(zip_path)} bytes")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
