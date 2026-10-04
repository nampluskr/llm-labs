import socket
import time

from fake_ollama import send_headers
from local_chat.models import list_models, unload_model


def test_tags의_모든_모델을_chat_thinking_여부와_함께_돌려준다(fake):
    fake.tags = ["qwen3:8b", "exaone3.5:7.8b", "bge-m3:latest"]
    fake.capabilities_by_model = {
        "qwen3:8b": ["completion", "tools", "thinking"],
        "exaone3.5:7.8b": ["completion"],
        "bge-m3:latest": ["embedding"],
    }
    assert list_models(fake.host) == [
        {"name": "qwen3:8b", "chat": True, "thinking": True},
        {"name": "exaone3.5:7.8b", "chat": True, "thinking": False},
        {"name": "bge-m3:latest", "chat": False, "thinking": False},  # 임베딩 모델은 목록에는 있지만 채팅은 못 한다
    ]


def test_모델_능력을_알_수_없으면_채팅_가능_사고_없음으로_둔다(fake):
    fake.tags = ["a"]
    fake.capabilities_by_model = {"a": "이상한 값"}
    assert list_models(fake.host) == [{"name": "a", "chat": True, "thinking": False}]


def test_목록을_못_받으면_빈_리스트(fake):
    fake.tags = None  # /api/tags가 404
    assert list_models(fake.host) == []
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert list_models(f"http://127.0.0.1:{port}", timeout=1) == []


def test_응답을_조금씩_흘려도_전체_시간_안에_포기한다(fake):
    fake.tags = ["a"]

    def trickle(h):
        send_headers(h)
        try:
            for _ in range(40):
                h.wfile.write(b" ")
                h.wfile.flush()
                time.sleep(0.25)
        except OSError:
            pass

    fake.show_script = trickle  # 모델별 확인이 느리다
    t0 = time.perf_counter()
    models = list_models(fake.host, timeout=1.5)
    assert time.perf_counter() - t0 < 4
    assert models == [{"name": "a", "chat": True, "thinking": False}]  # 목록은 유지하고 능력만 모름으로 둔다


def test_모델_내리기는_빈_messages와_keep_alive_0을_보낸다(fake):
    assert unload_model(fake.host, "qwen3:8b") is True
    assert fake.unloads == [{"model": "qwen3:8b", "messages": [], "keep_alive": 0, "stream": False}]
    assert fake.requests == []  # 일반 채팅 요청으로 세지 않는다


def test_모델_내리기가_실패하면_False(fake):
    fake.unload_status = 404
    assert unload_model(fake.host, "nope") is False
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert unload_model(f"http://127.0.0.1:{port}", "m", timeout=1) is False
