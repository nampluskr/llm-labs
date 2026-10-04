import pytest

from fake_ollama import FakeOllama


@pytest.fixture
def fake():
    f = FakeOllama()
    yield f
    f.close()
