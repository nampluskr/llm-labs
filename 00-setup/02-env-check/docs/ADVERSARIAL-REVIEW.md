# ADVERSARIAL-REVIEW — 반대 벤더 적대적 검증

**구현한 모델이 자기 결과를 판정하지 않게 한다.** Phase를 닫기 전에, 구현자와
**다른 벤더의 모델**에게 "이걸 깨 보라"고 시킨다.

`HARNESS.md` 4절의 세션 내 리뷰어와는 다른 층이다(2절). `PLAN.md`의 "적대적 검증"
절이 이 문서를 가리킨다(`DOC-SCHEMA.md` 6절).

---

## 1. 왜 필요한가

에이전트는 **자기가 만든 것을 통과시키는 쪽으로 실수한다.** 실패 유형이 셋이다.

| 유형 | 어떻게 나타나나 |
| --- | --- |
| 자기 채점 | 완료 조건을 스스로 판정하고 "충족"이라고 적는다. 근거는 자기 구현이다 |
| 검사가 실체를 안 본다 | 테스트는 전건 통과하는데 기능이 실제로 연결돼 있지 않다. stub·mock이 조건을 대신 만족시킨다 |
| 같은 눈으로 두 번 보기 | 같은 모델이 검토하면 구현할 때 놓친 것을 검토할 때도 놓친다. 같은 사전 확률을 공유하기 때문이다 |

세션 내 리뷰어(`HARNESS.md` 4절)는 1번과 2번을 상당히 잡지만 **3번을 못 잡는다.**
같은 모델·같은 세션 맥락이라서다. 벤더를 바꾸면 그 상관이 끊긴다.

**전제는 하나다 — "통과"를 기본값으로 두지 않는다.** 근거를 대지 못하면 미충족이다.

---

## 2. 두 층을 구분한다

혼동하기 쉬우므로 표로 못 박는다. **둘 다 한다.** 하나가 다른 하나를 대신하지 않는다.

| | 세션 내 리뷰어 | 반대 벤더 검토 |
| --- | --- | --- |
| 어디 | `.claude/agents/reviewer` | 별도 CLI 프로세스 |
| 누구 | 같은 벤더·같은 세션 | **다른 벤더의 모델** |
| 무엇을 보나 | 완료 조건 충족, 요구 ID 대조, **범위 초과** | 코드를 깨는 것. 재현 조건과 위반 조항 |
| 언제 | Phase 구현 직후 | 세션 내 리뷰어를 통과한 뒤 |
| 비용 | 낮다 | 높다 (외부 CLI 호출) |
| 정의 | `HARNESS.md` 4절 | 이 문서 |

순서는 **hook → 세션 내 리뷰어 → 반대 벤더**다. 앞의 둘이 잡을 것을 잡고 남은 것만
비싼 검토로 보낸다.

---

## 3. 언제 하나 — 적용 대상

**새 과제 구현과 리팩토링에는 반드시 한다.**

| 상황 | 적용 | 공격 초점 |
| --- | --- | --- |
| 새 기능 Phase | **필수** | 완료 조건이 실제로 충족되나. 경계·실패·빈 상태에서 깨지나 |
| **리팩토링** | **필수** | **동작이 바뀌지 않았나.** 겉보기 구조만 바뀌고 관측 가능한 결과가 같은지 |
| 문서 검증 (`SPEC`·`PLAN` 정합성) | 선택 | 요구 ID 누락, `INTENT`와의 어긋남 |
| 오타·주석·서식만 고친 변경 | 안 한다 | — |

**리팩토링이 특히 중요하다.** 리팩토링은 "동작은 그대로"가 전제인데, 그 전제를 구현자
자신이 판정하면 검증이 성립하지 않는다. 리팩토링 Phase의 공격 초점은 항상 **변경 전후의
관측 가능한 동작 차이**이며, 검토자에게 "이 변경으로 달라지는 사용자 동작을 하나라도
찾아라"를 준다.

`PLAN.md`는 **필수 통과 Phase**를 지정한다 — 미해결 Critical이 있으면 다음 Phase로
진행하지 못하는 Phase다. 나머지 Phase도 검증은 하되 진행을 막지는 않는다. 무엇을
필수로 둘지는 **사람이 정한다.**

---

## 4. 절차

