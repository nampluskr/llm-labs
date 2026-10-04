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

```
01-local-chat/
├── README.md
├── pyproject.toml           uv 환경 — 연습마다 하나 (저장소 DECISIONS R-10)
├── notebooks/               세 호출 방식 공부용 (D-9)
│   ├── 01-ollama.ipynb
│   ├── 02-langchain-ollama.ipynb
│   └── 03-http-api.ipynb
├── src/local_chat/
│   ├── clients/             호출 층 3개, 같은 인터페이스 — 이후 연습이 복사해 가는 공통 코드 (D-1·D-3)
│   │   ├── events.py        Token·Thinking·Done·Error 이벤트와 인터페이스
│   │   ├── ollama_client.py
│   │   ├── langchain_client.py
│   │   └── http_client.py
│   ├── session.py           화면과 분리된 대화 세션: 직전 10턴 문맥, 스트리밍, 중단
│   ├── conversation.py      대화 저장·불러오기 형식과 검증 (D-7)
│   ├── models.py            설치된 모델 목록, 모델 내리기
│   ├── capabilities.py      모델 능력 조회(사고 과정 지원 여부)
│   ├── options.py           num_ctx·temperature 검증
│   ├── webapp.py            pywebview 창과 JS에 공개하는 API
│   ├── ui/index.html        화면 하나 (D-2)
│   ├── console.py           호출 층을 콘솔에서 시험
│   └── app_ollama.py · app_langchain.py · app_http.py   앱 진입점 3개
├── tests/                   가짜 Ollama 서버로 도는 테스트와 실제 창을 띄우는 GUI 테스트
└── docs/
    ├── current/             BRIEF · DECISIONS · PLAN · PROGRESS
    ├── refs/                연습 플랜 사본 (docs/labs/01-basics/01-local-chat.md)
    ├── ADVERSARIAL-REVIEW.md
    ├── reviews/             반대 벤더 검토 기록 (A1~A5)
    └── history/v0.1/        마감한 버전 문서, 불변
```

## 설치

이 연습 폴더(`01-basics\01-local-chat`)에서 uv로 환경을 만든다. Python 3.13은 `.python-version`에
고정돼 있어 uv가 받아 쓴다.

```powershell
uv sync
```

`ollama`, `langchain-ollama`, `httpx`, `pywebview`, `jupyter`, `ipykernel`과 테스트용 `pytest`가 이 폴더의
`.venv`에 설치된다. Ollama 설치와 모델 받기는 이 연습에 포함되지 않는다(00-01 ollama-setup).

## 사용법

Ollama가 떠 있고 모델이 받아져 있는 상태에서 실행한다. 앱은 호출 방식마다 하나씩 3개이고 화면은 같다.

```powershell
uv run local-chat-ollama      # 공식 ollama 파이썬 클라이언트
uv run local-chat-langchain   # langchain-ollama
uv run local-chat-http        # HTTP API 직접 호출(httpx)
```

옵션은 `--host`(기본 `http://localhost:11434`)와 `--model`(기본 `qwen3:8b`)이다.

**대화**
- 질문을 쓰고 Enter(줄바꿈은 Shift+Enter) 또는 "보내기"를 누르면 답이 토큰 단위로 흘러나오고, 끝나면 `N토큰 · X tok/s`가
  보인다. "중단"으로 답변을 멈출 수 있다. 답변 중에는 새 질문을 보낼 수 없다.
- 직전 대화 10턴(질문·답 쌍)이 문맥으로 함께 전달된다. 시스템 메시지는 항상 붙는다.
- 모델이 사고 과정을 지원하면 답 위의 접이식 블록에 보인다. 생각하는 동안은 펼쳐지고 답이 시작되면 접히며 다시 펼 수 있다.
  사고 과정은 문맥과 저장 파일에 들어가지 않는다(D-10).

**모델과 옵션**
- 드롭다운에 `/api/tags`의 모든 모델이 보인다. 임베딩 모델은 "채팅 불가"로 표시돼 고를 수 없다. 모델을 바꾸면 이전 모델을
  메모리에서 내리고(`keep_alive: 0`, D-6) 다음 질문부터 새 모델로 답한다. 이전 모델을 내리지 못하거나 이전 답변 요청이 아직
  끝나지 않았으면 바꾸지 않고 이유를 보인다. 대화는 모델을 바꿔도 이어진다.
