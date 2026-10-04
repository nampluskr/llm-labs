"""화면과 분리된 대화 세션: 문맥 관리(직전 10턴), 작업 스레드 스트리밍, 중단.

화면(pywebview)은 emit 콜백으로 이벤트를 받기만 한다. 이 모듈은 화면을 모른다.

emit하는 이벤트(dict):
  {"type": "token", "text": str}
  {"type": "done", "eval_count": int, "tok_s": float}   정상 종료
  {"type": "stopped"}                                    사용자가 중단
  {"type": "error", "kind": str, "message": str}         실패
세 종료 이벤트(done·stopped·error) 중 정확히 하나가 마지막에 온다.
종료 이벤트를 emit하기 전에 대화 기록 갱신과 busy 해제를 끝낸다. 화면이 종료 이벤트를 받고
바로 다음 질문을 보내도 거절되지 않는다.
"""

import threading

from .clients import Done, Error, Token
from .defaults import SYSTEM_PROMPT

MAX_TURNS = 10  # 문맥으로 보내는 직전 대화 턴 수. 한 턴 = 질문 하나 + 답 하나


class ChatSession:
    def __init__(self, client, model, options, emit, system_prompt=SYSTEM_PROMPT):
        self._client, self._model, self._options = client, model, options
        self._emit_cb = emit
        self._system = system_prompt
        self._turns: list[tuple[str, str]] = []  # 끝난 턴만: (질문, 답)
        self._lock = threading.Lock()
        self._busy = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._idle = threading.Event()  # 질문을 처리 중이 아니면(종료 이벤트 emit까지 끝났으면) 켜져 있다
        self._idle.set()

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    def messages_for(self, text: str) -> list[dict]:
        """이번 질문과 함께 보낼 메시지: 시스템 + 직전 MAX_TURNS턴 + 질문."""
        messages = [{"role": "system", "content": self._system}]
        for question, answer in self._turns[-MAX_TURNS:]:
            messages.append({"role": "user", "content": question})
            messages.append({"role": "assistant", "content": answer})
        messages.append({"role": "user", "content": text})
        return messages

    def send(self, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            return {"ok": False, "reason": "empty"}
        with self._lock:
            if self._busy:
                return {"ok": False, "reason": "busy"}
            self._busy = True
            self._idle.clear()
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, args=(text,), daemon=True)
        self._thread.start()
        return {"ok": True}

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: float | None = None) -> bool:
        """처리 중인 질문이 종료 이벤트 emit까지 끝나기를 기다린다. 시간 안에 끝나면 True."""
        return self._idle.wait(timeout)

    def _emit(self, event: dict) -> None:
        try:
            self._emit_cb(event)
        except Exception:
            self._stop.set()  # 화면이 닫힌 것으로 보고 더 보내지 않는다

    def _run(self, text: str) -> None:
        reply: list[str] = []
        final: dict | None = None
        gen = None
        try:
            gen = self._client.stream(self.messages_for(text), model=self._model, options=self._options)
            for event in gen:
                if self._stop.is_set():
                    break
                if isinstance(event, Token):
                    reply.append(event.text)
                    self._emit({"type": "token", "text": event.text})
                elif isinstance(event, Done):
                    final = {"type": "done", "eval_count": event.eval_count, "tok_s": round(event.tokens_per_second, 1)}
                    break
                elif isinstance(event, Error):
                    final = {"type": "error", "kind": event.kind, "message": event.message}
                    break
        except Exception as e:  # 호출 층이 약속을 어겨 예외를 내도 busy가 남지 않게
            final = {"type": "error", "kind": "other", "message": f"호출 층 예외: {e!r}"}
        finally:
            if gen is not None:
                gen.close()
        answer = "".join(reply)
        if final is None:  # 사용자가 중단했거나 스트림이 종료 이벤트 없이 끝남
            final = {"type": "stopped"} if self._stop.is_set() else {"type": "error", "kind": "other", "message": "응답이 종료 이벤트 없이 끝났다"}
        with self._lock:
            if final["type"] == "done" or (final["type"] == "stopped" and answer):
                self._turns.append((text, answer))  # 사용자가 본 대로 남긴다(중단이면 받은 데까지)
            self._busy = False
        try:
            self._emit(final)
        finally:
            with self._lock:
                if self._thread is threading.current_thread():  # emit 안에서 다음 질문이 시작됐으면 그쪽이 idle을 켠다
                    self._idle.set()
