"""webapp.Api: 모델 목록, 모델 전환(이전 모델 내리기), 옵션 변경. 세 호출 층 모두로 확인한다(창 없이)."""

import json
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
def test_이전_요청이_끝나지_않았으면_내리지도_전환하지도_않고_끝나면_다시_할_수_있다(fake, api_for, name):
    """끝났는지 모르는 채로 내리면 그 요청이 뒤늦게 이전 모델을 다시 올릴 수 있다. 그러면 두 모델이 겹친다."""
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
    assert r["ok"] is False and r["reason"] == "previous_request_pending" and "다시 시도" in r["message"]
    assert 0.3 <= time.perf_counter() - t0 < 3  # 영원히 기다리지 않는다
    assert fake.unloads == []  # 내리지 않았다
    assert api.info()["model"] == "qwen3:8b" and api.info()["think"] is True and api._switching is False
    gate.set()  # 이전 요청이 끝난다
    assert api._session.wait_workers(5)
    r = api.set_model("exaone3.5:7.8b")
    assert r["ok"] is True and r["unloaded"] is True and len(fake.unloads) == 1


@pytest.mark.parametrize("name", list(CLIENTS))
def test_내리기_응답을_읽지_못해도_전환을_되돌리고_새_모델_질문을_보내지_않는다(fake, api_for, name):
    """예: 너무 깊게 중첩된 JSON은 json.loads가 RecursionError를 낸다. 어떤 예외도 복구를 우회하면 안 된다."""
    fake.unload_script = lambda h: send_lines(h, [b"[" * 5000 + b"]" * 5000 + chr(10).encode()])
    api = api_for(name)
    r = api.set_model("exaone3.5:7.8b")
    assert r["ok"] is False and r["reason"] == "unload_failed"
    assert api.info()["model"] == "qwen3:8b" and api._switching is False
    ask(api)
    assert fake.requests[-1]["model"] == "qwen3:8b"


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


# ---------------------------------------------------------------- Phase 5: 대화 저장


def pick(path):
    return lambda mode: str(path) if path is not None else None


@pytest.mark.parametrize("name", list(CLIENTS))
def test_저장한_대화를_새_앱에서_열면_같은_메시지_수와_순서와_role로_복원되고_문맥으로_이어진다(fake, api_for, tmp_path, name):
    api = api_for(name)
    for q in ("첫째 질문 😊", "둘째\n질문", "셋째"):
        ask(api, q)
    saved = api._session.export_messages()
    assert len(saved) == 6
    path = tmp_path / "대화 저장" / "한글 파일.json"
    path.parent.mkdir()
    r = api._save_to(str(path))
    assert r == {"ok": True, "path": str(path), "count": 6}
    # 새 앱(새 세션)에서 연다
    fake.requests.clear()
    fresh = api_for(name)
    assert fresh._session.turn_count == 0
    r = fresh._load_from(str(path))
    assert r["ok"] is True and r["count"] == 6 and r["messages"] == saved
    assert [m["role"] for m in r["messages"]] == ["user", "assistant"] * 3
    assert fresh._session.export_messages() == saved
    ask(fresh, "넷째 질문")
    contents = [m["content"] for m in fake.requests[-1]["messages"]]
    assert contents[1:] == ["첫째 질문 😊", "답", "둘째\n질문", "답", "셋째", "답", "넷째 질문"]  # 복원한 대화가 문맥으로 이어진다
    assert fresh.info()["model"] == "qwen3:8b"  # 불러와도 현재 모델은 바뀌지 않는다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_복원한_대화가_10턴을_넘어도_요청에는_직전_10턴만_실린다(fake, api_for, tmp_path, name):
    from local_chat import conversation

    messages = []
    for i in range(1, 13):
        messages += [{"role": "user", "content": f"질문{i}"}, {"role": "assistant", "content": f"답{i}"}]
    path = tmp_path / "long.json"
    conversation.save_file(path, messages)
    api = api_for(name)
    assert api._load_from(str(path))["count"] == 24
    ask(api, "질문13")
    contents = [m["content"] for m in fake.requests[-1]["messages"]]
    assert len(contents) == 22 and contents[1] == "질문3" and contents[-2] == "답12" and contents[-1] == "질문13"


