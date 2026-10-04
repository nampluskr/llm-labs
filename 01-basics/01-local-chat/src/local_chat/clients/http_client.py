"""HTTP API 직접 호출: httpx로 POST /api/chat, 응답은 줄마다 JSON 하나(NDJSON)."""

import json

import httpx

from .events import CONNECTION, OTHER, Error, Message, Token, classify, make_done, make_timeout


class HttpClient:
    name = "http"

    def __init__(self, host: str = "http://localhost:11434", read_timeout: float = 300.0):
        self._host = host.rstrip("/")
        self._timeout = make_timeout(read_timeout)

    def stream(self, messages: list[Message], *, model: str, options: dict):
        body = {"model": model, "messages": messages, "stream": True, "think": False, "options": options}
        try:
            with httpx.stream("POST", f"{self._host}/api/chat", json=body, timeout=self._timeout) as r:
                if r.status_code >= 400:
                    r.read()
                    msg = _error_text(r)
                    yield Error(classify(r.status_code, msg), msg)
                    return
                for line in r.iter_lines():
                    if not line:
                        continue
                    d = json.loads(line)
                    if "error" in d:
                        yield Error(classify(None, str(d["error"])), str(d["error"]))
                        return
                    piece = d.get("message", {}).get("content")
                    if piece is not None and not isinstance(piece, str):
                        raise ValueError(f"message.content가 문자열이 아니다: {piece!r}")
                    if piece:
                        yield Token(piece)
                    if d.get("done"):
                        yield make_done(d.get("eval_count"), d.get("eval_duration"))
                        return
            yield Error(OTHER, "응답이 done 없이 끝났다")
        except httpx.TransportError as e:
            yield Error(CONNECTION, str(e) or type(e).__name__)
        except (ValueError, KeyError, AttributeError, TypeError) as e:
            yield Error(OTHER, f"응답을 해석하지 못했다: {e!r}")


def _error_text(r: httpx.Response) -> str:
    try:
        return str(r.json()["error"])
    except (ValueError, KeyError, TypeError):
        return r.text or f"HTTP {r.status_code}"
