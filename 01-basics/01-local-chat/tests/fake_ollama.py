"""가짜 Ollama 서버: /api/chat, /api/show, /api/tags를 흉내 낸다. 호출 층·앱 테스트가 같이 쓴다."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def chunk(text="", done=False, thinking=None, **extra):
    d = {"model": "m", "created_at": "2026-01-01T00:00:00Z", "message": {"role": "assistant", "content": text}, "done": done}
    if thinking is not None:
        d["message"]["thinking"] = thinking
    d.update(extra)
    return d


def done_chunk(count=4, duration=2_000_000_000):
    return chunk("", True, done_reason="stop", eval_count=count, eval_duration=duration)


class FakeOllama:
    """/api/chat은 script(handler)가 응답을 쓰고, /api/show는 capabilities를 돌려준다.
    /api/tags는 tags(모델 이름 목록)를 돌려준다. 모델별 capabilities는 capabilities_by_model에 없으면 capabilities를 쓴다.
    빈 messages와 keep_alive 0인 /api/chat 요청은 "모델 내리기"로 보고 unloads에 쌓으며 requests에는 쌓지 않는다.
    requests에는 그 밖의 /api/chat 요청 본문만 쌓인다."""

    def __init__(self):
        self.requests = []
        self.unloads = []
        self.unload_status = 200  # 404 등으로 바꾸면 모델 내리기가 실패한다
        self.unload_delay = 0.0  # 모델 내리기 응답을 늦춘다(전환 중 상태 시험)
        self.unload_started = threading.Event()
        self.unload_time = None  # 내리기 요청이 서버에 도착한 시각(time.perf_counter)
        self.unload_body = None  # 주면 HTTP 200으로 이 JSON을 돌려준다(오류 본문 시험)
        self.unload_script = None  # 주면 내리기 응답을 직접 쓴다(헤더 trickle 시험)
        self.get_script = None  # 주면 GET 응답을 직접 쓴다(/api/tags 느린 응답 시험)
        self.tags = None  # 모델 이름 목록. None이면 /api/tags가 404
        self.capabilities_by_model = {}
        self.show_requests = []
        self.capabilities = ["completion"]  # 사고 과정을 지원하는 모델이면 "thinking"을 더한다
        self.show_script = None  # 주면 /api/show 응답을 직접 쓴다(느린 응답 시험)
        self.script = None
        self.disconnected = threading.Event()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if self.path == "/api/show":
                    owner.show_requests.append(body)
                    if owner.show_script is not None:
                        owner.show_script(self)
                        return
                    caps = owner.capabilities_by_model.get(body.get("model"), owner.capabilities)
                    send_lines(self, [{"model": body.get("model"), "capabilities": caps}])
                    return
                if body.get("messages") == [] and body.get("keep_alive") == 0:
                    owner.unloads.append(body)
                    owner.unload_time = time.perf_counter()
                    owner.unload_started.set()
                    if owner.unload_script is not None:
                        owner.unload_script(self)
                        return
                    if owner.unload_delay:
                        time.sleep(owner.unload_delay)
                    if owner.unload_body is not None:
                        send_lines(self, [owner.unload_body])
                        return
                    if owner.unload_status != 200:
                        send_lines(self, [{"error": "model not found"}], status=owner.unload_status)
                    else:
                        send_lines(self, [chunk("", True, done_reason="unload")])
                    return
                owner.requests.append(body)
                owner.script(self)

            def do_GET(self):
                if owner.get_script is not None:
                    owner.get_script(self)
                    return
                if self.path == "/api/tags" and owner.tags is not None:
                    items = [n if (n is None or isinstance(n, dict)) else {"name": n, "model": n} for n in owner.tags]  # dict·None은 그대로(잘못된 항목 시험)
                    send_lines(self, [{"models": items}])
                else:
                    send_lines(self, [{"error": "not found"}], status=404)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.host = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def send_headers(handler, status=200):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/x-ndjson")
    handler.end_headers()


def send_body(handler, lines, delay=0.0):
    """헤더를 이미 보낸 응답에 줄을 더한다. 스트림을 도중에 멈추는 시나리오에 쓴다."""
    for line in lines:
        data = line if isinstance(line, bytes) else (json.dumps(line, ensure_ascii=False) + chr(10)).encode("utf-8")
        handler.wfile.write(data)
        handler.wfile.flush()
        if delay:
            time.sleep(delay)


def trickle_headers(handler, seconds=10.0, interval=0.25):
    """응답 헤더를 끝내지 않고 조금씩 흘린다. httpx의 연산별 timeout만으로는 끝나지 않는 응답이다."""
    try:
        handler.wfile.write(b"HTTP/1.1 200 OK\r\n")
        end = time.time() + seconds
        while time.time() < end:
            handler.wfile.write(b"X-Slow: 1\r\n")
            handler.wfile.flush()
            time.sleep(interval)
    except OSError:
        pass


def send_lines(handler, lines, status=200, delay=0.0):
    """한 응답 전체(헤더 + 줄들). 같은 응답에 두 번 부르지 않는다(헤더가 본문에 섞인다)."""
    send_headers(handler, status)
    send_body(handler, lines, delay)
