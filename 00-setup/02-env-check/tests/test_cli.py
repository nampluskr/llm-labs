from types import SimpleNamespace

import pytest

from env_check import cli


def model(name, size, size_vram=0):
    return SimpleNamespace(model=name, size=size, size_vram=size_vram)


class FakeClient:
    """읽기 전용 호출(list·ps)만 가진다. 적재 호출(generate·chat)을 하면 AttributeError가 난다."""

    def __init__(self, models, loaded):
        self._models, self._loaded = models, loaded

    def list(self):
        return SimpleNamespace(models=self._models)

    def ps(self):
        return SimpleNamespace(models=self._loaded)


@pytest.mark.parametrize(
    "size, vram, expected",
    [
        (1000, 1000, "100% GPU"),
        (1000, 1200, "100% GPU"),
        (1000, 0, "100% CPU"),
        (1000, 750, "25%/75% CPU/GPU"),
        (0, 0, "알 수 없음"),
    ],
)
def test_processor_label(size, vram, expected):
    assert cli.processor_label(size, vram) == expected


def patch_server(monkeypatch, models, loaded):
    monkeypatch.setattr(cli, "get_version", lambda host: "0.35.1")
    monkeypatch.setattr(cli.ollama, "Client", lambda **kw: FakeClient(models, loaded))


def test_main_prints_models_and_loaded(monkeypatch, capsys):
    patch_server(
        monkeypatch,
        [model("qwen3:4b", 2_500_000_000), model("bge-m3:latest", 1_200_000_000)],
        [model("qwen3:4b", 5_000_000_000, 5_000_000_000)],
    )
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "0.35.1" in out
    assert "qwen3:4b" in out and "bge-m3:latest" in out
    assert "적재된 모델 (1개)" in out and "100% GPU" in out


def test_main_nothing_loaded(monkeypatch, capsys):
    patch_server(monkeypatch, [model("qwen3:4b", 2_500_000_000)], [])
    assert cli.main([]) == 0
    assert "적재된 모델 (0개): 없음" in capsys.readouterr().out


def test_main_no_models(monkeypatch, capsys):
    patch_server(monkeypatch, [], [])
    assert cli.main([]) == 0
    assert "받은 모델 (0개)" in capsys.readouterr().out


def test_main_server_down(monkeypatch, capsys):
    monkeypatch.setattr(cli, "HOST", "http://127.0.0.1:1")
    assert cli.main([]) == 1
    captured = capsys.readouterr()
    assert "오류" in captured.err and "127.0.0.1:1" in captured.err
    assert captured.out == ""
