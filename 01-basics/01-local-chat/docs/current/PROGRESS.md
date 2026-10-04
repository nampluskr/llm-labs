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

### Phase 2 — 공통 호출 층 (2026-10-04) — 완료

- **무엇을:** `src/local_chat/clients/`에 호출 층 3개(`ollama_client.py`·`langchain_client.py`·`http_client.py`)와 공유 이벤트(`events.py`)를 만들었다. 모두 `stream(messages, *, model, options)` 제너레이터이고 `Token`을 0개 이상, 마지막에 `Done`(통계) 또는 `Error`(kind: connection·model_not_found·other)를 정확히 하나 낸다. 도중에 `close()`하면 연결이 닫히고 마지막 이벤트 없이 끝난다. 콘솔 진입점 `python -m local_chat.console`이 세 방식을 차례로 돌려 토큰을 순차 출력하고 tok/s를 한 줄 출력한다.
- **결과:** `src/local_chat/`(패키지, uv_build)와 `tests/test_clients.py`. `pyproject.toml`에 pytest와 빌드 설정을 추가했다.
- **검증:**
  - 실제 Ollama(`qwen3:8b`)로 `python -m local_chat.console --client all`을 실행했다. 세 방식 모두 한글 토큰을 순차 출력하고 `[이름] N토큰 | 44.x tok/s`를 한 줄 출력했다.
  - 가짜 Ollama 서버 테스트 통과(최종 18개; 아래 적대적 검증 보완 포함). 처음 12개: 같은 입력에 세 층이 같은 이벤트, 요청 본문(모델·옵션·메시지·think=False) 동일, done 뒤 빈 청크, 모델 없음, 서버 없음, 스트림 도중 오류줄, done 없이 끊김, 해석 불가 줄, 통계 없는 done, 중단 시 서버가 연결 끊김을 봄, 콘솔 출력·종료 코드.
- **특이사항:**
  - 테스트가 불일치 하나를 잡았다. 통계가 없는 `done` 청크를 http는 오류로 처리했는데 ollama·langchain은 `Done(None, None)`을 냈다. 공통 `make_done`으로 검증해 세 층이 모두 `Error`를 내게 고쳤다.
  - 콘솔 `run()`의 `out=sys.stdout` 기본값이 import 시점에 고정돼 출력 캡처가 안 되던 것을 `None` → 호출 시점 `sys.stdout`으로 고쳤다.
  - 한글 인코딩(Phase 2 콘솔): 진입점에서 stdout을 UTF-8로 맞춘다. HTTP는 응답을 UTF-8로 해석한다. 테스트에 한글·이모지 토큰을 넣었다.
  - 이 환경의 `uv run pytest`는 rtk가 출력을 줄여 "No tests collected"로 보인다. `rtk proxy uv run python -m pytest tests`로 원본 출력을 확인했다.
- **적대적 검증:** 필수 통과 Phase. 세션 내 리뷰어(Critical·Major 없음, Minor 4건 모두 반영) → Codex `gpt-6.1-sol` 2회(2/3). 기록은 `docs/reviews/A2.md`.
  - Critical 없음. Major 3·Minor 2(1회차)와 Major 2·Minor 2(2회차) 중 오류 본문의 비문자열 `error`(예외 누출), SDK 층 읽기 타임아웃 없음, 비문자열 `content`, 콘솔 인코딩·flush 테스트 공백, 테스트 멈춤 가능성을 고쳤다.
  - 고치지 않은 것: 프로토콜을 어긴 응답(통계가 문자열, 빈 줄)에서 SDK와 HTTP의 성공/오류 판정이 다른 점, 실패 시 tok/s 줄 없음. 근거는 A2의 "유효하지 않은 지적과 반박 근거".
  - 알려진 한계: 막힌 `next()`는 다른 스레드의 `close()`로 못 끊는다(읽기 타임아웃 300초가 상한). Phase 3 UI는 작업 스레드 + 중단 플래그를 써야 한다.
  - 검증 도중 호출 층에 `read_timeout` 인자(기본 300초)가 생겼다. Phase 2 완료 조건에는 없던 것이지만 세 층의 종료 동등성을 위해 필요했다.

### Phase 3 — 채팅 화면(앱 3개) (2026-10-04) — 구현 완료, 적대적 검증 대기

