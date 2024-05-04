import enum
import json
import os
from typing import Optional

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage

GPT_MODEL_NAME = os.environ.get("GPT_MODEL_NAME", "gpt-4")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


class GPT:
    class Role(enum.Enum):
        SYSTEM = "system"
        USER = "user"
        ASSISTANT = "assistant"

    @staticmethod
    def get_question(messages: list[dict], params: Optional[str]) -> tuple[Optional[str], Optional[dict]]:
        tools: dict = {} if params is None else {
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "set_params",
                        "description": "Set or update parameter by index for {}".format(params),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "to_set": {
                                    "type": "array",
                                    "description": "params to set or update",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "index": {
                                                "type": "integer",
                                                "description": "Index of the parameter"
                                            },
                                            "value": {
                                                "type": "string",
                                                "description": "Value to set or update at the index"
                                            }
                                        }
                                    }
                                }
                            },
                            "required": ["to_set"]
                        }
                    }
                }
            ]
        }

        completion = client.chat.completions.create(
            messages=messages,
            model=GPT_MODEL_NAME,
            **tools,
        )

        message: ChatCompletionMessage = completion.choices[0].message
        if message.tool_calls:
            args = json.loads(message.tool_calls[0].function.arguments)
            return None, {"params": args["to_set"]}

        return completion.choices[0].message.content, None
