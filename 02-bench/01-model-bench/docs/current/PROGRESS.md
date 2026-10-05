> 버전: v0.1 · 작성일: 2026-10-05

# PROGRESS — 02-01 model-bench

## 계획된 작업

### Phase 1 — 측정 CLI (완료)

- **무엇을 했나:** `pyproject.toml`·`.python-version`(3.13)과 `src/model_bench/`의 `bench.py`(측정·CSV 저장·읽기), `stats.py`(모델별 요약, 첫 실행값 제외), `__main__.py`(`python -m model_bench run` CLI)를 만들었다. `tests/test_bench.py`·`tests/test_stats.py`를 추가했다.
- **결과(코드):** 모델마다 앞서 올라간 모델을 `keep_alive: 0`으로 내리고(D-5) 올리기 전 VRAM을 기준값으로 적은 뒤, 프롬프트 3개 × 반복 3회를 `/api/generate`(`stream: false`, `num_ctx` 4096)로 측정한다(D-2·D-3·D-4). 행마다 `tok_s`·`prompt_tok_s`·`load_ms`·`vram_mib`·`baseline_vram_mib`·`processor`·`first_run`·`eval_count`·`error`가 CSV에 들어간다. `thinking` 능력이 있는 모델에만 `think=True`를 보낸다.
- **검증:** `uv run pytest` 9개 통과(가짜 클라이언트: 행 수·열·첫 실행 표시·`num_ctx`·`think` 전달 조건·이전 모델 내리기·오류 격리·CSV 왕복·평균에서 첫 실행 제외·VRAM 여유 판정). 실제 Ollama 0.35.1로 `python -m model_bench run`을 실행해 모델 6개 × 9호출 = 54행, 오류 0, `out/bench-phase1.csv`가 만들어졌다(`bge-m3`는 건너뜀). 요약(첫 실행 제외 평균 ± 표준편차, 모델 점유 VRAM, PROCESSOR): `qwen3:4b` 71.13±1.13 tok/s·3,048MiB·100% GPU, `qwen3:8b` 45.35±0.66·5,497·100% GPU, `exaone3.5:7.8b` 50.28±0.64·5,106·100% GPU, `gemma3:12b` 30.21±0.22·8,903·100% GPU, `qwen3:14b` 22.56±0.49·9,103·7%/93% CPU/GPU, `qwen3:30b` 20.90±2.84·8,608·50%/50% CPU/GPU. 측정 전 기준 VRAM은 1,339~2,201MiB로 모델마다 달랐다(화면 겸용 점유).
- **특이사항(구현 중 에이전트가 내린 판단. 사용자가 확인함, 2026-10-05):**
  - `bge-m3`는 임베딩 모델이라 `/api/generate`로 측정할 수 없어, `/api/show`의 `capabilities`에 `completion`이 없는 모델은 건너뛰고 건너뛴 모델을 출력한다. BRIEF의 "받은 모델 전부"에 대한 예외다. 사용자가 D-11로 기록하기로 했다(2026-10-05).
  - 한 호출이 너무 길어지지 않게 `num_predict` 256으로 자르고 `temperature` 0·`seed` 0으로 고정했다. 사용자가 이 값을 D-10으로 기록하기로 했다(2026-10-05).
  - CSV의 `vram_mib`는 호출 직후 `nvidia-smi` 사용량(절대값)이고, 표·차트의 VRAM은 거기서 기준값을 뺀 모델 점유량이다. 9,303MiB 여유선은 이 점유량과 비교한다.

### Phase 2 — 화면 표시 (완료)

- **무엇을 했나:** `webapp.py`(pywebview 창과 `Api`: 최신 CSV 불러오기, 측정 실행, 측정 중 진행 이벤트)와 `ui/index.html`(모델별 표와 Plotly 차트 두 개)을 만들었다. Plotly.js는 오프라인에서도 열리도록 `plotly-basic.min.js`(2.35.2)를 `ui/`에 내려받아 두었다. `tests/test_gui.py`(실제 창)를 썼다.
- **결과:** 창이 최신 `out/bench-*.csv`를 불러와 모델별 표(tok/s 평균·표준편차·VRAM·첫 로드·첫 실행 tok/s·기준 VRAM·측정 수·PROCESSOR)와 Plotly 차트 두 개(tok/s 막대 평균 ± 표준편차, VRAM 막대와 9,303MiB 여유선)를 그린다. 여유를 넘는 모델의 VRAM은 붉게 강조한다. "측정 실행" 버튼은 같은 측정을 창에서 돌려 CSV를 저장하고 결과를 갱신한다.
- **검증:** `uv run pytest` 11개 통과(실제 창 GUI 테스트: 가짜 CSV 3개 모델로 표 값·막대 3개·오차 막대·VRAM 막대 3개·여유선과 "9,303" 문구·여유 초과 강조 1개 확인, Api 시험: 측정 실행이 CSV를 저장하고 중복 실행을 거절). 실제 측정 CSV(54행)로 창을 띄워 표 6행이 위 수치로 표시되고 막대 6개·여유선 문구가 나오는 것을 확인했다. "측정 실행" 버튼(D-9)은 실제 창에서 실제 모델로 눌러 확인했다: 상태가 "측정 시작…"에서 "완료"로 바뀌고, 표 6행이 갱신되고, CSV가 저장되고, 버튼이 다시 활성화됐다. 리뷰어(`reviewer`)가 완료 조건은 모두 충족이라 판정하고 범위 초과 3건(버튼, `num_predict`·`temperature`·`seed` 고정, `bge-m3` 제외)을 지적했다. 버튼은 사용자가 두기로 해 D-9로 기록했다. 나머지 둘도 사용자가 D-10·D-11로 기록하기로 했다.
- **특이사항:** 창을 만들 때 `Windows fatal exception: code 0x8001010d` 스택 덤프가 로그에 섞이지만 테스트는 통과한다(01-02와 같은 WinForms COM 소음으로 보이며 원인은 확인하지 않았다). 표의 tok/s는 소수 둘째 자리까지 고정해 표시한다.

## 계획 외 개선

### 측정 결과 요약 문서 남기기

- **요청:** `out/`이 `.gitignore`라 측정 CSV가 저장소에 남지 않으니, 결과 요약을 문서로 남겨 달라(사용자, 2026-10-05). CSV 자체를 커밋하는 안과 남기지 않는 안은 택하지 않았다.
- **조치:** `docs/refs/bench-results.md`를 만들었다(측정 조건, 모델별 표, 해석할 때 주의).
- **결과:** 모델 6개의 tok/s(평균 ± 표준편차)·점유 VRAM·PROCESSOR·첫 로드·첫 호출 tok/s·기준 VRAM이 이 문서에 있다. `01-hardware.md` 예상값은 고치지 않았다.
- **검증:** 표의 수치를 `out/bench-phase1.csv`를 `summarize`한 값(위 Phase 1 검증 항목)과 대조해 옮겼다.
