"""실제 pywebview 창으로 앱 3개를 확인한다: 질문 → 답변이 조금씩 늘며 표시되고, 끝나면 tok/s와 입력이 돌아온다."""

import json
import subprocess
import sys

import pytest

from fake_ollama import chunk, done_chunk, send_lines
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
