> 버전: v0.1 · 작성일: 2026-10-04

# 01 — 하드웨어·환경 실측

> 2026-10-04 이 PC에서 읽기 전용 명령으로 수집했다. 설치·변경은 하지 않았다.
> 다시 잴 때는 각 행의 "확인 명령"을 그대로 실행한다(PowerShell).

---

## 1. 하드웨어

| 항목 | 실측값 | 확인 명령 |
| --- | --- | --- |
| CPU | Intel Core i7-8700K @ 3.70GHz, 6코어 / 12스레드 | `Get-CimInstance Win32_Processor` |
| RAM | 32GB (8GB × 4, 2400MHz) | `Get-CimInstance Win32_PhysicalMemory` |
| GPU | NVIDIA GeForce GTX 1080 Ti (Pascal) | `nvidia-smi` |
| VRAM 총량 | 11,264 MiB | `nvidia-smi --query-gpu=memory.total --format=csv` |
| VRAM 사용 중(평상시) | 1,805 MiB 사용 / 9,303 MiB 여유 — 화면 출력 겸용이라 탐색기·브라우저·WebView2 앱 등이 점유 | `nvidia-smi --query-gpu=memory.used,memory.free --format=csv` |
| 공유 GPU 메모리 | 16.0GB(작업 관리자 표시, 사용 0.2GB). 따로 있는 메모리가 아니라 시스템 RAM 32GB의 절반을 GPU용으로 빌려줄 수 있다는 상한. 작업 관리자의 "GPU 메모리 27.0GB"는 전용 11GB + 공유 16GB | 작업 관리자 → 성능 → GPU |
| Compute Capability | 6.1 | `nvidia-smi --query-gpu=compute_cap --format=csv` |
| PCIe | Gen3 최대, 현재 x16 | `nvidia-smi --query-gpu=pcie.link.gen.max,pcie.link.width.current --format=csv` |
| GPU 전력 한도 | 280W | `nvidia-smi --query-gpu=power.limit --format=csv` |

## 2. 드라이버·OS

| 항목 | 실측값 | 확인 명령 |
| --- | --- | --- |
| OS | Windows 11 Pro, 10.0.26200 | `Get-CimInstance Win32_OperatingSystem` |
| NVIDIA 드라이버 | 572.70 | `nvidia-smi` |
| 드라이버가 지원하는 최대 CUDA | 12.8 | `nvidia-smi` 머리글 |
| CUDA Toolkit(`nvcc`) | 없음 — 런타임(Ollama·llama.cpp)이 자체 CUDA 런타임을 포함하므로 필요 없음 | `Get-Command nvcc` |

## 3. 디스크 여유

| 드라이브 | 여유 / 전체 | 용도 판단 |
| --- | --- | --- |
| C: | 520GB / 931GB | Ollama 기본 모델 저장 위치(`%USERPROFILE%\.ollama\models`). 여유 충분 |
| D: | 99GB / 237GB | `D:\projects` 워크스페이스. 모델 저장소로 쓰지 않는다 |
| E: | 144GB / 238GB | — |
| G: | 494GB / 931GB | 모델을 C:에서 옮길 경우 후보 |
| I: | 151GB / 1,863GB | — |
| F: | 0GB / 0GB | 매체 없음(이동식 드라이브로 보임) |

디스크 종류(SSD/HDD)는 `Get-PhysicalDisk`가 출력을 내지 않아 **확인 불가**. 모델 로드
시간에 영향을 주므로 설치 가이드(`02-ollama-install-guide.md`) 6-1의 로드 시간(`load_duration`)으로
간접 확인한다.

## 4. 개발 도구

