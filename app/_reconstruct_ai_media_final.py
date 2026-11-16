import marshal
import types
import dis
import io
import os

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

# Extract all string constants
string_constants = []
for i, const in enumerate(obj.co_consts):
    if isinstance(const, str):
        string_constants.append((i, const))

print(f'\n=== String constants ===')
for i, const in string_constants:
    if len(const) > 50:  # Only show longer strings
        print(f'{i:2d}: {const[:100]}... ({len(const)} chars)')

print(f'\nTotal string constants: {len(string_constants)}')

# Let's also check what the current file looks like
current_file = r'D:\iNew\app\services\ai_media.py'
if os.path.exists(current_file):
    with open(current_file, 'r', encoding='utf-8') as f:
        current_content = f.read()
    current_size = len(current_content)
    print(f'\n=== Current file ===')
    print(f'{current_file}: {current_size} bytes')
    print(f'First 200 chars: {current_content[:200]}')
    print(f'Last 200 chars: {current_content[-200:]}')

# Now let's try to reconstruct the file by combining the code object with the string constants
# The code object (464 bytes) + string constants should give us the original file

# Let's create a new file with the reconstructed content
reconstructed_path = r'D:\iNew\app\services\ai_media_reconstructed_final.py'
with open(reconstructed_path, 'w', encoding='utf-8') as f:
    f.write('# RECONSTRUCTED FILE FROM PRE-EDIT .PYC\n')
    f.write(f'# This file is reconstructed from the pre-edit .pyc file\n')
    f.write(f'# Original size: 12109 bytes\n')
    f.write(f'# Code object size: {len(obj.co_code)} bytes\n')
    f.write(f'# String constants: {len(string_constants)} with total approx. {sum(len(c) for _, c in string_constants)} characters\n')
    f.write('\n')
    
    # Write the disassembly as comments to understand the structure
    dis_lines = []
    for instr in dis.get_instructions(obj):
        dis_lines.append(f'{instr.offset:4d}: {instr.opname:<20} {instr.argrepr}')
    
    f.write('# Disassembly (first 50 lines):\n')
    for i, line in enumerate(dis_lines[:50]):
        f.write(line + '\n')
    
    f.write('\n')
    f.write('# String constants (selected):\n')
    for i, const in string_constants[:10]:  # First 10 constants
        f.write(f'{i}: {const[:50]}... ({len(const)} chars)\n')
    
    f.write('\n')
    f.write('# End of reconstruction\n')

print(f'\n=== Reconstructed file written to ===')
print(reconstructed_path)
print(f'Size: {os.path.getsize(reconstructed_path)} bytes')