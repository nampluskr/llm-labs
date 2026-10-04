# 00-01 ollama-setup

## 개요

이 PC에 Ollama를 설치하고, GPU에서 모델이 도는지 확인하고, 연습에 쓰는 모델 7개를 받는 연습이다.
설치는 사용자가 설치 가이드를 보고 PowerShell 명령을 직접 실행하고, 에이전트는 읽기 전용 명령으로
결과를 확인만 한다. 코드는 없다.

가이드 끝의 기록표(버전·VRAM·PROCESSOR 등)를 채워, 이후 연습(특히 02-01 model-bench)이 예상값을
보정할 첫 근거로 삼는다. llm-labs의 다른 모든 연습의 전제이며, 실사용 제품이 아니라 연습용이다.

## 설치

`docs/refs/02-ollama-install-guide.md`를 보고 PowerShell에서 한 줄씩 직접 실행한다.

```powershell
winget install --id Ollama.Ollama --exact
```

설치가 끝나면 새 PowerShell을 열고 `ollama --version`이 `0.35.1` 이상인지 확인한다. 이 PC에서
v0.1 마감 때 확인한 버전은 0.35.1이다. 연습용 모델은 `ollama pull <모델>`로 받는다
(`qwen3:4b`, `qwen3:8b`, `exaone3.5:7.8b`, `bge-m3`, `gemma3:12b`, `qwen3:14b`, `qwen3:30b`).

## 사용법

```powershell
ollama list     # 받은 모델 목록
ollama ps       # 메모리에 올라간 모델과 PROCESSOR(GPU/CPU 비율)
ollama run qwen3:4b "한 문장으로 자기소개 해줘"
```

- 서버는 `http://127.0.0.1:11434`에서 응답한다. `/api/generate`와 `/api/tags`를 확인했다.
- `qwen3:4b`는 적재해서 `100% GPU`(VRAM 5043 MiB, 약 72.9 tok/s)를 확인했다. 나머지 6개 모델은
  받기만 했고 적재·PROCESSOR는 확인하지 않았다(02-01 model-bench에서 잰다).
- 결과 기록은 `docs/refs/02-ollama-install-guide.md` 끝의 기록표에 있다.

## 요구 환경

- Windows 11, NVIDIA GTX 1080 Ti(VRAM 11GB), 드라이버 570 이상(확인값 572.70)
- C: 여유 30GB 이상(모델 7개는 약 50GB)
- winget

---

이 연습이 속한 llm-labs가 무엇을 왜 하는가(SSOT)는 저장소 `docs/INTENT.md`에 있다.
현재 버전 문서는 `docs/current/`, 지난 버전은 `docs/history/`에 있다(INIT 후).
