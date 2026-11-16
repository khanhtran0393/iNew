with open('D:\\\\iNew\\\\app\\\\services\\\\ai_key_router.py', 'r') as f:
    lines = f.readlines()
    # Look for the functions I added
    found_dd = False
    found_find_best = False
    found_get_purpose = False
    for i, line in enumerate(lines):
        if 'def dd(key_id: int)' in line:
            print(f'Found dd at line {i+1}')
            found_dd = True
        if 'def find_best_ai_key' in line:
            print(f'Found find_best_ai_key at line {i+1}')
            found_find_best = True
        if 'def get_purpose_meta' in line:
            print(f'Found get_purpose_meta at line {i+1}')
            found_get_purpose = True
            
    print(f'Found dd: {found_dd}, find_best_ai_key: {found_find_best}, get_purpose_meta: {found_get_purpose}')