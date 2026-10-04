"""실제 pywebview 창으로 앱 3개를 확인한다: 질문 → 답변이 조금씩 늘며 표시되고, 끝나면 tok/s와 입력이 돌아온다."""

import json
import subprocess
import sys
import threading

import pytest

from fake_ollama import chunk, done_chunk, send_body, send_headers, send_lines
from local_chat.clients import CLIENTS


def run_driver(name, host, scenario="ok", entry=False):
    cmd = [sys.executable, "tests/gui_driver.py", name, host, scenario] + (["entry"] if entry else [])
    p = subprocess.run(cmd, capture_output=True, timeout=90)
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
    assert "사고 과정 없음" in r["info"]  # 이 모델은 사고 과정을 지원하지 않는다(capabilities에 thinking 없음)
    assert fake.requests[0]["think"] is False  # 지원하지 않는 모델에는 think=True를 보내지 않는다
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
            release.wait(1.5)  # 첫 요청은 토큰 하나 뒤 응답이 멈췄다가, 취소된 뒤에 뒤늦게 토큰을 더 보낸다
            try:
                send_body(h, [chunk("늦음"), done_chunk(2, 1_000_000_000)])
            except OSError:
                pass  # 클라이언트가 이미 연결을 닫았다
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
    # 취소된 첫 요청의 서버가 뒤늦게 보낸 토큰·done이 창에 나타나지 않는다(창이 살아 있는 동안 관찰했다)
    assert r["late"] == {"final": "나", "status": "1토큰 · 1.0 tok/s", "send": False, "stop": True, "messages": 4}, r["late"]
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


@pytest.mark.parametrize("name", list(CLIENTS))
def test_앱_진입점으로_뜬_창도_질문에_답하고_인자가_전달된다(fake, name):
    """build()가 아니라 app_<이름>.main(argv)로 창을 띄운다: argparse → build → start 전체 경로."""
    fake.script = lambda h: send_lines(h, [chunk("가"), chunk("나"), done_chunk(2, 1_000_000_000)])
    r = run_driver(name, fake.host, "ok", entry=True)
    assert "driver_error" not in r, r
    assert name in r["title"] and "qwen3:4b" in r["info"]  # --model 인자가 화면에 반영됐다
    assert r["first"]["final"] == "가나" and r["first"]["status"] == "2토큰 · 2.0 tok/s"
    assert fake.requests[0]["model"] == "qwen3:4b"  # --model 인자가 요청에 실렸다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창은_늦게_도착한_전송_거부가_다음_질문의_화면을_지우지_않는다(fake, name):
    fake.script = lambda h: send_lines(h, [chunk("B1"), chunk("B2"), chunk("B3"), chunk("B4"), done_chunk(4, 1_000_000_000)], delay=0.5)
    r = run_driver(name, fake.host, "late_reject")
    assert "driver_error" not in r, r
    # A의 거부(0.9초)가 B의 답변(약 2초) 도중에 도착했지만 B의 화면은 그대로다
    assert r["mid"]["t"].startswith("B1") and r["mid"]["send"] is True and r["mid"]["stop"] is False and r["mid"]["messages"] == 4, r["mid"]
    assert r["end"] == {"final": "B1B2B3B4", "status": "4토큰 · 4.0 tok/s", "messages": 4}


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창은_사고_과정을_펼쳐_보여_주다가_답이_시작되면_접는다(fake, name):
    fake.capabilities = ["completion", "thinking"]
    fake.script = lambda h: send_lines(
        h,
        [chunk("", thinking="음…"), chunk("", thinking="<b>생각</b>"), chunk("답"), chunk("변"), done_chunk(4, 2_000_000_000)],
        delay=0.3,
    )
    r = run_driver(name, fake.host, "think")
    assert "driver_error" not in r, r
    assert fake.show_requests and fake.requests[0]["think"] is True  # 지원하는 모델에는 think=True
    keys = [tuple(k) for k, _, _ in r["seen"]]  # (블록 있음, 펼침, 제목, 답 있음)
    assert (True, True, "생각 중…", False) in keys, keys  # 생각하는 동안: 펼쳐져 있고 답은 아직 없다
    assert keys[-1] == (True, False, "생각 과정", True), keys  # 답이 시작되면 접히고 제목이 바뀐다
    assert keys.index((True, True, "생각 중…", False)) < keys.index(keys[-1])
    final = r["final"]
    assert final["think"] == "음…<b>생각</b>"  # 사고 과정은 글자 그대로(HTML로 해석하지 않음)
    assert final["answer"] == "답변"  # 답에는 사고 과정이 섞이지 않는다
    assert final["bold"] == 0
    assert r["reopened"] is True  # 접힌 사고 과정을 다시 펼 수 있다
    assert "사고 과정 표시" in r["info"]


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창은_사고_과정만_오고_답이_없이_끝나도_블록을_펼친_채_둔다(fake, name):
    fake.capabilities = ["completion", "thinking"]
    fake.script = lambda h: send_lines(h, [chunk("", thinking="생각만"), done_chunk(1, 1_000_000_000)], delay=0.2)
    r = run_driver(name, fake.host, "think")
    assert "driver_error" not in r, r
    keys = [tuple(k) for k, _, _ in r["seen"]]
    assert keys[-1] == (True, True, "생각 과정", False), keys  # 제목은 바뀌지만 답이 없으니 접지 않는다
    assert r["final"]["think"] == "생각만" and r["final"]["answer"] == ""
    assert r["final"]["status"] == "1토큰 · 1.0 tok/s"


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창은_사고_중에_오류가_나도_사고_과정과_오류를_함께_보인다(fake, name):
    fake.capabilities = ["completion", "thinking"]
    fake.script = lambda h: send_lines(h, [chunk("", thinking="생각 중"), {"error": "out of memory"}], delay=0.2)
    r = run_driver(name, fake.host, "think")
    assert "driver_error" not in r, r
    final = r["final"]
    assert final["think"] == "생각 중" and "out of memory" in final["answer"]
    assert final["status"] == "오류(other)"


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창은_생각_중_직접_닫았다가_답_도중_다시_연_블록을_또_접지_않는다(fake, name):
    fake.capabilities = ["completion", "thinking"]
    fake.script = lambda h: send_lines(
        h, [chunk("", thinking="생각"), chunk("답1"), chunk("답2"), chunk("답3"), chunk("답4"), done_chunk(4, 1_000_000_000)], delay=0.3
    )
    r = run_driver(name, fake.host, "think_reopen")
    assert "driver_error" not in r, r
    assert r.get("closed_early") is True and r.get("reopened_during") is True  # 생각 중에 직접 닫고, 답이 흐르는 도중 다시 열었다
    assert r["final"]["answer"] == "답1답2답3답4"
    assert r["open_at_end"] is True  # 다시 연 블록을 다음 토큰이 또 접지 않는다
