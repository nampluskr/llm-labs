"""생성 옵션 검증. 범위 밖 값은 조용히 고치지 않고 거절한다."""

import math

NUM_CTX_RANGE = (4096, 8192)  # D-5: 기본 4096, 설정에서 8192까지
TEMPERATURE_RANGE = (0.0, 2.0)


def _is_number(v) -> bool:
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return False
    try:
        return math.isfinite(v)
    except OverflowError:  # float으로 바꿀 수 없을 만큼 큰 정수
        return False


def validate_options(num_ctx, temperature) -> dict:
    """올바르면 {"num_ctx": int, "temperature": float}를 돌려주고, 아니면 ValueError(사람이 읽을 문구)."""
    if not _is_number(num_ctx) or int(num_ctx) != num_ctx:
        raise ValueError("num_ctx는 정수여야 한다")
    if not NUM_CTX_RANGE[0] <= num_ctx <= NUM_CTX_RANGE[1]:
        raise ValueError(f"num_ctx는 {NUM_CTX_RANGE[0]}~{NUM_CTX_RANGE[1]} 사이여야 한다")
    if not _is_number(temperature):
        raise ValueError("temperature는 숫자여야 한다")
    if not TEMPERATURE_RANGE[0] <= temperature <= TEMPERATURE_RANGE[1]:
        raise ValueError(f"temperature는 {TEMPERATURE_RANGE[0]}~{TEMPERATURE_RANGE[1]} 사이여야 한다")
    return {"num_ctx": int(num_ctx), "temperature": float(temperature)}
