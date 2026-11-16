import marshal

# Load the pre-edit .pyc file
pyc_path = r'D:\iNew\app\services\__pycache__\ai_media.cpython-313.pyc'
with open(pyc_path, 'rb') as f:
    data = f.read()
    # skip header (first 16 bytes)
    obj = marshal.loads(data[16:])

print('=== String constants in code object ===')
for i, const in enumerate(obj.co_consts):
    if isinstance(const, str) and len(const) > 50:
        print(f'{i:2d}: {const[:100]}...')
        print(f'     Full length: {len(const)} characters')
        print()

print(f'\nTotal string constants: {len([c for c in obj.co_consts if isinstance(c, str)])}')
print(f'Total constants: {len(obj.co_consts)}')