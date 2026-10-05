"""사용: uv run python -m prompt_playground 스펙.json 결과.json

스펙 JSON: {"prompt": "...", "variants": [{"temperature": 0.2, "top_p": 0.9, "seed": 1, "system": ""}, ...]}"""

import json
import sys
from pathlib import Path

from .runner import Variant, run_variants, save_results


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    spec_path, out_path = Path(argv[0]), Path(argv[1])
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        prompt = spec["prompt"]
        variants = [Variant(**v) for v in spec["variants"]]
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"스펙을 읽지 못했다: {e}", file=sys.stderr)
        return 2

    def show(i, r):
        status = r["error"] or f'{r["eval_count"]}토큰 {r["elapsed_s"]}초'
        print(f"[{i + 1}/{len(variants)}] {r['variant']} -> {status}")

    try:
        results = run_variants(prompt, variants, on_result=show)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    save_results(out_path, prompt, results)
    print(f"저장: {out_path}")
    return 0 if all(r["error"] is None for r in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
