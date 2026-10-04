workflow/ (project-workflow 3311e8f의 llm-labs 사본) 기준으로 초기화됨 (YYYY-MM-DD)

# llm-labs에서 지킬 것

- 저장소 `docs/INTENT.md`는 모든 연습이 공유하는 SSOT다. 사람의 요청으로만 고친다. 연습 폴더에 INTENT를 만들지 않는다
- 버전은 연습마다 따로다. 연습의 버전 문서는 `NN-category/NN-name/docs/current/`에 있고 사람이 쓴다. **고치지 않는다**
- 문서가 `INTENT.md`에 어긋나면 혼자 맞추지 말고 멈추고 보고한다
- major·minor 버전 번호는 사람이 정한다. 스스로 올리지 않는다. 태그는 `<연습명>/vX.Y`
- `backlog.json`은 CLI로만 바꾼다. 직접 편집하지 않는다
- 진행 중에 task를 추가하지 않는다. 계획 밖 작업은 그 연습의 `docs/current/PROGRESS.md`에 적는다
- task를 닫을 때마다 그 연습의 `PROGRESS.md`에 무엇을·결과·검증을 남긴다
- `docs/history/` 아래는 읽기만 한다. 수정도 삭제도 하지 않는다
- 완료 조건은 그 연습의 `PLAN.md`·`backlog.json`에 적힌 것으로 판정한다. 스스로 정하지 않는다
- 다른 연습 폴더를 고치지 않는다. 공통 코드가 필요하면 복사해 온다
- 되돌릴 수 없는 작업(배포·삭제·외부 상태 변경)은 먼저 묻는다

<!--
아래에 모든 연습에 걸리는 제약을 추가한다.
버전 마감 때 DECISIONS.md에서 승격된 것이 여기 들어온다. 출처를 남긴다.
한 연습에만 걸리는 제약은 여기가 아니라 그 연습 경로의 .claude/rules/로 간다.

- torch 버전을 올리지 않는다 (01-01-local-chat v0.1 D-3)

5~15줄을 넘기지 않는다. 길어지면 안 읽힌다.
설명과 배경은 여기 쓰지 않는다. 근거는 그 버전 DECISIONS.md에 있다.
-->
