"""pywebview 창 하나를 호출 층에 붙인다. 화면은 하나고 호출 층만 앱마다 다르다(D-3)."""

import argparse
import json
import threading
from pathlib import Path

import webview

from . import conversation
from .capabilities import show_capabilities
from .defaults import DEFAULT_HOST, DEFAULT_MODEL, DEFAULT_OPTIONS
from .models import FAILED, NOT_INSTALLED, UNLOADED, list_models, unload_model
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
        self._state_lock = threading.Lock()  # 전환 표시와 질문 시작을 서로 배타적으로 만든다(짧게만 쥔다)
        self._switching = False  # 모델 전환 중(이전 모델 내리기 포함)에는 질문을 받지 않는다
        self._file_busy = False  # 대화 저장·열기 중(대화상자가 열려 있는 동안 포함)에는 질문과 모델 전환을 받지 않는다
        self._pick_path = self._dialog  # (mode) -> 경로 또는 None. 시험에서는 대화상자 대신 경로를 돌려주는 함수로 바꾼다
        self._worker_wait = 3.0  # 전환할 때 중단된 이전 요청의 작업 스레드가 끝나기를 기다리는 시간(초)
        # 설치된 모델 전체(/api/tags). 현재 모델이 목록에 없으면(미설치이거나 목록을 못 받음) 맨 앞에 둔다
        self._catalog = list_models(client.host)
        entry = next((m for m in self._catalog if m["name"] == model), None)
        if entry is None:
            caps = show_capabilities(client.host, model)
            entry = {"name": model, "chat": None if caps is None else "completion" in caps, "thinking": caps is not None and "thinking" in caps}
            self._catalog.insert(0, entry)
        # 사고 과정은 모델이 지원할 때만 켠다. 지원하지 않는 모델에 think=True를 보내면 Ollama가 400을 낸다(D-10)
        self._session = ChatSession(client, model, options, self._emit, think=entry["thinking"])

    def _emit(self, event: dict) -> None:
        # json.dumps의 기본값(ensure_ascii=True)이라 U+2028 같은 문자도 이스케이프돼 나가 JS 문자열로 안전하다
        self._window.evaluate_js("window.onChatEvent(" + json.dumps(event) + ")")

    def send(self, text):
        # 이전 모델을 내리는 동안 새 모델의 질문이 시작되면 두 모델이 VRAM에서 겹친다(D-6이 막으려는 상황).
        # 전환 표시와 질문 시작이 같은 락 안이라 둘 중 하나만 성립한다: 질문이 먼저면 전환이 거절되고, 전환이 먼저면 질문이 거절된다
        with self._state_lock:
            if self._switching:
                return {"ok": False, "reason": "switching"}
            if self._file_busy:
                return {"ok": False, "reason": "file"}
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
        if entry["chat"] is False:
            return {"ok": False, "reason": "not_chat", "message": "채팅할 수 없는 모델이다(임베딩 모델)"}
        with self._config_lock:
            previous = self._session.model
            if name == previous:
                return {"ok": True, "unloaded": None, "info": self.info()}
            if entry["chat"] is None:
                # 목록을 읽을 때 확인하지 못한 모델은 고르는 순간 다시 확인한다. 그래도 모르면 바꾸지 않는다
                caps = show_capabilities(self._client.host, name)
                if caps is None:
                    return {"ok": False, "reason": "unknown_capabilities", "message": "모델 정보를 확인하지 못해 바꾸지 않았다"}
                entry["chat"], entry["thinking"] = "completion" in caps, "thinking" in caps
                if not entry["chat"]:
                    return {"ok": False, "reason": "not_chat", "message": "채팅할 수 없는 모델이다(임베딩 모델)"}
            previous_think = self._session.think
            with self._state_lock:
                if self._file_busy:
                    return {"ok": False, "reason": "file_busy", "message": "파일을 저장하거나 여는 중에는 바꿀 수 없다"}
                result = self._session.configure(model=name, think=entry["thinking"])
                if not result["ok"]:
                    return {**result, "message": "답변 중에는 바꿀 수 없다"}
                self._switching = True  # 내리기가 끝날 때까지 질문을 받지 않는다
            try:
                # 중단된 이전 요청이 아직 돌고 있으면 잠깐 기다린다. 내린 뒤에 그 요청이 모델을 다시 올리지 않게 한다.
                # 끝나지 않았다면 그 요청이 언제 모델을 다시 올릴지 알 수 없으므로 내리지 않고 전환도 하지 않는다
                if not self._session.wait_workers(self._worker_wait):
                    self._session.configure(model=previous, think=previous_think)
                    return {"ok": False, "reason": "previous_request_pending", "message": "이전 답변 요청이 아직 끝나지 않아 바꾸지 않았다. 잠시 뒤 다시 시도하세요"}
                # 이전 모델을 바로 내려 두 모델이 VRAM에 겹치지 않게 한다(D-6)
                try:
                    outcome = unload_model(self._client.host, previous)
                except Exception:  # 내리기 결과를 알 수 없으면 실패로 본다
                    outcome = FAILED
                if outcome == FAILED:
                    # 이전 모델이 남아 있을 수 있다. 새 모델을 올리면 겹치므로 전환을 되돌린다
                    self._session.configure(model=previous, think=previous_think)
                    return {"ok": False, "reason": "unload_failed", "message": "이전 모델을 내리지 못해 바꾸지 않았다. 다시 시도하세요"}
            finally:
                with self._state_lock:
                    self._switching = False
            # 설치돼 있지 않은 모델(404)은 내릴 것이 없다
            return {"ok": True, "unloaded": True if outcome == UNLOADED else None, "info": self.info()}

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

    def _dialog(self, mode):
        """파일 대화상자. 취소하면 None."""
        if mode == "save":
            result = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename="chat.json", file_types=("JSON (*.json)",))
        else:
            result = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=("JSON (*.json)",))
        if not result:
            return None
        return result if isinstance(result, str) else result[0]

    def _file_op(self, fn):
        """저장·열기를 한 번에 하나씩, 모델 전환과 겹치지 않게 돌린다. 도는 동안(대화상자가 열려 있는 동안 포함) 질문과 모델 전환은 거절된다."""
        with self._state_lock:
            if self._switching:
                return {"ok": False, "reason": "switching", "message": "모델을 바꾸는 중에는 저장하거나 열 수 없다"}
            if self._file_busy:
                return {"ok": False, "reason": "file_busy", "message": "다른 저장·열기를 처리하는 중이다"}
            self._file_busy = True
        try:
            return fn()
        finally:
            with self._state_lock:
                self._file_busy = False

    def save_chat(self):
        """대화상자로 경로를 물어 지금까지 끝난 대화를 JSON 파일로 저장한다. 답변 중에는 거절한다."""
        return self._file_op(self._save_flow)

    def _save_flow(self):
        path = self._pick_path("save")
        if not path:
            return {"ok": False, "reason": "cancelled", "message": "저장을 취소했다"}
        return self._write_chat(path)

    def _save_to(self, path):
        """경로를 알고 있을 때의 저장. 시험에서 대화상자 없이 쓴다. 밑줄로 시작해 JS에는 공개하지 않는다(임의 경로를 받지 않는다)."""
        return self._file_op(lambda: self._write_chat(path))

    def _write_chat(self, path):
        messages = self._session.export_messages()  # 대화상자를 여는 사이에 바뀐 것까지 담도록 경로를 받은 뒤에 읽는다
        if messages is None:
            return {"ok": False, "reason": "busy", "message": "답변 중에는 저장할 수 없다"}
        try:
            conversation.save_file(path, messages, self._session.model)
        except conversation.ConversationError as e:
            return {"ok": False, "reason": "error", "message": str(e)}
        return {"ok": True, "path": str(path), "count": len(messages)}

    def load_chat(self):
        """대화상자로 경로를 물어 JSON 파일의 대화로 현재 대화를 통째로 바꾼다. 파일이 올바르지 않으면 현재 대화는 그대로다. 답변 중에는 거절한다."""
        return self._file_op(self._load_flow)

    def _load_flow(self):
        path = self._pick_path("open")
        if not path:
            return {"ok": False, "reason": "cancelled", "message": "열기를 취소했다"}
        return self._read_chat(path)

    def _load_from(self, path):
        """경로를 알고 있을 때의 열기. 시험에서 대화상자 없이 쓴다. 밑줄로 시작해 JS에는 공개하지 않는다."""
        return self._file_op(lambda: self._read_chat(path))

    def _read_chat(self, path):
        try:
            messages = conversation.load_file(path)  # 먼저 검증한다. 실패하면 아래 복원까지 가지 않는다
        except conversation.ConversationError as e:
            return {"ok": False, "reason": "error", "message": str(e)}
        result = self._session.restore(messages)
        if not result["ok"]:
            return {**result, "message": "답변 중에는 열 수 없다"}
        return {"ok": True, "path": str(path), "count": len(messages), "messages": messages}

    def history(self):
        """지금 서버가 가진 대화(끝난 턴의 질문·답)와 파일 작업 중인지. 저장·열기 응답이 화면에 도착하지 못했을 때 화면을 맞추는 데 쓴다.
        답변 중이면 messages는 None이다."""
        return {"messages": self._session.export_messages(), "file_busy": self._file_busy}

    def info(self):
        options = self._session.options
        return {
            "client": self._client.name,
            "model": self._session.model,
            "num_ctx": options.get("num_ctx"),
            "temperature": options.get("temperature"),
            "think": self._session.think,
            # 전환 중이면 모델·think는 임시로 적용된 값일 수 있다(내리기에 실패하면 되돌려진다). 화면은 끝날 때까지 기다린다
            "switching": self._switching,
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
