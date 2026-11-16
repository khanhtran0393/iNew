import os, marshal, types, dis, io, re, json

# 1. Load the pre-edit .pyc (12,109 bytes) - this contains the original code object
pyc_path = r'D:\iNew\app\services\__pycache__\ai_media.cpython-313.pyc'
with open(pyc_path, 'rb') as f:
    data = f.read()
    # skip header (first 16 bytes)
    obj = marshal.loads(data[16:])

print('=== pre-edit code object ===')
print('name:', obj.co_name)
print('filename:', obj.co_filename)
print('code size:', len(obj.co_code))
print('consts count:', len(obj.co_consts))
print('names count:', len(obj.co_names))

# 2. Load the disassembly text (12,109 bytes) - this contains the original source
dis_path = r'D:\iNew\app\_ai_media_dis.txt'
with open(dis_path, 'r', encoding='utf-8') as f:
    dis_text = f.read()

print('\n=== disassembly text ===')
print('lines:', len(dis_text.splitlines()))
print('bytes:', len(dis_text))

# 3. Extract the original source from disassembly
# Look for "def " patterns that indicate function definitions
lines = dis_text.splitlines()
source_lines = []
for line in lines:
    if line.strip().startswith('def '):
        source_lines.append(line.strip())
    elif line.strip() and not line.startswith(' '):  # non-indented line
        source_lines.append(line.strip())

print('\n=== extracted functions ===')
for i, line in enumerate(source_lines[:20]):
    print(f'{i+1:2d}: {line}')

# 4. Reconstruct the module by combining the code object with source
# The code object contains the compiled bytecode, the disassembly contains the source
# We need to create a new module that has the correct code object and source

# Let's create a new .pyc file that contains the original code object
# and write the disassembly as source

# First, let's verify the code object is correct
print('\n=== code object details ===')
print('co_argcount:', obj.co_argcount)
print('co_nlocals:', obj.co_nlocals)
print('co_stacksize:', obj.co_stacksize)
print('co_flags:', obj.co_flags)
print('co_consts (first 10):', obj.co_consts[:10])

# Let's see what the disassembly text contains
print('\n=== disassembly preview ===')
for i in range(min(20, len(source_lines))):
    print(f'{i+1:2d}: {source_lines[i]}')

# 5. Let's try to write a reconstructed .py file
reconstructed_path = r'D:\iNew\app\services\ai_media_reconstructed.py'
with open(reconstructed_path, 'w', encoding='utf-8') as f:
    f.write('# RECONSTRUCTED FILE - DO NOT EDIT\n')
    f.write(dis_text)
    f.write('\n# END OF RECONSTRUCTION\n')

print(f'\n=== reconstructed source written to ===')
print(reconstructed_path)
print('size:', os.path.getsize(reconstructed_path), 'bytes')