각 Phase의 구현과 세션 내 리뷰어 검토를 마친 뒤:

### 1) 반대 벤더 CLI에 위임한다

검토자는 **마지막 실질 구현자의 반대 벤더**다.

| 구현 | 검토 |
| --- | --- |
| Claude Code | Codex `gpt-6.1-sol` |
| Codex | Claude `opus-5.5` |

토큰 한도로 구현자가 Phase 중간에 바뀌면 **마지막 실질 구현자**를 기준으로 다시 정한다.

### 2) 검토자를 제약한다

검토자는 **제품 소스 파일, 해당 Phase의 공격 초점, 관련 `PLAN` 조항만** 사용한다.
파일을 수정하지 않는다.

**주지 않는 것** — 구현 세션 대화, 구현 판단 근거, 문서·설정·실험 산출물, Git
상태·이력·원격, 셸 도구. 구현자의 논리에 오염되면 벤더를 바꾼 뜻이 없어진다.

지적은 `Critical` / `Major` / `Minor`, **정확한 재현 조건**, **위반한 `PLAN` 조항**을
포함해 심각도순으로 반환한다.

### 3) 보완한다

- **Critical은 전부 수정**하고 관련 검증을 재실행한다.
- Major·Minor는 **처리 여부와 근거를 기록**한다. 안 고쳐도 되지만 침묵하지 않는다.
- Critical을 수정했으면 **같은 반대 벤더 검토를 한 번 더** 실행해 해소를 확인한다.

### 4) Verification Attempt Limit — 3회

하나의 검증 대상(Phase 1개 또는 문서 1개)에 대한 검토 CLI 실행은 **실패·오류·프롬프트
재작성·보완 후 재검증을 모두 포함해 최대 3회**다. 보완 사이클을 따로 세지 않는다.
각 실행은 **최대 30분, 최대 3턴**으로 제한한다. 시간 초과·턴 초과로 중단된 실행도
3회 한도에 포함한다. 실행별 소요 시간과 턴 수를 검토 기록에 남긴다.

3회를 소진하면 추가 실행 대신 **마지막 유효 검토 결과, 반영한 보완, 미해결 지적과 남은
위험**을 기록하고 사용자에게 보고한다. 그 시점에 미해결 Critical이 남아 있으면 **다음
Phase로 진행하지 않고 사용자 판단을 요청한다.**

### 5) 기록한다

`docs/reviews/A{n}.md`에 남긴다. 양식은 6절.

### 6) CLI가 없으면

필요한 반대 벤더 CLI를 쓸 수 없으면 **오류와 대체 검증안을 사용자에게 보고하고,
승인 없이 생략하지 않는다.** 모델 접근이 거부될 때도 **기본 모델로 조용히 폴백하지
않는다.**

---

## 5. 헤드리스 명령어

`<REPO>` = 검토 대상 저장소의 절대 경로. `<PROMPT>` = 아래 템플릿을 치환한 문자열.

### Codex 검토 (Claude Code 구현 대상)

```
codex.cmd exec --model gpt-6.1-sol --sandbox read-only --cd "<REPO>" "<PROMPT>"
```

### Claude 검토 (Codex 구현 대상)

```
claude -p "<PROMPT>" --model claude-opus-5-5 --safe-mode --allowedTools "Read,Glob,Grep" --disallowedTools "Edit,Write,Bash" --permission-mode dontAsk --max-turns 3 --output-format json --no-session-persistence
```

- 호출자가 각 CLI 실행에 30분 시간 제한을 적용하고, 초과하면 프로세스를 종료한다.
  Claude는 `--max-turns 3`을 사용한다. Codex `exec`에는 턴 수 제한 옵션이 없으므로
  단일 프롬프트 실행(1턴)만 사용하고 `resume` 등 후속 턴을 이어가지 않는다.
  필요하면 `--max-budget-usd`로 Claude 호출별 비용 상한을 둔다.
- 문서 검증일 때만 검토자가 상위 문서·`AGENTS.md`를 읽도록 읽기 전용 셸(`cat`,
  `sed -n`)을 허용한다. 코드 검증에서는 셸을 주지 않는다.
- **모델 이름은 이 문서 작성 시점의 것이다.** 벤더의 최상위 모델이 바뀌면 여기를
  갱신하고 7절 버전 이력에 적는다. 규칙은 이름이 아니라 "구현자의 반대 벤더"다.

