> 버전: v0.1 · 작성일: 2026-10-04

# PROGRESS — 01-01 local-chat

## 계획된 작업

## 계획 외 개선

### 00 분리 후 잔여 문구 정리 (2026-10-04)

- **요청:** 설치 Phase를 00-setup으로 분리했으므로 01-01 문서에 고칠 곳이 있는지 확인하고, 찾은 것(README Phase 번호, 연습 플랜 4절 실측 문구) 모두 수정.
- **조치:**
  - `README.md` 폴더 구조의 Phase 번호를 PLAN에 맞췄다(notebooks → Phase 1, src → Phase 2~5, 정할 시점 → Phase 2·3). "INIT 전인 지금은 …" 문단을 INIT 이후 상태로 바꿨다.
  - 연습 플랜 4절(`docs/labs/01-basics/01-local-chat.md`)의 "00-01 설치 후 `ollama ps`로 실측한다"를 "00-01은 `qwen3:4b`만 실측, `qwen3:8b`는 02-01에서 실측"으로 고치고, 사본 `docs/refs/01-local-chat.md`를 다시 복사해 맞췄다.
- **결과:** BRIEF·DECISIONS·PLAN은 바꾸지 않았다(이미 분리 후 상태).
- **검증:** `git diff`로 변경이 위 세 곳뿐임을 확인했고, README의 Phase 번호가 PLAN과 일치하며 `docs/refs/` 사본이 원본과 같음을 확인했다.
