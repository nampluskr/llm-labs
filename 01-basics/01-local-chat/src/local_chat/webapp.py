"""pywebview 창 하나를 호출 층에 붙인다. 화면은 하나고 호출 층만 앱마다 다르다(D-3)."""

import argparse
import json
from pathlib import Path

import webview

from .capabilities import supports_thinking
from .defaults import DEFAULT_HOST, DEFAULT_MODEL, DEFAULT_OPTIONS
from .session import ChatSession

INDEX = Path(__file__).parent / "ui" / "index.html"


class Api:
    """JS에서 window.pywebview.api.*로 부르는 메서드만 공개 이름으로 둔다.
    pywebview는 공개 속성을 훑어 JS에 노출하므로 내부 상태는 밑줄로 시작한다."""

    def __init__(self, client, model, options):
        self._client, self._model, self._options = client, model, options
        self._window = None
        # 사고 과정은 모델이 지원할 때만 켠다. 지원하지 않는 모델에 think=True를 보내면 Ollama가 400을 낸다(D-10)
        self._think = supports_thinking(client.host, model)
        self._session = ChatSession(client, model, options, self._emit, think=self._think)

    def _emit(self, event: dict) -> None:
        # ensure_ascii=True라 U+2028 같은 문자도 \uXXXX로 나가 JS 문자열로 안전하다
        self._window.evaluate_js("window.onChatEvent(" + json.dumps(event) + ")")

    def send(self, text):
        return self._session.send(text)

    def stop(self):
        self._session.stop()

    def info(self):
        return {
            "client": self._client.name,
            "model": self._model,
            "num_ctx": self._options.get("num_ctx"),
            "temperature": self._options.get("temperature"),
            "think": self._think,
        }


def build(client, model=DEFAULT_MODEL, options=None, width=820, height=720):
    """창과 Api를 만든다(아직 start하지 않는다). 시험에서 start(func)로 창을 조작할 때도 쓴다."""
    api = Api(client, model, dict(options or DEFAULT_OPTIONS))
    window = webview.create_window(f"local-chat · {client.name}", url=str(INDEX), js_api=api, width=width, height=height)
    api._window = window
    window.events.closed += api._session.close  # 창을 닫으면 스트리밍 중단
    return window, api


def main(client_cls, argv=None) -> None:
    p = argparse.ArgumentParser(prog=f"local-chat-{client_cls.name}")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--model", default=DEFAULT_MODEL)
    args = p.parse_args(argv)
    build(client_cls(host=args.host), model=args.model)
    webview.start()
