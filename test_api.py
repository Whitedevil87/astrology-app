"""Test /api/analyze with proper session handling."""
import urllib.request, json, http.cookiejar

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# 1. Get CSRF (stores session cookie)
resp = opener.open("http://127.0.0.1:5000/api/csrf")
csrf = json.loads(resp.read())["csrf_token"]

# 2. Multipart form
boundary = "----TestBoundary12345"
fields = {"full_name": "Test Leo Friend", "birth_date": "1995-08-20",
          "birth_time": "14:00", "birth_place": "Delhi, India", "palm_enabled": "no"}
body = b""
for k, v in fields.items():
    body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
body += f"--{boundary}--\r\n".encode()

req = urllib.request.Request("http://127.0.0.1:5000/api/analyze", data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "X-CSRF-Token": csrf})

try:
    resp = opener.open(req)
    r = json.loads(resp.read())
    print("SUCCESS:", r.get("success"))
    print("SUN:", r.get("zodiac"))
    print("MOON:", r.get("moon_sign"))
    print("ASC:", r.get("ascendant"))
    v = r.get("vedic", {})
    print("MD:", v.get("mahadasha"), "| AD:", v.get("antardasha_demo"))
    print("NAK:", v.get("nakshatra"), "| LORD:", v.get("nakshatra_lord"))
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}")
