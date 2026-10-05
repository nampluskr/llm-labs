"""pywebview 창. 프롬프트와 변형을 받아 순차 실행하고, 결과가 나올 때마다 화면에 열로 추가한다(Phase 2)."""

import json
import threading
import time
from pathlib import Path

import webview

from .repro import compare_with_earlier
from .runner import DEFAULT_HOST, MAX_VARIANTS, MODEL, Variant, run_variants, save_results

INDEX = Path(__file__).parent / "ui" / "index.html"
OUT_DIR = Path(__file__).parents[2] / "out"  # .gitignore의 out/


def parse_variant(raw: dict) -> Variant:
    """화면의 입력(문자열일 수 있다)을 Variant로 바꾼다. 잘못되면 ValueError."""
    try:
        temperature = float(raw["temperature"])
        top_p = float(raw["top_p"])
        seed = int(raw["seed"])
        system = str(raw.get("system") or "")
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"변형 값을 읽지 못했다: {e!r}") from e
    if not 0.0 <= temperature <= 2.0:
        raise ValueError("temperature는 0~2")
    if not 0.0 < top_p <= 1.0:
        raise ValueError("top_p는 0 초과 1 이하")
    return Variant(temperature=temperature, top_p=top_p, seed=seed, system=system)


class Api:
    """JS에서 window.pywebview.api.*로 부르는 메서드만 공개 이름으로 둔다(공개 속성은 JS에 노출된다)."""

    def __init__(self, client=None, out_dir: Path = OUT_DIR):
        self._client = client
        self._out_dir = out_dir
        self._window = None
        self._lock = threading.Lock()
        self._busy = False  # 한 번에 한 실행만. 병렬 요청은 하지 않는다

    def _emit(self, event: dict) -> None:
        if self._window is None:
            return
        try:
            # ensure_ascii=True라 U+2028 같은 문자도 이스케이프돼 JS 문자열로 안전하다
            self._window.evaluate_js("window.onRunEvent(" + json.dumps(event) + ")")
        except Exception:  # 창이 이미 닫혔다. 실행은 끝까지 가되 화면 갱신은 포기한다
            pass

    def info(self):
        return {"model": MODEL, "max_variants": MAX_VARIANTS}

    def run(self, prompt, variants):
        """검증을 통과하면 작업 스레드에서 실행을 시작하고 바로 돌려준다. 진행은 onRunEvent로 온다."""
        prompt = str(prompt or "").strip()
        if not prompt:
            return {"ok": False, "reason": "prompt를 입력해야 한다"}
        try:
            parsed = [parse_variant(v) for v in variants or []]
            if not parsed or len(parsed) > MAX_VARIANTS:
                raise ValueError(f"변형은 1~{MAX_VARIANTS}개")
        except (ValueError, TypeError) as e:
            return {"ok": False, "reason": str(e)}
        with self._lock:
            if self._busy:
                return {"ok": False, "reason": "이미 실행 중이다"}
            self._busy = True
        threading.Thread(target=self._work, args=(prompt, parsed), daemon=True).start()
        return {"ok": True, "total": len(parsed)}

    def _work(self, prompt: str, variants: list[Variant]) -> None:
        done: list[dict] = []

        def on_result(i: int, r: dict) -> None:
            done.append(r)
            r["repro"] = compare_with_earlier(done, i)  # 저장 JSON에도 남는다
            self._emit({"type": "result", "index": i, "result": r})

        try:
            self._emit({"type": "start", "total": len(variants)})
            results = run_variants(prompt, variants, client=self._client, host=DEFAULT_HOST, on_result=on_result)
            path = self._out_dir / f"playground-{time.strftime('%Y%m%d-%H%M%S')}.json"
            save_results(path, prompt, results)
            self._emit({"type": "done", "saved": str(path)})
        except Exception as e:  # 작업 스레드가 조용히 죽어 화면이 "실행 중"에 갇히지 않게 한다
            self._emit({"type": "error", "message": f"{type(e).__name__}: {e}"})
        finally:
            with self._lock:
                self._busy = False


def build(client=None, width=1200, height=760, out_dir: Path = OUT_DIR):
    api = Api(client, out_dir)
    window = webview.create_window("prompt-playground", url=str(INDEX), js_api=api, width=width, height=height)
    api._window = window
    return window, api


def main() -> None:
    build()
    webview.start()


if __name__ == "__main__":
    main()
