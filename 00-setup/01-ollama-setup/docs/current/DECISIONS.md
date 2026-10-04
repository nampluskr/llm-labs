> 버전: v0.1 · 작성일: 2026-10-04

# DECISIONS — 00-01 ollama-setup

## D-1. 설치는 사용자가 직접 한다

- **선택:** 사용자가 `docs/refs/02-ollama-install-guide.md`를 보고 PowerShell 명령을 한 줄씩 직접
  실행한다. 에이전트는 읽기 전용 명령(`ollama --version`, `ollama list`, `ollama ps` 등)으로 결과를
  확인만 한다.
- **근거:** 저장소 규칙(`AGENTS.md`)이다. 설치 가이드도 에이전트 없이 사람이 입력 → 기대 결과 →
  다르면 순서로 따라 하도록 쓰여 있다.
- **배제한 대안:** 에이전트가 설치하고 모델을 받기 — 저장소 규칙상 하지 않는다.

## D-2. 설치 방법은 winget, 설치 파일은 대안

- **선택:** `winget install --id Ollama.Ollama --exact`로 설치한다. winget으로 안 될 때만 설치 파일을
  직접 받아 실행한다.
- **근거:** 설치 가이드 2단계의 순서다. winget 패키지 `Ollama.Ollama` 0.35.1을 2026-10-04에 확인했다.
- **배제한 대안:** 설치 파일을 기본으로 쓰기 — winget이 안 될 때의 대안으로만 둔다.

## D-3. 모델 저장 위치는 C: 기본을 유지한다

- **선택:** 모델을 기본 위치(`%USERPROFILE%\.ollama\models`, C:)에 둔다.
- **근거:** C:에 520GB가 남아 있고, 모델 7개를 모두 받아도 약 50GB다(`docs/refs/01-hardware.md` 3절).
- **배제한 대안:** `OLLAMA_MODELS`로 G: 등 다른 드라이브에 두기 — C: 여유가 충분해 옮길 필요가 없다.
  (옮기는 일은 이 버전의 범위 밖이다. BRIEF 4절.)

## D-4. 첫 GPU 확인은 작은 모델로 한다

- **선택:** 첫 확인 모델은 `qwen3:4b`(2.5GB)다.
- **근거:** 설치 가이드 4단계의 순서다. 작은 모델로 GPU 동작을 먼저 확인하고 나서 큰 모델을 받는다.
- **배제한 대안:** `qwen3:8b`(5.2GB)로 바로 확인하기 — 첫 확인에 더 큰 받기가 필요하다.

## D-5. 받을 모델은 7개다

- **선택:** `qwen3:4b`, `qwen3:8b`, `exaone3.5:7.8b`, `bge-m3`, `gemma3:12b`, `qwen3:14b`, `qwen3:30b`.
- **근거:**
  - 앞의 네 개는 `docs/refs/01-hardware.md` 5.2절에서 VRAM에 "여유"로 판정된 연습 기본 모델이다
    (`qwen3`는 범용, `exaone`은 한국어, `bge-m3`는 임베딩).
  - `gemma3:12b`는 "경계" 모델로 02-02 ctx-scaling의 상한 실험 대상이다.
  - `qwen3:14b`는 VRAM을 일부 넘지만 `docs/refs/01-hardware.md` 5.3절 추정에서 "가능"(일괄 처리에
    적합)이다. 사용자가 포함하기로 했다.
  - `qwen3:30b`는 VRAM을 넘어 RAM으로 넘치는 MoE 모델이고 02-01 model-bench가 반드시 측정한다
    (저장소 DECISIONS R-11).
- **배제한 대안:**
  - `gemma3:4b`와 번역·OCR 특화 모델(`translategemma`, `deepseek-ocr` 등) — 해당 연습을 착수할 때
    받는다(BRIEF 4절).
  - `gemma3:27b`, `qwen3:32b` — 연습용으로는 너무 느리다(`docs/refs/01-hardware.md` 5.3절).

## D-6. `100% GPU`가 아니어도 실패로 보지 않는다

- **선택:** `gemma3:12b`·`qwen3:14b`·`qwen3:30b`의 PROCESSOR가 `100% GPU`가 아니어도 실패가 아니라
  측정 결과로 기록표에 적는다. 나머지 모델은 `100% GPU`여야 통과다.
- **근거:** VRAM을 넘는 모델도 연습 대상에 넣기로 했다(저장소 DECISIONS R-11, `docs/refs/01-hardware.md`
  5.3절).
- **배제한 대안:** 모든 모델이 `100% GPU`여야 통과로 보기 — R-11과 모순되고 이 PC의 한계를 측정하는
  02-01의 목적과 맞지 않는다.
