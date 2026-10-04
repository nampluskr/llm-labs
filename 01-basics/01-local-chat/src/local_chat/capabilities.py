"""모델이 지원하는 기능을 Ollama에 물어본다(/api/show의 capabilities)."""

import httpx


def supports_thinking(host: str, model: str, timeout: float = 5.0) -> bool:
    """모델이 사고 과정을 지원하면 True. 알 수 없으면(서버 없음 등) False — 이어지는 chat 호출이 오류를 낸다.

    지원하지 않는 모델에 think=True를 보내면 Ollama가 400을 내므로, think는 지원할 때만 켠다."""
    try:
        r = httpx.post(f"{host.rstrip('/')}/api/show", json={"model": model}, timeout=timeout)
        r.raise_for_status()
        capabilities = r.json().get("capabilities")
        return isinstance(capabilities, list) and "thinking" in capabilities
    except (httpx.HTTPError, ValueError, AttributeError, TypeError):
        return False
