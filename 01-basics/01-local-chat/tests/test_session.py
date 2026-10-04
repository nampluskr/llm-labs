"""ChatSession: 직전 10턴 문맥, 이벤트 순서, 중복 질문 거절, 중단, 오류 처리."""

import threading
import time

import pytest

from fake_ollama import chunk, done_chunk, send_lines
from local_chat.clients import CLIENTS, Done, Error, Thinking, Token
from local_chat.session import MAX_TURNS, ChatSession

OPTIONS = {"num_ctx": 4096, "temperature": 0.7}


class ScriptedClient:
    """호출 층 약속(Token…, Done|Error)을 그대로 따르는 대역. 받은 메시지와 close 여부를 기록한다."""

    name = "scripted"

    def __init__(self, script):
        self.script = script  # 질문 텍스트 -> 이벤트 목록(또는 제너레이터 함수)
        self.calls = []
        self.thinks = []
        self.closed = threading.Event()

    def stream(self, messages, *, model, options, think=False):
        self.calls.append(messages)
        self.thinks.append(think)
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


def test_막힌_상태에서도_중단은_즉시_stopped를_내고_다음_질문을_받는다():
    gate = threading.Event()

    def stuck(text):
        yield Token("가")
        gate.wait(10)  # 서버가 멈춘 것처럼 다음 이벤트가 오지 않는다
        yield Token("늦음")
        yield Done(2, 1)

    client = ScriptedClient(lambda t: stuck(t) if t == "막힘" else echo(t))
    events = []
    got_first = threading.Event()

    def emit(ev):
        events.append(ev)
        if ev["type"] == "token":
            got_first.set()

    session = ChatSession(client, "m", OPTIONS, emit)
    assert session.send("막힘") == {"ok": True}
    assert got_first.wait(5)
    t0 = time.perf_counter()
    session.stop()
    assert time.perf_counter() - t0 < 1  # 막힌 읽기를 기다리지 않는다
    assert events[-1] == {"type": "stopped"}
    assert session.join(1)  # 종료 이벤트까지 끝난 상태
    assert session.turn_count == 1  # 받은 "가"까지 남았다
    assert session.send("다음") == {"ok": True}  # 막힌 작업 스레드가 남아 있어도 새 질문을 받는다
    session.join(10)
    assert {"role": "assistant", "content": "가"} in client.calls[-1]

    before = len(events)
    gate.set()  # 막혀 있던 옛 스레드가 깨어난다
    assert client.closed.wait(5)
    time.sleep(0.2)
    assert {"type": "token", "text": "늦음"} not in events[before - 1:]  # 옛 턴의 이벤트는 버려진다
    assert sum(e["type"] == "stopped" for e in events) == 1


def test_진행_중이_아닐_때_중단은_아무_일도_없고_두_번_눌러도_stopped는_하나다():
    session, events = make(ScriptedClient(echo))
    session.stop()
    assert events == []
    gate = threading.Event()

    def slow(text):
        yield Token("a")
        gate.wait(5)
        yield Done(1, 1)

    session, events = make(ScriptedClient(slow))
    session.send("q")
    time.sleep(0.1)
    session.stop()
    session.stop()
    gate.set()
    session.join(5)
    assert [e["type"] for e in events].count("stopped") == 1


def test_창을_닫으면_중단하고_새_질문을_받지_않는다():
    gate = threading.Event()

    def slow(text):
        yield Token("a")
        gate.wait(5)
        yield Done(1, 1)

    session, events = make(ScriptedClient(slow))
    session.send("q")
    time.sleep(0.1)
    session.close()
    gate.set()
    assert events[-1] == {"type": "stopped"}
    assert session.send("q2") == {"ok": False, "reason": "busy"}


