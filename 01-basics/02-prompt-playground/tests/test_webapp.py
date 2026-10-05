import json
import threading
import time

import pytest

from prompt_playground.webapp import Api, parse_variant
from test_runner import FakeClient


class FakeWindow:
    def __init__(self):
        self.events = []
        self.done = threading.Event()

    def evaluate_js(self, code):
        assert code.startswith("window.onRunEvent(") and code.endswith(")")
        event = json.loads(code[len("window.onRunEvent("):-1])
        self.events.append(event)
        if event["type"] in ("done", "error"):
            self.done.set()


def make_api(tmp_path, client=None):
    api = Api(client or FakeClient(), out_dir=tmp_path)
    api._window = FakeWindow()
    return api


def raw(t=0.5, p=0.9, s=1, system=""):
    return {"temperature": t, "top_p": p, "seed": s, "system": system}


def test_run_emits_start_results_in_order_then_done_and_saves(tmp_path):
    api = make_api(tmp_path)
    assert api.run("질문", [raw(s=1), raw(s=2), raw(s=3)]) == {"ok": True, "total": 3}
    assert api._window.done.wait(5)
    events = api._window.events
    assert [e["type"] for e in events] == ["start", "result", "result", "result", "done"]
    assert [e["index"] for e in events if e["type"] == "result"] == [0, 1, 2]
    saved = json.loads(open(events[-1]["saved"], encoding="utf-8").read())
    assert len(saved["results"]) == 3 and saved["prompt"] == "질문"


@pytest.mark.parametrize(
    "prompt, variants",
    [("", [raw()]), ("   ", [raw()]), ("q", []), ("q", [raw()] * 7), ("q", [raw(t=3)]), ("q", [raw(p=0)]), ("q", [raw(t="abc")]), ("q", [{"temperature": 1}])],
)
def test_rejects_bad_input_without_running(tmp_path, prompt, variants):
    client = FakeClient()
    api = make_api(tmp_path, client)
    r = api.run(prompt, variants)
    assert r["ok"] is False and r["reason"]
    assert client.calls == [] and api._window.events == []


def test_form_strings_are_parsed():
    v = parse_variant({"temperature": "0.7", "top_p": "0.9", "seed": "42", "system": ""})
    assert (v.temperature, v.top_p, v.seed) == (0.7, 0.9, 42)


def test_second_run_while_busy_is_rejected_and_busy_clears_after(tmp_path):
    gate = threading.Event()

    class Slow(FakeClient):
        def generate(self, **kw):
            gate.wait(5)
            return super().generate(**kw)

    api = make_api(tmp_path, Slow())
    assert api.run("q", [raw()])["ok"] is True
    assert api.run("q", [raw()]) == {"ok": False, "reason": "이미 실행 중이다"}
    gate.set()
    assert api._window.done.wait(5)
    time.sleep(0.05)
    assert api.run("q", [raw()])["ok"] is True  # 끝나면 다시 실행할 수 있다


def test_worker_crash_is_reported_not_swallowed(tmp_path):
    class Boom(FakeClient):
        def generate(self, **kw):
            raise RuntimeError("예상 밖")

    api = make_api(tmp_path, Boom())
    api.run("q", [raw()])
    assert api._window.done.wait(5)
    assert api._window.events[-1]["type"] == "error" and "RuntimeError" in api._window.events[-1]["message"]
    time.sleep(0.05)
    assert api.run("q", [raw()])["ok"] is True  # 오류 뒤에도 busy가 풀린다


def test_result_events_and_saved_json_carry_the_repro_comparison(tmp_path):
    class Fixed(FakeClient):
        def generate(self, **kw):
            super().generate(**kw)
            from types import SimpleNamespace
            return SimpleNamespace(response="같은 답", thinking="같은 생각", eval_count=5)

    api = make_api(tmp_path, Fixed())
    api.run("q", [raw(s=1), raw(s=1), raw(s=2)])
    assert api._window.done.wait(5)
    results = [e["result"] for e in api._window.events if e["type"] == "result"]
    assert results[0]["repro"] is None
    assert results[1]["repro"] == {"ref": 0, "response": {"same": True, "diff_at": None}, "thinking": {"same": True, "diff_at": None}}
    assert results[2]["repro"] is None  # seed가 다르면 같은 조건이 아니다
    saved = json.loads(open(api._window.events[-1]["saved"], encoding="utf-8").read())
    assert saved["results"][1]["repro"]["ref"] == 0
