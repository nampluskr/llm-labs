> 버전: v0.1 · 작성일: 2026-10-04

# Ollama 설치 가이드 — 터미널에서 직접 따라 하기

> 에이전트 없이 사람이 PowerShell에 명령을 **한 줄씩** 입력하며 설치한다.
> 각 단계는 **입력 → 기대 결과 → 다르면** 순서로 되어 있다. 기대 결과와 같을 때만 다음
> 단계로 넘어간다. 마지막의 "기록표"에 결과를 적어 두면 이후 연습 프로젝트의 근거가 된다.
>
> 기준 환경: Windows 11 Pro · GTX 1080 Ti(VRAM 11GB) · 드라이버 572.70 · Ollama 0.35.1
> (작성일 기준. 하드웨어 실측은 `01-hardware.md`)

---

## 준비 — PowerShell 열기

시작 메뉴에서 **Windows PowerShell**(또는 Windows Terminal)을 연다. 관리자 권한은 필요 없다.

---

## 1단계 — 설치 전 확인

### 1-1. GPU 드라이버 버전

```powershell
nvidia-smi --query-gpu=name,driver_version,compute_cap --format=csv,noheader
```

**기대 결과**
```
NVIDIA GeForce GTX 1080 Ti, 572.70, 6.1
```

**다르면** — 드라이버가 **570 미만**이면 Ollama가 이 GPU를 쓰지 못한다. NVIDIA 드라이버를
570 이상으로 올린 뒤 다시 확인한다. 572.70 이상이면 그대로 진행한다(드라이버를 일부러
올리지 않는다).

### 1-2. 디스크 여유 (C:)

```powershell
[math]::Round((Get-PSDrive C).Free/1GB)
```

**기대 결과** — `30` 이상의 숫자 (작성일 실측 약 520). 모델은 기본적으로 C:에 저장된다.

**다르면** — 30 미만이면 C:를 정리하거나, 6단계의 `OLLAMA_MODELS`로 저장 위치를 다른
드라이브로 바꾼다.

### 1-3. 포트 11434가 비어 있는지

```powershell
Get-NetTCPConnection -LocalPort 11434 -ErrorAction SilentlyContinue
```

**기대 결과** — 아무것도 출력되지 않는다.

**다르면** — 무언가 11434 포트를 쓰고 있다. 이미 Ollama가 설치돼 있을 수 있으니
`Get-Command ollama`로 확인한다.

### 1-4. Ollama가 아직 없는지

```powershell
Get-Command ollama -ErrorAction SilentlyContinue
```

**기대 결과** — 아무것도 출력되지 않는다.

**다르면** — 이미 설치돼 있다. 3단계(설치 확인)로 건너뛴다.

---

## 2단계 — 설치

### 2-1. 설치할 패키지 확인

```powershell
winget show --id Ollama.Ollama --exact
```

**기대 결과** — 첫 줄에 `찾음 Ollama [Ollama.Ollama]`(영문 환경은 `Found Ollama [Ollama.Ollama]`),
그 아래 `버전: 0.35.1` 이상.

**다르면** — 원본 약관 동의를 묻는 메시지가 나오면 `Y`를 입력한다. 패키지를 못 찾으면
2-2 대신 **2-2 (대안)** 으로 설치한다.

### 2-2. 설치

```powershell
winget install --id Ollama.Ollama --exact
```

**기대 결과** — 다운로드 진행 표시 후 `설치 성공`(`Successfully installed`). 설치 창이 잠깐
뜰 수 있다. 설치가 끝나면 Ollama가 **작업 표시줄 트레이(시계 옆)에 아이콘으로 상주**하고
서버가 자동으로 시작된다.

**다르면** — 오류 메시지를 기록표에 적고 **2-2 (대안)** 으로 설치한다.

### 2-2 (대안). 설치 파일을 직접 받아 실행

winget이 안 될 때만 한다.

```powershell
Invoke-WebRequest https://ollama.com/download/OllamaSetup.exe -OutFile "$env:TEMP\OllamaSetup.exe"
```
```powershell
& "$env:TEMP\OllamaSetup.exe"
```

설치 창에서 **Install**을 누른다. 끝나면 트레이에 아이콘이 생긴다.

### 2-3. 터미널 새로 열기

**지금 쓰던 PowerShell 창을 닫고 새로 연다.** 설치가 바꾼 PATH는 새 창에서만 적용된다.

---

## 3단계 — 설치 확인

### 3-1. 명령 위치

```powershell
Get-Command ollama | Select-Object -ExpandProperty Source
```

**기대 결과** — `C:\Users\<사용자>\AppData\Local\Programs\Ollama\ollama.exe` 같은 경로 하나.

**다르면** — `인식되지 않습니다` 오류면 2-3(새 창)을 했는지 확인한다. 새 창에서도 안 되면
PC를 로그아웃했다가 다시 로그인한다.

### 3-2. 버전

```powershell
ollama --version
```

