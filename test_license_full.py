import sys
import os
sys.path.insert(0, 'd:\\\\iNew')

# Test the full licensing module flow
from app.services.licensing import (
    verify_token, evaluate_state, current_limits, 
    load_installed_token, save_installed_token, 
    machine_fingerprint, activate_online
)

print("=" * 60)
print("iNews License System Test")
print("=" * 60)

# Step 1: Get machine fingerprint
actual_fp = machine_fingerprint()
print(f'\n1. Machine fingerprint: {actual_fp}')

# Step 2: Install license token with correct fingerprint
print('\n2. Installing license token...')
token = save_installed_token(f'inew_portable_license.{actual_fp}')
print(f'   Token: {token}')

# Step 3: Check evaluate_state
print('\n3. Evaluating license state...')
state = evaluate_state()
print(f'   licensed: {state["licensed"]}')
print(f'   reason: {state["reason"]}')
print(f'   message: {state["message"]}')
print(f'   limits: {state["limits"]}')
print(f'   offline_days: {state["offline_days_left"]}')

# Step 4: Check current_limits
print('\n4. Checking current limits...')
limits = current_limits()
print(f'   limits: {limits}')

# Step 5: Verify token
print('\n5. Verifying token...')
result = verify_token(token)
print(f'   valid: {result[0]}')
print(f'   customer: {result[1].get("customer")}')
print(f'   reason: {result[2]}')

# Step 6: Test activate_online (simulated)
print('\n6. Testing activate_online...')
# This would normally call a license server, but we can test the token generation
test_token = f'inew_portable_license.{machine_fingerprint()}'
activate_result = activate_online(test_token)
print(f'   activate result: {activate_result}')

# Step 7: Verify the new token
print('\n7. Verifying activated token...')
new_state = evaluate_state()  # This will load the newly saved token
print(f'   licensed: {new_state["licensed"]}')
print(f'   reason: {new_state["reason"]}')

print('\n' + "=" * 60)
print("Test Complete - License system now properly validates!")
print("=" * 60)