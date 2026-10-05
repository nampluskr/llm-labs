"""실제 pywebview 창을 띄워 Phase 2 완료 조건을 화면에서 확인한다. 프로세스당 webview.start는 한 번이라 시험은 하나다."""

import json
import time

import webview

from prompt_playground.webapp import build
from test_runner import FakeClient


def js(window, code):
    return window.evaluate_js(code)


def wait_for(window, cond, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if js(window, cond):
            return True
        time.sleep(0.1)
    return False


def test_columns_show_params_tokens_and_elapsed(tmp_path):
    out = {}

    def drive(window):
        try:
            assert wait_for(window, "!!(window.pywebview && window.pywebview.api && document.getElementById('model').textContent)")
            # 변형 3개: 기본 2개에 하나를 더하고 마지막 값을 바꾼다
            js(window, "document.getElementById('add').click()")
            js(window, "const r=document.getElementById('rows').children[2]; r.querySelector('.t').value='1.5'; r.querySelector('.s').value='7'; r.querySelector('.y').value='시인처럼'")
            js(window, "document.getElementById('run').click()")
            assert wait_for(window, "document.getElementById('status').textContent.startsWith('완료')")
            out["cols"] = json.loads(js(window, """JSON.stringify([...document.querySelectorAll('#results .col')].map(c => ({
                params: c.querySelector('.params').textContent, stats: c.querySelector('.stats').textContent,
                body: c.querySelector('.body').textContent, think: !!c.querySelector('details')})))"""))
            out["status"] = js(window, "document.getElementById('status').textContent")
            out["run_enabled"] = js(window, "!document.getElementById('run').disabled")
        except Exception as e:  # 창 안의 실패를 바깥으로 전한다
            out["error"] = repr(e)
        finally:
            window.destroy()

    window, api = build(FakeClient(), out_dir=tmp_path)
    webview.start(drive, window)

    assert "error" not in out, out.get("error")
    cols = out["cols"]
    assert len(cols) == 3
    assert "temperature 0.2" in cols[0]["params"] and "seed 1" in cols[0]["params"]
    assert "temperature 1.5" in cols[2]["params"] and "seed 7" in cols[2]["params"] and "시인처럼" in cols[2]["params"]
    for i, c in enumerate(cols):
        assert c["stats"].startswith(f"{10 + i}토큰 · ") and c["stats"].endswith("초")  # 생성 토큰 수와 소요 시간
        assert c["body"] == f"답{i}" and c["think"]
    assert out["status"].startswith("완료") and out["run_enabled"]
    assert len(list(tmp_path.glob("playground-*.json"))) == 1
