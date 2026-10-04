"""webapp.Api: 모델 목록, 모델 전환(이전 모델 내리기), 옵션 변경. 세 호출 층 모두로 확인한다(창 없이)."""

import threading
import time

import pytest

from fake_ollama import chunk, done_chunk, send_body, send_headers, send_lines
from local_chat.clients import CLIENTS
from local_chat.webapp import Api

OPTIONS = {"num_ctx": 4096, "temperature": 0.7}
CAPS = {
    "qwen3:8b": ["completion", "tools", "thinking"],
    "exaone3.5:7.8b": ["completion"],
    "bge-m3:latest": ["embedding"],
}


class Window:
    def __init__(self):
        self.events = []

    def evaluate_js(self, code):
        self.events.append(code)


@pytest.fixture
def api_for(fake):
    fake.tags = list(CAPS)
    fake.capabilities_by_model = CAPS
    fake.script = lambda h: send_lines(h, [chunk("답"), done_chunk(1, 1_000_000_000)])

    def make(name, model="qwen3:8b"):
        api = Api(CLIENTS[name](host=fake.host), model, dict(OPTIONS))
        api._window = Window()
        return api

    return make


def ask(api, text="q"):
    assert api.send(text) == {"ok": True}
    assert api._session.join(10)


@pytest.mark.parametrize("name", list(CLIENTS))
def test_드롭다운_목록은_tags의_모든_모델이고_임베딩은_채팅_불가로_표시한다(api_for, name):
    data = api_for(name).models()
    assert data["current"] == "qwen3:8b"
    assert data["models"] == [
        {"name": "qwen3:8b", "chat": True, "thinking": True},
        {"name": "exaone3.5:7.8b", "chat": True, "thinking": False},
        {"name": "bge-m3:latest", "chat": False, "thinking": False},
    ]


@pytest.mark.parametrize("name", list(CLIENTS))
def test_모델을_바꾸면_이전_모델에_keep_alive_0이_가고_다음_질문부터_새_모델로_답한다(fake, api_for, name):
    api = api_for(name)
    ask(api, "첫 질문")
    assert fake.requests[-1]["model"] == "qwen3:8b" and fake.requests[-1]["think"] is True
    assert fake.unloads == []  # 아직 바꾸지 않았다
    r = api.set_model("exaone3.5:7.8b")
    assert r["ok"] is True and r["unloaded"] is True and r["info"]["model"] == "exaone3.5:7.8b"
    assert fake.unloads == [{"model": "qwen3:8b", "messages": [], "keep_alive": 0, "stream": False}]  # 이전 모델을 내린다
    ask(api, "둘째 질문")
    last = fake.requests[-1]
    assert last["model"] == "exaone3.5:7.8b"  # 다음 질문부터 새 모델
    assert last["think"] is False  # 새 모델은 사고 과정을 지원하지 않으므로 끈다
    assert [m["content"] for m in last["messages"]][1:] == ["첫 질문", "답", "둘째 질문"]  # 대화는 이어진다
    assert api.info()["think"] is False and api.info()["model"] == "exaone3.5:7.8b"
    # 다시 사고 과정을 지원하는 모델로 돌아가면 이번엔 exaone이 내려간다
    assert api.set_model("qwen3:8b")["ok"] is True
    assert fake.unloads[-1]["model"] == "exaone3.5:7.8b" and len(fake.unloads) == 2
    ask(api, "셋째")
    assert fake.requests[-1]["model"] == "qwen3:8b" and fake.requests[-1]["think"] is True


@pytest.mark.parametrize("name", list(CLIENTS))
def test_같은_모델로_바꾸면_아무것도_내리지_않는다(fake, api_for, name):
    api = api_for(name)
    assert api.set_model("qwen3:8b") == {"ok": True, "unloaded": None, "info": api.info()}
    assert fake.unloads == []


@pytest.mark.parametrize("name", list(CLIENTS))
def test_목록에_없거나_채팅할_수_없는_모델로는_바꾸지_않고_아무것도_내리지_않는다(fake, api_for, name):
    api = api_for(name)
    for bad, reason in [("nope:1b", "unknown"), ("bge-m3:latest", "not_chat"), (None, "unknown"), (5, "unknown"), ("", "unknown")]:
        r = api.set_model(bad)
        assert r["ok"] is False and r["reason"] == reason, bad
    assert api.info()["model"] == "qwen3:8b" and fake.unloads == []


