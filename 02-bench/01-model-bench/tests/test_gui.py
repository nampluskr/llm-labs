"""실제 pywebview 창을 띄워 Phase 2 완료 조건을 화면에서 확인한다. 프로세스당 webview.start는 한 번이라 시험은 하나다."""

import json
import time

import webview

from model_bench.bench import Row, save_csv
from model_bench.webapp import build


def rows_for(model, tok, vram, processor="100% GPU", baseline=2000):
    first = Row(model, 0, 0, True, tok / 2, 100.0, 8000.0, baseline + vram, baseline, processor, 100, "")
    rest = [Row(model, 0, i, False, tok + d, 100.0, 10.0, baseline + vram, baseline, processor, 100, "") for i, d in enumerate((-1.0, 0.0, 1.0), 1)]
    return [first, *rest]


def js(window, code):
    return window.evaluate_js(code)


def wait_for(window, cond, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if js(window, cond):
            return True
        time.sleep(0.1)
    return False


def test_table_and_three_chart_elements(tmp_path):
    save_csv(tmp_path / "bench-20260101-000000.csv", rows_for("small:4b", 80.0, 3000) + rows_for("big:30b", 20.0, 8600, "50%/50% CPU/GPU") + rows_for("huge:70b", 5.0, 12000, "20%/80% CPU/GPU"))
    out = {}

    def drive(window):
        try:
            assert wait_for(window, "!!(window.pywebview && window.pywebview.api && document.querySelectorAll('#rows tr').length === 3)")
            assert wait_for(window, "document.querySelectorAll('#chart-tok .bars .point').length === 3 && document.querySelectorAll('#chart-vram .bars .point').length === 3")
            out["table"] = json.loads(js(window, "JSON.stringify([...document.querySelectorAll('#rows tr')].map(tr => [...tr.children].map(td => td.textContent)))"))
            out["header"] = json.loads(js(window, "JSON.stringify([...document.querySelectorAll('#table th')].map(th => th.textContent))"))
            out["tok_bars"] = js(window, "document.querySelectorAll('#chart-tok .bars .point').length")
            out["tok_errorbars"] = js(window, "document.querySelectorAll('#chart-tok .errorbar').length")
            out["vram_bars"] = js(window, "document.querySelectorAll('#chart-vram .bars .point').length")
            out["free_line"] = js(window, "document.querySelectorAll('#chart-vram .shapelayer path').length")
            out["free_text"] = js(window, "document.querySelector('#chart-vram .annotation-text').textContent")
            out["over_cells"] = js(window, "document.querySelectorAll('#rows td.over').length")
        except Exception as e:  # 창 안의 실패를 바깥으로 전한다
            out["error"] = repr(e)
        finally:
            window.destroy()

    window, api = build(client=None, out_dir=tmp_path)
    webview.start(drive, window)

    assert "error" not in out, out.get("error")
    # 모델별 tok/s·VRAM 표
    assert "tok/s 평균" in out["header"] and "VRAM (MiB)" in out["header"]
    small, big, huge = out["table"]
    assert small[0] == "small:4b" and small[1] == "80.00" and small[3] == "3,000"
    assert big[3] == "8,600" and "CPU/GPU" in big[-1]
    assert out["over_cells"] == 1  # 여유(9,303)를 넘는 huge만 강조
    # tok/s 막대(오차 막대 포함), VRAM 막대, 9,303MiB 여유선
    assert out["tok_bars"] == 3 and out["tok_errorbars"] >= 1
    assert out["vram_bars"] == 3
    assert out["free_line"] >= 1 and "9,303" in out["free_text"]
