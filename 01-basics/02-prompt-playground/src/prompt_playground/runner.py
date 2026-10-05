"""파라미터 변형을 순차 실행해 결과를 모은다(Phase 1)."""

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
import ollama

DEFAULT_HOST = "http://localhost:11434"
MODEL = "qwen3:4b"  # D-3
NUM_CTX = 4096
MAX_VARIANTS = 6  # BRIEF 4절


@dataclass(frozen=True)
class Variant:
    """한 번의 실행 조건. 프롬프트는 모든 변형이 같으므로 여기 없다."""

    temperature: float
    top_p: float
    seed: int
    system: str = ""

    def options(self) -> dict:
        return {"num_ctx": NUM_CTX, "temperature": self.temperature, "top_p": self.top_p, "seed": self.seed}


def validate(variants: list[Variant]) -> None:
    if not variants:
        raise ValueError("변형이 하나도 없다")
    if len(variants) > MAX_VARIANTS:
        raise ValueError(f"변형은 최대 {MAX_VARIANTS}개다(받은 {len(variants)}개)")


def run_one(client, prompt: str, variant: Variant) -> dict:
    """변형 하나를 실행한다. 실패해도 예외로 끊지 않고 error를 담아 돌려줘 나머지 변형은 계속한다."""
    started = time.monotonic()
    result = {"variant": asdict(variant)}
    try:
        # think=True: qwen3는 사고 과정을 thinking 필드로 분리해 받는다(CLAUDE.md, 01-01 D-10)
        r = client.generate(
            model=MODEL, prompt=prompt, system=variant.system or None, options=variant.options(), think=True, stream=False
        )
        result.update(
            response=r.response or "",
            thinking=r.thinking or "",
            eval_count=r.eval_count,
            elapsed_s=round(time.monotonic() - started, 3),
            error=None,
        )
    except (ollama.ResponseError, ollama.RequestError, httpx.HTTPError, ConnectionError) as e:
        # httpx 예외(타임아웃·연결 끊김)도 변형 하나의 실패다. 사고 과정 때문에 느린 모델은 타임아웃이 현실적이다
        result.update(
            response="", thinking="", eval_count=None, elapsed_s=round(time.monotonic() - started, 3), error=str(e) or type(e).__name__
        )
    return result


def run_variants(prompt: str, variants: list[Variant], *, host: str = DEFAULT_HOST, client=None, on_result=None) -> list[dict]:
    """변형을 순서대로 하나씩 실행한다. 병렬로 보내지 않는다(플랜 4절). on_result(i, result)로 진행을 알린다."""
    validate(variants)
    client = client or ollama.Client(host=host)
    results = []
    for i, variant in enumerate(variants):
        result = run_one(client, prompt, variant)
        results.append(result)
        if on_result:
            on_result(i, result)
    return results


def save_results(path: Path, prompt: str, results: list[dict]) -> None:
    """결과 N개를 JSON 하나로 저장한다."""
    payload = {"model": MODEL, "prompt": prompt, "results": results}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
