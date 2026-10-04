# AGENTS.md — llm-labs 운영 지침

> 이 파일이 llm-labs의 규칙 파일이다. `CLAUDE.md`는 이 파일을 가리킨다.
> 이 저장소는 `D:\projects` 워크스페이스 **밖**에 둔 연습 저장소라서 `D:\projects\AGENTS.md`가
> 자동으로 로드되지 않는다. 여기 필요한 규칙만 옮겨 둔다. 무엇을 왜 하는지는 `docs/INTENT.md`를 본다.

## 이 저장소의 규칙

- Ollama 기반 로컬 LLM 연습 프로젝트를 모아 하나씩 구현하는 저장소다. GitHub 저장소명은 폴더명과
  같은 `llm-labs`다. 연습 목록은 `docs/refs/03-project-list.md` 하나뿐이다.
- 연습 플랜은 `docs/labs/NN-category/NN-name.md`에 있다. 구현 폴더 `NN-category\NN-name\`는
  저장소 루트에, **그 연습을 착수할 때만** 만든다. 빈 폴더를 미리 만들지 않는다.
- 저장소 문서는 `docs/`에 있다(`INTENT.md`·`ROADMAP.md`·`DECISIONS.md`, `refs/` 참고 자료, `labs/` 연습
  플랜). 루트에는 `AGENTS.md`·`CLAUDE.md`·`workflow/`·하네스(`.claude/`)와 연습 폴더만 둔다. 저장소
  루트는 버전 없는 워크스페이스 층이고, **연습 폴더 하나가 프로젝트 하나**다. 버전·`docs/current/`·`docs/history/`·태그(`01-01-local-chat/v0.1`)는
  연습마다 따로다. 다른 연습 폴더를 고치지 않는다. 공통 코드는 쓰는 연습이 복사해 온다.
- 연습 저장소 안에서 실사용 프로젝트(`D:\projects\*`)를 고치지 않는다. 읽거나 CLI로 쓰기만 한다.
- 기획 문서는 **사용자의 요청·승인으로만** 만들고 고친다. 요청이 오면 되묻지 말고 바로 초안을
  쓰되, 요청받은 문서 하나만 쓰고 다음 문서로 넘어갈지는 한 줄로 제안만 한다. 모르는 내용은
  지어내지 말고 **한 번에 하나씩 묻는다.** 말한 것만 적고 빈 곳은 "미정"으로 둔다.
- **이 규칙은 지키기만 하고 설명하지 않는다.** "제가 대신 쓰지 않습니다" 같은 문장을 덧붙이지 않는다.

## workflow 가이드 — 언제 무엇을 읽나

가이드는 저장소 루트의 `workflow/`다. project-workflow 원본(`D:\projects\project-workflow\`)을
llm-labs에 맞게 고친 사본이고, **이 사본만 따른다.** 원본과 고친 곳은 `workflow/UPSTREAM.md`에
있다. 원본은 고치지 않고, 원본 갱신은 UPSTREAM 절차로 사용자에게 물어 반영한다. **전체를 미리
읽지 않는다.** 아래 상황에 들어갈 때 해당 문서만 열어 그대로 따른다. 본문의 **[llm-labs]** 표시가
원본과 다른 곳이며, 헷갈리면 `workflow/WORKFLOW.md` 0절을 따른다.

| 상황 | 먼저 읽을 문서 | 뽑아올 것 |
| --- | --- | --- |
| 기획 문서를 쓰거나 고칠 때 | `workflow/docs/DOC-SCHEMA.md` | 문서별 절(INTENT 2, BRIEF 3, DECISIONS 4, SPEC 5, PLAN 6, backlog 7), 필수 블럭, 판정 가능한 형태, "사람이 쓴다 = 묻는다"(1절) |
| 연습을 착수(INIT)하거나 새 버전을 시작할 때 | `workflow/docs/INIT.md` | 착수 모드(A 신규 / C 참조 후 신규 / B 새 버전, 연습마다 판별), 문서 검사, 연습 폴더 `docs/` 구조·플랜 복사, 하네스(루트 1회) |
| 절차 전체나 흐름이 헷갈릴 때 | `workflow/WORKFLOW.md` | 0절(llm-labs 두 층 구조), 문서 수명, 시작·개선 절차 |
| 연습의 버전을 마감하거나 중단할 때 | `workflow/docs/VERSIONING.md` | 마감 조건, 연습의 `docs/history/` 복사, DECISIONS 승격, 태그 `<연습명>/vX.Y`, ROADMAP 갱신 |
| hook·rules·reviewer를 설치·점검할 때 | `workflow/docs/HARNESS.md` | 설치 항목, 차단 증명(연습 폴더 경로로) |
| **Phase를 닫기 전, 그리고 리팩토링을 끝냈을 때** | `workflow/docs/ADVERSARIAL-REVIEW.md` | 세션 내 리뷰어와의 층 구분, 적용 대상, 절차와 3회 제한, 헤드리스 명령·프롬프트, 기록 양식 |
| 사람에게 줄 지시문이 필요할 때 | `workflow/docs/PROMPTS.md` | 단계별 프롬프트 원문(머리말의 바꿔 읽기 표) |

- 저장소 `docs/INTENT.md`는 모든 연습이 공유하는 SSOT다. **사람의 요청으로만** 고친다. 연습 폴더에
  INTENT를 만들지 않는다. 다른 문서가 INTENT에 어긋나면 혼자 맞추지 말고 멈추고 보고한다.
- 연습의 필수 문서는 `BRIEF`·`DECISIONS`·`PLAN`(+ 착수 시 `README`). `SPEC`·`backlog.json`은 선택이다.
- major·minor 버전 번호와 필수 통과 Phase는 **사람이 정한다.** 버전은 연습마다 따로다.
- 새 과제 구현과 **리팩토링에는 반대 벤더 적대적 검증이 필수다.** 게이트는
  `hook → 세션 내 리뷰어 → 반대 벤더` 세 층이고, 세션 내 리뷰어가 반대 벤더를 대신하지 않는다.
  검토자는 `workflow/docs/ADVERSARIAL-REVIEW.md`의 표를 따른다(Claude Code 구현 → Codex
  `gpt-6.1-sol`, Codex 구현 → Claude `opus-5.5`). 반대 벤더 CLI를 못 쓰면 **기본 모델로 폴백하지
  말고 멈추고 보고한다.**
- 검증 중 PROGRESS.md "계획 외 개선"에 적힌 변경은 사용자 요청일 수 있다. 되돌리기 전에 묻는다.

## 기술 기준 (연습 공통)

- 화면이 있는 연습은 모두 Python + pywebview(+ 차트는 Plotly.js), 화면이 필요 없으면
  Python CLI다(Electron은 쓰지 않는다. `docs/DECISIONS.md` R-9). Python은 uv로 관리하고
  `pyproject.toml`은 연습마다 둔다(PATH의 `python`은 Store 별칭이라 쓰지 않는다).
- 모델과 VRAM 판단의 근거는 `docs/refs/01-hardware.md`(GTX 1080 Ti 11GB, 화면 겸용으로 평상시 약 1.8GB 점유).
  Ollama 설치 전의 수치는 예상값이며, 설치 후 02-01 model-bench 실측으로 보정한다.
- Ollama 설치는 00-01 ollama-setup에서 사용자가 `docs/refs/02-ollama-install-guide.md`를 보고 직접 한다. 에이전트가 설치하지 않는다.
