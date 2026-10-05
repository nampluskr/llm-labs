# 01-02 prompt-playground

## 개요

같은 프롬프트를 `temperature`·`top_p`·`seed`·시스템 프롬프트만 바꿔 여러 번 실행하고, 결과를 열로
나란히 놓고 비교하는 pywebview 앱이다. 로컬 LLM과 Ollama가 처음인 사람이 "왜 같은 질문에 답이
매번 달라지는지, 그것을 어디까지 조절할 수 있는지"를 직접 확인하며 익히는 연습이다. 모델은
`qwen3:4b` 하나만 쓴다.

앱으로 생성 옵션이 출력에 주는 영향을 눈으로 보고, `seed`를 고정하면 같은 출력을 다시 얻을 수 있는지
확인한다. 이 PC에서 `seed` 재현성을 같은 조건 5회 실행으로 검증해 그 결과를 문서로 남기며, 이는
02-05 prompt-regression이 출력 고정의 근거로 쓴다. 학습용 연습이라 결과를 점수로 매기거나 저장한
결과를 이력으로 관리하는 기능은 만들지 않는다.

이 연습은 저장소 `llm-labs`의 연습 하나이며, 저장소의 의도는 저장소 루트의 `docs/INTENT.md`에 있다.

## 설치

저장소의 `01-basics/02-prompt-playground` 폴더에서 한 번 실행한다.

```
uv sync
```

## 사용법

창을 연다.

```
uv run prompt-playground
```

1. 프롬프트를 쓰고, 변형 행(`temperature`·`top_p`·`seed`·시스템 프롬프트)을 1~6개 채운다. "변형 추가"로 행을 늘린다.
2. "실행"을 누르면 변형을 한 번에 하나씩 순서대로 실행한다. 결과가 나올 때마다 열이 채워지고, 열마다 파라미터 값·생성 토큰 수·소요 시간이 보인다. 사고 과정은 접어서 볼 수 있다.
3. `temperature`·`top_p`·`seed`·시스템 프롬프트가 모두 같은 행이 둘 이상이면, 뒤의 열에 앞선 열과 답·사고 과정이 글자 단위로 같은지 표시된다.
4. 실행이 끝나면 결과가 `out/playground-<날짜시각>.json`에 저장된다. 저장한 결과를 다시 불러오는 기능은 없다.

변형 하나에 `qwen3:4b`로 20~46초가 걸렸다(대부분 사고 과정). 6개를 돌리면 몇 분이 걸릴 수 있다.

창 없이 JSON으로도 실행할 수 있다.

```
uv run python -m prompt_playground 스펙.json 결과.json
```

스펙 JSON은 `{"prompt": "...", "variants": [{"temperature": 0.2, "top_p": 0.9, "seed": 1, "system": ""}, ...]}` 형식이다.

테스트는 `uv run pytest`다(GUI 테스트가 창을 잠깐 띄운다).

## 재현성 검증 결과

이 PC에서 `qwen3:4b`의 `seed` 재현성을 같은 조건 5회 실행으로 검증했다. 모델이 올라가 있는 상태에서는 5회가 글자 단위로 같았고, 모델을 내렸다가 올린 직후의 첫 요청만 달랐다. 조건과 표는 `docs/refs/seed-reproducibility.md`에 있다.

## 요구 환경

- Windows(pywebview), uv(Python 3.13을 uv가 관리), 실행 중인 Ollama(`http://localhost:11434`)
- 모델 `qwen3:4b`를 미리 받아 둔다(`num_ctx` 4096에서 VRAM 약 3.2GB). GTX 1080 Ti 11GB·Ollama 0.35.1에서 확인했다.
