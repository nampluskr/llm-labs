"""pywebview 창. 측정 결과를 모델별 표와 Plotly 차트로 보여 준다(Phase 2, D-6·D-7)."""

import json
import threading
import time
from pathlib import Path

import webview

from .bench import FREE_VRAM_MIB, load_csv, run_bench, save_csv
from .stats import summarize

INDEX = Path(__file__).parent / "ui" / "index.html"
OUT_DIR = Path(__file__).parents[2] / "out"  # .gitignore의 out/


def latest_csv(out_dir: Path) -> Path | None:
    files = sorted(out_dir.glob("bench-*.csv"), key=lambda p: p.stat().st_mtime) if out_dir.exists() else []
    return files[-1] if files else None


class Api:
    """JS에서 window.pywebview.api.*로 부르는 메서드만 공개 이름으로 둔다."""

    def __init__(self, client=None, out_dir: Path = OUT_DIR):
        self._client = client
        self._out_dir = out_dir
        self._window = None
        self._lock = threading.Lock()
        self._busy = False  # 측정은 한 번에 하나만

    def _emit(self, event: dict) -> None:
        if self._window is None:
            return
        try:
            self._window.evaluate_js("window.onBenchEvent(" + json.dumps(event) + ")")
        except Exception:  # 창이 이미 닫혔다. 측정은 끝까지 간다
            pass

    def info(self):
        return {"free_vram_mib": FREE_VRAM_MIB}

    def load_latest(self):
        """out/의 가장 최근 CSV를 요약해 돌려준다. 없으면 summary가 빈 목록이다."""
        path = latest_csv(self._out_dir)
        if path is None:
            return {"path": None, "summary": []}
        return {"path": str(path), "summary": summarize(load_csv(path))}

    def run(self):
        with self._lock:
            if self._busy:
                return {"ok": False, "reason": "이미 측정 중이다"}
            self._busy = True
        threading.Thread(target=self._work, daemon=True).start()
        return {"ok": True}

    def _work(self) -> None:
        rows = []

        def on_row(r):
            rows.append(r)
            self._emit({"type": "row", "model": r.model, "n": len(rows), "error": r.error})

        try:
            self._emit({"type": "start"})
            run_bench(client=self._client, on_row=on_row)
            path = self._out_dir / f"bench-{time.strftime('%Y%m%d-%H%M%S')}.csv"
            save_csv(path, rows)
            self._emit({"type": "done", "saved": str(path), "summary": summarize(rows)})
        except Exception as e:  # 작업 스레드가 조용히 죽어 화면이 "측정 중"에 갇히지 않게 한다
            self._emit({"type": "error", "message": f"{type(e).__name__}: {e}"})
        finally:
            with self._lock:
                self._busy = False


def build(client=None, width=1200, height=900, out_dir: Path = OUT_DIR):
    api = Api(client, out_dir)
    window = webview.create_window("model-bench", url=str(INDEX), js_api=api, width=width, height=height)
    api._window = window
    return window, api


def main() -> None:
    build()
    webview.start()


if __name__ == "__main__":
    main()
