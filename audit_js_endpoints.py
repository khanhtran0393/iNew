import os
import re
from app.main import app

def audit_js():
    all_paths = set()
    for r in app.routes:
        if hasattr(r, "path"):
            all_paths.add(r.path)
        elif hasattr(r, "original_router"):
            prefix = getattr(r.include_context, "prefix", "") or ""
            for sub_r in r.original_router.routes:
                if hasattr(sub_r, "path"):
                    all_paths.add(prefix + sub_r.path)

    print(f"Total backend routes: {len(all_paths)}")

    js_endpoints = []
    for root, dirs, files in os.walk("app/web"):
        for f in files:
            if f.endswith((".html", ".js")):
                p = os.path.join(root, f)
                with open(p, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
                # Find fetch('/...'), postJson('/...'), getJson('/...'), href="/..."
                pattern = r'(?:fetch|postJson|getJson|postForm|url\s*:\s*|href\s*=\s*)[\(\'"`](/[a-zA-Z0-9_\-\{\}\$\.\/]+)'
                matches = re.findall(pattern, content)
                for m in matches:
                    clean = m.split("?")[0].split("#")[0].strip()
                    if not clean.startswith("/static") and not clean.startswith("/img") and not clean.startswith("/favicon"):
                        js_endpoints.append((f, clean))

    print(f"Total client endpoints found: {len(js_endpoints)}")

    unmatched = set()
    for f, ep in js_endpoints:
        # replace ${var} or {{ var }} or {var} with 1
        norm_ep = re.sub(r'(\$\{[^}]+\}|\{\{[^}]+\}|\{[^}]+\})', '1', ep)
        matched = False
        for r in all_paths:
            r_regex = "^" + re.sub(r'\{[^}]+\}', '[^/]+', r) + "$"
            if re.match(r_regex, norm_ep):
                matched = True
                break
        if not matched:
            unmatched.add((f, ep, norm_ep))

    if unmatched:
        print(f"Unmatched endpoints ({len(unmatched)}):")
        for f, ep, norm in sorted(unmatched):
            print(f"  [{f}] {ep} -> norm: {norm}")
    else:
        print("ALL CLIENT-SIDE JAVASCRIPT & LINK ENDPOINTS MATCH BACKEND 100%!")

if __name__ == "__main__":
    audit_js()
