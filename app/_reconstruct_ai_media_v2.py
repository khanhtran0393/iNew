import os, marshal, types, io

# Load the pre-edit .pyc file
pyc_path = r'D:\iNew\app\services\__pycache__\ai_media.cpython-313.pyc'
with open(pyc_path, 'rb') as f:
    data = f.read()
    # skip header (first 16 bytes)
    obj = marshal.loads(data[16:])

print('=== Code object info ===')
print(f'Name: {obj.co_name}')
print(f'Filename: {obj.co_filename}')
print(f'Code size: {len(obj.co_code)} bytes')
print(f'Constants: {len(obj.co_consts)}')
print(f'Names: {len(obj.co_names)}')

# Extract the source code from the disassembly
import dis
dis_lines = []
for instr in dis.get_instructions(obj):
    dis_lines.append(f'{instr.offset:4d}: {instr.opname:<20} {instr.argrepr}')

print('\n=== First 10 disassembly lines ===')
for i in range(min(10, len(dis_lines))):
    print(dis_lines[i])

# Let's try to reconstruct the source by creating a new module
# We'll use the code object to get the actual source lines
source_lines = []
for line in dis_lines:
    # Look for lines that contain actual Python code (not just imports or docstrings)
    if 'LOAD_CONST' in line or 'STORE' in line or 'CALL_FUNCTION' in line:
        source_lines.append(line)

print(f'\n=== Total disassembly lines: {len(dis_lines)}')
print(f'=== Code-related lines: {len(source_lines)}')

# Let's write this to a file for inspection
reconstructed_path = r'D:\iNew\app\services\ai_media_reconstructed_v2.py'
with open(reconstructed_path, 'w', encoding='utf-8') as f:
    f.write('# RECONSTRUCTED FILE FROM PRE-EDIT .PYC\n')
    f.write(f'# Original size: {12109} bytes\n')
    f.write(f'# Current size: {os.path.getsize(current_py_file) if os.path.exists(current_py_file) else "N/A"}\n')
    f.write(f'# Code object size: {len(obj.co_code)} bytes\n')
    f.write('\n')
    for line in dis_lines[:50]:  # First 50 lines for inspection
        f.write(line + '\n')

print(f'\n=== Reconstructed file written to ===')
print(reconstructed_path)