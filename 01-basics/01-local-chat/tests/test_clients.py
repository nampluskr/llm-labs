"""세 호출 층이 같은 입력에 같은 이벤트를 내는지, 실패 경로가 같은지 가짜 Ollama 서버로 확인한다."""

import socket
import threading
import time

import pytest

from local_chat.clients import CLIENTS, Done, Error, Token
from fake_ollama import chunk, done_chunk, send_lines
from local_chat.console import main as console_main

MESSAGES = [
    {"role": "system", "content": "시스템"},
    {"role": "user", "content": "질문"},
    {"role": "assistant", "content": "답"},
    {"role": "user", "content": "다시"},
]
OPTIONS = {"num_ctx": 4096, "temperature": 0.7}


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


def test_오류_본문의_error가_문자열이_아니어도_예외가_새지_않는다(fake):
    fake.script = lambda h: send_lines(h, [{"error": 42}], status=500)
    for name, c in clients(fake.host):
        events = collect(c)
        assert len(events) == 1 and isinstance(events[0], Error), name
        assert events[0].kind == "other" and events[0].message == "42", name


def test_응답이_멈추면_읽기_타임아웃으로_Error가_난다(fake):
    release = threading.Event()

    def script(h):
        send_lines(h, [chunk("a")])
        release.wait(10)  # 연결을 연 채 아무것도 보내지 않는다

    fake.script = script
    try:
        for name, cls in CLIENTS.items():
            t0 = time.perf_counter()
            events = list(cls(host=fake.host, read_timeout=0.5).stream(MESSAGES, model="m", options=OPTIONS))
            assert events[0] == Token("a"), name
            assert isinstance(events[-1], Error) and events[-1].kind == "connection", name
            assert time.perf_counter() - t0 < 5, name
    finally:
        release.set()


def test_콘솔_프로세스는_한글을_UTF8_바이트로_토큰마다_바로_내보낸다(fake):
    """실제 프로세스·파이프로 확인한다: 출력 인코딩과 flush는 capsys로는 보이지 않는다."""
    import os
    import subprocess
    import sys

    fake.script = lambda h: send_lines(h, [chunk("가"), chunk("나"), chunk("다"), done_chunk(3, 1_000_000_000)], delay=0.4)
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    proc = subprocess.Popen(
        [sys.executable, "-m", "local_chat.console", "--client", "http", "--host", fake.host],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
    )
    arrivals, data = [], b""

    def reader():
        nonlocal data
        while True:
            part = os.read(proc.stdout.fileno(), 4096)
            if not part:
                return
            data += part
            arrivals.append((time.perf_counter(), data))

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    try:
        t.join(30)  # 프로세스가 멈춰도 테스트가 끝나게 한다
        assert not t.is_alive(), "콘솔 프로세스가 30초 안에 끝나지 않았다"
        assert proc.wait(10) == 0, proc.stderr.read().decode("utf-8", "replace")
    finally:
        proc.kill()
    text = data.decode("utf-8")  # 바이트가 UTF-8이 아니면 여기서 실패한다
    assert "가나다" in text and text.count("tok/s") == 1
    first = next(t for t, d in arrivals if "가".encode() in d)
    last = next(t for t, d in arrivals if "다".encode() in d)
    assert last - first >= 0.5, "토큰이 몰려서 나왔다(flush되지 않음)"


def test_content가_문자열이_아니면_세_층_모두_Error(fake):
    fake.script = lambda h: send_lines(h, [chunk("a"), chunk(["가"]), done_chunk()])
    for name, c in clients(fake.host):
        events = collect(c)
        assert events[0] == Token("a"), name
        assert isinstance(events[-1], Error) and len(events) == 2, name


def test_사고_과정은_세_층이_같은_Thinking_이벤트로_낸다(fake):
    from local_chat.clients import Thinking

    fake.script = lambda h: send_lines(h, [chunk("", thinking="음"), chunk("", thinking="…"), chunk("답"), chunk("변"), done_chunk(4, 2_000_000_000)])
    expected = [Thinking("음"), Thinking("…"), Token("답"), Token("변"), Done(4, 2_000_000_000)]
    for name, c in clients(fake.host):
        events = list(c.stream(MESSAGES, model="m", options=OPTIONS, think=True))
        assert events == expected, name


def test_think_인자는_요청에_그대로_실린다(fake):
    fake.script = lambda h: send_lines(h, [chunk("a"), done_chunk()])
    for name, c in clients(fake.host):
        for think in (True, False):
            fake.requests.clear()
            list(c.stream(MESSAGES, model="m", options=OPTIONS, think=think))
            assert fake.requests[0]["think"] is think, (name, think)


def test_문자열이_아닌_thinking은_세_층_모두_Error(fake):
    fake.script = lambda h: send_lines(h, [chunk("a"), chunk("", thinking=["x"]), done_chunk()])
    for name, c in clients(fake.host):
        events = list(c.stream(MESSAGES, model="m", options=OPTIONS, think=True))
        assert events[0] == Token("a"), name
        assert isinstance(events[-1], Error) and len(events) == 2, name
