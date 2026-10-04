> 버전: v0.1 · 작성일: 2026-10-04

# BRIEF — 00-01 ollama-setup

## 1. 배경

llm-labs의 모든 연습은 이 PC에서 Ollama로 로컬 LLM을 돌리는 것을 전제로 한다(`docs/INTENT.md`). 2026-10-04
현재 Ollama는 아직 설치하지 않았다. 설치는 사용자가 `docs/refs/02-ollama-install-guide.md`를 보고
PowerShell 명령을 직접 실행한다. 하드웨어는 GTX 1080 Ti(VRAM 11GB)이고 화면 출력을 겸해 평상시 약
1.8GB를 쓴다(`docs/refs/01-hardware.md`). 연습 플랜은 `docs/labs/00-setup/01-ollama-setup.md`에 있다.

## 2. 이번 버전에서 풀고 싶은 문제

이 PC에 Ollama를 설치하고, GPU에서 모델이 도는 것을 확인하고, 연습에 쓰는 모델을 받는다. 설치
가이드의 기록표를 채워, 이후 연습(특히 02-01 model-bench)의 예상값을 보정할 첫 근거를 남긴다.

## 3. 이전 버전에서 아쉬웠던 것

해당 없음 (v0.1).

## 4. 하지 않을 것

- 에이전트가 Ollama를 설치하는 일. 사용자가 직접 한다. 에이전트는 읽기 전용 명령으로 확인만 한다.
- 비전·번역·OCR 특화 모델(`gemma3:4b`, `translategemma`, `deepseek-ocr` 등) 받기. 해당 연습을 착수할 때 받는다.
- 모델 저장 위치를 C: 기본 위치에서 다른 드라이브로 옮기는 일.
- Modelfile 작성·모델 튜닝. 01-04 modelfile-studio에서 한다. 여기서는 받은 모델만 쓴다.
- 성능 측정·비교. tok/s·VRAM을 체계적으로 재는 일은 02-01 model-bench에서 한다. 여기서는 기록표에
  한 번 적는 것까지만 한다.

## 5. 완료 조건

- 연습 플랜(`docs/labs/00-setup/01-ollama-setup.md`)의 Phase 1~4 완료 조건을 모두 만족한다
- `docs/refs/02-ollama-install-guide.md`의 기록표가 채워져 있다
- 다음 연습(00-02, 01-01)이 요구하는 모델이 받아져 있고, Ollama 서버가 응답한다