### 프롬프트 템플릿

`<Phase>` · `<changed-files>` · `<adversarial-focus>` · `<plan-refs>`를 치환한다.

```
You are an adversarial reviewer for <Phase>. Your job is to break this code, not to
confirm it works. Review only these product source files: <changed-files>. Attack these
specific points: <adversarial-focus>. Validate against these PLAN clauses: <plan-refs>.
Do not inspect Git status, branches, remotes, or commit history, and do not use shell
tools. For each finding, report severity (Critical/Major/Minor), exact reproduction
conditions, and the violated PLAN clause. Order findings by severity. Do not modify
any file.
```

**리팩토링 Phase의 `<adversarial-focus>`** 는 항상 동작 동등성으로 잡는다. 예:

```
Find any user-observable behavior that differs before and after this refactoring:
return values, error paths, ordering, lifecycle (creation/disposal counts), and
state that survives across calls. Assume the refactoring claims no behavior change.
```

---

## 6. 검토 기록 양식 — `docs/reviews/A{n}.md`

```
# A{n} — <프로젝트> Phase <n> 적대적 검증

- 구현자: Claude Code | Codex
- 검토 모델: gpt-6.1-sol | opus-5.5
- 대상 파일: ...
- 관련 PLAN 조항: ...
- 실행 회차: 1/3, 2/3, ... (각 회차: 일시, 소요 시간, 턴 수, 유효 여부, 사유)

## 지적

| # | 심각도 | 요약 | 재현 조건 | 위반 조항 | 처리 |
| --- | --- | --- | --- | --- | --- |

## 유효하지 않은 지적과 반박 근거

## 미해결 · 남은 위험
```

**유효하지 않은 지적의 반박 근거를 반드시 남긴다.** 이것이 없으면 다음 Phase에서 같은
지적이 다시 나왔을 때 판정을 처음부터 다시 한다.

**미충족이 하나라도 있으면 Phase를 닫지 않는다.**

---

## 7. 흔한 실패

- **검토자에게 구현 세션 맥락을 준다.** 편해 보이지만 검토자가 구현자의 논리를 그대로
  받아들인다. 벤더를 바꾼 효과가 사라진다.
- **모델 접근이 거부됐는데 기본 모델로 폴백한다.** 같은 벤더가 검토하게 되어 3번 실패
  유형(같은 눈으로 두 번 보기)이 그대로 남는데, 기록에는 "검증함"으로 남는다.
- **Major·Minor를 침묵으로 넘긴다.** 안 고치는 것은 되지만 근거 없이 넘기면 나중에
  그것이 결정이었는지 누락이었는지 구별되지 않는다.
- **3회 제한을 세지 않는다.** 프롬프트를 고쳐 가며 통과할 때까지 돌리면 검증이 아니라
  튜닝이다.
- **리팩토링에서 "테스트가 통과하니 동작이 같다"고 본다.** 테스트가 덮지 않는 동작이
  바뀐 것을 못 잡는다. 공격 초점을 동작 동등성으로 명시해 검토자가 테스트 밖을 보게 한다.

---

## 8. 버전 이력

| 버전 | 변경 |
| --- | --- |
| 1.0 | 최초 작성. `backlog`·`speech_transcriber`의 `docs/ADVERSARIAL-REVIEW.md`(2026-08-28)를 방법론 층으로 일반화. 세션 내 리뷰어와의 층 구분(2절), 적용 대상과 리팩토링 규정(3절), 흔한 실패(7절)를 추가 |
| 1.1 | Codex 검토 모델을 `gpt-5.6-sol`에서 `gpt-6-sol`로 변경. 검토자 표, CLI 명령, 기록 양식을 갱신 |
| 1.2 | 검토 대상별 실행 3회 한도를 유지하고 실행별 시간 30분·턴 3회 제한과 기록 항목을 추가 |
| 1.3 | Claude 검토 모델을 `opus-5`에서 `opus-5.5`로 변경. 검토자 표, CLI 명령(`--model claude-opus-5-5`로 고정), 기록 양식을 갱신 |
| 1.4 | Codex 검토 모델을 `gpt-6-sol`에서 `gpt-6.1-sol`로 변경. 검토자 표, CLI 명령, 기록 양식을 갱신 |