| 도구 | 실측값 | 비고 |
| --- | --- | --- |
| `python` (PATH) | Microsoft Store 실행 별칭(`...\WindowsApps\python.exe`) — 실제 인터프리터 아님 | 그대로 쓰지 않는다 |
| WinPython GPU | `C:\winpython\WPy64-31180_gpu\python-3.11.8.amd64\python.exe` — Python 3.11.8, torch 2.5.1+cu121(CUDA 사용 가능), transformers 5.14.1, faster-whisper 1.2.1, numpy 2.2.5, scikit-learn 1.7.2. pywebview·plotly 없음 | `_bin\speech_transcriber.cmd` 등이 쓰는 공용 환경 |
| uv | 0.11.29 | 관리 중인 Python: 3.13.14, 3.14.6 |
| Node.js / npm | v22.22.3 / 10.9.8 | Electron 프로젝트용 |
| git | 2.52.0.windows.1 | |
| gh | 2.98.0 | |
| winget | v1.29.380 | |
| 반대 벤더 CLI | codex 0.160.0, gemini 0.42.0 | 적대적 검증용 |
| Ollama / llama.cpp / LM Studio | 없음 | `Get-Command ollama,llama-server,lms` |

## 5. 판단 — 이 GPU로 되는 것과 안 되는 것

### 5.1 런타임 지원 (작성일 기준)

- **Ollama v0.35.1(2026-09-29)**: 공식 GPU 문서에 compute 6.1 / GTX 1080 Ti가 지원 목록에
  있다. compute 5.0~6.2는 **드라이버 570 이상**이 필요하며 현재 572.70이므로 만족한다.
- **llama.cpp b11382(2026-10-04)**: Windows 자산 중 `win-cuda-12.4-x64`만 Pascal을 포함한다.
  CUDA 13.0부터 sm_61 컴파일이 제거됐으므로 `win-cuda-13.4-x64`는 쓰지 않는다.
- **Pascal의 특성**: FP16 처리량이 낮다. FP16 원본보다 4~5비트 양자화(GGUF Q4/Q5)가 유리하다.
  Pascal용 커널은 첫 실행 때 PTX JIT 컴파일로 시작이 한 번 늦어질 수 있다.

### 5.2 모델별 적재 가능 여부 (VRAM 여유 9,303 MiB 기준)

파일 크기는 Ollama 라이브러리 표기(기본 태그, 4비트 양자화 계열). "적재"는 모델 전체가
GPU에 올라가는지를 말하며, 실제 여부는 설치 후 `ollama ps`의 PROCESSOR 열로 확인한다.

| 모델 태그 | 파일 크기 | 컨텍스트(최대) | 판정 | 비고 |
| --- | --- | --- | --- | --- |
| `qwen3:4b` | 2.5GB | 256K | 여유 | 가벼운 실험용 |
| `exaone3.5:7.8b` | 4.8GB | 32K | 여유 | 한국어·영어 이중언어 |
| `qwen3:8b` | 5.2GB | 40K | 여유 | 범용 기본 |
| `gemma3:12b` | 8.1GB | 128K | **경계** | 컨텍스트를 줄이고(예: 4K~8K) 다른 GPU 앱을 닫아야 할 수 있음. 실측 대상 |
| `qwen3:14b` | 9.3GB | 40K | 불가(GPU 단독) | 여유 메모리를 넘음. 일부 CPU 오프로드(5.3절) |
| `gemma3:27b`, `qwen3:32b` | 17~20GB | — | 불가(GPU 단독) | RAM에 넘쳐서만 돎(5.3절) |
| `bge-m3` (임베딩) | 1.2GB | 8K | 여유 | 다국어 임베딩. LLM 8B와 동시 적재 가능 범위 |

**특화 모델 (비교 대상)** — 04-03 translator·06-04 scan-ocr에서 범용 모델과 비교한다. 크기는 Ollama
라이브러리 기본 태그(q4_K_M) 표기. Pascal에서 도는지는 설치 후 확인한다.

