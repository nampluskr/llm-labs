> 버전: v0.1 · 작성일: 2026-10-04

# 02-01 model-bench — 모델별 속도·VRAM 비교

## 1. 개요

받은 모델 전부에 같은 프롬프트 세트를 돌려 생성 속도(tok/s), 프롬프트 처리 속도, 로드 시간,
VRAM 사용량, GPU/CPU 비율을 재고 Plotly 차트로 비교하는 앱이다. 이후 모든 프로젝트의
모델 선택 근거가 된다. `02-ollama-install-guide.md` 기록표를 자동화한 것이기도 하다.

- 응답의 `eval_count`·`eval_duration`·`prompt_eval_*`·`load_duration` 해석
- nvidia-smi로 VRAM 샘플링
- 반복 측정과 평균·편차

## 2. 기술 스택

| 항목 | 내용 |
| --- | --- |
| 런타임 | Python + pywebview(Plotly.js 차트) |
| 언어·패키지 | Python 3.13(uv), `ollama`, `numpy`, `pywebview` |
| Ollama API | `/api/tags`, `/api/generate`(stream: false), `/api/ps` |
| 모델 | 받은 모델 전부. VRAM을 넘는 MoE 모델 `qwen3:30b`(약 19GB, 활성 3B)를 반드시 포함한다 |
| num_ctx | 4096 고정(비교 조건 통일) |

## 3. 간단한 플랜

| Phase | 목적 | 완료 조건 |
| --- | --- | --- |
| 1 | 측정 CLI | `bench run`이 모델 × 프롬프트 3개 × 반복 3회를 실행해 행마다 tok/s·load_ms·VRAM_MiB·PROCESSOR가 있는 CSV를 만든다 |
| 2 | 차트 | 모델별 tok/s 막대(평균 ± 표준편차)와 VRAM 막대가 한 화면에 그려진다. 9,303MiB 여유선이 표시된다 |
| 3 | 결과 누적 | 실행할 때마다 날짜별 CSV가 쌓이고, 화면에서 두 날짜 결과를 겹쳐 볼 수 있다 |

## 4. 하드웨어 메모

- 측정 중에는 브라우저 등 GPU를 쓰는 앱을 닫는다. 화면 출력 겸용이라 평상시 점유(약 1.8GB)가 결과에 섞인다. 측정 전 기준값을 함께 기록한다.
- 모델 사이에 `keep_alive: 0`으로 이전 모델을 내린다. 첫 실행 측정값(PTX JIT, 디스크 로드)은 따로 표시한다.
- `gemma3:12b`처럼 "경계" 모델의 PROCESSOR 값이 이 측정의 핵심 결과다.
- `qwen3:30b`는 VRAM에 약 8GB, RAM에 약 11GB가 올라가는 오프로드 모델이다(`01-hardware.md` 5.3절).
  예상 약 10~20 tok/s를 실측으로 확인하고, PROCESSOR의 CPU/GPU 비율을 함께 기록한다. 측정 중
  RAM 여유가 빠듯해질 수 있으니 다른 앱을 닫는다.

## 5. 미정

없음
