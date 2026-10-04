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
