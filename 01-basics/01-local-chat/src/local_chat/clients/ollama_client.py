"""공식 ollama 파이썬 클라이언트."""

import httpx
import ollama

from .events import CONNECTION, OTHER, Error, Message, Thinking, Token, classify, make_done, make_timeout, thinking_text


class OllamaClient:
    name = "ollama"

    def __init__(self, host: str = "http://localhost:11434", read_timeout: float = 300.0):
        self.host = host
        self._client = ollama.Client(host=host, timeout=make_timeout(read_timeout))

    def stream(self, messages: list[Message], *, model: str, options: dict, think: bool = False):
        stream = None
        try:
            stream = self._client.chat(model=model, messages=messages, options=options, think=think, stream=True)
            for chunk in stream:
                thought = thinking_text(chunk.message.thinking)
                if thought and think:  # think=False면 사고 과정은 오지 않는 것이 계약이다. 와도 내보내지 않는다
                    yield Thinking(thought)
                piece = chunk.message.content
                if piece:
                    yield Token(piece)
                if chunk.done:
                    yield make_done(chunk.eval_count, chunk.eval_duration)
                    return
            yield Error(OTHER, "응답이 done 없이 끝났다")
        except ollama.ResponseError as e:
            yield Error(classify(e.status_code, e.error), str(e.error))
        except ollama.RequestError as e:
            yield Error(OTHER, str(e))
        except (ConnectionError, httpx.TransportError) as e:
            yield Error(CONNECTION, str(e) or type(e).__name__)
        except (ValueError, TypeError, AttributeError) as e:
            yield Error(OTHER, f"응답을 해석하지 못했다: {e!r}")
        finally:
            if stream is not None:
                stream.close()
