import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
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
    """읽기 전용 호출(version 요청·list·ps)만 가진다. 적재 호출(generate·chat)을 하면 AttributeError가 난다."""

    def __init__(self, models=(), loaded=(), version_response=None, list_error=None, ps_error=None):
        self._models, self._loaded = list(models), list(loaded)
        self._version_response = version_response or version_ok()
        self._list_error, self._ps_error = list_error, ps_error

    def _request_raw(self, method, path, **kw):
        assert (method, path) == ("GET", "/api/version")
        if isinstance(self._version_response, Exception):
            raise self._version_response
        return self._version_response

    def list(self):
        if self._list_error:
            raise self._list_error
        return SimpleNamespace(models=self._models)

    def ps(self):
        if self._ps_error:
            raise self._ps_error
        return SimpleNamespace(models=self._loaded)


def patch_client(monkeypatch, **kw):
    monkeypatch.setattr(cli.ollama, "Client", lambda **ckw: FakeClient(**kw))


def run(capsys, *argv):
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def text_status(out):
    """화면 출력에서 항목별 통과/실패를 {이름: bool}로 읽는다."""
    return {m.group(2): m.group(1) == "통과" for m in re.finditer(r"^\[(통과|실패)\] ([^:]+):", out, re.M)}


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


def test_all_pass_text(monkeypatch, capsys):
    patch_client(
        monkeypatch,
        models=[model("qwen3:4b", 2_500_000_000), model("bge-m3:latest", 1_200_000_000)],
        loaded=[model("qwen3:4b", 5_000_000_000, 5_000_000_000)],
    )
    code, out, err = run(capsys)
    assert code == 0 and err == ""
    assert text_status(out) == {"서버 연결": True, "버전": True, "받은 모델": True, "적재된 모델": True}
    assert "[통과] 버전: 0.35.1" in out
    assert "  qwen3:4b  2.5GB" in out and "  bge-m3:latest  1.2GB" in out
    assert "  qwen3:4b  5.0GB  100% GPU" in out
    assert out.rstrip().endswith("결과: 통과 (4/4)")


def test_all_pass_json(monkeypatch, capsys):
    patch_client(
        monkeypatch,
        models=[model("qwen3:4b", 2_500_000_000)],
        loaded=[model("qwen3:4b", 5_000_000_000, 5_000_000_000)],
    )
    code, out, err = run(capsys, "--json")
    assert code == 0 and err == ""
    result = json.loads(out)
    assert (result["ok"], result["passed"], result["total"]) == (True, 4, 4)
    by_name = {c["name"]: c for c in result["checks"]}
    assert list(by_name) == ["서버 연결", "버전", "받은 모델", "적재된 모델"]
    assert by_name["버전"]["data"] == "0.35.1"
    assert by_name["받은 모델"]["data"] == [{"name": "qwen3:4b", "size": 2_500_000_000}]
    assert by_name["적재된 모델"]["data"] == [
        {"name": "qwen3:4b", "size": 5_000_000_000, "processor": "100% GPU"}
    ]


def test_json_is_ascii_safe(monkeypatch, capsys):
    patch_client(monkeypatch, models=[model("qwen3:4b", 1)])
    _, out, _ = run(capsys, "--json")
    assert out.isascii()


def test_nothing_loaded_is_pass(monkeypatch, capsys):
    patch_client(monkeypatch, models=[model("qwen3:4b", 2_500_000_000)])
    code, out, _ = run(capsys)
    assert code == 0
    assert "[통과] 적재된 모델: 없음" in out


def test_no_models_fails_but_others_still_reported(monkeypatch, capsys):
    patch_client(monkeypatch)
    code, out, err = run(capsys)
    assert code == 1
    assert text_status(out) == {"서버 연결": True, "버전": True, "받은 모델": False, "적재된 모델": True}
    assert "[실패] 받은 모델: 받은 모델이 없다" in out
    assert out.rstrip().endswith("결과: 실패 (3/4 통과)")
    assert err == ""


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
    ],
    ids=["not-json", "no-version-key", "null", "list", "version-null", "version-empty", "version-object"],
)
def test_bad_version_fails_only_version(monkeypatch, capsys, version_response):
    patch_client(monkeypatch, models=[model("qwen3:4b", 1)], version_response=version_response)
    code, out, err = run(capsys)
    assert code == 1
    assert text_status(out) == {"서버 연결": True, "버전": False, "받은 모델": True, "적재된 모델": True}
    assert "Traceback" not in out + err
    assert out.rstrip().endswith("결과: 실패 (3/4 통과)")


