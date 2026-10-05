import pytest

from prompt_playground.repro import compare_text, compare_with_earlier


def res(t=0.5, p=0.9, s=1, system="", response="답", thinking="생각", error=None):
    return {"variant": {"temperature": t, "top_p": p, "seed": s, "system": system}, "response": response, "thinking": thinking, "error": error}


def test_compare_text_same_and_first_difference_position():
    assert compare_text("가나다", "가나다") == {"same": True, "diff_at": None}
    assert compare_text("가나다", "가라다") == {"same": False, "diff_at": 2}
    assert compare_text("가나다", "나나다") == {"same": False, "diff_at": 1}


def test_compare_text_prefix_differs_at_length_plus_one():
    assert compare_text("가나", "가나다") == {"same": False, "diff_at": 3}
    assert compare_text("가나다", "가나") == {"same": False, "diff_at": 3}
    assert compare_text("", "가") == {"same": False, "diff_at": 1}


def test_first_of_a_group_has_nothing_to_compare():
    assert compare_with_earlier([res()], 0) is None


def test_same_condition_compares_answer_and_thinking_separately():
    rs = [res(), res(response="답", thinking="다른 생각")]
    out = compare_with_earlier(rs, 1)
    assert out["ref"] == 0
    assert out["response"] == {"same": True, "diff_at": None}
    assert out["thinking"] == {"same": False, "diff_at": 1}


@pytest.mark.parametrize("field, value", [("t", 0.6), ("p", 0.8), ("s", 2), ("system", "규칙")])
def test_any_differing_condition_field_means_no_comparison(field, value):
    assert compare_with_earlier([res(), res(**{field: value})], 1) is None


def test_compares_against_the_earliest_same_condition_result():
    rs = [res(s=1, response="A"), res(s=2, response="B"), res(s=1, response="A"), res(s=1, response="C")]
    assert compare_with_earlier(rs, 2)["ref"] == 0
    out = compare_with_earlier(rs, 3)
    assert out["ref"] == 0 and out["response"]["same"] is False


def test_five_identical_conditions_all_compare_to_the_first():
    rs = [res() for _ in range(5)]
    outs = [compare_with_earlier(rs, i) for i in range(5)]
    assert outs[0] is None
    assert all(o["ref"] == 0 and o["response"]["same"] and o["thinking"]["same"] for o in outs[1:])


def test_error_on_either_side_is_not_compared():
    out = compare_with_earlier([res(), res(error="타임아웃", response="")], 1)
    assert out["ref"] == 0 and "unavailable" in out and "response" not in out
    out = compare_with_earlier([res(error="x", response=""), res()], 1)
    assert "unavailable" in out
