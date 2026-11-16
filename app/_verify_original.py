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

# 2. Let's extract the actual source from the .pyc by disassembling
import dis
dis_lines = []
for instr in dis.get_instructions(obj):
    dis_lines.append(f'{instr.offset:4d}: {instr.opname:<20} {instr.argrepr}')

print('\n=== disassembly preview ===')
for i in range(min(20, len(dis_lines))):
    print(f'{dis_lines[i]}')

# 3. Let's check the actual file size
py_file = r'D:\iNew\app\services\ai_media.py'
if os.path.exists(py_file):
    py_size = os.path.getsize(py_file)
    print(f'\n=== actual file size ===')
    print(f'{py_file}: {py_size} bytes')
else:
    print('\n=== actual file size ===')
    print('File not found:', py_file)

# 4. Let's see if we can find the original source in the .pyc by looking for string constants
print('\n=== string constants in code object ===')
for const in obj.co_consts:
    if isinstance(const, str) and len(const) > 20:
        print(f'const: {const[:100]}...')

# 5. Let's try to reconstruct by writing the disassembly to a file
reconstructed_path = r'D:\iNew\app\services\ai_media_reconstructed2.py'
with open(reconstructed_path, 'w', encoding='utf-8') as f:
    f.write('# RECONSTRUCTED FILE - DO NOT EDIT\n')
    f.write(dis_text)  # from previous step
    f.write('\n# END OF RECONSTRUCTION\n')

print(f'\n=== reconstructed file size ===')
print(f'{reconstructed_path}: {os.path.getsize(reconstructed_path)} bytes')