@pytest.mark.parametrize("name", list(CLIENTS))
def test_답변_중_모델_전환은_거절하고_이전_모델도_내리지_않는다(fake, api_for, name):
    gate = threading.Event()

    def script(h):
        send_headers(h)
        send_body(h, [chunk("가")])
        gate.wait(10)
        send_body(h, [chunk("나"), done_chunk(2, 1_000_000_000)])

    fake.script = script
    api = api_for(name)
    api.send("긴 답변")
    deadline = time.time() + 5
    while not api._window.events and time.time() < deadline:
        time.sleep(0.01)
    assert not api._session.join(0)  # 답변이 아직 진행 중이다(gate가 열리기 전)
    r = api.set_model("exaone3.5:7.8b")
    assert r == {"ok": False, "reason": "busy", "message": "답변 중에는 바꿀 수 없다"}
    assert fake.unloads == []  # 답변 중인 모델을 내리지 않았다
    assert api.info()["model"] == "qwen3:8b"
    assert api.set_options(8192, 0.2)["reason"] == "busy"
    gate.set()
    assert api._session.join(10)
    assert api.set_model("exaone3.5:7.8b")["ok"] is True  # 끝난 뒤에는 된다
    assert len(fake.requests) == 1 and fake.requests[0]["model"] == "qwen3:8b"  # 진행 중이던 답은 원래 모델로 끝났다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_이전_모델을_내리지_못하면_전환을_되돌리고_새_모델_질문을_보내지_않는다(fake, api_for, name):
    """이전 모델이 남아 있을 수 있는데 새 모델을 올리면 두 모델이 VRAM에서 겹친다(D-6)."""
    ask(api_for(name))  # 준비 확인용
    for fail in ("500", "오류 본문"):
        fake.requests.clear()
        fake.unloads.clear()
        fake.unload_status, fake.unload_body = (500, None) if fail == "500" else (200, {"error": "unload failed"})
        api = api_for(name)
        r = api.set_model("exaone3.5:7.8b")
        assert r["ok"] is False and r["reason"] == "unload_failed" and "다시 시도" in r["message"], fail
        assert api.info()["model"] == "qwen3:8b" and api.info()["think"] is True  # 모델과 think가 이전 값으로 돌아갔다
        assert api._switching is False  # 전환 중 표시도 풀렸다
        ask(api)
        assert fake.requests[-1]["model"] == "qwen3:8b"  # 질문은 이전 모델로 간다. 새 모델은 올라가지 않는다
        fake.unload_status, fake.unload_body = 200, None
        r = api.set_model("exaone3.5:7.8b")  # 서버가 나아지면 다시 시도할 수 있다
        assert r["ok"] is True and r["unloaded"] is True


@pytest.mark.parametrize("name", list(CLIENTS))
def test_설치돼_있지_않은_이전_모델은_내릴_것이_없으므로_전환한다(fake, name):
    fake.tags = ["exaone3.5:7.8b"]
    fake.capabilities_by_model = {"exaone3.5:7.8b": ["completion"], "local-only:1b": ["completion", "thinking"]}
    fake.unload_status = 404
    fake.script = lambda h: send_lines(h, [chunk("답"), done_chunk(1, 1_000_000_000)])
    api = Api(CLIENTS[name](host=fake.host), "local-only:1b", dict(OPTIONS))
    api._window = Window()
    r = api.set_model("exaone3.5:7.8b")
    assert r["ok"] is True and r["unloaded"] is None and r["info"]["model"] == "exaone3.5:7.8b"


@pytest.mark.parametrize("name", list(CLIENTS))
def test_목록을_읽을_때_확인하지_못한_모델은_고르는_순간_다시_확인한다(fake, name):
    fake.tags = ["qwen3:8b", "exaone3.5:7.8b", "bge-m3:latest", "broken:1b"]
    fake.capabilities_by_model = {"qwen3:8b": ["completion", "thinking"], "exaone3.5:7.8b": "이상한 값", "bge-m3:latest": "이상한 값", "broken:1b": "이상한 값"}
    fake.script = lambda h: send_lines(h, [chunk("답"), done_chunk(1, 1_000_000_000)])
    api = Api(CLIENTS[name](host=fake.host), "qwen3:8b", dict(OPTIONS))
    api._window = Window()
    assert [m["chat"] for m in api.models()["models"]] == [True, None, None, None]  # 확인 못 한 모델은 채팅 가능으로 가정하지 않는다
    # 다시 확인해도 알 수 없으면 바꾸지 않고, 아무것도 내리지 않는다
    r = api.set_model("broken:1b")
    assert r["ok"] is False and r["reason"] == "unknown_capabilities" and fake.unloads == []
    # 이번엔 서버가 임베딩이라고 알려 준다 -> 거절
    fake.capabilities_by_model["bge-m3:latest"] = ["embedding"]
    r = api.set_model("bge-m3:latest")
    assert r["ok"] is False and r["reason"] == "not_chat" and fake.unloads == []
    assert api.models()["models"][2]["chat"] is False  # 목록도 갱신됐다
    # 채팅 모델이라고 알려 주면 바뀌고, 능력(think)도 그때 확인한 값을 쓴다
    fake.capabilities_by_model["exaone3.5:7.8b"] = ["completion"]
    r = api.set_model("exaone3.5:7.8b")
    assert r["ok"] is True and r["info"]["think"] is False and len(fake.unloads) == 1
    ask(api)
    assert fake.requests[-1]["model"] == "exaone3.5:7.8b" and fake.requests[-1]["think"] is False