@pytest.mark.parametrize("name", list(CLIENTS))
def test_손상된_파일을_열면_거절하고_현재_대화는_그대로다(fake, api_for, tmp_path, name):
    api = api_for(name)
    ask(api, "지켜야 할 질문")
    before = api._session.export_messages()
    cases = {
        "깨진JSON.json": b'{"messages": [{"role": "user", "content": "q"}, {"role": "assis',
        "역할순서.json": json.dumps([{"role": "assistant", "content": "a"}, {"role": "user", "content": "q"}]).encode(),
        "홀수.json": json.dumps([{"role": "user", "content": "q"}]).encode(),
        "배열아님.json": b'{"messages": "x"}',
        "cp949.json": json.dumps({"messages": [{"role": "user", "content": "안녕"}, {"role": "assistant", "content": "반가워"}]}, ensure_ascii=False).encode("cp949"),
        "빈파일.json": b"",
    }
    for file_name, raw in cases.items():
        path = tmp_path / file_name
        path.write_bytes(raw)
        r = api._load_from(str(path))
        assert r["ok"] is False and r["reason"] == "error" and r["message"], file_name
        assert api._session.export_messages() == before, file_name  # 거절돼도 현재 대화는 그대로다
    r = api._load_from(str(tmp_path / "없는파일.json"))
    assert r["ok"] is False and "읽지 못했다" in r["message"]
    assert api._session.export_messages() == before
    ask(api, "이어서")  # 계속 쓸 수 있다
    assert api._session.turn_count == 2


@pytest.mark.parametrize("name", list(CLIENTS))
def test_답변_중에는_저장도_열기도_거절하고_파일을_건드리지_않는다(fake, api_for, tmp_path, name):
    from local_chat import conversation

    path = tmp_path / "chat.json"
    conversation.save_file(path, [{"role": "user", "content": "옛"}, {"role": "assistant", "content": "답"}])
    before = path.read_bytes()
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
    r = api._save_to(str(path))
    assert r["ok"] is False and r["reason"] == "busy"
    assert path.read_bytes() == before  # 저장하지 않았다
    r = api._load_from(str(path))
    assert r["ok"] is False and r["reason"] == "busy"
    assert api._session.turn_count == 0  # 대화가 바뀌지 않았다
    gate.set()
    assert api._session.join(10)
    assert api._save_to(str(path))["ok"] is True  # 끝난 뒤에는 된다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_모델을_바꾸는_중에는_저장도_열기도_거절한다(fake, api_for, tmp_path, name):
    fake.unload_delay = 1.0
    api = api_for(name)
    t = threading.Thread(target=lambda: api.set_model("exaone3.5:7.8b"))
    t.start()
    assert fake.unload_started.wait(5)
    path = tmp_path / "chat.json"
    assert api._save_to(str(path))["reason"] == "switching"
    assert api._load_from(str(path))["reason"] == "switching"
    assert not path.exists()
    t.join(10)
    assert api._save_to(str(path))["ok"] is True


@pytest.mark.parametrize("name", list(CLIENTS))
def test_대화상자를_취소하면_아무것도_하지_않는다(fake, api_for, tmp_path, name):
    api = api_for(name)
    ask(api, "질문")
    before = api._session.export_messages()
    api._pick_path = pick(None)  # 취소
    assert api.save_chat() == {"ok": False, "reason": "cancelled", "message": "저장을 취소했다"}
    assert api.load_chat() == {"ok": False, "reason": "cancelled", "message": "열기를 취소했다"}
    assert api._session.export_messages() == before and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("name", list(CLIENTS))
def test_경로를_안_주면_대화상자가_고른_경로로_저장하고_연다(fake, api_for, tmp_path, name):
    api = api_for(name)
    ask(api, "질문")
    path = tmp_path / "고른 파일.json"
    modes = []
    api._pick_path = lambda mode: (modes.append(mode), str(path))[1]
    assert api.save_chat()["ok"] is True
    fresh = api_for(name)
    fresh._pick_path = api._pick_path
    r = fresh.load_chat()
    assert r["ok"] is True and r["count"] == 2 and modes == ["save", "open"]


