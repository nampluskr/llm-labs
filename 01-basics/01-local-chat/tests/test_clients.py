"""세 호출 층이 같은 입력에 같은 이벤트를 내는지, 실패 경로가 같은지 가짜 Ollama 서버로 확인한다."""

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from local_chat.clients import CLIENTS, Done, Error, Token
from local_chat.console import main as console_main

MESSAGES = [
    {"role": "system", "content": "시스템"},
    {"role": "user", "content": "질문"},
    {"role": "assistant", "content": "답"},
    {"role": "user", "content": "다시"},
]
OPTIONS = {"num_ctx": 4096, "temperature": 0.7}


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


@pytest.fixture
def fake():
    f = FakeOllama()
    yield f
    f.close()


def collect(client, host_unused=None):
    return list(client.stream(MESSAGES, model="m", options=OPTIONS))


def clients(host):
    return [(name, cls(host=host)) for name, cls in CLIENTS.items()]


def test_정상_스트림은_세_층이_같은_이벤트를_낸다(fake):
    fake.script = lambda h: send_lines(h, [chunk("안"), chunk("녕 😊"), chunk(""), chunk("!"), done_chunk()])
    results = {name: collect(c) for name, c in clients(fake.host)}
    expected = [Token("안"), Token("녕 😊"), Token("!"), Done(4, 2_000_000_000)]
    assert results == {"ollama": expected, "langchain": expected, "http": expected}
    assert expected[-1].tokens_per_second == 2.0


def test_요청에_모델_옵션_메시지_사고끄기가_같이_실린다(fake):
    fake.script = lambda h: send_lines(h, [chunk("a"), done_chunk()])
    for name, c in clients(fake.host):
        fake.requests.clear()
        collect(c)
        (body,) = fake.requests
        assert body["model"] == "m", name
        assert body["messages"] == MESSAGES, name
        assert body["stream"] is True, name
        assert body["think"] is False, name
        assert body["options"]["num_ctx"] == 4096, name
        assert body["options"]["temperature"] == 0.7, name


def test_done_뒤의_내용없는_청크가_와도_Done은_하나다(fake):
    fake.script = lambda h: send_lines(h, [chunk("a"), done_chunk(), chunk("")])
    for name, c in clients(fake.host):
        events = collect(c)
        assert [type(e) for e in events] == [Token, Done], name


def test_모델_없음은_model_not_found_이벤트(fake):
    fake.script = lambda h: send_lines(h, [{"error": "model 'x' not found"}], status=404)
    for name, c in clients(fake.host):
        events = collect(c)
        assert len(events) == 1 and isinstance(events[0], Error), name
        assert events[0].kind == "model_not_found", name
        assert "not found" in events[0].message, name


def test_서버_없음은_connection_이벤트():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]  # 닫으면 아무도 듣지 않는 포트
    for name, c in clients(f"http://127.0.0.1:{port}"):
        events = collect(c)
        assert len(events) == 1 and isinstance(events[0], Error), name
        assert events[0].kind == "connection", name


def test_스트림_도중_오류줄은_토큰_뒤_Error로_끝난다(fake):
    fake.script = lambda h: send_lines(h, [chunk("a"), {"error": "out of memory"}])
    for name, c in clients(fake.host):
        events = collect(c)
        assert events[0] == Token("a"), name
        assert isinstance(events[-1], Error) and len(events) == 2, name
        assert "out of memory" in events[-1].message, name


def test_done_없이_끊기면_Error(fake):
    fake.script = lambda h: send_lines(h, [chunk("a"), chunk("b")])
    for name, c in clients(fake.host):
        events = collect(c)
        assert events[:2] == [Token("a"), Token("b")], name
        assert isinstance(events[-1], Error) and events[-1].kind == "other", name


def test_해석할_수_없는_줄은_Error(fake):
    fake.script = lambda h: send_lines(h, [chunk("a"), b"not json\n"])
    for name, c in clients(fake.host):
        events = collect(c)
        assert events[0] == Token("a"), name
        assert isinstance(events[-1], Error), name


def test_통계가_없는_done은_Error(fake):
    fake.script = lambda h: send_lines(h, [chunk("a"), chunk("", True, done_reason="stop")])
    for name, c in clients(fake.host):
        events = collect(c)
        assert events[0] == Token("a"), name
        assert isinstance(events[-1], Error), name


def test_중단하면_연결이_닫히고_마지막_이벤트는_없다(fake):
    def script(h):
        try:
            send_lines(h, [chunk(str(i)) for i in range(200)], delay=0.02)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            fake.disconnected.set()

    fake.script = script
    for name, c in clients(fake.host):
        fake.disconnected.clear()
        gen = c.stream(MESSAGES, model="m", options=OPTIONS)
        got = [next(gen), next(gen)]
        gen.close()
        assert all(isinstance(e, Token) for e in got), name
        assert fake.disconnected.wait(5), f"{name}: 서버가 연결 끊김을 보지 못했다"


def test_콘솔은_토큰을_순차_출력하고_tok_s를_한_줄_출력한다(fake, capsys):
    fake.script = lambda h: send_lines(h, [chunk("가"), chunk("나"), done_chunk(2, 1_000_000_000)])
    assert console_main(["--host", fake.host, "--client", "all"]) == 0
    out = capsys.readouterr().out
    assert out.count("tok/s") == 3
    for name in CLIENTS:
        assert f"[{name}] 2토큰 | 2.0 tok/s" in out
    assert out.count("가나") == 3


def test_콘솔은_실패하면_종료코드_1(fake, capsys):
    fake.script = lambda h: send_lines(h, [{"error": "model 'm' not found"}], status=404)
    assert console_main(["--host", fake.host, "--client", "http"]) == 1
    assert "오류(model_not_found)" in capsys.readouterr().out


def test_options는_키를_버리지_않고_세_층이_그대로_보낸다(fake):
    fake.script = lambda h: send_lines(h, [chunk("a"), done_chunk()])
    options = {"num_ctx": 8192, "temperature": 0.2, "top_p": 0.5, "seed": 7, "num_predict": 50}
    for name, c in clients(fake.host):
        fake.requests.clear()
        list(c.stream(MESSAGES, model="m", options=options))
        assert fake.requests[0]["options"] == options, name


class TimedOut:
    """write 시각을 기록하는 출력 대상."""

    def __init__(self):
        self.writes = []

    def write(self, s):
        if s:
            self.writes.append((time.perf_counter(), s))
        return len(s)

    def flush(self):
        pass


def test_토큰은_도착하는_대로_출력된다(fake):
    """서버가 토큰 사이에 0.3초씩 쉬면, 첫 토큰이 마지막 토큰보다 그만큼 먼저 출력돼야 한다(몰아서 출력하지 않음)."""
    from local_chat.console import run

    fake.script = lambda h: send_lines(h, [chunk("A"), chunk("B"), chunk("C"), done_chunk(3, 1_000_000_000)], delay=0.3)
    for name, c in clients(fake.host):
        out = TimedOut()
        assert run(c, "q", "m", out=out) == 0
        t = {s: ts for ts, s in out.writes if s in ("A", "B", "C")}
        assert set(t) == {"A", "B", "C"}, name
        assert t["C"] - t["A"] >= 0.5, f"{name}: 토큰이 몰려서 출력됐다 {t}"