@pytest.mark.parametrize("name", list(CLIENTS))
def test_중단한_뒤_바로_전환해도_이전_요청이_끝난_다음에_이전_모델을_내린다(fake, api_for, name):
    """stop()은 작업 스레드를 기다리지 않고 busy를 푼다. 내리기 전에 이전 요청이 끝나야 그 요청이 모델을 다시 올리지 못한다."""
    gate = threading.Event()
    gate_time = {}

    def script(h):
        send_headers(h)
        send_body(h, [chunk("가")])
        gate.wait(10)  # 서버가 멈춘 것처럼 응답을 더 보내지 않는다
        gate_time.setdefault("t", time.perf_counter())

    fake.script = script
    api = api_for(name)
    api._worker_wait = 5.0
    api.send("긴 답변")
    deadline = time.time() + 5
    while not api._window.events and time.time() < deadline:
        time.sleep(0.01)
    api.stop()
    assert api._session.join(2)  # 화면은 바로 풀린다
    assert not api._session.wait_workers(0)  # 그러나 이전 요청의 작업 스레드는 아직 돌고 있다
    threading.Timer(0.5, gate.set).start()
    r = api.set_model("exaone3.5:7.8b")
    assert r["ok"] is True and r["unloaded"] is True
    assert fake.unload_time >= gate_time["t"]  # 이전 요청이 끝난 뒤에 이전 모델을 내렸다
    assert api._session.wait_workers(0)  # 이전 작업 스레드가 끝났다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_이전_요청이_끝나지_않아도_기다리는_시간만_기다리고_전환한다(fake, api_for, name):
    gate = threading.Event()

    def script(h):
        send_headers(h)
        send_body(h, [chunk("가")])
        gate.wait(10)

    fake.script = script
    api = api_for(name)
    api._worker_wait = 0.3
    api.send("긴 답변")
    deadline = time.time() + 5
    while not api._window.events and time.time() < deadline:
        time.sleep(0.01)
    api.stop()
    t0 = time.perf_counter()
    r = api.set_model("exaone3.5:7.8b")
    assert r["ok"] is True and 0.3 <= time.perf_counter() - t0 < 3  # 영원히 기다리지 않는다
    gate.set()


@pytest.mark.parametrize("name", list(CLIENTS))
def test_set_options는_아주_큰_정수에도_예외_없이_거절한다(fake, api_for, name):
    api = api_for(name)
    for args in [(10**400, 0.7), (4096, 10**400), (-(10**400), 0.7)]:
        r = api.set_options(*args)
        assert r["ok"] is False and r["reason"] == "invalid", args
    assert api.info()["num_ctx"] == 4096


@pytest.mark.parametrize("name", list(CLIENTS))
def test_num_ctx와_temperature는_다음_요청에_그대로_실린다(fake, api_for, name):
    api = api_for(name)
    ask(api)
    assert fake.requests[-1]["options"] == {"num_ctx": 4096, "temperature": 0.7}
    r = api.set_options(8192, 0.2)
    assert r["ok"] is True and r["info"]["num_ctx"] == 8192 and r["info"]["temperature"] == 0.2
    ask(api)
    assert fake.requests[-1]["options"] == {"num_ctx": 8192, "temperature": 0.2}
    assert api.set_options(5120, 0)["ok"] is True  # temperature 0은 올바른 값이다
    ask(api)
    assert fake.requests[-1]["options"] == {"num_ctx": 5120, "temperature": 0.0}


