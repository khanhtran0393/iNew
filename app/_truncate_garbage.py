import io, os, sys

targets = [
    r'D:\iNew\app\services\ai_copilot.py',
    r'D:\iNew\app\services\ai_key_router.py',
    r'D:\iNew\app\services\ai_media.py',
]

for path in targets:
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    # The garbage append starts at the first literal backslash-n sequence
    idx = text.find('\\n')
    if idx == -1:
        print(f'{os.path.basename(path)}: no garbage found')
        continue
    # cut back to the end of the previous real line
    cut = text.rfind('\n', 0, idx)
    cleaned = text[:cut+1]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(cleaned)
    print(f'{os.path.basename(path)}: truncated at offset {cut} (removed {len(text)-len(cleaned)} chars)')