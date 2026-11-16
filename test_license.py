import sys
import os
sys.path.insert(0, 'd:\\\\iNew')

# Test the licensing module
from app.services.licensing import verify_token, evaluate_state, current_limits, load_installed_token, save_installed_token, machine_fingerprint

# Get the actual machine fingerprint
actual_fp = machine_fingerprint()
print(f'=== Machine fingerprint: {actual_fp} ===')

# Install a license token with the correct fingerprint
print('\n=== Step 1: Install license token ===')
try:
    token = save_installed_token(f'inew_portable_license.{actual_fp}')
    print(f'Token installed: {token}')
except Exception as e:
    print(f'Error installing token: {e}')

# Test evaluate_state
print('\n=== Step 2: evaluate_state ===')
state = evaluate_state()
print(f'State: licensed={state.get("licensed")}, reason={state.get("reason")}')

# Test current_limits
print('\n=== Step 3: current_limits ===')
limits = current_limits()
print(f'Limits: {limits}')

# Test verify_token with the installed token
print('\n=== Step 4: verify_token ===')
result = verify_token(token)
print(f'verify_token result: valid={result[0]}, customer={result[1].get("customer")}, reason={result[2]}')

print('\n=== Done ===')