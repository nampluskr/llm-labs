"""ChatSession: 직전 10턴 문맥, 이벤트 순서, 중복 질문 거절, 중단, 오류 처리."""

import threading
import time

import pytest

from fake_ollama import chunk, done_chunk, send_lines
from local_chat.clients import CLIENTS, Done, Error, Token
from local_chat.session import MAX_TURNS, ChatSession

OPTIONS = {"num_ctx": 4096, "temperature": 0.7}


class ScriptedClient:
    """호출 층 약속(Token…, Done|Error)을 그대로 따르는 대역. 받은 메시지와 close 여부를 기록한다."""

    name = "scripted"

    def __init__(self, script):
        self.script = script  # 질문 텍스트 -> 이벤트 목록(또는 제너레이터 함수)
        self.calls = []
        self.closed = threading.Event()

    def stream(self, messages, *, model, options):
        self.calls.append(messages)
        try:
            yield from self.script(messages[-1]["content"])
        finally:
            self.closed.set()


def echo(text):
    yield Token("답:")
    yield Token(text)
    yield Done(2, 1_000_000_000)


def make(client, emit=None):
    events = []
    session = ChatSession(client, "m", OPTIONS, emit or events.append)
    return session, events


def ask(session, text):
    assert session.send(text) == {"ok": True}
    session.join(10)


def test_문맥은_직전_10턴만_보낸다():
    client = ScriptedClient(echo)
    session, _ = make(client)
    for i in range(1, 13):
        ask(session, f"q{i}")
    ask(session, "q13")
    messages = client.calls[-1]
    assert len(messages) == 1 + 2 * MAX_TURNS + 1 == 22
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "q3"}  # q1·q2는 잘렸다
    assert messages[-2] == {"role": "assistant", "content": "답:q12"}
    assert messages[-1] == {"role": "user", "content": "q13"}
    roles = [m["role"] for m in messages[1:]]
    assert roles == ["user", "assistant"] * MAX_TURNS + ["user"]  # 순서·role 유지


def test_10턴_이하면_전부_보낸다():
    client = ScriptedClient(echo)
    session, _ = make(client)
    for i in range(1, 4):
        ask(session, f"q{i}")
    ask(session, "q4")
    assert len(client.calls[-1]) == 1 + 2 * 3 + 1


def test_토큰은_순서대로_오고_종료_이벤트는_하나다():
    session, events = make(ScriptedClient(echo))
    ask(session, "안녕")
    assert events == [
        {"type": "token", "text": "답:"},
        {"type": "token", "text": "안녕"},
        {"type": "done", "eval_count": 2, "tok_s": 2.0},
    ]


def test_빈_질문은_거절한다():
    session, events = make(ScriptedClient(echo))
    assert session.send("   ") == {"ok": False, "reason": "empty"}
    assert events == [] and session.turn_count == 0


def test_답변_중_다시_질문하면_거절하고_진행_중인_답은_그대로다():
    gate = threading.Event()

    def slow(text):
        yield Token("a")
        gate.wait(5)
        yield Token("b")
        yield Done(2, 1_000_000_000)

    client = ScriptedClient(slow)
    session, events = make(client)
    assert session.send("첫째") == {"ok": True}
    assert session.send("둘째") == {"ok": False, "reason": "busy"}
    gate.set()
    session.join(10)
    assert [e["text"] for e in events if e["type"] == "token"] == ["a", "b"]
    assert len(client.calls) == 1 and session.turn_count == 1
    assert session.send("셋째") == {"ok": True}  # 끝난 뒤에는 받는다
    session.join(10)


def test_종료_이벤트를_받은_즉시_다음_질문을_보내도_거절되지_않는다():
    results = []
    holder = {}

    def emit(ev):
        if ev["type"] == "done" and not results:
            results.append(holder["s"].send("바로 다음"))

    session = ChatSession(ScriptedClient(echo), "m", OPTIONS, emit)
    holder["s"] = session
    ask(session, "첫째")
    session.join(10)
    assert results == [{"ok": True}]


