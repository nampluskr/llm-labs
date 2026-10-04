"""대화 저장·불러오기(D-7): `/api/chat`의 messages 배열(role·content)을 JSON으로 저장하고 그대로 복원한다.

파일 모양:
  {"format": "local-chat", "version": 1, "saved_at": "...", "model": "...", "messages": [{"role": "user", "content": "..."}, ...]}
messages는 질문(user)과 답(assistant)이 번갈아 오고 user로 시작하며 쌍으로 끝난다(시스템 메시지는 매 질문마다 붙으므로 저장하지 않는다).
사고 과정은 대화 기록에 없으므로 저장되지 않는다(D-10). `model`은 참고용이고 불러올 때 현재 모델을 바꾸지 않는다.
messages 배열만 있는 파일(최상위가 배열)도 읽는다.

손상된 파일은 어떤 경우에도 예외가 아니라 ConversationError(사람이 읽을 문구)로 거절한다. 거절되면 현재 대화는 그대로다.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

FORMAT = "local-chat"
VERSION = 1
MAX_BYTES = 10 * 1024 * 1024  # 이보다 큰 파일은 읽지 않는다
ROLES = ("user", "assistant")  # 이 순서로 번갈아 온다


class ConversationError(Exception):
    """파일을 저장·불러오지 못했다. 메시지는 화면에 그대로 보인다."""


def parse(text: str) -> list[dict]:
    """JSON 문자열에서 검증된 messages를 꺼낸다. 올바르지 않으면 ConversationError."""
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as e:  # 깨진 JSON, 너무 깊게 중첩된 JSON
        raise ConversationError(f"JSON이 아니거나 손상된 파일이다 ({type(e).__name__})") from None
    if isinstance(data, dict):
        version = data.get("version")
        if version is not None and (isinstance(version, bool) or version != VERSION):
            raise ConversationError(f"지원하지 않는 형식 버전이다: {version!r}")
        if "messages" not in data:
            raise ConversationError("messages가 없다")
        raw = data["messages"]
    elif isinstance(data, list):
        raw = data
    else:
        raise ConversationError("대화 파일이 아니다(최상위가 객체나 배열이어야 한다)")
    if not isinstance(raw, list):
        raise ConversationError("messages가 배열이 아니다")
    messages = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ConversationError(f"{i + 1}번째 메시지가 객체가 아니다")
        role, content = item.get("role"), item.get("content")
        expected = ROLES[i % 2]
        if role not in ROLES:
            raise ConversationError(f"{i + 1}번째 메시지의 role이 올바르지 않다: {role!r}")
        if role != expected:
            raise ConversationError(f"{i + 1}번째 메시지는 {expected}여야 한다(질문과 답이 번갈아 와야 한다)")
        if not isinstance(content, str) or not content.strip():
            raise ConversationError(f"{i + 1}번째 메시지의 content가 비어 있거나 문자열이 아니다")
        messages.append({"role": role, "content": content})  # 알려진 필드만 옮긴다
    if len(messages) % 2:
        raise ConversationError("마지막 질문에 답이 없다(메시지 수가 홀수다)")
    return messages


def dumps(messages: list[dict], model: str | None = None) -> str:
    document = {
        "format": FORMAT,
        "version": VERSION,
        "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": model,
        "messages": messages,
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"  # 한글을 \uXXXX로 바꾸지 않는다


def save_file(path: str | os.PathLike, messages: list[dict], model: str | None = None) -> None:
    """임시 파일에 다 쓴 뒤 교체한다. 도중에 실패해도 기존 파일은 그대로고 임시 파일은 남지 않는다."""
    target = Path(path)
    tmp_name = None
    try:
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=target.name + ".", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:  # 인코딩을 명시한다(Windows 기본은 cp949)
            f.write(dumps(messages, model))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, target)
        tmp_name = None
    except OSError as e:
        raise ConversationError(f"저장하지 못했다: {e.strerror or e}") from None
    except UnicodeError:  # 짝 없는 서로게이트처럼 UTF-8로 쓸 수 없는 문자
        raise ConversationError("저장하지 못했다: UTF-8로 쓸 수 없는 문자가 있다") from None
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def load_file(path: str | os.PathLike) -> list[dict]:
    """파일을 읽어 검증한 messages를 돌려준다. 읽을 수 없거나 올바르지 않으면 ConversationError."""
    try:
        with open(path, "rb") as f:
            raw = f.read(MAX_BYTES + 1)
    except OSError as e:
        raise ConversationError(f"파일을 읽지 못했다: {e.strerror or e}") from None
    if len(raw) > MAX_BYTES:
        raise ConversationError(f"파일이 너무 크다(최대 {MAX_BYTES // (1024 * 1024)}MB)")
    try:
        text = raw.decode("utf-8-sig")  # BOM이 있어도 읽는다. 잘못된 바이트는 거절한다
    except UnicodeDecodeError:
        raise ConversationError("UTF-8 텍스트 파일이 아니다") from None
    return parse(text)
