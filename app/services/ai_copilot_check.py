with open('D:\\\\iNew\\\\app\\\\services\\\\ai_copilot.py', 'r') as f:
    lines = f.readlines()
    # Print last 10 lines
    for i in range(max(0, len(lines)-10), len(lines)):
        print(f'{i+1}: {lines[i].rstrip()}')