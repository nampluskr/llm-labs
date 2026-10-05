# 02-01 model-bench

## 개요

Ollama로 받아 둔 모델 전부에 같은 프롬프트를 돌려, 이 PC(GTX 1080 Ti 11GB)에서 모델별 생성 속도(tok/s)와 VRAM 사용량을 재고 표와 차트로 보여 주는 pywebview 앱이다. 어떤 모델이 이 PC에서 쓸 만한지 숫자로 알고, 이후 연습에서 쓸 모델을 고르는 근거로 삼는 것이 목적이다.

모델마다 프롬프트 3개 × 반복 3회를 `num_ctx` 4096으로 측정한다. VRAM을 넘는 MoE 모델 `qwen3:30b`도 포함해 GPU/CPU 비율(PROCESSOR)을 함께 기록한다. 결과는 CSV로 저장되고, 화면에서 모델별 tok/s·VRAM 표와 차트로 볼 수 있다. 품질 평가는 하지 않고 속도·VRAM 실측만 한다.

이 연습은 저장소 `llm-labs`의 연습 하나이며, 저장소의 의도는 저장소 루트의 `docs/INTENT.md`에 있다.

## 설치

저장소의 `02-bench/01-model-bench` 폴더에서 한 번 실행한다.

```
uv sync
```

## 사용법

창을 연다. `out/`에 저장된 가장 최근 측정 결과(`bench-*.csv`)가 있으면 바로 표와 차트로 보여 준다.

```
uv run model-bench
```

- "측정 실행"을 누르면 받은 모델 전부를 측정한다. 모델이 올라가는 시간 때문에 모델 6개에 15분 안팎이 걸렸다. 끝나면 결과가 `out/bench-<날짜시각>.csv`로 저장되고 표·차트가 갱신된다.
- 표는 모델별 tok/s 평균·표준편차, 점유 VRAM, 첫 로드 시간, 첫 실행 tok/s, 기준 VRAM, 측정 수, PROCESSOR를 보여 준다. 첫 실행(모델을 올린 직후 첫 호출)은 평균에서 뺀다.
- 차트는 모델별 tok/s 막대(평균 ± 표준편차)와 모델별 VRAM 막대를 그리고, VRAM 차트에 9,303MiB 여유선을 표시한다.

창 없이 CLI로도 측정할 수 있다.

```
uv run python -m model_bench run [-o 결과.csv] [--models 모델,모델]
```

생성 능력이 없는 모델(임베딩 모델 `bge-m3` 등)은 건너뛴다. 측정 도중 모델은 하나씩만 올리고 이전 모델은 바로 내린다.

테스트는 `uv run pytest`다(GUI 테스트가 창을 잠깐 띄운다).

## 측정 결과

이 PC에서 모델 6개를 측정한 결과 요약은 `docs/refs/bench-results.md`에 있다. 측정 원본 CSV는 `.gitignore`의 `out/`라 저장소에 없다.

## 요구 환경

- Windows(pywebview), uv(Python 3.13을 uv가 관리), 실행 중인 Ollama(`http://localhost:11434`), `nvidia-smi`(NVIDIA 드라이버)
- 측정할 모델을 미리 받아 둔다. GTX 1080 Ti 11GB·Ollama 0.35.1에서 확인했다.
- 측정 중에는 GPU를 쓰는 다른 앱을 닫는다. 화면 출력을 겸하는 GPU라서 다른 앱의 점유가 결과(기준 VRAM)에 섞인다. `qwen3:30b`는 RAM에 약 11GB가 올라가므로 RAM 여유도 필요하다.
