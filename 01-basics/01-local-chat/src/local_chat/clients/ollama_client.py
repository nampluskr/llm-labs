"""공식 ollama 파이썬 클라이언트."""

import httpx
import ollama

from .events import CONNECTION, OTHER, Error, Message, Token, make_done
from .http_client import classify


class OllamaClient:
    name = "ollama"

    def __init__(self, host: str = "http://localhost:11434"):
        self._client = ollama.Client(host=host)

    def stream(self, messages: list[Message], *, model: str, options: dict):
        stream = None
        try:
            stream = self._client.chat(model=model, messages=messages, options=options, think=False, stream=True)
            for chunk in stream:
                piece = chunk.message.content
                if piece:
                    yield Token(piece)
                if chunk.done:
                    yield make_done(chunk.eval_count, chunk.eval_duration)
                    return
            yield Error(OTHER, "응답이 done 없이 끝났다")
        except ollama.ResponseError as e:
            yield Error(classify(e.status_code, e.error), e.error)
        except (ConnectionError, httpx.TransportError) as e:
            yield Error(CONNECTION, str(e) or type(e).__name__)
        except (ValueError, TypeError, AttributeError) as e:
            yield Error(OTHER, f"응답을 해석하지 못했다: {e!r}")
        finally:
            if stream is not None:
                stream.close()
