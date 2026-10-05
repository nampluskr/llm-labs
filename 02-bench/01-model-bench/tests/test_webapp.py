"""Api: 측정 실행이 CSV를 저장하고 요약을 돌려주며, 중복 실행을 막는다."""

from model_bench.webapp import Api, latest_csv
from tests.test_bench import FakeClient


def test_run_saves_csv_and_load_latest_summarizes(tmp_path):
    api = Api(FakeClient(), out_dir=tmp_path)
    assert api.load_latest() == {"path": None, "summary": []}
    api._busy = True
    assert api.run()["ok"] is False  # 이미 측정 중이면 거절
    api._busy = False
    api._work()  # 창 없이 작업 스레드 본문을 직접 실행
    assert latest_csv(tmp_path) is not None
    models = [s["model"] for s in api.load_latest()["summary"]]
    assert models == ["a:1", "b:2"]  # 임베딩 모델은 빠졌다
    assert api._busy is False
