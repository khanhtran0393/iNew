import os
import sys
sys.path.insert(0, 'd:\\\\iNew')

# Check data directories
print("Checking data directories...")
print(f"iNew root exists: {os.path.exists('d:\\\\iNew')}")
print(f"data dir exists: {os.path.exists('d:\\\\iNew\\\\data')}")
print(f"app dir exists: {os.path.exists('d:\\\\iNew\\\\app')}")

# Check for license files
license_dir = 'd:\\\\iNew\\\\data'
if os.path.exists(license_dir):
    print(f"License dir contents: {os.listdir(license_dir)}")
else:
    print("License dir does not exist")

# Check app data dir
app_data = os.path.join('d:\\\\iNew\\\\app', 'data')
if os.path.exists(app_data):
    print(f"App data dir contents: {os.listdir(app_data)}")
else:
    print("App data dir does not exist")

# Check for license_state.json
state_file = os.path.join('d:\\\\iNew\\\\data', 'license_state.json') if os.path.exists('d:\\\\iNew\\\\data') else None
if state_file:
    print(f"State file exists: {os.path.exists(state_file)}")
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            print(f"State file contents: {f.read()}")