- **무엇을:** pywebview 화면 하나(`ui/index.html`)와 화면과 분리된 대화 세션(`session.py`)을 만들고, 호출 층마다 앱 진입점을 만들었다(`app_ollama.py`·`app_langchain.py`·`app_http.py`, `webapp.py`가 공통). 실행은 `uv run local-chat-ollama`·`local-chat-langchain`·`local-chat-http`(또는 `python -m local_chat.app_*`). 세션은 작업 스레드에서 호출 층을 돌려 토큰을 `evaluate_js`로 화면에 밀어 넣고, 질문마다 시스템 + 직전 10턴(질문·답 쌍) + 새 질문을 보낸다. 답변 중 다시 질문하면 거절하고(보내기 버튼도 막힘), 중단 버튼과 창 닫기는 스트리밍을 멈춘다.
- **결과:** `src/local_chat/{session,webapp,defaults,app_*}.py`, `src/local_chat/ui/index.html`, `tests/{test_session,test_gui}.py`·`gui_driver.py`·`fake_ollama.py`·`conftest.py`. 기본값(`defaults.py`)을 콘솔과 앱이 같이 쓴다.
- **검증:**
  - 테스트 51개 통과(호출 층 18, 세션 18, 실제 pywebview 창 15 = 앱 3개 × 5 시나리오). 세션 테스트는 12턴 뒤 요청에 직전 10턴만 실리는지(대역과 실제 호출 층 3개 모두 가짜 서버로), 이벤트 순서, 중복 질문 거절, 중단(서버가 막힌 상태 포함), 오류 처리, emit 실패(창 닫힘)를 확인한다.
  - GUI 테스트는 앱 3개 각각 실제 창을 띄워 `evaluate_js`로 확인한다: 답변 글자 수가 단계적으로 늘고 끝나면 `N토큰 · X tok/s`와 입력이 돌아오는지, 두 번째 요청에 첫 턴이 문맥으로 실렸는지, 모델 없음 오류 표시와 재질문, 서버가 멈춰도 중단 버튼이 3초 안에 듣고 다음 질문이 나가는지, 12번 이어 질문하면 마지막 요청에 직전 10턴만 실리는지, 모델 출력의 HTML이 글자 그대로 보이는지.
  - 실제 Ollama(`qwen3:8b`)로 앱 3개를 같은 방식으로 구동했다. 세 앱 모두 두 질문에 응답이 단계적으로 표시됐고 44~47 tok/s가 표시됐다.
- **특이사항:**
  - 테스트가 경합 하나를 잡았다. 종료 이벤트를 받은 직후 다음 질문을 보내면 `join()`이 아직 시작하지 않은 스레드를 기다렸다. `join`을 "종료 이벤트 emit까지 끝난 상태" 이벤트 기준으로 바꾸고, 종료 이벤트 emit 전에 기록 갱신과 busy 해제를 끝내게 했다.
  - 화면 표시의 `2.0 tok/s`가 JS에서 `2`로 나오던 것을 `toFixed(1)`로 고쳤다.
  - 정한 동작(PLAN에 없던 세부): 답변 중 새 질문은 거절한다(중단하고 보내기는 하지 않음). 실패한 턴은 문맥에 남기지 않고, 사용자가 중단한 턴은 받은 데까지 남긴다(받은 게 없으면 남기지 않음). 모델 출력은 `textContent`로만 넣어 HTML로 해석하지 않는다.
- **세션 내 리뷰어 지적과 처리:** 완료 조건 충족, Critical 없음, Major 1·Minor 3.
  - Major — 중단 버튼이 호출 층의 막힌 읽기를 못 끊어 화면이 최대 300초 busy로 남음. **수정.** `stop()`이 직접 기록을 확정하고 `stopped`를 즉시 emit하며, 그 턴의 작업 스레드는 취소 표시가 붙어 뒤에서 정리만 한다(이후 이벤트 버림, emit 직렬화로 `stopped` 뒤에 토큰이 끼지 않음). 막힌 스레드가 남아 있어도 새 질문을 받는다.
  - Minor — `gui_driver`의 죽은 `scenario` 인자와 항상 참인 `user_html_escaped`. **수정.** 시나리오(ok·stop·many·escape)로 실제 사용하고, HTML 이스케이프를 실제로 검증한다.
  - Minor — GUI 테스트에 중단 버튼·11턴 이상 시나리오 없음. **수정.** 위 시나리오로 추가했다.
  - Minor — `tests/` 아래 `.pyc`. 저장소 `.gitignore`가 무시하므로 처리하지 않았다.
  - 범위 초과 지적(중단 버튼, `--host`·`--model` 인자, 헤더의 `num_ctx`·`temperature` 표시): 중단은 "답변 중 다시 질문"과 창 닫기 정리를 위한 것이고, `--host`는 가짜 서버로 시험하는 데 필요하며, 헤더 표시는 읽기 전용이다. 모델 전환·옵션 조절·저장은 만들지 않았다(Phase 4·5).
- **적대적 검증:** 필수 통과 Phase. Codex 진행 예정.

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

### `<think>` 결정 D-10 작성 (2026-10-04)

- **요청:** 사고 과정 표시 여부를 어떻게 할지 묻자, 사용자가 "표시하지 않고 `think=False` 고정" 제안에 동의했다.
- **조치:** `docs/current/DECISIONS.md`에 D-10(qwen3 사고 과정)을 추가했다. 선택·근거·배제한 대안(접어서 표시, 항상 표시)은 제안한 그대로다. 다른 문서는 바꾸지 않았다. 연습 플랜 5절의 "미정" 문구는 그대로다.
- **결과:** 사고 과정 표시 기능은 v0.1에 만들지 않는다.
- **검증:** D-10에 필수 필드(선택·근거·배제한 대안)가 모두 있음을 확인했다.
