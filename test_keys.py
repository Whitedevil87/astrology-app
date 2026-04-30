import urllib.request, json, http.cookiejar
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
csrf = json.loads(op.open("http://127.0.0.1:5000/api/csrf").read())["csrf_token"]
bd = "----B"
body = b""
for k, v in {"full_name": "Test", "birth_date": "1995-08-20", "birth_time": "14:00", "birth_place": "Delhi, India", "palm_enabled": "no"}.items():
    body += f"--{bd}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
body += f"--{bd}--\r\n".encode()
req = urllib.request.Request("http://127.0.0.1:5000/api/analyze", data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={bd}", "X-CSRF-Token": csrf})
r = json.loads(op.open(req).read())
for k, v in r.items():
    if k != "report_html":
        print(f"{k}: {str(v)[:100]}")
