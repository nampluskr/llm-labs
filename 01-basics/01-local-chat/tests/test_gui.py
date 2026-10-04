"""실제 pywebview 창으로 앱 3개를 확인한다: 질문 → 답변이 조금씩 늘며 표시되고, 끝나면 tok/s와 입력이 돌아온다."""

import json
import os
import subprocess
import sys
import threading

import pytest

from fake_ollama import chunk, done_chunk, send_body, send_headers, send_lines
from local_chat.clients import CLIENTS


def run_driver(name, host, scenario="ok", entry=False, pick=None):
    cmd = [sys.executable, "tests/gui_driver.py", name, host, scenario] + (["entry"] if entry else [])
    env = {**os.environ, **({"GUI_DRIVER_PICK": str(pick)} if pick else {})}
    p = subprocess.run(cmd, capture_output=True, timeout=90, env=env)
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


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창_드롭다운에_모든_모델이_보이고_바꾸면_이전_모델을_내리고_다음_질문부터_새_모델과_옵션으로_답한다(fake, name):
    fake.tags = ["qwen3:8b", "exaone3.5:7.8b", "bge-m3:latest"]
    fake.capabilities_by_model = {
        "qwen3:8b": ["completion", "tools", "thinking"],
        "exaone3.5:7.8b": ["completion"],
        "bge-m3:latest": ["embedding"],
    }
    fake.script = lambda h: send_lines(h, [chunk("가"), chunk("나"), chunk("다"), done_chunk(3, 1_000_000_000)], delay=0.25)
    r = run_driver(name, fake.host, "models")
    assert "driver_error" not in r, r
    # 드롭다운: /api/tags의 모든 모델이 보이고, 채팅할 수 없는 모델만 선택 불가로 표시된다
    assert [o["value"] for o in r["options"]] == ["qwen3:8b", "exaone3.5:7.8b", "bge-m3:latest"]
    assert [o["disabled"] for o in r["options"]] == [False, False, True]
    assert "채팅 불가" in r["options"][2]["text"]
    assert r["initial"]["model"] == "qwen3:8b" and r["initial"]["numctx"] == "4096" and r["initial"]["temp"] == "0.7"
    # 전환: 헤더가 바뀌고, 이전 모델이 내려가고, 새 모델은 사고 과정을 지원하지 않는다
    assert r["switched"] is True and "exaone3.5:7.8b(으)로 바꿨습니다" in r["after_switch"]["status"]
    assert r["after_switch"]["model"] == "exaone3.5:7.8b" and "exaone3.5:7.8b" in r["after_switch"]["info"] and "사고 과정 없음" in r["after_switch"]["info"]
    assert fake.unloads == [{"model": "qwen3:8b", "messages": [], "keep_alive": 0, "stream": False}]
    # 임베딩 모델은 억지로 골라도 거절되고 선택이 되돌아간다
    assert "채팅할 수 없는" in r["embedding"]["status"] and r["embedding"]["model"] == "exaone3.5:7.8b"
    assert len(fake.unloads) == 1
    # 옵션: 헤더에 반영되고 다음 요청에 실린다
    assert r["options_set"] is True and "num_ctx 8192" in r["after_options"]["info"] and "temperature 0.2" in r["after_options"]["info"]
    assert r["ask"]["status"] == "3토큰 · 3.0 tok/s"
    body = fake.requests[0]
    assert body["model"] == "exaone3.5:7.8b" and body["think"] is False
    assert body["options"] == {"num_ctx": 8192, "temperature": 0.2}
    # 범위 밖·빈 값은 거절되고 입력이 되돌아간다
    assert "4096~8192" in r["out_of_range"]["status"] and r["out_of_range"]["numctx"] == "8192"
    assert "temperature" in r["empty_temp"]["status"] and r["empty_temp"]["temp"] == "0.2"
    # 답변 중에는 모델·옵션 입력이 모두 잠기고, 끝나면 풀린다
    assert r["locked_while_busy"] == [[True, True, True]], r["locked_while_busy"]
    assert r["after_busy"] == {"model": False, "numctx": False, "temp": False}
    assert len(fake.requests) == 2  # 거절된 변경은 요청을 만들지 않았다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창은_모델_전환_중에_보내기와_설정_입력을_잠그고_그_사이_보낸_질문은_나가지_않는다(fake, name):
    fake.tags = ["qwen3:8b", "exaone3.5:7.8b"]
    fake.capabilities_by_model = {"qwen3:8b": ["completion", "thinking"], "exaone3.5:7.8b": ["completion"]}
    fake.unload_delay = 1.5  # 이전 모델 내리기가 오래 걸린다
    fake.script = lambda h: send_lines(h, [chunk("답"), done_chunk(1, 1_000_000_000)])
    r = run_driver(name, fake.host, "switch_lock")
    assert "driver_error" not in r, r
    assert r["locked_during_switch"] == [[True, True, True, True]], r  # 전환 중: 모델·num_ctx·temperature·보내기가 모두 잠김
    assert r["bubbles_after_switch"] == 0 and fake.requests == []  # 잠긴 사이 보내려 한 질문은 말풍선도 요청도 만들지 않았다
    assert r["after"]["model"] is False and r["after"]["send"] is False  # 끝나면 풀린다
    assert "exaone3.5:7.8b" in r["after"]["info"] and len(fake.unloads) == 1


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창은_전환_응답이_끊겨도_서버가_실제로_쓰는_모델로_화면을_맞춘다(fake, name):
    fake.tags = ["qwen3:8b", "exaone3.5:7.8b"]
    fake.capabilities_by_model = {"qwen3:8b": ["completion", "thinking"], "exaone3.5:7.8b": ["completion"]}
    fake.script = lambda h: send_lines(h, [chunk("답"), done_chunk(1, 1_000_000_000)])
    r = run_driver(name, fake.host, "switch_lost")
    assert "driver_error" not in r, r
    # 서버에서는 전환됐으므로 화면(드롭다운·헤더)도 새 모델이어야 한다. 이전 모델로 되돌리면 다음 질문이 화면과 다른 모델로 간다
    assert r["after"]["model"] == "exaone3.5:7.8b" and "exaone3.5:7.8b" in r["after"]["info"] and "사고 과정 없음" in r["after"]["info"]
    assert r["after"]["send"] is False
    assert fake.requests[-1]["model"] == "exaone3.5:7.8b" and r["ask"]["status"] == "1토큰 · 1.0 tok/s"


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창은_전환_응답과_상태_조회가_모두_실패하면_잠가_두고_질문을_보내지_않는다(fake, name):
    fake.tags = ["qwen3:8b", "exaone3.5:7.8b"]
    fake.capabilities_by_model = {"qwen3:8b": ["completion", "thinking"], "exaone3.5:7.8b": ["completion"]}
    fake.script = lambda h: send_lines(h, [chunk("답"), done_chunk(1, 1_000_000_000)])
    r = run_driver(name, fake.host, "switch_blind")
    assert "driver_error" not in r, r
    # 서버가 실제로 쓰는 모델을 알 수 없으므로 화면과 다른 모델로 질문이 나가지 않게 잠가 둔다
    assert "서버 상태를 확인하지 못했습니다" in r["after"]["status"]
    assert r["after"]["send"] is True and r["after"]["model"] is True and r["after"]["numctx"] is True
    assert r["bubbles"] == 0 and fake.requests == []  # 잠긴 사이 보낸 질문은 말풍선도 요청도 만들지 않았다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창은_전환_도중_응답이_끊기면_전환이_끝난_뒤_서버의_최종_상태로_맞춘다(fake, name):
    """전환 중의 모델은 임시값이다. 내리기가 실패해 되돌려지면 화면도 이전 모델이어야 하고, 그 전에는 잠겨 있어야 한다."""
    fake.tags = ["qwen3:8b", "exaone3.5:7.8b"]
    fake.capabilities_by_model = {"qwen3:8b": ["completion", "thinking"], "exaone3.5:7.8b": ["completion"]}
    fake.unload_delay = 1.5
    fake.unload_status = 500  # 내리기가 실패해 서버는 전환을 되돌린다
    fake.script = lambda h: send_lines(h, [chunk("답"), done_chunk(1, 1_000_000_000)])
    r = run_driver(name, fake.host, "switch_midflight")
    assert "driver_error" not in r, r
    assert r["during"]["send"] is True and r["during"]["model"] is True  # 전환이 끝나기 전에는 잠겨 있다
    assert "exaone3.5:7.8b" not in r["during"]["info"]  # 임시로 적용된 새 모델을 확정값으로 보여 주지 않는다
    assert r["after"]["model"] == "qwen3:8b" and "qwen3:8b" in r["after"]["info"] and r["after"]["send"] is False  # 서버가 되돌린 최종 상태
    assert fake.requests[-1]["model"] == "qwen3:8b" and r["ask"]["status"] == "1토큰 · 1.0 tok/s"  # 질문은 화면에 보이는 모델로 간다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창은_처리_중에_온_다른_변경_이벤트를_받지_않고_화면을_현재_값으로_되돌린다(fake, name):
    fake.tags = ["qwen3:8b", "exaone3.5:7.8b", "qwen3:14b"]
    fake.capabilities_by_model = {"qwen3:8b": ["completion", "thinking"], "exaone3.5:7.8b": ["completion"], "qwen3:14b": ["completion", "thinking"]}
    fake.unload_delay = 1.0
    fake.script = lambda h: send_lines(h, [chunk("답"), done_chunk(1, 1_000_000_000)])
    r = run_driver(name, fake.host, "double_change")
    assert "driver_error" not in r, r
    # 첫 변경(exaone)만 적용되고, 처리 중에 온 두 번째 모델 변경·옵션 변경은 무시된다. 화면 = 서버
    assert r["after"]["model"] == "exaone3.5:7.8b" and "exaone3.5:7.8b" in r["after"]["info"]
    assert r["after"]["numctx"] == "4096" and "num_ctx 4096" in r["after"]["info"]
    assert [u["model"] for u in fake.unloads] == ["qwen3:8b"]  # 전환은 한 번만 일어났다
    assert fake.requests[-1]["model"] == "exaone3.5:7.8b" and fake.requests[-1]["options"]["num_ctx"] == 4096


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창에서_대화를_저장하고_새_창에서_열면_같은_메시지가_복원되고_문맥으로_이어진다(fake, tmp_path, name):
    from local_chat import conversation

    fake.script = lambda h: send_lines(h, [chunk("답"), done_chunk(1, 1_000_000_000)])
    path = tmp_path / "대화 저장" / "내 대화 😊.json"
    path.parent.mkdir()
    saved = run_driver(name, fake.host, "save", pick=path)
    assert "driver_error" not in saved, saved
    assert saved["saved"] is True and saved["status"] == "4개 메시지를 저장했습니다: 내 대화 😊.json"
    expected = [
        {"role": "user", "content": "첫째 질문 😊"},
        {"role": "assistant", "content": "답"},
        {"role": "user", "content": "둘째\n질문"},
        {"role": "assistant", "content": "답"},
    ]
    assert conversation.load_file(path) == expected  # 파일의 내용(한글·이모지·줄바꿈 보존)
    # 새 창(새 프로세스)에서 연다
    fake.requests.clear()
    loaded = run_driver(name, fake.host, "load", pick=path)
    assert "driver_error" not in loaded, loaded
    assert loaded["before"] == []  # 새 창은 빈 대화로 시작했다
    assert loaded["status"] == "4개 메시지를 불러왔습니다: 내 대화 😊.json"
    # 화면에 같은 개수·순서·role로 복원됐다
    assert loaded["bubbles"][:4] == [["user", "첫째 질문 😊"], ["assistant", "답"], ["user", "둘째\n질문"], ["assistant", "답"]]
    assert loaded["controls"] == {"send": False, "save": False, "open": False}  # 불러온 뒤 다시 쓸 수 있다
    # 복원한 대화가 다음 질문의 문맥으로 서버에 간다
    contents = [m["content"] for m in fake.requests[-1]["messages"]]
    assert contents[1:] == ["첫째 질문 😊", "답", "둘째\n질문", "답", "넷째 질문"]
    assert loaded["next"]["status"] == "1토큰 · 1.0 tok/s"
    assert len(loaded["bubbles"]) == 4  # 상태 확인 시점(질문 전)의 말풍선 수


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창에서_손상된_파일을_열면_오류를_보이고_화면의_대화는_그대로다(fake, tmp_path, name):
    fake.script = lambda h: send_lines(h, [chunk("답"), done_chunk(1, 1_000_000_000)])
    path = tmp_path / "깨진 대화.json"
    path.write_bytes(b'{"messages": [{"role": "user", "content": "q"}, {"role": "assis')
    r = run_driver(name, fake.host, "load_corrupt", pick=path)
    assert "driver_error" not in r, r
    assert r["before"] == [["user", "지켜야 할 질문"], ["assistant", "답"]]
    assert "JSON" in r["status"] and "손상" in r["status"]
    assert r["bubbles"] == r["before"]  # 화면의 대화가 그대로다
    assert r["controls"] == {"send": False, "save": False, "open": False}
    contents = [m["content"] for m in fake.requests[-1]["messages"]]
    assert contents[1:] == ["지켜야 할 질문", "답", "넷째 질문"]  # 서버 쪽 대화도 그대로다


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창은_이미_대화와_사고_과정_블록이_있는_화면_위에서_열어도_옛_화면을_남기지_않는다(fake, tmp_path, name):
    from local_chat import conversation

    fake.capabilities = ["completion", "thinking"]
    fake.script = lambda h: send_lines(h, [chunk("", thinking="생각"), chunk("답"), done_chunk(2, 1_000_000_000)])
    path = tmp_path / "파일의 대화.json"
    file_messages = [{"role": "user", "content": "파일의 질문 😊"}, {"role": "assistant", "content": "파일의 답"}]
    conversation.save_file(path, file_messages)
    r = run_driver(name, fake.host, "load_over", pick=path)
    assert "driver_error" not in r, r
    assert r["think_blocks_before"] == 1  # 열기 전 화면에는 사고 과정 블록이 있었다
    assert r["bubbles"] == [["user", "파일의 질문 😊"], ["assistant", "파일의 답"]]  # 옛 말풍선이 남지 않고 파일의 대화만 보인다
    assert r["think_blocks_after"] == 0 and "불러왔습니다" in r["status"]
    assert r["controls"] == {"send": False, "open": False}


@pytest.mark.parametrize("name", list(CLIENTS))
def test_창은_열기_응답이_끊겨도_서버가_가진_대화로_화면을_맞춘다(fake, tmp_path, name):
    from local_chat import conversation

    fake.script = lambda h: send_lines(h, [chunk("답"), done_chunk(1, 1_000_000_000)])
    path = tmp_path / "파일의 대화.json"
    conversation.save_file(path, [{"role": "user", "content": "파일의 질문"}, {"role": "assistant", "content": "파일의 답"}])
    r = run_driver(name, fake.host, "load_lost", pick=path)
    assert "driver_error" not in r, r
    # 서버에서는 열기가 끝났으므로 화면도 파일의 대화여야 한다(화면에 옛 대화가 남으면 서버와 어긋난다)
    assert r["bubbles"] == [["user", "파일의 질문"], ["assistant", "파일의 답"]]
    assert r["controls"] == {"send": False, "open": False}