def test_중단해도_답에는_화면에_전달된_토큰만_남는다():
    """stop()이 토큰 전달 직전·직후 어느 경계에 걸려도, 문맥에 남는 답 = 이벤트로 나간 토큰의 연결이다."""
    import random

    rng = random.Random(7)
    boundary_hits = 0
    for _ in range(80):
        def many(text):
            for i in range(60):
                yield Token(f"t{i} ")
            yield Done(60, 1_000_000_000)

        client = ScriptedClient(many)
        events = []

        def emit(ev):
            events.append(ev)
            time.sleep(0.0003)  # 전달 구간을 넓혀 stop()이 경계에 걸리기 쉽게 한다

        session = ChatSession(client, "m", OPTIONS, emit)
        session.send("q")
        timer = threading.Timer(rng.uniform(0, 0.012), session.stop)
        timer.start()
        assert session.join(10)
        timer.cancel()  # 첫 턴이 타이머보다 먼저 끝났다면, 늦게 발동한 stop()이 다음 턴을 중단시키지 않게 정리한다
        timer.join()
        terminals = [e["type"] for e in events if e["type"] != "token"]
        assert len(terminals) == 1 and events[-1]["type"] == terminals[0]
        delivered = "".join(e["text"] for e in events if e["type"] == "token")
        if events[-1]["type"] == "stopped":
            boundary_hits += 1
        session.join(10)
        session.send("다음")
        session.join(10)
        history = client.calls[-1][1:-1]  # system과 마지막 질문을 뺀 문맥
        if delivered:
            assert history == [{"role": "user", "content": "q"}, {"role": "assistant", "content": delivered}]
        else:
            assert history == []
    assert boundary_hits >= 10  # 중단이 실제로 걸린 경우가 충분했다(시험이 의미 있다)


class SleepyLock:
    """_emit_lock 대용. 첫 스레드(첫 턴의 작업 스레드)가 n번째로 락을 잡으려 할 때, 잡기 전에 0.3초 쉰다.
    경합 구간을 결정적으로 벌려 순서 결함을 드러낸다."""

    def __init__(self, sleep_on_acquisition: int):
        self._lock = threading.RLock()
        self._n = sleep_on_acquisition
        self._first = None
        self._count = 0

    def __enter__(self):
        tid = threading.get_ident()
        if self._first is None:
            self._first = tid
        if tid == self._first:
            self._count += 1
            if self._count == self._n:
                time.sleep(0.3)
        self._lock.acquire()
        return self

    def __exit__(self, *exc):
        self._lock.release()


def test_중단해도_답에는_화면에_전달된_토큰만_남는다_경계를_벌려서():
    """작업 스레드가 두 번째 토큰을 전달하려 락을 잡기 직전에 stop()이 들어와도 그 토큰은 문맥에 없다."""

    def three(text):
        yield Token("t0 ")
        yield Token("t1 ")
        yield Token("t2 ")
        yield Done(3, 1_000_000_000)

    client = ScriptedClient(three)
    session, events = make(client)
    session._emit_lock = SleepyLock(sleep_on_acquisition=2)
    session.send("q")
    deadline = time.time() + 5
    while not events and time.time() < deadline:
        time.sleep(0.005)
    session.stop()  # 작업 스레드가 두 번째 토큰 앞에서 쉬는 동안
    assert session.join(5)
    delivered = "".join(e["text"] for e in events if e["type"] == "token")
    assert delivered == "t0 " and events[-1] == {"type": "stopped"}
    session.send("다음")
    session.join(5)
    assert client.calls[-1][1:-1] == [{"role": "user", "content": "q"}, {"role": "assistant", "content": "t0 "}]


def test_새_턴의_토큰은_이전_턴의_종료_이벤트_뒤에_나간다():
    def two(text):
        yield Token(f"{text}1")
        yield Token(f"{text}2")
        yield Done(2, 1_000_000_000)

    session, events = make(ScriptedClient(two))
    # A의 작업 스레드가 종료 이벤트를 내려고 락을 잡기 직전(세 번째 획득)에 쉰다. 확정이 락 안에 있으면 그동안 busy라 B는 못 들어온다
    session._emit_lock = SleepyLock(sleep_on_acquisition=3)
    assert session.send("A") == {"ok": True}
    accepted = None
    deadline = time.time() + 5
    while time.time() < deadline:
        accepted = session.send("B")
        if accepted["ok"]:
            break
        time.sleep(0.01)
    assert accepted == {"ok": True}
    assert session.join(10)
    order = [e.get("text") or e["type"] for e in events]
    assert order == ["A1", "A2", "done", "B1", "B2", "done"], order


