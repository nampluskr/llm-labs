"""실제 pywebview 창을 띄워 Phase 2·3 완료 조건을 화면에서 확인한다. 프로세스당 webview.start는 한 번이라 시험은 하나다."""

import json
import time
from types import SimpleNamespace

import webview

from prompt_playground.webapp import build


class SeededClient:
    """seed를 고정하면 같은 출력을 내는 가짜 모델. seed 99만 호출마다 출력이 달라지는 '불안정한' 모델처럼 군다."""

    def __init__(self):
        self.n = 0

    def generate(self, **kw):
        o = kw["options"]
        n, self.n = self.n, self.n + 1
        tail = f" #{n}" if o["seed"] == 99 else ""
        return SimpleNamespace(response=f"답 {o['temperature']}/{o['seed']}{tail}", thinking=f"생각 {o['seed']}{tail}", eval_count=10 + n)


def js(window, code):
    return window.evaluate_js(code)


def wait_for(window, cond, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if js(window, cond):
            return True
        time.sleep(0.1)
    return False


# (temperature, top_p, seed, system): 1·2행은 같은 조건, 3행은 seed가 달라 다른 조건, 4·5행은 같은 조건이지만 출력이 달라지는 seed 99
ROWS = [(0.2, 0.9, 1, ""), (0.2, 0.9, 1, ""), (0.2, 0.9, 2, ""), (0.5, 0.9, 99, "시인처럼"), (0.5, 0.9, 99, "시인처럼")]


def test_columns_show_params_stats_and_reproducibility(tmp_path):
    out = {}

    def drive(window):
        try:
            assert wait_for(window, "!!(window.pywebview && window.pywebview.api && document.getElementById('model').textContent)")
            for _ in range(len(ROWS) - 2):  # 기본 행 2개에 추가
                js(window, "document.getElementById('add').click()")
            for i, (t, p, s, y) in enumerate(ROWS):
                js(window, f"""const r=document.getElementById('rows').children[{i}];
                    r.querySelector('.t').value='{t}'; r.querySelector('.p').value='{p}'; r.querySelector('.s').value='{s}'; r.querySelector('.y').value='{y}'""")
            js(window, "document.getElementById('run').click()")
            assert wait_for(window, "document.getElementById('status').textContent.startsWith('완료')")
            out["cols"] = json.loads(js(window, """JSON.stringify([...document.querySelectorAll('#results .col')].map(c => ({
                params: c.querySelector('.params').textContent, stats: c.querySelector('.stats').textContent,
                body: c.querySelector('.body').textContent, think: !!c.querySelector('details'),
                repro: c.querySelector('.repro') ? c.querySelector('.repro').textContent : null,
                repro_classes: c.querySelector('.repro') ? [...c.querySelectorAll('.repro span')].map(s => s.className) : []})))"""))
            out["status"] = js(window, "document.getElementById('status').textContent")
            out["run_enabled"] = js(window, "!document.getElementById('run').disabled")
        except Exception as e:  # 창 안의 실패를 바깥으로 전한다
            out["error"] = repr(e)
        finally:
            window.destroy()

    window, api = build(SeededClient(), out_dir=tmp_path)
    webview.start(drive, window)

    assert "error" not in out, out.get("error")
    cols = out["cols"]
    # Phase 2: 열 N개, 열마다 파라미터·토큰 수·소요 시간
    assert len(cols) == len(ROWS)
    assert "temperature 0.2" in cols[0]["params"] and "seed 1" in cols[0]["params"]
    assert "seed 99" in cols[3]["params"] and "시인처럼" in cols[3]["params"]
    for i, c in enumerate(cols):
        assert c["stats"].startswith(f"{10 + i}토큰 · ") and c["stats"].endswith("초")
        assert c["think"]
    # Phase 3: 같은 조건의 앞선 열과 비교해 답·사고 과정이 같은지 표시한다
    assert cols[0]["repro"] is None  # 같은 조건의 앞선 열이 없다
    assert cols[1]["repro"] == "#1과 같은 조건 · 답 글자 단위로 같음 · 사고 과정 글자 단위로 같음"
    assert cols[1]["repro_classes"] == ["same", "same"]
    assert cols[2]["repro"] is None  # seed가 달라 같은 조건이 아니다
    assert cols[3]["repro"] is None
    assert cols[4]["repro"].startswith("#4과 같은 조건 · 답 다름(") and "사고 과정 다름(" in cols[4]["repro"]
    assert cols[4]["repro_classes"] == ["diff", "diff"]
    assert out["status"].startswith("완료") and out["run_enabled"]
    saved = json.loads(next(tmp_path.glob("playground-*.json")).read_text(encoding="utf-8"))
    assert saved["results"][1]["repro"]["response"]["same"] is True and saved["results"][4]["repro"]["response"]["same"] is False
