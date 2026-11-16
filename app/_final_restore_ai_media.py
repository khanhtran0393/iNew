import os, marshal, json, shutil

# Load the manifest entry for ai_media
with open(r'D:\iNew\reconstructed_specs\manifest.json', 'r', encoding='utf-8') as f:
    manifest = json.load(f)

# Find the ai_media entry
entry = None
for e in manifest:
    if 'ai_media' in e['path']:
        entry = e
        break

if not entry:
    print("ERROR: Could not find ai_media entry in manifest")
    exit(1)

# Load the pre-edit .pyc file (the original source)
pyc_path = r'D:\iNew\app\services\__pycache__\ai_media.cpython-313.pyc'
with open(pyc_path, 'rb') as f:
    data = f.read()
    # Skip the first 16 bytes (pyc header)
    obj = marshal.loads(data[16:])

print(f"Manifest entry: {entry['path']}")
print(f"Manifest size: {entry['size_bytes']} bytes")
print(f"Pre-edit .pyc size: {os.path.getsize(pyc_path)} bytes")

# Extract the original source from the .pyc file
import dis
dis_lines = []
for instr in dis.get_instructions(obj):
    dis_lines.append(f'{instr.offset:4d}: {instr.opname:<20} {instr.argrepr}')

print(f"\nPre-edit .pyc contains {len(dis_lines)} disassembly lines")
print(f"Original source code object size: {len(obj.co_code)} bytes")

# Create a new file with the reconstructed content
reconstructed_path = r'D:\iNew\app\services\ai_media_restored.py'
with open(reconstructed_path, 'w', encoding='utf-8') as f:
    f.write('# RECONSTRUCTED FILE FROM PRE-EDIT .PYC\n')
    f.write(f'# Original size: {entry["size_bytes"]} bytes\n')
    f.write(f'# Code object size: {len(obj.co_code)} bytes\n')
    f.write(f'# Manifest offset: {entry["offset"]}\n')
    f.write(f'# Manifest size: {entry["size_bytes"]} bytes\n')
    f.write('\n')
    
    # Write the disassembly as comments to understand the structure
    f.write('# Disassembly (first 30 lines):\n')
    for i, line in enumerate(dis_lines[:30]):
        f.write(line + '\n')
    
    f.write('\n')
    f.write('# String constants (selected):\n')
    # Extract string constants from the code object
    string_constants = []
    for i, const in enumerate(obj.co_consts):
        if isinstance(const, str) and len(const) > 20:
            string_constants.append((i, const))
    
    for i, const in string_constants[:10]:
        f.write(f'{i}: {const[:50]}... ({len(const)} chars)\n')
    
    f.write('\n')
    f.write('# End of reconstruction\n')

print(f"\nReconstructed file written to: {reconstructed_path}")
print(f"Size: {os.path.getsize(reconstructed_path)} bytes")

# Verify the file can be compiled
try:
    compile(open(reconstructed_path, 'r', encoding='utf-8').read(), reconstructed_path, 'exec')
    print("✓ File compiles successfully")
except SyntaxError as e:
    print(f"✗ Syntax error: {e}")

# Compare with original .pyc size
original_size = entry["size_bytes"]
current_size = os.path.getsize(reconstructed_path)
print(f"\nSize comparison:")
print(f"  Original .pyc: {original_size} bytes")
print(f"  Reconstructed: {current_size} bytes")
print(f"  Difference: {original_size - current_size} bytes")