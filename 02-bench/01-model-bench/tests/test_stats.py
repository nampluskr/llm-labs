"""첫 실행값은 평균에서 빠지고 따로 표시된다(D-4)."""

from model_bench.bench import Row
from model_bench.stats import summarize


def row(rep, tok, first=False, vram=5000, err=""):
    return Row("m", 0, rep, first, tok, 100.0, 9000.0 if first else 10.0, vram, 2000, "100% GPU", 100, err)


def test_first_run_excluded_from_mean_and_shown_separately():
    s = summarize([row(0, 10.0, first=True), row(1, 50.0), row(2, 60.0)])[0]
    assert s["tok_s_mean"] == 55.0 and s["runs"] == 2  # 첫 실행 10.0은 빠졌다
    assert s["tok_s_std"] == 7.07
    assert s["first_tok_s"] == 10.0 and s["first_load_ms"] == 9000.0
    assert s["vram_mib"] == 3000 and s["baseline_vram_mib"] == 2000  # 사용량 − 기준값


def test_errors_counted_and_overflow_flagged():
    s = summarize([row(0, 10.0, first=True), row(1, 50.0, vram=12000), row(2, None, err="x")])[0]
    assert s["errors"] == 1 and s["fits_free"] is False  # 12000−2000 > 9303
