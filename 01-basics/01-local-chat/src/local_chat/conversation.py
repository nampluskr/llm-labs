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
import stat
import tempfile
import threading
from datetime import datetime
from pathlib import Path

FORMAT = "local-chat"
VERSION = 1
MAX_BYTES = 10 * 1024 * 1024  # 이보다 큰 파일은 읽지 않는다
READ_TIMEOUT = 15.0  # 파일을 읽는 데 걸릴 수 있는 시간(초). 이 안에 못 읽으면 거절한다(응답하지 않는 네트워크 드라이브 등)
MAX_MESSAGES = 20000  # 이보다 많은 메시지는 읽지도 저장하지도 않는다(화면이 그 많은 말풍선을 그리다 멈추지 않게)
ROLES = ("user", "assistant")  # 이 순서로 번갈아 온다


class ConversationError(Exception):
    """파일을 저장·불러오지 못했다. 메시지는 화면에 그대로 보인다."""


class _DuplicateKey(ValueError):
    """JSON 객체에 같은 키가 두 번 나온다."""


def _no_duplicate_keys(pairs):
    """json.loads는 중복 키를 조용히 마지막 값으로 덮는다. 검증이 보지 못하는 값이 쓰이지 않게 거절한다."""
    seen = set()  # 한 번만 훑는다. 키가 많은 파일에서 오래 걸리지 않게(중복 확인을 목록 검색으로 하면 제곱 시간이 든다)
    for key, _ in pairs:
        if key in seen:
            raise _DuplicateKey(key)
        seen.add(key)
    return dict(pairs)


def _reject_constant(name):
    """NaN·Infinity·-Infinity는 JSON이 아니다. 파이썬의 json은 기본으로 받아들이므로 거절한다."""
    raise ValueError(f"JSON에 없는 상수: {name}")


def parse(text: str) -> list[dict]:
    """JSON 문자열에서 검증된 messages를 꺼낸다. 올바르지 않으면 ConversationError."""
    try:
        data = json.loads(text, object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant)
    except _DuplicateKey as e:
        raise ConversationError(f"같은 키가 두 번 나온다: {e.args[0]!r}") from None
    except (ValueError, RecursionError) as e:  # 깨진 JSON, 너무 깊게 중첩된 JSON
        raise ConversationError(f"JSON이 아니거나 손상된 파일이다 ({type(e).__name__})") from None
    if isinstance(data, dict):
        if "format" in data and data["format"] != FORMAT:
            raise ConversationError(f"이 앱의 대화 파일이 아니다: format={data['format']!r}")
        if "version" in data:  # 없는 것은 허용하지만, 있다면 정수 1이어야 한다(null·1.0·"1"·true는 거절)
            version = data["version"]
            if type(version) is not int or version != VERSION:
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
    if len(raw) > MAX_MESSAGES:
        raise ConversationError(f"메시지가 너무 많다(최대 {MAX_MESSAGES}개)")
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
        try:
            content.encode("utf-8")
        except UnicodeEncodeError:  # JSON 이스케이프(\\ud800)로 든 짝 없는 서로게이트. 받아들이면 이후 모든 요청이 인코딩 오류로 실패한다
            raise ConversationError(f"{i + 1}번째 메시지에 UTF-8로 표현할 수 없는 문자(짝 없는 서로게이트)가 있다") from None
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
        if len(messages) > MAX_MESSAGES:  # 열 수 없는 파일을 만들지 않는다
            raise ConversationError(f"메시지가 너무 많아 저장할 수 없다(최대 {MAX_MESSAGES}개)")
        data = dumps(messages, model).encode("utf-8")  # 인코딩을 명시한다(Windows 기본은 cp949). 쓸 수 없는 문자는 여기서 UnicodeError
        if len(data) > MAX_BYTES:  # 읽을 수 없는 크기의 파일을 만들지 않는다(저장은 되는데 다시 열 수 없는 파일이 된다)
            raise ConversationError(f"대화가 너무 커서 저장할 수 없다(파일 최대 {MAX_BYTES // (1024 * 1024)}MB)")
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=target.name + ".", suffix=".tmp")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
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


def _read_bytes(path: str | os.PathLike) -> bytes:
    """일반 파일의 내용을 읽는다. 폴더·장치·파이프는 읽지 않는다(읽다가 끝없이 기다릴 수 있다)."""
    try:
        if not stat.S_ISREG(os.stat(path).st_mode):
            raise ConversationError("일반 파일이 아니다(폴더·장치·파이프는 읽지 않는다)")
        with open(path, "rb") as f:
            return f.read(MAX_BYTES + 1)
    except OSError as e:
        raise ConversationError(f"파일을 읽지 못했다: {e.strerror or e}") from None


def load_file(path: str | os.PathLike) -> list[dict]:
    """파일을 읽어 검증한 messages를 돌려준다. 읽을 수 없거나 올바르지 않으면 ConversationError.
    읽기에는 시간 제한이 있다(바이트 한도는 읽는 양만 제한하고 기다리는 시간은 제한하지 않는다)."""
    box: dict = {}

    def work():
        try:
            box["raw"] = _read_bytes(path)
        except ConversationError as e:
            box["error"] = e
        except Exception as e:  # 예상하지 못한 읽기 실패도 거절로 통일한다
            box["error"] = ConversationError(f"파일을 읽지 못했다: {e!r}")

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(READ_TIMEOUT)
    if worker.is_alive():  # 응답하지 않는 곳을 읽는 중이다. 기다리지 않고 거절한다(작업 스레드는 백그라운드에 남는다)
        raise ConversationError(f"파일을 읽는 데 너무 오래 걸린다({READ_TIMEOUT:g}초 넘음)")
    if "error" in box:
        raise box["error"]
    raw = box["raw"]
    if len(raw) > MAX_BYTES:
        raise ConversationError(f"파일이 너무 크다(최대 {MAX_BYTES // (1024 * 1024)}MB)")
    try:
        text = raw.decode("utf-8-sig")  # BOM이 있어도 읽는다. 잘못된 바이트는 거절한다
    except UnicodeDecodeError:
        raise ConversationError("UTF-8 텍스트 파일이 아니다") from None
    return parse(text)