def test_emit_콜백_안에서_중단해도_방금_전달한_토큰은_답에_남는다():
    holder = {}
    events = []

    def emit(ev):
        events.append(ev)
        if ev["type"] == "token" and ev["text"] == "a":
            holder["s"].stop()  # 화면에 "a"를 보여 주는 바로 그 호출 안에서 중단

    def two(text):
        yield Token("a")
        yield Token("b")
        yield Done(2, 1)

    client = ScriptedClient(two)
    session = ChatSession(client, "m", OPTIONS, emit)
    holder["s"] = session
    session.send("q")
    assert session.join(5)
    assert [e["type"] for e in events] == ["token", "stopped"]
    assert session.turn_count == 1
    session.send("다음")
    session.join(5)
    assert client.calls[-1][1:-1] == [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]


def test_사고_과정은_이벤트로_나가지만_문맥에는_넣지_않는다():
    def thinks(text):
        yield Thinking("음…")
        yield Thinking("생각")
        yield Token("답")
        yield Done(3, 1_000_000_000)

    client = ScriptedClient(thinks)
    events = []
    session = ChatSession(client, "m", OPTIONS, events.append, think=True)
    ask(session, "q1")
    assert [e["type"] for e in events] == ["thinking", "thinking", "token", "done"]
    assert [e["text"] for e in events if e["type"] == "thinking"] == ["음…", "생각"]
    assert client.thinks == [True]  # 세션이 think를 호출 층에 넘긴다
    ask(session, "q2")
    assert client.calls[-1][1:] == [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "답"},  # 사고 과정은 없다
        {"role": "user", "content": "q2"},
    ]


def test_사고_과정만_받고_중단하면_그_턴은_기록하지_않는다():
    gate = threading.Event()

    def only_thinking(text):
        yield Thinking("생각 중")
        gate.wait(5)
        yield Token("늦음")
        yield Done(1, 1)

    session, events = make(ScriptedClient(only_thinking))
    session.send("q")
    deadline = time.time() + 5
    while not events and time.time() < deadline:
        time.sleep(0.005)
    session.stop()
    gate.set()
    session.join(5)
    assert [e["type"] for e in events] == ["thinking", "stopped"]
    assert session.turn_count == 0  # 답이 없으면 남기지 않는다


def test_think를_안_주면_꺼진_채_호출한다():
    client = ScriptedClient(echo)
    session, _ = make(client)
    ask(session, "q")
    assert client.thinks == [False]


def test_사고_이벤트_전달이_실패하면_다음_이벤트를_기다리지_않고_바로_풀린다():
    gate = threading.Event()

    def thinks_then_block(text):
        yield Thinking("r")
        gate.wait(10)  # 다음 이벤트가 오지 않는다(서버 멈춤)
        yield Token("늦음")
        yield Done(1, 1)

    client = ScriptedClient(thinks_then_block)

    def failing_emit(ev):
        raise RuntimeError("window destroyed")

    session = ChatSession(client, "m", OPTIONS, failing_emit, think=True)
    t0 = time.perf_counter()
    session.send("q")
    assert session.join(2)  # 막힌 읽기가 풀리기를 기다리지 않는다
    assert time.perf_counter() - t0 < 2
    assert session.send("q2") == {"ok": True}  # busy가 풀려 있다
    gate.set()
    session.join(5)


def test_토큰_전달이_실패해도_막힌_읽기를_기다리지_않는다():
    gate = threading.Event()

    def token_then_block(text):
        yield Token("a")
        gate.wait(10)
        yield Done(1, 1)

    session = ChatSession(ScriptedClient(token_then_block), "m", OPTIONS, lambda ev: (_ for _ in ()).throw(RuntimeError("x")))
    session.send("q")
    assert session.join(2)
    assert session.turn_count == 0  # 전달되지 않은 토큰뿐이라 남기지 않는다
    gate.set()


