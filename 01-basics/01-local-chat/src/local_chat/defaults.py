"""콘솔과 앱이 같이 쓰는 기본값."""

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:8b"  # D-4
DEFAULT_OPTIONS = {"num_ctx": 4096, "temperature": 0.7}  # D-5
SYSTEM_PROMPT = "너는 간결하게 한국어로 답하는 도우미다."