@pytest.mark.parametrize(
    "error", [cli.ollama.ResponseError("", 500), TimeoutError("timed out"), ConnectionError("refused")]
)
def test_version_request_error_fails_connection_and_version(monkeypatch, capsys, error):
    patch_client(monkeypatch, models=[model("qwen3:4b", 1)], version_response=error)
    code, out, err = run(capsys)
    assert code == 1
    assert text_status(out) == {"서버 연결": False, "버전": False, "받은 모델": True, "적재된 모델": True}
    assert type(error).__name__ in out
    assert "오류" in err


def test_models_error_fails_only_models(monkeypatch, capsys):
    patch_client(monkeypatch, list_error=TypeError("boom"))
    code, out, _ = run(capsys)
    assert code == 1
    assert text_status(out) == {"서버 연결": True, "버전": True, "받은 모델": False, "적재된 모델": True}
    assert "TypeError: boom" in out


def test_loaded_error_fails_only_loaded(monkeypatch, capsys):
    patch_client(monkeypatch, models=[model("qwen3:4b", 1)], ps_error=TimeoutError("timed out"))
    code, out, _ = run(capsys)
    assert code == 1
    assert text_status(out) == {"서버 연결": True, "버전": True, "받은 모델": True, "적재된 모델": False}


def test_loaded_model_without_memory_fields(monkeypatch, capsys):
    patch_client(monkeypatch, models=[model("test", 1)], loaded=[model("test", 1_000_000_000, None)])
    code, out, _ = run(capsys)
    assert code == 0
    assert "알 수 없음" in out and "100% CPU" not in out


def test_text_and_json_report_same_results(monkeypatch, capsys):
    patch_client(monkeypatch, version_response=Response({}), list_error=TypeError("boom"))
    _, text_out, _ = run(capsys)
    _, json_out, _ = run(capsys, "--json")
    result = json.loads(json_out)
    assert {c["name"]: c["ok"] for c in result["checks"]} == text_status(text_out)
    assert f"({result['passed']}/{result['total']} 통과)" in text_out


def test_server_down(monkeypatch, capsys):
    monkeypatch.setattr(cli, "HOST", "http://127.0.0.1:1")
    code, out, err = run(capsys)
    assert code == 1
    assert text_status(out) == {"서버 연결": False, "버전": False, "받은 모델": False, "적재된 모델": False}
    assert out.rstrip().endswith("결과: 실패 (0/4 통과)")
    assert "오류" in err and "127.0.0.1:1" in err


def test_server_down_json_is_still_valid_json(monkeypatch, capsys):
    monkeypatch.setattr(cli, "HOST", "http://127.0.0.1:1")
    code, out, err = run(capsys, "--json")
    assert code == 1
    result = json.loads(out)
    assert (result["ok"], result["passed"], result["total"]) == (False, 0, 4)
    assert "오류" in err


def test_unknown_option_exits_2(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--nope"])
    assert e.value.code == 2


def test_does_not_follow_redirects(monkeypatch, capsys):
    """리다이렉트를 따라가면 허용한 세 엔드포인트(D-3) 밖으로 요청이 나간다."""
    requested = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requested.append(self.path)
            if self.path == "/api/version":
                self.send_response(302)
                self.send_header("Location", "/elsewhere")
                self.end_headers()
            else:
                body = b'{"version":"0.1.0","models":[]}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setattr(cli, "HOST", f"http://127.0.0.1:{server.server_address[1]}")
        code, out, err = run(capsys)
    finally:
        server.shutdown()
        server.server_close()
    assert code == 1
    assert set(requested) <= {"/api/version", "/api/tags", "/api/ps"}
    assert text_status(out)["서버 연결"] is False
