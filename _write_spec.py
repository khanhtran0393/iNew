spec_content = r"""# SPEC - PyInstaller Audit Restoration

## Restored: ai_key_router.py

### Missing functions (original PyInstaller bundle had 9, reconstructed bundle had only 3)

Added the following functions to `d:\iNew\app\services\ai_key_router.py`:

- `dd(key_id: int) -> dict` – Retrieve AI key details by ID
- `find_best_ai_key(text_content: str) -> AiApiKey` – Select the best AI key matching keyword heuristics
- `get_purpose_meta(purpose: str) -> dict` – Return metadata (description, capabilities, limitations) for a given purpose string
- `is_circuit_open(key_id: int) -> bool` – Return True when the circuit breaker has tripped (failure_count >= 5)
- `test_ai_key(key_id: int) -> bool` – Return True if the key record is active
- `test_gemini_api_key(api_key: str) -> bool` – Simple prefix check for Gemini keys (`AIza...`)

All functions preserve original signatures and integrate with the existing DB‑backed `AiApiKey` / `SessionLocal` infrastructure.

### Verification

- All 9 functions import successfully from `app.services.ai_key_router`
- License tests (`test_license.py`, `test_license_full.py`) continue to pass, confirming no regression
- `test_app_load.py` health checks remain functional
"""

with open(r'D:\iNew\SPEC.md', 'w', encoding='utf-8') as f:
    f.write(spec_content)
print('SPEC.md written successfully')