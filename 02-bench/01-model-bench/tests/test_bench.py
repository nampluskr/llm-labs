"""Phase 1: 측정 로직을 가짜 클라이언트로 확인한다."""

from types import SimpleNamespace as NS

import ollama

from model_bench import bench
from model_bench.bench import Row, bench_model, list_models, load_csv, processor_label, rate, run_bench, save_csv


class FakeClient:
    def __init__(self, models=None, fail=None):
        self.models = models or {"a:1": ["completion"], "b:2": ["completion", "thinking"], "emb:3": ["embedding"]}
        self.loaded: list[str] = []
        self.calls: list[dict] = []
        self.unloads: list[str] = []
        self.fail = fail

    def list(self):
        return NS(models=[NS(model=m) for m in self.models])

    def show(self, name):
        return NS(capabilities=self.models[name])

    def ps(self):
        return NS(models=[NS(model=m, size=1000, size_vram=500) for m in self.loaded])

    def generate(self, **kw):
        if kw.get("keep_alive") == 0:
            self.unloads.append(kw["model"])
            self.loaded = [m for m in self.loaded if m != kw["model"]]
            return NS()
        if kw["model"] == self.fail:
            raise ollama.ResponseError("boom")
        self.calls.append(kw)
        first = kw["model"] not in self.loaded
        if first:
            self.loaded.append(kw["model"])
        return NS(eval_count=100, eval_duration=2_000_000_000, prompt_eval_count=20, prompt_eval_duration=400_000_000,
                  load_duration=3_000_000_000 if first else 10_000_000)


def test_rate_and_processor():
    assert rate(100, 2_000_000_000) == 50.0
    assert rate(None, 5) is None and rate(5, 0) is None
    assert processor_label(1000, 1000) == "100% GPU"
    assert processor_label(1000, 480) == "52%/48% CPU/GPU"
    assert processor_label(1000, 0) == "100% CPU"


def test_embedding_model_is_skipped():
    run, skipped = list_models(FakeClient())
    assert run == ["a:1", "b:2"] and skipped == ["emb:3"]


def test_model_gets_prompts_x_repeats_rows_with_all_columns():
    c = FakeClient()
    rows = bench_model(c, "a:1", think=False, gpu_used=lambda: 4000)
    assert len(rows) == 3 * 3
    r = rows[0]
    assert r.tok_s == 50.0 and r.load_ms == 3000.0 and r.vram_mib == 4000 and r.baseline_vram_mib == 4000
    assert r.processor == "50%/50% CPU/GPU"
    assert [x.first_run for x in rows] == [True] + [False] * 8  # D-4: 모델마다 첫 호출만
    assert all(k["options"]["num_ctx"] == 4096 for k in c.calls)  # D-2


def test_think_only_sent_to_thinking_models():
    c = FakeClient()
    bench_model(c, "a:1", think=False, prompts=["x"], repeats=1, gpu_used=lambda: 0)
    bench_model(c, "b:2", think=True, prompts=["x"], repeats=1, gpu_used=lambda: 0)
    assert "think" not in c.calls[0] and c.calls[1]["think"] is True


def test_previous_model_is_unloaded_before_next():
    c = FakeClient()
    run_bench(client=c, on_skip=None)
    assert "a:1" in c.unloads  # b:2 전에 a:1을 내렸다
    assert c.loaded == []  # 끝나면 전부 내린다


def test_error_row_does_not_stop_other_models():
    c = FakeClient(fail="a:1")
    rows = run_bench(client=c)
    assert any(r.model == "a:1" and r.error for r in rows)
    assert any(r.model == "b:2" and not r.error for r in rows)


def test_csv_roundtrip(tmp_path):
    rows = bench_model(FakeClient(), "a:1", think=False, prompts=["x"], repeats=2, gpu_used=lambda: 4000)
    p = tmp_path / "x.csv"
    save_csv(p, rows)
    header = p.read_text(encoding="utf-8-sig").splitlines()[0].split(",")
    for col in ("tok_s", "load_ms", "vram_mib", "processor", "first_run", "baseline_vram_mib"):
        assert col in header
    assert load_csv(p) == rows
