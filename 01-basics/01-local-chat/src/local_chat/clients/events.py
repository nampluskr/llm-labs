"""세 호출 층이 공유하는 이벤트와 인터페이스.

stream()은 Token을 0개 이상 내고, 마지막에 Done 또는 Error를 정확히 하나 낸다.
호출자가 제너레이터를 도중에 close()하면 마지막 이벤트 없이 끝난다(중단).
예상 가능한 실패(서버 없음·모델 없음·스트림 끊김)는 예외가 아니라 Error 이벤트로 낸다.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

Message = dict[str, str]  # {"role": "system"|"user"|"assistant", "content": str}

CONNECTION = "connection"
MODEL_NOT_FOUND = "model_not_found"
OTHER = "other"


@dataclass(frozen=True)
class Token:
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


Event = Token | Done | Error


class ChatClient(Protocol):
    name: str

    def stream(self, messages: list[Message], *, model: str, options: dict) -> Iterator[Event]: ...


def make_done(eval_count, eval_duration) -> Done:
    """통계가 정수가 아니면 ValueError — 세 층이 같은 방식으로 Error 이벤트가 되게 한다."""
    for v in (eval_count, eval_duration):
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise ValueError(f"done 청크의 통계가 올바르지 않다: eval_count={eval_count!r}, eval_duration={eval_duration!r}")
    return Done(eval_count, eval_duration)
