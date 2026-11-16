from starlette.testclient import TestClient
from app.main import app

client = TestClient(app)

# 1. Test health endpoints
resp = client.get("/health/live")
print("GET /health/live:", resp.status_code, resp.json())

# 2. Test root redirect (should redirect to /setup or /dashboard)
resp = client.get("/", follow_redirects=False)
print("GET /:", resp.status_code, resp.headers.get("location"))

# 3. Test setup page
resp = client.get("/setup")
print("GET /setup:", resp.status_code, "Length:", len(resp.text))

# 4. Test license page
resp = client.get("/license")
print("GET /license:", resp.status_code, "Length:", len(resp.text))
if "Kích hoạt iNew" in resp.text:
    print("Found 'Kích hoạt iNew' in license page HTML!")

# 5. Test login page
resp = client.get("/auth/login")
print("GET /auth/login:", resp.status_code, "Length:", len(resp.text))
if "Đăng nhập" in resp.text:
    print("Found 'Đăng nhập' in login page HTML!")
