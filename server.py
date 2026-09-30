import json, os, subprocess, threading, queue
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

D = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.expanduser("~/storage/downloads/YT")
HOST, PORT = "127.0.0.1", 8080
os.makedirs(OUT, exist_ok=True)

jobs, q, lock = [], queue.Queue(), threading.Lock()

def num(x):
    try: return float(x)
    except Exception: return None

TEMPLATE = ("download:P|%(progress.downloaded_bytes)s|%(progress.total_bytes)s|"
            "%(progress.total_bytes_estimate)s|%(progress.speed)s|%(progress.eta)s")

def worker():
    while True:
        j = jobs[q.get()]
        j["status"] = "downloading"
        if j["format"] == "mp3":
            fa = ["-x", "--audio-format", "mp3", "--audio-quality", "0",
                  "--embed-thumbnail", "--add-metadata"]
        else:
            fa = ["-f", "bv*[height<=1080]+ba/b", "--merge-output-format", "mp4"]
        cmd = ["yt-dlp", "--newline", "--progress", "--no-playlist",
               "--progress-template", TEMPLATE,
               "--print", "before_dl:T|%(thumbnail)s|%(title)s"] + fa + \
              ["-o", OUT + "/%(title)s.%(ext)s", "--", j["url"]]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:
            line = line.strip()
            try:
                if line.startswith("T|"):
                    _, j["thumb"], j["title"] = line.split("|", 2)
                elif line.startswith("P|"):
                    _, d, t, e, s, eta = line.split("|")
                    d, tot = num(d), num(t) or num(e)
                    j.update(done=d, total=tot, speed=num(s), eta=num(eta))
                    if d and tot: j["pct"] = min(100, d / tot * 100)
            except Exception:
                pass
        j["status"] = "done" if p.wait() == 0 else "error"

threading.Thread(target=worker, daemon=True).start()

class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path == "/api/list":
            with lock: self._send(200, json.dumps(jobs))
        else:
            with open(os.path.join(D, "index.html"), encoding="utf-8") as f:
                self._send(200, f.read(), "text/html")
    def do_POST(self):
        if self.path != "/api/add": return self._send(404, "{}")
        try:
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            url, fmt = d["url"].strip(), d["format"]
            assert url.startswith(("http://", "https://")) and fmt in ("mp3", "mp4")
        except Exception:
            return self._send(400, "{}")
        with lock:
            jobs.append({"url": url, "format": fmt, "status": "pending", "pct": 0})
            q.put(len(jobs) - 1)
        self._send(200, "{}")
    def log_message(self, *a): pass

print(f"เปิดที่ http://{HOST}:{PORT}  (ไฟล์ไปที่ {OUT})")
ThreadingHTTPServer((HOST, PORT), H).serve_forever()
