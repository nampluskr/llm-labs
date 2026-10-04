> 버전: v0.1 · 작성일: 2026-10-04

# 01-04 modelfile-studio — 나만의 모델 만들기·테스트

## 1. 개요

기반 모델 + 시스템 프롬프트 + 파라미터(`num_ctx`·`temperature`·`stop` 등)를 묶은 Modelfile을
화면에서 편집하고, `ollama create`로 새 모델 태그를 만든 뒤 바로 테스트 질문을 보내는 앱이다.
예: "한국어로만 답하는 요약가", "커밋 메시지 작성기".

- Modelfile 문법(FROM, SYSTEM, PARAMETER, TEMPLATE)
- 모델 태그는 가중치를 복사하지 않고 설정만 덧입힌다는 점
- 같은 질문에 대한 기반 모델과 새 모델의 응답 비교

## 2. 기술 스택

| 항목 | 내용 |
| --- | --- |
| 런타임 | Python + pywebview |
| 언어·패키지 | Python 3.13(uv), `ollama`, `pywebview` |
| Ollama API | `/api/create`, `/api/show`, `/api/chat`, `/api/delete` |
| 모델 | 기반: `exaone3.5:7.8b`, `qwen3:4b` |
| num_ctx | Modelfile에서 지정(기본 4096) |

## 3. 간단한 플랜

| Phase | 목적 | 완료 조건 |
| --- | --- | --- |
| 1 | Modelfile 생성 | 화면 입력으로 Modelfile 텍스트를 만들고 `/api/create` 후 `ollama list`에 새 태그가 생긴다 |
| 2 | 비교 테스트 | 같은 질문을 기반 모델과 새 모델에 보내 두 답을 나란히 보여 준다 |
| 3 | 프리셋 관리 | Modelfile 프리셋 3개 이상을 파일로 저장·불러오고, 불러온 프리셋으로 다시 만들 수 있다 |

## 4. 하드웨어 메모

- 새 태그는 기반 모델의 가중치를 공유하므로 디스크를 거의 더 쓰지 않는다.
- Modelfile에서 `num_ctx`를 크게 잡으면 그 모델은 항상 큰 KV cache를 쓴다. 8192를 넘기면 `ollama ps`로 GPU 적재를 확인한다.

## 5. 미정

없음
