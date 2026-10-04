# 01-01 local-chat

## 개요

이 PC에서 Ollama로 돌리는 로컬 LLM과 대화하는 pywebview 채팅 앱이다. 답변이 토큰 단위로 흘러나오고,
대화 중에 모델을 바꿀 수 있으며, 대화를 JSON 파일로 저장·불러온다.

같은 채팅 앱을 Ollama 호출 방식 세 가지 — 공식 `ollama` 파이썬 클라이언트, `langchain-ollama`,
HTTP API 직접 호출 — 로 각각 만들어 방식마다 무엇이 다른지 비교한다. 앱에 앞서 세 방식의 기본
코드를 공부할 Jupyter 노트북도 함께 둔다.

llm-labs의 첫 연습이며, 여기서 만든 Ollama 호출·스트리밍 코드는 이후 연습이 복사해 쓴다. 실사용
제품이 아니라 연습용이다.

## 폴더 구조

v0.1을 마감할 때의 예정 구조다. `*` 표시는 아직 정하지 않은 이름·배치로, Phase 2·3 착수 때 정한다.

```
01-local-chat/
├── README.md
├── pyproject.toml           uv 환경 — 연습마다 하나 (저장소 DECISIONS R-10)
├── docs/                    INIT 때 생성
│   ├── current/             BRIEF · DECISIONS · PLAN · PROGRESS
│   ├── refs/                연습 플랜 사본 (docs/labs/01-basics/01-local-chat.md)
│   ├── ADVERSARIAL-REVIEW.md
│   ├── reviews/             반대 벤더 검토 기록
│   └── history/v0.1/        마감 때 current 복사, 불변
├── notebooks/               Phase 1 — 세 호출 방식 공부용 (D-9)
│   ├── 01-ollama.ipynb
│   ├── 02-langchain-ollama.ipynb
│   └── 03-http-api.ipynb
├── src/ *                   Phase 2~5
│   ├── clients/ *           호출 층 3개, 같은 인터페이스 — 이후 연습이 복사해 가는 공통 코드 (D-1·D-3)
│   │   ├── ollama_client.py *
│   │   ├── langchain_client.py *
│   │   └── http_client.py *
│   ├── ui/ *                pywebview 화면 하나 (D-2)
│   └── app_*.py *           진입점 3개 — 호출 방식마다 앱 하나
└── tests/ *                 첫 필요 시점에
```

현재 `docs/current/`에 `BRIEF.md`·`DECISIONS.md`·`PLAN.md`·`PROGRESS.md`가 있고, 연습 플랜 사본은 `docs/refs/`에 있다.
구현은 Phase 1(노트북)부터 시작하며, 위 구조는 진행하면서 채워진다.

## 설치

<!-- 버전 마감 때 갱신한다. 실제로 되는 것만 적는다. -->

## 사용법

<!-- 버전 마감 때 갱신한다. 실제로 동작하는 것만 적는다. -->

## 요구 환경

<!-- 버전 마감 때 갱신한다. -->

---

이 연습이 속한 llm-labs가 무엇을 왜 하는가(SSOT)는 저장소 `docs/INTENT.md`에 있다.
현재 버전 문서는 `docs/current/`, 지난 버전은 `docs/history/`에 있다(INIT 후).
