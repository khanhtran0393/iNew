import json, os, ast
root = r'D:\iNew'
manifest = json.load(open(os.path.join(root, 'reconstructed_specs', 'manifest.json'), encoding='utf-8'))
NOISE = {'all', 'in', 'nnel', 'return', 'has_location', 'origin', 'bool', 'str', 'int',
         'float', 'list', 'dict', 'set', 'tuple', 'bytes', 'None', 'True', 'False',
         'self', 'cls', 'args', 'kwargs', 'print', 'open', 'range', 'len', 'super',
         'isinstance', 'getattr', 'setattr', 'hasattr', 'type', 'ValueError',
         'TypeError', 'KeyError', 'Exception', 'RuntimeError', 'OSError'}

total_missing = 0
for m in manifest:
    p = m['path'].replace('\\', '/')
    full = os.path.join(root, p)
    if not os.path.exists(full):
        continue
    src = open(full, encoding='utf-8', errors='replace').read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(f'!! SYNTAX ERROR {p}: {e}')
        total_missing += 1
        continue
    defined = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)
        elif isinstance(node, ast.arg):
            defined.add(node.arg)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                defined.add(a.asname or a.name.split('.')[0])
    expected = set(m.get('functions', [])) | set(m.get('attributes', []))
    expected = {e for e in expected if e not in NOISE and not e.startswith('__')}
    miss = sorted(expected - defined)
    if miss:
        total_missing += len(miss)
        print(f'{p}: missing {len(miss)} -> {miss}')
print('TOTAL missing symbols:', total_missing)