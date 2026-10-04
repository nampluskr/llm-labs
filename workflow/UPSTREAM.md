> 작성일: 2026-10-04 · 버전 없음(저장소 전체 문서)

# UPSTREAM — 원본과 고친 곳

`workflow/`는 project-workflow를 llm-labs에 맞게 고친 사본이다. llm-labs의 연습은 이
사본만 따른다(INTENT 3절). 원본은 고치지 않는다.

## 1. 기준점

| 항목 | 값 |
| --- | --- |
| 원본 | `D:\projects\project-workflow` |
| 커밋 | `3311e8fa9a51d0291d967858794d3ca20ad14c16` (2026-09-24, "docs: 적대적 검증 모델 갱신과 실행별 제한 추가 (1.1~1.3)") |
| 복사일 | 2026-10-04 |
| 이후 반영 | 2026-10-04 원본의 **미커밋** 변경 `docs/ADVERSARIAL-REVIEW.md` 1.4(Codex 검토 모델 `gpt-6.1-sol`)를 그대로 다시 복사. 원본에서 커밋되면 그 커밋으로 이 표의 기준점을 갱신한다 |
| 복사한 것 | `WORKFLOW.md`, `docs/` 전체(`templates/` 포함) |
| 복사하지 않은 것 | 원본 레포 자체의 `README.md`·`BRIEF.md` (가이드가 아니라 원본 프로젝트의 문서) |

## 2. 왜 고쳤나

원본은 "저장소 하나 = 프로젝트 하나"를 전제로 한다. llm-labs는 독립된 연습 여러 개가 한
저장소에 모인 것이라, 원본을 그대로 따르면 저장소 전체에 버전이 하나로 묶인다. 2026-10-04
사용자 결정으로 다음 구조를 택했다.

- 저장소 루트와 `docs/`는 **버전 없는 워크스페이스 층**: `docs/INTENT.md`(공유 SSOT),
  `docs/ROADMAP.md`, `docs/DECISIONS.md`, `docs/refs/`(하드웨어·설치 가이드·연습 목록),
  `docs/labs/`(연습 플랜), 루트의 `AGENTS.md`·`CLAUDE.md`·`.claude/`, `workflow/`
- 연습 폴더 `NN-category/NN-name/`가 **프로젝트 층**: 연습마다 `v0.1`, `v0.2`…
- INTENT는 저장소 `docs/INTENT.md` 하나를 모든 연습이 공유한다. 연습 폴더에는 INTENT가 없다
- 공통 코드는 저장소에 두지 않고 쓰는 연습이 복사한다
- 저장소 문서를 `docs/`에 모으는 결정은 저장소 `docs/DECISIONS.md` R-14에 있다(2026-10-04)

## 3. 고친 곳

본문에서 고친 곳은 모두 **[llm-labs]** 로 표시했다. 각 문서의 버전 이력 표에도 `-llm-labs`
행을 붙였다.

