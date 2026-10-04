import math
import sys

import ollama

HOST = "http://127.0.0.1:11434"
TIMEOUT = 5.0


def get_version(client):
    # ollama 패키지에는 버전 조회 함수가 없어, 패키지가 쓰는 요청 함수로 /api/version을 읽는다(D-7)
    data = client._request_raw("GET", "/api/version").json()
    version = data.get("version") if isinstance(data, dict) else None
    if not isinstance(version, str) or not version:
        raise ValueError(f"/api/version 응답에 올바른 version이 없다: {data!r}")
    return version


def get_models(client):
    return [(m.model, m.size) for m in client.list().models]


def processor_label(size, size_vram):
    """`ollama ps`의 PROCESSOR 열과 같은 규칙으로 GPU/CPU 비율을 만든다."""
    if size is None or size_vram is None:
        return "알 수 없음"
    if size_vram == 0:
        return "100% CPU"
    if size_vram == size:
        return "100% GPU"
    if size_vram > size or size == 0:
        return "알 수 없음"
    cpu = math.floor((size - size_vram) / size * 100 + 0.5)
    return f"{cpu}%/{100 - cpu}% CPU/GPU"


def get_loaded(client):
    return [
        (m.model, m.size, processor_label(m.size, m.size_vram))
        for m in client.ps().models
    ]


def gb(size):
    return "크기 알 수 없음" if size is None else f"{size / 1e9:.1f}GB"


def main(argv=None):
    try:
        client = ollama.Client(host=HOST, timeout=TIMEOUT)
        version = get_version(client)
        models = get_models(client)
        loaded = get_loaded(client)
    except Exception as e:  # 연결 거부·시간 초과·HTTP 오류·예상 밖 응답 모두 같은 오류 경로로 보낸다
        print(f"오류: Ollama 서버를 확인할 수 없다 ({HOST}): {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print(f"Ollama 서버: 연결됨 ({HOST})")
    print(f"버전: {version}")
    print(f"받은 모델 ({len(models)}개):")
    for name, size in models:
        print(f"  {name}  {gb(size)}")
    if loaded:
        print(f"적재된 모델 ({len(loaded)}개):")
        for name, size, processor in loaded:
            print(f"  {name}  {gb(size)}  {processor}")
    else:
        print("적재된 모델 (0개): 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
