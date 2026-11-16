with open('D:\\\\iNew\\\\app\\\\services\\\\ai_copilot.py', 'r') as f:
    lines = f.readlines()
    # Look for the methods I added
    found = False
    for i, line in enumerate(lines):
        if 'def _topic_id_for_post' in line:
            print(f'Found _topic_id_for_post at line {i+1}')
            found = True
            # Print the method
            for j in range(i, min(i+15, len(lines))):
                print(f'{j+1}: {lines[j].rstrip()}')
            break
    if not found:
        print('Did not find _topic_id_for_post method')