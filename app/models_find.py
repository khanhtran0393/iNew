with open('D:\\\\iNew\\\\app\\\\models.py', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if 'class Base' in line:
            print(f'Base class found at line {i+1}')
            for j in range(i, min(i+10, len(lines))):
                print(f'{j+1}: {lines[j].rstrip()}')
            break