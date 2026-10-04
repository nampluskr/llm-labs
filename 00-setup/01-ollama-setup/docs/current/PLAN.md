> 버전: v0.1 · 작성일: 2026-10-04

# PLAN — 00-01 ollama-setup

SPEC은 두지 않는다. Phase마다 BRIEF 5절 완료 조건을 가리킨다.

이 연습에는 구현 코드가 없다. 설치와 모델 받기는 **사용자**가 직접 하고, **에이전트**는 읽기 전용
명령으로 확인만 한다(D-1).

## Phase 1 — 설치

- **목적:** Ollama를 설치하고 서버가 동작하게 한다(D-2).
- **BRIEF 완료 조건:** "연습 플랜의 Phase 1~4 완료 조건을 모두 만족한다"
- **사용자:** `docs/refs/02-ollama-install-guide.md` 1~3단계를 PowerShell에서 한 줄씩 직접 실행한다.
- **에이전트:** `ollama --version`을 읽기 전용으로 확인한다.
- **완료 조건:** `ollama --version`이 출력되고 버전이 `0.35.1` 이상이다.

## Phase 2 — GPU 동작 확인

- **목적:** 작은 모델로 GPU에서 모델이 도는지 확인한다(D-4).
- **BRIEF 완료 조건:** "Phase 1~4 완료 조건을 모두 만족한다", "`docs/refs/02-ollama-install-guide.md`의
  기록표가 채워져 있다"
- **사용자:** `ollama run qwen3:4b`를 실행하고 설치 가이드의 기록표(설치 날짜·방법·버전·VRAM·PROCESSOR)를 적는다.
- **에이전트:** `ollama ps`의 PROCESSOR와 기록표가 채워졌는지 확인한다.
- **완료 조건:** `ollama run qwen3:4b`가 응답하고, 그때 `ollama ps`의 PROCESSOR가 `100% GPU`다. 기록표의
  해당 항목이 채워져 있다.

## Phase 3 — API 확인

- **목적:** 이후 연습의 앱이 쓸 방식으로 Ollama API가 응답하는지 확인한다.
- **BRIEF 완료 조건:** "Phase 1~4 완료 조건을 모두 만족한다"
- **사용자:** 설치 가이드 6단계의 `/api/generate` 호출을 직접 실행한다.
- **에이전트:** 응답과 `eval_count`·`eval_duration`·`load_duration` 값을 확인한다.
- **완료 조건:** `/api/generate` 호출에서 응답 문자열이 나오고 `eval_count`·`eval_duration`·
  `load_duration`이 모두 0보다 크다.

## Phase 4 — 연습용 모델 받기

- **목적:** 연습에 쓰는 모델 7개를 받고 적재 상태를 기록한다(D-5, D-6).
- **BRIEF 완료 조건:** "Phase 1~4 완료 조건을 모두 만족한다", "기록표가 채워져 있다", "다음 연습(00-02,
  01-01)이 요구하는 모델이 받아져 있고, Ollama 서버가 응답한다"
- **사용자:** `ollama pull`로 모델을 받고, 모델마다 적재해 PROCESSOR를 기록표에 적는다. `qwen3:30b`를
  시험할 때는 다른 앱을 닫는다.
- **에이전트:** `ollama list`와 `/api/tags` 응답을 확인한다.
- **완료 조건:**
  - `ollama list`에 `qwen3:4b`·`qwen3:8b`·`exaone3.5:7.8b`·`bge-m3`·`gemma3:12b`·`qwen3:14b`·
    `qwen3:30b` 7개가 있다.
  - 모델마다 적재했을 때의 PROCESSOR 값이 기록표에 있다. `gemma3:12b`·`qwen3:14b`·`qwen3:30b`는
    `100% GPU`가 아니어도 실패가 아니라 측정 결과다. 나머지 모델은 `100% GPU`다.
  - 01-01이 쓰는 `qwen3:8b`·`qwen3:4b`·`exaone3.5:7.8b`가 목록에 있고 서버가 `/api/tags`에 응답한다.

## 적대적 검증

이 연습은 사용자가 설치하고 에이전트는 읽기 전용으로 확인하는 연습이라 구현 코드가 없다. 새 기능
구현도 리팩토링도 아니므로 검증 대상이 아니다(`workflow/docs/ADVERSARIAL-REVIEW.md` 3절).

- **필수 통과 Phase:** 없음 — 코드 없음
- **Phase별 공격 초점:** 해당 없음 — 코드 없음
