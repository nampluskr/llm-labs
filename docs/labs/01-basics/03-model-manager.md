> 버전: v0.1 · 작성일: 2026-10-04

# 01-03 model-manager — Ollama 모델 관리 GUI

## 1. 개요

받은 모델 목록, 각 모델의 크기·양자화·컨텍스트, 지금 메모리에 올라간 모델과 GPU/CPU 비율을
한 화면에 보여 주는 pywebview 앱이다. 모델 받기(진행률)·내리기·삭제도 여기서 한다.
`ollama list`·`ps`·`pull`·`rm`을 GUI로 옮긴 것이다. 모든 UI는 pywebview로 만든다(저장소 DECISIONS R-9).

- Ollama 관리 API 전반
- 스트리밍 진행률(NDJSON) 파싱
- 주기적 폴링으로 상태 갱신

## 2. 기술 스택

| 항목 | 내용 |
| --- | --- |
| 런타임 | Python + pywebview |
| 언어·패키지 | Python 3.13(uv), `ollama`, `pywebview` |
| Ollama API | `/api/tags`, `/api/ps`, `/api/show`, `/api/pull`(stream), `/api/delete`, `/api/generate`(`keep_alive: 0`으로 내리기) |
| 모델 | 해당 없음(관리 대상은 받은 모델 전부) |
| num_ctx | 해당 없음 |

## 3. 간단한 플랜

| Phase | 목적 | 완료 조건 |
| --- | --- | --- |
| 1 | 목록·상태 | 표의 행 수가 `ollama list` 출력의 모델 수와 같다. 적재된 모델은 `ollama ps`와 같은 PROCESSOR 값을 보인다 |
| 2 | 받기 | 모델 이름을 입력해 받으면 진행률이 0→100%로 갱신되고, 끝나면 목록에 행이 추가된다 |
| 3 | 내리기·삭제 | "내리기" 후 5초 안에 `ollama ps`에서 사라진다. "삭제"는 확인 대화 뒤에만 실행되고 목록에서 행이 빠진다 |

## 4. 하드웨어 메모

- 앱 자체는 VRAM을 쓰지 않는다. 다만 pywebview(WebView2) 창도 GPU 가속 화면을 쓰므로 VRAM을 수백 MB 차지할 수 있다(01-hardware 1절의 "평상시 1.8GB"에 포함되는 종류).
- 상태 폴링은 2~5초 간격이면 충분하다.

## 5. 미정

없음