@pytest.mark.parametrize("result,expected", [(None, None), ((), None), ([], None), ("C:/a/chat.json", "C:/a/chat.json"), (("C:/a/chat.json",), "C:/a/chat.json"), (["C:/a/chat.json", "x"], "C:/a/chat.json")])
def test_파일_대화상자의_반환_형태를_경로_하나나_None으로_정리한다(fake, result, expected):
    import webview

    class W:
        calls = []

        def create_file_dialog(self, kind, **kw):
            W.calls.append((kind, kw))
            return result

    api = Api(CLIENTS["http"](host=fake.host), "qwen3:8b", dict(OPTIONS))
    api._window = W()
    assert api._dialog("save") == expected
    assert api._dialog("open") == expected
    (save_kind, save_kw), (open_kind, _) = W.calls
    assert save_kind == webview.FileDialog.SAVE and open_kind == webview.FileDialog.OPEN
    assert save_kw["save_filename"] == "chat.json"  # 기본 파일 이름을 제안한다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_빈_대화도_저장하고_열면_현재_대화가_비워진다(fake, api_for, tmp_path, name):
    api = api_for(name)
    path = tmp_path / "empty.json"
    assert api._save_to(str(path)) == {"ok": True, "path": str(path), "count": 0}
    ask(api, "질문")
    r = api._load_from(str(path))
    assert r["ok"] is True and r["count"] == 0 and r["messages"] == [] and api._session.turn_count == 0


@pytest.mark.parametrize("name", list(CLIENTS))
def test_저장_실패는_예외가_아니라_오류_응답이고_기존_파일은_그대로다(fake, api_for, tmp_path, name):
    api = api_for(name)
    ask(api, "질문")
    r = api._save_to(str(tmp_path / "없는폴더" / "chat.json"))
    assert r["ok"] is False and r["reason"] == "error" and "저장하지 못했다" in r["message"]
    path = tmp_path / "chat.json"
    assert api._save_to(str(path))["ok"] is True
    before = path.read_bytes()
    api._session._turns.append(("짝 없는 서로게이트 \ud83d", "답"))  # UTF-8로 쓸 수 없는 문자가 대화에 들어간 경우
    r = api._save_to(str(path))
    assert r["ok"] is False and "UTF-8" in r["message"]
    assert path.read_bytes() == before


@pytest.mark.parametrize("name", list(CLIENTS))
def test_중단돼_받은_데까지만_남은_턴도_저장하고_복원한다(fake, api_for, tmp_path, name):
    gate = threading.Event()

    def script(h):
        send_headers(h)
        send_body(h, [chunk("받은 부분")])
        gate.wait(10)

    fake.script = script
    api = api_for(name)
    api.send("긴 답변")
    deadline = time.time() + 5
    while not api._window.events and time.time() < deadline:
        time.sleep(0.01)
    api.stop()
    gate.set()
    path = tmp_path / "stopped.json"
    assert api._save_to(str(path))["count"] == 2
    fresh = api_for(name)
    assert fresh._load_from(str(path))["messages"] == [{"role": "user", "content": "긴 답변"}, {"role": "assistant", "content": "받은 부분"}]


def test_JS에_공개되는_저장_열기는_경로를_받지_않는다():
    """공개 메서드(밑줄 없음)는 pywebview가 JS에 노출한다. 임의 경로를 받는 메서드는 밑줄로 숨긴다."""
    import inspect

    assert list(inspect.signature(Api.save_chat).parameters) == ["self"]
    assert list(inspect.signature(Api.load_chat).parameters) == ["self"]
    public = {n for n in dir(Api) if not n.startswith("_") and callable(getattr(Api, n))}
    assert {"save_chat", "load_chat", "history"} <= public
    assert not {"_save_to", "_load_from"} & public


def test_파일_대화상자_호출_형식이_실제_pywebview_시그니처와_파일_형식_문법에_맞는다():
    """create_file_dialog는 시험에서 실행하지 못하므로, 우리가 넘기는 인자가 시그니처와 pywebview의 file_types 문법에 맞는지 확인한다."""
    import inspect

    import webview
    from webview.util import parse_file_type

    sig = inspect.signature(webview.Window.create_file_dialog)
    sig.bind(None, webview.FileDialog.SAVE, save_filename="chat.json", file_types=("JSON (*.json)",))
    sig.bind(None, webview.FileDialog.OPEN, file_types=("JSON (*.json)",))
    assert parse_file_type("JSON (*.json)") == ("JSON", "*.json")


