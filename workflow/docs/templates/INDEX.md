# templates — 본보기 모음

새 프로젝트를 시작할 때 여기서 가져다 쓴다. **형식이 정해져 있어 매번 다시 쓰게
되는 것**만 둔다.

`INTENT.md`와 버전 문서(`BRIEF`·`DECISIONS`·`SPEC`·`PLAN`·`backlog.json`)의 빈 양식은
두지 않는다. 그건 **사람이 쓰는 것**이고, 형식은 `../DOC-SCHEMA.md`가 정의한다
(INTENT는 2절, 나머지는 3절 이하).

---

## 목록

| 파일 | 어디로 | 손볼 곳 |
| --- | --- | --- |
| `README.template.md` | `<project>/README.md` — **[llm-labs]** 연습 폴더 | 개요를 사람이 채운다 (설치·사용법은 마감 때) |
| `CLAUDE.template.md` | `<project>/CLAUDE.md` — **[llm-labs]** 저장소 루트, 1회 | 첫 줄 날짜, 모든 연습에 걸리는 제약. 기존 `CLAUDE.md`(`@AGENTS.md`)와 합친다 |
| `AGENTS.template.md` | `<project>/AGENTS.md` — **[llm-labs]** 루트에 이미 있으므로 덮어쓰지 않는다 | 구조 표만 참고해 합친다 |
| `claude/settings.template.json` | `<project>/.claude/settings.json` — **[llm-labs]** 저장소 루트, 1회 | 경로 확인 |
| `claude/hooks/guard.mjs` | `<project>/.claude/hooks/guard.mjs` — **[llm-labs]** 저장소 루트 | 그대로 |
| `claude/hooks/progress-check.mjs` | `<project>/.claude/hooks/progress-check.mjs` — **[llm-labs]** 저장소 루트 | 그대로(이미 연습 폴더별 판정으로 고쳐 둠) |
| `claude/agents/reviewer.template.md` | `<project>/.claude/agents/reviewer.md` — **[llm-labs]** 저장소 루트 | 그대로 |
| `gitignore/python.txt` | `<project>/.gitignore` — **[llm-labs]** 저장소 루트 | Python 연습이 있으면 |
| `gitignore/node.txt` | `<project>/.gitignore` — **[llm-labs]** 저장소 루트 | Electron 연습이 있으면. **[llm-labs]** 택일이 아니라 둘 다 합칠 수 있다 |

`.template` 접미사는 GitHub이 이 폴더의 `README.md`를 렌더링해 실제 문서로 오해하는
것을 막기 위해서다. 복사할 때 떼어낸다.

---

## 복사한 뒤 반드시 할 것

**hook은 복사만으로 동작하지 않는다.** `../HARNESS.md` 5절의 차단 증명을 돌린다.

| 시도 | 기대 |
| --- | --- |
| `docs/history/` 아래 파일 수정 | 차단 |
| `backlog.json` 직접 편집 | 차단 |
| `docs/current/BRIEF.md` 읽기 | 통과 |

**하나라도 기대와 다르면 초기화 실패다.**
