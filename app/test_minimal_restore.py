import os
import marshal

print("Testing .pyc file loading...")
pyc_path = r'D:\iNew\app\services\__pycache__\ai_media.cpython-313.pyc'

try:
    with open(pyc_path, 'rb') as f:
        data = f.read()
        print(f"File size: {len(data)} bytes")
        # Check header
        header = data[:16]
        print(f"Header bytes: {header.hex()}")
        # Skip header
        obj_data = data[16:]
        obj = marshal.loads(obj_data)
        print(f"Code object size: {len(obj.co_code)} bytes")
        print("Success!")
except Exception as e:
    print(f"Error: {e}")