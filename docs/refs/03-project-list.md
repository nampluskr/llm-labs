> 버전: v0.1 · 작성일: 2026-10-04

# 03 — 연습 프로젝트 목록

> Ollama를 LLM 런타임으로 쓰는 연습 프로젝트의 **유일한 목록**이다. 카테고리 8개에 프로젝트
> 37개를 둔다(00은 준비 2개, 01~07은 5개씩). 프로젝트별 기술 스택과 간단한 플랜은
> `docs\labs\NN-category\NN-name.md`에 하나씩 쓴다. 하드웨어 판단은 `01-hardware.md`,
> 설치는 `02-ollama-install-guide.md`를 본다.

---

## 1. 카테고리

| 번호 | 폴더 | 카테고리 | 목적 | 익히는 것 | 주요 기술 |
| --- | --- | --- | --- | --- | --- |
| 00 | `00-setup` | 환경 준비 | 다른 연습을 시작하기 전에 Ollama와 파이썬 개발 환경을 갖추고 점검 | Ollama 설치·모델 받기, uv·pywebview·jupyter 동작 확인, 환경 점검 | `ollama` CLI, uv, 파이썬 CLI |
| 01 | `01-basics` | Ollama 기초 | Ollama API와 앱 연결 방식 익히기 | 스트리밍, 모델 관리, 생성 파라미터, Modelfile | `/api/chat`·`/api/ps`, pywebview |
| 02 | `02-bench` | 성능·평가 | 이 PC(1080 Ti)에서 모델별 한계를 실측하고 품질 비교 | tok/s, VRAM, 컨텍스트 길이, 양자화, 한국어 품질 | nvidia-smi, numpy, Plotly |
| 03 | `03-rag` | 문서·지식 (RAG) | 내 문서를 근거로 답하게 하기 | 임베딩, 청크 분할, 유사도 검색, 근거 제시 | bge-m3, numpy 코사인 검색 |
| 04 | `04-automation` | 텍스트 처리 자동화 | 반복적인 텍스트 작업을 구조화된 출력으로 자동화 | JSON 스키마 출력, 요약, 번역, 분류 | `format` 스키마, pydantic |
| 05 | `05-agent` | 에이전트·도구 호출 | LLM이 도구를 골라 실행하게 하기 | tool calling, 반복 실행 루프, 코드 실행 | qwen3 tools, MCP |
| 06 | `06-vision` | 멀티모달 (비전) | 이미지를 입력으로 쓰기 | 이미지 설명, 화면 해석, 일괄 태깅 | gemma3 비전 입력 |
| 07 | `07-integration` | 기존 프로젝트 연계 | 이미 만든 도구의 출력·명령을 바깥에서 받아 로컬 LLM으로 처리하기 | 전사 후처리(speech_transcriber), 자막 요약(youtube-kit), 명령 감싸기 | 기존 도구의 파일·CLI + Ollama API |

---

## 2. 번호 규칙