@pytest.mark.parametrize("name", list(CLIENTS))
def test_사고_과정만_오고_끝난_턴은_기록하지_않아_저장한_파일을_다시_열_수_있다(fake, api_for, tmp_path, name):
    fake.script = lambda h: send_lines(h, [chunk("", thinking="생각만 하고"), done_chunk(1, 1_000_000_000)])
    api = api_for(name)
    ask(api, "질문")  # 화면에는 정상 종료로 보인다
    assert {k: v for k, v in api.history().items() if k != "version"} == {"messages": [], "file_busy": False}
    path = tmp_path / "chat.json"
    assert api._save_to(str(path))["count"] == 0
    fake.script = lambda h: send_lines(h, [chunk("답"), done_chunk(1, 1_000_000_000)])
    ask(api, "다음 질문")
    assert api._save_to(str(path))["count"] == 2
    assert api_for(name)._load_from(str(path))["count"] == 2  # 저장한 파일은 항상 다시 열 수 있다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_짝_없는_서로게이트가_든_파일은_거절하고_이후_대화가_오염되지_않는다(fake, api_for, tmp_path, name):
    api = api_for(name)
    ask(api, "지켜야 할 질문")
    before = api.history()
    path = tmp_path / "surrogate.json"
    path.write_bytes('[{"role": "user", "content": "\\ud800 안녕"}, {"role": "assistant", "content": "a"}]'.encode("utf-8"))
    r = api._load_from(str(path))
    assert r["ok"] is False and "UTF-8" in r["message"]
    assert api.history() == before
    ask(api, "이어서")  # 질문이 인코딩 오류로 실패하지 않는다
    assert fake.requests[-1]["messages"][-1]["content"] == "이어서"


@pytest.mark.parametrize("name", list(CLIENTS))
def test_history는_서버가_가진_대화를_돌려주고_답변_중에는_None이다(fake, api_for, name):
    gate = threading.Event()

    def script(h):
        send_headers(h)
        send_body(h, [chunk("가")])
        gate.wait(10)
        send_body(h, [chunk("나"), done_chunk(2, 1_000_000_000)])

    api = api_for(name)
    ask(api, "첫 질문")
    assert {k: v for k, v in api.history().items() if k != "version"} == {"messages": [{"role": "user", "content": "첫 질문"}, {"role": "assistant", "content": "답"}], "file_busy": False}
    fake.script = script
    api.send("긴 답변")
    deadline = time.time() + 5
    while len(api._window.events) < 2 and time.time() < deadline:
        time.sleep(0.01)
    assert {k: v for k, v in api.history().items() if k != "version"} == {"messages": None, "file_busy": False}
    gate.set()
    api._session.join(10)


@pytest.mark.parametrize("name", list(CLIENTS))
def test_파일을_읽는_동안에는_질문과_모델_전환과_다른_파일_작업을_받지_않고_끝나면_복원이_온전하다(fake, api_for, tmp_path, monkeypatch, name):
    """파일 작업이 도는 동안(대화상자가 열려 있는 동안 포함) 대화가 바뀔 수 있는 조작을 모두 막아 경합 자체를 없앤다."""
    from local_chat import conversation

    path = tmp_path / "chat.json"
    conversation.save_file(path, [{"role": "user", "content": "파일의 질문"}, {"role": "assistant", "content": "파일의 답"}])
    api = api_for(name)
    reading = threading.Event()
    proceed = threading.Event()
    real_load = conversation.load_file

    def slow_load(p):
        reading.set()
        proceed.wait(10)
        return real_load(p)

    monkeypatch.setattr(conversation, "load_file", slow_load)
    out = {}
    t = threading.Thread(target=lambda: out.update(api._load_from(str(path))))
    t.start()
    assert reading.wait(5)
    assert {k: v for k, v in api.history().items() if k != "version"} == {"messages": [], "file_busy": True}  # 서버가 파일 작업 중임을 알린다
    assert api.send("읽는 중에 시작한 질문") == {"ok": False, "reason": "file"}
    assert api.set_model("exaone3.5:7.8b")["reason"] == "file_busy" and fake.unloads == []
    assert api._save_to(str(tmp_path / "other.json"))["reason"] == "file_busy" and not (tmp_path / "other.json").exists()
    assert api._load_from(str(path))["reason"] == "file_busy"
    proceed.set()
    t.join(10)
    assert out["ok"] is True and out["count"] == 2
    assert {k: v for k, v in api.history().items() if k != "version"} == {"messages": out["messages"], "file_busy": False}  # 파일의 대화 그대로, 작업이 끝났다
    assert api.send("끝난 뒤의 질문") == {"ok": True}
    api._session.join(10)


