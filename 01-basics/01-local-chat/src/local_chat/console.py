"""콘솔에서 호출 층을 시험한다: python -m local_chat.console [--client ollama|langchain|http|all]"""

import argparse
import sys

from .clients import CLIENTS, Done, Error, Token

DEFAULT_MODEL = "qwen3:8b"
DEFAULT_OPTIONS = {"num_ctx": 4096, "temperature": 0.7}
DEFAULT_PROMPT = "스트리밍 응답이 왜 체감 속도를 높이는지 세 문장으로 설명해줘."


def run(client, prompt: str, model: str, out=None) -> int:
    out = out or sys.stdout
    messages = [
        {"role": "system", "content": "너는 간결하게 한국어로 답하는 도우미다."},
        {"role": "user", "content": prompt},
    ]
    print(f"[{client.name}] {model}", file=out)
    for event in client.stream(messages, model=model, options=DEFAULT_OPTIONS):
        if isinstance(event, Token):
            print(event.text, end="", file=out, flush=True)
        elif isinstance(event, Done):
            print(f"\n[{client.name}] {event.eval_count}토큰 | {event.tokens_per_second:.1f} tok/s", file=out)
            return 0
        elif isinstance(event, Error):
            print(f"\n[{client.name}] 오류({event.kind}): {event.message}", file=out)
            return 1
    return 1


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔 기본 코드페이지에서 한글이 깨지지 않게
    p = argparse.ArgumentParser(prog="local_chat.console")
    p.add_argument("--client", choices=[*CLIENTS, "all"], default="all")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--host", default="http://localhost:11434")
    p.add_argument("prompt", nargs="?", default=DEFAULT_PROMPT)
    args = p.parse_args(argv)
    names = list(CLIENTS) if args.client == "all" else [args.client]
    codes = [run(CLIENTS[n](host=args.host), args.prompt, args.model) for n in names]
    return 1 if any(codes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