def test_중단하면_stopped_이벤트와_받은_데까지의_답이_남고_연결을_닫는다():
    gate = threading.Event()

    def endless(text):
        yield Token("가")
        yield Token("나")
        gate.wait(5)
        for _ in range(1000):
            yield Token("다")
        yield Done(1, 1)

    client = ScriptedClient(endless)
    events = []
    first_two = threading.Event()

    def emit(ev):
        events.append(ev)
        if len(events) == 2:
            first_two.set()

    session = ChatSession(client, "m", OPTIONS, emit)
    assert session.send("질문") == {"ok": True}
    assert first_two.wait(5)
    session.stop()
    gate.set()
    session.join(10)
    assert events[-1] == {"type": "stopped"}
    assert sum(e["type"] in ("done", "stopped", "error") for e in events) == 1
    assert client.closed.wait(5)
    assert session.turn_count == 1
    session.send("다음")
    session.join(10)
    assert {"role": "assistant", "content": "가나"} in client.calls[-1]  # 중단된 답도 문맥에 있다


def test_토큰_없이_중단하면_그_턴은_기록하지_않는다():
    gate = threading.Event()

    def silent(text):
        gate.wait(5)
        yield Token("늦은 토큰")
        yield Done(1, 1)

    session, events = make(ScriptedClient(silent))
    session.send("질문")
    session.stop()
    gate.set()
    session.join(10)
    assert events == [{"type": "stopped"}] and session.turn_count == 0


def test_오류가_나면_error_이벤트가_오고_그_턴은_기록하지_않는다():
    def fail(text):
        yield Token("부분")
        yield Error("connection", "끊김")

    client = ScriptedClient(lambda t: fail(t) if t == "나쁨" else echo(t))
    session, events = make(client)
    ask(session, "나쁨")
    assert events[-1] == {"type": "error", "kind": "connection", "message": "끊김"}
    assert session.turn_count == 0
    ask(session, "좋음")
    assert len(client.calls[-1]) == 2  # 실패한 턴은 문맥에 없다(system + 질문)
    assert events[-1]["type"] == "done"


def test_호출_층이_예외를_내도_busy가_풀린다():
    def boom(text):
        raise RuntimeError("약속 위반")
        yield

    session, events = make(ScriptedClient(boom))
    ask(session, "q")
    assert events[-1]["type"] == "error" and "약속 위반" in events[-1]["message"]
    assert session.send("q2") == {"ok": True}
    session.join(10)


def test_종료_이벤트_없이_스트림이_끝나면_error():
    session, events = make(ScriptedClient(lambda t: iter([Token("a")])))
    ask(session, "q")
    assert events[-1]["type"] == "error" and session.turn_count == 0


def test_emit이_실패하면_창이_닫힌_것으로_보고_스트리밍을_멈춘다():
    emitted = []

    def emit(ev):
        emitted.append(ev)
        raise RuntimeError("window destroyed")

    produced = []

    def many(text):
        for i in range(1000):
            produced.append(i)
            yield Token("x")
        yield Done(1, 1)

    client = ScriptedClient(many)
    session = ChatSession(client, "m", OPTIONS, emit)
    session.send("q")
    session.join(10)
    assert len(produced) < 50  # 끝까지 돌지 않았다
    assert client.closed.wait(5)
    assert session.send("q2") == {"ok": True}  # busy가 풀려 있다
    session.join(10)


@pytest.mark.parametrize("name", list(CLIENTS))
def test_실제_호출층으로도_12턴_뒤_요청에_직전_10턴만_실린다(fake, name):
    fake.script = lambda h: send_lines(h, [chunk("답"), chunk("변"), done_chunk(2, 1_000_000_000)])
    events = []
    session = ChatSession(CLIENTS[name](host=fake.host), "m", OPTIONS, events.append)
    for i in range(1, 14):
        ask(session, f"q{i}")
    body = fake.requests[-1]
    contents = [m["content"] for m in body["messages"]]
    assert len(contents) == 22
    assert contents[1] == "q3" and contents[-1] == "q13" and contents[-2] == "답변"
    assert [e["type"] for e in events[:3]] == ["token", "token", "done"]
    assert events[-1] == {"type": "done", "eval_count": 2, "tok_s": 2.0}
