import socket
import time

from fake_ollama import send_headers, send_lines
from local_chat.models import FAILED, NOT_INSTALLED, UNLOADED, list_models, unload_model


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


def test_모델_능력을_알_수_없으면_chat은_None으로_둔다(fake):
    fake.tags = ["a"]
    fake.capabilities_by_model = {"a": "이상한 값"}
    # 확인하지 못했다고 채팅 가능으로 가정하면 임베딩 모델을 고를 수 있게 된다. 고르는 순간 다시 확인한다
    assert list_models(fake.host) == [{"name": "a", "chat": None, "thinking": False}]


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
    assert models == [{"name": "a", "chat": None, "thinking": False}]  # 목록은 유지하고 능력만 모름으로 둔다


def test_모델_내리기는_빈_messages와_keep_alive_0을_보내고_성공하면_unloaded(fake):
    assert unload_model(fake.host, "qwen3:8b") == UNLOADED
    assert fake.unloads == [{"model": "qwen3:8b", "messages": [], "keep_alive": 0, "stream": False}]
    assert fake.requests == []  # 일반 채팅 요청으로 세지 않는다
    assert fake.unload_paths == ["/api/chat"] and fake.bad_paths == []  # 실제 Ollama의 /api/chat 경로로 보냈다


def test_가짜_서버는_잘못된_endpoint에_성공으로_답하지_않는다(fake):
    """시험이 URL을 증명하려면 가짜 서버가 /api/chat·/api/show 밖의 경로를 받아 주면 안 된다."""
    import httpx

    body = {"model": "m", "messages": [], "keep_alive": 0, "stream": False}
    assert httpx.post(f"{fake.host}/wrong", json=body).status_code == 404
    assert fake.bad_paths == ["/wrong"] and fake.unloads == []


def test_설치돼_있지_않은_모델은_not_installed(fake):
    fake.unload_status = 404
    assert unload_model(fake.host, "nope") == NOT_INSTALLED


def test_서버_오류_이상한_본문_서버_없음은_failed(fake):
    fake.unload_status = 500
    assert unload_model(fake.host, "m") == FAILED
    fake.unload_status = 200
    for body in ({"error": "unload failed"}, {"model": "m"}, {"done": False}, ["done"], 5):
        fake.unload_body = body
        assert unload_model(fake.host, "m") == FAILED, body  # HTTP 200이어도 본문이 성공이 아니면 실패다
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    assert unload_model(f"http://127.0.0.1:{port}", "m", timeout=1) == FAILED


def test_헤더를_조금씩_흘리는_응답도_전체_시간_안에_포기한다(fake):
    """연산별 timeout은 헤더 trickle을 못 끊는다. /api/tags, /api/show, 모델 내리기 모두 전체 시간으로 끊어야 한다."""
    from fake_ollama import trickle_headers

    fake.tags = ["a"]
    fake.get_script = lambda h: trickle_headers(h)
    t0 = time.perf_counter()
    assert list_models(fake.host, timeout=1.0) == []
    assert time.perf_counter() - t0 < 3

    fake.get_script = None
    fake.show_script = lambda h: trickle_headers(h)
    t0 = time.perf_counter()
    assert list_models(fake.host, timeout=1.5) == [{"name": "a", "chat": None, "thinking": False}]
    assert time.perf_counter() - t0 < 4

    fake.unload_script = lambda h: trickle_headers(h)
    t0 = time.perf_counter()
    assert unload_model(fake.host, "a", timeout=1.0) == FAILED
    assert time.perf_counter() - t0 < 3


def test_tags에_잘못된_항목이_섞여도_정상_모델은_모두_보인다(fake):
    fake.tags = ["A", {}, None, {"name": 5}, {"name": ""}, "B"]
    fake.capabilities_by_model = {"A": ["completion"], "B": ["completion", "thinking"]}
    assert [m["name"] for m in list_models(fake.host)] == ["A", "B"]


def test_models가_리스트가_아니면_빈_목록(fake):
    fake.get_script = lambda h: send_lines(h, [{"models": "oops"}])
    assert list_models(fake.host) == []


def test_너무_깊게_중첩된_JSON도_예외_없이_실패로_처리한다(fake):
    fake.unload_script = lambda h: send_lines(h, [b"[" * 5000 + b"]" * 5000 + chr(10).encode()])
    assert unload_model(fake.host, "m") == FAILED
    fake.show_script = lambda h: send_lines(h, [b"[" * 5000 + b"]" * 5000 + chr(10).encode()])
    fake.tags = ["a"]
    assert list_models(fake.host) == [{"name": "a", "chat": None, "thinking": False}]
