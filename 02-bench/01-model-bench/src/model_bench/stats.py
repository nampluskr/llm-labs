"""행들을 모델별 요약(표·차트용)으로 줄인다. 첫 실행값은 평균·표준편차에서 뺀다(D-4)."""

import numpy as np

from .bench import FREE_VRAM_MIB, Row


def summarize(rows: list[Row]) -> list[dict]:
    """모델마다 한 줄. 모델이 나온 순서를 지킨다."""
    out = []
    for model in dict.fromkeys(r.model for r in rows):
        mine = [r for r in rows if r.model == model]
        ok = [r for r in mine if not r.error]
        steady = [r for r in ok if not r.first_run and r.tok_s is not None]
        tok = np.array([r.tok_s for r in steady])
        # 모델이 차지한 VRAM = 호출 직후 사용량 − 올리기 전 기준값. 첫 실행 이후 값의 평균
        deltas = [r.vram_mib - r.baseline_vram_mib for r in steady if r.vram_mib is not None and r.baseline_vram_mib is not None]
        first = next((r for r in mine if r.first_run), None)
        out.append({
            "model": model,
            "runs": len(steady),
            "errors": len(mine) - len(ok),
            "tok_s_mean": round(float(tok.mean()), 2) if len(tok) else None,
            "tok_s_std": round(float(tok.std(ddof=1)), 2) if len(tok) > 1 else (0.0 if len(tok) == 1 else None),
            "vram_mib": round(float(np.mean(deltas))) if deltas else None,
            "fits_free": bool(np.mean(deltas) <= FREE_VRAM_MIB) if deltas else None,
            "processor": (steady[-1].processor if steady else (first.processor if first else "")),
            "first_load_ms": first.load_ms if first else None,
            "first_tok_s": first.tok_s if first else None,
            "baseline_vram_mib": first.baseline_vram_mib if first else None,
        })
    return out
