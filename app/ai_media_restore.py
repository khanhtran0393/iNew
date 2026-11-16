import os
import marshal
import json

# Load manifest
with open(r'D:\iNew\reconstructed_specs\manifest.json', 'r', encoding='utf-8') as f:
    manifest = json.load(f)

# Find ai_media entry
entry = None
for e in manifest:
    if 'ai_media' in e['path']:
        entry = e
        break

if not entry:
    print("ERROR: ai_media entry not found")
    exit(1)

print(f"Found entry: {entry['path']}")
print(f"Size: {entry['size_bytes']} bytes")

# Load .pyc file
pyc_path = r'D:\iNew\app\services\__pycache__\ai_media.cpython-313.pyc'
with open(pyc_path, 'rb') as f:
    data = f.read()
    # Skip header (16 bytes)
    obj = marshal.loads(data[16:])

print(f".pyc size: {len(data)} bytes")
print(f"Code object size: {len(obj.co_code)} bytes")

# Write reconstructed file
out_path = r'D:\iNew\app\services\ai_media_restored.py'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('# RECONSTRUCTED FILE\n')
    f.write(f'# Size: {entry["size_bytes"]} bytes\n')
    f.write(f'# Code size: {len(obj.co_code)} bytes\n')
    
print(f"File written to: {out_path}")