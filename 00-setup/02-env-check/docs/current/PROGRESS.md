> 버전: v0.1 · 작성일: 2026-10-04

# PROGRESS — 00-02 env-check

## 계획된 작업

(아직 없음. INIT 승인 후 Phase 1부터 기록한다.)

## 계획 외 개선

### BRIEF 초안 작성 (2026-10-04)

- **요청:** 00-02 프로젝트 폴더를 만들고 착수(INIT), BRIEF부터 작성.
- **조치:** `00-setup/02-env-check/` 폴더와 `BRIEF.md` 초안을 만들었다. 내용은 연습 플랜과 ROADMAP "넘길 것"에서만 가져왔고, 플랜에 미정인 점검 항목 확장·결과 파일 저장은 "미정"으로 두었다. `docs/current/PROGRESS.md`는 Stop hook이 요구해 INIT 4번 항목을 앞당겨 만들었다.
- **결과:** BRIEF.md는 연습 폴더 루트에 있고 사용자 확인 전이다. DECISIONS·PLAN·README는 아직 없다. INIT은 이 문서들이 갖춰져야 진행한다.
- **검증:** BRIEF 필수 블럭 4개(배경·풀고 싶은 문제·하지 않을 것·완료 조건)가 있고, v0.1이라 3번은 "해당 없음"이다. INTENT 3·4절(로컬 Ollama, 학습·파인튜닝 제외)에 어긋나지 않는다.

### BRIEF 4절 미정 항목 확정, DECISIONS 초안 작성 (2026-10-04)

- **요청:** BRIEF 4번의 미정 항목은 하지 않을 것으로 두고, 다음은 DECISIONS 작성.
- **조치:** BRIEF 4절의 마지막 항목을 "미정"에서 "하지 않을 것"(점검 확장·파일 저장)으로 고쳤다. `DECISIONS.md` 초안에 D-1~D-5를 썼다(Python CLI, uv·3.13 고정, 읽기 전용 API, 점검 범위, 출력·종료 코드).
- **결과:** BRIEF·DECISIONS가 연습 폴더 루트에 있다. PLAN·README는 아직 없다. D-2의 3.13 고정은 이번 대화에서 확인한 이 PC의 uv 상태(3.13.14·3.14.6)와 플랜 기술 스택을 근거로 내가 정리한 것이라 확인이 필요하다.
- **검증:** 모든 결정에 선택·근거·배제한 대안이 있다. 근거는 플랜·BRIEF·저장소 DECISIONS(R-9·R-10)·AGENTS.md에서 가져왔다. INTENT 3·4절에 어긋나지 않는다.

### D-2 확정, CUDA·winpython 결정(D-6) 추가 (2026-10-04)

- **요청:** D-2의 Python 3.13 확정. CUDA 환경과 winpython 환경이 필요한지 확인하고 그 결론을 DECISIONS에 반영.
- **조치:** `DECISIONS.md`에 D-6(CUDA 환경 없음, winpython 미사용)을 추가했다. D-2는 확정이라 내용을 바꾸지 않았다.
- **결과:** DECISIONS가 D-1~D-6이다. PLAN·README는 아직 없다.
- **검증:** D-6 근거를 `docs/refs/01-hardware.md`(2절 CUDA Toolkit 없음, 4절 winpython GPU 환경)와 대조했다. 연습 플랜·목록에 torch·cuda를 쓰는 연습이 없음을 grep으로 확인했다.

### PLAN 초안 작성 (2026-10-04)

- **요청:** 플랜(PLAN) 작성.
- **조치:** `PLAN.md` 초안을 썼다. Phase 1~3의 목적·완료 조건은 연습 플랜 3절을 그대로 옮겼고 BRIEF 완료 조건을 가리키게 했다. "적대적 검증" 절의 필수 통과 Phase는 사람이 정하는 것이라 "미정"으로 두었다. Phase별 공격 초점은 내가 초안으로 적었다.
- **결과:** BRIEF·DECISIONS·PLAN이 연습 폴더 루트에 있다. README는 아직 없다.
- **검증:** 모든 Phase에 완료 조건이 있고, 적대적 검증 절에 두 필드가 있다(필수 통과 Phase는 미정). 완료 조건은 연습 플랜 원문과 대조했다.

### PLAN 필수 통과 Phase 확정 (2026-10-04)

- **요청:** 필수 통과 Phase는 Phase 2만.
- **조치:** `PLAN.md` 적대적 검증 절의 "필수 통과 Phase"를 "미정"에서 "Phase 2"로 고쳤다. Phase 1·3도 검증은 하되 진행을 막지는 않는다.
- **결과:** PLAN의 미정 항목이 없다. README는 아직 없다.
- **검증:** `PLAN.md`에서 해당 줄이 바뀐 것을 grep으로 확인했다.

### README 초안 작성 (2026-10-04)

- **요청:** README 작성.
- **조치:** `README.md`에 개요만 썼다. 설치·사용법·요구 환경은 착수 시점에 쓰지 않는다(`DOC-SCHEMA.md` 9절). 내용은 BRIEF·연습 플랜·DECISIONS에서 가져왔다.
- **결과:** BRIEF·DECISIONS·PLAN·README가 연습 폴더 루트에 모였다. INIT 전제 확인 2·3번을 충족한다.
- **검증:** 개요가 BRIEF·DECISIONS와 어긋나지 않는지 대조했다(읽기 전용 점검, 모델 비적재, `--json`, uv·3.13).

### INIT 진행 (2026-10-04)

- **요청:** INIT 진행.
- **조치:** 모드 A(신규, v0.1)로 판별했다. 문서 검사 후 BRIEF·DECISIONS·PLAN을 `docs/current/`로 옮기고(README는 연습 폴더 루트에 둔다), 연습 플랜을 `docs/refs/`로 복사했다. `docs/ADVERSARIAL-REVIEW.md`(`workflow/docs/`에서 복사)와 빈 `docs/reviews/`를 만들었다. history 폴더와 `src/`는 만들지 않았다(첫 마감 때 생긴다).
- **결과:** `.gitignore`와 `.claude/`는 저장소 루트에 이미 있어 점검만 했다. 기준 커밋을 만들었다.
- **검증:** 문서 검사 목록(`DOC-SCHEMA.md` 10절) 전 항목 통과. 사본은 `cmp`로 원본과 같음을 확인했다.