| 모델 태그 | 파일 크기 | 컨텍스트(최대) | 판정 | 비고 |
| --- | --- | --- | --- | --- |
| `translategemma:4b` | 3.3GB | 128K | 여유 | 번역 전용(Gemma 3 기반), 한국어 포함 55개 언어. 전용 프롬프트 형식 필요 |
| `translategemma:12b` | 8.1GB | 128K | **경계** | `gemma3:12b`와 같은 크기. 일부 CPU 오프로드 전제 |
| `aya-expanse:8b` | 5.1GB | 8K | 여유 | 다국어 23개(한국어 포함). 텍스트 전용 |
| `deepseek-ocr` | 6.7GB | 8K | 여유 | OCR 전용(3B), 문서 → md 변환. Ollama v0.13.0 이상 |
| `qwen2.5vl:7b` | 6.0GB | 125K | 여유 | 문서·표 인식이 강한 비전 모델 |
| `granite3.2-vision` | 2.4GB | 16K | 여유 | 문서 이해 특화 경량 비전 모델(2B) |

비전 모델은 이미지 처리부 때문에 같은 크기의 텍스트 모델보다 VRAM을 더 쓴다. 실제 사용량은
`ollama ps`로 확인한다.

**컨텍스트 길이 주의** — 모델 파일 외에 컨텍스트 캐시(KV cache)가 컨텍스트 길이에 비례해
VRAM을 더 쓰고, 계산 버퍼(약 0.3~0.5GB)도 붙는다. 최대 컨텍스트를 그대로 쓰면 "여유" 모델도
넘칠 수 있으므로, 연습 앱은 컨텍스트 길이(`num_ctx`)를 명시적으로 정한다.

아래는 KV cache(FP16, 모델 구조로 계산)와 계산 버퍼를 더한 **추정** 합계다. 실제 값은 설치 후
`ollama ps`의 SIZE 열과 02-01 실측으로 보정한다.

| 모델 | KV cache/토큰 | 합계 @ 4K | 합계 @ 8K | 합계 @ 32K | 판정(4K~8K) |
| --- | --- | --- | --- | --- | --- |
| `bge-m3` | 작음 | 약 1.5GB | — | — | 여유 |
| `qwen3:4b` | 약 144KB | 약 3.4GB | 약 4.0GB | 약 7.5GB | 여유 |
| `gemma3:4b` (비전) | — | 4~5GB(06-01 플랜 예상) | — | — | 여유 |
| `exaone3.5:7.8b` | 약 128KB | 약 5.6GB | 약 6.1GB | 약 9.2GB | 여유. 32K는 넘침 |
| `qwen3:8b` | 약 144KB | 약 6.1GB | 약 6.7GB | 약 10GB | 여유. 32K는 넘침 |
| `qwen3:8b` + `bge-m3` 동시 | — | 약 7.6GB | 약 8.2GB | — | 가능(RAG 조합) |
| `gemma3:12b` | 작음(슬라이딩 윈도우) | 약 9GB 이상 | — | — | 넘칠 가능성 큼. 일부 CPU 오프로드 전제 |

- 평상시 점유 1.8GB는 고정값이 아니다. pywebview(WebView2) 연습 앱 창 자체도 VRAM을 쓴다.
- Ollama는 이전 모델을 바로 내리지 않고 잠시 올려 둔다. 모델을 전환하면 두 모델이 동시에 올라가
  넘칠 수 있다.

### 5.3 VRAM을 넘는 모델 — 공유 GPU 메모리와 RAM 사용

VRAM에 다 안 들어가는 모델도 연습 대상에 넣는다(2026-10-04 사용자 결정). 넘친 부분은 시스템
RAM에 두며, 경로는 두 가지다.

| 경로 | 동작 | 넘친 부분의 속도 결정 요인 |
| --- | --- | --- |
| CPU 오프로드(Ollama 기본) | 안 들어가는 레이어를 RAM에 두고 CPU가 계산 | RAM 대역폭 약 38GB/s(DDR4-2400 듀얼채널), 6코어 CPU |
| 공유 메모리 폴백(NVIDIA "CUDA - Sysmem Fallback Policy", 드라이버 536.40+) | GPU가 계산하되 넘친 데이터를 PCIe로 RAM에서 읽음 | PCIe Gen3 x16 실효 약 12GB/s |

