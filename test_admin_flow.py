from starlette.testclient import TestClient
from app.main import app

client = TestClient(app)

# Test POST /auth/login
login_resp = client.post(
    "/auth/login",
    data={"username": "admin", "password": "admin123456"},
    follow_redirects=False
)
print("POST /auth/login:", login_resp.status_code, "Redirect to:", login_resp.headers.get("location"))
session_cookie = login_resp.cookies.get("inew_session")
print("Session cookie generated:", bool(session_cookie))

# Test accessing /dashboard with session cookie
dash_resp = client.get("/dashboard", cookies={"inew_session": session_cookie})
print("GET /dashboard with cookie:", dash_resp.status_code, "Length:", len(dash_resp.text))
if "dashboard" in dash_resp.text.lower() or "tổng quan" in dash_resp.text.lower():
    print("Dashboard rendered successfully for Admin!")
