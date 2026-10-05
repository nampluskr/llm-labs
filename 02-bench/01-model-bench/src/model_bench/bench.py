"""받은 모델 전부를 프롬프트 3개 × 반복 3회로 측정해 CSV로 저장한다(Phase 1, D-1~D-5, D-8)."""

import csv
import subprocess
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import httpx
import ollama

DEFAULT_HOST = "http://localhost:11434"
NUM_CTX = 4096  # D-2
REPEATS = 3  # D-4
NUM_PREDICT = 256  # 사고 과정이 긴 모델도 한 호출이 길어지지 않게 자른다(PROGRESS 구현 판단)
TIMEOUT_S = 900  # qwen3:30b 오프로드의 첫 로드를 견딘다
FREE_VRAM_MIB = 9303  # docs/refs/01-hardware.md: 평상시 점유를 뺀 여유

# 모델마다 같은 프롬프트 3개. 길이가 다른 입력으로 prompt_eval 속도도 본다.
PROMPTS = [
    "한국의 사계절을 두 문장으로 설명해 줘.",
    "파이썬에서 리스트와 튜플의 차이를 세 가지로 정리해 줘.",
    "로컬 LLM을 내 PC에서 돌리면 클라우드 API와 비교해 어떤 장단점이 있는지 짧게 설명해 줘.",
]


@dataclass
class Row:
    """CSV 한 행. 한 번의 호출 결과다."""

    model: str
    prompt_id: int
    rep: int
    first_run: bool  # 모델을 올린 뒤 첫 호출(디스크 로드·PTX JIT가 섞인다). 평균에서 뺀다(D-4)
    tok_s: float | None  # eval_count / eval_duration
    prompt_tok_s: float | None  # prompt_eval_count / prompt_eval_duration
    load_ms: float | None
    vram_mib: int | None  # 호출 직후 nvidia-smi memory.used(절대값)
    baseline_vram_mib: int | None  # 모델을 올리기 전 memory.used
    processor: str  # /api/ps의 size_vram/size에서 만든 GPU/CPU 비율
    eval_count: int | None
    error: str


COLUMNS = [f.name for f in fields(Row)]


def gpu_used_mib() -> int | None:
    """nvidia-smi로 GPU 메모리 사용량(MiB)을 읽는다. 못 읽으면 None."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout
        return int(out.strip().splitlines()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def processor_label(size: int, size_vram: int) -> str:
    """ollama ps의 PROCESSOR 열과 같은 형식. 예: '100% GPU', '48%/52% CPU/GPU'."""
    if size <= 0:
        return ""
    gpu = round(100 * size_vram / size)
    if gpu >= 100:
        return "100% GPU"
    if gpu <= 0:
        return "100% CPU"
    return f"{100 - gpu}%/{gpu}% CPU/GPU"


def rate(count, duration_ns) -> float | None:
    """토큰 수와 나노초 소요 시간으로 초당 토큰 수를 낸다."""
    if not count or not duration_ns:
        return None
    return round(count / (duration_ns / 1e9), 2)


def list_models(client) -> tuple[list[str], list[str]]:
    """(측정할 모델, 건너뛴 모델). 생성(completion)을 못 하는 임베딩 모델은 건너뛴다."""
    names = [m.model for m in client.list().models]
    run, skipped = [], []
    for name in names:
        caps = client.show(name).capabilities or []
        (run if "completion" in caps else skipped).append(name)
    return run, skipped


def unload_all(client) -> None:
    """올라가 있는 모델을 전부 바로 내린다(keep_alive: 0, CLAUDE.md·D-5)."""
    for m in client.ps().models:
        client.generate(model=m.model, prompt="", keep_alive=0)
    deadline = time.monotonic() + 30
    while client.ps().models and time.monotonic() < deadline:
        time.sleep(0.5)


def loaded_processor(client, model: str) -> str:
    for m in client.ps().models:
        if m.model == model:
            return processor_label(m.size or 0, m.size_vram or 0)
    return ""


def bench_model(client, model: str, *, think: bool, prompts=PROMPTS, repeats=REPEATS, on_row=None, gpu_used=gpu_used_mib) -> list[Row]:
    """모델 하나를 측정한다. 앞서 올라간 모델을 먼저 내리고, 올리기 전 VRAM을 기준값으로 적는다."""
    unload_all(client)
    baseline = gpu_used()
    rows: list[Row] = []
    for pid, prompt in enumerate(prompts):
        for rep in range(repeats):
            first = not rows
            kw = {"think": True} if think else {}  # 지원하지 않는 모델에는 think를 보내지 않는다(400)
            try:
                r = client.generate(
                    model=model, prompt=prompt, stream=False,
                    options={"num_ctx": NUM_CTX, "num_predict": NUM_PREDICT, "temperature": 0, "seed": 0}, **kw,
                )
                row = Row(
                    model=model, prompt_id=pid, rep=rep, first_run=first,
                    tok_s=rate(r.eval_count, r.eval_duration), prompt_tok_s=rate(r.prompt_eval_count, r.prompt_eval_duration),
                    load_ms=round((r.load_duration or 0) / 1e6, 1), vram_mib=gpu_used(), baseline_vram_mib=baseline,
                    processor=loaded_processor(client, model), eval_count=r.eval_count, error="",
                )
            except (ollama.ResponseError, ollama.RequestError, httpx.HTTPError, ConnectionError) as e:
                row = Row(model, pid, rep, first, None, None, None, gpu_used(), baseline, "", None, str(e) or type(e).__name__)
            rows.append(row)
            if on_row:
                on_row(row)
    return rows


def run_bench(host: str = DEFAULT_HOST, *, client=None, on_row=None, on_skip=None, models: list[str] | None = None) -> list[Row]:
    """받은 모델 전부를 측정한다."""
    client = client or ollama.Client(host=host, timeout=TIMEOUT_S)
    run, skipped = list_models(client)
    if on_skip:
        on_skip(skipped)
    if models is not None:
        run = [m for m in run if m in models]
    rows: list[Row] = []
    for model in run:
        think = "thinking" in (client.show(model).capabilities or [])
        rows += bench_model(client, model, think=think, on_row=on_row)
    unload_all(client)
    return rows


def save_csv(path: Path, rows: list[Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:  # utf-8-sig: 엑셀에서 바로 열린다
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(asdict(r) for r in rows)


def load_csv(path: Path) -> list[Row]:
    def num(s, cast):
        return cast(s) if s not in ("", None) else None

    rows = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for d in csv.DictReader(f):
            rows.append(Row(
                model=d["model"], prompt_id=int(d["prompt_id"]), rep=int(d["rep"]), first_run=d["first_run"] == "True",
                tok_s=num(d["tok_s"], float), prompt_tok_s=num(d["prompt_tok_s"], float), load_ms=num(d["load_ms"], float),
                vram_mib=num(d["vram_mib"], int), baseline_vram_mib=num(d["baseline_vram_mib"], int),
                processor=d["processor"], eval_count=num(d["eval_count"], int), error=d["error"],
            ))
    return rows
