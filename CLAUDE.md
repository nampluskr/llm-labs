workflow/ (project-workflow 3311e8f의 llm-labs 사본) 기준으로 초기화됨 (2026-10-04)

@AGENTS.md

# llm-labs에서 지킬 것

- 저장소 `docs/INTENT.md`는 모든 연습이 공유하는 SSOT다. 사람의 요청으로만 고친다. 연습 폴더에 INTENT를 만들지 않는다
- 버전은 연습마다 따로다. 연습의 버전 문서는 `NN-category/NN-name/docs/current/`에 있고 사람이 쓴다. **고치지 않는다**
- 문서가 `INTENT.md`에 어긋나면 혼자 맞추지 말고 멈추고 보고한다
- major·minor 버전 번호는 사람이 정한다. 스스로 올리지 않는다. 태그는 `<연습명>/vX.Y`
- 진행 중에 task를 추가하지 않는다. 계획 밖 작업은 그 연습의 `docs/current/PROGRESS.md`에 적는다
- task를 닫을 때마다 그 연습의 `PROGRESS.md`에 무엇을·결과·검증을 남긴다
- `docs/history/` 아래는 읽기만 한다. 수정도 삭제도 하지 않는다
- 완료 조건은 그 연습의 `PLAN.md`에 적힌 것으로 판정한다. 스스로 정하지 않는다
- 다른 연습 폴더를 고치지 않는다. 공통 코드가 필요하면 복사해 온다
- 되돌릴 수 없는 작업(배포·삭제·외부 상태 변경)은 먼저 묻는다
- 모델을 바꾸는 코드는 이전 모델을 바로 내린다(`keep_alive: 0`). 두 모델이 VRAM에 겹치면 11GB를 넘길 수 있다 (01-01-local-chat v0.1 D-6)
- 사고 과정을 지원하는 모델(`/api/show`의 `capabilities`에 `thinking`)은 `think=True`로 사고 과정을 분리해 받는다. `think=False`를 믿지 않는다(`qwen3:4b`는 무시하고 추론이 답에 섞인다). 지원하지 않는 모델에는 `think=True`를 보내지 않는다(400) (01-01-local-chat v0.1 D-10)
