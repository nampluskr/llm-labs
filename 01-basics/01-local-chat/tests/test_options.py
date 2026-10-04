import math

import pytest

from local_chat.options import NUM_CTX_RANGE, TEMPERATURE_RANGE, validate_options


def test_범위_안의_값은_그대로_받는다():
    assert validate_options(4096, 0.7) == {"num_ctx": 4096, "temperature": 0.7}
    assert validate_options(8192, 0) == {"num_ctx": 8192, "temperature": 0.0}
    assert validate_options(6000, 2) == {"num_ctx": 6000, "temperature": 2.0}
    assert validate_options(5120.0, 1.5) == {"num_ctx": 5120, "temperature": 1.5}  # 정수로 떨어지는 실수는 정수로


@pytest.mark.parametrize("num_ctx", [4095, 8193, 0, -1, 32768, 4096.5, "4096", None, True, math.nan, math.inf, [4096]])
def test_num_ctx가_범위_밖이거나_정수가_아니면_거절한다(num_ctx):
    with pytest.raises(ValueError, match="num_ctx"):
        validate_options(num_ctx, 0.7)


@pytest.mark.parametrize("temperature", [-0.1, 2.1, 100, "0.7", None, True, math.nan, math.inf, -math.inf])
def test_temperature가_범위_밖이거나_숫자가_아니면_거절한다(temperature):
    with pytest.raises(ValueError, match="temperature"):
        validate_options(4096, temperature)


def test_경계값은_받는다():
    assert validate_options(NUM_CTX_RANGE[0], TEMPERATURE_RANGE[0]) == {"num_ctx": 4096, "temperature": 0.0}
    assert validate_options(NUM_CTX_RANGE[1], TEMPERATURE_RANGE[1]) == {"num_ctx": 8192, "temperature": 2.0}
