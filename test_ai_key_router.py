import sys
sys.path.insert(0, r'D:\iNew')

from app.services.ai_key_router import (
    dd,
    find_best_ai_key,
    get_purpose_meta,
    is_circuit_open,
    record_key_usage,
    resolve_candidates,
    test_ai_key,
    test_gemini_api_key,
    trip_circuit_breaker,
)

# Quick sanity checks (these will fail without a real DB, but should not crash import)
print("All 9 functions imported successfully:")
print(f"  dd: {dd}")
print(f"  find_best_ai_key: {find_best_ai_key}")
print(f"  get_purpose_meta: {get_purpose_meta}")
print(f"  is_circuit_open: {is_circuit_open}")
print(f"  record_key_usage: {record_key_usage}")
print(f"  resolve_candidates: {resolve_candidates}")
print(f"  test_ai_key: {test_ai_key}")
print(f"  test_gemini_api_key: {test_gemini_api_key}")
print(f"  trip_circuit_breaker: {trip_circuit_breaker}")