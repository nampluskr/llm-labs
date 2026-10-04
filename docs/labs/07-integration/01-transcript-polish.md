> 버전: v0.1 · 작성일: 2026-10-04

# 07-01 transcript-polish — 전사 결과 다듬기·요약·번역

## 1. 개요

`speech_transcriber`가 낸 verbatim SRT를 받아 문장부호 복원, 군말 제거, 요약, 번역을 하는 후처리 도구다.
`speech_transcriber` README는 "LLM 없음(문장부호 복원·군말 제거·요약·번역을 하지 않는다)"고 적고 있는데,
바로 그 빠진 단계를 로컬 LLM으로 채운다.

- SRT 자막 묶음 단위 처리(타임코드 유지)
- 원문을 바꾸지 않고 "정리본"을 따로 내기
- 긴 전사의 구간 요약 → 전체 요약

## 2. 기술 스택

| 항목 | 내용 |
| --- | --- |
| 런타임 | Python CLI(`speech_transcriber`의 출력 파일을 입력으로 받는 별도 단계) |
| 언어·패키지 | Python 3.13(uv), `ollama`, `srt` |
| Ollama API | `/api/chat` |
| 모델 | `exaone3.5:7.8b`(한국어), `qwen3:8b`(비교) |
| num_ctx | 8192 |

## 3. 간단한 플랜

| Phase | 목적 | 완료 조건 |
| --- | --- | --- |
| 1 | 문장부호·군말 | 자막 N줄 묶음 단위로 정리한 SRT를 내고, 자막 개수와 각 타임코드가 원본과 같다 |
| 2 | 요약 | 10분 구간별 요약과 전체 요약을 `summary.md`로 낸다 |
| 3 | 번역 | 한→영 또는 영→한 번역 SRT를 내고, 자막 개수·타임코드가 원본과 같다 |

## 4. 하드웨어 메모

- `speech_transcriber`(faster-whisper)와 Ollama를 동시에 돌리면 VRAM을 나눠 쓴다. 전사가 끝난 뒤 후처리를 실행한다.

## 5. 미정

- 결과를 `speech_transcriber`의 새 버전으로 옮길지(INTENT 3절) — 연습을 끝낸 뒤 판단
