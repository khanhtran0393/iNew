import json, os, re

root = r'D:\iNew'
man = json.load(open(os.path.join(root, 'reconstructed_specs', 'manifest.json'), encoding='utf-8'))

entry = None
for e in man:
    if 'ai_media' in e['path']:
        entry = e
        break

with open(r'D:\iNew\app\_manifest_ai_media.json', 'w', encoding='utf-8') as f:
    json.dump(entry, f, ensure_ascii=False, indent=2)

print('KEYS:', list(entry.keys()))
print('\nFUNCTIONS:', entry['functions'])
print('\nSTRING_LITERALS:')
for s in entry.get('string_literals', []):
    print('  -', repr(s))
print('\nATTRIBUTES:', entry.get('attributes'))
print('\nOFFSET:', entry.get('offset'), 'SIZE:', entry.get('size_bytes'))

# Check extracted_strings.json for anything about ai_media
es_path = os.path.join(root, 'extracted_strings.json')
if os.path.exists(es_path):
    with open(es_path, 'r', encoding='utf-8') as f:
        es = json.load(f)
    print('\n=== extracted_strings.json top-level keys ===')
    if isinstance(es, dict):
        for k, v in es.items():
            print(f'  {k}: {type(v).__name__}', (len(v) if hasattr(v, '__len__') else ''))
    else:
        print('  list len', len(es))
        print('  sample:', es[0] if es else None)
