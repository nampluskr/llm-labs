> 버전: v0.1 · 작성일: 2026-10-05

# PLAN — 02-01 model-bench

`SPEC`이 없어서 대응 요구는 `BRIEF.md` 5절의 완료 조건 번호를 가리킨다.

## Phase 인덱스

### Phase 1 — 측정 CLI

- **목적:** 받은 모델 전부를 측정해 결과를 CSV로 저장한다.
- **대응 요구:** BRIEF 완료 조건 1, 3
- **완료 조건:** 받은 모델 전부(`qwen3:30b` 포함)를 프롬프트 3개 × 반복 3회로 측정해 CSV를 만든다. 행마다 `tok/s`·`load_ms`·`VRAM_MiB`·`PROCESSOR`, 첫 실행 표시, 측정 전 기준 VRAM이 있다.

### Phase 2 — 화면 표시

- **목적:** 측정 결과를 pywebview 화면에 표와 차트로 보여 준다.
- **대응 요구:** BRIEF 완료 조건 1, 2
- **완료 조건:** pywebview 화면에 모델별 tok/s·VRAM 표가 나오고, 모델별 tok/s 막대(평균 ± 표준편차), 모델별 VRAM 막대, 9,303MiB 여유선이 Plotly 차트로 그려진다.

## 적대적 검증

이 연습은 반대 벤더 적대적 검증을 하지 않는다. 사용자가 이 연습에 한정한 예외로 정했다(저장소 `docs/DECISIONS.md` R-17, R-16과 같은 방식, 2026-10-05). 절차(`workflow/docs/ADVERSARIAL-REVIEW.md`)는 적용하지 않는다.

| 필드 | 내용 |
| --- | --- |
| 필수 통과 Phase | 없음 |
| Phase 1 공격 초점 | 해당 없음(R-17) |
| Phase 2 공격 초점 | 해당 없음(R-17) |
