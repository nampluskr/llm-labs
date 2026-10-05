import json
from types import SimpleNamespace

import httpx
import ollama
import pytest

from prompt_playground.runner import MAX_VARIANTS, MODEL, Variant, run_variants, save_results


class FakeClient:
    """generate 호출을 기록하고, 호출 순서대로 응답한다."""

    def __init__(self, fail_on=(), error=None):
        self.calls = []
        self.fail_on = set(fail_on)
        self.error = error or ollama.ResponseError("boom", 500)

    def generate(self, **kwargs):
        n = len(self.calls)
        self.calls.append(kwargs)
        if n in self.fail_on:
            raise self.error
        return SimpleNamespace(response=f"답{n}", thinking=f"생각{n}", eval_count=10 + n)


def variants(n):
    return [Variant(temperature=0.1 * i, top_p=0.9, seed=i) for i in range(n)]


def test_runs_sequentially_in_order_with_fixed_model_and_think():
    client = FakeClient()
    results = run_variants("질문", variants(3), client=client)
    assert [r["response"] for r in results] == ["답0", "답1", "답2"]
    assert [c["options"]["seed"] for c in client.calls] == [0, 1, 2]
    assert all(c["model"] == MODEL == "qwen3:4b" and c["think"] is True and c["stream"] is False for c in client.calls)
    assert all(c["prompt"] == "질문" for c in client.calls)


def test_options_carry_the_four_parameters():
    client = FakeClient()
    run_variants("q", [Variant(temperature=0.3, top_p=0.5, seed=7, system="규칙")], client=client)
    call = client.calls[0]
    assert call["options"] == {"num_ctx": 4096, "temperature": 0.3, "top_p": 0.5, "seed": 7}
    assert call["system"] == "규칙"


def test_empty_system_is_not_sent():
    client = FakeClient()
    run_variants("q", variants(1), client=client)
    assert client.calls[0]["system"] is None


def test_limits_to_six_variants():
    assert MAX_VARIANTS == 6
    run_variants("q", variants(6), client=FakeClient())
    with pytest.raises(ValueError):
        run_variants("q", variants(7), client=FakeClient())
    with pytest.raises(ValueError):
        run_variants("q", [], client=FakeClient())


def test_one_failure_does_not_stop_the_rest():
    results = run_variants("q", variants(3), client=FakeClient(fail_on={1}))
    assert [r["error"] is None for r in results] == [True, False, True]
    assert results[1]["response"] == "" and results[2]["response"] == "답2"


def test_save_writes_n_results_as_json(tmp_path):
    results = run_variants("질문", variants(4), client=FakeClient())
    path = tmp_path / "out" / "r.json"
    save_results(path, "질문", results)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["model"] == "qwen3:4b" and data["prompt"] == "질문"
    assert len(data["results"]) == 4
    assert {"variant", "response", "thinking", "eval_count", "elapsed_s", "error"} <= data["results"][0].keys()
    assert data["results"][2]["variant"] == {"temperature": pytest.approx(0.2), "top_p": 0.9, "seed": 2, "system": ""}


@pytest.mark.parametrize("error", [httpx.ReadTimeout("느림"), httpx.ConnectError("끊김"), ConnectionError("끊김")])
def test_timeout_or_connection_error_is_one_failure_not_a_stop(error, tmp_path):
    results = run_variants("q", variants(3), client=FakeClient(fail_on={1}, error=error))
    assert [r["error"] is None for r in results] == [True, False, True]
    assert results[1]["error"]  # 빈 문구여도 원인 이름이 남는다
    save_results(tmp_path / "r.json", "q", results)
    assert len(json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))["results"]) == 3