VRAM 대역폭(약 484GB/s)에 비해 두 경로 모두 수십 배 느리고, 보통 공유 메모리 폴백이 CPU
오프로드보다 더 느리다. Ollama는 남은 VRAM을 보고 레이어를 나누므로 기본적으로 CPU 오프로드가
쓰인다. 어느 쪽이 빠른지는 NVIDIA 제어판의 정책을 바꿔 가며 02-01에서 실측한다.

**상한** — 공유 GPU 메모리 16GB는 RAM과 같은 메모리라 VRAM에 더해지지 않는다. 실제 상한은
남는 VRAM 약 9GB + Windows·앱이 쓰고 남은 RAM으로, 모델 크기 약 25GB 안팎이다.

아래 속도는 토큰 생성이 메모리 대역폭에 묶인다는 가정의 **추정**이다(`num_ctx` 4K, VRAM에 약
8GB를 올리고 나머지는 RAM). 02-01 실측으로 보정한다.

| 모델 | 크기 | VRAM / RAM | 예상 생성 속도 | 판정 |
| --- | --- | --- | --- | --- |
| `qwen3:8b`(기준) | 5.2GB | 전부 VRAM | 약 30~40 tok/s | 여유 |
| `gemma3:12b` | 8.1GB | 약 8 / 1GB | 약 15 tok/s | 가능 |
| `qwen3:14b` | 9.3GB | 약 8 / 1.5GB | 약 10 tok/s | 가능. 일괄 처리에 적합 |
| `qwen3:30b`(MoE, 활성 3B) | 약 19GB | 약 8 / 11GB | 약 10~20 tok/s | 가능. 토큰마다 읽는 가중치가 약 2GB라 크기에 비해 빠름 |
| `gpt-oss:20b`(MoE, 활성 3.6B) | 약 14GB | 약 8 / 6GB | 약 15~25 tok/s | 후보. MXFP4 형식이 Pascal에서 도는지 확인 필요 |
| `gemma3:27b` | 약 17GB | 약 8 / 9GB | 약 2~3 tok/s | 상한 실험용 |
| `qwen3:32b` | 약 20GB | 약 8 / 12GB | 약 2 tok/s | 연습용으로는 너무 느림 |
| 70B급 | 40GB 이상 | — | — | 불가. RAM 초과 |

- 19GB급 모델을 RAM에 올리면 32GB 중 남는 메모리가 줄어, 브라우저·연습 앱과 동시에 쓰기가
  빠듯해질 수 있다.
- 큰 모델은 첫 로드가 오래 걸린다. 디스크 종류는 확인 불가(3절).
- 오프로드 여부는 `ollama ps`의 PROCESSOR 열에 `48%/52% CPU/GPU`처럼 나뉘어 표시된다.

---

## 출처

- Ollama GPU 지원: <https://docs.ollama.com/gpu> (v0.35.1 태그의 `docs/gpu.mdx`와 대조)
- Ollama Windows: <https://docs.ollama.com/windows>
- llama.cpp 릴리스 자산: <https://github.com/ggml-org/llama.cpp/releases> (b11382)
- Pascal과 CUDA 13: <https://localaimaster.com/blog/pascal-gpus-after-cuda-13>
- 모델 크기: <https://ollama.com/library/qwen3>, <https://ollama.com/library/exaone3.5>,
  <https://ollama.com/library/gemma3>, <https://ollama.com/library/bge-m3>
- 특화 모델: <https://ollama.com/library/translategemma>, <https://ollama.com/library/aya-expanse>,
  <https://ollama.com/library/deepseek-ocr>, <https://ollama.com/library/qwen2.5vl>,
  <https://ollama.com/library/granite3.2-vision> (2026-10-04 확인)
- CUDA Sysmem Fallback Policy: <https://nvidia.custhelp.com/app/answers/detail/a_id/5490>
- 5.2절 KV cache 합계, 5.3절 MoE 크기·예상 속도: 모델 구조와 대역폭으로 계산한 추정(출처 없음, 실측 전)
