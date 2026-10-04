import socket

from local_chat.capabilities import supports_thinking


def test_thinking을_지원하는_모델은_True(fake):
    fake.capabilities = ["completion", "tools", "thinking"]
    assert supports_thinking(fake.host, "qwen3:8b") is True
    assert fake.show_requests == [{"model": "qwen3:8b"}]


def test_지원하지_않는_모델은_False(fake):
    fake.capabilities = ["completion"]
    assert supports_thinking(fake.host, "exaone3.5:7.8b") is False


def test_서버가_없거나_오류면_False():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert supports_thinking(f"http://127.0.0.1:{port}", "m", timeout=1) is False


def test_capabilities_필드가_없거나_이상해도_False(fake):
    for bad in (None, "thinking", 5):
        fake.capabilities = bad
        assert supports_thinking(fake.host, "m") is False, bad


def test_응답을_조금씩_흘려도_전체_시간_안에_포기한다(fake):
    """각 청크가 읽기 시간 안에 도착해도 전체가 오래 걸리면 False로 돌아와 창 열기를 막지 않는다."""
    import time

    from fake_ollama import send_headers

    def trickle(h):
        send_headers(h)
        try:
            for _ in range(40):
                h.wfile.write(b" ")
                h.wfile.flush()
                time.sleep(0.25)
        except OSError:
            pass

    fake.show_script = trickle
    t0 = time.perf_counter()
    assert supports_thinking(fake.host, "m", timeout=1.0) is False
    assert time.perf_counter() - t0 < 3


def test_너무_큰_응답은_False(fake):
    from fake_ollama import send_headers

    def huge(h):
        send_headers(h)
        try:
            h.wfile.write(b" " * 2_000_000)
            h.wfile.flush()
        except OSError:
            pass

    fake.show_script = huge
    assert supports_thinking(fake.host, "m", timeout=3.0) is False