- `num_ctx`(4096~8192)와 `temperature`(0~2)는 다음 질문부터 요청에 실린다. 범위 밖 값은 고쳐서 받지 않고 거절한다.
- 답변 중과 모델 전환 중에는 모델·옵션 입력이 잠긴다.

**대화 저장**
- "대화 저장"은 끝난 대화를 JSON 파일로 쓰고, "대화 열기"는 파일의 대화로 현재 대화를 통째로 바꾼다(합치지 않는다). 열어도
  현재 모델과 옵션은 바뀌지 않는다. 답변 중과 모델 전환 중에는 쓸 수 없다.
- 파일은 UTF-8이고 한글을 이스케이프하지 않는다. `{"format": "local-chat", "version": 1, "saved_at", "model", "messages": [{"role", "content"}, ...]}`
  모양이며, `messages`는 질문(user)과 답(assistant)이 번갈아 온다. 저장은 임시 파일에 쓴 뒤 교체하므로 도중에 실패해도 기존 파일이
  손상되지 않는다.
- 손상된 파일(깨진 JSON, 질문·답 순서 오류, 빈 메시지, UTF-8이 아닌 파일, 짝 없는 서로게이트, 10MB 초과 등)은 이유를 보이며
  거절하고 현재 대화는 그대로 둔다.

**콘솔과 노트북**

```powershell
uv run python -m local_chat.console --client all     # 세 호출 층을 차례로 돌려 토큰을 출력하고 tok/s를 한 줄 출력
uv run jupyter lab notebooks                          # 세 호출 방식의 기본 코드(비스트리밍·스트리밍·멀티턴)
```

**테스트**

```powershell
uv run pytest                    # 호출 층·세션·형식·Api 등(가짜 Ollama 서버. 실제 Ollama 없이 통과)
```

`tests/test_gui.py`는 앱 3개마다 실제 pywebview 창을 띄워 조작하므로 오래 걸리고(전체 약 10분) 화면에 창이 잠깐씩 뜬다.

**알려진 한계**
- 서버가 응답을 멈추면 진행 중인 요청을 끊을 수 없다. 이때 모델 전환은 거절되고, 서버가 풀리거나 읽기 시간 제한(300초)이
  지나야 다시 바꿀 수 있다.
- 모델 목록은 창을 열 때 한 번 읽는다. 새로 받은 모델은 앱을 다시 열어야 보인다(모델 받기·삭제는 01-03 model-manager).
- 파일 대화상자(`create_file_dialog`)는 자동 시험하지 못했다. 시험은 대화상자 대신 경로를 돌려주는 함수로 대신했다.
- 모델 목록 조회와 모델 내리기는 세 호출 방식 각각이 아니라 공통 `httpx` 한 경로로 보낸다.

## 요구 환경

- Windows 10/11, WebView2 런타임(pywebview가 사용). 개발·확인은 Windows 11에서 했다.
- uv와 Python 3.13(uv가 받아 쓴다).
- Ollama가 `http://localhost:11434`에서 실행 중이어야 한다(0.35.1에서 확인했다).
- 기본 모델 `qwen3:8b`가 받아져 있어야 한다(`qwen3:4b`, `exaone3.5:7.8b` 등 받아 둔 다른 모델은 드롭다운에서 고른다).
  `qwen3:8b`는 4096 컨텍스트에서 VRAM 약 5.2GB를 쓴다(이 PC의 GTX 1080 Ti 11GB에서 `ollama ps`로 확인).
- 클라우드 LLM API는 쓰지 않는다. 모든 호출은 이 PC의 Ollama로 간다.

---

이 연습이 속한 llm-labs가 무엇을 왜 하는가(SSOT)는 저장소 `docs/INTENT.md`에 있다.
현재 버전 문서는 `docs/current/`, 지난 버전은 `docs/history/`에 있다.