**기대 결과**
```
ollama version is 0.35.1
```

**다르면** — `Warning: could not connect to a running Ollama instance`가 함께 나오면 서버가
안 떠 있는 것이다. 시작 메뉴에서 **Ollama**를 실행하고 다시 입력한다.

### 3-3. 서버 응답

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/version
```

**기대 결과**
```
version
-------
0.35.1
```

**다르면** — `연결할 수 없습니다` 오류면 3-2의 "다르면"과 같이 Ollama를 실행한다.

### 3-4. 모델 목록 (아직 비어 있음)

```powershell
ollama list
```

**기대 결과** — 머리글 한 줄만 나온다.
```
NAME    ID    SIZE    MODIFIED
```

---

## 4단계 — 첫 모델로 GPU 동작 확인

작은 모델(`qwen3:4b`, 2.5GB)로 먼저 확인한다.

### 4-1. 받기 전 VRAM 사용량

```powershell
nvidia-smi --query-gpu=memory.used --format=csv,noheader
```

**기대 결과** — `1805 MiB` 안팎 (화면 출력과 열린 앱이 쓰는 양). **기록표에 적는다.**

### 4-2. 모델 받기

```powershell
ollama pull qwen3:4b
```

**기대 결과** — 진행 막대가 끝나고 마지막 줄에 `success`.

**다르면** — 네트워크 오류면 같은 명령을 다시 입력한다(받은 부분부터 이어서 받는다).

### 4-3. 한 번 실행

```powershell
ollama run qwen3:4b "한 문장으로 자기소개 해줘"
```

**기대 결과** — 몇 초 뒤 한국어 답변이 나오고 프롬프트로 돌아온다. qwen3는 답 앞에
`Thinking...` 같은 사고 과정을 먼저 보여 줄 수 있다 — 정상이다.

**다르면** — 첫 실행은 GPU 커널 준비 때문에 유난히 오래 걸릴 수 있다. 1~2분 기다린다.

### 4-4. GPU에 올라갔는지 (가장 중요)

4-3 직후 5분 안에 입력한다(5분이 지나면 모델이 메모리에서 내려간다).

```powershell
ollama ps
```

**기대 결과** — `PROCESSOR` 열이 `100% GPU`. (다른 열 구성은 버전에 따라 조금 다를 수 있다.)
```
NAME        ID              SIZE      PROCESSOR    CONTEXT    UNTIL
qwen3:4b    xxxxxxxxxxxx    x.x GB    100% GPU     4096       4 minutes from now
```

**다르면**
- `100% CPU` — GPU를 못 잡았다. **5단계(로그 확인)** 로 간다.
- `xx%/yy% CPU/GPU` — 일부만 GPU에 올라갔다. 브라우저 등 GPU를 쓰는 앱을 닫고 4-3부터 다시.

### 4-5. VRAM 증가 확인

```powershell
nvidia-smi --query-gpu=memory.used --format=csv,noheader
```

**기대 결과** — 4-1보다 **수 GB 많다.** 기록표에 적는다.

---

## 5단계 — 로그 확인

4-4가 `100% GPU`였어도 한 번 본다.

```powershell
Get-Content "$env:LOCALAPPDATA\Ollama\server.log" -Tail 40
```

**기대 결과** — `error`, `failed`, `no compatible GPUs` 같은 줄이 없다. GPU 정보 줄에
`GTX 1080 Ti`가 보이면 확실하다.

**다르면** — 오류 줄을 기록표에 복사해 둔다. 자세한 로그를 보려면:
1. 트레이의 Ollama 아이콘 우클릭 → **Quit Ollama**
2. 아래 두 줄을 차례로 입력
```powershell
$env:OLLAMA_DEBUG="1"
```
```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe"
```
3. 4-3부터 다시 하고 `server.log`를 본다

---

## 6단계 — API 확인 (앱이 쓸 방식)

이후 연습 프로젝트의 앱은 이 API로 Ollama를 부른다. 한 줄씩 입력한다.

### 6-1. Ollama 고유 API

```powershell
$body = '{"model":"qwen3:4b","prompt":"1+1은?","stream":false}'
```
```powershell
$r = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:11434/api/generate -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($body))
```
```powershell
$r.response
```
```powershell
$r | Select-Object eval_count, eval_duration, load_duration
```

**기대 결과** — `$r.response`에 답변 문자열, 마지막 명령에 세 숫자가 모두 0보다 크다
(`*_duration`은 나노초). `eval_count / (eval_duration / 1e9)`가 초당 생성 토큰 수다.

### 6-2. OpenAI 호환 API

```powershell
$body = '{"model":"qwen3:4b","messages":[{"role":"user","content":"1+1은?"}]}'
```
```powershell
(Invoke-RestMethod -Method Post -Uri http://127.0.0.1:11434/v1/chat/completions -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($body))).choices[0].message.content
```

**기대 결과** — 답변 문자열이 출력된다.

**다르면** — 한글이 `???`로 나오면 PowerShell 창의 글꼴/인코딩 문제다. 답 자체는 정상이다.

---

## 7단계 — 연습용 모델 더 받기 (선택)

필요할 때 하나씩 받는다. 크기와 적재 판단은 `01-hardware.md` 5.2절.

| 명령 | 크기 | 용도 |
| --- | --- | --- |
| `ollama pull qwen3:8b` | 5.2GB | 범용 기본 |
| `ollama pull exaone3.5:7.8b` | 4.8GB | 한국어 |
| `ollama pull gemma3:12b` | 8.1GB | 상한 실험 (GPU에 다 안 들어갈 수 있음) |
| `ollama pull qwen3:14b` | 9.3GB | VRAM을 일부 넘어 CPU로 넘치는 모델. 일괄 처리에 적합(예상) |
| `ollama pull bge-m3` | 1.2GB | 임베딩 (문서 검색용) |
| `ollama pull qwen3:30b` | 약 19GB | MoE(활성 3B). VRAM을 넘어 RAM에 약 11GB가 올라가는 오프로드 모델. 02-01 측정 대상 |

모델마다 4-3 → 4-4를 반복해 `PROCESSOR` 값을 기록표에 적는다. `gemma3:12b`·`qwen3:14b`·`qwen3:30b`가
`100% GPU`가 아니어도 실패가 아니라 측정 결과다(`01-hardware.md` 5.3절). `qwen3:30b`는 크기가
커서 받기와 첫 로드가 오래 걸리고, 실행 중 RAM 여유가 줄어드니 다른 앱을 닫고 시험한다.

---

## 8단계 — 설정 (필요할 때만)

기본값으로 충분하다. 바꿀 때는 **시작 메뉴 → "계정의 환경 변수 편집"** 에서 사용자 변수를
추가하고, 트레이에서 Ollama를 종료했다가 다시 실행한다.

| 변수 | 언제 | 값 예시 |
| --- | --- | --- |
| `OLLAMA_MODELS` | 모델을 C: 말고 다른 곳에 둘 때 | `G:\ollama\models` |
| `OLLAMA_CONTEXT_LENGTH` | 기본 컨텍스트(4096)를 늘릴 때 | `8192` |
| `OLLAMA_KEEP_ALIVE` | 모델을 메모리에 더 오래(기본 5분) 둘 때 | `30m` |

`OLLAMA_HOST`는 바꾸지 않는다. 기본값(`127.0.0.1`)이어야 이 PC에서만 접근된다.

---

## 자주 쓰는 명령

| 명령 | 하는 일 |
| --- | --- |
| `ollama list` | 받은 모델 목록 |
| `ollama ps` | 지금 메모리에 올라간 모델과 GPU/CPU 비율 |
| `ollama run <모델>` | 대화 모드 (끝내려면 `/bye`) |
| `ollama stop <모델>` | 모델을 메모리에서 내림 |
| `ollama rm <모델>` | 모델 삭제 |
| `ollama show <모델>` | 모델 정보 (크기, 컨텍스트, 양자화) |

---

## 제거 (필요할 때)

```powershell
winget uninstall --id Ollama.Ollama --exact
```
모델과 로그는 남으므로 직접 지운다.
```powershell
Remove-Item -Recurse "$env:USERPROFILE\.ollama"
```
```powershell
Remove-Item -Recurse "$env:LOCALAPPDATA\Ollama"
```
**기대 결과** — 새 PowerShell 창에서 `Get-Command ollama -ErrorAction SilentlyContinue`가 아무것도
출력하지 않는다.

---

## 기록표

설치하면서 채운다.

| 항목 | 값 |
| --- | --- |
| 설치 날짜 | 2026-10-04 |
| 설치 방법 (winget / 설치 파일) | winget |
| `ollama --version` | 0.35.1 |
| 받기 전 VRAM (4-1) | 1839 MiB (모델 적재 전 측정) |
| `qwen3:4b` 실행 중 VRAM (4-5) | 5043 MiB |
| `qwen3:4b` PROCESSOR (4-4) | 100% GPU |
| `qwen3:4b` 초당 생성 토큰 (6-1) | 72.9 tok/s |
| 로그 오류 (5단계) | 없음 |
| 추가 모델별 PROCESSOR (7단계) | 미측정 (적재 테스트 생략) |
| 막힌 곳과 해결 방법 | 없음 |

---

## 출처

- Ollama Windows: <https://docs.ollama.com/windows>
- Ollama GPU 요구사항: <https://docs.ollama.com/gpu>
- Ollama FAQ(`ollama ps`, 컨텍스트, 환경 변수): <https://docs.ollama.com/faq>
- Ollama 문제 해결(로그 위치, 디버그): <https://docs.ollama.com/troubleshooting>
- winget 패키지 `Ollama.Ollama` 0.35.1 (2026-10-04 `winget show`로 확인)
