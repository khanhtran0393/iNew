import marshal
import types
import dis
import io

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

# Let's create a simple decompiler
def decompile_code(obj):
    source_lines = []
    for instr in dis.get_instructions(obj):
        # Convert disassembly to Python source
        if instr.opname == 'RESUME':
            source_lines.append('def <module>()')
        elif instr.opname == 'LOAD_CONST':
            const_val = obj.co_consts[instr.arg]
            if isinstance(const_val, str):
                source_lines.append(f'# LOAD_CONST: {const_val}')
            else:
                source_lines.append(f'# LOAD_CONST: {const_val}')
        elif instr.opname == 'STORE_NAME':
            var_name = instr.arg
            source_lines.append(f'{var_name} = ...')
        elif instr.opname == 'RETURN_VALUE':
            source_lines.append('return ...')
        # Add more cases as needed
    return source_lines

# Let's try to decompile
try:
    source_lines = decompile_code(obj)
    print(f'\n=== Decompiled source lines: {len(source_lines)}')
    for i, line in enumerate(source_lines[:20]):
        print(f'{i+1:2d}: {line}')
except Exception as e:
    print(f'\n=== Decompilation error: {e}')