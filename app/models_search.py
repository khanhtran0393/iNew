with open('D:\\\\iNew\\\\app\\\\models.py', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if '__static_attributes__' in line:
            print(f'Line {i+1}: {line.rstrip()}')
        if 'ai_key_id' in line:
            print(f'Line {i+1}: {line.rstrip()}')
        if 'nnel' in line:
            print(f'Line {i+1}: {line.rstrip()}')
        if 'nual' in line:
            print(f'Line {i+1}: {line.rstrip()}')
        if 'ready' in line:
            print(f'Line {i+1}: {line.rstrip()}')