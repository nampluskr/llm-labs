from types import SimpleNamespace

import pytest

from env_check import cli


def model(name, size, size_vram=0):
    return SimpleNamespace(model=name, size=size, size_vram=size_vram)


class Response:
    def __init__(self, data=None, body_error=None):
        self._data, self._body_error = data, body_error

    def json(self):
        if self._body_error:
            raise self._body_error
        return self._data


def version_ok(version="0.35.1"):
    return Response({"version": version})


class FakeClient:
    """읽기 전용 호출(list·ps)만 가진다. 적재 호출(generate·chat)을 하면 AttributeError가 난다."""

    def __init__(self, models, loaded, version_response=None):
        self._models, self._loaded = models, loaded
        self._version_response = version_response or version_ok()

    def _request_raw(self, method, path, **kw):
        assert (method, path) == ("GET", "/api/version")
        if isinstance(self._version_response, Exception):
            raise self._version_response
        return self._version_response

    def list(self):
        return SimpleNamespace(models=self._models)

    def ps(self):
        return SimpleNamespace(models=self._loaded)


@pytest.mark.parametrize(
    "size, vram, expected",
    [
        (1000, 1000, "100% GPU"),
        (1000, 0, "100% CPU"),
        (1000, 750, "25%/75% CPU/GPU"),
        (1000, 755, "25%/75% CPU/GPU"),
        (1000, 995, "1%/99% CPU/GPU"),
        (1000, 1200, "알 수 없음"),
        (0, 0, "100% CPU"),
        (0, 5, "알 수 없음"),
        (1000, None, "알 수 없음"),
        (None, 500, "알 수 없음"),
        (None, None, "알 수 없음"),
    ],
)
def test_processor_label(size, vram, expected):
    assert cli.processor_label(size, vram) == expected


def patch_server(monkeypatch, models, loaded, version_response=None):
    monkeypatch.setattr(
        cli.ollama, "Client", lambda **kw: FakeClient(models, loaded, version_response)
    )


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


def test_get_version_parses_response():
    assert cli.get_version(FakeClient([], [])) == "0.35.1"


@pytest.mark.parametrize(
    "version_response",
    [
        Response(body_error=ValueError("Expecting value")),
        Response({}),
        Response(None),
        Response([]),
        Response({"version": None}),
        Response({"version": ""}),
        Response({"version": {"a": 1}}),
        cli.ollama.ResponseError("", 500),
    ],
    ids=["not-json", "no-version-key", "null", "list", "version-null", "version-empty", "version-object", "http-500"],
)
def test_main_unexpected_version_response(monkeypatch, capsys, version_response):
    patch_server(monkeypatch, [], [], version_response)
    assert cli.main([]) == 1
    captured = capsys.readouterr()
    assert "오류" in captured.err and "Traceback" not in captured.err
    assert captured.out == ""


def test_main_timeout(monkeypatch, capsys):
    patch_server(monkeypatch, [], [], TimeoutError("timed out"))
    assert cli.main([]) == 1
    assert "TimeoutError" in capsys.readouterr().err


def test_main_prints_connection_and_version(monkeypatch, capsys):
    patch_server(monkeypatch, [], [])
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "연결됨" in out and "버전: 0.35.1" in out


def test_main_loaded_model_without_memory_fields(monkeypatch, capsys):
    patch_server(monkeypatch, [], [model("test", 1_000_000_000, None)])
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "알 수 없음" in out and "100% CPU" not in out