@pytest.mark.parametrize("name", list(CLIENTS))
def test_저장하는_동안에도_질문을_받지_않아_저장한_파일은_그_시점의_대화다(fake, api_for, tmp_path, monkeypatch, name):
    from local_chat import conversation

    api = api_for(name)
    ask(api, "저장 전 질문")
    writing = threading.Event()
    proceed = threading.Event()
    real_save = conversation.save_file

    def slow_save(p, messages, model=None):
        writing.set()
        proceed.wait(10)
        return real_save(p, messages, model)

    monkeypatch.setattr(conversation, "save_file", slow_save)
    path = tmp_path / "chat.json"
    out = {}
    t = threading.Thread(target=lambda: out.update(api._save_to(str(path))))
    t.start()
    assert writing.wait(5)
    assert api.send("저장하는 중에 시작한 질문") == {"ok": False, "reason": "file"}
    proceed.set()
    t.join(10)
    assert out["ok"] is True and out["count"] == 2
    assert [m["content"] for m in conversation.load_file(path)] == ["저장 전 질문", "답"]
    assert len(fake.requests) == 1  # 저장 중에 시작하려던 질문은 서버까지 가지 않았다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_대화상자가_열려_있는_동안에도_파일_작업_중이다(fake, api_for, tmp_path, name):
    api = api_for(name)
    opened = threading.Event()
    proceed = threading.Event()

    def slow_dialog(mode):
        opened.set()
        proceed.wait(10)
        return None  # 사용자가 취소했다

    api._pick_path = slow_dialog
    out = {}
    t = threading.Thread(target=lambda: out.update(api.save_chat()))
    t.start()
    assert opened.wait(5)
    assert api.history()["file_busy"] is True
    assert api.send("대화상자가 열려 있는 동안") == {"ok": False, "reason": "file"}
    proceed.set()
    t.join(10)
    assert out["reason"] == "cancelled" and api.history()["file_busy"] is False
    assert api.send("취소한 뒤") == {"ok": True}
    api._session.join(10)


@pytest.mark.parametrize("name", list(CLIENTS))
def test_중복된_키가_든_파일은_거절하고_현재_대화를_지우지_않는다(fake, api_for, tmp_path, name):
    api = api_for(name)
    ask(api, "지켜야 할 질문")
    before = api.history()["messages"]
    cases = {
        "messages 중복.json": '{"format":"local-chat","version":1,"messages":[{"role":"user","content":"질문"},{"role":"assistant","content":"답"}],"messages":[]}',
        "role 중복.json": '{"messages":[{"role":"system","role":"user","content":"q"},{"role":"assistant","content":"a"}]}',
        "content 중복.json": '{"messages":[{"role":"user","content":null,"content":"q"},{"role":"assistant","content":"a"}]}',
        "version 중복.json": '{"version":2,"version":1,"messages":[]}',
    }
    for file_name, text in cases.items():
        path = tmp_path / file_name
        path.write_bytes(text.encode("utf-8"))
        r = api._load_from(str(path))
        assert r["ok"] is False and "같은 키" in r["message"], file_name
        assert api.history()["messages"] == before, file_name  # 대화가 비워지거나 바뀌지 않았다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_읽을_수_없는_크기가_될_대화는_저장하지_않고_기존_파일을_보존한다(fake, api_for, tmp_path, monkeypatch, name):
    """저장은 되는데 다시 열 수 없는 파일이 생기면 안 된다. 열기의 크기 한도와 같은 한도를 저장에도 건다."""
    from local_chat import conversation

    api = api_for(name)
    ask(api, "질문")
    path = tmp_path / "chat.json"
    assert api._save_to(str(path))["ok"] is True
    before = path.read_bytes()
    monkeypatch.setattr(conversation, "MAX_BYTES", len(before) - 1)  # 같은 대화의 저장 결과가 한도를 넘는다
    r = api._save_to(str(path))
    assert r["ok"] is False and "너무 커서" in r["message"]
    assert path.read_bytes() == before and [p.name for p in tmp_path.iterdir()] == ["chat.json"]
    monkeypatch.setattr(conversation, "MAX_BYTES", len(before))
    assert api._save_to(str(path))["ok"] is True  # 한도 안이면 저장되고
    assert api._load_from(str(path))["ok"] is True  # 저장한 파일은 항상 다시 열 수 있다


