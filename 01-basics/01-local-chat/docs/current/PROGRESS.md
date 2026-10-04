> 버전: v0.1 · 작성일: 2026-10-04

# PROGRESS — 01-01 local-chat

## 계획된 작업

### Phase 1 — 세 호출 방식 노트북 (2026-10-04) — 완료

- **무엇을:** `notebooks/`에 `01-ollama.ipynb`(공식 클라이언트), `02-langchain-ollama.ipynb`(`ChatOllama`), `03-http-api.ipynb`(`httpx`로 `/api/chat` NDJSON)를 만들었다. 세 노트북 모두 같은 모델(`qwen3:8b`)·옵션(`num_ctx` 4096, `temperature` 0.7)·`think=False`·메시지를 쓰고, 비스트리밍 → 스트리밍 + tok/s → 멀티턴 순서다.
- **결과:** 노트북 3개(실행 결과 출력 포함). 이 연습의 uv 환경도 만들었다(`pyproject.toml`, `uv.lock`, `.python-version` 3.13; `ollama`·`langchain-ollama`·`httpx`·`pywebview`·`jupyter`·`ipykernel`).
- **검증:** `jupyter nbconvert --execute`로 세 노트북을 처음부터 끝까지 실행했다. 세 노트북 모두 오류 셀 0개, 미실행 셀 0개, 종료 코드 0. 스트리밍 tok/s는 44.9 / 44.7 / 44.3(`eval_count / eval_duration`, Ollama가 잰 값).
- **특이사항:**
  - `langchain-ollama`의 `stream()`은 통계가 든 청크(`done=True`) 뒤에 내용 없는 청크를 하나 더 낸다. 그래서 "마지막 청크"가 아니라 `done`이 참인 청크에서 통계를 읽는다.
  - 청크 수(76·69·71)가 생성 토큰 수(78~90)보다 작다. 청크 하나가 항상 토큰 하나는 아니다. 노트북은 청크를 그대로 출력한다.
  - 03의 "첫 토큰까지" 2.09s는 모델 적재 시간이 섞인 값이다(01·02는 0.05s, 이미 적재된 상태).
  - 노트북은 `THINK=False`로 고정했다. 사고 과정 표시는 아직 미정이다(Phase 3 전에 정한다).
- **적대적 검증:** 아직 하지 않았다. 필수 통과 Phase가 아니다(Phase 2·3).

### Phase 2 — 공통 호출 층 (2026-10-04) — 구현 완료, 적대적 검증 대기

- **무엇을:** `src/local_chat/clients/`에 호출 층 3개(`ollama_client.py`·`langchain_client.py`·`http_client.py`)와 공유 이벤트(`events.py`)를 만들었다. 모두 `stream(messages, *, model, options)` 제너레이터이고 `Token`을 0개 이상, 마지막에 `Done`(통계) 또는 `Error`(kind: connection·model_not_found·other)를 정확히 하나 낸다. 도중에 `close()`하면 연결이 닫히고 마지막 이벤트 없이 끝난다. 콘솔 진입점 `python -m local_chat.console`이 세 방식을 차례로 돌려 토큰을 순차 출력하고 tok/s를 한 줄 출력한다.
- **결과:** `src/local_chat/`(패키지, uv_build)와 `tests/test_clients.py`. `pyproject.toml`에 pytest와 빌드 설정을 추가했다.
- **검증:**
  - 실제 Ollama(`qwen3:8b`)로 `python -m local_chat.console --client all`을 실행했다. 세 방식 모두 한글 토큰을 순차 출력하고 `[이름] N토큰 | 44.x tok/s`를 한 줄 출력했다.
  - 가짜 Ollama 서버 테스트 12개 통과: 같은 입력에 세 층이 같은 이벤트, 요청 본문(모델·옵션·메시지·think=False) 동일, done 뒤 빈 청크, 모델 없음, 서버 없음, 스트림 도중 오류줄, done 없이 끊김, 해석 불가 줄, 통계 없는 done, 중단 시 서버가 연결 끊김을 봄, 콘솔 출력·종료 코드.
- **특이사항:**
  - 테스트가 불일치 하나를 잡았다. 통계가 없는 `done` 청크를 http는 오류로 처리했는데 ollama·langchain은 `Done(None, None)`을 냈다. 공통 `make_done`으로 검증해 세 층이 모두 `Error`를 내게 고쳤다.
  - 콘솔 `run()`의 `out=sys.stdout` 기본값이 import 시점에 고정돼 출력 캡처가 안 되던 것을 `None` → 호출 시점 `sys.stdout`으로 고쳤다.
  - 한글 인코딩(Phase 2 콘솔): 진입점에서 stdout을 UTF-8로 맞춘다. HTTP는 응답을 UTF-8로 해석한다. 테스트에 한글·이모지 토큰을 넣었다.
  - 이 환경의 `uv run pytest`는 rtk가 출력을 줄여 "No tests collected"로 보인다. `rtk proxy uv run python -m pytest tests`로 원본 출력을 확인했다.
