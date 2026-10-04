"""모델이 지원하는 기능을 Ollama에 물어본다(/api/show의 capabilities).

이 모듈은 창을 여는 경로와 사용자의 조작 경로에서 불리므로 모든 호출의 전체 시간을 제한한다.
httpx의 timeout은 연산 하나(연결·헤더 한 번 읽기·본문 한 조각 읽기)의 무응답 시간만 재서, 헤더나 본문을
조금씩 흘려 보내면 끝나지 않을 수 있다. 그래서 요청을 작업 스레드에서 돌리고 바깥에서 전체 시간을 재며,
넘으면 클라이언트를 닫아 막힌 소켓을 풀어 준다."""

import json
import threading
import time

import httpx

MAX_BODY = 1_000_000  # 응답이 이보다 크면 메타 조회로 보지 않는다


def fetch_json(method: str, url: str, body: dict | None = None, timeout: float = 5.0):
    """전체 시간(timeout)과 크기(MAX_BODY) 안에서 JSON을 읽어 돌려준다. 실패하면 httpx.HTTPError나 ValueError."""
    client = httpx.Client(timeout=timeout)
    box: dict = {}

    def work():
        try:
            deadline = time.monotonic() + timeout
            with client.stream(method, url, json=body) as r:
                r.raise_for_status()
                data = bytearray()
                for part in r.iter_bytes():
                    data += part
                    if time.monotonic() > deadline:
                        raise httpx.ReadTimeout("전체 시간 제한을 넘었다")
                    if len(data) > MAX_BODY:
                        raise ValueError("응답이 너무 크다")
            box["value"] = json.loads(bytes(data))
        except (httpx.HTTPError, ValueError) as e:  # 호출한 쪽이 아는 실패는 그대로 넘긴다
            box["error"] = e
        except Exception as e:  # 그 밖의 읽기 실패(예: 너무 깊게 중첩된 JSON의 RecursionError)도 같은 실패로 통일한다
            box["error"] = ValueError(f"응답을 읽지 못했다: {e!r}")

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():  # 헤더를 조금씩 흘리는 등 연산 하나가 끝나지 않는 경우
        client.close()  # 막힌 소켓을 닫아 작업 스레드를 풀어 준다
        raise httpx.ReadTimeout("전체 시간 제한을 넘었다")
    client.close()
    if "error" in box:
        raise box["error"]
    return box["value"]


def show_capabilities(host: str, model: str, timeout: float = 5.0) -> list[str] | None:
    """/api/show의 capabilities 목록. 알 수 없으면(서버 없음, 느림, 이상한 응답) None."""
    try:
        capabilities = fetch_json("POST", f"{host.rstrip('/')}/api/show", {"model": model}, timeout).get("capabilities")
    except (httpx.HTTPError, ValueError, AttributeError, TypeError):
        return None
    return capabilities if isinstance(capabilities, list) else None


def supports_thinking(host: str, model: str, timeout: float = 5.0) -> bool:
    """모델이 사고 과정을 지원하면 True. 알 수 없으면 False — 이어지는 chat 호출이 오류를 낸다.

    지원하지 않는 모델에 think=True를 보내면 Ollama가 400을 내므로, think는 지원할 때만 켠다."""
    capabilities = show_capabilities(host, model, timeout)
    return capabilities is not None and "thinking" in capabilities
