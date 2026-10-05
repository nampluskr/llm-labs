"""사용: uv run python -m model_bench run [-o 결과.csv] [--models a,b]

받은 모델 전부를 측정해 CSV로 저장한다. 화면은 `uv run model-bench`."""

import argparse
import sys
import time
from pathlib import Path

from .bench import run_bench, save_csv

OUT_DIR = Path(__file__).parents[2] / "out"  # .gitignore의 out/


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="model_bench", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="받은 모델 전부를 측정해 CSV로 저장")
    r.add_argument("-o", "--out", type=Path, default=None, help="CSV 경로(기본: out/bench-<날짜시각>.csv)")
    r.add_argument("--models", default=None, help="쉼표로 나눈 모델만 측정(기본: 받은 모델 전부)")
    args = p.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # 파일로 돌릴 때 cp949로 깨지지 않게

    out = args.out or OUT_DIR / f"bench-{time.strftime('%Y%m%d-%H%M%S')}.csv"

    def show(row):
        tag = " (첫 실행)" if row.first_run else ""
        status = row.error or f"{row.tok_s} tok/s · load {row.load_ms}ms · VRAM {row.vram_mib}MiB · {row.processor}"
        print(f"{row.model} p{row.prompt_id}r{row.rep}{tag}: {status}", flush=True)

    def skip(names):
        for n in names:
            print(f"건너뜀(생성 불가 모델): {n}", flush=True)

    models = args.models.split(",") if args.models else None
    rows = run_bench(on_row=show, on_skip=skip, models=models)
    save_csv(out, rows)
    print(f"저장: {out}")
    return 0 if rows and all(not r.error for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