# ---------------------------------------------------------------- Phase 5 보완: 대화 버전 확인, 감시


@pytest.mark.parametrize("name", list(CLIENTS))
def test_화면이_아는_대화_버전이_서버와_다르면_질문을_보내지_않고_서버의_대화를_돌려준다(fake, api_for, tmp_path, name):
    """저장·열기 응답이 화면에 도착하지 못하는 등 어떤 이유로든 화면과 서버의 대화가 어긋나면, 질문이 보이지 않는 문맥으로 나가지 않게 한다."""
    from local_chat import conversation

    api = api_for(name)
    v0 = api.info()["version"]
    assert api.send("첫 질문", v0) == {"ok": True}  # 맞는 버전이면 보낸다
    api._session.join(10)
    v1 = api.history()["version"]
    assert v1 == v0 + 1  # 끝난 턴이 기록되면 버전이 오른다
    path = tmp_path / "chat.json"
    conversation.save_file(path, [{"role": "user", "content": "파일의 질문"}, {"role": "assistant", "content": "파일의 답"}])
    fake.requests.clear()
    assert api._load_from(str(path))["version"] == v1 + 1  # 화면이 이 응답을 못 받았다고 하자(화면은 v1을 안다)
    r = api.send("보이지 않는 문맥으로 나가면 안 되는 질문", v1)
    assert r["ok"] is False and r["reason"] == "desync" and r["version"] == v1 + 1
    assert r["messages"] == [{"role": "user", "content": "파일의 질문"}, {"role": "assistant", "content": "파일의 답"}]
    assert fake.requests == []  # 모델에는 아무것도 가지 않았다
    assert api.send("다시 보낸 질문", r["version"]) == {"ok": True}  # 서버의 버전을 알면 보낸다
    api._session.join(10)
    contents = [m["content"] for m in fake.requests[-1]["messages"]]
    assert contents[1:] == ["파일의 질문", "파일의 답", "다시 보낸 질문"]


@pytest.mark.parametrize("name", list(CLIENTS))
def test_버전은_기록되지_않는_턴과_실패에는_오르지_않고_복원에는_오른다(fake, api_for, tmp_path, name):
    from local_chat import conversation

    api = api_for(name)
    v = api.info()["version"]
    fake.script = lambda h: send_lines(h, [chunk("", thinking="생각만"), done_chunk(1, 1_000_000_000)])  # 빈 답: 기록되지 않는다
    ask(api, "빈 답이 되는 질문")
    assert api.history()["version"] == v
    fake.script = lambda h: send_lines(h, [{"error": "boom"}], status=500)
    ask(api, "실패하는 질문")
    assert api.history()["version"] == v
    path = tmp_path / "empty.json"
    conversation.save_file(path, [])
    api._load_from(str(path))
    assert api.history()["version"] == v + 1  # 내용이 같아 보여도 복원은 버전을 올린다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_종료_이벤트는_서버의_대화_버전을_알린다(fake, api_for, name):
    api = api_for(name)
    ask(api, "질문")
    terminal = [json.loads(c[len("window.onChatEvent("):-1]) for c in api._window.events if '"done"' in c]
    assert terminal and terminal[-1]["version"] == api.history()["version"]


def test_버전을_주지_않으면_확인하지_않는다(fake, api_for):
    api = api_for("http")
    assert api.send("질문") == {"ok": True}  # 시험·내부 호출 호환
    api._session.join(10)