| 규칙 | 내용 |
| --- | --- |
| 카테고리 번호 | 추천 학습 순서(기초 → 실측 → RAG → 자동화 → 에이전트 → 비전 → 연계) |
| 프로젝트 번호 | 카테고리 안의 추천 착수 순서(쉬운 것 → 어려운 것) |
| 우선순위 | 번호와 별개로 아래 3절의 "우선순위" 열에만 적는다. 우선순위가 바뀌어도 파일 이름은 바꾸지 않는다 |
| 프로젝트 ID | `카테고리-프로젝트` 번호. 예: `03-01` = `docs\labs\03-rag\01-*.md` |
| 접두사 | 항상 두 자리 숫자 + `-`. 착수한 연습은 `llm-labs` 저장소 루트에 같은 이름의 폴더(`NN-category\NN-name\`)로 만들고, 번호를 떼지 않는다 |
| 폴더·파일 생성 | 연습 플랜은 `docs\labs\` 아래 참조 문서로 둔다. 저장소 루트의 구현 폴더는 그 연습을 착수할 때 만든다 |
| 카테고리 README | 두지 않는다. 목록은 이 문서 하나뿐이다 |

**프로젝트 파일의 틀** — 모든 프로젝트 파일은 다음 5개 절을 갖는다.

1. 개요 — 무엇을, 왜, 이 카테고리에서 익히는 것
2. 기술 스택 — 런타임(pywebview), 라이브러리, 모델, `num_ctx`
3. 간단한 플랜 — Phase 2~4개, Phase마다 판정 가능한 완료 조건
4. 하드웨어 메모 — 예상 VRAM, 1080 Ti 기준 주의점
5. 미정

**공통 기술 스택 기준**

| 갈래 | 언제 | 스택 |
| --- | --- | --- |
| Python + pywebview | 화면이 있는 모든 앱(저장소 DECISIONS R-9) | uv 가상환경(연습마다 `pyproject.toml`, Python 3.13), `ollama`(공식 파이썬 클라이언트), pywebview, 차트가 필요하면 Plotly.js. 탐색기·탭 형태는 `tab-explorer-templates`의 NumPy 갈래에서 출발 |
| Python CLI | 화면이 필요 없는 도구 | uv, `ollama`, argparse, `--json` 출력 |

모델은 `01-hardware.md` 5.2절에서 "여유"로 판정한 `qwen3:4b`·`qwen3:8b`·`exaone3.5:7.8b`·`bge-m3`와
비전용 `gemma3:4b`를 쓴다. VRAM·속도 수치는 Ollama 설치 전이라 모두 예상값이며, 설치 후 02-01 결과로 보정한다.

---

## 3. 프로젝트

"파일" 열은 `작성됨` 또는 `미작성`이다. 작성된 프로젝트 파일 수와 `작성됨` 행 수가 같아야 한다.
우선순위는 상·중·하로 적는다. 카테고리마다 "상" 1개(07은 2개)가 그 카테고리의 첫 착수 후보다.
00은 다른 모든 연습의 선행 준비라 둘 다 "상"이다.

### 00 — 환경 준비

| ID | 프로젝트 | 한 줄 설명 | 우선순위 | 난이도 | 모델 | 파일 |
| --- | --- | --- | --- | --- | --- | --- |
| 00-01 | [ollama-setup](../labs/00-setup/01-ollama-setup.md) | Ollama 설치(사용자가 직접), GPU 적재 확인, 연습용 모델 받기 | 상 | 하 | `qwen3:4b`·`qwen3:8b`·`exaone3.5:7.8b`·`bge-m3`·`gemma3:12b`·`qwen3:14b`·`qwen3:30b` | 작성됨 |
| 00-02 | [env-check](../labs/00-setup/02-env-check.md) | uv·pywebview·jupyter 동작 확인과 Ollama·모델·GPU를 한 번에 점검하는 CLI | 상 | 하 | 받은 모델 전부 | 작성됨 |

### 01 — Ollama 기초

| ID | 프로젝트 | 한 줄 설명 | 우선순위 | 난이도 | 모델 | 파일 |
| --- | --- | --- | --- | --- | --- | --- |
| 01-01 | [local-chat](../labs/01-basics/01-local-chat.md) | 스트리밍 채팅, 모델 전환, 대화 저장 | 상 | 하 | qwen3:8b | 작성됨 |
| 01-02 | [prompt-playground](../labs/01-basics/02-prompt-playground.md) | 같은 프롬프트를 파라미터만 바꿔 나란히 비교 | 중 | 하 | qwen3:4b | 작성됨 |
| 01-03 | [model-manager](../labs/01-basics/03-model-manager.md) | 모델 목록·적재 상태·pull 진행률·삭제 GUI | 중 | 하 | 받은 모델 전부 | 작성됨 |
| 01-04 | [modelfile-studio](../labs/01-basics/04-modelfile-studio.md) | 시스템 프롬프트와 파라미터로 나만의 모델 생성·테스트 | 하 | 하 | exaone3.5:7.8b | 작성됨 |
| 01-05 | [tray-assistant](../labs/01-basics/05-tray-assistant.md) | 단축키로 부르는 창, 클립보드 텍스트 질문 | 하 | 중 | qwen3:4b | 작성됨 |

### 02 — 성능·평가

| ID | 프로젝트 | 한 줄 설명 | 우선순위 | 난이도 | 모델 | 파일 |
| --- | --- | --- | --- | --- | --- | --- |
| 02-01 | [model-bench](../labs/02-bench/01-model-bench.md) | 모델별 tok/s·로드 시간·VRAM을 측정하고 Plotly로 비교 | 상 | 하 | 받은 모델 전부 | 작성됨 |
| 02-02 | [ctx-scaling](../labs/02-bench/02-ctx-scaling.md) | `num_ctx`에 따른 VRAM·속도·GPU 적재 한계 측정 | 중 | 중 | qwen3:8b, gemma3:12b | 작성됨 |
| 02-03 | [quant-compare](../labs/02-bench/03-quant-compare.md) | 같은 모델의 양자화 수준별 속도·품질 비교 | 하 | 중 | qwen3:4b, bge-m3 | 작성됨 |
| 02-04 | [ko-eval](../labs/02-bench/04-ko-eval.md) | 한국어 문항 세트로 모델별 정답률 비교 | 중 | 중 | exaone3.5:7.8b, qwen3 | 작성됨 |
| 02-05 | [prompt-regression](../labs/02-bench/05-prompt-regression.md) | 프롬프트 변경 전후 출력 스냅샷 테스트 | 하 | 중 | qwen3:4b | 작성됨 |

### 03 — 문서·지식 (RAG)

| ID | 프로젝트 | 한 줄 설명 | 우선순위 | 난이도 | 모델 | 파일 |
| --- | --- | --- | --- | --- | --- | --- |
| 03-01 | [doc-qa](../labs/03-rag/01-doc-qa.md) | 로컬 md·pdf 문서에 근거 문단과 함께 답함 | 상 | 중 | qwen3:8b + bge-m3 | 작성됨 |
| 03-02 | [projects-search](../labs/03-rag/02-projects-search.md) | `D:\projects` 문서 의미 검색, 증분 색인 | 중 | 중 | bge-m3 | 작성됨 |
| 03-03 | [embedding-map](../labs/03-rag/03-embedding-map.md) | 문서 임베딩을 2D로 투영해 군집 시각화 | 중 | 중 | bge-m3, qwen3:4b | 작성됨 |
| 03-04 | [repo-digest](../labs/03-rag/04-repo-digest.md) | 코드 저장소의 구조 요약과 README 초안 생성 | 하 | 중 | qwen3:8b | 작성됨 |
| 03-05 | [paper-reader](../labs/03-rag/05-paper-reader.md) | 논문 PDF 요약, 용어집, 섹션별 질문 | 하 | 상 | qwen3:8b + bge-m3 | 작성됨 |

### 04 — 텍스트 처리 자동화

| ID | 프로젝트 | 한 줄 설명 | 우선순위 | 난이도 | 모델 | 파일 |
| --- | --- | --- | --- | --- | --- | --- |
| 04-01 | [commit-writer](../labs/04-automation/01-commit-writer.md) | `git diff`로 커밋 메시지 초안 생성 | 중 | 하 | qwen3:4b | 작성됨 |
| 04-02 | [json-extractor](../labs/04-automation/02-json-extractor.md) | 자유 텍스트에서 스키마 JSON 추출 | 상 | 하 | qwen3:8b | 작성됨 |
| 04-03 | [translator](../labs/04-automation/03-translator.md) | 한↔영 번역, 용어집 고정, 대조 보기, 영어 md·pdf 문서 구조 유지 번역·저장 | 중 | 중 | exaone3.5:7.8b | 작성됨 |
| 04-04 | [file-tagger](../labs/04-automation/04-file-tagger.md) | 폴더 파일 분류·태그·이름 변경 제안(적용은 승인 후) | 하 | 중 | qwen3:4b | 작성됨 |
| 04-05 | [log-analyzer](../labs/04-automation/05-log-analyzer.md) | 로그 파일 오류 요약·분류·원인 후보 제시 | 하 | 중 | qwen3:8b | 작성됨 |

### 05 — 에이전트·도구 호출

| ID | 프로젝트 | 한 줄 설명 | 우선순위 | 난이도 | 모델 | 파일 |
| --- | --- | --- | --- | --- | --- | --- |
| 05-01 | [tool-agent](../labs/05-agent/01-tool-agent.md) | 계산기·파일 검색 같은 도구를 골라 호출 | 상 | 중 | qwen3:8b | 작성됨 |
| 05-02 | [shell-helper](../labs/05-agent/02-shell-helper.md) | 자연어 → PowerShell 명령 제안, 실행은 확인 후 | 중 | 중 | qwen3:8b | 작성됨 |
| 05-03 | [data-analyst](../labs/05-agent/03-data-analyst.md) | CSV에 대해 pandas 코드 생성·실행, Plotly 차트로 답 | 중 | 상 | qwen3:8b | 작성됨 |
| 05-04 | [mcp-local](../labs/05-agent/04-mcp-local.md) | 로컬 모델에 MCP 서버 연결 | 하 | 상 | qwen3:8b | 작성됨 |
| 05-05 | [planner-executor](../labs/05-agent/05-planner-executor.md) | 작업을 단계로 나누고 단계마다 실행·검토 | 하 | 상 | qwen3:8b | 작성됨 |

### 06 — 멀티모달 (비전)

| ID | 프로젝트 | 한 줄 설명 | 우선순위 | 난이도 | 모델 | 파일 |
| --- | --- | --- | --- | --- | --- | --- |
| 06-01 | [image-caption](../labs/06-vision/01-image-caption.md) | 이미지 폴더에 설명·태그 일괄 생성 | 상 | 하 | gemma3:4b | 작성됨 |
| 06-02 | [screenshot-qa](../labs/06-vision/02-screenshot-qa.md) | 클립보드 캡처를 붙여 넣고 질문 | 중 | 중 | gemma3:4b | 작성됨 |
| 06-03 | [photo-search](../labs/06-vision/03-photo-search.md) | 캡션 + bge-m3로 사진을 문장으로 검색 | 중 | 중 | bge-m3 | 작성됨 |
| 06-04 | [scan-ocr](../labs/06-vision/04-scan-ocr.md) | 스캔 PDF·이미지 OCR → md 저장, 04-03 번역으로 연계 | 중 | 중 | gemma3:4b | 작성됨 |
| 06-05 | [receipt-scanner](../labs/06-vision/05-receipt-scanner.md) | 영수증 이미지 → JSON(04-02 모듈 재사용) | 하 | 중 | gemma3:4b | 작성됨 |

### 07 — 기존 프로젝트 연계

| ID | 프로젝트 | 한 줄 설명 | 우선순위 | 난이도 | 모델 | 파일 |
| --- | --- | --- | --- | --- | --- | --- |
| 07-01 | [transcript-polish](../labs/07-integration/01-transcript-polish.md) | speech_transcriber SRT의 문장부호 복원·요약·번역 | 상 | 중 | exaone3.5:7.8b | 작성됨 |
| 07-02 | [youtube-digest](../labs/07-integration/02-youtube-digest.md) | youtube-kit 자막으로 요약·챕터 생성 | 상 | 중 | qwen3:8b | 작성됨 |
| 07-03 | [markdown-ask](../labs/07-integration/03-markdown-ask.md) | md 문서를 열어 보며 요약·질문하는 독립 창(`D:\projects` 문서 읽기 전용) | 중 | 중 | qwen3:8b, bge-m3 | 작성됨 |
| 07-04 | [backlog-assist](../labs/07-integration/04-backlog-assist.md) | 자연어 → backlog task 초안, `backlog validate`로 검증 | 하 | 중 | qwen3:8b | 작성됨 |
| 07-05 | [error-explainer](../labs/07-integration/05-error-explainer.md) | `ex <명령>`으로 감싸 실행, 실패하면 원인 설명·확인 명령 제안 | 하 | 중 | qwen3:8b | 작성됨 |

07 카테고리는 기존 도구를 고치지 않고 그 출력 파일·CLI를 바깥에서 쓰기만 한다(INTENT 3절). 결과가
쓸 만하면 해당 레포의 새 버전으로 옮겨 갈지는 연습을 끝낸 뒤 판단한다.

---

## 4. 미정

없음
