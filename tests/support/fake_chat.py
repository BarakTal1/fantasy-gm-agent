"""A minimal scripted chat model for deterministic agent tests.
It replays a fixed list of AIMessages; if a message has tool_calls, the agent
runs the tool and calls the model again, advancing to the next scripted message.
"""
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class FakeToolCallingModel(BaseChatModel):
    responses: list[AIMessage]
    i: int = 0

    @property
    def _llm_type(self) -> str:
        return "fake-tool-calling"

    def _generate(self, messages: list[BaseMessage], stop=None,
                  run_manager: CallbackManagerForLLMRun | None = None,
                  **kwargs: Any) -> ChatResult:
        msg = self.responses[min(self.i, len(self.responses) - 1)]
        self.i += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def bind_tools(self, tools, **kwargs):  # create_react_agent calls this
        return self
