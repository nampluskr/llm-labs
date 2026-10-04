> 버전: v0.1 · 작성일: 2026-10-04

# 07-04 backlog-assist — 자연어로 backlog task 초안 만들기

## 1. 개요

"로그인 화면에 비밀번호 표시 토글 추가, 테스트 포함" 같은 자연어를 `backlog.json`의 task 초안으로
바꾸고, `backlog validate`로 검증한 뒤 사람이 승인하면 `backlog add`로 넣는 CLI다.
04-02 json-extractor의 추출 모듈을 쓰고, 검증은 기존 `backlog` 도구에 맡긴다.

- 기존 도구의 데이터 계약(SPEC)을 스키마로 옮기기
- LLM 출력 → 기존 검증기 통과 → 승인 → 반영
- 기존 도구를 고치지 않고 바깥에서 쓰기

## 2. 기술 스택

| 항목 | 내용 |
| --- | --- |
| 런타임 | Python CLI |
| 언어·패키지 | Python 3.13(uv), `ollama`, `pydantic`, 04-02 추출 모듈, `backlog` CLI 호출 |
| Ollama API | `/api/chat`(`format`) |
| 모델 | `qwen3:8b` |
| num_ctx | 4096 |

## 3. 간단한 플랜

| Phase | 목적 | 완료 조건 |
| --- | --- | --- |
| 1 | 초안 | 자연어 10건이 `backlog` SPEC의 task 필드를 갖춘 JSON 초안으로 바뀐다 |
| 2 | 검증 | 초안을 임시 파일에 넣고 `backlog validate`를 돌려, 10건 중 통과 건수와 실패 사유를 출력한다 |
| 3 | 반영 | 승인한 초안만 `backlog add`로 들어가고, 이후 `backlog validate`가 오류 0으로 끝난다 |

## 4. 하드웨어 메모

- 짧은 입력·출력이라 VRAM·시간 부담이 적다.

## 5. 미정

- 결과를 `backlog`의 새 버전으로 옮길지(INTENT 3절) — 연습을 끝낸 뒤 판단. `backlog`는 표준 라이브러리만 쓰는 원칙이 있어 그대로는 옮길 수 없다
