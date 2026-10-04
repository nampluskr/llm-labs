"""화면과 분리된 대화 세션: 문맥 관리(직전 10턴), 작업 스레드 스트리밍, 중단.

화면(pywebview)은 emit 콜백으로 이벤트를 받기만 한다. 이 모듈은 화면을 모른다.

emit하는 이벤트(dict):
  {"type": "thinking", "text": str}                      사고 과정 조각(think가 켜졌을 때만)
  {"type": "token", "text": str}
  {"type": "done", "eval_count": int, "tok_s": float}   정상 종료
  {"type": "stopped"}                                    사용자가 중단
  {"type": "error", "kind": str, "message": str}         실패
세 종료 이벤트(done·stopped·error) 중 정확히 하나가 마지막에 온다.
사고 과정은 화면에만 보이고 문맥에는 넣지 않는다(답만 대화 기록에 남는다).

동시성 규칙 (_emit_lock 하나가 이벤트 순서와 기록의 일관성을 지킨다)
  - 답(turn.reply)에는 emit이 성공한 토큰만 남는다(먼저 쌓고 실패하면 되돌린다). 사용자가 못 본 토큰은 문맥에 남지 않는다.
  - 토큰 emit, 기록 확정, 종료 이벤트 emit은 모두 _emit_lock 안에서 한다. 기록 확정과 종료
    이벤트 emit은 같은 락 구간이라, 확정 직후 새 질문이 받아져도 그 턴의 토큰은 이전 턴의
    종료 이벤트 뒤에 나간다.
  - 종료 이벤트 emit 전에 busy가 풀린다. 화면이 종료 이벤트를 받고 바로 다음 질문을 보내도
    거절되지 않는다(emit 콜백 안에서 send해도 된다).
  - 모델·옵션·think 설정(configure)은 답변 중에는 거절하고, 질문을 보내는 순간의 값이 그 턴에 고정된다.
  - 중단(stop)은 작업 스레드가 막혀 있어도(모델 적재 중, 서버 무응답) 즉시 효과가 난다.
    stop()이 직접 기록을 확정하고 stopped를 emit하며, 그 턴의 작업 스레드는 취소 표시가
    붙어 뒤에서 정리만 한다(이후 이벤트는 버려지고, 호출 층 제너레이터는 깨어나는 대로 닫힌다).
"""

import threading
import time

from .clients import Done, Error, Thinking, Token
from .defaults import SYSTEM_PROMPT

MAX_TURNS = 10  # 문맥으로 보내는 직전 대화 턴 수. 한 턴 = 질문 하나 + 답 하나


class _Turn:
    def __init__(self, text: str, model: str, options: dict, think: bool):
        self.text = text
        self.model, self.options, self.think = model, options, think  # 보내는 순간의 설정. 진행 중에는 바뀌지 않는다
        self.reply: list[str] = []  # 화면에 전달된 토큰만
        self.cancelled = threading.Event()  # stop()·emit 실패가 붙인다. 이후 이 턴의 emit은 버려진다
        self.finalized = False  # 기록 확정과 busy 해제를 한 번만 하기 위한 표시


