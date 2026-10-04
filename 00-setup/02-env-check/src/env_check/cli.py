import argparse
import json
import math
import sys

import ollama

HOST = "http://127.0.0.1:11434"
TIMEOUT = 5.0


def request_version(client):
    # ollama 패키지에는 버전 조회 함수가 없어, 패키지가 쓰는 요청 함수로 /api/version을 읽는다(D-7)
    return client._request_raw("GET", "/api/version")


def parse_version(response):
    data = response.json()
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


def describe(error):
    return f"{type(error).__name__}: {error}"


def check(name, ok, detail, data=None):
    return {"name": name, "ok": ok, "detail": detail, "data": data}


def check_connection_and_version(client):
    """서버 연결과 버전은 /api/version 요청 하나에서 나온다. 연결이 실패하면 버전도 확인할 수 없다."""
    try:
        response = request_version(client)
    except Exception as e:  # 연결 거부·시간 초과·HTTP 오류 모두 같은 경로로 보낸다
        return [
            check("서버 연결", False, describe(e)),
            check("버전", False, "서버에 연결하지 못해 확인하지 못했다"),
        ]
    connection = check("서버 연결", True, HOST)
    try:
        version = parse_version(response)
    except Exception as e:  # JSON이 아니거나 version이 없거나 형식이 틀린 응답
        return [connection, check("버전", False, describe(e))]
    return [connection, check("버전", True, version, version)]


def check_models(client):
    try:
        models = get_models(client)
    except Exception as e:
        return check("받은 모델", False, describe(e))
    data = [{"name": name, "size": size} for name, size in models]
    if not models:
        return check("받은 모델", False, "받은 모델이 없다", data)
    return check("받은 모델", True, f"{len(models)}개", data)


def check_loaded(client):
    try:
        loaded = get_loaded(client)
    except Exception as e:
        return check("적재된 모델", False, describe(e))
    data = [{"name": n, "size": s, "processor": p} for n, s, p in loaded]
    return check("적재된 모델", True, f"{len(loaded)}개" if loaded else "없음", data)


def run_checks(client):
    return [
        *check_connection_and_version(client),
        check_models(client),
        check_loaded(client),
    ]


def summarize(checks):
    passed = sum(c["ok"] for c in checks)
    return {"ok": passed == len(checks), "passed": passed, "total": len(checks)}


def render_text(checks):
    lines = []
    for c in checks:
        lines.append(f"[{'통과' if c['ok'] else '실패'}] {c['name']}: {c['detail']}")
        if c["name"] == "받은 모델":
            lines += [f"  {m['name']}  {gb(m['size'])}" for m in c["data"] or []]
        elif c["name"] == "적재된 모델":
            lines += [f"  {m['name']}  {gb(m['size'])}  {m['processor']}" for m in c["data"] or []]
    s = summarize(checks)
    if s["ok"]:
        lines.append(f"결과: 통과 ({s['passed']}/{s['total']})")
    else:
        lines.append(f"결과: 실패 ({s['passed']}/{s['total']} 통과)")
    return "\n".join(lines)


def render_json(checks):
    return json.dumps({**summarize(checks), "checks": checks}, indent=2)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="env-check", description="Ollama 서버·모델·적재 상태를 점검한다.")
    parser.add_argument("--json", action="store_true", help="결과를 JSON으로 출력한다")
    args = parser.parse_args(argv)

    client = ollama.Client(host=HOST, timeout=TIMEOUT, follow_redirects=False)
    checks = run_checks(client)

    print(render_json(checks) if args.json else render_text(checks))
    if not checks[0]["ok"]:
        print(f"오류: Ollama 서버를 확인할 수 없다 ({HOST}): {checks[0]['detail']}", file=sys.stderr)
    return 0 if summarize(checks)["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
