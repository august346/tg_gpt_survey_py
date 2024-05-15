import enum
import json
import os
from typing import Optional

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage


GPT_MODEL_NAME = os.environ.get("GPT_MODEL_NAME", "gpt-4o")
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]


class GPT:
    class Role(enum.Enum):
        SYSTEM = "system"
        USER = "user"
        ASSISTANT = "assistant"

    @staticmethod
    def get_question(messages: list[dict], indexes: Optional[list[int]]) -> tuple[Optional[str], Optional[dict], int]:
        tools: dict = {} if indexes is None else {
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "set_param",
                        "description": "Set parameter value by index",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "index": {
                                    "type": "integer",
                                    "enum": indexes,
                                    "description": "Index of the parameter",
                                },
                                "value": {
                                    "type": "string",
                                    "description": "Parameter value"
                                }
                            },
                            "required": ["index", "value"]
                        }
                    }
                }
            ]
        }

        client = OpenAI(api_key=OPENAI_API_KEY)

        completion = client.chat.completions.create(
            messages=messages,
            model=GPT_MODEL_NAME,
            **tools,
        )

        message: ChatCompletionMessage = completion.choices[0].message
        tokens: int = completion.usage.total_tokens

        if message.tool_calls:
            call_list = []
            for call in message.tool_calls:
                call_list.append({"args": json.loads(call.function.arguments), "call_id": call.id})
            return None, {"calls": call_list, "message": message.model_dump()}, tokens

        return completion.choices[0].message.content, None, tokens
