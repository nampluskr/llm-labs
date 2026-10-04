"""langchain-ollama의 ChatOllama.

stream()은 통계가 든 청크(response_metadata["done"])를 낸 뒤 내용 없는 청크를 하나 더 낸다.
그래서 마지막 청크가 아니라 done 청크에서 통계를 읽고, 그 시점에 끝낸다.
"""

import httpx
import ollama
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from .events import CONNECTION, OTHER, Error, Message, Token, make_done
from .http_client import classify

_ROLES = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}


class LangchainClient:
    name = "langchain"

    def __init__(self, host: str = "http://localhost:11434"):
        self._host = host

    def stream(self, messages: list[Message], *, model: str, options: dict):
        stream = None
        try:
            llm = ChatOllama(
                model=model,
                base_url=self._host,
                reasoning=False,
                num_ctx=options.get("num_ctx"),
                temperature=options.get("temperature"),
            )
            stream = llm.stream([_ROLES[m["role"]](m["content"]) for m in messages])
            for chunk in stream:
                if chunk.content:
                    yield Token(chunk.content)
                meta = chunk.response_metadata
                if meta.get("done"):
                    yield make_done(meta.get("eval_count"), meta.get("eval_duration"))
                    return
            yield Error(OTHER, "응답이 done 없이 끝났다")
        except ollama.ResponseError as e:
            yield Error(classify(e.status_code, e.error), e.error)
        except (ConnectionError, httpx.TransportError) as e:
            yield Error(CONNECTION, str(e) or type(e).__name__)
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            yield Error(OTHER, f"응답을 해석하지 못했다: {e!r}")
        finally:
            if stream is not None:
                stream.close()