class ChatSession:
    def __init__(self, client, model, options, emit, system_prompt=SYSTEM_PROMPT, think=False):
        self._client, self._model, self._options, self._think = client, model, dict(options), think
        self._emit_cb = emit
        self._system = system_prompt
        self._turns: list[tuple[str, str]] = []  # 끝난 턴만: (질문, 답)
        self._lock = threading.Lock()  # 기록·busy·현재 턴. emit 중에 오래 쥐지 않는다
        self._emit_lock = threading.RLock()  # 이벤트 순서. emit 콜백이 같은 스레드에서 stop()을 불러도 막히지 않게 RLock
        self._busy = False
        self._turn: _Turn | None = None
        self._idle = threading.Event()  # 질문을 처리 중이 아니면(종료 이벤트 emit까지 끝났으면) 켜져 있다
        self._idle.set()
        self._closed = False
        self._workers: set[threading.Thread] = set()  # 아직 끝나지 않은 작업 스레드(중단된 턴의 것 포함)

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    @property
    def model(self) -> str:
        return self._model

    @property
    def options(self) -> dict:
        return dict(self._options)

    @property
    def think(self) -> bool:
        return self._think

    def export_messages(self) -> list[dict] | None:
        """끝난 턴의 질문·답을 messages 배열(user, assistant 번갈아)로 돌려준다. 답변 중이면 None(진행 중인 턴은 저장하지 않는다)."""
        with self._lock:
            if self._busy:
                return None
            messages = []
            for question, answer in self._turns:
                messages.append({"role": "user", "content": question})
                messages.append({"role": "assistant", "content": answer})
            return messages

    def restore(self, messages: list[dict]) -> dict:
        """대화를 messages(검증된 user, assistant 쌍)로 통째로 바꾼다. 답변 중에는 거절한다. 다음 질문의 문맥은 이 기록의 직전 10턴이다."""
        turns = [(messages[i]["content"], messages[i + 1]["content"]) for i in range(0, len(messages), 2)]
        with self._lock:
            if self._busy:
                return {"ok": False, "reason": "busy"}
            self._turns = turns
        return {"ok": True}

    def configure(self, model: str | None = None, options: dict | None = None, think: bool | None = None) -> dict:
        """다음 질문부터 쓸 설정을 바꾼다. 답변 중에는 거절한다(진행 중인 답의 모델·옵션이 바뀌지 않게)."""
        with self._lock:
            if self._busy:
                return {"ok": False, "reason": "busy"}
            if model is not None:
                self._model = model
            if options is not None:
                self._options = dict(options)
            if think is not None:
                self._think = think
        return {"ok": True}

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
            if self._busy or self._closed:
                return {"ok": False, "reason": "busy"}
            self._busy = True
            self._idle.clear()
            turn = self._turn = _Turn(text, self._model, dict(self._options), self._think)
            messages = self.messages_for(text)  # 문맥은 보내는 순간에 확정한다
            worker = threading.Thread(target=self._run, args=(turn, messages), daemon=True)
            self._workers.add(worker)
        worker.start()
        return {"ok": True}

    def stop(self) -> None:
        """진행 중인 답을 즉시 중단한다. 작업 스레드가 막혀 있어도 기다리지 않는다."""
        with self._emit_lock:
            with self._lock:
                turn = self._turn
                if turn is None or turn.finalized:
                    return
                turn.cancelled.set()
                self._finalize(turn, "stopped")
            self._emit(turn, {"type": "stopped"}, force=True)
            self._set_idle(turn)

    def close(self) -> None:
        """창이 닫힐 때: 중단하고 새 질문을 받지 않는다."""
        self._closed = True
        self.stop()

    def wait_workers(self, timeout: float) -> bool:
        """중단된 턴의 작업 스레드까지 모두 끝나기를 기다린다. 시간 안에 끝나면 True.
        stop()은 작업 스레드를 기다리지 않고 busy를 풀므로, 모델을 내리기 전에 이전 요청이 끝났는지 확인하는 데 쓴다."""
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                pending = [w for w in self._workers if w is not threading.current_thread()]
            if not pending:
                return True
            left = deadline - time.monotonic()
            if left <= 0:
                return False
            pending[0].join(left)

    def join(self, timeout: float | None = None) -> bool:
        """처리 중인 질문이 종료 이벤트 emit까지 끝나기를 기다린다. 시간 안에 끝나면 True."""
        return self._idle.wait(timeout)

    def _finalize(self, turn: _Turn, outcome: str) -> None:
        """기록을 확정하고 busy를 푼다(self._lock을 쥔 채 부른다). 턴당 한 번만 일어난다."""
        turn.finalized = True
        answer = "".join(turn.reply)
        # 답이 비어 있으면(사고 과정만 오고 끝남, 공백뿐인 답) 그 턴은 남기지 않는다. 빈 assistant 메시지는 문맥으로
        # 보낼 수 없고, 저장하면 다시 열 수 없는 파일이 된다(열기는 빈 content를 거절한다). 실패한 턴과 같게 다룬다
        if outcome in ("done", "stopped") and answer.strip():
            self._turns.append((turn.text, answer))  # 사용자가 본 대로 남긴다(중단이면 본 데까지)
        self._busy = False

    def _set_idle(self, turn: _Turn) -> None:
        with self._lock:
            if self._turn is turn:  # emit 안에서 다음 질문이 시작됐으면 그쪽이 idle을 켠다
                self._idle.set()

    def _abort(self, turn: _Turn) -> None:
        """이벤트 전달이 실패했을 때(창이 닫힘): 호출 층의 다음 이벤트를 기다리지 않고 바로 확정하고 idle로 만든다.
        _emit_lock을 쥔 채 부른다. 이미 확정된 턴이면 아무것도 하지 않는다."""
        turn.cancelled.set()
        with self._lock:
            if not turn.finalized:
                self._finalize(turn, "stopped")
        self._set_idle(turn)

    def _emit(self, turn: _Turn, event: dict, force: bool = False) -> bool:
        """_emit_lock을 쥔 채 부른다. 취소된 턴의 이벤트는 버린다. force는 stop()이 stopped를 낼 때만 쓴다."""
        if turn.cancelled.is_set() and not force:
            return False
        try:
            self._emit_cb(event)
        except Exception:  # 화면이 닫힌 것으로 보고 이 턴을 취소한다
            turn.cancelled.set()
            return False
        return True

    def _run(self, turn: _Turn, messages: list[dict]) -> None:
        try:
            self._run_turn(turn, messages)
        finally:
            with self._lock:
                self._workers.discard(threading.current_thread())

    def _run_turn(self, turn: _Turn, messages: list[dict]) -> None:
        final: dict | None = None
        gen = None
        try:
            # 이미 중단된 턴은 요청을 시작하지 않는다(중단 뒤 모델을 내렸는데 이 요청이 뒤늦게 그 모델을 다시 올리지 않게)
            gen = None if turn.cancelled.is_set() else self._client.stream(messages, model=turn.model, options=turn.options, think=turn.think)
            for event in (gen if gen is not None else ()):
                if turn.cancelled.is_set():
                    break
                if isinstance(event, Thinking):
                    with self._emit_lock:  # 사고 과정은 답(turn.reply)에 넣지 않는다
                        if not self._emit(turn, {"type": "thinking", "text": event.text}):
                            self._abort(turn)
                elif isinstance(event, Token):
                    with self._emit_lock:
                        # 먼저 쌓고 emit이 실패하면 되돌린다. emit 콜백이 같은 스레드에서 stop()을 불러도(RLock)
                        # 방금 전달한 토큰이 답에 들어 있다. 다른 스레드의 stop()은 락 때문에 끼어들 수 없다
                        turn.reply.append(event.text)
                        if not self._emit(turn, {"type": "token", "text": event.text}):
                            turn.reply.pop()  # 전달되지 않은 토큰은 답에 남기지 않는다
                            self._abort(turn)
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
        with self._emit_lock:  # 기록 확정과 종료 이벤트 emit을 한 구간으로 묶는다
            with self._lock:
                if turn.finalized:  # stop()이 이미 확정했다. 이 스레드는 정리만 했다
                    return
                if final is None:  # 취소됐거나 스트림이 종료 이벤트 없이 끝남
                    final = {"type": "stopped"} if turn.cancelled.is_set() else {"type": "error", "kind": "other", "message": "응답이 종료 이벤트 없이 끝났다"}
                self._finalize(turn, final["type"])
            try:
                self._emit(turn, final)
            finally:
                self._set_idle(turn)
