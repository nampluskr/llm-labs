"""같은 조건으로 실행한 결과끼리 출력이 글자 단위로 같은지 비교한다(Phase 3).

같은 조건 = `temperature`·`top_p`·`seed`·시스템 프롬프트가 모두 같다. 하나라도 다르면 출력이 달라지는 것이
정상이라 재현성 비교 대상이 아니다. 답(`response`)과 사고 과정(`thinking`)을 따로 비교한다(02-05가
"답이 같았나"와 "생성 과정 전체가 같았나"를 가려 쓸 수 있게)."""

CONDITION_FIELDS = ("temperature", "top_p", "seed", "system")


def condition(result: dict) -> tuple:
    v = result["variant"]
    return tuple(v[f] for f in CONDITION_FIELDS)


def compare_text(a: str, b: str) -> dict:
    """글자 단위 비교. 다르면 처음 달라지는 글자의 위치(1부터)를 준다. 한쪽이 다른 쪽의 앞부분이면 짧은 쪽 길이 + 1이다."""
    if a == b:
        return {"same": True, "diff_at": None}
    n = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return {"same": False, "diff_at": n + 1}


def compare_with_earlier(results: list[dict], index: int) -> dict | None:
    """results[index]를 같은 조건의 가장 앞선 결과와 비교한다. 같은 조건의 앞선 결과가 없으면 None.
    둘 중 하나라도 오류였으면 비교하지 않고 이유를 돌려준다."""
    current = results[index]
    key = condition(current)
    ref = next((i for i in range(index) if condition(results[i]) == key), None)
    if ref is None:
        return None
    if current["error"] or results[ref]["error"]:
        return {"ref": ref, "unavailable": "오류가 난 실행이 있어 비교할 수 없다"}
    return {
        "ref": ref,
        "response": compare_text(results[ref]["response"], current["response"]),
        "thinking": compare_text(results[ref]["thinking"], current["thinking"]),
    }
