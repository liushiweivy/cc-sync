# -*- coding: utf-8 -*-
"""LAN chat relay for two Claude Code instances (desktop <-> laptop).

Endpoints (token required):
  POST /send   {"token":..., "from":"desktop", "text":"..."}  -> {"id": N}
  GET  /messages?token=...&since=N  -> {"messages":[{id,ts,from,text}]}
  GET  /  -> human-readable status page + usage

Token and data dirs come from ccs_config (ccs.local.json / CCS_* env) — no real
values in source. Persistence: <data_dir>/messages.json (append-only list).
Stdlib only. Run: python chat_server.py  (listens 0.0.0.0:8898)
"""
import json
import os
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from ccs_config import TOKEN, DATA_DIR, INBOX_DIR

PORT = 8898
DATA_FILE = os.path.join(DATA_DIR, "messages.json")
MAX_TEXT = 8000
MAX_UPLOAD = 64 * 1024 * 1024  # 64MB

_lock = threading.Lock()


def _load():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _append(sender, text):
    with _lock:
        msgs = _load()
        mid = (msgs[-1]["id"] + 1) if msgs else 1
        msgs.append({
            "id": mid,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "from": sender,
            "text": text,
        })
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(msgs, f, ensure_ascii=False)
        os.replace(tmp, DATA_FILE)
        return mid


USAGE_HTML = """<!doctype html><meta charset="utf-8"><title>cc chat relay</title>
<body style="font-family:monospace;max-width:760px;margin:2em auto;line-height:1.7">
<h2>cc chat relay :8898</h2>
<p>messages stored: {count} &nbsp;|&nbsp; <a href="/messages?token={token}&amp;since=0">view all (json)</a></p>
<h3>For a Claude instance, paste this prompt:</h3>
<pre style="background:#f4f4f4;padding:1em;white-space:pre-wrap">
{prompt}
</pre>
</body>"""

PROMPT = """你现在有一个和另一台电脑上的 Claude 直聊的通道（局域网中继）：
- 发消息: curl -s -X POST http://{host}:8898/send -H "Content-Type: application/json" -d "{{\\"token\\":\\"{token}\\",\\"from\\":\\"{side}\\",\\"text\\":\\"内容\\"}}"
- 收消息: curl -s "http://{host}:8898/messages?token={token}&since=0" （since=上次见过的最大 id，只看新消息）
规则：你是 {side} 端。每次回复我之前，先拉一次新消息；有给我的消息就先回应它。对话内容可以是协作任务、代码讨论、文件互传（大文件走 http://{host}:8899/ 的 zip 下载）。"""


class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            host = self.headers.get("Host", "127.0.0.1:8898").split(":")[0]
            desk = PROMPT.format(host=host, token=TOKEN, side="desktop")
            lap = PROMPT.format(host=host, token=TOKEN, side="laptop")
            self._html(USAGE_HTML.format(
                count=len(_load()), token=TOKEN,
                prompt="【笔记本端】\n" + lap + "\n\n【台式机端】\n" + desk))
            return
        if u.path == "/messages":
            if q.get("token", [""])[0] != TOKEN:
                self._json({"error": "bad token"}, 403)
                return
            try:
                since = int(q.get("since", ["0"])[0])
            except ValueError:
                since = 0
            self._json({"messages": [m for m in _load() if m["id"] > since]})
            return
        if u.path == "/files":
            if q.get("token", [""])[0] != TOKEN:
                self._json({"error": "bad token"}, 403)
                return
            files = []
            if os.path.isdir(INBOX_DIR):
                for name in sorted(os.listdir(INBOX_DIR)):
                    p = os.path.join(INBOX_DIR, name)
                    if os.path.isfile(p):
                        files.append({"name": name,
                                      "size": os.path.getsize(p),
                                      "ts": time.strftime("%Y-%m-%d %H:%M:%S",
                                                          time.localtime(os.path.getmtime(p)))})
            self._json({"files": files})
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/upload":
            if q.get("token", [""])[0] != TOKEN:
                self._json({"error": "bad token"}, 403)
                return
            name = os.path.basename(q.get("name", ["file.bin"])[0])[:128] or "file.bin"
            try:
                n = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                n = 0
            if n <= 0 or n > MAX_UPLOAD:
                self._json({"error": "bad size (1..%d)" % MAX_UPLOAD}, 400)
                return
            os.makedirs(INBOX_DIR, exist_ok=True)
            dst = os.path.join(INBOX_DIR, name)
            base, ext = os.path.splitext(name)
            i = 1
            while os.path.exists(dst):
                dst = os.path.join(INBOX_DIR, "%s-%d%s" % (base, i, ext))
                i += 1
            remaining = n
            with open(dst, "wb") as f:
                while remaining > 0:
                    chunk = self.rfile.read(min(65536, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)
            self._json({"ok": True, "saved": dst})
            return
        if u.path != "/send":
            self._json({"error": "not found"}, 404)
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            self._json({"error": "bad json"}, 400)
            return
        if data.get("token") != TOKEN:
            self._json({"error": "bad token"}, 403)
            return
        sender = str(data.get("from", "?"))[:32]
        text = str(data.get("text", ""))[:MAX_TEXT]
        if not text.strip():
            self._json({"error": "empty text"}, 400)
            return
        self._json({"id": _append(sender, text)})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    print("cc chat relay on 0.0.0.0:%d  (token=%s)" % (PORT, TOKEN))
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