- **적대적 검증:** 필수 통과 Phase. 세션 내 리뷰어 → Codex 순서로 진행 예정.

## 계획 외 개선

### 00 분리 후 잔여 문구 정리 (2026-10-04)

- **요청:** 설치 Phase를 00-setup으로 분리했으므로 01-01 문서에 고칠 곳이 있는지 확인하고, 찾은 것(README Phase 번호, 연습 플랜 4절 실측 문구) 모두 수정.
- **조치:**
  - `README.md` 폴더 구조의 Phase 번호를 PLAN에 맞췄다(notebooks → Phase 1, src → Phase 2~5, 정할 시점 → Phase 2·3). "INIT 전인 지금은 …" 문단을 INIT 이후 상태로 바꿨다.
  - 연습 플랜 4절(`docs/labs/01-basics/01-local-chat.md`)의 "00-01 설치 후 `ollama ps`로 실측한다"를 "00-01은 `qwen3:4b`만 실측, `qwen3:8b`는 02-01에서 실측"으로 고치고, 사본 `docs/refs/01-local-chat.md`를 다시 복사해 맞췄다.
- **결과:** BRIEF·DECISIONS·PLAN은 바꾸지 않았다(이미 분리 후 상태).
- **검증:** `git diff`로 변경이 위 세 곳뿐임을 확인했고, README의 Phase 번호가 PLAN과 일치하며 `docs/refs/` 사본이 원본과 같음을 확인했다.

### 착수 후속 — ROADMAP 갱신·환경 구성 (2026-10-04)

- **요청:** "모두 승인" — INIT 보고에서 승인을 구한 ROADMAP 갱신과 Phase 1 진행.
- **조치:** `docs/ROADMAP.md` 진행 현황에서 01-01을 "진행 중 / v0.1"로 갱신했다. Phase 1 착수 때 이 연습의 uv 환경(`pyproject.toml`)을 만들었다. PLAN에는 환경 구성 task가 없지만 Phase 1 실행에 필요해, 00-02와 같은 방식(`uv init --bare` → 3.13 고정 → `uv add`)으로 했다. 프로젝트명은 숫자로 시작할 수 없어 `local-chat`이다.
- **결과:** ROADMAP 반영, 환경 생성. `<think>` 표시·Phase 2 콘솔 UTF-8 처리는 따로 정해진 바 없어 문서를 바꾸지 않았다.
- **검증:** `git diff`와 `uv run python --version`(3.13.14)으로 확인했다.

### Phase 1 적대적 검증 (2026-10-04)

- **요청:** "phase-1 도 적대적 검증 진행" (PLAN상 Phase 1은 필수 통과 Phase가 아니라 선택 검증).
- **조치:** 세션 내 리뷰어 → Codex `gpt-6.1-sol` 순서로 돌렸다. 기록은 `docs/reviews/A1.md`. 리뷰어의 Minor 2건(청크·토큰 설명 문구, 첫 토큰 시간에 적재 시간 포함 안내)은 세 노트북의 설명 셀만 고쳤다(코드·저장된 출력은 그대로).
- **결과:** Codex는 Critical·Major·Minor 없음(1/3회, 약 71초). 리뷰어는 Critical·Major 없음, Minor 4건 중 2건 수정·2건은 근거와 함께 유지. `pywebview` 선취(R5)는 사용자 결정 대기.
- **검증:** 수정은 마크다운 셀뿐이라 실행 결과에 영향이 없다. `git diff`로 세 노트북의 변경이 설명 셀 4곳뿐임을 확인했다.

### `pywebview` 의존성 선취 유지 (2026-10-04)

- **요청:** 적대적 검증(A1 R5)이 `pywebview`가 Phase 3용인데 Phase 1 환경에 미리 들어 있다고 지적하자, 사용자가 "pywebview 선취"로 답했다. 그대로 두는 것으로 해석했다.
- **조치:** 코드·의존성은 바꾸지 않았다. 선취 사유를 여기에 남긴다. 이 연습이 pywebview 앱이 목적이고(D-2) Phase 3에서 반드시 쓰며, 환경을 한 번에 만들어 `uv.lock`이 흔들리지 않게 하기 위해서다. 공통 코드를 미리 넓히는 일이 아니라 의존성 한 줄이라 BRIEF 4절을 어긴 것으로 보지 않는다.
- **결과:** `pyproject.toml`에 `pywebview`가 남는다. A1 R5는 이 결정으로 해소됐다.
- **검증:** `pyproject.toml`에 의존성이 그대로 있음을 확인했다.
