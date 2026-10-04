"""가짜 Ollama 서버: /api/chat 하나만 흉내 낸다. 호출 층·앱 테스트가 같이 쓴다."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def chunk(text="", done=False, **extra):
    d = {"model": "m", "created_at": "2026-01-01T00:00:00Z", "message": {"role": "assistant", "content": text}, "done": done}
    d.update(extra)
    return d


def done_chunk(count=4, duration=2_000_000_000):
    return chunk("", True, done_reason="stop", eval_count=count, eval_duration=duration)


class FakeOllama:
    """/api/chat 하나만 흉내 낸다. script(handler)가 응답을 쓴다."""

    def __init__(self):
        self.requests = []
        self.script = None
        self.disconnected = threading.Event()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.requests.append(body)
                owner.script(self)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.host = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def send_lines(handler, lines, status=200, delay=0.0):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/x-ndjson")
    handler.end_headers()
    for line in lines:
        handler.wfile.write((json.dumps(line, ensure_ascii=False) + "\n").encode("utf-8") if not isinstance(line, bytes) else line)
        handler.wfile.flush()
        if delay:
            time.sleep(delay)
