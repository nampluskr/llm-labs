"""설치된 모델 목록과 모델 내리기. 모델 받기·삭제 같은 관리는 하지 않는다(01-03 model-manager)."""

import time

import httpx

from .capabilities import fetch_json, show_capabilities


def list_models(host: str, timeout: float = 8.0) -> list[dict]:
    """/api/tags의 모든 모델을 {name, chat, thinking}으로 돌려준다. 목록을 못 받으면 빈 리스트.

    chat: 채팅할 수 있는가(capabilities에 completion이 있다. 임베딩 모델은 없다). 알 수 없으면 True로 둔다.
    thinking: 사고 과정을 지원하는가. 알 수 없으면 False.
    timeout은 목록과 모델별 확인을 합친 전체 시간이다."""
    deadline = time.monotonic() + timeout
    try:
        tags = fetch_json("GET", f"{host.rstrip('/')}/api/tags", timeout=min(5.0, timeout))
        names = [m["name"] for m in tags["models"]]
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        return []
    models = []
    for name in names:
        left = deadline - time.monotonic()
        caps = show_capabilities(host, name, timeout=left) if left > 0.2 else None
        models.append({
            "name": name,
            "chat": True if caps is None else "completion" in caps,
            "thinking": caps is not None and "thinking" in caps,
        })
    return models


def unload_model(host: str, model: str, timeout: float = 10.0) -> bool:
    """모델을 메모리에서 내린다: 빈 messages와 keep_alive 0을 /api/chat에 보낸다(D-6). 성공하면 True.
    적재돼 있지 않은 모델에 보내도 Ollama는 성공으로 답한다. 설치돼 있지 않으면 404라 False."""
    try:
        fetch_json("POST", f"{host.rstrip('/')}/api/chat", {"model": model, "messages": [], "keep_alive": 0, "stream": False}, timeout)
    except (httpx.HTTPError, ValueError):
        return False
    return True
