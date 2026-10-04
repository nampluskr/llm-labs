> 버전: v0.1 · 작성일: 2026-10-04

# 00-01 ollama-setup — Ollama 설치와 모델 받기

## 1. 개요

이 PC에 Ollama를 설치하고, GPU에서 모델이 도는지 확인하고, 연습에 쓰는 모델을 받는다. **설치는
사용자가 `02-ollama-install-guide.md`를 보고 PowerShell 명령을 직접 실행**하고, 에이전트는 읽기 전용
명령으로 결과를 확인만 한다. 코드는 없다. 이후 모든 연습의 전제가 되며, 가이드 끝의 기록표가 02-01
model-bench의 예상값을 보정하는 첫 근거가 된다.

- Ollama 설치와 서버 동작 확인
- 모델 적재 여부(`ollama ps`의 PROCESSOR)로 GPU 사용 확인
- Ollama API 호출과 응답의 `eval_count`·`eval_duration`·`load_duration`

## 2. 기술 스택

| 항목 | 내용 |
| --- | --- |
| 런타임 | 없음(코드 없음). PowerShell 명령 |
| 도구 | `winget` 또는 설치 파일, `ollama` CLI, `nvidia-smi` |
| Ollama API | `/api/generate`(확인용), `/v1/chat/completions`(확인용) |
| 모델 | `qwen3:4b`(첫 확인), `qwen3:8b`, `exaone3.5:7.8b`, `bge-m3`, `gemma3:12b`, `qwen3:14b`, `qwen3:30b` |
| num_ctx | 해당 없음 |

## 3. 간단한 플랜

| Phase | 목적 | 완료 조건 |
| --- | --- | --- |
| 1 | 설치 | 사용자가 설치 가이드 1~3단계를 마치고, `ollama --version`이 출력되며 버전이 `0.35.1` 이상이다 |
| 2 | GPU 동작 확인 | `ollama run qwen3:4b`가 응답하고, 그때 `ollama ps`의 PROCESSOR가 `100% GPU`다. 가이드의 기록표(설치 날짜·방법·버전·VRAM·PROCESSOR)가 채워져 있다 |
| 3 | API 확인 | 가이드 6단계의 `/api/generate` 호출에서 응답 문자열이 나오고 `eval_count`·`eval_duration`·`load_duration`이 모두 0보다 크다 |
| 4 | 연습용 모델 받기 | `ollama list`에 위 모델 7개가 있고, 모델마다 적재했을 때의 PROCESSOR 값이 기록표에 있다. `gemma3:12b`·`qwen3:14b`·`qwen3:30b`가 `100% GPU`가 아니어도 실패가 아니라 측정 결과다. 01-01이 쓰는 `qwen3:8b`·`qwen3:4b`·`exaone3.5:7.8b`가 목록에 있고 서버가 `/api/tags`에 응답한다 |

## 4. 하드웨어 메모

- 모델 7개를 모두 받으면 디스크를 약 50GB 쓴다. 기본 저장 위치 C:에는 520GB가 남아 있고, 위치는 옮기지 않는다(`01-hardware.md` 3절).
- `qwen3:30b`(약 19GB)는 받기와 첫 로드가 오래 걸리고, 실행 중 RAM 여유가 줄어든다. 다른 앱을 닫고 시험한다(`01-hardware.md` 5.3절).
- 비전·번역·OCR 특화 모델(`gemma3:4b`, `translategemma`, `deepseek-ocr` 등)은 이 연습에서 받지 않는다. 해당 연습을 착수할 때 받는다.

## 5. 미정

- 에이전트가 읽기 전용으로 확인하는 명령의 범위
