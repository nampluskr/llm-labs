"""실제 pywebview 창으로 앱 3개를 확인한다: 질문 → 답변이 조금씩 늘며 표시되고, 끝나면 tok/s와 입력이 돌아온다."""

import json
import subprocess
import sys
import threading

import pytest

from fake_ollama import chunk, done_chunk, send_body, send_headers, send_lines
from local_chat.clients import CLIENTS


def run_driver(name, host, scenario="ok"):
    p = subprocess.run([sys.executable, "tests/gui_driver.py", name, host, scenario], capture_output=True, timeout=90)
    out = p.stdout.decode("utf-8", "replace")
    line = next((l for l in out.splitlines() if l.startswith("RESULT ")), None)
    assert line, f"드라이버가 결과를 내지 못했다 (exit {p.returncode})\n{out}\n{p.stderr.decode('utf-8', 'replace')[-2000:]}"
    return json.loads(line[len("RESULT "):])


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창에서_질문하면_답변이_스트리밍으로_표시된다(fake, name):
    fake.script = lambda h: send_lines(h, [chunk("가"), chunk("나"), chunk("다"), chunk("라"), done_chunk(4, 2_000_000_000)], delay=0.25)
    r = run_driver(name, fake.host)
    assert "driver_error" not in r, r
    assert r["ready"] and name in r["title"] and "qwen3:8b" in r["info"] and "num_ctx 4096" in r["info"]
    first = r["first"]
    assert first["final"] == "가나다라" and first["status"] == "4토큰 · 2.0 tok/s", first
    # 몰아서 나온 게 아니라 글자 수가 단계적으로 늘었다
    grown = [s for s in first["samples"] if s]
    assert len(grown) >= 3 and grown == sorted(grown, key=len), first["samples"]
    # 답변 중에는 보내기가 막히고 중단이 켜지며, 끝나면 돌아온다
    assert (True, False) in [tuple(b) for b in first["buttons"]]
    assert tuple(first["buttons"][-1]) == (False, True)
    assert r["after_ready_to_send"] is True
    assert r["second"]["final"] == "가나다라"  # 두 번째 질문도 같은 창에서 동작
    assert r["messages"] == 4
    # 두 번째 요청에는 첫 턴이 문맥으로 실렸다
    contents = [m["content"] for m in fake.requests[-1]["messages"]]
    assert contents[1:] == ["안녕", "가나다라", "또 질문"]


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창에서_모델이_없으면_오류가_표시되고_다시_질문할_수_있다(fake, name):
    fake.script = lambda h: send_lines(h, [{"error": "model 'qwen3:8b' not found"}], status=404)
    r = run_driver(name, fake.host)
    assert "driver_error" not in r, r
    assert r["first"]["status"] == "오류(model_not_found)"
    assert "not found" in r["first"]["final"]
    assert tuple(r["first"]["buttons"][-1]) == (False, True)
    assert r["messages"] == 4  # 실패 뒤에도 두 번째 질문을 보낼 수 있었다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창에서_중단_버튼은_서버가_멈춰도_바로_먹고_다음_질문이_나간다(fake, name):
    release = threading.Event()
    calls = []

    def script(h):
        calls.append(1)
        if len(calls) == 1:
            send_headers(h)
            send_body(h, [chunk("가")])
            release.wait(30)  # 첫 요청은 토큰 하나 뒤 응답이 멈춘다
        else:
            send_lines(h, [chunk("나"), done_chunk(1, 1_000_000_000)])

    fake.script = script
    try:
        r = run_driver(name, fake.host, "stop")
    finally:
        release.set()
    assert "driver_error" not in r, r
    assert r["got_token"] and r["before"] == {"send": True, "stop": False}  # 답변 중: 보내기 막힘, 중단 켜짐
    assert r["stopped"] and r["stop_seconds"] < 3, r  # 막힌 읽기(타임아웃 300초)를 기다리지 않았다
    assert r["after"] == {"send": False, "stop": True, "status": "중단했습니다"}
    assert r["next"]["status"] == "1토큰 · 1.0 tok/s" and r["next"]["final"] == "나" and r["messages"] == 4  # 다음 답이 실제로 성공했다
    # 중단된 턴의 받은 부분("가")이 두 번째 요청의 문맥에 있다
    contents = [m["content"] for m in fake.requests[1]["messages"]]
    assert contents[1:] == ["멈출 질문", "가", "다음 질문"]


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창에서_12번_이어_질문해도_요청에는_직전_10턴만_실린다(fake, name):
    fake.script = lambda h: send_lines(h, [chunk("답"), done_chunk(1, 1_000_000_000)])
    r = run_driver(name, fake.host, "many")
    assert "driver_error" not in r, r
    assert all(st and "tok/s" in st for st in r["statuses"]), r["statuses"]
    assert len(fake.requests) == 12
    contents = [m["content"] for m in fake.requests[-1]["messages"]]
    assert len(contents) == 22 and contents[1] == "질문2" and contents[-1] == "질문12"  # 12번째 요청: 질문1 턴이 빠졌다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창은_모델_출력의_HTML을_해석하지_않고_글자_그대로_보인다(fake, name):
    fake.script = lambda h: send_lines(h, [chunk("<b>굵게</b>"), done_chunk(1, 1_000_000_000)])
    r = run_driver(name, fake.host, "escape")
    assert "driver_error" not in r, r
    assert r["first"]["final"] == "<b>굵게</b>"
    assert r["bold_elements"] == 0


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창은_브리지가_없거나_호출이_실패해도_UI가_막히지_않는다(fake, name):
    fake.script = lambda h: send_lines(h, [chunk("답"), done_chunk(1, 1_000_000_000)])
    r = run_driver(name, fake.host, "bridge")
    assert "driver_error" not in r, r
    # 브리지가 없을 때: 아무것도 만들지 않고 입력을 지키며 안내만 한다
    assert r["no_bridge"] == {"messages": 0, "input": "질문", "send_disabled": False, "stop_disabled": True, "status": "준비 중입니다. 잠시 뒤에 다시 보내세요."}
    # 호출이 거부될 때: 말풍선을 되돌리고 입력을 복구하며 다시 보낼 수 있다
    assert r["rejected"] == {"messages": 0, "input": "질문", "send_disabled": False, "stop_disabled": True, "status": "보내지 못했습니다. 다시 시도하세요."}
    assert r["recovered"]["final"] == "답" and r["recovered"]["status"] == "1토큰 · 1.0 tok/s"
    assert fake.requests and len(fake.requests) == 1  # 실패한 두 번은 서버까지 가지 않았다
