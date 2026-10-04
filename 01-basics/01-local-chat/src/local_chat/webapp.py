"""pywebview 창 하나를 호출 층에 붙인다. 화면은 하나고 호출 층만 앱마다 다르다(D-3)."""

import argparse
import json
import threading
from pathlib import Path

import webview

from .capabilities import supports_thinking
from .defaults import DEFAULT_HOST, DEFAULT_MODEL, DEFAULT_OPTIONS
from .models import list_models, unload_model
from .options import validate_options
from .session import ChatSession

INDEX = Path(__file__).parent / "ui" / "index.html"


class Api:
    """JS에서 window.pywebview.api.*로 부르는 메서드만 공개 이름으로 둔다.
    pywebview는 공개 속성을 훑어 JS에 노출하므로 내부 상태는 밑줄로 시작한다."""

    def __init__(self, client, model, options):
        self._client = client
        self._window = None
        self._config_lock = threading.Lock()  # 모델 전환·옵션 변경을 한 번에 하나씩
        # 설치된 모델 전체(/api/tags). 현재 모델이 목록에 없으면(미설치이거나 목록을 못 받음) 맨 앞에 둔다
        self._catalog = list_models(client.host)
        entry = next((m for m in self._catalog if m["name"] == model), None)
        if entry is None:
            entry = {"name": model, "chat": True, "thinking": supports_thinking(client.host, model)}
            self._catalog.insert(0, entry)
        # 사고 과정은 모델이 지원할 때만 켠다. 지원하지 않는 모델에 think=True를 보내면 Ollama가 400을 낸다(D-10)
        self._session = ChatSession(client, model, options, self._emit, think=entry["thinking"])

    def _emit(self, event: dict) -> None:
        # json.dumps의 기본값(ensure_ascii=True)이라 U+2028 같은 문자도 이스케이프돼 나가 JS 문자열로 안전하다
        self._window.evaluate_js("window.onChatEvent(" + json.dumps(event) + ")")

    def send(self, text):
        return self._session.send(text)

    def stop(self):
        self._session.stop()

    def models(self):
        """드롭다운에 보일 모델 전체와 현재 모델."""
        return {"models": self._catalog, "current": self._session.model}

    def set_model(self, name):
        """다음 질문부터 쓸 모델을 바꾼다. 답변 중에는 거절한다. 바꾸면 이전 모델을 바로 내린다(D-6)."""
        entry = next((m for m in self._catalog if m["name"] == name), None) if isinstance(name, str) else None
        if entry is None:
            return {"ok": False, "reason": "unknown", "message": "목록에 없는 모델이다"}
        if not entry["chat"]:
            return {"ok": False, "reason": "not_chat", "message": "채팅할 수 없는 모델이다(임베딩 모델)"}
        with self._config_lock:
            previous = self._session.model
            if name == previous:
                return {"ok": True, "unloaded": None, "info": self.info()}
            result = self._session.configure(model=name, think=entry["thinking"])
            if not result["ok"]:
                return {**result, "message": "답변 중에는 바꿀 수 없다"}
            # 이전 모델을 바로 내려 두 모델이 VRAM에 겹치지 않게 한다. 실패해도 전환은 유지하고 알린다
            return {"ok": True, "unloaded": unload_model(self._client.host, previous), "info": self.info()}

    def set_options(self, num_ctx, temperature):
        """다음 질문부터 쓸 num_ctx·temperature를 바꾼다. 범위 밖 값과 답변 중에는 거절한다(고쳐서 받지 않는다)."""
        try:
            options = validate_options(num_ctx, temperature)
        except ValueError as e:
            return {"ok": False, "reason": "invalid", "message": str(e)}
        with self._config_lock:
            result = self._session.configure(options=options)
            if not result["ok"]:
                return {**result, "message": "답변 중에는 바꿀 수 없다"}
            return {"ok": True, "info": self.info()}

    def info(self):
        options = self._session.options
        return {
            "client": self._client.name,
            "model": self._session.model,
            "num_ctx": options.get("num_ctx"),
            "temperature": options.get("temperature"),
            "think": self._session.think,
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
