import sys

import httpx
import ollama

HOST = "http://127.0.0.1:11434"
TIMEOUT = 5.0


def get_version(host):
    response = httpx.get(f"{host}/api/version", timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()["version"]


def get_models(client):
    return [(m.model, m.size) for m in client.list().models]


def processor_label(size, size_vram):
    """`ollama ps`의 PROCESSOR 열과 같은 규칙으로 GPU/CPU 비율을 만든다."""
    if not size:
        return "알 수 없음"
    if size_vram >= size:
        return "100% GPU"
    if size_vram <= 0:
        return "100% CPU"
    gpu = size_vram / size * 100
    return f"{100 - gpu:.0f}%/{gpu:.0f}% CPU/GPU"


def get_loaded(client):
    return [
        (m.model, m.size, processor_label(m.size or 0, m.size_vram or 0))
        for m in client.ps().models
    ]


def gb(size):
    return f"{(size or 0) / 1e9:.1f}GB"


def main(argv=None):
    try:
        version = get_version(HOST)
        client = ollama.Client(host=HOST, timeout=TIMEOUT)
        models = get_models(client)
        loaded = get_loaded(client)
    except (httpx.HTTPError, ConnectionError, ollama.ResponseError) as e:
        print(f"오류: Ollama 서버를 확인할 수 없다 ({HOST}): {e}", file=sys.stderr)
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
