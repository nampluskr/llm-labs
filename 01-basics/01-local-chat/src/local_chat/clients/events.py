"""세 호출 층이 공유하는 이벤트와 인터페이스.

stream()은 Thinking·Token을 0개 이상 내고, 마지막에 Done 또는 Error를 정확히 하나 낸다.
Thinking은 모델의 사고 과정(think=True일 때만 온다), Token은 답이다. 사고 과정은 문맥에 넣지 않는다.
호출자가 제너레이터를 도중에 close()하면 마지막 이벤트 없이 끝난다(중단).
예상 가능한 실패(서버 없음·모델 없음·스트림 끊김)는 예외가 아니라 Error 이벤트로 낸다.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

import httpx

Message = dict[str, str]  # {"role": "system"|"user"|"assistant", "content": str}

CONNECTION = "connection"
MODEL_NOT_FOUND = "model_not_found"
OTHER = "other"


@dataclass(frozen=True)
class Token:
    text: str


@dataclass(frozen=True)
class Thinking:
    text: str


@dataclass(frozen=True)
class Done:
    eval_count: int
    eval_duration_ns: int

    @property
    def tokens_per_second(self) -> float:
        if self.eval_duration_ns <= 0:
            return 0.0
        return self.eval_count / (self.eval_duration_ns / 1e9)


@dataclass(frozen=True)
class Error:
    kind: str  # CONNECTION | MODEL_NOT_FOUND | OTHER
    message: str


Event = Token | Thinking | Done | Error


class ChatClient(Protocol):
    name: str
    host: str  # 모델 능력 조회(capabilities.supports_thinking)에 쓴다

    def stream(self, messages: list[Message], *, model: str, options: dict, think: bool = False) -> Iterator[Event]: ...


def make_done(eval_count, eval_duration) -> Done:
    """통계가 정수가 아니면 ValueError — 세 층이 같은 방식으로 Error 이벤트가 되게 한다."""
    for v in (eval_count, eval_duration):
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise ValueError(f"done 청크의 통계가 올바르지 않다: eval_count={eval_count!r}, eval_duration={eval_duration!r}")
    return Done(eval_count, eval_duration)


def classify(status: int | None, message: str) -> str:
    """HTTP 상태·오류 문구로 Error.kind를 정한다. 세 층이 같은 규칙을 쓴다."""
    message = str(message)  # 서버가 문자열이 아닌 error 값을 보내도 예외가 새지 않게
    if status == 404 or "not found" in message.lower():
        return MODEL_NOT_FOUND
    return OTHER


def make_timeout(read_seconds: float) -> httpx.Timeout:
    """연결은 10초, 응답 대기는 read_seconds(큰 모델 적재를 기다릴 수 있게 길게). 세 층이 같은 값을 쓴다."""
    return httpx.Timeout(10.0, read=read_seconds)


def thinking_text(value) -> str:
    """청크의 사고 과정 값을 문자열로 확인한다. 없으면 빈 문자열, 문자열이 아니면 ValueError."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"message.thinking이 문자열이 아니다: {value!r}")
    return value