def test_configure한_모델_옵션_think는_다음_질문부터_호출_층에_전달된다():
    seen = []

    class Recording(ScriptedClient):
        def stream(self, messages, *, model, options, think=False):
            seen.append((model, dict(options), think))
            return super().stream(messages, model=model, options=options, think=think)

    session = ChatSession(Recording(echo), "A", {"num_ctx": 4096, "temperature": 0.7}, lambda ev: None, think=False)
    ask(session, "q1")
    assert session.configure(model="B", options={"num_ctx": 8192, "temperature": 0.1}, think=True) == {"ok": True}
    ask(session, "q2")
    assert seen == [("A", {"num_ctx": 4096, "temperature": 0.7}, False), ("B", {"num_ctx": 8192, "temperature": 0.1}, True)]


def test_답변_중에는_설정_변경을_거절하고_진행_중인_턴은_처음_값을_쓴다():
    gate = threading.Event()
    seen = []

    class Slow(ScriptedClient):
        def stream(self, messages, *, model, options, think=False):
            seen.append((model, dict(options)))
            return super().stream(messages, model=model, options=options, think=think)

    def slow(text):
        yield Token("a")
        gate.wait(5)
        yield Done(1, 1)

    session = ChatSession(Slow(slow), "A", {"num_ctx": 4096, "temperature": 0.7}, lambda ev: None)
    session.send("q")
    time.sleep(0.1)
    assert session.configure(model="B") == {"ok": False, "reason": "busy"}
    assert session.configure(options={"num_ctx": 8192, "temperature": 0.7}) == {"ok": False, "reason": "busy"}
    assert session.model == "A" and session.options == {"num_ctx": 4096, "temperature": 0.7}  # 바뀌지 않았다
    gate.set()
    session.join(5)
    assert seen == [("A", {"num_ctx": 4096, "temperature": 0.7})]
    assert session.configure(model="B") == {"ok": True}  # 끝난 뒤에는 바꿀 수 있다


def test_options는_바깥에서_고쳐도_세션에_영향이_없다():
    options = {"num_ctx": 4096, "temperature": 0.7}
    session = ChatSession(ScriptedClient(echo), "A", options, lambda ev: None)
    options["num_ctx"] = 99999
    session.options["num_ctx"] = 99999
    assert session.options == {"num_ctx": 4096, "temperature": 0.7}


def test_이미_중단된_턴은_호출_층_요청을_시작하지_않는다():
    """중단 뒤 모델을 내렸는데 이 요청이 뒤늦게 시작돼 그 모델을 다시 올리면 안 된다(작업 스레드가 아직 stream()을 부르기 전에 중단된 경우)."""
    from local_chat.session import _Turn

    client = ScriptedClient(echo)
    events = []
    session = ChatSession(client, "m", OPTIONS, events.append)
    turn = _Turn("q", "m", dict(OPTIONS), False)
    turn.cancelled.set()
    session._busy = True
    session._turn = turn
    session._idle.clear()
    worker = threading.Thread(target=session._run, args=(turn, session.messages_for("q")))
    session._workers.add(worker)
    worker.start()
    worker.join(5)
    assert client.calls == [] and events == []  # 요청이 가지 않았고, 취소된 턴의 이벤트는 버려졌다
    assert session.join(2) and session.send("다음") == {"ok": True}  # busy도 풀렸다
    session.join(5)
    assert len(client.calls) == 1


def test_wait_workers는_중단된_턴의_작업_스레드가_끝나기를_기다린다():
    gate = threading.Event()

    def slow(text):
        yield Token("a")
        gate.wait(5)
        yield Done(1, 1)

    session, events = make(ScriptedClient(slow))
    session.send("q")
    time.sleep(0.1)
    session.stop()
    assert session.join(2)  # busy는 바로 풀린다
    assert session.wait_workers(0.2) is False  # 작업 스레드는 아직 막혀 있다
    threading.Timer(0.3, gate.set).start()
    assert session.wait_workers(5) is True
    assert session.wait_workers(0) is True  # 더 기다릴 스레드가 없다
