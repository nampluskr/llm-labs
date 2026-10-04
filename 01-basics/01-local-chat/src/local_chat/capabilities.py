"""모델이 지원하는 기능을 Ollama에 물어본다(/api/show의 capabilities)."""

import json
import time

import httpx

MAX_BODY = 1_000_000  # 응답이 이보다 크면 능력 확인으로 보지 않는다


def supports_thinking(host: str, model: str, timeout: float = 5.0) -> bool:
    """모델이 사고 과정을 지원하면 True. 알 수 없으면(서버 없음, 느림, 이상한 응답) False — 이어지는 chat 호출이 오류를 낸다.

    지원하지 않는 모델에 think=True를 보내면 Ollama가 400을 내므로, think는 지원할 때만 켠다.
    창을 여는 경로에서 부르므로 전체 시간을 제한한다: httpx의 timeout은 무응답 시간만 재서, 응답을 조금씩
    흘려 보내면 끝나지 않을 수 있다. 읽는 동안 마감 시각과 크기를 직접 확인한다."""
    deadline = time.monotonic() + timeout
    try:
        with httpx.stream("POST", f"{host.rstrip('/')}/api/show", json={"model": model}, timeout=timeout) as r:
            r.raise_for_status()
            body = bytearray()
            for part in r.iter_bytes():
                body += part
                if time.monotonic() > deadline or len(body) > MAX_BODY:
                    return False
        capabilities = json.loads(bytes(body)).get("capabilities")
        return isinstance(capabilities, list) and "thinking" in capabilities
    except (httpx.HTTPError, ValueError, AttributeError, TypeError):
        return False