@pytest.mark.parametrize("name", list(CLIENTS))
def test_범위_밖_옵션은_거절하고_기존_값을_유지한다(fake, api_for, name):
    api = api_for(name)
    bad_values = [(4095, 0.7), (8193, 0.7), (32768, 0.7), (4096.5, 0.7), ("8192", 0.7), (None, 0.7), (4096, -0.1), (4096, 2.5), (4096, None), (4096, "x")]
    for num_ctx, temperature in bad_values:
        r = api.set_options(num_ctx, temperature)
        assert r["ok"] is False and r["reason"] == "invalid" and r["message"], (num_ctx, temperature)
    assert api.info()["num_ctx"] == 4096 and api.info()["temperature"] == 0.7
    ask(api)
    assert fake.requests[-1]["options"] == {"num_ctx": 4096, "temperature": 0.7}  # 요청에는 거절 전의 값이 실린다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_모델_목록을_못_받으면_현재_모델만_보이고_그대로_동작한다(fake, name):
    fake.tags = None
    fake.capabilities = ["completion", "thinking"]
    fake.script = lambda h: send_lines(h, [chunk("답"), done_chunk(1, 1_000_000_000)])
    api = Api(CLIENTS[name](host=fake.host), "qwen3:8b", dict(OPTIONS))
    api._window = Window()
    assert api.models() == {"models": [{"name": "qwen3:8b", "chat": True, "thinking": True}], "current": "qwen3:8b"}
    ask(api)
    assert fake.requests[-1]["model"] == "qwen3:8b" and fake.requests[-1]["think"] is True


@pytest.mark.parametrize("name", list(CLIENTS))
def test_이전_모델을_내리는_동안에는_질문을_받지_않고_내리기가_끝나면_새_모델로_간다(fake, api_for, name):
    """D-6: 이전 모델을 내리는 도중에 새 모델의 질문이 시작되면 두 모델이 VRAM에서 겹친다."""
    fake.unload_delay = 1.0
    api = api_for(name)
    result = {}
    t = threading.Thread(target=lambda: result.update(api.set_model("exaone3.5:7.8b")))
    t.start()
    assert fake.unload_started.wait(5)  # 내리기 요청이 서버에 도착했다(아직 응답 전)
    r = api.send("전환 중 질문")
    assert r == {"ok": False, "reason": "switching"}
    assert fake.requests == []  # 새 모델 요청은 가지 않았다
    t.join(10)
    assert result["ok"] is True and result["unloaded"] is True
    assert api.send("전환 뒤 질문") == {"ok": True}  # 내리기가 끝났으니 받는다
    assert api._session.join(10)
    assert [r["model"] for r in fake.requests] == ["exaone3.5:7.8b"]  # 내리기 뒤에 새 모델 요청이 갔다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_전환과_질문이_거의_동시에_와도_둘_중_하나만_성립한다(fake, api_for, name):
    """질문이 먼저면 전환이 거절되고, 전환이 먼저면 질문이 거절된다. 새 모델 질문이 이전 모델 내리기와 겹치면 안 된다."""
    for _ in range(15):
        fake.requests.clear()
        fake.unloads.clear()
        fake.unload_delay = 0.15
        api = api_for(name)
        out = {}
        start = threading.Barrier(2)

        def do_switch():
            start.wait()
            out["switch"] = api.set_model("exaone3.5:7.8b")

        def do_send():
            start.wait()
            out["send"] = api.send("동시 질문")

        threads = [threading.Thread(target=do_switch), threading.Thread(target=do_send)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        api._session.join(10)
        if out["send"]["ok"]:
            assert out["switch"]["ok"] is False and out["switch"]["reason"] == "busy"  # 질문이 먼저 시작돼 전환이 거절됐다
            assert fake.unloads == [] and [r["model"] for r in fake.requests] == ["qwen3:8b"]
        else:
            assert out["send"]["reason"] == "switching" and out["switch"]["ok"] is True  # 전환이 먼저라 질문이 거절됐다
            assert fake.requests == [] and len(fake.unloads) == 1


@pytest.mark.parametrize("name", list(CLIENTS))
def test_목록에_없는_현재_모델은_맨_앞에_넣고_능력은_show로_확인한다(fake, name):
    fake.tags = ["exaone3.5:7.8b", "bge-m3:latest"]
    fake.capabilities_by_model = {"exaone3.5:7.8b": ["completion"], "bge-m3:latest": ["embedding"], "local-only:1b": ["completion", "thinking"]}
    fake.unload_status = 404  # 설치돼 있지 않아 내릴 수 없다
    fake.script = lambda h: send_lines(h, [chunk("답"), done_chunk(1, 1_000_000_000)])
    api = Api(CLIENTS[name](host=fake.host), "local-only:1b", dict(OPTIONS))
    api._window = Window()
    data = api.models()
    assert [m["name"] for m in data["models"]] == ["local-only:1b", "exaone3.5:7.8b", "bge-m3:latest"] and data["current"] == "local-only:1b"
    assert data["models"][0] == {"name": "local-only:1b", "chat": True, "thinking": True}  # 능력은 /api/show로 확인한다
    r = api.set_model("exaone3.5:7.8b")
    assert r["ok"] is True and r["unloaded"] is None  # 설치돼 있지 않은 이전 모델은 내릴 것이 없다(404)
    ask(api)
    assert fake.requests[-1]["model"] == "exaone3.5:7.8b"
