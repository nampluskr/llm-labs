> 버전: v0.1 · 작성일: 2026-10-04

# BRIEF — 00-02 env-check

## 1. 배경

00-01 ollama-setup에서 Ollama를 설치하고 모델 7개를 받았다. 그때 서버 응답·버전·모델 목록·적재 상태(PROCESSOR)는
사람이 `ollama list`·`ollama ps`와 API 호출로 손수 확인했다. 이후 연습은 연습 폴더마다 `pyproject.toml`을 두고
uv로 환경을 따로 만든다(저장소 DECISIONS R-10). 하지만 uv·pywebview·jupyter가 이 PC에서 실제로 동작하는지는
아직 확인하지 않았다. 연습 플랜은 `docs/labs/00-setup/02-env-check.md`에 있다.

## 2. 이번 버전에서 풀고 싶은 문제

- 이 연습 폴더에서 uv로 환경을 만들고, pywebview 창과 jupyter 커널이 실제로 뜨는지 확인한다.
- Ollama 서버 연결·버전·받은 모델·적재 상태를 한 번에 점검하는 파이썬 CLI를 만든다. 반복 실행할 수 있고
  사람이 읽는 출력과 `--json` 출력을 낸다.

## 3. 이전 버전에서 아쉬웠던 것

해당 없음 (v0.1).

## 4. 하지 않을 것

- 에이전트가 Ollama를 설치하거나 모델을 받는 일. 점검은 읽기 전용 API만 쓴다.
- 점검 중 모델을 적재하는 일. 현재 상태만 읽는다. 적재하면 평상시 점유(약 1.8GB)와 PROCESSOR가 섞인다.
- 성능 측정·비교(tok/s·VRAM 실측). 02-01 model-bench에서 한다.
- 화면(GUI)을 가진 앱 만들기. pywebview는 창이 뜨는지 확인하는 용도뿐이다.
- 점검 항목의 확장(`nvidia-smi` VRAM·드라이버 버전·디스크 여유 등)과 점검 결과의 파일 저장. 이번 버전은 Ollama 서버·버전·모델 목록·적재 상태까지만 점검하고 화면·JSON으로만 출력한다.

## 5. 완료 조건

- 연습 플랜(`docs/labs/00-setup/02-env-check.md`)의 Phase 1~3 완료 조건을 모두 만족한다
- 서버가 꺼져 있을 때 `env-check`가 오류 문구와 종료 코드 1을 낸다
- 점검 항목마다 통과/실패 한 줄과 전체 결과가 출력되고, `--json`이 같은 내용을 낸다
