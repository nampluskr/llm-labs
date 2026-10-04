# 00-02 env-check

## 개요

연습을 시작하기 전에 파이썬 개발 환경(uv, pywebview, jupyter)이 이 PC에서 동작하는지 확인하고,
Ollama 서버·받은 모델·GPU 적재 상태를 한 번에 점검하는 파이썬 CLI(`env-check`)를 만드는 연습이다.
점검은 읽기 전용 API만 쓰므로 모델을 적재하지 않고 VRAM을 추가로 쓰지 않는다. 결과는 점검 항목별
통과/실패와 전체 결과로 출력하고, `--json`으로 같은 내용을 JSON으로도 낸다.

00-01 ollama-setup에서 사람이 손으로 확인하던 것의 일부를 반복 실행할 수 있게 한 것이다. 연습마다
`pyproject.toml`을 두는 구조(uv, Python 3.13)가 이 PC에서 실제로 동작하는지도 이 연습에서 확인한다.
실사용 제품이 아니라 연습용이다.

## 설치

이 연습 폴더(`00-setup\02-env-check`)에서 uv로 환경을 만든다. Python 3.13은 `.python-version`에
고정돼 있어 uv가 받아 쓴다.

```powershell
uv sync
```

`ollama`, `pywebview`, `jupyter`, `ipykernel`과 테스트용 `pytest`가 이 폴더의 `.venv`에 설치된다.
`pywebview` 창과 `jupyter` 커널은 v0.1 Phase 1에서 이 환경에서 뜨는 것을 한 번 직접 확인했다
(창을 띄워 `loaded` 이벤트 확인, `nbconvert --execute`로 셀 한 개 실행). 이 확인은 일회성이었고,
`env-check` 명령이 매번 하는 점검에는 포함되지 않는다.

## 사용법

Ollama가 떠 있는 상태에서 실행한다. 점검은 읽기 전용이라 모델을 적재하지 않는다.

```powershell
uv run env-check          # 항목별 통과/실패와 전체 결과
uv run env-check --json   # 같은 내용을 JSON으로
```

점검 항목은 4개이고 서로 독립이다. 하나가 실패해도 나머지를 계속 점검한다.

| 항목 | 통과 조건 |
| --- | --- |
| 서버 연결 | `/api/version` 요청이 성공한다 |
| 버전 | 응답에 비어 있지 않은 `version`이 있다 |
| 받은 모델 | 목록을 읽었고 1개 이상이다 |
| 적재된 모델 | 목록을 읽었다(적재가 없어도 통과) |

출력 예(정상):

```
[통과] 서버 연결: http://127.0.0.1:11434
[통과] 버전: 0.35.1
[통과] 받은 모델: 7개
  qwen3:30b  18.6GB
  ...
[통과] 적재된 모델: 없음
결과: 통과 (4/4)
```

- 종료 코드는 전체 통과이면 `0`, 하나라도 실패이면 `1`이다. 알 수 없는 옵션은 `2`다.
- 서버에 연결하지 못하면 항목이 실패로 나오고, 오류 문구(`오류: Ollama 서버를 확인할 수 없다 ...`)가
  stderr에도 나간다.
- 적재된 모델의 `PROCESSOR`는 `ollama ps`와 같은 규칙(`100% GPU`, `100% CPU`, `25%/75% CPU/GPU` 등)이다.
- `--json`은 `ok`·`passed`·`total`·`checks`(항목마다 `name`·`ok`·`detail`·`data`)를 낸다. 한글은
  `\uXXXX`로 이스케이프돼 출력 인코딩과 무관하다.
- 서버 주소는 `http://127.0.0.1:11434`로 고정이고 바꾸는 옵션은 없다.
- 파이프나 리다이렉트로 화면 출력을 받으면 Windows 기본 인코딩(cp949)으로 나와 한글이 깨져 보일 수 있다.
  그때는 `$env:PYTHONUTF8 = "1"`을 설정하거나 `--json`을 쓴다.

테스트는 같은 폴더에서 `uv run pytest`로 돌린다. 테스트는 가짜 Ollama 클라이언트와 로컬 임시 서버를 쓰므로
실제 Ollama 서버가 없어도 통과한다.

## 요구 환경

- Windows 11
- uv (이 PC에서 확인한 버전 0.11.29). Python 3.13은 uv가 받는다.
- 실행 중인 Ollama와 받은 모델 1개 이상 (00-01 ollama-setup 참고. 확인한 Ollama 버전은 0.35.1)
- GPU와 CUDA는 점검 도구가 직접 쓰지 않는다. GPU는 Ollama가 쓰고 NVIDIA 드라이버만 있으면 된다.
- `pywebview` 창 확인에는 Windows 데스크톱 환경이 필요하다.

---

이 연습이 속한 llm-labs가 무엇을 왜 하는가(SSOT)는 저장소 `docs/INTENT.md`에 있다.
현재 버전 문서는 `docs/current/`에 있다. 지난 버전 기록은 첫 마감 때 생긴다.
