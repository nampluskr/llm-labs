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