| 파일 | 고친 곳 |
| --- | --- |
| `WORKFLOW.md` | **0절 신설**(두 층 구조, 원본 규칙 → llm-labs 대응표). 1절 가이드·INTENT 위치, 2절 이름 규칙, 3절 기획 자료, 4절 모드 판별, 5절 마감 노드, 6절 문서표, 7절 시작 절차(git·하네스 1회, 플랜 복사, ROADMAP), 8절 4번, 9절 저장소 구조, 10절 태그, 12절 실패 패턴, 13절 이력 |
| `docs/INIT.md` | 머리말(대상 = 연습 폴더), 0절 금지 3건, 1절 모드, 2절 전제, 4절 A·C 절차(11단계), 5절 B 확인·절차, 6절 하네스(루트 1회, 첫 줄), 7절 차단 증명, 9절 멈춤 규칙, 10절 이력 |
| `docs/VERSIONING.md` | 4절 마감 절차(태그 `<연습명>/vX.Y`, ROADMAP 갱신), INTENT 위치, 6절 승격(연습 전용 제약은 `.claude/rules/`), 출처 표기, 7절 README, 9절 검사 목록, 11절 이력 |
| `docs/DOC-SCHEMA.md` | 1절 버전 줄·루트 문서 표기·문서표, 2절 INTENT 위치, 9절 README 위치, 10절 검사 목록, 11절 이력 |
| `docs/HARNESS.md` | 2절 하네스는 루트 하나, 4절 hook 설명, 5절 차단 증명 4·5번 추가, 7절 이력 |
| `docs/PROMPTS.md` | 머리말에 바꿔 읽기 표, 3·7·8절에 연습 단위 예시, 12절 이력 |
| `docs/templates/claude/hooks/progress-check.mjs` | **로직 변경.** 연습 폴더별로 판정(그 연습의 `docs/` 밖 변경 ↔ 그 연습의 PROGRESS.md), 저장소 루트·`docs/` 파일은 판정 제외, `git status --porcelain -uall` |
| `docs/templates/CLAUDE.template.md` | 루트 CLAUDE.md용으로 다시 씀(공유 INTENT, 연습별 문서·PROGRESS, 태그, 다른 연습 수정 금지) |
| `docs/templates/AGENTS.template.md` | 구조 표를 두 층으로, 루트 AGENTS.md가 이미 있다는 안내 |
| `docs/templates/README.template.md` | INTENT 위치를 저장소 `docs/INTENT.md`로 |
| `docs/templates/INDEX.md` | 복사 위치(연습 폴더 / 저장소 루트 1회), gitignore 둘 다 합칠 수 있음 |
| (여러 파일) | **저장소 문서 위치.** INTENT·ROADMAP·DECISIONS를 저장소 `docs/`로, `refs/`를 `docs/refs/`·`docs/labs/`로 옮긴 데 맞춰 `WORKFLOW.md`(0·1·2·3·6·7·9·12·13절)·`INIT`·`VERSIONING`·`DOC-SCHEMA`·`PROMPTS`·`templates/`의 경로 문구를 바꿨다(2026-10-04) |
**고치지 않은 것**

| 파일 | 이유 |
| --- | --- |
| `docs/ADVERSARIAL-REVIEW.md` | 원본과 바이트 단위로 같다(사용자 조건). Codex 검토 모델 `gpt-6.1-sol`은 원본 1.4에서 바뀐 것을 다시 복사했다. `<REPO>`를 연습 폴더 경로로 읽는다는 점은 `WORKFLOW.md` 0절에 적었다 |
| `docs/templates/claude/hooks/guard.mjs` | `/docs/history/` 포함 여부로 판정하므로 연습 폴더 안의 history도 이미 막는다 |
| `docs/templates/claude/settings.template.json`, `claude/agents/reviewer.template.md`, `gitignore/*` | 바꿀 곳 없음 |

## 4. 원본 갱신을 반영하는 절차

자동으로 반영하지 않는다. 사람이 판단한다.

1. 원본의 새 커밋을 확인한다.
   ```
   git -C D:/projects/project-workflow log --oneline 3311e8f..HEAD
   git -C D:/projects/project-workflow diff 3311e8f..HEAD -- WORKFLOW.md docs/
   ```
2. 바뀐 곳마다 llm-labs에 반영할지 사용자에게 묻는다. **[llm-labs]** 로 고친 곳과 겹치면
   겹친다고 함께 보고한다.
3. 반영했으면 이 문서의 1절 커밋·복사일과 3절 표를 갱신한다.
4. `ADVERSARIAL-REVIEW.md`가 바뀌었으면 고치지 말고 그대로 다시 복사한다.

## 5. 검증

- 고친 사본에 대한 반대 벤더 적대적 검증은 사용자 결정(2026-10-04)으로 하지 않는다
- `progress-check.mjs`는 2026-10-04 임시 git 저장소에서 5가지 경우로 확인했다
  (루트만 변경 → 통과, 연습 코드만 변경 → 차단, PROGRESS 함께 변경 → 통과, 다른 연습 누락 →
  차단, 연습 docs만 변경 → 통과)
