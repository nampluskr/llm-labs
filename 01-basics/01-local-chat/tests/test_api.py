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
def test_모델_내리기가_실패해도_전환은_유지하고_알린다(fake, api_for, name):
    fake.unload_status = 404
    api = api_for(name)
    r = api.set_model("exaone3.5:7.8b")
    assert r["ok"] is True and r["unloaded"] is False and r["info"]["model"] == "exaone3.5:7.8b"
    ask(api)
    assert fake.requests[-1]["model"] == "exaone3.5:7.8b"


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
def test_목록에_없는_현재_모델은_맨_앞에_넣고_다른_모델로_바꾸면_내리기_실패를_알린다(fake, name):
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
    assert r["ok"] is True and r["unloaded"] is False  # 전환은 유지하고 내리기 실패를 알린다
    ask(api)
    assert fake.requests[-1]["model"] == "exaone3.5:7.8b"
