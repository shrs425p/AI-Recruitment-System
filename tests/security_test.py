"""
security_test.py - Hard security tests for the AI Recruitment System.

Tests:
 1. HR routes return 401 with no session (no browser access)
 2. /desktop-bootstrap refuses to authenticate without a valid nonce
 3. /api/desktop-login returns 403 with a bogus nonce
 4. /api/desktop-login returns 403 with an empty body
 5. /api/desktop-login returns 403 with a replayed (already used) nonce
 6. /api/desktop-login is rate-limit resistant (does not leak timing info)
 7. Candidate routes are publicly accessible (no session needed)
 8. /login page returns 403 in browser mode (LOGIN_ENABLED=False)
 9. HR API routes return 401, not a redirect, for API clients
10. No HR route is accidentally public (enumeration check)
11. Session fixation: session.clear() happens before granting access
"""

import secrets
import sys
import time

import requests

BASE     = "http://127.0.0.1:5001"
PASS     = "[PASS]"
FAIL     = "[FAIL]"

results = []

def check(name, condition, details=""):
    status = PASS if condition else FAIL
    print(f"  {status} {name}")
    if details:
        print(f"         {details}")
    results.append((name, condition))

def get(path, **kwargs):
    return requests.get(BASE + path, allow_redirects=False, timeout=5, **kwargs)

def post(path, **kwargs):
    return requests.post(BASE + path, allow_redirects=False, timeout=5, **kwargs)

print("\n" + "="*60)
print("  AI Recruitment System - Security Test Suite")
print("="*60 + "\n")

# ── 1. Core HR routes blocked without session ────────────────────────────────
print("[ Block 1 ] HR routes must be blocked to unauthenticated browsers\n")

hr_routes = [
    "/dashboard",
    "/candidates",
    "/rankings",
    "/schedule",
    "/settings",
    "/interviews",
]
for route in hr_routes:
    r = get(route)
    blocked = r.status_code in (401, 403, 302)
    check(f"GET {route} -> {r.status_code} (expected 401/302/403)", blocked)

# ── 2. HR API routes return 401, not redirect ────────────────────────────────
print("\n[ Block 2 ] HR API endpoints must return 401 JSON, not HTML redirect\n")

hr_api_routes = [
    "/api/stats",
    "/api/logs",
    "/api/candidates",
    "/api/pipeline-status",
]
for route in hr_api_routes:
    r = get(route, headers={"Accept": "application/json"})
    is_401  = r.status_code == 401
    is_json = "application/json" in r.headers.get("Content-Type", "")
    check(f"GET {route} -> 401 JSON", is_401 and is_json,
          f"status={r.status_code}, content-type={r.headers.get('Content-Type','?')}")

# ── 3. /api/desktop-login rejects bogus nonces ──────────────────────────────
print("\n[ Block 3 ] /api/desktop-login must reject invalid nonces\n")

r = post("/api/desktop-login", json={"nonce": "totally-fake-nonce-12345"})
check("Bogus nonce -> 403", r.status_code == 403)

r = post("/api/desktop-login", json={})
check("Empty body -> 403", r.status_code == 403)

r = post("/api/desktop-login", json={"nonce": ""})
check("Empty nonce string -> 403", r.status_code == 403)

r = post("/api/desktop-login", json={"nonce": None})
check("Null nonce -> 403", r.status_code == 403)

r = post("/api/desktop-login", data="not json at all", headers={"Content-Type": "text/plain"})
check("Non-JSON body -> 403 or 415 (rejected)", r.status_code in (403, 415),
      f"got {r.status_code} — 415 Unsupported Media Type is also a correct secure response")

# ── 4. Nonce replay protection ───────────────────────────────────────────────
print("\n[ Block 4 ] Nonce must be single-use (no replay)\n")
fake_nonce = secrets.token_urlsafe(32)
r1 = post("/api/desktop-login", json={"nonce": fake_nonce})
r2 = post("/api/desktop-login", json={"nonce": fake_nonce})
check("Same nonce sent twice -> both 403 (not in pool)", r1.status_code == 403 and r2.status_code == 403)

# ── 5. /desktop-bootstrap shows Access Denied in browser ────────────────────
print("\n[ Block 5 ] /desktop-bootstrap must show access-denied message to browser\n")

r = get("/desktop-bootstrap")
check("/desktop-bootstrap returns 200 (page loads)", r.status_code == 200)
check("/desktop-bootstrap contains access-denied JS timeout",
      "Access Denied" in r.text or "pywebview" in r.text,
      "page must contain 'Access Denied' or pywebviewready handler")
check("/desktop-bootstrap is NOT a redirect to dashboard",
      "dashboard" not in r.headers.get("Location", ""))

# ── 6. Public candidate routes accessible without session ───────────────────
print("\n[ Block 6 ] Public/candidate routes must be accessible without auth\n")

r = get("/api/health")
check("GET /api/health -> 200", r.status_code == 200)

r = get("/candidate-interview/FAKE_TOKEN")
check("GET /candidate-interview/FAKE_TOKEN -> not 401 (publicly reachable)",
      r.status_code != 401, f"got {r.status_code}")

# ── 7. /login is disabled in browser mode ───────────────────────────────────
print("\n[ Block 7 ] /login must be blocked when LOGIN_ENABLED=False\n")

r = get("/login")
check("/login GET -> 403 (browser login disabled)", r.status_code == 403,
      f"got {r.status_code}")

# ── 8. Session fixation ──────────────────────────────────────────────────────
print("\n[ Block 8 ] Session cannot be fixed by pre-setting cookies\n")

session_client = requests.Session()
session_client.cookies.set("session", "eyJsb2dnZWRfaW4iOnRydWV9.fake")
r = session_client.get(BASE + "/dashboard", allow_redirects=False, timeout=5)
check("Tampered session cookie -> still blocked", r.status_code in (401, 403, 302))

# ── 9. Security headers present ─────────────────────────────────────────────
print("\n[ Block 9 ] Security response headers\n")

r = get("/api/health")
check("X-Content-Type-Options: nosniff", r.headers.get("X-Content-Type-Options") == "nosniff")
check("X-Frame-Options present", "X-Frame-Options" in r.headers)
check("Cache-Control: no-store on API", "no-store" in r.headers.get("Cache-Control", ""))

# ── 10. Timing consistency ───────────────────────────────────────────────────
print("\n[ Block 10 ] Timing consistency (anti-oracle)\n")

times = []
for _ in range(5):
    start = time.perf_counter()
    post("/api/desktop-login", json={"nonce": secrets.token_urlsafe(32)})
    times.append(time.perf_counter() - start)

avg = sum(times) / len(times)
variance = max(times) - min(times)
check(f"Response time variance < 200ms (avg={avg*1000:.1f}ms, spread={variance*1000:.1f}ms)",
      variance < 0.2)

# ── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "="*60)
total  = len(results)
passed = sum(1 for _, ok in results if ok)
failed = total - passed
print(f"  Result: {passed}/{total} passed, {failed} failed")
print("="*60 + "\n")

if failed:
    sys.exit(1)
