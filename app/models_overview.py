with open('D:\\\\iNew\\\\app\\\\models.py', 'r') as f:
    lines = f.readlines()
    classes = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('class'):
            classes.append((i+1, stripped))
    for cls_line, cls_name in classes:
        print(f'{cls_line}: {cls_name}')
        # Show a few lines after the class definition
        for j in range(cls_line, min(cls_line + 5, len(lines))):
            print(f'  {j+1}: {lines[j].rstrip()}')
        print()